'use strict';

const cc = require('cc');
function resolveSprite(plan, assets, uuid) {
    const ids=(plan.assets||[]).filter(a=>a.kind==='sprite'&&a.sourceId.endsWith(':'+uuid));
    if(ids.length!==1||!assets.has(ids[0].sourceId))throw Error('STATIC_MASK_FRAME_IDENTITY_AMBIGUOUS:'+uuid);
    const asset=assets.get(ids[0].sourceId);
    if(!(asset instanceof cc.SpriteFrame))throw Error('STATIC_MASK_FRAME_NATIVE_TYPE_DIFFERS:'+uuid);
    return asset;
}
function objectUuid(value) { return value && (value._uuid || value.uuid) || null; }
function vectorEvidence(value, keys) {
    if (!value || typeof value !== 'object') return null;
    const result = {};
    for (const key of keys) {
        const item = value[key];
        if (typeof item !== 'number' || !Number.isFinite(item)) return null;
        result[key] = item;
    }
    return result;
}
function numericArrayEvidence(value) {
    return Array.isArray(value) && value.every(item => typeof item === 'number' && Number.isFinite(item)) ? value.slice() : null;
}
function vectorArrayEvidence(value) {
    if (!Array.isArray(value)) return null;
    const rows = value.map(item => vectorEvidence(item, ['x', 'y', 'z']));
    return rows.every(Boolean) ? rows : null;
}
function spriteFrameEvidence(frame) {
    if (!(frame instanceof cc.SpriteFrame) || frame.constructor !== cc.SpriteFrame) return null;
    const texture = frame.texture || frame._texture || null;
    const rect = vectorEvidence(frame.rect, ['x', 'y', 'width', 'height']);
    const originalSize = vectorEvidence(frame.originalSize, ['width', 'height']);
    const offset = vectorEvidence(frame.offset, ['x', 'y']);
    const pivot = vectorEvidence(frame.pivot, ['x', 'y']);
    const vertices = frame.vertices;
    let vertexData = null;
    if (vertices === null) vertexData = null;
    else if (vertices && typeof vertices === 'object') {
        const rawPosition = vectorArrayEvidence(vertices.rawPosition);
        const positions = numericArrayEvidence(vertices.positions);
        const indexes = numericArrayEvidence(vertices.indexes);
        const uv = numericArrayEvidence(vertices.uv);
        const nuv = numericArrayEvidence(vertices.nuv);
        const minPos = vectorEvidence(vertices.minPos, ['x', 'y', 'z']);
        const maxPos = vectorEvidence(vertices.maxPos, ['x', 'y', 'z']);
        if ([rawPosition, positions, indexes, uv, nuv, minPos, maxPos].some(value => value === null)) return null;
        vertexData = {rawPosition, positions, indexes, uv, nuv, minPos, maxPos};
    } else return null;
    const textureEvidence = texture && objectUuid(texture) &&
        typeof texture.width === 'number' && Number.isFinite(texture.width) &&
        typeof texture.height === 'number' && Number.isFinite(texture.height) ? {
            type: texture.constructor && texture.constructor.name || null,
            uuid: objectUuid(texture), width: texture.width, height: texture.height,
        } : null;
    const insets = [frame.insetTop, frame.insetBottom, frame.insetLeft, frame.insetRight];
    const frameUuid = objectUuid(frame);
    if (!frameUuid || !textureEvidence || !rect || !originalSize || !offset || !pivot ||
        typeof frame.rotated !== 'boolean' || insets.some(value => typeof value !== 'number' || !Number.isFinite(value)) ||
        typeof frame.flipUVX !== 'boolean' || typeof frame.flipUVY !== 'boolean' ||
        typeof frame.packable !== 'boolean' || typeof frame.pixelsToUnit !== 'number' || !Number.isFinite(frame.pixelsToUnit) ||
        typeof frame._meshType !== 'number' || !Number.isFinite(frame._meshType)) return null;
    return {
        type: frame.constructor && frame.constructor.name || null, uuid: frameUuid, texture: textureEvidence,
        atlasUuid: typeof frame.atlasUuid === 'string' ? frame.atlasUuid : null,
        rect, originalSize, offset, rotated: frame.rotated, insets, flipUVX: frame.flipUVX, flipUVY: frame.flipUVY,
        packable: frame.packable, pixelsToUnit: frame.pixelsToUnit, pivot,
        meshType: frame._meshType, vertices: vertexData,
    };
}
function sameSpriteFrameResource(expected, actual) {
    const expectedEvidence = spriteFrameEvidence(expected);
    const actualEvidence = spriteFrameEvidence(actual);
    return {verified: !!expectedEvidence && !!actualEvidence &&
        JSON.stringify(expectedEvidence) === JSON.stringify(actualEvidence), expected: expectedEvidence, actual: actualEvidence};
}
function maskRendererEvidence(renderer) {
    if (!renderer) return null;
    const material = renderer.customMaterial || null, effect = material && material.effectAsset;
    let sharedMaterialUuids = null, material0Uuid = null, materialReadbackError = null;
    try { sharedMaterialUuids = Array.isArray(renderer.sharedMaterials) ? renderer.sharedMaterials.map(objectUuid) : null; }
    catch (error) { materialReadbackError = String(error && error.message || error); }
    try { material0Uuid = typeof renderer.getMaterial === 'function' ? objectUuid(renderer.getMaterial(0)) : null; }
    catch (error) { materialReadbackError = String(error && error.message || error); }
    return {type: renderer.constructor && renderer.constructor.name || null, componentUuid: renderer.uuid || null,
        customMaterialUuid: objectUuid(material), customEffectUuid: objectUuid(effect),
        sharedMaterialUuids, material0Uuid, materialReadbackError};
}

