'use strict';

// Creator 2.4.15 Spine writes the node content size from SkeletonData during
// setSkeletonData. Creator 3.8.8 also writes both UITransform anchors from the
// SkeletonData offsets. The persistent CreatorSpineUITransformPreserver applies
// the exact authored values after Skeleton lifecycle callbacks on reopen and
// instantiation; restoreAuthored remains a construction-only helper.
const SOURCE_ENGINE_EVIDENCE = Object.freeze({
    engineVersion: '2.4.15',
    path: 'extensions/spine/Skeleton.js',
    url: 'https://raw.githubusercontent.com/cocos/cocos-engine/v2.4.15/extensions/spine/Skeleton.js',
    sha256: '7cdc119e26aa6dceec4bd78ae30dd08f39daa2f0da5d914d2197a730b558a5e8',
    mutation: 'skeletonData notify -> _updateSkeletonData -> setSkeletonData writes node.setContentSize(data.width,data.height); no anchor assignment',
});
const TARGET_ENGINE_EVIDENCE = Object.freeze({
    engineVersion: '3.8.8',
    path: 'cocos/spine/skeleton.ts',
    url: 'https://raw.githubusercontent.com/cocos/cocos-engine/v3.8.8/cocos/spine/skeleton.ts',
    sha256: '2e86383e7e7dfb93bc40ec1d7e44c6bb2bebc8a3e95c100ad16620bd24114329',
    mutation: 'skeletonData setter invokes _updateUITransform which writes contentSize and anchorX/anchorY from SkeletonData',
});
const PRESERVER_SCRIPT_UUID = 'ae82405a-3c6a-5cba-a281-e3c3a51973df';
const rawPreserverUuid=PRESERVER_SCRIPT_UUID.replace(/-/g,'');
const uuidAlphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
let PRESERVER_COMPILED_ID=rawPreserverUuid.slice(0,5);
for(let i=5;i<32;i+=3){const value=parseInt(rawPreserverUuid.slice(i,i+3),16);PRESERVER_COMPILED_ID+=uuidAlphabet[value>>6]+uuidAlphabet[value&63];}
function isPreserverType(type){return type===PRESERVER_SCRIPT_UUID||type===PRESERVER_COMPILED_ID;}

const PRESERVER_CLASS_NAME = 'MonkeySpineUITransformPreserver';
const STATIC_SORT_PROXY_MARKER_UUID = '9094b98e-f332-509c-a99d-7a0b8fc42364';
const STATIC_SORT_PROXY_PRESENTER_UUID = 'f4fa4dce-6293-52c2-b9bc-532f8551cb92';

function compiledScriptId(uuid) {
    const raw = uuid.replace(/-/g, '');
    let compiled = raw.slice(0, 5);
    for (let index = 5; index < 32; index += 3) {
        const value = parseInt(raw.slice(index, index + 3), 16);
        compiled += uuidAlphabet[value >> 6] + uuidAlphabet[value & 63];
    }
    return compiled;
}

function isPinnedScriptType(type, uuid) {
    return type === uuid || type === compiledScriptId(uuid);
}

function isSerializedGeneratedSortProxyRoot(child, parent, sourceId, records, allowedSourceIds) {
    if (!child || child.__type__ !== 'cc.Node' || !parent) return false;
    const deref = value => value && Number.isInteger(value.__id__) ? records[value.__id__] : null;
    const components = (child._components || []).map(deref).filter(Boolean);
    const markers = components.filter(row => isPinnedScriptType(row.__type__, STATIC_SORT_PROXY_MARKER_UUID));
    const presenters = components.filter(row => isPinnedScriptType(row.__type__, STATIC_SORT_PROXY_PRESENTER_UUID));
    if (markers.length !== 1 || presenters.length !== 1) return false;
    const marker = markers[0], presenter = presenters[0];
    const allowed = allowedSourceIds instanceof Set ? allowedSourceIds : new Set([sourceId]);
    return marker.kind === 'root' && allowed.has(marker.sourceNode) &&
        deref(marker.sourceRootOwner) === parent &&
        deref(presenter.sourceRoot) === parent && deref(presenter.proxyRoot) === child &&
        presenter.sourceRootId === marker.sourceNode;
}

