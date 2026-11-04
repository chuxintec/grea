'use strict';
const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const Module = require('module');
const zlib = require('zlib');
const load = Module._load;
const digest = value => crypto.createHash('sha256').update(value).digest('hex');
function crc32(bytes) {
    let crc = 0xffffffff;
    for (const byte of bytes) {
        crc ^= byte;
        for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
    }
    return (crc ^ 0xffffffff) >>> 0;
}
function pngChunk(name, data) {
    const type = Buffer.from(name, 'ascii'), length = Buffer.alloc(4), checksum = Buffer.alloc(4);
    length.writeUInt32BE(data.length); checksum.writeUInt32BE(crc32(Buffer.concat([type, data])));
    return Buffer.concat([length, type, data, checksum]);
}
function png1x1(rgba) {
    const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
    const header = Buffer.alloc(13); header.writeUInt32BE(1, 0); header.writeUInt32BE(1, 4);
    header[8] = 8; header[9] = 6;
    return Buffer.concat([signature, pngChunk('IHDR', header),
        pngChunk('IDAT', zlib.deflateSync(Buffer.from([0, ...rgba]))), pngChunk('IEND', Buffer.alloc(0))]);
}
const canonical = value => {
    if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
    if (value && typeof value === 'object') return '{' + Object.keys(value).sort()
        .map(key => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}';
    return JSON.stringify(value);
};
class Asset { constructor(uuid) { this._uuid = uuid; } }
class BufferAsset extends Asset { constructor(uuid, bytes) { super(uuid); this.bytes = bytes; } buffer() { return this.bytes.buffer.slice(this.bytes.byteOffset, this.bytes.byteOffset + this.bytes.byteLength); } }
class Texture2D extends Asset { constructor(uuid, image) { super(uuid); this.mipmaps = [image]; } }
class JsonAsset extends Asset { constructor(uuid, json) { super(uuid); this.json = json; } }
class Material extends Asset {
    constructor(name) { super(''); this.name = name; this.passes = []; }
    initialize(info) { this.effectAsset = info.effectAsset || { name: info.effectName }; this.technique = info.technique; this.passes = [{}]; }
    get effectName() { return this.effectAsset && this.effectAsset.name || ''; }
}
const cc = { Asset, BufferAsset, Texture2D, JsonAsset, Material,
    js: { getClassName: value => value && value.constructor && value.constructor.name }, assetManager: { loadAny() {} } };
Module._load = function (request, parent, isMain) { if (request === 'cc') return cc; return load.call(this, request, parent, isMain); };
const helper = require('../src/monkey/targets/CreatorStaticRetainedAssets.js');
Module._load = load;

const bytes = Buffer.from([1, 2, 3, 4]);
const sourcePixels = new Uint8Array([100, 50, 25, 128]);
const browserPixels = new Uint8Array([100, 50, 24, 128]); // Browser alpha-premultiply roundtrip differs from source RGBA.
let nativeCanvasPixels = new Uint8Array(browserPixels);
const pngBytes = png1x1(sourcePixels);
const sourceMaterialJson = '{"__type__":"cc.Material","_effectAsset":{"__uuid__":"source-effect-uuid"},"_name":"movie-clip","caption":"雪","measurement":1.0}';
const sourceEffectJson = '{"__type__":"cc.EffectAsset","_name":"movie-clip","spriteRef":{"__uuid__":"source-sprite-uuid"}}';
const envelope = { retentionOnly: true, renderingRecovered: false, sourceMaterialId: 'material-id',
    sourceEffectId: 'effect-id', sourceDocumentEncoding: 'opaque-json-text-v1', sourceMaterialJson,
    sourceEffectJson, measurement: 1, caption: '雪' };
