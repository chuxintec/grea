'use strict';
const cc = require('cc');
const crypto = require('crypto');

function sha(bytes) {
    return crypto.createHash('sha256').update(Buffer.from(bytes.buffer || bytes,
        bytes.byteOffset || 0, bytes.byteLength || bytes.length)).digest('hex');
}
function uuidOf(asset) { return asset && (asset._uuid || asset.uuid); }
function expectedType(entry) {
    switch (entry.retentionKind) {
        case 'buffer-asset': return cc.BufferAsset;
        case 'texture-asset': return cc.Texture2D;
        case 'retained-source-material': return cc.JsonAsset;
        case 'builtin-default-material': return cc.Material;
        default: throw new Error('RETAINED_ASSET_KIND_UNSUPPORTED: ' + entry.retentionKind);
    }
}
function loadUuid(uuid, type) {
    return new Promise((resolve, reject) => cc.assetManager.loadAny({ uuid }, { reloadAsset: true }, (error, asset) => {
        if (error) return reject(error);
        if (!(asset instanceof type)) return reject(new Error('Unexpected retained asset type: ' + uuid));
        resolve(asset);
    }));
}
function canonical(value) {
    if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
    if (value && typeof value === 'object') {
        return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}';
    }
    return JSON.stringify(value);
}
function asPixels(data) {
    if (data instanceof ArrayBuffer) return new Uint8Array(data);
    if (ArrayBuffer.isView(data)) return new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
    return null;
}
function canvasPixels(source, width, height) {
    if (typeof document === 'undefined' || !source || width <= 0 || height <= 0)
        throw new Error('Creator browser Canvas pixel readback is unavailable');
    const canvas = document.createElement('canvas');
    canvas.width = width; canvas.height = height;
    const context = canvas.getContext('2d', { willReadFrequently: true });
    if (!context) throw new Error('Creator browser Canvas 2D context is unavailable');
    context.drawImage(source, 0, 0, width, height);
    return new Uint8Array(context.getImageData(0, 0, width, height).data);
}
function imagePixels(imageAsset) {
    const data = imageAsset && imageAsset.data;
    const direct = asPixels(data);
    if (direct) return { pixels: direct, access: 'typed-array' };
    if (data && imageAsset.width > 0 && imageAsset.height > 0)
        return { pixels: canvasPixels(data, imageAsset.width, imageAsset.height), access: 'image-canvas' };
    throw new Error('Creator ImageAsset pixel data is unavailable');
}
function decodePinnedPng(raw, width, height) {
    if (typeof Image === 'undefined' || typeof document === 'undefined')
        throw new Error('RETAINED_TEXTURE_BROWSER_DECODER_UNAVAILABLE');
    return new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => {
            const actualWidth = image.naturalWidth || image.width;
            const actualHeight = image.naturalHeight || image.height;
            if (actualWidth !== width || actualHeight !== height) {
                reject(new Error('RETAINED_TEXTURE_PNG_DIMENSIONS_DIFFER'));
                return;
            }
            try { resolve(canvasPixels(image, width, height)); } catch (error) { reject(error); }
        };
        image.onerror = () => reject(new Error('RETAINED_TEXTURE_PNG_BROWSER_DECODE_FAILED'));
        image.src = 'data:image/png;base64,' + Buffer.from(raw).toString('base64');
    });
}
function equalBytes(left, right) {
    return left.length === right.length && left.every((value, index) => value === right[index]);
}
function readProjectAsset(projectRoot, relativePath) {
    const fs = require('fs'), path = require('path');
    const root = fs.realpathSync(projectRoot || Editor.Project.path);
    if (typeof relativePath !== 'string' || (!relativePath.startsWith('assets/resources/RetainedAssets/Textures/') && !relativePath.startsWith('assets/resources/Textures/')) || !relativePath.endsWith('.png'))
        throw new Error('RETAINED_TEXTURE_SOURCE_PATH_INVALID');
    const source = fs.realpathSync(path.resolve(root, relativePath));
    if (!source.startsWith(root + path.sep)) throw new Error('RETAINED_TEXTURE_SOURCE_PATH_INVALID');
    return fs.readFileSync(source);
}

