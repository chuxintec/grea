'use strict';
const assert = require('node:assert/strict');
const Module = require('node:module');
const load = Module._load;

class Component { constructor(node) { this.node=node;this.enabled=true; } }
class Asset {}
class AnimationClip extends Asset { constructor() { super();this.tracks=[]; } }
class JsonAsset extends Asset {}
class UIOpacity extends Component { constructor(node) { super(node);this.opacity=255; } }
class Animation extends Component {
    constructor(node) { super(node);this._clips=[];this.defaultClip=null;this.playOnLoad=false; }
    set clips(value) { this._clips=value;this.node.animationStateInitialized=true; }
    get clips() { return this._clips; }
    play() { throw new Error('play must not be called'); }
    sample() { throw new Error('sample must not be called'); }
}
class Slot {}
class Binding extends Component {}
class Node {
    constructor(name) { this.name=name;this.parent=null;this.children=[];this.components=[];this.animationStateInitialized=false; }
    addChild(child) { child.parent=this;this.children.push(child);return child; }
    getComponent(type) { return this.components.find(row => row instanceof type) || null; }
    addComponent(type) { const row=new type(this);this.components.push(row);return row; }
}
const cc = { Asset, AnimationClip, JsonAsset, UIOpacity, Animation, Component,
    js: { getClassByName: () => null },
    Class: ({extends: Base}) => class extends Base {} };
Module._load = function (request, parent, isMain) {
    if (request === 'cc') return cc;
    if (request === './static-animation-bindings.js' && parent && parent.filename.endsWith('CreatorStaticAnimationIntegration.js'))
        return require('../src/monkey/targets/CreatorStaticAnimationBindings.js');
    return load.call(this, request, parent, isMain);
};

const helper = require('../src/monkey/targets/CreatorStaticAnimationIntegration.js');
const staticAnimationBindings = require('../src/monkey/targets/CreatorStaticAnimationBindings.js');
const componentId = 'source:animation-component';
const clipId = 'source:opacity-clip';
const ownerId = 'source:owner';
const targetId = 'source:target';
const owner = new Node('owner');
const branch = owner.addChild(new Node('branch'));
const target = branch.addChild(new Node('part'));
const clip = new AnimationClip();
const plan = {
    components: [{ sourceId: componentId, node: ownerId, type: 'cc.Animation', clips: [clipId],
        defaultClip: clipId, enabled: true, playOnLoad: false }],
    nodes: [{ sourceId: ownerId, opacity: 255 }, { sourceId: targetId, opacity: 41 }],
    animations: [{ id: clipId + '@' + componentId, partial: true, tracks: [{ path: 'branch/part', node: targetId,
        property: 'opacity', nativeProperty: 'opacity' }] }],
    syncPrefabBindings: [],
};
const animationAssets = new Map([[clipId + '@' + componentId, {
    id: clipId + '@' + componentId, path: 'assets/Animations/Opacity.anim',
    uuid: 'native-clip-uuid', sha256: 'a'.repeat(64), partial: true, asset: clip,
}]]);
const sourceEvidence = new Map();
const nodes = new Map([[ownerId, owner], [targetId, target]]);
const bindingTypes = { BindingType: Binding, ClipSlotType: Slot };
const readback = helper.bind(plan, nodes, animationAssets, sourceEvidence, [], bindingTypes);
assert.equal(readback[0].staticReferenceStatus, 'reference_fields_verified');
assert.equal(target.getComponent(UIOpacity).opacity, 41);
assert(owner.animationStateInitialized, 'cc.Animation clips assignment constructs disabled animation state');
assert.equal(owner.getComponent(Animation).enabled, false);
assert.equal(owner.getComponent(Animation).playOnLoad, false);
const saved = helper.readSaved(plan, nodes, animationAssets, sourceEvidence, [], bindingTypes);
assert.equal(saved[0].staticReferenceStatus, 'reference_fields_verified');
assert.equal(target.getComponent(UIOpacity).opacity, 41, 'saved readback keeps source Node.opacity');

// Reopened/reloaded Editor assets can be distinct JS instances. This diagnostic
// records UUID/type and strict object-identity results without relaxing the gate.
clip._uuid = 'native-clip-uuid';
const identityOwner = new Node('identity-owner');
const identityComponent = 'identity:animation-component';
const identityClipId = 'identity:clip';
const identityPlan = {...plan, components: [{...plan.components[0], sourceId: identityComponent,
    node: 'identity:owner', clips: [identityClipId], defaultClip: identityClipId}],
    nodes: [{sourceId: 'identity:owner', opacity: 255}],
    animations: [{id: identityClipId + '@' + identityComponent, tracks: []}],
    syncPrefabBindings: []};
