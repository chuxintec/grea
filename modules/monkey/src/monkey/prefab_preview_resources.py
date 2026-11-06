"""Reuse explicitly selected, hash-owned sprite resources for static state previews."""
from copy import deepcopy
from . import io
from .output_limits import copy_verified
from .sources.compiled import fail


def select_sprites(ir_path, source_ids, output):
    path=io.safe(ir_path); ir=io.stage_document(path)
    selected=set(source_ids)
    if not selected or len(selected)!=len(source_ids):fail('PREVIEW_RESOURCE_SELECTION','sourceIds','Use unique explicit IDs')
    frames=[f for f in ir['spriteFrames']if f['sourceId']in selected]
    if {f['sourceId']for f in frames}!=selected:fail('PREVIEW_RESOURCE_MISSING','sourceIds','Selected sprite absent')
    owner={f['path']:f for f in io.stage_manifest(path.parent)['files']}
    out=io.new_output(output,[path.parent])
    for relative in sorted({f[k]for f in frames for k in ('image','originalImage')}):
        record=owner.get(relative)
        if not record:fail('PREVIEW_RESOURCE_UNOWNED',relative,'Resource is absent from stage manifest')
        copy_verified(io.inside(path.parent,relative),io.inside(out,relative),record['sha256'],record['bytes'])
    result=dict(schemaVersion=1,sourceProfile=ir['sourceProfile'],sourceManifestSha256=ir['sourceManifestSha256'],
                sourceRoots=ir.get('sourceRoots',{}),sourceNames={s:ir.get('sourceNames',{}).get(s,{})for s in selected},
                sourceLocations={},diagnostics=[],assets=[],nodes=[],components=[],spriteFrames=frames,bitmapFonts=[],
                materials=[],animationClips=[],prefabInstances=[],aliases={},quarantinedAssets=[],evidenceFiles=[],
                previewResourceSelection=dict(parentIrSha256=io.sha(io.stage_bytes(path)),sourceIds=sorted(selected)))
    io.write_json(out/'ir.json',result);return io.finish(out,result)


def merge_resources(base_plan_path, resource_plan_path, output):
    base_path,extra_path=io.safe(base_plan_path),io.safe(resource_plan_path)
    base,extra=io.stage_document(base_path),io.stage_document(extra_path)
    if base['targetProfile']!=extra['targetProfile']or base['namespace']!=extra['namespace']:
        fail('PREVIEW_RESOURCE_TARGET','plan','Target profile and namespace must match')
    if extra.get('nodes')or extra.get('components')or extra.get('sourcePrefabs'):
        fail('PREVIEW_RESOURCE_SCOPE','plan','Supplement must contain only resource assets')
    retained=set();skip_targets=set()
    if base['targetProfile'].startswith('unity'):
        existing={t['id']:t for t in base.get('textures',[])}
        base_copies={c['target']:c for c in base['copies']};extra_copies={c['target']:c for c in extra['copies']}
        for t in extra.get('textures',[]):
            if t['id']not in existing:continue
            old=existing[t['id']]
            if any(old.get(k)!=t.get(k)for k in ('size','originalSize','offset','border')) or base_copies[old['path']]['sha256']!=extra_copies[t['path']]['sha256']:
                fail('PREVIEW_RESOURCE_ID_COLLISION',t['id'],'Overlapping source texture differs')
            retained.add(t['id']);skip_targets.add(t['path'])
    result=deepcopy(base);out=io.new_output(output,[base_path.parent,extra_path.parent])
    for f in io.stage_manifest(base_path.parent)['files']:
        if f['path']=='plan.json':continue
        copy_verified(io.inside(base_path.parent,f['path']),io.inside(out,f['path']),f['sha256'],f['bytes'])
    owner={f['path']:f for f in io.stage_manifest(extra_path.parent)['files']}
    prefix='preview-resources/'+io.sha(io.stage_bytes(extra_path))[:16]+'/'
    targets={c['target']for c in result['copies']}
    for c in extra['copies']:
        if c['target']in skip_targets:continue
        if c['target']in targets:fail('PREVIEW_RESOURCE_COLLISION',c['target'],'Supplement target already exists')
        targets.add(c['target']);record=owner.get(c['source'])
        if not record or record['sha256']!=c['sha256']:fail('PREVIEW_RESOURCE_UNOWNED',c['source'],'Supplement hash differs')
        new_source=prefix+c['source'];copy_verified(io.inside(extra_path.parent,c['source']),io.inside(out,new_source),record['sha256'],record['bytes'])
        result['copies'].append(dict(c,source=new_source))
    for key in ('textures','assets'):
        if key not in extra:continue
        identity='id' if key=='textures' or base['targetProfile'].startswith('unity') else 'sourceId'
        known={a[identity]for a in result.get(key,[])}
        additions=[a for a in extra[key]if not(key=='textures'and a[identity]in retained)]
        if any(a[identity]in known for a in additions):fail('PREVIEW_RESOURCE_ID_COLLISION',key,'Resource identity already exists')
        result.setdefault(key,[]).extend(additions)
    result.setdefault('previewResourceStages',[]).append(dict(planSha256=io.sha(io.stage_bytes(extra_path)),sourceManifestSha256=extra['sourceManifestSha256']))
    io.write_json(out/'plan.json',result);return io.finish(out,result)
