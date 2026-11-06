"""Bounded replacement of frozen flow-layout artifacts by Unity layout components."""
import collections
import json
import re
import subprocess
from pathlib import Path
from .io import safe,inside,read,load,sha,new_output,write_json
from .providers.assetripper import fingerprint
from .sources.compiled import fail
from .layout.standard import find_analysis,find_output_paths

LIMIT=128*1024**2


def same_size(a,b):
    return len(a)==len(b) and all(abs(x-y)<.001 for x,y in zip(a,b))


def classify(spec,parent,children,source_cell=None,template_size=None):
    """Choose standard Unity behavior from observed inputs, not source recurrence."""
    if spec.get('startAxis')!=0 or spec.get('constraint',0)!=0 or spec.get('affectedByScale'):
        fail('LAYOUT_REVIEW_REQUIRED',spec['sourceId'],'This bounded repair covers the observed horizontal, unconstrained, unscaled subset only')
    sizes=[c['size'] for c in children]
    positive=[s for s in sizes if all(x>0 for x in s)]
    uniform=not sizes or all(same_size(s,sizes[0])for s in sizes)
    if spec['resize']==2:
        cell=source_cell or spec['cellSize'];mode='unity-grid'
        reason='Authored fixed-cell sizing; Unity GridLayoutGroup owns both child dimensions'
    elif uniform and positive:
        cell=positive[0];mode='unity-content-grid'
        reason='Observed uniform item rectangles; standard Unity grid owns fixed cells and wrapping'
    elif uniform and template_size:
        cell=template_size;mode='unity-content-grid'
        if source_cell and not same_size(cell,source_cell):fail('LAYOUT_TEMPLATE_SIZE_CONFLICT',spec['sourceId'],'Declared cell and exact nested template root differ')
        reason='Exact nested Prefab root supplies missing instance dimensions; no guessed default size'
    elif uniform and not spec['enabled']:
        cell=source_cell or [0,0];mode='unity-content-grid'
        reason='Disabled authored layout; preserve baked RectTransforms without executing any arranger'
    elif uniform and source_cell and all(v>0 for v in source_cell):
        cell=source_cell;mode='unity-content-grid'
        reason='Explicit source cell dimensions are available; nested instance content remains an independent recovery gap'
    elif not uniform and sum(c['size'][0]for c in children)+spec['spacingXY'][0]*max(0,len(children)-1)+spec['padding'][0]+spec['padding'][2]<=parent['size'][0]+.001:
        cell=None;mode='unity-horizontal-row'
        reason='Authored heterogeneous single row fits its fixed width; native row preserves child dimensions and grows with text height'
    else:fail('LAYOUT_REVIEW_REQUIRED',spec['sourceId'],'No proven native layout mapping for this item geometry')
    if cell and (len(cell)!=2 or any(x<0 for x in cell)):fail('LAYOUT_CELL_SIZE',spec['sourceId'],'Invalid authored cell size')
    return dict(mode=mode,cellSize=cell,enabled=spec['enabled'],fitVertical=spec['resize']==1,
                staticAuthoredRects=not spec['enabled'],reason=reason,
                corner=(2 if spec['verticalDirection']==0 else 0)+(1 if spec['horizontalDirection']==1 else 0),
                alignment=(6 if spec['verticalDirection']==0 else 0)+(2 if spec['horizontalDirection']==1 else 0),
                padding=spec['padding'],spacing=spec['spacingXY'],sourceCellSize=source_cell,
                exception='Unity grid minimum row must collapse for empty content, and content metrics must outrank background Image'if mode=='unity-content-grid'else None)


def audit(candidate,output,expected_manifest):
    root=safe(candidate);manifest_raw=read(root/'manifest.json',max_bytes=LIMIT)
    if sha(manifest_raw)!=expected_manifest:fail('LAYOUT_PATCH_BASE_CHANGED',str(root),'Exact frozen base manifest required')
    manifest=load(manifest_raw,max_nodes=16_000_000,max_depth=128)
    paths=load(read(find_output_paths(root)));plan_raw=read(inside(root,paths['plan']),max_bytes=LIMIT);plan=load(plan_raw,max_nodes=16_000_000,max_depth=128)
    rb=load(read(find_analysis(root,'editor-readback.json'),max_bytes=LIMIT),max_nodes=16_000_000,max_depth=128)
    structured=load(read(find_analysis(root,'structured-objects.json'),max_bytes=LIMIT),max_nodes=16_000_000,max_depth=128)
    assets={a['sourceId']:a for a in structured['objects']};nodes={n['sourceId']:n for n in plan['nodes']};native={n['sourceId']:n for n in rb['nodes']}
    prefabs={p['sourceId']:p for p in plan['sourcePrefabs']};native_prefabs={p['sourceId']:p for p in rb['sourcePrefabs']}
    flow_path='Assets/Generated/Views/NativeFlowLayoutGroup.cs';flow_guid=re.search(rb'^guid: ([0-9a-f]{32})\r?$',read(inside(root,flow_path+'.meta')),re.M)[1].decode()
    cases=[];documents={}
    def document(sid):
        if sid not in documents:documents[sid]=load(read(inside(root,assets[sid]['decodedEvidence']),max_bytes=LIMIT),max_nodes=16_000_000,max_depth=128)['document']['instances']
        return documents[sid]
    def source_dimensions(value):
        if value is None:return None
        if '__value_type__'in value:return value['values']
        return [value['width'],value['height']]
    for c in plan['components']:
        if not(c.get('convertible')and c.get('type')=='cc.Layout'and c.get('layoutType')==3):continue
        owner=c['sourceId'].split('#')[0];doc=document(owner);source_node=doc[int(c['node'].split('#')[1])]
        raw_component=source_node['_components'][int(c['sourceId'].rsplit('/',1)[-1])]
        source_cell=source_dimensions(raw_component.get('_N$cellSize',raw_component.get('_cellSize')))
        template_sizes=[];template_sources=[]
        for child in nodes[c['node']]['children']:
            raw_child=doc[int(child.split('#')[1])];asset=raw_child.get('_prefab',{}).get('asset',{}).get('__uuid__')
            if asset:
                target=owner.split(':')[0]+':'+asset
                if target not in assets:fail('LAYOUT_TEMPLATE_IDENTITY',child,'Exact nested Prefab is absent; no name fallback')
                target_doc=document(target);size=source_dimensions(target_doc[target_doc[0]['data']['__id__']].get('_contentSize'))
                if size:template_sizes.append(size);template_sources.append(dict(sourceId=target,rootSize=size))
        template_size=template_sizes[0]if template_sizes and all(same_size(s,template_sizes[0])for s in template_sizes)else None
        children=[native[s]for s in nodes[c['node']]['children']]
        choice=classify(c,native[c['node']],children,source_cell,template_size)
        cases.append(dict(sourceId=c['sourceId'],node=c['node'],owner=owner,sourcePrefabPath=prefabs[owner]['path'],sourcePrefabGuid=native_prefabs[owner]['guid'],sourceRoot=prefabs[owner]['root'],sourceNodes=prefabs[owner]['nodes'],nodeCount=prefabs[owner]['nodeCount'],**choice,templateEvidence=template_sources))
    affected=[]
    for sid in sorted({c['owner']for c in cases}):
        path=prefabs[sid]['path'];body=read(inside(root,path),max_bytes=LIMIT)
        if flow_guid.encode()not in body:fail('LAYOUT_PATCH_REFERENCE',path,'Frozen source Prefab no longer has the observed layout')
        affected.append(dict(sourceId=sid,path=path,guid=native_prefabs[sid]['guid'],sha256=sha(body),sourceComponents=[c['sourceId']for c in cases if c['owner']==sid]))
    aggregators=[]
    for key in ('prefab','editableProbe'):
        path=paths[key];aggregators.append(dict(kind=key,path=path,sha256=fingerprint(inside(root,path))))
    # Caller receives complete case/asset lists; no candidate is modified in audit.
    out=new_output(output,[root]);report=dict(schemaVersion=1,status='audited',source=str(root),sourceManifestSha256=expected_manifest,importPlanSha256=sha(plan_raw),flowScriptPath=flow_path,flowScriptGuid=flow_guid,cases=cases,prefabs=affected,aggregators=aggregators,
        counts=dict(sourcePrefabs=len(affected),sourceComponents=len(cases),aggregators=len(aggregators),modes=dict(collections.Counter(c['mode']for c in cases)),disabledComponents=sum(not c['enabled']for c in cases)),
        parentScope='NativeChildLayoutGroup shared notification base remains only for existing Linear users; no new flow/scale/fixed-row recurrence retained',sourceAttribution='Frozen history and SourceRecovery/RetiredLayout retain original source and license',editor='not_run')
    write_json(out/'layout-audit.json',report);return dict(status='audited',counts=report['counts'],report=str(out/'layout-audit.json'))


