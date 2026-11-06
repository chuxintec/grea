"""Source-bound typed modules in a complete resource candidate, never a worktree edit."""
from pathlib import Path
import copy
import hashlib
import tempfile

from . import __version__
from .io import safe, inside, read, load, sha, encoded, write_json, new_output
from .sources.compiled import fail
from .candidate_snapshot import snapshot
from .output_limits import check_inventory, CHUNK_BYTES
from .owned_fs import RootReader

PROFILE = 'unity-6000.6.2f1-ugui'


def settings(source, contract=None, selectors=None, configuration_table=None):
    if (contract or selectors or configuration_table) and not source:
        fail('PACKAGE_MODULE_INPUT','$','Optional strict enhancement requires an exact --code-source')
    return dict(source=safe(source) if source else None, contract=safe(contract) if contract else None,
                selectors=safe(selectors) if selectors else None,
                configuration=safe(configuration_table) if configuration_table else None)


def prepare(spec, source_rows):
    """Prove source membership before lowering; same code path for fresh/frozen packages."""
    source=spec['source'];raw=read(source);digest=sha(raw)
    matches=[row['path'] for row in source_rows if row.get('sha256')==digest and row.get('bytes')==len(raw)]
    if not matches: fail('PACKAGE_MODULE_SOURCE_NOT_OWNED',source.name,'Exact original source must occur in this package/candidate inventory')
    contract_raw=read(spec['contract'],max_bytes=128*1024) if spec['contract'] else None
    roots=load(read(spec['selectors'],max_bytes=64*1024)) if spec['selectors'] else None
    evidence=None
    if roots is not None:
        from .code_type_evidence import extract_type_evidence
        evidence=extract_type_evidence(source,roots,load(contract_raw) if contract_raw else None,namespace=None if contract_raw else 'Game.Domain.Recovered')
        if evidence['status'] not in ('ready','selected_ready'):
            fail('PACKAGE_MODULE_TYPE_EVIDENCE',source.name,'Type/dependency evidence incomplete; run code-types for the fillable contract: '+str(evidence.get('diagnostics',[])[:3]))
        contract_raw=encoded(evidence['contract'])
    from .code_selection import select_modules
    contract=load(contract_raw)
    if roots is None:
        roots=[dict(classId=m['classId'],methodId=f['id']) for m in contract.get('modules',[]) for f in m.get('methods',[])]
    selected=select_modules(source,roots,contract)
    if selected['status']!='selected_ready':
        fail('PACKAGE_MODULE_SELECTION',source.name,'Selection is blocked: '+str(selected['diagnostics'][:3]))
    from .code_modules import prepare as prepare_modules
    with tempfile.TemporaryDirectory(prefix='monkey-package-modules-') as tmp:
        path=Path(tmp).resolve()/'contract.json';write_json(path,selected['contract'])
        generated=prepare_modules(source,path,spec['configuration'])
    generated.update(sourceMembers=matches,selection=selected,typeEvidence=evidence)
    return generated


