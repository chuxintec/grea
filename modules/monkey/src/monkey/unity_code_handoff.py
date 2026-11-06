"""Preserve explicit IL2CPP declarations and original code as editable AI evidence.

Only parses text and hashes/copies files; no source code or DLL is executed.
Metadata declarations remain outside Assets and never count as recovered logic.
"""
import bisect
import re
import shutil
from pathlib import Path
from .io import safe,read,load,sha,write_json,inside
from .sources.compiled import fail
from .layout.standard import find_analysis

ROLES={'metadata','source-binary','source-package','source-script','il2cpp-declarations','dummy-assembly','semantic-snapshot','asset-evidence','native-media','recovery-source',
       'method-map','decoded-table-manifest','resource-alias-index','adapted-binary'}


def declared(manifest):
    p=safe(manifest);data=load(read(p));rows=data.get('files')
    if data.get('schemaVersion')!=1 or not isinstance(rows,list)or not 1<=len(rows)<=2000:fail('UNITY_CODE_EVIDENCE_SCHEMA',str(p),'Expected1..2000 frozen files')
    seen=set();total=0;result=[]
    for row in rows:
        path=safe(p.parent/row['path']);role=row.get('role')
        if role not in ROLES or path in seen:fail('UNITY_CODE_EVIDENCE_ENTRY',str(path),'Unknown role or duplicate path')
        seen.add(path);raw=read(path,max_bytes=128*1024**2);total+=len(raw)
        if len(raw)!=row.get('bytes')or sha(raw)!=row.get('sha256')or total>1024**3:fail('UNITY_CODE_EVIDENCE_CHANGED',str(path),'Frozen bytes or aggregate budget differ')
        result.append(dict(row,path=str(path)))
    originals={r['sha256'] for r in result if r['role']=='source-binary'}
    for row in result:
        if row['role']=='adapted-binary' and (row.get('derivedFromSha256') not in originals or row['derivedFromSha256']==row['sha256']):
            fail('UNITY_ADAPTED_PROVENANCE',row['path'],'Adapted binary requires a distinct original source-binary identity in this manifest')
    return p,data,result


def declarations(raw, root, assemblies):
    text=raw.decode('utf-8');images=[(int(m[2]),m[1])for m in re.finditer(r'^// Image [0-9]+: (.+) - ([0-9]+)\r?$',text,re.M)]
    starts=[x[0]for x in images]
    if not images or starts!=sorted(set(starts)):fail('UNITY_DECLARATION_IMAGES','$','Exact ordered Il2CppDumper image/type table required')
    markers=list(re.finditer(r'^// Namespace: ([^\r\n]*)\r?$',text,re.M));records=[];methods=0;fields=0
    for index,mark in enumerate(markers):
        end=markers[index+1].start()if index+1<len(markers)else len(text);block=text[mark.start():end]
        token=re.search(r'// TypeDefIndex: ([0-9]+)',block)
        if not token:continue
        type_id=int(token[1]);image_index=bisect.bisect_right(starts,type_id)-1
        if image_index<0:fail('UNITY_DECLARATION_TYPE','$','Type index precedes first assembly')
        assembly=images[image_index][1]
        if assembly not in assemblies:continue
        declaration=next((line.strip()for line in block.splitlines()if '// TypeDefIndex:'in line),'')
        signatures=[line.strip().split('{',1)[0].rstrip()for line in block.splitlines()
                    if re.match(r'^\s*(?!//|\[|#)[^;\r\n]*\([^;\r\n]*\)\s*(?:\{|;)\s*.*$',line)]
        field_lines=[line.strip()for line in block.splitlines()if re.search(r';\s*// 0x[0-9A-Fa-f]+\s*$',line)]
        methods+=len(signatures);fields+=len(field_lines)
        row=dict(assembly=assembly,typeDefIndex=type_id,namespace=mark[1],declaration=declaration,
                 sourceCharStart=mark.start(),sourceCharEnd=end,methods=len(signatures),fields=len(field_lines),methodBodies='TODO: not present in metadata declarations')
        if signatures or field_lines or re.search(r'\benum\b',declaration):
            folder=re.sub(r'[^A-Za-z0-9_.-]','_',assembly)
            dest=root/folder/(str(type_id)+'.cs.txt');dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text('// Metadata declaration draft; excluded from Unity compilation.\n// TODO: restore every method body from original code evidence; no business logic recovered here.\n'+block,encoding='utf-8')
            row.update(path=dest.relative_to(root.parent.parent).as_posix(),sha256=sha(read(dest,max_bytes=128*1024**2)),status='declaration-draft')
        else:row['status']='empty-original-declaration-indexed-not-generated'
        records.append(row)
    return dict(types=records,methods=methods,fields=fields,methodsImplemented=0)


