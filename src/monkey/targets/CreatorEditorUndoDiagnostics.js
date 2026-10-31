'use strict';

const DEFAULT_LIMITS = Object.freeze({maxObjects: 10000, maxEdges: 30000, maxDepth: 64, maxNodeSamples: 16});
const SCENE_UNDO_PATH = /(?:^|[\\/])builtin[\\/]scene[\\/]dist[\\/]script[\\/]export[\\/]undo[\\/]scene\.ccc$/i;

function boundedText(value, limit) {
    try { return String(value).slice(0, limit); } catch (_) { return '<unavailable>'; }
}

function constructorName(value) {
    try { return value && value.constructor && typeof value.constructor.name === 'string' ?
        value.constructor.name.slice(0, 128) : ''; } catch (_) { return ''; }
}

function ownKeyCount(value, limit = 256) {
    try {
        let count = 0;
        for (const key in value) if (Object.prototype.hasOwnProperty.call(value, key)) {
            count++;
            if (count >= limit) return {count, capped: true};
        }
        return {count, capped: false};
    } catch (_) { return {count: null, capped: false}; }
}

function describeValue(value, realm) {
    if (value === null) return {type: 'null'};
    const type = typeof value;
    if (type === 'string') return {type, length: value.length};
    if (type !== 'object' && type !== 'function') return {type};
    let node = false;
    try {
        const Node = realm && realm.cc && realm.cc.Node;
        node = typeof Node === 'function' && value instanceof Node;
    } catch (_) { /* cross-realm instance check is best-effort */ }
    if (!node) node = constructorName(value) === 'Node';
    const result = {type, constructor: constructorName(value), node};
    if (Array.isArray(value)) result.arrayLength = value.length;
    else result.ownEnumerableKeyCount = ownKeyCount(value).count;
    if (node) {
        try { if (typeof value.name === 'string') result.nodeName = value.name.slice(0, 128); } catch (_) {}
        try { if (typeof value.uuid === 'string') result.nodeUuid = value.uuid.slice(0, 128); } catch (_) {}
    }
    return result;
}

function describeUndoField(value) {
    const result = describeValue(value, globalThis);
    try {
        if (typeof value === 'string') result.length = value.length;
        else if (Array.isArray(value)) result.arrayLength = value.length;
        else if (value instanceof Map || value instanceof Set) result.collectionSize = value.size;
        else if (value && typeof value === 'object') {
            result.ownEnumerableKeyCount = Object.keys(value).length;
        }
    } catch (_) { result.detailUnavailable = true; }
    return result;
}

function describeManagerFields(manager, limit = 32) {
    const fields = [];
    let keys;
    try { keys = Object.getOwnPropertyNames(manager); } catch (_) { return fields; }
    for (const key of keys) {
        if (!/(?:record|undo|redo|pause|start|end|reset|snapshot|command|dump)/i.test(key)) continue;
        let descriptor;
        try { descriptor = Object.getOwnPropertyDescriptor(manager, key); } catch (_) { continue; }
        if (!descriptor || !Object.prototype.hasOwnProperty.call(descriptor, 'value')) {
            fields.push({name: key.slice(0, 128), accessor: true});
        } else fields.push({name: key.slice(0, 128), value: describeUndoField(descriptor.value)});
        if (fields.length >= limit) break;
    }
    return fields;
}

function describeUndoMethods(prototype, maxMethods = 32, maxSourceLength = 2500) {
    const methods = [];
    let current = prototype;
    let depth = 0;
    while (current && current !== Object.prototype && depth < 4 && methods.length < maxMethods) {
        let keys;
        try { keys = Object.getOwnPropertyNames(current); } catch (_) { break; }
        for (const name of keys) {
            if (!/(?:record|undo|redo|pause|start|end|reset|snapshot)/i.test(name)) continue;
            let descriptor;
            try { descriptor = Object.getOwnPropertyDescriptor(current, name); } catch (_) { continue; }
            if (!descriptor || typeof descriptor.value !== 'function') continue;
            let source = '<source-unavailable>';
            try { source = Function.prototype.toString.call(descriptor.value).slice(0, maxSourceLength); }
            catch (_) {}
            methods.push({name: name.slice(0, 128), ownerDepth: depth, source,
                sourceTruncated: source.length >= maxSourceLength});
            if (methods.length >= maxMethods) break;
        }
        current = Object.getPrototypeOf(current);
        depth++;
    }
    return methods;
}

