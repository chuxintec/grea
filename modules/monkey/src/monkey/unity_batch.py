"""Serial whole-input inspection and a single merged TypeTree code handoff."""
import copy
import subprocess
from pathlib import Path
from .io import safe, read, load, sha, write_json
from .sources.compiled import fail
from .unity_parse_limits import parse_limits as resolve_limits,reader_fingerprint
from .unity_payloads import load_typed,validate_payloads,copy_payloads


def inspect_all(rows, provider_python, output, schema_pool, budget, parse_limits=None):
    limits=resolve_limits(parse_limits)
    out=safe(output);stage=out/'BatchInspection';stage.mkdir()
    job=dict(schemaVersion=1,schemaPool=schema_pool,files=[],parseLimits=limits,readerContractSha256=reader_fingerprint())
    for index,row in enumerate(rows):
        job['files'].append(dict(row,inspection=str(out/('SourceInspection' if index==0 else 'DependencyInspection-'+str(index-1)))))
    write_json(stage/'job.json',job)
    worker=Path(__file__).parent/'sources/unity_worker.py'
    result=stage/'batch.json';receipt=dict(status='started',workerSha256=reader_fingerprint(),parseLimits=limits,containers=len(rows),processExited=False)
    with (stage/'provider.log').open('wb')as log:
        p=subprocess.Popen([str(provider_python),'-I','-B',str(worker),'--inspect-batch',str(stage/'job.json'),str(result)],cwd=stage,stdout=log,stderr=subprocess.STDOUT)
        receipt['pid']=p.pid;write_json(stage/'execution.json',receipt)
        try:p.wait(timeout=budget)
        except subprocess.TimeoutExpired:
            p.terminate()
            try:p.wait(timeout=15)
            except subprocess.TimeoutExpired:pass
        receipt.update(processExited=p.poll()is not None,exitCode=p.poll())
    if p.poll()!=0:
        receipt['status']='failed' if receipt['processExited']else'pending_child_exit';write_json(stage/'execution.json',receipt)
        fail('UNITY_BATCH_INSPECTION_FAILED',str(stage),'Inspect owned provider.log; no resource input silently skipped')
    body=load(read(result,max_bytes=128*1024**2),max_nodes=16_000_000,max_depth=128)
    if len(body['files'])!=len(rows):fail('UNITY_BATCH_COUNT',str(stage),'Not every explicit container was inspected')
    receipts=[]
    for expected,record in zip(rows,body['files']):
        r=record['receipt']
        if r.get('status')not in ('partial','inspected')or not r.get('sourceUnchanged')or r.get('source',{}).get('sha256')!=expected['sha256']:
            fail('UNITY_BATCH_SOURCE',record['path'],'A container failed inspection or changed; see batch.json')
        typed=Path(record['inspection'])/'typed-objects.json'
        if sha(read(typed,max_bytes=128*1024**2))!=r['typedObjectsSha256']:fail('UNITY_BATCH_TYPED_CHANGED',str(typed),'Typed snapshot differs')
        document=load_typed(typed);validate_payloads(typed.parent,document)
        if r.get('parseLimits')!=limits or document.get('parseLimits')!=limits:fail('UNITY_BATCH_LIMITS',str(typed),'Parse limits differ')
        receipts.append((Path(record['path']),r))
    receipt.update(status='inspected',schemaBundlesRead=body['schemaBundlesRead'],containersInspected=body['containersInspected'])
    write_json(stage/'execution.json',receipt)
    return receipts


def merged_model_inputs(inspections, output, manifest_sha):
    """Resolve MonoScript across the entire frozen serialized-file namespace."""
    out=safe(output);out.mkdir();files=[];objects=[];names={};embedded={};borrowed={};aliases=[];sources=[]
    for index,(path,receipt)in enumerate(inspections):
        stage=out.parent/('SourceInspection'if index==0 else'DependencyInspection-'+str(index-1))
        data=load_typed(stage/'typed-objects.json')
        validate_payloads(stage,data)
        mapping={};skipped=set();sources.append(receipt['source'])
        for f in data['files']:
            name=f['name'];digest=f.get('serializedFileSha256')
            if not digest:fail('UNITY_BATCH_FILE_IDENTITY',name,'Serialized-file byte hash required')
            if name in names:
                old=names[name]
                if old['serializedFileSha256']!=digest:fail('UNITY_BATCH_FILE_AMBIGUOUS',name,'Same serialized name has different bytes')
                mapping[f['id']]=old['id'];skipped.add(f['id']);aliases.append(dict(source=receipt['source']['sha256'],file=name,equivalentTo=old['id']));continue
            row=copy.deepcopy(f);row['id']=str(len(files));row['containerSha256']=receipt['source']['sha256'];mapping[f['id']]=row['id'];files.append(row);names[name]=row
        for o in data['objects']:
            if o['file']in skipped or o['type']not in ('MonoBehaviour','MonoScript'):continue
            row=copy.deepcopy(o);row['file']=mapping[o['file']]
            # Code declaration generation needs identity headers, not large instance value arrays.
            # Full typed values remain frozen in all601 original resource shards.
            wanted=('m_Script','m_GameObject')if o['type']=='MonoBehaviour'else('m_ClassName','m_Namespace','m_AssemblyName')
            if isinstance(row.get('data'),dict):row['data']={k:row['data'][k]for k in wanted if k in row['data']}
            objects.append(row)
        for field,target in [('embeddedSchemas',embedded),('borrowedSchemas',borrowed)]:
            for key,value in data.get(field,{}).items():
                if key in target and target[key]!=value:fail('UNITY_BATCH_SCHEMA_AMBIGUOUS',key,'Schema content differs')
                target[key]=value
    merged=dict(schemaVersion=1,sourceFamily='unity',source=dict(sha256=manifest_sha),files=files,objects=objects,
                embeddedSchemas=embedded,borrowedSchemas=borrowed,sources=sources,aliases=aliases,sourceCodeExecuted=False)
    write_json(out/'typed-objects.json',merged)
    write_json(out/'inspection.json',dict(typedObjectsSha256=sha(read(out/'typed-objects.json',max_bytes=128*1024**2))))
    return dict(scope='MonoBehaviour/MonoScript code subset; complete resource shards retained separately',serializedFiles=len(files),objects=len(objects),byteIdenticalFileAliases=len(aliases),containers=len(sources))


