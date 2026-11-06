"""Adapt the shared explicit-URL acquisition to Unity's typed input closure."""
from pathlib import Path
import shutil
from .io import safe,read,load,sha,inside,write_json,new_output
from .providers.assetripper import fingerprint
from .sources.compiled import fail
from .sources.unity_serialized import container_kind
from .unity_schemas import frozen_pool
from .layout.standard import find_analysis


def protected_inputs(source,dependencies,texture_cache,schema_manifest,dependency_manifest,provider_python,asset_ripper):
    source=safe(source);extras=list(map(safe,dependencies));provider=safe(asset_ripper);python=safe(Path(provider_python).resolve())
    if any(not p.is_file()for p in (source,*extras,provider,python)):
        fail('UNITY_PROVIDER_MISSING','$','Source, dependency and existing provider files are required before acquisition')
    protected=[source,*extras,provider.parent,python.parent]
    for manifest in (texture_cache,schema_manifest,dependency_manifest):
        if manifest:
            manifest=safe(manifest);protected.append(manifest)
            protected.extend(safe(manifest.parent/row['path']) for row in load(read(manifest))['files'])
    return protected


def prepare(source,output,manifest,cache_root,budget,protected):
    from .acquisition import prepare as prepare_remote
    source=safe(source)
    selection=dict(path=source,sha256=fingerprint(source),inputs=[dict(id='unity-source',path=source)])
    return prepare_remote(manifest,output,selection,cache_root,budget,protected,derive_input_set=False)


def merge(acquired,texture_cache=None,dependency_manifest=None,dependencies=()):
    """Exact paths and bytes only; no URL/filename guessing or source execution."""
    out=acquired['receipt'].parent
    receipt=load(read(acquired['receipt']))
    textures={}
    if texture_cache:
        manifest=safe(texture_cache)
        for row in load(read(manifest))['files']:
            logical=row['logicalPath']
            if logical in textures:fail('UNITY_ACQUIRED_TEXTURE_COLLISION',logical,'Duplicate local logical path')
            textures[logical]=dict(row,path=str(safe(manifest.parent/row['path'])))
    if dependency_manifest and dependencies:
        fail('UNITY_DEPENDENCY_OPTIONS','$','Choose either explicit dependency files or a frozen lookup pool')
    bundles=[]
    pool=frozen_pool(dependency_manifest)['files'] if dependency_manifest else None
    classified=[]
    for row in receipt['files']:
        if row['status'] not in ('local_verified','downloaded'):continue
        path=inside(acquired['filesRoot'],row['path'])
        payload=read(path,max_bytes=128*1024*1024)
        if sha(payload)!=row['sha256'] or len(payload)!=row['bytes']:
            fail('UNITY_ACQUIRED_SOURCE_CHANGED',row['path'],'Acquired bytes differ from receipt')
        logical=row['path']
        if logical.startswith('Assets/Textures/astc/'):
            # Actual source Texture2D dimensions/mip are checked again during hydration.
            from .sources.unity_worker import astc_header
            if len(payload)<16:fail('UNITY_ACQUIRED_TEXTURE_INVALID',logical,'ASTC header required')
            try:shape=astc_header(payload,int.from_bytes(payload[7:10],'little'),int.from_bytes(payload[10:13],'little'))
            except ValueError as error:fail('UNITY_ACQUIRED_TEXTURE_INVALID',logical,str(error))
            if min(shape['width'],shape['height'])<=0:fail('UNITY_ACQUIRED_TEXTURE_INVALID',logical,'Positive dimensions required')
            previous=textures.get(logical)
            if previous and (previous['sha256']!=row['sha256']or previous['bytes']!=row['bytes']):
                fail('UNITY_ACQUIRED_TEXTURE_COLLISION',logical,'Different bytes for the same source texture key; no override')
            textures[logical]=dict(path=str(path),logicalPath=logical,bytes=len(payload),sha256=row['sha256'])
            classified.append(dict(path=logical,disposition='explicit-astc-cache',header=shape))
        elif container_kind(payload[:16]):
            bundles.append(dict(path=str(path),bytes=len(payload),sha256=row['sha256']))
            classified.append(dict(path=logical,disposition='explicit-unity-dependency-container'))
        else:
            classified.append(dict(path=logical,disposition='source-evidence-only-no-source-adapter'))
    if textures:
        texture_cache=out/'unity-texture-cache.json'
        write_json(texture_cache,dict(schemaVersion=1,files=list(textures.values())))
    dependencies=list(map(str,dependencies))
    if pool is not None:
        seen={r['sha256']for r in pool}
        for row in bundles:
            if row['sha256']not in seen:pool.append(row);seen.add(row['sha256'])
        if len(pool)>2000 or sum(r['bytes']for r in pool)>1024*1024*1024:
            fail('UNITY_ACQUIRED_POOL_BUDGET','$','Combined frozen pool exceeds existing limits')
        dependency_manifest=out/'unity-dependency-pool.json'
        write_json(dependency_manifest,dict(schemaVersion=1,files=pool))
    else:
        for row in bundles:
            if row['path'] not in dependencies:dependencies.append(row['path'])
    acquired['classification']=classified
    write_json(out/'unity-inputs.json',dict(schemaVersion=1,classification=classified,textureCache=str(texture_cache)if texture_cache else None,
                                          dependencyManifest=str(dependency_manifest)if dependency_manifest else None,dependencies=dependencies,
                                          sourceCodeExecuted=False))
    return dict(texture_cache=texture_cache,dependency_manifest=dependency_manifest,dependencies=dependencies)


