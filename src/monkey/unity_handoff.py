"""Count actual native files separately from source objects and retained evidence."""
import collections
import re
from pathlib import Path
from .io import read,load,sha,write_json
from .layout.standard import find_analysis
from .unity_payloads import load_typed


def reference_gaps(project):
    """Account missing YAML GUIDs, including code deliberately kept outside Assets."""
    project=Path(project);assets=project/'Assets';available=set();quarantined={}
    for root,excluded in ((assets,False),(project/'SourceRecovery/Code/Provider',True)):
        for path in root.rglob('*.meta'):
            match=re.search(rb'^guid: ([0-9a-f]{32})\r?$',read(path),re.M)
            if match:
                guid=match[1].decode()
                if excluded:quarantined[guid]=path.relative_to(project).as_posix()
                else:available.add(guid)
    missing=collections.defaultdict(collections.Counter)
    for path in assets.rglob('*'):
        if not path.is_file() or path.suffix not in ('.prefab','.unity','.asset','.mat','.controller','.overridecontroller','.anim','.mixer','.shadervariants'):continue
        raw=read(path,max_bytes=128*1024**2)
        if not raw.startswith(b'%YAML'):continue
        for guid in re.findall(rb'\bguid: ([0-9a-f]{32})\b',raw):
            guid=guid.decode()
            if guid in available or guid=='0'*32 or re.fullmatch(r'0{16}[ef]0{15}',guid):continue
            missing[guid][path.relative_to(project).as_posix()]+=1
    return [dict(guid=g,references=sum(paths.values()),paths=[dict(path=p,references=n) for p,n in sorted(paths.items())],
                 reason='quarantined-provider-code' if g in quarantined else 'unavailable-asset-or-package',
                 retainedMeta=quarantined.get(g)) for g,paths in sorted(missing.items())]


