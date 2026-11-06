'use strict';

const assert = require('node:assert/strict');
const Module = require('node:module');
const fs = require('node:fs');
const path = require('node:path');
const load = Module._load;

class Material { constructor(uuid, effectAsset) { this.uuid = uuid; this.effectAsset = effectAsset; this.technique = 0; } }
class SpriteFrame { constructor(uuid) { this.uuid = uuid; this.rect = { width: 128, height: 128 }; } }
class Sprite { constructor(frame, material) { this.spriteFrame = frame; this.customMaterial = material; } }
const cc = { Material, SpriteFrame, Sprite, Color: class {}, Vec2: class {} };
Module._load = function (request, parent, isMain) {
    if (request === 'cc') return cc;
    return load.call(this, request, parent, isMain);
};

const helperSource = path.resolve(__dirname, '../src/monkey/targets/materials/sprite_outline');
const emitted = fs.mkdtempSync(path.join('/private/tmp', 'sprite-outline-creator-test-'));
fs.copyFileSync(path.join(helperSource, 'CreatorSpriteOutlineImporter.js'), path.join(emitted, 'sprite-outline-importer.js'));
fs.copyFileSync(path.join(helperSource, 'CreatorSpriteOutlineMaterialBindings.js'), path.join(emitted, 'sprite-outline-material-bindings.js'));
const importer = require(path.join(emitted, 'sprite-outline-importer.js'));
const effectAsset = { uuid: '11111111-1111-1111-1111-111111111111' };
const material = new Material('22222222-2222-2222-2222-222222222222', effectAsset);
const properties = {
    outlineColor: { x: 0.2, y: 0.6, z: 0.9, w: 1 },
    outlineTextureSize: { x: 128, y: 128 },
    outlineWidth: 5,
    fillAlpha: 0,
    alphaThreshold: 0.01,
};
material.getProperty = name => properties[name];
const spec = {
    schema: 'monkey-prefab-sprite-outline-binding/1',
    profile: 'cocos24-sprite-alpha-outline-v1',
    programCanonicalSha256: '53fbec41d8b524d31908b3b27f1b6cccbd2fcd1eb0be9ace5917be386dad4784',
    materialSourceId: 'fixture:material',
    properties: { outlineColor: [0.2, 0.6, 0.9, 1], outlineTextureSize: [128, 128], outlineWidth: 5, fillAlpha: 0, alphaThreshold: 0.01 },
    creator: { effectUuid: effectAsset.uuid, materialUuid: material.uuid },
    sourceComponentIds: ['fixture:prefab#4'],
    spriteBindings: [{ sourceId: 'fixture:prefab#4', spriteFrameSourceId: 'fixture:frame' }],
};
const frameUuid = '33333333-3333-3333-3333-333333333333@f9941';
const prefabReloadFrame = new SpriteFrame(frameUuid);
// Asset DB and a reloaded Prefab may expose separate JS wrappers for the same
// persisted SpriteFrame. Identity must follow the native UUID, not object ===.
const resolvedAssetFrame = new SpriteFrame(frameUuid);
const sprite = new Sprite(prefabReloadFrame, material);
const components = [{ sourceId: 'fixture:prefab#4', type: 'cc.Sprite', convertible: true,
    spriteFrame: 'fixture:frame', node: 'fixture:node' }];
const nodes = new Map([['fixture:node', { getComponent(type) { return type === Sprite ? sprite : null; } }]]);
const resolveFrame = id => id === 'fixture:frame' ? resolvedAssetFrame : null;

const result = importer.readSaved(spec, components, nodes, material, effectAsset, resolveFrame, 'fixture:prefab');
assert.equal(result.verified, true);
assert.deepEqual(result.spriteBindings, [{ sourceId: 'fixture:prefab#4',
    spriteFrameSourceId: 'fixture:frame', materialUuid: material.uuid }]);

const wrongFrame = new SpriteFrame();
sprite.spriteFrame = wrongFrame;
assert.throws(() => importer.readSaved(spec, components, nodes, material, effectAsset, resolveFrame, 'fixture:prefab'),
    /SPRITE_OUTLINE_SOURCE_FRAME_MISMATCH/);
sprite.spriteFrame = prefabReloadFrame;
sprite.customMaterial = { uuid: '44444444-4444-4444-4444-444444444444' };
assert.throws(() => importer.readSaved(spec, components, nodes, material, effectAsset, resolveFrame, 'fixture:prefab'),
    /SPRITE_OUTLINE_COMPONENT_PERSISTED_READBACK_MISMATCH/);
Module._load = load;
fs.rmSync(emitted, { recursive: true, force: true });
