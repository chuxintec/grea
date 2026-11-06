"""Explicit target path slots, asset identities and ownership; never arbitrary JSON rewrites."""
from pathlib import Path,PurePosixPath
from .io import safe,read,load,sha,new_output,write_json,stage_manifest,inside
from .sources.compiled import fail
from .targets import unity,cocos

PATH_FIELDS={'assets':('path','fontAssetPath'),'textures':('path',),'bitmapFonts':('path','fontPath'),
             'animations':('path',),'sourcePrefabs':('path',)}


def asset_path(value,profile):
    prefix='Assets/' if profile==unity.PROFILE else 'assets/'
    if not isinstance(value,str) or not value.startswith(prefix) or '\\' in value or '\x00' in value or ':' in value:
        fail('PROJECT_TYPED_PATH',str(value),'Expected target asset-relative path')
    parts=value.split('/')
    if any(p in ('','.','..') for p in parts) or PurePosixPath(value).is_absolute():
        fail('PROJECT_TYPED_PATH',value,'Unsafe typed asset path')
    return value


def replace_slots(document,slots,changes):
    """Only declared path scalars can change. Source names, text and dynamic keys are untouched."""
    import copy
    result=copy.deepcopy(document)
    seen=set()
    for slot in slots:
        pointer=slot['pointer'];key=tuple(pointer)
        if key in seen:fail('PROJECT_SLOT_DUPLICATE',str(pointer),'Repeated typed slot')
        seen.add(key);parent=result
        for part in pointer[:-1]:parent=parent[part]
        if parent[pointer[-1]]!=slot['path']:fail('PROJECT_SLOT_STALE',str(pointer),'Path differs from frozen slot')
        if slot['path'] in changes:
            profile=unity.PROFILE if slot['path'].startswith('Assets/') else cocos.PROFILE
            parent[pointer[-1]]=asset_path(changes[slot['path']],profile)
    return result


def import_plan_model(document,profile):
    if profile not in (unity.PROFILE,cocos.PROFILE):fail('PROJECT_PROFILE',profile,'Unsupported native target')
    slots=[];assets=[]
    for collection,fields in PATH_FIELDS.items():
        for index,item in enumerate(document.get(collection,[])):
            source_id=item.get('sourceId',item.get('id'))
            if not isinstance(source_id,str):fail('PROJECT_SOURCE_ID',collection,'Expected explicit source identity')
            paths={}
            for field in fields:
                if item.get(field) is not None:
                    paths[field]=asset_path(item[field],profile)
                    slots.append(dict(pointer=[collection,index,field],path=paths[field],sourceId=source_id))
            identity={k:item[k] for k in ('uuid','guid','nativeId','atlasGuid') if item.get(k) is not None}
            assets.append(dict(sourceId=source_id,collection=collection,nativeKind=item.get('kind',collection),paths=paths,
                               identity=identity,identityState='declared' if identity else 'native_assignment_pending',
                               subresource=item.get('subresource'),rootNode=item.get('root')))
    return dict(schemaVersion=1,targetProfile=profile,pathSlots=slots,assets=assets,
                policy='explicit-target-fields-v1',sourceNamesAndDynamicKeysRewritten=False)


def inspect(candidate,output):
    candidate=safe(candidate);m=stage_manifest(candidate);profile=m.get('targetProfile')
    if profile not in (unity.PROFILE,cocos.PROFILE):fail('PROJECT_PROFILE',str(candidate),'Expected known target candidate')
    from .layout import locate
    path=(locate(m,'importPlan') if profile==unity.PROFILE
          else 'extensions/monkey-import/import-plan.json')
    plan=inside(candidate,path);raw=read(plan,max_bytes=128*1024*1024)
    entry=next((f for f in m['files'] if f['path']==path),None)
    if not entry or sha(raw)!=entry['sha256']:fail('PROJECT_PLAN_CHANGED',path,'Owned plan identity differs')
    model=import_plan_model(load(raw,max_nodes=8_000_000),profile)
    files=[]
    for f in m['files']:
        inside(candidate,f['path'])
        files.append(dict(path=f['path'],sha256=f['sha256'],bytes=f['bytes'],owner=f.get('owner','unknown')))
    model.update(candidateManifestSha256=sha(read(candidate/'manifest.json',max_bytes=128*1024*1024)),
                 importPlan=dict(path=path,sha256=sha(raw)),files=files,formatApplied=False,
                 nativeIdentityWarning='Unmaterialized source Prefabs lack actual GUID/UUID; no inferred identity claim')
    out=new_output(output,[candidate]);write_json(out/'project-model.json',model)
    return dict(status='modeled',assets=len(model['assets']),typedPathSlots=len(model['pathSlots']),
                nativeAssignmentPending=sum(a['identityState']=='native_assignment_pending' for a in model['assets']),
                formatApplied=False,report=str(out/'project-model.json'))