function summarizeStructure(root, realm = globalThis, limits = {}) {
    const cap = {...DEFAULT_LIMITS, ...limits};
    const result = {
        objects: 0, arrays: 0, edges: 0, strings: 0, totalStringChars: 0, maxStringLength: 0,
        maxPropertyKeyLength: 0, maxPropertyValueStringLength: 0, maxArrayLength: 0, maxPropertiesPerObject: 0,
        aliases: 0, cycles: 0, accessors: 0, estimatedUniqueGraphCharsUpperBound: 0,
        maxDepth: 0, nodeSamples: [], truncatedObjects: false, truncatedEdges: false, truncatedDepth: false,
    };
    const seen = new WeakSet(), active = new WeakSet();
    const stack = [{value: root, depth: 0, exit: false, propertyKey: null}];
    const addString = value => {
        result.strings++;
        result.totalStringChars += value.length;
        result.maxStringLength = Math.max(result.maxStringLength, value.length);
        result.estimatedUniqueGraphCharsUpperBound += 2 + value.length * 6;
    };
    while (stack.length) {
        const entry = stack.pop(), value = entry.value;
        if (entry.exit) { active.delete(value); continue; }
        result.maxDepth = Math.max(result.maxDepth, entry.depth);
        if (entry.depth > cap.maxDepth) { result.truncatedDepth = true; continue; }
        if (typeof value === 'string') {
            addString(value);
            if (entry.propertyKey !== null) result.maxPropertyValueStringLength =
                Math.max(result.maxPropertyValueStringLength, value.length);
            continue;
        }
        if (value === null || (typeof value !== 'object' && typeof value !== 'function')) {
            result.estimatedUniqueGraphCharsUpperBound += value === null ? 4 : 24;
            continue;
        }
        if (active.has(value)) { result.cycles++; continue; }
        if (seen.has(value)) { result.aliases++; continue; }
        if (result.objects >= cap.maxObjects) { result.truncatedObjects = true; continue; }
        seen.add(value); active.add(value); result.objects++;
        const isArray = Array.isArray(value);
        if (isArray) {
            result.arrays++;
            result.maxArrayLength = Math.max(result.maxArrayLength, value.length);
            result.estimatedUniqueGraphCharsUpperBound += 2 + Math.min(value.length, cap.maxEdges) * 2;
        } else {
            result.estimatedUniqueGraphCharsUpperBound += 2;
            try {
                if ((typeof realm?.cc?.Node === 'function' && value instanceof realm.cc.Node) ||
                    constructorName(value) === 'Node') {
                    if (result.nodeSamples.length < cap.maxNodeSamples) {
                        const sample = {};
                        try { if (typeof value.name === 'string') sample.name = value.name.slice(0, 128); } catch (_) {}
                        try { if (typeof value.uuid === 'string') sample.uuid = value.uuid.slice(0, 128); } catch (_) {}
                        result.nodeSamples.push(sample);
                    }
                }
            } catch (_) {}
        }
        stack.push({value, depth: entry.depth, exit: true});
        let keys;
        try {
            if (isArray) {
                const length = Math.min(value.length, Math.max(0, cap.maxEdges - result.edges));
                keys = Array.from({length}, (_, index) => String(index));
                if (length < value.length) result.truncatedEdges = true;
            } else {
                keys = [];
                for (const key in value) {
                    if (!Object.prototype.hasOwnProperty.call(value, key)) continue;
                    if (result.edges + keys.length >= cap.maxEdges) { result.truncatedEdges = true; break; }
                    keys.push(key);
                }
            }
        } catch (_) { keys = []; result.accessors++; }
        if (!isArray) result.maxPropertiesPerObject = Math.max(result.maxPropertiesPerObject, keys.length);
        for (let index = keys.length - 1; index >= 0; index--) {
            const key = keys[index];
            result.edges++;
            if (result.edges > cap.maxEdges) { result.truncatedEdges = true; break; }
            const keyText = String(key);
            result.maxPropertyKeyLength = Math.max(result.maxPropertyKeyLength, keyText.length);
            result.estimatedUniqueGraphCharsUpperBound += 4 + keyText.length * 6;
            let descriptor;
            try { descriptor = Object.getOwnPropertyDescriptor(value, key); }
            catch (_) { result.accessors++; continue; }
            if (!descriptor || !Object.prototype.hasOwnProperty.call(descriptor, 'value')) {
                result.accessors++;
                continue;
            }
            stack.push({value: descriptor.value, depth: entry.depth + 1, exit: false,
                propertyKey: keyText});
        }
    }
    result.estimatedUniqueGraphCharsUpperBound += result.objects * 2;
    result.estimateKind = 'unique-graph-upper-bound; shared aliases counted once';
    return result;
}

function sceneUndoTargets(requireFn) {
    const cache = requireFn && requireFn.cache;
    if (!cache || typeof cache !== 'object') return [];
    const targets = [];
    for (const filename of Object.keys(cache)) {
        if (!SCENE_UNDO_PATH.test(filename)) continue;
        const mod = cache[filename], exports = mod && mod.exports;
        if (!exports || (typeof exports !== 'object' && typeof exports !== 'function')) continue;
        const candidates = [exports];
        try {
            for (const key of Object.getOwnPropertyNames(exports)) {
                let descriptor;
                try { descriptor = Object.getOwnPropertyDescriptor(exports, key); } catch (_) { continue; }
                candidates.push(descriptor && descriptor.value);
            }
        } catch (_) {}
        const seen = new Set();
        for (const ctor of candidates) {
            if (typeof ctor !== 'function' || ctor.name !== 'SceneUndoManager' || seen.has(ctor)) continue;
            seen.add(ctor);
            const prototype = ctor.prototype;
            const descriptor = prototype && Object.getOwnPropertyDescriptor(prototype, 'snapshot');
            const recordDescriptor = prototype && Object.getOwnPropertyDescriptor(prototype, 'record');
            if (descriptor && typeof descriptor.value === 'function')
                targets.push({filename, ctor, prototype, descriptor, recordDescriptor});
        }
    }
    return targets;
}

function safeError(error) {
    return {name: boundedText(error && error.name || 'Error', 96),
        messageLength: boundedText(error && error.message || '', 512).length};
}