function serializedProxyOriginMap(plan, prefabId, nodeOrigins) {
    const mapping = new Map(nodeOrigins);
    for (const link of plan.prefabInstances || []) {
        if (!link || link.owner !== prefabId) continue;
        if (!Array.isArray(link.nodes))
            throw new Error('SPINE_UI_TRANSFORM_PROXY_ORIGIN_INSTANCE_MAPPING_INVALID:' + prefabId);
        for (const pair of link.nodes) {
            if (!pair || typeof pair.instanceObject !== 'string' || !pair.instanceObject ||
                typeof pair.templateObject !== 'string' || !pair.templateObject)
                throw new Error('SPINE_UI_TRANSFORM_PROXY_ORIGIN_INSTANCE_EDGE_INVALID:' + prefabId);
            const previous = mapping.get(pair.instanceObject);
            if (previous && previous !== pair.templateObject)
                throw new Error('SPINE_UI_TRANSFORM_PROXY_ORIGIN_AMBIGUOUS:' + pair.instanceObject);
            mapping.set(pair.instanceObject, pair.templateObject);
        }
    }
    return mapping;
}

function pair(value, sourceId, field) {
    if (!Array.isArray(value) || value.length !== 2 ||
        value.some(channel => typeof channel !== 'number' || !Number.isFinite(channel))) {
        throw new Error('SPINE_UI_TRANSFORM_SOURCE_VALUE_INVALID:' + sourceId + ':' + field);
    }
    return [value[0], value[1]];
}

function originMap(plan, key) {
    const result = new Map();
    for (const group of plan.syncPrefabBindings || []) {
        if (!group || !Array.isArray(group[key]))
            throw new Error('SPINE_UI_TRANSFORM_ORIGIN_CHAIN_INVALID:' + key);
        const overrides = group.rootOverrides || {};
        if (!overrides || typeof overrides !== 'object' || Array.isArray(overrides))
            throw new Error('SPINE_UI_TRANSFORM_ROOT_OVERRIDES_INVALID');
        const geometryKeys = new Set(['size', 'anchor', 'contentSize', 'anchorPoint', 'width', 'height',
            'anchorX', 'anchorY', '_contentSize', '_anchorPoint']);
        const geometryPaths = ['contentSize', 'anchorPoint', 'anchorX', 'anchorY', 'width', 'height'];
        if (Object.entries(overrides).some(([name, path]) => geometryKeys.has(name) ||
            (typeof path === 'string' && geometryPaths.some(field => path.includes(field)))))
            throw new Error('SPINE_UI_TRANSFORM_ROOT_GEOMETRY_OVERRIDE_FORBIDDEN:' + group.root);
        for (const edge of group[key]) {
            if (!edge || typeof edge.instanceSourceId !== 'string' || !edge.instanceSourceId ||
                typeof edge.templateSourceId !== 'string' || !edge.templateSourceId)
                throw new Error('SPINE_UI_TRANSFORM_ORIGIN_EDGE_INVALID:' + key);
            const previous = result.get(edge.instanceSourceId);
            if (previous && previous !== edge.templateSourceId)
                throw new Error('SPINE_UI_TRANSFORM_ORIGIN_AMBIGUOUS:' + edge.instanceSourceId);
            result.set(edge.instanceSourceId, edge.templateSourceId);
        }
    }
    return result;
}

function canonicalId(sourceId, mapping, kind) {
    const chain = [sourceId];
    const seen = new Set(chain);
    let current = sourceId;
    while (mapping.has(current)) {
        current = mapping.get(current);
        if (seen.has(current)) throw new Error('SPINE_UI_TRANSFORM_ORIGIN_CYCLE:' + kind + ':' + sourceId);
        seen.add(current);
        chain.push(current);
    }
    return { sourceId: current, chain };
}

