'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const ownedImportUndo = require('../src/monkey/targets/CreatorOwnedImportUndo.js');

function fixture() {
    const registry = new Map();
    class SceneUndoManager {
        constructor() { this.records = []; this._uuidDumpMap = {}; }
        snapshot() { return 'original-snapshot'; }
        updateDump(uuids) { for (const uuid of uuids) this._uuidDumpMap[uuid] = {captured: true}; }
        record(uuid, dumpImmediately = true) {
            if (this.records.includes(uuid)) return;
            if (dumpImmediately) this.updateDump([uuid]);
            this.records.push(uuid);
        }
    }
    const manager = new SceneUndoManager();
    const cce = {
        SceneFacadeManager: {_facadeFSM: {generalSceneFacade: {_undoMgr: manager}}},
        Node: {query: uuid => registry.get(uuid) || null},
        Component: {query: uuid => registry.get(uuid) || null},
    };
    const filename = '/creator/builtin/scene/dist/script/export/undo/scene.ccc';
    const requireFn = {cache: {[filename]: {exports: {SceneUndoManager}}}};
    const realm = {JSON: {stringify: (...args) => JSON.stringify(...args)}};
    return {registry, SceneUndoManager, manager, cce, requireFn, realm};
}

test('broker isolates only registered roots and restores the live manager methods at finish', () => {
    const value = fixture();
    value.manager.records = ['user-before-import'];
    value.manager._uuidDumpMap = {'user-before-import': {user: true}};
    const originalRecord = value.SceneUndoManager.prototype.record;
    const originalSnapshot = value.SceneUndoManager.prototype.snapshot;
    const scope = ownedImportUndo.begin(value.cce, value.realm, value.requireFn);
    assert.equal(scope.installed, true);
    assert.equal(value.SceneUndoManager.prototype.snapshot, originalSnapshot,
        'broker must not install the expensive snapshot diagnostic wrapper');

    const importedRoot = {uuid: 'import-root', parent: null, children: [], _components: []};
    const importedChild = {uuid: 'import-child', parent: importedRoot, children: [], _components: []};
    importedRoot.children.push(importedChild);
    value.registry.set(importedRoot.uuid, importedRoot);
    value.registry.set(importedChild.uuid, importedChild);
    value.manager.record(importedRoot.uuid);
    value.manager.record(importedChild.uuid);
    scope.registerOwnedRoot(importedRoot);
    assert.deepEqual(value.manager.records, ['user-before-import']);
    assert.deepEqual(value.manager._uuidDumpMap, {'user-before-import': {user: true}});

    const unrelated = {uuid: 'unrelated-user-node'};
    value.registry.set(unrelated.uuid, unrelated);
    value.manager.record(unrelated.uuid);
    assert.deepEqual(value.manager.records, ['user-before-import', 'unrelated-user-node']);
    assert.ok(value.SceneUndoManager.prototype.record !== originalRecord);

    const done = scope.finish();
    assert.equal(done.scope.closed, true);
    assert.equal(value.SceneUndoManager.prototype.record, originalRecord);
    assert.equal(value.SceneUndoManager.prototype.snapshot, originalSnapshot);
    value.manager.record(importedChild.uuid);
    assert.ok(value.manager.records.includes(importedChild.uuid), 'record behavior resumes after finish');
});

test('broker returns a safe no-op when the real facade manager path or shape is absent', () => {
    const value = fixture();
    const originalRecord = value.SceneUndoManager.prototype.record;
    const missing = ownedImportUndo.begin({}, value.realm, value.requireFn);
    assert.equal(missing.installed, false);
    assert.equal(missing.reason, 'general-scene-undo-manager-unavailable');
    assert.equal(missing.registerOwnedRoot({uuid: 'new'}).registered, false);
    assert.equal(value.SceneUndoManager.prototype.record, originalRecord);

    value.manager._uuidDumpMap = [];
    const badShape = ownedImportUndo.begin(value.cce, value.realm, value.requireFn);
    assert.equal(badShape.installed, false);
    assert.equal(badShape.reason, 'general-scene-undo-manager-dump-shape-mismatch');
    assert.equal(value.SceneUndoManager.prototype.record, originalRecord);
});

test('broker injects Creator strict validity and cleans only destroyed unresolved registered roots', () => {
    const value = fixture();
    const required = name => {
        if (name === 'cc') return {isValid: (object, strict) => strict === true && object.destroyed !== true};
        throw new Error('unexpected module ' + name);
    };
    required.cache = value.requireFn.cache;
    const scope = ownedImportUndo.begin(value.cce, value.realm, required);
    assert.equal(scope.installed, true);
    const root = {uuid: 'broker-destroyed-root', parent: null, children: [], _components: [], destroyed: false};
    const child = {uuid: 'broker-destroyed-child', parent: root, children: [], _components: [], destroyed: false};
    root.children.push(child);
    value.manager.record(root.uuid);
    value.manager.record(child.uuid);
    scope.registerOwnedRoot(root);
    root.destroyed = true;
    child.destroyed = true;
    const done = scope.finish();
    assert.deepEqual(value.manager.records, []);
    assert.deepEqual(value.manager._uuidDumpMap, {});
    assert.equal(done.scope.pendingDestroyedOwnedCleanupCount, 2);
});
