'use strict';

const PREFIX = '[MONKEY_CREATOR_EDITOR_SERIALIZE_SCOPE]';
const MAX_DIAGNOSTICS = 128;
const PRESENTER_CLASS = 'MonkeyStaticSortQueueProxyPresenter';
const MARKER_CLASS = 'MonkeyStaticSortQueueProxyMarker';
let activeInstallation = null;
let activeRuntimeProbe = null;
let activeSerializationContext = null;

function validOwnedPresenter(cc, Presenter, Marker, presenter, proxyRoot) {
    if (!presenter || presenter.constructor !== Presenter || !proxyRoot || presenter.node !== proxyRoot || presenter.proxyRoot !== proxyRoot ||
        !presenter.sourceRoot || !(presenter.sourceRoot instanceof cc.Node) || proxyRoot.parent !== presenter.sourceRoot ||
        typeof presenter.sourceRootId !== 'string' || !presenter.sourceRootId ||
        typeof presenter.sourcePrefabId !== 'string' || !presenter.sourcePrefabId ||
        typeof presenter.prefabPath !== 'string' || !presenter.prefabPath ||
        !Number.isInteger(presenter.hiddenLayer))
        throw new Error('CREATOR_EDITOR_SERIALIZE_PRESENTER_IDENTITY_INVALID');
    const marker = proxyRoot.getComponent(Marker);
    if (!marker || marker.constructor !== Marker || marker.kind !== 'root' || marker.sourceNode !== presenter.sourceRootId ||
        marker.sourceRootOwner !== presenter.sourceRoot)
        throw new Error('CREATOR_EDITOR_SERIALIZE_MARKER_OWNER_INVALID:' + presenter.sourceRootId);
    const sourceNodes = presenter.sourceNodes, originalLayers = presenter.originalLayers;
    if (!Array.isArray(sourceNodes) || sourceNodes.length === 0 || !Array.isArray(originalLayers) ||
        sourceNodes.length !== originalLayers.length || new Set(sourceNodes).size !== sourceNodes.length)
        throw new Error('CREATOR_EDITOR_SERIALIZE_SOURCE_DENOMINATOR_INVALID:' + presenter.sourceRootId);
    for (let index = 0; index < sourceNodes.length; index++) {
        const node = sourceNodes[index];
        if (!(node instanceof cc.Node) || !node.isValid || !Number.isInteger(originalLayers[index]))
            throw new Error('CREATOR_EDITOR_SERIALIZE_SOURCE_NODE_INVALID:' + presenter.sourceRootId + ':' + index);
        let current = node, reachedRoot = false;
        while (current) {
            if (current === proxyRoot) throw new Error('CREATOR_EDITOR_SERIALIZE_SOURCE_NODE_IN_PROXY:' + presenter.sourceRootId + ':' + index);
            if (current === presenter.sourceRoot) { reachedRoot = true; break; }
            current = current.parent;
        }
        if (!reachedRoot) throw new Error('CREATOR_EDITOR_SERIALIZE_SOURCE_NODE_OWNER_INVALID:' + presenter.sourceRootId + ':' + index);
        if (node.layer !== originalLayers[index] && node.layer !== presenter.hiddenLayer)
            throw new Error('CREATOR_EDITOR_SERIALIZE_SOURCE_LAYER_UNEXPECTED:' + presenter.sourceRootId + ':' + index + ':' + node.layer);
    }
    return {presenter, marker, root: presenter.sourceRoot, proxyRoot};
}

function nodeRoots(cc, input) {
    if (input instanceof cc.Node) return [input];
    if (cc.Prefab && input instanceof cc.Prefab && input.data instanceof cc.Node) return [input.data];
    return [];
}

function inspectScopes(cc, input) {
    const roots = nodeRoots(cc, input);
    if (roots.length === 0) return {scopes: [], reason: 'non-node-input'};
    const Presenter = cc.js && cc.js.getClassByName(PRESENTER_CLASS);
    const Marker = cc.js && cc.js.getClassByName(MARKER_CLASS);
    if (typeof Presenter !== 'function' || typeof Marker !== 'function')
        return {scopes: [], reason: 'typed-classes-not-registered'};
    const valid = [], visited = new Set();
    for (const base of roots) {
        const stack = [base];
        while (stack.length) {
            const node = stack.pop();
            if (!node || visited.has(node)) continue;
            visited.add(node);
            const marker = node.getComponent(Marker);
            const presenter = node.getComponent(Presenter);
            if (marker && marker.kind === 'root' || presenter) {
                if (!marker || !presenter) throw new Error('CREATOR_EDITOR_SERIALIZE_PROXY_IDENTITY_INCOMPLETE:' + String(node.uuid || ''));
                const scope = validOwnedPresenter(cc, Presenter, Marker, presenter, node);
                if (!roots.some(root => containsNode(root, scope.root)))
                    throw new Error('CREATOR_EDITOR_SERIALIZE_SCOPE_OUTSIDE_ARGUMENT:' + presenter.sourceRootId);
                valid.push(scope);
            }
            for (let index = node.children.length - 1; index >= 0; index--) stack.push(node.children[index]);
        }
    }
    // A root scope's typed sourceNodes cover its owned descendant closure. Do
    // not mutate the same nested layer references twice through another scope.
    return {scopes: valid.filter(scope => !valid.some(other => other !== scope && containsNode(other.root, scope.root))),
        reason: valid.length ? 'owned-root-scope' : 'no-owned-scope'};
}

function collectScopes(cc, input) {
    return inspectScopes(cc, input).scopes;
}

function containsNode(root, target) {
    for (let current = target; current; current = current.parent) if (current === root) return true;
    return false;
}

function functionInfo(value, maxSourceLength = 220) {
    if (typeof value !== 'function') return null;
    let source = '';
    try { source = Function.prototype.toString.call(value).slice(0, maxSourceLength); } catch (_) { source = '<source-unavailable>'; }
    return {name: value.name || '', source};
}

function localIdText(value) {
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) return value.length === 1 ? localIdText(value[0]) : '';
    if (value && typeof value === 'object') {
        if (Array.isArray(value.localID)) return localIdText(value.localID);
        if (typeof value.localID === 'string') return value.localID;
    }
    return '';
}

