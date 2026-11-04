"""Explicit immutable continuation of a frozen native static candidate plan.

Reuses previously verified resource payloads; adds typed component/resource
bindings from pinned original evidence. No page-specific branches or edits to
existing candidates are permitted by this operation.
"""
from pathlib import Path
import copy
from . import io
from .output_limits import copy_verified


def prepare(plan_path, ir_path, output, *, font_completion=None):
    source=Path(plan_path).resolve();ir_path=Path(ir_path).resolve()
    plan=io.stage_document(source);ir=io.stage_document(ir_path)
    if io.sha(ir_path.read_bytes())!=plan['sourceIrSha256']:
        raise ValueError('STATIC_COMPLETION_IR_IDENTITY_DIFFERS')
    raw=io.stage_bytes(Path(plan['sourceManifestPath']))
    if io.sha(raw)!=plan['sourceManifestSha256']:raise ValueError('STATIC_COMPLETION_SOURCE_CHANGED')
    manifest=io.load(raw,max_nodes=8_000_000)
    out=io.new_output(output,[source.parent,ir_path.parent])
    for row in io.stage_manifest(source.parent)['files']:
        if row['path']!=source.name:
            copy_verified(io.inside(source.parent,row['path']),io.inside(out,row['path']),row['sha256'],row['bytes'])
    if font_completion is not None:
        if not plan['targetProfile'].startswith('unity-'):raise ValueError('STATIC_FONT_COMPLETION_TARGET_INVALID')
        from .prefab_static_font_completion import apply_prepared
        plan=apply_prepared(plan,font_completion['receipt'],font_completion['receiptSha256'],font_completion['bindingSha256'],out)['plan']
    from .prefab_static_asset_completion import _missing_refs,prepare_for_target as prepare_source_assets
    resource_completion=None
    if _missing_refs(plan,manifest)[0]:
        resource_completion=prepare_source_assets(plan,Path(plan['sourceManifestPath']),out/'SourceAssetCompletion')
        plan=resource_completion['plan']
        plan['sourceResourceCompletion']['stageRelativePath']='SourceAssetCompletion'
    from .prefab_static_button import enrich
    from .prefab_static_toggle import _resolve_component
    button_origins={row['instanceSourceId']:row['templateSourceId'] for relation in plan.get('syncPrefabBindings',[]) for row in relation.get('componentOrigins',[])}
    button_pairs=[]
    for component in plan['components']:
        if component['type']!='cc.Button' or component.get('transition') not in (0,1,3):continue
        if component.get('staticButtonBinding'):continue
        sid=component['sourceId'];seen=set()
        while sid in button_origins:
            if sid in seen:raise ValueError('STATIC_BUTTON_ORIGIN_CYCLE')
            seen.add(sid);sid=button_origins[sid]
        _,node,_=_resolve_component(manifest,sid,'cc.Button')
        proxy=copy.deepcopy(component);proxy['sourceId']=sid;proxy['node']=node
        button_pairs.append((component,proxy,sid))
    enrich(dict(sourceProfile=manifest['sourceProfile'],sourceManifestPath=plan['sourceManifestPath'],sourceManifestSha256=plan['sourceManifestSha256'],components=[p for _,p,_ in button_pairs]))
    for component,proxy,sid in button_pairs:
        binding=proxy.get('staticButtonBinding')
        if binding:
            binding['sourceId']=component['sourceId'];binding['sourceNodeId']=component['node']
            binding['sourceOriginId']=sid;component['staticButtonBinding']=binding
    nodes={n['sourceId']:n for n in plan['nodes']}
    bitmap_ids={f['id'] for f in plan.get('bitmapFonts',[])}|{a['sourceId'] for a in plan.get('assets',[])if a.get('kind')=='bitmap'}
    for c in plan['components']:
        if c['type']=='cc.Label':c['bitmapLabel']=c.get('font') in bitmap_ids
    from .prefab_bitmap_missing_glyphs import prepare as prepare_bitmap_missing
    plan['bitmapMissingGlyphs']=prepare_bitmap_missing(plan,manifest)
    for binding in plan['bitmapMissingGlyphs']['components']:
        component=next(c for c in plan['components']if c['sourceId']==binding['sourceComponentId'])
        component.update(convertible=True,bitmapMissingGlyphPolicy=binding['policy'],bitmapMissingGlyphDisplayText=binding['displayText'])
        if plan['targetProfile'].startswith('cocos-'):
            component.update(nativeType='cc.Label',nativeOverflow=component['overflow'],sizingPolicy='native-label-sizing-v1')
    for component in plan['components']:
        if component['type']=='cc.Button' and component.get('staticButtonBinding',{}).get('renderReady') and component.get('target') in (set(nodes)|{None}):
            component['convertible']=True
            if plan['targetProfile'].startswith('cocos-'):component['nativeType']='cc.Button'
        if component['type']=='cc.Label' and plan['targetProfile'].startswith('unity-') and (component.get('italic') or component.get('underline')):
            codes={d['code'] for d in plan['diagnostics'] if d.get('sourceId')==component['sourceId']}
            allowed={'UNSUPPORTED_COMPONENT_SEMANTIC','SYSTEM_FONT_PLATFORM_UNVERIFIED','LABEL_STYLE_UNSUPPORTED','LABEL_METRICS_NOT_VERIFIED','COMPONENT_HANDOFF'}
            if 'LABEL_STYLE_UNSUPPORTED' in codes and codes<=allowed:
                component['convertible']=True;component['nativeTextStylePolicy']='tmp-font-style-flags-v1'
    from .targets.progress import configure_progress
    configure_progress(plan['components'],nodes)
    origins={}
    for relation in plan.get('syncPrefabBindings',[]):
        for row in relation.get('componentOrigins',[]):
            sid,tid=row['instanceSourceId'],row['templateSourceId']
            if sid in origins and origins[sid]!=tid:raise ValueError('STATIC_COMPLETION_COMPONENT_ORIGIN_AMBIGUOUS')
            origins[sid]=tid
    def root(sid):
        seen=set()
        while sid in origins:
            if sid in seen:raise ValueError('STATIC_COMPLETION_COMPONENT_ORIGIN_CYCLE')
            seen.add(sid);sid=origins[sid]
        return sid
    plan['staticAnimationComponentOrigins']=[dict(instanceSourceId=sid,templateSourceId=root(sid)) for sid in sorted(origins)]
    for c in plan['components']:
        if c.get('staticProgressBinding') and c['sourceId'] in origins:c['staticProgressBinding']['sourceTemplateId']=root(c['sourceId'])
        if c['type']=='cc.Animation':c['defaultClipKnown']='defaultClip' in c
    if plan.get('staticTimeMaterials'):
        from .prefab_static_time_materials import prepare as prepare_time, attach as attach_time
        target='creator' if plan['targetProfile'].startswith('cocos-') else 'unity'
        time=prepare_time(Path(plan['sourceManifestPath']),ir_path,target,out/'StaticTimeCompletion')
        for payload in time['spec']['payloads']:payload['source']='StaticTimeCompletion/'+payload['source']
        attach_time(plan,time['spec'],target)
    from .prefab_static_presentation import apply_unity, apply_creator
    (apply_creator if plan['targetProfile'].startswith('cocos-') else apply_unity)(plan,manifest)
    from .prefab_static_mask_sort import prepare as prepare_masks
    import json
    plan['staticMasks']=prepare_masks(plan,manifest)
    for mask in plan['staticMasks']['masks']:mask['sourceFieldsJson']=json.dumps(mask['sourceFields'],sort_keys=True,ensure_ascii=False,separators=(',',':'))
    from .prefab_static_layout_completion import prepare as prepare_layout
    plan['layoutCompletion']=prepare_layout(plan,manifest)
    from .prefab_static_controls import prepare as prepare_controls
    plan['staticControls']=prepare_controls(plan,manifest)
    from .prefab_static_sort_queue import to_unity_proxy_spec,to_creator_proxy_spec
    sort_spec=to_creator_proxy_spec if plan['targetProfile'].startswith('cocos-') else to_unity_proxy_spec
    plan['staticSortQueue']=[sort_spec(plan,manifest,prefab['root']) for prefab in plan.get('sourcePrefabs',[])]
    from .prefab_static_particle import prepare as prepare_particles
    prepare_particles(plan,manifest,out)
    from .prefab_static_retained_assets import prepare as prepare_assets
    retained=prepare_assets(plan,Path(plan['sourceManifestPath']),out/'RetainedAssets')
    plan=retained['plan']
    if resource_completion:
        contract=resource_completion['contract']
        for asset in contract['assets']:
            if asset['sourceType']!='cc.Texture2D':continue
            payloads={r['target']:r for r in contract['payloads']}
            plan['staticRetainedAssets']['assets'].append(dict(sourceId=asset['sourceId'],sourceType=asset['sourceType'],retentionKind='texture-asset',
                sourceNative=asset['sourceNative'],dimensions=asset['decodedSize'],rgbaSha256=asset['decodedRgbaSha256'],
                unityPngSha256=payloads[asset['unity']['path']]['sha256'],creatorPngSha256=payloads[asset['creator']['path']]['sha256'],
                unity=asset['unity'],creator=dict(asset['creator'],uuid=asset['creator']['textureUuid'])))
    for row in retained['contract']['copies']:row['source']='RetainedAssets/'+row['source']
    for row in retained['contract']['payloads']:row['source']='RetainedAssets/'+row['source']
    from .prefab_static_animation import prepare_static_animation_assets,plan_source_asset_animation_clips
    evidence=prepare_static_animation_assets(plan,manifest,out)
    if evidence['diagnostics']:raise ValueError('STATIC_ANIMATION_SOURCE_EVIDENCE_MISSING: '+str(evidence['diagnostics']))
    plan['staticAnimationEvidence']=[dict(sourceClipId=a['sourceClipId'],path=a['path'],sha256=a['nativeAssetSha256']) for a in evidence['assets']]
    for a in evidence['assets']:
        if plan['targetProfile'].startswith('cocos-'):
            from .targets.cocos import identity
            plan['assets'].append(dict(sourceId=a['sourceClipId']+'@static-animation-evidence',path=a['path'],kind='json',uuid=identity(plan['namespace'],a['sourceClipId']+'@static-animation-evidence'),sha256=a['nativeAssetSha256']))
        from .targets.unity import guid
        plan['copies'].append(dict(source=a['path'],target=a['path'],sha256=a['nativeAssetSha256'],guid=guid(plan['namespace'],a['sourceClipId']+'@static-animation-evidence'),sourceId=a['sourceClipId']+'@static-animation-evidence',role='static-animation-source-evidence'))
    selected=[sid for sid,usages in evidence['sourceClipUsages'].items() if any(u['kind']=='static_field_asset_ref' for u in usages)]
    standalone=plan_source_asset_animation_clips(ir,selected,plan['targetProfile'])
    if any(not clip['convertible'] for clip in standalone['clips']):raise ValueError('STATIC_ANIMATION_DIRECT_FIELD_RESOURCE_UNSUPPORTED')
    plan['animations'].extend(standalone['clips'])
    plan['staticAnimationAssetReferences']=[dict(sourceId=a['sourceClipId'],animationId=a['id'],path=a['path']) for a in standalone['clips']]
    plan['staticCompletion']={'schemaVersion':1,'parentPlanSha256':io.sha(source.read_bytes()),'sourceIrSha256':plan['sourceIrSha256'],'dynamicBusiness':'disabled_or_partial','visual':'pending_user_review'}
    io.write_json(out/'plan.json',plan)
    return io.finish(out,plan)
