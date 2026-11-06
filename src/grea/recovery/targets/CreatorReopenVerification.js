'use strict';

// Read-only native-file capture plus create-only additive receipts. The caller
// supplies a callback that invokes CreatorScene.readSaved on the saved scene.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const POINTER_RELATIVE = 'Analysis/Readback/current-revision.json';
const REVISION_RE = /^Analysis\/Readback\/reopened-([1-9][0-9]*)\.json$/;
const SHA_RE = /^[0-9a-f]{64}$/;
const ORIGIN_PATHS = new Set(['Analysis/Readback/editor-readback.json', 'Analysis/editor-readback.json']);
const NATIVE_ROOTS = new Set(['assets/Game', 'assets/resources']);
const MAX_RECEIPT_BYTES = 128 * 1024 * 1024;

function fail(code) { throw new Error(code); }
function sha(bytes) { return crypto.createHash('sha256').update(bytes).digest('hex'); }
function validSha(value) { return typeof value === 'string' && SHA_RE.test(value); }
function isObject(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }

function safeRelative(relative, label, allowOrigin = false) {
    if (typeof relative !== 'string' || !relative || relative.includes('\\') || relative.includes('\0') ||
        path.posix.isAbsolute(relative)) fail('CREATOR_REOPEN_UNSAFE_PATH:' + label);
    const parts = relative.split('/');
    if (parts.some(part => !part || part === '.' || part === '..')) fail('CREATOR_REOPEN_UNSAFE_PATH:' + label);
    if (REVISION_RE.test(relative) || relative === POINTER_RELATIVE || (allowOrigin && ORIGIN_PATHS.has(relative)))
        return relative;
    fail('CREATOR_REOPEN_PATH_NOT_ALLOWED:' + label);
}

function inside(root, relative) {
    const base = path.resolve(root), full = path.resolve(base, ...relative.split('/'));
    if (full !== base && !full.startsWith(base + path.sep)) fail('CREATOR_REOPEN_PATH_ESCAPES:' + relative);
    let current = base;
    for (const part of relative.split('/')) {
        current = path.join(current, part);
        if (fs.existsSync(current) && fs.lstatSync(current).isSymbolicLink()) fail('CREATOR_REOPEN_SYMLINK:' + relative);
    }
    return full;
}

function readBytes(root, relative) {
    const full = inside(root, relative);
    if (!fs.existsSync(full)) fail('CREATOR_REOPEN_FILE_MISSING:' + relative);
    const stat = fs.statSync(full);
    if (!stat.isFile() || stat.size > MAX_RECEIPT_BYTES) fail('CREATOR_REOPEN_FILE_INVALID:' + relative);
    return fs.readFileSync(full);
}

function parseObject(bytes, label) {
    let value;
    try { value = JSON.parse(bytes.toString('utf8')); } catch (_) { fail('CREATOR_REOPEN_JSON_INVALID:' + label); }
    if (!isObject(value)) fail('CREATOR_REOPEN_JSON_SHAPE:' + label);
    return value;
}

function validateIdentity(receipt, manifestSha256, sourcePlanSha256, projectUuid, sceneUuid) {
    if (receipt.manifestSha256 !== manifestSha256) fail('CREATOR_REOPEN_MANIFEST_MISMATCH');
    if (receipt.projectUuid !== projectUuid) fail('CREATOR_REOPEN_PROJECT_MISMATCH');
    if (receipt.sceneUuid !== sceneUuid) fail('CREATOR_REOPEN_SCENE_MISMATCH');
    if (receipt.sourcePlanSha256 && receipt.sourcePlanSha256 !== sourcePlanSha256)
        fail('CREATOR_REOPEN_PLAN_MISMATCH');
}