function ownNestedLayerOverrideEvidence(scope, phase, limit = 48) {
    const evidenceRows = [];
    let sourceNodeCount = 0, prefabNodeCount = 0, candidateInstanceCount = 0;
    for (let index = 0; index < scope.presenter.sourceNodes.length; index++) {
        const node = scope.presenter.sourceNodes[index];
        if (!node || !node.isValid) continue;
        sourceNodeCount++;
        const prefabInfo = node._prefab || null;
        const fileId = prefabInfo && typeof prefabInfo.fileId === 'string' ? prefabInfo.fileId : '';
        if (!fileId) continue;
        prefabNodeCount++;
        const candidates = [];
        const seenInstances = new Set();
        const inspectInstance = (owner, instance, referencePath) => {
            if (!instance || seenInstances.has(instance) || !Array.isArray(instance.propertyOverrides)) return;
            seenInstances.add(instance);
            candidateInstanceCount++;
            const matching = [];
            for (const override of instance.propertyOverrides) {
                const path = override && (override.propertyPath || override.path);
                const target = override && override.targetInfo;
                const targetId = localIdText(target);
                if (!targetId || targetId !== fileId || !Array.isArray(path) || path.length !== 1 ||
                    (path[0] !== '_layer' && path[0] !== 'layer')) continue;
                matching.push({targetLocalId: targetId, propertyPath: path[0], value: override.value});
            }
            if (matching.length) candidates.push({ownerNodeUuid: String(owner.uuid || ''), referencePath, matching});
        };
        for (let ancestor = node; ancestor; ancestor = ancestor.parent) {
            // Creator 3.8.8 stores synchronized nested instance data through
            // Node._prefab.instance (PrefabInfo -> PrefabInstance), not as a
            // Node component. This is the serialized reference path used by
            // the saved PrefabInfo.instance field.
            const prefabInfo = ancestor._prefab;
            if (prefabInfo && typeof prefabInfo === 'object')
                inspectInstance(ancestor, prefabInfo.instance, 'node._prefab.instance');
            let components = Array.isArray(ancestor._components) ? ancestor._components : [];
            if (components.length === 0 && typeof ancestor.getComponents === 'function') {
                try { components = ancestor.getComponents() || []; } catch (_) { components = []; }
            }
            for (const component of components) {
                const overrides = component && component.propertyOverrides;
                if (!Array.isArray(overrides)) continue;
                inspectInstance(ancestor, component, 'node._components');
            }
            if (ancestor === scope.root) break;
        }
        if (candidates.length || node.layer !== scope.presenter.originalLayers[index]) {
            evidenceRows.push({sourceNodeUuid: String(node.uuid || ''), sourceNodeName: String(node.name || ''),
                sourceIndex: index, sourceFileId: fileId, nodeLayer: node.layer,
                authoredLayer: scope.presenter.originalLayers[index], candidates});
        }
    }
    const rows = evidenceRows.filter(row => row.candidates.length).concat(evidenceRows.filter(row => !row.candidates.length)).slice(0, limit);
    return {phase, sourceNodeCount, prefabNodeCount, candidateInstanceCount,
        matchingSourceNodeCount: evidenceRows.length, overrideMatchedSourceNodeCount: evidenceRows.filter(row => row.candidates.length).length,
        returnedRowCount: rows.length, rows};
}

function safeNestedLayerOverrideEvidence(scope, phase) {
    try { return ownNestedLayerOverrideEvidence(scope, phase); }
    catch (error) { return {phase, inspectionError: String(error).slice(0, 240), rows: []}; }
}

function collectAuthoredNestedOverridePatches(scope, preRestoreLayers) {
    const presenter = scope.presenter;
    const byInstance = new Map();
    for (let index = 0; index < presenter.sourceNodes.length; index++) {
        const node = presenter.sourceNodes[index];
        const authoredLayer = presenter.originalLayers[index];
        if (authoredLayer === presenter.hiddenLayer) continue;
        const beforeLayer = preRestoreLayers[index];
        if (beforeLayer !== presenter.hiddenLayer && beforeLayer !== authoredLayer)
            throw new Error('CREATOR_EDITOR_SERIALIZE_SOURCE_LAYER_PROVENANCE_INVALID:' + presenter.sourceRootId + ':' + index);
        const prefabInfo = node && node._prefab;
        const fileId = prefabInfo && typeof prefabInfo.fileId === 'string' ? prefabInfo.fileId : '';
        if (!fileId) continue;
        const matches = [];
        for (let owner = node; owner; owner = owner.parent) {
            const instance = owner._prefab && owner._prefab.instance;
            const overrides = instance && instance.propertyOverrides;
            if (!Array.isArray(overrides)) continue;
            for (let overrideIndex = 0; overrideIndex < overrides.length; overrideIndex++) {
                const override = overrides[overrideIndex];
                const path = override && (override.propertyPath || override.path);
                if (localIdText(override && override.targetInfo) !== fileId || !Array.isArray(path) ||
                    path.length !== 1 || (path[0] !== '_layer' && path[0] !== 'layer')) continue;
                matches.push({owner, instance, overrides, override, overrideIndex});
            }
            if (owner === scope.root) break;
        }
        if (matches.length > 1)
            throw new Error('CREATOR_EDITOR_SERIALIZE_NESTED_LAYER_OVERRIDE_AMBIGUOUS:' + presenter.sourceRootId + ':' + index + ':' + fileId);
        if (matches.length === 0) continue;
        const match = matches[0];
        // A row at the presenter's hidden value is attributable to this
        // presenter's suppression only when the exact owned source Node was
        // captured at a different authored layer before suppression.
        if (match.override.value !== presenter.hiddenLayer) continue;
        let group = byInstance.get(match.instance);
        if (!group) {
            group = {instance: match.instance, owner: match.owner, originalArray: match.overrides,
                replacementArray: match.overrides.slice(), changes: []};
            byInstance.set(match.instance, group);
        } else if (group.originalArray !== match.overrides) {
            throw new Error('CREATOR_EDITOR_SERIALIZE_NESTED_OVERRIDE_ARRAY_CHANGED:' + presenter.sourceRootId + ':' + index);
        }
        const descriptors = Object.getOwnPropertyDescriptors(match.override);
        if (!descriptors.value || !Object.prototype.hasOwnProperty.call(descriptors.value, 'value'))
            throw new Error('CREATOR_EDITOR_SERIALIZE_NESTED_OVERRIDE_VALUE_NOT_OWNED:' + presenter.sourceRootId + ':' + index);
        descriptors.value = {...descriptors.value, value: authoredLayer};
        const replacement = Object.create(Object.getPrototypeOf(match.override), descriptors);
        if (replacement.constructor !== match.override.constructor || replacement.targetInfo !== match.override.targetInfo ||
            replacement.propertyPath !== match.override.propertyPath || replacement.value !== authoredLayer)
            throw new Error('CREATOR_EDITOR_SERIALIZE_NESTED_OVERRIDE_CLONE_INVALID:' + presenter.sourceRootId + ':' + index);
        group.replacementArray[match.overrideIndex] = replacement;
        group.changes.push({sourceIndex: index, sourceFileId: fileId,
            ownerNodeUuid: String(match.owner.uuid || ''), previousValue: match.override.value, authoredValue: authoredLayer});
    }
    return Array.from(byInstance.values());
}

