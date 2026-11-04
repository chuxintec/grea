"""Immutable, pinned continuation of component families in an existing plan."""
from pathlib import Path
import re

from . import __version__, io
from .output_limits import check_inventory, copy_verified
from .sources.compiled import fail


SCHEMA='monkey-static-prefab-continuation/1'
_SHA=re.compile(r'^[0-9a-f]{64}$')
_FAMILIES={'materials','animation','spine'}


def _summary(result):
    """Keep CLI output bounded; full family evidence remains in the plan."""
    detail=result.get('continuation',result.get('rendering',{}))
    keys=('componentCount','componentReferenceCount','clipSlotCount','sourceEvidenceAssetCount',
          'convertedCurveSlotCount','partialOrEvidenceOnlyCurveSlotCount','sourceDataAssetCount')
    nested=detail.get('summary',{})
    spine_keys=('sourceSpineComponentCount','syncInstanceComponentCount','sourceSkeletonDataAssetCount',
                'missingSourceSkeletonDataReferenceCount','missingSourceObjectReferenceCount',
                'sourceAstcPagesCopiedOpaque','sourceAstcPagesDecoded','rendered','animated',
                'sourceComponentCount','eligibleComponentCount','sourceVisibleEligibleCount','decodedPageCount','dataAssetCount')
    return {'schema':result.get('schema')or detail.get('schema')or detail.get('contract'),'status':result.get('status'),
            **{key:detail[key]for key in keys if key in detail},
            **{key:nested[key]for key in spine_keys if key in nested}}


def _input(request, name):
    spec=request.get(name)
    if not isinstance(spec,dict) or set(spec)!={'path','sha256'}:
        fail('STATIC_CONTINUATION_INPUT_INVALID',name,'Expected absolute path and exact SHA-256')
    if not isinstance(spec['path'],str) or not Path(spec['path']).is_absolute():
        fail('STATIC_CONTINUATION_INPUT_INVALID',name,'Expected an absolute path')
    if not isinstance(spec['sha256'],str) or not _SHA.fullmatch(spec['sha256']):
        fail('STATIC_CONTINUATION_INPUT_INVALID',name,'Expected a lowercase SHA-256')
    path=io.safe(spec['path']);raw=io.read(path,max_bytes=128*1024*1024)
    if io.sha(raw)!=spec['sha256']:
        fail('STATIC_CONTINUATION_INPUT_CHANGED',str(path),'Input differs from its pin')
    return path,raw


def _materials(plan, manifest_path, ir_path, output):
    from .prefab_static_time_materials import prepare as prepare_materials, attach
    relative='Continuation/StaticTimeMaterials'
    prepared=prepare_materials(manifest_path,ir_path,'unity',output/relative)
    if prepared.get('diagnostics'):
        fail('STATIC_CONTINUATION_MATERIAL_GAP','materials',str(prepared['diagnostics']))
    spec=prepared.get('spec')
    if spec is None:
        return plan,{'status':'no_matching_profile','components':0}
    for payload in spec['payloads']:
        payload['source']=relative+'/'+payload['source']
    plan=attach(plan,spec,'unity')
    return plan,{'status':'prepared','components':sum(len(row['spriteBindings'])for row in plan['staticTimeMaterials']['materials']),
                 'materials':len(spec['materials']),'sourceTimeSeconds':0.0,'dynamicBehaviorRecovered':False}


