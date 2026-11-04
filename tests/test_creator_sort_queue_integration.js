'use strict';

const assert = require('node:assert/strict');
const Module = require('node:module');
const load = Module._load;
const classes = new Map();
const ownedRegistrations = [];
const ccMock = { Canvas: function Canvas() {}, Layers:{Enum:{UI_2D:33554432}}, js: { getClassByName: name => classes.get(name) || null } };
Module._load = function (request, parent, isMain) {
    if (request === 'cc') return ccMock;
    if (request === './owned-import-undo.js' && /CreatorStaticSortQueueIntegration\.js$/.test(parent && parent.filename || ''))
        return {registerRoot: root => { ownedRegistrations.push(root); return {registered: true}; }};
    return load.call(this, request, parent, isMain);
};
globalThis.EditorExtends = { UuidUtils: { decompressUuid: uuid => uuid } };

const bridge = require('../src/monkey/targets/CreatorStaticSortQueueIntegration.js');
assert.deepEqual(bridge.validatePlan({ sourcePrefabs: [], staticCompletion: null }),
    { applicable: false, status: 'not_applicable' }, 'ordinary export without static completion is explicitly out of scope');
assert.deepEqual(bridge.validatePlan({ sourcePrefabs: [], staticSortQueue: [] }),
    { applicable: true, status: 'required', rows: [] });
assert.throws(() => bridge.validatePlan({ sourcePrefabs: [], staticCompletion: { schemaVersion: 1 } }),
    /staticCompletion requires a staticSortQueue array/, 'static completion cannot silently skip the native queue contract');
assert.throws(() => bridge.validatePlan({ sourcePrefabs: [{ root: 'r', sourceId: 'p', path: 'p.prefab' }],
    staticCompletion: { schemaVersion: 1 }, staticSortQueue: [] }),
/count differs/, 'static completion must bind every source Prefab');
assert.throws(() => bridge.validatePlan({ sourcePrefabs: [{ root: 'r', sourceId: 'p', path: 'p.prefab' }],
    staticCompletion: { schemaVersion: 1 }, staticSortQueue: [{ rootScope: 'wrong', sourcePrefabId: 'p', prefabPath: 'p.prefab' }] }),
/root\/sourcePrefabId\/path identity differs/, 'contract identity mismatch fails closed');
const sourcePrefab = { root: 'r', sourceId: 'p', path: 'p.prefab' };
const queueContract = { rootScope: 'r', sourcePrefabId: 'p', prefabPath: 'p.prefab', sourceManifestSha256: 'm',
    sourceDrawEvents: [], renderers: [], masks: [], sourceChildOrder: {}, sourceNodeActive: {} };
assert.throws(() => bridge.validatePlan({ sourcePrefabs: [sourcePrefab], sourceManifestSha256: 'm',
    staticCompletion: { schemaVersion: 1 }, staticSortQueue: [queueContract] }),
/incomplete or differently bound/, 'coverage must include an explicit non-draw contract array');
queueContract.nonDrawRenderers = [];
assert.equal(bridge.validatePlan({ sourcePrefabs: [sourcePrefab], sourceManifestSha256: 'm',
    staticCompletion: { schemaVersion: 1 }, staticSortQueue: [queueContract] }).applicable, true);

function ApiClass() {}
ApiClass.moduleUuid = bridge.API_MODULE_UUID;
ApiClass.prototype.__scriptUuid = bridge.API_MODULE_UUID;
Object.assign(ApiClass, { create() {}, readPersistent() {}, readInitialized() {}, isGeneratedProxyRoot() {} });
classes.set(bridge.API_CLASS_NAME, ApiClass);
assert.deepEqual(bridge.registerApiClass(ApiClass),
    { uuid: bridge.API_MODULE_UUID, className: bridge.API_CLASS_NAME, registered: true },
    'registered class is pinned to its actual Creator script UUID');
function SpoofedApi() {}
SpoofedApi.moduleUuid = bridge.API_MODULE_UUID;
SpoofedApi.prototype.__scriptUuid = 'other-script-uuid';
assert.throws(() => bridge.registerApiClass(SpoofedApi), /loaded API class does not match/,
    'a matching self-declared constant cannot spoof the source script UUID');

console.log('Creator sort queue integration contract checks passed');

const nestedCanvas = {enabledInHierarchy:true};
const canvasOwner = { parent:null, getComponent:()=>nestedCanvas };
const intermediate = { parent:canvasOwner, getComponent:()=>null };
const leaf = { parent:intermediate, getComponent:()=>null };
assert.equal(bridge.parentCanvas(leaf), nestedCanvas);
assert.equal(bridge.parentCanvas({parent:null,getComponent:()=>null}), null);

