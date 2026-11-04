'use strict';
const cc = require('cc');

const PROFILE = 'cocos24-ui-color-sprite-v1';
const PROGRAM_HASH = 'b4e5e249e052cb9370d4e4995b6d5f2f223e8e9cba447d28d2a2d2d0bf4f9b9d';
const EPSILON = 0.0001;
const PROPERTIES = ['brightness', 'saturation', 'constrast', 'gray', 'silhouette'];

function uuid(asset) { return asset && (asset.uuid || asset._uuid); }

function validate(spec) {
    if (!spec || spec.profile !== PROFILE || spec.programCanonicalSha256 !== PROGRAM_HASH)
        throw Error('MATERIAL_PROFILE_UNSUPPORTED');
    const paths = spec.creator || {};
    const segment = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(spec.module || '');
    if (!segment || paths.effectPath !== `assets/resources/Shaders/${spec.module}/Shader2DUIColor.effect` ||
        paths.materialPath !== `assets/resources/Materials/${spec.module}/Shader2DUIColor.mtl`)
        throw Error('MATERIAL_ASSET_PATH_UNSUPPORTED');
    if (!/^[0-9a-f-]{36}$/i.test(paths.effectUuid || '') || !/^[0-9a-f-]{36}$/i.test(paths.materialUuid || ''))
        throw Error('MATERIAL_NATIVE_UUID_MISSING');
    if (typeof spec.materialSourceId !== 'string' || !spec.materialSourceId)
        throw Error('MATERIAL_SOURCE_ID_MISSING');
    const values = spec.properties || {};
    if (!PROPERTIES.every(name => Object.prototype.hasOwnProperty.call(values, name)))
        throw Error('MATERIAL_PROPERTY_CONTRACT_INCOMPLETE');
    for (const name of PROPERTIES.slice(0, 4)) if (!Number.isFinite(values[name])) throw Error('MATERIAL_PROPERTY_NONFINITE: ' + name);
    if (!Array.isArray(values.silhouette) || values.silhouette.length !== 4 || !values.silhouette.every(Number.isFinite))
        throw Error('MATERIAL_PROPERTY_INVALID: silhouette');
}

function sameNumber(actual, expected) {
    return Number.isFinite(actual) && Math.abs(actual - expected) <= EPSILON;
}

function colorValues(value) {
    if (value && Number.isFinite(value.x) && Number.isFinite(value.y) && Number.isFinite(value.z) && Number.isFinite(value.w))
        return [value.x, value.y, value.z, value.w];
    if (value && Number.isFinite(value.r) && Number.isFinite(value.g) && Number.isFinite(value.b) && Number.isFinite(value.a)) {
        const factor = Math.max(value.r, value.g, value.b, value.a) > 1 ? 1 / 255 : 1;
        return [value.r * factor, value.g * factor, value.b * factor, value.a * factor];
    }
    throw Error('MATERIAL_COLOR_READBACK_TYPE');
}

function verifyProperties(spec, material) {
    if (!material || material.technique !== 0) return false;
    for (const name of PROPERTIES.slice(0, 4)) {
        if (!sameNumber(material.getProperty(name), spec.properties[name])) return false;
    }
    let observed;
    try { observed = colorValues(material.getProperty('silhouette')); }
    catch (_) { return false; }
    return observed.every((value, index) => sameNumber(value, spec.properties.silhouette[index]));
}

function create(spec, effectAsset) {
    validate(spec);
    // Creator may prefix an Effect's display name with its importer-relative
    // resource path. Identity is the planned UUID of the hash-pinned asset.
    if (!(effectAsset instanceof cc.EffectAsset) || uuid(effectAsset) !== spec.creator.effectUuid)
        throw Error('MATERIAL_EFFECT_NATIVE_IDENTITY_MISMATCH');
    const material = new cc.Material();
    material.name = 'Shader2DUIColor';
    material.initialize({ effectAsset, technique: 0, defines: { USE_TEXTURE: true } });
    const values = spec.properties;
    material.setProperty('brightness', values.brightness);
    material.setProperty('saturation', values.saturation);
    material.setProperty('constrast', values.constrast);
    material.setProperty('gray', values.gray);
    material.setProperty('silhouette', new cc.Color(
        values.silhouette[0] * 255, values.silhouette[1] * 255,
        values.silhouette[2] * 255, values.silhouette[3] * 255));
    if (uuid(material.effectAsset) !== spec.creator.effectUuid || !verifyProperties(spec, material))
        throw Error('MATERIAL_NATIVE_CREATE_READBACK_MISMATCH');
    return material;
}

function serialize(spec, material) {
    validate(spec);
    if (uuid(material && material.effectAsset) !== spec.creator.effectUuid || !verifyProperties(spec, material))
        throw Error('MATERIAL_NATIVE_PRE_SAVE_MISMATCH');
    if (typeof EditorExtends === 'undefined' || typeof EditorExtends.serialize !== 'function')
        throw Error('MATERIAL_EDITOR_SERIALIZER_UNAVAILABLE');
    const serialized = EditorExtends.serialize(material);
    return typeof serialized === 'string' ? serialized : JSON.stringify(serialized);
}

