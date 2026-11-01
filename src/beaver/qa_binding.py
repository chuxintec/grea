"""Owned-run inspection and attach-only, PID-directed macOS UI sessions.

No operation here starts or terminates an application. The native helper is a
locally compiled, source/hash-bound controller, never a LaunchServices client.
"""
import json
import math
import os
import plistlib
import shutil
import subprocess
import time
import uuid
from datetime import datetime,timezone,timedelta
from pathlib import Path

from .errors import BeaverError,fail
from .io import safe,read,load,sha,encoded,write_json,new_output
from .implementation import identity
from .output_limits import digest_file
from . import process_identity

BACKEND='macos-native-ax-pid/1'
CONTRACT='beaver-unity-qa-binding/1'


def _same(a,b):
    try:return os.path.samefile(a,b)
    except (OSError,ValueError,TypeError):return False


def _argv_matches(actual,expected):
    return isinstance(actual,list) and len(actual)==len(expected) and bool(actual) and _same(actual[0],expected[0]) and actual[1:]==expected[1:]


def capture_origin(pid,exe,args,env):
    """Capture only our Popen child's birth; wrapper exec preserves this ID.

    Raw kernel argv/env are used transiently and never returned or recorded.
    A legacy unknown snapshot cannot be promoted to this strong provenance.
    """
    expected_child=[str(exe),*args[args.index(str(exe))+1:]]
    for attempt in range(5):
        s=process_identity.snapshot(pid)
        actual=s.get('arguments')
        is_child=_same(s.get('executablePath'),exe) and _argv_matches(actual,expected_child)
        is_wrapper=args[0]=='/usr/bin/sandbox-exec' and _same(s.get('executablePath'),args[0]) and _argv_matches(actual,args)
        if (s.get('status')=='verified' and s.get('ppid')==os.getpid() and s.get('uniqueId')
                and (is_child or is_wrapper) and all((s.get('environment') or {}).get(k)==v for k,v in env.items())):
            return dict(status='verified',pid=pid,parentPid=os.getpid(),uniqueId=s['uniqueId'],startTime=s['startTime'],
                        initialExecutablePath=s['executablePath'],initialPhase='player' if is_child else 'sandbox-exec',
                        expectedArgumentsSha256=sha(encoded(expected_child)),environmentMatched=True,
                        birthIdentitySource=s.get('birthIdentitySource'))
        if attempt<4:time.sleep(0.02)
    return dict(status='unknown',reason='Owned birth/argv/environment snapshot unavailable; binding must refuse')


