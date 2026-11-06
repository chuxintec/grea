// Read and bind the source-pinned Cocos 3.8.8 builtin Spine Material.
// Values labelled observed below are read from actual Creator runtime objects;
// expected values are only used as guards and are never copied into readback.
'use strict';

const SOURCE_PROFILE = 'cocos24-builtin-spine-material-v1';
const SOURCE_PROGRAM_HASH = 'fa1eb573d4176d66532beaa206631488779d0a04edde8f974131acdaee643b38';
const TARGET_EFFECT_NAME = 'builtin-spine';
const TARGET_EFFECT_PROGRAM = 'spine|sprite-vs:vert|sprite-fs:frag';
const TARGET_EFFECT_PROGRAM_HASH = 3890043391;
const BUILTIN_MATERIAL_UUID = 'default-spine-material';
const SOURCE_DEFAULT_MATERIAL_SHA256 = '7cdc119e26aa6dceec4bd78ae30dd08f39daa2f0da5d914d2197a730b558a5e8';

function error(code, message) {
  const value = new Error(message);
  value.code = code;
  return value;
}

function own(value, key) {
  return value != null && Object.prototype.hasOwnProperty.call(value, key);
}

function valueOrMissing(object, key) {
  return object != null && key in Object(object) ? { status: 'observed', value: object[key] }
    : { status: 'not_exposed_by_installed_runtime' };
}

function copyDefines(pass) {
  if (!pass || !pass.defines || typeof pass.defines !== 'object') {
    return { status: 'not_exposed_by_installed_runtime', values: null };
  }
  return { status: 'observed', values: Object.assign({}, pass.defines) };
}

function copyBlendState(pass) {
  const blendState = pass && pass.blendState;
  const targets = blendState && blendState.targets;
  if (!Array.isArray(targets)) {
    return { status: 'not_exposed_by_installed_runtime', targets: null };
  }
  return {
    status: 'observed',
    targets: targets.map((target, index) => ({
      index,
      blend: valueOrMissing(target, 'blend'),
      blendEq: valueOrMissing(target, 'blendEq'),
      blendAlphaEq: valueOrMissing(target, 'blendAlphaEq'),
      blendSrc: valueOrMissing(target, 'blendSrc'),
      blendDst: valueOrMissing(target, 'blendDst'),
      blendSrcAlpha: valueOrMissing(target, 'blendSrcAlpha'),
      blendDstAlpha: valueOrMissing(target, 'blendDstAlpha'),
    })),
  };
}

function readMaterial(material, role) {
  if (!material) return { status: 'material_reference_missing', role };
  const effect = material.effectAsset || null;
  const programs = effect && Array.isArray(effect.shaders) ? effect.shaders : null;
  const passes = Array.isArray(material.passes) ? material.passes : null;
  const shaderObjects = passes ? passes.map((pass, index) => {
    const shader = pass && pass._shader;
    return {
      index,
      program: valueOrMissing(pass, 'program'),
      defines: copyDefines(pass),
      blendState: copyBlendState(pass),
      compiledShader: shader ? { status: 'observed', name: valueOrMissing(shader, 'name') }
        : { status: 'not_compiled_or_not_exposed' },
      // The installed public Pass API exposes a Shader object but no numeric
      // native shader hash. Do not substitute the Effect program hash here.
      nativeShaderHash: { status: 'not_exposed_by_installed_runtime' },
    };
  }) : null;
  return {
    status: 'observed',
    role,
    materialUuid: valueOrMissing(material, '_uuid').status === 'observed'
      ? valueOrMissing(material, '_uuid') : valueOrMissing(material, 'uuid'),
    materialName: valueOrMissing(material, 'name'),
    isMaterialInstance: material.parent != null,
    parentMaterialUuid: material.parent ? valueOrMissing(material.parent, '_uuid') : { status: 'not_a_material_instance' },
    effect: effect ? {
      status: 'observed', name: valueOrMissing(effect, 'name'),
      uuid: valueOrMissing(effect, '_uuid').status === 'observed' ? valueOrMissing(effect, '_uuid') : valueOrMissing(effect, 'uuid'),
    } : { status: 'effect_asset_missing' },
    effectPrograms: programs ? programs.map(program => ({
      name: valueOrMissing(program, 'name'),
      hash: valueOrMissing(program, 'hash'),
    })) : { status: 'not_exposed_by_installed_runtime' },
    passes: shaderObjects || { status: 'not_exposed_by_installed_runtime' },
  };
}

