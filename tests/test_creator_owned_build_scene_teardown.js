'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const teardown = require('../src/monkey/targets/CreatorOwnedBuildSceneTeardown.js');
const ownedUndo = require('../src/monkey/targets/CreatorOwnedImportUndo.js');

function fixture(options = {}) {
    const directNodes = new Map(), directComponents = new Map();
    const recycleNode = Object.create(null), recycleComponent = Object.create(null);
    const calls = [];
    let serial = 0;
    class Scene {
        constructor(name) { this.name=name; this.uuid='owned-scene-'+(++serial); this.children=[]; this._components=[]; this.parent=null; this.destroyCalls=0; }
        destroy() { this.destroyCalls++; this.destroyRequested=true; return true; }
    }
    const general = {
        _recycleNode:recycleNode, _recycleComponent:recycleComponent,
        queryCurrentSceneUuid:()=> 'active-user-scene-asset',
        queryRecycleNode(uuid) { return this._recycleNode[uuid] ?? null; },
        queryRecycleComponent(uuid) { return this._recycleComponent[uuid] ?? null; },
    };
    const manager = (direct, recycle) => ({
        query(uuid) { return direct.get(uuid) ?? recycle[uuid] ?? null; },
        remove() { throw new Error('NodeManager.remove must not be called'); },
    });
    const nodeManager=manager(directNodes,recycleNode), componentManager=manager(directComponents,recycleComponent);
    general._nodeMgr=nodeManager; general._compMgr=componentManager;
    const cce={SceneFacadeManager:{_facadeFSM:{currentState:{modeName:'general'},generalSceneFacade:general}},
        Node:{query:uuid=>nodeManager.query(uuid)},Component:{query:uuid=>componentManager.query(uuid)}};
    const cc={Scene,isValid:(object,strict)=>!!object&&!(strict&&object.destroyed),
        director:{getScene:()=>options.directorScene||{uuid:'active-user-scene'}},
        CCObject:{_deferredDestroy(){calls.push('flush');if(options.flushThrows)throw Error('flush failed');
            for(const [uuid,node] of [...directNodes]) {
                const subtree=[];const walk=n=>{subtree.push(n);for(const child of n.children||[])walk(child);};walk(node);
                if(node.destroyRequested||subtree.some(n=>n.destroyRequested))for(const n of subtree) {
                    if(n.uuid===options.keepValidUuid)continue;
                    n.destroyed=true;directNodes.delete(n.uuid);
                    if(!Object.hasOwn(recycleNode,n.uuid))recycleNode[n.uuid]=n;
                    for(const comp of n._components||[]) {
                        comp.destroyed=true;directComponents.delete(comp.uuid);
                        if(!Object.hasOwn(recycleComponent,comp.uuid))recycleComponent[comp.uuid]=comp;
                    }
                }
            }
        }}};
    const scene=teardown.create(cc,'Candidate');
    directNodes.set(scene.uuid,scene);
    const canvas={uuid:'owned-canvas-'+serial,children:[],_components:[],parent:scene};
    scene.children.push(canvas);directNodes.set(canvas.uuid,canvas);
    const transform={uuid:'owned-ui-'+serial,node:canvas};canvas._components.push(transform);directComponents.set(transform.uuid,transform);
    const foreignUuid=options.foreignUuid || null;
    if(foreignUuid)recycleNode[foreignUuid]={uuid:foreignUuid,children:[],_components:[],foreign:true};
    return {cc,cce,general,scene,canvas,transform,directNodes,directComponents,recycleNode,recycleComponent,calls,
        async cleanup(primaryError=null) { return teardown.cleanupAfterBuild(scene,{cc,cce,dynamicRelease:async value=>{assert.equal(value,scene);calls.push('release');}},primaryError); }};
}

test('normal owned build teardown releases, destroys, flushes, and removes only exact owned tombstones', async()=>{
    const value=fixture();
    value.recycleNode['unrelated-user-node']={uuid:'unrelated-user-node',foreign:true};
    const result=await value.cleanup();
    assert.equal(result.cleaned,true);assert.equal(result.error,null);
    assert.deepEqual(value.calls,['release','flush']);
    assert.equal(value.scene.destroyCalls,1);
    assert.equal(value.cce.Node.query(value.scene.uuid),null);
    assert.equal(value.cce.Node.query(value.canvas.uuid),null);
    assert.equal(value.cce.Component.query(value.transform.uuid),null);
    assert.ok(value.recycleNode['unrelated-user-node']);
    assert.equal(result.postCleanup.tombstonesRemovedCount,3);
});

