'use strict';

// Teardown for a detached Scene tree created by CreatorScene.assemble. The
// factory records exact root identity; callers cannot use this path to retire
// a loaded/user SceneAsset or a director-owned Scene.
const ownedBuildRoots = new WeakSet();

function fail(code, details = {}) {
    let suffix = '';
    try { suffix = JSON.stringify(details); } catch (_) { suffix = '{"details":"unavailable"}'; }
    return Object.assign(new Error(code + (suffix && suffix !== '{}' ? ' ' + suffix : '')), {code, details});
}

function create(cc, name) {
    if (!cc || typeof cc.Scene !== 'function') throw fail('CREATOR_BUILD_SCENE_CONSTRUCTOR_UNAVAILABLE');
    const scene = new cc.Scene(name);
    ownedBuildRoots.add(scene);
    return scene;
}

function collect(scene) {
    const result = [], visited = new Set(), uuids = new Set();
    const walk = node => {
        if (!node || visited.has(node)) return;
        visited.add(node);
        if (node.uuid || node._uuid) {
            const uuid = node.uuid || node._uuid, key = 'node:' + uuid;
            if (uuids.has(key)) throw fail('CREATOR_BUILD_SCENE_DUPLICATE_OWNED_UUID', {kind:'node', uuid});
            uuids.add(key); result.push({kind:'node', uuid, object:node});
        }
        const components = Array.isArray(node.components) ? node.components :
            Array.isArray(node._components) ? node._components : [];
        for (const component of components) if (component && (component.uuid || component._uuid)) {
            const uuid = component.uuid || component._uuid, key = 'component:' + uuid;
            if (uuids.has(key)) throw fail('CREATOR_BUILD_SCENE_DUPLICATE_OWNED_UUID', {kind:'component', uuid});
            uuids.add(key); result.push({kind:'component', uuid, object:component});
        }
        const children = Array.isArray(node.children) ? node.children :
            Array.isArray(node._children) ? node._children : [];
        for (const child of children) walk(child);
    };
    walk(scene);
    if (!result.length || result[0].object !== scene) throw fail('CREATOR_BUILD_SCENE_ROOT_IDENTITY_MISSING');
    return result;
}

function assertDetached(scene, cc, cce, sceneAsset = null) {
    const director = cc && cc.director;
    if (!director || typeof director.getScene !== 'function') throw fail('CREATOR_BUILD_SCENE_DIRECTOR_UNAVAILABLE');
    if (director.getScene() === scene) throw fail('CREATOR_BUILD_SCENE_IS_DIRECTOR_SCENE', {uuid:scene.uuid || null});
    const fsm = cce && cce.SceneFacadeManager && cce.SceneFacadeManager._facadeFSM;
    if (!fsm || !fsm.currentState || fsm.currentState.modeName !== 'general')
        throw fail('CREATOR_BUILD_SCENE_GENERAL_FACADE_NOT_CURRENT', {modeName:fsm && fsm.currentState && fsm.currentState.modeName || null});
    const general = fsm.generalSceneFacade;
    if (!general || typeof general.queryCurrentSceneUuid !== 'function') throw fail('CREATOR_BUILD_SCENE_CURRENT_UUID_API_UNAVAILABLE');
    const currentUuid = general.queryCurrentSceneUuid();
    if (typeof currentUuid !== 'string') throw fail('CREATOR_BUILD_SCENE_CURRENT_UUID_INVALID', {valueType:currentUuid === null ? 'null' : typeof currentUuid});
    if (currentUuid && (currentUuid === scene.uuid || sceneAsset && currentUuid === sceneAsset._uuid))
        throw fail('CREATOR_BUILD_SCENE_IS_EDITOR_SCENE', {currentUuid, sceneUuid:scene.uuid || null});
}

function managerFor(cce, kind) {
    const fsm = cce && cce.SceneFacadeManager && cce.SceneFacadeManager._facadeFSM;
    const general = fsm && fsm.currentState && fsm.currentState.modeName === 'general' && fsm.generalSceneFacade;
    return general && general[kind === 'node' ? '_nodeMgr' : '_compMgr'] || null;
}