function validateCurrentPointer(root, pointer, originPath, originSha, manifestSha256, sourcePlanSha256, projectUuid, sceneUuid) {
    if (pointer.schemaVersion !== 1 || pointer.kind !== 'creator-reopen-readback-revision')
        fail('CREATOR_REOPEN_POINTER_SCHEMA_INVALID');
    const match = typeof pointer.readbackPath === 'string' && REVISION_RE.exec(pointer.readbackPath);
    if (!match || Number(match[1]) !== pointer.revision || !Number.isSafeInteger(pointer.revision) || pointer.revision <= 0)
        fail('CREATOR_REOPEN_POINTER_REVISION_INVALID');
    if (pointer.originReceiptPath !== originPath || pointer.originReceiptSha256 !== originSha ||
        pointer.manifestSha256 !== manifestSha256 || pointer.sourcePlanSha256 !== sourcePlanSha256 ||
        pointer.projectUuid !== projectUuid || pointer.sceneUuid !== sceneUuid)
        fail('CREATOR_REOPEN_POINTER_IDENTITY_MISMATCH');
    let currentPath = pointer.readbackPath, expectedHash = pointer.readbackSha256;
    let maxSeen = pointer.revision, chain = 0;
    const seen = new Set();
    while (true) {
        if (++chain > 4096 || seen.has(currentPath)) fail('CREATOR_REOPEN_POINTER_CHAIN_INVALID');
        seen.add(currentPath);
        safeRelative(currentPath, 'chain');
        if (!validSha(expectedHash)) fail('CREATOR_REOPEN_POINTER_CHAIN_SHA_INVALID');
        const bytes = readBytes(root, currentPath);
        if (sha(bytes) !== expectedHash) fail('CREATOR_REOPEN_POINTER_CHAIN_HASH_MISMATCH');
        const receipt = parseObject(bytes, currentPath);
        validateIdentity(receipt, manifestSha256, sourcePlanSha256, projectUuid, sceneUuid);
        const info = receipt.readbackRevision;
        if (!isObject(info)) fail('CREATOR_REOPEN_POINTER_CHAIN_METADATA_MISSING');
        if (info.schemaVersion !== 1 || info.readSavedMethod !== 'CreatorScene.readSaved')
            fail('CREATOR_REOPEN_POINTER_CHAIN_METHOD_METADATA_INVALID');
        const revisionMatch = REVISION_RE.exec(currentPath);
        const thisRevision = Number(revisionMatch && revisionMatch[1]);
        if (info.revision !== thisRevision || info.originReceiptPath !== originPath ||
            info.originReceiptSha256 !== originSha || info.manifestSha256 !== manifestSha256 ||
            info.sourcePlanSha256 !== sourcePlanSha256 || info.projectUuid !== projectUuid || info.sceneUuid !== sceneUuid)
            fail('CREATOR_REOPEN_POINTER_CHAIN_METADATA_MISMATCH');
        const previousPath = info.previousReceiptPath;
        const previousHash = info.previousReceiptSha256;
        if (previousPath === originPath) {
            if (previousHash !== originSha || sha(readBytes(root, originPath)) !== originSha)
                fail('CREATOR_REOPEN_POINTER_ORIGIN_HASH_MISMATCH');
            break;
        }
        const priorMatch = typeof previousPath === 'string' && REVISION_RE.exec(previousPath);
        const priorRevision = Number(priorMatch && priorMatch[1]);
        if (!priorMatch || !Number.isSafeInteger(priorRevision) || priorRevision >= maxSeen)
            fail('CREATOR_REOPEN_POINTER_CHAIN_ORDER_INVALID');
        maxSeen = priorRevision;
        currentPath = previousPath;
        expectedHash = previousHash;
    }
}