def serialized_layout_ids(body,flow_guid,node_map,cases):
    headers=list(re.finditer(rb'^--- !u!([0-9]+) &(-?[0-9]+).*$',body,re.M));by_go={};references=collections.Counter(x.decode()for x in re.findall(rb'\{fileID: (-?[0-9]+)\}',body))
    for i,h in enumerate(headers):
        if h[1]!=b'114':continue
        block=body[h.end():headers[i+1].start()if i+1<len(headers)else len(body)]
        if re.search(rb'^  m_Script:.*guid: '+flow_guid.encode(),block,re.M):
            go=re.search(rb'^  m_GameObject: \{fileID: (-?[0-9]+)\}',block,re.M)
            if not go or go[1].decode()in by_go:fail('LAYOUT_SCRIPT_IDENTITY','$','Ambiguous legacy component owner')
            by_go[go[1].decode()]=h[2].decode()
    result=[]
    for case in cases:
        owner=node_map[case['node']]['gameObjectFileId'];old=by_go.get(owner)
        if not old or references[old]!=1:fail('LAYOUT_COMPONENT_REFERENCED',case['sourceId'],'Require exact sole m_Component ownership before retiring the known script')
        result.append(dict(case,oldComponentFileId=old))
    if len(by_go)!=len(result):fail('LAYOUT_CASE_COVERAGE','$','Every observed legacy component must have one disposition')
    return result


def aggregate_node_ids(body,plan):
    headers=list(re.finditer(rb'^--- !u!([0-9]+) &(-?[0-9]+).*$',body,re.M));go_names={};rects={}
    for i,h in enumerate(headers):
        block=body[h.end():headers[i+1].start()if i+1<len(headers)else len(body)];fid=h[2].decode()
        if h[1]==b'1':
            name=re.search(rb'^  m_Name: (.*)$',block,re.M)
            if name:go_names[fid]=name[1].decode()
        elif h[1]==b'224':
            go=re.search(rb'^  m_GameObject: \{fileID: (-?[0-9]+)\}',block,re.M);father=re.search(rb'^  m_Father: \{fileID: (-?[0-9]+)\}',block,re.M);children=re.search(rb'^  m_Children:([^\n]*\n(?:  -[^\n]*\n)*)',block,re.M)
            if go and father and children:rects[fid]=dict(go=go[1].decode(),father=father[1].decode(),children=[x.decode()for x in re.findall(rb'fileID: (-?[0-9]+)',children[1])])
    roots=[fid for fid,r in rects.items()if r['father']=='0']
    if len(roots)!=1:fail('LAYOUT_AGGREGATE_ROOT','$','Unique wrapper root required')
    nodes={n['sourceId']:n for n in plan['nodes']};source_roots=[n['sourceId']for n in plan['nodes']if n.get('parent')not in nodes]
    if 'roots'in plan and plan['roots']!=source_roots:fail('LAYOUT_AGGREGATE_ROOT','$','Declared root ordinals differ from the exact source graph')
    design=[fid for fid in rects[roots[0]]['children']if go_names.get(rects[fid]['go'])=='DesignRoot']
    if len(design)!=1 or len(rects[design[0]]['children'])!=len(source_roots):fail('LAYOUT_AGGREGATE_ROOT','$','Exact conversion wrapper and root ordinal set required')
    result={}
    def walk(sid,fid):
        r=rects[fid];n=nodes[sid]
        if len(r['children'])!=len(n['children']):fail('LAYOUT_AGGREGATE_CHILDREN',sid,'Source child ordinal graph differs')
        result[sid]=dict(sourceId=sid,gameObjectFileId=r['go'],transformFileId=fid)
        for source,child in zip(n['children'],r['children']):walk(source,child)
    for sid,fid in zip(source_roots,rects[design[0]]['children']):walk(sid,fid)
    return result