async function cleanup(scene, options = {}) {
    const {cc, cce, editorExtends = null, sceneAsset = null, dynamicRelease} = options;
    if (!scene || !ownedBuildRoots.has(scene)) throw fail('CREATOR_BUILD_SCENE_NOT_EXACT_OWNED_ROOT');
    if (!cc || typeof cc.isValid !== 'function' || !cc.CCObject || typeof cc.CCObject._deferredDestroy !== 'function')
        throw fail('CREATOR_BUILD_SCENE_DESTROY_APIS_UNAVAILABLE');
    if (typeof dynamicRelease !== 'function') throw fail('CREATOR_BUILD_SCENE_RELEASE_CALLBACK_UNAVAILABLE');
    assertDetached(scene, cc, cce, sceneAsset);
    const captured = collect(scene);
    for (const entry of captured) if (cc.isValid(entry.object, true) !== true)
        throw fail('CREATOR_BUILD_SCENE_TREE_NOT_LIVE_BEFORE_CLEANUP', {kind:entry.kind, uuid:entry.uuid});

    const errors = [];
    try { await dynamicRelease(scene); } catch (error) { errors.push(error); }
    let sceneGuardFailed = false;
    try { assertDetached(scene, cc, cce, sceneAsset); }
    catch (error) { errors.push(error); sceneGuardFailed = true; }
    if (!sceneGuardFailed) {
        try {
            const result = scene.destroy();
            if (result === false) errors.push(fail('CREATOR_BUILD_SCENE_DESTROY_REJECTED'));
        } catch (error) { errors.push(error); }
        try { cc.CCObject._deferredDestroy(); }
        catch (error) { errors.push(fail('CREATOR_BUILD_SCENE_DEFERRED_DESTROY_FAILED', {message:String(error && error.message || error).slice(0,160)})); }
    }

    const flushFailed = errors.some(error => error && error.code === 'CREATOR_BUILD_SCENE_DEFERRED_DESTROY_FAILED');
    const tombstonesRemoved = [], tombstoneFailures = [];
    let undoRetirement = {retired:false,reason:'not-attempted',retiredObjectCount:0};
    if (!flushFailed) {
        let savedScope;
        try { savedScope = require('./creator-saved-scene-scope.js'); }
        catch (_) { savedScope = require('./CreatorSavedSceneScope.js'); }
        for (const entry of captured) {
            let valid;
            try { valid = cc.isValid(entry.object, true); }
            catch (_) { valid = null; }
            if (valid !== false) {
                tombstoneFailures.push({kind:entry.kind,uuid:entry.uuid,reason:'strict-invalid-not-proven'});
                continue;
            }
            const result = savedScope.removeExactOwnedTombstone(entry.kind, entry.uuid, entry.object,
                cce, cc, editorExtends, () => assertDetached(scene, cc, cce, sceneAsset));
            if (result.removed) tombstonesRemoved.push({kind:entry.kind,uuid:entry.uuid});
            else if (result.attempted || ['manager-pre-remove-query-failed','cce-pre-remove-query-failed'].includes(result.reason))
                tombstoneFailures.push({kind:entry.kind,uuid:entry.uuid,reason:result.reason});
        }
        if (cc.isValid(scene, true) === false) {
            let ownedUndo;
            try { ownedUndo = require('./owned-import-undo.js'); }
            catch (_) { ownedUndo = require('./CreatorOwnedImportUndo.js'); }
            if (ownedUndo && typeof ownedUndo.retireDestroyedRoot === 'function')
                undoRetirement = ownedUndo.retireDestroyedRoot(scene, captured);
            if (!undoRetirement.retired && undoRetirement.reason !== 'no-owned-import')
                errors.push(fail('CREATOR_BUILD_SCENE_UNDO_IDENTITY_RETIREMENT_FAILED', undoRetirement));
        }
    }
    ownedBuildRoots.delete(scene);
    const post = {rootUuid:captured[0].uuid, capturedObjectCount:captured.length,
        rootValidStrict:cc.isValid(scene, true), tombstonesRemovedCount:tombstonesRemoved.length,
        tombstonesRemoved, tombstoneFailures, undoRetirement};
    if (post.rootValidStrict !== false) errors.push(fail('CREATOR_BUILD_SCENE_NOT_DESTROYED_AFTER_FLUSH', post));
    if (tombstoneFailures.length) errors.push(fail('CREATOR_BUILD_SCENE_TOMBSTONE_CLEANUP_INCOMPLETE', post));
    if (errors.length) {
        const error = fail('CREATOR_BUILD_SCENE_TEARDOWN_FAILED', {errors:errors.map(item=>String(item && item.message || item).slice(0,256)),post});
        error.postCleanup = post;
        return {cleaned:false,error,postCleanup:post};
    }
    return {cleaned:true,error:null,postCleanup:post};
}

async function cleanupAfterBuild(scene, options, primaryError = null) {
    let result;
    try { result = await cleanup(scene, options); }
    catch (error) { result = {cleaned:false,error}; }
    if (primaryError && result.error) {
        try { primaryError.cleanupError = result.error; } catch (_) {}
    }
    return result;
}

module.exports = {create, cleanup, cleanupAfterBuild};