def inventory(project,inspections,exported,relocation=None):
    # Container paths name the provider export; relocated files are matched through their original export path.
    from .shader_handoff import shader_artifact
    from .shader_content import classify
    origin={new:old for old,new in (relocation or {}).items()}
    native=[];by_path={};guids=collections.defaultdict(list)
    for p in sorted((project/'Assets').rglob('*')):
        if not p.is_file()or p.suffix.lower()in ('.meta','.cs','.dll','.asmdef','.asmref','.js','.wasm'):continue
        rel=p.relative_to(project).as_posix();meta=p.with_suffix(p.suffix+'.meta')
        guid=None
        if meta.is_file():
            found=re.findall(rb'^guid: ([0-9a-f]{32})\r?$',read(meta),re.M)
            if len(found)==1:guid=found[0].decode()
        raw=read(p,max_bytes=128*1024**2)
        row=dict(path=rel,bytes=p.stat().st_size,sha256=sha(raw),guid=guid,kind=p.suffix.lower()or'extensionless',nativeImport='not_run')
        if shader_artifact(rel,raw[:1024]):
            content=classify(raw,p.suffix)if len(raw)<=16*1024**2 else dict(classification='unknown',dialect=None,platforms=[],evidence=[dict(code='SHADER_CLASSIFICATION_BUDGET',message='Content classification deferred; file exceeds 16 MiB')])
            category=content['classification']
            row['shaderEvidence']=dict(content,nativeCompilation='not_run',runtimeDisposition='source-review'if category=='source-text'else'evidence-only'if category in('platform-compiled','recovered-binary')else'blocked')
        native.append(row);by_path.setdefault(origin.get(rel,rel).casefold(),[]).append(row)
        if guid:guids[guid].append(row)
    roots=[];objects=0;unparsed=0;containers=[]
    for index,(source,receipt)in enumerate(inspections):
        stage=project.parent/('SourceInspection'if index==0 else'DependencyInspection-'+str(index-1));d=load_typed(stage/'typed-objects.json')
        files={f['id']:f for f in d['files']};objects+=len(d['objects']);unparsed+=sum(o['status']!='parsed'for o in d['objects'])
        containers.append(dict(source=receipt['source'],disposition='submitted-to-native-provider',nativeProviderStatus=exported['status']))
        for o in d['objects']:
            if o['type']!='AssetBundle'or o['status']!='parsed':continue
            for entry in o['data'].get('m_Container',[]):
                if not isinstance(entry,list)or len(entry)!=2 or not isinstance(entry[0],str):continue
                logical,value=entry;ptr=value.get('asset',{})if isinstance(value,dict)else{}
                original=dict(containerSha256=receipt['source']['sha256'],file=files[o['file']]['name'],pathId=ptr.get('pathId'),fileId=ptr.get('fileId'),logicalPath=logical)
                matches=by_path.get(logical.casefold(),[])
                roots.append(dict(source=original,status='exact-original-container-path-candidate'if len(matches)==1 and matches[0]['guid']else'unmapped-original-asset-path',
                                  target=matches[0]if len(matches)==1 and matches[0]['guid']else None))
    unique_roots={(r['source']['file'],r['source']['fileId'],r['source']['pathId'])for r in roots}
    counts=dict(collections.Counter(r['kind']for r in native));duplicates=[dict(guid=g,paths=[r['path']for r in rows])for g,rows in guids.items()if len(rows)>1]
    missing=reference_gaps(project)
    shader_rows=[r for r in native if 'shaderEvidence'in r]
    report=dict(schemaVersion=1,containers=containers,sourceObjects=objects,unparsedSourceObjects=unparsed,
                originalContainerEntries=len(roots),uniqueOriginalContainerReferences=len(unique_roots),sourceToTarget=roots,
                nativeFiles=native,uniqueNativeGuids=len(guids),nativeFilesWithoutGuid=sum(r['guid']is None for r in native),
                duplicateNativeGuids=duplicates,unresolvedAssetGuids=missing,unresolvedAssetReferences=sum(r['references'] for r in missing),counts=counts,native='not_run',business='not_run',
                shaderPolicy=dict(schema='monkey-shader-handoff/1',counts=dict(collections.Counter(r['shaderEvidence']['classification']for r in shader_rows)),nativeCompilation='not_run',
                                  defaultRuntimeAdoption='hold-all-unverified-shaders',requiresConsumerBuildFilter=True,assetFilesAreNotRuntimeApproval=True),
                mappingScope='Only unique exact original AssetBundle container path -> exported Assets path; no name-only fallback',
                sourceObjectCountIsNotNativeAssetCount=True)
    write_json(find_analysis(project,'full-resource-handoff.json'),report)
    start=project/'Docs/START-HERE.md'
    start.write_text('''# AI development handoff

This is a bulk Unity 6 editable resource candidate. Open ProjectSettings/ProjectVersion.txt's exact Editor version.
Read Analysis/Tasks/full-resource-handoff.json first: actual native files/GUIDs, original logical assets and unmapped items are separate.
SourceRecovery/Original retains every unique explicitly supplied container. Lookup/schema copies are evidence, not extra native assets.
Analysis/Evidence/all-typed-objects.json (when present) preserves exact source file/pathID, references and parsed fields across the full input set.
Analysis/Code/unity-code-model.json contains proven named field classes; SourceRecovery/Code/Source and Code/Drafts retain original code and metadata signatures/TODOs.
Analysis/Mappings/unity-relocation.json maps every provider export path to its monkey-project/2.0.0 location with the same GUID.
Metadata-only declarations do not contain recovered business logic; uncompiled drafts remain outside Assets. Do not count empty or unsupported methods as working behavior.
Repair missing script/package/Shader/Spine dependencies using their exact source identities. Never resolve collisions by first matching name or replace unknown logic with fake rewards.
Shader-related nativeFiles have content-based shaderEvidence and a hold/review runtimeDisposition. Platform binaries and recovered dumps are source evidence, not approved runtime Shader source. Even source-text is not_run for native compilation. Use the consumer build filter and native dependencies before adopting runtime assets; do not delete referenced evidence blindly.
Native import/compile, Editor save/reload, Player and gameplay are separate gates; current native state is not_run unless an independent receipt says otherwise.
''')
    return dict(nativeFiles=len(native),uniqueNativeGuids=len(guids),nativeCounts=counts,sourceObjects=objects,
                originalContainerEntries=len(roots),uniqueOriginalContainerReferences=len(unique_roots),mappedOriginalEntries=sum(r['target']is not None for r in roots),
                duplicateNativeGuids=len(duplicates),unresolvedAssetGuids=len(missing),unresolvedAssetReferences=sum(r['references'] for r in missing),
                report='Analysis/Tasks/full-resource-handoff.json',native='not_run')