const identityAssets = new Map([[identityClipId + '@' + identityComponent,
    {...animationAssets.get(clipId + '@' + componentId), id: identityClipId + '@' + identityComponent,
        uuid: 'native-clip-uuid'}]]);
helper.bind(identityPlan, new Map([['identity:owner', identityOwner]]), identityAssets,
    sourceEvidence, [], bindingTypes);
const identityAnimation = identityOwner.getComponent(Animation);
const identityMarker = identityOwner.getComponent(Binding);
const duplicateClipObject = new AnimationClip(); duplicateClipObject._uuid = clip._uuid;
identityAnimation.clips = [duplicateClipObject];
identityMarker.nativeClips = [duplicateClipObject];
identityMarker.sourceClips[0].nativeClip = duplicateClipObject;
const identitySpec = helper.buildSpec(identityPlan.components[0], identityOwner, identityPlan,
    identityAssets, sourceEvidence, []);
const identityValue = identityAssets.get(identityClipId + '@' + identityComponent);
const identityResolution = (clipPath, uuid, sha) => clipPath === identityValue.path && uuid === identityValue.uuid
    && (!sha || sha === identityValue.sha256) ? identityValue.asset : null;
const identityResult = staticAnimationBindings.read(identityOwner, identitySpec,
    identityResolution, () => null, bindingTypes);
assert.equal(identityResult.status, 'mismatch');
const clipDiagnostic = identityResult.diagnostics[0].comparison.clipReferences[0];
assert.equal(clipDiagnostic.expectedGuid, 'native-clip-uuid');
assert.equal(clipDiagnostic.animationUuidMatchesExpected, true, JSON.stringify(clipDiagnostic));
assert.equal(clipDiagnostic.animationIsResolvedObject, false,
    'same serialized GUID but different runtime object stays a failed strict binding');

const syncOwnerId = 'instance:owner';
const syncTargetId = 'instance:target';
const syncComponentId = 'instance:animation-component';
const syncOwner = new Node('sync-owner');
const syncTarget = syncOwner.addChild(new Node('branch')).addChild(new Node('part'));
const syncAnimationId = clipId + '@' + syncComponentId;
const syncPlan = {
    components: [{...plan.components[0], sourceId: syncComponentId, node: syncOwnerId}],
    nodes: [{sourceId: syncOwnerId, opacity: 255}, {sourceId: syncTargetId, opacity: 63}],
    animations: [{id: syncAnimationId, tracks: [{path: 'branch/part', node: targetId, property: 'opacity', nativeProperty: 'opacity'}]}],
    syncPrefabBindings: [{origins: [{instanceSourceId: syncTargetId, templateSourceId: targetId}]}],
};
const syncAssets = new Map([[syncAnimationId, {...animationAssets.get(clipId + '@' + componentId), id: syncAnimationId}]]);
const syncNodes = new Map([[syncOwnerId, syncOwner], [syncTargetId, syncTarget]]);
helper.bind(syncPlan, syncNodes, syncAssets, sourceEvidence, [], bindingTypes);
assert.equal(syncTarget.getComponent(UIOpacity).opacity, 63,
    'sync-clone hierarchy path maps to its exact instance source node and source opacity');

const deepOwnerId='deep:owner',deepTargetId='deep:target',middleTargetId='middle:target';
const deepComponentId='deep:animation-component',deepAnimationId=clipId+'@'+deepComponentId;
const deepOwner=new Node('deep-owner'),deepTarget=deepOwner.addChild(new Node('branch')).addChild(new Node('part'));
const deepPlan={
    components:[{...plan.components[0],sourceId:deepComponentId,node:deepOwnerId}],
    nodes:[{sourceId:deepOwnerId,opacity:255},{sourceId:deepTargetId,opacity:77}],
    animations:[{id:deepAnimationId,tracks:[{path:'branch/part',node:targetId,property:'opacity',nativeProperty:'opacity'}]}],
    syncPrefabBindings:[
        {origins:[{instanceSourceId:deepTargetId,templateSourceId:middleTargetId}]},
        {origins:[{instanceSourceId:middleTargetId,templateSourceId:targetId}]},
    ],
};
const deepAssets=new Map([[deepAnimationId,{...animationAssets.get(clipId+'@'+componentId),id:deepAnimationId}]]);
helper.bind(deepPlan,new Map([[deepOwnerId,deepOwner],[deepTargetId,deepTarget]]),deepAssets,sourceEvidence,[],bindingTypes);
assert.equal(deepTarget.getComponent(UIOpacity).opacity,77,'multi-hop instance to template lineage is followed exactly');

