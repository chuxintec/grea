'use strict';
// Candidate-time cc.Animation binding. All native assets are imported before
// this adapter runs; actual AnimationClip/JsonAsset objects are serialized.
const cc = require('cc');
const bindings = require('./static-animation-bindings.js');

function assetObject(value) {
    if (value instanceof cc.Asset) return value;
    if (value && value.asset instanceof cc.Asset) return value.asset;
    return null;
}

function mapEntries(value) {
    if (value instanceof Map) return [...value.entries()];
    if (Array.isArray(value)) return value.map(row => [row.id || row.sourceClipId, row]);
    if (value && typeof value === 'object') return Object.entries(value);
    return [];
}

function byId(value) {
    return new Map(mapEntries(value));
}

function resolveComponentOrigin(componentId, componentOrigins) {
    const rows = (componentOrigins || []).filter(row => row && row.instanceSourceId === componentId);
    const ids = [...new Set(rows.map(row => row.templateSourceId).filter(Boolean))];
    if (ids.length > 1) throw new Error(`STATIC_ANIMATION_COMPONENT_ORIGIN_AMBIGUOUS:${componentId}`);
    return ids.length === 1 ? ids[0] : componentId;
}

function clipFor(sourceClipId, componentId, plan, animationAssets, componentOrigins) {
    const componentOrigin = resolveComponentOrigin(componentId, componentOrigins);
    const ids = [sourceClipId + '@' + componentId, sourceClipId + '@' + componentOrigin,
        sourceClipId + '@source-asset', sourceClipId];
    const map = byId(animationAssets);
    for (const id of ids) {
        if (!map.has(id)) continue;
        const value = map.get(id);
        const clip = assetObject(value);
        if (clip instanceof cc.AnimationClip) return { id, clip, value };
    }
    return null;
}

function evidenceFor(sourceClipId, sourceEvidenceAssets) {
    const value = byId(sourceEvidenceAssets).get(sourceClipId);
    const asset = assetObject(value);
    if (asset instanceof cc.JsonAsset) return { asset, value };
    return null;
}

function nodeEntries(nodes) {
    if (!(nodes instanceof Map)) throw new Error('STATIC_ANIMATION_NODE_MAP_REQUIRED');
    return [...nodes.entries()];
}

function childNodes(node) {
    if (Array.isArray(node && node.children)) return node.children;
    if (node && typeof node.getChildren === 'function') return node.getChildren();
    return [];
}

function resolveSourceNodeLineage(sourceNodeId, plan, componentId) {
    const relations = plan.syncPrefabBindings || [];
    const lineage = [], seen = new Set();
    let current = sourceNodeId;
    for (let depth = 0; depth < 64; depth++) {
        if (seen.has(current)) throw new Error(`STATIC_ANIMATION_OPACITY_NODE_ORIGIN_CYCLE:${componentId}:${current}`);
        seen.add(current);lineage.push(current);
        const parents = new Set();
        for (const relation of relations) for (const row of relation.origins || []) {
            if (row && row.instanceSourceId === current && typeof row.templateSourceId === 'string') parents.add(row.templateSourceId);
        }
        if (parents.size > 1) throw new Error(`STATIC_ANIMATION_OPACITY_NODE_ORIGIN_AMBIGUOUS:${componentId}:${current}`);
        if (parents.size === 0) return lineage;
        current = [...parents][0];
    }
    throw new Error(`STATIC_ANIMATION_OPACITY_NODE_ORIGIN_DEPTH_EXCEEDED:${componentId}:${sourceNodeId}`);
}

