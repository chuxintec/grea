'use strict';

const assert = require('node:assert/strict');
const Module = require('node:module');
const load = Module._load;

class Component { constructor(node) { this.node = node; this.enabled = true; } }
class Texture { constructor(uuid, width = 2048, height = 2048) { this._uuid = uuid; this.uuid = uuid; this.width = width; this.height = height; } }
class SpriteFrame {
    constructor(uuid, width = 676, height = 916, overrides = {}) {
        this._uuid = uuid; this.uuid = uuid; this.texture = new Texture('native-texture-uuid');
        this.rect = {x: 0, y: 0, width, height}; this.originalSize = {width, height}; this.offset = {x: 0, y: 0};
        this.rotated = false; this.insetTop = 0; this.insetBottom = 0; this.insetLeft = 0; this.insetRight = 0;
        this.flipUVX = false; this.flipUVY = false; this.packable = true; this.pixelsToUnit = 100;
        this.pivot = {x: 0.5, y: 0.5}; this._meshType = 0; this.atlasUuid = ''; this.vertices = null;
        Object.assign(this, overrides);
    }
}
class Sprite extends Component {
    constructor(node) { super(node); this._spriteFrame = null; this._sizeMode = Sprite.SizeMode.TRIMMED; }
    get sizeMode() { return this._sizeMode; }
    set sizeMode(value) { this._sizeMode = value; }
    get spriteFrame() { return this._spriteFrame; }
    set spriteFrame(value) {
        this._spriteFrame = value;
        if (value && this._sizeMode !== Sprite.SizeMode.CUSTOM)
            this.node.setContentSize(value.rect.width, value.rect.height);
    }
}
Sprite.SizeMode = { CUSTOM: 0, TRIMMED: 1, RAW: 2 };
class Graphics extends Component {}
class Mask extends Component {
    constructor(node) { super(node); this.uuid = 'native-mask-component'; this._type = 0; this._inverted = false; this._alphaThreshold = 0.1; this.subComp = null; }
    set type(value) { this._type = value; if (value === Mask.Type.SPRITE_STENCIL) this.subComp = this.node.getComponent(Sprite); }
    get type() { return this._type; }
    set spriteFrame(value) { if (this.subComp) this.subComp.spriteFrame = value; }
    get spriteFrame() { return this.subComp ? this.subComp.spriteFrame : null; }
    set inverted(value) { this._inverted = value; }
    get inverted() { return this._inverted; }
    set alphaThreshold(value) { this._alphaThreshold = value; }
    get alphaThreshold() { return this._alphaThreshold; }
    onLoad() { if (this._type === Mask.Type.SPRITE_STENCIL) this.subComp = this.node.getComponent(Sprite); else this.subComp = {}; }
}
Mask.Type = { GRAPHICS_RECT: 0, GRAPHICS_ELLIPSE: 1, GRAPHICS_STENCIL: 2, SPRITE_STENCIL: 3 };
class Identity extends Component {
    constructor(node) {
        super(node); this.sourceId = ''; this.nativeId = ''; this.sourceMaskType = -1;
        this.sourceInverted = false; this.sourceAlphaThreshold = 0.1; this.sourceFieldsJson = '';
        this.sourceSpriteFrameUuid = ''; this.sourceSpriteFrame = null; this.nativeMask = null;
    }
}
class Node {
    constructor() { this.components = []; this.contentSize = {width: 0, height: 0}; }
    setContentSize(width, height) { this.contentSize = {width, height}; }
    addComponent(Type) { const value = new Type(this); this.components.push(value); return value; }
    getComponent(Type) { return this.components.find(value => value instanceof Type) || null; }
    getComponents(Type) { return this.components.filter(value => value instanceof Type); }
}
const cc = { Component, SpriteFrame, Sprite, Graphics, Mask, js: { getClassByName: name => name === 'MonkeyStaticMaskIdentity' ? Identity : null } };
Module._load = function (request, parent, isMain) {
    if (request === 'cc') return cc;
    return load.call(this, request, parent, isMain);
};

const helper = require('../src/monkey/targets/CreatorStaticMaskSort.js');
const sourceSpriteId = 'source-frame-uuid';
const nativeSpriteUuid = 'creator-imported-asset-uuid';
const frame = new SpriteFrame(nativeSpriteUuid);
const spec = { sourceId: 'source-mask-id', nativeId: 'native-mask-id', node: 'source-node',
    maskType: 2, inverted: false, enabled: true, alphaThreshold: 1,
    spriteFrameUuid: sourceSpriteId,
    sourceFields: { __type__: 'cc.Mask', _N$alphaThreshold: 1, _spriteFrame: { __uuid__: sourceSpriteId } } };