def install(prepared, project, manifest):
    """Compose generated code and evidence into a new owned resource project."""
    project=safe(project)
    if manifest.get('targetProfile')!=PROFILE:
        fail('PACKAGE_MODULE_TARGET',str(project),'Typed C# module assembly targets Unity6 only')
    files=dict(prepared['files']);files.pop('AGENTS.md',None);files.pop('Docs/START-HERE.md',None)
    existing={p.relative_to(project).as_posix().casefold():p.relative_to(project).as_posix() for p in project.rglob('*') if p.is_file()}
    reused=[]
    for rel,raw in files.items():
        other=existing.get(rel.casefold())
        if other is not None:
            if other!=rel or read(inside(project,rel),max_bytes=512*1024**2)!=raw:
                fail('PACKAGE_MODULE_COLLISION',rel,'Existing resources/manual code cannot be replaced by module assembly')
            reused.append(rel)
    source_report=prepared['report']
    mapping_names=['resource-paths.json','source-map.json','cocos-assets.json','config.json','component-code-bindings.json','structured-objects.json','agent-work.json','editor-readback.json']
    from .layout.standard import find_analysis
    maps={}
    for name in mapping_names:
        path=find_analysis(project,name)
        if path.is_file(): maps[name]=dict(path=path.relative_to(project).as_posix(),sha256=sha(read(path,max_bytes=128*1024**2)))
    module_report=dict(schemaVersion=1,kind='package-typed-modules-v1',source=source_report['source'],
        sourceMembers=prepared['sourceMembers'],contractSha256=source_report['contractSha256'],
        coverage=source_report['coverage'],methods=source_report['methods'],configuration=source_report.get('configuration'),
        sourceExecuted=False,sourceResourceMappings=maps,dependencies=copy.deepcopy(prepared['requests']),
        sourceComponentBinding='not_automatically_recovered; indexed original component bindings remain authoritative',
        validation=dict(compile='not_run_for_composed_project',behavior='reuse_only_with_exact_code_identity',editor='not_run_for_composed_project'),
        selection=dict(requested=prepared['selection'].get('requested',[]),autoAdded=prepared['selection'].get('autoAdded',[])),
        fileStates=[dict(path=p,status='identical_resource_reused' if p in reused else 'generated',sha256=sha(v),bytes=len(v))for p,v in sorted(files.items())])
    # Dependencies carry only IDs/fingerprints/paths, never in-memory payloads.
    for request in module_report['dependencies']: request.pop('reusableFiles',None)
    files['Analysis/Code/package-modules.json']=encoded(module_report)
    if prepared['typeEvidence'] is not None: files['Analysis/Code/type-evidence.json']=encoded(prepared['typeEvidence'])
    new_ids={}
    import re
    old_ids={row['id']:row['path'] for row in manifest.get('assignedAssetIdentities',[])}
    for rel,raw in files.items():
        if not rel.startswith('Assets/') or not rel.endswith('.meta'): continue
        found=re.findall(rb'^guid: ([0-9a-f]{32})\r?$',raw,re.M)
        if len(found)!=1: fail('PACKAGE_MODULE_META',rel,'Generated asset requires one stable GUID')
        identity=found[0].decode();target=rel[:-5]
        if (identity in old_ids and old_ids[identity]!=target) or (identity in new_ids and new_ids[identity]!=target):
            fail('PACKAGE_MODULE_GUID_COLLISION',rel,'Generated script/config GUID collides with a resource identity')
        new_ids[identity]=target
    docs=['# Recovered modules in this resource candidate','',
          'Generated C# is already installed under Assets/Game/Domain/Recovered; do not copy it from a separate workspace.',
          'Source method bodies, explicit types/call domains and unselected methods: Analysis/Code/code-modules.json and source-method-index.json.',
          'Resource/config/component mappings and dependencies: Analysis/Code/package-modules.json.',
          'Original constructors, entity lifecycle and unresolved source components are not restored by ordinary domain classes.',
          'SourceRecovery remains excluded from compilation. Do not connect missing methods or drafts to normal gameplay.',
          'Original numeric JSON remains the runtime source. Explicit module state/config initialization is required before calling entry methods.',
          'Use beaver for adoption into a human worktree; this command writes only a new monkey candidate.',
          'Compile/import/behavior of this assembled project are separate gates; prior evidence only applies to byte-identical artifacts.','']
    files['Docs/RECOVERED-MODULES.md']='\n'.join(docs).encode()
    start=project/'Docs/START-HERE.md'
    start_raw=read(start) if start.exists() else b'# Recovery start\n'
    files['Docs/START-HERE.md']=start_raw+b'\nRecovered C# modules are included: [entry, source and unresolved bindings](RECOVERED-MODULES.md).\n'
    previous_rows={row['path']:row for row in manifest.get('files',[])}
    for rel,raw in files.items():
        if rel not in reused and rel in existing.values() and rel!='Docs/START-HERE.md':
            fail('PACKAGE_MODULE_COLLISION',rel,'Reserved module handoff path already exists in the resource base')
        if previous_rows.get(rel,{}).get('owner')=='manual':
            fail('PACKAGE_MODULE_MANUAL',rel,'Human-owned files cannot be changed during candidate assembly')
    for rel,raw in files.items():
        if rel in reused: continue
        dest=inside(project,rel);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    manifest['codeModules']=dict(schemaVersion=1,kind='package-typed-modules-v1',report='Analysis/Code/package-modules.json',
        sourceSha256=source_report['source']['sha256'],contractSha256=source_report['contractSha256'],implementedMethods=source_report['coverage']['implementedMethods'],
        moduleIds=[r['id']for r in prepared['requests'] if r['id']not in ('RecoveryTypes','SourceEvidence','RecipeJsonConfiguration')],
        files=sorted(files),sourceResourceMappings=maps,sourceComponentBinding=module_report['sourceComponentBinding'])
    return files


