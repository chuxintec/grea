'use strict';

// Independent adapter for Creator's native sp.Skeleton component. The main
// prefab importer owns component construction and must call this after mapping
// each sourceComponentId to the created component and each source asset ID to
// a loaded sp.SkeletonData instance.
function explicitField(fields, name, target) {
    const row = fields && fields[name] && fields[name][target];
    return row && (row.status === 'explicit' || row.status === 'resolved_source_engine_default') && typeof row.member === 'string'
        ? { member: row.member, value: row.value }
        : null;
}

function assign(component, row) {
    if (!row) return;
    if (!(row.member in component)) throw new Error('Missing Creator Spine member: ' + row.member);
    component[row.member] = row.value;
}

const SOURCE_DEFAULT_SPINE_MATERIAL_SHA256 = '7cdc119e26aa6dceec4bd78ae30dd08f39daa2f0da5d914d2197a730b558a5e8';

function sourceMaterialBindingKind(binding) {
    const evidence = binding && binding.sourceMaterialBinding;
    if (!evidence) {
        return typeof binding.sourceMaterialReferenceSourceId === 'string' && binding.sourceMaterialReferenceSourceId &&
            typeof binding.sourceMaterialSourceId === 'string' && binding.sourceMaterialSourceId
            ? 'explicit' : null;
    }
    if (evidence.status === 'explicit') {
        return typeof binding.sourceMaterialReferenceSourceId === 'string' && binding.sourceMaterialReferenceSourceId &&
            typeof binding.sourceMaterialSourceId === 'string' && binding.sourceMaterialSourceId
            ? 'explicit' : null;
    }
    if (evidence.status === 'resolved_source_engine_default' &&
        binding.sourceMaterialReferenceSourceId === null && binding.sourceMaterialSourceId === null &&
        evidence.sourceEngineVersion === '2.4.15' &&
        evidence.sourcePath === 'extensions/spine/Skeleton.js' &&
        evidence.sourceSha256 === SOURCE_DEFAULT_SPINE_MATERIAL_SHA256 &&
        evidence.method === "Skeleton._getDefaultMaterial -> cc.Material.getBuiltinMaterial('2d-spine')" &&
        evidence.targetProfile === "Creator 3.8.8 builtinResMgr.get('default-spine-material')") {
        return 'resolved_source_engine_default';
    }
    return null;
}

function applyCreatorSpineBinding(binding, resolveComponent, resolveSkeletonData) {
    if (!binding || !binding.sourceComponentId || !binding.creator || !binding.creator.fields)
        throw new Error('Invalid source-exact Spine component binding');
    const component = resolveComponent(binding.sourceComponentId);
    if (!component) throw new Error('No native component for source ID: ' + binding.sourceComponentId);

    const data = binding.creator.fields.skeletonData;
    if (data && data.sourceAssetId) {
        const asset = resolveSkeletonData(data.sourceAssetId);
        if (!asset) throw new Error('No exact Creator SkeletonData for source asset: ' + data.sourceAssetId);
        component.skeletonData = asset;
    }
    // An absent source UUID intentionally leaves skeletonData untouched. This
    // preserves room for source code to assign it later without inventing one.
    const fields = binding.creator.fields;
    const staticPose = binding.creatorStaticPose || null;
    const staticSourceScale = staticPose && staticPose.sourceTimeScale;
    for (const name of ['skin', 'animation', 'loop', ...(staticPose ? [] : ['timeScale']), 'premultipliedAlpha',
        'tint', 'debugSlots', 'debugBones', 'debugMesh', 'enableBatch', 'caching'])
        assign(component, explicitField(fields, name, 'creator'));

    if (staticPose) {
        const sourceScale = staticPose.sourceTimeScale;
        const sourceScaleRow = explicitField(fields, 'timeScale', 'creator');
        if (staticPose.policy !== 'enabled_realtime_renderer_with_serialized_timeScale_zero' ||
            staticPose.nativeEnabled !== true || staticPose.nativeTimeScale !== 0 ||
            !sourceScale || !sourceScaleRow ||
            !Object.is(sourceScale.value, sourceScaleRow.value) ||
            !['explicit', 'resolved_source_engine_default'].includes(sourceScale.status))
            throw new Error('Invalid source-pinned Creator static t0 policy');
        // Creator's Skeleton.updateAnimation() continues to update render data
        // while timeScale=0. This serialized value freezes realtime animation
        // at its initialized pose and survives Prefab save/reopen; `paused` is
        // runtime-only and is intentionally not used.
        component.timeScale = 0;
        component.enabled = true;
        if (typeof component.updateMaterial === 'function') component.updateMaterial();
    }

    const materialBinding = binding.creatorMaterialBinding || null;
    const materialBindingKind = materialBinding ? sourceMaterialBindingKind(materialBinding) : null;
    if (materialBinding && (materialBinding.targetMaterialUuid !== 'default-spine-material' ||
        materialBinding.contract !== 'cocos24-builtin-spine-material-v1' ||
        materialBinding.evidenceStatus !== 'source_to_internal_to_creator_builtin_pinned' ||
        !/^[0-9a-f]{64}$/.test(materialBinding.contractSha256 || '') ||
        materialBinding.sourceComponentId !== binding.sourceComponentId ||
        !materialBindingKind))
        throw new Error('Invalid exact Creator built-in Spine material mapping');

    return {
        sourceComponentId: binding.sourceComponentId,
        staticDataBound: !!(data && data.sourceAssetId),
        unresolvedDynamicAssignment: !(data && data.sourceAssetId),
        appliedFields: ['skin', 'animation', 'loop', ...(staticPose ? ['staticPose.nativeTimeScale'] : ['timeScale']), 'premultipliedAlpha',
            'tint', 'debugSlots', 'debugBones', 'debugMesh', 'enableBatch', 'caching']
            .filter(name => name === 'staticPose.nativeTimeScale' || !!explicitField(fields, name, 'creator')),
        sourceTimeScale: staticPose ? staticSourceScale.value : undefined,
        nativeTimeScale: staticPose ? component.timeScale : undefined,
        nativeEnabled: staticPose ? component.enabled : undefined,
        materialRoute: materialBinding ? 'builtin-spine-material' : undefined,
        sourceCallbacksExecuted: false,
    };
}