function installTemporaryAuthoredNestedOverrides(groups) {
    const installed = [];
    try {
        for (const group of groups) {
            group.instance.propertyOverrides = group.replacementArray;
            if (group.instance.propertyOverrides !== group.replacementArray)
                throw new Error('CREATOR_EDITOR_SERIALIZE_NESTED_OVERRIDE_TEMP_ASSIGN_FAILED');
            installed.push(group);
        }
    } catch (error) {
        for (let index = installed.length - 1; index >= 0; index--)
            installed[index].instance.propertyOverrides = installed[index].originalArray;
        throw error;
    }
    let restored = false;
    return () => {
        if (restored) return;
        for (let index = installed.length - 1; index >= 0; index--) {
            const group = installed[index];
            if (group.instance.propertyOverrides !== group.replacementArray)
                throw new Error('CREATOR_EDITOR_SERIALIZE_NESTED_OVERRIDE_TEMP_REPLACED');
            group.instance.propertyOverrides = group.originalArray;
            if (group.instance.propertyOverrides !== group.originalArray)
                throw new Error('CREATOR_EDITOR_SERIALIZE_NESTED_OVERRIDE_RESTORE_FAILED');
        }
        restored = true;
    };
}

function prefabReferenceSummary(value) {
    if (!value || typeof value !== 'object') return null;
    return {type: value.constructor && value.constructor.name || '', uuid: String(value.uuid || value._uuid || ''),
        name: String(value.name || value._name || ''), fileId: typeof value.fileId === 'string' ? value.fileId : null,
        instanceType: value.instance && value.instance.constructor && value.instance.constructor.name || null};
}

function prefabUtilityCallEvidence(label, args, result) {
    const input = args[0];
    const scopes = activeSerializationContext && activeSerializationContext.scopes || [];
    const sourceFileIds = new Set();
    for (const scope of scopes) for (const node of scope.presenter.sourceNodes) {
        const fileId = node && node._prefab && node._prefab.fileId;
        if (typeof fileId === 'string') sourceFileIds.add(fileId);
    }
    const summarizeInstance = instance => {
        const overrides = instance && instance.propertyOverrides;
        if (!Array.isArray(overrides)) return null;
        const layerRows = [];
        for (const row of overrides) {
            const path = row && (row.propertyPath || row.path);
            if (!Array.isArray(path) || path.length !== 1 || (path[0] !== '_layer' && path[0] !== 'layer')) continue;
            const id = localIdText(row.targetInfo);
            if (sourceFileIds.size && !sourceFileIds.has(id)) continue;
            if (layerRows.length < 48) layerRows.push({targetLocalId: id, value: row.value});
        }
        return {type: instance.constructor && instance.constructor.name || '', overrideCount: overrides.length,
            sourceLayerOverrides: layerRows};
    };
    const summarizeEntity = value => {
        if (!value || typeof value !== 'object') return {type: typeof value, value: value === null ? null : undefined};
        const preview = {type: value.constructor && value.constructor.name || '', uuid: String(value.uuid || value._uuid || ''),
            name: String(value.name || value._name || ''), ownKeys: Object.keys(value).slice(0, 32)};
        if (value.fileId) preview.fileId = value.fileId;
        if (value._prefab) {
            preview.prefabInfo = prefabReferenceSummary(value._prefab);
            preview.prefabInstance = summarizeInstance(value._prefab.instance);
        }
        if (value.data && typeof value.data === 'object') {
            preview.data = {type: value.data.constructor && value.data.constructor.name || '',
                uuid: String(value.data.uuid || value.data._uuid || ''), name: String(value.data.name || value.data._name || ''),
                prefabInfo: prefabReferenceSummary(value.data._prefab),
                prefabInstance: summarizeInstance(value.data._prefab && value.data._prefab.instance)};
        }
        if (value.prefab && typeof value.prefab === 'object') {
            preview.prefab = {type: value.prefab.constructor && value.prefab.constructor.name || '',
                uuid: String(value.prefab.uuid || value.prefab._uuid || ''), name: String(value.prefab.name || value.prefab._name || ''),
                data: value.prefab.data ? {type: value.prefab.data.constructor && value.prefab.data.constructor.name || '',
                    name: String(value.prefab.data.name || value.prefab.data._name || ''),
                    prefabInfo: prefabReferenceSummary(value.prefab.data._prefab),
                    prefabInstance: summarizeInstance(value.prefab.data._prefab && value.prefab.data._prefab.instance)} : null};
        }
        return preview;
    };
    const prefabRoot = result && result.prefab && result.prefab.data || result && result.data || null;
    let visitedNodeCount = 0;
    const instanceRows = [];
    if (prefabRoot && Array.isArray(prefabRoot.children)) {
        const visited = new Set(), stack = [prefabRoot];
        while (stack.length && visitedNodeCount < 8192) {
            const node = stack.pop();
            if (!node || visited.has(node)) continue;
            visited.add(node); visitedNodeCount++;
            const info = node._prefab;
            const instance = info && info.instance;
            const overrides = instance && instance.propertyOverrides;
            if (Array.isArray(overrides)) {
                const layerRows = [];
                for (const row of overrides) {
                    const path = row && (row.propertyPath || row.path);
                    const targetId = localIdText(row && row.targetInfo);
                    if (!Array.isArray(path) || path.length !== 1 || (path[0] !== '_layer' && path[0] !== 'layer') ||
                        (sourceFileIds.size && !sourceFileIds.has(targetId))) continue;
                    if (layerRows.length < 48) layerRows.push({targetLocalId: targetId, value: row.value});
                }
                if (layerRows.length && instanceRows.length < 48)
                    instanceRows.push({ownerNodeUuid: String(node.uuid || ''), ownerNodeName: String(node.name || ''),
                        ownerPrefabInfoFileId: info.fileId || '', instanceFileId: instance.fileId || '',
                        instanceAssetUuid: String(info.asset && (info.asset.uuid || info.asset._uuid) || ''), layerRows});
            }
            if (Array.isArray(node.children)) for (let index = node.children.length - 1; index >= 0; index--) stack.push(node.children[index]);
        }
    }
    return {label, input: summarizeEntity(input), inputPrefabInfo: prefabReferenceSummary(input && input._prefab),
        inputPrefabInstance: summarizeInstance(input && input._prefab && input._prefab.instance),
        result: summarizeEntity(result), prefabDataInstanceLayerOverrides: instanceRows,
        prefabDataNodesVisited: visitedNodeCount, scopeRootIds: scopes.map(scope => scope.presenter.sourceRootId),
        liveScopeEvidence: scopes.map(scope => safeNestedLayerOverrideEvidence(scope, 'getPrefabForSerialize-call'))};
}

