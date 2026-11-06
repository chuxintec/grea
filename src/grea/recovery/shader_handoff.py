"""Read-only, bounded Shader evidence classification for frozen candidates."""
import collections
import re
from pathlib import Path
from .io import safe,inside,read,load,sha,new_output,write_json,encoded
from .sources.containers import relative
from .sources.compiled import fail
from .shader_content import classify

SCHEMA='monkey-shader-handoff/1'
SUFFIXES={'.shader','.hlsl','.cginc','.glsl','.vert','.frag','.compute','.shadergraph','.shadervariants','.spv','.dxbc','.dxil','.metallib'}
HEX=re.compile(r'^[0-9a-f]{64}$')


def shader_artifact(path,header):
    if not path.startswith('Assets/')or path.endswith('.meta'):return False
    if Path(path).suffix.lower()in SUFFIXES:return True
    kind=re.search(rb'^--- !u!([0-9]+) &',header,re.M)
    if kind:return kind[1]in(b'48',b'200')
    return any(p.casefold()in('shader','shaders')for p in path.split('/')[:-1])


def _pointer_id(value):
    return isinstance(value,str)and re.fullmatch(r'-?(0|[1-9][0-9]{0,18})',value)is not None and -(1<<63)<=int(value)<(1<<63)and str(int(value))==value


