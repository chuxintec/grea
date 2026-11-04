'use strict';
// Source-order marker and disabled cc.Animation binding for static native previews.
// The adapter never calls play(), sample(), or updates animation time.
const cc = require('cc');

const NativeStaticAnimationBinding = cc.js.getClassByName('MonkeyNativeStaticAnimationBinding') || cc.Class({
    name: 'MonkeyNativeStaticAnimationBinding',
    extends: cc.Component,
    properties: {
        sourceComponentId: { default: '' },
        sourceNodeId: { default: '' },
        sourceEnabled: { default: false },
        sourceEnabledKnown: { default: false },
        sourcePlayOnLoad: { default: false },
        sourcePlayOnLoadKnown: { default: false },
        sourceDefaultClipId: { default: '' },
        sourceDefaultClipKnown: { default: false },
        hasSourceDefaultClip: { default: false },
        sourceClipOrderJson: { default: '[]' },
        clipBindingsJson: { default: '[]' },
        nativeClips: { default: [], type: [cc.AnimationClip] },
        nativeDefaultClip: { default: null, type: cc.AnimationClip },
        sourceEvidenceAssets: { default: [], type: [cc.JsonAsset] },
        sourceEvidenceBindingsJson: { default: '[]' },
    },
});

function attach(node, spec, resolveClip, resolveSourceEvidence, types = {}) {
    if (!node || !spec || spec.schema !== 'monkey-static-animation-bindings/1'
        || typeof resolveClip !== 'function') throw new Error('STATIC_ANIMATION_BINDING_INPUT_INVALID');
    let animation = node.getComponent(cc.Animation);
    if (!animation) animation = node.addComponent(cc.Animation);
    const BindingType = types.BindingType || NativeStaticAnimationBinding;
    const ClipSlotType = types.ClipSlotType || null;
    let marker = node.getComponent(BindingType);
    if (!marker) marker = node.addComponent(BindingType);

    const rows = [...(spec.clips || [])].sort((a, b) => a.order - b.order);
    const resolved = rows.map(row => ({
        row,
        clip: row.status === 'native_clip_reference_resolved'
            ? resolveClip(row.nativeClipPath, row.nativeClipGuid, row.assetSha256) : null,
        evidence: row.sourceEvidencePath && typeof resolveSourceEvidence === 'function'
            ? resolveSourceEvidence(row.sourceEvidencePath, row.sourceEvidenceGuid, row.sourceEvidenceSha256) : null,
    }));
    for (const pair of resolved) {
        if (pair.row.status === 'native_clip_reference_resolved' && !pair.clip)
            throw new Error(`STATIC_ANIMATION_CLIP_REFERENCE_MISSING:${pair.row.sourceClipId}`);
        if (!pair.clip && !pair.evidence)
            throw new Error(`STATIC_ANIMATION_SLOT_HAS_NO_REAL_ASSET_REFERENCE:${pair.row.sourceClipId}`);
    }
    const sourceDefault = spec.hasSourceDefaultClip
        ? resolved.find(pair => pair.row.sourceClipId === spec.sourceDefaultClipId) : null;
    const defaultClip = sourceDefault && sourceDefault.clip ? sourceDefault.clip : null;

    // Preserve exact original ordering/status in a serializable marker, including
    // unavailable source clips. Standard cc.Animation receives the resolved assets
    // in that same relative order and remains disabled.
    animation.clips = resolved.filter(pair => pair.clip).map(pair => pair.clip);
    animation.defaultClip = defaultClip;
    animation.playOnLoad = !!spec.sourcePlayOnLoad;
    animation.enabled = false;
    marker.sourceComponentId = spec.sourceComponentId || '';
    marker.sourceNodeId = spec.sourceNodeId || '';
    marker.sourceEnabled = !!spec.sourceEnabled;
    marker.sourceEnabledKnown = !!spec.sourceEnabledKnown;
    marker.sourcePlayOnLoad = !!spec.sourcePlayOnLoad;
    marker.sourcePlayOnLoadKnown = !!spec.sourcePlayOnLoadKnown;
    marker.sourceDefaultClipId = spec.sourceDefaultClipId || '';
    marker.sourceDefaultClipKnown = !!spec.sourceDefaultClipKnown;
    marker.hasSourceDefaultClip = !!spec.hasSourceDefaultClip;
    const bindingRows = rows.map(row => ({
        order: row.order,
        sourceClipId: row.sourceClipId,
        planAnimationId: row.planAnimationId,
        path: row.nativeClipPath || null,
        guid: row.nativeClipGuid || null,
        assetSha256: row.assetSha256 || null,
        status: row.status,
    }));
    const typedMarker = !!(types.BindingType && ClipSlotType);
    if (typedMarker) {
        marker.sourceClipOrder = [...(spec.sourceClipOrder || [])];
        marker.sourceClips = resolved.map(pair => {
            const slot = new ClipSlotType();
            slot.order = pair.row.order;
            slot.sourceClipId = pair.row.sourceClipId || '';
            slot.planAnimationId = pair.row.planAnimationId || '';
            slot.status = pair.row.status || '';
            slot.curveStatus = pair.row.curveStatus || '';
            slot.partial = pair.row.partial !== false;
            slot.nativeClipPath = pair.row.nativeClipPath || '';
            slot.nativeClipGuid = pair.row.nativeClipGuid || '';
            slot.nativeClipSha256 = pair.row.assetSha256 || '';
            slot.sourceEvidencePath = pair.row.sourceEvidencePath || '';
            slot.sourceEvidenceGuid = pair.row.sourceEvidenceGuid || '';
            slot.sourceEvidenceSha256 = pair.row.sourceEvidenceSha256 || '';
            slot.gapCodes = (pair.row.gaps || []).map(gap => typeof gap === 'string' ? gap : gap.code || 'unknown');
            slot.nativeClip = pair.clip;
            slot.sourceEvidence = pair.evidence;
            return slot;
        });
    } else {
        marker.sourceClipOrderJson = JSON.stringify(spec.sourceClipOrder || []);
        marker.clipBindingsJson = JSON.stringify(bindingRows);
        marker.sourceEvidenceBindingsJson = JSON.stringify(rows.filter(row => row.sourceEvidencePath).map(row => ({
            order: row.order,
            sourceClipId: row.sourceClipId,
            path: row.sourceEvidencePath,
            guid: row.sourceEvidenceGuid,
            sha256: row.sourceEvidenceSha256,
            type: 'JsonAsset',
        })));
    }
    marker.nativeClips = resolved.filter(pair => pair.clip).map(pair => pair.clip);
    marker.nativeDefaultClip = defaultClip;
    marker.sourceEvidenceAssets = resolved.filter(pair => pair.evidence).map(pair => pair.evidence);
    marker.enabled = false;

    return read(node, spec, resolveClip, resolveSourceEvidence, types);
}

