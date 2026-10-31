'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const diagnostics = require('../src/monkey/targets/CreatorEditorUndoDiagnostics.js');

function makeFixture(snapshot) {
    const realm = {JSON: {stringify: (...args) => JSON.stringify(...args)}};
    class SceneUndoManager {
        snapshot(...args) { return snapshot.apply(this, args); }
        updateDump(uuids) { for (const uuid of uuids) this._uuidDumpMap[uuid] = {dumped: true}; }
        record(uuid, dumpImmediately = true) {
            if (!this.records.includes(uuid)) {
                if (dumpImmediately) this.updateDump([uuid]);
                this.records.push(uuid);
            }
        }
        beginRecording() { return 'recording'; }
        cancelRecording() { return true; }
        endRecording() { return true; }
        undo() { return Promise.resolve(); }
        redo() { return Promise.resolve(); }
        reset() { this.records.length = 0; this._uuidDumpMap = {}; }
    }
    const filename = '/creator/builtin/scene/dist/script/export/undo/scene.ccc';
    const requireFn = {cache: {[filename]: {exports: {SceneUndoManager}}}};
    const records = [];
    const probe = diagnostics.install({realm, requireFn, onRecord: row => records.push(row)});
    return {realm, SceneUndoManager, filename, requireFn, records, probe};
}

test('wraps only the loaded builtin SceneUndoManager snapshot and records bounded call context', () => {
    const fixture = makeFixture(function (input) { return this.realm.JSON.stringify(input); });
    const manager = new fixture.SceneUndoManager();
    manager.realm = fixture.realm;
    manager.records = ['uuid-secret-must-not-be-copied'];
    manager._autoCommands = new Array(3);
    manager._uuidDumpMap = new Map([['uuid-secret-must-not-be-copied', {value: 'no-copy'}]]);
    const result = manager.snapshot({token: 'do-not-copy-secret', child: {count: 4}});
    assert.deepEqual(JSON.parse(result), {token: 'do-not-copy-secret', child: {count: 4}});
    assert.equal(fixture.records.length, 1);
    const row = fixture.records[0];
    assert.equal(row.receiver.constructor, 'SceneUndoManager');
    assert.equal(row.args[0].type, 'object');
    assert.ok(row.snapshotSource.length <= 6000);
    assert.equal(row.stringifyInputs.length, 1);
    assert.equal(row.stringifyInputs[0].stats.objects, 2);
    assert.ok(!JSON.stringify(row).includes('do-not-copy-secret'));
    assert.ok(!JSON.stringify(row).includes('uuid-secret-must-not-be-copied'));
    assert.equal(row.receiverUndoFields.find(field => field.name === 'records').value.arrayLength, 1);
    assert.equal(row.receiverUndoFields.find(field => field.name === '_autoCommands').value.arrayLength, 3);
    assert.equal(row.receiverUndoFields.find(field => field.name === '_uuidDumpMap').value.collectionSize, 1);
    assert.ok(fixture.probe.summary().undoMethods.some(method => method.name === 'snapshot'));
    for (const method of ['record', 'beginRecording', 'cancelRecording', 'endRecording', 'undo', 'redo', 'reset'])
        assert.ok(fixture.probe.summary().undoMethods.some(row => row.name === method), `captures ${method} source`);
    assert.equal(fixture.realm.JSON.stringify({ok: true}), '{"ok":true}');
    fixture.probe.uninstall();
});