function resolveAnimationPath(owner, path, nodes, plan, track, componentId) {
    if (typeof path !== 'string') throw new Error(`STATIC_ANIMATION_OPACITY_PATH_MISSING:${componentId}`);
    const segments = path === '' ? [] : path.split('/');
    if (segments.some(segment => !segment || segment === '.' || segment === '..'))
        throw new Error(`STATIC_ANIMATION_OPACITY_PATH_INVALID:${componentId}:${path}`);
    let current = [owner];
    for (const segment of segments) {
        const next = [];
        for (const parent of current) {
            const matches = childNodes(parent).filter(child => child && child.name === segment);
            if (matches.length > 1) throw new Error(`STATIC_ANIMATION_OPACITY_PATH_AMBIGUOUS:${componentId}:${path}:${segment}`);
            if (matches.length === 1) next.push(matches[0]);
        }
        if (next.length !== 1) throw new Error(`STATIC_ANIMATION_OPACITY_PATH_UNRESOLVED:${componentId}:${path}:${segment}`);
        current = next;
    }
    if (current.length !== 1) throw new Error(`STATIC_ANIMATION_OPACITY_PATH_AMBIGUOUS:${componentId}:${path}`);
    const target = current[0];
    const mapped = nodeEntries(nodes).filter(([, node]) => node === target);
    if (mapped.length !== 1) throw new Error(`STATIC_ANIMATION_OPACITY_NODE_MAPPING_NOT_UNIQUE:${componentId}:${path}`);
    const sourceNodeId = mapped[0][0];
    const sourceNode = (plan.nodes || []).filter(row => row && row.sourceId === sourceNodeId);
    if (sourceNode.length !== 1 || sourceNode[0].sourceId !== sourceNodeId)
        throw new Error(`STATIC_ANIMATION_OPACITY_SOURCE_NODE_MISSING:${sourceNodeId}`);
    if (track.node) {
        const targetLineage = resolveSourceNodeLineage(sourceNodeId, plan, componentId);
        const trackLineage = resolveSourceNodeLineage(track.node, plan, componentId);
        // Accept only direct identity or an ancestor/descendant relationship in
        // the exact instance->template chain. Two sibling clones of one template
        // share a terminal ID but are not interchangeable source nodes.
        const equivalent = targetLineage.includes(track.node) || trackLineage.includes(sourceNodeId);
        if (!equivalent) throw new Error(`STATIC_ANIMATION_OPACITY_TRACK_NODE_MISMATCH:${componentId}:${track.node}:${sourceNodeId}`);
    }
    const opacity = sourceNode[0].opacity;
    if (typeof opacity !== 'number' || !Number.isFinite(opacity))
        throw new Error(`STATIC_ANIMATION_OPACITY_SOURCE_VALUE_MISSING:${sourceNodeId}`);
    return { sourceNodeId, node: target, sourceNode: sourceNode[0], opacity, path };
}

function boundOpacityTargets(component, owner, plan, animationAssets, componentOrigins, nodes) {
    const targets = new Map();
    for (const sourceClipId of component.clips || []) {
        const native = clipFor(sourceClipId, component.sourceId, plan, animationAssets, componentOrigins);
        if (!native) continue; // Evidence-only slots are not bound to cc.Animation.
        const specs = (plan.animations || []).filter(row => row && row.id === native.id);
        if (specs.length !== 1) throw new Error(`STATIC_ANIMATION_OPACITY_CLIP_SPEC_NOT_UNIQUE:${native.id}`);
        for (const track of specs[0].tracks || []) {
            if (track.property !== 'opacity' && track.nativeProperty !== 'opacity') continue;
            const resolved = resolveAnimationPath(owner, track.path || track.nodePath, nodes, plan, track, component.sourceId);
            const previous = targets.get(resolved.sourceNodeId);
            if (previous && previous.opacity !== resolved.opacity)
                throw new Error(`STATIC_ANIMATION_OPACITY_SOURCE_VALUE_CONFLICT:${resolved.sourceNodeId}`);
            targets.set(resolved.sourceNodeId, resolved);
        }
    }
    return [...targets.values()];
}

