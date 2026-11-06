"""Read-only native-startup checks. Never launches an Editor or changes host settings."""
from pathlib import Path
import shutil
import math
import re
from .io import safe,stage_manifest,new_output,finish,write_json,read,sha,diagnostic,inside,load
from .sources.containers import fingerprint


def classify_log(text):
    initialized='Initialize engine version:' in text
    readonly='attempt to write a readonly database' in text
    ipc=any(s in text for s in ('Connection invalid','Connection Invalid','_LSModifyNotification'))
    entitlement='Successfully resolved entitlement details' in text
    token='Access token is unavailable' in text
    findings=[]
    if not initialized and (readonly or ipc):
        findings.append(dict(code='HOST_CACHE_OR_IPC_ACCESS_SUSPECTED',confidence='inference',
            message='Startup stopped before engine initialization with host database/IPC warnings; review sandbox/cache access before requesting another bounded run'))
    if token and not entitlement:findings.append(dict(code='LICENSE_ENTITLEMENT_NOT_CONFIRMED',confidence='observed',message='Token update failed and no entitlement resolution is recorded'))
    if token and entitlement:findings.append(dict(code='LICENSE_TOKEN_UPDATE_WARNING',confidence='observed',message='Entitlement resolution is recorded despite failed token update; this alone does not prove a license failure'))
    import_events=text.count("Imported 'GUID:")
    completed='Monkey native import:' in text
    if import_events and not completed:
        findings.append(dict(code='NATIVE_IMPORT_COMPLETION_NOT_RECORDED',confidence='observed',message='Import activity is recorded without the converter completion marker; verify the native readback, do not assume completion'))
    resource_errors={
        'ASYNC_ENTRYPOINT_REQUIRES_BATCH_WITHOUT_QUIT':'Async import requires the owned batch launcher without the quit flag',
        'TMP_RESOURCES_REQUIRE_ASYNC_ENTRYPOINT':'Resource completion must be prepared through the async entrypoint',
        'TMP_ESSENTIAL_IMPORT_FAILED':'Resource package completion failed',
        'TMP_ESSENTIAL_IMPORT_CANCELLED':'Resource package import was cancelled',
        'TMP_PACKAGE_UNRESOLVED':'Installed TMP package location could not be resolved',
        'TMP_PACKAGE_VERSION_MISMATCH':'Installed package differs from the explicit supported dependency',
        'TMP_ESSENTIAL_ARCHIVE_MISSING':'Resolved package is missing its essential-resource archive',
        'TMP_ESSENTIAL_IMPORT_INCOMPLETE':'Resource archive exists but required files are absent after import',
        'TMP_ESSENTIAL_ASSETS_NOT_READY':'Resource files exist but native assets did not load',
        'TMP_SHADER_NAME_MISMATCH':'Imported shader identity differs from the required shader; no substitution',
        'Native TMP bitmap shader unavailable after resource import':'Required bitmap shader was unavailable; inspect resource location and import receipt'
    }
    for marker,message in resource_errors.items():
        if marker in text:findings.append(dict(code=marker if marker.startswith('TMP_') else 'TMP_BITMAP_SHADER_UNAVAILABLE',confidence='observed',message=message))
    if any(s in text for s in ('error CS','Scripts have compiler errors')):findings.append(dict(code='NATIVE_SCRIPT_COMPILE_FAILED',confidence='observed',message='Editor recorded script compiler errors'))
    return dict(engineInitialized=initialized,readonlyDatabaseWarning=readonly,ipcWarning=ipc,
                entitlementResolved=entitlement,tokenUpdateWarning=token,importLogEntries=import_events,converterCompletionRecorded=completed,findings=findings)


