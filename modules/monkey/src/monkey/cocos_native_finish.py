"""Plan one bounded incremental source-scene/font finish in an existing owned copy."""
from pathlib import Path
from .io import safe,inside,read,load,sha,new_output,write_json
from .sources.compiled import fail
from .layout.standard import find_analysis,analysis_rel,find_output_paths


def prepare(candidate,output,excluded=()):
    root=safe(candidate);out=new_output(output,[root]);locations=load(read(find_output_paths(root)));plan_path=inside(root,locations['plan']);plan=load(read(plan_path,max_bytes=128*1024**2),max_nodes=16_000_000,max_depth=128)
    rb_path=find_analysis(root,'editor-readback.json');raw=read(rb_path,max_bytes=128*1024**2);rb=load(raw,max_nodes=16_000_000,max_depth=128)
    if not rb.get('sceneReopened')or rb.get('missingScripts')!=0:fail('BULK_FINISH_BASE',str(root),'Require existing native saved/reopened source candidate')
    structured=load(read(find_analysis(root,'structured-objects.json'),max_bytes=128*1024**2),max_nodes=16_000_000,max_depth=128)
    scenes=[]
    for asset in structured['objects']:
        if asset.get('kind')!='cc.SceneAsset':continue
        sid=asset['sourceId'];nodes=[n for n in plan['nodes']if n['sourceId'].split('#')[0]==sid];roots=[n for n in nodes if not n.get('parent')]
        if len(roots)!=1:fail('BULK_SCENE_ROOT',sid,'Exactly one source root required')
        name=Path(asset['decodedEvidence']).stem
        if not name or any(x in name for x in '/\\\x00:'):fail('BULK_SCENE_NAME',sid,'Unsafe source scene name')
        path=(Path(locations['scene']).parent/'Sources'/sid.split(':')[0]/(name+'.unity')).as_posix()
        scenes.append(dict(sourceId=sid,root=roots[0]['sourceId'],nodes=[n['sourceId']for n in nodes],nodeCount=len(nodes),path=path,
                           status='excluded'if sid in excluded else'export',reason='Product explicitly excludes mini-game Scene; original decoded/source bytes retained'if sid in excluded else''))
    bad=[];labels={x['sourceId']:x for x in rb['labels']};fonts={x['id']:x for x in rb['fonts']}
    for c in plan['components']:
        if c.get('type')!='cc.Label'or not c.get('convertible'):continue
        actual=labels.get(c['sourceId']);font=fonts.get(c.get('font'))
        if actual and font and c.get('overflow')==2 and actual['fontGuid']==font['guid']and actual['text']==c['text']and actual['allCharactersPresent']and abs(actual['fontSize']-c['fontSize'])>.00001:bad.append(c['sourceId'])
    spec=dict(inputPlanSha256=sha(read(plan_path,max_bytes=128*1024**2)),candidatePrefabSha256=sha(read(inside(root,locations['prefab']),max_bytes=128*1024**2)),priorReadbackSha256=sha(raw),scenes=scenes,fontSourceIds=bad,budgetSeconds=600,deadlineUtc='set-at-execution-only')
    write_json(out/'bulk-finish-plan.json',spec);helper=Path(__file__).parent/'targets/UnityBulkFinish.cs';(out/'UnityBulkFinish.cs').write_bytes(read(helper))
    write_json(out/'preparation.json',dict(schemaVersion=1,source=str(root),sourceManifestSha256=sha(read(root/'manifest.json',max_bytes=128*1024**2)),planSha256=sha(read(out/'bulk-finish-plan.json')),helperSha256=sha(read(helper)),sourceScenes=len(scenes),exportScenes=sum(s['status']=='export'for s in scenes),fontCases=len(bad),editor='not_run'))
    return dict(status='prepared',sourceScenes=[{k:v for k,v in scene.items()if k!='nodes'}for scene in scenes],fontCases=len(bad),report=str(out/'preparation.json'))


def validated_preparation(candidate,preparation,expected_manifest):
    root=safe(candidate);prepared=safe(preparation);receipt=load(read(prepared/'preparation.json'))
    if sha(read(root/'manifest.json',max_bytes=128*1024**2))!=expected_manifest or receipt.get('sourceManifestSha256')!=expected_manifest or receipt.get('source')!=str(root):
        fail('BULK_FINISH_SOURCE_CHANGED',str(root),'Exact prepared candidate manifest required')
    raw=read(prepared/'bulk-finish-plan.json');helper=read(prepared/'UnityBulkFinish.cs')
    if sha(raw)!=receipt.get('planSha256')or sha(helper)!=receipt.get('helperSha256')or sha(helper)!=sha(read(Path(__file__).parent/'targets/UnityBulkFinish.cs')):
        fail('BULK_FINISH_PREPARATION_CHANGED',str(prepared),'Prepared plan/helper differs from frozen current implementation')
    plan=load(raw);locations=load(read(find_output_paths(root)))
    for path,key in [(locations['plan'],'inputPlanSha256'),(locations['prefab'],'candidatePrefabSha256'),(analysis_rel(root,'editor-readback.json'),'priorReadbackSha256')]:
        if sha(read(inside(root,path),max_bytes=128*1024**2))!=plan[key]:fail('BULK_FINISH_INPUT_CHANGED',path,'Prepared native input changed')
    return root,plan,helper,locations