function applyCreatorSpineBindings(bindings, resolvers) {
    if (!Array.isArray(bindings) || !resolvers || typeof resolvers.resolveComponent !== 'function' ||
        typeof resolvers.resolveSkeletonData !== 'function')
        throw new Error('Creator Spine binding resolvers are required');
    return bindings.map(binding => applyCreatorSpineBinding(
        binding, resolvers.resolveComponent, resolvers.resolveSkeletonData));
}

function sourceNodeActivity(plan, sourceNodeId) {
    if (!plan || !Array.isArray(plan.nodes) || typeof sourceNodeId !== 'string' || !sourceNodeId)
        return { sourceNodeId, nodeActive: null, hierarchyActive: null, chain: [], status: 'source_activity_unavailable' };
    const nodes = new Map(plan.nodes.map(row => [row.sourceId, row]));
    if (nodes.size !== plan.nodes.length) throw new Error('SPINE_SOURCE_NODE_IDENTITY_DUPLICATE');
    const chain = [];
    const seen = new Set();
    let current = sourceNodeId;
    let hierarchyActive = true;
    let complete = false;
    let nodeActive = null;
    while (current) {
        if (seen.has(current)) throw new Error('SPINE_SOURCE_NODE_HIERARCHY_CYCLE:' + sourceNodeId);
        seen.add(current);
        const row = nodes.get(current);
        if (!row) break;
        chain.push(current);
        if (typeof row.active !== 'boolean') hierarchyActive = null;
        else if (row.active === false) hierarchyActive = false;
        if (current === sourceNodeId && typeof row.active === 'boolean') nodeActive = row.active;
        const parent = row.parent;
        if (parent === null || parent === undefined || parent === '') { complete = true; break; }
        current = parent;
    }
    if (hierarchyActive !== false && !complete) hierarchyActive = null;
    return {
        sourceNodeId, nodeActive, hierarchyActive, chain,
        status: hierarchyActive === false ? 'verified_source_hierarchy_inactive'
            : hierarchyActive === true ? 'verified_source_hierarchy_active' : 'source_activity_unresolved',
    };
}

