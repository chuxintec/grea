"""Explicit opt-in partial export of a container with invalid ETC1 objects."""
import subprocess
from pathlib import Path
from .io import safe,read,sha,load,new_output,write_json
from .sources.compiled import fail


def quarantine(source,provider_python,output,budget_seconds=120):
    source=safe(source);requested=Path(provider_python).absolute();safe(requested.parent);python=safe(requested.resolve(strict=True))
    if not 1<=budget_seconds<=1200:fail('UNITY_PROVIDER_BUDGET','$','Expected1..1200 seconds')
    out=new_output(output,[source,python.parent]);raw=read(source,max_bytes=128*1024*1024)
    write_json(out/'job.json',dict(source=str(source),sourceSha256=sha(raw)))
    receipt=dict(schemaVersion=1,status='started',sourceSha256=sha(raw),processExited=False)
    with (out/'provider.log').open('wb')as log:
        p=subprocess.Popen([str(requested),'-I','-B',str(Path(__file__).parent/'sources/unity_worker.py'),'--quarantine-invalid-textures',str(out/'job.json'),str(out/'quarantine.json')],cwd=out,stdout=log,stderr=subprocess.STDOUT)
        receipt['pid']=p.pid;write_json(out/'execution.json',receipt)
        try:p.wait(timeout=budget_seconds)
        except subprocess.TimeoutExpired:
            p.terminate()
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:pass
        receipt.update(processExited=p.poll()is not None,exitCode=p.poll())
    receipt['sourceUnchanged']=sha(read(source,max_bytes=128*1024*1024))==sha(raw)
    if p.poll()==0 and receipt['sourceUnchanged']:
        body=load(read(out/'quarantine.json'));derived=read(out/'derived.container',max_bytes=128*1024*1024)
        if body.get('sourceSha256')!=sha(raw)or body.get('derivedSha256')!=sha(derived)or body.get('retainedObjectsUnchanged')is not True:
            fail('UNITY_QUARANTINE_RECEIPT',str(out),'Derived container proof differs')
        receipt.update(status='quarantined',removed=len(body['removed']),derived=str(out/'derived.container'),report=str(out/'quarantine.json'))
    else:receipt['status']='failed'if receipt['processExited']else'pending_child_exit'
    write_json(out/'execution.json',receipt);return receipt
