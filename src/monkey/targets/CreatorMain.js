'use strict';
// Creator-only, explicitly invoked. No source scripts are loaded or run.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const execution=require('./execution.js');
const batch=require('./batch.js');
const spriteMetadata=require('./sprite-metadata.js');
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
const req = (message, ...args) => Editor.Message.request('asset-db', message, ...args);
function within(root, relative) {
    if (typeof relative !== 'string' || path.isAbsolute(relative) || relative.split(/[\\/]/).includes('..')) throw Error('Unsafe relative path');
    const dest = path.resolve(root, relative);
    let cursor = dest;
    while (cursor !== path.dirname(cursor)) {
        if (fs.existsSync(cursor) && fs.lstatSync(cursor).isSymbolicLink()) throw Error('Symlink path');
        cursor = path.dirname(cursor);
    }
    if (!dest.startsWith(root + path.sep)) throw Error('Path escapes candidate');
    return dest;
}
async function sceneJob(method,args,phase,trackExecution=true) {
    const call=async(name,values)=>{
        try{return await Editor.Message.request('scene','execute-scene-script',{name:'monkey-import',method:name,args:values});}
        catch(error){throw Error('NATIVE_SCENE_RPC_FAILED '+name+': '+String(error&&error.message||error).split('\n')[0].slice(0,512));}
    };
    const started=await call('beginJob',[method,args]);
    if(!started||typeof started.jobId!=='string')throw Error('NATIVE_JOB_START_INVALID');
    while(true) {
        const state=await call('jobStatus',[started.jobId]);
        if(!state||state.jobId!==started.jobId)throw Error('NATIVE_JOB_STATUS_INVALID');
        if(trackExecution)execution.checkpoint(state.phase||phase,state.processed,state.total);
        if(state.status==='failed')throw Error('Native '+method+' failed: '+state.error);
        if(state.status==='completed')return call('takeJob',[started.jobId]);
        if(state.status!=='running')throw Error('NATIVE_JOB_STATUS_INVALID');
        await new Promise(resolve=>setTimeout(resolve,250));
    }
}
module.exports = {
    load() {execution.start(()=>module.exports.methods.importCandidate()).catch(error=>console.error('MONKEY_NATIVE_BOOTSTRAP_FAILED: '+String(error.message||error).slice(0,1024)));}, unload() {execution.stop();},
    methods: {
        async revalidateSavedCandidate() {
            const root=path.resolve(Editor.Project.path);
            const manifestRaw=fs.readFileSync(within(root,'manifest.json'));
            const planRaw=fs.readFileSync(path.join(__dirname,'import-plan.json'));
            const manifest=JSON.parse(manifestRaw),plan=JSON.parse(planRaw);
            const contextRaw=fs.readFileSync(within(root,'Analysis/Readback/native-readback-context.json'));
            const context=JSON.parse(contextRaw);
            const original=JSON.parse(fs.readFileSync(within(root,'Analysis/Readback/editor-readback.json'),'utf8'));
            if(hash(contextRaw)!==original.nativeReadbackContextSha256||context.manifestSha256!==hash(manifestRaw)||context.sourcePlanSha256!==hash(planRaw)||
                context.projectUuid!==manifest.projectUuid||context.projectUuid!==plan.projectUuid||
                context.sceneUuid!==original.sceneUuid||context.nativePlan.nativeProjectRoot!==root)
                throw Error('CREATOR_REOPEN_NATIVE_CONTEXT_IDENTITY_MISMATCH');
            const savedPrefabs=context.nativePlan.savedPrefabs.map(info=>({...info,
                sha256:hash(fs.readFileSync(within(root,info.path)))}));
            const nativePlan={...context.nativePlan,savedPrefabs,nativeDeadlineMs:Date.now()+1200000,readbackReloadSavedAssets:true};
            await Editor.Message.request('scene','execute-scene-script',
                {name:'monkey-import',method:'beginOwnedImportUndo',args:[]});
            try {
                const revision=await require('./reopen-verification.js').createRevision({
                    projectRoot:root,projectUuid:context.projectUuid,sceneUuid:context.sceneUuid,
                    creatorVersion:Editor.App.version,nativeRoots:plan.outputPaths.nativeRoots,
                    readbackContext:{...original,sourcePlanSha256:hash(planRaw)},
                    runReadSaved:()=>sceneJob('readSaved',[context.sceneUuid,nativePlan],'native-readback',false)});
                console.info('MONKEY_EDITOR_REOPEN_READBACK '+JSON.stringify(revision));
                return revision;
            } finally {
                await Editor.Message.request('scene','execute-scene-script',
                    {name:'monkey-import',method:'finishOwnedImportUndo',args:[]});
            }
        },
        async inspectOrdinarySaveApi() {
            const root=path.resolve(Editor.Project.path);
            const planRaw=fs.readFileSync(path.join(__dirname,'import-plan.json'));
            const result=await Editor.Message.request('scene','execute-scene-script',
                {name:'monkey-import',method:'inspectOrdinarySaveApi',args:[]});
            const directory=within(root,'Analysis/Readback/EditorSerialization');
            fs.mkdirSync(directory,{recursive:true});
            let sequence=1;
            while(fs.existsSync(path.join(directory,'save-api-'+sequence+'.json')))sequence++;
            const file=path.join(directory,'save-api-'+sequence+'.json');
            fs.writeFileSync(file,JSON.stringify({schemaVersion:1,planSha256:hash(planRaw),
                capturedAtUtc:new Date().toISOString(),...result},null,2)+'\n',{flag:'wx'});
            console.info('MONKEY_EDITOR_SAVE_API_RECEIPT '+file);
            return file;
        },
        async stopOrdinarySaveProbe() {
            return Editor.Message.request('scene','execute-scene-script',
                {name:'monkey-import',method:'stopOrdinarySaveProbe',args:[]});
        },
        async importCandidate() {
            await Editor.Message.request('scene','execute-scene-script',
                {name:'monkey-import',method:'beginOwnedImportUndo',args:[]});
            try { return await module.exports.methods.importCandidateOwned(); }
            finally {
                const evidence=await Editor.Message.request('scene','execute-scene-script',
                    {name:'monkey-import',method:'finishOwnedImportUndo',args:[]});
                const root=path.resolve(Editor.Project.path);
                const directory=within(root,'Analysis/Readback');
                fs.mkdirSync(directory,{recursive:true});
                let sequence=1;
                while(fs.existsSync(path.join(directory,'owned-import-undo-'+sequence+'.json')))sequence++;
                fs.writeFileSync(path.join(directory,'owned-import-undo-'+sequence+'.json'),
                    JSON.stringify(evidence,null,2)+'\n',{flag:'wx'});
            }
        },
        async importCandidateOwned() {
            const root = path.resolve(Editor.Project.path);
            const manifestRaw = fs.readFileSync(within(root, 'manifest.json'));
            const manifest = JSON.parse(manifestRaw);
            const planRaw = fs.readFileSync(path.join(__dirname, 'import-plan.json'));
            const plan = JSON.parse(planRaw);
            const outputPaths=plan.outputPaths||{scene:'assets/generated/views/Candidate.scene',prefabs:'assets/generated/prefabs',animations:'assets/generated/animations',nativeRoots:['assets']};
            if(!Array.isArray(outputPaths.nativeRoots)||outputPaths.nativeRoots.length<1||outputPaths.nativeRoots.length>8)throw Error('Invalid native output roots');
            for(const value of [outputPaths.scene,outputPaths.prefabs,outputPaths.animations,...outputPaths.nativeRoots]) {
                if(typeof value!=='string'||!(value==='assets'||value.startsWith('assets/')))throw Error('Invalid typed output path');within(root,value);
            }

            const project = JSON.parse(fs.readFileSync(within(root, 'package.json'), 'utf8'));
            if (manifest.targetProfile !== 'cocos-3.8.8' || project.creator.version !== '3.8.8' || Editor.App.version !== '3.8.8' || project.uuid !== plan.projectUuid || manifest.projectUuid !== project.uuid) throw Error('Wrong Creator/project');
            if (fs.existsSync(within(root, outputPaths.scene)) || fs.existsSync(within(root, 'Analysis/Readback/editor-readback.json')) || fs.existsSync(within(root, 'Analysis/editor-readback.json'))) throw Error('Native output exists; use a fresh candidate');
            // Creator import legitimately edits metas; all original content and glue must still match.
            for (const f of manifest.files) {
                if (f.path.startsWith('assets/') && f.path.endsWith('.meta')) continue;
                if (hash(fs.readFileSync(within(root, f.path))) !== f.sha256) throw Error('Generated content changed: ' + f.path);
            }
            for(const a of plan.animations||[])if(a.convertible&&fs.existsSync(within(root,a.path)))throw Error('Animation output exists; use fresh candidate');
            for(const p of plan.sourcePrefabs||[]) {
                if(!p.path.startsWith(outputPaths.prefabs+'/')||!p.path.endsWith('.prefab'))throw Error('Unsafe prefab path');
                if(fs.existsSync(within(root,p.path)))throw Error('Prefab output exists; use fresh candidate');
            }
            if (!(await req('query-ready'))) throw Error('Asset database not ready');
            let codeEmission=null;
            if(manifest.codeEmission) {
                const spec=manifest.codeEmission;
                if(typeof spec.scriptPath!=='string'||!spec.scriptPath.startsWith('assets/'))throw Error('Typed script path required');
                within(root,spec.scriptPath);
                const info=await req('query-asset-info','db://'+spec.scriptPath);
                if(!info||info.invalid||info.uuid!==spec.scriptUuid)throw Error('Native code script identity differs');
                codeEmission={scriptPath:spec.scriptPath,scriptUuid:info.uuid,language:spec.language};
            }
            const apiTiming={};
            const timedReq=async(message,...args)=>{
                const start=Date.now();
                try{return await req(message,...args);}
                finally{const t=apiTiming[message]||(apiTiming[message]={count:0,totalMs:0,maxMs:0});const ms=Date.now()-start;t.count++;t.totalMs+=ms;t.maxMs=Math.max(t.maxMs,ms);}
            };
            let prepared=0;
            // query-ready already completed the initial import. Do not enqueue
            // two redundant refreshes per image on whole-package inputs.
            await batch.map(plan.assets,8,async a=>{
                execution.checkpoint('texture-metadata',prepared,plan.assets.length);
                const url = 'db://' + a.path;
                const info = await timedReq('query-asset-info', url);
                if (!info || info.invalid || info.uuid !== a.uuid) throw Error('Native asset import/identity mismatch: ' + a.path);
                if (a.kind === 'sprite') {
                    // Query the parent to discover the native subasset identity.
                    // Save/reimport the SpriteFrame itself: updating a parent
                    // image meta can persist subMetas without invalidating the
                    // already-imported SpriteFrame payload in library.
                    const m = JSON.parse(JSON.stringify(await timedReq('query-asset-meta', a.uuid)));
                    const spriteEntries = Object.values(m.subMetas || {}).filter(s => s.importer === 'sprite-frame');
                    if (spriteEntries.length !== 1) throw Error('Expected exactly one native sprite-frame');
                    const sm = spriteEntries[0]; const u = sm.userData;
                    const [left, top, right, bottom] = a.border;
                    const origin=a.trimOrigin||[0,0];
                    const fullRect=origin.every(v=>v===0)&&a.offset.every(v=>v===0)&&a.size.every((v,i)=>v===a.originalSize[i]);
                    const desired={trimType: fullRect?'none':'custom', rotated: false, trimX: origin[0], trimY: origin[1],
                        width: a.size[0], height: a.size[1], rawWidth: a.originalSize[0], rawHeight: a.originalSize[1],
                        offsetX: a.offset[0], offsetY: a.offset[1], borderLeft: left, borderTop: top, borderRight: right, borderBottom: bottom};
                    // Subresource IDs are assigned by the native importer and retained, never synthesized.
                    const vertices=spriteMetadata.rectVertices(a);
                    if(Object.entries(desired).some(([key,value])=>u[key]!==value)||JSON.stringify(u.vertices)!==JSON.stringify(vertices)) {
                        Object.assign(u,desired,{vertices,meshType:0});
                        const saved=await timedReq('save-asset-meta', sm.uuid, JSON.stringify(sm));
                        if(saved&&saved.invalid)throw Error('Native SpriteFrame metadata save failed: '+a.sourceId);
                        const persisted=await timedReq('query-asset-meta',sm.uuid);
                        if(!persisted||persisted.uuid!==sm.uuid||!persisted.userData||
                            Object.entries(desired).some(([key,value])=>persisted.userData[key]!==value)||
                            JSON.stringify(persisted.userData.vertices)!==JSON.stringify(vertices))throw Error('Native SpriteFrame metadata did not persist: '+a.sourceId);
                        // Public reimport returns void; its library output is
                        // checked below before the scene worker loads the frame.
                        await timedReq('reimport-asset',sm.uuid);
                    }
                }
                prepared++;
            });
            await timedReq('refresh-asset','db://assets');
            let resolved=0;
            const assets=await batch.map(plan.assets,16,async a=>{
                execution.checkpoint('textures',resolved++,plan.assets.length);
                const url='db://'+a.path,info=await timedReq('query-asset-info',url);
                if(!info||info.invalid||info.uuid!==a.uuid)throw Error('Native asset identity changed: '+a.path);
                if(a.kind==='sprite') {
                    const sf = await timedReq('query-asset-info', url + '/spriteFrame');
                    const texture = await timedReq('query-asset-info', url + '/texture');
                    if (!sf || !texture || sf.invalid || texture.invalid) throw Error('Native subresource missing: ' + url);
                    if(!/^[a-f0-9-]{36}@[a-f0-9]+$/.test(sf.uuid))throw Error('Native SpriteFrame storage identity unsupported');
                    // Profile-bound Creator library readiness, not a retry or
                    // another metadata write. Observe this one import until its
                    // actual generated payload matches the requested meta.
                    const library=within(root,'library/'+sf.uuid.slice(0,2)+'/'+sf.uuid+'.json');
                    const readyEnd=Math.min(Date.now()+10000,execution.deadlineMs()??Infinity);
                    while(true){
                        let data=null;try{data=JSON.parse(fs.readFileSync(library,'utf8'));}catch(error){if(error.code&&error.code!=='ENOENT')throw error;}
                        if(spriteMetadata.libraryMatches(a,data))break;
                        if(Date.now()>=readyEnd)throw Error('Native SpriteFrame import did not settle: '+a.sourceId);
                        execution.checkpoint('textures',resolved,plan.assets.length);
                        await new Promise(resolve=>setTimeout(resolve,100));
                    }
                    return {...a, spriteFrameUuid: sf.uuid, textureUuid: texture.uuid};
                }
                return {...a};
            });
            fs.mkdirSync(within(root,'Analysis/Readback'),{recursive:true});fs.writeFileSync(within(root,'Analysis/Readback/native-api-timing.json'),JSON.stringify({stage:'assets',apiTiming},null,2)+'\n',{flag:'wx'});
            execution.checkpoint('hierarchy',0,plan.nodes.length);
            const nativeDeadlineMs=execution.deadlineMs()??Date.now()+1200000;
            const resourceProbes=plan.resourceProbes?JSON.parse(JSON.stringify(plan.resourceProbes)):null;
            if(resourceProbes) {
                if(resourceProbes.profile!=='creator-spine-3.8-v1'||resourceProbes.spines.length>16)throw Error('Unsupported resource probe scope');
                for(const spec of resourceProbes.spines) {
                    for(const file of spec.files)if(hash(fs.readFileSync(within(root,file.path)))!==file.sha256)throw Error('Resource probe original bytes changed');
                    const skeleton=await timedReq('query-asset-info','db://'+spec.skeletonPath);
                    if(!skeleton||skeleton.invalid||skeleton.uuid!==spec.skeletonUuid)throw Error('Native Spine import/UUID differs');
                    for(const page of spec.pages) {
                        const image=await timedReq('query-asset-info','db://'+page.path);
                        const texture=await timedReq('query-asset-info','db://'+page.path+'/texture');
                        if(!image||image.uuid!==page.imageUuid||!texture||texture.invalid)throw Error('Spine native page import differs');
                        page.textureUuid=texture.uuid;
                    }
                }
            }
            let materialReadback=null;
            if(plan.materialBinding) {
                const spec=plan.materialBinding,materialPath=within(root,spec.creator.materialPath);
                const metaPath=within(root,spec.creator.materialMetaPath);
                if(fs.existsSync(materialPath))throw Error('Native material output already exists');
                const serialized=await sceneJob('prepareMaterial',[{...spec,nativeDeadlineMs}],'materials');
                fs.mkdirSync(path.dirname(materialPath),{recursive:true});
                if(fs.existsSync(metaPath)) {
                    if(JSON.parse(fs.readFileSync(metaPath,'utf8')).uuid!==spec.creator.materialUuid)throw Error('Native material metadata UUID conflict');
                } else fs.writeFileSync(metaPath,JSON.stringify({ver:'1.0.5',importer:'material',imported:false,uuid:spec.creator.materialUuid,files:[],subMetas:{},userData:{}},null,2),{flag:'wx'});
                fs.writeFileSync(materialPath,serialized,{flag:'wx'});
                await timedReq('refresh-asset','db://'+path.dirname(spec.creator.materialPath));
                const info=await timedReq('query-asset-info','db://'+spec.creator.materialPath);
                const meta=JSON.parse(fs.readFileSync(metaPath,'utf8'));
                if(!info||info.invalid||info.uuid!==spec.creator.materialUuid||meta.uuid!==spec.creator.materialUuid)throw Error('Native material import UUID differs');
                materialReadback=await sceneJob('readMaterial',[{...spec,nativeDeadlineMs}],'materials');
                materialReadback.metaUuid=meta.uuid;materialReadback.metaUuidVerified=true;
            }
            let spriteOutlineReadback=null;
            if(plan.spriteOutlineBinding) {
                const spec=plan.spriteOutlineBinding,materialPath=within(root,spec.creator.materialPath),metaPath=within(root,spec.creator.materialMetaPath);
                if(fs.existsSync(materialPath))throw Error('Outline material output already exists');
                const serialized=await sceneJob('prepareOutlineMaterial',[{...spec,nativeDeadlineMs}],'materials');
                fs.mkdirSync(path.dirname(materialPath),{recursive:true});
                if(fs.existsSync(metaPath)){
                    if(JSON.parse(fs.readFileSync(metaPath,'utf8')).uuid!==spec.creator.materialUuid)throw Error('Outline material metadata UUID conflict');
                }else fs.writeFileSync(metaPath,JSON.stringify({ver:'1.0.5',importer:'material',imported:false,uuid:spec.creator.materialUuid,files:[],subMetas:{},userData:{}},null,2),{flag:'wx'});
                fs.writeFileSync(materialPath,serialized,{flag:'wx'});
                await timedReq('refresh-asset','db://'+path.dirname(spec.creator.materialPath));
                const info=await timedReq('query-asset-info','db://'+spec.creator.materialPath),meta=JSON.parse(fs.readFileSync(metaPath,'utf8'));
                if(!info||info.invalid||info.uuid!==spec.creator.materialUuid||meta.uuid!==spec.creator.materialUuid)throw Error('Outline material import UUID differs');
                spriteOutlineReadback=await sceneJob('readOutlineMaterial',[{...spec,nativeDeadlineMs}],'materials');
                spriteOutlineReadback.metaUuid=meta.uuid;spriteOutlineReadback.metaUuidVerified=true;
            }
            if(plan.staticTimeMaterials)for(const row of plan.staticTimeMaterials.materials) {
                const materialPath=within(root,row.creator.materialPath),metaPath=within(root,row.creator.materialMetaPath);
                if(fs.existsSync(materialPath))throw Error('Static-time material output already exists');
                const serialized=await sceneJob('prepareStaticTimeMaterial',[{...plan.staticTimeMaterials,nativeDeadlineMs},row.sourceMaterialId],'materials');
                fs.mkdirSync(path.dirname(materialPath),{recursive:true});
                if(fs.existsSync(metaPath)) {
                    if(JSON.parse(fs.readFileSync(metaPath,'utf8')).uuid!==row.creator.materialUuid)throw Error('Static-time material metadata UUID conflict');
                } else fs.writeFileSync(metaPath,JSON.stringify({ver:'1.0.5',importer:'material',imported:false,uuid:row.creator.materialUuid,files:[],subMetas:{},userData:{}},null,2),{flag:'wx'});
                fs.writeFileSync(materialPath,serialized,{flag:'wx'});
                await timedReq('refresh-asset','db://'+path.dirname(row.creator.materialPath));
                const info=await timedReq('query-asset-info','db://'+row.creator.materialPath);
                if(!info||info.invalid||info.uuid!==row.creator.materialUuid||JSON.parse(fs.readFileSync(metaPath,'utf8')).uuid!==row.creator.materialUuid)
                    throw Error('Static-time material import identity differs');
                await sceneJob('readStaticTimeMaterial',[{...plan.staticTimeMaterials,nativeDeadlineMs},row.sourceMaterialId],'materials');
            }
            for(const entry of plan.staticRetainedAssets?.assets||[])if(entry.retentionKind==='builtin-default-material') {
                const dest=within(root,entry.creator.path);
                if(fs.existsSync(dest))throw Error('Retained builtin material already exists');
                const serialized=await sceneJob('prepareRetainedBuiltin',[entry],'materials');
                fs.mkdirSync(path.dirname(dest),{recursive:true});
                fs.writeFileSync(dest+'.meta',JSON.stringify({ver:'1.0.21',importer:'material',imported:false,uuid:entry.creator.uuid,files:[],subMetas:{},userData:{}}));
                fs.writeFileSync(dest,serialized,{flag:'wx'});
                await timedReq('refresh-asset','db://'+path.dirname(entry.creator.path));
                const info=await timedReq('query-asset-info','db://'+entry.creator.path);
                if(!info||info.invalid||info.uuid!==entry.creator.uuid)throw Error('Retained builtin material identity differs');
            }
            const nativePlan={...plan,nativeProjectRoot:root,resourceProbes,assets,nativeDeadlineMs,components:plan.components.filter(c=>c.convertible||c.staticFieldBinding||c.staticProgressBinding||c.staticControlBinding||(plan.staticAnimationEvidence&&c.type==='cc.Animation')),animations:(plan.animations||[]).filter(a=>a.convertible)};
            const earlyAnimationAssets=[];
            if(plan.staticAnimationEvidence) {
                const prepared=await sceneJob('prepareStaticAnimationAssets',[nativePlan],'animations');
                for(const a of prepared) {
                    if(!a.path.startsWith(outputPaths.animations+'/')||!a.path.endsWith('.anim'))throw Error('Unsafe animation path');
                    fs.mkdirSync(path.dirname(within(root,a.path)),{recursive:true});
                    await timedReq('refresh-asset','db://'+path.dirname(a.path));
                    const info=await timedReq('create-asset','db://'+a.path,a.serialized,{overwrite:false,rename:false});
                    if(!info||info.invalid)throw Error('Static animation asset import failed');
                    earlyAnimationAssets.push({id:a.id,path:a.path,uuid:info.uuid,sha256:hash(fs.readFileSync(within(root,a.path)))});
                }
                nativePlan.animationAssets=earlyAnimationAssets;
            }
            let result = await sceneJob('assemble',[nativePlan],'hierarchy');
            if (!result || (typeof result.serialized !== 'string'&&!result.assemblyId)) throw Error('No native scene serialization');
            const assemblyId=result.assemblyId;const savedPrefabs=[];
            if(assemblyId) {
                try {
                    for(const spec of plan.sourcePrefabs||[]) {
                        const dest=within(root,spec.path);fs.mkdirSync(path.dirname(dest),{recursive:true});
                        await timedReq('refresh-asset','db://'+outputPaths.prefabs);
                        const p=await sceneJob('serializePrefab',[assemblyId,spec.sourceId,savedPrefabs,nativePlan],'source-prefabs');
                        if(!p||p.path!==spec.path||p.sourceId!==spec.sourceId||typeof p.serialized!=='string')throw Error('Native prefab serialization differs');
                        const info=await timedReq('create-asset','db://'+p.path,p.serialized,{overwrite:false,rename:false});
                        if(!info||info.invalid)throw Error('Native prefab save failed');
                        savedPrefabs.push({sourceId:p.sourceId,path:p.path,uuid:info.uuid,nativeInitialNodes:p.nativeInitialNodes,spineUITransformReceipt:p.spineUITransformReceipt,sha256:hash(fs.readFileSync(dest))});
                    }
                    result=await sceneJob('finishAssembly',[assemblyId,savedPrefabs,nativePlan],'candidate-save');
                }finally{
                    await Editor.Message.request('scene','execute-scene-script',{name:'monkey-import',method:'releaseAssembly',args:[assemblyId]});
                }
            }
            const animationAssets=[...earlyAnimationAssets];
            for(const a of result.animationAssets||[]) {
                if(!a.path.startsWith(outputPaths.animations+'/')||!a.path.endsWith('.anim'))throw Error('Unsafe animation path');
                within(root,a.path);
                const info=await req('create-asset','db://'+a.path,a.serialized,{overwrite:false,rename:false});
                if(!info||info.invalid)throw Error('Native animation save failed');
                animationAssets.push({id:a.id,uuid:info.uuid,path:a.path});
            }
            const expectedPrefabs=new Map((plan.sourcePrefabs||[]).map(p=>[p.sourceId,p]));
            const serializedIds=new Set();
            if(!assemblyId&&(result.sourcePrefabs||[]).length!==expectedPrefabs.size)throw Error('Prefab serialization count mismatch');
            for(const p of result.sourcePrefabs||[]) {
                const spec=expectedPrefabs.get(p.sourceId);
                if(!spec||serializedIds.has(p.sourceId)||p.path!==spec.path||typeof p.serialized!=='string')throw Error('Unexpected prefab serialization');
                serializedIds.add(p.sourceId);
                const dest=within(root,p.path);
                fs.mkdirSync(path.dirname(dest),{recursive:true});
            }
            if(expectedPrefabs.size)await timedReq('refresh-asset','db://'+outputPaths.prefabs);
            await batch.map(result.sourcePrefabs||[],8,async p=>{
                execution.checkpoint('source-prefabs',savedPrefabs.length,(plan.sourcePrefabs||[]).length);
                const info=await timedReq('create-asset','db://'+p.path,p.serialized,{overwrite:false,rename:false});
                if(!info||info.invalid)throw Error('Native prefab save failed: '+p.sourceId);
                savedPrefabs.push({sourceId:p.sourceId,path:p.path,uuid:info.uuid,nativeInitialNodes:p.nativeInitialNodes,spineUITransformReceipt:p.spineUITransformReceipt,sha256:hash(fs.readFileSync(within(root,p.path)))});expectedPrefabs.delete(p.sourceId);
            });
            execution.checkpoint('candidate-save');
            const scene = await req('create-asset', 'db://'+outputPaths.scene, result.serialized, {overwrite: false, rename: false});
            if (!scene || scene.invalid) throw Error('Native scene save failed');
            // Re-load saved/imported scene through the engine asset manager, not the in-memory tree.
            execution.checkpoint('native-readback');
            const readbackPlan={...nativePlan,animationAssets,savedPrefabs,nativeInitialNodes:result.nativeInitialNodes};
            fs.mkdirSync(within(root,'Analysis/Readback'),{recursive:true});
            fs.writeFileSync(within(root,'Analysis/Readback/native-readback-context.json'),JSON.stringify({
                schemaVersion:1,sceneUuid:scene.uuid,projectUuid:project.uuid,
                sourcePlanSha256:hash(planRaw),manifestSha256:hash(manifestRaw),nativePlan:readbackPlan},null,2)+'\n',{flag:'wx'});
            const nativeReadbackContextSha256=hash(fs.readFileSync(within(root,'Analysis/Readback/native-readback-context.json')));
            const saved = await sceneJob('readSaved',[scene.uuid,readbackPlan],'native-readback');
            saved.materialBinding=materialReadback;
            saved.spriteOutlineBinding=spriteOutlineReadback;
            fs.mkdirSync(within(root,'Analysis/Readback'),{recursive:true});
            fs.writeFileSync(within(root,'Analysis/Readback/source-prefabs-readback.json'),JSON.stringify(saved,null,2)+'\n');
            saved.staticPreviews=[];
            for(const state of nativePlan.previewStates||(nativePlan.previewState?[nativePlan.previewState]:[])) {
                const statePlan={...nativePlan,savedPrefabs,previewState:state};
                const source=savedPrefabs.find(p=>p.sourceId===state.sourcePrefabId);
                if(!source)throw Error('STATIC_PREVIEW_SOURCE_MISSING');
                const body=await sceneJob('createStaticPreview',[source.uuid,statePlan],'candidate-save');
                const stem='assets/Game/Preview/States/State_'+state.stateSha256.slice(0,16);
                fs.mkdirSync(path.dirname(within(root,stem)),{recursive:true});
                await timedReq('refresh-asset','db://assets/Game/Preview');
                const prefab=await timedReq('create-asset','db://'+stem+'.prefab',body.prefabSerialized,{overwrite:false,rename:false});
                const preview=await timedReq('create-asset','db://'+stem+'.scene',body.sceneSerialized,{overwrite:false,rename:false});
                if(!prefab||!preview||prefab.invalid||preview.invalid)throw Error('STATIC_PREVIEW_SAVE_FAILED');
                saved.staticPreview=await sceneJob('readStaticPreview',[preview.uuid,statePlan],'native-readback');
                saved.staticPreview.prefabPath=stem+'.prefab';saved.staticPreview.scenePath=stem+'.scene';
                saved.staticPreview.prefabUuid=prefab.uuid;
                fs.mkdirSync(within(root,'Analysis/Readback'),{recursive:true});fs.writeFileSync(within(root,'Analysis/Readback/static-preview-attempt.json'),JSON.stringify(saved.staticPreview,null,2)+'\n');
                if(!saved.staticPreview.state.verified||(saved.staticPreview.clones||[]).some(x=>!x.verified)||(saved.staticPreview.spriteProjections&&!saved.staticPreview.spriteProjections.verified))throw Error('STATIC_PREVIEW_READBACK_FAILED');
                saved.staticPreviews.push(saved.staticPreview);
            }

            for(const p of savedPrefabs)if(p.sha256&&hash(fs.readFileSync(within(root,p.path)))!==p.sha256)throw Error('Shared native template changed: '+p.sourceId);
            const nativeFiles = [];
            function collect(relative) {
                const folder = within(root, relative);
                for (const name of fs.readdirSync(folder).sort()) {
                    const rel = relative + '/' + name; const full = within(root, rel);
                    if (fs.lstatSync(full).isDirectory()) collect(rel);
                    else nativeFiles.push({path: rel, sha256: hash(fs.readFileSync(full))});
                }
            }
            for(const folder of outputPaths.nativeRoots)if(fs.existsSync(within(root,folder)))collect(folder);
            const rb = {...saved, assets, sceneUuid:scene.uuid, creatorVersion:Editor.App.version, projectUuid:project.uuid,
                manifestSha256:hash(manifestRaw),nativeReadbackContextSha256, nativeFiles,apiTiming,codeEmission,numericCodeExercise:result.numericCodeExercise||[]};
            fs.mkdirSync(within(root,'Analysis/Readback'),{recursive:true});fs.writeFileSync(within(root,'Analysis/Readback/editor-readback.json'),JSON.stringify(rb,null,2)+'\n',{flag:'wx'});
            return {sceneUuid:scene.uuid,nodeCount:rb.nodeCount,editorValidation:'readback-recorded'};
        }
    }
};