async function load(contract) {
    if (!contract || contract.schema !== 'monkey-prefab-static-retained-assets/1' || !Array.isArray(contract.assets))
        throw new Error('RETAINED_ASSET_CONTRACT_INVALID');
    const pairs = await Promise.all(contract.assets.map(async entry => [entry.sourceId,
        await loadUuid(entry.creator.uuid, expectedType(entry))]));
    return new Map(pairs);
}

function resolve(contract, assets, sourceId) {
    const entry = (contract.assets || []).filter(row => row.sourceId === sourceId);
    if (entry.length !== 1) throw new Error('RETAINED_ASSET_SOURCE_ID_NOT_UNIQUE: ' + sourceId);
    const value = assets && assets.get(sourceId);
    if (!value || !(value instanceof expectedType(entry[0])))
        throw new Error('RETAINED_ASSET_NATIVE_REFERENCE_MISSING: ' + sourceId);
    return value;
}

function createBuiltin(entry, sourceEffect) {
    if (!entry || entry.retentionKind !== 'builtin-default-material' ||
        (!sourceEffect || sourceEffect._uuid !== '60f7195c-ec2a-45eb-ba94-8955f60e81d0') || entry.creator.effectName !== 'builtin-sprite')
        throw new Error('RETAINED_BUILTIN_MATERIAL_SOURCE_PROFILE_INVALID: '+JSON.stringify({name:sourceEffect&&sourceEffect.name,uuid:sourceEffect&&sourceEffect._uuid,expected:entry&&entry.creator}));
    const material = new cc.Material(entry.creator.path.split('/').pop().replace(/\.mtl$/, ''));
    const info = { technique: 0, defines: { USE_TEXTURE: true } };
    if (sourceEffect) info.effectAsset = sourceEffect; else info.effectName = entry.creator.effectName;
    material.initialize(info);
    if ((sourceEffect && material.effectAsset !== sourceEffect) || (!material.effectAsset||material.effectAsset._uuid!=='60f7195c-ec2a-45eb-ba94-8955f60e81d0') || material.technique !== 0)
        throw new Error('RETAINED_BUILTIN_MATERIAL_INITIALIZATION_FAILED: '+JSON.stringify({effect:material.effectName,technique:material.technique,passes:material.passes.length,expected:entry.creator.effectName}));
    return material;
}

function serializeBuiltin(material) {
    if (!(material instanceof cc.Material) || (!material.effectAsset||material.effectAsset._uuid!=='60f7195c-ec2a-45eb-ba94-8955f60e81d0') || material.technique !== 0)
        throw new Error('RETAINED_BUILTIN_MATERIAL_NOT_NATIVE_DEFAULT');
    if (!globalThis.EditorExtends || typeof EditorExtends.serialize !== 'function')
        throw new Error('Creator native material serializer unavailable');
    const raw = EditorExtends.serialize(material);
    return typeof raw === 'string' ? raw : JSON.stringify(raw);
}