const materialFileText = JSON.stringify(envelope).replace('"measurement":1,', '"measurement":1.0,');
const materialFileBytes = Buffer.from(materialFileText, 'utf8');
const sourceMaterialDocumentSha256 = digest(Buffer.from(sourceMaterialJson, 'utf8'));
const sourceEffectDocumentSha256 = digest(Buffer.from(sourceEffectJson, 'utf8'));
const contract = { schema: 'monkey-prefab-static-retained-assets/1', assets: [
    { sourceId: 'buffer-id', retentionKind: 'buffer-asset', contentSha256: digest(bytes), creator: { uuid: 'uuid-buffer', type: 'cc.BufferAsset' } },
    { sourceId: 'texture-id', retentionKind: 'texture-asset', dimensions: [1, 1], rgbaSha256: digest(sourcePixels),
        creatorPngSha256: digest(pngBytes), creator: { uuid: 'uuid-texture', imageUuid: 'image-texture-uuid', type: 'cc.Texture2D',
            path: 'assets/resources/RetainedAssets/Textures/texture-id.png' } },
    { sourceId: 'material-id', retentionKind: 'retained-source-material', sourceEffectId: 'effect-id',
        sourceMaterialDocumentSha256, sourceEffectDocumentSha256,
        creator: { uuid: 'uuid-json', type: 'cc.JsonAsset', path: 'assets/resources/RetainedAssets/Materials/material-id.json', contentSha256: digest(materialFileBytes) } },
    { sourceId: 'builtin-id', retentionKind: 'builtin-default-material', sourceDocumentSha256: 'f'.repeat(64), creator: { uuid: 'uuid-material', type: 'cc.Material', path: 'assets/resources/Default.mtl', effectName: 'builtin-sprite' } },
] };
const assets = new Map([
    ['uuid-buffer', new BufferAsset('uuid-buffer', bytes)],
    ['uuid-texture', new Texture2D('uuid-texture', { _uuid: 'image-texture-uuid', width: 1, height: 1,
        get data() { return { nativeCanvasPixels: true, get pixels() { return nativeCanvasPixels; } }; } })],
    ['uuid-json', new JsonAsset('uuid-json', JSON.parse(materialFileBytes.toString('utf8')))],
    ['uuid-material', Object.assign(new Material('default'), { _uuid: 'uuid-material', effectAsset: { name: 'builtin-sprite',_uuid:'60f7195c-ec2a-45eb-ba94-8955f60e81d0' }, technique: 0, passes: [{ defines: { USE_TEXTURE: true } }] })],
]);
cc.assetManager.loadAny = ({ uuid }, options, callback) => callback(null, assets.get(uuid));
globalThis.Image = class {
    set src(value) { this.value = value; this.naturalWidth = 1; this.naturalHeight = 1; this.pixels = browserPixels; queueMicrotask(() => this.onload()); }
};
globalThis.document = { createElement() {
    return { width: 0, height: 0, getContext() {
        const context = { source: null, drawImage(source) { this.source = source; },
            getImageData() { return { data: this.source.pixels }; } };
        return context;
    } };
} };

