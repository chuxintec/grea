'use strict';
// Exact source-effect t0 projection. No engine/global clock is read here or in
// the generated Effect; only a separately pinned sourceTimeSeconds=0 is valid.
const cc = require('cc');

const PROFILE = 'cocos24-static-t0-sprite-effects-v1';
const SCHEMA = 'monkey-prefab-static-time-materials/1';
const EPSILON = 0.00001;

function uuid(asset) { return asset && (asset.uuid || asset._uuid); }
function near(a, b) { return Number.isFinite(a) && Math.abs(a - b) <= EPSILON; }

function validate(spec, row) {
    if (!spec || spec.schema !== SCHEMA || spec.profile !== PROFILE || spec.target !== 'creator' ||
        spec.staticTimeSeconds !== 0 || !spec.targetShader || !spec.targetShader.creator ||
        !/^[0-9a-f-]{36}$/i.test(spec.targetShader.creator.uuid || '') || !row ||
        !['textured-uv-flow-t0-v1', 'textured-flash-sweep-t0-v1'].includes(row.profile) ||
        row.staticTimeSeconds !== 0 || !row.creator || !/^[0-9a-f-]{36}$/i.test(row.creator.effectUuid || '') ||
        !/^[0-9a-f-]{36}$/i.test(row.creator.materialUuid || '') ||
        !Array.isArray(row.spriteBindings) || !row.spriteBindings.length)
        throw Error('STATIC_TIME_MATERIAL_SPEC_INVALID');
    if (!row.targetProperties || !near(row.targetProperties.sourceTimeSeconds, 0) ||
        !Array.isArray(row.targetProperties.sourceColor) || row.targetProperties.sourceColor.length !== 4)
        throw Error('STATIC_TIME_MATERIAL_PROPERTIES_INVALID');
}

function colorArray(value) {
    if (value instanceof cc.Color) return [value.r / 255, value.g / 255, value.b / 255, value.a / 255];
    if (value && Number.isFinite(value.r) && Number.isFinite(value.g) && Number.isFinite(value.b) && Number.isFinite(value.a)) {
        const scale = Math.max(value.r, value.g, value.b, value.a) > 1 ? 1 / 255 : 1;
        return [value.r * scale, value.g * scale, value.b * scale, value.a * scale];
    }
    if (Array.isArray(value) && value.length === 4 && value.every(Number.isFinite)) return value;
    return null;
}

function verifyProperties(spec, row, material) {
    if (!(material instanceof cc.Material) || material.technique !== 0) return false;
    const p = row.targetProperties;
    if (!near(material.getProperty('sourceTimeSeconds'), 0)) return false;
    for (let i = 0; i < 7; i++) {
        const expected = p[`sourceScalar${i}`] || 0;
        if (!near(material.getProperty(`sourceScalar${i}`), expected)) return false;
    }
    const color = colorArray(material.getProperty('sourceColor0'));
    if (!color) return false;
    return color.every((value, i) => near(value, p.sourceColor[i]));
}

function create(spec, row, effectAsset) {
    validate(spec, row);
    if (!(effectAsset instanceof cc.EffectAsset) || uuid(effectAsset) !== row.creator.effectUuid)
        throw Error('STATIC_TIME_EFFECT_NATIVE_IDENTITY_MISMATCH');
    const material = new cc.Material();
    material.name = 'StaticT0Sprite';
    material.initialize({ effectAsset, technique: 0, defines: { USE_TEXTURE: true } });
    const p = row.targetProperties;
    material.setProperty('sourceTimeSeconds', 0);
    for (let i = 0; i < 7; i++) material.setProperty(`sourceScalar${i}`, p[`sourceScalar${i}`] || 0);
    material.setProperty('sourceColor0', new cc.Color(p.sourceColor[0] * 255, p.sourceColor[1] * 255,
        p.sourceColor[2] * 255, p.sourceColor[3] * 255));
    if (!verifyProperties(spec, row, material)) throw Error('STATIC_TIME_MATERIAL_CREATE_READBACK_MISMATCH');
    return material;
}

function serialize(spec, row, material) {
    validate(spec, row);
    if (uuid(material && material.effectAsset) !== row.creator.effectUuid || !verifyProperties(spec, row, material))
        throw Error('STATIC_TIME_MATERIAL_PRE_SAVE_MISMATCH');
    if (typeof EditorExtends === 'undefined' || typeof EditorExtends.serialize !== 'function')
        throw Error('STATIC_TIME_EDITOR_SERIALIZER_UNAVAILABLE');
    const result = EditorExtends.serialize(material);
    return typeof result === 'string' ? result : JSON.stringify(result);
}

function readback(spec, row, material, effectAsset) {
    validate(spec, row);
    if (!(material instanceof cc.Material) || uuid(material) !== row.creator.materialUuid ||
        uuid(material.effectAsset) !== row.creator.effectUuid || uuid(effectAsset) !== row.creator.effectUuid ||
        !verifyProperties(spec, row, material))
        throw Error('STATIC_TIME_MATERIAL_PERSISTENT_READBACK_MISMATCH');
    return { sourceMaterialId: row.sourceMaterialId, profile: row.profile, materialUuid: uuid(material),
        effectUuid: uuid(material.effectAsset), sourceMaterialDocumentSha256: row.sourceMaterialDocumentSha256,
        sourceEffectDocumentSha256: row.effectDocumentSha256, shaderPayloadSha256: spec.targetShaderSha256,
        staticTimeSeconds: 0, sourcePropertiesVerified: true, targetPropertiesVerified: true,
        targetProperties: { ...row.targetProperties },
        boundSpriteComponentIds: row.spriteBindings.map(x => x.sourceId).sort() };
}

