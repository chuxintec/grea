"""Apply proven Creator version defaults without changing serialized source facts."""
import copy
from pathlib import Path
from . import io,__version__
from .output_limits import check_inventory,copy_verified

CONTRACT='monkey-cocos-spine-version-defaults/1'
SCHEMA='monkey-static-spine-default-completion/1'
ENGINE_SHA='7cdc119e26aa6dceec4bd78ae30dd08f39daa2f0da5d914d2197a730b558a5e8'
ENGINE_LOGICAL='extensions/spine/Skeleton.js'
ENGINE_URL='https://raw.githubusercontent.com/cocos/cocos-engine/v2.4.15/'+ENGINE_LOGICAL

def render_pma(row):
    raw=row.get('sourcePma')or{}
    if raw.get('valueKnown')is True and type(raw.get('value'))is bool:return raw['value']
    effective=row.get('effectivePma')or{}
    if (effective.get('contract')==CONTRACT and effective.get('sourceVersion')=='2.4.15'
        and effective.get('sourceEngineSha256')==ENGINE_SHA and effective.get('field')=='premultipliedAlpha'
        and effective.get('valueKnown')is True and effective.get('value')is True
        and type(raw.get('unknownComponentCount'))is int and raw['unknownComponentCount']>0
        and isinstance(raw.get('knownValues'),list)and all(value is True for value in raw['knownValues'])):
        return True
    return None

def apply_defaults(plan,engine_path,engine_sha):
    path=io.safe(engine_path);raw=io.read(path,max_bytes=2*1024**2)
    if engine_sha!=ENGINE_SHA or io.sha(raw)!=ENGINE_SHA:raise ValueError('SPINE_DEFAULT_ENGINE_PIN_INVALID')
    fragment=plan.get('staticSpineContinuation')or{}
    if fragment.get('sourceVersion')!='2.4.15'or fragment.get('sourceProfile')!='cocos-2.4.15-bundle':
        raise ValueError('SPINE_DEFAULT_SOURCE_VERSION_UNSUPPORTED')
    if fragment.get('sourceManifestSha256')!=plan.get('sourceManifestSha256'):
        raise ValueError('SPINE_DEFAULT_SOURCE_MANIFEST_MISMATCH')
    patched=copy.deepcopy(plan);source=patched['staticSpineContinuation'];components=[];assets=[];gaps=[]
    for data in source['dataAssets']:
        sid=data['sourceDataAssetId'];rows=[c for c in source['components']
            if c.get('sourceDataReference',{}).get('sourceDataAssetId')==sid]
        if not rows:continue
        values=[];missing=[]
        for c in rows:
            state=c.get('sourceFieldStates',{}).get('premultipliedAlpha')
            if not isinstance(state,dict)or type(state.get('present'))is not bool:
                raise ValueError('SPINE_DEFAULT_SOURCE_FIELD_STATE_MISSING:'+c['sourceComponentId'])
            if state['present']:
                if type(state.get('value'))is not bool:raise ValueError('SPINE_DEFAULT_SOURCE_FIELD_TYPE_INVALID')
                values.append(state['value'])
            else:values.append(True);missing.append(c['sourceComponentId'])
        if not missing:continue
        if len(set(values))!=1:
            gaps.append(dict(sourceDataAssetId=sid,sourceComponentIds=[c['sourceComponentId']for c in rows],
                field='premultipliedAlpha',code='SOURCE_PMA_EFFECTIVE_VALUES_CONFLICT'));continue
        if data.get('sourcePma',{}).get('unknownComponentCount')!=len(missing):
            raise ValueError('SPINE_DEFAULT_COMPONENT_DENOMINATOR_MISMATCH:'+sid)
        data['effectivePma']=dict(contract=CONTRACT,sourceVersion='2.4.15',sourceEngineSha256=ENGINE_SHA,
            field='premultipliedAlpha',valueKnown=True,value=True,source='pinned-source-version-default')
        components.extend(missing);assets.append(sid)
    proof=dict(contract=CONTRACT,sourceVersion='2.4.15',sourceEngine=dict(logicalPath=ENGINE_LOGICAL,
        sha256=ENGINE_SHA,originUrl=ENGINE_URL),fields=dict(premultipliedAlpha=True),
        componentSourceIds=sorted(components),dataAssetSourceIds=sorted(assets),gaps=gaps,
        serializedSourceFieldPresencePreserved=True,sourceCodeExecuted=False)
    patched['staticSpineDefaultCompletion']=proof
    return patched,proof

def prepare(request_path,expected_request_sha256,output):
    from .prefab_static_continuation import _input,_SHA
    path=io.safe(request_path);raw=io.read(path,max_bytes=1024**2)
    if not _SHA.fullmatch(expected_request_sha256 or '')or io.sha(raw)!=expected_request_sha256:
        raise ValueError('SPINE_DEFAULT_REQUEST_PIN_INVALID')
    request=io.load(raw)
    if (set(request)!={'schema','schemaVersion','plan','planManifest','sourceComponentEngine'}
        or request['schema']!=SCHEMA or type(request['schemaVersion'])is not int or request['schemaVersion']!=1):
        raise ValueError('SPINE_DEFAULT_REQUEST_INVALID')
    paths={};inputs={}
    for key in ('plan','planManifest','sourceComponentEngine'):paths[key],inputs[key]=_input(request,key)
    if paths['planManifest']!=paths['plan'].parent/'manifest.json':raise ValueError('SPINE_DEFAULT_PLAN_OWNER_INVALID')
    plan=io.stage_document(paths['plan']);manifest=io.load(inputs['planManifest'],max_nodes=8_000_000)
    check_inventory(manifest['files'],manifest,str(paths['plan']))
    patched,proof=apply_defaults(plan,paths['sourceComponentEngine'],io.sha(inputs['sourceComponentEngine']))
    out=io.new_output(output,[path,*[p.parent for p in paths.values()]])
    stage=out/'plan';stage.mkdir()
    for row in manifest['files']:
        if row['path']==paths['plan'].name:continue
        copy_verified(io.inside(paths['plan'].parent,row['path']),io.inside(stage,row['path']),row['sha256'],row['bytes'])
    rendering=patched.get('staticSpineRendering')or{}
    engine=rendering.get('sourceEngine')or{}
    from .prefab_static_spine_rendering import prepare_rendering
    result=prepare_rendering(patched,stage,patched['staticSpineContinuation']['runtimeDependency'],
        stage/'spine_static_defaults_rendering',source_engine_file=engine.get('path'),
        expected_source_engine_sha256=engine.get('sha256'),reuse_rendering=rendering)
    patched=result['plan'];patched['staticSpineRendering']['sourceComponentDefaults']=proof
    io.write_json(stage/'spine_static_defaults_rendering/spine-static-rendering.json',patched['staticSpineRendering'])
    for key,p in paths.items():
        if io.sha(io.read(p,max_bytes=128*1024**2))!=io.sha(inputs[key]):raise ValueError('SPINE_DEFAULT_INPUT_CHANGED')
    if io.sha(io.read(path))!=expected_request_sha256:raise ValueError('SPINE_DEFAULT_REQUEST_CHANGED')
    patched['toolVersion']=__version__;io.write_json(stage/'plan.json',patched);io.finish(stage,patched)
    report=dict(schema=SCHEMA,schemaVersion=1,toolVersion=__version__,status='prepared',sourceDefaults=proof,
        planPath=str(stage/'plan.json'),rendering=patched['staticSpineRendering']['summary'],
        sourceCodeExecuted=False,native='not_run',visual='not_run')
    return io.finish(out,report)
