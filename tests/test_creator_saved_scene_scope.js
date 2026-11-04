'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const savedSceneScope = require('../src/monkey/targets/CreatorSavedSceneScope.js');

function fixture() {
    const directNodes = new Map(), directComponents = new Map(), engineNodes = new Map(), engineComponents = new Map();
    const recycleNode = Object.create(null), recycleComponent = Object.create(null);
    const calls = [];
    class SceneAsset { constructor(uuid, scene) { this._uuid = uuid; this.scene = scene; } }
    class Scene {
        constructor(uuid) { this.uuid = uuid; this._id = uuid; this.children = []; this._components = []; this.destroyCalls = 0; }
        destroy() { this.destroyCalls++; this.destroyed = true; if (this.clearUuidOnDestroy) this.uuid = null; return true; }
    }
    const scene = new Scene('scene-root');
    const child = {uuid: 'saved-node', children: [], _components: [], constructor: {name: 'Node'}};
    const component = {uuid: 'saved-component', constructor: {name: 'Animation'}};
    child._components.push(component); scene.children.push(child);
    const asset = new SceneAsset('manifest-scene', scene);
    directNodes.set(scene.uuid, scene); directNodes.set(child.uuid, child);
    directComponents.set(component.uuid, component);
    engineNodes.set(scene.uuid, scene); engineNodes.set(child.uuid, child); engineComponents.set(component.uuid, component);
    const general = {
        _recycleNode: recycleNode,
        _recycleComponent: recycleComponent,
        queryCurrentSceneUuid: () => 'another-open-scene',
        queryRecycleNode(uuid) { return this._recycleNode[uuid] ?? null; },
        queryRecycleComponent(uuid) { return this._recycleComponent[uuid] ?? null; },
    };
    let managerRemoveCalls = 0;
    const nodeManager = {
        query: uuid => directNodes.get(uuid) ?? general.queryRecycleNode(uuid),
        remove: () => { managerRemoveCalls++; },
    };
    const componentManager = {
        query: uuid => directComponents.get(uuid) ?? general.queryRecycleComponent(uuid),
        remove: () => { managerRemoveCalls++; },
    };
    general._nodeMgr = nodeManager; general._compMgr = componentManager;
    const fsm = {currentState: {modeName: 'general'}, generalSceneFacade: general};
    const editorExtends = {
        Node: {getNode: uuid => engineNodes.get(uuid) || null, remove: uuid => engineNodes.delete(uuid)},
        Component: {getComponent: uuid => engineComponents.get(uuid) || null, remove: uuid => engineComponents.delete(uuid)},
    };
    const cce = {
        SceneFacadeManager: {_facadeFSM: fsm},
        Node: {query: uuid => nodeManager.query(uuid)},
        Component: {query: uuid => componentManager.query(uuid)},
    };
    const cc = {
        SceneAsset,
        isValid: (value, strict) => !!value && !(strict && value.destroyed),
        director: {getScene: () => null},
        CCObject: {_deferredDestroy: () => {
            calls.push('flush');
            const visit = node => {
                if (!node) return;
                node.destroyed = true;
                const id = node.uuid || node._uuid || node._id;
                if (id && directNodes.get(id) === node) { directNodes.delete(id); recycleNode[id] = node; }
                for (const comp of node._components || []) {
                    comp.destroyed = true;
                    const cid = comp.uuid || comp._uuid;
                    if (cid && directComponents.get(cid) === comp) { directComponents.delete(cid); recycleComponent[cid] = comp; }
                    if (cid) engineComponents.delete(cid);
                }
                engineNodes.delete(id);
                for (const childNode of node.children || []) visit(childNode);
            };
            visit(scene);
        }},
    };
    const scope = savedSceneScope.begin({asset, requestedUuid: 'manifest-scene', scene, cc, cce,
        editorExtends, dynamicRelease: value => { assert.equal(value, scene); calls.push('dynamic.release'); }});
    return {scene, child, component, asset, cc, cce, fsm, general, directNodes, directComponents,
        recycleNode, recycleComponent, engineNodes, engineComponents, calls, scope, editorExtends,
        get managerRemoveCalls() { return managerRemoveCalls; }};
}