test('owned import scope filters exact registered objects while preserving user undo state', () => {
    const fixture = makeFixture(function (input) { return this.realm.JSON.stringify(input); });
    const manager = new fixture.SceneUndoManager();
    manager.records = ['existing-user-node'];
    manager._uuidDumpMap = {'existing-user-node': {userData: 'keep'}};
    const userCommand = {id: 'user-command'};
    manager._commandArray = [userCommand];
    manager._autoCommands = [];
    manager._manualCommands = [];
    const ownedNode = {uuid: 'new-import-node'};
    const unrelatedUserNode = {uuid: 'unrelated-user-node'};
    const registry = new Map([[ownedNode.uuid, ownedNode], ['existing-user-node', {uuid: 'existing-user-node'}],
        [unrelatedUserNode.uuid, unrelatedUserNode]]);
    const scope = fixture.probe.beginOwnedImportScope(manager, uuid => registry.get(uuid));
    scope.registerOwnedObject(ownedNode);

    manager.record(ownedNode.uuid);
    manager.record('existing-user-node');
    manager.record(unrelatedUserNode.uuid);
    assert.deepEqual(manager.records, ['existing-user-node', 'unrelated-user-node']);
    assert.deepEqual(manager._uuidDumpMap, {'existing-user-node': {userData: 'keep'},
        'unrelated-user-node': {dumped: true}});
    assert.equal(manager._commandArray[0], userCommand);
    assert.deepEqual(scope.summary(), {
        ownedObjectCount: 1, ownedRootCount: 0, suppressedRecordCount: 1, suppressedUuidCount: 1,
        dynamicOwnedDiscoveries: 0, preexistingOwnedMatches: 0,
        pendingOwnedObjectCount: 0, pendingUnresolvedAtFinish: 0, pendingIdentityConflicts: 0,
        pendingDestroyedOwnedCleanupCount: 0, pendingDestroyedOwnedUnverifiedCount: 0,
        preRegistrationRecordRemovals: 0, preRegistrationDumpRemovals: 0,
        baselineRecordCount: 1, baselineDumpKeyCount: 1, closed: false,
    });

    const final = scope.finish();
    assert.equal(final.closed, true);
    // Once scope ends, normal Creator recording is restored for the same UUID.
    manager.record(ownedNode.uuid);
    assert.deepEqual(manager.records, ['existing-user-node', 'unrelated-user-node', 'new-import-node']);
    assert.ok(Object.hasOwn(manager._uuidDumpMap, 'existing-user-node'));
    assert.ok(Object.hasOwn(manager._uuidDumpMap, 'new-import-node'));
    fixture.probe.uninstall();
});

test('registration removes only constructor-time residue for a new exact UUID', () => {
    const fixture = makeFixture(function (input) { return this.realm.JSON.stringify(input); });
    const manager = new fixture.SceneUndoManager();
    manager.records = ['existing-user-node'];
    manager._uuidDumpMap = {'existing-user-node': {keep: true}};
    const registry = new Map();
    const scope = fixture.probe.beginOwnedImportScope(manager, uuid => registry.get(uuid));

    // Creator may call record(uuid) inside Node construction before the
    // importer has an opportunity to register the newly created Node.
    const node = {uuid: 'constructed-before-parent'};
    registry.set(node.uuid, node);
    manager.record(node.uuid);
    assert.deepEqual(manager.records, ['existing-user-node', 'constructed-before-parent']);
    assert.ok(Object.hasOwn(manager._uuidDumpMap, node.uuid));

    scope.registerOwnedObject(node);
    assert.deepEqual(manager.records, ['existing-user-node']);
    assert.deepEqual(manager._uuidDumpMap, {'existing-user-node': {keep: true}});
    assert.equal(scope.summary().preRegistrationRecordRemovals, 1);
    assert.equal(scope.summary().preRegistrationDumpRemovals, 1);
    manager.record(node.uuid);
    assert.deepEqual(manager.records, ['existing-user-node']);
    scope.finish();
    fixture.probe.uninstall();
});

