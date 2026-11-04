'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const helper = require('../src/monkey/targets/spine/CreatorSpineUITransformBindings');
const proxyMarkerPath = path.join(__dirname, '../src/monkey/targets/CreatorStaticSortQueueProxyMarker.ts');
const proxyPresenterPath = path.join(__dirname, '../src/monkey/targets/CreatorStaticSortQueueProxyPresenter.ts');
const proxyMarkerMeta = JSON.parse(fs.readFileSync(proxyMarkerPath + '.meta', 'utf8'));
const proxyPresenterMeta = JSON.parse(fs.readFileSync(proxyPresenterPath + '.meta', 'utf8'));
assert.equal(helper.STATIC_SORT_PROXY_MARKER_UUID, proxyMarkerMeta.uuid);
assert.equal(helper.STATIC_SORT_PROXY_PRESENTER_UUID, proxyPresenterMeta.uuid);
assert.match(fs.readFileSync(proxyMarkerPath, 'utf8'), /public sourceRootOwner/);
assert.match(fs.readFileSync(proxyPresenterPath, 'utf8'), /public sourceRootId/);
assert.match(fs.readFileSync(proxyPresenterPath, 'utf8'), /public sourceRoot:/);
assert.match(fs.readFileSync(proxyPresenterPath, 'utf8'), /public proxyRoot:/);

const preserverPath = path.join(__dirname, '../src/monkey/targets/spine/CreatorSpineUITransformPreserver.ts');
const preserverMetaPath = preserverPath + '.meta';
const preserverSource = fs.readFileSync(preserverPath, 'utf8');
const preserverMeta = JSON.parse(fs.readFileSync(preserverMetaPath, 'utf8'));
assert.equal(preserverMeta.uuid, helper.PRESERVER_SCRIPT_UUID);
assert.match(preserverSource, /@executeInEditMode\(true\)/);
assert.match(preserverSource, /@executionOrder\(1000\)/);
for (const field of ['target', 'sourceNodeId', 'sourceWidth', 'sourceHeight', 'sourceAnchorX', 'sourceAnchorY'])
  assert.match(preserverSource, new RegExp('public ' + field + '\\b'));