def validate_progress(progress,expected_plan_hash):
    phases={'preflight','texture-settings','texture-metadata','textures','tmp-resources','fonts','hierarchy','components','animations','source-prefabs','candidate-save','scene-reopen','native-readback','complete'}
    statuses={'running','budget_exhausted','failed','completed','completed_partial'}
    if type(progress.get('schemaVersion')) is not int or progress.get('schemaVersion')!=1 or progress.get('phase') not in phases or progress.get('status') not in statuses:
        raise ValueError('Unsupported native progress schema/phase/status')
    if not isinstance(progress.get('planSha256'),str) or not re.fullmatch('[a-f0-9]{64}',progress['planSha256']) or progress['planSha256']!=expected_plan_hash:
        raise ValueError('Native progress belongs to a different import plan')
    count,total=progress.get('processed'),progress.get('total');elapsed=progress.get('elapsedSeconds')
    if type(count) is not int or type(total) is not int or not 0<=count<=total or total>1_000_000:
        raise ValueError('Invalid native progress counts')
    if type(elapsed) not in (int,float) or not math.isfinite(elapsed) or elapsed<0 or progress.get('nativeResumeSupported') is not False:
        raise ValueError('Invalid native progress timing/resume contract')
    return {k:progress[k] for k in ('schemaVersion','phase','status','planSha256','processed','total','elapsedSeconds','nativeResumeSupported')}


def preflight(candidate,output,log=None,progress=None):
    root=safe(candidate);manifest=stage_manifest(root);diagnostics=[]
    for row in manifest['files']:
        p=inside(root,row['path'])
        if not p.is_file() or fingerprint(p)!=row['sha256']:
            diagnostics.append(diagnostic('GENERATED_FILE_CHANGED',row['path'],'Candidate differs from frozen ownership manifest'))
    profile=manifest.get('targetProfile');unity=profile=='unity-6000.6.2f1-ugui'
    version=root/'ProjectSettings/ProjectVersion.txt'
    editor=Path('/Applications/Unity/Hub/Editor/6000.6.2f1/Unity.app/Contents/MacOS/Unity')
    if not unity:diagnostics.append(diagnostic('PREFLIGHT_TARGET_UNSUPPORTED',str(profile),'This preflight currently checks only the declared Unity profile'))
    if not version.exists() or '6000.6.2f1' not in version.read_text():diagnostics.append(diagnostic('EDITOR_VERSION_MISMATCH','ProjectVersion.txt','Expected Unity 6000.6.2f1'))
    if not editor.is_file():diagnostics.append(diagnostic('EDITOR_NOT_INSTALLED','Unity6000.6.2f1','Required local Editor absent; no installation attempted'))
    cli=shutil.which('unity')
    if not cli:diagnostics.append(diagnostic('UNITY_CLI_NOT_FOUND','PATH','Local Unity CLI absent; no installation attempted'))
    locks=[str(p.relative_to(root)) for p in (root/'Temp/UnityLockfile',root/'Library/EditorInstance.json') if p.exists()]
    if locks:diagnostics.append(diagnostic('EDITOR_OWNERSHIP_REQUIRES_CHECK',','.join(locks),'Existing Editor state; check exact project/process before a new invocation, never delete locks'))
    observation=None
    if log:
        raw=read(safe(log),max_bytes=32*1024*1024);observation=classify_log(raw.decode('utf-8',errors='replace'))
        observation['sha256']=sha(raw)
        diagnostics.extend(diagnostic(f['code'],'native-startup-log',f['message']) for f in observation['findings'])
    native_progress=None
    if progress:
        from .layout import locate
        plan_path=inside(root,locate(manifest,'importPlan'))
        native_progress=validate_progress(load(read(safe(progress),max_bytes=65536)),fingerprint(plan_path))
        diagnostics.append(diagnostic('NATIVE_PROGRESS_UNVERIFIED',native_progress['phase'],
            'Reported state '+native_progress['status']+'; progress is not native readback or permission to resume in place'))
    out=new_output(output,[root]);report=dict(schemaVersion=1,candidateManifestSha256=fingerprint(root/'manifest.json'),
        targetProfile=profile,editorExecutablePresent=editor.is_file(),unityCliPresent=bool(cli),existingEditorMarkers=locks,
        hostWriteAccess='not_probed',hostIpcAccess='not_probed',nativeExecution='reported_unverified' if native_progress else 'not_run',startupObservation=observation,nativeProgress=native_progress,
        nextAction='Use an isolated acceptance copy and request a fresh bounded window; if host access is restricted, use the normal execution approval flow. No automatic retries or security-setting changes.',diagnostics=diagnostics)
    write_json(out/'preflight.json',report);return finish(out,report)
