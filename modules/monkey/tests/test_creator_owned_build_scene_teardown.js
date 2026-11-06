'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const teardown = require('../src/monkey/targets/CreatorOwnedBuildSceneTeardown.js');
const ownedUndo = require('../src/monkey/targets/CreatorOwnedImportUndo.js');

function fixture(options = {}) {
    const directNodes = new Map(), directComponents = new Map(), globalQueue=[];
    const recycleNode = Object.create(null), recycleComponent = Object.create(null);
    const calls = [];
    let serial = 0;
    class Scene {
        constructor(name) { this.name=name; this.uuid='owned-scene-'+(++serial); this.children=[]; this._components=[]; this.parent=null; this.destroyCalls=0; this.destroyImmediateCalls=0; }
        destroy() { this.destroyCalls++;if(this.toDestroy||this.destroyed)return false;this.toDestroy=true;calls.push('destroy');return true; }
        _destroyImmediate() {
            this.destroyImmediateCalls++;calls.push('destroy-immediate');
            if(options.immediateThrows)throw Error('immediate destroy failed');
            const destroyNode=node=>{
                for(const child of [...(node.children||[])])destroyNode(child);
                for(const comp of node._components||[]) {
                    if(comp.uuid===options.keepValidUuid)continue;
                    comp.destroyed=true;comp.toDestroy=false;directComponents.delete(comp.uuid);
                    if(!Object.hasOwn(recycleComponent,comp.uuid))recycleComponent[comp.uuid]=comp;
                }
                if(node.uuid!==options.keepValidUuid) {
                    node.destroyed=true;node.toDestroy=false;directNodes.delete(node.uuid);
                    if(!Object.hasOwn(recycleNode,node.uuid))recycleNode[node.uuid]=node;
                }
            };
            destroyNode(this);
        }
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
    const cc={Scene,isValid:(object,strict)=>!!object&&!object.destroyed&&!(strict&&object.toDestroy),
        director:{getScene:()=>options.directorScene||{uuid:'active-user-scene'}},
        CCObject:{_deferredDestroy(){calls.push('global-deferred-destroy');for(const object of globalQueue){object.toDestroy=false;object.destroyed=true;}}}};
    const scene=teardown.create(cc,'Candidate');
    directNodes.set(scene.uuid,scene);
    const canvas={uuid:'owned-canvas-'+serial,children:[],_components:[],parent:scene};
    scene.children.push(canvas);directNodes.set(canvas.uuid,canvas);
    const transform={uuid:'owned-ui-'+serial,node:canvas};canvas._components.push(transform);directComponents.set(transform.uuid,transform);
    const foreignUuid=options.foreignUuid || null;
    if(foreignUuid)recycleNode[foreignUuid]={uuid:foreignUuid,children:[],_components:[],foreign:true};
    return {cc,cce,general,scene,canvas,transform,directNodes,directComponents,recycleNode,recycleComponent,globalQueue,calls,
        async cleanup(primaryError=null) { return teardown.cleanupAfterBuild(scene,{cc,cce,dynamicRelease:async value=>{assert.equal(value,scene);calls.push('release');}},primaryError); }};
}

test('normal owned build teardown queues and immediately destroys only its exact owned root', async()=>{
    const value=fixture();
    value.recycleNode['unrelated-user-node']={uuid:'unrelated-user-node',foreign:true};
    const result=await value.cleanup();
    assert.equal(result.cleaned,true);assert.equal(result.error,null);
    assert.deepEqual(value.calls,['release','destroy','destroy-immediate']);
    assert.equal(result.postCleanup.sceneDestroyQueued,true);
    assert.equal(value.scene.destroyImmediateCalls,1);
    assert.equal(value.cce.Node.query(value.scene.uuid),null);
    assert.equal(value.cce.Node.query(value.canvas.uuid),null);
    assert.equal(value.cce.Component.query(value.transform.uuid),null);
    assert.ok(value.recycleNode['unrelated-user-node']);
    assert.equal(result.postCleanup.tombstonesRemovedCount,3);
});

test('Creator ToDestroy objects remain live and are safely retired through their exact owned root',async()=>{
    const value=fixture();value.scene.toDestroy=true;value.canvas.toDestroy=true;value.transform.toDestroy=true;
    const result=await value.cleanup();
    assert.equal(result.cleaned,true);
    assert.deepEqual(value.calls,['release','destroy-immediate']);
    assert.equal(value.scene.destroyCalls,0);
    assert.equal(result.postCleanup.sceneDestroyQueued,false);
    assert.ok(result.postCleanup.beforeDestroy.some(row=>row.uuid===value.canvas.uuid&&row.state==='queued-to-destroy'));
    assert.equal(value.cc.isValid(value.canvas,false),false);
});

test('already Destroyed owned members still block cleanup before release or tombstone purging',async()=>{
    const value=fixture();value.transform.destroyed=true;
    const direct=value.cce.Component.query(value.transform.uuid);
    const result=await value.cleanup();
    assert.equal(result.cleaned,false);
    assert.equal(result.error.code,'CREATOR_BUILD_SCENE_TREE_NOT_LIVE_BEFORE_CLEANUP');
    assert.deepEqual(value.calls,[]);
    assert.strictEqual(value.cce.Component.query(value.transform.uuid),direct);
});

test('owned immediate destroy never flushes unrelated Creator destruction queue entries',async()=>{
    const value=fixture();const unrelated={uuid:'unrelated-queued-object',toDestroy:true,destroyed:false};
    const foreign={uuid:'foreign-recycle-object',foreign:true};value.recycleNode[unrelated.uuid]=unrelated;
    value.globalQueue.push(unrelated);
    value.recycleNode['foreign-recycle-object']=foreign;
    const result=await value.cleanup();
    assert.equal(result.cleaned,true);
    assert.equal(unrelated.destroyed,false);assert.equal(unrelated.toDestroy,true);
    assert.strictEqual(value.recycleNode['foreign-recycle-object'],foreign);
    assert.equal(result.postCleanup.globalDeferredDestroyCalled,false);
    assert.equal(value.calls.includes('global-deferred-destroy'),false);
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

test('exact immediate destroy failure preserves all exact and foreign cache entries', async()=>{
    const value=fixture({immediateThrows:true});
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
    assert.deepEqual(value.calls,['release','destroy','destroy-immediate']);
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
