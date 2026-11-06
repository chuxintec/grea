'use strict';

// Owns only the temporary Scene instance loaded for Creator saved-scene
// readback. It never releases the SceneAsset or its dependencies.
function fail(code, message, details = {}) {
    let detailText = '';
    try {
        detailText = JSON.stringify(details);
        if (detailText.length > 768) detailText = detailText.slice(0, 768) + '…';
    } catch (_) { detailText = '{\"details\":\"unserializable\"}'; }
    const error = new Error(code + (message ? ': ' + message : '') + (detailText && detailText !== '{}' ? ' ' + detailText : ''));
    error.code = code;
    error.details = details;
    return error;
}

const retiredOwnedObjects = new Map();
const MAX_RETIRED_OWNED_OBJECTS = 50000;

function objectKey(kind, uuid) { return kind + ':' + uuid; }

function sceneNodes(root) {
    const out = [];
    const seen = new Set();
    const visit = node => {
        if (!node || seen.has(node)) return;
        seen.add(node);
        out.push(node);
        const children = Array.isArray(node.children) ? node.children :
            Array.isArray(node._children) ? node._children : [];
        for (const child of children) visit(child);
    };
    visit(root);
    return out;
}

function currentSceneGuard(scene, asset, cc, cce) {
    const director = cc && cc.director;
    if (!director || typeof director.getScene !== 'function')
        throw fail('CREATOR_SAVED_SCENE_DIRECTOR_UNAVAILABLE');
    if (director.getScene() === scene)
        throw fail('CREATOR_SAVED_SCENE_IS_DIRECTOR_SCENE', '', {uuid: scene.uuid || null});

    const manager = cce && cce.SceneFacadeManager;
    const fsm = manager && manager._facadeFSM;
    const state = fsm && fsm.currentState;
    if (!state || state.modeName !== 'general')
        throw fail('CREATOR_SAVED_SCENE_GENERAL_FACADE_NOT_CURRENT', '', {
            modeName: state && typeof state.modeName === 'string' ? state.modeName : null,
        });
    const general = fsm.generalSceneFacade;
    if (!general || typeof general.queryCurrentSceneUuid !== 'function')
        throw fail('CREATOR_SAVED_SCENE_CURRENT_UUID_API_UNAVAILABLE');
    const currentUuid = general.queryCurrentSceneUuid();
    if (typeof currentUuid !== 'string')
        throw fail('CREATOR_SAVED_SCENE_CURRENT_UUID_INVALID', '', {
            valueType: currentUuid === null ? 'null' : typeof currentUuid,
            valueClass: currentUuid && currentUuid.constructor && currentUuid.constructor.name || null,
        });
    if (currentUuid === asset._uuid)
        throw fail('CREATOR_SAVED_SCENE_IS_EDITOR_SCENE', '', {uuid: currentUuid});
}

function safeFunctionSource(value, maxLength = 1000) {
    if (typeof value !== 'function') return {type: typeof value};
    let source = '';
    try { source = Function.prototype.toString.call(value); }
    catch (error) { source = '[toString failed: ' + String(error && error.name || 'Error') + ']'; }
    return {name: value.name || '', length: source.length,
        source: source.length > maxLength ? source.slice(0, maxLength) + '…' : source};
}

function shortName(value) {
    try { return value && value.constructor && String(value.constructor.name || '').slice(0, 96) || null; }
    catch (_) { return null; }
}

function valueShape(value) {
    if (value === null) return {type: 'null'};
    if (value === undefined) return {type: 'undefined'};
    const type = typeof value;
    const out = {type, className: shortName(value)};
    if (type !== 'object') return out;
    if (Array.isArray(value)) out.length = value.length;
    try { if (Number.isFinite(value.size)) out.size = value.size; } catch (_) {}
    try { out.ownKeyCount = Object.getOwnPropertyNames(value).length; } catch (_) {}
    return out;
}

