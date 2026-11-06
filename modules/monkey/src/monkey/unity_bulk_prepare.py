"""Resumable whole-pool texture preparation, separate from provider export timeboxes."""
import re,subprocess
from pathlib import Path
from .io import safe,read,load,sha,new_output,write_json
from .sources.compiled import fail
from .providers.assetripper import fingerprint
from .unity_parse_limits import reader_fingerprint
from .unity_payloads import load_typed,validate_payloads


def prepare(inspection,texture_cache,capture,provider_python,output,budget=1200,resume=False):
    if type(budget)is not int or not 30<=budget<=1500:fail('UNITY_BULK_PREPARE_BUDGET','$','Expected30..1500 seconds')
    old=safe(inspection);manifest=safe(texture_cache);cap=safe(capture);requested=Path(provider_python).absolute();python=safe(requested.resolve(strict=True));out=safe(output)
    summary=load(read(old/'BatchInspection/execution.json'));batch=load(read(old/'BatchInspection/batch.json',max_bytes=128*1024**2),max_nodes=16_000_000,max_depth=128)
    if summary.get('status')!='inspected'or summary.get('workerSha256')!=reader_fingerprint():fail('UNITY_BULK_INSPECTION_DRIFT',str(old),'Frozen same-reader successful batch required; no reparse fallback')
    if not 1<=len(batch.get('files',[]))<=2000:fail('UNITY_BULK_CONTAINER_COUNT',str(old),'Expected1..2000 explicit inspected containers')
    sources=[]
    for index,row in enumerate(batch['files']):
        receipt=row['receipt'];path=safe(row['path']);typed=old/('SourceInspection'if index==0 else'DependencyInspection-'+str(index-1))/'typed-objects.json'
        if fingerprint(typed)!=receipt['typedObjectsSha256']or fingerprint(path)!=receipt['source']['sha256']or not receipt.get('sourceUnchanged'):fail('UNITY_BULK_INSPECTION_DRIFT',str(path),'Frozen source/typed bytes changed')
        validate_payloads(typed.parent,load_typed(typed))
        sources.append(dict(index=index,path=str(path),bytes=path.stat().st_size,sha256=receipt['source']['sha256'],typedSha256=receipt['typedObjectsSha256'],needsTextures=bool(receipt['summary'].get('externalTextureTokens')),invalidInline=receipt['summary'].get('invalidInlineTextures',0)))
    pool=load(read(manifest));cache=[];seen=set();total=0
    if pool.get('schemaVersion')!=1 or not isinstance(pool.get('files'),list)or not 1<=len(pool['files'])<=10000:fail('UNITY_BULK_TEXTURE_POOL',str(manifest),'Explicit <=10000 texture pool required')
    for row in pool['files']:
        logical=row['logicalPath'];path=safe(manifest.parent/row['path'])
        if not re.fullmatch(r'Assets/Textures/astc/[0-9]+/[^/\\\x00]+\.txt',logical)or logical in seen or type(row.get('bytes'))is not int or not 0<row['bytes']<=128*1024**2 or not re.fullmatch('[0-9a-f]{64}',row.get('sha256','')):fail('UNITY_BULK_TEXTURE_IDENTITY',logical,'Unique exact cache key/size/SHA256 required')
        seen.add(logical);total+=row['bytes'];cache.append(dict(row,path=str(path)))
    if total>2*1024**3:fail('UNITY_BULK_TEXTURE_BYTES','$','Pool exceeds2GiB')
    capture_raw=read(cap);captured=load(capture_raw);missing=[]
    capture_job=load(read(cap.parent/'capture-job.json'))
    if capture_job.get('inspectionManifestSha256')!=fingerprint(old/'all-inputs.json')or captured.get('poolEntries')!=len(cache):fail('UNITY_BULK_CAPTURE_DRIFT',str(cap),'Capture must bind this inspection and exact acquired pool')
    if captured.get('requestedKeys')!=captured.get('capturedKeys',0)+len(captured.get('failures',[])):fail('UNITY_BULK_CAPTURE_PENDING',str(cap),'Every requested key must have terminal captured/404 disposition')
    for row in captured.get('failures',[]):
        logical=row['logicalPath']
        if row.get('status')!='failed'or row.get('reason')!='HTTPError: HTTP Error 404: Not Found'or logical in seen or logical in missing:fail('UNITY_BULK_CAPTURE_FAILURE',logical,'Only exact terminal source-key HTTP404 can be quarantined')
        missing.append(logical)
    worker=Path(__file__).parent/'sources/unity_hydrate_worker.py'
    definition=dict(schemaVersion=1,sources=sources,cache=cache,missingKeys=missing,inspection=str(old),inspectionManifestSha256=fingerprint(old/'all-inputs.json'),cacheManifestSha256=fingerprint(manifest),captureSha256=sha(capture_raw),workerSha256=fingerprint(worker),sourceWorkerSha256=summary['workerSha256'],pixelsFabricated=False,sourceCodeExecuted=False)
    if resume:
        if load(read(out/'prepare-job.json'))!=definition:fail('UNITY_BULK_PREPARE_DRIFT',str(out),'Resume only exact same immutable job')
    else:
        out=new_output(out,[old,manifest,cap,python.parent,*[r['path']for r in sources],*[r['path']for r in cache]]);write_json(out/'prepare-job.json',definition)
    receipt=dict(schemaVersion=1,status='started',budgetSeconds=budget,jobSha256=fingerprint(out/'prepare-job.json'),processExited=False,resume=resume)
    with (out/'provider.log').open('ab')as log:
        (out/'provider.log').chmod(0o600)
        child=subprocess.Popen([str(requested),'-I','-B',str(worker),str(out/'prepare-job.json'),str(budget-15)],cwd=out,stdout=log,stderr=subprocess.STDOUT)
        receipt['pid']=child.pid;write_json(out/'execution.json',receipt)
        try:child.wait(timeout=budget)
        except subprocess.TimeoutExpired:
            child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:pass
        receipt.update(processExited=child.poll()is not None,exitCode=child.poll(),status='partial')
    result=out/'prepared.json'
    if child.poll()==0 and result.exists():
        body=load(read(result));receipt.update(status=body['status'],containers=body['containers'],prepared=body['prepared'],missingTextureObjects=body['missingTextureObjects'],hydratedTextures=body['hydratedTextures'])
    write_json(out/'execution.json',receipt);return dict(receipt,report=str(result))