def execute(candidate,preparation,output,editor,expected_manifest,budget_seconds,deadline_utc,window_end_utc,execute=False,previous_execution=None):
    """Explicit in-place finish of an owned native copy; no clone or full importer."""
    import os,signal,subprocess,threading,time
    from datetime import timedelta
    from .native import now,utc,stamp,redact_log
    if type(budget_seconds)is not int or not 1<=budget_seconds<=1500:raise ValueError('Method budget must be 1..1500 seconds')
    deadline,end=utc(deadline_utc),utc(window_end_utc)
    if not now()<deadline<=end-timedelta(seconds=120)or end>now()+timedelta(minutes=30):raise ValueError('Fresh <=30 minute outer window and >=120 second cleanup margin required')
    if execute and threading.current_thread()is not threading.main_thread():raise ValueError('Execution requires CLI main thread')
    executable=safe(editor)
    if executable.name not in ('Unity','Unity.exe')or not executable.is_file()or not os.access(executable,os.X_OK):fail('BULK_FINISH_EDITOR',str(executable),'Explicit installed Editor executable required')
    root,plan,helper,locations=validated_preparation(candidate,preparation,expected_manifest)
    helper_path=inside(root,(Path(locations['plan']).parent/'UnityBulkFinish.cs').as_posix());plan_path=find_analysis(root,'bulk-finish-plan.json')
    previous_files={}
    if (root/'Temp/UnityLockfile').exists():fail('BULK_FINISH_EXISTING_STATE',str(root),'Never remove an Editor lock')
    if previous_execution:
        previous=safe(previous_execution);old=load(read(previous/'execution-result.json'));old_spec=load(read(previous/'execution-plan.json'))
        failed=read(previous/'bulk-finish-readback.json');old_rb=load(failed)
        if old.get('project')!=str(root)or old.get('processExited')is not True or old.get('status')!='partial'or old.get('historicalManifestUnchanged')is not True or old.get('nativeStatus')not in ('failed','partial')or any(r.get('savedReopened')or r.get('status')not in ('failed','excluded')for r in old_rb.get('scenes',[]))or any(r.get('status')!='configuration-verified'or r.get('prefabUnchanged')is not True for r in old_rb.get('fonts',[]))or old.get('sourceManifestSha256')!=expected_manifest:
            fail('BULK_FINISH_PREVIOUS_STATE',str(previous),'Only an exited, unchanged owned failure with no saved source Scene may be resumed')
        old_preparation=safe(old_spec['preparation']);old_plan=load(read(old_preparation/'bulk-finish-plan.json'));old_plan.update(budgetSeconds=old_spec['budgetSeconds'],deadlineUtc=old_spec['deadlineUtc'])
        if sha(read(helper_path))!=old_spec['helperSha256']or load(read(plan_path))!=old_plan or read(find_analysis(root,'bulk-finish-readback.json'))!=failed:
            fail('BULK_FINISH_PREVIOUS_CHANGED',str(root),'Prior helper/plan/failure evidence changed; no overwrite')
        previous_files={helper_path:read(helper_path),plan_path:read(plan_path),find_analysis(root,'bulk-finish-readback.json'):failed}
    elif any(p.exists()for p in [helper_path,plan_path,find_analysis(root,'bulk-finish-readback.json')]):fail('BULK_FINISH_EXISTING_STATE',str(root),'Explicit exact previous execution required; unknown files never overwritten')
    for row in plan['scenes']:
        if row['status']=='export'and inside(root,row['path']).exists():fail('BULK_FINISH_EXISTING_SCENE',row['path'],'Source Scene already exists')
    out=new_output(output,[root,safe(preparation),executable]);plan.update(budgetSeconds=budget_seconds,deadlineUtc=stamp(deadline))
    spec=dict(schemaVersion=1,status='planned',project=str(root),preparation=str(safe(preparation)),sourceManifestSha256=expected_manifest,
              planSha256=sha(read(safe(preparation)/'bulk-finish-plan.json')),helperSha256=sha(helper),editor=str(executable),method='MonkeyImporter.FinishBulkBatch',
              deadlineUtc=stamp(deadline),windowEndUtc=stamp(end),budgetSeconds=budget_seconds,fullReimport=False,processStarted=False,processExited=True)
    write_json(out/'execution-plan.json',spec)
    if not execute:return dict(spec,report=str(out/'execution-plan.json'))
    if previous_files:
        archive=out/'PreviousLayer';archive.mkdir()
        for path,body in previous_files.items():
            (archive/path.name).write_bytes(body)
        meta=helper_path.with_suffix('.cs.meta')
        if meta.exists():(archive/meta.name).write_bytes(read(meta))
        write_json(out/'previous-layer.json',dict(previousExecution=str(safe(previous_execution)),files=[dict(path=str(p.relative_to(root)),sha256=sha(body))for p,body in previous_files.items()]))
        (find_analysis(root,'bulk-finish-readback.json')).unlink()
    helper_path.write_bytes(helper);write_json(plan_path,plan)
    # Source manifest/readback remain immutable historical records; new files form an additive layer.
    result=dict(spec,status='running',startedUtc=stamp(now()));child=None;interrupted=[];handlers={}
    def signal_handler(number,frame):interrupted.append(number)
    try:
        for number in (signal.SIGINT,signal.SIGTERM):handlers[number]=signal.getsignal(number);signal.signal(number,signal_handler)
        with (out/'console.log').open('wb')as log:
            (out/'console.log').chmod(0o600);(out/'editor.log').touch(mode=0o600)
            child=subprocess.Popen([str(executable),'-batchmode','-projectPath',str(root),'-executeMethod',spec['method'],'-logFile',str(out/'editor.log')],cwd=root,stdout=log,stderr=subprocess.STDOUT)
            result.update(processStarted=True,processExited=False,pid=child.pid);write_json(out/'execution-result.json',result)
            while child.poll()is None:
                if interrupted or now()>=deadline:
                    result['stopReason']='operator-interrupted'if interrupted else'internal-deadline';child.terminate();break
                time.sleep(.5)
            if child.poll()is None:
                try:child.wait(timeout=max(.01,min(60,(end-now()).total_seconds())))
                except subprocess.TimeoutExpired:pass
    except (OSError,KeyboardInterrupt)as error:result['error']=type(error).__name__
    finally:
        if child is not None and child.poll()is None:
            child.terminate()
            try:child.wait(timeout=max(.01,min(30,(end-now()).total_seconds())))
            except subprocess.TimeoutExpired:pass
        for number,handler in handlers.items():signal.signal(number,handler)
        result.update(processExited=child is None or child.poll()is not None,exitCode=child.poll()if child else None,endedUtc=stamp(now()),status='partial')
        result['redactedLog']=redact_log(out/'editor.log')
        result['historicalManifestUnchanged']=sha(read(root/'manifest.json',max_bytes=128*1024**2))==expected_manifest
        readback=find_analysis(root,'bulk-finish-readback.json')
        if readback.exists()and result['processExited']:
            body=load(read(readback));(out/'bulk-finish-readback.json').write_bytes(read(readback))
            result.update(nativeStatus=body.get('status'),scenes=[{k:r.get(k)for k in ('sourceId','status','sourceNodes','savedReopened','missingScripts','reason')}for r in body.get('scenes',[])],fontCases=len(body.get('fonts',[])))
            if body.get('status')=='completed'and result.get('exitCode')==0 and result['historicalManifestUnchanged']:result['status']='completed'
        write_json(out/'execution-result.json',result)
    return dict(result,report=str(out/'execution-result.json'))