function keyNames(object, limit = 32) {
    try { return Object.getOwnPropertyNames(object).slice(0, limit).map(x => String(x).slice(0, 96)); }
    catch (_) { return []; }
}

function currentGeneral(cce) {
    const fsm = cce && cce.SceneFacadeManager && cce.SceneFacadeManager._facadeFSM;
    if (!fsm || !fsm.currentState || fsm.currentState.modeName !== 'general') return null;
    return fsm.generalSceneFacade || null;
}

function recycleInfo(general, kind, uuid, object) {
    const field = kind === 'node' ? '_recycleNode' : '_recycleComponent';
    const method = kind === 'node' ? 'queryRecycleNode' : 'queryRecycleComponent';
    let cache, ownerDescriptor, entryDescriptor, recycleResult;
    try {
        ownerDescriptor = Object.getOwnPropertyDescriptor(general, field);
        cache = ownerDescriptor && Object.prototype.hasOwnProperty.call(ownerDescriptor, 'value') ? ownerDescriptor.value : null;
        entryDescriptor = cache && Object.getOwnPropertyDescriptor(cache, uuid);
        recycleResult = general && typeof general[method] === 'function' ? general[method](uuid) : undefined;
    } catch (_) { return {field, method, inspectError: true}; }
    return {field, method,
        ownerOwn: !!ownerDescriptor,
        ownerData: !!ownerDescriptor && Object.prototype.hasOwnProperty.call(ownerDescriptor, 'value'),
        ownerClass: shortName(cache),
        entryOwn: !!entryDescriptor,
        entryData: !!entryDescriptor && Object.prototype.hasOwnProperty.call(entryDescriptor, 'value'),
        entryConfigurable: !!entryDescriptor && entryDescriptor.configurable === true,
        entryEnumerable: !!entryDescriptor && entryDescriptor.enumerable === true,
        entryWritable: !!entryDescriptor && entryDescriptor.writable === true,
        entrySameObject: !!entryDescriptor && entryDescriptor.value === object,
        queryRecycleSameObject: recycleResult === object,
        queryRecycleShape: valueShape(recycleResult)};
}

// Runtime fallback for opaque .ccc bundle inspection. Keep required evidence
// first and bound by structure, so the emitted JSON stays valid and useful.
function runtimeCacheDiagnostic(kind, uuid, cce, editorExtends, manager, managerAfter, queryAfter, object = null) {
    const fsm = cce && cce.SceneFacadeManager && cce.SceneFacadeManager._facadeFSM;
    const general = fsm && fsm.generalSceneFacade;
    const managerProto = manager && Object.getPrototypeOf(manager);
    const queryFn = kind === 'node' ? cce && cce.Node && cce.Node.query : cce && cce.Component && cce.Component.query;
    const method = kind === 'node' ? 'queryRecycleNode' : 'queryRecycleComponent';
    const cacheField = kind === 'node' ? '_recycleNode' : '_recycleComponent';
    return {
        schema: 'creator-saved-scene-manager-runtime-diagnostic/v2', kind, uuid: String(uuid || '').slice(0, 128),
        activeMode: fsm && fsm.currentState && fsm.currentState.modeName || null,
        managerClass: shortName(manager),
        managerQuerySource: safeFunctionSource(manager && manager.query, 1600),
        managerRemoveSource: safeFunctionSource(manager && manager.remove, 1600),
        managerOwnKeys: keyNames(manager, 48), managerPrototypeKeys: keyNames(managerProto, 64),
        managerAfter: valueShape(managerAfter),
        cceQuerySource: safeFunctionSource(queryFn, 1000), cceAfter: valueShape(queryAfter),
        facadeRecycleQuerySource: safeFunctionSource(general && general[method], 1600),
        facadeRecycleOtherQuerySource: safeFunctionSource(general && general[kind === 'node' ? 'queryRecycleComponent' : 'queryRecycleNode'], 600),
        facadeOwnKeys: keyNames(general, 48), cacheField,
        cache: recycleInfo(general, kind, uuid, object),
    };
}