def assemble(candidate, expected_manifest_sha256, output, spec):
    """One public convert route reuses frozen resources without decoding or Editor startup."""
    root,manifest,rows,digest=snapshot(candidate)
    if digest!=expected_manifest_sha256: fail('PACKAGE_MODULE_BASE_CHANGED',str(root),'Frozen resource candidate manifest differs')
    if manifest.get('targetProfile')!=PROFILE: fail('PACKAGE_MODULE_TARGET',str(root),'Typed module composition targets Unity6')
    if manifest.get('codeModules'): fail('PACKAGE_MODULE_ALREADY_ASSEMBLED',str(root),'Use the original frozen resource base; regeneration of a composed project requires an explicit conflict plan')
    prepared=prepare(spec,list(rows.values())) if spec['contract'] or spec['selectors'] else None
    inputs=[root]+([spec['source']] if spec['source'] else [])+[p for p in (spec['contract'],spec['selectors'],spec['configuration']) if p]
    out=new_output(output,inputs);project=out/'UnityProject';project.mkdir()
    allowed=set(rows)|{manifest['_manifestName']}
    for path in root.rglob('*'):
        if path.is_symlink(): fail('SYMLINK_PATH',str(path),'Frozen candidate contains a symbolic link')
        if path.is_file() and path.relative_to(root).as_posix() not in allowed:
            fail('CANDIDATE_UNOWNED',path.relative_to(root).as_posix(),'Freeze native results first; unowned cache/manual files are not imported')
    with RootReader(root) as view:
        for rel,row in rows.items():
            dest=inside(project,rel);dest.parent.mkdir(parents=True,exist_ok=True)
            h=hashlib.sha256();size=0
            with view.open(rel) as src,dest.open('xb') as dst:
                for chunk in iter(lambda:src.read(CHUNK_BYTES),b''):
                    size+=len(chunk)
                    if size>row['bytes']:fail('CANDIDATE_DRIFT',rel,'Owned resource grew during composition')
                    h.update(chunk);dst.write(chunk)
            if size!=row['bytes'] or h.hexdigest()!=row['sha256']:fail('CANDIDATE_DRIFT',rel,'Owned resource changed during composition')
    m=copy.deepcopy(manifest);m.pop('_manifestName',None)
    changes=install(prepared,project,m) if prepared else {}
    draft_specs=prepare_drafts_for_candidate(root,rows,spec['source'],manifest=manifest)
    changes.update(install_drafts(draft_specs,project,m))
    inventory={rel:dict(row)for rel,row in rows.items()}
    for rel,raw in changes.items():inventory[rel]=dict(path=rel,sha256=sha(raw),bytes=len(raw),owner='generated')
    m.update(schemaVersion=1,toolVersion=__version__,files=sorted(inventory.values(),key=lambda r:r['path']),resultKind='candidate',status='partial',
             resourceBase=dict(manifestSha256=digest,copiedFiles=len(rows),bytes=sum(row['bytes']for row in rows.values()),mode='exact_frozen_resources_no_redecode'))
    m['limits']=check_inventory(m['files'],m,str(project))
    # Existing native proof applies only to unchanged resource assets, not the new assembly.
    m['validation']=dict(editor='not_run_for_composed_project',compiled='not_run_for_composed_project',behavior='not_run_for_composed_project')
    from .identities import assigned
    assigned(project,m);write_json(project/'manifest.json',m)
    if sha(read(root/manifest['_manifestName'],max_bytes=128*1024**2))!=digest:fail('PACKAGE_MODULE_BASE_CHANGED',str(root),'Frozen base manifest changed during composition')
    report=dict(schemaVersion=1,toolVersion=__version__,mode='package-module-assembly',status='partial',workflowStatus='partial',completed=True,resultKind='candidate',
        resourceBase=m['resourceBase'],codeModules=m.get('codeModules'),codeDrafts=m['codeDrafts'],sourceExecuted=False,editorStarted=False,
        projects=[dict(path='UnityProject',targetProfile=PROFILE,manifestSha256=sha(read(project/'manifest.json',max_bytes=128*1024**2)))],
        nextAction=dict(code='REVIEW_COMPOSED_CANDIDATE',message='Use package-modules.json for implemented methods and exact resource/component gaps; compile/import before adoption'))
    write_json(out/'conversion-result.json',report)
    (out/'README.md').write_text('# Composed Unity candidate\n\nOpen UnityProject/; recovered modules and frozen resources are together. Read Docs/START-HERE.md.\n',encoding='utf-8')
    return report