function componentActivity(component) {
  const node = component && component.node;
  return {
    componentEnabled: valueOrMissing(component, 'enabled'),
    componentEnabledInHierarchy: valueOrMissing(component, 'enabledInHierarchy'),
    nodeActive: valueOrMissing(node, 'active'),
    nodeActiveInHierarchy: valueOrMissing(node, 'activeInHierarchy'),
  };
}

function isActiveFromObservedState(activity) {
  return activity.componentEnabledInHierarchy.status === 'observed' &&
    activity.componentEnabledInHierarchy.value === true &&
    activity.nodeActiveInHierarchy.status === 'observed' &&
    activity.nodeActiveInHierarchy.value === true;
}

function collectCreatorSpineMaterialReadback(componentSourceId, component, options) {
  options = options || {};
  if (typeof componentSourceId !== 'string' || !componentSourceId) {
    throw error('SPINE_MATERIAL_COMPONENT_ID', 'A source component ID is required for readback.');
  }
  if (!component || typeof component !== 'object') {
    throw error('SPINE_MATERIAL_COMPONENT_MISSING', 'The native Creator sp.Skeleton object was not supplied.');
  }

  const activity = componentActivity(component);
  const customMaterial = valueOrMissing(component, 'customMaterial');
  let sharedMaterial = { status: 'method_not_exposed_by_installed_runtime' };
  if (typeof component.getSharedMaterial === 'function') {
    sharedMaterial = { status: 'observed', value: component.getSharedMaterial(0) || null };
  }
  const resourceMaterial = customMaterial.status === 'observed' && customMaterial.value
    ? customMaterial.value : sharedMaterial.value || options.materialResource || null;
  let resourceReadback = readMaterial(resourceMaterial, customMaterial.value ? 'customMaterial' : 'sharedMaterial');
  const activityAllowsRuntime = !options.isPrefabAsset && isActiveFromObservedState(activity);

  if (options.isPrefabAsset === true || !activityAllowsRuntime) {
    return {
      schema: 'creator-spine-material-readback/1',
      sourceComponentId: componentSourceId,
      sourceProfile: SOURCE_PROFILE,
      activity,
      resourceReadback,
      runtimeReadback: {
        status: options.isPrefabAsset === true ? 'not_run_inactive_prefab_resource_only'
          : 'not_run_component_or_node_inactive_or_activity_unobserved',
        drawCount: { status: 'not_read_for_inactive_component' },
        draws: [],
      },
      nativeCompilation: 'not_claimed',
    };
  }

  const drawList = component.drawList;
  if (!drawList || !Array.isArray(drawList.data) || !Number.isInteger(drawList.length)) {
    return {
      schema: 'creator-spine-material-readback/1', sourceComponentId: componentSourceId,
      sourceProfile: SOURCE_PROFILE, activity, resourceReadback,
      runtimeReadback: { status: 'draw_list_not_exposed_by_installed_runtime', drawCount: { status: 'missing' }, draws: [] },
      nativeCompilation: 'not_claimed',
    };
  }
  if (drawList.length === 0) {
    return {
      schema: 'creator-spine-material-readback/1', sourceComponentId: componentSourceId,
      sourceProfile: SOURCE_PROFILE, activity, resourceReadback,
      runtimeReadback: { status: 'active_but_no_render_slots_populated', drawCount: { status: 'observed', value: 0 }, draws: [] },
      nativeCompilation: 'not_claimed',
    };
  }

  if (resourceReadback.status !== 'observed') {
    const activeMaterial = drawList.data[0] && drawList.data[0].material;
    if (activeMaterial && activeMaterial.parent) {
      resourceReadback = readMaterial(activeMaterial.parent, 'active_draw_material_parent');
    }
  }

  const draws = [];
  for (let index = 0; index < drawList.length; index++) {
    const row = drawList.data[index];
    const material = row && row.material;
    const texture = row && row.texture;
    draws.push({
      drawIndex: index,
      renderSlotIdentity: { status: 'source_slot_name_not_exposed_by_installed_SkeletonDrawData', drawIndex: index },
      indexOffset: valueOrMissing(row, 'indexOffset'),
      indexCount: valueOrMissing(row, 'indexCount'),
      textureUuid: texture ? (valueOrMissing(texture, 'uuid').status === 'observed'
        ? valueOrMissing(texture, 'uuid') : valueOrMissing(texture, '_uuid')) : { status: 'texture_reference_missing' },
      material: readMaterial(material, 'active_draw_slot_material'),
    });
  }
  return {
    schema: 'creator-spine-material-readback/1', sourceComponentId: componentSourceId,
    sourceProfile: SOURCE_PROFILE, activity, resourceReadback,
    runtimeReadback: { status: 'observed_active_draw_materials', drawCount: { status: 'observed', value: drawList.length }, draws },
    nativeCompilation: 'not_claimed',
  };
}