function createStaticMasks(specs, nodes, resolveSprite) {
    if (!Array.isArray(specs)) throw Error('STATIC_MASK_PLAN_INVALID');
    const rows = [];
    for (const spec of specs) {
        if (!spec || !spec.sourceFields || typeof spec.sourceFields !== 'object' || Array.isArray(spec.sourceFields))
            throw Error('STATIC_MASK_SOURCE_FIELDS_MISSING');
        const sourceFieldsJson = typeof spec.sourceFieldsJson === 'string' ? spec.sourceFieldsJson : JSON.stringify(spec.sourceFields);
        if (typeof sourceFieldsJson !== 'string') throw Error('STATIC_MASK_SOURCE_FIELDS_JSON_INVALID: ' + spec.sourceId);
        const node = nodes.get(spec.node);
        if (!node) throw Error('STATIC_MASK_NODE_MISSING: ' + spec.sourceId);
        let sprite = null;
        let spriteFrame = null;
        if (spec.maskType === 2) {
            spriteFrame = resolveSprite && resolveSprite(spec.spriteFrameUuid);
            if (!spriteFrame) throw Error('STATIC_MASK_SPRITE_FRAME_MISSING: ' + spec.sourceId);
            // A source image Mask owns a native Sprite backing even when the
            // source node has no standalone Sprite component. Create it before
            // assigning a frame so CUSTOM sizing applies to the first assignment.
            sprite = node.getComponent(cc.Sprite) || node.addComponent(cc.Sprite);
            if (!(sprite instanceof cc.Sprite)) throw Error('STATIC_MASK_NATIVE_SPRITE_MISSING: ' + spec.sourceId);
            if (!cc.Sprite.SizeMode || cc.Sprite.SizeMode.CUSTOM === undefined)
                throw Error('STATIC_MASK_SPRITE_CUSTOM_SIZE_MODE_UNAVAILABLE: ' + spec.sourceId);
            // Mask.type creates its renderer from the existing Sprite. Set the
            // persisted Sprite's size mode before assigning its frame so Creator
            // cannot resize source UITransform from the frame's trimmed rect.
            sprite.sizeMode = cc.Sprite.SizeMode.CUSTOM;
        }
        if (node.getComponent(cc.Mask)) throw Error('STATIC_MASK_ALREADY_EXISTS: ' + spec.sourceId);
        const mask = node.addComponent(cc.Mask);
        if (!(mask instanceof cc.Mask)) throw Error('STATIC_MASK_CREATE_FAILED: ' + spec.sourceId);
        const type = spec.maskType === 0 ? cc.Mask.Type.GRAPHICS_RECT :
            spec.maskType === 1 ? cc.Mask.Type.GRAPHICS_ELLIPSE :
            spec.maskType === 2 ? cc.Mask.Type.SPRITE_STENCIL : null;
        if (type === null) throw Error('STATIC_MASK_TYPE_UNSUPPORTED: ' + spec.sourceId);
        mask.type = type;
        // Creator creates its stencil renderer in Mask.onLoad/onEnable. A
        // newly-added component on an inactive prefab node has not reached
        // that lifecycle yet; initialize the same native backing explicitly
        // before setters such as inverted access subComp.
        if (!mask.subComp && typeof mask.onLoad === 'function') mask.onLoad();
        if (!mask.subComp) throw Error('STATIC_MASK_NATIVE_BACKING_MISSING: ' + spec.sourceId);
        if (spec.maskType === 2) {
            if (mask.subComp !== sprite) throw Error('STATIC_MASK_NATIVE_SPRITE_BACKING_MISMATCH: ' + spec.sourceId);
            sprite.spriteFrame = spriteFrame;
        }
        mask.inverted = spec.inverted;
        mask.alphaThreshold = spec.alphaThreshold;
        mask.enabled = spec.enabled;
        const IdentityType = cc.js && cc.js.getClassByName && cc.js.getClassByName('MonkeyStaticMaskIdentity');
        if (!IdentityType) throw Error('STATIC_MASK_IDENTITY_TYPE_MISSING: ' + spec.sourceId);
        const identity = node.addComponent(IdentityType);
        if (!(identity instanceof IdentityType)) throw Error('STATIC_MASK_IDENTITY_CREATE_FAILED: ' + spec.sourceId);
        identity.sourceId = spec.sourceId;
        identity.nativeId = spec.nativeId;
        identity.sourceMaskType = spec.maskType;
        identity.sourceInverted = spec.inverted;
        identity.sourceAlphaThreshold = spec.alphaThreshold;
        identity.sourceFieldsJson = sourceFieldsJson;
        identity.sourceSpriteFrameUuid = spec.spriteFrameUuid || '';
        identity.sourceSpriteFrame = spec.maskType === 2 ? mask.spriteFrame : null;
        identity.nativeMask = mask;
        identity.enabled = false;
        rows.push(readStaticMasks([spec], nodes, resolveSprite, {initialized: true})[0]);
    }
    return rows;
}