test('owned scope rejects preexisting UUIDs and requires the exact resolved object identity', () => {
    const fixture = makeFixture(function (input) { return this.realm.JSON.stringify(input); });
    const manager = new fixture.SceneUndoManager();
    manager.records = ['user-node'];
    manager._uuidDumpMap = {'user-node': {keep: true}};
    const userObject = {uuid: 'user-node'};
    const impostor = {uuid: 'user-node'};
    const registry = new Map([['user-node', userObject]]);
    const scope = fixture.probe.beginOwnedImportScope(manager, uuid => registry.get(uuid));
    let conflict;
    try { scope.registerOwnedObject(userObject); } catch (error) { conflict = error; }
    assert.match(conflict.message, /CREATOR_UNDO_OWNED_UUID_PREEXISTING:/);
    const detail = JSON.parse(conflict.message.slice(conflict.message.indexOf(':') + 1));
    assert.equal(detail.phase, 'adoptResolvedObject');
    assert.equal(detail.uuid, 'user-node');
    assert.equal(detail.object.uuid, 'user-node');
    assert.deepEqual(detail.baseline.recordPositions, [0]);
    assert.equal(detail.baseline.recordMatched, true);
    assert.equal(detail.current.dumpKeyPresent, true);
    assert.equal(detail.resolverSameObject, true);
    assert.throws(() => scope.registerOwnedObject(impostor), /CREATOR_UNDO_OWNED_UUID_PREEXISTING:/);
    assert.deepEqual(manager.records, ['user-node']);
    assert.deepEqual(manager._uuidDumpMap, {'user-node': {keep: true}});
    manager.record('user-node');
    assert.deepEqual(manager.records, ['user-node']);
    scope.finish();
    fixture.probe.uninstall();
});


test('preexisting dump-only UUID diagnostics identify protected dump key and resolved identity', () => {
    const fixture = makeFixture(function (input) { return this.realm.JSON.stringify(input); });
    const manager = new fixture.SceneUndoManager();
    manager.records = [];
    manager._uuidDumpMap = {'candidate-root': {opaque: true}};
    const root = {uuid: 'candidate-root', parent: null, children: [], _components: []};
    const registry = new Map([[root.uuid, root]]);
    const scope = fixture.probe.beginOwnedImportScope(manager, uuid => registry.get(uuid));
    let conflict;
    try { scope.registerOwnedRoot(root); } catch (error) { conflict = error; }
    assert.ok(conflict);
    const detail = JSON.parse(conflict.message.slice(conflict.message.indexOf(':') + 1));
    assert.equal(detail.phase, 'registerOwnedRoot.root');
    assert.equal(detail.uuid, root.uuid);
    assert.equal(detail.baseline.recordMatched, false);
    assert.equal(detail.baseline.dumpKeyMatched, true);
    assert.equal(detail.current.dumpKeyPresent, true);
    assert.equal(detail.current.dumpDescriptor.data, true);
    assert.equal(detail.resolverSameObject, true);
    assert.ok(JSON.stringify(detail).length < 5000);
    scope.finish();
    fixture.probe.uninstall();
});