function emitRuntimeCacheDiagnostic(diagnostic) {
    let serialized;
    try { serialized = JSON.stringify(diagnostic); }
    catch (_) { serialized = '{"schema":"creator-saved-scene-manager-runtime-diagnostic/v2","serializationFailed":true}'; }
    // Do not truncate JSON text. Drop only lower-priority source material.
    if (serialized.length > 10000) {
        diagnostic.facadeRecycleOtherQuerySource = undefined;
        diagnostic.cceQuerySource = undefined;
        serialized = JSON.stringify(diagnostic);
    }
    if (serialized.length > 10000) {
        diagnostic.managerOwnKeys = (diagnostic.managerOwnKeys || []).slice(0, 16);
        diagnostic.managerPrototypeKeys = (diagnostic.managerPrototypeKeys || []).slice(0, 16);
        diagnostic.facadeOwnKeys = (diagnostic.facadeOwnKeys || []).slice(0, 16);
        serialized = JSON.stringify(diagnostic);
    }
    try {
        const logger = globalThis.console;
        if (logger && typeof logger.log === 'function')
            logger.log('[CREATOR_SAVED_SCENE_MANAGER_RUNTIME] ' + serialized);
    } catch (_) {}
}

function managerForKind(cce, kind) {
    const general = currentGeneral(cce);
    return general && general[kind === 'node' ? '_nodeMgr' : '_compMgr'] || null;
}

