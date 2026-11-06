"""AssetRipper 2.0.0 public loopback API host. No source assemblies executed."""
import hashlib
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from ..io import safe,read,load,sha,new_output,write_json
from ..sources.compiled import fail
from ..sources.unity_serialized import container_kind

VERSION='2.0.0+1ac666f47d8e9dedf96afb0b914c70d7656151ea'
TARGET_VERSION='6000.6.2f1'
MAX_INPUT=128*1024*1024


def fingerprint(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda:stream.read(1024*1024),b''):h.update(data)
    return h.hexdigest()


class Form(HTMLParser):
    def __init__(self):super().__init__();self.values={};self.select=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='input' and a.get('name') and 'disabled' not in a:
            if a.get('type')!='checkbox' or 'checked'in a:self.values[a['name']]=a.get('value','')
        elif tag=='select':self.select=a.get('name')
        elif tag=='option' and self.select and 'selected'in a:self.values[self.select]=a.get('value','')
    def handle_endtag(self,tag):
        if tag=='select':self.select=None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):return None


def export(source,executable,output,budget_seconds=600,dependencies=None,bulk=False):
    if not 30<=budget_seconds<=(1500 if bulk else 7200):fail('UNITY_EXPORT_BUDGET','$','Expected bounded provider stage')
    source=safe(source);exe=safe(executable)
    if not source.is_file() or not exe.is_file():fail('UNITY_EXPORT_INPUT','$','Explicit file and existing provider executable required')
    source_raw=read(source,max_bytes=MAX_INPUT)
    if not container_kind(source_raw[:16]):
        fail('UNITY_CONTAINER_UNSUPPORTED',str(source),'Expected an exact Unity bundle or UnityWebData1.0 signature')
    if exe.stat().st_size>256*1024*1024:fail('UNITY_PROVIDER_BUDGET',str(exe),'Provider executable exceeds budget')
    dependency_paths=[safe(p)for p in (dependencies or [])]
    if len(dependency_paths)>2000 or len(set([source,*dependency_paths]))!=len(dependency_paths)+1:fail('UNITY_DEPENDENCY_SET','$','Duplicate or oversized explicit dependency set')
    snapshots=[(source,source_raw)]
    for path in dependency_paths:
        data=read(path,max_bytes=MAX_INPUT)
        if not container_kind(data[:16]):fail('UNITY_DEPENDENCY_FORMAT',str(path),'Expected explicit Unity container')
        snapshots.append((path,data))
    if sum(len(data)for _,data in snapshots)>(8 if bulk else 1)*1024**3:fail('UNITY_DEPENDENCY_BUDGET','$','Bundle inputs exceed declared mode budget')
    if len({p.name.casefold()for p,_ in snapshots})!=len(snapshots):fail('UNITY_DEPENDENCY_NAME_COLLISION','$','Distinct source basenames collide')
    out=new_output(output,[source,exe.parent,*dependency_paths]);runtime=out/'runtime';runtime.mkdir();inputs=out/'source';inputs.mkdir()
    copied=[]
    for path,data in snapshots:
        dest=inputs/path.name;dest.write_bytes(data);copied.append(dest)
    owned_exe=runtime/exe.name;shutil.copy2(exe,owned_exe)
    binaries=[dict(name=exe.name,sha256=fingerprint(exe),bytes=exe.stat().st_size)]
    # Only declared companion library names, not a recursive provider-directory copy.
    for name in ('libcapstone.dylib','libcapstone.so','capstone.dll'):
        path=exe.parent/name
        if path.exists():
            path=safe(path)
            if path.stat().st_size>32*1024*1024:fail('UNITY_PROVIDER_BUDGET',name,'Companion library exceeds budget')
            shutil.copy2(path,runtime/name);binaries.append(dict(name=name,sha256=fingerprint(path),bytes=path.stat().st_size))
    env=dict(os.environ,DOTNET_BUNDLE_EXTRACT_BASE_DIR=str(out/'bundle-cache'),DOTNET_CLI_TELEMETRY_OPTOUT='1')
    check=subprocess.Popen([str(owned_exe),'--version'],cwd=out,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    try:
        version_raw,_=check.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        check.terminate()
        try:check.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            write_json(out/'version-check.json',dict(status='pending_child_exit',pid=check.pid))
            fail('UNITY_PROVIDER_PENDING_CHILD',str(check.pid),'Version query did not exit after normal TERM')
        fail('UNITY_PROVIDER_TIMEOUT',str(exe),'Version query timed out and exited after normal TERM')
    first_line=version_raw.decode('utf-8',errors='strict').splitlines()[0] if version_raw else ''
    write_json(out/'version-check.json',dict(exitCode=check.returncode,firstLine=first_line,outputSha256=sha(version_raw),processExited=True))
    if check.returncode or first_line!='AssetRipper.GUI.Web '+VERSION:
        fail('UNITY_PROVIDER_VERSION',str(exe),'Expected exact AssetRipper '+VERSION)
    receipt=dict(schemaVersion=1,provider='AssetRipper',providerVersion=VERSION,binaries=binaries,
                 source=dict(bytes=len(source_raw),sha256=sha(source_raw)),dependencies=[dict(name=p.name,bytes=len(data),sha256=sha(data))for p,data in snapshots[1:]],targetVersion=TARGET_VERSION,
                 status='started',stage='startup',budgetSeconds=budget_seconds,bulkMode=bulk,processExited=False,sourceCodeExecuted=False,
                 settingsWriteScope='owned runtime directory only',editor='not_run',business='not_run')
    journal=out/'export.json'
    def save(stage=None):
        if stage:receipt['stage']=stage
        write_json(journal,receipt)
    save();start=time.monotonic();deadline=start+budget_seconds;process=None
    log_path=out/'console.log'
    with log_path.open('wb') as log:
        log_path.chmod(0o600)
        try:
            process=subprocess.Popen([str(owned_exe),'--headless','--port','0','--log-path',str(out/'provider.log')],cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT)
            receipt['pid']=process.pid;save()
            endpoint=None
            while time.monotonic()<min(start+max(60,min(600,budget_seconds//2)),deadline-10):
                if process.poll() is not None:raise RuntimeError('Provider exited before endpoint')
                text=read(log_path,max_bytes=8*1024*1024).decode(errors='replace')
                match=re.search(r'http://127\.0\.0\.1:([0-9]+)',text)
                if match:endpoint=match.group();break
                time.sleep(.1)
            if endpoint is None:raise TimeoutError('Provider startup exceeded budget')
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
            def request(route,form=None):
                remaining=deadline-time.monotonic()-10
                if remaining<=0:raise TimeoutError('Provider method deadline')
                req=urllib.request.Request(endpoint+route,data=urllib.parse.urlencode(form,doseq=True).encode() if form is not None else None)
                try:
                    with opener.open(req,timeout=remaining) as response:
                        if response.status!=200:raise RuntimeError('Unexpected provider HTTP status')
                        if form is not None:raise RuntimeError('Provider command returned an error page instead of completion redirect; inspect owned provider.log')
                        data=response.read(4*1024*1024+1)
                        if len(data)>4*1024*1024:raise RuntimeError('Provider response budget')
                        return data
                except urllib.error.HTTPError as error:
                    if form is not None and error.code==302 and error.headers.get('Location') in ('/','/Settings/Edit'):
                        error.close();return b''
                    raise
            save('settings');html=request('/Settings/Edit');parsed=Form();parsed.feed(html.decode());values=parsed.values
            if not all(k in values for k in ('TargetVersion','ScriptContentLevel','ShaderExportMode','TextExportMode')):
                raise RuntimeError('Provider settings schema differs')
            values.update(TargetVersion=TARGET_VERSION,ScriptContentLevel='Level0',ShaderExportMode='Yaml',TextExportMode='Bytes',ExportUnreadableAssets='')
            values.pop('SaveSettingsToDisk',None)
            request('/Settings/Update',values);after=request('/Settings/Edit');parsed=Form();parsed.feed(after.decode())
            required={'TargetVersion':TARGET_VERSION,'ScriptContentLevel':'Level0','ShaderExportMode':'Yaml','TextExportMode':'Bytes'}
            if any(parsed.values.get(k)!=v for k,v in required.items()) or 'SaveSettingsToDisk'in parsed.values:
                raise RuntimeError('Provider did not retain exact settings')
            receipt['settings']=required;receipt['settingsReadbackSha256']=sha(after);save('load')
            # ASP.NET accepts at most 1024 form values. The private inputs
            # directory contains exactly the validated snapshots for this run.
            if len(copied) > 1024:
                request('/LoadFolder', {'Path': str(inputs)})
            else:
                request('/LoadFile', {'Path': [str(p) for p in copied]})
            export_root=out/'exported'
            if export_root.exists():raise RuntimeError('Fresh provider export root already exists')
            save('export');request('/Export/UnityProject',{'Path':str(export_root),'CreateSubfolder':'false'})
            settings=list(export_root.glob('**/ProjectSettings/ProjectVersion.txt'))
            if len(settings)!=1:raise RuntimeError('Expected exactly one native Unity project')
            project=settings[0].parent.parent
            if not re.search(r'^m_EditorVersion:\s*'+re.escape(TARGET_VERSION)+r'\s*$',settings[0].read_text(),re.M):
                raise RuntimeError('Provider export target is not exact Unity 6')
            files=[];total=0
            for path in sorted(export_root.rglob('*')):
                safe(path)
                if path.is_file():
                    total+=path.stat().st_size
                    if total>(8 if bulk else 2)*1024**3 or len(files)>=(200_000 if bulk else 50_000):raise RuntimeError('Provider output budget')
                    files.append(dict(path=path.relative_to(export_root).as_posix(),bytes=path.stat().st_size,sha256=fingerprint(path)))
            asset_files=[p for p in (project/'Assets').rglob('*')if p.is_file() and p.suffix.lower()not in ('.meta','.cs','.dll','.asmdef','.asmref','.js','.wasm')]
            unreadable=list((project/'AssetRipper/UnreadableAssets').rglob('*.unreadable'))
            receipt.update(status='exported_partial'if asset_files else 'exported_evidence_only',project=str(project.relative_to(out)),outputFiles=len(files),outputBytes=total,
                           nativeAssetFiles=len(asset_files),unreadableObjectFiles=len(unreadable),
                           scriptRecovery='disabled; original typed evidence retained separately',shaderRecovery='original YAML, compilation not verified')
            write_json(out/'output-files.json',dict(schemaVersion=1,files=files));save('complete')
        except Exception as error:
            receipt.update(status='failed',error=dict(type=type(error).__name__,message=str(error).splitlines()[0][:300]));save()
        finally:
            if process:
                if process.poll() is None:process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:receipt['status']='pending_child_exit'
                receipt.update(processExited=process.poll() is not None,exitCode=process.poll())
            receipt['sourceUnchanged']=all(fingerprint(path)==sha(data)for path,data in snapshots)
            if not receipt['sourceUnchanged']:receipt['status']='source_changed'
            receipt['elapsedSeconds']=round(time.monotonic()-start,3);save()
    return receipt