const node = new Node();
node.setContentSize(678, 922);
assert.equal(node.getComponent(Sprite), null, 'source image Mask has no authored Sprite component');
const nodes = new Map([[spec.node, node]]);
const resolveSprite = id => id === sourceSpriteId ? frame : null;

const created = helper.createStaticMasks([spec], nodes, resolveSprite);
const sprite = node.getComponent(Sprite);
assert.ok(sprite instanceof Sprite, 'image Mask creates its actual native Sprite backing');
assert.equal(created.length, 1);
assert.equal(created[0].verified, true);
assert.equal(created[0].alphaThreshold, 1, 'source alpha threshold 1 is retained verbatim');
assert.equal(created[0].sourceSpriteFrameUuid, sourceSpriteId);
assert.equal(created[0].nativeSpriteFrameUuid, nativeSpriteUuid,
    'source UUID and Creator imported SpriteFrame UUID are distinct fields');
assert.deepEqual(created[0].failedChecks, [], 'successful rows carry an empty field-specific failure list');
assert.equal(created[0].checks.identityNativeMaskReference, true);
assert.equal(created[0].expected.nativeId, spec.nativeId);
assert.equal(created[0].actual.identity.nativeMaskUuid, node.getComponent(Mask).uuid);
assert.equal(created[0].actual.backingRenderer.type, 'Sprite');
assert.equal(created[0].expected.resolvedSpriteFrameUuid, nativeSpriteUuid);
assert.equal(created[0].initialized, true);
assert.equal(created[0].initializedBackingVerified, true);
assert.equal(sprite.sizeMode, Sprite.SizeMode.CUSTOM);
assert.deepEqual(node.contentSize, {width: 678, height: 922},
    'assigning the trimmed source SpriteFrame does not resize the source UITransform');
assert.deepEqual(created[0].sourceFields, spec.sourceFields, 'readback parses saved marker JSON, not the spec object');
assert.equal(node.getComponent(Identity).enabled, false);

assert.equal(helper.readStaticMasks([spec], nodes, resolveSprite, {initialized: true})[0].verified, true);

const mask = node.getComponent(Mask);
mask.subComp = null; // _sprite is a nonserialized Mask cache after persistent Prefab reload.
const persistent = helper.readStaticMasks([spec], nodes, resolveSprite)[0];
assert.equal(persistent.verified, true, 'persistent readback follows the saved node Sprite reference');
assert.deepEqual(persistent.failedChecks, []);
assert.equal(persistent.actual.backingCacheType, null);
assert.equal(persistent.initialized, false);
assert.equal(persistent.maskSpriteFrameUuid, null);
assert.equal(persistent.nativeSpriteFrameUuid, nativeSpriteUuid);
mask.subComp = sprite;

sprite.spriteFrame = new SpriteFrame(nativeSpriteUuid); // same imported asset represented by a distinct loaded object
const identity = node.getComponent(Identity);
identity.sourceSpriteFrame = sprite.spriteFrame;
const duplicateAssetInstance = helper.readStaticMasks([spec], nodes, resolveSprite)[0];
assert.equal(duplicateAssetInstance.verified, true,
    'equivalent typed SpriteFrame instances pass across load domains by full immutable resource identity');
assert.equal(duplicateAssetInstance.checks.identitySpriteFrameReference, true,
    'identity marker still points to the exact SpriteFrame on its node');
assert.equal(duplicateAssetInstance.checks.spriteFrameResourceIdentity, true);
assert.equal(helper.readStaticMasks([spec], nodes, resolveSprite, {initialized: true})[0].verified, true,
    'initialized Mask cache must point to the same node SpriteFrame instance');
identity.sourceSpriteFrame = frame;
const wrongLoadDomainIdentityRef = helper.readStaticMasks([spec], nodes, resolveSprite)[0];
assert.equal(wrongLoadDomainIdentityRef.verified, false,
    'a structurally equivalent frame from another load domain cannot replace the node identity reference');
assert.ok(wrongLoadDomainIdentityRef.failedChecks.includes('identitySpriteFrameReference'));
identity.sourceSpriteFrame = sprite.spriteFrame;