function removeExactOwnedTombstone(kind, uuid, resolved, cce, cc, editorExtends, guard) {
    // Destroy may clear uuid fields on Creator objects. The caller must supply
    // the exact identity/UUID pair captured before destruction; if the object
    // still exposes a UUID, it must continue to match that captured value.
    const currentUuid = resolved && (resolved.uuid || resolved._uuid);
    if (!['node', 'component'].includes(kind) || typeof uuid !== 'string' || !uuid ||
        !resolved || typeof resolved !== 'object' || (currentUuid && currentUuid !== uuid))
        return {attempted: false, removed: false, reason: 'exact-owned-identity-required'};
    if (typeof cc.isValid !== 'function' || cc.isValid(resolved, true) !== false)
        return {attempted: false, removed: false, reason: 'identity-or-destroy-state-unverified'};
    try { if (typeof guard !== 'function') throw new Error('cleanup guard required'); guard(); }
    catch (error) { return {attempted: false, removed: false, reason: 'current-scene-guard-failed', guardCode: error.code || null}; }

    const general = currentGeneral(cce);
    const manager = managerForKind(cce, kind);
    const cacheField = kind === 'node' ? '_recycleNode' : '_recycleComponent';
    const queryRecycleName = kind === 'node' ? 'queryRecycleNode' : 'queryRecycleComponent';
    const owner = kind === 'node' ? cce && cce.Node : cce && cce.Component;
    const cceQuery = owner && owner.query;
    let managerBefore, queryBefore, tombstoneBefore;
    try { managerBefore = manager && typeof manager.query === 'function' ? manager.query(uuid) : undefined; }
    catch (_) { return {attempted: false, removed: false, reason: 'manager-pre-remove-query-failed'}; }
    if (managerBefore !== resolved)
        return {attempted: false, removed: false, reason: 'manager-pre-remove-object-mismatch', managerClass: shortName(manager)};
    try { queryBefore = typeof cceQuery === 'function' ? cceQuery.call(owner, uuid) : undefined; }
    catch (_) { return {attempted: false, removed: false, reason: 'cce-pre-remove-query-failed'}; }
    if (queryBefore !== resolved)
        return {attempted: false, removed: false, reason: 'cce-pre-remove-object-mismatch'};
    if (!general || typeof general[queryRecycleName] !== 'function')
        return {attempted: false, removed: false, reason: 'recycle-query-api-unavailable'};
    try { tombstoneBefore = general[queryRecycleName](uuid); }
    catch (_) { return {attempted: false, removed: false, reason: 'recycle-query-failed'}; }
    if (tombstoneBefore !== resolved)
        return {attempted: false, removed: false, reason: 'recycle-entry-object-mismatch', recycleValue: valueShape(tombstoneBefore)};

    let cacheDescriptor, cache, entryDescriptor;
    try {
        cacheDescriptor = Object.getOwnPropertyDescriptor(general, cacheField);
        if (!cacheDescriptor || !Object.prototype.hasOwnProperty.call(cacheDescriptor, 'value'))
            return {attempted: false, removed: false, reason: 'recycle-cache-owner-not-own-data'};
        cache = cacheDescriptor.value;
        entryDescriptor = cache && Object.getOwnPropertyDescriptor(cache, uuid);
    } catch (_) { return {attempted: false, removed: false, reason: 'recycle-entry-descriptor-read-failed'}; }
    if (!entryDescriptor || !Object.prototype.hasOwnProperty.call(entryDescriptor, 'value') || entryDescriptor.value !== resolved)
        return {attempted: false, removed: false, reason: 'recycle-entry-not-exact-owned-data'};
    if (entryDescriptor.configurable !== true)
        return {attempted: false, removed: false, reason: 'recycle-entry-not-configurable'};

    let deleted = false;
    try { deleted = Reflect.deleteProperty(cache, uuid); }
    catch (_) { return {attempted: true, removed: false, reason: 'recycle-entry-delete-threw'}; }
    if (!deleted) return {attempted: true, removed: false, reason: 'recycle-entry-delete-rejected'};

    let tombstoneAfter, managerAfter, queryAfter;
    try { tombstoneAfter = general[queryRecycleName](uuid); }
    catch (_) { return {attempted: true, removed: false, reason: 'recycle-post-delete-query-failed'}; }
    try { managerAfter = manager.query(uuid); }
    catch (_) { return {attempted: true, removed: false, reason: 'manager-post-delete-query-failed'}; }
    try { queryAfter = cceQuery.call(owner, uuid); }
    catch (_) { return {attempted: true, removed: false, reason: 'cce-post-delete-query-failed', managerAfter: valueShape(managerAfter)}; }
    if (managerAfter === undefined || queryAfter === undefined ||
        (managerAfter !== null && typeof managerAfter !== 'object') || (queryAfter !== null && typeof queryAfter !== 'object'))
        return {attempted: true, removed: false, reason: 'post-delete-query-returned-invalid-value',
            managerAfter: valueShape(managerAfter), queryAfter: valueShape(queryAfter)};
    const entryAfter = Object.getOwnPropertyDescriptor(cache, uuid);
    const removed = !entryAfter && tombstoneAfter === null && managerAfter !== resolved && queryAfter !== resolved;
    const reason = !removed ? entryAfter ? 'recycle-entry-still-present' :
        tombstoneAfter !== null ? 'recycle-query-still-resolves-object' :
            managerAfter === resolved ? 'manager-still-resolves-retired-object' :
                queryAfter === resolved ? 'cce-query-still-resolves-retired-object' : 'post-delete-state-unverified' : null;
    const result = {attempted: true, removed, reason, cacheField, managerClass: shortName(manager),
        managerAfter: valueShape(managerAfter), queryAfter: valueShape(queryAfter),
        tombstoneAfter: valueShape(tombstoneAfter), entryStillOwn: !!entryAfter};
    if (!removed) emitRuntimeCacheDiagnostic(runtimeCacheDiagnostic(kind, uuid, cce, editorExtends, manager, managerAfter, queryAfter, resolved));
    return result;
}

function maybeRemoveRetiredObject(kind, uuid, resolved, cce, cc, asset, editorExtends) {
    const retired = retiredOwnedObjects.get(objectKey(kind, uuid));
    if (!retired || retired.object !== resolved || retired.sceneAssetUuid !== asset._uuid)
        return {attempted: false, removed: false, reason: !retired ? 'not-owned-by-saved-scope' : 'scope-scene-asset-mismatch'};
    return removeExactOwnedTombstone(kind, uuid, resolved, cce, cc, editorExtends,
        () => currentSceneGuard(resolved, asset, cc, cce));
}

