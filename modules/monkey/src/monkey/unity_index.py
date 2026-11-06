"""Bounded metadata catalog from an explicit frozen list; no cache discovery."""
import subprocess,re
from pathlib import Path
from .io import safe,read,load,sha,new_output,write_json
from .sources.compiled import fail


def catalog(manifest,provider_python,output,budget_seconds=600):
    manifest=safe(manifest);raw=read(manifest);data=load(raw)
    if data.get('schemaVersion')!=1 or not isinstance(data.get('files'),list) or not 1<=len(data['files'])<=2000:
        fail('UNITY_INDEX_MANIFEST',str(manifest),'Expected1..2000 explicitly frozen files')
    if not 1<=budget_seconds<=1200:fail('UNITY_INDEX_BUDGET','$','Expected1..1200 seconds')
    requested=Path(provider_python).absolute();safe(requested.parent);python=safe(requested.resolve(strict=True));files=[];seen=set();total=0
    for row in data['files']:
        path=safe(manifest.parent/row['path']);size=row.get('bytes');digest=row.get('sha256')
        if not path.is_file() or path in seen or type(size)is not int or not 0<size<=128*1024*1024 or not isinstance(digest,str)or not re.fullmatch('[0-9a-f]{64}',digest):
            fail('UNITY_INDEX_ENTRY',str(path),'Invalid/duplicate explicit input identity')
        seen.add(path);total+=size;files.append(dict(id=row.get('id',str(len(files))),path=str(path),bytes=size,sha256=digest))
    if total>1024*1024*1024:fail('UNITY_INDEX_BUDGET','$','Aggregate inputs exceed1GiB')
    out=new_output(output,[manifest,python.parent,*seen]);job=out/'index-job.json';write_json(job,dict(schemaVersion=1,sourceManifestSha256=sha(raw),files=files))
    receipt=dict(schemaVersion=1,status='started',sourceManifestSha256=sha(raw),workerSha256=sha(read(Path(__file__).parent/'sources/unity_worker.py')),processExited=False,budgetSeconds=budget_seconds)
    with (out/'provider.log').open('wb')as log:
        (out/'provider.log').chmod(0o600)
        p=subprocess.Popen([str(requested),'-I','-B',str(Path(__file__).parent/'sources/unity_worker.py'),'--index',str(job),str(out/'unity-index.json')],cwd=out,stdout=log,stderr=subprocess.STDOUT)
        receipt['pid']=p.pid;write_json(out/'index.json',receipt)
        try:p.wait(timeout=budget_seconds)
        except subprocess.TimeoutExpired:
            p.terminate()
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:pass
        receipt.update(processExited=p.poll()is not None,exitCode=p.poll())
    if p.poll()==0:
        body=read(out/'unity-index.json',max_bytes=128*1024*1024);indexed=load(body,max_nodes=8_000_000)
        if indexed.get('sourceManifestSha256')!=sha(raw):fail('UNITY_INDEX_CHANGED',str(out),'Index manifest identity differs')
        receipt.update(status='partial'if indexed['summary']['failed']else'indexed',summary=indexed['summary'],indexSha256=sha(body))
    else:receipt['status']='failed'if receipt['processExited']else'pending_child_exit'
    write_json(out/'index.json',receipt)
    return dict(receipt,report=str(out/'unity-index.json'))
