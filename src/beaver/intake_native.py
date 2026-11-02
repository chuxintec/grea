"""Create-only intake execution using the established native asset importer."""
from pathlib import Path
import subprocess
import time
import signal
import threading

from .io import safe, inside, read, load, write_json, new_output, encoded
from .errors import fail
from .output_limits import digest_file, copy_verified, MANIFEST_BYTES, MANIFEST_NODES
from .transaction_fs import lock
from .native_environment import editor_environment
from .unity import editor_path, source_files, source_directories
from .intake import checked_plan, recheck, CONTRACT
from .adoption import native_lock
from .adoption_native import run_child

HELPER_ROOT = 'Assets/BeaverIntakeTools'


def _install(target):
    folder = inside(target, HELPER_ROOT)
    if folder.exists() or inside(target, HELPER_ROOT+'.meta').exists():
        fail('INTAKE_HELPER_CONFLICT', str(folder), 'Owned helper destination must be absent')
    folder.joinpath('Editor').mkdir(parents=True)
    owned = {}
    for name in ('BeaverIntake.cs', 'BeaverAdoption.cs'):
        p = folder/'Editor'/name
        p.write_bytes((Path(__file__).parent/'targets'/name).read_bytes())
        owned[name] = digest_file(p)
    return owned


def _cleanup(target, owned):
    folder = inside(target, HELPER_ROOT)
    allowed = {'Editor.meta'} | {'Editor/'+n+s for n in owned for s in ('', '.meta')}
    if not folder.is_dir(): fail('INTAKE_HELPER_DRIFT', str(folder), 'Owned helper disappeared')
    for name, expected in owned.items():
        p = folder/'Editor'/name
        if not p.is_file() or digest_file(p) != expected:
            fail('INTAKE_HELPER_DRIFT', str(p), 'Owned helper changed; preserve for inspection')
    if any(p.is_symlink() or p.is_file() and p.relative_to(folder).as_posix() not in allowed for p in folder.rglob('*')):
        fail('INTAKE_HELPER_DRIFT', str(folder), 'Unknown helper content')
    for p in sorted(folder.rglob('*'), key=lambda p:len(p.parts), reverse=True):
        if p.is_file(): p.unlink()
        else: p.rmdir()
    folder.rmdir()
    meta = inside(target, HELPER_ROOT+'.meta')
    if meta.exists(): meta.unlink()


def _files(target):
    return {p:v for p,v in source_files(target).items() if p != HELPER_ROOT+'.meta' and not p.startswith(HELPER_ROOT+'/')}


def _directories(target):
    return [p for p in source_directories(target) if p!=HELPER_ROOT and not p.startswith(HELPER_ROOT+'/')]


def _guard(plan, current):
    before = plan['targetBefore']
    if any(current.get(p) != v for p,v in before.items()):
        fail('INTAKE_EXISTING_CHANGED', plan['targetRoot'], 'An existing source/meta/settings file changed; preserve evidence')
    allowed = {r['target']+s for r in plan['additions'] for s in ('', '.meta')}
    allowed |= {p+'.meta' for p in plan['newDirectories']}
    if set(current)-set(before)-allowed:
        fail('INTAKE_UNPLANNED_CHANGE', plan['targetRoot'], 'Unexpected project files were created')
    dirs=set(_directories(safe(plan['targetRoot'])));old=set(plan['targetDirectoriesBefore'])
    if not old<=dirs or dirs-old-set(plan['newDirectories']):
        fail('INTAKE_DIRECTORY_DRIFT',plan['targetRoot'],'Existing directory removed or undeclared directory created')
    for p,expected in plan['targetAuxiliary'].items():
        path=inside(safe(plan['targetRoot']),p)
        if (digest_file(path) if path.is_file() else None)!=expected:
            fail('INTAKE_STATE_DRIFT',p,'Existing adoption state changed; it is not intake-owned')


def _native_plan(plan):
    return dict(targetRoot=plan['targetRoot'], targetFiles=plan['targetBefore'], operations=[
        dict(action='add', source=None, target=r['target'], guid=r['guid'], before=None,
             after=dict(path=r['target'], guid=r['guid'], file=r['file'], meta=r['meta'])) for r in plan['additions']])


