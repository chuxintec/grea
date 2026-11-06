'use strict';
// Creator 3.8.8 Editor-only assembly. Native PrefabInfo/overrides are serialized
// by the installed SDK; no source graph or interpreter is included in Player.
const cc=require('cc');
const dynamic=require('./dynamic-ui.js');
const ownedUndo=require('./owned-import-undo.js');
const sourceChildren=require('./static-richtext.js').sourceChildren;
const sortQueue=require('./CreatorStaticSortQueueIntegration.js');
let current=null,sequence=0;
const api=()=>{
    const u=cc.Prefab._utils,p=globalThis.EditorExtends&&EditorExtends.PrefabUtils;
    if(!u||!p||!u.generateTargetMap||!p.addPrefabInfo||!p.checkAndStripNode)throw Error('Native Prefab SDK unavailable');
    return {u,p};
};
function sourceTemplateNode(plan,id) {
    const origins=new Map(),nodes=new Set(plan.nodes.map(n=>n.sourceId));
    for(const relation of plan.syncPrefabBindings||[])for(const pair of relation.origins||[]) {
        if(!nodes.has(pair.instanceSourceId)||!nodes.has(pair.templateSourceId)||
            origins.has(pair.instanceSourceId)&&origins.get(pair.instanceSourceId)!==pair.templateSourceId)
            throw Error('Native sync node origin differs');
        origins.set(pair.instanceSourceId,pair.templateSourceId);
    }
    const seen=new Set();
    while(origins.has(id)){if(seen.has(id))throw Error('Native sync node origin cycle');seen.add(id);id=origins.get(id);}
    return id;
}
const nativeClass=name=>name==='sp.Skeleton'?cc.sp.Skeleton:typeof name==='string'&&name.startsWith('cc.')?cc[name.slice(3)]:undefined;
function markMounted(object,root){
    // Match the native SDK's applyMountedChildren/applyMountedComponents editor
    // bookkeeping so checkAndStripNode retains additions to an instance.
    if(!cc.editorExtrasTag)throw Error('Native editor extras tag unavailable');
    object[cc.editorExtrasTag]??={};object[cc.editorExtrasTag].mountedRoot=root;
}
function serializeNative(root,asset){
    // The SDK strips live object IDs for native instance serialization. They
    // must be restored before destroying our temporary tree: Scheduler cleanup
    // still needs each live Component's actual ID, not its Prefab fileID.
    const ids=[];
    function walk(n){ids.push([n,n._id]);for(const c of n.components)ids.push([c,c._id]);n.children.forEach(walk);}walk(root);
    function checkMounted(stage){
        const snapshots=[];
        const owned=new Set();function gather(n){owned.add(n);n.children.forEach(gather);}gather(root);
        function visit(n){for(const group of n._prefab?.instance?.mountedComponents||[])for(const c of group.components||[]){
            if(!c||!cc.isValid(c,true)||!c.node||!owned.has(c.node)||!c.node.components.includes(c))throw Error('Mounted native component invalid '+stage+': '+JSON.stringify({node:n.name,component:c&&cc.js.getClassName(c),flags:c&&c._objFlags,owner:c&&c.node&&c.node.name,owned:!!(c&&owned.has(c.node)),attached:!!(c&&c.node&&c.node.components.includes(c)),prefab:c&&c.__prefab}));
            snapshots.push({stage,node:n.name,component:cc.js.getClassName(c),flags:c._objFlags,nodeFlags:c.node._objFlags,prefab:c.__prefab,target:group.targetInfo.localID});
        }n.children.forEach(visit);}visit(root);return snapshots;
    }
    try{recordNativeInstanceReferences(root);const before=checkMounted('before strip');api().p.checkAndStripNode(root,true);const after=checkMounted('after strip');
        // The default SDK parser discards components under a syncable instance
        // root even when the native mountedComponents table references them.
        // Use its explicit native retention option for those additions; linked
        // PrefabInfo/instance records and template hashes remain independently
        // checked after native expansion, rather than rewriting serialized JSON.
        const options=after.length?{reserveContentsForSyncablePrefab:true}:undefined;
        const raw=EditorExtends.serialize(asset,options),text=typeof raw==='string'?raw:JSON.stringify(raw);
        const records=JSON.parse(text);if(Array.isArray(records)&&records.some(x=>x?.__type__==='cc.MountedComponentsInfo'&&x.components.some(c=>c===null)))throw Error('Native serializer dropped mounted component: '+JSON.stringify({before,after}));
        return text;}
    finally{for(const [obj,id]of ids){obj._id=id;if(obj instanceof cc.Component&&!obj.uuid)cc.Scheduler.enableForTarget(obj);}}
}
function session(id,plan) {
    if(!current||current.id!==id||current.plan!==plan&&current.plan.projectUuid!==plan.projectUuid)throw Error('Native assembly session differs');
    if(plan.nativeDeadlineMs!=null&&Date.now()>=plan.nativeDeadlineMs)throw Error('NATIVE_BUDGET_EXHAUSTED');
    return current;
}
function keep(plan,scene,nodes,result,nativeAssets){if(current)throw Error('Native assembly session already exists');current={id:'prefabs-'+(++sequence),plan,scene,nodes,result,nativeAssets:new Map(nativeAssets||[]),prepared:new Set()};return current.id;}
function release(id){if(current&&current.id===id){dynamic.release(current.scene);current.scene.destroy();current=null;}}
function mapTree(root,spec,plan) {
    const source=new Map(plan.nodes.map(n=>[n.sourceId,n])),mapped=new Map();
    function walk(id,node){const s=source.get(id),children=node&&sourceChildren(node);if(!s||!node||s.children.length!==children.length)throw Error('Native template topology differs: '+id);mapped.set(id,node);s.children.forEach((child,i)=>walk(child,children[i]));}
    walk(spec.root,root);return mapped;
}
function value(v,replacements=new Map()) {
    if(v==null||['string','number','boolean'].includes(typeof v))return v;
    if(replacements.has(v))return replacements.get(v);
    if(v instanceof cc.Node||v instanceof cc.Component||v instanceof cc.Asset)return v;
    if(Array.isArray(v))return v.map(x=>value(x,replacements));
    if(v instanceof cc.ValueType&&typeof v.clone==='function')return v.clone();
    if(Object.getPrototypeOf(v)===Object.prototype)return Object.fromEntries(Object.entries(v).map(([k,x])=>[k,value(x,replacements)]));
    const name=cc.js.getClassName(v),ctor=v.constructor,keys=ctor&&ctor.__values__;
    if(typeof name==='string'&&(name.startsWith('Monkey.StaticFields.')||['MonkeyStaticAnimationClipSlot','MonkeyStaticLayoutSlot','MonkeyStaticWidgetSlot'].includes(name))&&cc.js.getClassByName(name)===ctor&&Array.isArray(keys)) {
        const copy=new ctor();for(const key of keys)copy[key]=value(v[key],replacements);return copy;
    }
    throw Error('Unsupported native serialized override value');
}
function equal(a,b) {
    if(a===b)return true;if(a==null||b==null)return false;
    if(a instanceof cc.Asset&&b instanceof cc.Asset)return !!a._uuid&&a._uuid===b._uuid;
    if(a instanceof cc.Node||a instanceof cc.Component||b instanceof cc.Node||b instanceof cc.Component)return false;
    if(a.constructor!==b.constructor)return false;
    if(Array.isArray(a))return a.length===b.length&&a.every((v,i)=>equal(v,b[i]));
    if(typeof a==='object'){const keys=Object.keys(a);return keys.length===Object.keys(b).length&&keys.every(k=>equal(a[k],b[k]));}
    return false;
}
const excluded=new Set(['node','__prefab','_id','_objFlags','_name']);
function componentFields(comp){const keys=comp.constructor.__values__;if(!Array.isArray(keys))throw Error('Native component serialization schema absent');return keys.filter(k=>!excluded.has(k));}
function targetIds(root) {
    const {u}=api(),map={};u.generateTargetMap(root,map,true);const inverse=new Map();
    function walk(v,path){for(const [key,obj]of Object.entries(v)){const p=[...path,key];if(obj instanceof cc.Node||obj instanceof cc.Component)inverse.set(obj,p);else if(obj&&typeof obj==='object')walk(obj,p);}}
    walk(map,[]);return inverse;
}
function delta(instance,obj,key,v,ids) {
    if(equal(obj[key],v))return;
    const localID=ids.get(obj);if(!localID)throw Error('Native override target has no scoped fileID');
    const {u}=api(),patch=new u.PropertyOverrideInfo(),target=new u.TargetInfo();target.localID=localID;
    patch.targetInfo=target;patch.propertyPath=[key];patch.value=value(v);instance.propertyOverrides.push(patch);obj[key]=value(v);
}
function instanceRoots(root){const result=[];function walk(n){if(n!==root&&n._prefab&&n._prefab.instance){result.push(n);return;}sourceChildren(n).forEach(walk);}walk(root);return result;}
function recordNativeInstanceReferences(root) {
    const roots=instanceRoots(root);if(!roots.length)return;
    const {u}=api();
    if(!u.TargetOverrideInfo||!u.TargetInfo||!u.PropertyOverrideInfo||!root._prefab)
        throw Error('Native Prefab reference override SDK unavailable');
    const scoped=new Map();
    for(const instanceRoot of roots) {
      const templateRoot=instanceRoot._prefab.asset?.data;
      if(!(templateRoot instanceof cc.Node))throw Error('Native instance template unavailable for state comparison');
      const templateByPath=new Map([...targetIds(templateRoot)].map(([object,path])=>[JSON.stringify(path),object]));
      for(const [object,localID]of targetIds(instanceRoot)) {
        if(scoped.has(object))throw Error('Ambiguous native instance reference scope');
        scoped.set(object,{root:instanceRoot,localID});
        // Runtime changes made while composing an outer Prefab must survive
        // template expansion. In particular, nested presentation roots remain
        // disabled and authored source layers are restored before serialization.
        if(object instanceof cc.Node)for(const key of ['_active','_layer']) {
            const instance=instanceRoot._prefab.instance;
            const template=templateByPath.get(JSON.stringify(localID));
            // Mounted children retain their own native serialization. Existing
            // template nodes only need an override when their value differs.
            if(!template)continue;
            if(!(template instanceof cc.Node))throw Error('Native node state template type mismatch');
            instance.propertyOverrides??=[];
            const matches=instance.propertyOverrides.filter(p=>equal(p.targetInfo?.localID,localID)&&equal(p.propertyPath,[key]));
            if(matches.length>1)throw Error('Duplicate native node-state override');
            if(equal(template[key],object[key])){
                if(matches.length)instance.propertyOverrides.splice(instance.propertyOverrides.indexOf(matches[0]),1);
                continue;
            }
            const patch=matches[0]||new u.PropertyOverrideInfo();
            if(!matches.length){patch.targetInfo=new u.TargetInfo();patch.targetInfo.localID=[...localID];patch.propertyPath=[key];instance.propertyOverrides.push(patch);}
            patch.value=value(object[key]);
        }
      }
    }
    root._prefab.targetOverrides??=[];
    function reference(source,path,target) {
        const destination=scoped.get(target);if(!destination)return;
        const origin=scoped.get(source);
        if(origin?.root===destination.root)return; // template-local native refs
        const sourceObject=origin?.root||source,sourceID=origin?.localID||null;
        const matches=root._prefab.targetOverrides.filter(p=>p.source===sourceObject&&
            equal(p.sourceInfo?.localID||null,sourceID)&&equal(p.propertyPath,path));
        if(matches.length>1)throw Error('Duplicate native cross-instance reference override');
        if(matches.length&&(matches[0].target!==destination.root||!equal(matches[0].targetInfo?.localID,destination.localID)))
            throw Error('Conflicting native cross-instance reference override');
        const patch=matches[0]||new u.TargetOverrideInfo();
        patch.source=sourceObject;patch.sourceInfo=null;
        if(origin){patch.sourceInfo=new u.TargetInfo();patch.sourceInfo.localID=[...sourceID];}
        patch.propertyPath=[...path];patch.target=destination.root;
        patch.targetInfo=new u.TargetInfo();patch.targetInfo.localID=[...destination.localID];
        if(!matches.length)root._prefab.targetOverrides.push(patch);
    }
    function inspect(source,item,path,ancestors) {
        if(item==null||typeof item!=='object')return;
        if(item instanceof cc.Node||item instanceof cc.Component){reference(source,path,item);return;}
        if(item instanceof cc.Asset||item instanceof cc.ValueType)return;
        if(ancestors.has(item))throw Error('Cyclic native serialized reference value');
        const next=new Set(ancestors);next.add(item);
        const keys=Array.isArray(item)?item.map((_,i)=>String(i)):
            Object.getPrototypeOf(item)===Object.prototype?Object.keys(item):item.constructor?.__values__;
        if(!Array.isArray(keys))throw Error('Native reference override value schema absent');
        for(const key of keys)inspect(source,item[key],[...path,key],next);
    }
    function visit(node){for(const component of node.components)for(const key of componentFields(component))
        inspect(component,component[key],[key],new Set());node.children.forEach(visit);}
    visit(root);
}
async function prepare(state,owner,saved,load) {
    if(state.prepared.has(owner))return;
    const {plan,nodes}=state,specs=new Map(plan.sourcePrefabs.map(p=>[p.sourceId,p]));
    for(const link of (plan.prefabInstances||[]).filter(x=>x.owner===owner&&x.outermost)) {
        const info=saved.find(x=>x.sourceId===link.template),spec=specs.get(link.template);
        if(!info||!info.sha256)throw Error('Native template must be saved first');
        const asset=await load(info.uuid,cc.Prefab),root=cc.instantiate(asset),previous=nodes.get(link.root),parent=previous.parent,index=previous.getSiblingIndex();
        ownedUndo.registerRoot(root);
        if(!root._prefab||!root._prefab.instance||root._prefab.asset._uuid!==info.uuid)throw Error('SDK did not create a native Prefab instance');
        const template=mapTree(root,spec,plan),replacements=new Map(),components=[],added=[];
        const ids=targetIds(root),instance=root._prefab.instance,{u}=api();
        for(const pair of link.nodes){const old=nodes.get(pair.instanceObject),node=template.get(pair.templateObject);if(!old||!node)throw Error('Instance node correspondence absent');replacements.set(old,node);
            // Opacity curves add a native UIOpacity authoring dependency to the
            // standalone template. Recreate that same planned dependency on
            // the source instance before comparing native component sets.
            if(node.getComponent(cc.UIOpacity)&&!old.getComponent(cc.UIOpacity)) {
                const authored=(plan.animations||[]).some(a=>a.convertible&&(a.tracks||[]).some(t=>t.node===sourceTemplateNode(plan,pair.templateObject)&&t.property.split('.')[0]==='opacity'));
                if(authored){const source=plan.nodes.find(n=>n.sourceId===pair.instanceObject);const opacity=old.addComponent(cc.UIOpacity);opacity.opacity=source.opacity;}
            }
            const sourceMask=old.getComponent(cc.Mask),templateMask=node.getComponent(cc.Mask);
            if(sourceMask&&templateMask&&sourceMask.type===templateMask.type&&node.getComponent(cc.Graphics)&&!old.getComponent(cc.Graphics)) {
                if(sourceMask.type!==cc.Mask.Type.GRAPHICS_RECT&&sourceMask.type!==cc.Mask.Type.GRAPHICS_ELLIPSE)throw Error('Unexpected native Mask graphics dependency');
                // Creator 3.8.8 Mask.onLoad authors its native Graphics helper.
                // Materialize it on inactive source nodes as the saved template
                // already has, without activating any recovered user scripts.
                sourceMask.onLoad();
            }
            const used=new Map();for(const from of old.components){const cls=from.constructor,i=used.get(cls)||0;used.set(cls,i+1);let to=node.getComponents(cls)[i];
                if(!to){
                    const mounted=(link.mountedComponents||[]).find(m=>m.node===pair.instanceObject&&nativeClass(m.nativeType)===cls);
                    if(!mounted||!u.MountedComponentsInfo)throw Error('Native mounted component has no typed source delta: '+pair.instanceObject+':'+cc.js.getClassName(cls));
                    const localID=ids.get(node);if(!localID)throw Error('Native mounted component parent has no scoped fileID');
                    to=node.addComponent(cls);to.__prefab=new u.CompPrefabInfo();to.__prefab.fileId=to.uuid;
                    if(!to.__prefab.fileId)throw Error('Mounted native component fileID unavailable');
                    markMounted(to,root);const group=new u.MountedComponentsInfo();group.targetInfo=new u.TargetInfo();group.targetInfo.localID=localID;group.components=[to];instance.mountedComponents.push(group);added.push(to);
                }
                replacements.set(from,to);components.push([from,to]);}
            if(node.components.length!==old.components.length)throw Error('Removed component needs native delta adapter: '+JSON.stringify({instanceNode:pair.instanceObject,templateNode:pair.templateObject,source:old.components.map(c=>cc.js.getClassName(c)),template:node.components.map(c=>cc.js.getClassName(c))}));
        }
        for(const mount of link.mountedChildren||[]){
            const oldParent=nodes.get(mount.parent),parentNode=replacements.get(oldParent)||oldParent,localID=ids.get(parentNode);
            if(!parentNode||!localID||!u.MountedChildrenInfo)throw Error('Native mounted child parent has no scoped fileID');
            const group=new u.MountedChildrenInfo();group.targetInfo=new u.TargetInfo();group.targetInfo.localID=localID;group.nodes=[];
            for(const sid of mount.roots){const child=nodes.get(sid);if(!child)throw Error('Native mounted child absent');child.parent=parentNode;child.setSiblingIndex(parentNode.children.length-1);markMounted(child,root);group.nodes.push(child);}
            instance.mountedChildren.push(group);
        }
        for(const pair of link.nodes){const old=nodes.get(pair.instanceObject),node=replacements.get(old);for(const key of ['_name','_active','_layer','_lpos','_lrot','_lscale'])delta(instance,node,key,value(old[key],replacements),ids);}
        for(const [from,to]of components)for(const key of componentFields(from)){
            const next=value(from[key],replacements);if(added.includes(to))to[key]=next;else delta(instance,to,key,next,ids);
        }
        root.parent=parent;root.setSiblingIndex(index);
        for(const pair of link.nodes)nodes.set(pair.instanceObject,replacements.get(nodes.get(pair.instanceObject)));
        // Known native node references outside this instance must follow replacements.
        for(const node of nodes.values())for(const c of node.components)for(const key of componentFields(c)){
            if(replacements.has(c[key]))c[key]=replacements.get(c[key]);
        }
        previous.parent=null;previous.destroy();
    }
    state.prepared.add(owner);
}
async function serializePrefab(id,sid,saved,plan,load) {
    sortQueue.validatePlan(plan);
    const state=session(id,plan),spec=plan.sourcePrefabs.find(p=>p.sourceId===sid);if(!spec)throw Error('Unexpected native prefab owner');
    // Bind persistent asset dependencies before native instance deltas are
    // recorded, so inherited carriers serialize the same final references.
    for(const info of saved)if(!state.nativeAssets.has(info.sourceId)) {
        const asset=await load(info.uuid,cc.Prefab);
        if(!(asset instanceof cc.Prefab)||asset._uuid!==info.uuid)throw Error('Static Prefab asset identity differs: '+info.sourceId);
        state.nativeAssets.set(info.sourceId,asset);
    }
    const ownerNodes=new Map(spec.nodes.map(nodeId=>[nodeId,state.nodes.get(nodeId)]));
    require('./static-field-integration.js').createAssign(plan,ownerNodes,state.nativeAssets);
    await prepare(state,sid,saved,load);
    const sourceRoot=state.nodes.get(spec.root),renderContextParent=sourceRoot&&sourceRoot.parent;
    const renderCanvas=sourceRoot&&sortQueue.parentCanvas(sourceRoot);
    if(!sourceRoot||!renderContextParent||!renderCanvas||!renderCanvas.enabledInHierarchy||!renderCanvas.node.activeInHierarchy)
        throw Error('Static sort proxy requires the actual active nested Prefab Canvas context: '+spec.root);
    const root=cc.instantiate(sourceRoot);
    ownedUndo.registerRoot(root);
    try {
        root.parent=renderContextParent;root.setSiblingIndex(renderContextParent.children.length-1);root.name=spec.nativeRootName;
        const mapped=mapTree(root,spec,plan);
        let nativeInitialNodes=dynamic.settleRoot(root,mapped,plan);
        if(plan.spineBinding) {
            // Construction only: source-authored geometry is serialized along
            // with its persistent native preserver. Reopen never calls this.
            require('./spine-ui-transform.js').restoreAuthored(plan,mapped,cc,spec.sourceId);
            nativeInitialNodes=dynamic.settleRoot(root,mapped,plan,false);
        }
        // settleRoot temporarily detaches its owned tree; restore the real
        // source Canvas hierarchy before proxy initialization/readback.
        root.parent=renderContextParent;root.setSiblingIndex(renderContextParent.children.length-1);
        if(!root.activeInHierarchy||!renderCanvas.enabledInHierarchy)
            throw Error('Nested native sort proxy root did not reactivate in its Canvas context');
        const proxy=sortQueue.createForPrefab(plan,spec.root,mapped),presenter=proxy.presenter||null;
        const prefab=new cc.Prefab();prefab.name=root.name;prefab.data=root;
        const {p}=api();
        if(root._prefab&&root._prefab.instance)throw Error('Creator root template inheritance requires a dedicated native asset contract');
        p.addPrefabInfo(root,root,prefab);root._prefab.nestedPrefabInstanceRoots=instanceRoots(root);
        let serialized,persistentSortReadback;
        sortQueue.prepareForSerialization(presenter);
        try {
            root.parent=null;
            serialized=serializeNative(root,prefab);
            persistentSortReadback=sortQueue.readPersistent(plan,spec.root,mapped,root);
        } finally {sortQueue.restoreAfterSerialization(presenter);root.parent=renderContextParent;}
        const initializedSortReadback=sortQueue.readInitialized(plan,spec.root,mapped,root);
        const spineUITransformReceipt=plan.spineBinding?require('./spine-ui-transform.js').verifySerializedPrefab(plan,spec,serialized,{saved,templates:saved}):null;
        return {sourceId:sid,path:spec.path,nativeInitialNodes,spineUITransformReceipt,
            staticSortQueue:{create:proxy.createReadback,persistent:persistentSortReadback,initialized:initializedSortReadback},serialized};
    }finally{root.destroy();}
}
async function finish(id,saved,plan,load) {
    const state=session(id,plan);
    try {
        for(const owner of new Set(plan.prefabInstances.map(x=>x.owner)))await prepare(state,owner,saved,load);
        dynamic.settle(state.scene,state.nodes,plan);
        const nativeInitialNodes=dynamic.capture(state.nodes);
        const {u,p}=api(),info=new u.PrefabInfo();info.root=state.scene;info.nestedPrefabInstanceRoots=instanceRoots(state.scene);state.scene._prefab=info;
        dynamic.release(state.scene);
        const asset=new cc.SceneAsset();asset.scene=state.scene;
        return {...state.result,nativeInitialNodes,serialized:serializeNative(state.scene,asset)};
    }finally{release(id);}
}
function read(plan,mapped,templates,saved,owner=null){
    const rows=[];
    for(const link of (plan.prefabInstances||[]).filter(x=>owner===null||x.owner===owner)){
        const root=mapped.get(link.root),info=saved.find(x=>x.sourceId===link.template),spec=plan.sourcePrefabs.find(x=>x.sourceId===link.template),asset=templates.get(link.template);
        const actual=root&&root._prefab;if(!actual||!actual.instance||!actual.asset||actual.asset._uuid!==info.uuid)throw Error('Saved native instance template UUID differs: '+link.root);
        const canonical=mapTree(asset.data,spec,plan);
        for(const pair of link.nodes){const n=mapped.get(pair.instanceObject),t=canonical.get(pair.templateObject);if(!n||!t||!n._prefab||!t._prefab||n._prefab.fileId!==t._prefab.fileId||n._prefab.asset._uuid!==t._prefab.asset._uuid)throw Error('Saved native node fileID/asset correspondence differs: '+pair.instanceObject);}
        const nativeMap={};api().u.generateTargetMap(root,nativeMap,true);
        function destination(group){let value=nativeMap;for(const key of group.targetInfo&&group.targetInfo.localID||[])value=value&&value[key];return value;}
        let mountedRoots=0,mountedNodes=0,mountedComponents=0;
        for(const group of link.mountedChildren||[]){
            const parent=mapped.get(group.parent);
            for(const sid of group.roots){const child=mapped.get(sid);if(!child||child.parent!==parent||!(actual.instance.mountedChildren||[]).some(g=>destination(g)===parent&&g.nodes.includes(child)))throw Error('Saved native mounted-child relationship differs');mountedRoots++;}
            for(const sid of group.nodes){if(!mapped.has(sid)||link.nodes.some(p=>p.instanceObject===sid))throw Error('Saved mounted subtree overlaps template correspondence');mountedNodes++;}
        }
        for(const mounted of link.mountedComponents||[]){
            const node=mapped.get(mounted.node),cls=nativeClass(mounted.nativeType),component=node&&cls&&node.getComponent(cls);
            if(!component||!(actual.instance.mountedComponents||[]).some(g=>destination(g)===node&&g.components.includes(component)))throw Error('Saved native mounted-component relationship differs');mountedComponents++;
        }
        rows.push({root:link.root,templateSourceId:link.template,templatePath:spec.path,templateUuid:info.uuid,templateRootFileId:asset.data._prefab.fileId,nodeCount:link.nodes.length,nativeInstance:true,correspondingSourceVerified:true,nodeCorrespondenceVerified:true,templateUnchanged:true,propertyModificationCount:actual.instance.propertyOverrides.length,mountedChildrenVerified:true,mountedComponentsVerified:true,mountedRootCount:mountedRoots,mountedNodeCount:mountedNodes,mountedComponentCount:mountedComponents});
    }
    return rows;
}
module.exports={sourceTemplateNode,keep,release,serializePrefab,finish,read,recordNativeInstanceReferences};