def _resolve(project,build,profile,expected_owner,run,full_bundle=False):
    from .qa_runtime import _read_owner,_read_control_json,_guard_root,_id,_hash_tree,_app_executable
    root,profile_root,owner=_read_owner(project,build,profile,expected_owner)
    _id(run,'runId');data=root.parent.parent/'data';p=_guard_root(data/'runs'/(run+'.json'))
    if not p.is_file():fail('QA_BIND_RUN_MISSING',run,'Explicit run does not exist; no app selection or fallback launch')
    record=_read_control_json(p,128*1024)
    if (record.get('runId'),record.get('projectId'),record.get('buildId'),record.get('profileId'),record.get('expectedOwnerSha256'))!=(run,project,build,profile,expected_owner):
        fail('QA_BIND_RUN_IDENTITY',run,'Run must match the explicit owner/project/build/profile')
    if record.get('owned') is not True or record.get('status')!='running':fail('QA_BIND_NOT_RUNNING',run,'Only an owned running run may be resolved; never launches a substitute')
    app=root/'App.app';exe=_app_executable(app);log=data/'logs'/profile/(run+'.log')
    if record.get('cwd')!=str(app) or not _same(record.get('executablePath'),exe) or record.get('logPath')!=str(log):fail('QA_BIND_RUN_PATH',run,'Recorded launch spelling/executable/log does not match controlled paths')
    origin=record.get('instanceOrigin',{})
    if origin.get('status')!='verified' or origin.get('pid')!=record.get('pid') or not origin.get('uniqueId'):
        fail('QA_BIND_BIRTH_UNPROVEN',run,'Strong owned launch birth proof is unavailable; legacy wrapper snapshots are not upgraded')
    info_path=app/'Contents/Info.plist';info=plistlib.loads(read(info_path))
    if info.get('CFBundleIdentifier')!=owner.get('bundleIdentifier'):fail('QA_BIND_BUNDLE_ID',run,'Bundle identity differs from the immutable owner')
    exe_sha=digest_file(exe,max_bytes=owner['artifactMaxFileBytes'])
    if exe_sha!=record.get('executableSha256'):fail('QA_BIND_EXECUTABLE_DRIFT',run,'Owned executable bytes changed')
    if full_bundle and _hash_tree(app,max_file_bytes=owner['artifactMaxFileBytes'],max_total_bytes=owner['artifactMaxTotalBytes'],max_files=owner['artifactMaxFiles'])!=owner['bundle']['treeSha256']:
        fail('QA_BUNDLE_DRIFT',run,'Owned bundle changed')
    s=process_identity.snapshot(record['pid'])
    expected=[str(exe),*owner['arguments'],'-logFile',str(log)]
    if (s.get('status')!='verified' or s.get('uniqueId')!=origin['uniqueId'] or s.get('startTime')!=origin.get('startTime')
            or s.get('ppid')!=origin.get('parentPid') or not _same(s.get('executablePath'),exe)
            or not _argv_matches(s.get('arguments'),expected) or sha(encoded(expected))!=origin.get('expectedArgumentsSha256')):
        fail('QA_BIND_PROCESS_CHANGED',run,'Birth, executable, parent or exact argv identity is missing/changed; no fallback')
    for name,b in owner['environmentBindings'].items():
        value=str(profile_root) if b['kind']=='profile' else owner['configInputs'][b['id']]['path']
        if (s.get('environment') or {}).get(name)!=value or record.get('cleanEnvironment',{}).get(name)!=value:
            fail('QA_BIND_PROFILE_CHANGED',run,'Live typed profile/config binding differs from owned launch')
    st=exe.stat()
    report=dict(schemaVersion=1,contract='beaver-unity-qa-instance/1',status='process-verified',projectId=project,buildId=build,profileId=profile,runId=run,
                ownerSha256=expected_owner,processRecord=str(p),processRecordSha256=digest_file(p),pid=s['pid'],parentPid=s['ppid'],uniqueId=s['uniqueId'],startTime=s['startTime'],
                launchBundlePath=record['cwd'],declaredExecutablePath=str(exe),observedExecutablePath=s['executablePath'],executableSameFile=True,
                executableSha256=exe_sha,executableDevice=st.st_dev,executableInode=st.st_ino,bundleIdentifier=info['CFBundleIdentifier'],infoPlistSha256=digest_file(info_path),
                argumentsMatched=True,profileBindingsMatched=True,launchPerformed=False,windowOwnership='not-yet-observed',attachAllowed=False,
                limitations=['Process inspection is not an input session; no App selection or launch occurs','Filesystem-equivalent spelling does not identify a GUI instance'])
    return report


def inspect_instance(project,build,profile,expected_owner,run,out):
    report=_resolve(project,build,profile,expected_owner,run,True)
    folder=new_output(out,[safe(report['launchBundlePath']),safe(report['processRecord']).parent]);report['report']=str(folder/'qa-instance.json');write_json(folder/'qa-instance.json',report)
    return report


def _helper_source():return Path(__file__).parent/'targets/BeaverAppBinding.m'


def _compile(folder):
    if os.uname().sysname!='Darwin':fail('QA_ATTACH_BACKEND_UNSUPPORTED',BACKEND,'Native PID binding currently requires macOS')
    source=_helper_source();native=folder/'native';native.mkdir(mode=0o700);binary=native/'BeaverAppBinding'
    command=['/usr/bin/clang','-fobjc-arc','-framework','Foundation','-framework','AppKit','-framework','ApplicationServices',str(source),'-o',str(binary)]
    result=subprocess.run(command,capture_output=True,timeout=60)
    if result.returncode:fail('QA_ATTACH_HELPER_COMPILE',BACKEND,'Native controller compilation failed; no input or app launch attempted')
    return dict(path=str(binary),sha256=digest_file(binary),sourceSha256=digest_file(source))