function collectNativeFiles(root, nativeRoots) {
    if (!Array.isArray(nativeRoots) || !nativeRoots.length) fail('CREATOR_REOPEN_NATIVE_ROOTS_REQUIRED');
    const files = new Map();
    const walk = (relative, absolute) => {
        const stat = fs.lstatSync(absolute);
        if (stat.isSymbolicLink()) fail('CREATOR_REOPEN_NATIVE_SYMLINK:' + relative);
        if (stat.isDirectory()) {
            for (const name of fs.readdirSync(absolute).sort()) walk(relative + '/' + name, path.join(absolute, name));
        } else if (stat.isFile()) {
            files.set(relative, sha(fs.readFileSync(absolute)));
        } else fail('CREATOR_REOPEN_NATIVE_ENTRY_UNSUPPORTED:' + relative);
    };
    for (const nativeRoot of [...new Set(nativeRoots)].sort()) {
        if (!NATIVE_ROOTS.has(nativeRoot)) fail('CREATOR_REOPEN_NATIVE_ROOT_NOT_ALLOWED:' + nativeRoot);
        const absolute = inside(root, nativeRoot);
        if (!fs.existsSync(absolute) || !fs.lstatSync(absolute).isDirectory())
            fail('CREATOR_REOPEN_NATIVE_ROOT_MISSING:' + nativeRoot);
        walk(nativeRoot, absolute);
    }
    if (!files.size) fail('CREATOR_REOPEN_NATIVE_FILES_EMPTY');
    return [...files].sort(([a], [b]) => a.localeCompare(b)).map(([filePath, hash]) => ({path: filePath, sha256: hash}));
}

function nextRevision(root) {
    const directory = inside(root, 'Analysis/Readback');
    fs.mkdirSync(directory, {recursive: true});
    let max = 0;
    for (const name of fs.readdirSync(directory)) {
        const match = /^reopened-([1-9][0-9]*)\.json$/.exec(name);
        if (match) max = Math.max(max, Number(match[1]));
    }
    if (!Number.isSafeInteger(max + 1)) fail('CREATOR_REOPEN_REVISION_OVERFLOW');
    return max + 1;
}

