'use strict';
// Creator Editor helper for exact native outline Effect/Material identity and
// scene Sprite bindings. No source code, source UUIDs or assets are executed.
const cc = require('cc');

const PROFILE = 'cocos24-sprite-alpha-outline-v1';
const PROGRAM_HASH = '53fbec41d8b524d31908b3b27f1b6cccbd2fcd1eb0be9ace5917be386dad4784';
const EPSILON = 0.0001;

function uuid(asset) { return asset && (asset.uuid || asset._uuid); }
function sameSpriteFrame(actual, expected) {
    const actualUuid = uuid(actual), expectedUuid = uuid(expected);
    return actual instanceof cc.SpriteFrame && expected instanceof cc.SpriteFrame &&
        typeof actualUuid === 'string' && actualUuid.length > 0 && actualUuid === expectedUuid;
}
function validate(spec) {
    if (!spec || spec.schema !== 'monkey-prefab-sprite-outline-binding/1' || spec.profile !== PROFILE ||
        spec.programCanonicalSha256 !== PROGRAM_HASH || !spec.creator)
        throw Error('SPRITE_OUTLINE_PROFILE_UNSUPPORTED');
    const p = spec.properties || {};
    if (!Array.isArray(p.outlineColor) || p.outlineColor.length !== 4 ||
        !Array.isArray(p.outlineTextureSize) || p.outlineTextureSize.length !== 2 ||
        !Number.isFinite(p.outlineWidth) || p.outlineWidth < 0 || p.outlineWidth > 8 ||
        !Number.isFinite(p.fillAlpha) || p.fillAlpha < 0 || p.fillAlpha > 1 ||
        !Number.isFinite(p.alphaThreshold) || p.alphaThreshold < 0 || p.alphaThreshold >= 1)
        throw Error('SPRITE_OUTLINE_PROPERTIES_INVALID');
    if (!Array.isArray(spec.sourceComponentIds) || !spec.sourceComponentIds.length ||
        !Array.isArray(spec.spriteBindings) || spec.spriteBindings.length !== spec.sourceComponentIds.length ||
        spec.spriteBindings.some((row, i) => !row || row.sourceId !== spec.sourceComponentIds[i] || !row.spriteFrameSourceId))
        throw Error('SPRITE_OUTLINE_SOURCE_BINDINGS_INVALID');
    if (!/^[0-9a-f-]{36}$/i.test(spec.creator.effectUuid || '') ||
        !/^[0-9a-f-]{36}$/i.test(spec.creator.materialUuid || ''))
        throw Error('SPRITE_OUTLINE_CREATOR_IDENTITY_INVALID');
}
function near(a, b) { return Number.isFinite(a) && Math.abs(a - b) <= EPSILON; }
function vec2(value) {
    if (Array.isArray(value) && value.length === 2) return value;
    if (value && Number.isFinite(value.x) && Number.isFinite(value.y)) return [value.x, value.y];
    return null;
}
function rgba(value) {
    if (value && Number.isFinite(value.x) && Number.isFinite(value.y) && Number.isFinite(value.z) && Number.isFinite(value.w))
        return [value.x, value.y, value.z, value.w];
    if (value && Number.isFinite(value.r) && Number.isFinite(value.g) && Number.isFinite(value.b) && Number.isFinite(value.a)) {
        const factor = Math.max(value.r, value.g, value.b, value.a) > 1 ? 1 / 255 : 1;
        return [value.r * factor, value.g * factor, value.b * factor, value.a * factor];
    }
    return null;
}
function verifyProperties(spec, material) {
    if (!material || material.technique !== 0) return false;
    const p = spec.properties;
    const color = rgba(material.getProperty('outlineColor'));
    const size = vec2(material.getProperty('outlineTextureSize'));
    return !!color && !!size && color.every((v, i) => near(v, p.outlineColor[i])) &&
        size.every((v, i) => near(v, p.outlineTextureSize[i])) &&
        near(material.getProperty('outlineWidth'), p.outlineWidth) &&
        near(material.getProperty('fillAlpha'), p.fillAlpha) &&
        near(material.getProperty('alphaThreshold'), p.alphaThreshold);
}
function create(spec, effectAsset) {
    validate(spec);
    if (!(effectAsset instanceof cc.EffectAsset) || uuid(effectAsset) !== spec.creator.effectUuid)
        throw Error('SPRITE_OUTLINE_EFFECT_NATIVE_IDENTITY_MISMATCH');
    const material = new cc.Material();
    material.name = 'Shader2DOutline';
    material.initialize({ effectAsset, technique: 0, defines: { USE_TEXTURE: true } });
    const p = spec.properties;
    material.setProperty('outlineColor', new cc.Color(p.outlineColor[0] * 255, p.outlineColor[1] * 255,
        p.outlineColor[2] * 255, p.outlineColor[3] * 255));
    material.setProperty('outlineTextureSize', new cc.Vec2(p.outlineTextureSize[0], p.outlineTextureSize[1]));
    material.setProperty('outlineWidth', p.outlineWidth);
    material.setProperty('fillAlpha', p.fillAlpha);
    material.setProperty('alphaThreshold', p.alphaThreshold);
    if (!verifyProperties(spec, material)) throw Error('SPRITE_OUTLINE_NATIVE_CREATE_READBACK_MISMATCH');
    return material;
}
function serialize(spec, material) {
    validate(spec);
    if (uuid(material && material.effectAsset) !== spec.creator.effectUuid || !verifyProperties(spec, material))
        throw Error('SPRITE_OUTLINE_PRE_SAVE_MISMATCH');
    if (typeof EditorExtends === 'undefined' || typeof EditorExtends.serialize !== 'function')
        throw Error('SPRITE_OUTLINE_EDITOR_SERIALIZER_UNAVAILABLE');
    const serialized = EditorExtends.serialize(material);
    return typeof serialized === 'string' ? serialized : JSON.stringify(serialized);
}
function readback(spec, material, effectAsset) {
    validate(spec);
    if (!(material instanceof cc.Material) || uuid(material) !== spec.creator.materialUuid ||
        uuid(material.effectAsset) !== spec.creator.effectUuid || uuid(effectAsset) !== spec.creator.effectUuid ||
        !verifyProperties(spec, material)) throw Error('SPRITE_OUTLINE_NATIVE_PERSISTED_READBACK_MISMATCH');
    return { materialUuid: uuid(material), effectUuid: uuid(material.effectAsset), technique: material.technique,
        propertiesVerified: true, properties: { ...spec.properties }, status: 'creator-editor-readback' };
}
async function createSaveReadback(spec, effectAsset, saveAndReload) {
    validate(spec);
    if (typeof saveAndReload !== 'function') throw Error('SPRITE_OUTLINE_ASSET_SAVER_REQUIRED');
    const candidate = create(spec, effectAsset);
    const record = await saveAndReload({ assetPath: spec.creator.materialPath,
        assetBytes: serialize(spec, candidate), assetUuid: spec.creator.materialUuid,
        metaPath: spec.creator.materialMetaPath, expectedMetaUuid: spec.creator.materialUuid });
    if (!record || record.assetPath !== spec.creator.materialPath || record.metaPath !== spec.creator.materialMetaPath ||
        record.uuid !== spec.creator.materialUuid || record.metaUuid !== spec.creator.materialUuid ||
        typeof record.metaContents !== 'string' || !record.material)
        throw Error('SPRITE_OUTLINE_ASSET_DB_SAVE_RECEIPT_MISMATCH');
    let meta;
    try { meta = JSON.parse(record.metaContents); } catch (_) { throw Error('SPRITE_OUTLINE_META_READBACK_INVALID'); }
    if (meta.uuid !== spec.creator.materialUuid) throw Error('SPRITE_OUTLINE_META_UUID_READBACK_MISMATCH');
    return { material: record.material, readback: { ...readback(spec, record.material, effectAsset), metaUuid: meta.uuid } };
}
function expectedFrame(spec, sourceId, resolve) {
    const binding = spec.spriteBindings.find(row => row.sourceId === sourceId);
    const frame = binding && resolve(binding.spriteFrameSourceId);
    if (!(frame instanceof cc.SpriteFrame)) throw Error('SPRITE_OUTLINE_SOURCE_FRAME_MISSING: ' + (binding && binding.spriteFrameSourceId));
    return frame;
}
function bind(spec, savedMaterial, spritesBySourceId, resolveSpriteFrame) {
    validate(spec);
    if (!verifyProperties(spec, savedMaterial) || typeof resolveSpriteFrame !== 'function')
        throw Error('SPRITE_OUTLINE_MATERIAL_NOT_VERIFIED');
    const keys = spritesBySourceId instanceof Map ? [...spritesBySourceId.keys()] : Object.keys(spritesBySourceId || {});
    if (keys.length !== spec.sourceComponentIds.length || spec.sourceComponentIds.some(id => !keys.includes(id)))
        throw Error('SPRITE_OUTLINE_SOURCE_SPRITE_MAP_MISMATCH');
    for (const sourceId of spec.sourceComponentIds) {
        const sprite = spritesBySourceId instanceof Map ? spritesBySourceId.get(sourceId) : spritesBySourceId[sourceId];
        if (!(sprite instanceof cc.Sprite) || !sameSpriteFrame(sprite.spriteFrame, expectedFrame(spec, sourceId, resolveSpriteFrame)))
            throw Error('SPRITE_OUTLINE_SOURCE_SPRITEFRAME_MISMATCH: ' + sourceId);
        const current = sprite.customMaterial;
        if (current && uuid(current) !== uuid(savedMaterial) && current.parent !== savedMaterial)
            throw Error('SPRITE_OUTLINE_EXISTING_CUSTOM_MATERIAL_CONFLICT: ' + sourceId);
        sprite.customMaterial = savedMaterial;
        if (!sameSpriteFrame(sprite.spriteFrame, expectedFrame(spec, sourceId, resolveSpriteFrame)) ||
            !sprite.customMaterial || (sprite.customMaterial !== savedMaterial && uuid(sprite.customMaterial) !== uuid(savedMaterial) && sprite.customMaterial.parent !== savedMaterial))
            throw Error('SPRITE_OUTLINE_BINDING_READBACK_MISMATCH: ' + sourceId);
    }
    return spec.sourceComponentIds.map(sourceId => ({ sourceId, materialUuid: uuid(savedMaterial),
        effectUuid: uuid(savedMaterial.effectAsset), spriteFrameSourceId: spec.spriteBindings.find(row => row.sourceId === sourceId).spriteFrameSourceId,
        propertiesVerified: true }));
}
function readPersistent(spec, savedMaterial, spritesBySourceId, effectAsset, resolveSpriteFrame) {
    const material = readback(spec, savedMaterial, effectAsset);
    const keys = spritesBySourceId instanceof Map ? [...spritesBySourceId.keys()] : Object.keys(spritesBySourceId || {});
    if (keys.length !== spec.sourceComponentIds.length || spec.sourceComponentIds.some(id => !keys.includes(id)))
        throw Error('SPRITE_OUTLINE_SOURCE_SPRITE_MAP_MISMATCH');
    for (const sourceId of spec.sourceComponentIds) {
        const sprite = spritesBySourceId instanceof Map ? spritesBySourceId.get(sourceId) : spritesBySourceId[sourceId];
        if (!(sprite instanceof cc.Sprite) || !sameSpriteFrame(sprite.spriteFrame, expectedFrame(spec, sourceId, resolveSpriteFrame)) ||
            !sprite.customMaterial || (sprite.customMaterial !== savedMaterial && uuid(sprite.customMaterial) !== uuid(savedMaterial) && sprite.customMaterial.parent !== savedMaterial))
            throw Error('SPRITE_OUTLINE_COMPONENT_PERSISTED_READBACK_MISMATCH: ' + sourceId);
    }
    return { ...material, spriteBindings: spec.spriteBindings.map(row => ({ ...row, materialUuid: material.materialUuid })) };
}

function readBound(spec, savedMaterial, sourceId, sprite, resolveSpriteFrame) {
    validate(spec);
    if (!spec.sourceComponentIds.includes(sourceId) || !verifyProperties(spec, savedMaterial) ||
        !(sprite instanceof cc.Sprite) || typeof resolveSpriteFrame !== 'function') return false;
    const frame = expectedFrame(spec, sourceId, resolveSpriteFrame);
    const custom = sprite.customMaterial;
    return sameSpriteFrame(sprite.spriteFrame, frame) && !!custom &&
        (custom === savedMaterial || uuid(custom) === uuid(savedMaterial) || custom.parent === savedMaterial);
}

module.exports = { create, serialize, createSaveReadback, readback, bind, readBound, readPersistent, verifyProperties, sameSpriteFrame };