def scope_rows(source, pool):
    source=safe(source);raw=read(source,max_bytes=128*1024**2);primary=dict(path=str(source),bytes=len(raw),sha256=sha(raw));rows=[primary];seen={primary['sha256']};aliases=[]
    for row in pool['files']:
        if row['sha256']in seen:aliases.append(dict(row,disposition='byte-identical-container-alias'))
        else:rows.append(row);seen.add(row['sha256'])
    return rows,aliases


def inspect_set(source,manifest,provider_python,output,budget=600,schema_manifest=None,parse_limits=None):
    from .unity_schemas import frozen_pool
    from .io import new_output
    limits=resolve_limits(parse_limits)
    pool=frozen_pool(manifest);schemas=frozen_pool(schema_manifest)if schema_manifest else pool
    rows,aliases=scope_rows(source,pool);out=new_output(output,[source,safe(manifest),*[Path(r['path'])for r in pool['files']]])
    write_json(out/'all-inputs.json',dict(schemaVersion=1,files=rows,aliases=aliases,manifestSha256=pool['sourceManifestSha256']))
    result=inspect_all(rows,provider_python,out,schemas,budget,limits)
    summary=dict(containers=len(result),parsed=sum(r['summary']['parsed']for _,r in result),unparsed=sum(r['summary']['unparsed']for _,r in result),
                 externalTextureTokens=sum(r['summary'].get('externalTextureTokens',0)for _,r in result),invalidInlineTextures=sum(r['summary'].get('invalidInlineTextures',0)for _,r in result))
    receipt=dict(schemaVersion=1,status='partial'if summary['unparsed']else'inspected',summary=summary,sourceCodeExecuted=False,native='not_run',scope='all explicitly frozen unique containers')
    write_json(out/'inspection-set.json',receipt);return receipt


def reuse_inspections(rows, previous, output, schema_pool, parse_limits=None):
    """Verify a complete batch receipt and copy snapshots, never reparse source bodies."""
    previous=safe(previous);out=safe(output);limits=resolve_limits(parse_limits)
    job=load(read(previous/'BatchInspection/job.json'));execution=load(read(previous/'BatchInspection/execution.json'))
    if execution.get('status')!='inspected'or execution.get('workerSha256')!=reader_fingerprint():
        fail('UNITY_BATCH_REUSE_WORKER',str(previous),'Successful same-worker snapshot required')
    if job.get('parseLimits')!=limits or job.get('readerContractSha256')!=reader_fingerprint():fail('UNITY_BATCH_REUSE_LIMITS',str(previous),'Reader policy differs; inspect afresh')
    if job.get('schemaPool')!=schema_pool or len(job.get('files',[]))!=len(rows):fail('UNITY_BATCH_REUSE_INPUT',str(previous),'Exact schema/input set differs')
    result=[];records=[]
    for index,(expected,old)in enumerate(zip(rows,job['files'])):
        if any(old.get(k)!=expected[k]for k in ('path','bytes','sha256')):fail('UNITY_BATCH_REUSE_INPUT',str(previous),'Container identity differs')
        raw=read(Path(expected['path']),max_bytes=128*1024**2)
        if len(raw)!=expected['bytes']or sha(raw)!=expected['sha256']:fail('UNITY_BATCH_REUSE_INPUT',expected['path'],'Original changed')
        name='SourceInspection'if index==0 else'DependencyInspection-'+str(index-1);stage=previous/name
        receipt=load(read(stage/'inspection.json'));body=read(stage/'typed-objects.json',max_bytes=128*1024**2)
        if receipt.get('status')not in ('inspected','partial')or not receipt.get('sourceUnchanged')or sha(body)!=receipt.get('typedObjectsSha256'):
            fail('UNITY_BATCH_REUSE_TYPED',str(stage),'Receipt or snapshot changed')
        document=load_typed(stage/'typed-objects.json')
        if document.get('parseLimits')!=limits or receipt.get('parseLimits')!=limits:fail('UNITY_BATCH_REUSE_LIMITS',str(stage),'Snapshot limits differ')
        validate_payloads(stage,document)
        (out/name).mkdir();(out/name/'typed-objects.json').write_bytes(body);write_json(out/name/'inspection.json',receipt)
        copy_payloads(stage,out/name,document)
        result.append((Path(expected['path']),receipt));records.append(dict(path=expected['path'],inspection=str(out/name),receipt=receipt))
    stage=out/'BatchInspection';stage.mkdir();write_json(stage/'execution.json',dict(execution,reusedFrom=str(previous)))
    write_json(stage/'job.json',dict(job,files=[dict(row,inspection=str(out/('SourceInspection'if i==0 else'DependencyInspection-'+str(i-1))))for i,row in enumerate(rows)]))
    write_json(stage/'batch.json',dict(schemaVersion=1,files=records,schemaBundlesRead=execution.get('schemaBundlesRead'),containersInspected=len(rows),sourceCodeExecuted=False))
    return result
