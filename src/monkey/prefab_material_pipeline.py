"""Automatic exact-profile material planning with owned target payloads."""
import base64
import math
from importlib.resources import files
from pathlib import Path
from .io import inside, read, sha, diagnostic
from .sources.compiled import fail


def discover(ir, ir_path):
    standard={m['sourceId'] for m in ir.get('materials',[]) if m.get('nativeRole')=='standard-ugui'}
    custom={m for c in ir.get('components',[]) for m in c.get('materials',[]) if m not in standard}
    if not custom or ir.get('sourceProfile') not in ('cocos-2.4.15-bundle','cocos-2.4.15-project'):
        return None, []
    source=ir.get('sourceManifestPath')
    if not source:
        return None, []
    from .prefab_materials import plan_ui_color, MaterialProfileError
    try:
        # Both pins are checked by the profile before any generated resource is
        # accepted; recognizing a name or UUID alone is never sufficient.
        result=plan_ui_color(source,ir_path,'Shared',ir['sourceManifestSha256'],sha(read(ir_path)))
        return result, []
    except (MaterialProfileError,OSError) as error:
        return None,[diagnostic('MATERIAL_PROFILE_HANDOFF','materials',str(error))]


def supported_component(component, profile, resolve):
    if not profile or component.get('type')!='cc.Sprite':return False
    spec=profile['spec']
    return (component['sourceId'] in spec['sourceComponentIds'] and
            [resolve(m) for m in component.get('materials',[])]==[spec['materialSourceId']])


def identity_text_component(component,profile,resolve):
    """A proven identity UI-color transform needs no text shader replacement.

    This is only the frozen default static material. Nonidentity parameters and
    later source behavior remain outside this projection.
    """
    if not profile or component.get('type') not in ('cc.Label','cc.RichText'):return False
    spec=profile['spec']
    if [resolve(m)for m in component.get('materials',[])]!=[spec['materialSourceId']]:return False
    return spec.get('properties')==dict(brightness=1.0,constrast=1.0,gray=0.0,saturation=1.0,silhouette=[1.0,1.0,1.0,1.0])

def prepare(profile,target,output):
    if not profile:return None
    prefix='Assets/' if target=='unity' else 'assets/'
    payloads=[]
    for row in profile['ownedFiles']:
        if not row['path'].startswith(prefix):continue
        if row.get('sourcePath'):
            path=row['sourcePath']
            allowed='src/monkey/targets/materials/ui_color/'
            if not path.startswith(allowed) or '/' in path[len(allowed):]:fail('MATERIAL_HELPER_PATH',path,'Unsupported payload')
            raw=files('monkey.targets').joinpath('materials/ui_color/'+path[len(allowed):]).read_bytes()
        else:raw=base64.b64decode(row['contentBase64'],validate=True)
        if sha(raw)!=row['sha256'] or len(raw)!=row['byteLength']:fail('MATERIAL_PAYLOAD_CHANGED',row['path'],'Profile payload differs')
        source='material-payloads/'+sha(row['path'].encode())+Path(row['path']).suffix
        dest=inside(output,source);dest.parent.mkdir(exist_ok=True);dest.write_bytes(raw)
        payloads.append(dict(source=source,target=row['path'],sha256=sha(raw)))
    return dict(spec=profile['spec'],payloads=payloads)


def emit(binding,plan_root,output):
    if not binding:return
    for target,row in binding['spec'].get('nativeBindingHelpers',{}).items():
        basename={'unity':'UnityMaterialBindings.cs','creator38':'CreatorMaterialBindings.js'}.get(target)
        if not basename:fail('MATERIAL_HELPER_PATH',target,'Unsupported helper')
        raw=files('monkey.targets').joinpath('materials/ui_color/'+basename).read_bytes()
        if sha(raw)!=row['sha256']:fail('MATERIAL_HELPER_CHANGED',basename,'Regenerate the plan for current native helper code')
    for row in binding['payloads']:
        raw=read(inside(plan_root,row['source']))
        if sha(raw)!=row['sha256']:fail('MATERIAL_PAYLOAD_CHANGED',row['source'],'Plan-owned payload differs')
        dest=inside(output,row['target'])
        if dest.exists():fail('MATERIAL_ASSET_COLLISION',row['target'],'Refuse to overwrite')
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)


def verify(spec,row,target):
    if not spec:return []
    def gap():return [diagnostic('MATERIAL_NATIVE_READBACK_MISMATCH',spec['materialSourceId'],'Native shader/material identity or source parameter readback differs')]
    if not isinstance(row,dict) or row.get('sourceId')!=spec['materialSourceId'] or row.get('propertiesVerified') is not True:return gap()
    if target=='unity':
        if (row.get('materialGuid')!=spec['materialGuid'] or row.get('shaderGuid')!=spec['shaderGuid'] or
            row.get('persistent') is not True or type(row.get('localFileId'))is not int or row['localFileId']==0):return gap()
        observed={k:row.get(k)for k in ('brightness','saturation','constrast','gray')}
        color=row.get('silhouette')
        observed['silhouette']=[color.get(k)for k in 'rgba'] if isinstance(color,dict) else None
    else:
        if (row.get('materialUuid')!=spec['creator']['materialUuid'] or row.get('effectUuid')!=spec['creator']['effectUuid'] or
            row.get('metaUuid')!=spec['creator']['materialUuid'] or row.get('metaUuidVerified')is not True or row.get('technique')!=0):return gap()
        observed=row.get('properties')or {}
    def same(a,b):return type(a)in(int,float) and math.isfinite(a) and abs(a-b)<=1e-4
    for key,value in spec['properties'].items():
        actual=observed.get(key)
        if isinstance(value,list):
            if not isinstance(actual,list) or len(actual)!=len(value) or not all(same(a,b)for a,b in zip(actual,value)):return gap()
        elif not same(actual,value):return gap()
    return []
