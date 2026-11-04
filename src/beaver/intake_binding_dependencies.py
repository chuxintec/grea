"""Bounded selected-Prefab compiler closure and dependency-ordered intake views.

Views are new owned selections of exact parent bytes. They do not change the
parent candidate or imply that deferred compiler inputs were adopted.
"""
from pathlib import Path
from collections import Counter
import re

from . import __version__
from .candidate_snapshot import snapshot, verify
from .csharp import inspect
from .errors import fail, BeaverError
from .io import safe, read, load, write_json, new_output, sha, encoded
from .output_limits import digest_file, copy_verified, MANIFEST_BYTES, MANIFEST_NODES
from .intake import guid, preview
from .implementation import identity
from .managed_metadata import inspect_managed


def document(path):
    return load(read(path, max_bytes=MANIFEST_BYTES), max_nodes=MANIFEST_NODES)


def closure(roots, graph):
    result = set(roots)
    pending = list(roots)
    while pending:
        for dep in graph.get(pending.pop(), set()):
            if dep not in result:
                result.add(dep)
                pending.append(dep)
    return result


def ordered_groups(graph, maximum=16):
    """Stable dependency-first SCC packing; never split a dependency cycle."""
    remaining = set(graph)
    groups, blocked = [], []
    # Tarjan on the explicitly selected source dependency graph.
    index, stack, on_stack, indices, low, components = 0, [], set(), {}, {}, []
    def visit(node):
        nonlocal index
        indices[node] = low[node] = index; index += 1
        stack.append(node); on_stack.add(node)
        for dep in sorted(graph[node] & remaining):
            if dep not in indices:
                visit(dep); low[node] = min(low[node], low[dep])
            elif dep in on_stack:
                low[node] = min(low[node], indices[dep])
        if low[node] == indices[node]:
            component = []
            while True:
                value = stack.pop(); on_stack.remove(value); component.append(value)
                if value == node: break
            components.append(sorted(component))
    for node in sorted(remaining):
        if node not in indices: visit(node)
    accepted = set()
    batch = []
    for component in components:
        missing = set().union(*(graph[n] for n in component)) - accepted - set(component)
        if len(component) > maximum or missing:
            blocked.append(dict(paths=component, reason='cycle_exceeds_batch_limit' if len(component)>maximum else 'dependency_not_scheduled', dependencies=sorted(missing)))
            continue
        if len(batch) + len(component) > maximum:
            groups.append(batch); batch = []
        batch.extend(component); accepted.update(component)
    if batch: groups.append(batch)
    return groups, blocked


def _contexts(candidate, files, source):
    compiler = [p for p in files if p.startswith('Assets/') and p.endswith('.cs')]
    if len(compiler)>512:fail('INTAKE_DEPENDENCY_BUDGET',str(candidate),'At most512 selected C# inputs')
    for path in compiler:
        if digest_file(source/path) != files[path]['sha256'] or digest_file(source/(path+'.meta')) != files[path+'.meta']['sha256']:
            fail('INTAKE_DEPENDENCY_SOURCE_DRIFT', path, 'Prepared project must match the exact frozen compiler source and metadata')
    matches = []
    inputs = list((source/'Library/Bee').glob('*-inputdata.json'))
    if len(inputs)>64: fail('INTAKE_DEPENDENCY_CONTEXT_BUDGET',str(source),'At most64 Bee input contexts')
    for file in inputs:
        data = document(file).get('ScriptCompilationBuildProgram.Data.ScriptCompilationData', {})
        rows = data.get('Assemblies', [])
        owned = [r for r in rows if r.get('Path') == str(source) and any(s in compiler for s in r.get('SourceFiles', []))]
        if owned and set(compiler) <= {s for r in owned for s in r.get('SourceFiles', [])}:
            matches.append((file, owned))
    if len(matches)!=1:
        fail('INTAKE_DEPENDENCY_CONTEXT_AMBIGUOUS',str(source),'One actual Bee context must cover all candidate C# sources')
    file, rows = matches[0]
    result, runtime, pins = {}, [], {str(file):digest_file(file)}
    for row in rows:
        owned = sorted(set(row.get('SourceFiles', [])) & set(compiler))
        if not owned: continue
        rsp = source/'Library/Bee/artifacts'/(file.name.removesuffix('-inputdata.json')+'.dag')/(row['Name']+'.rsp')
        if not rsp.is_file():
            options = list((source/'Library/Bee/artifacts').glob('*.dag/'+row['Name']+'.rsp'))
            if len(options)!=1: fail('INTAKE_DEPENDENCY_CONTEXT_AMBIGUOUS',row['Name'],'Exact compilation response file required')
            rsp = options[0]
        pins[str(rsp)] = digest_file(rsp)
        asmdef = row.get('Asmdef')
        editor = row['Name']=='Assembly-CSharp-Editor' and not asmdef
        if asmdef:
            if asmdef not in files or digest_file(source/asmdef)!=files[asmdef]['sha256']:
                fail('INTAKE_DEPENDENCY_SCOPE_DRIFT',str(asmdef),'Actual assembly definition must be inventoried and unchanged')
            platforms = document(source/asmdef).get('includePlatforms', [])
            editor = platforms==['Editor']
        scope = dict(assembly=row['Name'],editorOnly=editor,asmdef=asmdef,inputData=str(file),inputDataSha256=pins[str(file)],responseFile=str(rsp),responseFileSha256=pins[str(rsp)])
        for path in owned:
            if path in result:fail('INTAKE_DEPENDENCY_CONTEXT_AMBIGUOUS',path,'One actual compilation scope per source required')
            result[path] = scope
        if not editor:runtime.append(str(rsp))
    return result, runtime, pins