def prepare(request_path, expected_request_sha256, output):
    if not isinstance(expected_request_sha256,str) or not _SHA.fullmatch(expected_request_sha256):
        fail('STATIC_CONTINUATION_REQUEST_HASH',str(request_path),'Expected a lowercase SHA-256')
    request_path=io.safe(request_path);raw=io.read(request_path,max_bytes=1024*1024)
    if io.sha(raw)!=expected_request_sha256:
        fail('STATIC_CONTINUATION_REQUEST_HASH',str(request_path),'Request differs from its pin')
    request=io.load(raw)
    allowed={'schema','schemaVersion','plan','planManifest','ir','sourceManifest','families','spineRuntime','spineRendering','spineSourceEngine'}
    if (not isinstance(request,dict)or set(request)-allowed or request.get('schema')!=SCHEMA
            or type(request.get('schemaVersion'))is not int or request['schemaVersion']!=1):
        fail('STATIC_CONTINUATION_REQUEST_INVALID',str(request_path),'Unsupported continuation request')
    families=request.get('families',['materials','animation'])
    if (not isinstance(families,list)or not families or any(not isinstance(x,str)or x not in _FAMILIES for x in families)
            or len(set(families))!=len(families)):
        fail('STATIC_CONTINUATION_FAMILIES_INVALID','families','Expected distinct supported component families')
    rendering=request.get('spineRendering',False)
    if (type(rendering)is not bool or rendering and ('spine'not in families or 'spineRuntime'not in request or 'spineSourceEngine'not in request)
            or 'spineSourceEngine'in request and not rendering):
        fail('STATIC_CONTINUATION_RENDERING_INVALID','spineRendering','Rendering requires the spine family, pinned runtime and independently pinned source engine file')
    paths={};raws={}
    for name in ('plan','planManifest','ir','sourceManifest'):
        paths[name],raws[name]=_input(request,name)
    if rendering:
        paths['spineSourceEngine'],raws['spineSourceEngine']=_input(request,'spineSourceEngine')
    if paths['planManifest']!=paths['plan'].parent/'manifest.json':
        fail('STATIC_CONTINUATION_SOURCE_MISMATCH','planManifest','Expected the plan owning stage manifest')
    plan=io.stage_document(paths['plan']);ir=io.stage_document(paths['ir'])
    manifest=io.load(raws['sourceManifest'],max_nodes=8_000_000)
    if not all(isinstance(value,dict)for value in (plan,ir,manifest)):
        fail('STATIC_CONTINUATION_INPUT_INVALID','inputs','Expected JSON objects')
    if (plan.get('targetProfile')!='unity-6000.6.2f1-ugui' or plan.get('schemaVersion')!=1
            or ir.get('sourceProfile')!='cocos-2.4.15-bundle' or manifest.get('sourceProfile')!=ir.get('sourceProfile')
            or manifest.get('sourceVersion')!='2.4.15'):
        fail('STATIC_CONTINUATION_PROFILE_UNSUPPORTED','profile','Expected the Cocos 2.4.15 to native Unity UI profile')
    if (plan.get('sourceIrSha256')!=io.sha(raws['ir'])
            or plan.get('sourceManifestSha256')!=io.sha(raws['sourceManifest'])
            or ir.get('sourceManifestSha256')!=io.sha(raws['sourceManifest'])
            or io.safe(plan.get('sourceManifestPath',''))!=paths['sourceManifest']):
        fail('STATIC_CONTINUATION_SOURCE_MISMATCH','inputs','Plan, IR and source manifest do not share exact pins')
    runtime_manifest=None;runtime_root=None;runtime_path=None;runtime_sha=None
    if 'spineRuntime'in request and 'spine'not in families:
        fail('STATIC_CONTINUATION_RUNTIME_INVALID','spineRuntime','SDK input requires the spine family')
    if 'spine'in families and 'spineRuntime'in request:
        runtime=request.get('spineRuntime')
        if not isinstance(runtime,dict)or set(runtime)!={'manifest','assetsRoot'}:
            fail('STATIC_CONTINUATION_RUNTIME_REQUIRED','spineRuntime','Explicit pinned SDK backup is required')
        runtime_path,runtime_raw=_input(runtime,'manifest')
        runtime_sha=io.sha(runtime_raw)
        if not isinstance(runtime['assetsRoot'],str)or not Path(runtime['assetsRoot']).is_absolute():
            fail('STATIC_CONTINUATION_RUNTIME_INVALID','spineRuntime.assetsRoot','Expected an absolute directory path')
        runtime_root=io.safe(runtime['assetsRoot'])
        if not runtime_root.is_dir():
            fail('STATIC_CONTINUATION_RUNTIME_INVALID',str(runtime_root),'SDK asset root is not a directory')
        runtime_manifest=io.load(runtime_raw,max_nodes=8_000_000)
        paths['spineRuntimeManifest']=runtime_path;raws['spineRuntimeManifest']=runtime_raw
    inventory=io.load(raws['planManifest'],max_nodes=8_000_000)
    check_inventory(inventory['files'],inventory,str(paths['plan']))
    out=io.new_output(output,[request_path,*[p.parent for p in paths.values()],*([runtime_root]if runtime_root else[])])
    stage=out/'plan';stage.mkdir()
    for row in inventory['files']:
        if row['path']==paths['plan'].name:continue
        copy_verified(io.inside(paths['plan'].parent,row['path']),io.inside(stage,row['path']),row['sha256'],row['bytes'])
    results={}
    if 'materials'in families:
        plan,results['materials']=_materials(plan,paths['sourceManifest'],paths['ir'],stage)
    if 'animation'in families:
        from .prefab_static_animation_continuation import prepare as prepare_animation
        result=prepare_animation(plan,ir,manifest,stage)
        plan=result['plan'];results['animation']=_summary(result)
    if 'spine'in families:
        from .prefab_static_spine_continuation import prepare as prepare_spine
        result=prepare_spine(plan,ir,manifest,stage,unity_runtime_manifest=runtime_manifest,
                             unity_runtime_manifest_path=runtime_path,unity_runtime_manifest_sha256=runtime_sha,
                             unity_runtime_assets_root=runtime_root)
        plan=result['plan'];results['spine']=_summary(result)
        if rendering:
            from .prefab_static_spine_rendering import prepare as prepare_rendering
            generator=Path(__file__).parent/'targets/UnityImporter.cs'
            plan['staticSpineRenderingTargetUnits']={
                'status':'declared_generator_mapping_requires_native_verification',
                'targetUnitsPerSourcePixel':1.0,'coordinateSpace':'source-pixels-to-ugui-local-units',
                'generatorSourceSha256':io.sha(io.read(generator)),
                'runtimeCheck':'exact-plan-node-RectTransform-fields-and-actual-canvas-reference-ppu'}
            result=prepare_rendering(plan,stage,plan['staticSpineContinuation']['runtimeDependency'],stage/'spine_static_rendering',
                                     source_engine_file=paths['spineSourceEngine'],expected_source_engine_sha256=io.sha(raws['spineSourceEngine']))
            plan=result['plan'];results['spineRendering']=_summary(result)
    if (io.sha(io.read(request_path,max_bytes=1024*1024))!=expected_request_sha256
            or any(io.sha(io.read(path,max_bytes=128*1024*1024))!=io.sha(raws[name])for name,path in paths.items())):
        fail('STATIC_CONTINUATION_INPUT_CHANGED','inputs','A frozen input changed during continuation; output is incomplete')
    plan['toolVersion']=__version__
    plan['staticContinuation']={'schema':SCHEMA,'parentPlanSha256':io.sha(raws['plan']),
                                'families':families,'spineRendering':rendering,'sourceBusinessExecuted':False,'native':'not_run'}
    io.write_json(stage/'plan.json',plan);io.finish(stage,plan)
    report={'schema':SCHEMA,'schemaVersion':1,'toolVersion':__version__,'preparationStatus':'prepared',
            'requestSha256':expected_request_sha256,'inputs':{name:{'path':str(path),'sha256':io.sha(raws[name])}for name,path in paths.items()},
            'planPath':str(stage/'plan.json'),'familyResults':results,'native':'not_run','visual':'not_run',
            'sourceBusinessExecuted':False,'diagnostics':[]}
    io.finish(out,report)
    return report