function observed(entry) {
  return entry && entry.status === 'observed' ? entry.value : undefined;
}

function validateRuntimeReadback(readback, source) {
  const runtime = readback && readback.runtimeReadback;
  if (!runtime || runtime.status !== 'observed_active_draw_materials') {
    return { status: 'not_run', reason: runtime ? runtime.status : 'runtime_readback_missing', mismatches: [], missingFields: [] };
  }
  const expectedBlend = {
    normal: [source.premultipliedAlpha ? 1 : 5, 10],
    additive: [source.premultipliedAlpha ? 1 : 5, 1],
    multiply: [2, 10],
    screen: [1, 6],
  };
  const allowedBlendPairs = new Set();
  for (const [mode, count] of Object.entries(source.sourceBlendModeCounts || {})) {
    if (count > 0 && expectedBlend[mode]) allowedBlendPairs.add(expectedBlend[mode].join(':'));
  }
  const mismatches = [];
  const missingFields = [];
  for (const draw of runtime.draws || []) {
    const pass = draw.material && draw.material.passes && draw.material.passes[0];
    const defines = pass && pass.defines && pass.defines.values;
    for (const [name, expected] of Object.entries({
      USE_LOCAL: !source.enableBatch,
      TWO_COLORED: source.useTint,
      USE_ALPHA_TEST: false,
    })) {
      if (!defines || !Object.prototype.hasOwnProperty.call(defines, name)) {
        missingFields.push({ drawIndex: draw.drawIndex, field: `defines.${name}` });
      } else if (defines[name] !== expected) {
        mismatches.push({ drawIndex: draw.drawIndex, field: `defines.${name}`, expected, observed: defines[name] });
      }
    }
    const target = pass && pass.blendState && pass.blendState.targets && pass.blendState.targets[0];
    const blendSrc = target && observed(target.blendSrc);
    const blendDst = target && observed(target.blendDst);
    if (!Number.isInteger(blendSrc) || !Number.isInteger(blendDst)) {
      missingFields.push({ drawIndex: draw.drawIndex, field: 'blendState.targets[0].blendSrc/blendDst' });
    } else if (!allowedBlendPairs.has(`${blendSrc}:${blendDst}`)) {
      mismatches.push({ drawIndex: draw.drawIndex, field: 'blendState.targets[0]', observed: [blendSrc, blendDst],
                        sourceAllowed: Array.from(allowedBlendPairs) });
    }
    if (!pass || !pass.compiledShader || pass.compiledShader.status !== 'observed') {
      missingFields.push({ drawIndex: draw.drawIndex, field: 'compiledShaderObject' });
    }
    const programs = draw.material && draw.material.effectPrograms;
    const program = Array.isArray(programs) && programs.find(item =>
      observed(item.name) === TARGET_EFFECT_PROGRAM);
    if (!program || observed(program.hash) !== TARGET_EFFECT_PROGRAM_HASH) {
      if (!program) missingFields.push({ drawIndex: draw.drawIndex, field: 'EffectAsset.shaders[].hash' });
      else mismatches.push({ drawIndex: draw.drawIndex, field: 'EffectAsset.shaders[].hash',
                             expected: TARGET_EFFECT_PROGRAM_HASH, observed: observed(program.hash) });
    }
  }
  return {
    status: mismatches.length ? 'mismatch' : missingFields.length ? 'incomplete' : 'matched_observations',
    reason: 'material_pass_objects_observed_without_forcing_shader_compilation',
    mismatches,
    missingFields,
    nativeCompilation: 'not_claimed',
  };
}

function resolveBuiltinSpineMaterial(cclegacy) {
  const manager = cclegacy && cclegacy.builtinResMgr;
  if (!manager || typeof manager.get !== 'function') {
    return { status: 'builtin_resource_manager_missing', material: null };
  }
  const material = manager.get(BUILTIN_MATERIAL_UUID) || null;
  return material ? { status: 'observed', material } : { status: 'builtin_spine_material_missing', material: null };
}