const imageBinding={sourceId:'sprite-component',sourceType:'cc.Sprite',sourceSpriteFrameUuid:'old-source-frame',sourceSpriteFrameAssetId:'source-frame-asset',nativeSpriteImageUuidExpected:'native-image'};
const resolvedPlan={sourcePrefabs:[sourcePrefab],sourceManifestSha256:'m',staticSortQueue:[{...queueContract,nonDrawRenderers:[imageBinding]}],assets:[{sourceId:'source-frame-asset',kind:'sprite',uuid:'native-image',spriteFrameUuid:'actual-native-sub-frame'}]};
assert.equal(bridge.spec(resolvedPlan,'r').nonDrawRenderers[0].nativeSpriteFrameUuidExpected,'actual-native-sub-frame');
assert.equal(imageBinding.nativeSpriteFrameUuidExpected,undefined,'the frozen contract is not mutated');
assert.throws(()=>bridge.spec({...resolvedPlan,assets:[{...resolvedPlan.assets[0],uuid:'foreign-image'}]},'r'),/imported ImageAsset metadata/);
assert.throws(()=>bridge.spec({...resolvedPlan,assets:[{...resolvedPlan.assets[0],spriteFrameUuid:null}]},'r'),/imported ImageAsset metadata/);

const defaultLayerPlan={...resolvedPlan,nodes:[{sourceId:'r'}],staticSortQueue:[{...resolvedPlan.staticSortQueue[0],sourceNodeIds:['r']}]};
assert.equal(bridge.spec(defaultLayerPlan,'r').sourceNodeLayers.r,33554432);
assert.equal(bridge.spec({...defaultLayerPlan,nodes:[{sourceId:'r',sourceLayer:0}]},'r').sourceNodeLayers.r,0);
assert.throws(()=>bridge.spec({...defaultLayerPlan,nodes:[{sourceId:'r',sourceLayer:'wrong'}]},'r'),/target layer is invalid/);

testProxyRegistration();

function testProxyRegistration() {
    const sourcePrefab = { root: 'owned-root', sourceId: 'owned-prefab', path: 'owned.prefab' };
    const row = { rootScope: 'owned-root', sourcePrefabId: 'owned-prefab', prefabPath: 'owned.prefab',
        sourceManifestSha256: 'manifest-hash', sourceDrawEvents: [], renderers: [], nonDrawRenderers: [], masks: [],
        sourceChildOrder: {}, sourceNodeActive: {}, sourceNodeIds: ['owned-root'] };
    const plan = { sourcePrefabs: [sourcePrefab], sourceManifestSha256: 'manifest-hash',
        staticSortQueue: [row], nodes: [{sourceId:'owned-root'}], assets: [] };
    const proxyRoot = {parent:null, children:[], getComponent: ctor => ctor === Presenter ? presenter : null};
    const presenter = {sourceRoot:null, sourceRootId:'owned-root', proxyRoot};
    function Presenter() {}
    classes.set('MonkeyStaticSortQueueProxyPresenter', Presenter);
    const sourceRoot = {parent:{}, children:[], activeInHierarchy:true,
        getComponent: ctor => ctor === ccMock.Canvas ? {enabledInHierarchy:true,node:{activeInHierarchy:true}} : null};
    presenter.sourceRoot = sourceRoot;
    sourceRoot.children.push(proxyRoot);
    proxyRoot.parent = sourceRoot;
    function RegisteredApi() {}
    RegisteredApi.moduleUuid = bridge.API_MODULE_UUID;
    RegisteredApi.prototype.__scriptUuid = bridge.API_MODULE_UUID;
    Object.assign(RegisteredApi, {
        create: () => ({verified:true,presentationMode:'initialized'}),
        attachSourceIdentities() {}, readPersistent() {}, readInitialized() {},
        isGeneratedProxyRoot: node => node === proxyRoot,
    });
    classes.set(bridge.API_CLASS_NAME, RegisteredApi);
    bridge.registerApiClass(RegisteredApi);
    ownedRegistrations.length = 0;
    const result = bridge.createForPrefab(plan, 'owned-root', new Map([['owned-root',sourceRoot]]));
    assert.equal(result.proxyRoot, proxyRoot);
    assert.deepEqual(ownedRegistrations, [proxyRoot],
        'register the exact generated proxy root after create returns while it is attached');
}