def resume_state(previous_execution,source,report,targets):
    run=safe(previous_execution);result=load(read(run/'execution-result.json'))
    if result.get('status')!='partial'or not result.get('processExited')or not result.get('frozenSourceUnchanged'):
        fail('LAYOUT_RESUME_STATE',str(run),'Require an exited owned partial layer with unchanged frozen source')
    previous=safe(result['candidate']);prepared=safe(result['preparation']);receipt=load(read(prepared/'preparation.json'))
    if receipt['source']!=str(source)or receipt['auditSha256']!=report['auditSha256']or fingerprint(prepared/'preparation.json')!=result['preparationSha256']:
        fail('LAYOUT_RESUME_PROVENANCE',str(run),'Exact same frozen source/audit and previous preparation required')
    plan_raw=read(find_analysis(previous,'layout-patch-plan.json'),max_bytes=LIMIT)
    prior_plan=load(plan_raw,max_nodes=16_000_000,max_depth=128);locations=load(read(find_output_paths(previous)))
    previous_helper=inside(previous,(Path(locations['plan']).parent/'UnityLayoutPatch.cs').as_posix())
    if fingerprint(previous_helper)!=receipt['helperSha256']or fingerprint(inside(previous,locations['plan']))!=prior_plan['targetImportPlanSha256']:
        fail('LAYOUT_RESUME_CODE_CHANGED',str(previous),'Previous helper and import plan must retain their exact owned hashes')
    # This continuation changes only the Editor probe, not the runtime mapping.
    # Reusing geometry evidence after a runtime adapter change requires a new review.
    for template,relative in [('UnityImporter.cs',(Path(locations['plan']).parent/'MonkeyImporter.cs').as_posix()),('UnityButtonAnimations.cs',(Path(locations['plan']).parent/'NativeButtonAnimations.cs').as_posix()),('UnityDynamicUi.cs','Assets/Monkey/Editor/UnityDynamicUi.cs'),('IntrinsicGridLayoutGroup.cs','Assets/Game/Presentation/Recovery/IntrinsicGridLayoutGroup.cs')]:
        if read(inside(previous,relative))!=read(Path(__file__).parent/'targets'/template):fail('LAYOUT_RESUME_RUNTIME_CHANGED',relative,'Runtime/common conversion code differs; do not reuse prior native geometry without scoped review')
    native_raw=read(find_analysis(previous,'layout-patch-readback.json'),max_bytes=LIMIT);native=load(native_raw,max_nodes=16_000_000,max_depth=128)
    if sha(plan_raw)!=result['executedPlanSha256']or native.get('planSha256')!=sha(plan_raw)or native_raw!=read(run/'layout-patch-readback.json',max_bytes=LIMIT)or not native.get('sourceRuntimeTypeAbsent'):
        fail('LAYOUT_RESUME_EVIDENCE',str(run),'Exact prior plan/readback/runtime-type proof required')
    if len({r['path']for r in native['assets']})!=len(native['assets']):fail('LAYOUT_RESUME_DUPLICATE_ASSET',str(run),'Prior asset evidence contains duplicate identities')
    rows={r['path']:r for r in native['assets']if r.get('status')in('saved-reopened-identity-and-geometry-verified','reused-prior-saved-native-evidence')};known={t['path']for t in targets}
    if not set(rows)<=known:fail('LAYOUT_RESUME_COVERAGE',str(run),'Prior proof includes unknown assets')
    for target in targets:
        path=target['path'];row=rows.get(path);actual=fingerprint(inside(previous,path))
        if actual!=(row['afterSha256']if row else target['sha256']):fail('LAYOUT_RESUME_ASSET_CHANGED',path,'Changed or partially saved asset has no exact successful native proof')
        if read(inside(previous,path+'.meta'))!=read(inside(source,path+'.meta')):fail('LAYOUT_RESUME_GUID_CHANGED',path,'Exact persistent asset meta must remain unchanged')
        if row:
            if row['beforeSha256']!=target['sha256']or row['guid']!=target['guid']or row['missingAfter']!=0 or {m['sourceId']for m in row['mappings']}!={c['sourceId']for c in target['cases']}:
                fail('LAYOUT_RESUME_ASSET_PROOF',path,'Successful row coverage differs from the original audit')
            target['convertedSha256']=actual;target['reusedPriorEvidence']=True
    return previous,dict(run=str(run),readback=native_raw,plan=plan_raw,execution=read(run/'execution-result.json'),assets=len(rows),probes=len(native.get('probes',[])))