def _job(stage, plan, journal, mode):
    targets = {r['source']:r['target'] for r in plan['additions']}
    checks = []
    for v in plan['spec']['verifications']:
        owners = []
        for o in v['objects']:
            fields = []
            for f in o['fields']:
                value = f['value']
                text = value if isinstance(value,str) else ('true' if value is True else 'false' if value is False else str(value))
                fields.append(dict(propertyPath=f['propertyPath'],kind=f['kind'],text=text if f['kind']!='object' else '',reference=value if f['kind']=='object' else None))
            owners.append(dict(o,fields=fields))
        checks.append(dict(asset=targets[v['asset']],objects=owners))
    return dict(targetRoot=plan['targetRoot'],stage=str(stage),mode=mode,planSha256=journal['planSha256'],
                additions=[dict(target=r['target'],guid=r['guid'],fileHash=r['file']['sha256'],metaHash=r['meta']['sha256']) for r in plan['additions']],
                externalScripts=plan['externalScripts'],verifications=checks)


def _gate(stage, plan, journal, editor, mode, budget):
    if threading.current_thread() is not threading.main_thread():
        fail('INTAKE_SIGNAL_OWNER', str(stage), 'Main-thread owned process required')
    path = stage/('intake-job-'+mode+'.json')
    write_json(path,_job(stage,plan,journal,mode))
    args=[str(editor),'-batchmode','-nographics','-projectPath',plan['targetRoot'],'-executeMethod','BeaverIntake.Run','-logFile',str(stage/('intake-'+mode+'.log'))]
    interrupted=[];handlers={};process=None
    native_lock(safe(plan['targetRoot']))
    try:
        with (stage/('intake-'+mode+'-console.log')).open('w') as stream:
            process=subprocess.Popen(args,env=editor_environment('BEAVER_INTAKE_JOB',path),cwd=plan['targetRoot'],stdout=stream,stderr=subprocess.STDOUT)
            journal.update(state='native-'+mode,pid=process.pid,processExited=False);write_json(stage/'journal.json',journal)
            for number in (signal.SIGINT,signal.SIGTERM): handlers[number]=signal.signal(number,lambda n,f:interrupted.append(n))
            deadline=time.monotonic()+budget
            while process.poll() is None and not interrupted and time.monotonic()<deadline: time.sleep(.2)
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=30)
                except subprocess.TimeoutExpired:pass
            journal.update(processExited=process.poll() is not None,exitCode=process.poll());write_json(stage/'journal.json',journal)
            write_json(stage/('intake-'+mode+'-process.json'),dict(pid=process.pid,exited=journal['processExited'],exitCode=process.poll(),interrupted=bool(interrupted)))
    finally:
        for number,handler in handlers.items():signal.signal(number,handler)
    if not journal['processExited']:fail('INTAKE_EXIT_PENDING',str(stage),'Owned Editor has not exited; no recovery/cleanup until its identity is resolved')
    result_path=stage/('native-intake-'+mode+'.json')
    result=load(read(result_path,max_bytes=MANIFEST_BYTES),max_nodes=MANIFEST_NODES) if result_path.is_file() else {}
    if process.returncode!=0 or result.get('status')!='verified' or result.get('planSha256')!=journal['planSha256']:
        fail('INTAKE_NATIVE_FAILED',str(result_path),'Native gate failed; inspect evidence and use intake rollback, never replay apply')
    return result