test('foreign same-UUID recycle value is preserved', async()=>{
    const value=fixture({foreignUuid:'owned-canvas-1'});
    const foreign=value.recycleNode['owned-canvas-1'];
    const result=await value.cleanup();
    assert.strictEqual(value.recycleNode['owned-canvas-1'],foreign);
    assert.equal(value.cce.Node.query('owned-canvas-1'),foreign);
    assert.equal(result.postCleanup.tombstonesRemoved.some(row=>row.uuid==='owned-canvas-1'),false);
});

test('strict-valid tree members are never purged', async()=>{
    const value=fixture({keepValidUuid:'owned-canvas-1'});
    const result=await value.cleanup();
    assert.strictEqual(value.cce.Node.query('owned-canvas-1'),value.canvas);
    assert.equal(value.recycleNode['owned-canvas-1'],undefined);
    assert.equal(result.cleaned,false);
    assert.equal(result.error.code,'CREATOR_BUILD_SCENE_TEARDOWN_FAILED');
});

test('deferred destroy failure preserves all exact and foreign cache entries', async()=>{
    const value=fixture({flushThrows:true});
    const nodeBefore=value.cce.Node.query(value.canvas.uuid);
    const result=await value.cleanup();
    assert.strictEqual(value.cce.Node.query(value.canvas.uuid),nodeBefore);
    assert.equal(result.cleaned,false);
    assert.equal(result.postCleanup.tombstonesRemovedCount,0);
});

test('assemble error remains primary while its finally cleanup still runs', async()=>{
    const value=fixture();const assembleError=Error('assembly failed');let caught;
    try { throw assembleError; }
    catch(error) { caught=error; }
    finally { await teardown.cleanupAfterBuild(value.scene,{cc:value.cc,cce:value.cce,
        dynamicRelease:async()=>value.calls.push('release')},caught); }
    assert.strictEqual(caught,assembleError);
    assert.equal(caught.cleanupError,undefined);
    assert.deepEqual(value.calls,['release','flush']);
    assert.equal(value.cce.Node.query(value.scene.uuid),null);
});

test('teardown retires only its exact Undo identities so the saved Scene can register same UUIDs',async()=>{
    const value=fixture();
    class SceneUndoManager {
        constructor(){this.records=[];this._uuidDumpMap={};}
        snapshot(){return null;}
        record(uuid,dump=true){if(!this.records.includes(uuid)){if(dump)this._uuidDumpMap[uuid]={undo:true};this.records.push(uuid);}}
    }
    const undoMgr=new SceneUndoManager();
    value.general._undoMgr=undoMgr;
    const filename='/creator/builtin/scene/dist/script/export/undo/scene.ccc';
    const requireFn=name=>name==='cc'?value.cc:(()=>{throw Error('unexpected module '+name);})();
    requireFn.cache={[filename]:{exports:{SceneUndoManager}}};
    const realm={JSON:{stringify:(...args)=>JSON.stringify(...args)}};
    const scope=ownedUndo.start(value.cce,realm,requireFn);
    ownedUndo.registerRoot(value.scene);ownedUndo.registerRoot(value.canvas);
    const oldRootUuid=value.scene.uuid;
    const result=await value.cleanup();
    assert.equal(result.cleaned,true);
    assert.equal(result.postCleanup.undoRetirement.retired,true);
    assert.equal(result.postCleanup.undoRetirement.retiredObjectCount,3);
    assert.equal(scope.scope.ownedObjectCount,0);
    const replacement=new value.cc.Scene('CandidateReloaded');replacement.uuid=oldRootUuid;
    value.directNodes.set(oldRootUuid,replacement);
    assert.equal(ownedUndo.registerRoot(replacement).registered,true,
        'same-UUID saved Scene object is accepted only after old exact object is dead and unresolved');
    ownedUndo.finish();
});