function sourceRows(plan) {
    if (!plan || !Array.isArray(plan.nodes) || !Array.isArray(plan.components))
        throw new Error('SPINE_UI_TRANSFORM_PLAN_INVALID');
    const nodes = new Map(plan.nodes.map(row => [row.sourceId, row]));
    if (nodes.size !== plan.nodes.length) throw new Error('SPINE_UI_TRANSFORM_NODE_IDENTITY_DUPLICATE');
    const components = new Map(plan.components.map(row => [row.sourceId, row]));
    if (components.size !== plan.components.length) throw new Error('SPINE_UI_TRANSFORM_COMPONENT_IDENTITY_DUPLICATE');
    const nodeOrigins = originMap(plan, 'origins');
    const componentOrigins = originMap(plan, 'componentOrigins');
    const ownersByNode = new Map();
    for (const prefab of plan.sourcePrefabs || []) {
        for (const nodeId of prefab.nodes || []) {
            let owners = ownersByNode.get(nodeId);
            if (!owners) ownersByNode.set(nodeId, owners = []);
            if (!owners.includes(prefab.sourceId)) owners.push(prefab.sourceId);
        }
    }
    const grouped = new Map();
    for (const component of plan.components) {
        if (!component || !(component.spineBinding || component.type === 'sp.Skeleton')) continue;
        if (!component.sourceId || !nodes.has(component.node))
            throw new Error('SPINE_UI_TRANSFORM_COMPONENT_NODE_MISSING:' + (component.sourceId || 'unknown'));
        const canonicalNode = canonicalId(component.node, nodeOrigins, 'node');
        const templateNode = nodes.get(canonicalNode.sourceId);
        if (!templateNode) throw new Error('SPINE_UI_TRANSFORM_TEMPLATE_NODE_MISSING:' + canonicalNode.sourceId);
        const logicalNode = nodes.get(component.node);
        const templateSize = pair(templateNode.size, canonicalNode.sourceId, 'size');
        const templateAnchor = pair(templateNode.anchor, canonicalNode.sourceId, 'anchor');
        if (!near(pair(logicalNode.size, component.node, 'size'), templateSize) ||
            !near(pair(logicalNode.anchor, component.node, 'anchor'), templateAnchor) ||
            (logicalNode.sourceUITransformEnabled !== false) !== (templateNode.sourceUITransformEnabled !== false))
            throw new Error('SPINE_UI_TRANSFORM_SYNC_GEOMETRY_OVERRIDE_FORBIDDEN:' + component.node);
        const canonicalComponent = canonicalId(component.sourceId, componentOrigins, 'component');
        const templateComponent = components.get(canonicalComponent.sourceId);
        if (!templateComponent || templateComponent.type !== 'sp.Skeleton' || templateComponent.node !== canonicalNode.sourceId)
            throw new Error('SPINE_UI_TRANSFORM_TEMPLATE_COMPONENT_MISMATCH:' + component.sourceId);
        let row = grouped.get(component.node);
        if (!row) {
            row = {
                sourceId: component.node,
                canonicalSourceId: canonicalNode.sourceId,
                originChain: canonicalNode.chain,
                size: templateSize,
                anchor: templateAnchor,
                enabled: logicalNode.sourceUITransformEnabled !== false,
                ownerSourcePrefabIds: ownersByNode.get(component.node) || [],
                componentSourceIds: [],
                canonicalComponentSourceIds: [],
            };
            grouped.set(component.node, row);
        }
        if (row.canonicalSourceId !== canonicalNode.sourceId)
            throw new Error('SPINE_UI_TRANSFORM_NODE_ORIGIN_AMBIGUOUS:' + component.node);
        row.componentSourceIds.push(component.sourceId);
        row.canonicalComponentSourceIds.push(canonicalComponent.sourceId);
    }
    return Array.from(grouped.values());
}

function preserverClass(cc) {
    if (!cc || !cc.js || typeof cc.js.getClassByName !== 'function')
        throw new Error('SPINE_UI_TRANSFORM_PRESERVER_CLASS_RESOLVER_REQUIRED');
    const ctor = cc.js.getClassByName(PRESERVER_CLASS_NAME);
    if (!ctor || !isPreserver(ctor, cc))
        throw new Error('SPINE_UI_TRANSFORM_PRESERVER_CLASS_IDENTITY_MISMATCH');
    return ctor;
}

function isPreserver(value, cc) {
    if (!value || !cc || !cc.js) return false;
    const ctor = typeof value === 'function' ? value : value.constructor;
    if (typeof ctor !== 'function') return false;
    const className = typeof cc.js.getClassName === 'function' ? cc.js.getClassName(ctor) : ctor.name;
    const resolved = typeof cc.js.getClassByName === 'function'
        ? cc.js.getClassByName(PRESERVER_CLASS_NAME) : null;
    const classIds = [];
    if (typeof cc.js.getClassId === 'function') classIds.push(cc.js.getClassId(ctor));
    classIds.push(ctor.__cid__);
    return className === PRESERVER_CLASS_NAME && resolved === ctor && classIds.some(isPreserverType);
}

function readNodeTransform(node, sourceId, cc) {
    const transform = node && cc && node.getComponent(cc.UITransform);
    if (!transform) throw new Error('SPINE_UI_TRANSFORM_NATIVE_COMPONENT_MISSING:' + sourceId);
    return {
        transform,
        size: [transform.width, transform.height],
        anchor: [transform.anchorX, transform.anchorY],
        enabled: transform.enabled !== false,
    };
}