function queryAndCheck(kind, object, cce, cc, asset, editorExtends, allowRetiredRemoval) {
    const uuid = object && (object.uuid || object._uuid);
    if (typeof uuid !== 'string' || !uuid) return null;
    const api = kind === 'node' ? cce.Node : cce.Component;
    let resolved;
    try { resolved = api.query(uuid); }
    catch (error) {
        throw fail('CREATOR_SAVED_SCENE_QUERY_FAILED', String(error && error.message || error).slice(0, 240), {kind, uuid});
    }
    if (resolved === undefined)
        throw fail('CREATOR_SAVED_SCENE_QUERY_RETURNED_UNDEFINED', '', {kind, uuid});
    if (resolved !== null && resolved !== object) {
        let removal = null;
        if (allowRetiredRemoval)
            removal = maybeRemoveRetiredObject(kind, uuid, resolved, cce, cc, asset, editorExtends);
        if (removal && removal.attempted) {
            try { resolved = api.query(uuid); }
            catch (error) {
                throw fail('CREATOR_SAVED_SCENE_QUERY_FAILED', String(error && error.message || error).slice(0, 240), {kind, uuid, phase: 'post-tombstone-delete-requery'});
            }
            if (resolved === undefined)
                throw fail('CREATOR_SAVED_SCENE_QUERY_RETURNED_UNDEFINED', '', {kind, uuid, phase: 'post-tombstone-delete-requery'});
            if (resolved === object) return resolved;
            if (resolved === null) {
                if (removal.removed) return null;
                throw fail('CREATOR_SAVED_SCENE_STALE_TOMBSTONE_NOT_CLEARED', '', {kind, uuid, removal});
            }
        }
        throw fail('CREATOR_SAVED_SCENE_UUID_OWNED_BY_OTHER_OBJECT', '', {
            kind, uuid, sameObject: false,
            resolvedClass: shortName(resolved),
            resolvedUuid: resolved && (resolved.uuid || resolved._uuid) || null,
            sceneClass: shortName(object),
            resolvedValidStrict: resolved && typeof cc.isValid === 'function' ? !!cc.isValid(resolved, true) : null,
            resolvedObjFlags: resolved && Number.isFinite(resolved._objFlags) ? resolved._objFlags : null,
            resolvedIsPriorScopeObject: !!resolved && retiredOwnedObjects.get(objectKey(kind, uuid))?.object === resolved,
            exactOwnedTombstoneRemoval: removal,
        });
    }
    return resolved;
}

function captureOwnedObjects(scene) {
    const objects = [];
    for (const node of sceneNodes(scene)) {
        if (node && (node.uuid || node._uuid)) objects.push({kind: 'node', uuid: node.uuid || node._uuid, object: node});
        const components = Array.isArray(node.components) ? node.components :
            Array.isArray(node._components) ? node._components : [];
        for (const component of components) {
            if (component && (component.uuid || component._uuid))
                objects.push({kind: 'component', uuid: component.uuid || component._uuid, object: component});
        }
    }
    return objects;
}

function verifyTreeQueries(scene, cce, cc, asset, editorExtends, allowRetiredRemoval = false) {
    if (!cce || !cce.Node || typeof cce.Node.query !== 'function' ||
        !cce.Component || typeof cce.Component.query !== 'function')
        throw fail('CREATOR_SAVED_SCENE_QUERY_API_UNAVAILABLE');
    for (const entry of captureOwnedObjects(scene))
        queryAndCheck(entry.kind, entry.object, cce, cc, asset, editorExtends, allowRetiredRemoval);
}