function runtimeModuleNamespaces(realm) {
    const system = realm && realm.System;
    if (!system || (typeof system !== 'object' && typeof system !== 'function'))
        return {systemKeys: [], registrySlots: [], moduleRows: []};
    const systemKeys = Object.getOwnPropertyNames(system).slice(0, 64);
    const slots = [];
    const candidateTables = [];
    for (const symbol of Object.getOwnPropertySymbols(system)) {
        let value;
        try { value = system[symbol]; } catch (_) { continue; }
        if (!value || typeof value !== 'object') continue;
        const ids = Object.keys(value);
        const records = ids.filter(id => value[id] && typeof value[id] === 'object' &&
            (Object.prototype.hasOwnProperty.call(value[id], 'n') || Object.prototype.hasOwnProperty.call(value[id], 'id')));
        if (records.length > 0) {
            slots.push({symbol: String(symbol), moduleRecordCount: records.length});
            candidateTables.push({value, ids: records});
        }
    }
    for (const key of systemKeys) {
        let value;
        try { value = system[key]; } catch (_) { continue; }
        if (!value || typeof value !== 'object' || Array.isArray(value)) continue;
        const ids = Object.keys(value);
        const records = ids.filter(id => value[id] && typeof value[id] === 'object' &&
            (Object.prototype.hasOwnProperty.call(value[id], 'n') || Object.prototype.hasOwnProperty.call(value[id], 'id')));
        if (records.length > 0) {
            slots.push({key, moduleRecordCount: records.length});
            candidateTables.push({value, ids: records});
        }
    }
    const seen = new Set(), moduleRows = [];
    const relevant = /scene|prefab|serialize|facade/i;
    for (const table of candidateTables) for (const id of table.ids) {
        if (!relevant.test(id) || seen.has(id)) continue;
        seen.add(id);
        const record = table.value[id];
        let namespace = record && record.n;
        if (!namespace && typeof system.get === 'function') {
            try { namespace = system.get(id); } catch (_) { /* module may not have completed */ }
        }
        const exports = namespace && (typeof namespace === 'object' || typeof namespace === 'function') ?
            Object.getOwnPropertyNames(namespace).slice(0, 64).map(name => {
                let value;
                try { value = namespace[name]; } catch (_) { return {name, type: 'getter-error'}; }
                return {name, type: typeof value, function: functionInfo(value)};
            }) : [];
        moduleRows.push({id, loadedNamespace: !!namespace, exports});
        if (moduleRows.length >= 96) break;
    }
    return {systemKeys, registrySlots: slots, moduleRows};
}

function describeInterestingDescriptors(value, pattern = /scene|prefab|facade|manager|serialize|proxy/i, maxKeys = 48) {
    if (!value || (typeof value !== 'object' && typeof value !== 'function')) return {type: typeof value, keys: []};
    const keys = Object.getOwnPropertyNames(value).slice(0, maxKeys);
    const descriptors = [];
    for (const key of keys) {
        if (!pattern.test(key)) continue;
        let descriptor;
        try { descriptor = Object.getOwnPropertyDescriptor(value, key); } catch (_) { continue; }
        if (!descriptor) continue;
        const entry = {key, configurable: !!descriptor.configurable, enumerable: !!descriptor.enumerable,
            writable: !!descriptor.writable, hasGetter: typeof descriptor.get === 'function',
            hasSetter: typeof descriptor.set === 'function', valueType: typeof descriptor.value,
            function: functionInfo(descriptor.value)};
        if (descriptor.value && typeof descriptor.value === 'object') {
            entry.childKeys = Object.getOwnPropertyNames(descriptor.value).filter(name => pattern.test(name)).slice(0, 24);
        }
        descriptors.push(entry);
    }
    return {type: typeof value, constructor: value.constructor && value.constructor.name || '', keys, descriptors};
}

function cachedBuiltinSceneModules(requireFn) {
    const cache = requireFn && requireFn.cache;
    if (!cache || typeof cache !== 'object') return {available: false, modules: []};
    const paths = Object.keys(cache).filter(filename =>
        /(?:^|[\\/])builtin[\\/]scene[\\/]/i.test(filename) &&
        /(?:facade|proxy|serialize|prefab|utils)/i.test(filename));
    return {available: true, matchedModuleCount: paths.length, modules: paths.slice(0, 96).map(filename => {
        const mod = cache[filename];
        let exports = null;
        try { exports = mod && mod.exports; } catch (_) { /* inspect only loaded cache entries */ }
        const exportKeys = exports && (typeof exports === 'object' || typeof exports === 'function') ?
            Object.getOwnPropertyNames(exports).slice(0, 64) : [];
        const exportFunctions = [];
        const nestedExportFunctions = [];
        for (const key of exportKeys) {
            let descriptor;
            try { descriptor = Object.getOwnPropertyDescriptor(exports, key); } catch (_) { continue; }
            if (descriptor && typeof descriptor.value === 'function') {
                const ctor = descriptor.value;
                const prototype = ctor.prototype;
                const prototypeNames = prototype ? Object.getOwnPropertyNames(prototype).filter(name => /save|serialize|scene|prefab|root/i.test(name)).slice(0, 24) : [];
                const prototypeFunctions = [];
                for (const name of prototypeNames.slice(0, 12)) {
                    let methodDescriptor;
                    try { methodDescriptor = Object.getOwnPropertyDescriptor(prototype, name); } catch (_) { continue; }
                    if (methodDescriptor && typeof methodDescriptor.value === 'function') {
                        const maxSourceLength = (ctor.name || key) === 'PrefabSceneProxy' &&
                            (name === 'serialize' || name === 'save') ? 6000 : 1200;
                        prototypeFunctions.push({name, function: functionInfo(methodDescriptor.value, maxSourceLength)});
                    }
                }
                exportFunctions.push({key, function: functionInfo(ctor),
                    prototypeMethods: prototypeNames, prototypeFunctions});
            } else if (descriptor && descriptor.value && typeof descriptor.value === 'object') {
                const nestedNames = Object.getOwnPropertyNames(descriptor.value).slice(0, 64);
                for (const nestedName of nestedNames) {
                    if (nestedName !== 'getPrefabForSerialize') continue;
                    let nestedDescriptor;
                    try { nestedDescriptor = Object.getOwnPropertyDescriptor(descriptor.value, nestedName); } catch (_) { continue; }
                    if (nestedDescriptor && typeof nestedDescriptor.value === 'function')
                        nestedExportFunctions.push({key, nestedName,
                            function: functionInfo(nestedDescriptor.value, 6000)});
                }
            }
        }
        return {filename, module: mod, exports, id: mod && mod.id || '', loaded: !!(mod && mod.loaded),
            exportsType: exports === null ? 'null' : typeof exports, exportKeys, exportFunctions, nestedExportFunctions};
    })};
}