async function staleSceneFixture() {
    const first = fixture();
    const firstDone = await first.scope.cleanup();
    assert.equal(firstDone.error, null);
    first.recycleNode['scene-root'] = first.scene;
    first.recycleNode[first.child.uuid] = first.child;
    first.recycleComponent[first.component.uuid] = first.component;
    const nextScene = {uuid: first.scene.uuid, children: [], _components: []};
    const nextAsset = new first.cc.SceneAsset(first.asset._uuid, nextScene);
    const options = {asset: nextAsset, requestedUuid: first.asset._uuid, scene: nextScene,
        cc: first.cc, cce: first.cce, editorExtends: first.editorExtends, dynamicRelease: () => {}};
    return {...first, nextScene, nextAsset, options};
}

test('cleans only exact owned destroyed recycle tombstone after dynamic release and flush', async () => {
    const value = fixture();
    value.scene.clearUuidOnDestroy = true;
    value.recycleNode['other-user-node'] = {uuid: 'other-user-node'};
    const result = await value.scope.cleanup();
    assert.equal(result.cleaned, true);
    assert.equal(result.error, null);
    assert.equal(result.postCleanup.validStrict, false);
    assert.equal(result.postCleanup.queryReturnsSameOwnedRoot, false);
    assert.equal(result.postCleanup.rootUuid, 'scene-root');
    assert.equal(value.cce.Node.query('scene-root'), null);
    assert.equal(Object.prototype.hasOwnProperty.call(value.recycleNode, 'scene-root'), false);
    assert.equal(Object.prototype.hasOwnProperty.call(value.recycleNode, value.child.uuid), false);
    assert.equal(Object.prototype.hasOwnProperty.call(value.recycleComponent, value.component.uuid), false);
    assert.ok(value.recycleNode['other-user-node'], 'unrelated user tombstone remains');
    assert.equal(value.managerRemoveCalls, 0, 'remove emits recycle events and is never used as purge');
    assert.deepEqual(value.calls, ['dynamic.release', 'flush']);
    assert.equal(value.scene.destroyCalls, 1);
    assert.equal((await value.scope.cleanup()).alreadyCleaned, true);
});

test('removes exact prior owned tombstone and never calls NodeManager.remove', async () => {
    const value = await staleSceneFixture();
    const ownedOld = [...value.recycleNode['scene-root'] ? [value.recycleNode['scene-root']] : []];
    assert.equal(ownedOld.length, 1);
    const nextScope = savedSceneScope.begin(value.options);
    assert.equal(value.cce.Node.query('scene-root'), null);
    assert.equal(Object.prototype.hasOwnProperty.call(value.recycleNode, 'scene-root'), false);
    assert.equal(value.managerRemoveCalls, 0);
    assert.ok(nextScope);
});


test('purges exact prior owned descendant and component tombstones without manager remove events', async () => {
    const value = await staleSceneFixture();
    const newScene = {uuid: 'new-scene-root', children: [], _components: []};
    const newChild = {uuid: value.child.uuid, children: [], _components: []};
    const newComponent = {uuid: value.component.uuid};
    newChild._components.push(newComponent); newScene.children.push(newChild);
    const newAsset = new value.cc.SceneAsset(value.asset._uuid, newScene);
    const scope = savedSceneScope.begin({asset: newAsset, requestedUuid: value.asset._uuid,
        scene: newScene, cc: value.cc, cce: value.cce, editorExtends: value.editorExtends, dynamicRelease: () => {}});
    assert.equal(scope.scene, newScene);
    assert.equal(Object.prototype.hasOwnProperty.call(value.recycleNode, value.child.uuid), false);
    assert.equal(Object.prototype.hasOwnProperty.call(value.recycleComponent, value.component.uuid), false);
    assert.equal(value.managerRemoveCalls, 0);
});

test('leaves same-UUID foreign user tombstone intact', async () => {
    const value = await staleSceneFixture();
    const foreign = {uuid: 'scene-root', children: [], _components: []};
    value.recycleNode['scene-root'] = foreign;
    assert.throws(() => savedSceneScope.begin(value.options), error =>
        error.code === 'CREATOR_SAVED_SCENE_UUID_OWNED_BY_OTHER_OBJECT');
    assert.equal(value.recycleNode['scene-root'], foreign);
    assert.equal(value.managerRemoveCalls, 0);
});

