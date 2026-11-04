'use strict';

const assert = require('node:assert/strict');
const bridge = require('../src/monkey/targets/materials/spine/CreatorSpineMaterialBindings');
const spineBinding = require('../src/monkey/targets/spine/creator_spine_binding');

function makePass({ defines, blendSrc, blendDst, shaderName = 'observed-gfx-shader' }) {
  return {
    program: 'spine|sprite-vs:vert|sprite-fs:frag',
    defines: Object.assign({ USE_ALPHA_TEST: false }, defines),
    blendState: { targets: [{ blend: true, blendSrc, blendDst, blendSrcAlpha: blendSrc, blendDstAlpha: blendDst }] },
    _shader: { name: shaderName },
  };
}

function makeMaterial({ uuid = 'default-spine-material', hash = 3890043391, isInstance = false, pass } = {}) {
  const material = {
    _uuid: uuid,
    name: isInstance ? 'builtin-spine (Instance)' : 'builtin-spine',
    effectAsset: { name: 'builtin-spine', _uuid: 'builtin-spine-effect',
      shaders: [{ name: 'spine|sprite-vs:vert|sprite-fs:frag', hash }] },
    passes: [pass || makePass({ defines: { USE_LOCAL: true, TWO_COLORED: false }, blendSrc: 5, blendDst: 10 })],
    parent: isInstance ? { _uuid: 'default-spine-material' } : null,
  };
  return material;
}

function makeContract() {
  return {
    profile: 'cocos24-builtin-spine-material-v1',
    creatorBindingStatus: 'source-semantics-exact-builtin-spine',
    pins: { effectProgramCanonicalSha256: 'fa1eb573d4176d66532beaa206631488779d0a04edde8f974131acdaee643b38',
      materialReferenceSourceId: 'gameAsset:material-ref', materialSourceId: 'internal:material-ref' },
    spec: { creator38: {
      sourceVariantConditions: { INPUT_IS_GAMMA: false, CC_USE_ALPHA_ATLAS_texture: false, USE_ALPHA_TEST: false },
      perComponent: [{ sourceComponentId: 'prefab#1/components/0', sourceMaterialReferenceSourceId: 'gameAsset:material-ref',
        sourceMaterialSourceId: 'internal:material-ref', premultipliedAlpha: false,
        useTint: false, enableBatch: false, sourceCacheMode: { effectiveDefaultCacheMode: 0 },
        sourceBlendModeCounts: { normal: 1, additive: 0, multiply: 0, screen: 0 } }],
    } },
  };
}

function makeComponent({ active = true, drawList } = {}) {
  return {
    node: { active: active, activeInHierarchy: active },
    enabled: true,
    enabledInHierarchy: active,
    premultipliedAlpha: true,
    useTint: true,
    enableBatch: true,
    customMaterial: null,
    _shared: null,
    getSharedMaterial(index) { return index === 0 ? this._shared : null; },
    setAnimationCacheMode(mode) { this.cacheMode = mode; },
    set customMaterial(value) { this._custom = value; this._shared = value; },
    get customMaterial() { return this._custom || null; },
    drawList: drawList || { length: 0, data: [] },
  };
}

const sourceId = 'prefab#1/components/0';
const activeMaterial = makeMaterial({ isInstance: true,
  pass: makePass({ defines: { USE_LOCAL: true, TWO_COLORED: false }, blendSrc: 5, blendDst: 10 }) });
const activeComponent = makeComponent({ drawList: { length: 1, data: [{ material: activeMaterial,
  texture: { uuid: 'page-texture-uuid' }, indexOffset: 0, indexCount: 6 }] } });
const activeReadback = bridge.collectCreatorSpineMaterialReadback(sourceId, activeComponent);
assert.equal(activeReadback.resourceReadback.status, 'observed');
assert.equal(activeReadback.runtimeReadback.status, 'observed_active_draw_materials');
assert.equal(activeReadback.runtimeReadback.draws[0].material.passes[0].defines.values.TWO_COLORED, false);
assert.equal(activeReadback.runtimeReadback.draws[0].material.passes[0].blendState.targets[0].blendSrc.value, 5);
assert.equal(activeReadback.runtimeReadback.draws[0].textureUuid.value, 'page-texture-uuid');
assert.equal(activeReadback.runtimeReadback.draws[0].material.passes[0].nativeShaderHash.status,
  'not_exposed_by_installed_runtime');

const inactiveMaterial = makeMaterial();
const inactiveComponent = makeComponent({ active: false });
inactiveComponent.customMaterial = inactiveMaterial;
const inactiveReadback = bridge.collectCreatorSpineMaterialReadback(sourceId, inactiveComponent, { isPrefabAsset: true });
assert.equal(inactiveReadback.resourceReadback.status, 'observed');
assert.equal(inactiveReadback.runtimeReadback.status, 'not_run_inactive_prefab_resource_only');

let builtinLookupCount = 0;
const component = makeComponent({ drawList: { length: 1, data: [{ material: activeMaterial,
  texture: { uuid: 'page-texture-uuid' }, indexOffset: 0, indexCount: 6 }] } });