function matchesPinnedBuiltinResource(material) {
  if (!material) return { ok: false, code: 'SPINE_BUILTIN_MATERIAL_MISSING' };
  const effect = material.effectAsset;
  const programs = effect && Array.isArray(effect.shaders) ? effect.shaders : [];
  const program = programs.find(item => item && item.name === TARGET_EFFECT_PROGRAM);
  if (material._uuid !== BUILTIN_MATERIAL_UUID || !effect || effect.name !== TARGET_EFFECT_NAME || !program) {
    return { ok: false, code: 'SPINE_BUILTIN_RESOURCE_IDENTITY_MISMATCH' };
  }
  if (program.hash !== TARGET_EFFECT_PROGRAM_HASH) {
    return { ok: false, code: 'SPINE_BUILTIN_EFFECT_PROGRAM_HASH_MISMATCH', observedProgramHash: program.hash };
  }
  return { ok: true, observedProgramHash: program.hash, observedProgramName: program.name };
}

function sourceMaterialMode(source, pins) {
  const evidence = source && source.sourceMaterialBinding;
  if (!evidence || evidence.status === 'explicit') {
    return source && typeof source.sourceMaterialReferenceSourceId === 'string' &&
      source.sourceMaterialReferenceSourceId === pins.materialReferenceSourceId &&
      source.sourceMaterialSourceId === pins.materialSourceId ? 'explicit' : null;
  }
  if (evidence.status === 'resolved_source_engine_default' &&
      source.sourceMaterialReferenceSourceId === null && source.sourceMaterialSourceId === null &&
      evidence.sourceEngineVersion === '2.4.15' &&
      evidence.sourcePath === 'extensions/spine/Skeleton.js' &&
      evidence.sourceSha256 === SOURCE_DEFAULT_MATERIAL_SHA256 &&
      evidence.method === "Skeleton._getDefaultMaterial -> cc.Material.getBuiltinMaterial('2d-spine')" &&
      evidence.targetProfile === "Creator 3.8.8 builtinResMgr.get('default-spine-material')") return 'resolved_source_engine_default';
  return null;
}