async function createSerialized(spec, row, effectAsset, saveAndReload) {
    validate(spec, row);
    if (typeof saveAndReload !== 'function') throw Error('STATIC_TIME_ASSET_SAVER_REQUIRED');
    const candidate = create(spec, row, effectAsset);
    const record = await saveAndReload({ assetPath: row.creator.materialPath,
        assetBytes: serialize(spec, row, candidate), assetUuid: row.creator.materialUuid,
        metaPath: row.creator.materialMetaPath, expectedMetaUuid: row.creator.materialUuid });
    if (!record || record.assetPath !== row.creator.materialPath || record.metaPath !== row.creator.materialMetaPath ||
        record.uuid !== row.creator.materialUuid || record.metaUuid !== row.creator.materialUuid ||
        typeof record.metaContents !== 'string' || !record.material)
        throw Error('STATIC_TIME_ASSET_DB_SAVE_RECEIPT_MISMATCH');
    let meta;
    try { meta = JSON.parse(record.metaContents); } catch (_) { throw Error('STATIC_TIME_META_READBACK_INVALID'); }
    if (meta.uuid !== row.creator.materialUuid) throw Error('STATIC_TIME_META_UUID_READBACK_MISMATCH');
    return { material: record.material, readback: readback(spec, row, record.material, effectAsset), metaUuid: meta.uuid };
}

function expectedFrame(binding, resolveSpriteFrame) {
    const frame = resolveSpriteFrame && resolveSpriteFrame(binding.spriteFrameSourceId);
    if (!(frame instanceof cc.SpriteFrame)) throw Error('STATIC_TIME_SOURCE_FRAME_MISSING: ' + binding.spriteFrameSourceId);
    return frame;
}

function apply(spec, row, material, spritesBySourceId, resolveSpriteFrame) {
    validate(spec, row);
    if (!verifyProperties(spec, row, material) || typeof resolveSpriteFrame !== 'function')
        throw Error('STATIC_TIME_MATERIAL_NOT_VERIFIED');
    const entries = spritesBySourceId instanceof Map ? [...spritesBySourceId.entries()] : Object.entries(spritesBySourceId || {});
    const expected = new Set(row.spriteBindings.map(x => x.sourceId));
    if (entries.length !== expected.size || entries.some(([id]) => !expected.has(id)))
        throw Error('STATIC_TIME_SOURCE_SPRITE_MAP_MISMATCH');
    for (const [sourceId, sprite] of entries) {
        const binding = row.spriteBindings.find(x => x.sourceId === sourceId);
        const expected = expectedFrame(binding, resolveSpriteFrame);
        if (!(sprite instanceof cc.Sprite) || uuid(sprite.spriteFrame) !== uuid(expected))
            throw Error('STATIC_TIME_SOURCE_SPRITE_FRAME_MISMATCH: ' + sourceId);
        sprite.customMaterial = material;
        if (uuid(sprite.customMaterial) !== uuid(material) || uuid(sprite.spriteFrame) !== uuid(expected))
            throw Error('STATIC_TIME_SPRITE_MATERIAL_BINDING_MISMATCH: ' + sourceId);
    }
    return row.spriteBindings.map(x => ({ sourceId: x.sourceId, sourceMaterialId: row.sourceMaterialId,
        targetMaterialUuid: uuid(material), sourceFrameSourceId: x.spriteFrameSourceId,
        staticTimeSeconds: 0, targetPropertiesVerified: true }));
}

function readBound(spec, row, material, sourceId, sprite, resolveSpriteFrame) {
    validate(spec, row);
    const binding = row.spriteBindings.find(x => x.sourceId === sourceId);
    if (!binding || !verifyProperties(spec, row, material) || !(sprite instanceof cc.Sprite) || typeof resolveSpriteFrame !== 'function') return false;
    const expected = expectedFrame(binding, resolveSpriteFrame);
    return uuid(sprite.customMaterial) === uuid(material) && uuid(sprite.spriteFrame) === uuid(expected);
}

function readPersistent(spec, row, material, effectAsset, spritesBySourceId, resolveSpriteFrame) {
    const saved = readback(spec, row, material, effectAsset);
    const entries = spritesBySourceId instanceof Map ? [...spritesBySourceId.entries()] : Object.entries(spritesBySourceId || {});
    const expected = new Set(row.spriteBindings.map(x => x.sourceId));
    if (entries.length !== expected.size || entries.some(([id]) => !expected.has(id)))
        throw Error('STATIC_TIME_SOURCE_SPRITE_MAP_MISMATCH');
    for (const [sourceId, sprite] of entries)
        if (!readBound(spec, row, material, sourceId, sprite, resolveSpriteFrame))
            throw Error('STATIC_TIME_PERSISTENT_SPRITE_BINDING_MISMATCH: ' + sourceId);
    return saved;
}

module.exports = { create, serialize, createSerialized, readback, apply, readBound, readPersistent, verifyProperties };