const bindResult = bridge.bindCreatorSpineMaterial(sourceId, component, makeContract(), {
  builtinResMgr: { get(id) { builtinLookupCount++; return id === 'default-spine-material' ? inactiveMaterial : null; } },
}, { sourceMaterialReferenceSourceId: 'gameAsset:material-ref' });
assert.equal(builtinLookupCount, 1);
assert.equal(bindResult.status, 'bound_resource_observed_runtime_separately');
assert.equal(bindResult.targetMaterialIdentity.effectProgramHash, 3890043391);
assert.equal(bindResult.sourceMaterialBinding.resolvedSourceId, 'internal:material-ref');
assert.equal(bindResult.readback.runtimeReadback.status, 'observed_active_draw_materials');
assert.equal(bindResult.runtimeValidation.status, 'matched_observations');
assert.equal(component.premultipliedAlpha, false);
assert.equal(component.useTint, false);
assert.equal(component.enableBatch, false);

const sourceDefaultContract = makeContract();
sourceDefaultContract.spec.creator38.perComponent[0].sourceMaterialReferenceSourceId = null;
sourceDefaultContract.spec.creator38.perComponent[0].sourceMaterialSourceId = null;
sourceDefaultContract.spec.creator38.perComponent[0].sourceMaterialBinding = {
  status: 'resolved_source_engine_default', sourceEngineVersion: '2.4.15',
  sourcePath: 'extensions/spine/Skeleton.js',
  sourceSha256: '7cdc119e26aa6dceec4bd78ae30dd08f39daa2f0da5d914d2197a730b558a5e8',
  method: "Skeleton._getDefaultMaterial -> cc.Material.getBuiltinMaterial('2d-spine')",
  targetProfile: "Creator 3.8.8 builtinResMgr.get('default-spine-material')",
};
const defaultMaterialComponent = makeComponent();
const defaultMaterialResult = bridge.bindCreatorSpineMaterial(sourceId, defaultMaterialComponent,
  sourceDefaultContract, { builtinResMgr: { get(id) { return id === 'default-spine-material' ? inactiveMaterial : null; } } });
assert.equal(defaultMaterialResult.status, 'bound_resource_observed_runtime_separately');
assert.equal(defaultMaterialResult.sourceMaterialBinding.status, 'resolved_source_engine_default');
assert.equal(defaultMaterialResult.sourceMaterialBinding.referenceSourceId, null);

const staticDefaultBinding = {
  sourceComponentId: sourceId,
  creator: { fields: {} },
  creatorMaterialBinding: {
    sourceComponentId: sourceId, targetMaterialUuid: 'default-spine-material',
    contract: 'cocos24-builtin-spine-material-v1', contractSha256: 'a'.repeat(64),
    evidenceStatus: 'source_to_internal_to_creator_builtin_pinned',
    sourceMaterialReferenceSourceId: null, sourceMaterialSourceId: null,
    sourceMaterialBinding: sourceDefaultContract.spec.creator38.perComponent[0].sourceMaterialBinding,
  },
};
const appliedDefault = spineBinding.applyCreatorSpineBinding(staticDefaultBinding, () => makeComponent(), () => null);
assert.equal(appliedDefault.materialRoute, 'builtin-spine-material');
staticDefaultBinding.creatorMaterialBinding.sourceMaterialBinding.sourceSha256 = '0'.repeat(64);
assert.throws(() => spineBinding.applyCreatorSpineBinding(staticDefaultBinding, () => makeComponent(), () => null),
  /Invalid exact Creator built-in Spine material mapping/);

const wrongMaterial = makeMaterial({ hash: 1 });
const wrong = bridge.bindCreatorSpineMaterial(sourceId, makeComponent(), makeContract(), {
  builtinResMgr: { get() { return wrongMaterial; } },
}, { sourceMaterialReferenceSourceId: 'gameAsset:material-ref' });
assert.equal(wrong.status, 'binding_not_attempted');
assert.equal(wrong.resourceGuard.code, 'SPINE_BUILTIN_EFFECT_PROGRAM_HASH_MISMATCH');

const unexpectedPass = makePass({ defines: { USE_LOCAL: true, TWO_COLORED: false }, blendSrc: 7, blendDst: 10 });
const unexpectedMaterial = makeMaterial({ isInstance: true, pass: unexpectedPass });
const unexpectedComponent = makeComponent({ drawList: { length: 1, data: [{ material: unexpectedMaterial,
  texture: { uuid: 'page-texture-uuid' }, indexOffset: 0, indexCount: 6 }] } });
const mismatch = bridge.bindCreatorSpineMaterial(sourceId, unexpectedComponent, makeContract(), {
  builtinResMgr: { get() { return inactiveMaterial; } },
}, { sourceMaterialReferenceSourceId: 'gameAsset:material-ref' });
assert.equal(mismatch.runtimeValidation.status, 'mismatch');
assert.equal(mismatch.readback.runtimeReadback.draws[0].material.passes[0].blendState.targets[0].blendSrc.value, 7);

const sourceRefMissing = bridge.bindCreatorSpineMaterial(sourceId, makeComponent(), makeContract(), {
  builtinResMgr: { get() { return inactiveMaterial; } },
});
assert.equal(sourceRefMissing.status, 'binding_not_attempted');
assert.equal(sourceRefMissing.sourceMaterialStatus, 'source_material_reference_not_supplied');
const sourceRefWrong = bridge.bindCreatorSpineMaterial(sourceId, makeComponent(), makeContract(), {
  builtinResMgr: { get() { return inactiveMaterial; } },
}, { sourceMaterialReferenceSourceId: 'gameAsset:other-material' });
assert.equal(sourceRefWrong.status, 'binding_not_attempted');
assert.equal(sourceRefWrong.sourceMaterialStatus, 'source_material_reference_mismatch');

console.log('Creator Spine material bridge neutral tests passed');