def _native(helper,request,before_dispatch=None):
    if digest_file(helper['path'])!=helper['sha256'] or digest_file(_helper_source())!=helper['sourceSha256']:fail('QA_ATTACH_HELPER_DRIFT',BACKEND,'Controller/source identity changed')
    if before_dispatch is not None:before_dispatch()
    try:
        result=subprocess.run([helper['path']],input=encoded(request),capture_output=True,timeout=20)
    except (subprocess.TimeoutExpired,OSError,subprocess.SubprocessError):
        return _unknown_native('QA_ATTACH_NATIVE_OUTCOME_UNKNOWN')
    if len(result.stdout)>2*1024**2:return _unknown_native('QA_ATTACH_HELPER_OUTPUT_UNKNOWN',result.returncode)
    try:data=load(result.stdout,max_nodes=15000)
    except Exception:return _unknown_native('QA_ATTACH_HELPER_PROTOCOL_UNKNOWN',result.returncode)
    if not isinstance(data,dict) or data.get('status') not in ('verified','performed','performed_exit_observed','blocked'):
        return _unknown_native('QA_ATTACH_HELPER_STATUS_UNKNOWN',result.returncode)
    if request.get('operation') in ('click','drag','key','text','close'):
        counts=('eventsPosted','axActionsAttempted','axActionsPerformed')
        if any(type(data.get(k)) is not int or data[k]<0 for k in counts):
            return _unknown_native('QA_ATTACH_EFFECT_COUNTS_UNKNOWN',result.returncode)
        op=request['operation'];status=data['status']
        delivered=data['axActionsPerformed']>0 if op=='close' else data['eventsPosted']>0
        if status=='verified' or (status in ('performed','performed_exit_observed') and not delivered):
            return _unknown_native('QA_ATTACH_EFFECT_STATUS_MISMATCH',result.returncode)
    data['processExitCode']=result.returncode
    if result.returncode!=0 and data.get('status')!='blocked':
        data['nativeStatus']=data['status']
        data['status']='partial' if _reported_effects(data) else 'unknown'
        data['errorCode']='QA_ATTACH_NATIVE_EXIT_UNEXPECTED'
    elif result.returncode==0 and data.get('status')=='blocked':
        return _unknown_native('QA_ATTACH_NATIVE_STATUS_EXIT_MISMATCH',result.returncode)
    elif data.get('status')=='blocked' and _reported_effects(data):
        data['nativeStatus']='blocked'
        data['status']='partial'
        data['errorCode']=data.get('errorCode') or 'QA_ATTACH_BLOCKED_AFTER_EFFECT'
    return data


def _reported_effects(data):
    return any(type(data.get(k)) is int and data[k]>0 for k in ('eventsPosted','axActionsAttempted','axActionsPerformed'))


def _unknown_native(code='QA_ATTACH_NATIVE_OUTCOME_UNKNOWN',exit_code='unknown'):
    return dict(status='unknown',errorCode=code,message='Native operation outcome is unknown; effects may have been delivered.',
                eventsPosted='unknown',axActionsAttempted='unknown',axActionsPerformed='unknown',
                inputDelivery='possibly-delivered',processExitCode=exit_code)


def _atomic_receipt(folder,response):
    """Atomically persist our owned input receipt, creating or updating only it."""
    target=folder/'qa-input-result.json';temporary=folder/('.qa-input-result.'+uuid.uuid4().hex+'.tmp')
    try:
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as stream:
            stream.write(encoded(response));stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,target)
    finally:
        try:temporary.unlink()
        except FileNotFoundError:pass