function readCreatorSpineBinding(binding, resolveComponent, readContext) {
    if (!binding || !binding.sourceComponentId || !binding.creator || !binding.creator.fields)
        throw new Error('Invalid source-exact Spine component binding');
    const resolved = resolveComponent(binding.sourceComponentId);
    const component = Array.isArray(resolved)
        ? (resolved.length === 1 ? resolved[0] : null)
        : resolved;
    if (!component) throw new Error('Expected exactly one saved native sp.Skeleton for source ID: ' + binding.sourceComponentId);

    const fields = binding.creator.fields;
    const sourceData = fields.skeletonData || {};
    const hasStaticSourceData = typeof sourceData.sourceAssetId === 'string' && sourceData.sourceAssetId.length > 0;
    const expectedData = sourceData.creator && sourceData.creator.nativeUuid;
    const skeletonData = component.skeletonData || null;
    const actualDataUuid = skeletonData && skeletonData.uuid || null;
    const runtimeData = skeletonData && typeof skeletonData.getRuntimeData === 'function'
        ? skeletonData.getRuntimeData(true)
        : null;
    const requestedAnimationRow = explicitField(fields, 'animation', 'creator');
    const requestedSkinRow = explicitField(fields, 'skin', 'creator');
    const requestedAnimation = requestedAnimationRow && requestedAnimationRow.value ? requestedAnimationRow.value : null;
    const requestedSkin = requestedSkinRow && requestedSkinRow.value ? requestedSkinRow.value : null;
    const animations = runtimeData && Array.isArray(runtimeData.animations) ? runtimeData.animations : [];
    const skins = runtimeData && Array.isArray(runtimeData.skins) ? runtimeData.skins : [];
    const animationExists = requestedAnimation === null || !hasStaticSourceData || !runtimeData ? null
        : animations.some(row => row && row.name === requestedAnimation);
    const skinExists = requestedSkin === null || !hasStaticSourceData || !runtimeData ? null
        : skins.some(row => row && row.name === requestedSkin);
    const isCached = typeof component.isAnimationCached === 'function' && component.isAnimationCached();
    const currentEntry = !isCached && typeof component.getCurrent === 'function' ? component.getCurrent(0) : null;
    const actualAnimation = isCached
        ? (component._animationName || null)
        : (currentEntry && currentEntry.animation && currentEntry.animation.name) || component.animation || null;
    const actualSkin = (component._skeleton && component._skeleton.skin && component._skeleton.skin.name)
        || component._skinName || null;
    const runtimeSkeletonInitialized = !!component._skeleton || !!currentEntry || isCached;
    const sourceActivity = (readContext && readContext.sourceActivity) || binding.sourceNodeActivity || null;
    const readbackScope = readContext && typeof readContext.readbackScope === 'string'
        ? readContext.readbackScope : 'unspecified';
    const sourceNodeActive = sourceActivity && typeof sourceActivity.nodeActive === 'boolean'
        ? sourceActivity.nodeActive : null;
    const sourceHierarchyActive = sourceActivity && typeof sourceActivity.hierarchyActive === 'boolean'
        ? sourceActivity.hierarchyActive : null;
    const nativeNodeActive = component.node && typeof component.node.active === 'boolean'
        ? component.node.active : null;

    const actual = {
        nativeComponentUuid: component.uuid || null,
        skeletonDataUuid: actualDataUuid,
        defaultSkin: component.defaultSkin,
        currentSkin: actualSkin,
        defaultAnimation: component.defaultAnimation,
        currentAnimation: actualAnimation,
        loop: component.loop,
        timeScale: component.timeScale,
        enabled: component.enabled,
        premultipliedAlpha: component.premultipliedAlpha,
        useTint: component.useTint,
        debugBones: component.debugBones,
        debugSlots: component.debugSlots,
        debugMesh: component.debugMesh,
        enableBatch: component.enableBatch,
        defaultCacheMode: typeof component.defaultCacheMode === 'number' ? component.defaultCacheMode : null,
        runtimeAnimationNames: animations.map(row => row && row.name).filter(name => typeof name === 'string'),
        runtimeSkinNames: skins.map(row => row && row.name).filter(name => typeof name === 'string'),
    };
    const checks = {
        exactSkeletonDataUuid: hasStaticSourceData ? !!expectedData && actualDataUuid === expectedData : null,
        requestedAnimationExists: requestedAnimation === null ? null : animationExists,
        requestedSkinExists: requestedSkin === null ? null : skinExists,
        requestedAnimationActive: requestedAnimation === null || !runtimeData || !runtimeSkeletonInitialized
            ? null : actualAnimation === requestedAnimation,
        requestedSkinActive: requestedSkin === null || !runtimeData || !runtimeSkeletonInitialized
            ? null : actualSkin === requestedSkin,
        sourceNodeActiveMatchesPlan: sourceNodeActive === null || nativeNodeActive === null
            ? null : sourceNodeActive === nativeNodeActive,
    };
    const staticPose = binding.creatorStaticPose || null;
    if (staticPose) {
        const sourceScale = staticPose.sourceTimeScale;
        const sourceScaleRow = explicitField(fields, 'timeScale', 'creator');
        checks.sourceTimeScaleRetainedInPinnedSpec = !!sourceScale && !!sourceScaleRow &&
            Object.is(sourceScale.value, sourceScaleRow.value) &&
            ['explicit', 'resolved_source_engine_default'].includes(sourceScale.status);
        checks.nativeTimeScaleFrozenAtT0 = component.timeScale === 0 && staticPose.nativeTimeScale === 0;
        checks.nativeRendererEnabled = component.enabled === true && staticPose.nativeEnabled === true;
        checks.serializedAnimationContinuesToRender = staticPose.policy === 'enabled_realtime_renderer_with_serialized_timeScale_zero';
    }
    const materialBinding = binding.creatorMaterialBinding || null;
    if (materialBinding) {
        checks.exactBuiltinMaterialContract = materialBinding.sourceComponentId === binding.sourceComponentId &&
            materialBinding.targetMaterialUuid === 'default-spine-material' &&
            materialBinding.contract === 'cocos24-builtin-spine-material-v1' &&
            materialBinding.evidenceStatus === 'source_to_internal_to_creator_builtin_pinned' &&
            /^[0-9a-f]{64}$/.test(materialBinding.contractSha256 || '') &&
            !!sourceMaterialBindingKind(materialBinding);
        // The Creator engine resolves the built-in Spine material internally
        // in _updateBuiltinMaterial(). Do not assign a custom material here.
        checks.usesDefaultBuiltinMaterialRoute = component.customMaterial == null;
    }
    for (const key of ['skin', 'animation', 'loop', 'timeScale', 'premultipliedAlpha',
        'tint', 'debugSlots', 'debugBones', 'debugMesh', 'enableBatch', 'caching']) {
        if (key === 'timeScale' && staticPose) continue;
        const row = explicitField(fields, key, 'creator');
        if (!row) continue;
        const actualValue = key === 'skin' ? actual.defaultSkin
            : key === 'animation' ? actual.defaultAnimation
                : key === 'caching' ? actual.defaultCacheMode
                    : key === 'tint' ? actual.useTint : actual[key];
        checks[key + 'FieldMatchesSource'] = Object.is(actualValue, row.value);
    }
    const failures = Object.entries(checks).filter(([, value]) => value === false).map(([name]) => name);
    const serializedRequestedIdentityVerified = hasStaticSourceData && !!runtimeData &&
        checks.exactSkeletonDataUuid === true &&
        (requestedAnimation === null || checks.requestedAnimationExists === true && checks.animationFieldMatchesSource === true) &&
        (requestedSkin === null || checks.requestedSkinExists === true && checks.skinFieldMatchesSource === true);
    const runtimePoseStatus = runtimeSkeletonInitialized
        ? (failures.length ? 'initialized_runtime_state_mismatch' : 'initialized_runtime_state_verified')
        : sourceHierarchyActive === false ? 'runtime_state_not_initialized_source_inactive'
            : sourceHierarchyActive === true ? 'runtime_state_not_initialized_active_source'
                : 'runtime_state_not_initialized_source_activity_unknown';
    return {
        sourceComponentId: binding.sourceComponentId,
        nativeComponentType: component.constructor && component.constructor.name || 'sp.Skeleton',
        status: failures.length ? 'mismatch'
            : !hasStaticSourceData ? 'incomplete_dynamic_assignment'
            : !runtimeData ? 'incomplete_runtime_data'
                : !runtimeSkeletonInitialized && serializedRequestedIdentityVerified && sourceHierarchyActive === false
                    ? 'verified_source_inactive_runtime_uninitialized'
                    : !runtimeSkeletonInitialized && serializedRequestedIdentityVerified && sourceHierarchyActive === true
                        ? 'incomplete_active_source_runtime_pose_uninitialized'
                        : !runtimeSkeletonInitialized && serializedRequestedIdentityVerified
                            ? 'incomplete_source_activity_unknown_runtime_uninitialized'
                            : 'verified',
        staticDataBoundBySource: hasStaticSourceData,
        expectedTargetDataUuidAvailable: !!expectedData,
        runtimeDataAvailable: !!runtimeData,
        dynamicAssignmentUnverified: !hasStaticSourceData,
        observedDataWithoutStaticSourceReference: !hasStaticSourceData && !!actualDataUuid,
        requestedAnimation,
        requestedSkin,
        sourceActivity: sourceActivity || { status: 'source_activity_unavailable', nodeActive: null, hierarchyActive: null, chain: [] },
        // Keep persisted component identity distinct from an initialized
        // instance's runtime pose. Callers should use `instantiated_mapped`
        // only when the component came from the exact saved-prefab instance map.
        readbackScope,
        serializedIdentityStatus: serializedRequestedIdentityVerified ? 'verified' : 'incomplete_or_mismatch',
        instantiatedRuntimeStatus: runtimeSkeletonInitialized
            ? (failures.length ? 'initialized_mismatch' : 'initialized_verified')
            : 'not_initialized',
        nativeNodeActive,
        runtimeSkeletonInitialized,
        runtimePoseStatus,
        serializedRequestedIdentityVerified,
        actual,
        checks,
        failures,
        sourceCodeExecuted: false,
        staticVisiblePose: staticPose ? {
            policy: staticPose.policy,
            sourceTimeScale: staticPose.sourceTimeScale,
            nativeTimeScale: component.timeScale,
            nativeEnabled: component.enabled === true,
            sourceMaterialRoute: staticPose.sourceMaterialRoute,
        } : null,
    };
}