function cachedSceneModuleInfo(requireFn) {
    const cache = cachedBuiltinSceneModules(requireFn);
    return {available: cache.available, matchedModuleCount: cache.matchedModuleCount,
        modules: cache.modules.map(({filename, id, loaded, exportsType, exportKeys, exportFunctions, nestedExportFunctions}) =>
            ({filename, id, loaded, exportsType, exportKeys, exportFunctions, nestedExportFunctions}))};
}

function currentSceneInfo(cc) {
    try {
        const scene = cc && cc.director && typeof cc.director.getScene === 'function' ? cc.director.getScene() : null;
        return scene ? {available: true, name: String(scene.name || ''), uuid: String(scene.uuid || scene._id || ''),
            childCount: Array.isArray(scene.children) ? scene.children.length : null,
            directChildNames: Array.isArray(scene.children) ? scene.children.slice(0, 40).map(node => String(node && node.name || '')) : []} :
            {available: false, reason: 'director-scene-unavailable'};
    } catch (error) { return {available: false, error: String(error).slice(0, 240)}; }
}

function activeOwnedSerializationHooks() {
    if (!activeInstallation) return [];
    return activeInstallation.api.diagnostics().installedMethods.map(label => {
        const patch = activeInstallation.api._patches && activeInstallation.api._patches.find(row => row.label === label);
        return patch ? {label, originalFunction: functionInfo(patch.descriptor.value, 6000)} : {label, originalFunction: null};
    });
}

function probeRuntimeApi(cc, editorExtends = globalThis.EditorExtends, realm = globalThis, requireFn = null) {
    const editor = realm && realm.Editor;
    const describeObject = value => value && (typeof value === 'object' || typeof value === 'function') ? {
        type: typeof value,
        constructor: value.constructor && value.constructor.name || '',
        keys: Object.getOwnPropertyNames(value).slice(0, 80),
        symbols: Object.getOwnPropertySymbols(value).slice(0, 24).map(String),
    } : {type: typeof value};
    const editorFunctions = {};
    if (editorExtends) for (const key of ['serialize', 'serializeCompiled', 'Parser']) {
        let value;
        try { value = editorExtends[key]; } catch (error) { editorFunctions[key] = {error: String(error)}; continue; }
        const descriptor = Object.getOwnPropertyDescriptor(editorExtends, key);
        editorFunctions[key] = {ownDescriptor: descriptor ? {
            configurable: !!descriptor.configurable, enumerable: !!descriptor.enumerable,
            writable: !!descriptor.writable, hasGetter: typeof descriptor.get === 'function',
            hasSetter: typeof descriptor.set === 'function', valueType: typeof descriptor.value,
        } : null,
            function: functionInfo(value), valueType: typeof value,
            nestedKeys: value && (typeof value === 'object' || typeof value === 'function') ? Object.getOwnPropertyNames(value).slice(0, 48) : []};
    }
    const message = editor && editor.Message;
    const messageRequest = message && message.request;
    const packageApi = editor && editor.Package;
    let packages = null;
    if (packageApi && typeof packageApi.getPackages === 'function') {
        try { packages = packageApi.getPackages({name: 'scene'}).map(row => ({name: row.name, path: row.path, main: row.main})); }
        catch (error) { packages = {error: String(error)}; }
    }
    const registry = runtimeModuleNamespaces(realm);
    const exportMatches = [];
    for (const row of registry.moduleRows) for (const item of row.exports) {
        const cls = item.function;
        if (!cls) continue;
        const className = cls.name || item.name;
        if (!/^(SceneFacadeManager|SceneFacadeFSM|PrefabSceneProxy|PrefabSceneFacade|GeneralSceneFacade|SceneProxy|Parser)$/.test(className)) continue;
        const moduleNamespace = (function () {
            const sys = realm && realm.System;
            try { return sys && typeof sys.get === 'function' ? sys.get(row.id) : null; } catch (_) { return null; }
        })();
        let ctor = moduleNamespace && moduleNamespace[item.name];
        if (item.name === 'default' && moduleNamespace) ctor = moduleNamespace.default;
        const proto = ctor && ctor.prototype;
        const methods = proto ? Object.getOwnPropertyNames(proto).filter(name => typeof proto[name] === 'function').slice(0, 48)
            .map(name => ({name, function: functionInfo(proto[name])})) : [];
        exportMatches.push({moduleId: row.id, exportName: item.name, className, methods});
    }
    return {
        Editor: describeObject(editor),
        EditorMessage: describeObject(message),
        EditorMessageRequest: functionInfo(messageRequest),
        scenePackages: packages,
        EditorExtends: describeObject(editorExtends),
        EditorExtendsFunctions: editorFunctions,
        cc: describeObject(cc),
        currentScene: currentSceneInfo(cc),
        cce: describeInterestingDescriptors(realm && realm.cce),
        System: registry,
        facadeExports: exportMatches.slice(0, 32),
        cachedBuiltinSceneModules: cachedSceneModuleInfo(requireFn),
        activeOwnedSerializationHooks: activeOwnedSerializationHooks(),
    };
}