def freeze_native_resources(candidate, expected_manifest_sha256, expected_readback_sha256, output):
    """Seal an existing native import as a fresh complete inventory, without an Editor.

    Old owned bytes remain authoritative unless an exact pinned Editor nativeFiles
    record proves the saved asset. Editor-only settings and folder metadata are
    retained explicitly; they are not promoted to recovered source behavior.
    """
    root,manifest,owned,pin=snapshot(candidate)
    if pin!=expected_manifest_sha256 or manifest.get('targetProfile')!=PROFILE:
        fail('RESOURCE_FREEZE_BASE',str(root),'Exact Unity candidate owning manifest required')
    from .layout.standard import find_analysis
    rb_path=find_analysis(root,'editor-readback.json');raw=read(rb_path,max_bytes=128*1024**2)
    if sha(raw)!=expected_readback_sha256:fail('RESOURCE_FREEZE_READBACK_CHANGED',str(rb_path),'Expected pinned saved Editor readback')
    rb=load(raw,max_nodes=8_000_000)
    from .layout import standard
    from .native_readback_contract import saved_readback_admission
    instruction=load(read(root/standard.locate(manifest,'importPlan'),max_bytes=128*1024**2),max_nodes=8_000_000)
    admission=saved_readback_admission(rb,gallery=instruction.get('galleryOnly')is True,
        expected_plan_sha256=sha(read(root/standard.locate(manifest,'importPlan'))),
        expected_source_manifest_sha256=instruction.get('sourceManifestSha256'))
    if not admission['valid']:
        fail('RESOURCE_FREEZE_READBACK',str(rb_path),'Saved readback admission failed: '+
             '; '.join(row['field'] for row in admission['issues']))
    # Resource retention and source acceptance are different consumers. Retain a
    # current full verification report, including every unresolved limitation.
    from .targets.unity import verify as verify_unity
    from .unity_verification_contract import unresolved_diagnostics
    with tempfile.TemporaryDirectory(prefix='monkey-resource-verification-',dir=Path(tempfile.gettempdir()).resolve())as temporary:
        verify_unity(root,Path(temporary)/'verification',level='editor')
        source_verification=load(read(Path(temporary)/'verification/verification.json'),max_nodes=8_000_000)
    current=unresolved_diagnostics(source_verification.get('diagnostics',[]),source_verification.get('componentCoverage',{}))
    dimensions=('staticValidation','nativeStaticValidation','staticPresentationValidation')
    validation_gaps=[dict(code=row.get('code'),sourceId=row.get('sourceId'),message=row.get('message'))for row in current['blocking']]
    validation_gaps.extend(dict(code='RESOURCE_SOURCE_VALIDATION_INCOMPLETE',dimension=key,status=source_verification.get(key))
                           for key in dimensions if source_verification.get(key)!='pass')
    native={}
    for row in rb.get('nativeFiles',[]):
        rel=row.get('path');inside(root,rel)
        if not rel.startswith('Assets/') or rel in native:
            fail('RESOURCE_FREEZE_NATIVE_PATH',str(rel),'Unique root-relative Assets identity required')
        native[rel]=row['sha256']
    if not native:fail('RESOURCE_FREEZE_NATIVE_FILES',str(rb_path),'Readback has no exact native file identities')
    published={'Assets','Packages','ProjectSettings','Analysis','Docs','SourceRecovery'};paths=set(owned);paths.add(rb_path.relative_to(root).as_posix())
    for folder in published:
        for path in (root/folder).rglob('*'):
            if path.is_symlink():fail('SYMLINK_PATH',str(path),'Published native input contains a symbolic link')
            if path.is_file():paths.add(path.relative_to(root).as_posix())
    out=new_output(output,[root]);files=[];retained=[];counts=dict(native=0,original=0,retainedEditorState=0)
    with RootReader(root) as view:
        for rel in sorted(paths):
            previous=owned.get(rel);proof=native.get(rel)
            folder_meta=rel.startswith('Assets/') and rel.endswith('.meta') and (root/rel[:-5]).is_dir()
            editor_state=(rel.startswith('ProjectSettings/') or rel=='Packages/packages-lock.json' or rel.startswith('Analysis/Readback/') or folder_meta)
            capture_settings=rel.startswith('ProjectSettings/') and (previous or {}).get('owner')!='manual'
            expected=proof or (None if capture_settings else (previous or {}).get('sha256'))
            if expected is None and not editor_state:
                fail('RESOURCE_FREEZE_UNOWNED',rel,'Unlisted code/assets are not accepted without a native file identity')
            target=inside(out,rel);target.parent.mkdir(parents=True,exist_ok=True);digest=hashlib.sha256();size=0
            with view.open(rel) as src,target.open('xb') as dst:
                for chunk in iter(lambda:src.read(CHUNK_BYTES),b''):
                    size+=len(chunk)
                    if size>512*1024**2:fail('OUTPUT_FILE_BUDGET',rel,'Frozen file exceeds the shared file budget')
                    digest.update(chunk);dst.write(chunk)
            actual=digest.hexdigest()
            if expected is not None and actual!=expected:fail('RESOURCE_FREEZE_DRIFT',rel,'Saved/current bytes differ from the original or native readback identity')
            if previous and proof is None and not capture_settings and size!=previous['bytes']:fail('RESOURCE_FREEZE_DRIFT',rel,'Original owned byte length changed')
            if rel=='ProjectSettings/ProjectVersion.txt' and b'm_EditorVersion: 6000.6.2f1' not in read(target,max_bytes=65536):
                fail('RESOURCE_FREEZE_EDITOR_VERSION',rel,'Captured Editor version must match the exact readback target')
            state='native' if proof else 'original' if previous and not capture_settings else 'retainedEditorState';counts[state]+=1
            owner='retained' if state=='retainedEditorState' else (previous or {}).get('owner','generated')
            files.append(dict(path=rel,bytes=size,sha256=actual,owner=owner))
            if state=='retainedEditorState':retained.append(dict(path=rel,sha256=actual,bytes=size,validation='retained_current_editor_state;not_independent_native_proof',previousSha256=(previous or {}).get('sha256')))
    missing=set(native)-paths
    if missing:fail('RESOURCE_FREEZE_NATIVE_MISSING',str(sorted(missing)[:3]),'Native readback file no longer exists')
    verification_path='Analysis/Code/resource-source-verification.json'
    if verification_path in paths:fail('RESOURCE_FREEZE_EXISTS',verification_path,'Never overwrite an earlier resource verification')
    write_json(out/verification_path,source_verification)
    verification_file=out/verification_path
    files.append(dict(path=verification_path,bytes=verification_file.stat().st_size,sha256=sha(read(verification_file)),owner='generated'))
    proof=dict(schemaVersion=1,contract='monkey-resource-inventory-seal/1',sourceManifestSha256=pin,nativeReadbackSha256=sha(raw),counts=counts,retainedEditorState=retained,
               purpose='resource-inventory-for-module-composition',sourceAcceptance='not_granted',
               sourceVerificationPath=verification_path,sourceVerificationSha256=sha(read(verification_file)),
               nativeReadbackStatus=rb['status'],verificationScope=admission['scope'],validationGaps=validation_gaps,
               editorStarted=False,sourceExecuted=False,validation='Saved resource inventory sealed; current verifier result retained; selection approval and Player not granted')
    path='Analysis/Code/resource-freeze.json';write_json(out/path,proof);f=out/path
    if path in paths:fail('RESOURCE_FREEZE_EXISTS',path,'Never overwrite an earlier native freeze')
    files.append(dict(path=path,bytes=f.stat().st_size,sha256=sha(read(f)),owner='generated'))
    m=copy.deepcopy(manifest);m.pop('_manifestName',None);m.update(toolVersion=__version__,files=files,resourceFreeze=proof,status='partial'if validation_gaps else manifest.get('status','candidate'))
    m['limits']=check_inventory(files,m,str(out))
    from .identities import assigned
    assigned(out,m);write_json(out/'manifest.json',m)
    if sha(read(root/manifest['_manifestName'],max_bytes=128*1024**2))!=pin or sha(read(rb_path,max_bytes=128*1024**2))!=sha(raw):
        fail('RESOURCE_FREEZE_INPUT_CHANGED',str(root),'Input manifest/readback changed during freezing')
    return dict(status='frozen_native_resources',workflowStatus='partial'if validation_gaps else'sealed',sourceAcceptance='not_granted',validationGaps=validation_gaps,candidate=str(out),manifestSha256=sha(read(out/'manifest.json',max_bytes=128*1024**2)),files=len(files),nativeFiles=counts['native'],retainedEditorState=counts['retainedEditorState'],editorStarted=False)