def execute(plan_path, output, editor, expected, budget=600):
    if type(budget)is not int or not 1<=budget<=1200:fail('INTAKE_BUDGET',str(budget),'1..1200 seconds per phase')
    plan=checked_plan(plan_path,expected);target=safe(plan['targetRoot']);editor=editor_path(editor)
    stage=new_output(output,[target,safe(plan['candidateRoot']),safe(plan_path).parent,safe(plan['specPath'])])
    write_json(stage/'intake-plan.json',plan);write_json(stage/'plan-identity.json',dict(sha256=expected))
    journal=dict(contract=CONTRACT,planSha256=expected,state='prepared',processExited=True,targetRoot=str(target))
    write_json(stage/'journal.json',journal)
    with lock(target):
        recheck(plan);native_lock(target)
        for i,row in enumerate(plan['additions']):
            for kind,suffix in [('file',''),('meta','.meta')]:
                pin=row[kind];copy_verified(inside(safe(plan['candidateRoot']),row['source']+suffix),stage/f'after/{i}/{kind}',pin['sha256'],pin['bytes'])
        owned=_install(target);journal['helperOwned']=owned;write_json(stage/'journal.json',journal)
        try:
            before=_gate(stage,plan,journal,editor,'preflight',budget)
            if _files(target)!=plan['targetBefore']:fail('INTAKE_PREFLIGHT_CHANGED',str(target),'Preflight changed project inputs before import')
            # Same native importer/identity-preserving payload and rollback code as adoption.
            imported=run_child(stage,_native_plan(plan),journal,editor,'apply',budget)
            _guard(plan,_files(target))
            reopened=_gate(stage,plan,journal,editor,'verify',budget)
            if before['scripts']!=reopened['scripts']:fail('INTAKE_SCRIPT_BINDING_DRIFT',str(target),'Retained script identities changed across independent Editor processes')
            _cleanup(target,owned);owned=None
            after=_files(target);_guard(plan,after)
            for r in plan['additions']:
                if after.get(r['target'],{}).get('sha256')!=r['file']['sha256'] or after.get(r['target']+'.meta',{}).get('sha256')!=r['meta']['sha256']:
                    fail('INTAKE_IMPORTED_DRIFT',r['target'],'Imported bytes differ from pinned payload')
            journal.update(state='complete',afterFiles=after,afterDirectories=_directories(target),nativeVerified=True)
            write_json(stage/'journal.json',journal)
            result=dict(status='verified',transaction=str(stage),report=str(stage/'journal.json'),additions=len(plan['additions']),externalScripts=len(plan['externalScripts']),existingBytesUnchanged=True,independentReopen=True,fieldsChecked=reopened['fieldsChecked'],native='verified-declared-intake-subset',visual='not_run',business='not_run')
            write_json(stage/'intake-result.json',result);return result
        except BaseException:
            journal['state']='recovery-required'
            if journal.get('processExited'):
                if owned:
                    try:_cleanup(target,owned)
                    except Exception as error:journal['cleanupError']=str(error)
                journal['afterFiles']=_files(target)
                journal['afterDirectories']=_directories(target)
            write_json(stage/'journal.json',journal)
            raise


def recover(transaction, editor, expected, budget=600):
    if type(budget)is not int or not 1<=budget<=1200:fail('INTAKE_BUDGET',str(budget),'1..1200 seconds per phase')
    stage=safe(transaction);plan=checked_plan(stage/'intake-plan.json',expected);target=safe(plan['targetRoot']);editor=editor_path(editor)
    journal=load(read(stage/'journal.json',max_bytes=MANIFEST_BYTES),max_nodes=MANIFEST_NODES)
    if journal.get('contract')!=CONTRACT or journal.get('planSha256')!=expected or not journal.get('processExited') or journal.get('state') not in ('complete','recovery-required') or journal.get('cleanupError'):
        fail('INTAKE_RECOVERY_STATE',str(stage),'Exited owned complete/recoverable transaction and clean helper required')
    with lock(target):
        native_lock(target);current=_files(target)
        if current!=journal.get('afterFiles') or _directories(target)!=journal.get('afterDirectories'):
            fail('INTAKE_ROLLBACK_CONFLICT',str(target),'Project changed after recorded transaction; preserve all later edits')
        _guard(plan,current)
        if not (stage/'native-apply.json').exists():
            if current!=plan['targetBefore']:fail('INTAKE_RECOVERY_UNKNOWN',str(stage),'No native write checkpoint and project is not exact before-state')
            journal.update(state='rolled-back',restored=0);write_json(stage/'journal.json',journal)
            return dict(status='rolled-back',restored=0,report=str(stage/'journal.json'))
        owned=_install(target)
        try:
            native=run_child(stage,_native_plan(plan),journal,editor,'rollback',budget)
            _gate(stage,plan,journal,editor,'rollback-check',budget)
            _cleanup(target,owned);owned=None
            if _files(target)!=plan['targetBefore'] or _directories(target)!=plan['targetDirectoriesBefore']:
                fail('INTAKE_ROLLBACK_INCOMPLETE',str(stage),'Existing/new-file set differs from exact original before-state')
            journal.update(state='rolled-back',restored=len(native['restored']));write_json(stage/'journal.json',journal)
            return dict(status='rolled-back',restored=len(native['restored']),report=str(stage/'journal.json'),existingBytesUnchanged=True)
        except BaseException:
            journal['state']='recovery-required'
            if journal.get('processExited') and owned:
                try:_cleanup(target,owned)
                except Exception as error:journal['cleanupError']=str(error)
            if journal.get('processExited') and not journal.get('cleanupError'):
                journal['afterFiles']=_files(target)
                journal['afterDirectories']=_directories(target)
            write_json(stage/'journal.json',journal);raise
