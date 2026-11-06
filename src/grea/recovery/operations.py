"""Read-only environment checks and output-space estimates. No install/delete API."""
from collections import defaultdict
from importlib.metadata import version,PackageNotFoundError
from pathlib import Path
import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys

from . import __version__
from .io import safe,read,load,sha,write_json,new_output
from .sources.compiled import fail


def doctor(output,unity_editor=None,creator_editor=None,provider_python=None):
    checks=[]
    checks.append(dict(name='python',status='pass' if sys.version_info>=(3,11) else 'fail',actual=platform.python_version(),required='>=3.11'))
    for package,expected in [('Pillow','12.2.0'),('pypinyin','0.55.0')]:
        try:actual=version(package)
        except PackageNotFoundError:actual=None
        checks.append(dict(name=package,status='pass' if actual==expected else 'fail',actual=actual,required=expected))
    protected=[]
    for kind,location,expected in [('unity',unity_editor,'6000.6.2f1'),('creator',creator_editor,'3.8.8')]:
        if not location:
            checks.append(dict(name=kind,status='not_checked',action='Pass an explicit installed Editor path; no Editor is launched.'));continue
        p=safe(location);protected.append(p);info=p.parent.parent/'Info.plist';actual=None;identity=None
        if p.is_file() and info.is_file():
            raw=read(info,max_bytes=1024*1024);meta=plistlib.loads(raw);identity=sha(raw)
            candidates=[str(meta.get(k,''))for k in ('CFBundleVersion','CFBundleShortVersionString')]
            actual=expected if expected in candidates else next((x for x in candidates if x),None)
        checks.append(dict(name=kind,path=str(p),expected=expected,actual=actual,infoPlistSha256=identity,
                           status='pass' if actual==expected else 'fail',processLaunched=False,
                           action='Use the exact installed Editor; this check does not install, connect to, or validate a project.'))
    if provider_python:
        # Keep a venv's invocation path: resolving its Python symlink changes the environment.
        p=Path(provider_python).absolute();protected.append(p.parent)
        if not re.fullmatch(r'python(?:\d+(?:\.\d+)*)?(?:\.exe)?',p.name,re.I) or not p.is_file():
            fail('DOCTOR_PROVIDER_PATH',str(p),'Expected an explicit installed Python executable')
        script="import json,sys;from importlib.metadata import version;print(json.dumps({'python':sys.version.split()[0],'UnityPy':version('UnityPy')}))"
        try:
            run=subprocess.run([str(p),'-I','-B','-c',script],capture_output=True,text=True,timeout=10,check=False)
            actual=json.loads(run.stdout) if run.returncode==0 and len(run.stdout)<4096 else {}
            checks.append(dict(name='unitypy-provider',path=str(p),actual=actual,status='pass' if actual.get('UnityPy')=='1.25.3' else 'fail',
                               sourceCodeExecuted=False,action='Reuse the pinned provider; no dependency installation was attempted.'))
        except (subprocess.TimeoutExpired,ValueError,OSError):checks.append(dict(name='unitypy-provider',status='fail',action='Provider metadata probe failed; no source code was loaded.'))
    else:checks.append(dict(name='unitypy-provider',status='not_checked',action='Pass --provider-python only for Unity-source recovery.'))
    disk=shutil.disk_usage(Path(output).absolute().parent if Path(output).absolute().parent.exists() else Path.cwd())
    report=dict(schemaVersion=1,status='ready_for_checked_scope' if all(c['status']!='fail'for c in checks) else 'attention_required',
                toolVersion=__version__,platform=sys.platform,machine=platform.machine(),checks=checks,nodeAvailable=shutil.which('node')is not None,
                freeBytes=disk.free,editorStarted=False,dependenciesInstalled=False,sourceCodeExecuted=False,
                limitations=['Only explicitly selected editors/provider are checked.','macOS Editor versions use bundle metadata; other OS Editor version probes remain not_checked/failed rather than guessed.','A dependency or executable check is not project import, compilation, or gameplay validation.'])
    out=new_output(output,protected);write_json(out/'environment.json',report)
    return dict(status=report['status'],checks=checks,report=str(out/'environment.json'))