def prepare(audit_directory,output,previous_execution=None):
    report_path=safe(audit_directory)/'layout-audit.json';report=load(read(report_path,max_bytes=LIMIT),max_nodes=16_000_000,max_depth=128)
    root=safe(report['source'])
    if fingerprint(root/'manifest.json')!=report['sourceManifestSha256']:fail('LAYOUT_PATCH_BASE_CHANGED',str(root),'Frozen base changed')
    paths=load(read(find_output_paths(root)));raw_plan=read(inside(root,paths['plan']),max_bytes=LIMIT)
    if sha(raw_plan)!=report['importPlanSha256']:fail('LAYOUT_PATCH_BASE_CHANGED',str(root),'Frozen import plan changed')
    plan=load(raw_plan,max_nodes=16_000_000,max_depth=128);contract=load(read(find_analysis(root,'native-identity-contract.json'),max_bytes=LIMIT),max_nodes=16_000_000,max_depth=128)
    source_objects={p['sourceId']:{r['sourceId']:r for r in p['objects']}for p in contract['prefabs']};targets=[]
    readback=load(read(find_analysis(root,'editor-readback.json'),max_bytes=LIMIT),max_nodes=16_000_000,max_depth=128)
    baselines={p['sourceId']:p['nodes']for p in readback['sourcePrefabs']};global_baseline={n['sourceId']:n for n in readback['nodes']}
    nodes={n['sourceId']:n for n in plan['nodes']}
    def selected(cases):
        result=set()
        for case in cases:
            sid=case['node'];result.add(sid);result.update(nodes[sid]['children'])
            while nodes[sid].get('parent')in nodes:
                sid=nodes[sid]['parent'];result.add(sid)
        return sorted(result)
    for asset in report['prefabs']:
        body=read(inside(root,asset['path']),max_bytes=LIMIT)
        if sha(body)!=asset['sha256']:fail('LAYOUT_PATCH_ASSET_CHANGED',asset['path'],'Frozen Prefab changed')
        cases=[c for c in report['cases']if c['owner']==asset['sourceId']]
        identities=source_objects[asset['sourceId']]
        targets.append(dict(asset,aggregate=False,cases=serialized_layout_ids(body,report['flowScriptGuid'],identities,cases),baseline=baselines[asset['sourceId']],identities=list(identities.values())))
    for asset in report['aggregators']:
        body=read(inside(root,asset['path']),max_bytes=LIMIT)
        if sha(body)!=asset['sha256']:fail('LAYOUT_PATCH_ASSET_CHANGED',asset['path'],'Frozen aggregate changed')
        meta=read(inside(root,asset['path']+'.meta'));guid=re.search(rb'^guid: ([0-9a-f]{32})\r?$',meta,re.M)[1].decode()
        identities=aggregate_node_ids(body,plan);subset=selected(report['cases'])
        targets.append(dict(asset,guid=guid,sourceId=asset['kind'],aggregate=True,cases=serialized_layout_ids(body,report['flowScriptGuid'],identities,report['cases']),baseline=[global_baseline[sid]for sid in subset],identities=[identities[sid]for sid in subset]))
    # No external serialized object may point to a retired component local ID.
    old_ids={t['guid']:{c['oldComponentFileId']for c in t['cases']}for t in targets}
    reference_pattern=re.compile(rb'\{[^{}\n]*fileID: (-?[0-9]+)[^{}\n]*guid: ([0-9a-f]{32})[^{}\n]*\}')
    for file in (root/'Assets').rglob('*'):
        if not file.is_file()or file.suffix not in {'.prefab','.unity','.asset','.anim','.controller'}:continue
        for local,guid in reference_pattern.findall(file.read_bytes()):
            if local.decode()in old_ids.get(guid.decode(),set()):fail('LAYOUT_EXTERNAL_REFERENCE',str(file),'Retired layout is referenced externally; review that typed reference before replacement')
    clone_source=root;prior=None
    if previous_execution:
        clone_source,prior=resume_state(previous_execution,root,dict(report,auditSha256=fingerprint(report_path)),targets)
    out=new_output(output,[root,clone_source,safe(audit_directory)]);project=out/'UnityProject';project.mkdir()
    # APFS clone-on-write gives independent file inodes without duplicating a warm Library.
    for name in ['Assets','Packages','ProjectSettings','Analysis','Docs','SourceRecovery','Library']:
        source=clone_source/name
        if source.is_dir():subprocess.run(['/bin/cp','-cR',str(source),str(project/name)],check=True)
    for name in ['AGENTS.md','manifest.json']:
        subprocess.run(['/bin/cp','-c',str(clone_source/name),str(project/name)],check=True)
    sample=report['prefabs'][0]['path']
    if (project/sample).stat().st_ino==(clone_source/sample).stat().st_ino:fail('LAYOUT_CLONE_NOT_INDEPENDENT',sample,'Mutable candidate must not hardlink the previous layer')
    archive=project/'SourceRecovery/RetiredLayout';archive.mkdir(parents=True,exist_ok=prior is not None)
    flow=inside(project,report['flowScriptPath'])
    if prior:
        if flow.exists()or Path(str(flow)+'.meta').exists()or read(archive/'NativeFlowLayoutGroup.cs.txt')!=read(inside(root,report['flowScriptPath'])):
            fail('LAYOUT_RESUME_RUNTIME',str(project),'Exact retired source archive required; legacy runtime must stay absent')
        history=find_analysis(project,'layout-patch-history');history.mkdir(exist_ok=True)
        previous_readback=history/(sha(prior['readback'])+'.readback.json');previous_readback.write_bytes(prior['readback'])
        (history/(sha(prior['plan'])+'.plan.json')).write_bytes(prior['plan'])
        (history/(sha(prior['execution'])+'.execution.json')).write_bytes(prior['execution'])
        (find_analysis(project,'layout-patch-readback.json')).unlink()
    else:
        (archive/'NativeFlowLayoutGroup.cs.txt').write_bytes(read(flow));(archive/'NativeFlowLayoutGroup.cs.meta.txt').write_bytes(read(Path(str(flow)+'.meta')))
    (archive/'NativeLinearLayoutGroup-parent-context.cs.txt').write_bytes(read(project/'Assets/Generated/Views/NativeLinearLayoutGroup.cs'))
    (archive/'cocos-layout-mit.txt').write_bytes(read(Path(__file__).parent/'licenses/cocos-layout-mit.txt'))
    # Retire only the known legacy type before compiling this independent candidate.
    # The Editor patch removes only its exactly audited missing slots; no source layout code executes.
    if not prior:flow.unlink();Path(str(flow)+'.meta').unlink()
    (archive/'README.md').write_text('Frozen dev3 runtime layout source and attribution retained verbatim. Production replacement uses Unity layout components. The shared Linear notification parent is retained in the production subset; broader Linear migration is outside this fix. No legal conclusion is made.\n')
    changed={c['sourceId']:c for c in report['cases']}
    for c in plan['components']:
        if c['sourceId']in changed:
            choice=changed[c['sourceId']];c.update(nativeLayoutMode=choice['mode'],nativeCellSize=choice['cellSize']or[],presentationPolicy='unity-layout-components-v2')
            if choice['sourceCellSize']is not None:c['cellSize']=choice['sourceCellSize']
    write_json(inside(project,paths['plan']),plan)
    for name,relative in [('UnityImporter.cs',Path(paths['plan']).parent/'MonkeyImporter.cs'),('UnityButtonAnimations.cs',Path(paths['plan']).parent/'NativeButtonAnimations.cs'),('UnityDynamicUi.cs','Assets/Monkey/Editor/UnityDynamicUi.cs')]:
        inside(project,str(relative)).write_bytes(read(Path(__file__).parent/'targets'/name))
    intrinsic=next(r['path']for r in load(read(root/'manifest.json',max_bytes=LIMIT),max_nodes=16_000_000,max_depth=128)['files']if r['path'].endswith('/IntrinsicGridLayoutGroup.cs'))
    inside(project,intrinsic).write_bytes(read(Path(__file__).parent/'targets/IntrinsicGridLayoutGroup.cs'))
    helper=Path(__file__).parent/'targets/UnityLayoutPatch.cs';helper_target=inside(project,(Path(paths['plan']).parent/'UnityLayoutPatch.cs').as_posix());helper_target.write_bytes(read(helper))
    import uuid
    Path(str(helper_target)+'.meta').write_text('fileFormatVersion: 2\nguid: '+uuid.uuid5(uuid.NAMESPACE_URL,'monkey/native-layout-patch/editor-v1').hex+'\n')
    patch_plan=dict(schemaVersion=1,source=str(root),sourceManifestSha256=report['sourceManifestSha256'],auditSha256=fingerprint(report_path),targetImportPlanSha256=fingerprint(inside(project,paths['plan'])),flowScriptGuid=report['flowScriptGuid'],targets=targets,deadlineUtc='set-at-execution',budgetSeconds=900)
    if prior:patch_plan.update(priorReadbackPath=previous_readback.relative_to(project).as_posix(),priorReadbackSha256=sha(prior['readback']),reusedAssets=prior['assets'])
    write_json(find_analysis(project,'layout-patch-plan.json'),patch_plan)
    write_json(out/'preparation.json',dict(schemaVersion=1,status='prepared',source=str(root),candidate=str(project),sourceManifestSha256=report['sourceManifestSha256'],auditSha256=fingerprint(report_path),patchPlanSha256=fingerprint(find_analysis(project,'layout-patch-plan.json')),helperSha256=fingerprint(helper),targets=len(targets),sourcePrefabs=len(report['prefabs']),sourceComponents=len(report['cases']),reusedAssets=prior['assets']if prior else 0,newTargetAssets=len(targets)-(prior['assets']if prior else 0),previousExecution=prior['run']if prior else None,editor='not_run',clone='APFS-copy-on-write-independent-inodes',legacyRuntimeCodeRetired=True))
    return dict(status='prepared',candidate=str(project),targets=len(targets),report=str(out/'preparation.json'))