assert.match(preserverSource, /public onLoad\(\): void\s*\{\s*this\.restoreFromLifecycle\('onLoad'\)/);
assert.match(preserverSource, /public onEnable\(\): void\s*\{\s*this\.restoreFromLifecycle\('onEnable'\)/);
assert.match(preserverSource, /target\.setContentSize\(this\.sourceWidth, this\.sourceHeight\)/);
assert.match(preserverSource, /target\.setAnchorPoint\(this\.sourceAnchorX, this\.sourceAnchorY\)/);
assert.match(preserverSource, /target\.node !== this\.node/);

class UITransform {
  constructor(width, height, anchorX, anchorY, enabled = true) {
    this.width = width; this.height = height; this.anchorX = anchorX; this.anchorY = anchorY; this.enabled = enabled;
  }
  setContentSize(width, height) { this.width = width; this.height = height; }
  setAnchorPoint(x, y) { this.anchorX = x; this.anchorY = y; }
}
class Preserver {
  configure(target, sourceNodeId, size, anchor) {
    this.target = target; this.sourceNodeId = sourceNodeId;
    [this.sourceWidth, this.sourceHeight] = size;
    [this.sourceAnchorX, this.sourceAnchorY] = anchor;
    target.setContentSize(...size); target.setAnchorPoint(...anchor);
  }
}
Preserver.__cid__ = helper.PRESERVER_SCRIPT_UUID;
const cc = {
  UITransform,
  js: {
    getClassByName(name) { return name === helper.PRESERVER_CLASS_NAME ? Preserver : null; },
    getClassName(ctor) { return ctor === Preserver ? helper.PRESERVER_CLASS_NAME : ctor.name; },
    getClassId(ctor) { return ctor.__cid__; },
  },
};
Preserver.__cid__='ae824BaPGpcuqKB48OlGXPf';
assert.equal(helper.isPreserver(Preserver,cc),true);
Preserver.__cid__='ae824BaPGpcuqKB48OlGXPa';
assert.equal(helper.isPreserver(Preserver,cc),false);
Preserver.__cid__=helper.PRESERVER_SCRIPT_UUID;
function makeNode(ui) {
  const node = { components: [] };
  ui.node = node;
  node.getComponent = type => type === UITransform ? ui : node.components.find(row => row.constructor === type) || null;
  node.getComponents = type => node.components.filter(row => row.constructor === type);
  node.addComponent = type => { const component = new type(); component.node = node; node.components.push(component); return component; };
  return node;
}
const sourceId = 'gameAsset:prefab#81';
const plan = {
  nodes: [{ sourceId, size: [681, 293], anchor: [0.5, 0.5], children: [], sourceUITransformEnabled: true }],
  sourcePrefabs: [{ sourceId: 'gameAsset:prefab', root: sourceId, nodes: [sourceId] }],
  components: [{ sourceId: sourceId + '/components/0', node: sourceId, type: 'sp.Skeleton', spineBinding: {} }],
};
const ui = new UITransform(646.2987060546875, 264.01171875, 0.5004825309534706, 0.49944359908340363);
const node = makeNode(ui);
const preserver = node.addComponent(Preserver);
preserver.configure(ui, sourceId, [681, 293], [0.5, 0.5]);
// Reproduce Skeleton's post-deserialization UITransform rewrite.
ui.setContentSize(646.2987060546875, 264.01171875);
ui.setAnchorPoint(0.5004825309534706, 0.49944359908340363);
const nodes = new Map([[sourceId, node]]);
const initialRead = helper.readAuthored(plan, nodes, cc, 'gameAsset:prefab');
assert.equal(initialRead.status, 'mismatch');
assert.deepEqual([ui.width, ui.height], [646.2987060546875, 264.01171875]);
assert.match(helper.readAuthored.toString(), /readNodeTransform/);
assert.doesNotMatch(helper.readAuthored.toString(), /setContentSize|setAnchorPoint|restoreAuthoredNow/);
const restored = helper.restoreAuthored(plan, nodes, cc, 'gameAsset:prefab');
assert.equal(restored.status, 'restored_authored_ui_transform');
assert.equal(restored.rows[0].engineOverrideObserved, true);
assert.deepEqual([ui.width, ui.height], [681, 293]);
assert.deepEqual([ui.anchorX, ui.anchorY], [0.5, 0.5]);
assert.equal(helper.readAuthored(plan, nodes, cc, 'gameAsset:prefab').status, 'verified');
const driftAgain = [700, 300];
ui.setContentSize(...driftAgain);
const attached = helper.attachPreservers(plan, nodes, cc, 'gameAsset:prefab');
assert.equal(attached.status, 'attached');
assert.equal(preserver.sourceNodeId, sourceId);
assert.deepEqual([ui.width, ui.height], [681, 293]);
assert.equal(helper.SOURCE_ENGINE_EVIDENCE.sha256, '7cdc119e26aa6dceec4bd78ae30dd08f39daa2f0da5d914d2197a730b558a5e8');
assert.equal(helper.TARGET_ENGINE_EVIDENCE.sha256, '2e86383e7e7dfb93bc40ec1d7e44c6bb2bebc8a3e95c100ad16620bd24114329');
assert.notEqual(helper.SOURCE_ENGINE_EVIDENCE.sha256, helper.TARGET_ENGINE_EVIDENCE.sha256);

const makeSerialized = (size, anchor) => [
  { __type__: 'cc.Prefab', data: { __id__: 1 } },
  { __type__: 'cc.Node', _children: [], _components: [{ __id__: 2 }, { __id__: 3 }] },
  { __type__: 'cc.UITransform', _node: { __id__: 1 }, _enabled: true,
    _contentSize: { width: size[0], height: size[1] }, _anchorPoint: { x: anchor[0], y: anchor[1] } },
  { __type__: helper.PRESERVER_SCRIPT_UUID, _node: { __id__: 1 }, _enabled: true,
    target: { __id__: 2 }, sourceNodeId: sourceId, sourceWidth: 681, sourceHeight: 293,
    sourceAnchorX: 0.5, sourceAnchorY: 0.5 },
];
const prefabSpec = { sourceId: 'gameAsset:prefab', root: sourceId };
assert.equal(helper.verifySerializedPrefab(plan, prefabSpec, makeSerialized([681, 293], [0.5, 0.5])).status, 'verified');
assert.throws(() => helper.verifySerializedPrefab(plan, prefabSpec,
  makeSerialized([646.2987, 264.0117], [0.50048, 0.49944])), /SERIALIZED_AUTHORED_VALUE_MISMATCH/);
const compiledPreserver=makeSerialized([681,293],[0.5,0.5]);compiledPreserver[3].__type__='ae824BaPGpcuqKB48OlGXPf';
assert.equal(helper.verifySerializedPrefab(plan,prefabSpec,compiledPreserver).status,'verified');
compiledPreserver[3].__type__='arbitrary.OtherComponent';
assert.throws(()=>helper.verifySerializedPrefab(plan,prefabSpec,compiledPreserver),/PRESERVER_SERIALIZED_COMPONENT_MISMATCH/);
const missingPreserver = makeSerialized([681, 293], [0.5, 0.5]);
missingPreserver[1]._components = [{ __id__: 2 }];
assert.throws(() => helper.verifySerializedPrefab(plan, prefabSpec, missingPreserver), /PRESERVER_SERIALIZED_COMPONENT_MISMATCH/);
const wrongPreserver = makeSerialized([681, 293], [0.5, 0.5]);
wrongPreserver[3].sourceAnchorY = 0.5172407;
assert.throws(() => helper.verifySerializedPrefab(plan, prefabSpec, wrongPreserver), /PRESERVER_SERIALIZED_VALUE_MISMATCH/);

const generatedProxyPlan = structuredClone(plan);
const generatedProxyChildId = 'gameAsset:prefab#82';
generatedProxyPlan.nodes[0].children = [generatedProxyChildId];
generatedProxyPlan.nodes.push({ sourceId: generatedProxyChildId, size: [1, 1], anchor: [0.5, 0.5], children: [] });
generatedProxyPlan.sourcePrefabs[0].nodes = [sourceId, generatedProxyChildId];
function serializedWithProxy({markerOwner = 1, presenterSource = 1, presenterProxy = 5, markerSourceNode = sourceId,
  preserverSourceNodeId = sourceId,
  markerType = helper.STATIC_SORT_PROXY_MARKER_UUID, presenterType = helper.STATIC_SORT_PROXY_PRESENTER_UUID} = {}) {
  const records = makeSerialized([681, 293], [0.5, 0.5]);
  records[3].sourceNodeId = preserverSourceNodeId;
  records[1]._children = [{ __id__: 4 }, { __id__: 5 }];
  records.push({ __type__: 'cc.Node', _children: [], _components: [] }); // source child, id 4
  records.push({ __type__: 'cc.Node', _children: [], _components: [{ __id__: 6 }, { __id__: 7 }] }); // generated proxy, id 5
  records.push({ __type__: markerType, _node: { __id__: 5 }, kind: 'root', sourceNode: markerSourceNode,
    sourceRootOwner: { __id__: markerOwner } });
  records.push({ __type__: presenterType, _node: { __id__: 5 }, sourceRootId: markerSourceNode,
    sourceRoot: { __id__: presenterSource }, proxyRoot: { __id__: presenterProxy } });
  return records;
}
assert.equal(helper.verifySerializedPrefab(generatedProxyPlan, prefabSpec, serializedWithProxy()).status, 'verified',
  'a generated direct child is filtered only when marker and presenter refs prove exact ownership');
assert.equal(helper.verifySerializedPrefab(generatedProxyPlan, prefabSpec, serializedWithProxy({
  markerType: helper.compiledScriptId(helper.STATIC_SORT_PROXY_MARKER_UUID),
  presenterType: helper.compiledScriptId(helper.STATIC_SORT_PROXY_PRESENTER_UUID),
})).status, 'verified', 'Creator compiled script UUIDs retain the same typed identity');
assert.throws(() => helper.verifySerializedPrefab(generatedProxyPlan, prefabSpec,
  serializedWithProxy({markerOwner: 4})), /SERIALIZED_CHILD_COUNT_MISMATCH/,
  'a sourceRootOwner mismatch does not remove a child from the source denominator');
assert.throws(() => helper.verifySerializedPrefab(generatedProxyPlan, prefabSpec,
  serializedWithProxy({presenterProxy: 4})), /SERIALIZED_CHILD_COUNT_MISMATCH/,
  'a presenter proxyRoot mismatch does not remove a child from the source denominator');
assert.throws(() => helper.verifySerializedPrefab(generatedProxyPlan, prefabSpec,
  serializedWithProxy({markerType: 'MonkeyStaticSortQueueProxyMarker'})), /SERIALIZED_CHILD_COUNT_MISMATCH/,
  'a class-name lookalike without the pinned script UUID does not remove a child');

const disabledPlan = structuredClone(plan);
disabledPlan.nodes[0].sourceUITransformEnabled = false;
assert.throws(() => helper.restoreAuthored(disabledPlan, nodes, cc, 'gameAsset:prefab'), /ENABLED_STATE_MISMATCH/);

// Sync Prefab template identity must follow an explicit, possibly chained
// origins map. Native instance serialization may omit inherited children and
// components, so the saved template receipt + raw PrefabInfo UUID is required.
const templatePrefabId = 'gameAsset:template-prefab';
const templateNodeId = templatePrefabId + '#4';
const templateComponentId = templateNodeId + '/components/0';
const templateChildId = templatePrefabId + '#5';
const intermediateNodeId = templatePrefabId + '#4::sync-node';
const intermediateComponentId = templatePrefabId + '#4::sync-component';
const intermediateChildId = templatePrefabId + '#4::sync-child';
const intermediateChildComponentId = intermediateChildId + '/components/0';
const ownerPrefabId = 'gameAsset:owner-prefab';
const ownerRootId = ownerPrefabId + '#1';
const instanceRootId = ownerPrefabId + '#1::sync-node-root';
const instanceComponentId = ownerPrefabId + '#1::sync-component-spine';
const instanceChildId = ownerPrefabId + '#1::sync-node-child';
const instanceChildComponentId = ownerPrefabId + '#1::sync-component-child-spine';
const templateChildComponentId = templateChildId + '/components/0';
const size = [227.5, 120.25], anchor = [0.25, 0.75];
const syncPlan = {
  nodes: [
    { sourceId: ownerRootId, size: [10, 10], anchor: [0.5, 0.5], children: [instanceRootId] },
    { sourceId: instanceRootId, size, anchor, children: [instanceChildId] },
    { sourceId: instanceChildId, size: [80, 40], anchor: [0.5, 0.5], children: [] },
    { sourceId: intermediateNodeId, size, anchor, children: [intermediateChildId] },
    { sourceId: intermediateChildId, size: [80, 40], anchor: [0.5, 0.5], children: [] },
    { sourceId: templateNodeId, size, anchor, children: [templateChildId] },
    { sourceId: templateChildId, size: [80, 40], anchor: [0.5, 0.5], children: [] },
  ],
  components: [
    { sourceId: instanceComponentId, node: instanceRootId, type: 'sp.Skeleton', spineBinding: {} },
    { sourceId: instanceChildComponentId, node: instanceChildId, type: 'sp.Skeleton', spineBinding: {} },
    { sourceId: intermediateComponentId, node: intermediateNodeId, type: 'sp.Skeleton', spineBinding: {} },
    { sourceId: intermediateChildComponentId, node: intermediateChildId, type: 'sp.Skeleton', spineBinding: {} },
    { sourceId: templateComponentId, node: templateNodeId, type: 'sp.Skeleton', spineBinding: {} },
    { sourceId: templateChildComponentId, node: templateChildId, type: 'sp.Skeleton', spineBinding: {} },
  ],
  sourcePrefabs: [
    { sourceId: ownerPrefabId, root: ownerRootId, nodes: [ownerRootId, instanceRootId, instanceChildId] },
    { sourceId: templatePrefabId, root: intermediateNodeId,
      nodes: [intermediateNodeId, intermediateChildId, templateNodeId, templateChildId] },
  ],
  syncPrefabBindings: [{
    owner: ownerPrefabId, root: instanceRootId, template: templatePrefabId,
    rootOverrides: { position: '_trs[0:3]' },
    origins: [
      { instanceSourceId: instanceRootId, templateSourceId: intermediateNodeId },
      { instanceSourceId: intermediateNodeId, templateSourceId: templateNodeId },
      { instanceSourceId: instanceChildId, templateSourceId: intermediateChildId },
      { instanceSourceId: intermediateChildId, templateSourceId: templateChildId },
    ],
    componentOrigins: [
      { instanceSourceId: instanceComponentId, templateSourceId: intermediateComponentId },
      { instanceSourceId: intermediateComponentId, templateSourceId: templateComponentId },
      { instanceSourceId: instanceChildComponentId, templateSourceId: intermediateChildComponentId },
      { instanceSourceId: intermediateChildComponentId, templateSourceId: templateChildComponentId },
    ],
  }],
  prefabInstances: [{
    owner: ownerPrefabId, root: instanceRootId, template: templatePrefabId, outermost: true,
    nodes: [
      { instanceObject: instanceRootId, templateObject: intermediateNodeId },
      { instanceObject: instanceChildId, templateObject: intermediateChildId },
    ],
  }],
};
assert.equal(helper.sourceRows(syncPlan).find(row => row.sourceId === instanceRootId).canonicalSourceId, templateNodeId);
assert.deepEqual(helper.sourceRows(syncPlan).find(row => row.sourceId === instanceRootId).originChain,
  [instanceRootId, intermediateNodeId, templateNodeId]);
const instanceUI = new UITransform(0, 0, 0.5, 0.5);
const instanceNode = makeNode(instanceUI);
const instanceChildNode = makeNode(new UITransform(0, 0, 0.5, 0.5));
const instanceNodes = new Map([[instanceRootId, instanceNode], [instanceChildId, instanceChildNode]]);
helper.attachPreservers(syncPlan, instanceNodes, cc, ownerPrefabId);
assert.equal(instanceNode.getComponent(Preserver).sourceNodeId, templateNodeId);
assert.deepEqual([instanceUI.width, instanceUI.height], size);
assert.equal(instanceChildNode.getComponent(Preserver).sourceNodeId, templateChildId);
assert.equal(helper.readAuthored(syncPlan, instanceNodes, cc, ownerPrefabId).status, 'verified');

const templateUuid = '12345678-1234-5678-9abc-def012345678';
const templateReceipt = {
  status: 'verified', sourcePrefabId: templatePrefabId,
  rows: [
    { sourceId: intermediateNodeId, canonicalSourceId: templateNodeId, expectedSize: size,
      actualSize: size, expectedAnchor: anchor, actualAnchor: anchor, enabled: true,
      verified: true, preserverSerialized: true },
    { sourceId: intermediateChildId, canonicalSourceId: templateChildId, expectedSize: [80, 40],
      actualSize: [80, 40], expectedAnchor: [0.5, 0.5], actualAnchor: [0.5, 0.5], enabled: true,
      verified: true, preserverSerialized: true },
  ],
};
const instanceSerialized = [
  { __type__: 'cc.Prefab', data: { __id__: 1 } },
  { __type__: 'cc.Node', _children: [{ __id__: 2 }], _components: [] },
  // The source clone root has a Spine child, but the native instance strips it.
  { __type__: 'cc.Node', _children: [], _components: [], _prefab: { __id__: 3 } },
  { __type__: 'cc.PrefabInfo', asset: { __uuid__: templateUuid } },
];
const prefabSpecForOwner = { sourceId: ownerPrefabId, root: ownerRootId };
const saved = [{ sourceId: templatePrefabId, uuid: templateUuid, sha256: 'a'.repeat(64) }];
const templates = [{ sourceId: templatePrefabId, uuid: templateUuid, spineUITransformReceipt: templateReceipt }];
assert.equal(helper.verifySerializedPrefab(syncPlan, prefabSpecForOwner, instanceSerialized,
  { saved, templates }).nativePrefabInstanceProofs[0].verified, true);
assert.throws(() => helper.verifySerializedPrefab(syncPlan, prefabSpecForOwner, instanceSerialized),
  /NATIVE_INSTANCE_EVIDENCE_REQUIRED/);
const wrongTemplateUuid = structuredClone(instanceSerialized);
wrongTemplateUuid[3].asset.__uuid__ = '00000000-0000-0000-0000-000000000000';
assert.throws(() => helper.verifySerializedPrefab(syncPlan, prefabSpecForOwner, wrongTemplateUuid,
  { saved, templates }), /NATIVE_TEMPLATE_UUID_MISMATCH/);
const geometryOverride = structuredClone(syncPlan);
geometryOverride.syncPrefabBindings[0].rootOverrides.anchor = '_anchorPoint';
assert.throws(() => helper.sourceRows(geometryOverride), /ROOT_GEOMETRY_OVERRIDE_FORBIDDEN/);
const originCycle = structuredClone(syncPlan);
originCycle.syncPrefabBindings[0].origins[1].templateSourceId = instanceRootId;
assert.throws(() => helper.sourceRows(originCycle), /ORIGIN_CYCLE/);

const nestedProxyPlan = structuredClone(generatedProxyPlan);
const nestedProxySourceComponent = nestedProxyPlan.components[0].sourceId;
const nestedMiddlePrefabId = 'gameAsset:sort-middle-template';
const nestedMiddleRootId = nestedMiddlePrefabId + '#1';
const nestedMiddleComponentId = nestedMiddleRootId + '/components/0';
const nestedFinalPrefabId = 'gameAsset:sort-final-template';
const nestedFinalRootId = nestedFinalPrefabId + '#1';
const nestedFinalComponentId = nestedFinalRootId + '/components/0';
nestedProxyPlan.nodes.push(
  {sourceId:nestedMiddleRootId,size:[681,293],anchor:[0.5,0.5],children:[]},
  {sourceId:nestedFinalRootId,size:[681,293],anchor:[0.5,0.5],children:[]},
);
nestedProxyPlan.components.push(
  {sourceId:nestedMiddleComponentId,node:nestedMiddleRootId,type:'sp.Skeleton',spineBinding:{}},
  {sourceId:nestedFinalComponentId,node:nestedFinalRootId,type:'sp.Skeleton',spineBinding:{}},
);
nestedProxyPlan.sourcePrefabs.push(
  {sourceId:nestedMiddlePrefabId,root:nestedMiddleRootId,nodes:[nestedMiddleRootId]},
  {sourceId:nestedFinalPrefabId,root:nestedFinalRootId,nodes:[nestedFinalRootId]},
);
nestedProxyPlan.syncPrefabBindings = [{owner:'gameAsset:prefab',root:sourceId,template:nestedMiddlePrefabId,
  rootOverrides:{position:'_trs[0:3]'},
  origins:[
    {instanceSourceId:sourceId,templateSourceId:nestedMiddleRootId},
    {instanceSourceId:nestedMiddleRootId,templateSourceId:nestedFinalRootId},
  ],
  componentOrigins:[
    {instanceSourceId:nestedProxySourceComponent,templateSourceId:nestedMiddleComponentId},
    {instanceSourceId:nestedMiddleComponentId,templateSourceId:nestedFinalComponentId},
  ]}];
assert.equal(helper.verifySerializedPrefab(nestedProxyPlan,prefabSpec,
  serializedWithProxy({markerSourceNode:nestedFinalRootId,preserverSourceNodeId:nestedFinalRootId})).status,'verified',
  'an inherited proxy may use only the terminal root in the exact two-edge origins chain');
assert.throws(()=>helper.verifySerializedPrefab(nestedProxyPlan,prefabSpec,
  serializedWithProxy({markerSourceNode:'gameAsset:foreign-root#1'})),/SERIALIZED_CHILD_COUNT_MISMATCH/,
  'a foreign root ID outside the exact instance-to-template chain remains a source child');
const ambiguousProxyPlan=structuredClone(nestedProxyPlan);
ambiguousProxyPlan.syncPrefabBindings[0].origins.push({instanceSourceId:sourceId,templateSourceId:'gameAsset:foreign-root#1'});
assert.throws(()=>helper.verifySerializedPrefab(ambiguousProxyPlan,prefabSpec,
  serializedWithProxy({markerSourceNode:nestedFinalRootId,preserverSourceNodeId:nestedFinalRootId})),/ORIGIN_AMBIGUOUS/,
  'an ambiguous instance-to-template mapping cannot authorize a proxy root');
const cyclicProxyPlan=structuredClone(nestedProxyPlan);
cyclicProxyPlan.syncPrefabBindings[0].origins[1].templateSourceId=sourceId;
assert.throws(()=>helper.verifySerializedPrefab(cyclicProxyPlan,prefabSpec,
  serializedWithProxy({markerSourceNode:nestedFinalRootId,preserverSourceNodeId:nestedFinalRootId})),/ORIGIN_CYCLE/,
  'a cyclic instance-to-template mapping cannot authorize a proxy root');
const wrongClass = { ...Preserver, __cid__: 'wrong-script-uuid' };
const wrongCc = { ...cc, js: { ...cc.js, getClassByName: () => wrongClass } };
assert.equal(helper.isPreserver(wrongClass, wrongCc), false);
assert.throws(() => helper.attachPreservers(plan, nodes, wrongCc, 'gameAsset:prefab'), /CLASS_IDENTITY_MISMATCH/);

console.log('Creator Spine UITransform preservation neutral tests passed');