function writeCreateOnly(filePath, bytes) {
    const fd = fs.openSync(filePath, 'wx', 0o600);
    try { fs.writeFileSync(fd, bytes); fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
}

function writePointerAtomic(filePath, value) {
    const directory = path.dirname(filePath);
    const temp = path.join(directory, '.current-revision.' + process.pid + '.' + crypto.randomBytes(8).toString('hex') + '.tmp');
    writeCreateOnly(temp, value);
    try {
        fs.renameSync(temp, filePath);
        try { const dirFd = fs.openSync(directory, 'r'); try { fs.fsyncSync(dirFd); } finally { fs.closeSync(dirFd); } } catch (_) {}
    } catch (error) {
        try { fs.unlinkSync(temp); } catch (_) {}
        throw error;
    }
}

async function createRevision(options = {}) {
    const root = path.resolve(options.projectRoot || '');
    if (!options.projectRoot || typeof options.runReadSaved !== 'function') fail('CREATOR_REOPEN_READ_SAVED_CALLBACK_REQUIRED');
    const originalPath = safeRelative(options.originalReadbackPath || 'Analysis/Readback/editor-readback.json',
        'origin', true);
    if (!ORIGIN_PATHS.has(originalPath)) fail('CREATOR_REOPEN_ORIGIN_PATH_NOT_ALLOWED');
    const sourcePlanPath = options.sourcePlanPath || 'extensions/monkey-import/import-plan.json';
    if (sourcePlanPath !== 'extensions/monkey-import/import-plan.json') fail('CREATOR_REOPEN_PLAN_PATH_NOT_ALLOWED');
    const manifestPath = options.manifestPath || 'manifest.json';
    if (manifestPath !== 'manifest.json') fail('CREATOR_REOPEN_MANIFEST_PATH_NOT_ALLOWED');
    const manifestRaw = readBytes(root, manifestPath), planRaw = readBytes(root, sourcePlanPath), originalRaw = readBytes(root, originalPath);
    const manifestSha256 = sha(manifestRaw), sourcePlanSha256 = sha(planRaw), originReceiptSha256 = sha(originalRaw);
    const projectUuid = options.projectUuid;
    const sceneUuid = options.sceneUuid;
    if (typeof projectUuid !== 'string' || !projectUuid || typeof sceneUuid !== 'string' || !sceneUuid)
        fail('CREATOR_REOPEN_PROJECT_SCENE_IDENTITY_REQUIRED');
    const original = parseObject(originalRaw, originalPath);
    if (original.manifestSha256 !== manifestSha256 || original.projectUuid !== projectUuid || original.sceneUuid !== sceneUuid)
        fail('CREATOR_REOPEN_ORIGINAL_IDENTITY_MISMATCH');
    if (options.creatorVersion && original.creatorVersion !== options.creatorVersion)
        fail('CREATOR_REOPEN_CREATOR_VERSION_MISMATCH');
    if (isObject(options.readbackContext)) {
        if (options.readbackContext.projectUuid !== projectUuid || options.readbackContext.sceneUuid !== sceneUuid ||
            options.readbackContext.manifestSha256 !== manifestSha256 ||
            options.readbackContext.sourcePlanSha256 !== sourcePlanSha256)
            fail('CREATOR_REOPEN_CONTEXT_IDENTITY_MISMATCH');
    }

    let pointer = null, previousReceiptPath = originalPath, previousReceiptSha256 = originReceiptSha256;
    let originPath = originalPath, originSha = originReceiptSha256;
    const pointerAbs = inside(root, POINTER_RELATIVE);
    if (fs.existsSync(pointerAbs)) {
        const pointerRaw = readBytes(root, POINTER_RELATIVE);
        pointer = parseObject(pointerRaw, POINTER_RELATIVE);
        validateCurrentPointer(root, pointer, originalPath, originReceiptSha256, manifestSha256,
            sourcePlanSha256, projectUuid, sceneUuid);
        previousReceiptPath = pointer.readbackPath;
        previousReceiptSha256 = pointer.readbackSha256;
        originPath = pointer.originReceiptPath;
        originSha = pointer.originReceiptSha256;
    }

    // This callback is the only source of the refreshed native readback body.
    const savedReadback = await options.runReadSaved();
    if (!isObject(savedReadback) || !Array.isArray(savedReadback.nodes) ||
        !Array.isArray(savedReadback.components) || !Array.isArray(savedReadback.sourcePrefabs))
        fail('CREATOR_REOPEN_READ_SAVED_RESULT_INVALID');
    const revision = nextRevision(root);
    const nativeFiles = collectNativeFiles(root, options.nativeRoots);
    const revisionInfo = {schemaVersion: 1, revision, previousReceiptPath, previousReceiptSha256,
        originReceiptPath: originPath, originReceiptSha256: originSha,
        manifestSha256, sourcePlanSha256, projectUuid, sceneUuid,
        readSavedMethod: 'CreatorScene.readSaved'};
    const readback = {...(isObject(options.readbackContext) ? options.readbackContext : {}),
        ...savedReadback, sceneUuid, creatorVersion: options.creatorVersion || original.creatorVersion,
        projectUuid, manifestSha256, sourcePlanSha256, nativeFiles, readbackRevision: revisionInfo};
    const readbackBytes = Buffer.from(JSON.stringify(readback, null, 2) + '\n', 'utf8');
    const readbackPath = `Analysis/Readback/reopened-${revision}.json`;
    const readbackAbs = inside(root, readbackPath);
    writeCreateOnly(readbackAbs, readbackBytes);

    const pointerValue = {schemaVersion: 1, kind: 'creator-reopen-readback-revision', revision,
        readbackPath, readbackSha256: sha(readbackBytes), previousReceiptPath, previousReceiptSha256,
        originReceiptPath: originPath, originReceiptSha256: originSha,
        manifestSha256, sourcePlanSha256, projectUuid, sceneUuid};
    writePointerAtomic(pointerAbs, Buffer.from(JSON.stringify(pointerValue, null, 2) + '\n', 'utf8'));
    return {readbackPath, readbackSha256: pointerValue.readbackSha256,
        pointerPath: POINTER_RELATIVE, revision, previousReceiptPath, previousReceiptSha256,
        originReceiptPath: originPath, originReceiptSha256: originSha,
        manifestSha256, sourcePlanSha256, projectUuid, sceneUuid, nativeFileCount: nativeFiles.length};
}

module.exports = {createRevision};