def _target_types(target):
    assemblies, types = {}, {}
    paths = list((target/'Library/ScriptAssemblies').glob('*.dll'))
    if len(paths)>128:fail('INTAKE_DEPENDENCY_TARGET_BUDGET',str(target),'At most128 target managed metadata files')
    if not paths:fail('INTAKE_DEPENDENCY_TARGET_METADATA',str(target),'Bounded current target metadata snapshot is required; native identity remains unverified')
    for file in sorted(paths):
        try:
            raw=read(file,max_bytes=64*1024*1024);result=inspect_managed(raw)
        except ValueError as error:fail('INTAKE_DEPENDENCY_TARGET_METADATA',str(file),str(error))
        name=result['name'];assemblies[name]=dict(path=str(file),sha256=sha(raw))
        for value in result['types']:types.setdefault(value, []).append(name)
    sources = {}
    source_paths=list(target.joinpath('Assets').rglob('*.cs'))
    if len(source_paths)>10000:fail('INTAKE_DEPENDENCY_TARGET_BUDGET',str(target),'At most10000 retained C# source paths')
    for file in source_paths:
        if file.is_symlink():fail('SYMLINK_PATH',str(file),'Target compiler source must be a regular owned file')
        digest=digest_file(file)
        sources.setdefault(digest,[]).append(file.relative_to(target).as_posix())
    return assemblies, types, sources


def runtime_identity(package_evidence, runtime_readback):
    if not package_evidence or not runtime_readback:
        return None,{}
    context=document(safe(package_evidence));editor=safe(context['editorPath'])
    log=safe(runtime_readback);raw=read(log,max_bytes=64*1024*1024)
    paths=re.findall(r"^Mono path\[\d+\] = '([^']+)'",raw.decode('utf-8-sig'),re.M)
    root=editor/'Contents/Resources/Scripting/MonoBleedingEdge/lib/mono/unityjit-macos'
    if str(root) not in paths:
        fail('INTAKE_DEPENDENCY_RUNTIME_IDENTITY',str(log),'Existing native readback must identify this supplied Editor Mono runtime path')
    file=root/'mscorlib.dll';metadata=inspect_managed(read(file,max_bytes=64*1024*1024))
    if metadata['name']!='mscorlib' or not {'System.String','System.Boolean','System.Int32','System.Double'}<=set(metadata['types']):
        fail('INTAKE_DEPENDENCY_RUNTIME_IDENTITY',str(file),'Actual Editor runtime core library TypeDefs are required')
    pins={str(log):sha(raw),str(file):digest_file(file)}
    return dict(assembly=metadata['name'],types=set(metadata['types'])),pins


