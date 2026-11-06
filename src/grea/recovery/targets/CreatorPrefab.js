'use strict';
const sourceChildren=require('./static-richtext.js').sourceChildren;
// Editor-only native Prefab serialization; no source runtime or business execution.
const cc=require('cc');
const jobs=require('./jobs.js');
const dynamic=require('./dynamic-ui.js');
const ownedUndo=require('./owned-import-undo.js');
const sortQueue=require('./CreatorStaticSortQueueIntegration.js');
const near=(a,b)=>a.length===b.length&&a.every((v,i)=>Math.abs(v-b[i])<0.001);
function failMaskReadback(plan,spec,persistent,initialized) {
    const rows=[...persistent.map(row=>({phase:'persistent',...row})),...initialized.map(row=>({phase:'initialized',...row}))];
    const failed=rows.filter(row=>!row.verified);let evidence=null;
    if(plan.nativeProjectRoot) {
        const fs=require('fs'),path=require('path'),crypto=require('crypto');
        const root=fs.realpathSync(plan.nativeProjectRoot);
        const frozen=JSON.parse(fs.readFileSync(path.join(root,'extensions/monkey-import/import-plan.json'),'utf8'));
        if(frozen.projectUuid!==plan.projectUuid||frozen.sourceManifestSha256!==plan.sourceManifestSha256)
            throw Error('STATIC_MASK_DIAGNOSTIC_PROJECT_IDENTITY_MISMATCH');
        const folder=path.join(root,'Analysis/Readback/StaticMasks');fs.mkdirSync(folder,{recursive:true});
        const key=crypto.createHash('sha256').update(spec.root).digest('hex').slice(0,24);
        for(let sequence=0;sequence<10000;sequence++) {
            const target=path.join(folder,key+'-'+sequence+'.json');
            try {
                fs.writeFileSync(target,JSON.stringify({scope:'native-static-mask-diagnostic-only',status:'failed',
                    projectUuid:plan.projectUuid,sourceManifestSha256:plan.sourceManifestSha256,
                    sourcePrefabId:spec.sourceId,rootScope:spec.root,rows},null,2)+'\n',{flag:'wx'});
                evidence=path.relative(root,target);break;
            }catch(error){if(error.code!=='EEXIST')throw error;}
        }
        if(!evidence)throw Error('STATIC_MASK_DIAGNOSTIC_SEQUENCE_EXHAUSTED');
    }
    throw Error('STATIC_MASK_PERSISTENT_OR_INITIALIZED_READBACK_FAILED:'+JSON.stringify({
        sourcePrefabId:spec.sourceId,failed:failed.slice(0,4).map(row=>({phase:row.phase,sourceId:row.sourceId,
            failedChecks:row.failedChecks||null})),evidence}));
}
function uiState(node,src,root=null) {
    if(!src.sourceGeometryProfile)return {};
    const group=node.getComponent(cc.UIOpacity);const opacity=group&&group.enabled?group.opacity:255;
    const sourceLayer=node.layer===src.sourceLayer || (root&&sortQueue.sourceSuppressionEvidence(root,node,src.sourceLayer));
    if(!sourceLayer||Math.abs(opacity-src.opacity)>.001)throw Error('Source UI layer/opacity differs: '+src.sourceId);
    const state={sourceLayer:src.sourceLayer,opacity};
    if(src.verifyUiColor||node.getComponent(cc.RichText)||node.getComponent(cc.sp.Skeleton)) {
        const renderer=node.getComponent(cc.Sprite)||node.getComponent(cc.Label)||node.getComponent(cc.RichText)||node.getComponent(cc.sp.Skeleton);
        if(!renderer)throw Error('Source UI renderer missing: '+src.sourceId);
        const nativeColor=renderer instanceof cc.RichText?renderer.fontColor:renderer.color;
        const color=[nativeColor.r,nativeColor.g,nativeColor.b,nativeColor.a];
        if(!near(color,src.color))throw Error('Source renderer color differs: '+src.sourceId);
        state.color=color;
    }
    return state;
}
async function serialize(plan,nodes) {
    sortQueue.validatePlan(plan);
    const result=[];
    for(const spec of plan.sourcePrefabs||[]) {
        jobs.progress('source-prefabs',result.length,(plan.sourcePrefabs||[]).length);
        if(result.length%16===0)await new Promise(resolve=>setTimeout(resolve,0));
        if(plan.nativeDeadlineMs&&Date.now()>=plan.nativeDeadlineMs)throw Error('NATIVE_BUDGET_EXHAUSTED');
        const sourceRoot=nodes.get(spec.root),renderContextParent=sourceRoot&&sourceRoot.parent;
        const renderCanvas=sourceRoot&&sortQueue.parentCanvas(sourceRoot);
        if(!sourceRoot||!renderContextParent||!renderCanvas||!renderCanvas.enabledInHierarchy||!renderCanvas.node.activeInHierarchy)
            throw Error('Static sort proxy requires the actual active source Canvas context: '+spec.root);
        const root=cc.instantiate(sourceRoot);
        ownedUndo.registerRoot(root);
        try {
            root.parent=renderContextParent;root.setSiblingIndex(renderContextParent.children.length-1);
            if(spec.rootNamePolicy==='creator-asset-basename-v1')root.name=spec.nativeRootName;
            const mapped=new Map();const sources=new Map(plan.nodes.map(n=>[n.sourceId,n]));
            function walk(sid,n){mapped.set(sid,n);sources.get(sid).children.forEach((child,i)=>walk(child,sourceChildren(n)[i]));}walk(spec.root,root);
            let nativeInitialNodes=dynamic.settleRoot(root,mapped,plan);
        if(plan.spineBinding) {
            // Construction only: source-authored geometry is serialized along
            // with its persistent native preserver. Reopen never calls this.
            require('./spine-ui-transform.js').restoreAuthored(plan,mapped,cc,spec.sourceId);
            nativeInitialNodes=dynamic.settleRoot(root,mapped,plan,false);
        }
        // settleRoot owns and tears down its temporary Scene; remount after the
        // final layout pass before native proxy lifecycle/render readback.
        root.parent=renderContextParent;root.setSiblingIndex(renderContextParent.children.length-1);
        if(!root.activeInHierarchy||!renderCanvas.enabledInHierarchy)throw Error('Native sort proxy source root did not reactivate in its Canvas context');
            const prefab=new cc.Prefab();prefab.name=root.name;prefab.data=root;
            const proxy=sortQueue.createForPrefab(plan,spec.root,mapped),presenter=proxy.presenter;
            let serialized,persistentSortReadback;
            sortQueue.prepareForSerialization(presenter);
            try {
                root.parent=null;
                const raw=EditorExtends.serialize(prefab);serialized=typeof raw==='string'?raw:JSON.stringify(raw);
                persistentSortReadback=sortQueue.readPersistent(plan,spec.root,mapped,root);
            } finally {sortQueue.restoreAfterSerialization(presenter);root.parent=renderContextParent;}
            const initializedSortReadback=sortQueue.readInitialized(plan,spec.root,mapped,root);
            const spineUITransformReceipt=plan.spineBinding?require('./spine-ui-transform.js').verifySerializedPrefab(plan,spec,serialized):null;
            result.push({sourceId:spec.sourceId,path:spec.path,nativeInitialNodes,spineUITransformReceipt,
                staticSortQueue:{create:proxy.createReadback,persistent:persistentSortReadback,initialized:initializedSortReadback},serialized});
        } finally {root.destroy();}
    }
    return result;
}
function createReadContext(plan) {
    const scene=new cc.Scene('OwnedStaticPrefabReadback');
    ownedUndo.registerRoot(scene);
    const node=new cc.Node('OwnedStaticPrefabCanvas');ownedUndo.registerRoot(node);node.layer=cc.Layers.Enum.UI_2D;node.parent=scene;
    const ui=node.addComponent(cc.UITransform);ui.setContentSize(...plan.designSize);ui.setAnchorPoint(0,0);
    const canvas=node.addComponent(cc.Canvas);
    const cameraNode=new cc.Node('OwnedStaticPrefabCamera');ownedUndo.registerRoot(cameraNode);cameraNode.parent=scene;cameraNode.setPosition(0,0,1000);
    const camera=cameraNode.addComponent(cc.Camera);camera.projection=cc.Camera.ProjectionType.ORTHO;
    camera.orthoHeight=plan.designSize[1]/2;camera.near=1;camera.far=2000;camera.visibility=cc.Layers.Enum.UI_2D;
    canvas.cameraComponent=camera;
    const sourceParent=new cc.Node('OwnedStaticPrefabDesign');ownedUndo.registerRoot(sourceParent);sourceParent.layer=cc.Layers.Enum.UI_2D;sourceParent.parent=node;
    const designUI=sourceParent.addComponent(cc.UITransform);designUI.setContentSize(...plan.designSize);designUI.setAnchorPoint(0,0);
    scene._load();scene._activate(true);
    return {scene,canvas,sourceParent};
}
function read(prefab,spec,plan,info,templates,staticAssets,animationContext) {
    sortQueue.validatePlan(plan);
    const root=cc.instantiate(prefab),context=createReadContext(plan);
    ownedUndo.registerRoot(root);
    try {
        if(root.parent)throw Error('Saved prefab has external parent');
        const {scene,canvas}=context;
        if(!scene.activeInHierarchy||!canvas.enabledInHierarchy)throw Error('Owned native Prefab Canvas context is not active');
        // Execute native lifecycle in an owned scene, without touching the user's open scene.
        root.parent=context.sourceParent;
        const sources=new Map(plan.nodes.map(n=>[n.sourceId,n]));const mapped=new Map(),geometryMismatches=[];
        if(spec.rootNamePolicy&&(spec.rootNamePolicy!=='creator-asset-basename-v1'||spec.sourceRootName!==sources.get(spec.root).name||spec.nativeRootName!==spec.path.split('/').pop().slice(0,-7)))throw Error('Prefab name policy differs');
        function match(sid,node) {
            const original=sources.get(sid),src=dynamic.expected(original,plan,info.nativeInitialNodes),ui=node.getComponent(cc.UITransform);
            const expectedName=sid===spec.root&&spec.rootNamePolicy==='creator-asset-basename-v1'?spec.nativeRootName:src&&src.name;
            if(!src||expectedName!==node.name||src.children.length!==sourceChildren(node).length||!ui)throw Error('Prefab hierarchy differs: '+sid);
            const actual={position:[node.position.x,node.position.y,node.position.z],scale:[node.scale.x,node.scale.y,node.scale.z],
                rotation:[node.rotation.x,node.rotation.y,node.rotation.z,node.rotation.w],size:[ui.width,ui.height],anchor:[ui.anchorX,ui.anchorY],active:node.active,...uiState(node,src,root)};
            const fields=Object.keys(actual).filter(key=>['active','sourceLayer','opacity'].includes(key)?actual[key]!==src[key]:!near(actual[key],src[key]));
            if(fields.length)geometryMismatches.push({sourceId:sid,fields,expected:Object.fromEntries(fields.map(key=>[key,src[key]])),actual:Object.fromEntries(fields.map(key=>[key,actual[key]]))});
            mapped.set(sid,node);src.children.forEach((child,i)=>match(child,sourceChildren(node)[i]));
        }
        if(plan.spineBinding) {
            const lifecycleNodes=new Map();
            function index(sid,node){
                const src=sources.get(sid),children=node&&sourceChildren(node);
                if(!src||!node||children.length!==src.children.length)throw Error('Saved lifecycle hierarchy differs: '+sid);
                lifecycleNodes.set(sid,node);src.children.forEach((child,i)=>index(child,children[i]));
            }
            index(spec.root,root);
            dynamic.settleRoot(root,lifecycleNodes,plan,false);
            const geometry=require('./spine-ui-transform.js').readAuthored(plan,lifecycleNodes,cc,spec.sourceId);
            if(geometry.status!=='verified')throw Error('SPINE_UI_TRANSFORM_SAVED_PREFAB_MISMATCH: '+JSON.stringify(geometry));
        }
        root.parent=context.sourceParent;root.setSiblingIndex(context.sourceParent.children.length-1);
        if(!root.activeInHierarchy||!canvas.enabledInHierarchy)throw Error('Initialized Prefab probe did not reactivate in its Canvas context');
        match(spec.root,root);
        const persistent=new Map();
        function savedMap(sid,node){
            if(!node)throw Error('Saved behavior owner absent: '+sid);
            persistent.set(sid,node);sources.get(sid).children.forEach((child,i)=>savedMap(child,sourceChildren(node)[i]));
        }
        savedMap(spec.root,prefab.data);
        // The loaded Editor instance may carry the presenter's temporary hidden
        // layer. Independently prove the serialized Prefab retains each source
        // layer and opacity before accepting that initialized presentation.
        for(const id of spec.nodes){const src=dynamic.expected(sources.get(id),plan,info.nativeInitialNodes);uiState(persistent.get(id),src);}
        if(mapped.size!==spec.nodeCount||spec.nodes.some(id=>!mapped.has(id)))throw Error('Prefab node boundary differs');
        const assets=new Map(plan.assets.map(a=>[a.sourceId,a]));const components=[];const numericCodeBindings=[],behaviorBindings=[];
        for(const c of plan.components.filter(c=>c.convertible&&mapped.has(c.node))) {
            const node=mapped.get(c.node),comp=c.behaviorBinding?
                require('./behavior-bindings.js').read(node,c.behaviorBinding,c.enabled):node.getComponent(c.spineBinding?cc.sp.Skeleton:cc[c.type==='cc.LabelOutline'?'Label':c.type.slice(3)]);
            if(!comp)throw Error('Prefab component missing: '+c.sourceId);
            if(c.type==='cc.ProgressBar')require('./progress.js').read(comp,c,mapped);
            if(c.behaviorBinding)behaviorBindings.push(require('./behavior-bindings.js').readPersistent(persistent.get(c.node),c.behaviorBinding,c.enabled,c.sourceId,info.uuid));
            if(c.codeClassName)numericCodeBindings.push(require('./numeric-code.js').read(comp,c));
            if(c.type==='cc.Sprite'&&c.spriteFrame&&(!comp.spriteFrame||comp.spriteFrame._uuid!==assets.get(c.spriteFrame).spriteFrameUuid))throw Error('Prefab sprite reference differs');
            if(c.nativeSpriteOutlineMaterialSourceId&&(!plan.spriteOutlineBinding||!require('./sprite-outline-material-bindings.js').readBound(plan.spriteOutlineBinding,comp.customMaterial,c.sourceId,comp,id=>staticAssets.get(id))))throw Error('Prefab outline material differs: '+c.sourceId);
            if(c.nativeMaterialSourceId&&(!plan.materialBinding||!comp.customMaterial||comp.customMaterial._uuid!==plan.materialBinding.creator.materialUuid||
               !require('./material-bindings.js').readBound(plan.materialBinding,comp.customMaterial,comp)))throw Error('Prefab custom material differs: '+c.sourceId);
            if(c.nativeStaticTimeMaterialSourceId) {
                const row=plan.staticTimeMaterials&&plan.staticTimeMaterials.materials.find(x=>x.sourceMaterialId===c.nativeStaticTimeMaterialSourceId);
                if(!row||!require('./static-time-materials.js').readBound(plan.staticTimeMaterials,row,staticAssets.get(row.sourceMaterialId),c.sourceId,comp,id=>staticAssets.get(id)))
                    throw Error('Prefab static-time material differs: '+c.sourceId);
            }
            if(c.type==='cc.RichText'&&(comp.string!==(c.staticRichText?c.staticRichText.creatorMarkup:c.text)||comp.fontFamily!==c.fontFamily))throw Error('Prefab RichText font/text differs');
            if(c.type==='cc.Label') {
                const fontMatches=c.nativeSystemFont?
                    comp.useSystemFont&&comp.font===null&&comp.fontFamily===c.fontFamily:
                    comp.font&&assets.get(c.font)&&comp.font._uuid===assets.get(c.font).uuid;
                if(!fontMatches||comp.string!==c.text)throw Error('Prefab font/text reference differs');
            }
            if(c.type==='cc.Label'&&comp.overflow!==(c.nativeOverflow??c.overflow))throw Error('Prefab Label overflow policy differs');
            if(c.type==='cc.LabelOutline'&&!(comp.font instanceof cc.BitmapFont)&&
               (comp.enableOutline!==!!c.enabled||Math.abs(comp.outlineWidth-c.width)>.0001||!near([comp.outlineColor.r,comp.outlineColor.g,comp.outlineColor.b,comp.outlineColor.a],c.outlineColor)))
                throw Error('Prefab Label outline fields differ: '+c.sourceId);
            if(c.type==='cc.Sprite'&&comp.sizeMode!==(c.nativeSizeMode??c.sizeMode))throw Error('Prefab Sprite sizing policy differs');
            if(c.type==='cc.ScrollView'&&comp.content!==mapped.get(c.content))throw Error('Prefab scroll reference escapes graph');
            if(c.type==='cc.Button'){
                const target=c.staticButtonBinding&&c.target?mapped.get(c.target):node;
                if(comp.target!==target)throw Error('Prefab button reference differs');
                if(c.staticButtonBinding){
                    if(comp.enabled||comp.transition!==c.transition||comp.interactable!==c.interactable||Math.abs(comp.zoomScale-c.zoomScale)>.0001||Math.abs(comp.duration-c.duration)>.0001)throw Error('Static button state differs');
                    for(const name of ['normalColor','hoverColor','pressedColor','disabledColor']){
                        const v=comp[name];if(!near([v.r,v.g,v.b,v.a],c.staticButtonBinding[name]))throw Error('Static button color differs: '+name);
                    }
                }
            }
            if(c.type==='cc.Widget'&&comp.target!==(c.target?mapped.get(c.target):null))throw Error('Prefab widget reference differs');
            components.push(c.sourceId);
        }
        const spineSpecs=plan.components.filter(c=>c.convertible&&c.spineBinding&&mapped.has(c.node));
        const spineModule=require('./spine-bindings.js'),spineById=new Map(spineSpecs.map(c=>[c.sourceId,c]));
        const spineContext=(id,scope)=>({sourceActivity:spineModule.sourceNodeActivity(plan,spineById.get(id).node),readbackScope:scope});
        const spineBindings=spineModule.readCreatorSpineBindings(spineSpecs.map(c=>c.spineBinding),id=> {
            const c=spineById.get(id);return c?mapped.get(c.node).getComponents(cc.sp.Skeleton):[];
        },id=>spineContext(id,'instantiated_mapped'));
        const serializedSpineBindings=spineModule.readCreatorSpineBindings(spineSpecs.map(c=>c.spineBinding),id=> {
            const c=spineById.get(id);return c?persistent.get(c.node).getComponents(cc.sp.Skeleton):[];
        },id=>spineContext(id,'serialized_template'));
        const staticFieldBindings=plan.components.some(c=>c.staticFieldBinding&&persistent.has(c.node))?require('./static-field-integration.js').read(plan,persistent,staticAssets,info.uuid):[];
        let toggleFields=null;
        if(plan.toggleBinding){
            const subset={bindings:plan.toggleBinding.bindings.filter(x=>persistent.has(x.nodeSourceId))};
            toggleFields=require('./static-toggle.js').Read(subset,id=>persistent.get(id),require('./static-field-integration.js').resolver(plan,persistent,staticAssets));
            if(toggleFields.fields.some(x=>!x.verified))throw Error('STATIC_TOGGLE_SAVED_READBACK_FAILED');
        }
        const staticProgressFields=plan.components.filter(c=>c.staticProgressBinding&&!c.convertible&&persistent.has(c.node)).map(c=>{
            const bar=plan.components.find(x=>x.sourceId===c.staticProgressBinding.barSpriteSourceId);
            return require('./static-progress.js').read(persistent.get(c.node).getComponent(cc.ProgressBar),c.staticProgressBinding,persistent.get(bar.node).getComponent(cc.Sprite));
        });
        const staticControlFields=plan.staticControls?require('./static-controls.js').read(plan.staticControls.bindings.filter(x=>persistent.has(x.node)),persistent,require('./static-field-integration.js').resolver(plan,persistent,staticAssets)):[];
        const animationPlan={...plan,components:plan.components.filter(c=>persistent.has(c.node))};
        const staticAnimationFields=animationContext?require('./static-animation-integration.js').readSaved(animationPlan,persistent,animationContext.animations,animationContext.evidence,plan.staticAnimationComponentOrigins):[];
        const staticMaskReadback=plan.staticMasks&&plan.staticMasks.masks?require('./static-masks.js'):null;
        const maskSpecs=staticMaskReadback?plan.staticMasks.masks.filter(x=>persistent.has(x.node)):[];
        const resolveMaskSprite=uuid=>staticMaskReadback.resolveSprite(plan,staticAssets,uuid);
        const staticMaskFields=staticMaskReadback?staticMaskReadback.readStaticMasks(maskSpecs,persistent,resolveMaskSprite):[];
        const staticMaskInitializedFields=staticMaskReadback?staticMaskReadback.readStaticMasks(maskSpecs,mapped,resolveMaskSprite,{initialized:true}):[];
        if(staticMaskFields.some(row=>!row.verified)||staticMaskInitializedFields.some(row=>!row.verified))
            failMaskReadback(plan,spec,staticMaskFields,staticMaskInitializedFields);
        const staticLayoutFields=plan.layoutCompletion?require('./static-layout-completion.js').read(plan.layoutCompletion,persistent).staticLayoutFields:[];
        const prefabInstances=require('./prefab-instances.js').read(plan,mapped,templates,plan.savedPrefabs||[],spec.sourceId);
        const staticSortPersistent=sortQueue.readPersistent(plan,spec.root,persistent,prefab.data);
        const staticSortInitialized=sortQueue.readInitialized(plan,spec.root,mapped,root);
        const bitmapMissingGlyphFields=plan.bitmapMissingGlyphs?require('./bitmap-missing-glyphs.js').read(plan.bitmapMissingGlyphs,persistent,mapped,staticAssets,cc):[];
        const staticLayoutProbe=plan.layoutCompletion?require('./static-layout-completion.js').probe(plan,mapped):null;
        return {...info,bitmapMissingGlyphFields,staticLayoutProbe,staticMaskFields,staticMaskInitializedFields,staticLayoutFields,staticAnimationFields,staticControlFields,staticProgressFields,toggleFields,staticFieldBindings,spineBindings,serializedSpineBindings,prefabInstances,
            staticSortQueue:{persistent:staticSortPersistent,initialized:staticSortInitialized},nodeCount:mapped.size,savedReloaded:true,geometryVerified:geometryMismatches.length===0,geometryMismatches,referencesVerified:true,components,
            numericCodeBindings,behaviorBindings,rootNamePolicy:spec.rootNamePolicy||'source-name-v1',sourceRootName:sources.get(spec.root).name,nativeRootName:root.name};
    } finally {root.destroy();context.scene._activate(false);context.scene.destroy();}
}
module.exports={serialize,read,uiState,failMaskReadback};