sprite.spriteFrame = new SpriteFrame(nativeSpriteUuid, 676, 916, {texture: new Texture('other-texture-uuid')});
identity.sourceSpriteFrame = sprite.spriteFrame;
const wrongTexture = helper.readStaticMasks([spec], nodes, resolveSprite)[0];
assert.equal(wrongTexture.verified, false, 'matching SpriteFrame UUID cannot hide a different bound texture');
assert.ok(wrongTexture.failedChecks.includes('spriteFrameResourceIdentity'));

sprite.spriteFrame = new SpriteFrame(nativeSpriteUuid, 676, 916, {rect: {x: 1, y: 0, width: 676, height: 916}});
identity.sourceSpriteFrame = sprite.spriteFrame;
const wrongRect = helper.readStaticMasks([spec], nodes, resolveSprite)[0];
assert.equal(wrongRect.verified, false, 'matching UUID and texture cannot hide a different frame rectangle');
assert.ok(wrongRect.failedChecks.includes('spriteFrameResourceIdentity'));

sprite.spriteFrame = new SpriteFrame(nativeSpriteUuid, 676, 916, {insetTop: 2});
identity.sourceSpriteFrame = sprite.spriteFrame;
assert.equal(helper.readStaticMasks([spec], nodes, resolveSprite)[0].verified, false,
    'matching UUID cannot hide changed slice border values');

sprite.spriteFrame = new SpriteFrame(nativeSpriteUuid, 676, 916, {originalSize: {width: 680, height: 916}});
identity.sourceSpriteFrame = sprite.spriteFrame;
assert.equal(helper.readStaticMasks([spec], nodes, resolveSprite)[0].verified, false,
    'matching UUID cannot hide changed untrimmed dimensions');

sprite.spriteFrame = new SpriteFrame(nativeSpriteUuid, 676, 916, {vertices: {
    rawPosition: [], positions: [], indexes: [0, 1, 2], uv: [], nuv: [],
    minPos: {x: 0, y: 0, z: 0}, maxPos: {x: 1, y: 1, z: 0},
}});
identity.sourceSpriteFrame = sprite.spriteFrame;
assert.equal(helper.readStaticMasks([spec], nodes, resolveSprite)[0].verified, false,
    'matching UUID cannot hide changed mesh geometry');

sprite.spriteFrame = new SpriteFrame(sourceSpriteId); // same source-looking UUID, wrong native asset identity
identity.sourceSpriteFrame = sprite.spriteFrame;
const wrongNativeFrame = helper.readStaticMasks([spec], nodes, resolveSprite)[0];
assert.equal(wrongNativeFrame.verified, false,
    'readback still requires the resolved imported native SpriteFrame identity');
assert.ok(wrongNativeFrame.failedChecks.includes('spriteReferenceAndFrame'));
sprite.spriteFrame = frame;
identity.sourceSpriteFrame = frame;

identity.sourceFieldsJson = JSON.stringify({ ...spec.sourceFields, _N$alphaThreshold: 0 });
const wrongSourceFields = helper.readStaticMasks([spec], nodes, resolveSprite)[0];
assert.equal(wrongSourceFields.verified, false,
    'tampered saved source fields fail readback');
assert.ok(wrongSourceFields.failedChecks.includes('identitySourceFieldsJson'));
identity.sourceFieldsJson = JSON.stringify(spec.sourceFields);
identity.sourceSpriteFrame = new SpriteFrame(nativeSpriteUuid);
assert.equal(helper.readStaticMasks([spec], nodes, resolveSprite)[0].verified, false,
    'marker must retain the same typed SpriteFrame reference as the native mask');
identity.sourceSpriteFrame = frame;
identity.nativeMask = new Mask(node);
const wrongMaskReference = helper.readStaticMasks([spec], nodes, resolveSprite)[0];
assert.equal(wrongMaskReference.verified, false,
    'marker must retain an actual typed reference to the rendered native Mask');
assert.ok(wrongMaskReference.failedChecks.includes('identityNativeMaskReference'));
identity.nativeMask = mask;
mask.subComp = new Sprite(node);
assert.equal(helper.readStaticMasks([spec], nodes, resolveSprite, {initialized: true})[0].verified, false,
    'initialized readback requires Mask.subComp to be the same typed Sprite as the node component');

const missingResolver = helper.readStaticMasks([spec], nodes, () => null)[0];
assert.equal(missingResolver.verified, false, 'missing asset resolution cannot verify a nonempty source ref');