test('owned root covers its exact existing and future descendants/components without swallowing another root', () => {
    const fixture = makeFixture(function (input) { return this.realm.JSON.stringify(input); });
    const manager = new fixture.SceneUndoManager();
    manager.records = ['baseline-user-node'];
    manager._uuidDumpMap = {'baseline-user-node': {keep: true}};
    const commands = [{id: 'preserve-command'}];
    manager._commandArray = commands;
    const registry = new Map();
    const makeNode = uuid => ({uuid, parent: null, children: [], _components: []});
    const addChild = (parent, child) => { child.parent = parent; parent.children.push(child); };
    const ownedRoot = makeNode('owned-scene-root');
    const initialChild = makeNode('initial-child');
    const initialComponent = {uuid: 'initial-component', node: initialChild};
    initialChild._components.push(initialComponent);
    addChild(ownedRoot, initialChild);
    for (const object of [ownedRoot, initialChild, initialComponent]) registry.set(object.uuid, object);

    const scope = fixture.probe.beginOwnedImportScope(manager, uuid => registry.get(uuid));
    // Simulate constructors recording before the importer registers the root.
    for (const object of [ownedRoot, initialChild, initialComponent]) manager.record(object.uuid);
    assert.equal(manager.records.length, 4);
    assert.equal(scope.registerOwnedRoot(ownedRoot).registered, true);
    assert.deepEqual(manager.records, ['baseline-user-node']);
    assert.deepEqual(manager._uuidDumpMap, {'baseline-user-node': {keep: true}});

    manager.record(initialChild.uuid);
    manager.record(initialComponent.uuid);
    const futureChild = makeNode('future-child');
    registry.set(futureChild.uuid, futureChild);
    // Constructor-time residue is retained until a parent relationship proves
    // ownership; the first record after parenting cleans it then suppresses.
    manager.record(futureChild.uuid);
    addChild(ownedRoot, futureChild);
    manager.record(futureChild.uuid);
    assert.ok(!manager.records.includes(futureChild.uuid));
    assert.ok(!Object.hasOwn(manager._uuidDumpMap, futureChild.uuid));

    const futureComponent = {uuid: 'future-component', node: null};
    registry.set(futureComponent.uuid, futureComponent);
    manager.record(futureComponent.uuid);
    futureComponent.node = futureChild;
    futureChild._components.push(futureComponent);
    manager.record(futureComponent.uuid);
    assert.ok(!manager.records.includes(futureComponent.uuid));
    assert.ok(!Object.hasOwn(manager._uuidDumpMap, futureComponent.uuid));

    const notOwnedRoot = makeNode('unrelated-user-root');
    const notOwnedChild = makeNode('unrelated-user-child');
    addChild(notOwnedRoot, notOwnedChild);
    registry.set(notOwnedChild.uuid, notOwnedChild);
    manager.record(notOwnedChild.uuid);
    assert.ok(manager.records.includes(notOwnedChild.uuid));
    assert.ok(Object.hasOwn(manager._uuidDumpMap, notOwnedChild.uuid));

    const lateChild = makeNode('late-child-with-no-second-record');
    registry.set(lateChild.uuid, lateChild);
    manager.record(lateChild.uuid);
    addChild(ownedRoot, lateChild);
    const final = scope.finish();
    assert.ok(!manager.records.includes(lateChild.uuid));
    assert.ok(!Object.hasOwn(manager._uuidDumpMap, lateChild.uuid));
    assert.equal(final.ownedRootCount, 1);
    assert.ok(final.dynamicOwnedDiscoveries >= 2);
    assert.equal(manager.records[0], 'baseline-user-node');
    assert.ok(manager.records.includes(notOwnedChild.uuid));
    assert.equal(manager._commandArray, commands);

    // Scope cleanup removes only the record hook; normal user undo remains live.
    manager.record(initialChild.uuid);
    assert.ok(manager.records.includes(initialChild.uuid));
    fixture.probe.uninstall();
});

test('owned root stays pending while UUID queries miss and adopts only after exact identity appears', () => {
    const fixture = makeFixture(function (input) { return this.realm.JSON.stringify(input); });
    const manager = new fixture.SceneUndoManager();
    manager.records = ['baseline-user-node'];
    manager._uuidDumpMap = {'baseline-user-node': {keep: true}};
    const registry = new Map();
    const root = {uuid: 'pending-root', parent: null, children: [], _components: []};
    const child = {uuid: 'pending-child', parent: root, children: [], _components: []};
    root.children.push(child);
    const scope = fixture.probe.beginOwnedImportScope(manager, uuid => registry.get(uuid) || null);

    manager.record(root.uuid);
    manager.record(child.uuid);
    const registered = scope.registerOwnedRoot(root);
    assert.equal(registered.registered, true);
    assert.equal(registered.objectCount, 0);
    assert.equal(registered.pendingObjectCount, 2);
    assert.deepEqual(manager.records, ['baseline-user-node', root.uuid, child.uuid]);
    assert.ok(Object.hasOwn(manager._uuidDumpMap, root.uuid));
    assert.equal(scope.summary().pendingOwnedObjectCount, 2);

    registry.set(root.uuid, root);
    registry.set(child.uuid, child);
    // The first exact record call adopts the previously pending identities,
    // removes only their constructor-time residue, then suppresses new record.
    manager.record(child.uuid);
    manager.record(root.uuid);
    assert.deepEqual(manager.records, ['baseline-user-node']);
    assert.deepEqual(manager._uuidDumpMap, {'baseline-user-node': {keep: true}});
    assert.equal(scope.summary().pendingOwnedObjectCount, 0);
    const final = scope.finish();
    assert.equal(final.pendingUnresolvedAtFinish, 0);
    fixture.probe.uninstall();
});