function near(actual, expected) {
    return Array.isArray(actual) && actual.length === 2 && actual.every((value, index) =>
        typeof value === 'number' && Number.isFinite(value) && Math.abs(value - expected[index]) <= 0.001);
}

function selectPrefabRows(rows, sourcePrefabId) {
    if (!sourcePrefabId) return rows;
    return rows.filter(row => row.ownerSourcePrefabIds.includes(sourcePrefabId));
}

function nodePreservers(node, ctor) {
    if (node && typeof node.getComponents === 'function') return node.getComponents(ctor) || [];
    if (node && typeof node.getComponent === 'function') {
        const value = node.getComponent(ctor);
        return value ? [value] : [];
    }
    throw new Error('SPINE_UI_TRANSFORM_COMPONENT_LOOKUP_UNAVAILABLE');
}

function preserverMatches(component, transform, row) {
    return !!component && component.target === transform &&
        component.sourceNodeId === row.canonicalSourceId &&
        near([component.sourceWidth, component.sourceHeight], row.size) &&
        near([component.sourceAnchorX, component.sourceAnchorY], row.anchor) &&
        component.enabled !== false;
}

function attachPreservers(plan, nodes, cc, sourcePrefabId) {
    if (!nodes || typeof nodes.get !== 'function' || !cc || !cc.UITransform)
        throw new Error('SPINE_UI_TRANSFORM_RESOLVER_REQUIRED');
    const ctor = preserverClass(cc);
    const rows = selectPrefabRows(sourceRows(plan), sourcePrefabId);
    const attached = [];
    for (const row of rows) {
        const node = nodes.get(row.sourceId);
        if (!node) throw new Error('SPINE_UI_TRANSFORM_NODE_UNRESOLVED:' + row.sourceId);
        const transform = node.getComponent(cc.UITransform);
        if (!transform) throw new Error('SPINE_UI_TRANSFORM_NATIVE_COMPONENT_MISSING:' + row.sourceId);
        let components = nodePreservers(node, ctor);
        if (components.some(component => !isPreserver(component, cc)))
            throw new Error('SPINE_UI_TRANSFORM_PRESERVER_CLASS_IDENTITY_MISMATCH:' + row.sourceId);
        if (components.length > 1) throw new Error('SPINE_UI_TRANSFORM_PRESERVER_DUPLICATE:' + row.sourceId);
        let component = components[0];
        if (!component) {
            if (typeof node.addComponent !== 'function') throw new Error('SPINE_UI_TRANSFORM_ADD_COMPONENT_UNAVAILABLE');
            component = node.addComponent(ctor);
        }
        if (!isPreserver(component, cc) || typeof component.configure !== 'function')
            throw new Error('SPINE_UI_TRANSFORM_PRESERVER_CLASS_IDENTITY_MISMATCH:' + row.sourceId);
        component.configure(transform, row.canonicalSourceId, row.size, row.anchor);
        if (!preserverMatches(component, transform, row))
            throw new Error('SPINE_UI_TRANSFORM_PRESERVER_ASSIGNMENT_FAILED:' + row.sourceId);
        attached.push({
            sourceId: row.sourceId, canonicalSourceId: row.canonicalSourceId,
            originChain: row.originChain, componentSourceIds: row.componentSourceIds,
            size: row.size, anchor: row.anchor, verified: true,
        });
    }
    return { schema: 'creator-spine-ui-transform-preserver/1', status: 'attached', rows: attached };
}