def execute(preparation,output,editor,budget_seconds,deadline_utc,window_end_utc,execute=False):
    """Run only the prepared independent candidate in one explicit new window."""
    import signal,time
    from datetime import timedelta
    from .native import now,stamp,utc,redact_log
    prepared=safe(preparation);receipt=load(read(prepared/'preparation.json'));root=inside(prepared,'UnityProject');source=safe(receipt['source'])
    if receipt.get('status')!='prepared'or receipt.get('candidate')!=str(root)or source==root:
        fail('LAYOUT_PREPARATION_IDENTITY',str(prepared),'Exact independent prepared candidate required')
    plan_path=find_analysis(root,'layout-patch-plan.json');plan_raw=read(plan_path,max_bytes=LIMIT);plan=load(plan_raw,max_nodes=16_000_000,max_depth=128)
    locations=load(read(find_output_paths(root)));helper=inside(root,(Path(locations['plan']).parent/'UnityLayoutPatch.cs').as_posix())
    if sha(plan_raw)!=receipt['patchPlanSha256']or fingerprint(helper)!=receipt['helperSha256']or fingerprint(inside(root,locations['plan']))!=plan['targetImportPlanSha256']:
        fail('LAYOUT_PREPARATION_CHANGED',str(root),'Prepared helper, patch plan or import plan changed')
    if fingerprint(source/'manifest.json')!=receipt['sourceManifestSha256']or (find_analysis(root,'layout-patch-readback.json')).exists():
        fail('LAYOUT_EXECUTION_STATE',str(root),'Frozen base changed or candidate already executed; do not reuse a failed native layer')
    protected={str(source/'manifest.json'):receipt['sourceManifestSha256']}
    for target in plan['targets']:
        for base in (root,source):
            file=inside(base,target['path'])
            expected=target.get('convertedSha256',target['sha256'])if base==root else target['sha256']
            if fingerprint(file)!=expected:fail('LAYOUT_TARGET_CHANGED',str(file),'Exact audited or successfully saved asset bytes required')
        for relative in [target['path'],target['path']+'.meta']:
            file=inside(source,relative);protected[str(file)]=fingerprint(file)
    for relative in ['Assets/Generated/Views/NativeFlowLayoutGroup.cs','Assets/Generated/Views/NativeFlowLayoutGroup.cs.meta','Assets/Generated/Views/NativeLinearLayoutGroup.cs']:
        file=inside(source,relative);protected[str(file)]=fingerprint(file)
    executable=safe(editor)
    if not executable.is_file():fail('LAYOUT_EDITOR_MISSING',str(executable),'Explicit existing Unity Editor executable required')
    start=now();deadline=utc(deadline_utc);end=utc(window_end_utc)
    if isinstance(budget_seconds,bool)or not 1<=budget_seconds<=900 or not start<deadline<=end-timedelta(minutes=2)or end-start>timedelta(minutes=30):
        fail('LAYOUT_WINDOW_INVALID','$','Require a fresh <=30 minute window, <=900 method seconds and two-minute outer reserve')
    out=new_output(output,[root,source,prepared,executable]);spec=dict(schemaVersion=1,status='planned',candidate=str(root),preparation=str(prepared),editor=str(executable),method='MonkeyImporter.ReplaceAuditedLayouts',
        preparationSha256=fingerprint(prepared/'preparation.json'),patchPlanSha256=receipt['patchPlanSha256'],helperSha256=receipt['helperSha256'],sourceManifestSha256=receipt['sourceManifestSha256'],
        budgetSeconds=budget_seconds,deadlineUtc=stamp(deadline),windowEndUtc=stamp(end),sourcePrefabs=48,targets=50,componentSlots=189,reusedAssets=receipt.get('reusedAssets',0),newTargetAssets=receipt.get('newTargetAssets',50),fullReimport=False,graphics='disabled',processStarted=False,processExited=True)
    write_json(out/'execution-plan.json',spec)
    if not execute:return dict(spec,report=str(out/'execution-plan.json'))
    plan.update(deadlineUtc=stamp(deadline),budgetSeconds=budget_seconds);write_json(plan_path,plan)
    result=dict(spec,status='running',executedPlanSha256=fingerprint(plan_path),startedUtc=stamp(now()));child=None;interrupted=[];handlers={}
    try:
        for number in (signal.SIGINT,signal.SIGTERM):handlers[number]=signal.getsignal(number);signal.signal(number,lambda number,frame:interrupted.append(number))
        with (out/'console.log').open('wb')as log:
            (out/'console.log').chmod(0o600);(out/'editor.log').touch(mode=0o600)
            child=subprocess.Popen([str(executable),'-batchmode','-nographics','-projectPath',str(root),'-executeMethod',spec['method'],'-logFile',str(out/'editor.log')],cwd=root,stdout=log,stderr=subprocess.STDOUT)
            result.update(processStarted=True,processExited=False,pid=child.pid);write_json(out/'execution-result.json',result)
            while child.poll()is None:
                if interrupted or now()>=deadline:
                    result['stopReason']='operator-interrupted'if interrupted else'internal-deadline';child.terminate();break
                with (out/'editor.log').open('rb')as engine_log:
                    engine_log.seek(max(0,(out/'editor.log').stat().st_size-65536));tail=engine_log.read(65536)
                if b"'com.unity.editor.headless' was not found"in tail or re.search(rb'\berror CS[0-9]{4}\b',tail):
                    result['stopReason']='startup-entitlement-check-failed'if b"'com.unity.editor.headless' was not found"in tail else'editor-compilation-failed'
                    child.terminate();break
                time.sleep(.5)
    except (OSError,KeyboardInterrupt)as error:result['error']=type(error).__name__
    finally:
        if child is not None and child.poll()is None:
            child.terminate()
            try:child.wait(timeout=max(.01,min(20,(end-now()).total_seconds())))
            except subprocess.TimeoutExpired:
                child.kill();child.wait(timeout=10)
        for number,handler in handlers.items():signal.signal(number,handler)
        result.update(status='partial',processExited=child is None or child.poll()is not None,exitCode=child.poll()if child else None,endedUtc=stamp(now()),redactedLog=redact_log(out/'editor.log'))
        result['frozenSourceUnchanged']=all(fingerprint(Path(p))==digest for p,digest in protected.items());write_json(out/'source-protected-hashes.json',protected)
        native=find_analysis(root,'layout-patch-readback.json')
        if native.is_file()and result['processExited']:
            body=load(read(native,max_bytes=LIMIT),max_nodes=16_000_000,max_depth=128);(out/'layout-patch-readback.json').write_bytes(read(native,max_bytes=LIMIT))
            result.update(nativeStatus=body.get('status'),nativeReason=body.get('reason'),assets=len(body.get('assets',[])),probes=len(body.get('probes',[])))
            if body.get('status')=='completed'and result.get('exitCode')==0 and result['frozenSourceUnchanged']and body.get('planSha256')==result['executedPlanSha256']:
                result['status']='completed'
        write_json(out/'execution-result.json',result)
    return dict(result,report=str(out/'execution-result.json'))