function installRuntimeCallProbe(cc, editorExtends = globalThis.EditorExtends, realm = globalThis, requireFn = null) {
    if (activeRuntimeProbe) throw new Error('CREATOR_EDITOR_RUNTIME_PROBE_ALREADY_INSTALLED');
    const apiInfo = probeRuntimeApi(cc, editorExtends, realm, requireFn);
    const patches = [], callCounts = Object.create(null), callRows = [];
    const recordCall = (label, thisArg, args) => {
        callCounts[label] = (callCounts[label] || 0) + 1;
        if (callRows.length >= 128) return;
        const argTypes = args.slice(0, 8).map(arg => arg === null ? 'null' :
            arg && arg.constructor ? arg.constructor.name : typeof arg);
        const row = {label, callIndex: callCounts[label], thisType: thisArg && thisArg.constructor && thisArg.constructor.name || typeof thisArg,
            argTypes};
        callRows.push(row);
        console.info('[MONKEY_CREATOR_SAVE_CALL_PROBE] ' + JSON.stringify(row));
    };
    const patchFunction = (holder, key, label) => {
        if (!holder || typeof holder[key] !== 'function') return;
        if (patches.some(row => row.holder === holder && row.key === key)) return;
        const descriptor = Object.getOwnPropertyDescriptor(holder, key);
        if (!descriptor || typeof descriptor.value !== 'function' ||
            (!descriptor.writable && !descriptor.configurable)) return;
        const original = descriptor.value;
        const wrapper = new Proxy(original, {apply(target, thisArg, args) {
            recordCall(label, thisArg, args);
            return Reflect.apply(target, thisArg, args);
        }});
        Object.defineProperty(holder, key, {...descriptor, value: wrapper});
        patches.push({holder, key, descriptor, wrapper});
    };
    const patchPrefabUtility = (holder, key, label) => {
        if (!holder || typeof holder[key] !== 'function' || patches.some(row => row.holder === holder && row.key === key)) return;
        const descriptor = Object.getOwnPropertyDescriptor(holder, key);
        if (!descriptor || typeof descriptor.value !== 'function' || (!descriptor.writable && !descriptor.configurable)) return;
        const original = descriptor.value;
        const wrapper = new Proxy(original, {apply(target, thisArg, args) {
            recordCall(label, thisArg, args);
            let result;
            try {
                result = Reflect.apply(target, thisArg, args);
            } catch (error) {
                try { console.info('[MONKEY_CREATOR_PREFAB_SERIALIZE_PROBE] ' + JSON.stringify({
                    label, outcome: 'throw', error: String(error).slice(0, 240), scopeRootIds:
                        activeSerializationContext && activeSerializationContext.scopes.map(scope => scope.presenter.sourceRootId) || [],
                })); } catch (_) { /* diagnostics must not replace the original exception */ }
                throw error;
            }
            let evidence;
            try { evidence = prefabUtilityCallEvidence(label, args, result); }
            catch (error) { evidence = {label, outcome: 'diagnostic-error', error: String(error).slice(0, 240)}; }
            try { console.info('[MONKEY_CREATOR_PREFAB_SERIALIZE_PROBE] ' + JSON.stringify(evidence)); } catch (_) { /* diagnostics are non-invasive */ }
            return result;
        }});
        Object.defineProperty(holder, key, {...descriptor, value: wrapper});
        patches.push({holder, key, descriptor, wrapper});
    };
    patchFunction(editorExtends, 'serializeCompiled', 'EditorExtends.serializeCompiled');
    const maybePatchParser = (value, label) => {
        if (typeof value === 'function' && value.name === 'Parser' && value.prototype)
            patchFunction(value.prototype, 'parse', label + '.prototype.parse');
    };
    maybePatchParser(editorExtends && editorExtends.Parser, 'EditorExtends.Parser');
    maybePatchParser(editorExtends && editorExtends.serialize && editorExtends.serialize.Parser, 'EditorExtends.serialize.Parser');
    for (const match of apiInfo.facadeExports) {
        const system = realm && realm.System;
        let ns = null;
        try { ns = system && system.get && system.get(match.moduleId); } catch (_) { /* diagnostics only */ }
        const ctor = ns && ns[match.exportName];
        if (!ctor || !ctor.prototype) continue;
        const names = match.className === 'Parser' ? ['parse'] :
            match.className === 'SceneFacadeManager' ? ['saveScene'] :
            match.className === 'SceneFacadeFSM' ? ['toPrefab'] :
            match.className === 'PrefabSceneProxy' ? ['save', 'serialize'] :
            match.className === 'PrefabSceneFacade' || match.className === 'GeneralSceneFacade' ? ['saveScene'] :
            match.className === 'SceneProxy' ? ['save', 'serialize'] : [];
        for (const name of names) patchFunction(ctor.prototype, name,
            match.moduleId + ':' + match.className + (match.className === 'Parser' ? '.prototype.' : '.') + name);
    }
    // Editor scene modules are CommonJS-loaded in this realm. Cocos 3.8.8's
    // System registry is a separate VM/module cache, so instrument the actual
    // already-loaded builtin exports as well as any System namespace exports.
    const cached = cachedBuiltinSceneModules(requireFn);
    const classMethods = {
        SceneFacadeManager: ['saveScene'], SceneFacadeFSM: ['toPrefab'],
        PrefabSceneProxy: ['save', 'serialize'], PrefabSceneFacade: ['saveScene'],
        GeneralSceneFacade: ['saveScene'], SceneProxy: ['save', 'serialize'], Parser: ['parse'],
    };
    for (const module of cached.modules) {
        const exports = module.exports;
        if (!exports || (typeof exports !== 'object' && typeof exports !== 'function')) continue;
        for (const key of module.exportKeys) {
            let descriptor;
            try { descriptor = Object.getOwnPropertyDescriptor(exports, key); } catch (_) { continue; }
            const ctor = descriptor && descriptor.value;
            if (typeof ctor !== 'function' || !ctor.prototype) continue;
            const className = ctor.name || key;
            for (const name of classMethods[className] || [])
                patchFunction(ctor.prototype, name, module.id + ':' + className + '.prototype.' + name);
        }
        if (/proxy-utils\.ccc$/i.test(module.filename)) {
            for (const name of ['serializePrefab', 'serializeScene', 'checkClose'])
                patchFunction(exports, name, module.id + ':' + name);
        }
        for (const key of module.exportKeys) {
            let exportDescriptor;
            try { exportDescriptor = Object.getOwnPropertyDescriptor(exports, key); } catch (_) { continue; }
            const namespace = exportDescriptor && exportDescriptor.value;
            if (!namespace || typeof namespace !== 'object') continue;
            const nested = Object.getOwnPropertyDescriptor(namespace, 'getPrefabForSerialize');
            if (nested && typeof nested.value === 'function')
                patchPrefabUtility(namespace, 'getPrefabForSerialize', module.id + ':exports.' + key + '.getPrefabForSerialize');
        }
        if (/\/index\.ccc$/i.test(module.filename) && /\/scene\/dist\/script\/export\/serialize\//i.test(module.filename)) {
            for (const name of ['serialize', 'serializeSafe'])
                patchFunction(exports, name, module.id + ':' + name);
        }
    }
    let uninstalled = false;
    const api = {
        initialProbe: apiInfo,
        callCounts,
        callRows,
        uninstall() {
            if (uninstalled) return;
            for (let index = patches.length - 1; index >= 0; index--) {
                const patch = patches[index];
                if (patch.holder[patch.key] !== patch.wrapper)
                    throw new Error('CREATOR_EDITOR_RUNTIME_PROBE_HOOK_REPLACED:' + patch.key);
                Object.defineProperty(patch.holder, patch.key, patch.descriptor);
            }
            uninstalled = true;
            activeRuntimeProbe = null;
        },
        summary() { return {patched: patches.map(row => row.key), callCounts: {...callCounts}, callRows: callRows.slice()}; },
    };
    activeRuntimeProbe = api;
    return api;
}