function restoreAuthored(plan, nodes, cc, sourcePrefabId) {
    if (!nodes || typeof nodes.get !== 'function' || !cc || !cc.UITransform)
        throw new Error('SPINE_UI_TRANSFORM_RESOLVER_REQUIRED');
    const rows = selectPrefabRows(sourceRows(plan), sourcePrefabId);
    const restored = [];
    for (const row of rows) {
        const node = nodes.get(row.sourceId);
        if (!node) throw new Error('SPINE_UI_TRANSFORM_NODE_UNRESOLVED:' + row.sourceId);
        const before = readNodeTransform(node, row.sourceId, cc);
        if (before.enabled !== row.enabled) throw new Error('SPINE_UI_TRANSFORM_ENABLED_STATE_MISMATCH:' + row.sourceId);
        // Spine's target initializer can replace authored UITransform geometry.
        // This writes only the values present in the frozen target plan.
        before.transform.setContentSize(row.size[0], row.size[1]);
        before.transform.setAnchorPoint(row.anchor[0], row.anchor[1]);
        const after = readNodeTransform(node, row.sourceId, cc);
        const verified = near(after.size, row.size) && near(after.anchor, row.anchor) && after.enabled === row.enabled;
        restored.push({
            sourceId: row.sourceId, componentSourceIds: row.componentSourceIds,
            expectedSize: row.size, actualSize: after.size, expectedAnchor: row.anchor,
            actualAnchor: after.anchor, enabled: after.enabled,
            engineOverrideObserved: !near(before.size, row.size) || !near(before.anchor, row.anchor),
            verified,
        });
        if (!verified) throw new Error('SPINE_UI_TRANSFORM_RESTORE_FAILED:' + row.sourceId);
    }
    return {
        schema: 'creator-spine-ui-transform-readback/1', status: 'restored_authored_ui_transform',
        sourceEngine: SOURCE_ENGINE_EVIDENCE, targetEngine: TARGET_ENGINE_EVIDENCE,
        restoredNodeCount: restored.length, rows: restored, sourceCodeExecuted: false,
    };
}

function readAuthored(plan, nodes, cc, sourcePrefabId) {
    if (!nodes || typeof nodes.get !== 'function' || !cc || !cc.UITransform)
        throw new Error('SPINE_UI_TRANSFORM_RESOLVER_REQUIRED');
    const ctor = preserverClass(cc);
    const rows = selectPrefabRows(sourceRows(plan), sourcePrefabId).map(row => {
        const node = nodes.get(row.sourceId);
        if (!node) throw new Error('SPINE_UI_TRANSFORM_NODE_UNRESOLVED:' + row.sourceId);
        const actual = readNodeTransform(node, row.sourceId, cc);
        const preservers = nodePreservers(node, ctor);
        const identityVerified = preservers.length === 1 && isPreserver(preservers[0], cc) &&
            preserverMatches(preservers[0], actual.transform, row);
        return {
            sourceId: row.sourceId, canonicalSourceId: row.canonicalSourceId,
            originChain: row.originChain, componentSourceIds: row.componentSourceIds,
            expectedSize: row.size, actualSize: actual.size, expectedAnchor: row.anchor,
            actualAnchor: actual.anchor, enabled: actual.enabled,
            preserverIdentityVerified: identityVerified,
            verified: identityVerified && near(actual.size, row.size) && near(actual.anchor, row.anchor) && actual.enabled === row.enabled,
        };
    });
    return {
        schema: 'creator-spine-ui-transform-readback/1',
        status: rows.every(row => row.verified) ? 'verified' : 'mismatch',
        rows, sourceCodeExecuted: false,
    };
}