test('refuses a matching tombstone when the own descriptor is protected', async () => {
    const value = await staleSceneFixture();
    const old = value.recycleNode['scene-root'];
    Object.defineProperty(value.recycleNode, 'scene-root', {value: old, enumerable: true, writable: true, configurable: false});
    assert.throws(() => savedSceneScope.begin(value.options), error =>
        error.code === 'CREATOR_SAVED_SCENE_UUID_OWNED_BY_OTHER_OBJECT' && /not-configurable/.test(error.message));
    assert.equal(value.recycleNode['scene-root'], old);
});

test('post-delete manager query errors do not count as successful tombstone cleanup', async () => {
    const value = await staleSceneFixture();
    const manager = value.fsm.generalSceneFacade._nodeMgr;
    const original = manager.query;
    let calls = 0;
    manager.query = uuid => { calls++; if (calls === 2) throw new Error('manager after delete'); return original(uuid); };
    assert.throws(() => savedSceneScope.begin(value.options), error =>
        error.code === 'CREATOR_SAVED_SCENE_UUID_OWNED_BY_OTHER_OBJECT' || error.code === 'CREATOR_SAVED_SCENE_QUERY_FAILED');
});

test('post-delete cce query errors are surfaced instead of treating cache as empty', async () => {
    const value = await staleSceneFixture();
    const original = value.cce.Node.query;
    let calls = 0;
    value.cce.Node.query = uuid => { calls++; if (calls >= 3) throw new Error('cce after delete'); return original(uuid); };
    assert.throws(() => savedSceneScope.begin(value.options), error => error.code === 'CREATOR_SAVED_SCENE_QUERY_FAILED');
});

test('foreign or current replacements are rechecked after exact tombstone removal', async () => {
    const foreignCase = await staleSceneFixture();
    const foreign = {uuid: 'scene-root', children: [], _components: []};
    const manager = foreignCase.fsm.generalSceneFacade._nodeMgr;
    manager.query = uuid => foreignCase.recycleNode[uuid] ?? (uuid === 'scene-root' ? foreign : null);
    foreignCase.cce.Node.query = uuid => manager.query(uuid);
    assert.throws(() => savedSceneScope.begin(foreignCase.options), error =>
        error.code === 'CREATOR_SAVED_SCENE_UUID_OWNED_BY_OTHER_OBJECT' && /resolvedUuid/.test(error.message));

    const currentCase = await staleSceneFixture();
    const currentManager = currentCase.fsm.generalSceneFacade._nodeMgr;
    currentManager.query = uuid => currentCase.recycleNode[uuid] ?? (uuid === 'scene-root' ? currentCase.nextScene : null);
    currentCase.cce.Node.query = uuid => currentManager.query(uuid);
    const scope = savedSceneScope.begin(currentCase.options);
    assert.equal(scope.scene, currentCase.nextScene);
});


test('rechecks Editor current-scene guard after async dynamic release before destroying', async () => {
    const value = fixture();
    const scope = savedSceneScope.begin({asset: value.asset, requestedUuid: value.asset._uuid,
        scene: value.scene, cc: value.cc, cce: value.cce, editorExtends: value.editorExtends,
        dynamicRelease: async () => { value.general.queryCurrentSceneUuid = () => value.asset._uuid; }});
    const result = await scope.cleanup();
    assert.equal(result.cleaned, false);
    assert.match(result.error.message, /CREATOR_SAVED_SCENE_DESTROY_ABORTED_CURRENT_SCENE_GUARD/);
    assert.equal(value.scene.destroyCalls, 0);
    assert.equal(value.cce.Node.query('scene-root'), value.scene);
});

test('requires strict invalidity after deferred flush and reports failure otherwise', async () => {
    const value = fixture();
    value.cc.isValid = () => true;
    const result = await value.scope.cleanup();
    assert.equal(result.cleaned, false);
    assert.equal(result.error.code, 'CREATOR_SAVED_SCENE_CLEANUP_FAILED');
    assert.match(result.error.message, /CREATOR_SAVED_SCENE_NOT_DESTROYED_AFTER_FLUSH/);
    assert.equal(result.postCleanup.validStrict, true);
});