function ensureBoundOpacityComponents(component, owner, plan, animationAssets, componentOrigins, nodes) {
    const targets = boundOpacityTargets(component, owner, plan, animationAssets, componentOrigins, nodes);
    for (const row of targets) {
        let opacity = row.node.getComponent(cc.UIOpacity);
        if (!opacity) opacity = row.node.addComponent(cc.UIOpacity);
        if (!opacity) throw new Error(`STATIC_ANIMATION_OPACITY_COMPONENT_CREATE_FAILED:${row.sourceNodeId}`);
        // AnimationClip state construction can query the target component even while
        // cc.Animation.enabled is false. Seed it from the exact source NodeSpec value.
        opacity.opacity = row.opacity;
    }
    return targets;
}

function verifyBoundOpacityComponents(component, owner, plan, animationAssets, componentOrigins, nodes) {
    const targets = boundOpacityTargets(component, owner, plan, animationAssets, componentOrigins, nodes);
    for (const row of targets) {
        const opacity = row.node.getComponent(cc.UIOpacity);
        if (!opacity || opacity.opacity !== row.opacity)
            throw new Error(`STATIC_ANIMATION_OPACITY_SAVED_COMPONENT_OR_VALUE_DIFFERS:${row.sourceNodeId}`);
    }
    return targets;
}

function buildSpec(component, node, plan, animationAssets, sourceEvidenceAssets, componentOrigins) {
    const sourceOrder = component.clips || [];
    const clips = sourceOrder.map((sourceClipId, order) => {
        const native = clipFor(sourceClipId, component.sourceId, plan, animationAssets, componentOrigins);
        const evidence = evidenceFor(sourceClipId, sourceEvidenceAssets);
        if (!native && !evidence) throw new Error(`STATIC_ANIMATION_SLOT_HAS_NO_REAL_ASSET_REFERENCE:${sourceClipId}`);
        const planId = native ? native.id : sourceClipId + '@' + resolveComponentOrigin(component.sourceId, componentOrigins);
        const assetInfo = native && native.value || {};
        const sourceInfo = evidence && evidence.value || {};
        if (native && (!assetInfo.path || !(assetInfo.uuid || assetInfo.guid) || !(assetInfo.sha256 || assetInfo.assetSha256)))
            throw new Error(`STATIC_ANIMATION_NATIVE_ASSET_IDENTITY_INCOMPLETE:${sourceClipId}`);
        if (evidence && (!sourceInfo.path || !(sourceInfo.uuid || sourceInfo.guid)
            || !(sourceInfo.sha256 || sourceInfo.assetSha256)))
            throw new Error(`STATIC_ANIMATION_SOURCE_EVIDENCE_IDENTITY_INCOMPLETE:${sourceClipId}`);
        return {
            order,
            sourceClipId,
            planAnimationId: planId,
            status: native ? 'native_clip_reference_resolved' : 'source_evidence_retained',
            curveStatus: native ? (assetInfo.partial ? 'partial_curves' : 'converted_curves') : 'source_curves_not_lowered',
            partial: !native || assetInfo.partial === true,
            nativeClipPath: assetInfo.path || null,
            nativeClipGuid: assetInfo.uuid || assetInfo.guid || null,
            assetSha256: assetInfo.sha256 || assetInfo.assetSha256 || null,
            sourceEvidencePath: evidence ? sourceInfo.path : null,
            sourceEvidenceGuid: evidence ? sourceInfo.uuid || sourceInfo.guid : null,
            sourceEvidenceSha256: evidence ? sourceInfo.sha256 || sourceInfo.assetSha256 : null,
            nativeClip: native && native.clip,
            sourceEvidence: evidence && evidence.asset,
            gaps: assetInfo.gaps || [],
        };
    });
    const defaultClipId = component.defaultClip || null;
    return {
        schema: 'monkey-static-animation-bindings/1',
        sourceComponentId: component.sourceId,
        targetComponentId: component.sourceId,
        sourceNodeId: component.node,
        targetNodeId: component.node,
        sourceEnabled: component.enabled === true,
        sourceEnabledKnown: typeof component.enabled === 'boolean',
        sourcePlayOnLoad: component.playOnLoad === true,
        sourcePlayOnLoadKnown: typeof component.playOnLoad === 'boolean',
        sourceDefaultClipId: defaultClipId,
        sourceDefaultClipKnown: Object.prototype.hasOwnProperty.call(component, 'defaultClip'),
        hasSourceDefaultClip: !!defaultClipId,
        sourceClipOrder: [...sourceOrder],
        clips,
        nativePlaybackEnabled: false,
        nativeAnimatorEnabled: false,
        curveCompleteness: clips.every(row => !row.partial) ? 'complete' : 'partial',
        status: clips.every(row => row.nativeClip || row.sourceEvidence) ? 'resolved' : 'partial',
    };
}