function validateOwnedScene(options) {
    const {asset, requestedUuid, scene, cc, cce} = options || {};
    const editorExtends = options && options.editorExtends || globalThis.EditorExtends || null;
    if (!cc || typeof cc.SceneAsset !== 'function' || !(asset instanceof cc.SceneAsset))
        throw fail('CREATOR_SAVED_SCENE_ASSET_TYPE_MISMATCH');
    if (typeof requestedUuid !== 'string' || !requestedUuid || asset._uuid !== requestedUuid)
        throw fail('CREATOR_SAVED_SCENE_ASSET_UUID_MISMATCH', '', {
            requestedUuid: requestedUuid || null, assetUuid: asset._uuid || null,
        });
    if (!scene || asset.scene !== scene)
        throw fail('CREATOR_SAVED_SCENE_ASSET_INSTANCE_MISMATCH', '', {
            sceneUuid: scene && scene.uuid || null,
            assetSceneUuid: asset.scene && asset.scene.uuid || null,
        });
    if (!cc.CCObject || typeof cc.CCObject._deferredDestroy !== 'function')
        throw fail('CREATOR_SAVED_SCENE_DEFERRED_DESTROY_UNAVAILABLE');
    if (typeof cc.isValid !== 'function')
        throw fail('CREATOR_SAVED_SCENE_ISVALID_API_UNAVAILABLE');
    currentSceneGuard(scene, asset, cc, cce);
    verifyTreeQueries(scene, cce, cc, asset, editorExtends, true);
    return {asset, requestedUuid, scene, cc, cce, editorExtends};
}