// Validate EditorExtends.serialize output before writing it. This guards the
// persisted native Prefab bytes, so a later in-memory restore cannot hide a bad
// serialized UITransform value.
function verifySerializedPrefab(plan, prefabSpec, serialized, context) {
    if (!plan || !Array.isArray(plan.nodes) || !prefabSpec ||
        typeof prefabSpec.sourceId !== 'string' || typeof prefabSpec.root !== 'string')
        throw new Error('SPINE_UI_TRANSFORM_SERIALIZED_PLAN_INVALID');
    const records = typeof serialized === 'string' ? JSON.parse(serialized) : serialized;
    if (!Array.isArray(records)) throw new Error('SPINE_UI_TRANSFORM_SERIALIZED_PREFAB_INVALID');
    const deref = value => value && Number.isInteger(value.__id__) ? records[value.__id__] : null;
    const prefabRecord = records.find(row => row && row.__type__ === 'cc.Prefab' && deref(row.data));
    const root = prefabRecord && deref(prefabRecord.data);
    if (!root || root.__type__ !== 'cc.Node') throw new Error('SPINE_UI_TRANSFORM_SERIALIZED_ROOT_MISSING');
    const sourceNodes = new Map(plan.nodes.map(row => [row.sourceId, row]));
    const rows = selectPrefabRows(sourceRows(plan), prefabSpec.sourceId);
    const nodeOrigins = originMap(plan, 'origins');
    const spineRows = new Map(rows.map(row => [row.sourceId, row]));
    const spineNodeIds = new Set(spineRows.keys());
    const instanceLinks = (plan.prefabInstances || []).filter(link => link &&
        link.owner === prefabSpec.sourceId && link.outermost === true);
    const proxyNodeOrigins = serializedProxyOriginMap(plan, prefabSpec.sourceId, nodeOrigins);
    const nativeNodes = new Map();
    const verified = [];
    const covered = new Set();
    function walk(sourceId, nativeNode) {
        const source = sourceNodes.get(sourceId);
        if (!source || !nativeNode || nativeNode.__type__ !== 'cc.Node')
            throw new Error('SPINE_UI_TRANSFORM_SERIALIZED_NODE_MISMATCH:' + sourceId);
        nativeNodes.set(sourceId, nativeNode);
        const proxySourceIdChain = canonicalId(sourceId, proxyNodeOrigins, 'serialized-sort-proxy-root').chain;
        const allowedProxySourceIds = new Set(proxySourceIdChain);

        // Native Prefab instances are an atomic serialized reference. Creator's
        // SDK may strip the inherited descendants and Components from this raw
        // owner file. Verify the exact saved template asset and origin mapping,
        // then leave final expanded-value verification to readAuthored after
        // normal instantiate/reopen lifecycle.
        const linksAtNode = instanceLinks.filter(link => link.root === sourceId);
        if (linksAtNode.length > 1) throw new Error('SPINE_UI_TRANSFORM_NATIVE_INSTANCE_ROOT_AMBIGUOUS:' + sourceId);
        const nativeLink = linksAtNode[0];
        if (nativeLink) {
            const linkedRows = rows.filter(row => Array.isArray(nativeLink.nodes) &&
                nativeLink.nodes.some(pair => pair && pair.instanceObject === row.sourceId &&
                    canonicalId(pair.templateObject, nodeOrigins, 'native-template-node').sourceId === row.canonicalSourceId));
            const proof = verifyNativeInstanceLink(plan, prefabSpec, nativeLink, linkedRows,
                nativeNode, records, context, nodeOrigins);
            for (const row of linkedRows) {
                if (covered.has(row.sourceId)) throw new Error('SPINE_UI_TRANSFORM_NATIVE_INSTANCE_DUPLICATE:' + row.sourceId);
                const templateRow = proof.templateReceipt.rows.find(item => item &&
                    (item.canonicalSourceId || item.sourceId) === row.canonicalSourceId);
                verified.push({
                    sourceId: row.sourceId, canonicalSourceId: row.canonicalSourceId,
                    originChain: row.originChain, expectedSize: row.size,
                    actualSize: templateRow.actualSize || templateRow.expectedSize,
                    expectedAnchor: row.anchor,
                    actualAnchor: templateRow.actualAnchor || templateRow.expectedAnchor,
                    enabled: templateRow.enabled, verified: true,
                    preserverSerialized: false, nativePrefabInherited: true,
                    nativePrefabTemplateUuid: proof.templateUuid,
                });
                covered.add(row.sourceId);
            }
            proofRows.push(proof.publicReceipt);
            return;
        }

        const children = (nativeNode._children || []).map(deref);
        const sourceChildren = children.filter(child =>
            !isSerializedGeneratedSortProxyRoot(child, nativeNode, sourceId, records, allowedProxySourceIds));
        if (sourceChildren.length !== (source.children || []).length)
            throw new Error('SPINE_UI_TRANSFORM_SERIALIZED_CHILD_COUNT_MISMATCH:' + sourceId + ':' +
                sourceChildren.length + '/' + (source.children || []).length);
        if (spineNodeIds.has(sourceId)) {
            const spineRow = spineRows.get(sourceId);
            const transforms = (nativeNode._components || []).map(deref)
                .filter(row => row && row.__type__ === 'cc.UITransform');
            if (transforms.length !== 1)
                throw new Error('SPINE_UI_TRANSFORM_SERIALIZED_COMPONENT_COUNT_MISMATCH:' + sourceId);
            const transform = transforms[0];
            const expectedSize = spineRow.size;
            const expectedAnchor = spineRow.anchor;
            const actualSize = transform._contentSize && [transform._contentSize.width, transform._contentSize.height];
            const actualAnchor = transform._anchorPoint && [transform._anchorPoint.x, transform._anchorPoint.y];
            const expectedEnabled = source.sourceUITransformEnabled !== false;
            const enabled = transform._enabled !== false;
            const matches = near(actualSize, expectedSize) && near(actualAnchor, expectedAnchor) && enabled === expectedEnabled;
            if (!matches) throw new Error('SPINE_UI_TRANSFORM_SERIALIZED_AUTHORED_VALUE_MISMATCH:' + sourceId);

            // Require the serialized lifecycle preserver on this node too.
            // Matching its exact source ID plus local UITransform reference
            // prevents a separate/editor-only restore receipt from passing.
            const allPreservers = (nativeNode._components || []).map(deref).filter(row => row &&
                isPreserverType(row.__type__) && typeof row.sourceNodeId === 'string' && row.target);
            const preservers = allPreservers.filter(row => row.sourceNodeId === spineRow.canonicalSourceId &&
                deref(row.target) === transform);
            if (preservers.length === 1) {
                const preserver = preservers[0];
                const preserverMatches = preserver._enabled !== false &&
                    Math.abs(preserver.sourceWidth - expectedSize[0]) <= 0.001 &&
                    Math.abs(preserver.sourceHeight - expectedSize[1]) <= 0.001 &&
                    Math.abs(preserver.sourceAnchorX - expectedAnchor[0]) <= 0.001 &&
                    Math.abs(preserver.sourceAnchorY - expectedAnchor[1]) <= 0.001;
                if (!preserverMatches) throw new Error('SPINE_UI_TRANSFORM_PRESERVER_SERIALIZED_VALUE_MISMATCH:' + sourceId);
            } else if (preservers.length > 1 || allPreservers.length) {
                throw new Error('SPINE_UI_TRANSFORM_PRESERVER_SERIALIZED_COMPONENT_MISMATCH:' + sourceId);
            } else if (spineRow.canonicalSourceId === sourceId) {
                throw new Error('SPINE_UI_TRANSFORM_PRESERVER_SERIALIZED_COMPONENT_MISMATCH:' + sourceId);
            }
            verified.push({
                sourceId, canonicalSourceId: spineRow.canonicalSourceId,
                originChain: spineRow.originChain, expectedSize, actualSize,
                expectedAnchor, actualAnchor, enabled, verified: matches,
                preserverSerialized: preservers.length === 1,
            });
            covered.add(sourceId);
        }
        for (let index = 0; index < (source.children || []).length; index++)
            walk(source.children[index], sourceChildren[index]);
    }
    const proofRows = [];
    walk(prefabSpec.root, root);
    if (verified.length !== spineNodeIds.size || covered.size !== spineNodeIds.size)
        throw new Error('SPINE_UI_TRANSFORM_SERIALIZED_DENOMINATOR_MISMATCH:' + prefabSpec.sourceId + ':' + verified.length + '/' + spineNodeIds.size);
    return {
        schema: 'creator-spine-ui-transform-serialized/1', status: 'verified',
        sourcePrefabId: prefabSpec.sourceId, spineNodeCount: verified.length, rows: verified,
        nativePrefabInstanceProofs: proofRows,
        sourceEngine: SOURCE_ENGINE_EVIDENCE, targetEngine: TARGET_ENGINE_EVIDENCE,
        preserverScriptUuid: PRESERVER_SCRIPT_UUID,
        sourceCodeExecuted: false,
    };
}

