"""Account every original/acquired input in the self-contained Unity-source initial."""
from pathlib import Path
import shutil
from .io import safe,inside,read,load,sha,new_output,write_json
from .providers.assetripper import fingerprint
from .sources.compiled import fail
from .layout.standard import find_analysis,analysis_rel
from .unity_payloads import load_typed,validate_payloads


def freeze(candidate,texture_cache,source_manifest,source_root,output,expected_manifest):
    root=safe(candidate);pool_path=safe(texture_cache);original_manifest=safe(source_manifest);source_root=safe(source_root)
    from .unity_native import owned
    actual,files=owned(root)
    if actual!=expected_manifest:fail('UNITY_BULK_FREEZE_CHANGED',str(root),'Exact complete owned source candidate required')
    payload_files={}
    evidence=find_analysis(root,'unity-typed-objects.json').parent
    for typed_path in [find_analysis(root,'unity-typed-objects.json'),*sorted(evidence.glob('dependency-typed-*.json'))]:
        document=load_typed(typed_path)
        for record in validate_payloads(evidence,document):payload_files[record['path']]=record
    source=load(read(original_manifest));pool=load(read(pool_path));named=load(read(find_analysis(root,'code-evidence-handoff.json'),max_bytes=128*1024**2),max_nodes=16_000_000,max_depth=128)
    for rel in [*(analysis_rel(root,n) for n in ('initial-handoff.json','full-input-disposition.json','all-texture-inputs.json')),'Docs/BULK-INITIAL-HANDOFF.md']:
        if inside(root,rel).exists():fail('UNITY_BULK_FREEZE_EXISTS',rel,'No existing frozen/manual handoff overwritten')
    manifest_raw=read(root/'recovery-manifest.json',max_bytes=128*1024**2);manifest=load(manifest_raw,max_nodes=8_000_000)
    out=new_output(output,[root,pool_path,original_manifest,source_root]);(out/'original-recovery-manifest.json').write_bytes(manifest_raw)
    retained={};by_path={r['path']:r for r in files}
    for r in files:
        if r['path'].startswith('SourceRecovery/'):retained.setdefault(r['sha256'],[]).append(r['path'])
    texture_rows=[];pending=[]
    for row in pool['files']:
        path=safe(pool_path.parent/row['path']);target=inside(root,'SourceRecovery/TextureCache/'+row['logicalPath']);digest=fingerprint(path)
        if digest!=row['sha256']or path.stat().st_size!=row['bytes']:fail('UNITY_BULK_TEXTURE_CHANGED',row['logicalPath'],'Frozen cache changed')
        if target.exists():
            if fingerprint(target)!=digest:fail('UNITY_BULK_TEXTURE_TARGET_CHANGED',str(target),'Preserved raw texture changed')
            disposition='already-retained'
        else:pending.append((path,target));disposition='unreferenced-raw-retained'
        relative=target.relative_to(root).as_posix();retained.setdefault(digest,[]).append(relative)
        texture_rows.append(dict(logicalPath=row['logicalPath'],path=relative,bytes=row['bytes'],sha256=digest,disposition=disposition))
    original_rows=[]
    for row in source['files']:
        path=inside(source_root,row['path'])
        if row.get('status')!='frozen'or path.stat().st_size!=row['bytes']or fingerprint(path)!=row['sha256']:fail('UNITY_BULK_SOURCE_CHANGED',row['path'],'Original frozen source changed')
        candidates=sorted(set(retained.get(row['sha256'],[])))
        if not candidates:fail('UNITY_BULK_INPUT_NOT_RETAINED',row['path'],'No exact retained original byte evidence in project')
        original_rows.append(dict(sourcePath=row['path'],sourceRole=row['role'],bytes=row['bytes'],sha256=row['sha256'],evidencePaths=candidates,disposition='original-bytes-retained',nativeAssetCount='separate-resource-ledger'))
    write_json(out/'input-preview.json',dict(sourceFiles=len(original_rows),textureInputs=len(texture_rows),additionalRawCopies=len(pending),sourceManifestSha256=fingerprint(original_manifest)))
    # All identity/preexistence checks precede additive writes.
    for path,target in pending:target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    write_json(find_analysis(root,'full-input-disposition.json'),dict(schemaVersion=1,originalManifestSha256=fingerprint(original_manifest),files=original_rows,sourceCodeExecuted=False))
    write_json(find_analysis(root,'all-texture-inputs.json'),dict(schemaVersion=1,manifestSha256=fingerprint(pool_path),files=texture_rows))
    resources=load(read(find_analysis(root,'full-resource-handoff.json'),max_bytes=128*1024**2),max_nodes=16_000_000,max_depth=128)
    summary=dict(schemaVersion=1,status='editable-initial',previousManifestSha256=expected_manifest,targetVersion='6000.6.2f1',originalInputFiles=len(original_rows),acquiredTextureFiles=len(texture_rows),newlyRetainedUnusedTextures=len(pending),nativeResourceFiles=len(resources['nativeFiles']),uniqueNativeGuids=resources['uniqueNativeGuids'],uniqueNativeContentHashes=len({r['sha256']for r in resources['nativeFiles']}),nativeGuidPending=resources['nativeFilesWithoutGuid'],duplicateNativeGuids=len(resources['duplicateNativeGuids']),sourceObjects=resources['sourceObjects'],unparsedSourceObjects=resources['unparsedSourceObjects'],mappedOriginalEntries=sum(r['target']is not None for r in resources['sourceToTarget']),unmappedOriginalEntries=sum(r['target']is None for r in resources['sourceToTarget']),metadataTypesIndexed=len(named['types']),metadataDraftFiles=sum(r['status']=='declaration-draft'for r in named['types']),declaredMethods=named['declaredMethods'],declaredFields=named['declaredFields'],implementedMethods=0,validation=dict(editor='not_run',player='not_run',visual='not_run',business='not_run'),rawCopiesNotNativeAssets=True)
    summary.update(typedPayloadChunks=len(payload_files),typedPayloadBytes=sum(r['bytes']for r in payload_files.values()))
    summary.update(unresolvedAssetGuids=len(resources.get('unresolvedAssetGuids',[])),
                   unresolvedAssetReferences=resources.get('unresolvedAssetReferences',0))
    write_json(find_analysis(root,'initial-handoff.json'),summary)
    (root/'Docs/BULK-INITIAL-HANDOFF.md').write_text('''# Editable Unity6 initial handoff

Start with Analysis/Tasks/initial-handoff.json, full-resource-handoff.json, full-input-disposition.json and code-evidence-handoff.json.
Every frozen original source file and acquired texture has retained byte/hash evidence; unused textures remain raw inputs. Retained archives, schema copies and metadata declarations are not extra native assets.
Assets contains the one whole-pool AssetRipper export, signed-format source media and only proven nonempty schema C# fields. SourceRecovery retains original packages/code, all typed resource shards and named metadata declaration drafts; no method body is claimed implemented.
Large source Font.m_FontData and AssetBundle.m_PreloadTable may use UnityArrayChunks descriptors. All sealed chunks are under Analysis/Evidence/typed-data/ beside the typed JSON; preserve this complete closure. Ordinary references list inline PPtrs, while streamed table references must be read from their ordered, endian-tagged chunks. The typed document records parseLimits and parseUsage. These are development evidence, not a Player interpreter.
Exact source container paths map only to unique exported asset paths/GUIDs; unresolved mappings/references are explicit. Do not reuse by first matching name. Sprite localIDs/importer/Editor compilation and save/reload have not run for this candidate.
Original HTTP404 texture objects were quarantined from derived provider inputs, leaving original references unresolved; no placeholder pixels were fabricated. Source containers remain unchanged.
Runtime numeric configuration must use UTF-8 JSON as the sole editable source and be parsed at runtime. Raw binary/config evidence is retained; implement typed loaders without silent fallback before gameplay acceptance.
Open in Unity6000.6.2f1 for development; this is an initial recovery project with missing dependency/field/runtime work. Editor, Player, visuals and gameplay remain separate unrun gates.
''')
    with (root/'AGENTS.md').open('a')as f:f.write('\nStart bulk development with Docs/BULK-INITIAL-HANDOFF.md. Formal runtime numeric data is UTF-8 JSON as sole editable source; parse it at runtime. Raw source/config evidence is immutable, and unavailable logic is an explicit TODO.\n')
    manifest['bulkInitialHandoff']=summary;manifest['files']=[dict(path=p.relative_to(root).as_posix(),bytes=p.stat().st_size,sha256=fingerprint(p))for p in sorted(root.rglob('*'))if p.is_file()and p!=root/'recovery-manifest.json']
    write_json(root/'recovery-manifest.json',manifest)
    result=dict(status='frozen-initial',candidate=str(root),manifestSha256=fingerprint(root/'recovery-manifest.json'),files=len(manifest['files']),bytes=sum(r['bytes']for r in manifest['files']),summary=summary)
    write_json(out/'freeze-result.json',result);return result
