'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const reopen = require('../src/monkey/targets/CreatorReopenVerification.js');

const sha = value => crypto.createHash('sha256').update(value).digest('hex');
function fixture() {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'creator-reopen-'));
    const manifest = Buffer.from('{"projectUuid":"project-1"}\n');
    const plan = Buffer.from('{"schemaVersion":1,"nodes":[]}\n');
    fs.mkdirSync(path.join(root, 'Analysis/Readback'), {recursive: true});
    fs.mkdirSync(path.join(root, 'extensions/monkey-import'), {recursive: true});
    fs.mkdirSync(path.join(root, 'assets/Game/Content'), {recursive: true});
    fs.mkdirSync(path.join(root, 'assets/resources'), {recursive: true});
    fs.writeFileSync(path.join(root, 'manifest.json'), manifest);
    fs.writeFileSync(path.join(root, 'extensions/monkey-import/import-plan.json'), plan);
    fs.writeFileSync(path.join(root, 'assets/Game/Content/test.prefab'), 'native-v1');
    const original = {creatorVersion: '3.8.8', projectUuid: 'project-1', sceneUuid: 'scene-1',
        manifestSha256: sha(manifest), assets: [{sourceId: 'asset-stable', uuid: 'asset-uuid'}],
        nodes: [], components: [], sourcePrefabs: [], nativeFiles: []};
    fs.writeFileSync(path.join(root, 'Analysis/Readback/editor-readback.json'), JSON.stringify(original, null, 2) + '\n');
    const context = {...original, sourcePlanSha256: sha(plan)};
    return {root, context, originalBytes: fs.readFileSync(path.join(root, 'Analysis/Readback/editor-readback.json'))};
}
function opts(fx, runReadSaved, overrides = {}) {
    return {projectRoot: fx.root, sceneUuid: 'scene-1', projectUuid: 'project-1', creatorVersion: '3.8.8',
        sourcePlanPath: 'extensions/monkey-import/import-plan.json', manifestPath: 'manifest.json',
        originalReadbackPath: 'Analysis/Readback/editor-readback.json', nativeRoots: ['assets/Game', 'assets/resources'],
        readbackContext: fx.context, runReadSaved, ...overrides};
}
const saved = marker => ({nodes: [{sourceId: 'node-1', nativeMarker: marker}], components: [], sourcePrefabs: [], sceneMetric: marker});

test('writes create-only Editor readSaved revisions with current native hashes and an atomic pointer chain', async () => {
    const fx = fixture();
    let calls = 0;
    const first = await reopen.createRevision(opts(fx, async () => { calls++; return saved('fresh-1'); }));
    assert.equal(calls, 1);
    assert.equal(first.revision, 1);
    const firstPath = path.join(fx.root, first.readbackPath);
    const firstBytes = fs.readFileSync(firstPath);
    const firstReceipt = JSON.parse(firstBytes.toString('utf8'));
    assert.equal(firstReceipt.sceneMetric, 'fresh-1');
    assert.equal(firstReceipt.assets[0].uuid, 'asset-uuid');
    assert.equal(firstReceipt.readbackRevision.readSavedMethod, 'CreatorScene.readSaved');
    assert.equal(firstReceipt.nativeFiles.find(row => row.path.endsWith('test.prefab')).sha256, sha('native-v1'));
    assert.deepEqual(fs.readFileSync(path.join(fx.root, 'Analysis/Readback/editor-readback.json')), fx.originalBytes);

    fs.writeFileSync(path.join(fx.root, 'assets/Game/Content/test.prefab'), 'native-after-normal-save');
    const second = await reopen.createRevision(opts(fx, async () => { calls++; return saved('fresh-2'); }));
    assert.equal(calls, 2);
    assert.equal(second.revision, 2);
    const secondReceipt = JSON.parse(fs.readFileSync(path.join(fx.root, second.readbackPath), 'utf8'));
    assert.equal(secondReceipt.nativeFiles.find(row => row.path.endsWith('test.prefab')).sha256, sha('native-after-normal-save'));
    assert.equal(secondReceipt.readbackRevision.previousReceiptPath, first.readbackPath);
    assert.equal(secondReceipt.readbackRevision.previousReceiptSha256, sha(firstBytes));
    assert.deepEqual(fs.readFileSync(firstPath), firstBytes, 'earlier receipt remains immutable');
    const pointer = JSON.parse(fs.readFileSync(path.join(fx.root, 'Analysis/Readback/current-revision.json'), 'utf8'));
    assert.equal(pointer.readbackPath, second.readbackPath);
    assert.equal(pointer.readbackSha256, sha(fs.readFileSync(path.join(fx.root, second.readbackPath))));
});

test('does not create a receipt or pointer when real readSaved rejects', async () => {
    const fx = fixture();
    await assert.rejects(reopen.createRevision(opts(fx, async () => { throw new Error('readSaved failed'); })), /readSaved failed/);
    assert.deepEqual(fs.readdirSync(path.join(fx.root, 'Analysis/Readback')), ['editor-readback.json']);
});

test('rejects mismatched reopen context before calling readSaved', async () => {
    const fx = fixture();
    let called = false;
    const context = {...fx.context, sourcePlanSha256: '0'.repeat(64)};
    await assert.rejects(reopen.createRevision(opts(fx, async () => { called = true; return saved('x'); },
        {readbackContext: context})), /CREATOR_REOPEN_CONTEXT_IDENTITY_MISMATCH/);
    assert.equal(called, false);
});

test('rejects a corrupt existing pointer rather than silently falling back or replacing it', async () => {
    const fx = fixture();
    const pointerPath = path.join(fx.root, 'Analysis/Readback/current-revision.json');
    fs.writeFileSync(pointerPath, '{bad json');
    let called = false;
    await assert.rejects(reopen.createRevision(opts(fx, async () => { called = true; return saved('x'); })), /CREATOR_REOPEN_JSON_INVALID/);
    assert.equal(called, false);
    assert.equal(fs.readFileSync(pointerPath, 'utf8'), '{bad json');
});

test('rejects paths outside the fixed native roots', async () => {
    const fx = fixture();
    await assert.rejects(reopen.createRevision(opts(fx, async () => saved('x'), {nativeRoots: ['../../outside']})),
        /CREATOR_REOPEN_NATIVE_ROOT_NOT_ALLOWED/);
});