function componentType(bindingTypes) {
    const BindingType = bindingTypes && bindingTypes.BindingType
        || cc.js.getClassByName('MonkeyNativeStaticAnimationBinding');
    const ClipSlotType = bindingTypes && bindingTypes.ClipSlotType
        || cc.js.getClassByName('MonkeyStaticAnimationClipSlot');
    if (!BindingType || !ClipSlotType) throw new Error('STATIC_ANIMATION_PERSISTED_TYPES_UNAVAILABLE');
    return { BindingType, ClipSlotType };
}

function bind(plan, nodes, animationAssets, sourceEvidenceAssets, componentOrigins, bindingTypes) {
    const types = componentType(bindingTypes);
    const animationMap = byId(animationAssets);
    const evidenceMap = byId(sourceEvidenceAssets);
    const readbacks = [];
    for (const component of (plan.components || []).filter(row => row && row.type === 'cc.Animation')) {
        const node = nodes.get(component.node);
        if (!node) throw new Error(`STATIC_ANIMATION_NODE_MISSING:${component.node}`);
        ensureBoundOpacityComponents(component, node, plan, animationMap, componentOrigins, nodes);
        const spec = buildSpec(component, node, plan, animationMap, evidenceMap, componentOrigins);
        const resolveClip = (path, uuid, sha) => {
            const found = [...animationMap.values()].map(value => ({ value, asset: assetObject(value) }))
                .find(row => row.asset instanceof cc.AnimationClip && row.value.path === path
                    && (row.value.uuid || row.value.guid) === uuid
                    && (!sha || (row.value.sha256 || row.value.assetSha256) === sha));
            return found ? found.asset : null;
        };
        const resolveSourceEvidence = (path, uuid, sha) => {
            const found = [...evidenceMap.values()].map(value => ({ value, asset: assetObject(value) }))
                .find(row => row.asset instanceof cc.JsonAsset && row.value.path === path
                    && (row.value.uuid || row.value.guid) === uuid
                    && (!sha || (row.value.sha256 || row.value.assetSha256) === sha));
            return found ? found.asset : null;
        };
        const readback = bindings.attach(node, spec, resolveClip, resolveSourceEvidence, types);
        if (readback.status === 'mismatch') throw new Error(`STATIC_ANIMATION_ATTACH_READBACK_FAILED:${component.sourceId}:${JSON.stringify(readback.diagnostics)}`);
        readbacks.push({ sourceComponentId: component.sourceId, targetComponentId: component.sourceId, targetNodeId: component.node,
            staticReferenceStatus: readback.status, curveCompleteness: spec.curveCompleteness,
            playbackExecuted: false, binding: readback });
    }
    return readbacks;
}