def runtime_field(field, runtime):
    result={k:field[k] for k in ('name','type','assembly')}
    if result['assembly']=='netstandard':
        base=re.sub(r'(\[[,]*\])+$','',result['type'])
        if runtime is None or '`' in base or base not in runtime['types']:
            fail('INTAKE_DEPENDENCY_RUNTIME_TYPE',result['type'],'Reference facade must resolve to a proven runtime TypeDef; no guessed field assembly')
        result['assembly']=runtime['assembly']
    elif 'netstandard, Version=' in result['type']:
        fail('INTAKE_DEPENDENCY_RUNTIME_TYPE',result['type'],'Generic argument facade requires explicit runtime forwarding support')
    return result


def script_root(additions, explicit=None):
    if explicit is not None:
        from .intake_contract import _asset_path
        _asset_path(explicit+'/Probe.cs','scriptTargetRoot',{'.cs'})
        return explicit.rstrip('/')
    roots=set()
    for row in additions:
        relative=row['source'].removeprefix('Assets/')
        if not row['target'].endswith(relative):
            fail('INTAKE_DEPENDENCY_SCRIPT_MAPPING','additions','Explicit script target root required for a nonuniform mapping')
        roots.add(row['target'][:-len(relative)].rstrip('/'))
    if len(roots)!=1:
        fail('INTAKE_DEPENDENCY_SCRIPT_MAPPING','additions','One exact mapping prefix or explicit script target root required')
    return next(iter(roots))