def prepare_drafts(sources, *, reuse=None):
    """Full export is independent of strict typing/profile enhancement."""
    from .code_drafts import prepare as prepare_source
    batch=[];seen={}
    for path,member in sources:
        raw=read(path);identity=sha(raw)
        if identity in seen:
            seen[identity]['sourceMembers'].append(member);continue
        try:
            result=dict(reuse[identity],source=path) if reuse and identity in reuse else prepare_source(path,expected_source_sha256=identity)
            result.setdefault('stageReuse',dict(mode='fresh_static_parse',parserExecuted=True))
        except Exception as error:
            # One file cannot cancel other sources. Exact source remains beside
            # the failed draft so an Agent can repair the parse/transcription.
            from .sources.compiled import ParseError
            if not isinstance(error,(ParseError,ValueError,RecursionError)):raise
            digest=identity[:12];source_rel='SourceRecovery/Code/Source/'+digest+'/Source.js';draft='SourceRecovery/CSharp/'+digest+'/ParseFailure.cs'
            reason=getattr(error,'code',type(error).__name__)
            body='// Full-source parse/transcription failed: '+reason+'\n#error Repair this source transcription using the adjacent exact source\n/*\n'+raw.decode('utf-8',errors='replace').replace('*/','* /')+'\n*/\n'
            report_path='Analysis/Code/Drafts/'+digest+'/csharp-drafts.json'
            report=dict(schemaVersion=1,status='parse_failed_source_retained',source=dict(sha256=identity,bytes=len(raw)),diagnostics=[dict(code=reason)],diagnosticCount=1,sourcePath=source_rel,reportPath=report_path,draftRoot='SourceRecovery/CSharp/'+digest,methodsExported=0,coverageUnknown=True,sourceExecuted=False)
            result=dict(files={source_rel:raw,draft:body.encode(),report_path:encoded(report)},report=report,source=path)
        result['sourceMembers']=[member];batch.append(result);seen[identity]=result
    return batch