test('owned root rejects a different resolved object without cleaning or claiming either UUID', () => {
    const fixture = makeFixture(function (input) { return this.realm.JSON.stringify(input); });
    const manager = new fixture.SceneUndoManager();
    manager.records = [];
    manager._uuidDumpMap = {};
    const root = {uuid: 'mismatched-root', parent: null, children: [], _components: []};
    const child = {uuid: 'mismatched-child', parent: root, children: [], _components: []};
    root.children.push(child);
    const registry = new Map([[root.uuid, root], [child.uuid, {uuid: child.uuid}]]);
    const scope = fixture.probe.beginOwnedImportScope(manager, uuid => registry.get(uuid) || null);
    manager.record(root.uuid);
    manager.record(child.uuid);
    let caught = null;
    try { scope.registerOwnedRoot(root); } catch (error) { caught = error; }
    assert.ok(caught && caught.message.startsWith('CREATOR_UNDO_OWNED_OBJECT_NOT_REGISTERED_BY_UUID:'));
    assert.ok(caught.message.length < 2048, 'identity mismatch diagnostics remain bounded');
    const identity = JSON.parse(caught.message.slice(caught.message.indexOf('{')));
    assert.equal(identity.phase, 'registerOwnedRoot.preflight');
    assert.equal(identity.root.uuid, root.uuid);
    assert.equal(identity.object.uuid, child.uuid);
    assert.equal(identity.resolved.uuid, child.uuid);
    assert.equal(identity.sameObject, false);
    assert.deepEqual(manager.records, [root.uuid, child.uuid]);
    assert.ok(Object.hasOwn(manager._uuidDumpMap, root.uuid));
    assert.equal(scope.summary().ownedRootCount, 0);
    assert.equal(scope.summary().pendingOwnedObjectCount, 0);
    scope.finish();
    fixture.probe.uninstall();
});

test('finish reports identities that remain unresolved without cleaning their records', () => {
    const fixture = makeFixture(function (input) { return this.realm.JSON.stringify(input); });
    const manager = new fixture.SceneUndoManager();
    manager.records = [];
    manager._uuidDumpMap = {};
    const registry = new Map();
    const root = {uuid: 'unresolved-root', parent: null, children: [], _components: []};
    const scope = fixture.probe.beginOwnedImportScope(manager, uuid => registry.get(uuid) || null);
    manager.record(root.uuid);
    scope.registerOwnedRoot(root);
    const final = scope.finish();
    assert.equal(final.pendingOwnedObjectCount, 1);
    assert.equal(final.pendingUnresolvedAtFinish, 1);
    assert.ok(manager.records.includes(root.uuid));
    assert.ok(Object.hasOwn(manager._uuidDumpMap, root.uuid));
    fixture.probe.uninstall();
});

test('finish cleans only unresolved constructor residue for explicitly registered, strictly destroyed owned trees', () => {
    const fixture = makeFixture(function (input) { return this.realm.JSON.stringify(input); });
    const manager = new fixture.SceneUndoManager();
    manager.records = ['baseline-user'];
    manager._uuidDumpMap = {'baseline-user': {keep: true}};
    const registry = new Map();
    const root = {uuid: 'destroyed-proxy-root', parent: null, children: [], _components: [], destroyed: false};
    const child = {uuid: 'destroyed-proxy-child', parent: root, children: [], _components: [], destroyed: false};
    root.children.push(child);
    const scope = fixture.probe.beginOwnedImportScope(manager, uuid => registry.has(uuid) ? registry.get(uuid) : null,
        (object, strict) => strict === true && object.destroyed !== true);
    manager.record(root.uuid);
    manager.record(child.uuid);
    scope.registerOwnedRoot(root);
    root.destroyed = true;
    child.destroyed = true;
    const final = scope.finish();
    assert.deepEqual(manager.records, ['baseline-user']);
    assert.deepEqual(manager._uuidDumpMap, {'baseline-user': {keep: true}});
    assert.equal(final.pendingDestroyedOwnedCleanupCount, 2);
    assert.equal(final.pendingUnresolvedAtFinish, 0);
    fixture.probe.uninstall();
});