function bindCreatorSpineMaterial(componentSourceId, component, contract, cclegacy, options) {
  options = options || {};
  if (!contract || contract.profile !== SOURCE_PROFILE ||
      contract.creatorBindingStatus !== 'source-semantics-exact-builtin-spine' ||
      !contract.pins || contract.pins.effectProgramCanonicalSha256 !== SOURCE_PROGRAM_HASH ||
      !contract.spec || !contract.spec.creator38 || !contract.spec.creator38.sourceVariantConditions ||
      contract.spec.creator38.sourceVariantConditions.INPUT_IS_GAMMA !== false ||
      contract.spec.creator38.sourceVariantConditions.CC_USE_ALPHA_ATLAS_texture !== false ||
      contract.spec.creator38.sourceVariantConditions.USE_ALPHA_TEST !== false) {
    throw error('SPINE_MATERIAL_PROFILE_MISMATCH', 'Source Spine Effect profile is not the pinned Cocos 2.4.15 builtin program.');
  }
  const rows = contract.spec.creator38.perComponent;
  const source = Array.isArray(rows) && rows.find(row => row.sourceComponentId === componentSourceId);
  if (!source) throw error('SPINE_MATERIAL_SOURCE_COMPONENT', 'Source component is outside the pinned material plan.');
  const materialMode = sourceMaterialMode(source, contract.pins);
  if (!materialMode) {
    throw error('SPINE_SOURCE_MATERIAL_CONTRACT_MISMATCH', 'Source material reference or redirect target differs from the pinned profile.');
  }
  if (materialMode === 'explicit' && !options.sourceMaterialReferenceSourceId) {
    return {
      schema: 'creator-spine-material-bind/1', sourceComponentId: componentSourceId, status: 'binding_not_attempted',
      sourceProfile: SOURCE_PROFILE, sourceMaterialStatus: 'source_material_reference_not_supplied',
      expectedSourceMaterialReferenceSourceId: source.sourceMaterialReferenceSourceId,
      expectedSourceMaterialSourceId: source.sourceMaterialSourceId,
      readback: component ? collectCreatorSpineMaterialReadback(componentSourceId, component, options) : null,
    };
  }
  if (materialMode === 'resolved_source_engine_default' && options.sourceMaterialReferenceSourceId) {
    throw error('SPINE_SOURCE_MATERIAL_CONTRACT_MISMATCH', 'A source-engine-default material row cannot carry a serialized source reference.');
  }
  if (materialMode === 'explicit' && options.sourceMaterialReferenceSourceId !== source.sourceMaterialReferenceSourceId) {
    return {
      schema: 'creator-spine-material-bind/1', sourceComponentId: componentSourceId, status: 'binding_not_attempted',
      sourceProfile: SOURCE_PROFILE, sourceMaterialStatus: 'source_material_reference_mismatch',
      expectedSourceMaterialReferenceSourceId: source.sourceMaterialReferenceSourceId,
      observedSourceMaterialReferenceSourceId: options.sourceMaterialReferenceSourceId,
      expectedSourceMaterialSourceId: source.sourceMaterialSourceId,
      readback: component ? collectCreatorSpineMaterialReadback(componentSourceId, component, options) : null,
    };
  }
  if (!component || typeof component !== 'object' || !('premultipliedAlpha' in component) ||
      !('customMaterial' in component) || !component.node) {
    throw error('SPINE_MATERIAL_COMPONENT_TYPE', 'Expected a native Creator sp.Skeleton component.');
  }
  if (typeof source.premultipliedAlpha !== 'boolean' || typeof source.useTint !== 'boolean' ||
      typeof source.enableBatch !== 'boolean') {
    throw error('SPINE_MATERIAL_SOURCE_VARIANT_UNKNOWN', 'Source PMA, tint or batch state is unresolved.');
  }
  if (source.sourceBlendModeCounts && source.sourceBlendModeCounts.screen > 0 && !source.premultipliedAlpha) {
    throw error('SPINE_MATERIAL_SCREEN_BLEND_MISMATCH', 'Creator 3.8 changes Screen blend factors for straight alpha.');
  }
  const resolved = resolveBuiltinSpineMaterial(cclegacy);
  const resourceGuard = matchesPinnedBuiltinResource(resolved.material);
  if (!resourceGuard.ok) {
    return {
      schema: 'creator-spine-material-bind/1', sourceComponentId: componentSourceId, status: 'binding_not_attempted',
      sourceProfile: SOURCE_PROFILE, resourceManagerStatus: resolved.status,
      resourceGuard, readback: collectCreatorSpineMaterialReadback(componentSourceId, component, options),
    };
  }

  const cacheMode = source.sourceCacheMode && source.sourceCacheMode.effectiveDefaultCacheMode;
  if (!Number.isInteger(cacheMode) || ![0, 1, 2].includes(cacheMode)) {
    throw error('SPINE_MATERIAL_CACHE_MODE_UNKNOWN', 'Source animation cache mode is outside the pinned Cocos 2.4 value set.');
  }
  if (typeof component.setAnimationCacheMode === 'function') component.setAnimationCacheMode(cacheMode);
  component.premultipliedAlpha = source.premultipliedAlpha;
  component.useTint = source.useTint;
  component.enableBatch = source.enableBatch;
  component.customMaterial = resolved.material;

  const readback = collectCreatorSpineMaterialReadback(componentSourceId, component,
    Object.assign({}, options, { materialResource: resolved.material }));
  const effectiveMaterialUuid = readback.resourceReadback.materialUuid;
  const materialBindingReadback = effectiveMaterialUuid && effectiveMaterialUuid.status === 'observed'
    && effectiveMaterialUuid.value === BUILTIN_MATERIAL_UUID;
  return {
    schema: 'creator-spine-material-bind/1', sourceComponentId: componentSourceId,
    status: materialBindingReadback ? 'bound_resource_observed_runtime_separately' : 'binding_readback_missing',
    sourceProfile: SOURCE_PROFILE,
    sourceMaterialBinding: {
      referenceSourceId: source.sourceMaterialReferenceSourceId || null,
      resolvedSourceId: source.sourceMaterialSourceId || null,
      targetResourceUuid: 'default-spine-material',
      status: materialMode === 'explicit' ? 'exact_source_builtin_profile_mapping' : 'resolved_source_engine_default',
      sourceDefaultEvidence: materialMode === 'resolved_source_engine_default' ? source.sourceMaterialBinding : null,
    },
    targetMaterialIdentity: { status: 'observed', uuid: resolved.material._uuid, effectName: resolved.material.effectAsset.name,
                             effectProgramName: resourceGuard.observedProgramName,
                             effectProgramHash: resourceGuard.observedProgramHash },
    materialReferenceReadback: materialBindingReadback ? 'observed' : 'missing',
    runtimeValidation: validateRuntimeReadback(readback, source),
    readback,
  };
}

module.exports = {
  bindCreatorSpineMaterial,
  collectCreatorSpineMaterialReadback,
  resolveBuiltinSpineMaterial,
};