def object_headers(body):
    """Read-only native serialization identities, including non-layout components."""
    headers=list(re.finditer(rb'^--- !u!([0-9]+) &(-?[0-9]+).*$',body,re.M));result={}
    for i,h in enumerate(headers):
        key=h[2].decode()
        if key in result:fail('LAYOUT_DUPLICATE_LOCAL_ID',key,'Ambiguous serialized native object identity')
        block=body[h.end():headers[i+1].start()if i+1<len(headers)else len(body)]
        script=re.search(rb'^  m_Script:.*guid: ([0-9a-f]{32})',block,re.M)
        owner=re.search(rb'^  m_GameObject: \{fileID: (-?[0-9]+)\}',block,re.M)
        result[key]=dict(classId=int(h[1]),scriptGuid=script[1].decode()if script else None,gameObjectFileId=owner[1].decode()if owner else None)
    return result


def finish(execution,output):
    """Freeze a narrowly verified candidate and an explicit consumer-guarded delta."""
    run=safe(execution);result=load(read(run/'execution-result.json'))
    if result.get('status')!='completed'or not result.get('processExited')or result.get('exitCode')!=0 or not result.get('frozenSourceUnchanged'):
        fail('LAYOUT_NATIVE_NOT_COMPLETE',str(run),'Successful exited native subset evidence required')
    root=safe(result['candidate']);prepared=safe(result['preparation']);receipt=load(read(prepared/'preparation.json'));source=safe(receipt['source'])
    plan_path=find_analysis(root,'layout-patch-plan.json');plan=load(read(plan_path,max_bytes=LIMIT),max_nodes=16_000_000,max_depth=128)
    native_path=find_analysis(root,'layout-patch-readback.json');native_raw=read(native_path,max_bytes=LIMIT);native=load(native_raw,max_nodes=16_000_000,max_depth=128)
    if fingerprint(plan_path)!=result['executedPlanSha256']or read(run/'layout-patch-readback.json',max_bytes=LIMIT)!=native_raw or native.get('planSha256')!=result['executedPlanSha256']or native.get('status')!='completed'or not native.get('sourceRuntimeTypeAbsent')or not native.get('legacyReferencesAbsent'):
        fail('LAYOUT_NATIVE_CHANGED',str(root),'Exact successful plan/readback/runtime-closure binding required')
    original=read(source/'manifest.json',max_bytes=LIMIT)
    if sha(original)!=receipt['sourceManifestSha256']or read(root/'manifest.json',max_bytes=LIMIT)!=original:fail('LAYOUT_MANIFEST_CHANGED',str(root),'Unsealed exact base manifest required')
    base=load(original,max_nodes=16_000_000,max_depth=128);targets={t['path']:t for t in plan['targets']};assets={r['path']:r for r in native['assets']}
    if set(targets)!=set(assets)or len(targets)!=50 or len(native.get('probes',[]))!=6:fail('LAYOUT_NATIVE_COVERAGE','$','Exact asset and representative behavior coverage required')
    for path,target in targets.items():
        row=assets[path];before=read(inside(source,path),max_bytes=LIMIT);after=read(inside(root,path),max_bytes=LIMIT)
        if sha(before)!=target['sha256']or row['beforeSha256']!=target['sha256']or row['afterSha256']!=sha(after)or row['guid']!=target['guid']or row['status']not in('saved-reopened-identity-and-geometry-verified','reused-prior-saved-native-evidence')or row['missingAfter']!=0:
            fail('LAYOUT_ASSET_EVIDENCE_CHANGED',path,'Saved/reopened asset hash or identity differs')
        if row['status']=='reused-prior-saved-native-evidence':
            prior_path=inside(root,plan['priorReadbackPath'])
            if not target.get('reusedPriorEvidence')or row.get('priorReadbackSha256')!=plan['priorReadbackSha256']or fingerprint(prior_path)!=plan['priorReadbackSha256']:
                fail('LAYOUT_PRIOR_PROOF_CHANGED',path,'Reused native evidence must retain its exact history hash')
        if read(inside(source,path+'.meta'))!=read(inside(root,path+'.meta')):fail('LAYOUT_ASSET_GUID_CHANGED',path,'Prefab meta identity must stay byte-identical')
        old=object_headers(before);new=object_headers(after);retired={c['oldComponentFileId']:c for c in target['cases']};mapping={m['sourceId']:m for m in row['mappings']}
        if set(mapping)!={c['sourceId']for c in target['cases']}:fail('LAYOUT_MAPPING_COVERAGE',path,'Every retired component needs one native identity mapping')
        for local,identity in old.items():
            if local not in retired and new.get(local)!=identity:fail('LAYOUT_OTHER_IDENTITY_CHANGED',path+':'+local,'Unrelated native object or component identity changed')
        for local,case in retired.items():
            m=mapping[case['sourceId']];actual=new.get(m['newComponentFileId'])
            if old[local]['scriptGuid']!=plan['flowScriptGuid']or actual!=dict(classId=114,scriptGuid=m['scriptGuid'],gameObjectFileId=old[local]['gameObjectFileId'])or actual['scriptGuid']==plan['flowScriptGuid']or m['oldComponentFileId']!=local:
                fail('LAYOUT_REPLACEMENT_IDENTITY',path+':'+local,'Observed native component identity does not match its exact retired owner')
        if set(new)!=(set(old)-set(retired))|{m['newComponentFileId']for m in mapping.values()}:
            fail('LAYOUT_UNEXPECTED_NATIVE_OBJECTS',path,'Only audited replacement components may alter the serialized object set')
        row['allOtherSerializedObjectIdentitiesPreserved']=True
    # Recheck every indexed base file; clone-on-write must never modify the frozen source.
    for row in base['files']:
        if fingerprint(inside(source,row['path']))!=row['sha256']:fail('LAYOUT_FROZEN_SOURCE_CHANGED',row['path'],'Frozen source was modified')
    out=new_output(output,[root,source,prepared,run]);archive=root/'SourceRecovery/RetiredLayout'
    (archive/'source-manifest.json').write_bytes(original)
    choices={c['sourceId']:c for t in plan['targets']if not t['aggregate']for c in t['cases']};source_targets=[t for t in plan['targets']if not t['aggregate']]
    summary=dict(schemaVersion=1,status='native-layout-subset-verified',sourceManifestSha256=sha(original),executedPlanSha256=result['executedPlanSha256'],readbackSha256=sha(native_raw),
                 sourcePrefabs=48,sourceComponents=len(choices),assets=50,reusedNativeAssets=native.get('reusedAssets',0),componentMappings=sum(len(r['mappings'])for r in assets.values()),sourceFrozenFilesVerified=len(base['files']),
                 objectIdentity='All unrelated serialized native object IDs/types/script/owner identities preserved; exact retired-to-native local ID map in readback',
                 timing='Editor-native-forced-update',player='not_run',business='not_run',visualPixelParity='not_run',
                 probeLimitations=native.get('limitations',[]),
                 parentScope='Existing NativeLinearLayoutGroup and shared child-change notification base retained; no source flow recurrence is shipped',
                 consumerGuard='Check every old path/hash and all legacy-script references in the actual game before applying or deleting the retired script; manual changes require merge; this command never writes a game project')
    write_json(find_analysis(root,'layout-patch-summary.json'),summary)
    text=['# Native layout incremental candidate','',
          'This independent candidate replaces an audited layout subset of frozen dev3. Source limits, business drafts and Player/pixel parity status are unchanged. Original readbacks are historical; Analysis/Readback/layout-patch-readback.json is the new separately bound native evidence.','',
          'Unity GridLayoutGroup supplies sizing/wrapping/placement; the heterogeneous questionnaire uses HorizontalLayoutGroup. Disabled layouts retain authored RectTransforms and remain disabled. Exact nested template evidence supplies the two zero-dimension cases; unresolved nested content is still a separate recovery gap.','',
          'IntrinsicGridLayoutGroup changes only layout priority and empty vertical metrics. It contains no child placement/wrapping recurrence. The existing Linear helper/notification parent remains outside this scoped Flow fix. Original source and license remain in SourceRecovery/RetiredLayout and frozen history; no legal determination is made.','',
          'Before adoption, verify old hashes and every legacy script reference in the actual game; merge manual differences. Runtime source removal is permitted only after all referencing objects have been replaced. Native GameObject/RectTransform IDs and unrelated component IDs remain stable; changed layout component IDs have explicit mappings. No game was modified by this tool.','',
          '|Source Prefab|GUID|Component dispositions|','|---|---|---|']
    for target in source_targets:
        modes='; '.join(c['sourceId'].split('#')[-1]+' → '+c['mode']+(' (disabled; authored rectangles retained)'if not c['enabled']else'')for c in target['cases'])
        text.append('|'+target['path']+'|'+target['guid']+'|'+modes+'|')
    (root/'Docs/NATIVE-LAYOUT-PATCH.md').write_text('\n'.join(text)+'\n')
    structure=root/'Docs/PROJECT-STRUCTURE.md'
    structure.write_text(structure.read_text()+'\n## Native layout exception register\n\nIntrinsicGridLayoutGroup inherits Unity GridLayoutGroup: priority 1 prevents background Image metrics overriding content; empty vertical metrics collapse to padding. Plain GridLayoutGroup plus ContentSizeFitter was rejected for these two observed behaviors; HorizontalLayoutGroup covers the fixed heterogeneous row but cannot represent its uniform wrapping neighbors. No placement algorithm or source graph exists in this component. NativeLinearLayoutGroup and its notification base remain a separately scoped legacy dependency; this patch does not claim their migration. See NATIVE-LAYOUT-PATCH.md.\n')
    start=root/'Docs/START-HERE.md';start.write_text('Current incremental native layout layer: [NATIVE-LAYOUT-PATCH.md](NATIVE-LAYOUT-PATCH.md). Editor subset verified; Player/business/pixel parity not_run. Original dev3 reports remain historical.\n\n'+start.read_text())
    files=[]
    for directory in ['Assets','Packages','ProjectSettings','Analysis','Docs','SourceRecovery']:
        for file in sorted((root/directory).rglob('*')):
            if file.is_file():
                safe(file);relative=file.relative_to(root).as_posix();files.append(dict(path=relative,sha256=fingerprint(file),bytes=file.stat().st_size,owner='manual'if relative.startswith('Assets/Manual/')else'generated'))
    files.append(dict(path='AGENTS.md',sha256=fingerprint(root/'AGENTS.md'),bytes=(root/'AGENTS.md').stat().st_size,owner='generated'))
    old_files={r['path']:r for r in base['files']};new_files={r['path']:r for r in files};changes=[]
    for path in sorted(set(old_files)|set(new_files)):
        a=old_files.get(path);b=new_files.get(path)
        if a is None or b is None or a['sha256']!=b['sha256']:changes.append(dict(path=path,kind='added'if a is None else'removed'if b is None else'changed',beforeSha256=a['sha256']if a else None,afterSha256=b['sha256']if b else None))
    base['files']=files;base['nativeLayoutPatch']=summary;base['status']='partial'
    base['editorValidation']=dict(status='partial',nativeLayoutSubset='verified',originalEvidence='historical-dev3',player='not_run',sourceLimitations='retained')
    base['nativeProjectFiles']=dict(count=len(files),bytes=sum(r['bytes']for r in files),excludes=['Library','Temp','Logs','UserSettings'])
    write_json(root/'manifest.json',base)
    delta=dict(summary,candidate=str(root),candidateManifestSha256=fingerprint(root/'manifest.json'),changes=changes,assetMappings=list(assets.values()))
    write_json(out/'delta.json',delta);write_json(out/'finish-result.json',dict(status='frozen-layout-candidate',candidate=str(root),manifestSha256=delta['candidateManifestSha256'],files=len(files),changes=len(changes),assets=50,componentMappings=summary['componentMappings']))
    return dict(status='frozen-layout-candidate',candidate=str(root),manifestSha256=delta['candidateManifestSha256'],changes=len(changes),report=str(out/'finish-result.json'))