test('destroyed-pending cleanup preserves baseline, foreign, valid, and resolver-error identities', () => {
    const fixture = makeFixture(function (input) { return this.realm.JSON.stringify(input); });
    const manager = new fixture.SceneUndoManager();
    manager.records = ['baseline-node'];
    manager._uuidDumpMap = {'baseline-node': {keep: true}};
    const objects = {};
    const root = {uuid: 'scope-root', parent: null, children: [], _components: [], destroyed: true};
    const baseline = {uuid: 'baseline-node', parent: root, children: [], _components: [], destroyed: true};
    const foreign = {uuid: 'foreign-pending', parent: root, children: [], _components: [], destroyed: true};
    const valid = {uuid: 'valid-pending', parent: root, children: [], _components: [], destroyed: false};
    const throws = {uuid: 'query-error-pending', parent: root, children: [], _components: [], destroyed: true};
    root.children.push(baseline, foreign, valid, throws);
    const scope = fixture.probe.beginOwnedImportScope(manager, uuid => {
        if (uuid === throws.uuid) throw new Error('query unavailable');
        return Object.hasOwn(objects, uuid) ? objects[uuid] : null;
    }, (object, strict) => strict === true && object.destroyed !== true);
    for (const item of [baseline, foreign, valid, throws]) manager.record(item.uuid);
    scope.registerOwnedRoot(root);
    objects[foreign.uuid] = {uuid: foreign.uuid};
    const final = scope.finish();
    assert.ok(manager.records.includes('baseline-node'));
    assert.ok(Object.hasOwn(manager._uuidDumpMap, 'baseline-node'));
    for (const item of [foreign, valid, throws]) {
        assert.ok(manager.records.includes(item.uuid), item.uuid + ' record preserved');
        assert.ok(Object.hasOwn(manager._uuidDumpMap, item.uuid), item.uuid + ' dump preserved');
    }
    assert.equal(final.pendingDestroyedOwnedCleanupCount, 1, 'only the destroyed registered root itself is eligible');
    assert.ok(final.pendingUnresolvedAtFinish >= 3);
    fixture.probe.uninstall();
});

test('destroyed-pending cleanup is disabled without an injected strict validity API', () => {
    const fixture = makeFixture(function (input) { return this.realm.JSON.stringify(input); });
    const manager = new fixture.SceneUndoManager();
    manager.records = [];
    manager._uuidDumpMap = {};
    const root = {uuid: 'no-validity-root', parent: null, children: [], _components: []};
    const scope = fixture.probe.beginOwnedImportScope(manager, () => null);
    manager.record(root.uuid);
    scope.registerOwnedRoot(root);
    const final = scope.finish();
    assert.deepEqual(manager.records, [root.uuid]);
    assert.ok(Object.hasOwn(manager._uuidDumpMap, root.uuid));
    assert.equal(final.pendingDestroyedOwnedCleanupCount, 0);
    assert.equal(final.pendingUnresolvedAtFinish, 1);
    fixture.probe.uninstall();
});

