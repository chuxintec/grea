"""Manifest-bound Creator execution in a fresh owned copy, with bounded child lifetime."""
from pathlib import Path
from datetime import timedelta
import os,shutil,subprocess,time,signal,threading
from .io import safe,inside,stage_manifest,read,load,write_json,new_output,sha
from .sources.containers import fingerprint
from .sources.compiled import fail
from .targets import cocos
from .preflight import validate_progress
from .native import now,stamp,utc,redact_log
from .layout.standard import find_analysis


def source(candidate,expected):
    root=safe(candidate)
    if fingerprint(root/'manifest.json')!=expected:fail('NATIVE_SOURCE_IDENTITY',str(root),'Frozen manifest differs')
    manifest=stage_manifest(root)
    if manifest.get('targetProfile')!=cocos.PROFILE:fail('NATIVE_TARGET_UNSUPPORTED',str(root),'Expected Creator 3.8.8')
    expected_files={f['path'] for f in manifest['files']}|{'manifest.json'}
    if {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}!=expected_files:fail('NATIVE_SOURCE_DRIFT',str(root),'Unknown or missing files')
    for f in manifest['files']:
        if fingerprint(inside(root,f['path']))!=f['sha256']:fail('NATIVE_SOURCE_DRIFT',f['path'],'Generated content changed')
    helper=root/'extensions/monkey-import/execution.js'
    if not helper.is_file() or 'MONKEY_NATIVE_EXECUTE' not in helper.read_text():fail('NATIVE_ENTRYPOINT_MISSING',str(root),'Regenerate with explicit Creator CLI execution support')
    return root,manifest,fingerprint(root/'extensions/monkey-import/import-plan.json')