function begin(options) {
    const owned = validateOwnedScene(options); // Must succeed before Undo scope registration.
    if (typeof options.dynamicRelease !== 'function')
        throw fail('CREATOR_SAVED_SCENE_DYNAMIC_RELEASE_UNAVAILABLE');
    const dynamicRelease = options.dynamicRelease;
    let finished = false;

    return {
        scene: owned.scene,
        asset: owned.asset,
        async cleanup() {
            if (finished) return {cleaned: false, alreadyCleaned: true, error: null};
            // Recheck immediately before destruction: an Editor scene may have
            // become current while the asynchronous readback was in progress.
            try { validateOwnedScene(owned); }
            catch (error) { return {cleaned: false, error}; }

            const ownedRootUuid = owned.scene.uuid || owned.scene._uuid || null;
            const ownedObjects = captureOwnedObjects(owned.scene);
            const rootEntry = ownedObjects.find(entry => entry.kind === 'node' && entry.uuid === ownedRootUuid) ||
                {kind: 'node', uuid: ownedRootUuid, object: owned.scene};
            const errors = [];
            try { await dynamicRelease(owned.scene); }
            catch (error) { errors.push(error); }
            let destroyAllowed = true;
            try { currentSceneGuard(owned.scene, owned.asset, owned.cc, owned.cce); }
            catch (error) {
                destroyAllowed = false;
                errors.push(fail('CREATOR_SAVED_SCENE_DESTROY_ABORTED_CURRENT_SCENE_GUARD', String(error && error.message || error).slice(0, 320)));
            }
            if (destroyAllowed) {
                try {
                    const destroyed = owned.scene.destroy();
                    if (destroyed === false)
                        errors.push(fail('CREATOR_SAVED_SCENE_DESTROY_REJECTED'));
                } catch (error) { errors.push(error); }
                try { owned.cc.CCObject._deferredDestroy(); }
                catch (error) { errors.push(error); }
            }
            const strictValid = typeof owned.cc.isValid === 'function' ? !!owned.cc.isValid(owned.scene, true) : null;
            const objFlags = Number.isFinite(owned.scene._objFlags) ? owned.scene._objFlags : null;
            const editorRegistry = owned.editorExtends && owned.editorExtends.Node;
            const getNode = editorRegistry && editorRegistry.getNode;
            let editorNode = null;
            try { if (typeof getNode === 'function') editorNode = getNode.call(editorRegistry, ownedRootUuid); } catch (_) {}
            const nodeManager = managerForKind(owned.cce, 'node');
            let tombstonesRemoved = 0;
            const tombstoneFailures = [];
            if (strictValid === false) {
                for (const entry of ownedObjects) {
                    retiredOwnedObjects.set(objectKey(entry.kind, entry.uuid), {...entry, sceneAssetUuid: owned.requestedUuid});
                }
                for (const entry of ownedObjects) {
                    if (owned.cc.isValid(entry.object, true)) {
                        if (tombstoneFailures.length < 16)
                            tombstoneFailures.push({kind: entry.kind, uuid: entry.uuid, reason: 'owned-object-still-valid-after-flush'});
                        continue;
                    }
                    const api = entry.kind === 'node' ? owned.cce.Node : owned.cce.Component;
                    let current;
                    try { current = api.query(entry.uuid); }
                    catch (error) {
                        if (tombstoneFailures.length < 16)
                            tombstoneFailures.push({kind: entry.kind, uuid: entry.uuid, reason: 'post-flush-query-failed', error: String(error && error.message || error).slice(0, 160)});
                        continue;
                    }
                    if (current === undefined) {
                        if (tombstoneFailures.length < 16)
                            tombstoneFailures.push({kind: entry.kind, uuid: entry.uuid, reason: 'post-flush-query-returned-undefined'});
                        continue;
                    }
                    if (current !== entry.object) continue; // null or a different live identity is preserved.
                    const removal = maybeRemoveRetiredObject(entry.kind, entry.uuid, entry.object,
                        owned.cce, owned.cc, owned.asset, owned.editorExtends);
                    if (removal.removed) tombstonesRemoved++;
                    else if (tombstoneFailures.length < 16)
                        tombstoneFailures.push({kind: entry.kind, uuid: entry.uuid, reason: removal.reason || 'exact-tombstone-removal-unverified'});
                }
            }
            let queryNode = null, managerNode = null;
            try { queryNode = owned.cce.Node.query(ownedRootUuid); } catch (_) {}
            try { if (nodeManager && typeof nodeManager.query === 'function') managerNode = nodeManager.query(ownedRootUuid); } catch (_) {}
            const rootStillResolves = queryNode === owned.scene;
            const postCleanup = {rootUuid: ownedRootUuid,
                rootClass: owned.scene.constructor && owned.scene.constructor.name || null,
                validStrict: strictValid, objFlags,
                queryReturnsSameOwnedRoot: rootStillResolves,
                managerQueryReturnsSameOwnedRoot: managerNode === owned.scene,
                editorRegistryReturnsSameOwnedRoot: editorNode === owned.scene,
                ownedTreeObjectCount: ownedObjects.length,
                tombstonesRemoved, tombstoneFailures};
            if (strictValid !== false)
                errors.push(fail('CREATOR_SAVED_SCENE_NOT_DESTROYED_AFTER_FLUSH', '', postCleanup));
            if (rootStillResolves || managerNode === owned.scene || tombstoneFailures.length)
                errors.push(fail('CREATOR_SAVED_SCENE_OWNED_TOMBSTONES_REMAIN', '', postCleanup));
            finished = true;
            const cleanupError = errors.length ? fail('CREATOR_SAVED_SCENE_CLEANUP_FAILED',
                errors.map(error => String(error && error.message || error).slice(0, 480)).join(' | '),
                {errorCount: errors.length, postCleanup}) : null;
            return {cleaned: strictValid === false && !errors.some(error => error && error.code === 'CREATOR_SAVED_SCENE_OWNED_TOMBSTONES_REMAIN'), error: cleanupError, postCleanup};
        },
    };
}

function preservePrimaryError(primaryError, cleanupError) {
    if (!primaryError) return cleanupError || null;
    if (cleanupError) {
        try { primaryError.cleanupError = cleanupError; }
        catch (_) { /* Preserve the original thrown value. */ }
    }
    return primaryError;
}

module.exports = {begin, validateOwnedScene, preservePrimaryError, runtimeCacheDiagnostic, removeExactOwnedTombstone};