def font_evidence(root,instruction,readback_path):
    """Accept an additive native proof only when frozen source/Prefab hashes match."""
    path=find_analysis(root,'bulk-finish-readback.json')
    if not path.is_file():return {}
    body=load(read(path))
    if body.get('status')!='completed':return {}
    locations=load(read(find_output_paths(root)))
    if body.get('status')!='completed'or body.get('priorReadbackSha256')!=sha(read(readback_path,max_bytes=128*1024**2))or body.get('inputPlanSha256')!=sha(read(inside(root,locations['plan']),max_bytes=128*1024**2))or body.get('candidatePrefabSha256')!=sha(read(inside(root,locations['prefab']),max_bytes=128*1024**2)):
        fail('BULK_FONT_EVIDENCE_CHANGED',str(path),'Successful source/plan-bound native incremental proof required')
    prefabs={p['sourceId']:p for p in instruction.get('sourcePrefabs',[])};result={}
    for row in body.get('fonts',[]):
        source=row['sourceId'];prefab=prefabs.get(source.split('#')[0],{})
        if source in result or row.get('status')!='configuration-verified'or row.get('prefabUnchanged')is not True or row.get('prefabPath')!=prefab.get('path')or row.get('prefabSha256')!=sha(read(inside(root,prefab['path']),max_bytes=128*1024**2)):
            fail('BULK_FONT_PREFAB_CHANGED',source,'Exact unchanged source Prefab required')
        result[source]=row
    return result