function readback(spec, savedMaterial, effectAsset) {
    validate(spec);
    if (!(savedMaterial instanceof cc.Material) || !uuid(savedMaterial) ||
        uuid(savedMaterial) !== spec.creator.materialUuid ||
        uuid(savedMaterial.effectAsset) !== spec.creator.effectUuid || uuid(effectAsset) !== spec.creator.effectUuid ||
        !verifyProperties(spec, savedMaterial))
        throw Error('MATERIAL_NATIVE_PERSISTED_READBACK_MISMATCH');
    return { sourceId: spec.materialSourceId, materialUuid: uuid(savedMaterial), effectUuid: uuid(savedMaterial.effectAsset),
        technique: savedMaterial.technique, propertiesVerified: true,
        properties:Object.fromEntries(PROPERTIES.map(name=>[name,name==='silhouette'?colorValues(savedMaterial.getProperty(name)):savedMaterial.getProperty(name)])),
        status: 'creator-editor-readback' };
}

async function createSaveReadback(spec, effectAsset, saveAndReload) {
    validate(spec);
    if (typeof saveAndReload !== 'function') throw Error('MATERIAL_ASSET_SAVER_REQUIRED');
    const candidate = create(spec, effectAsset);
    const bytes = serialize(spec, candidate);
    // The host callback must create/verify the adjacent .mtl.meta UUID immediately
    // before writing the serialized asset, import it, then report the asset path,
    // metadata UUID/content and loaded cc.Material. The helper checks those receipts.
    const record = await saveAndReload({ assetPath: spec.creator.materialPath, assetBytes: bytes,
        assetUuid: spec.creator.materialUuid, metaPath: spec.creator.materialMetaPath,
        expectedMetaUuid: spec.creator.materialUuid });
    if (!record || record.assetPath !== spec.creator.materialPath || record.metaPath !== spec.creator.materialMetaPath ||
        record.uuid !== spec.creator.materialUuid ||
        !record.material || typeof record.metaContents !== 'string')
        throw Error('MATERIAL_ASSET_DB_SAVE_RECEIPT_MISMATCH');
    let meta;
    try { meta = JSON.parse(record.metaContents); }
    catch (_) { throw Error('MATERIAL_META_READBACK_INVALID'); }
    if (meta.uuid !== spec.creator.materialUuid || record.metaUuid !== spec.creator.materialUuid)
        throw Error('MATERIAL_META_UUID_READBACK_MISMATCH');
    return { material: record.material,
        readback: { ...readback(spec, record.material, effectAsset), metaUuid: meta.uuid, metaUuidVerified: true } };
}

function expectedBindings(spec) {
    const ids = (spec.spriteBindings || []).map(row=>row.sourceId);
    if (ids.some(id => typeof id !== 'string' || !id || !(spec.sourceComponentIds||[]).includes(id)) || new Set(ids).size !== ids.length)
        throw Error('MATERIAL_SOURCE_COMPONENT_IDS_INVALID');
    return ids;
}

function mapGet(spritesBySourceId, sourceId) {
    return spritesBySourceId instanceof Map ? spritesBySourceId.get(sourceId) : spritesBySourceId[sourceId];
}

function readBound(spec, savedMaterial, sprite) {
    validate(spec);
    if (!(sprite instanceof cc.Sprite) || !verifyProperties(spec, savedMaterial)) return false;
    const actual = sprite.customMaterial;
    if (!actual || (actual !== savedMaterial && uuid(actual) !== uuid(savedMaterial) && actual.parent !== savedMaterial)) return false;
    return uuid(actual.effectAsset) === spec.creator.effectUuid && verifyProperties(spec, actual);
}

function bind(spec, savedMaterial, spritesBySourceId) {
    validate(spec);
    const ids = expectedBindings(spec);
    const keys = spritesBySourceId instanceof Map ? Array.from(spritesBySourceId.keys()) : Object.keys(spritesBySourceId || {});
    if (keys.length !== ids.length || ids.some(id => !keys.includes(id))) throw Error('MATERIAL_SOURCE_SPRITE_MAP_MISMATCH');
    for (const sourceId of ids) {
        const sprite = mapGet(spritesBySourceId, sourceId);
        if (!(sprite instanceof cc.Sprite)) throw Error('MATERIAL_SOURCE_COMPONENT_TYPE_UNSUPPORTED: ' + sourceId);
        const current = sprite.customMaterial;
        if (current && uuid(current) !== uuid(savedMaterial) && current.parent !== savedMaterial)
            throw Error('MATERIAL_EXISTING_CUSTOM_MATERIAL_CONFLICT: ' + sourceId);
        sprite.customMaterial = savedMaterial;
        if (!readBound(spec, savedMaterial, sprite)) throw Error('MATERIAL_COMPONENT_BINDING_READBACK_MISMATCH: ' + sourceId);
    }
    return ids.map(sourceId => ({ sourceId, materialUuid: uuid(savedMaterial), effectUuid: uuid(savedMaterial.effectAsset), propertiesVerified: true }));
}

function readPersistent(spec, savedMaterial, spritesBySourceId, effectAsset) {
    const material = readback(spec, savedMaterial, effectAsset);
    const ids = expectedBindings(spec);
    const keys = spritesBySourceId instanceof Map ? Array.from(spritesBySourceId.keys()) : Object.keys(spritesBySourceId || {});
    if (keys.length !== ids.length || ids.some(id => !keys.includes(id))) throw Error('MATERIAL_SOURCE_SPRITE_MAP_MISMATCH');
    for (const sourceId of ids) {
        if (!readBound(spec, savedMaterial, mapGet(spritesBySourceId, sourceId)))
            throw Error('MATERIAL_COMPONENT_PERSISTED_READBACK_MISMATCH: ' + sourceId);
    }
    return { ...material, spriteBindings: ids.map(sourceId => ({ sourceId, materialUuid: material.materialUuid })) };
}

module.exports = { create, serialize, createSaveReadback, readback, bind, readBound, readPersistent };