def native_import(candidate,output,editor,expected_manifest,budget_seconds,deadline_utc,window_end_utc,execute=False):
    if execute and threading.current_thread() is not threading.main_thread():raise ValueError('Execution requires CLI main thread')
    deadline,end=utc(deadline_utc),utc(window_end_utc)
    if type(budget_seconds) is not int or not 1<=budget_seconds<=3600:raise ValueError('Method budget must be 1..3600 seconds')
    if not now()<deadline<=end-timedelta(seconds=30) or end>now()+timedelta(hours=1):raise ValueError('Invalid bounded window')
    executable=safe(editor)
    if executable.name not in ('CocosCreator','CocosCreator.exe') or not executable.is_file() or not os.access(executable,os.X_OK):fail('NATIVE_EDITOR_PATH',str(executable),'Explicit installed Creator executable required')
    root,manifest,plan_hash=source(candidate,expected_manifest)
    out=new_output(output,[root]);spec=dict(schemaVersion=1,targetProfile=cocos.PROFILE,sourceManifestSha256=expected_manifest,
        importPlanSha256=plan_hash,launcherSourceSha256=fingerprint(Path(__file__)),editor=str(executable),
        method='monkey-import.importCandidate',readiness=['asset-db/query-ready','scene/query-is-ready'],
        budgetSeconds=budget_seconds,deadlineUtc=stamp(deadline),windowEndUtc=stamp(end),nativeResumeSupported=False)
    write_json(out/'native-plan.json',spec)
    if not execute:return dict(status='planned',processStarted=False,report=str(out/'native-plan.json'))
    project=out/'CocosProject';shutil.copytree(root,project)
    result=dict(schemaVersion=1,status='partial',sourceManifestSha256=expected_manifest,importPlanSha256=plan_hash,
        startedUtc=stamp(now()),processStarted=False,processExited=True,nativeResumeSupported=False)
    process=None;handlers={};interrupted=[];stopped=None
    def interrupt(number,frame):interrupted.append(number)
    def terminate_owned():
        if process is not None and process.poll() is None:
            process.terminate()
            cleanup=min(end,now()+timedelta(seconds=120))
            while process.poll() is None and now()<cleanup:
                try:process.wait(timeout=min(5,max(.01,(cleanup-now()).total_seconds())))
                except subprocess.TimeoutExpired:pass
    console=out/'console.log'
    try:
        if now()>=deadline:raise ValueError('NATIVE_DEADLINE_ELAPSED_BEFORE_LAUNCH')
        env=dict(os.environ,MONKEY_NATIVE_EXECUTE='1',MONKEY_NATIVE_PROJECT=str(project),MONKEY_NATIVE_MANIFEST=expected_manifest,
            MONKEY_NATIVE_DEADLINE_UTC=stamp(deadline),MONKEY_NATIVE_BUDGET_SECONDS=str(budget_seconds))
        console.touch(mode=0o600)
        with console.open('w') as stream:
            process=subprocess.Popen([str(executable),'--project',str(project)],cwd=project,env=env,stdout=stream,stderr=subprocess.STDOUT)
            result.update(pid=process.pid,processStarted=True,processExited=False)
            write_json(out/'execution-journal.json',dict(result,status='running'))
            for number in (signal.SIGINT,signal.SIGTERM):handlers[number]=signal.getsignal(number);signal.signal(number,interrupt)
            while process.poll() is None:
                if interrupted or now()>=deadline:
                    stopped='operator_interrupted' if interrupted else 'internal_deadline';break
                progress=find_analysis(project,'native-progress.json')
                if progress.exists():
                    raw=load(read(progress,max_bytes=65536))
                    if raw.get('sourceManifestSha256')!=expected_manifest:raise ValueError('Native manifest binding differs')
                    result['nativeProgress']=validate_progress(raw,plan_hash)
                    if raw['status'] in ('completed','completed_partial','failed','budget_exhausted'):
                        stopped='native_completed' if raw['status'].startswith('completed') else 'native_failed';break
                # A scope/options failure occurs before the extension may write project evidence.
                if console.exists():
                    with console.open(errors='replace') as log:
                        log.seek(max(0,console.stat().st_size-8192));tail=log.read()
                    if 'cc.Scheduler: Illegal target which doesn' in tail:stopped='native_lifecycle_error';break
                    if 'MONKEY_NATIVE_BOOTSTRAP_FAILED:' in tail:stopped='bootstrap_failed';break
                time.sleep(.5)
            terminate_owned()
            result.update(processExited=process.poll() is not None,processExitCode=process.poll(),stopReason=stopped)
    except (Exception,KeyboardInterrupt) as error:
        result.update(reason='NATIVE_HOST_FAILED',error=str(error)[:4096]);terminate_owned()
        result.update(processExited=process is None or process.poll() is not None,processExitCode=process.poll() if process else None)
    finally:
        for number,handler in handlers.items():signal.signal(number,handler)
    if not result['processExited']:result.update(reason='NATIVE_EXIT_PENDING',requiresAttention=True)
    elif stopped=='native_completed':
        try:
            checked=cocos.verify(project,out/'Verification','editor')
            result['verification']=dict(editor=checked.get('editorValidation'),diagnostics=len(checked['diagnostics']))
            if checked.get('editorValidation')=='pass' and not checked['diagnostics']:result['status']='candidate'
            else:result['reason']='NATIVE_ACCEPTANCE_PARTIAL'
        except (ValueError,OSError,KeyError,TypeError) as error:result.update(reason='NATIVE_VERIFICATION_FAILED',error=str(error)[:4096])
    else:result.setdefault('reason','NATIVE_IMPORT_FAILED')
    # This specific SDK lifecycle failure must not be hidden by an otherwise
    # successful field readback. The log is owned and bounded by this run.
    if console.exists():
        with console.open(errors='replace')as stream:
            lifecycle_error=any('cc.Scheduler: Illegal target which doesn' in line for line in stream)
        if lifecycle_error:
            result.update(status='partial',reason='NATIVE_CREATOR_LIFECYCLE_ERROR')
    failure=find_analysis(project,'native-error.json')
    if failure.exists():
        data=load(read(failure,max_bytes=65536));result['nativeError']=str(data.get('message',''))[:4096]
    result.update(endedUtc=stamp(now()),redactedLog=redact_log(console))
    write_json(out/'execution-result.json',result)
    return dict(result,report=str(out/'execution-result.json'))
