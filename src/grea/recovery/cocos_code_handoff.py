"""Named bulk source drafts; optional owned-candidate additive handoff transaction."""
import json,os,shutil,subprocess
from pathlib import Path
from . import __version__
from .io import safe,inside,read,load,sha,write_json,new_output
from .sources.code import drafts
from .sources.compiled import fail
from .layout import standard
from .layout.standard import find_analysis


def enrich(candidate,output,expected_manifest=None,apply=False,reuse_facts=None,expected_facts=None):
    root=safe(candidate);manifest_path=root/'manifest.json';raw=read(manifest_path,max_bytes=128*1024**2);identity=sha(raw);manifest=load(raw,max_nodes=8_000_000)
    if apply and identity!=expected_manifest:fail('CODE_HANDOFF_MANIFEST_CHANGED',str(root),'Explicit current owned manifest hash required')
    if apply and (root/'Temp/UnityLockfile').exists():fail('CODE_HANDOFF_EDITOR_ACTIVE',str(root),'Close owned Editor before additive handoff')
    index=load(read(find_analysis(root,'code-index.json'),max_bytes=128*1024**2),max_nodes=8_000_000);modules=[m for m in index['modules']if m.get('entryType')=='module_candidate'and m.get('sourceEvidence')]
    if not modules:fail('CODE_HANDOFF_NO_MODULES',str(root),'No explicit recovered original module list')
    out=new_output(output,[root]);job=[]
    for m in modules:
        path=inside(root,m['sourceEvidence']);body=read(path)
        if sha(body)!=m['sha256']:fail('CODE_HANDOFF_SOURCE_CHANGED',str(path),'Original module differs from frozen code index')
        job.append(dict(id=m['sourceId'],path=str(path),sha256=m['sha256']))
    write_json(out/'job.json',dict(schemaVersion=1,files=job))
    if reuse_facts:
        prior=read(safe(reuse_facts),max_bytes=128*1024**2)
        if sha(prior)!=expected_facts:fail('CODE_HANDOFF_FACTS_CHANGED',str(reuse_facts),'Explicit frozen facts SHA256 required')
        (out/'facts.json').write_bytes(prior)
    else:
        node=shutil.which('node')
        if not node:fail('DEPENDENCY_MISSING','node','Static Acorn parser required')
        env={k:v for k,v in os.environ.items()if k not in ('NODE_OPTIONS','NODE_PATH')}
        with (out/'parser.log').open('wb')as log:
            process=subprocess.run([node,'--max-old-space-size=768',str(Path(__file__).with_name('code-handoff-batch.cjs')),str(out/'job.json'),str(out/'facts.json')],env=env,cwd=out,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        if process.returncode:fail('CODE_HANDOFF_AST',str(out),'Static batch parser failed; no source executed')
    facts=load(read(out/'facts.json',max_bytes=128*1024**2),max_nodes=8_000_000);by={r['id']:r for r in facts['records']};entries=[];emitted=[]
    # monkey-project/2.0.0 keeps one draft per class: the named draft replaces the untouched stub at the same path.
    current=standard.current(manifest);replaced=set()
    for m in modules:
        record=by[m['sourceId']]
        if record['sha256']!=m['sha256']:fail('CODE_HANDOFF_SOURCE_CHANGED',m['sourceId'],'AST report identity differs')
        updated=dict(m,syntax=dict(m.get('syntax',{}),members=record['members']))
        if current:
            token,cs,ts=drafts(updated,m['sourceId'],m['namespace']);relative=Path(m['draft']);replaced.add(relative.as_posix())
            body=cs if relative.suffix=='.cs' else ts
        else:
            token,cs,ts=drafts(updated,m['sourceId']);body=cs
            name=Path(m['sourceEvidence']).stem;relative=Path('SourceRecovery/CodeDrafts/NamedCSharp')/(name+'-'+sha(m['sourceId'].encode())[:12]+'.cs')
        target=out/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(body)
        emitted.append(relative.as_posix());entries.append(dict(sourceId=m['sourceId'],name=m.get('name'),rf=m.get('rf',[]),dependencies=m.get('dependencies',[]),sourceFile=m.get('sourceFile'),sourceFileBytes=m.get('source_bytes'),memberByteBasis='module-relative-UTF8',original=m['sourceEvidence'],originalSha256=m['sha256'],draft=relative.as_posix(),members=record['members'],methodsImplemented=0,compiled=False))
    report=dict(schemaVersion=1,toolVersion=__version__,sourceManifestSha256=identity,modules=len(entries),namedMembers=sum(len(e['members']['methods'])for e in entries),fieldDeclarations=sum(len(e['members']['fields'])for e in entries),methodsImplemented=0,sourceExecuted=False,entries=entries)
    (out/'Analysis').mkdir(exist_ok=True)
    write_json(find_analysis(out,'named-code-handoff.json'),report);emitted.append('Analysis/Code/named-code-handoff.json')
    if current:text='''# Recovered code status

Read Analysis/Code/named-code-handoff.json and the drafts it lists (SourceRecovery/Code/Drafts/<Layer>/<Module>) before implementing behavior.
Each draft's folder and namespace mirror its future five-layer location; Unclassified means no binding or name evidence yet.
Every member points to its exact original module, byte range/hash, literal JS owner alias and parameters.
Types/alias ownership and all unimplemented bodies remain explicit TODOs. Drafts stay outside Assets.
Use native import/readback receipts for actual Prefab/Scene/resource coverage; business and Player are separate gates.
'''
    else:text='''# AI development entry

Read Analysis/Code/named-code-handoff.json and SourceRecovery/CodeDrafts/NamedCSharp before implementing behavior.
Every member points to its exact original module, byte range/hash, literal JS owner alias and parameters.
Types/alias ownership and all unimplemented bodies remain explicit TODOs. Named drafts stay outside Assets.
Legacy uniform Invoke drafts are historical only; do not treat their module count as recovered code.
Use native import/readback receipts for actual Prefab/Scene/resource coverage; business and Player are separate gates.
'''
    p=out/('Docs/CODE-STATUS.md' if current else 'Docs/AI-ENTRY.md');p.parent.mkdir(exist_ok=True);p.write_text(text);emitted.append(p.relative_to(out).as_posix())
    if any(sha(read(Path(r['path'])))!=r['sha256'] for r in job):fail('CODE_HANDOFF_SOURCE_CHANGED',str(root),'Module changed during static analysis')
    if apply:
        existing={r['path']:r for r in manifest['files']}
        for rel in emitted:
            dest=inside(root,rel)
            if rel in replaced:
                row=existing.get(rel)
                if not row or row.get('owner','generated')!='generated' or not dest.is_file() or sha(read(dest,max_bytes=128*1024**2))!=row['sha256']:
                    fail('CODE_HANDOFF_TARGET_CHANGED',rel,'Only an untouched generated draft can be replaced by its named draft')
            elif dest.exists()or rel in existing:fail('CODE_HANDOFF_TARGET_EXISTS',rel,'Additive handoff will not overwrite existing work')
        if sha(read(manifest_path,max_bytes=128*1024**2))!=identity:fail('CODE_HANDOFF_MANIFEST_CHANGED',str(root),'Candidate changed during source analysis')
        (out/'original-manifest.json').write_bytes(raw)
        for rel in emitted:
            src=out/rel;dest=inside(root,rel);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
            body=read(src,max_bytes=128*1024**2)
            if rel in existing:existing[rel].update(bytes=len(body),sha256=sha(body))
            else:manifest['files'].append(dict(path=rel,bytes=len(body),sha256=sha(body),owner='generated'))
        manifest['codeHandoff']=dict(toolVersion=__version__,sourceManifestSha256=identity,report='Analysis/Code/named-code-handoff.json',modules=len(entries),methodsImplemented=0)
        write_json(manifest_path,manifest)
    result=dict(status='partial',modules=len(entries),namedMethods=report['namedMembers'],fieldDeclarations=report['fieldDeclarations'],methodsImplemented=0,applied=apply,sourceExecuted=False,report=str(find_analysis(out,'named-code-handoff.json')))
    write_json(out/'handoff-result.json',result);return result