function install(options = {}) {
    const realm = options.realm || globalThis;
    const requireFn = options.requireFn || require;
    const targets = sceneUndoTargets(requireFn);
    const records = [];
    if (targets.length !== 1) return {
        installed: false, reason: targets.length ? 'ambiguous-loaded-scene-undo-manager' : 'scene-undo-manager-not-loaded',
        targetCount: targets.length, summary: () => ({installed: false, reason: targets.length ?
            'ambiguous-loaded-scene-undo-manager' : 'scene-undo-manager-not-loaded', records: records.slice()}),
        uninstall() {},
    };
    const target = targets[0], {prototype, descriptor, recordDescriptor} = target;
    const originalSnapshot = descriptor.value;
    const originalRecord = recordDescriptor && recordDescriptor.value;
    const originalSource = (() => {
        try { return Function.prototype.toString.call(originalSnapshot).slice(0, 6000); }
        catch (_) { return '<source-unavailable>'; }
    })();
    const undoMethods = describeUndoMethods(prototype, options.maxUndoMethods || 32,
        options.maxUndoMethodSourceLength || 2500);
    const observeSnapshots = options.observeSnapshots !== false && options.recordOnly !== true;
    let installed = false, recordHookInstalled = false, snapshotHookInstalled = false, activeDepth = 0;
    const activeOwnedScopes = new WeakMap();
    const append = record => {
        records.push(record);
        if (typeof options.onRecord === 'function') {
            try { options.onRecord(record); } catch (_) { /* diagnostics never affect Editor behavior */ }
        }
    };
    const wrappedSnapshot = function (...args) {
        const record = {
            event: 'scene-undo-snapshot', modulePath: boundedText(target.filename, 512),
            constructorName: target.ctor.name, snapshotSource: originalSource,
            receiver: describeValue(this, realm), args: args.slice(0, 16).map(value => describeValue(value, realm)),
            receiverUndoFields: describeManagerFields(this, options.maxUndoFields || 32),
            argsTruncated: args.length > 16, stringifyInputs: [], stringifyHookInstalled: false,
            asynchronousSnapshotUnsupported: false, error: null,
        };
        if (activeDepth > 0) {
            record.nestedSnapshot = true;
            let nestedResult;
            try { nestedResult = Reflect.apply(originalSnapshot, this, args); }
            catch (error) { record.error = safeError(error); throw error; }
            finally { append(record); }
            if (nestedResult && (typeof nestedResult === 'object' || typeof nestedResult === 'function')) {
                try { record.asynchronousSnapshotUnsupported = typeof nestedResult.then === 'function'; }
                catch (_) { record.thenableCheckFailed = true; }
            }
            return nestedResult;
        }
        const json = realm && realm.JSON;
        const stringifyDescriptor = json && Object.getOwnPropertyDescriptor(json, 'stringify');
        const originalStringify = stringifyDescriptor && stringifyDescriptor.value;
        let jsonHookInstalled = false;
        activeDepth++;
        try {
            if (typeof originalStringify === 'function' && stringifyDescriptor &&
                (stringifyDescriptor.writable || stringifyDescriptor.configurable)) {
                const stringifyProxy = new Proxy(originalStringify, {apply(fn, thisArg, stringifyArgs) {
                    if (record.stringifyInputs.length < 64) {
                        let stats;
                        try { stats = summarizeStructure(stringifyArgs[0], realm, options.limits); }
                        catch (error) { stats = {diagnosticError: safeError(error)}; }
                        record.stringifyInputs.push({input: describeValue(stringifyArgs[0], realm), stats,
                            replacerType: typeof stringifyArgs[1], spaceType: typeof stringifyArgs[2]});
                    } else record.stringifyInputCallCountCapped = true;
                    return Reflect.apply(fn, thisArg, stringifyArgs);
                }});
                Object.defineProperty(json, 'stringify', {...stringifyDescriptor, value: stringifyProxy});
                jsonHookInstalled = true;
                record.stringifyHookInstalled = true;
            } else record.stringifyHookUnavailable = true;
            let result;
            try { result = Reflect.apply(originalSnapshot, this, args); }
            catch (error) { record.error = safeError(error); throw error; }
            if (result && (typeof result === 'object' || typeof result === 'function')) {
                try { record.asynchronousSnapshotUnsupported = typeof result.then === 'function'; }
                catch (_) { record.thenableCheckFailed = true; }
            }
            return result;
        } finally {
            if (jsonHookInstalled) Object.defineProperty(json, 'stringify', stringifyDescriptor);
            activeDepth--;
            append(record);
        }
    };

    const wrappedRecord = function (...args) {
        const uuid = args[0];
        let resolved = null;
        if (typeof uuid === 'string') {
            const scopes = activeOwnedScopes.get(this) || [];
            for (let index = scopes.length - 1; index >= 0; index--) {
                const scope = scopes[index];
                if (scope.closed) continue;
                try { resolved = scope.resolveUuid(uuid); } catch (_) { resolved = null; }
                if (resolved && scope.isOwnedObject(resolved, uuid)) {
                    // Remove a constructor-time record if the Node only became
                    // a descendant of an explicitly owned root after creation.
                    scope.cleanupOwnedUuid(uuid);
                    scope.suppressedRecordCount++;
                    scope.suppressedUuids.add(uuid);
                    return undefined;
                }
            }
        }
        return Reflect.apply(originalRecord, this, args);
    };

    try {
        if (recordDescriptor && typeof originalRecord === 'function') {
            Object.defineProperty(prototype, 'record', {...recordDescriptor, value: wrappedRecord});
            recordHookInstalled = true;
        }
        if (observeSnapshots) {
            Object.defineProperty(prototype, 'snapshot', {...descriptor, value: wrappedSnapshot});
            snapshotHookInstalled = true;
        }
        installed = true;
    } catch (error) {
        try { if (snapshotHookInstalled && prototype.snapshot === wrappedSnapshot) Object.defineProperty(prototype, 'snapshot', descriptor); } catch (_) {}
        try { if (recordHookInstalled && prototype.record === wrappedRecord) Object.defineProperty(prototype, 'record', recordDescriptor); } catch (_) {}
        return {installed: false, reason: 'scene-undo-method-not-patchable', targetPath: target.filename,
            diagnosticError: safeError(error), summary: () => ({installed: false,
                reason: 'scene-undo-method-not-patchable', targetPath: target.filename}), uninstall() {}};
    }

    function beginOwnedImportScope(manager, resolveUuid, isValidObject = null) {
        if (!installed || !recordHookInstalled) throw new Error('CREATOR_UNDO_OWNED_SCOPE_RECORD_HOOK_UNAVAILABLE');
        if (!manager || !prototype.isPrototypeOf(manager)) throw new Error('CREATOR_UNDO_OWNED_SCOPE_MANAGER_MISMATCH');
        if (typeof resolveUuid !== 'function') throw new Error('CREATOR_UNDO_OWNED_SCOPE_RESOLVER_REQUIRED');
        if (!Array.isArray(manager.records)) throw new Error('CREATOR_UNDO_OWNED_SCOPE_RECORDS_UNAVAILABLE');

        const baselineRecords = new Set(manager.records.filter(value => typeof value === 'string'));
        const baselineRecordPositions = new Map();
        manager.records.forEach((value, index) => {
            if (typeof value !== 'string') return;
            const indices = baselineRecordPositions.get(value) || [];
            if (indices.length < 8) indices.push(index);
            baselineRecordPositions.set(value, indices);
        });
        const getDumpMap = () => {
            try {
                const descriptor = Object.getOwnPropertyDescriptor(manager, '_uuidDumpMap');
                return descriptor && Object.prototype.hasOwnProperty.call(descriptor, 'value') &&
                    descriptor.value && typeof descriptor.value === 'object' && !Array.isArray(descriptor.value) ?
                    descriptor.value : null;
            } catch (_) { return null; }
        };
        const initialDumpMap = getDumpMap();
        const baselineDumpKeys = new Set();
        if (initialDumpMap) {
            try {
                if (initialDumpMap instanceof Map) for (const key of initialDumpMap.keys()) baselineDumpKeys.add(key);
                else for (const key of Object.keys(initialDumpMap)) baselineDumpKeys.add(key);
            } catch (_) {}
        }
        if (isValidObject !== null && typeof isValidObject !== 'function')
            throw new Error('CREATOR_UNDO_OWNED_SCOPE_VALIDITY_CALLBACK_INVALID');
        const scope = {manager, resolveUuid, isValidObject, baselineRecords, baselineRecordPositions, baselineDumpKeys,
            ownedObjects: new WeakSet(), ownedUuids: new Set(), ownedObjectByUuid: new Map(),
            pendingObjects: new Map(), pendingOwnerRoots: new Map(), ownedRoots: new Set(), ownedRootObjects: new Map(), suppressedUuids: new Set(),
            suppressedRecordCount: 0, preRegistrationRecordRemovals: 0, preRegistrationDumpRemovals: 0,
            dynamicOwnedDiscoveries: 0, preexistingOwnedMatches: 0, pendingIdentityConflicts: 0,
            pendingUnresolvedAtFinish: 0, pendingDestroyedOwnedCleanupCount: 0,
            pendingDestroyedOwnedUnverifiedCount: 0,
            closed: false};
        let scopes = activeOwnedScopes.get(manager);
        if (!scopes) { scopes = []; activeOwnedScopes.set(manager, scopes); }
        scopes.push(scope);

        const objectUuid = object => {
            try { return object && typeof object.uuid === 'string' && object.uuid.length ? object.uuid : null; }
            catch (_) { return null; }
        };
        const safeIdentityText = (object, key, limit = 96) => {
            try { return object && typeof object[key] === 'string' ? object[key].slice(0, limit) : null; }
            catch (_) { return null; }
        };
        const objectIdentity = object => {
            if (!object) return null;
            let constructor = null;
            try { constructor = object.constructor && typeof object.constructor.name === 'string' ? object.constructor.name.slice(0, 96) : null; } catch (_) {}
            const isNode = looksLikeNode(object);
            let node = isNode ? object : null;
            if (!node) { try { node = object.node || null; } catch (_) {} }
            const chain = [], visited = new Set();
            for (let current = node; current && !visited.has(current) && chain.length < 12; current = current.parent) {
                visited.add(current);
                chain.push({name: safeIdentityText(current, 'name'), uuid: objectUuid(current)});
            }
            let truncated = false;
            if (node && chain.length === 12) {
                try { truncated = !!node.parent; } catch (_) {}
            }
            return {kind: isNode ? 'Node' : node ? 'Component' : 'Object', constructor,
                uuid: objectUuid(object), name: safeIdentityText(object, 'name'),
                nodeUuid: node ? objectUuid(node) : null, parentPath: chain.reverse(), parentPathTruncated: truncated};
        };
        const registrationMismatch = (phase, root, object, resolved) => {
            const rootInfo = objectIdentity(root), objectInfo = objectIdentity(object), resolvedInfo = objectIdentity(resolved);
            return new Error('CREATOR_UNDO_OWNED_OBJECT_NOT_REGISTERED_BY_UUID:' + JSON.stringify({phase,
                root: rootInfo, object: objectInfo, resolved: resolvedInfo,
                sameObject: !!object && object === resolved,
                requestedUuid: objectUuid(object), resolvedUuid: objectUuid(resolved)}));
        };
        const summarizeDumpValue = value => {
            if (value === null) return {type: 'null'};
            if (value === undefined) return {type: 'undefined'};
            const summary = {type: typeof value};
            try { summary.className = value && value.constructor && value.constructor.name || null; } catch (_) {}
            if (typeof value === 'object') {
                try { summary.ownKeyCount = Object.getOwnPropertyNames(value).length; } catch (_) {}
                if (Array.isArray(value)) summary.length = value.length;
            }
            return summary;
        };
        const preexistingUuidError = (phase, uuid, object, root = null) => {
            let currentRecords = [];
            try {
                for (let index = 0; index < manager.records.length && currentRecords.length < 8; index++)
                    if (manager.records[index] === uuid) currentRecords.push(index);
            } catch (_) {}
            const dumpMap = getDumpMap();
            let currentDumpPresent = false, currentDumpDescriptor = null, currentDumpValue;
            try {
                if (dumpMap instanceof Map) {
                    currentDumpPresent = dumpMap.has(uuid);
                    if (currentDumpPresent) currentDumpValue = dumpMap.get(uuid);
                } else if (dumpMap) {
                    currentDumpDescriptor = Object.getOwnPropertyDescriptor(dumpMap, uuid) || null;
                    currentDumpPresent = !!currentDumpDescriptor;
                    if (currentDumpDescriptor && Object.prototype.hasOwnProperty.call(currentDumpDescriptor, 'value'))
                        currentDumpValue = currentDumpDescriptor.value;
                }
            } catch (_) {}
            let resolved = null, resolverError = null;
            try { resolved = scope.resolveUuid(uuid); }
            catch (error) { resolverError = safeError(error); }
            const diagnostic = {phase, uuid,
                root: objectIdentity(root), object: objectIdentity(object),
                resolver: objectIdentity(resolved), resolverSameObject: !!resolved && resolved === object,
                baseline: {recordMatched: scope.baselineRecords.has(uuid),
                    recordPositions: scope.baselineRecordPositions.get(uuid) || [],
                    dumpKeyMatched: scope.baselineDumpKeys.has(uuid)},
                current: {recordCount: Array.isArray(manager.records) ? manager.records.length : null,
                    recordPositions: currentRecords, dumpMapClass: dumpMap && dumpMap.constructor && dumpMap.constructor.name || null,
                    dumpKeyPresent: currentDumpPresent, dumpDescriptor: currentDumpDescriptor ? {
                        data: Object.prototype.hasOwnProperty.call(currentDumpDescriptor, 'value'),
                        configurable: currentDumpDescriptor.configurable === true,
                        enumerable: currentDumpDescriptor.enumerable === true,
                        writable: currentDumpDescriptor.writable === true,
                    } : null, dumpValue: currentDumpPresent ? summarizeDumpValue(currentDumpValue) : null},
                scope: {baselineRecordCount: scope.baselineRecords.size, baselineDumpKeyCount: scope.baselineDumpKeys.size,
                    ownedUuidCount: scope.ownedUuids.size, pendingObjectCount: scope.pendingObjects.size},
                resolverError};
            return new Error('CREATOR_UNDO_OWNED_UUID_PREEXISTING:' + JSON.stringify(diagnostic));
        };

        const removeOwnedResidue = uuid => {
            if (scope.baselineRecords.has(uuid) || scope.baselineDumpKeys.has(uuid)) return;
            for (let index = manager.records.length - 1; index >= 0; index--) {
                if (manager.records[index] !== uuid) continue;
                manager.records.splice(index, 1);
                scope.preRegistrationRecordRemovals++;
            }
            const currentDumpMap = getDumpMap();
            if (currentDumpMap) {
                const hasDump = currentDumpMap instanceof Map ? currentDumpMap.has(uuid) :
                    Object.prototype.hasOwnProperty.call(currentDumpMap, uuid);
                if (hasDump) {
                    if (currentDumpMap instanceof Map) currentDumpMap.delete(uuid);
                    else delete currentDumpMap[uuid];
                    scope.preRegistrationDumpRemovals++;
                }
            }
        };
        const adoptResolvedObject = (object, uuid, strict = true) => {
            if (scope.closed) throw new Error('CREATOR_UNDO_OWNED_SCOPE_CLOSED');
            if (!object || (typeof object !== 'object' && typeof object !== 'function'))
                { if (strict) throw new Error('CREATOR_UNDO_OWNED_OBJECT_INVALID'); return false; }
            if (!uuid || objectUuid(object) !== uuid)
                { if (strict) throw new Error('CREATOR_UNDO_OWNED_OBJECT_UUID_REQUIRED'); return false; }
            if (scope.baselineRecords.has(uuid) || scope.baselineDumpKeys.has(uuid))
                { if (strict) throw preexistingUuidError('adoptResolvedObject', uuid, object); return false; }
            const priorOwned = scope.ownedObjectByUuid.get(uuid);
            const priorPending = scope.pendingObjects.get(uuid);
            if ((priorOwned && priorOwned !== object) || (priorPending && priorPending !== object)) {
                if (strict) throw new Error('CREATOR_UNDO_OWNED_UUID_IDENTITY_CONFLICT');
                scope.pendingIdentityConflicts++;
                return false;
            }
            let resolved;
            try { resolved = scope.resolveUuid(uuid); } catch (_) {}
            if (resolved !== object) {
                if (strict) throw registrationMismatch('registerOwnedObject', null, object, resolved);
                return false;
            }

            scope.ownedObjects.add(object);
            scope.ownedUuids.add(uuid);
            scope.ownedObjectByUuid.set(uuid, object);
            if (scope.pendingObjects.get(uuid) === object) {
                scope.pendingObjects.delete(uuid);
                scope.pendingOwnerRoots.delete(uuid);
            }
            removeOwnedResidue(uuid);
            return true;
        };
        const stageOwnedObject = (object, strict = true, phase = 'registerOwnedRoot.stage', owningRoot = null) => {
            if (scope.closed) throw new Error('CREATOR_UNDO_OWNED_SCOPE_CLOSED');
            if (!object || (typeof object !== 'object' && typeof object !== 'function'))
                { if (strict) throw new Error('CREATOR_UNDO_OWNED_OBJECT_INVALID'); return false; }
            const uuid = objectUuid(object);
            if (!uuid) { if (strict) throw new Error('CREATOR_UNDO_OWNED_OBJECT_UUID_REQUIRED'); return false; }
            if (scope.baselineRecords.has(uuid) || scope.baselineDumpKeys.has(uuid))
                { if (strict) throw preexistingUuidError(phase, uuid, object); return false; }
            const priorOwned = scope.ownedObjectByUuid.get(uuid);
            const priorPending = scope.pendingObjects.get(uuid);
            if ((priorOwned && priorOwned !== object) || (priorPending && priorPending !== object)) {
                if (strict) throw new Error('CREATOR_UNDO_OWNED_UUID_IDENTITY_CONFLICT');
                scope.pendingIdentityConflicts++;
                return false;
            }
            let resolved;
            try { resolved = scope.resolveUuid(uuid); } catch (_) {}
            if (resolved && resolved !== object) {
                if (strict) throw registrationMismatch(phase, null, object, resolved);
                scope.pendingIdentityConflicts++;
                return false;
            }
            if (resolved === object) return adoptResolvedObject(object, uuid, strict);
            scope.pendingObjects.set(uuid, object);
            if (owningRoot && scope.ownedRoots.has(owningRoot)) {
                let roots = scope.pendingOwnerRoots.get(uuid);
                if (!roots) { roots = new Set(); scope.pendingOwnerRoots.set(uuid, roots); }
                roots.add(owningRoot);
            }
            return true;
        };

        const nodeComponents = node => {
            for (const key of ['_components', 'components']) {
                try { if (Array.isArray(node[key])) return node[key].slice(); } catch (_) {}
            }
            try {
                if (typeof options.enumerateNodeComponents === 'function') {
                    const values = options.enumerateNodeComponents(node);
                    if (Array.isArray(values)) return values.slice();
                }
            } catch (_) {}
            return [];
        };
        const collectRootObjects = root => {
            const objects = [], seen = new Set(), pending = [root];
            while (pending.length) {
                const node = pending.shift();
                if (!node || seen.has(node)) continue;
                seen.add(node); objects.push(node);
                for (const component of nodeComponents(node))
                    if (component && !seen.has(component)) { seen.add(component); objects.push(component); }
                let children = [];
                try { if (Array.isArray(node.children)) children = node.children.slice(); } catch (_) {}
                pending.push(...children);
            }
            return objects;
        };
        const looksLikeNode = object => {
            if (!object || typeof object !== 'object' || !objectUuid(object)) return false;
            try { return Array.isArray(object.children); } catch (_) { return false; }
        };
        const isUnderOwnedRoot = node => {
            const seen = new Set();
            for (let current = node; current && !seen.has(current); current = current.parent) {
                if (scope.ownedRoots.has(current)) return true;
                seen.add(current);
            }
            return false;
        };
        scope.cleanupOwnedUuid = removeOwnedResidue;
        scope.isOwnedObject = (object, uuid) => {
            if (objectUuid(object) !== uuid) return false;
            const priorOwned = scope.ownedObjectByUuid.get(uuid);
            const priorPending = scope.pendingObjects.get(uuid);
            if ((priorOwned && priorOwned !== object) || (priorPending && priorPending !== object)) {
                scope.pendingIdentityConflicts++;
                return false;
            }
            if (scope.ownedObjects.has(object)) return true;
            let node = null;
            if (looksLikeNode(object)) node = object;
            else { try { node = object && object.node; } catch (_) {} }
            if (!isUnderOwnedRoot(node)) return false;
            if (scope.baselineRecords.has(uuid) || scope.baselineDumpKeys.has(uuid)) {
                scope.preexistingOwnedMatches++;
                return false;
            }
            const wasKnown = scope.ownedUuids.has(uuid);
            if (!adoptResolvedObject(object, uuid, false)) return false;
            if (!wasKnown) scope.dynamicOwnedDiscoveries++;
            return true;
        };

        const registerOwnedObject = object => {
            if (!adoptResolvedObject(object, objectUuid(object), true))
                throw new Error('CREATOR_UNDO_OWNED_OBJECT_REGISTRATION_FAILED');
            return {registered: true};
        };
        const registerOwnedRoot = root => {
            if (!looksLikeNode(root)) throw new Error('CREATOR_UNDO_OWNED_ROOT_INVALID');
            const rootUuid = objectUuid(root);
            if (scope.baselineRecords.has(rootUuid) || scope.baselineDumpKeys.has(rootUuid))
                throw preexistingUuidError('registerOwnedRoot.root', rootUuid, root, root);
            const objects = collectRootObjects(root);
            // Validate the entire current tree before mutating the ownership set.
            // Existing baseline objects remain outside this import scope.
            for (const object of objects) {
                const uuid = objectUuid(object);
                if (!uuid || scope.baselineRecords.has(uuid) || scope.baselineDumpKeys.has(uuid)) continue;
                const priorOwned = scope.ownedObjectByUuid.get(uuid);
                const priorPending = scope.pendingObjects.get(uuid);
                if ((priorOwned && priorOwned !== object) || (priorPending && priorPending !== object))
                    throw new Error('CREATOR_UNDO_OWNED_UUID_IDENTITY_CONFLICT');
                let resolved;
                try { resolved = scope.resolveUuid(uuid); } catch (_) {}
                if (resolved && resolved !== object)
                    throw registrationMismatch('registerOwnedRoot.preflight', root, object, resolved);
                if (scope.ownedUuids.has(uuid) && scope.ownedObjectByUuid.get(uuid) !== object)
                    throw new Error('CREATOR_UNDO_OWNED_UUID_IDENTITY_CONFLICT');
            }
            scope.ownedRoots.add(root);
            scope.ownedRootObjects.set(root, new Set(objects));
            let pendingCount = 0;
            for (const object of objects) {
                const uuid = objectUuid(object);
                if (!uuid || scope.baselineRecords.has(uuid) || scope.baselineDumpKeys.has(uuid)) continue;
                stageOwnedObject(object, true, 'registerOwnedRoot.stage', root);
                if (scope.pendingObjects.get(uuid) === object) pendingCount++;
            }
            return {registered: true, objectCount: objects.filter(object => {
                const uuid = objectUuid(object); return uuid && scope.ownedUuids.has(uuid);
            }).length, pendingObjectCount: pendingCount};
        };

        const retireDestroyedOwnedRoot = (root, capturedEntries) => {
            const rejected = reason => ({retired:false,reason,retiredObjectCount:0});
            if (scope.closed) return rejected('scope-closed');
            if (!scope.ownedRoots.has(root)) return rejected('root-not-registered-by-this-scope');
            if (!Array.isArray(capturedEntries)) return rejected('captured-object-list-required');
            const rootEntry = capturedEntries.find(entry => entry && entry.kind === 'node' && entry.object === root);
            const rootUuid = rootEntry && rootEntry.uuid;
            if (typeof rootUuid !== 'string' || !rootUuid) return rejected('captured-root-uuid-missing');
            const eligible = [], seen = new Set();
            for (const entry of capturedEntries) {
                if (!entry || !['node','component'].includes(entry.kind) || typeof entry.uuid !== 'string' || !entry.uuid ||
                    !entry.object || typeof entry.object !== 'object') return rejected('captured-entry-invalid');
                const key = entry.kind + ':' + entry.uuid;
                if (seen.has(key)) return rejected('captured-entry-duplicate');
                seen.add(key);
                const currentUuid = objectUuid(entry.object);
                if (currentUuid && currentUuid !== entry.uuid) return rejected('captured-object-uuid-changed');
                if (scope.baselineRecords.has(entry.uuid) || scope.baselineDumpKeys.has(entry.uuid))
                    return rejected('baseline-uuid-protected');
                const mapped = scope.ownedObjectByUuid.get(entry.uuid) === entry.object ||
                    scope.pendingObjects.get(entry.uuid) === entry.object;
                if (!mapped) continue; // This scope never adopted this captured object identity.
                try {
                    if (!scope.isValidObject || scope.isValidObject(entry.object, true) !== false)
                        return rejected('strict-destroyed-state-unverified');
                    if (scope.resolveUuid(entry.uuid) !== null)
                        return rejected('resolver-still-resolves-or-foreign');
                } catch (_) { return rejected('validity-or-resolver-query-failed'); }
                eligible.push(entry);
            }
            if (!eligible.some(entry => entry.kind === 'node' && entry.object === root && entry.uuid === rootUuid))
                return rejected('owned-root-identity-not-adopted');

            for (const entry of eligible) {
                removeOwnedResidue(entry.uuid);
                if (scope.ownedObjectByUuid.get(entry.uuid) === entry.object) {
                    scope.ownedObjectByUuid.delete(entry.uuid);
                    scope.ownedUuids.delete(entry.uuid);
                    scope.ownedObjects.delete(entry.object);
                }
                if (scope.pendingObjects.get(entry.uuid) === entry.object) {
                    scope.pendingObjects.delete(entry.uuid);
                    scope.pendingOwnerRoots.delete(entry.uuid);
                }
                if (scope.ownedRoots.has(entry.object)) {
                    scope.ownedRoots.delete(entry.object);
                    scope.ownedRootObjects.delete(entry.object);
                }
                for (const [registeredRoot, members] of scope.ownedRootObjects)
                    if (members.has(entry.object)) members.delete(entry.object);
            }
            scope.ownedRoots.delete(root);
            scope.ownedRootObjects.delete(root);
            return {retired:true,reason:null,retiredObjectCount:eligible.length,
                retiredUuids:eligible.map(entry=>entry.uuid).slice(0,64)};
        };

        const finish = () => {
            if (scope.closed) return summary();
            // Sweep the final descendants/components so constructor-time
            // records are removed even when no later record() call occurred.
            for (const root of scope.ownedRoots)
                for (const object of collectRootObjects(root)) stageOwnedObject(object, false, 'finish.finalSweep', root);
            // Constructor-time records can outlive resolver registration when a
            // generated subtree is destroyed before the end of the import. Only
            // purge residue for exact, explicitly-owned identities whose owning
            // registered root and object are both strictly destroyed.
            for (const [uuid, object] of [...scope.pendingObjects]) {
                let cleared = false;
                try {
                    const roots = scope.pendingOwnerRoots.get(uuid);
                    const hasExactDestroyedRoot = roots instanceof Set && [...roots].some(root => {
                        if (!scope.ownedRoots.has(root) || !objectUuid(root)) return false;
                        return scope.isValidObject && scope.isValidObject(root, true) === false;
                    });
                    if (scope.isValidObject && objectUuid(object) === uuid && hasExactDestroyedRoot &&
                        scope.isValidObject(object, true) === false &&
                        !scope.baselineRecords.has(uuid) && !scope.baselineDumpKeys.has(uuid)) {
                        const resolved = scope.resolveUuid(uuid);
                        if (resolved === null) {
                            removeOwnedResidue(uuid);
                            scope.pendingObjects.delete(uuid);
                            scope.pendingOwnerRoots.delete(uuid);
                            scope.pendingDestroyedOwnedCleanupCount++;
                            cleared = true;
                        }
                    }
                } catch (_) { /* query/validity errors remain unresolved and untouched */ }
                if (!cleared) scope.pendingDestroyedOwnedUnverifiedCount++;
            }
            scope.pendingUnresolvedAtFinish = scope.pendingObjects.size;
            scope.closed = true;
            const current = activeOwnedScopes.get(manager) || [];
            const index = current.lastIndexOf(scope);
            if (index >= 0) current.splice(index, 1);
            if (!current.length) activeOwnedScopes.delete(manager);
            return summary();
        };
        const summary = () => ({ownedObjectCount: scope.ownedUuids.size, ownedRootCount: scope.ownedRoots.size,
            suppressedRecordCount: scope.suppressedRecordCount,
            suppressedUuidCount: scope.suppressedUuids.size,
            dynamicOwnedDiscoveries: scope.dynamicOwnedDiscoveries,
            preexistingOwnedMatches: scope.preexistingOwnedMatches,
            pendingOwnedObjectCount: scope.pendingObjects.size,
            pendingUnresolvedAtFinish: scope.pendingUnresolvedAtFinish,
            pendingDestroyedOwnedCleanupCount: scope.pendingDestroyedOwnedCleanupCount,
            pendingDestroyedOwnedUnverifiedCount: scope.pendingDestroyedOwnedUnverifiedCount,
            pendingIdentityConflicts: scope.pendingIdentityConflicts,
            preRegistrationRecordRemovals: scope.preRegistrationRecordRemovals,
            preRegistrationDumpRemovals: scope.preRegistrationDumpRemovals,
            baselineRecordCount: baselineRecords.size, baselineDumpKeyCount: baselineDumpKeys.size,
            closed: scope.closed});
        return {registerOwnedObject, registerOwnedRoot, retireDestroyedOwnedRoot, finish, summary};
    }
    return {
        installed: true, targetPath: target.filename, constructorName: target.ctor.name,
        ownedRecordIsolationAvailable: recordHookInstalled,
        snapshotDiagnosticsAvailable: snapshotHookInstalled,
        beginOwnedImportScope,
        snapshotSource: originalSource, undoMethods,
        summary: () => ({installed, targetPath: target.filename, constructorName: target.ctor.name,
            ownedRecordIsolationAvailable: recordHookInstalled,
            snapshotDiagnosticsAvailable: snapshotHookInstalled,
            snapshotSource: originalSource, undoMethods, recordCount: records.length, records: records.slice()}),
        uninstall() {
            if (!installed) return;
            if (snapshotHookInstalled && prototype.snapshot !== wrappedSnapshot)
                throw new Error('CREATOR_UNDO_DIAGNOSTIC_HOOK_REPLACED');
            if (recordHookInstalled && prototype.record !== wrappedRecord)
                throw new Error('CREATOR_UNDO_RECORD_DIAGNOSTIC_HOOK_REPLACED');
            if (snapshotHookInstalled) Object.defineProperty(prototype, 'snapshot', descriptor);
            if (recordHookInstalled) Object.defineProperty(prototype, 'record', recordDescriptor);
            recordHookInstalled = false;
            snapshotHookInstalled = false;
            installed = false;
        },
    };
}

module.exports = {install, summarizeStructure, describeValue, describeManagerFields, describeUndoMethods};