def prepared_inputs(directory):
    root=safe(directory);job_raw=read(root/'prepare-job.json');job=load(job_raw);body=load(read(root/'prepared.json',max_bytes=128*1024**2),max_nodes=16_000_000,max_depth=128)
    if body.get('status')!='prepared'or body.get('jobSha256')!=sha(job_raw)or body.get('prepared')!=len(job['sources'])or len(body.get('rows',[]))!=len(job['sources']):fail('UNITY_BULK_PREPARED_INCOMPLETE',str(root),'Every frozen container must have a durable preparation disposition')
    paths=[]
    for expected,row in zip(job['sources'],body['rows']):
        if row.get('index')!=expected['index']or row.get('source')!=expected or fingerprint(safe(expected['path']))!=expected['sha256']:fail('UNITY_BULK_PREPARED_CHANGED',str(root),'Frozen source/row changed')
        path=safe(row['derived'])if row.get('derived')else safe(expected['path'])
        if row.get('derived')and (not path.is_relative_to(root/'containers')or fingerprint(path)!=row['derivedSha256']):fail('UNITY_BULK_DERIVED_CHANGED',str(path),'Completed derived container changed')
        paths.append(path)
    return job,body,paths


def export_prepared(directory,asset_ripper,output,budget=1200,deadline_utc=None,window_end_utc=None):
    if not 30<=budget<=1500:fail('UNITY_BULK_EXPORT_BUDGET','$','Separate provider stage must be30..1500 seconds')
    from .providers.assetripper import export
    from datetime import timedelta
    from .native import now,utc
    deadline=end=None
    if deadline_utc or window_end_utc:
        if not deadline_utc or not window_end_utc:raise ValueError('Both internal and outer deadlines required')
        deadline,end=utc(deadline_utc),utc(window_end_utc)
        if not now()<deadline<=end-timedelta(seconds=120)or end>now()+timedelta(minutes=30):raise ValueError('Fresh <=30 minute outer window and >=120 second cleanup margin required')
    job,body,paths=prepared_inputs(directory)
    effective=min(budget,int((deadline-now()).total_seconds())-45)if deadline else budget
    if effective<30:raise ValueError('Not enough time remains before the internal deadline')
    result=export(paths[0],asset_ripper,output,effective,dependencies=paths[1:],bulk=True)
    write_json(safe(output)/'bulk-export-binding.json',dict(schemaVersion=1,preparedJobSha256=fingerprint(safe(directory)/'prepare-job.json'),preparedSha256=fingerprint(safe(directory)/'prepared.json'),deadlineUtc=deadline_utc,windowEndUtc=window_end_utc,sourceContainers=len(paths),hydratedTextures=body['hydratedTextures'],missingTextureObjects=body['missingTextureObjects'],originalsRetained=True,sourceCodeExecuted=False))
    return result
