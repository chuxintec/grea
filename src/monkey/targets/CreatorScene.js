'use strict';
// Editor scene script. It creates an isolated native tree, never touches the open scene.
const cc = require('cc');
const sourceChildren=require('./static-richtext.js').sourceChildren;
const motion=require('./animation.js');
const prefabs=require('./prefab.js');
const relations=require('./prefab-instances.js');
const staticSortQueue=require('./CreatorStaticSortQueueIntegration.js');
const staticSortSerialization=require('./static-sort-serialization.js');
const ownedUndo=require('./owned-import-undo.js');
const ownedBuildTeardown=require('./owned-build-scene-teardown.js');
let saveCallProbe=null;
let undoSnapshotProbe=null;
const dynamic=require('./dynamic-ui.js');
const batch=require('./batch.js');
const jobs=require('./jobs.js');
const numeric=require('./numeric-code.js');
const behaviors=require('./behavior-bindings.js');
const resources=require('./resources.js');
const color = a => new cc.Color(...a);
function tiledReadback(plan,nodes) {
    if(!plan.rendererBudget)return null;
    const rows=[];
    for(const c of plan.components) {
        if(!c.convertible||c.type!=='cc.Sprite'||c.mode!==2||!c.spriteFrame)continue;
        const sprite=nodes.get(c.node).getComponent(cc.Sprite);
        if(!sprite||!sprite.spriteFrame)throw Error('Tiled native SpriteFrame missing: '+c.sourceId);
        if(!sprite.renderData)sprite._flushAssembler();
        sprite.renderData.vertDirty=true;sprite._assembler.updateRenderData(sprite);
        const data=sprite.renderData;
        if((data.vertexCount>0&&!data.chunk)||data.vertexCount>plan.rendererBudget.vertexCapacity)throw Error('Tiled native mesh allocation failed: '+c.sourceId);
        rows.push({sourceId:c.sourceId,vertexCount:data.vertexCount,indexCount:data.indexCount,allocated:true,
            spriteFrameUuid:sprite.spriteFrame._uuid});
    }
    return {profile:plan.rendererBudget.profile,macroKiB:cc.macro.BATCHER2D_MEM_INCREMENT,sprites:rows};
}
const checkTime=plan=>{if(plan.nativeDeadlineMs&&Date.now()>=plan.nativeDeadlineMs)throw Error('NATIVE_BUDGET_EXHAUSTED');};
// Reload only the requested saved root. A global reload also replaces every
// dependency, breaking shared native Asset identity across loaded Prefabs.
const loadAsset = (uuid, type, forceReload=false) => new Promise((resolve,reject) => cc.assetManager.loadAny(forceReload?{uuid,reloadAsset:true}:{uuid}, {reloadAsset:type===cc.SpriteFrame}, (e,a) => {
    if (e) reject(e); else if (!(a instanceof type)) reject(Error('Unexpected native asset type: '+uuid)); else resolve(a);
}));
function describe(root, plan) {
    const nodes=[];
    const visit=n=>{nodes.push(n);for(const child of sourceChildren(n))visit(child);};visit(root);
    return {nodeCount:plan.nodes.length, treeNodeCount:nodes.length};
}
module.exports = {
    load() { staticSortSerialization.install(cc, EditorExtends, globalThis, require); },
    unload() { ownedUndo.finish(); if(saveCallProbe){saveCallProbe.uninstall();saveCallProbe=null;} if(undoSnapshotProbe){undoSnapshotProbe.uninstall();undoSnapshotProbe=null;} staticSortSerialization.uninstall(); },
    methods: {
        beginOwnedImportUndo() { return ownedUndo.start(globalThis.cce,globalThis,require); },
        finishOwnedImportUndo() { return ownedUndo.finish(); },
        inspectOrdinarySaveApi() {
            staticSortSerialization.install(cc,EditorExtends,globalThis,require);
            if(!saveCallProbe)saveCallProbe=staticSortSerialization.installRuntimeCallProbe(cc,EditorExtends,globalThis,require);
            if(!undoSnapshotProbe)undoSnapshotProbe=require('./editor-undo-diagnostics.js').install({realm:globalThis,requireFn:require});
            return {runtime:staticSortSerialization.probeRuntimeApi(cc,EditorExtends,globalThis,require),calls:saveCallProbe.summary(),undo:undoSnapshotProbe.summary()};
        },
        stopOrdinarySaveProbe() {
            const result=saveCallProbe?saveCallProbe.summary():{patched:[],callCounts:{},callRows:[]};
            if(saveCallProbe){saveCallProbe.uninstall();saveCallProbe=null;}
            if(undoSnapshotProbe){result.undo=undoSnapshotProbe.summary();undoSnapshotProbe.uninstall();undoSnapshotProbe=null;}
            return result;
        },
        async prepareRetainedBuiltin(entry) {
            const helper=require('./static-retained-assets.js'),material=helper.createBuiltin(entry,await loadAsset('60f7195c-ec2a-45eb-ba94-8955f60e81d0',cc.EffectAsset));
            try{return helper.serializeBuiltin(material);}finally{material.destroy();}
        },
        async prepareStaticAnimationAssets(plan) {
            const result=[];
            for(const spec of plan.animations||[])if(spec.convertible) {
                const clip=motion.create({...spec,assetOnly:true},new Map());
                try {const raw=EditorExtends.serialize(clip);result.push({id:spec.id,path:spec.path,serialized:typeof raw==='string'?raw:JSON.stringify(raw)});}
                finally{clip.destroy();}
            }
            return result;
        },
        async createStaticPreview(uuid,plan){return require("./static-preview.js").create(uuid,plan,loadAsset);},
        async readStaticPreview(uuid,plan){return require("./static-preview.js").read(uuid,plan,loadAsset);},
        async prepareStaticTimeMaterial(spec, sourceId) {
            const row=spec.materials.find(x=>x.sourceMaterialId===sourceId);
            if(!row)throw Error('STATIC_TIME_SOURCE_MATERIAL_MISSING');
            const helper=require('./static-time-materials.js');
            const material=helper.create(spec,row,await loadAsset(row.creator.effectUuid,cc.EffectAsset));
            try{return helper.serialize(spec,row,material);}finally{material.destroy();}
        },
        async readStaticTimeMaterial(spec, sourceId) {
            const row=spec.materials.find(x=>x.sourceMaterialId===sourceId);
            if(!row)throw Error('STATIC_TIME_SOURCE_MATERIAL_MISSING');
            return require('./static-time-materials.js').readback(spec,row,
                await loadAsset(row.creator.materialUuid,cc.Material),await loadAsset(row.creator.effectUuid,cc.EffectAsset));
        },
        async prepareOutlineMaterial(spec) {
            const helper=require('./sprite-outline-material-bindings.js');
            const effect=await loadAsset(spec.creator.effectUuid,cc.EffectAsset),material=helper.create(spec,effect);
            try{return helper.serialize(spec,material);}finally{material.destroy();}
        },
        async readOutlineMaterial(spec) {
            return require('./sprite-outline-material-bindings.js').readback(spec,
                await loadAsset(spec.creator.materialUuid,cc.Material),await loadAsset(spec.creator.effectUuid,cc.EffectAsset));
        },
        async prepareMaterial(spec) {
            const helper=require('./material-bindings.js');
            const effect=await loadAsset(spec.creator.effectUuid,cc.EffectAsset);
            const material=helper.create(spec,effect);
            try{return helper.serialize(spec,material);}finally{material.destroy();}
        },
        async readMaterial(spec) {
            return require('./material-bindings.js').readback(spec,
                await loadAsset(spec.creator.materialUuid,cc.Material),await loadAsset(spec.creator.effectUuid,cc.EffectAsset));
        },
        beginJob(method,args){return jobs.begin(method,args,module.exports.methods);},
        jobStatus(id){return jobs.status(id);},
        takeJob(id){return jobs.take(id);},
        releaseAssembly(id){relations.release(id);},
        async serializePrefab(id,sid,saved,plan){return relations.serializePrefab(id,sid,saved,plan,loadAsset);},
        async finishAssembly(id,saved,plan){return relations.finish(id,saved,plan,loadAsset);},
        async assemble(plan) {
            if (!globalThis.EditorExtends || typeof EditorExtends.serialize !== 'function') throw Error('Native serializer unavailable');
            staticSortQueue.validatePlan(plan);
            if(plan.rendererBudget) {
                const kib=plan.rendererBudget.macroConfig.BATCHER2D_MEM_INCREMENT;
                if(!Number.isInteger(kib)||kib<144||kib>2303)throw Error('Invalid native tiled renderer budget');
                cc.macro.BATCHER2D_MEM_INCREMENT=kib;
            }
            const scene = ownedBuildTeardown.create(cc,'Candidate');
            ownedUndo.registerRoot(scene);
            let retained=false;
            let assembleError=null;
            try {
                const canvasNode = new cc.Node('Canvas');ownedUndo.registerRoot(canvasNode);canvasNode.layer=cc.Layers.Enum.UI_2D;canvasNode.parent=scene;
                canvasNode.addComponent(cc.UITransform).setContentSize(...plan.designSize);
                const canvas=canvasNode.addComponent(cc.Canvas);
                const cameraNode=new cc.Node('Camera');ownedUndo.registerRoot(cameraNode);cameraNode.parent=scene;cameraNode.setPosition(0,0,1000);
                const camera=cameraNode.addComponent(cc.Camera);camera.projection=cc.Camera.ProjectionType.ORTHO;
                camera.orthoHeight=plan.designSize[1]/2;camera.near=1;camera.far=2000;camera.visibility=cc.Layers.Enum.UI_2D;canvas.cameraComponent=camera;
                const design = new cc.Node('DesignRoot');ownedUndo.registerRoot(design);design.parent=canvasNode;design.layer=cc.Layers.Enum.UI_2D;
                design.addComponent(cc.UITransform).setContentSize(...plan.designSize);design.getComponent(cc.UITransform).setAnchorPoint(0,0);
                design.setPosition(-plan.designSize[0]/2,-plan.designSize[1]/2,0);
                const nodes=new Map();const sourceNodes=new Map(plan.nodes.map(n=>[n.sourceId,n]));const assets=new Map(plan.assets.map(a=>[a.sourceId,a]));
                const native=new Map();
                let loaded=0;
                await batch.map(plan.assets,16,async a=>{checkTime(plan);native.set(a.sourceId,await loadAsset(a.kind==='sprite'?a.spriteFrameUuid:a.uuid,a.kind==='sprite'?cc.SpriteFrame:a.kind==='json'?cc.JsonAsset:a.kind==='audio'?cc.AudioClip:cc.Font));jobs.progress('textures',++loaded,plan.assets.length);});
                if(plan.staticRetainedAssets)for(const [sid,asset]of await require('./static-retained-assets.js').load(plan.staticRetainedAssets))native.set(sid,asset);
                const animationContext=plan.staticAnimationEvidence?await require('./static-animation-context.js').load(plan,loadAsset,native):null;
                const spineAssets=new Map();
                for(const asset of (plan.spineBinding&&plan.spineBinding.assets)||[])
                    spineAssets.set(asset.sourceId,await loadAsset(asset.creator.nativeUuid,cc.sp.SkeletonData));
                for(const [id,asset]of spineAssets)native.set(id,asset);
                let nodeProgress=0;
                for(const n of plan.nodes) {
                    if(nodeProgress%256===0){jobs.progress('hierarchy',nodeProgress,plan.nodes.length);await new Promise(resolve=>setTimeout(resolve,0));}nodeProgress++;
                    checkTime(plan);
                    const node=new cc.Node(n.name);ownedUndo.registerRoot(node);node.layer=n.sourceLayer??cc.Layers.Enum.UI_2D;nodes.set(n.sourceId,node);
                    node.setPosition(...n.position);node.setRotation(new cc.Quat(...n.rotation));node.setScale(...n.scale);
                    const ui=node.addComponent(cc.UITransform);ui.setContentSize(...n.size);ui.setAnchorPoint(...n.anchor);
                    if(n.sourceUITransformEnabled===false)ui.enabled=false;
                    if(n.opacity!==255)node.addComponent(cc.UIOpacity).opacity=n.opacity;
                    node.active=n.active;
                }
                for(const n of plan.nodes) {
                    const node=nodes.get(n.sourceId);node.parent=n.parent?nodes.get(n.parent):design;
                }
                for(const n of plan.nodes)for(let i=0;i<n.children.length;i++)nodes.get(n.children[i]).setSiblingIndex(i);
                const nativeRefs=[];const codeEntries=[];
                let componentProgress=0;
                for(const c of plan.components) {
                    if(componentProgress%256===0){jobs.progress('components',componentProgress,plan.components.length);await new Promise(resolve=>setTimeout(resolve,0));}componentProgress++;
                    checkTime(plan);
                    if(!c.convertible || c.type==='cc.LabelOutline'||c.type==='cc.Toggle'||c.type==='cc.ToggleContainer')continue;
                    const node=nodes.get(c.node);const source=sourceNodes.get(c.node);let comp;
                    if(c.spineBinding) {
                        comp=node.addComponent(cc.sp.Skeleton);
                        require('./spine-bindings.js').applyCreatorSpineBinding(c.spineBinding,
                            id=>id===c.sourceId?comp:null,id=>spineAssets.get(id));
                        comp.color=color(source.color);
                    } else if(c.behaviorBinding) {
                        comp=behaviors.bind(node,c.behaviorBinding,c.enabled);
                    } else if(c.type==='cc.Sprite') {
                        comp=node.addComponent(cc.Sprite);comp.type=c.mode;comp.sizeMode=c.nativeSizeMode??c.sizeMode;comp.trim=c.trim;
                        comp.spriteFrame=c.spriteFrame?native.get(c.spriteFrame):null;comp.color=color(source.color);
                        comp.enabled=c.enabled&&!c.needsSpriteBinding;
                    } else if(c.type==='cc.RichText') {
                        comp=node.addComponent(cc.RichText);comp.font=null;comp.fontFamily=c.fontFamily;comp.fontColor=color(source.color);
                        require('./static-richtext.js').apply(comp,c.staticRichText);
                    } else if(c.type==='cc.Label') {
                        comp=node.addComponent(c.codeClassName?numeric.type(c):cc.Label);if(c.codeClassName)codeEntries.push({component:comp,spec:c});comp.overflow=c.nativeOverflow??c.overflow;
                        if(c.nativeSystemFont){comp.font=null;comp.useSystemFont=true;comp.fontFamily=c.fontFamily;}
                        else {comp.useSystemFont=false;comp.font=native.get(c.font);}
                        comp.string=c.text;comp.fontSize=c.fontSize;comp.lineHeight=c.lineHeight;comp.spacingX=c.spacing;
                        comp.horizontalAlign=c.horizontalAlign;comp.verticalAlign=c.verticalAlign;
                        comp.enableWrapText=c.wrap;comp.isBold=!!c.bold;comp.isItalic=!!c.italic;comp.isUnderline=!!c.underline;comp.color=color(source.color);
                    } else if(c.type==='cc.Button') {
                        comp=node.addComponent(cc.Button);comp.enabled=false;comp.target=c.staticButtonBinding?(c.target?nodes.get(c.target):node):node;comp.transition=c.transition;comp.duration=c.duration;
                        comp.zoomScale=c.zoomScale;comp.interactable=c.interactable;comp.clickEvents=[];
                        if(c.staticButtonBinding)for(const name of ['normalColor','hoverColor','pressedColor','disabledColor'])comp[name]=color(c.staticButtonBinding[name]);
                    } else if(c.type==='cc.BlockInputEvents') {comp=node.addComponent(cc.BlockInputEvents);
                    } else if(c.type==='cc.Mask') {comp=node.addComponent(cc.Mask);comp.type=cc.Mask.Type.GRAPHICS_RECT;
                    } else if(c.type==='cc.ProgressBar') {
                        comp=node.addComponent(cc.ProgressBar);
                    } else if(c.type==='cc.ScrollView') {
                        comp=node.addComponent(cc.ScrollView);comp.enabled=c.enabled;comp.horizontal=c.horizontal;comp.vertical=c.vertical;comp.content=nodes.get(c.content);
                    } else if(c.type==='cc.Widget') {
                        comp=node.addComponent(cc.Widget);comp.target=c.target?nodes.get(c.target):null;comp.alignMode=c.alignMode;
                        comp.isAlignTop=!!(c.flags&1);comp.isAlignBottom=!!(c.flags&4);comp.isAlignLeft=!!(c.flags&8);comp.isAlignRight=!!(c.flags&32);
                        [comp.left,comp.bottom,comp.right,comp.top]=c.margins;
                        [comp.isAbsoluteLeft,comp.isAbsoluteBottom,comp.isAbsoluteRight,comp.isAbsoluteTop]=c.absolute;
                        [comp.horizontalCenter,comp.verticalCenter]=c.center||[0,0];
                        [comp.isAbsoluteHorizontalCenter,comp.isAbsoluteVerticalCenter]=c.centerAbsolute||[true,true];
                    } else if(c.type==='cc.Layout') {
                        comp=node.addComponent(cc.Layout);comp.type=c.layoutType;comp.resizeMode=c.resize;comp.cellSize=new cc.Size(...c.cellSize);
                        [comp.paddingLeft,comp.paddingBottom,comp.paddingRight,comp.paddingTop]=c.padding;
                        [comp.spacingX,comp.spacingY]=c.spacingXY;comp.startAxis=c.startAxis;
                        comp.horizontalDirection=c.horizontalDirection;comp.verticalDirection=c.verticalDirection;comp.affectedByScale=c.affectedByScale;
                        if(c.layoutType===1)comp.alignVertical=!!c.alignCross;
                        if(c.layoutType===2)comp.alignHorizontal=!!c.alignCross;
                        comp.constraint=c.constraint||0;comp.constraintNum=c.constraintCount||2;
                    } else throw Error('Unimplemented native type: '+c.type);
                    if(c.type!=='cc.Sprite')comp.enabled=c.spineBinding&&c.spineBinding.creatorStaticPose?c.spineBinding.creatorStaticPose.nativeEnabled:c.staticButtonBinding?false:c.enabled;
                    nativeRefs.push({sourceId:c.sourceId,nodeUuid:node.uuid,componentUuid:comp.uuid,type:c.type});
                }
                if(plan.spriteOutlineBinding) {
                    const outlineMaterial=await loadAsset(plan.spriteOutlineBinding.creator.materialUuid,cc.Material);
                    native.set(plan.spriteOutlineBinding.materialSourceId,outlineMaterial);
                    require('./sprite-outline-importer.js').bind(plan.spriteOutlineBinding,plan.components,nodes,outlineMaterial,id=>native.get(id));
                }
                if(plan.materialBinding) {
                    const material=await loadAsset(plan.materialBinding.creator.materialUuid,cc.Material);
                    native.set(plan.materialBinding.materialSourceId,material);
                    const sprites=new Map(plan.materialBinding.spriteBindings.map(binding=> {
                        const c=plan.components.find(c=>c.sourceId===binding.sourceId&&c.convertible);
                        if(!c)throw Error('Planned material component absent');
                        return [c.sourceId,nodes.get(c.node).getComponent(cc.Sprite)];
                    }));
                    require('./material-bindings.js').bind(plan.materialBinding,material,sprites);
                }
                if(plan.staticTimeMaterials)for(const row of plan.staticTimeMaterials.materials) {
                    const material=await loadAsset(row.creator.materialUuid,cc.Material);
                    native.set(row.sourceMaterialId,material);
                    const sprites=new Map(row.spriteBindings.map(binding=> {
                        const c=plan.components.find(x=>x.sourceId===binding.sourceId&&x.convertible&&x.type==='cc.Sprite');
                        if(!c)throw Error('STATIC_TIME_PLAN_SPRITE_MISSING');
                        return [c.sourceId,nodes.get(c.node).getComponent(cc.Sprite)];
                    }));
                    require('./static-time-materials.js').apply(plan.staticTimeMaterials,row,material,sprites,id=>native.get(id));
                }
                for(const c of plan.components.filter(c=>c.type==='cc.ProgressBar')) {
                    if(c.convertible)require('./progress.js').bind(nodes.get(c.node).getComponent(cc.ProgressBar),c,nodes);
                    else if(c.staticProgressBinding) {
                        const node=nodes.get(c.node),bar=plan.components.find(x=>x.sourceId===c.staticProgressBinding.barSpriteSourceId);
                        const comp=node.addComponent(cc.ProgressBar);comp.enabled=false;
                        require('./static-progress.js').bind(comp,c.staticProgressBinding,nodes.get(bar.node).getComponent(cc.Sprite));
                    }
                }
                for(const c of plan.components.filter(c=>c.convertible&&c.type==='cc.LabelOutline')) {
                    const label=nodes.get(c.node).getComponent(cc.Label);
                    if(!label)throw Error('Outline requires mapped Label');
                    if(!(label.font instanceof cc.BitmapFont)) {label.enableOutline=!!c.enabled;label.outlineColor=color(c.outlineColor);label.outlineWidth=c.width;}
                    nativeRefs.push({sourceId:c.sourceId,nodeUuid:label.node.uuid,componentUuid:label.uuid,type:c.type});
                }
                // Components are built in an isolated, non-running Scene. Flush the
                // public Label API after all properties/outlines so the default
                // "Label" measurement cannot leak into the saved UITransform.
                if(animationContext)require('./static-animation-integration.js').bind(plan,nodes,animationContext.animations,animationContext.evidence,plan.staticAnimationComponentOrigins);
                if(plan.bitmapMissingGlyphs)require('./bitmap-missing-glyphs.js').attach(plan.bitmapMissingGlyphs,nodes,native,cc);
                if(plan.staticMasks){const masks=require('./static-masks.js');masks.createStaticMasks(plan.staticMasks.masks,nodes,uuid=>masks.resolveSprite(plan,native,uuid));}
                if(plan.layoutCompletion)require('./static-layout-completion.js').attach(plan.layoutCompletion,nodes);
                if(plan.staticControls){
                    const builtinMaterials=new Map();
                    if(plan.staticControls.bindings.some(x=>x.sourceType==='cc.Graphics'))builtinMaterials.set('builtin-graphics',await loadAsset('f0416e68-0200-4b77-a926-4f9d16e494da',cc.Material));
                    require('./static-controls.js').createAssign(plan.staticControls.bindings,nodes,require('./static-field-integration.js').resolver(plan,nodes,native),builtinMaterials);
                }
                if(plan.toggleBinding){
                    const gaps=require('./static-toggle.js').Create(plan.toggleBinding,id=>nodes.get(id),require('./static-field-integration.js').resolver(plan,nodes,native));
                    if(gaps.length)throw Error('STATIC_TOGGLE_BINDING_FAILED: '+gaps.join(','));
                }
                if(plan.spineBinding)require('./spine-ui-transform.js').attachPreservers(plan,nodes,cc);
                require('./static-field-integration.js').createAssign(plan,nodes,native);
                staticSortQueue.attachSourceIdentities(plan,nodes);
                for(const c of plan.components.filter(c=>c.convertible&&c.type==='cc.Label')) {
                    checkTime(plan);nodes.get(c.node).getComponent(cc.Label).updateRenderData(true);
                }
                await resources.attach(plan,canvasNode,loadAsset);
                const numericCodeExercise=numeric.exercise(codeEntries);
                const animationAssets=[];
                for(const spec of plan.animations||[])if(spec.convertible&&!plan.staticAnimationEvidence) {
                    const clip=motion.create(spec,nodes);const raw=EditorExtends.serialize(clip);
                    animationAssets.push({id:spec.id,path:spec.path,serialized:typeof raw==='string'?raw:JSON.stringify(raw)});
                }
                if((plan.prefabInstances||[]).length || (plan.staticPrefabAssetDependencies?.dependencies||[]).length) {
                    // Retained assemblies need the same real native Canvas lifecycle
                    // as the non-retained path before individual Prefab serialization.
                    dynamic.settle(scene,nodes,plan,null,true);
                    const assemblyId=relations.keep(plan,scene,nodes,{nativeRefs,animationAssets,numericCodeExercise,...describe(scene,plan)},native);
                    retained=true;return {assemblyId,nativeRefs,animationAssets,numericCodeExercise};
                }
                dynamic.settle(scene,nodes,plan,null,true);
                const nativeInitialNodes=dynamic.capture(nodes);
                const asset=new cc.SceneAsset();asset.scene=scene;
                jobs.progress('candidate-save',0,1);
                const serialized=EditorExtends.serialize(asset);
                const sourcePrefabs=await prefabs.serialize(plan,nodes);
                return {serialized:typeof serialized==='string'?serialized:JSON.stringify(serialized),nativeInitialNodes,nativeRefs,animationAssets,
                    sourcePrefabs,numericCodeExercise,
                    nodes:plan.nodes.map(n=>({sourceId:n.sourceId,nodeUuid:nodes.get(n.sourceId).uuid})),...describe(scene,plan)};
            } catch(error) {assembleError=error;throw error;}
            finally {
                if(!retained) {
                    const cleanup=await ownedBuildTeardown.cleanupAfterBuild(scene,{cc,cce:globalThis.cce,
                        editorExtends:globalThis.EditorExtends,dynamicRelease:dynamic.release},assembleError);
                    if(cleanup.error) {
                        if(assembleError) {
                            console.error('CREATOR_BUILD_SCENE_TEARDOWN_AFTER_FAILURE: '+String(cleanup.error.message||cleanup.error));
                        } else throw cleanup.error;
                    }
                }
            }
        },
        async readSaved(uuid,plan) {
            staticSortQueue.validatePlan(plan);
            const asset=await loadAsset(uuid,cc.SceneAsset,plan.readbackReloadSavedAssets===true);const scene=asset.scene;
            const sceneScopeModule=require('./creator-saved-scene-scope.js');
            const sceneScope=sceneScopeModule.begin({asset,requestedUuid:uuid,scene,cc,cce:globalThis.cce,editorExtends:globalThis.EditorExtends,
                dynamicRelease:ownedScene=>dynamic.release(ownedScene)});
            let readbackError=null;
            try {
            ownedUndo.registerRoot(scene);
            // Loading a SceneAsset alone does not perform Scene._load, which is
            // where Creator expands native instance placeholders. Initialize
            // this owned, inactive Scene without running/activating it.
            if((plan.prefabInstances||[]).length)scene._load();
            ownedUndo.registerRoot(scene);
            const nodes=[];const visit=n=>{nodes.push(n);for(const child of sourceChildren(n))visit(child);};visit(scene);
            const design=nodes.find(n=>n.name==='DesignRoot');if(!design)throw Error('Saved scene missing DesignRoot');
            const saved=[];const walk=n=>{saved.push(n);for(const child of sourceChildren(n))walk(child);};for(const n of design.children)walk(n);
            if(saved.length!==plan.nodes.length)throw Error('Saved source node count mismatch: '+saved.length+'/'+plan.nodes.length);
            // Match hierarchy by child indices; duplicate source names do not lose identity.
            const mapped=new Map(),sourceNodes=new Map(plan.nodes.map(n=>[n.sourceId,n]));
            function match(sid,n) {
                const src=sourceNodes.get(sid);if(!src||src.name!==n.name||src.children.length!==sourceChildren(n).length)throw Error('Saved hierarchy differs');
                mapped.set(sid,n);src.children.forEach((id,i)=>match(id,sourceChildren(n)[i]));
            }
            plan.nodes.filter(n=>n.parent===null).forEach((n,i)=>match(n.sourceId,design.children[i]));
            // Initialize the owned saved Scene normally. Persistent native
            // presentation components run their lifecycle; audit remains read-only.
            if(plan.spineBinding) {
                dynamic.settle(scene,mapped,plan,null,false);
                const geometry=require('./spine-ui-transform.js').readAuthored(plan,mapped,cc);
                if(geometry.status!=='verified')throw Error('SPINE_UI_TRANSFORM_SAVED_SCENE_MISMATCH: '+JSON.stringify(geometry));
            }
            for(const n of plan.nodes)if(n.sourceUITransformEnabled===false&&mapped.get(n.sourceId).getComponent(cc.UITransform).enabled!==false)throw Error('Saved UITransform enabled state differs');
            const labels=[];const refs=[];const numericCodeBindings=[];
            for(const c of plan.components.filter(c=>c.convertible)) {
                const n=mapped.get(c.node);const type=c.type==='cc.LabelOutline'?'Label':c.type.slice(3);const comp=c.behaviorBinding?behaviors.read(n,c.behaviorBinding,c.enabled):n.getComponent(c.spineBinding?cc.sp.Skeleton:cc[type]);
                if(!comp)throw Error('Saved component missing: '+c.type);
                if(c.nativeSpriteOutlineMaterialSourceId&&(!plan.spriteOutlineBinding||!require('./sprite-outline-material-bindings.js').readBound(plan.spriteOutlineBinding,comp.customMaterial,c.sourceId,comp,id=>{const a=plan.assets.find(x=>x.sourceId===id);return a&&comp.spriteFrame&&comp.spriteFrame._uuid===a.spriteFrameUuid?comp.spriteFrame:null;})))throw Error('Saved outline material differs: '+c.sourceId);
                if(c.nativeMaterialSourceId&&(!plan.materialBinding||!comp.customMaterial||comp.customMaterial._uuid!==plan.materialBinding.creator.materialUuid||
                   !require('./material-bindings.js').readBound(plan.materialBinding,comp.customMaterial,comp)))throw Error('Saved custom material differs: '+c.sourceId);
                if(c.type==='cc.ProgressBar')require('./progress.js').read(comp,c,mapped);
                if(c.codeClassName)numericCodeBindings.push(numeric.read(comp,c));
                if(c.type==='cc.Label'&&comp.overflow!==(c.nativeOverflow??c.overflow))throw Error('Saved Label overflow policy differs: '+c.sourceId);
                if(c.type==='cc.Sprite'&&comp.sizeMode!==(c.nativeSizeMode??c.sizeMode))throw Error('Saved Sprite sizing policy differs: '+c.sourceId);
                refs.push({sourceId:c.sourceId,nodeUuid:n.uuid,componentUuid:comp.uuid,type:c.type,nativeType:cc.js.getClassName(comp)});
                if(c.type==='cc.Label'||c.type==='cc.RichText')labels.push({sourceId:c.sourceId,text:comp.string,fontUuid:comp.font&&comp.font._uuid,useSystemFont:comp.useSystemFont,fontFamily:comp.fontFamily});
            }
            const frames=[];
            const savedFrames=new Map(saved.flatMap(n=>n.getComponents(cc.Sprite)).map(s=>s.spriteFrame).filter(Boolean).map(sf=>[sf._uuid,sf]));
            for(const a of plan.assets.filter(a=>a.kind==='sprite')) {
                // Resolve from saved Sprite where available or load the importer-owned subresource.
                let sf=savedFrames.get(a.spriteFrameUuid);
                if(!sf) {
                    // Native importer identities are sent by the main process for unused source assets.
                    if(!a.spriteFrameUuid)throw Error('Native SpriteFrame identity required for readback');
                    sf=await loadAsset(a.spriteFrameUuid,cc.SpriteFrame);
                }
                frames.push({sourceId:a.sourceId,uuid:sf._uuid,textureUuid:sf.texture&&sf.texture._uuid,
                    rect:[sf.rect.x,sf.rect.y,sf.rect.width,sf.rect.height],originalSize:[sf.originalSize.width,sf.originalSize.height],
                    offset:[sf.offset.x,sf.offset.y],border:[sf.insetLeft,sf.insetTop,sf.insetRight,sf.insetBottom],
                    mesh:sf.vertices?{rawPosition:sf.vertices.rawPosition.flatMap(v=>[v.x,v.y,v.z]),indexes:Array.from(sf.vertices.indexes),uv:Array.from(sf.vertices.uv),nuv:Array.from(sf.vertices.nuv)}:null});
            }
            const animations=[];
            for(const info of plan.animationAssets||[]) {
                const spec=(plan.animations||[]).find(s=>s.id===info.id);
                animations.push(motion.read(await loadAsset(info.uuid,cc.AnimationClip),spec));
            }
            const jsonAssets=[];
            const audioAssets=[];
            for(const a of plan.assets.filter(a=>a.kind==='audio')) {
                const clip=await loadAsset(a.uuid,cc.AudioClip),duration=clip.getDuration();
                if(!Number.isFinite(duration)||duration<0)throw Error('Native AudioClip duration unavailable');
                audioAssets.push({sourceId:a.sourceId,uuid:clip._uuid,duration});
            }
            for(const a of plan.assets.filter(a=>a.kind==='json')) {
                const json=await loadAsset(a.uuid,cc.JsonAsset);jsonAssets.push({sourceId:a.sourceId,uuid:json._uuid,value:json.json});
            }
            const fontPages=[];
            for(const a of plan.assets.filter(a=>a.kind==='bitmap')) {
                const font=await loadAsset(a.uuid,cc.BitmapFont),sf=font.spriteFrame;
                if(!(sf instanceof cc.SpriteFrame)||!sf.texture)throw Error('Native BitmapFont page absent');
                fontPages.push({sourceId:a.sourceId,fontUuid:font._uuid,spriteFrameUuid:sf._uuid,textureUuid:sf.texture._uuid,
                    rect:[sf.rect.x,sf.rect.y,sf.rect.width,sf.rect.height]});
            }
            const templates=new Map();
            for(const info of plan.savedPrefabs||[])templates.set(info.sourceId,await loadAsset(info.uuid,cc.Prefab,plan.readbackReloadSavedAssets===true));
            const staticAssets=new Map(templates);
            const retainedAssets=plan.staticRetainedAssets?await require('./static-retained-assets.js').load(plan.staticRetainedAssets):new Map();
            for(const [sid,asset]of retainedAssets)staticAssets.set(sid,asset);
            const staticRetainedAssetReadback=plan.staticRetainedAssets?await require('./static-retained-assets.js').read(plan.staticRetainedAssets,retainedAssets,plan.nativeProjectRoot):[];
            const animationContext=plan.staticAnimationEvidence?await require('./static-animation-context.js').load(plan,loadAsset,staticAssets):null;
            if(plan.spriteOutlineBinding)staticAssets.set(plan.spriteOutlineBinding.materialSourceId,await loadAsset(plan.spriteOutlineBinding.creator.materialUuid,cc.Material));
            for(const a of (plan.spineBinding&&plan.spineBinding.assets)||[])staticAssets.set(a.sourceId,await loadAsset(a.creator.nativeUuid,cc.sp.SkeletonData));
            if(plan.materialBinding)staticAssets.set(plan.materialBinding.materialSourceId,await loadAsset(plan.materialBinding.creator.materialUuid,cc.Material));
            if(plan.components.some(c=>c.staticFieldBinding))for(const a of plan.assets)staticAssets.set(a.sourceId,await loadAsset(a.kind==='sprite'?a.spriteFrameUuid:a.uuid,a.kind==='sprite'?cc.SpriteFrame:a.kind==='json'?cc.JsonAsset:a.kind==='audio'?cc.AudioClip:cc.Font));
            let staticTimeMaterials=null;
            if(plan.staticTimeMaterials) {
                const materials=[];
                for(const row of plan.staticTimeMaterials.materials) {
                    const material=await loadAsset(row.creator.materialUuid,cc.Material);
                    const effect=await loadAsset(row.creator.effectUuid,cc.EffectAsset);
                    staticAssets.set(row.sourceMaterialId,material);
                    const sprites=new Map(row.spriteBindings.map(binding=> {
                        const c=plan.components.find(x=>x.sourceId===binding.sourceId&&x.convertible&&x.type==='cc.Sprite');
                        if(!c||!mapped.has(c.node))throw Error('STATIC_TIME_SAVED_SPRITE_MISSING');
                        return [c.sourceId,mapped.get(c.node).getComponent(cc.Sprite)];
                    }));
                    materials.push(require('./static-time-materials.js').readPersistent(plan.staticTimeMaterials,row,material,effect,sprites,id=>staticAssets.get(id)));
                }
                staticTimeMaterials={schema:plan.staticTimeMaterials.schema,profile:plan.staticTimeMaterials.profile,sourceManifestSha256:plan.staticTimeMaterials.sourceManifestSha256,normalizedIrSha256:plan.staticTimeMaterials.normalizedIrSha256,materials};
            }
            const prefabInstances=relations.read(plan,mapped,templates,plan.savedPrefabs||[]);
            const sourcePrefabs=[];
            for(const spec of plan.sourcePrefabs||[]) {
                jobs.progress('native-readback',sourcePrefabs.length,(plan.sourcePrefabs||[]).length);
                if(sourcePrefabs.length%16===0)await new Promise(resolve=>setTimeout(resolve,0));
                checkTime(plan);
                const info=(plan.savedPrefabs||[]).find(p=>p.sourceId===spec.sourceId);
                if(!info)throw Error('Saved prefab identity absent');
                sourcePrefabs.push(prefabs.read(templates.get(spec.sourceId),spec,plan,info,templates,staticAssets,animationContext));
            }
            const dynamicUiProbes=await dynamic.probe(plan,design,(done,total)=>jobs.progress('native-readback',sourcePrefabs.length+done,sourcePrefabs.length+total));
            const spineSpecs=plan.components.filter(c=>c.convertible&&c.spineBinding);
            const spineModule=require('./spine-bindings.js'),spineById=new Map(spineSpecs.map(c=>[c.sourceId,c]));
            const spineBindings=spineModule.readCreatorSpineBindings(spineSpecs.map(c=>c.spineBinding),id=> {
                const c=spineById.get(id);return c?mapped.get(c.node).getComponents(cc.sp.Skeleton):[];
            },id=>({sourceActivity:spineModule.sourceNodeActivity(plan,spineById.get(id).node),readbackScope:'saved_scene_mapped'}));
            const sourceComponentCoverage=plan.components.map((spec,sourceIndex)=>({sourceIndex,sourceId:spec.sourceId||null,sourceType:spec.type||null,
                nativeComponentReadback:refs.filter(row=>row.sourceId===spec.sourceId).map(row=>({sourceId:row.sourceId,type:row.type,nativeType:row.nativeType,componentUuid:row.componentUuid,nodeUuid:row.nodeUuid}))}));
            return {sourceDiagnostics:plan.sourceDiagnostics||[],staticRetainedAssetReadback,spineBindings,staticTimeMaterials,resourceProbes:await resources.read(plan,scene),tiledRenderer:tiledReadback(plan,mapped),dynamicUiProbes,nativeInitialNodes:plan.nativeInitialNodes,sourcePrefabs,prefabInstances,jsonAssets,audioAssets,fontPages,animations,numericCodeBindings,nodeCount:saved.length,sourceComponentCoverage,nodes:[...mapped].map(([sourceId,n])=>({sourceId,nodeUuid:n.uuid,name:n.name,
                position:[n.position.x,n.position.y,n.position.z],size:[n.getComponent(cc.UITransform).width,n.getComponent(cc.UITransform).height],
                pivot:[n.getComponent(cc.UITransform).anchorX,n.getComponent(cc.UITransform).anchorY],scale:[n.scale.x,n.scale.y,n.scale.z],
                rotation:[n.rotation.x,n.rotation.y,n.rotation.z,n.rotation.w],active:n.active,...prefabs.uiState(n,sourceNodes.get(sourceId))})),components:refs,labels,frames};
            } catch(error) { readbackError=error; throw error; }
            finally {
                const cleanup=await sceneScope.cleanup();
                console.info('CREATOR_SAVED_SCENE_CLEANUP '+JSON.stringify({cleaned:cleanup.cleaned,
                    postCleanup:cleanup.postCleanup||null,error:cleanup.error?String(cleanup.error.message):null}));
                if(cleanup.error) {
                    if(!readbackError)throw cleanup.error;
                    sceneScopeModule.preservePrimaryError(readbackError,cleanup.error);
                    console.error('CREATOR_SAVED_SCENE_CLEANUP_AFTER_FAILURE: '+String(cleanup.error.message));
                }
            }
        }
    }
};