let projectRootForCleanup = null;
(async () => {
    const loaded = await helper.load(contract);
    assert.strictEqual(helper.resolve(contract, loaded, 'buffer-id'), loaded.get('buffer-id'));
    const projectRoot = fs.mkdtempSync(path.join('/private/tmp', 'creator-retained-assets-'));
    projectRootForCleanup = projectRoot;
    const materialPath = path.join(projectRoot, contract.assets[2].creator.path);
    fs.mkdirSync(path.dirname(materialPath), { recursive: true });
    fs.writeFileSync(materialPath, materialFileBytes);
    const pngPath = path.join(projectRoot, contract.assets[1].creator.path);
    fs.mkdirSync(path.dirname(pngPath), { recursive: true });
    fs.writeFileSync(pngPath, pngBytes);
    const result = await helper.read(contract, loaded, projectRoot);
    assert.strictEqual(result.length, 4);
    const textureRead = result.find(row => row.sourceId === 'texture-id');
    assert.strictEqual(textureRead.imageUuid, 'image-texture-uuid');
    assert.strictEqual(textureRead.pngSha256, digest(pngBytes));
    assert.strictEqual(textureRead.sourceRgbaSha256, digest(sourcePixels));
    assert.strictEqual(textureRead.pngPixelSha256, digest(browserPixels));
    assert.strictEqual(textureRead.nativeImagePixelSha256, digest(browserPixels));
    assert.strictEqual(textureRead.pixelComparison, 'browser-decoded-png-to-native-image-canvas-exact-v1');
    assert.strictEqual(textureRead.nativePixelsEqualPng, true);
    assert.notStrictEqual(textureRead.nativeImagePixelSha256, textureRead.sourceRgbaSha256);
    const materialRead = result.find(row => row.sourceId === 'material-id');
    assert.strictEqual(materialRead.nonRendering, true);
    assert.strictEqual(materialRead.sourceSha256, digest(materialFileBytes));
    assert.strictEqual(materialRead.nativeJsonValueVerified, true);
    assert.deepStrictEqual(loaded.get('material-id').json, envelope);
    assert(loaded.get('material-id').json.sourceMaterialJson.includes('"__type__":"cc.Material"'));
    assert(loaded.get('material-id').json.sourceMaterialJson.includes('"__uuid__":"source-effect-uuid"'));
    assert(loaded.get('material-id').json.sourceEffectJson.includes('"__type__":"cc.EffectAsset"'));

    const originalPngBytes = fs.readFileSync(pngPath);
    const changedPng = Buffer.from(originalPngBytes); changedPng[changedPng.length - 1] ^= 0xff;
    fs.writeFileSync(pngPath, changedPng);
    await assert.rejects(() => helper.read(contract, loaded, projectRoot), /RETAINED_TEXTURE_PNG_BYTES_DIFFER/);
    fs.writeFileSync(pngPath, originalPngBytes);
    nativeCanvasPixels = new Uint8Array([100, 50, 23, 128]);
    await assert.rejects(() => helper.read(contract, loaded, projectRoot), /RETAINED_TEXTURE_PNG_PIXEL_COMPARISON_FAILED/);
    nativeCanvasPixels = new Uint8Array(browserPixels);

    const originalMaterialBytes = fs.readFileSync(materialPath);
    fs.writeFileSync(materialPath, originalMaterialBytes.toString('utf8').replace('1.0', '2.0'));
    await assert.rejects(() => helper.read(contract, loaded, projectRoot), /RETAINED_MATERIAL_DOCUMENT_DIFFER/);
    fs.writeFileSync(materialPath, originalMaterialBytes);
    const originalSourceMaterialJson = loaded.get('material-id').json.sourceMaterialJson;
    loaded.get('material-id').json.sourceMaterialJson = originalSourceMaterialJson.replace('"__type__":"cc.Material",', '');
    await assert.rejects(() => helper.read(contract, loaded, projectRoot), /RETAINED_MATERIAL_DOCUMENT_DIFFER/);
    loaded.get('material-id').json.sourceMaterialJson = originalSourceMaterialJson;

    const material = helper.createBuiltin(contract.assets[3], { name: 'builtin-sprite',_uuid:'60f7195c-ec2a-45eb-ba94-8955f60e81d0' });
    globalThis.EditorExtends = { serialize: () => ({ type: 'native-material' }) };
    assert.strictEqual(helper.serializeBuiltin(material), '{"type":"native-material"}');
    assert.throws(() => helper.createBuiltin(contract.assets[3], { name: 'movie-clip' }), /SOURCE_PROFILE_INVALID/);
    fs.rmSync(projectRoot, { recursive: true, force: true });
    projectRootForCleanup = null;
    delete globalThis.Image; delete globalThis.document;
    console.log('creator retained asset load/read passed');
})().catch(error => {
    if (projectRootForCleanup) fs.rmSync(projectRootForCleanup, { recursive: true, force: true });
    delete globalThis.Image; delete globalThis.document;
    console.error(error); process.exitCode = 1;
});