def _validate_session_shape(session,path):
    keys={'schemaVersion','contract','sessionId','implementationSha256','backend','createdUtc','expiresUtc','instance','window','helper','launchPerformed','limitation'}
    if not isinstance(session,dict) or set(session)!=keys:fail('QA_BIND_SESSION_SCHEMA',str(path),'Binding session has an unknown or incomplete envelope')
    if (session.get('schemaVersion')!=1 or session.get('contract')!=CONTRACT or session.get('backend')!=BACKEND
            or session.get('launchPerformed') is not False or not isinstance(session.get('sessionId'),str)
            or len(session['sessionId'])!=32 or any(c not in '0123456789abcdef' for c in session['sessionId'])):
        fail('QA_BIND_SESSION_SCHEMA',str(path),'Binding session identity or launch invariant is invalid')
    instance=session.get('instance');window=session.get('window');helper=session.get('helper')
    if not isinstance(instance,dict) or not isinstance(window,dict) or not isinstance(helper,dict):
        fail('QA_BIND_SESSION_SCHEMA',str(path),'Binding session evidence objects are malformed')
    instance_keys={'schemaVersion','contract','status','projectId','buildId','profileId','runId','ownerSha256','processRecord','processRecordSha256','pid','parentPid','uniqueId','startTime','launchBundlePath','declaredExecutablePath','observedExecutablePath','executableSameFile','executableSha256','executableDevice','executableInode','bundleIdentifier','infoPlistSha256','argumentsMatched','profileBindingsMatched','launchPerformed','windowOwnership','attachAllowed','limitations'}
    if set(instance)!=instance_keys:
        fail('QA_BIND_SESSION_SCHEMA',str(path),'Binding session process/run record has unknown or incomplete fields')
    if not {'windowId','ownerPid','bounds'}<=set(window) or set(window)-{'windowId','ownerPid','bounds','title'}:
        fail('QA_BIND_SESSION_SCHEMA',str(path),'Bound window identity is malformed')
    if not {'path','sha256','sourceSha256'}==set(helper):
        fail('QA_BIND_SESSION_SCHEMA',str(path),'Bound helper identity is malformed')
    bounds=window.get('bounds')
    if (type(window.get('windowId')) is not int or not 1<=window['windowId']<=0xffffffff or window.get('ownerPid')!=instance.get('pid')
            or not isinstance(bounds,dict) or set(bounds)!={'x','y','width','height'}
            or any(type(bounds[k]) not in (int,float) or not math.isfinite(bounds[k]) for k in bounds)
            or bounds['width']<=0 or bounds['height']<=0):
        fail('QA_BIND_SESSION_SCHEMA',str(path),'Window is not bound to the recorded process')
    if (type(instance.get('pid')) is not int or instance['pid']<=0 or not isinstance(instance.get('uniqueId'),str)
            or not isinstance(instance.get('startTime'),list) or len(instance['startTime'])!=2
            or any(type(v) is not int or v<0 for v in instance['startTime'])
            or not all(isinstance(helper.get(k),str) and len(helper[k])==64 and all(c in '0123456789abcdef' for c in helper[k]) for k in ('sha256','sourceSha256'))
            or not isinstance(helper.get('path'),str)
            or instance.get('launchPerformed') is not False or instance.get('attachAllowed') is not False):
        fail('QA_BIND_SESSION_SCHEMA',str(path),'Binding process or helper identity fields are malformed')


def _request(report,operation,window=None):
    r=dict(operation=operation,pid=report['pid'],startTime=report['startTime'],executableDevice=report['executableDevice'],executableInode=report['executableInode'],bundleIdentifier=report['bundleIdentifier'])
    if window is not None:r['windowId']=window
    return r


def bind(project,build,profile,expected_owner,run,out,window_id=None,backend=BACKEND):
    if backend!=BACKEND:fail('QA_ATTACH_BACKEND_UNSUPPORTED',backend,'cua-macos getApp may launch and has no PID attach-only contract; no fallback is allowed')
    report=_resolve(project,build,profile,expected_owner,run,True);folder=new_output(out,[safe(report['launchBundlePath']),safe(report['processRecord']).parent])
    helper=_compile(folder);result=_native(helper,_request(report,'windows'))
    windows=result.get('windows',[])
    chosen=[w for w in windows if w.get('windowId')==window_id] if window_id is not None else windows
    if result['status']!='verified' or len(chosen)!=1:
        blocked=dict(status='blocked',errorCode=result.get('errorCode') or 'QA_BIND_WINDOW_AMBIGUOUS',message=result.get('message') or 'Select exactly one owned visible window',instance=report,native=result,launchPerformed=False,report=str(folder/'qa-bind-result.json'))
        write_json(folder/'qa-bind-result.json',blocked);return blocked
    report2=_resolve(project,build,profile,expected_owner,run)
    if report2['uniqueId']!=report['uniqueId'] or report2['executableSha256']!=report['executableSha256']:fail('QA_BIND_PROCESS_CHANGED',run,'Process changed during window binding')
    if chosen[0].get('ownerPid')!=report['pid']:fail('QA_BIND_WINDOW_OWNER',run,'Window owner does not match the controlled process')
    now=datetime.now(timezone.utc);session=dict(schemaVersion=1,contract=CONTRACT,sessionId=uuid.uuid4().hex,implementationSha256=identity(),backend=BACKEND,createdUtc=now.isoformat(),expiresUtc=(now+timedelta(minutes=5)).isoformat(),instance=report,window=chosen[0],helper=helper,launchPerformed=False,
        limitation='Kernel/owner guards run before every event and afterward; checks and OS event posting are not atomic and do not prove business acceptance')
    session_path=folder/'qa-binding.json';write_json(session_path,session);session_sha=digest_file(session_path)
    result=dict(status='bound',session=str(session_path),sessionSha256=session_sha,pid=report['pid'],uniqueId=report['uniqueId'],window=chosen[0],launchPerformed=False,report=str(folder/'qa-bind-result.json'))
    write_json(folder/'qa-bind-result.json',result);return result