def attach(conversion,output,acquired):
    """Attach raw acquired evidence and sanitized receipts before native sealing."""
    from .unity_native import owned
    output=safe(output)
    record=output/'conversion-result.json'
    if load(read(record))!=conversion:fail('UNITY_ACQUIRED_CONVERSION_CHANGED',str(output),'Conversion receipt changed')
    receipt=load(read(acquired['receipt']))
    conversion['acquisition']=dict(acquired['summary'],classification=acquired['classification'])
    unknown=[r for r in acquired['classification']if r['disposition']=='source-evidence-only-no-source-adapter']
    if unknown:conversion['diagnostics'].append(dict(code='UNITY_ACQUIRED_EVIDENCE_ONLY',items=unknown))
    if acquired['summary']['missingFiles']:
        conversion['diagnostics'].append(dict(code='UNITY_ACQUIRED_DECLARATIONS_MISSING',count=acquired['summary']['missingFiles'],receipt=str(acquired['receipt'])))
    if conversion['completed']:
        for row in conversion['projects']:
            project=output/row['path']
            identity,_=owned(project)
            target_root=project/'SourceRecovery/Acquired'
            evidence=find_analysis(project,'acquisition.json')
            if target_root.exists() or evidence.exists():fail('UNITY_ACQUIRED_CONVERSION_CHANGED',str(project),'Acquisition evidence exists')
            staging=new_output(output/('AcquisitionAttachment-'+row['path']),[project,acquired['filesRoot']])
            staged_root=staging/'Acquired';staged_root.mkdir()
            manifest=load(read(project/'recovery-manifest.json',max_bytes=128*1024*1024))
            added=[]
            for entry in receipt['files']:
                if entry['status']not in ('local_verified','downloaded'):continue
                raw=read(inside(acquired['filesRoot'],entry['path']),max_bytes=128*1024*1024)
                if len(raw)!=entry['bytes'] or sha(raw)!=entry['sha256']:
                    fail('UNITY_ACQUIRED_SOURCE_CHANGED',entry['path'],'Acquired evidence changed before copy')
                dest=inside(staged_root,entry['path'])
                dest.parent.mkdir(parents=True,exist_ok=True)
                with dest.open('xb')as writer:writer.write(raw)
                added.append(dict(path='SourceRecovery/Acquired/'+entry['path'],bytes=len(raw),sha256=sha(raw)))
            staged_receipt=staging/'acquisition.json'
            write_json(staged_receipt,dict(receipt,classification=acquired['classification'],sourceCodeExecuted=False))
            added.append(dict(path='Analysis/Ledger/acquisition.json',bytes=staged_receipt.stat().st_size,sha256=fingerprint(staged_receipt)))
            if owned(project)[0]!=identity:fail('UNITY_ACQUIRED_CONVERSION_CHANGED',str(project),'Candidate changed before acquisition attachment')
            target_root.parent.mkdir(exist_ok=True)
            shutil.move(staged_root,target_root)
            evidence.parent.mkdir(parents=True,exist_ok=True);shutil.move(staged_receipt,evidence)
            manifest['files'].extend(added)
            manifest['acquisition']=conversion['acquisition']
            write_json(project/'recovery-manifest.json',manifest)
    write_json(record,conversion)