def space_preview(root,output,protect=(),max_files=500000):
    root=safe(root);protected=[safe(p)for p in protect]
    if not root.is_dir():fail('SPACE_ROOT',str(root),'Expected an existing output directory')
    if type(max_files)is not int or not 1<=max_files<=500000:fail('SPACE_FILE_BUDGET',str(root),'Expected 1..500000 files')
    # Aggregate by cache directory or top-level retained folder; never retain a giant per-file list.
    raw_names={'sources','sourcerecovery','sourceinspection','sourcecode','raw','evidence','analysis','backup','backups','assets','packages','projectsettings','settings','docs'}
    cache_names={'library','temp','obj','logs'};groups=defaultdict(lambda:dict(files=0,logicalBytes=0));markers=[];stack=[root];count=0;directories=0;skipped=[];complete=True;entries_scanned=0;skipped_count=0
    def skip(path,reason):
        nonlocal skipped_count
        skipped_count+=1
        if len(skipped)<1000:skipped.append(dict(path=path,reason=reason))
    while stack and complete:
        directory=stack.pop();directories+=1
        if directories>500000:complete=False;break
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    entries_scanned+=1
                    if entries_scanned>500000:complete=False;break
                    p=Path(entry.path);rel=p.relative_to(root);parts=rel.parts
                    if entry.is_symlink():skip(rel.as_posix(),'symlink-not-followed');continue
                    if entry.is_dir(follow_symlinks=False):stack.append(p);continue
                    if not entry.is_file(follow_symlinks=False):skip(rel.as_posix(),'special-file');continue
                    if count>=max_files:complete=False;break
                    count+=1;size=entry.stat(follow_symlinks=False).st_size
                    if p.name in ('manifest.json','recovery-manifest.json'):markers.append(p)
                    forced=any(p==x or p.is_relative_to(x)for x in protected) or any(x.casefold()in raw_names for x in parts)
                    cache=next((i for i,x in enumerate(parts[:-1]) if x.casefold()in cache_names),None)
                    group='/'.join(parts[:cache+1]) if cache is not None and not forced else parts[0] if len(parts)>1 else '.'
                    row=groups[(group,False if forced else cache is not None)];row['files']+=1;row['logicalBytes']+=size
        except OSError as error:skip(directory.relative_to(root).as_posix(),type(error).__name__)
    owned=set();marker_bytes=0
    for p in markers:
        size=p.stat().st_size
        if size>32*1024*1024 or marker_bytes+size>64*1024*1024:continue
        try:
            d=load(read(p),max_nodes=8_000_000);marker_bytes+=size
            if d.get('schemaVersion')==1 and (d.get('targetProfile')in ('unity-6000.6.2f1-ugui','cocos-3.8.8') or d.get('targetVersion')=='6000.6.2f1') and isinstance(d.get('files'),list):owned.add(p.parent)
        except Exception:continue
    rows=[]
    for (relative,is_cache),values in sorted(groups.items()):
        p=root/relative;owners=[parent for parent in owned if p.is_relative_to(parent)]
        recognized=is_cache and bool(owners) and not any((parent/'Temp/UnityLockfile').exists()for parent in owners)
        rows.append(dict(path=relative,**values,category='regenerable-editor-cache' if recognized else 'retained',protected=not recognized,
                         action='review-only; close any owning Editor before a separately authorized cleanup' if recognized else 'retain original/evidence/current-candidate/manual-or-unrecognized content'))
    report=dict(schemaVersion=1,status='preview' if complete and not skipped else 'incomplete-preview',root=str(root),scanComplete=complete and not skipped,
                filesScanned=count,directoriesScanned=directories,entriesScanned=min(entries_scanned,500000),entryBudget=500000,rows=rows,skipped=skipped,skippedCount=skipped_count,omittedSkipped=skipped_count-len(skipped),
                logicalBytes=sum(r['logicalBytes']for r in rows),reviewableCacheLogicalBytes=sum(r['logicalBytes']for r in rows if not r['protected']),
                deletedFiles=0,deleteSupported=False,candidateBytesReverified=False,
                limitations=['Only space metadata was scanned. No candidate integrity or process-idle claim is made.',
                             'All candidate assets, raw inputs, evidence, manual and unknown files are retained by default.',
                             'Logical size is not guaranteed physical reclaimable space (hard links, sparse files and APFS clones may share blocks).'])
    out=new_output(output,[root,*protected]);write_json(out/'space-preview.json',report)
    return dict(status=report['status'],filesScanned=count,logicalBytes=report['logicalBytes'],reviewableCacheLogicalBytes=report['reviewableCacheLogicalBytes'],deletedFiles=0,report=str(out/'space-preview.json'))