function readStaticMasks(specs, nodes, resolveSprite, options = {}) {
    const initialized = options === true || (options && options.initialized === true);
    return specs.map(spec => {
        const node = nodes.get(spec.node);
        const components = node && node.getComponents(cc.Mask);
        if (!components || components.length !== 1)
            throw Error('STATIC_MASK_NATIVE_COMPONENT_COUNT_MISMATCH: ' + spec.sourceId);
        const mask = components[0];
        const IdentityType = cc.js && cc.js.getClassByName && cc.js.getClassByName('MonkeyStaticMaskIdentity');
        const identities = node && IdentityType ? node.getComponents(IdentityType) : [];
        if (!IdentityType || !identities || identities.length !== 1)
            throw Error('STATIC_MASK_IDENTITY_COMPONENT_COUNT_MISMATCH: ' + spec.sourceId);
        const identity = identities[0];
        const expectedType = spec.maskType === 0 ? cc.Mask.Type.GRAPHICS_RECT :
            spec.maskType === 1 ? cc.Mask.Type.GRAPHICS_ELLIPSE : cc.Mask.Type.SPRITE_STENCIL;
        const expectedSpriteFrame = spec.maskType === 2 && resolveSprite ? resolveSprite(spec.spriteFrameUuid) : null;
        const sprite = spec.maskType === 2 ? node.getComponent(cc.Sprite) : null;
        const nativeSpriteFrame = sprite ? sprite.spriteFrame : null;
        const frameResource = spec.maskType === 2 ? sameSpriteFrameResource(expectedSpriteFrame, nativeSpriteFrame) : null;
        const identitySpriteFrameSameDomain = spec.maskType !== 2 || identity.sourceSpriteFrame === nativeSpriteFrame;
        const spriteOK = spec.maskType !== 2 || (sprite && expectedSpriteFrame && frameResource.verified && identitySpriteFrameSameDomain);
        const initializedBackingOK = !initialized || spec.maskType !== 2 || (mask.subComp === sprite && mask.spriteFrame === nativeSpriteFrame);
        const dependencyOK = spec.maskType === 2 ? !!node.getComponent(cc.Sprite) :
            !!node.getComponent(cc.Graphics) && !node.getComponent(cc.Sprite);
        const sourceFieldsJson = typeof spec.sourceFieldsJson === 'string' ? spec.sourceFieldsJson : JSON.stringify(spec.sourceFields);
        let sourceFields = null;
        try { sourceFields = JSON.parse(identity.sourceFieldsJson); } catch (_) { /* validation below fails closed */ }
        const expectedFrameUuid = objectUuid(expectedSpriteFrame);
        const nativeFrameUuid = objectUuid(nativeSpriteFrame);
        const backingRenderer = spec.maskType === 2 ? sprite : node.getComponent(cc.Graphics);
        const expectedSourceMaterials = spec.sourceFields && Array.isArray(spec.sourceFields._materials) ?
            spec.sourceFields._materials.map(value => value && typeof value === 'object' ? value.__uuid__ || null : value) : [];
        const checks = {
            nodeFound: !!node,
            maskComponentCount: components.length === 1,
            identityComponentCount: identities.length === 1,
            maskNodeIdentity: mask.node === node,
            maskUuidPresent: typeof mask.uuid === 'string' && mask.uuid.length > 0,
            nativeMaskType: mask.type === expectedType,
            enabled: mask.enabled === spec.enabled,
            inverted: mask.inverted === spec.inverted,
            alphaThreshold: mask.alphaThreshold === spec.alphaThreshold,
            spriteReferenceAndFrame: spriteOK,
            backingDependency: dependencyOK,
            initializedBacking: initializedBackingOK,
            identityDisabled: identity.enabled === false,
            identitySourceId: identity.sourceId === spec.sourceId,
            identityNativeId: identity.nativeId === spec.nativeId,
            identityNativeMaskReference: identity.nativeMask === mask,
            identityMaskType: identity.sourceMaskType === spec.maskType,
            identityInverted: identity.sourceInverted === spec.inverted,
            identityAlphaThreshold: identity.sourceAlphaThreshold === spec.alphaThreshold,
            identitySourceFieldsJson: identity.sourceFieldsJson === sourceFieldsJson,
            identitySourceSpriteFrameUuid: identity.sourceSpriteFrameUuid === (spec.spriteFrameUuid || ''),
            identitySpriteFrameReference: spec.maskType === 2 ? identitySpriteFrameSameDomain : identity.sourceSpriteFrame === null,
            spriteFrameResourceIdentity: spec.maskType === 2 ? !!frameResource.verified : true,
            sourceFieldsParsed: !!sourceFields,
        };
        const identityOK = identity.enabled === false && identity.sourceId === spec.sourceId &&
            identity.nativeMask === mask &&
            identity.nativeId === spec.nativeId && identity.sourceMaskType === spec.maskType &&
            identity.sourceInverted === spec.inverted && identity.sourceAlphaThreshold === spec.alphaThreshold &&
            identity.sourceFieldsJson === sourceFieldsJson && identity.sourceSpriteFrameUuid === (spec.spriteFrameUuid || '') &&
            (spec.maskType === 2 ? identitySpriteFrameSameDomain : identity.sourceSpriteFrame === null) &&
            initializedBackingOK;
        const verified = mask.node === node && mask.type === expectedType && mask.enabled === spec.enabled &&
            mask.inverted === spec.inverted && mask.alphaThreshold === spec.alphaThreshold && spriteOK && dependencyOK &&
            identityOK && !!sourceFields && typeof mask.uuid === 'string' && mask.uuid.length > 0;
        const nativeSpriteFrameUuid = spec.maskType === 2 && nativeSpriteFrame ?
            (nativeSpriteFrame._uuid || nativeSpriteFrame.uuid || null) : null;
        return {sourceId: spec.sourceId, node: spec.node, nativeType: mask.constructor.name,
            componentUuid: mask.uuid, enabled: mask.enabled, maskType: spec.maskType,
            nativeMaskType: mask.type, inverted: mask.inverted, alphaThreshold: mask.alphaThreshold,
            expected: {sourceId: spec.sourceId, nativeId: spec.nativeId, node: spec.node, nodeUuid: node.uuid || null,
                nativeType: spec.nativeType || 'cc.Mask', maskType: spec.maskType, expectedMaskType: expectedType,
                enabled: spec.enabled, inverted: spec.inverted, alphaThreshold: spec.alphaThreshold,
                sourceSpriteFrameUuid: spec.spriteFrameUuid || null, resolvedSpriteFrameUuid: expectedFrameUuid,
                sourceMaterials: expectedSourceMaterials, sourceFieldsJson},
            actual: {nodeUuid: node.uuid || null, componentUuid: mask.uuid || null, componentType: mask.constructor.name,
                maskNodeMatches: mask.node === node, maskType: mask.type, enabled: mask.enabled, inverted: mask.inverted,
                alphaThreshold: mask.alphaThreshold, maskSpriteFrameUuid: objectUuid(mask.spriteFrame),
                spriteComponentUuid: sprite && sprite.uuid || null, spriteFrameUuid: nativeFrameUuid,
                spriteFrameResourceEvidence: frameResource,
                identitySpriteFrameIsNodeFrame: spec.maskType === 2 ? identitySpriteFrameSameDomain : null,
                initializedMaskFrameIsNodeFrame: initialized && spec.maskType === 2 ? mask.spriteFrame === nativeSpriteFrame : null,
                backingCacheType: mask.subComp && mask.subComp.constructor && mask.subComp.constructor.name || null,
                backingRenderer: maskRendererEvidence(backingRenderer), sourceFieldsJson: identity.sourceFieldsJson,
                identity: {sourceId: identity.sourceId, nativeId: identity.nativeId, enabled: identity.enabled,
                    sourceMaskType: identity.sourceMaskType, sourceInverted: identity.sourceInverted,
                    sourceAlphaThreshold: identity.sourceAlphaThreshold, sourceSpriteFrameUuid: identity.sourceSpriteFrameUuid,
                    sourceSpriteFrameUuidActual: objectUuid(identity.sourceSpriteFrame),
                    nativeMaskUuid: objectUuid(identity.nativeMask)}},
            checks, failedChecks: Object.keys(checks).filter(key => !checks[key]),
            sourceSpriteFrameUuid: spec.maskType === 2 ? spec.spriteFrameUuid : null,
            nativeSpriteFrameUuid, maskSpriteFrameUuid: initialized && mask.spriteFrame ?
                (mask.spriteFrame._uuid || mask.spriteFrame.uuid || null) : null,
            initialized, initializedBackingVerified: initialized ? !!initializedBackingOK : null,
            sourceFieldsJson: identity.sourceFieldsJson,
            sourceFields, identitySourceId: identity.sourceId, identityNativeId: identity.nativeId,
            verified: !!verified};
    });
}

