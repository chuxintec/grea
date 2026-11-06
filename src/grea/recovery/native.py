"""Explicit, bounded native import in an independent copy; never launches during planning."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import os,re,shutil,subprocess,time,signal,threading
from . import __version__
from .byte_budgets import UNITY_INSTRUCTION, enforce, record
from .io import safe,inside,stage_manifest,read,load,sha,write_json,new_output
from .sources.containers import fingerprint
from .sources.compiled import fail
from .targets import unity
from .layout import locate
from .preflight import validate_progress
from .layout.standard import find_analysis


def recover_execution(request_path,expected_request_sha256,out):
    """Create a read-only, hash-bound recovery receipt for a stale native journal."""
    from .native_execution_recovery import recover_execution as recover
    return recover(request_path,expected_request_sha256,out)


def now():return datetime.now(timezone.utc)
def stamp(value):return value.isoformat().replace('+00:00','Z')
def utc(value):
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset()!=timedelta(0):raise ValueError('Deadline must explicitly use UTC')
    return parsed


def source(candidate,expected_manifest):
    root=safe(candidate)
    if not re.fullmatch('[0-9a-f]{64}',expected_manifest) or fingerprint(root/'manifest.json')!=expected_manifest:
        fail('NATIVE_SOURCE_IDENTITY',str(root),'Frozen manifest differs from --expected-manifest')
    manifest=stage_manifest(root)
    if manifest.get('targetProfile')!=unity.PROFILE:fail('NATIVE_TARGET_UNSUPPORTED',str(root),'Expected supported Unity profile')
    plan = inside(root, locate(manifest, 'importPlan'))
    enforce('unityImportInstruction', plan.stat().st_size, UNITY_INSTRUCTION, plan,
            'IMPORT_PLAN_BUDGET', basis='file size')
    expected={r['path'] for r in manifest['files']}|{'manifest.json'}
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual!=expected:fail('NATIVE_SOURCE_DRIFT',str(root),'Unknown or missing files in frozen candidate')
    for record in manifest['files']:
        if fingerprint(inside(root,record['path']))!=record['sha256']:
            fail('NATIVE_SOURCE_DRIFT',record['path'],'Candidate changed; no launch')
    adapter=inside(root,locate(manifest,'importer'))
    if not adapter.exists() or 'public static void ImportBatchAsync()' not in adapter.read_text():
        fail('NATIVE_ASYNC_ENTRYPOINT_MISSING',str(root),'Regenerate with the async native adapter')
    return root,manifest,fingerprint(plan)


def redact_log(path):
    if not path.exists():return None
    path.chmod(0o600);target=path.with_name(path.stem+'.redacted'+path.suffix)
    hide=False;arguments=False
    with path.open(errors='replace') as stream,target.open('w') as output:
        for line in stream:
            if line.startswith('COMMAND LINE ARGUMENTS:'):
                arguments=True;output.write('COMMAND LINE ARGUMENTS: [REDACTED]\n');continue
            if arguments:
                if line.startswith(('[UnityMemory]','Initialize engine version:','[Package Manager]')):arguments=False
                else:continue
            if hide:output.write('[REDACTED]\n');hide=False;continue
            if line.strip().lower() in ('-accesstoken','-hubsessionid','-password','-serial'):
                output.write(line);hide=True;continue
            line=re.sub(r'(?i)((?:access.?token|authorization|password|secret)\s*[:=]\s*)\S+',r'\1[REDACTED]',line)
            if any(k in line for k in ('Machine Id:','Session Id:','Correlation Id:','External correlation Id:')):line=line.split(':',1)[0]+': [REDACTED]\n'
            output.write(line)
    target.chmod(0o600);return target.name


def native_import(candidate,output,editor,expected_manifest,budget_seconds,deadline_utc,window_end_utc,execute=False,render_preview=False):
    if type(render_preview) is not bool:raise ValueError('render_preview must be a boolean')
    if Path(editor).name in ('CocosCreator','CocosCreator.exe'):
        if render_preview:raise ValueError('--render-preview is currently Unity-only')
        from .native_creator import native_import as creator_import
        return creator_import(candidate,output,editor,expected_manifest,budget_seconds,deadline_utc,window_end_utc,execute)
    if execute and threading.current_thread() is not threading.main_thread():raise ValueError('Native execution requires the CLI main thread for safe signal handling')
    deadline,end=utc(deadline_utc),utc(window_end_utc)
    if type(budget_seconds) is not int or not 1<=budget_seconds<=3600:raise ValueError('Method budget must be 1..3600 seconds')
    if not now()<deadline<=end-timedelta(seconds=30) or end>now()+timedelta(hours=1):
        raise ValueError('Use a future internal UTC deadline, at least 30 seconds cleanup margin and at most a one-hour outer window')
    executable=safe(editor)
    if executable.name not in ('Unity','Unity.exe') or not executable.is_file() or not os.access(executable,os.X_OK):
        fail('NATIVE_EDITOR_PATH',str(executable),'Explicit installed Unity Editor executable required; not the unity CLI')
    root,manifest,plan_hash=source(candidate,expected_manifest)
    out=safe(output)
    spec=dict(schemaVersion=1,toolVersion=__version__,launcherSha256=fingerprint(Path(__file__)),source=str(root),sourceManifestSha256=expected_manifest,
              importPlanSha256=plan_hash,byteBudgets=[record('unityImportInstruction', UNITY_INSTRUCTION, (root/locate(manifest,'importPlan')).stat().st_size, basis='file size')],editor=str(executable),method='MonkeyImporter.ImportBatchAsync',
              budgetSeconds=budget_seconds,deadlineUtc=stamp(deadline),windowEndUtc=stamp(end),
              batchmode=True,noGraphics=not render_preview,renderPreview=render_preview,quitFlag=False,project='UnityProject',nativeResumeSupported=False)
    if out.exists():
        files={p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()}
        if files!={'native-plan.json','plan-identity.json'}:fail('NATIVE_WORKSPACE_EXISTS',str(out),'Only an unchanged planning-only workspace can be executed; keep partial/manual projects')
        raw=read(out/'native-plan.json');identity=load(read(out/'plan-identity.json'))
        if sha(raw)!=identity.get('sha256') or load(raw)!=spec:fail('NATIVE_PLAN_CHANGED',str(out),'Plan or options differ; create a fresh output')
    else:
        out=new_output(out,[root,executable])
        write_json(out/'native-plan.json',spec);write_json(out/'plan-identity.json',dict(schemaVersion=1,sha256=fingerprint(out/'native-plan.json')))
    if not execute:return dict(status='planned',processStarted=False,report=str(out/'native-plan.json'))
    result=dict(schemaVersion=1,status='partial',processStarted=False,processExited=True,sourceManifestSha256=expected_manifest,
                importPlanSha256=plan_hash,project='UnityProject',nativeResumeSupported=False,startedUtc=stamp(now()))
    project=out/'UnityProject';shutil.copytree(root,project)
    if now()>=deadline:
        result.update(reason='NATIVE_DEADLINE_ELAPSED_BEFORE_LAUNCH');write_json(out/'execution-result.json',result)
        return dict(result,report=str(out/'execution-result.json'))
    env=dict(os.environ,MONKEY_NATIVE_BUDGET_SECONDS=str(budget_seconds),MONKEY_NATIVE_DEADLINE_UTC=stamp(deadline))
    args=[str(executable),'-batchmode']+([] if render_preview else ['-nographics'])+['-projectPath',str(project),'-executeMethod',spec['method'],'-logFile',str(out/'import.log')]
    console=out/'console.log';console.touch(mode=0o600);(out/'import.log').touch(mode=0o600)
    process=None;stopped=None;old_handlers={};interrupted=[]
    def interrupted_handler(number,frame):interrupted.append(number)
    try:
        with console.open('w') as stream:
            process=subprocess.Popen(args,cwd=project,env=env,stdout=stream,stderr=subprocess.STDOUT)
            result.update(processStarted=True,processExited=False,pid=process.pid)
            write_json(out/'execution-journal.json',dict(result,status='running'))
            for signum in (signal.SIGINT,signal.SIGTERM):
                old_handlers[signum]=signal.getsignal(signum);signal.signal(signum,interrupted_handler)
            while process.poll() is None:
                if interrupted or now()>=end-timedelta(seconds=30):
                    stopped='operator_interrupted' if interrupted else 'outer_timebox'
                    process.terminate() # Only the child we own. No process groups or SIGKILL.
                    break
                time.sleep(0.5)
            if process.poll() is None:
                try:process.wait(timeout=min(30,max(0.01,(end-now()).total_seconds())))
                except subprocess.TimeoutExpired:pass
            result.update(processExited=process.poll() is not None,processExitCode=process.poll(),stopReason=stopped)
    except KeyboardInterrupt:
        stopped='operator_interrupted'
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=min(30,max(0.01,(end-now()).total_seconds())))
            except subprocess.TimeoutExpired:pass
        result.update(processExited=process is None or process.poll() is not None,processExitCode=process.poll() if process else None,stopReason=stopped)
    except OSError as error:
        result.update(reason='NATIVE_HOST_IO_FAILED' if process is not None else 'NATIVE_LAUNCH_FAILED',error=str(error))
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=min(30,max(0.01,(end-now()).total_seconds())))
            except subprocess.TimeoutExpired:pass
        result.update(processExited=process is None or process.poll() is not None,processExitCode=process.poll() if process else None)
    except Exception as error:
        result.update(status='partial',reason='NATIVE_HOST_EXCEPTION',error=f'{type(error).__name__}: {error}')
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=min(30,max(0.01,(end-now()).total_seconds())))
            except subprocess.TimeoutExpired:pass
        result.update(processExited=process is None or process.poll() is not None,
                      processExitCode=process.poll() if process else None)
    finally:
        for signum,handler in old_handlers.items():signal.signal(signum,handler)
    phase='native-progress';control_exception=None;finalization_exception=None
    try:
        progress=find_analysis(project,'native-progress.json')
        if progress.exists():
            try:result['nativeProgress']=validate_progress(load(read(progress,max_bytes=65536)),plan_hash)
            except (ValueError,OSError) as error:result.update(reason='NATIVE_PROGRESS_INVALID',error=str(error))
        if not result['processExited']:
            result.update(reason='NATIVE_EXIT_PENDING',requiresAttention=True)
        elif not stopped and result.get('processExitCode')==0 and result.get('nativeProgress',{}).get('status') in ('completed','completed_partial'):
            phase='verification'
            checked=unity.verify(project,out/'Verification','editor')
            result.update(verification=dict(editor=checked.get('editorValidation'),diagnostics=len(checked['diagnostics'])))
            if not checked['diagnostics'] and result['nativeProgress']['status']=='completed':result['status']='candidate'
            else:result['reason']='NATIVE_ACCEPTANCE_PARTIAL'
        else:result.setdefault('reason','NATIVE_STOPPED' if stopped else 'NATIVE_IMPORT_FAILED')
    except Exception as error:
        result.update(status='partial',reason='NATIVE_VERIFICATION_EXCEPTION' if phase=='verification' else 'NATIVE_POST_IMPORT_EXCEPTION',
                      error=f'{type(error).__name__}: {error}',verification=dict(status='failed' if phase=='verification' else 'not_run',
                      exceptionType=type(error).__name__) if phase=='verification' else result.get('verification'))
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=min(30,max(0.01,(end-now()).total_seconds())))
            except subprocess.TimeoutExpired:pass
        result.update(processExited=process is None or process.poll() is not None,
                      processExitCode=process.poll() if process else None)
    except BaseException as error:
        # Preserve control-flow exceptions, but persist the best observed child
        # exit and a structured partial receipt before re-raising below.
        control_exception=error
        result.update(status='partial',reason='NATIVE_HOST_INTERRUPTED',
                      error=f'{type(error).__name__}: {error}',
                      verification=dict(status='interrupted' if phase=='verification' else 'not_run',
                                        exceptionType=type(error).__name__) if phase=='verification' else result.get('verification'))
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=min(30,max(0.01,(end-now()).total_seconds())))
            except subprocess.TimeoutExpired:pass
        result.update(processExited=process is None or process.poll() is not None,
                      processExitCode=process.poll() if process else None)
    finally:
        # This post-import finalizer runs for ordinary verifier exceptions and
        # BaseException control flow. It records only the actual owned process
        # status; it never converts an unknown exit code into success.
        if process is not None:
            actual_code=process.poll()
            result.update(processExited=actual_code is not None,processExitCode=actual_code)
        try:result['redactedLog']=redact_log(out/'import.log')
        except Exception as error:
            result.update(status='partial',reason=result.get('reason') or 'NATIVE_FINALIZATION_EXCEPTION',
                          redactionError=f'{type(error).__name__}: {error}')
        result.update(endedUtc=stamp(now()))
        result_path=out/'execution-result.json';journal_path=out/'execution-journal.json'
        try:
            write_json(result_path,result)
            if journal_path.exists():
                from .io import encoded
                final_journal=dict(result,journalState='finalized',executionResultSha256=sha(encoded(result)))
                write_json(journal_path,final_journal)
        except Exception as error:
            finalization_exception=error
            result.update(status='partial',journalFinalized=False,
                          journalFinalizationError=f'{type(error).__name__}: {error}')
            try:write_json(result_path,result)
            except Exception:pass
    if control_exception is not None:raise control_exception
    if finalization_exception is not None:raise finalization_exception
    return dict(result,report=str(out/'execution-result.json'))