test('retirement removes only exact destroyed owned identities after UUID queries return null, then permits same-UUID replacement', () => {
    const fixture = makeFixture(function (input) { return this.realm.JSON.stringify(input); });
    const manager = new fixture.SceneUndoManager();
    manager.records = ['user-baseline'];
    manager._uuidDumpMap = {'user-baseline': {keep:true}};
    const registry = new Map();
    const root = {uuid:'retire-root',parent:null,children:[],_components:[],destroyed:false};
    const component = {uuid:'retire-component',node:root,destroyed:false};root._components.push(component);
    registry.set(root.uuid,root);registry.set(component.uuid,component);
    const scope=fixture.probe.beginOwnedImportScope(manager,uuid=>registry.has(uuid)?registry.get(uuid):null,
        (object,strict)=>strict===true&&object.destroyed!==true);
    // Records can precede explicit ownership registration during construction.
    manager.record(root.uuid);manager.record(component.uuid);
    assert.equal(scope.registerOwnedRoot(root).registered,true);
    assert.deepEqual(manager.records,['user-baseline']);
    root.destroyed=true;component.destroyed=true;registry.delete(root.uuid);registry.delete(component.uuid);
    const retired=scope.retireDestroyedOwnedRoot(root,[
        {kind:'node',uuid:root.uuid,object:root},{kind:'component',uuid:component.uuid,object:component},
    ]);
    assert.equal(retired.retired,true);assert.equal(retired.retiredObjectCount,2);
    assert.deepEqual(manager.records,['user-baseline']);
    assert.deepEqual(manager._uuidDumpMap,{'user-baseline':{keep:true}});
    assert.equal(scope.summary().ownedRootCount,0,'retired descendant root handles do not retain old identities');
    const replacement={uuid:root.uuid,parent:null,children:[],_components:[],destroyed:false};
    registry.set(replacement.uuid,replacement);
    assert.equal(scope.registerOwnedRoot(replacement).registered,true,
        'same UUID can bind to the new serialized-scene object only after old identity retirement');
    assert.equal(scope.summary().ownedObjectCount,1);
    scope.finish();fixture.probe.uninstall();
});

test('retirement rejects live identities, foreign replacements, query errors, and nonowned roots', () => {
    const scenarios=[
        {name:'still-valid',registryMode:'null',destroyed:false,expected:'strict-destroyed-state-unverified'},
        {name:'foreign-same-uuid',registryMode:'foreign',destroyed:true,expected:'resolver-still-resolves-or-foreign'},
        {name:'query-error',registryMode:'throw',destroyed:true,expected:'validity-or-resolver-query-failed'},
    ];
    for(const scenario of scenarios){
        const fixture=makeFixture(function(input){return this.realm.JSON.stringify(input);});
        const manager=new fixture.SceneUndoManager();manager.records=[];manager._uuidDumpMap={};
        const root={uuid:'retire-'+scenario.name,parent:null,children:[],_components:[],destroyed:false};
        const registry=new Map([[root.uuid,root]]);
        let behavior='exact';
        const resolver=uuid=>{
            if(behavior==='throw')throw Error('query failed');
            if(behavior==='foreign')return {uuid,destroyed:true};
            return registry.get(uuid)||null;
        };
        const scope=fixture.probe.beginOwnedImportScope(manager,resolver,(object,strict)=>strict===true&&object.destroyed!==true);
        scope.registerOwnedRoot(root);root.destroyed=scenario.destroyed;behavior=scenario.registryMode;
        if(scenario.registryMode==='null')registry.delete(root.uuid);
        const result=scope.retireDestroyedOwnedRoot(root,[{kind:'node',uuid:root.uuid,object:root}]);
        assert.equal(result.retired,false,scenario.name);
        assert.equal(result.reason,scenario.expected,scenario.name);
        assert.equal(scope.summary().ownedObjectCount,1,scenario.name+' ownership retained');
        scope.finish();fixture.probe.uninstall();
    }
    const fixture=makeFixture(function(input){return this.realm.JSON.stringify(input);});
    const manager=new fixture.SceneUndoManager();manager.records=['baseline-user'];manager._uuidDumpMap={'baseline-user':{keep:true}};
    const registry=new Map();const scope=fixture.probe.beginOwnedImportScope(manager,uuid=>registry.get(uuid)||null,
        (object,strict)=>strict===true&&object.destroyed!==true);
    const foreignRoot={uuid:'never-registered-root',parent:null,children:[],_components:[],destroyed:true};
    const denied=scope.retireDestroyedOwnedRoot(foreignRoot,[{kind:'node',uuid:foreignRoot.uuid,object:foreignRoot}]);
    assert.equal(denied.retired,false);assert.equal(denied.reason,'root-not-registered-by-this-scope');
    assert.deepEqual(manager.records,['baseline-user']);
    assert.deepEqual(manager._uuidDumpMap,{'baseline-user':{keep:true}});
    scope.finish();fixture.probe.uninstall();
});