function assetReferenceEvidence(value, ExpectedType) {
    let typeMatches = false, persistent = false;
    try { typeMatches = !!(ExpectedType && value instanceof ExpectedType); } catch (_) {}
    if (typeMatches) {
        try { persistent = typeof cc.isValid === 'function' ? cc.isValid(value, true) : true; } catch (_) {}
    }
    let uuid = null;
    try { if (value && typeof value._uuid === 'string') uuid = value._uuid; } catch (_) {}
    return {typeMatches, persistent, uuid};
}

function read(node, spec, resolveClip, resolveSourceEvidence, types = {}) {
    if (!node || !spec) throw new Error('STATIC_ANIMATION_BINDING_INPUT_INVALID');
    const animation = node.getComponent(cc.Animation);
    const BindingType = types.BindingType || NativeStaticAnimationBinding;
    const marker = node.getComponent(BindingType);
    if (!animation || !marker) return { status: 'partial', diagnostics: ['native components missing'] };
    const typedMarker = !!(types.BindingType && types.ClipSlotType);
    const rows = typedMarker ? (marker.sourceClips || []).map(slot => ({
        order: slot.order,
        sourceClipId: slot.sourceClipId,
        planAnimationId: slot.planAnimationId,
        status: slot.status,
        curveStatus: slot.curveStatus,
        partial: slot.partial,
        nativeClipPath: slot.nativeClipPath,
        nativeClipGuid: slot.nativeClipGuid,
        nativeClipSha256: slot.nativeClipSha256,
        sourceEvidencePath: slot.sourceEvidencePath,
        sourceEvidenceGuid: slot.sourceEvidenceGuid,
        sourceEvidenceSha256: slot.sourceEvidenceSha256,
        gapCodes: slot.gapCodes || [],
    })) : JSON.parse(marker.clipBindingsJson || '[]');
    const clips = [...(animation.clips || [])];
    const expectedNative = rows.filter(row => row.status === 'native_clip_reference_resolved');
    const markerNativeClips = [...(marker.nativeClips || [])];
    const clipRefsMatch = expectedNative.length === clips.length && markerNativeClips.length === clips.length
        && clips.every((clip, index) => markerNativeClips[index] === clip);
    const fieldsMatch = marker.sourceComponentId === spec.sourceComponentId
        && marker.sourceNodeId === spec.sourceNodeId
        && marker.sourceEnabled === !!spec.sourceEnabled
        && marker.sourceEnabledKnown === !!spec.sourceEnabledKnown
        && marker.sourcePlayOnLoad === !!spec.sourcePlayOnLoad
        && marker.sourcePlayOnLoadKnown === !!spec.sourcePlayOnLoadKnown
        && marker.sourceDefaultClipId === (spec.sourceDefaultClipId || '')
        && marker.sourceDefaultClipKnown === !!spec.sourceDefaultClipKnown
        && marker.hasSourceDefaultClip === !!spec.hasSourceDefaultClip
        && (typedMarker
            ? JSON.stringify(marker.sourceClipOrder || []) === JSON.stringify(spec.sourceClipOrder || [])
            : marker.sourceClipOrderJson === JSON.stringify(spec.sourceClipOrder || []))
        && animation.enabled === false && marker.enabled === false
        && animation.defaultClip === marker.nativeDefaultClip;
    const evidenceRows = typedMarker ? [] : JSON.parse(marker.sourceEvidenceBindingsJson || '[]');
    const expectedEvidenceRows = (spec.clips || []).filter(row => row.sourceEvidencePath);
    const sourceEvidenceMatches = (typedMarker
        ? (marker.sourceClips || []).length === (spec.clips || []).length
            && (spec.clips || []).every((row, index) => {
                const slot = marker.sourceClips[index];
                const expectedClip = row.status === 'native_clip_reference_resolved'
                    ? resolveClip(row.nativeClipPath, row.nativeClipGuid, row.assetSha256) : null;
                const expectedEvidence = row.sourceEvidencePath && typeof resolveSourceEvidence === 'function'
                    ? resolveSourceEvidence(row.sourceEvidencePath, row.sourceEvidenceGuid, row.sourceEvidenceSha256) : null;
                return slot && slot.order === row.order && slot.sourceClipId === row.sourceClipId
                    && slot.planAnimationId === row.planAnimationId && slot.status === row.status
                    && slot.curveStatus === (row.curveStatus || '') && slot.partial === (row.partial !== false)
                    && slot.nativeClipPath === (row.nativeClipPath || '')
                    && slot.nativeClipGuid === (row.nativeClipGuid || '')
                    && slot.nativeClipSha256 === (row.assetSha256 || '')
                    && slot.sourceEvidencePath === (row.sourceEvidencePath || '')
                    && slot.sourceEvidenceGuid === (row.sourceEvidenceGuid || '')
                    && slot.sourceEvidenceSha256 === (row.sourceEvidenceSha256 || '')
                    && JSON.stringify(slot.gapCodes || []) === JSON.stringify((row.gaps || []).map(gap => typeof gap === 'string' ? gap : gap.code || 'unknown'))
                    && slot.nativeClip === expectedClip && slot.sourceEvidence === expectedEvidence;
            })
        : JSON.stringify(evidenceRows) === JSON.stringify(expectedEvidenceRows.map(row => ({
        order: row.order,
        sourceClipId: row.sourceClipId,
        path: row.sourceEvidencePath,
        guid: row.sourceEvidenceGuid,
        sha256: row.sourceEvidenceSha256,
        type: 'JsonAsset',
    }))) && marker.sourceEvidenceAssets.length === expectedEvidenceRows.length
        && expectedEvidenceRows.every((row, index) => typeof resolveSourceEvidence === 'function'
            && marker.sourceEvidenceAssets[index] === resolveSourceEvidence(row.sourceEvidencePath, row.sourceEvidenceGuid, row.sourceEvidenceSha256)));
    const nativeRefsMatch = clips.length === expectedNative.length && expectedNative.every((row, index) =>
        typeof resolveClip === 'function'
            && clips[index] === resolveClip(row.nativeClipPath, row.nativeClipGuid, row.assetSha256));
    const matches = fieldsMatch && clipRefsMatch && sourceEvidenceMatches && nativeRefsMatch;
    const clipReferenceEvidence = expectedNative.map((row, index) => {
        const specRow = (spec.clips || []).find(candidate => candidate.order === row.order
            && candidate.sourceClipId === row.sourceClipId) || row;
        const expected = typeof resolveClip === 'function'
            ? resolveClip(specRow.nativeClipPath, specRow.nativeClipGuid,
                specRow.assetSha256 || specRow.nativeClipSha256) : null;
        const animationClip = clips[index] || null;
        const markerClip = markerNativeClips[index] || null;
        return {order: row.order, sourceClipId: row.sourceClipId,
            expectedGuid: row.nativeClipGuid || null,
            expectedResolved: assetReferenceEvidence(expected, cc.AnimationClip),
            animationClip: assetReferenceEvidence(animationClip, cc.AnimationClip),
            markerNativeClip: assetReferenceEvidence(markerClip, cc.AnimationClip),
            animationIsResolvedObject: animationClip === expected,
            markerIsAnimationObject: markerClip === animationClip,
            animationUuidMatchesExpected: !!expected && animationClip && animationClip._uuid === expected._uuid,
            markerUuidMatchesExpected: !!expected && markerClip && markerClip._uuid === expected._uuid};
    });
    const sourceEvidenceEvidence = expectedEvidenceRows.map(row => {
        const expected = typeof resolveSourceEvidence === 'function'
            ? resolveSourceEvidence(row.sourceEvidencePath, row.sourceEvidenceGuid, row.sourceEvidenceSha256) : null;
        const markerAsset = typedMarker
            ? (marker.sourceClips || []).find(slot => slot.order === row.order)?.sourceEvidence
            : marker.sourceEvidenceAssets[expectedEvidenceRows.indexOf(row)];
        return {order: row.order, sourceClipId: row.sourceClipId,
            expectedGuid: row.sourceEvidenceGuid || null,
            expectedResolved: assetReferenceEvidence(expected, cc.JsonAsset),
            markerAsset: assetReferenceEvidence(markerAsset, cc.JsonAsset),
            sameObject: markerAsset === expected,
            uuidMatchesExpected: !!expected && markerAsset && markerAsset._uuid === expected._uuid};
    });
    const fieldChecks = {
        sourceComponentId: marker.sourceComponentId === spec.sourceComponentId,
        sourceNodeId: marker.sourceNodeId === spec.sourceNodeId,
        sourceEnabled: marker.sourceEnabled === !!spec.sourceEnabled,
        sourceEnabledKnown: marker.sourceEnabledKnown === !!spec.sourceEnabledKnown,
        sourcePlayOnLoad: marker.sourcePlayOnLoad === !!spec.sourcePlayOnLoad,
        sourcePlayOnLoadKnown: marker.sourcePlayOnLoadKnown === !!spec.sourcePlayOnLoadKnown,
        sourceDefaultClipId: marker.sourceDefaultClipId === (spec.sourceDefaultClipId || ''),
        sourceDefaultClipKnown: marker.sourceDefaultClipKnown === !!spec.sourceDefaultClipKnown,
        hasSourceDefaultClip: marker.hasSourceDefaultClip === !!spec.hasSourceDefaultClip,
        sourceClipOrder: typedMarker
            ? JSON.stringify(marker.sourceClipOrder || []) === JSON.stringify(spec.sourceClipOrder || [])
            : marker.sourceClipOrderJson === JSON.stringify(spec.sourceClipOrder || []),
        animationDisabled: animation.enabled === false,
        markerDisabled: marker.enabled === false,
        defaultClipMirrored: animation.defaultClip === marker.nativeDefaultClip,
        clipOrder: clips.length === expectedNative.length,
        nativeClipMarkerCount: markerNativeClips.length === expectedNative.length,
    };
    const comparison = matches ? null : {checks: {fieldsMatch, clipRefsMatch, sourceEvidenceMatches, nativeRefsMatch},
        fieldChecks, animationClipCount: clips.length, expectedNativeClipCount: expectedNative.length,
        markerNativeClipCount: markerNativeClips.length,
        clipReferences: clipReferenceEvidence, sourceEvidenceReferences: sourceEvidenceEvidence};
    return {
        status: matches ? (spec.status === 'resolved' ? 'reference_fields_verified' : 'partial') : 'mismatch',
        sourceComponentId: marker.sourceComponentId,
        sourceNodeId: marker.sourceNodeId,
        sourceEnabled: marker.sourceEnabled,
        sourcePlayOnLoad: marker.sourcePlayOnLoad,
        sourceDefaultClipId: marker.sourceDefaultClipId,
        sourceClipOrder: typedMarker ? [...(marker.sourceClipOrder || [])] : JSON.parse(marker.sourceClipOrderJson || '[]'),
        clipBindings: rows,
        nativeClipCount: clips.length,
        sourceEvidenceAssetCount: marker.sourceEvidenceAssets.length,
        sourceEvidenceBindings: evidenceRows,
        animationDisabled: !animation.enabled,
        markerDisabled: !marker.enabled,
        playbackExecuted: false,
        diagnostics: matches ? [] : [{code: 'STATIC_ANIMATION_REFERENCE_COMPARISON', comparison}],
    };
}

module.exports = { NativeStaticAnimationBinding, attach, read };