def analyze(candidate, target, source_project, output, *, dotnet, sdk_root,
            additions, package_evidence=None, expected_package_evidence=None, script_target_root=None, runtime_readback=None):
    incoming, manifest, files, manifest_sha = snapshot(candidate); verify(incoming, files)
    target, source = safe(target), safe(source_project)
    out = new_output(output, [incoming,target,source])
    script_target_root=script_root(additions,script_target_root)
    scopes, response_files, pins = _contexts(incoming,files,source)
    source_names=sorted({s['assembly'] for s in scopes.values() if not s['editorOnly']})
    inspected=inspect(source,out/'semantics',dict(responseFiles=response_files,sourceAssemblies=source_names,dotnet=dotnet,sdkRoot=sdk_root))
    semantics=document(Path(inspected['report']))
    if semantics.get('status')!='ok' or semantics.get('unknownCompileInputs'):
        fail('INTAKE_DEPENDENCY_SEMANTICS',inspected['report'],'Exact compilation must have no errors or unknown compiler inputs')
    semantic_rows={row['path']:dict(row,assembly=assembly['name']) for assembly in semantics['assemblies'] for row in assembly['sourceSemantics']}
    for assembly in semantics['assemblies']:
        for row in assembly['sources']:
            path=row['path']
            if path not in files or files[path]['sha256']!=row['sha256']:
                fail('INTAKE_DEPENDENCY_SEMANTIC_DRIFT',path,'Semantic source must equal frozen inventory')
    oracle=document(incoming/'Analysis/BeaverIntakeBindings/serialized-oracle.json')
    fragments=document(incoming/'Analysis/BeaverIntakeBindings/intake-spec-fragments.json')
    by_guid={guid(read(incoming/(p+'.meta')),p):p for p in scopes}
    roots, native_types, package_refs = set(), {}, {}
    for prefab in oracle['prefabs']:
        for owner in prefab['owners']:
            for prop in owner['properties']:
                if prop['path']!='m_Script' or not prop.get('reference'):continue
                ref=prop['reference'];path=by_guid.get(ref['guid'])
                if path:
                    roots.add(path);native_types.setdefault(path,set()).add((ref['scriptType'],ref['scriptAssembly']))
                else: package_refs[ref['guid']]=ref
    graph={p:{r['path'] for r in row['dependencies']} for p,row in semantic_rows.items()}
    selected=closure(roots,graph)
    for path in selected:
        if path not in semantic_rows or semantic_rows[path]['unresolved']:
            fail('INTAKE_DEPENDENCY_UNKNOWN',path,'Selected compiler dependency must resolve within the inspected source scope')
    assemblies,target_types,target_sources=_target_types(target)
    bound={r['source'] for r in fragments['externalScripts']}
    scope_only={r['path'] for r in fragments['omittedCompilerInputs']}
    classifications, declarations, reused, obstacles = [], {}, [], []
    runtime,runtime_pins=runtime_identity(package_evidence,runtime_readback)
    resolved_support, support_pins, resolved_existing = set(), dict(runtime_pins), set()
    for path,scope in sorted(scopes.items()):
        row=semantic_rows.get(path)
        item=dict(path=path,sha256=files[path]['sha256'],guid=guid(read(incoming/(path+'.meta')),path),scope=scope,nativeReferenced=path in roots,inSelectedClosure=path in selected)
        if scope['editorOnly']:
            item['category']='editor_only_importer_scope'
            item['exclusionEvidence']='actual Editor-only compilation domain; no runtime assembly/source or native serialized reference points to this file'
            if path in selected: fail('INTAKE_DEPENDENCY_EDITOR_REFERENCE',path,'Selected runtime closure reaches Editor-only code')
        elif path in bound: item['category']='verified_retained_script_binding'
        elif path in scope_only: item['category']='preparation_replaced_original_script'
        elif row is None: item['category']='unknown';obstacles.append(dict(path=path,reason='no_semantic_scope'))
        elif path not in selected:
            item['category']='outside_selected_static_dependency_closure'
            item['exclusionEvidence']='not a root and not reachable from exact serialized roots through resolved source-symbol dependencies; not a whole-product dead-code claim'
        else:
            item.update(types=row['types'],dependencies=sorted(graph[path]),lateBoundDependencies=row.get('lateBoundDependencies',[]))
            main=[t for t in row['types'] if t['fullName'].split('.')[-1]==Path(path).stem and t.get('unityObject')]
            if len(main)!=1:
                item['category']='runtime_compiler_support'
                copies=target_sources.get(files[path]['sha256'],[])
                support_match=[]
                for copy in copies:
                    current=target/Path(copy).parent;scope_candidates=[]
                    while current!=target and current.is_relative_to(target):
                        asmrefs=list(current.glob('*.asmref'))
                        asmdefs=list(current.glob('*.asmdef'))
                        if asmrefs or len(asmdefs)>1:break
                        if asmdefs:
                            info=document(asmdefs[0])
                            if info.get('autoReferenced',True) and not info.get('includePlatforms') and not info.get('excludePlatforms'):
                                name=info.get('name')
                                if row['types'] and all(target_types.get(t['fullName'])==[name] for t in row['types']):
                                    scope_candidates.append((name,asmdefs[0]))
                            break
                        current=current.parent
                    if len(scope_candidates)==1:
                        name,definition=scope_candidates[0]
                        support_match.append(dict(target=copy,assembly=name,asmdef=str(definition),types=[t['fullName'] for t in row['types']]))
                if len(support_match)==1:
                    item['category']='retained_compiler_support';item['retainedSupport']=support_match[0]
                    resolved_support.add(path)
                    for file in (target/support_match[0]['target'],target/(support_match[0]['target']+'.meta'),Path(support_match[0]['asmdef'])):
                        support_pins[str(file)]=digest_file(file)
                    support_pins[assemblies[support_match[0]['assembly']]['path']]=assemblies[support_match[0]['assembly']]['sha256']
                else:obstacles.append(dict(path=path,reason='existing_intake_requires_MonoScript_class_identity_for_each_new_source',types=[t['fullName'] for t in row['types']]))
            else:
                main=main[0]
                existing=target_types.get(main['fullName'],[])
                copies=target_sources.get(files[path]['sha256'],[])
                if existing:
                    item['category']='retained_type_requires_binding_review'
                    item['targetAssemblies']=existing;item['byteIdenticalTargetSources']=copies
                    item['targetSourcePins']=[dict(path=copy,sha256=digest_file(target/copy),metaSha256=digest_file(target/(copy+'.meta')),guid=guid(read(target/(copy+'.meta')),copy)) for copy in copies]
                    reused.append(item)
                    if len(existing)==1 and len(copies)==1:
                        resolved_existing.add(path)
                        for file in (target/copies[0],target/(copies[0]+'.meta')):support_pins[str(file)]=digest_file(file)
                    same_identity=len(copies)==1 and len(existing)==1 and guid(read(target/(copies[0]+'.meta')),copies[0])==item['guid']
                    if same_identity:
                        item['category']='retained_script_same_identity'
                        item['externalScriptDeclaration']=dict(source=path,sourceGuid=item['guid'],sourceType=main['fullName'],sourceAssembly=row['assembly'],target=copies[0],targetGuid=item['guid'],targetType=main['fullName'],targetAssembly=existing[0],targetLocalId=11500000,targetSha256=files[path]['sha256'],targetMetaSha256=digest_file(target/(copies[0]+'.meta')),reason='Pinned same GUID/type/bytes from prior target adoption; native GetClass verification remains required')
                    else:obstacles.append(dict(path=path,reason='exact_type_already_present; must reuse verified target identity instead of duplicate newScript',targetAssemblies=existing,byteIdenticalTargetSources=copies))
                else:
                    item['category']='field_carrier' if main['fieldCarrier'] else 'runtime_support_component'
                    try:runtime_fields=[runtime_field(f,runtime) for f in main['fields']]
                    except BeaverError as error:
                        item['category']='unknown_runtime_field_identity';obstacles.append(dict(path=path,reason=error.code,diagnostic=error.as_dict()))
                    else:
                        declarations[path]=dict(source=path,target=script_target_root+'/'+path.removeprefix('Assets/'),guid=item['guid'],sha256=files[path]['sha256'],metaSha256=files[path+'.meta']['sha256'],sourceType=main['fullName'],sourceAssembly=row['assembly'],targetType=main['fullName'],targetAssembly='Assembly-CSharp',baseType=main['baseType'],baseAssembly=main['baseAssembly'],localId=11500000,fields=runtime_fields,reason='Exact source/meta selected by resolved native/semantic closure; field/behavior evidence is pinned; native GetClass/compile/readback still required')
            if item.get('lateBoundDependencies'):
                obstacles.append(dict(path=path,reason='late_bound_dependency_requires_explicit_evidence',symbols=item['lateBoundDependencies']))
        classifications.append(item)
    # A dependency requiring a new binding/compiler-support route blocks its
    # dependants; it is never disguised as a four-helper compiler omission.
    unsafe={r['path'] for r in classifications if r.get('lateBoundDependencies')}
    eligible_graph={p:graph[p]-bound-resolved_support-resolved_existing for p in declarations if p not in unsafe}
    groups,blocked=ordered_groups(eligible_graph)
    for entry in blocked:obstacles.append(entry)
    evidence=dict(contract='beaver-intake-dependencies/1',implementationSha256=identity(),candidateManifestSha256=manifest_sha,sourceProject=str(source),contextPins=pins,runtimeFieldPolicy=dict(referenceFacade='netstandard',runtimeAssembly=runtime['assembly'] if runtime else None,proofPins=runtime_pins,policy='exact reused native Mono path and runtime core TypeDefs; unresolved/generic facade identities block'),semanticReport=dict(path=inspected['report'],sha256=digest_file(Path(inspected['report']))),targetMetadata=assemblies,retainedCompilerPins=support_pins,targetMetadataPolicy='bounded compiled snapshot plus source pins; current native compilation/GetClass not yet verified',selectedNativeRoots=sorted(roots),selectedCompilerClosure=sorted(selected),compilerClassifications=classifications,categoryCounts=dict(Counter(r['category'] for r in classifications)),compilerScopes=[dict(path=p,sha256=files[p]['sha256'],category='preparation_assembly_scope' if p in scope_only else 'unknown_compiler_input') for p in files if p.startswith('Assets/') and Path(p).suffix.lower() in {'.asmdef','.asmref','.rsp','.dll'}],packageScriptReferences=list(package_refs.values()),reuseCandidates=reused,blockingInputs=obstacles,dependencyGroups=groups,newScriptBatchLimit=16,native='not_run',targetWrites=False)
    write_json(out/'dependency-evidence.json',evidence)
    batches=[]
    # Every code batch pairs its scripts with one real selected image asset.
    # Later asset adoption must reuse these explicit assets after native success.
    payloads=[r for r in additions if r['source'].endswith('.png') and not (target/r['target']).exists() and not (target/(r['target']+'.meta')).exists()]
    for index,group in enumerate(groups):
        if index>=len(payloads):fail('INTAKE_DEPENDENCY_BATCH_ASSET',str(out),'A real noncompiler addition is required by the unchanged intake contract for every batch')
        payload=payloads[index];batch=out/('batch-%02d'%(index+1));view=batch/'candidate';view.mkdir(parents=True)
        chosen={p for p in files if p.startswith(('Packages/','ProjectSettings/'))}
        for path in group+[payload['source']]:chosen.update((path,path+'.meta'))
        # Include all original directory metadata for the chosen asset ancestry.
        for path in list(chosen):
            for parent in Path(path).parents:
                meta=parent.as_posix()+'.meta'
                if meta in files:chosen.add(meta)
        inventory=[]
        for path in sorted(chosen):
            pin=files[path];copy_verified(incoming/path,view/path,pin['sha256'],pin['bytes']);inventory.append(dict(pin,path=path,owner='generated'))
        lineage=dict(parentCandidate=str(incoming),parentManifestSha256=manifest_sha,dependencyEvidence=str(out/'dependency-evidence.json'),dependencyEvidenceSha256=digest_file(out/'dependency-evidence.json'),selectedCompilerInputs=group,deferredCompilerInputs=sorted(set(scopes)-set(group)),policy='owned exact-byte batch selection; not a baseline, omission claim or native acceptance')
        write_json(view/'Analysis/intake-batch-lineage.json',lineage)
        raw=(view/'Analysis/intake-batch-lineage.json').read_bytes();inventory.append(dict(path='Analysis/intake-batch-lineage.json',sha256=sha(raw),bytes=len(raw),owner='generated'))
        doc={k:manifest[k] for k in ('schemaVersion','targetProfile','native','diagnostics','staticPresentation','visibleEdits','player','business') if k in manifest}
        doc.update(namespace='beaver-intake-batch/'+manifest_sha+'/'+str(index+1),scopeMode='selection',files=inventory,producer=dict(name='beaver',version=__version__,implementationSha256=identity()),selection=lineage)
        write_json(view/'manifest.json',doc)
        view_root,_,view_files,view_sha=snapshot(view);verify(view_root,view_files)
        spec=dict(schemaVersion=4,operation='additive-intake',candidateManifestSha256=view_sha,additions=[payload],externalScripts=[],omittedCompilerInputs=[],verifications=[],protectedAssets=[],evidence=[dict(path=str(out/'dependency-evidence.json'),sha256=digest_file(out/'dependency-evidence.json'))]+[dict(path=p,sha256=h) for p,h in sorted(support_pins.items())],externalAssets=[],packageScripts=[],engineObjects=[],newScripts=[declarations[p] for p in group])
        from .intake_contract import validate_spec
        validate_spec(spec);write_json(batch/'intake-spec.json',spec)
        try:
            plan=preview(view,target,batch/'intake-spec.json',batch/'consumer-plan',package_evidence,expected_package_evidence)
        except BeaverError as error:plan=dict(status=error.status,error=error.as_dict())
        batches.append(dict(index=index+1,candidate=str(view),spec=str(batch/'intake-spec.json'),specSha256=digest_file(batch/'intake-spec.json'),newScripts=len(group),dependsOn=list(range(1,index+1)),intakePlan=plan,targetBefore='actual_current_target_only; replan after predecessor native success',payloadAddition=payload))
    verify(incoming,files)
    write_json(out/'batch-recipes.json',dict(contract='beaver-intake-dependency-batches/1',batches=batches,blockingInputs=obstacles,sourceNative=manifest.get('native'),formalAdoption='not_run',native='not_run',targetWrites=False))
    return dict(report=str(out/'dependency-evidence.json'),batches=str(out/'batch-recipes.json'),categoryCounts=evidence['categoryCounts'],scheduledNewScripts=sum(len(g) for g in groups),batchCount=len(groups),blockingInputs=len(obstacles))