test('requires dynamic release ownership callback before granting cleanup scope', () => {
    const value = fixture();
    assert.throws(() => savedSceneScope.begin({asset: value.asset, requestedUuid: value.asset._uuid,
        scene: value.scene, cc: value.cc, cce: value.cce}), error => error.code === 'CREATOR_SAVED_SCENE_DYNAMIC_RELEASE_UNAVAILABLE');
    assert.equal(value.scene.destroyCalls, 0);
});

test('refuses collisions before teardown and protects current scene identities', () => {
    const cases = [
        ['director', v => { v.cc.director.getScene = () => v.scene; }, 'CREATOR_SAVED_SCENE_IS_DIRECTOR_SCENE'],
        ['editor', v => { v.general.queryCurrentSceneUuid = () => v.asset._uuid; }, 'CREATOR_SAVED_SCENE_IS_EDITOR_SCENE'],
        ['mode', v => { v.fsm.currentState.modeName = 'prefab'; }, 'CREATOR_SAVED_SCENE_GENERAL_FACADE_NOT_CURRENT'],
        ['uuid', v => { v.asset._uuid = 'different'; }, 'CREATOR_SAVED_SCENE_ASSET_UUID_MISMATCH'],
        ['asset scene', v => { v.asset.scene = {}; }, 'CREATOR_SAVED_SCENE_ASSET_INSTANCE_MISMATCH'],
        ['deferred destroy', v => { delete v.cc.CCObject._deferredDestroy; }, 'CREATOR_SAVED_SCENE_DEFERRED_DESTROY_UNAVAILABLE'],
    ];
    for (const [name, edit, code] of cases) {
        const value = fixture(); edit(value);
        assert.throws(() => savedSceneScope.begin({asset: value.asset, requestedUuid: 'manifest-scene',
            scene: value.scene, cc: value.cc, cce: value.cce, dynamicRelease: () => {}}), error => error.code === code, name);
        assert.equal(value.scene.destroyCalls, 0, name);
        assert.deepEqual(value.calls, [], name);
    }
});

test('rechecks current scene before cleanup and leaves newly opened user scene untouched', async () => {
    const value = fixture();
    value.general.queryCurrentSceneUuid = () => value.asset._uuid;
    const result = await value.scope.cleanup();
    assert.equal(result.cleaned, false);
    assert.equal(result.error.code, 'CREATOR_SAVED_SCENE_IS_EDITOR_SCENE');
    assert.equal(value.scene.destroyCalls, 0);
    assert.deepEqual(value.calls, []);
});

test('runtime cache diagnostic prioritizes query, remove and recycle methods in valid bounded JSON', () => {
    const value = fixture();
    const manager = value.fsm.generalSceneFacade._nodeMgr;
    value.recycleNode['scene-root'] = value.scene;
    const diagnostic = savedSceneScope.runtimeCacheDiagnostic('node', 'scene-root', value.cce,
        value.editorExtends, manager, manager.query('scene-root'), value.cce.Node.query('scene-root'), value.scene);
    assert.equal(diagnostic.schema, 'creator-saved-scene-manager-runtime-diagnostic/v2');
    assert.match(diagnostic.managerQuerySource.source, /queryRecycleNode/);
    assert.match(diagnostic.managerRemoveSource.source, /managerRemoveCalls/);
    assert.match(diagnostic.facadeRecycleQuerySource.source, /queryRecycleNode/);
    assert.equal(diagnostic.cache.queryRecycleSameObject, true);
    assert.ok(JSON.stringify(diagnostic).length < 10000);
});

test('cleanup failure is attached without replacing primary readback error', () => {
    const primary = new Error('readback failed');
    const cleanup = new Error('cleanup failed');
    assert.equal(savedSceneScope.preservePrimaryError(primary, cleanup), primary);
    assert.equal(primary.cleanupError, cleanup);
    assert.equal(savedSceneScope.preservePrimaryError(null, cleanup), cleanup);
});