test('counts cycles, repeated aliases, Node identities, size and traversal caps without copying contents', () => {
    class Node { constructor(name) { this.name = name; this.uuid = 'node-uuid'; } }
    const shared = {privateText: 'credential-shaped-payload'};
    const node = new Node('UI node');
    const input = {left: shared, right: shared, node};
    shared.owner = input;
    const stats = diagnostics.summarizeStructure(input, {cc: {Node}}, {maxObjects: 10, maxEdges: 20});
    assert.equal(stats.objects, 3);
    assert.ok(stats.aliases >= 1);
    assert.ok(stats.cycles >= 1);
    assert.equal(stats.nodeSamples[0].name, 'UI node');
    assert.equal(stats.nodeSamples[0].uuid, 'node-uuid');
    assert.equal(stats.maxStringLength, 'credential-shaped-payload'.length);
    assert.ok(stats.estimatedUniqueGraphCharsUpperBound > 0);
    assert.ok(!JSON.stringify(stats).includes('credential-shaped-payload'));
    const bounded = diagnostics.summarizeStructure({items: Array.from({length: 20}, () => ({value: 'x'}))},
        globalThis, {maxObjects: 4, maxEdges: 4, maxDepth: 8});
    assert.ok(bounded.objects <= 4);
    assert.ok(bounded.edges <= 4);
    assert.ok(bounded.truncatedObjects || bounded.truncatedEdges);
});

test('restores the exact JSON.stringify descriptor even when snapshot throws', () => {
    const realm = {JSON: {stringify: value => JSON.stringify(value)}};
    const originalDescriptor = Object.getOwnPropertyDescriptor(realm.JSON, 'stringify');
    const fixture = makeFixture(function (input) {
        this.realm.JSON.stringify(input);
        throw new RangeError('Invalid string length');
    });
    fixture.probe.uninstall();
    const records = [];
    const probe = diagnostics.install({realm, requireFn: fixture.requireFn, onRecord: row => records.push(row)});
    const manager = new fixture.SceneUndoManager(); manager.realm = realm;
    assert.throws(() => manager.snapshot({data: 'bounded'}), RangeError);
    assert.deepEqual(Object.getOwnPropertyDescriptor(realm.JSON, 'stringify'), originalDescriptor);
    assert.equal(records[0].error.name, 'RangeError');
    probe.uninstall();
});

test('restores JSON immediately for thenable snapshots and reports async capture unsupported', async () => {
    const realm = {JSON: {stringify: value => JSON.stringify(value)}};
    const fixture = makeFixture(async function (input) {
        await Promise.resolve();
        return this.realm.JSON.stringify(input);
    });
    fixture.probe.uninstall();
    const records = [];
    const probe = diagnostics.install({realm, requireFn: fixture.requireFn, onRecord: row => records.push(row)});
    const manager = new fixture.SceneUndoManager(); manager.realm = realm;
    const pending = manager.snapshot({after: 'await'});
    assert.equal(records[0].asynchronousSnapshotUnsupported, true);
    assert.equal(records[0].stringifyHookInstalled, true);
    assert.equal(records[0].stringifyInputs.length, 0);
    assert.equal(await pending, '{"after":"await"}');
    assert.equal(realm.JSON.stringify({restored: true}), '{"restored":true}');
    probe.uninstall();
});

test('does not patch when the specific builtin cache module or class is absent', () => {
    const noModule = diagnostics.install({realm: {JSON}, requireFn: {cache: {}}});
    assert.equal(noModule.installed, false);
    assert.equal(noModule.reason, 'scene-undo-manager-not-loaded');
    const wrongClass = diagnostics.install({realm: {JSON}, requireFn: {cache: {
        '/creator/builtin/scene/dist/script/export/undo/scene.ccc': {exports: {Other: class Other { snapshot() {} }}},
    }}});
    assert.equal(wrongClass.installed, false);
    assert.equal(wrongClass.reason, 'scene-undo-manager-not-loaded');
});
