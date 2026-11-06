'use strict';
// Explicit CLI execution only. Ordinary project opening never imports a candidate.
const fs=require('fs');const path=require('path');const crypto=require('crypto');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
let state=null;
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function write(name,value) {
    const target=path.join(state.root,'Analysis','Readback',name),temp=target+'.tmp';fs.mkdirSync(path.dirname(target),{recursive:true});
    fs.writeFileSync(temp,JSON.stringify(value,null,2)+'\n',{mode:0o600});fs.renameSync(temp,target);
}
function checkpoint(phase,processed=0,total=1,status='running') {
    if(!state)return;
    if(state.cancelled)throw Error('NATIVE_EXECUTION_CANCELLED');
    if(Date.now()>=state.deadline || (state.methodStarted && Date.now()-state.methodStarted>=state.budgetMs))throw Error('NATIVE_BUDGET_EXHAUSTED');
    write('native-progress.json',{schemaVersion:1,phase,status,processed,total,planSha256:state.planHash,
        sourceManifestSha256:state.manifestHash,nativeResumeSupported:false,
        elapsedSeconds:state.methodStarted?(Date.now()-state.methodStarted)/1000:0,
        methodStartedUtc:state.methodStarted?new Date(state.methodStarted).toISOString():null,readiness:state.readiness||null});
}
async function start(run) {
    if(process.env.MONKEY_NATIVE_EXECUTE!=='1')return;
    if(state)throw Error('NATIVE_EXECUTION_ALREADY_STARTED');
    const root=fs.realpathSync(Editor.Project.path);
    if(root!==fs.realpathSync(process.env.MONKEY_NATIVE_PROJECT||''))throw Error('NATIVE_PROJECT_BINDING_MISMATCH');
    const manifestHash=process.env.MONKEY_NATIVE_MANIFEST||'';
    const deadline=Date.parse(process.env.MONKEY_NATIVE_DEADLINE_UTC||'');
    const budgetMs=Number(process.env.MONKEY_NATIVE_BUDGET_SECONDS)*1000;
    if(!/^[a-f0-9]{64}$/.test(manifestHash)||!Number.isFinite(deadline)||deadline<=Date.now()||!Number.isFinite(budgetMs)||budgetMs<1000||budgetMs>3600000)throw Error('NATIVE_EXECUTION_OPTIONS_INVALID');
    state={root,manifestHash,deadline,budgetMs,methodStarted:0,cancelled:false,
        planHash:hash(fs.readFileSync(path.join(__dirname,'import-plan.json')))};
    try {
        if(Editor.App.version!=='3.8.8'||hash(fs.readFileSync(path.join(root,'manifest.json')))!==manifestHash)throw Error('NATIVE_CANDIDATE_BINDING_MISMATCH');
        checkpoint('preflight');
        while(true) {
            const assetReady=await Editor.Message.request('asset-db','query-ready');
            const sceneReady=await Editor.Message.request('scene','query-is-ready');
            state.readiness={assetType:typeof assetReady,assetReady:assetReady==null?null:assetReady,sceneType:typeof sceneReady,sceneReady:sceneReady==null?null:sceneReady};
            if(![true,false,undefined,null].includes(assetReady)||![true,false,undefined,null].includes(sceneReady))throw Error('NATIVE_READINESS_SCHEMA_INVALID: '+JSON.stringify(state.readiness).slice(0,512));
            if(assetReady===true&&sceneReady===true)break;
            checkpoint('preflight');await delay(500);
        }
        state.methodStarted=Date.now();checkpoint('preflight',1,1);
        let timer;
        try {
            await Promise.race([run(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('NATIVE_BUDGET_EXHAUSTED')),Math.min(budgetMs,deadline-Date.now()));})]);
        } finally {clearTimeout(timer);}
        checkpoint('complete',1,1,'completed');
    } catch(error) {
        const message=String(error&&error.message||error).slice(0,4096);
        write('native-error.json',{schemaVersion:1,sourceManifestSha256:manifestHash,planSha256:state.planHash,message,atUtc:new Date().toISOString()});
        write('native-progress.json',{schemaVersion:1,phase:'complete',status:message==='NATIVE_BUDGET_EXHAUSTED'?'budget_exhausted':'failed',processed:0,total:1,
            planSha256:state.planHash,sourceManifestSha256:manifestHash,nativeResumeSupported:false,elapsedSeconds:state.methodStarted?(Date.now()-state.methodStarted)/1000:0});
        console.error('MONKEY_NATIVE_EXECUTION_FAILED: '+message);
    }
}
function deadlineMs(){return state?Math.min(state.deadline,state.methodStarted+state.budgetMs):null;}
function stop(){if(state)state.cancelled=true;}
module.exports={start,stop,checkpoint,deadlineMs};