def cached_drafts(root,manifest,rows):
    """Reuse exact generated source stages, never trusting only a success marker.

    The caller pins the owning manifest. Every returned payload is independently
    checked against that inventory, including compact indices and detail shards.
    A changed generator is a cold stage, while dirty or manual payloads fail.
    """
    from .code_drafts import _signature
    metadata=manifest.get('codeDrafts') or {}
    report_path=metadata.get('report')
    if not report_path:return {}
    def checked(rel):
        row=rows.get(rel)
        if row is None or row.get('owner')!='generated':fail('PACKAGE_DRAFT_CACHE_OWNER',str(rel),'Cached draft must have exact generated ownership')
        raw=read(inside(root,rel),max_bytes=row['bytes'])
        if len(raw)!=row['bytes'] or sha(raw)!=row['sha256']:fail('PACKAGE_DRAFT_CACHE_DRIFT',rel,'Cached draft content differs from owning manifest')
        return raw
    summary=load(checked(report_path));signature=_signature();result={}
    for item in summary.get('sources',[]):
        if item.get('generatorSignature')!=signature:continue
        report_rel=item['reportPath'];raw_report=checked(report_rel);r=load(raw_report,max_nodes=8_000_000)
        identity=item['source']['sha256']
        if r.get('source')!=item['source']:fail('PACKAGE_DRAFT_CACHE_IDENTITY',report_rel,'Cached source identity differs from package summary')
        paths={r['sourcePath'],report_rel,r['documentationPath']}
        paths.update(row['targetPath']for row in r['classes'])
        paths.update(row['path']for row in r['details'])
        payloads={p:checked(p)for p in sorted(paths)}
        if sha(payloads[r['sourcePath']])!=identity:fail('PACKAGE_DRAFT_CACHE_IDENTITY',r['sourcePath'],'Cached original source differs')
        result[identity]=dict(files=payloads,report=r,generatorSignature=signature,
            stageReuse=dict(mode='verified_full_draft_stage',parserExecuted=False,reportSha256=sha(raw_report),verifiedFiles=len(payloads)))
    return result


