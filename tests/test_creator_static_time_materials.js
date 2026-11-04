'use strict';

const assert = require('node:assert/strict');
const Module = require('node:module');
const load = Module._load;

class EffectAsset { constructor(uuid) { this.uuid = uuid; } }
class Material {
    constructor() { this.uuid = '22222222-2222-2222-2222-222222222222'; this.technique = 0; this.props = {}; }
    initialize(config) { this.effectAsset = config.effectAsset; }
    setProperty(name, value) { this.props[name] = value; }
    getProperty(name) { return this.props[name]; }
}
class SpriteFrame { constructor(uuid) { this.uuid = uuid; } }
class Sprite { constructor(uuid, frame) { this.uuid = uuid; this.spriteFrame = frame; this.customMaterial = null; } }
class Color { constructor(r, g, b, a) { Object.assign(this, { r, g, b, a }); } }
const cc = { EffectAsset, Material, SpriteFrame, Sprite, Color };
Module._load = function (request, parent, isMain) {
    if (request === 'cc') return cc;
    return load.call(this, request, parent, isMain);
};

const helper = require('../src/monkey/targets/materials/static_time/CreatorStaticTimeMaterials.js');
const effect = new EffectAsset('11111111-1111-1111-1111-111111111111');
const frameUuid = '33333333-3333-3333-3333-333333333333';
const ownerFrame = new SpriteFrame(frameUuid);
const assetDbFrame = new SpriteFrame(frameUuid); // wrappers differ after native re-load
const sprite = new Sprite('44444444-4444-4444-4444-444444444444', ownerFrame);
const spec = { schema: 'monkey-prefab-static-time-materials/1',
    profile: 'cocos24-static-t0-sprite-effects-v1', target: 'creator', staticTimeSeconds: 0,
    targetShader: { creator: { uuid: effect.uuid } }, targetShaderSha256: 'a'.repeat(64) };
const row = { sourceMaterialId: 'fixture:material', profile: 'textured-uv-flow-t0-v1',
    staticTimeSeconds: 0, sourceMaterialDocumentSha256: 'b'.repeat(64), effectDocumentSha256: 'c'.repeat(64),
    creator: { effectUuid: effect.uuid, materialUuid: '22222222-2222-2222-2222-222222222222' },
    targetProperties: { sourceTimeSeconds: 0, sourceScalar0: 0.25, sourceScalar1: 0, sourceScalar2: 0,
        sourceScalar3: 0, sourceScalar4: 0, sourceScalar5: 0, sourceScalar6: 0, sourceColor: [1, 1, 1, 1] },
    spriteBindings: [{ sourceId: 'fixture:owner#5/sprite', sourceComponentId: 'fixture:template#2/sprite',
        spriteFrameSourceId: 'fixture:frame' }] };
const material = helper.create(spec, row, effect);
helper.apply(spec, row, material, new Map([[row.spriteBindings[0].sourceId, sprite]]),
    id => id === 'fixture:frame' ? assetDbFrame : null);
assert.equal(sprite.customMaterial.uuid, material.uuid);
assert.equal(sprite.spriteFrame.uuid, frameUuid);
assert.equal(helper.readBound(spec, row, material, row.spriteBindings[0].sourceId, sprite,
    id => id === 'fixture:frame' ? new SpriteFrame(frameUuid) : null), true);

// A wrong native UUID is rejected even if a wrapper is otherwise valid.
sprite.spriteFrame = new SpriteFrame('55555555-5555-5555-5555-555555555555');
assert.equal(helper.readBound(spec, row, material, row.spriteBindings[0].sourceId, sprite,
    id => id === 'fixture:frame' ? assetDbFrame : null), false);
assert.equal(material.getProperty('sourceTimeSeconds'), 0);