def attach(manifest,project,overrides=None):
    manifest,data,rows=declared(manifest);out=project/'SourceRecovery/Code/Source';out.mkdir(parents=True,exist_ok=True)
    from .layout import LayoutPlanner
    planner=LayoutPlanner('unity',overrides=overrides)
    for existing in (project/'Assets').rglob('*'):
        if existing.is_file():planner.claim(existing.relative_to(project).as_posix())
    copied=[];drafts=[];total_methods=0;total_fields=0
    selected=data.get('assemblies',[])
    if not isinstance(selected,list)or any(not isinstance(n,str)or not re.fullmatch('[A-Za-z0-9_.-]+',n)for n in selected):fail('UNITY_CODE_ASSEMBLIES',str(manifest),'Explicit exact assembly names required')
    for row in rows:
        path=Path(row['path']);dest=inside(out,row['role']+'/'+row['sha256'][:16]+'-'+path.name);dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():shutil.copy2(path,dest)
        if sha(read(dest,max_bytes=128*1024**2))!=row['sha256']:fail('UNITY_CODE_COPY_CHANGED',str(dest),'Evidence copy differs')
        native=None
        if row['role']=='native-media':
            payload=read(path,max_bytes=128*1024**2);suffix=path.suffix.lower()
            good=(suffix=='.png'and payload.startswith(b'\x89PNG\r\n\x1a\n'))or(suffix in('.jpg','.jpeg')and payload.startswith(b'\xff\xd8'))or(suffix=='.mp3'and(payload.startswith(b'ID3')or len(payload)>1 and payload[0]==255 and payload[1]&224==224))
            if not good:fail('UNITY_MEDIA_FORMAT',str(path),'Declared native media signature differs; keep unrecognized bytes as evidence')
            target=planner.path(row['sha256'],'native',suffix,metadata=dict(bundle='',logicalPath=path.stem))
            native=inside(project,target);native.parent.mkdir(parents=True,exist_ok=True)
            if not native.exists():shutil.copy2(path,native)
            if sha(read(native,max_bytes=128*1024**2))!=row['sha256']:fail('UNITY_MEDIA_COPY_CHANGED',str(native),'Media copy differs')
        copied.append(dict(role=row['role'],sha256=row['sha256'],bytes=row['bytes'],path=dest.relative_to(project).as_posix(),nativePath=native.relative_to(project).as_posix()if native else None,nativeIdentity='pending-editor-import'if native else'not-applicable'))
        if row['role']=='adapted-binary':copied[-1]['derivedFromSha256']=row['derivedFromSha256']
        if row['role']=='il2cpp-declarations':
            recovered=declarations(read(path,max_bytes=128*1024**2),project/'SourceRecovery/Code/Drafts/Il2Cpp',selected)
            drafts.extend(recovered['types']);total_methods+=recovered['methods'];total_fields+=recovered['fields']
    report=dict(schemaVersion=1,manifestSha256=sha(read(manifest)),files=copied,types=drafts,declaredMethods=total_methods,declaredFields=total_fields,
                methodsImplemented=0,sourceCodeExecuted=False,compiled='not_run',scope='explicit original evidence and metadata declarations; no invented method bodies',
                adaptedBinaries=sum(r['role']=='adapted-binary' for r in copied),
                derivationProof='manifest-declared hash relationship only; adapted bytes are not original module bytes')
    write_json(find_analysis(project,'code-evidence-handoff.json'),report)
    return dict(files=len(copied),bytes=sum(r['bytes']for r in copied),typesIndexed=len(drafts),typeDraftFiles=sum(t['status']=='declaration-draft'for t in drafts),declaredMethods=total_methods,declaredFields=total_fields,methodsImplemented=0,report='Analysis/Code/code-evidence-handoff.json')