function serializedAssetUuid(value, records) {
    if (!value || typeof value !== 'object') return null;
    if (typeof value.__uuid__ === 'string' && value.__uuid__) return value.__uuid__;
    if (typeof value.uuid === 'string' && value.uuid) return value.uuid;
    if (Number.isInteger(value.__id__)) {
        const asset = records[value.__id__];
        if (asset && typeof asset._uuid === 'string' && asset._uuid) return asset._uuid;
        if (asset && typeof asset.__uuid__ === 'string' && asset.__uuid__) return asset.__uuid__;
    }
    return null;
}

function verifyNativeInstanceLink(plan, prefabSpec, link, inheritedRows, nativeRoot, records, context, nodeOrigins) {
    const saved = context && Array.isArray(context.saved) ? context.saved : [];
    const templates = context && Array.isArray(context.templates) ? context.templates : [];
    if (!saved.length || (inheritedRows.length && !templates.length) || !Array.isArray(link.nodes))
        throw new Error('SPINE_UI_TRANSFORM_NATIVE_INSTANCE_EVIDENCE_REQUIRED');
    const savedTemplate = saved.find(item => item && item.sourceId === link.template &&
        typeof item.uuid === 'string' && item.uuid && typeof item.sha256 === 'string' && item.sha256);
    if (!savedTemplate) throw new Error('SPINE_UI_TRANSFORM_NATIVE_TEMPLATE_SAVED_MISSING:' + link.template);
    const mappings = new Map(link.nodes.map(pair => [pair.instanceObject, pair.templateObject]));
    if (mappings.size !== link.nodes.length) throw new Error('SPINE_UI_TRANSFORM_NATIVE_INSTANCE_MAPPING_DUPLICATE:' + link.root);
    const prefabInfo = nativeRoot && nativeRoot._prefab &&
        (nativeRoot._prefab.__type__ === 'cc.PrefabInfo' ? nativeRoot._prefab :
            Number.isInteger(nativeRoot._prefab.__id__) ? records[nativeRoot._prefab.__id__] : null);
    const actualUuid = prefabInfo && prefabInfo.__type__ === 'cc.PrefabInfo'
        ? serializedAssetUuid(prefabInfo.asset, records) : null;
    if (!actualUuid || actualUuid !== savedTemplate.uuid)
        throw new Error('SPINE_UI_TRANSFORM_NATIVE_TEMPLATE_UUID_MISMATCH:' + link.template);
    if (!inheritedRows.length) {
        return {
            templateReceipt: null, templateUuid: actualUuid,
            publicReceipt: {
                owner: link.owner, root: link.root, template: link.template,
                templateUuid: actualUuid, inheritedSourceIds: [], mapping: [],
                evidence: 'raw-PrefabInfo.asset-uuid+saved-template+plan.prefabInstances.nodes',
                verified: true,
            },
        };
    }
    const template = templates.find(item => item && item.sourceId === link.template &&
        item.uuid === (savedTemplate && savedTemplate.uuid));
    const receipt = (template && (template.spineUITransformReceipt || template.receipt)) ||
        (savedTemplate && savedTemplate.spineUITransformReceipt);
    if (!savedTemplate || !template || !receipt || receipt.status !== 'verified' ||
        receipt.sourcePrefabId !== link.template || !Array.isArray(receipt.rows))
        throw new Error('SPINE_UI_TRANSFORM_NATIVE_TEMPLATE_RECEIPT_MISSING:' + link.template);
    for (const row of inheritedRows) {
        const immediateTemplateId = mappings.get(row.sourceId);
        if (!immediateTemplateId || canonicalId(immediateTemplateId, nodeOrigins, 'native-template-node').sourceId !== row.canonicalSourceId)
            throw new Error('SPINE_UI_TRANSFORM_NATIVE_INSTANCE_ORIGIN_MISMATCH:' + row.sourceId);
        const templateRow = receipt.rows.find(item => item &&
            (item.canonicalSourceId || item.sourceId) === row.canonicalSourceId && item.verified === true);
        if (!templateRow || !near(templateRow.expectedSize, row.size) ||
            !near(templateRow.expectedAnchor, row.anchor) || templateRow.enabled !== row.enabled)
            throw new Error('SPINE_UI_TRANSFORM_NATIVE_TEMPLATE_RECEIPT_MISMATCH:' + row.canonicalSourceId);
        const inheritedReceipt = templateRow.nativePrefabInherited === true &&
            Array.isArray(receipt.nativePrefabInstanceProofs) &&
            receipt.nativePrefabInstanceProofs.some(proof => proof && proof.verified === true &&
                Array.isArray(proof.inheritedSourceIds) && proof.inheritedSourceIds.includes(templateRow.sourceId));
        if (templateRow.preserverSerialized !== true && !inheritedReceipt)
            throw new Error('SPINE_UI_TRANSFORM_NATIVE_TEMPLATE_PRESERVER_UNPROVEN:' + row.canonicalSourceId);
    }
    return {
        templateReceipt: receipt, templateUuid: actualUuid,
        publicReceipt: {
            owner: link.owner, root: link.root, template: link.template,
            templateUuid: actualUuid, inheritedSourceIds: inheritedRows.map(row => row.sourceId),
            mapping: link.nodes.filter(pair => inheritedRows.some(row =>
                row.sourceId === pair.instanceObject && row.canonicalSourceId === pair.templateObject)),
            evidence: 'raw-PrefabInfo.asset-uuid+saved-template-readback-receipt+plan.prefabInstances.nodes',
            verified: true,
        },
    };
}

module.exports = { SOURCE_ENGINE_EVIDENCE, TARGET_ENGINE_EVIDENCE, PRESERVER_SCRIPT_UUID,
    STATIC_SORT_PROXY_MARKER_UUID, STATIC_SORT_PROXY_PRESENTER_UUID, compiledScriptId, isSerializedGeneratedSortProxyRoot,
    PRESERVER_CLASS_NAME, sourceRows, isPreserver, attachPreservers,
    restoreAuthored, readAuthored, verifySerializedPrefab };
