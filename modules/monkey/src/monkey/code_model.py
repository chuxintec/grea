"""Source-bound named methods, including explicit unimplemented semantic regions."""
import os
import shutil
import subprocess
from pathlib import Path
from .io import safe,read,sha,load,new_output,write_json
from .sources.compiled import fail


def inspect(source,output,module_name,bulk=False):
    source=safe(source);raw=read(source)
    if not isinstance(module_name,str) or not module_name or len(module_name)>200:
        fail('CODE_MODULE_NAME',str(module_name),'Expected explicit source module name')
    node=shutil.which('node')
    if not node:fail('DEPENDENCY_MISSING','Node','Required static parser')
    out=new_output(output,[source])
    env={k:v for k,v in os.environ.items() if k not in ('NODE_OPTIONS','NODE_PATH')}
    with source.open('rb') as stream:
        run=subprocess.run([node,'--max-old-space-size=768',str(Path(__file__).with_name('code-facts.cjs'))],stdin=stream,
                           capture_output=True,timeout=120,env=env,cwd=out)
    if run.returncode:
        (out/'ast-error.log').write_bytes(run.stderr[:256*1024])
        write_json(out/'code-model.json',dict(schemaVersion=1,status='failed',code='CODE_AST_FAILED',sourceSha256=sha(raw)))
        fail('CODE_AST_FAILED',str(source),'Static AST failed; source never executed')
    data=load(run.stdout)
    if data.get('schemaVersion')!=1 or data.get('source')!={'sha256':sha(raw),'bytes':len(raw)}:
        fail('CODE_IDENTITY',str(source),'AST input identity differs')
    seen={};ambiguous=[]
    for method in data['methods']:
        span=method['sourceBytes'];start,end=span['start'],span['end']
        if not 0<=start<end<=len(raw) or sha(raw[start:end])!=method['sourceSha256']:
            fail('CODE_METHOD_IDENTITY',method['name'],'AST method range/hash differs')
        key=(method['scopeBytes']['start'],method['ownerAlias'],method['name'],method['static'],method.get('accessor'))
        if key in seen:
            if not bulk:fail('CODE_METHOD_AMBIGUOUS',method['name'],'Repeated member assignment requires control-flow recovery')
            for member in (seen[key],method):
                member['semantic']=dict(kind='unsupported',reason='Repeated member assignment; control-flow/ownership unresolved')
                member['status']='unsupported'
            ambiguous.append(dict(name=method['name'],scopeBytes=method['scopeBytes'],sourceBytes=method['sourceBytes']))
        seen[key]=method
        method['status']='semantic_candidate' if method['semantic']['kind']!='unsupported' else 'unsupported'
    if sha(read(source))!=sha(raw):fail('SOURCE_CHANGED',str(source),'Source changed during static inspection')
    data.update(moduleName=module_name,ambiguousAssignments=ambiguous,bulkEvidence=bulk,status='partial',sourceFamily='javascript',compiled=False,business='not_run',
                summary=dict(methods=len(data['methods']),semanticCandidates=sum(m['status']=='semantic_candidate' for m in data['methods']),
                             unsupported=sum(m['status']=='unsupported' for m in data['methods'])))
    write_json(out/'code-model.json',data)
    return dict(status='partial',module=module_name,summary=data['summary'],report=str(out/'code-model.json'),sourceExecuted=False)