def prepare_drafts_for_candidate(root,rows,explicit_source=None,*,manifest=None):
    sources=[]
    for rel,row in rows.items():
        if rel.endswith('.js') and (rel.startswith('SourceRecovery/Code/Source/') or rel.startswith('SourceRecovery/Original/')) and '/Emission/' not in rel:
            sources.append((inside(root,rel),rel))
    if explicit_source:
        identity=sha(read(explicit_source));matches=[rel for rel,row in rows.items() if row.get('sha256')==identity]
        if not matches:fail('PACKAGE_MODULE_SOURCE_NOT_OWNED',str(explicit_source),'Exact source must belong to the resource candidate')
        if identity not in {rows[member]['sha256'] for _,member in sources}:
            sources.append((explicit_source,matches[0]))
    return prepare_drafts(sources,reuse=cached_drafts(root,manifest,rows) if manifest else None)


def install_drafts(batch,project,manifest):
    changes={};reports=[]
    for item in batch:
        for rel,raw in item['files'].items():
            if rel in ('AGENTS.md','Docs/START-HERE.md'):continue
            previous=changes.get(rel)
            if previous is not None and previous!=raw:fail('PACKAGE_DRAFT_COLLISION',rel,'Source partitions must not collide')
            target=inside(project,rel)
            if target.exists() and read(target,max_bytes=512*1024**2)!=raw:fail('PACKAGE_DRAFT_COLLISION',rel,'Never overwrite resource/manual files with a draft')
            changes[rel]=raw
        r=item['report']
        reports.append(dict(source=r.get('source'),sourceMembers=item['sourceMembers'],reportPath=r.get('reportPath'),coverage=r.get('coverage'),status=r.get('status'),generatorSignature=item.get('generatorSignature'),stageReuse=item.get('stageReuse'),diagnostics=r.get('diagnosticCount',(r.get('coverage') or {}).get('diagnosticCount',len(r.get('diagnostics',[]))))))
    summary=dict(schemaVersion=1,kind='full-csharp-drafts-v1',sourceFiles=len(batch),sources=reports,sourceExecuted=False,
                 quality='approximate_source_transcription;syntax_and_API_errors_allowed;not_compiled_or_equivalent',
                 sourceComponentBinding='Original mapping is retained; draft components and API mappings require game developer repair',
                 resources='Analysis/Mappings/resource-paths.json',configuration='Analysis/Mappings/config.json',componentBindings='Analysis/Code/component-code-bindings.json')
    changes['Analysis/Code/package-csharp-drafts.json']=encoded(summary)
    changes['Docs/CSHARP-DRAFTS.md']=b'# Full C# drafts\n\nSourceRecovery/CSharp contains actual best-effort C# source, excluded from Unity compilation. Syntax/type/API errors are repair tasks, not export blockers. Read Analysis/Code/package-csharp-drafts.json for each original source and method mapping. Keep source JSON/config/resource maps and saved Scene/Prefab identities together. Strict compiled modules, if present, are an enhancement and do not replace these full drafts. Use beaver/game developers for adoption and repair. No original code/runtime executes.\n'
    start=project/'Docs/START-HERE.md';start_raw=changes.get('Docs/START-HERE.md') or (read(start) if start.exists() else b'# Recovery start\n')
    changes['Docs/START-HERE.md']=start_raw+b'\nFull C# drafts are included: [coverage, quality and repair entry](CSHARP-DRAFTS.md).\n'
    previous_rows={r['path']:r for r in manifest.get('files',[])}
    previous_drafts=set((manifest.get('codeDrafts') or {}).get('files',[]))
    for rel,raw in changes.items():
        target=inside(project,rel)
        row=previous_rows.get(rel)
        if row and row.get('owner')=='manual':
            fail('PACKAGE_DRAFT_MANUAL',rel,'Human-owned files cannot be changed during draft assembly')
        if target.exists() and read(target,max_bytes=512*1024**2)!=raw:
            if rel!='Docs/START-HERE.md' and (rel not in previous_drafts or not row or row.get('owner')!='generated'):
                fail('PACKAGE_DRAFT_COLLISION',rel,'Draft reports cannot overwrite unknown resource files')
    for rel,raw in changes.items():
        dest=inside(project,rel);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    manifest['codeDrafts']=dict(schemaVersion=1,kind='full-csharp-drafts-v1',report='Analysis/Code/package-csharp-drafts.json',sourceFiles=len(batch),files=sorted(changes),quality=summary['quality'])
    return changes