function install(cc, editorExtends = globalThis.EditorExtends, realm = globalThis, requireFn = null) {
    if (activeInstallation) {
        if (activeInstallation.cc === cc && activeInstallation.editorExtends === editorExtends &&
            activeInstallation.realm === realm && activeInstallation.requireFn === requireFn) {
            activeInstallation.api.refresh();
            return activeInstallation.api;
        }
        throw new Error('CREATOR_EDITOR_SERIALIZE_GUARD_ALREADY_INSTALLED');
    }
    if (!cc || typeof cc.Node !== 'function' || !editorExtends || typeof editorExtends.serialize !== 'function')
        throw new Error('CREATOR_EDITOR_SERIALIZE_ENTRY_UNAVAILABLE');
    const keys = ['serialize'];
    const patches = [];
    let depth = 0, diagnosticCount = 0, priorityDiagnosticCount = 0;

    const log = (record, priority, consumeQuota = true) => {
        if (priority) priorityDiagnosticCount++;
        else if (consumeQuota) {
            if (diagnosticCount >= MAX_DIAGNOSTICS) return;
            diagnosticCount++;
        }
        console.info(PREFIX + ' ' + JSON.stringify(record));
    };
    const patchOwnedLayerSerialize = (holder, key, label) => {
        if (!holder || patches.some(row => row.holder === holder && row.key === key)) return false;
        const descriptor = Object.getOwnPropertyDescriptor(holder, key);
        if (!descriptor || typeof descriptor.value !== 'function' || (!descriptor.writable && !descriptor.configurable)) return false;
        const original = descriptor.value;
        const wrapper = function (...args) {
            if (depth > 0) return Reflect.apply(original, this, args);
            let root = null;
            try { root = this && typeof this.getRootNode === 'function' ? this.getRootNode() : null; }
            catch (error) {
                log({method: label, outcome: 'root-resolution-threw', error: String(error).slice(0, 240)}, true);
                throw error;
            }
            if (!(root instanceof cc.Node)) {
                return Reflect.apply(original, this, args);
            }
            depth++;
            let scopes = [], snapshots = [], changedLayerCount = 0, restoredNodeCount = 0, error = null, restoreError = null;
            let restoreNestedOverrides = () => {};
            let previousSerializationContext = null;
            let serializationContextInstalled = false;
            const nestedOverrideChanges = [];
            const nestedLayerEvidence = [];
            try {
                scopes = collectScopes(cc, root);
                for (const scope of scopes) snapshots.push({scope, layers: scope.presenter.sourceNodes.map(node => node.layer)});
                for (const {scope} of snapshots)
                    nestedLayerEvidence.push(safeNestedLayerOverrideEvidence(scope, 'before-authored-restore'));
                const overrideGroups = [];
                for (const {scope, layers} of snapshots) {
                    const groups = collectAuthoredNestedOverridePatches(scope, layers);
                    overrideGroups.push(...groups);
                    for (const group of groups) nestedOverrideChanges.push(...group.changes);
                }
                for (const {scope} of snapshots) {
                    const presenter = scope.presenter;
                    for (let index = 0; index < presenter.sourceNodes.length; index++) {
                        const node = presenter.sourceNodes[index];
                        if (node.layer !== presenter.originalLayers[index]) changedLayerCount++;
                        if (node.layer !== presenter.originalLayers[index]) node.layer = presenter.originalLayers[index];
                    }
                }
                restoreNestedOverrides = installTemporaryAuthoredNestedOverrides(overrideGroups);
                for (const {scope} of snapshots)
                    nestedLayerEvidence.push(safeNestedLayerOverrideEvidence(scope, 'before-native-serialize'));
                previousSerializationContext = activeSerializationContext;
                activeSerializationContext = {scopes: snapshots.map(row => row.scope)};
                serializationContextInstalled = true;
                const result = Reflect.apply(original, this, args);
                for (const {scope} of snapshots)
                    nestedLayerEvidence.push(safeNestedLayerOverrideEvidence(scope, 'after-native-serialize'));
                return result;
            } catch (cause) {
                error = cause;
                throw cause;
            } finally {
                if (serializationContextInstalled) activeSerializationContext = previousSerializationContext;
                try { restoreNestedOverrides(); }
                catch (cause) { restoreError = cause; }
                for (let scopeIndex = snapshots.length - 1; scopeIndex >= 0; scopeIndex--) {
                    const {scope, layers} = snapshots[scopeIndex];
                    for (let index = 0; index < scope.presenter.sourceNodes.length; index++) {
                        const node = scope.presenter.sourceNodes[index];
                        if (node && node.isValid) {
                            if (node.layer !== layers[index]) node.layer = layers[index];
                            restoredNodeCount++;
                        }
                    }
                }
                for (const {scope} of snapshots)
                    nestedLayerEvidence.push(safeNestedLayerOverrideEvidence(scope, 'after-live-layer-restore'));
                depth--;
                if (scopes.length || error) log({method: label, sourceRootIds: snapshots.map(row => row.scope.presenter.sourceRootId),
                    sourceNodeCount: snapshots.reduce((count, row) => count + row.layers.length, 0),
                    changedLayerCount, restoredNodeCount, nestedOverridePatchCount: nestedOverrideChanges.length,
                    nestedOverrideChanges, nestedLayerEvidence, restoreError: restoreError ? String(restoreError).slice(0, 240) : null,
                    outcome: error || restoreError ? 'throw' : 'return'}, changedLayerCount > 0 || !!error || !!restoreError,
                scopes.length === 0 && !error);
                if (restoreError && !error) throw restoreError;
            }
        };
        Object.defineProperty(holder, key, {...descriptor, value: wrapper});
        patches.push({holder, key, wrapper, descriptor, label});
        return true;
    };
    const refreshCachedPrefabSerializer = () => {
        const cached = cachedBuiltinSceneModules(requireFn);
        let count = 0;
        for (const module of cached.modules) {
            const exports = module.exports;
            if (!exports || (typeof exports !== 'object' && typeof exports !== 'function')) continue;
            for (const key of module.exportKeys) {
                let descriptor;
                try { descriptor = Object.getOwnPropertyDescriptor(exports, key); } catch (_) { continue; }
                const ctor = descriptor && descriptor.value;
                if (typeof ctor !== 'function' || !ctor.prototype || (ctor.name || key) !== 'PrefabSceneProxy') continue;
                if (patchOwnedLayerSerialize(ctor.prototype, 'serialize', module.id + ':PrefabSceneProxy.serialize')) count++;
            }
        }
        return count;
    };
    try {
        for (const key of keys) {
            const original = editorExtends[key];
            const wrapper = new Proxy(original, {
                apply(target, thisArg, args) {
                    if (depth > 0) return Reflect.apply(target, thisArg, args);
                    depth++;
                    let scopes = [], scopeReason = 'unresolved', snapshots = [], error = null, result;
                    let restoredNodeCount = 0, changedLayerCount = 0;
                    try {
                        const scanned = inspectScopes(cc, args[0]);
                        scopes = scanned.scopes;
                        scopeReason = scanned.reason;
                        for (const scope of scopes) {
                            const p = scope.presenter;
                            snapshots.push({scope, layers: p.sourceNodes.map(node => node.layer)});
                        }
                        // Use Creator's setter so synchronized Prefab instances
                        // reconcile their serialized _layer override records.
                        for (const {scope} of snapshots) {
                            const p = scope.presenter;
                            for (let index = 0; index < p.sourceNodes.length; index++) {
                                const node = p.sourceNodes[index];
                                if (node.layer !== p.originalLayers[index]) changedLayerCount++;
                                if (node.layer !== p.originalLayers[index]) node.layer = p.originalLayers[index];
                            }
                        }
                        result = Reflect.apply(target, thisArg, args);
                        return result;
                    } catch (cause) {
                        error = cause;
                        throw cause;
                    } finally {
                        for (let scopeIndex = snapshots.length - 1; scopeIndex >= 0; scopeIndex--) {
                            const {scope, layers} = snapshots[scopeIndex];
                            for (let index = 0; index < scope.presenter.sourceNodes.length; index++) {
                                const node = scope.presenter.sourceNodes[index];
                                if (node && node.isValid) {
                                    if (node.layer !== layers[index]) node.layer = layers[index];
                                    restoredNodeCount++;
                                }
                            }
                        }
                        depth--;
                        const input = args[0];
                        const root = input instanceof cc.Node ? input :
                            (cc.Prefab && input instanceof cc.Prefab && input.data instanceof cc.Node ? input.data : null);
                        if (root || scopes.length || error) {
                            log({method: key, inputType: input && input.constructor ? input.constructor.name : typeof input,
                                inputNodeUuid: root ? String(root.uuid || '') : null,
                                scopeReason,
                                matchedSourceRootIds: snapshots.map(row => row.scope.presenter.sourceRootId),
                                sourceNodeCount: snapshots.reduce((n, row) => n + row.layers.length, 0),
                                changedLayerCount, restoredNodeCount, outcome: error ? 'throw' : 'return'},
                            changedLayerCount > 0 || !!error, scopes.length === 0 && !error);
                        }
                    }
                },
            });
            const descriptor = Object.getOwnPropertyDescriptor(editorExtends, key);
            if (!descriptor || (!descriptor.writable && !descriptor.set && !descriptor.configurable))
                throw new Error('CREATOR_EDITOR_SERIALIZE_ENTRY_NOT_PATCHABLE:' + key);
            Object.defineProperty(editorExtends, key, {...descriptor, value: wrapper});
            patches.push({holder: editorExtends, key, original, wrapper, descriptor, label: 'EditorExtends.' + key});
        }
        refreshCachedPrefabSerializer();
    } catch (error) {
        for (let index = patches.length - 1; index >= 0; index--) {
            const patch = patches[index];
            if (patch.holder[patch.key] === patch.wrapper) Object.defineProperty(patch.holder, patch.key, patch.descriptor);
        }
        throw error;
    }
    let uninstalled = false;
    const api = {
        uninstall() {
            if (uninstalled) return;
            for (let index = patches.length - 1; index >= 0; index--) {
                const patch = patches[index];
                if (patch.holder[patch.key] !== patch.wrapper)
                    throw new Error('CREATOR_EDITOR_SERIALIZE_ENTRY_REPLACED:' + patch.label);
                Object.defineProperty(patch.holder, patch.key, patch.descriptor);
            }
            uninstalled = true;
            activeInstallation = null;
        },
        refresh() { return {cachedPrefabProxySerializeMethodsPatched: refreshCachedPrefabSerializer()}; },
        diagnostics() { return {installedMethods: patches.map(row => row.label), diagnosticCount, priorityDiagnosticCount}; },
        _patches: patches,
    };
    activeInstallation = {cc, editorExtends, realm, requireFn, api};
    return api;
}

function uninstall() {
    if (activeInstallation) activeInstallation.api.uninstall();
}

module.exports = {install, uninstall, collectScopes, inspectScopes, validOwnedPresenter,
    probeRuntimeApi, installRuntimeCallProbe, PREFIX};