def _validate_session(path,expected):
    path=safe(path);raw=read(path)
    if sha(raw)!=expected:fail('QA_BIND_SESSION_DRIFT',str(path),'Explicit expected binding SHA differs')
    session=load(raw)
    _validate_session_shape(session,path)
    if session.get('contract')!=CONTRACT or session.get('implementationSha256')!=identity() or session.get('backend')!=BACKEND:fail('QA_BIND_SESSION_TOOL',str(path),'Binding belongs to a different tool/backend')
    try:expired=datetime.now(timezone.utc)>=datetime.fromisoformat(session['expiresUtc'])
    except Exception:fail('QA_BIND_SESSION_TIME',str(path),'Invalid binding expiry')
    if expired:fail('QA_BIND_SESSION_EXPIRED',str(path),'Create a fresh attach-only binding to the still-running explicit run')
    if session['helper']['path']!=str(path.parent/'native/BeaverAppBinding'):fail('QA_BIND_HELPER_PATH',str(path),'Controller must reside in this exact binding output')
    old=session['instance'];new=_resolve(old['projectId'],old['buildId'],old['profileId'],old['ownerSha256'],old['runId'])
    for k in ('pid','uniqueId','startTime','executableDevice','executableInode','executableSha256','bundleIdentifier','infoPlistSha256','processRecordSha256'):
        if new[k]!=old[k]:fail('QA_BIND_SESSION_STALE',str(path),'Owned process/bundle/run changed since binding')
    return path,session,new