async function read(contract, assets, projectRoot) {
    if (!contract || contract.schema !== 'monkey-prefab-static-retained-assets/1')
        throw new Error('RETAINED_ASSET_CONTRACT_INVALID');
    const result = [];
    for (const entry of contract.assets || []) {
        const asset = resolve(contract, assets, entry.sourceId);
        const uuid = uuidOf(asset);
        if (!uuid || uuid !== entry.creator.uuid) throw new Error('RETAINED_ASSET_UUID_DIFFERS: ' + entry.sourceId);
        const row = { sourceId: entry.sourceId, retentionKind: entry.retentionKind,
            nativeType: cc.js.getClassName(asset), uuid, persistent: true, verified: true };
        if (entry.retentionKind === 'buffer-asset') {
            const bytes = asset.buffer();
            row.sourceSha256 = sha(new Uint8Array(bytes));
            if (row.sourceSha256 !== entry.contentSha256) throw new Error('RETAINED_BUFFER_BYTES_DIFFER: ' + entry.sourceId);
        } else if (entry.retentionKind === 'texture-asset') {
            const image = (asset.mipmaps || [])[0];
            if (!image || image.width !== entry.dimensions[0] || image.height !== entry.dimensions[1])
                throw new Error('RETAINED_TEXTURE_DIMENSIONS_DIFFER: ' + entry.sourceId);
            if (!entry.creator.imageUuid || uuidOf(image) !== entry.creator.imageUuid)
                throw new Error('RETAINED_TEXTURE_IMAGE_UUID_DIFFER: ' + entry.sourceId);
            const pngBytes = readProjectAsset(projectRoot, entry.creator.path);
            row.pngSha256 = sha(pngBytes);
            if (row.pngSha256 !== entry.creatorPngSha256) throw new Error('RETAINED_TEXTURE_PNG_BYTES_DIFFER: ' + entry.sourceId);
            const native = imagePixels(image);
            const pixelLength = image.width * image.height * 4;
            if (native.pixels.length !== pixelLength) throw new Error('RETAINED_TEXTURE_PIXEL_LENGTH_DIFFER: ' + entry.sourceId);
            row.width = image.width; row.height = image.height; row.imageUuid = uuidOf(image);
            row.sourceRgbaSha256 = entry.rgbaSha256;
            row.nativePixelAccess = native.access;
            row.nativeImagePixelSha256 = sha(native.pixels);
            if (native.access === 'typed-array') {
                if (row.nativeImagePixelSha256 !== entry.rgbaSha256)
                    throw new Error('RETAINED_TEXTURE_PIXELS_DIFFER: ' + entry.sourceId);
                row.pixelComparison = 'native-typed-array-source-rgba-exact-v1';
                row.nativePixelsEqualPng = null;
            } else {
                const pngPixels = await decodePinnedPng(pngBytes, image.width, image.height);
                row.pngPixelSha256 = sha(pngPixels);
                row.nativePixelsEqualPng = equalBytes(native.pixels, pngPixels);
                row.pixelComparison = 'browser-decoded-png-to-native-image-canvas-exact-v1';
                if (!row.nativePixelsEqualPng)
                    throw new Error('RETAINED_TEXTURE_PNG_PIXEL_COMPARISON_FAILED: ' + entry.sourceId);
            }
        } else if (entry.retentionKind === 'retained-source-material') {
            const fs=require('fs'),path=require('path');
            const root=fs.realpathSync(projectRoot||Editor.Project.path),source=path.resolve(root,entry.creator.path);
            if(!entry.creator.path.startsWith('assets/resources/RetainedAssets/')||!source.startsWith(root+path.sep))throw Error('RETAINED_MATERIAL_SOURCE_PATH_INVALID');
            const raw=fs.readFileSync(source),expected=JSON.parse(raw.toString('utf8'));
            row.sourceSha256=sha(raw);
            row.nativeJsonValueVerified=canonical(asset.json)===canonical(expected);
            if (row.sourceSha256 !== entry.creator.contentSha256 || !row.nativeJsonValueVerified || asset.json.retentionOnly !== true ||
                asset.json.renderingRecovered !== false || asset.json.sourceMaterialId !== entry.sourceId ||
                asset.json.sourceEffectId !== entry.sourceEffectId || asset.json.sourceDocumentEncoding!=='opaque-json-text-v1' ||
                typeof asset.json.sourceMaterialJson!=='string'||typeof asset.json.sourceEffectJson!=='string'||
                sha(Buffer.from(asset.json.sourceMaterialJson,'utf8'))!==entry.sourceMaterialDocumentSha256||
                sha(Buffer.from(asset.json.sourceEffectJson,'utf8'))!==entry.sourceEffectDocumentSha256)
                throw new Error('RETAINED_MATERIAL_DOCUMENT_DIFFER: ' + entry.sourceId);
            row.nonRendering = true;
        } else if (entry.retentionKind === 'builtin-default-material') {
            const defines = asset.passes.length === 1 ? asset.passes[0].defines : null;
            if ((!asset.effectAsset||asset.effectAsset._uuid!=='60f7195c-ec2a-45eb-ba94-8955f60e81d0') || asset.technique !== 0 || asset.passes.length !== 1 ||
                !defines || defines.USE_TEXTURE !== true)
                throw new Error('RETAINED_BUILTIN_MATERIAL_PROFILE_DIFFER: ' + entry.sourceId);
            row.effectName = asset.effectName; row.technique = asset.technique; row.passCount = asset.passes.length;
            row.defines = { USE_TEXTURE: defines.USE_TEXTURE };
            row.sourceSha256 = entry.sourceDocumentSha256;
        }
        result.push(row);
    }
    return result;
}

module.exports = { load, resolve, createBuiltin, serializeBuiltin, read };