def classify_project(project,manifest,expected_manifest,output,source_mapping=None,expected_source_mapping=None):
    root=safe(project);owner_path=safe(manifest);owner_raw=read(owner_path,max_bytes=128*1024**2)
    if sha(owner_raw)!=expected_manifest:fail('SHADER_OWNER_IDENTITY',str(owner_path),'Frozen candidate manifest SHA differs')
    owner=load(owner_raw,max_nodes=16000000);declared=owner.get('files')
    if not isinstance(declared,list)or len(declared)>250000:fail('SHADER_OWNER_SCHEMA','$','Expected bounded owned file inventory')
    files={}
    for row in declared:
        path=relative(row['path'])
        if path in files or type(row.get('bytes'))is not int or row['bytes']<0 or not HEX.fullmatch(str(row.get('sha256',''))):fail('SHADER_OWNER_SCHEMA',path,'Duplicate path or missing frozen byte identity')
        files[path]=row
    mapping_path=None;mapping_raw=None;mapping=[]
    if source_mapping is not None:
        mapping_path=safe(source_mapping);mapping_raw=read(mapping_path,max_bytes=128*1024**2)
        if not expected_source_mapping or sha(mapping_raw)!=expected_source_mapping:fail('SHADER_MAPPING_IDENTITY',str(mapping_path),'Frozen source mapping SHA required')
        mapping=load(mapping_raw,max_nodes=16000000).get('sourceToTarget')
        if not isinstance(mapping,list)or len(mapping)>500000:fail('SHADER_MAPPING_SCHEMA','$','Expected bounded sourceToTarget array')
    elif expected_source_mapping is not None:fail('SHADER_MAPPING_IDENTITY','$','Expected mapping path with its SHA')
    selected=[];headers=0;other_types=0
    for path,row in files.items():
        if not path.startswith('Assets/')or path.endswith('.meta'):continue
        suffix=Path(path).suffix.lower();shader_path=any(p.casefold()in('shader','shaders')for p in path.split('/')[:-1])
        if suffix in SUFFIXES:selected.append(path)
        elif shader_path or suffix=='.asset':
            headers+=1
            if headers>20000:fail('SHADER_DISCOVERY_BUDGET','$','More than 20000 asset headers; supply a smaller frozen candidate inventory')
            with inside(root,path).open('rb')as stream:header=stream.read(1024)
            if shader_artifact(path,header):selected.append(path)
            elif shader_path:other_types+=1
    if len(selected)>5000:fail('SHADER_DISCOVERY_BUDGET','$','More than 5000 shader-related files')
    source_index=collections.defaultdict(list);selected_set=set(selected)
    for row in mapping:
        if not isinstance(row,dict):fail('SHADER_MAPPING_SCHEMA','$','Expected source association object')
        target=row.get('target')
        if isinstance(target,dict)and target.get('path')in selected_set:source_index[target['path']].append(row)
    pins={};total=0
    def owned_bytes(path,limit):
        nonlocal total
        entry=files[path]
        if entry['bytes']>limit:fail('SHADER_ASSET_BUDGET',path,'Asset exceeds bounded classification size')
        data=read(inside(root,path),max_bytes=limit);total+=len(data)
        if total>256*1024**2:fail('SHADER_TOTAL_BUDGET','$','Shader subset exceeds 256 MiB')
        if len(data)!=entry['bytes']or sha(data)!=entry['sha256']:fail('SHADER_ASSET_CHANGED',path,'Candidate asset differs from owner manifest')
        pins[path]=entry;return data
    items=[]
    for path in sorted(selected):
        raw=owned_bytes(path,16*1024**2);content=classify(raw,Path(path).suffix);meta=path+'.meta';meta_sha=None;guid=None;diagnostics=[]
        if meta in files:
            metadata=owned_bytes(meta,1024**2);meta_sha=sha(metadata);matches=re.findall(rb'^guid: ([0-9a-f]{32})\r?$',metadata,re.M)
            if len(matches)==1:guid=matches[0].decode()
            else:diagnostics.append('metadata-guid-missing-or-ambiguous')
        else:diagnostics.append('metadata-not-owned')
        ids=re.findall(rb'^--- !u![0-9]+ &(-?[0-9]{1,19})\r?$',raw,re.M)if raw.lstrip().startswith((b'%YAML',b'--- !u!'))else[]
        declared_ids=[int(i)for i in ids if -(1<<63)<=int(i)<(1<<63)and int(i)!=0]
        target=dict(guid=guid,localFileID=declared_ids[0])if guid and len(ids)==len(declared_ids)==1 else None
        entries=[];rejected=[]
        for association in source_index[path]:
            destination=association['target'];original=association.get('source',{})
            if destination.get('sha256')!=sha(raw)or destination.get('bytes')!=len(raw)or not guid or destination.get('guid')!=guid:
                rejected.append(dict(reason='source-map-target-byte-or-guid-mismatch',source=original));continue
            if not isinstance(original,dict)or not isinstance(original.get('file'),str)or not original['file']or not HEX.fullmatch(str(original.get('containerSha256','')))or not all(_pointer_id(original.get(k))for k in ('fileId','pathId'))or original['pathId']=='0':
                rejected.append(dict(reason='source-pointer-identity-unavailable',source=original));continue
            entry=dict(original)
            raw_sha=entry.get('rawSha256');entry['rawSha256']=raw_sha if isinstance(raw_sha,str)and HEX.fullmatch(raw_sha)else None
            entry['rawShaEvidence']='reported-in-frozen-map'if entry['rawSha256']else'unavailable-not-inferred'
            entry['identityScope']='assetbundle-container-pointer';entries.append(entry)
            if entry.get('fileId')!='0':diagnostics.append('source-external-pointer-not-resolved')
        identities={(r.get('containerSha256'),r.get('file'),r.get('fileId'),r.get('pathId'))for r in entries}
        mapping_status='inconsistent'if rejected else'ambiguous'if len(identities)>1 else'mapped-container-pointer'if entries else'unmapped'
        source=dict(ownerManifestSha256=expected_manifest,sourceMappingSha256=expected_source_mapping,mappingStatus=mapping_status,entries=entries,rejectedAssociations=rejected,
                    metaPath=meta if meta in files else None,metaSha256=meta_sha,declaredGuid=guid,declaredLocalFileIDs=declared_ids,
                    targetIdentityEvidence='serialized-declaration-only'if target else'unmapped-native-identity',nativeReadback='not_run',contentEvidence=content['evidence'],diagnostics=sorted(set(diagnostics)))
        classification=content['classification'];disposition='source-review'if classification=='source-text'else'evidence-only'if classification in('platform-compiled','recovered-binary')else'blocked'
        item=dict(path=path,bytes=len(raw),sha256=sha(raw),classification=classification,source=source,target=target,dialect=content['dialect'],
                  platformEvidence=[dict(kind='declared-source-platforms',values=content['platforms'],compatibilityVerified=False)]if content['platforms']else[],
                  nativeCompilation='not_run',runtimeDisposition=disposition)
        item['evidenceId']='shader-evidence:'+sha(encoded(item));items.append(item)
    for path,entry in pins.items():
        data=read(inside(root,path),max_bytes=16*1024**2)
        if len(data)!=entry['bytes']or sha(data)!=entry['sha256']:fail('SHADER_ASSET_CHANGED',path,'Shader subset changed during classification')
    if sha(read(owner_path,max_bytes=128*1024**2))!=expected_manifest or mapping_path and sha(read(mapping_path,max_bytes=128*1024**2))!=expected_source_mapping:
        fail('SHADER_INPUT_CHANGED','$','Frozen manifest or source mapping changed')
    out=new_output(output,[root,owner_path,*([mapping_path]if mapping_path else[])])
    handoff=dict(schema=SCHEMA,items=items);write_json(out/'handoff.json',handoff)
    report=dict(schemaVersion=1,status='classified',contract=SCHEMA,ownerManifestSha256=expected_manifest,sourceMappingSha256=expected_source_mapping,
                scope=dict(classifiedFiles=len(items),declaredFiles=len(files),assetHeadersRead=headers,otherSerializedTypesExcluded=other_types,shaderSubsetBytes=total,shaderSubsetUnchanged=True,wholeProjectBytesReaudited=False,
                           discovery='declared shader extensions/directories and serialized Shader/variant headers; other untyped binaries not inferred'),
                counts=dict(collections.Counter(r['classification']for r in items)),sourceMappingCounts=dict(collections.Counter(r['source']['mappingStatus']for r in items)),
                nativeCompilation='not_run',nativeImport='not_run',sourceCodeExecuted=False,projectWritten=False,
                handoffSha256=sha(read(out/'handoff.json')),handoff='handoff.json')
    write_json(out/'report.json',report);return dict(report,output=str(out))