def bundle(delta_directory,output):
    """Package only the verified runtime/Prefab delta; never apply it to a game."""
    import zipfile
    delta_root=safe(delta_directory);delta=load(read(delta_root/'delta.json',max_bytes=LIMIT),max_nodes=16_000_000,max_depth=128)
    finished=load(read(delta_root/'finish-result.json'));root=safe(delta['candidate'])
    if finished.get('status')!='frozen-layout-candidate'or fingerprint(root/'manifest.json')!=delta['candidateManifestSha256']or finished['manifestSha256']!=delta['candidateManifestSha256']:
        fail('LAYOUT_BUNDLE_IDENTITY',str(root),'Exact successfully frozen candidate required')
    manifest=load(read(root/'manifest.json',max_bytes=LIMIT),max_nodes=16_000_000,max_depth=128)
    indexed={r['path']:r for r in manifest['files']};assets={r['path']:r for r in delta['assetMappings']}
    plan=load(read(find_analysis(root,'layout-patch-plan.json'),max_bytes=LIMIT),max_nodes=16_000_000,max_depth=128)
    runtime=next(p for p in indexed if p.endswith('/IntrinsicGridLayoutGroup.cs'))
    retired={'Assets/Generated/Views/NativeFlowLayoutGroup.cs','Assets/Generated/Views/NativeFlowLayoutGroup.cs.meta'}
    wanted=set(assets)|{runtime}|retired;changes={r['path']:r for r in delta['changes']}
    if not wanted<=set(changes)or len(assets)!=50:fail('LAYOUT_BUNDLE_COVERAGE','$','Exact 50 Prefabs, one runtime adapter and two retired files required')
    out=new_output(output,[root,delta_root]);payload=out/'payload';payload.mkdir();files=[];operations=[]
    def copy(relative,destination):
        source=inside(root,relative);record=indexed[relative]
        if fingerprint(source)!=record['sha256']:fail('LAYOUT_BUNDLE_CHANGED',relative,'Frozen payload bytes changed')
        target=inside(payload,destination);target.parent.mkdir(parents=True,exist_ok=True);subprocess.run(['/bin/cp','-c',str(source),str(target)],check=True)
        if fingerprint(target)!=record['sha256']:fail('LAYOUT_BUNDLE_COPY',destination,'Copy hash mismatch')
        files.append(dict(path=destination,sha256=record['sha256'],bytes=record['bytes']))
    for path in sorted(wanted):
        operation=dict(changes[path]);operations.append(operation)
        if operation['kind']=='removed':continue
        copy(path,path);meta=path+'.meta';copy(meta,meta)
        operation.update(expectedMetaSha256=indexed[meta]['sha256'],guid=assets[path]['guid']if path in assets else re.search(rb'^guid: ([0-9a-f]{32})\r?$',read(inside(root,meta)),re.M)[1].decode())
    for name in ['NativeFlowLayoutGroup.cs.txt','NativeFlowLayoutGroup.cs.meta.txt','NativeLinearLayoutGroup-parent-context.cs.txt','cocos-layout-mit.txt','README.md']:
        copy('SourceRecovery/RetiredLayout/'+name,'SourceAttribution/'+name)
    for relative in ['Analysis/Readback/layout-patch-readback.json','Analysis/Readback/layout-patch-summary.json','Docs/NATIVE-LAYOUT-PATCH.md','Docs/PROJECT-STRUCTURE.md']:
        copy(relative,'Evidence/'+relative)
    package=dict(schemaVersion=1,status='verified-layout-delta-not-applied',baseManifestSha256=delta['sourceManifestSha256'],candidateManifestSha256=delta['candidateManifestSha256'],
        operations=operations,payload=files,sourcePrefabs=48,assets=50,componentMappings=189,reusedNativeAssets=delta.get('reusedNativeAssets',0),assetMappings=delta['assetMappings'],retiredScriptGuid=plan['flowScriptGuid'],
        requiredEnvironment=dict(unity='6000.6.2f1',ugui='2.6.0'),retainedDependency='NativeLinearLayoutGroup and NativeChildLayoutGroup remain unchanged; do not delete their source file',
        guards=['Resolve exact existing asset GUIDs and old hashes; changed/manual content requires merge','Preserve all existing asset meta GUIDs and unrelated native component/object local IDs','Verify all legacy script GUID references and C# type users in the actual game before deleting the retired source/meta','Apply all coupled Prefabs and the IntrinsicGridLayoutGroup adapter together, then perform the game owner native compile/readback','This package contains no Library, original media pool or full project reimport; no game was modified'],
        limitations=delta.get('probeLimitations',[]),player='not_run',business='not_run',pixelParity='not_run')
    write_json(out/'adoption-manifest.json',package)
    (out/'README.md').write_text('Verified native layout delta; not applied to any game.\n\n50 Prefabs + one runtime adapter, with two retired source/meta deletion instructions. Preserve existing meta GUIDs. Check each old SHA and all actual game references/type users before adoption; merge manual changes. Do not copy conversion helpers or warm caches into the game. SourceAttribution retains original code/license. Evidence is limited to native layout/identity and six representative Editor probes; source Label text/Player/business/pixel parity limits remain explicit. See adoption-manifest.json for exact paths, old/new hashes, actual component identity mappings and requirements.\n')
    archive=out/'monkey-native-layout-delta.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6)as zipped:
        for file in sorted(payload.rglob('*')):
            if file.is_file():zipped.write(file,file.relative_to(out).as_posix())
        for name in ['adoption-manifest.json','README.md']:zipped.write(out/name,name)
    with zipfile.ZipFile(archive)as zipped:
        for record in files:
            with zipped.open('payload/'+record['path'])as stream:
                import hashlib
                digest=hashlib.sha256()
                for chunk in iter(lambda:stream.read(1024**2),b''):digest.update(chunk)
            if digest.hexdigest()!=record['sha256']:fail('LAYOUT_BUNDLE_ARCHIVE',record['path'],'Archive bytes differ')
    result=dict(status='verified-layout-delta-not-applied',archive=str(archive),archiveSha256=fingerprint(archive),archiveBytes=archive.stat().st_size,adoptionManifestSha256=fingerprint(out/'adoption-manifest.json'),operations=len(operations),payloadFiles=len(files),assets=50,componentMappings=189,candidateManifestSha256=delta['candidateManifestSha256'])
    write_json(out/'bundle-result.json',result);return dict(result,report=str(out/'bundle-result.json'))