def input_event(session_path,expected_session,spec_path,expected_spec,out):
    path,session,report=_validate_session(session_path,expected_session);raw=read(safe(spec_path))
    if sha(raw)!=expected_spec:fail('QA_BIND_INPUT_DRIFT',str(spec_path),'Explicit input specification SHA differs')
    try:spec=load(raw,max_nodes=10000,max_depth=16)
    except Exception:fail('QA_BIND_INPUT_SPEC',str(spec_path),'Input specification is not bounded valid JSON')
    if not isinstance(spec,dict) or spec.get('operation') not in ('observe','click','drag','key','text','close','screenshot'):fail('QA_BIND_INPUT_SPEC',str(spec_path),'Unknown closed input operation')
    op=spec['operation']
    fields={'observe':{'operation'},'close':{'operation'},'screenshot':{'operation'},
            'click':{'operation','x','y','button'},'drag':{'operation','points','button'},
            'key':{'operation','key'},'text':{'operation','text'}}[op]
    required={'observe':{'operation'},'close':{'operation'},'screenshot':{'operation'},
              'click':{'operation','x','y'},'drag':{'operation','points'},
              'key':{'operation','key'},'text':{'operation','text'}}[op]
    if not required<=set(spec) or set(spec)-fields:fail('QA_BIND_INPUT_SPEC',str(spec_path),'Input specification contains missing or unsupported fields')
    if 'button' in spec and spec['button'] not in ('left','right'):fail('QA_BIND_INPUT_SPEC',str(spec_path),'Unsupported mouse button')
    def finite_number(value):return type(value) in (int,float) and math.isfinite(value)
    if op=='click' and not all(finite_number(spec[k]) for k in ('x','y')):fail('QA_BIND_INPUT_SPEC',str(spec_path),'Click coordinates must be finite numbers')
    if op=='drag':
        points=spec['points']
        if not isinstance(points,list) or not 2<=len(points)<=64 or any(not isinstance(p,dict) or set(p)!={'x','y'} or not finite_number(p['x']) or not finite_number(p['y']) for p in points):
            fail('QA_BIND_INPUT_SPEC',str(spec_path),'Drag requires 2..64 exact finite points')
    if op=='key' and spec['key'] not in ('return','escape','space','tab','left','right','up','down','backspace','command-q'):
        fail('QA_BIND_INPUT_SPEC',str(spec_path),'Unsupported key operation')
    if op=='text':
        text=spec['text']
        try:units=len(text.encode('utf-16-le','strict'))//2 if isinstance(text,str) else 0
        except UnicodeError:units=0
        if not 1<=units<=256:fail('QA_BIND_INPUT_SPEC',str(spec_path),'Text must contain 1..256 valid UTF-16 code units')
    folder=new_output(out,[path.parent,safe(spec_path),safe(report['launchBundlePath'])]);request=_request(report,op,session['window']['windowId'])
    if spec['operation']=='screenshot':
        request['operation']='observe';result=_native(session['helper'],request)
        if result['status']=='verified':
            target=folder/'window.png';capture=subprocess.run(['/usr/sbin/screencapture','-x','-l',str(session['window']['windowId']),str(target)],capture_output=True,timeout=20)
            after=_native(session['helper'],request)
            if capture.returncode or not target.is_file():result=dict(status='blocked',errorCode='QA_BIND_SCREENSHOT_UNPROVEN',message='Window capture failed; no global fallback')
            elif after['status']!='verified':result=dict(status='unknown',errorCode='QA_BIND_SCREENSHOT_OWNER_UNKNOWN',message='Screenshot was captured but post-capture owner verification is unknown.',screenshot=dict(path=str(target),sha256=digest_file(target)))
            else:result=dict(status='performed',screenshot=dict(path=str(target),sha256=digest_file(target)),identity=after.get('identity'),selectedWindow=after.get('selectedWindow'),eventsPosted=0)
    else:request.update(spec)
    mutating=op in ('click','drag','key','text','close')
    if op!='screenshot':
        pending=None;dispatch_started=False
        if mutating:
            pending=dict(status='partial',rawStatus='dispatch_outcome_unknown',sessionSha256=expected_session,inputSpecSha256=expected_spec,
                         pid=report['pid'],uniqueId=report['uniqueId'],windowId=session['window']['windowId'],launchPerformed=False,
                         dispatchState='possibly-delivered',native=_unknown_native('QA_ATTACH_DISPATCH_PENDING'),
                         limitations=['Native input may have been delivered; this receipt is durable before controller dispatch','Input delivery does not establish business acceptance'])
        def persist_pending():
            nonlocal dispatch_started
            _atomic_receipt(folder,pending);dispatch_started=True
        try:
            result=_native(session['helper'],request, before_dispatch=persist_pending if pending is not None else None)
        except BeaverError:
            raise
        except subprocess.TimeoutExpired:
            if not dispatch_started and pending is not None:persist_pending()
            result=_unknown_native('QA_ATTACH_NATIVE_OUTCOME_UNKNOWN')
        except Exception:
            if not dispatch_started:raise
            result=_unknown_native('QA_ATTACH_NATIVE_OUTCOME_UNKNOWN')
    raw_status=result.get('status','unknown')
    response_status=raw_status if raw_status in ('blocked','failed','not_run','performed','performed_exit_observed') else 'partial' if raw_status in ('partial','unknown') or mutating else raw_status
    response=dict(status=response_status,rawStatus=raw_status,dispatchState='possibly-delivered' if mutating and raw_status in ('unknown','partial') else 'completed',sessionSha256=expected_session,inputSpecSha256=expected_spec,pid=report['pid'],uniqueId=report['uniqueId'],windowId=session['window']['windowId'],launchPerformed=False,native=result,
                  report=str(folder/'qa-input-result.json'),limitations=['Event posting is directed to a guarded PID but OS guard/event sequence is not atomic','Posted input does not establish a click callback, save, server action or other business acceptance'])
    if raw_status=='unknown' and mutating:response_status='partial';response['status']=response_status
    _atomic_receipt(folder,response);return response