function readSaved(plan, nodes, animationAssets, sourceEvidenceAssets, componentOrigins, bindingTypes) {
    const types = componentType(bindingTypes);
    const animationMap = byId(animationAssets), evidenceMap = byId(sourceEvidenceAssets);
    const readbacks = [];
    for (const component of (plan.components || []).filter(row => row && row.type === 'cc.Animation')) {
        const node = nodes.get(component.node);
        if (!node) throw new Error(`STATIC_ANIMATION_SAVED_NODE_MISSING:${component.node}`);
        verifyBoundOpacityComponents(component, node, plan, animationMap, componentOrigins, nodes);
        const spec = buildSpec(component, node, plan, animationMap, evidenceMap, componentOrigins);
        const resolveClip = (path, uuid, sha) => [...animationMap.values()].map(value => ({ value, asset: assetObject(value) }))
            .find(row => row.asset instanceof cc.AnimationClip && row.value.path === path
                && (row.value.uuid || row.value.guid) === uuid
                && (!sha || (row.value.sha256 || row.value.assetSha256) === sha))?.asset || null;
        const resolveSourceEvidence = (path, uuid, sha) => [...evidenceMap.values()].map(value => ({ value, asset: assetObject(value) }))
            .find(row => row.asset instanceof cc.JsonAsset && row.value.path === path
                && (row.value.uuid || row.value.guid) === uuid
                && (!sha || (row.value.sha256 || row.value.assetSha256) === sha))?.asset || null;
        const readback = bindings.read(node, spec, resolveClip, resolveSourceEvidence, types);
        if (readback.status === 'mismatch') throw new Error(`STATIC_ANIMATION_SAVED_READBACK_FAILED:${component.sourceId}:${JSON.stringify(readback.diagnostics)}`);
        readbacks.push({ sourceComponentId: component.sourceId, targetComponentId: component.sourceId, targetNodeId: component.node,
            staticReferenceStatus: readback.status, curveCompleteness: spec.curveCompleteness,
            playbackExecuted: readback.playbackExecuted, binding: readback });
    }
    return readbacks;
}

function readFieldReferences(plan, sourceClipAssets, savedStaticFields = []) {
    const map = byId(sourceClipAssets), references = [];
    const savedByComponent = new Map((savedStaticFields || []).filter(row => row && row.binding)
        .map(row => [row.binding.sourceId, row.binding]));
    for (const component of plan.components || []) {
        const fields = component.staticFieldBinding && component.staticFieldBinding.fields || [];
        for (const field of fields.filter(row => row && row.sourceDeclaredType === 'cc.AnimationClip' && !row.nullExpected)) {
            const ids = [];
            if (field.refValue) ids.push(field.refValue);
            for (const id of field.refValues || []) if (id) ids.push(id);
            for (const sourceClipId of ids) {
                const value = map.get(sourceClipId);
                const asset = assetObject(value);
                const isClip = asset instanceof cc.AnimationClip;
                const savedBinding = savedByComponent.get(component.sourceId);
                const savedField = savedBinding && (savedBinding.fields || []).find(row => row.sourceFieldName === field.sourceFieldName);
                let actualUuid = null;
                let actualReferenceVerified = false;
                if (savedField && savedField.referenceEvidence && !Array.isArray(savedField.referenceEvidence)) {
                    actualUuid = savedField.referenceEvidence.actual && savedField.referenceEvidence.actual.nativeUuid;
                    actualReferenceVerified = savedField.referenceVerified === true
                        && savedField.referenceEvidence.sourceId === sourceClipId;
                } else if (savedField && Array.isArray(savedField.referenceEvidence)) {
                    const evidence = savedField.referenceEvidence.find(row => row && row.sourceId === sourceClipId);
                    actualUuid = evidence && evidence.actual && evidence.actual.nativeUuid;
                    actualReferenceVerified = savedField.referencesVerified === true && !!evidence && evidence.verified === true;
                }
                references.push({ sourceComponentId: component.sourceId, fieldName: field.sourceFieldName,
                    sourceClipId, uuid: isClip ? asset._uuid : null, actualUuid,
                    objectType: isClip ? 'AnimationClip' : null,
                    persistent: isClip && cc.isValid(asset, true),
                    status: isClip && cc.isValid(asset, true) && actualReferenceVerified && actualUuid === asset._uuid
                        ? 'resolved_native_animation_clip' : 'unresolved_native_animation_clip' });
            }
        }
    }
    return references;
}

module.exports = { bind, readSaved, readFieldReferences, buildSpec, boundOpacityTargets };
