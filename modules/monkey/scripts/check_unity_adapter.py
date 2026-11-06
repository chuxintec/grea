"""Compile Editor adapter against explicit existing assemblies without launching Unity.

This proves API/type compatibility only, never Editor import/save or rendering.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

p=argparse.ArgumentParser()
p.add_argument('--unity-contents',type=Path,required=True)
p.add_argument('--ugui-assemblies',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
scripting=a.unity_contents/'Resources/Scripting'
mono=scripting/'MonoBleedingEdge'
refs={}
for folder in [scripting/'Managed',scripting/'Managed/UnityEngine']:
    for path in folder.glob('*.dll'):refs[path.name]=path
for name in ['mscorlib.dll','System.dll','System.Core.dll']:
    refs[name]=mono/'lib/mono/4.8-api'/name
refs['netstandard.dll']=mono/'lib/mono/4.8-api/Facades/netstandard.dll'
for name in ['UnityEngine.UI.dll','Unity.TextMeshPro.dll']:
    refs[name]=a.ugui_assemblies/name
source=Path(__file__).resolve().parents[1]/'src/monkey/targets/UnityImporter.cs'
args=['-nologo','-nostdlib+','-target:library','-langversion:latest',f'-out:{out}/Monkey.Editor.dll',
      *[f'-r:{v.resolve()}' for v in refs.values()],str(source),str(source.with_name('ContentPreviewView.cs')),str(source.with_name('IntrinsicGridLayoutGroup.cs'))]
(out/'compile.rsp').write_text('\n'.join('"'+v+'"' for v in args))
result=subprocess.run([str(mono/'bin/mono'),str(mono/'lib/mono/msbuild/Current/bin/Roslyn/csc.exe'), '-noconfig', '@'+str(out/'compile.rsp')],capture_output=True,text=True)
(out/'compile.log').write_text(result.stdout+result.stderr)
report=dict(status='pass' if result.returncode==0 else 'fail',level='C# assembly compile only; no Unity Editor',
            sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            viewSourceSha256=hashlib.sha256(source.with_name('ContentPreviewView.cs').read_bytes()).hexdigest(),exitCode=result.returncode,
            gridSourceSha256=hashlib.sha256(source.with_name('IntrinsicGridLayoutGroup.cs').read_bytes()).hexdigest(),
            assemblies=[dict(path=str(path.resolve()),sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in refs.values()])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('status','level','exitCode')}))
print((result.stdout+result.stderr)[:4000])
raise SystemExit(result.returncode)