const cloneA='clone-a:target',cloneB='clone-b:target',cloneOwner='clone-owner',cloneComponent='clone-component';
const cloneAnimation=clipId+'@'+cloneComponent,cloneOwnerNode=new Node('clone-owner'),cloneBNode=cloneOwnerNode.addChild(new Node('branch')).addChild(new Node('part'));
const siblingClonePlan={
    components:[{...plan.components[0],sourceId:cloneComponent,node:cloneOwner}],
    nodes:[{sourceId:cloneOwner,opacity:255},{sourceId:cloneB,opacity:55}],
    animations:[{id:cloneAnimation,tracks:[{path:'branch/part',node:cloneA,property:'opacity',nativeProperty:'opacity'}]}],
    syncPrefabBindings:[{origins:[{instanceSourceId:cloneA,templateSourceId:targetId},{instanceSourceId:cloneB,templateSourceId:targetId}]}],
};
const cloneAssets=new Map([[cloneAnimation,{...animationAssets.get(clipId+'@'+componentId),id:cloneAnimation}]]);
assert.throws(()=>helper.bind(siblingClonePlan,new Map([[cloneOwner,cloneOwnerNode],[cloneB,cloneBNode]]),cloneAssets,sourceEvidence,[],bindingTypes),
    /STATIC_ANIMATION_OPACITY_TRACK_NODE_MISMATCH/,'sibling clones of the same template are not interchangeable');

const ambiguousLineagePlan={...deepPlan,syncPrefabBindings:[
    {origins:[{instanceSourceId:deepTargetId,templateSourceId:middleTargetId},{instanceSourceId:deepTargetId,templateSourceId:'other:template'}]},
]};
assert.throws(()=>helper.bind(ambiguousLineagePlan,new Map([[deepOwnerId,deepOwner],[deepTargetId,deepTarget]]),deepAssets,sourceEvidence,[],bindingTypes),
    /STATIC_ANIMATION_OPACITY_NODE_ORIGIN_AMBIGUOUS/,'ambiguous exact node lineage is rejected');

const unboundOwner = new Node('unbound-owner');
const noBoundClips = {...plan, components: [{...plan.components[0], sourceId: 'source:unbound-component', node: 'source:unbound-owner', clips: [], defaultClip: null}],
    nodes: [...plan.nodes, {sourceId: 'source:unbound-owner', opacity: 255}]};
const noBoundNodes = new Map([['source:unbound-owner', unboundOwner]]);
helper.bind(noBoundClips, noBoundNodes, animationAssets, sourceEvidence, [], bindingTypes);
assert.equal(unboundOwner.getComponent(UIOpacity), null, 'unbound asset-only clips do not synthesize target components');

const ambiguousOwner = new Node('ambiguous-owner');
ambiguousOwner.addChild(new Node('branch')).addChild(new Node('part'));
ambiguousOwner.addChild(new Node('branch')).addChild(new Node('part'));
const ambiguousPlan = {...plan, components: [{...plan.components[0], node: 'source:ambiguous-owner'}],
    nodes: [...plan.nodes, {sourceId: 'source:ambiguous-owner', opacity: 255}]};
assert.throws(() => helper.bind(ambiguousPlan,
    new Map([['source:ambiguous-owner', ambiguousOwner], [targetId, target]]), animationAssets, sourceEvidence, [], bindingTypes),
    /STATIC_ANIMATION_OPACITY_PATH_AMBIGUOUS/);

const missingMappingOwner = new Node('missing-map-owner');
const missingMappingTarget = missingMappingOwner.addChild(new Node('branch')).addChild(new Node('part'));
const missingPlan = {...plan, components: [{...plan.components[0], node: 'source:missing-owner'}],
    nodes: [...plan.nodes, {sourceId: 'source:missing-owner', opacity: 255}]};
assert.throws(() => helper.bind(missingPlan,
    new Map([['source:missing-owner', missingMappingOwner]]), animationAssets, sourceEvidence, [], bindingTypes),
    /STATIC_ANIMATION_OPACITY_NODE_MAPPING_NOT_UNIQUE/);

target.getComponent(UIOpacity).opacity = 42;
assert.throws(() => helper.readSaved(plan, nodes, animationAssets, sourceEvidence, [], bindingTypes),
    /STATIC_ANIMATION_OPACITY_SAVED_COMPONENT_OR_VALUE_DIFFERS/);