// Read-only data catalog helper for Creator's isolated SkeletonData resource
// probe. The primary importer can use this in its Spine resource readback to
// publish the complete native name lists without selecting an animation.
function readCreatorSpineDataCatalog(sourceId, skeletonData, expected) {
    if (!sourceId || !skeletonData) throw new Error('Source ID and loaded sp.SkeletonData are required');
    const runtimeData = typeof skeletonData.getRuntimeData === 'function'
        ? skeletonData.getRuntimeData(true)
        : null;
    if (!runtimeData) {
        return { sourceId, status: 'runtime_data_unavailable', uuid: skeletonData.uuid || null,
            animationNames: [], skinNames: [], diagnostics: ['getRuntimeData(true) returned no SkeletonData'] };
    }
    const animationNames = Array.isArray(runtimeData.animations)
        ? runtimeData.animations.map(row => row && row.name).filter(name => typeof name === 'string')
        : [];
    const skinNames = Array.isArray(runtimeData.skins)
        ? runtimeData.skins.map(row => row && row.name).filter(name => typeof name === 'string')
        : [];
    const diagnostics = [];
    if (expected && expected.nativeUuid && skeletonData.uuid !== expected.nativeUuid)
        diagnostics.push('SkeletonData UUID differs from expected native readback UUID');
    if (expected && expected.animationName && !animationNames.includes(expected.animationName))
        diagnostics.push('Requested animation name is absent from SkeletonData runtime data');
    if (expected && expected.skinName && !skinNames.includes(expected.skinName))
        diagnostics.push('Requested skin name is absent from SkeletonData runtime data');
    return {
        sourceId,
        status: diagnostics.length ? 'mismatch' : 'verified',
        uuid: skeletonData.uuid || null,
        animationNames,
        skinNames,
        boneCount: Array.isArray(runtimeData.bones) ? runtimeData.bones.length : null,
        slotCount: Array.isArray(runtimeData.slots) ? runtimeData.slots.length : null,
        sourceCodeExecuted: false,
        diagnostics,
    };
}

function readCreatorSpineBindings(bindings, resolveComponent, resolveReadContext) {
    if (!Array.isArray(bindings) || typeof resolveComponent !== 'function')
        throw new Error('Creator Spine readback requires bindings and an exact component resolver');
    return bindings.map(binding => readCreatorSpineBinding(binding, resolveComponent,
        typeof resolveReadContext === 'function' ? resolveReadContext(binding.sourceComponentId) : null));
}

module.exports = {
    applyCreatorSpineBinding,
    applyCreatorSpineBindings,
    readCreatorSpineBinding,
    readCreatorSpineBindings,
    sourceNodeActivity,
    readCreatorSpineDataCatalog,
};
