'use strict';
// Editor-only task state. Long native work must not hold a 30-second Scene RPC.
let current=null,sequence=0;
const phases=new Set(['textures','materials','hierarchy','components','source-prefabs','candidate-save','native-readback']);
function begin(method,args,handlers) {
    const arity={prepareRetainedBuiltin:1,prepareStaticAnimationAssets:1,prepareStaticTimeMaterial:2,readStaticTimeMaterial:2,prepareOutlineMaterial:1,readOutlineMaterial:1,createStaticPreview:2,readStaticPreview:2,assemble:1,readSaved:2,serializePrefab:4,finishAssembly:3,prepareMaterial:1,readMaterial:1},planIndex={prepareRetainedBuiltin:0,prepareStaticAnimationAssets:0,prepareStaticTimeMaterial:0,readStaticTimeMaterial:0,prepareOutlineMaterial:0,readOutlineMaterial:0,createStaticPreview:1,readStaticPreview:1,assemble:0,readSaved:1,serializePrefab:3,finishAssembly:2,prepareMaterial:0,readMaterial:0};
    if(!Object.hasOwn(arity,method)||!Array.isArray(args)||args.length!==arity[method]||typeof handlers[method]!=='function')throw Error('NATIVE_JOB_METHOD_INVALID');
    if(current)throw Error('NATIVE_JOB_ALREADY_EXISTS');
    const plan=args[planIndex[method]],deadline=plan&&plan.nativeDeadlineMs!=null?plan.nativeDeadlineMs:Date.now()+1200000;
    if(!Number.isFinite(deadline)||deadline<=Date.now())throw Error('NATIVE_BUDGET_EXHAUSTED');
    const job=current={id:String(++sequence)+'-'+Date.now(),method,deadline,status:'running',phase:method==='assemble'?'hierarchy':'native-readback',processed:0,total:1};
    Promise.resolve().then(()=>handlers[method](...args)).then(result=>{
        if(job.status==='running'){job.result=result;job.status='completed';}
    },error=>{if(job.status==='running'){job.status='failed';job.error=String(error&&error.message||error).split('\n')[0].slice(0,16*1024);}});
    return {jobId:job.id};
}
function checked(id) {
    if(!current||id!==current.id)throw Error('NATIVE_JOB_ID_MISMATCH');
    if(current.status==='running'&&Date.now()>=current.deadline){current.status='failed';current.error='NATIVE_BUDGET_EXHAUSTED';}
    return current;
}
function status(id) {
    const j=checked(id);return {jobId:j.id,status:j.status,phase:j.phase,processed:j.processed,total:j.total,error:j.error||null};
}
function take(id) {
    const j=checked(id);
    if(j.status==='running')throw Error('NATIVE_JOB_NOT_COMPLETE');
    if(j.status==='failed')throw Error(j.error);
    const result=j.result;current=null;return result;
}
function progress(phase,processed,total) {
    if(!current)return;
    const j=checked(current.id);
    if(j.status!=='running')throw Error(j.error||'NATIVE_JOB_STOPPED');
    if(!phases.has(phase)||!Number.isSafeInteger(processed)||!Number.isSafeInteger(total)||processed<0||processed>total||total>1000000)throw Error('NATIVE_JOB_PROGRESS_INVALID');
    Object.assign(j,{phase,processed,total});
}
module.exports={begin,status,take,progress};
