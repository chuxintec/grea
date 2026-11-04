'use strict';
// Optional Creator 3.8 stage hooks for a source-profiled Sprite outline.
// The caller owns asset-db material persistence and invokes these hooks only
// when import-plan.json contains spriteOutlineBinding.
const cc = require('cc');
const bindings = require('./sprite-outline-material-bindings');

function rowsFor(spec, components) {
    if (!Array.isArray(components)) throw Error('SPRITE_OUTLINE_PLAN_COMPONENTS_MISSING');
    return spec.spriteBindings.map(binding => {
        const component = components.find(row => row.sourceId === binding.sourceId);
        if (!component || component.type !== 'cc.Sprite' || !component.convertible ||
            component.spriteFrame !== binding.spriteFrameSourceId || !component.node)
            throw Error('SPRITE_OUTLINE_PLAN_COMPONENT_MISMATCH: ' + binding.sourceId);
        return { binding, component };
    });
}

function buildSpriteMap(spec, components, nodes, resolveSpriteFrame) {
    if (!(nodes instanceof Map) || typeof resolveSpriteFrame !== 'function')
        throw Error('SPRITE_OUTLINE_IMPORT_CONTEXT_MISSING');
    const sprites = new Map();
    for (const { binding, component } of rowsFor(spec, components)) {
        const node = nodes.get(component.node);
        const sprite = node && node.getComponent(cc.Sprite);
        const frame = resolveSpriteFrame(binding.spriteFrameSourceId);
        if (!(sprite instanceof cc.Sprite) || !(frame instanceof cc.SpriteFrame) ||
            !bindings.sameSpriteFrame(sprite.spriteFrame, frame))
            throw Error('SPRITE_OUTLINE_SOURCE_FRAME_MISMATCH: ' + binding.sourceId);
        if (Math.abs(frame.rect.width - spec.properties.outlineTextureSize[0]) > 0.01 ||
            Math.abs(frame.rect.height - spec.properties.outlineTextureSize[1]) > 0.01)
            throw Error('SPRITE_OUTLINE_TEXTURE_SIZE_MISMATCH: ' + binding.sourceId);
        sprites.set(binding.sourceId, sprite);
    }
    return sprites;
}

async function createMaterial(spec, effectAsset, saveAndReload) {
    return bindings.createSaveReadback(spec, effectAsset, saveAndReload);
}

function bind(spec, components, nodes, material, resolveSpriteFrame) {
    const sprites = buildSpriteMap(spec, components, nodes, resolveSpriteFrame);
    return bindings.bind(spec, material, sprites, resolveSpriteFrame);
}

function resolveReference(spec, id, nativeReferences) {
    if (!spec || !id || id !== spec.materialSourceId) return undefined;
    if (!(nativeReferences instanceof Map)) throw Error('SPRITE_OUTLINE_NATIVE_REFERENCE_MAP_MISSING');
    return nativeReferences.get(id);
}

function readSaved(spec, components, nodes, material, effectAsset, resolveSpriteFrame, prefabId) {
    const wanted = spec.spriteBindings.filter(row => row.sourceId.startsWith(prefabId + '#'));
    if (!wanted.length) return { sourcePrefabId: prefabId, status: 'not-applicable', verified: true, spriteBindings: [] };
    const all = buildSpriteMap(spec, components, nodes, resolveSpriteFrame);
    const readback = bindings.readback(spec, material, effectAsset);
    for (const row of wanted) {
        const sprite = all.get(row.sourceId);
        if (!sprite || !bindings.readBound(spec, material, row.sourceId, sprite, resolveSpriteFrame))
            throw Error('SPRITE_OUTLINE_COMPONENT_PERSISTED_READBACK_MISMATCH: ' + row.sourceId);
    }
    return { sourcePrefabId: prefabId, status: 'creator-native-readback', verified: true,
        materialUuid: readback.materialUuid, effectUuid: readback.effectUuid,
        spriteBindings: wanted.map(row => ({ sourceId: row.sourceId,
            spriteFrameSourceId: row.spriteFrameSourceId, materialUuid: readback.materialUuid })) };
}

module.exports = { createMaterial, bind, readSaved, resolveReference, buildSpriteMap };