function createStaticSort(sortOrders, sortRoots, sortGroups, nodes) {
    if (!Array.isArray(sortOrders) || !Array.isArray(sortRoots) || !Array.isArray(sortGroups)) throw Error('STATIC_SORT_PLAN_INVALID');
    return readStaticSort(sortOrders, sortRoots, sortGroups, nodes);
}

function readStaticSort(sortOrders, sortRoots, sortGroups, nodes) {
    const groupByParent = new Map(sortGroups.map(group => [group.parent, group]));
    const nodeIdByNode = new Map(Array.from(nodes.entries(), ([id, node]) => [node, id]));
    const orders = sortOrders.map(spec => {
        const node = nodes.get(spec.node);
        const group = node && groupByParent.get(nodeIdByNode.get(node.parent));
        return {sourceId: spec.sourceId, node: spec.node, nativeType: null, sortOrder: spec.sortOrder,
            enabled: spec.enabled, siblingIndex: node && node.getSiblingIndex(),
            sourceGroupRepresentable: !!group && group.representableBySiblingOrder,
            sourceQueueMapped: false, diagnostic: 'STATIC_SORT_GLOBAL_QUEUE_ADAPTER_REQUIRED', verified: false};
    });
    const roots = sortRoots.map(spec => {
        const node = nodes.get(spec.node);
        return {sourceId: spec.sourceId, node: spec.node, nativeType: null, enabled: spec.enabled,
            childCount: node ? node.children.length : -1,
            sourceQueueMapped: false, diagnostic: 'STATIC_SORT_GLOBAL_QUEUE_ADAPTER_REQUIRED', verified: false};
    });
    return {sortOrders: orders, sortRoots: roots};
}

module.exports = {createStaticMasks, readStaticMasks, createStaticSort, readStaticSort,resolveSprite};
