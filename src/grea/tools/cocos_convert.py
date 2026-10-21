"""Finite Creator 2.4 serialized Node/Scene/Prefab to 3.8 candidate conversion.

Not a generic engine/runtime converter. Unsupported data prevents target graph publication.
"""
import argparse,copy,hashlib,json,uuid
from grea.host.paths import Path
from grea.safe_paths import canonical_path,relative_name,disjoint,unique_paths
from .cocos_project import meta,identity

SUPPORTED={'cc.SceneAsset','cc.Scene','cc.Prefab','cc.Node','cc.Sprite','cc.Label','cc.UITransform','cc.UIOpacity','cc.Canvas'}
NODE_FIELDS={'__type__','_name','_objFlags','_parent','_children','_active','_components','_prefab','_id','_trs','_contentSize','_anchorPoint','_opacity','_color','_lpos','_lrot','_lscale','_layer','_groupIndex','groupIndex','_skewX','_skewY','_is3DNode','_eulerAngles','_cullingMask','_renderFlag'}
def refs(value):
    if isinstance(value,dict):
        if '__uuid__' in value:yield value['__uuid__']
        for v in value.values():yield from refs(v)
    elif isinstance(value,list):
        for v in value:yield from refs(v)

def convert(source,output,source_version,asset_map=None):
    source=canonical_path(source);output=disjoint(output,source)
    if source_version not in ('2.4.15','3.8.8'):raise ValueError('Only explicit 2.4.15 and 3.8.8 serialized subsets supported')
    if source.suffix not in ('.fire','.scene','.prefab') or source.stat().st_size>8*1024**2:raise ValueError('Expected bounded uncompiled scene/prefab JSON')
    raw=source.read_bytes();graph=json.loads(raw)
    if not isinstance(graph,list) or not 1<=len(graph)<=20000 or not all(isinstance(x,dict) for x in graph):raise ValueError('Expected flat serialized object array')
    mappings={};assets=[]
    if asset_map:
        asset_map=canonical_path(asset_map)
        if asset_map.stat().st_size>1024**2:raise ValueError('Asset map too large')
        m=json.loads(asset_map.read_text());unique_paths([x['target'] for x in m['assets']])
        for row in m['assets']:
            if row['source_uuid'] in mappings or row['target_uuid'] in mappings.values():raise ValueError('Duplicate UUID mapping')
            uuid.UUID(row['target_uuid']);p=asset_map.parent/relative_name(row['source'])
            if any(x.is_symlink() for x in (p,*p.parents)) or not p.is_file() or p.stat().st_size>32*1024**2:raise ValueError('Invalid asset source')
            if p.suffix not in ('.json','.txt','.mp3','.ogg','.wav'):raise ValueError('Texture/atlas/Spine import requires explicit native importer migration; not copied as a generic file')
            if hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Stale asset source')
            target=relative_name(row['target'])
            if not target.startswith('assets/'):raise ValueError('Target asset must be within assets')
            mappings[row['source_uuid']]=row['target_uuid'];assets.append((row,p))
    problems=[]
    for i,obj in enumerate(graph):
        kind=obj.get('__type__')
        if kind=='cc.Sprite' or (kind=='cc.Label' and obj.get('_font')):problems.append(dict(object=i,type=kind,reason='Native texture/SpriteFrame/font importer migration is not implemented'))
        if kind not in SUPPORTED:problems.append(dict(object=i,type=kind,reason='unsupported component/object; no runtime emulation'))
        if source_version=='2.4.15' and kind in ('cc.Sprite','cc.Canvas','cc.UITransform','cc.UIOpacity'):problems.append(dict(object=i,type=kind,reason='2.4 component migration not implemented; do not copy incompatible fields'))
        if kind=='cc.Label' and source_version=='2.4.15':
            allowed={'__type__','_name','_objFlags','node','_enabled','_id','_string','_fontSize','_lineHeight','_horizontalAlign','_verticalAlign','_overflow','_enableWrapText','_useSystemFont','_fontFamily','_font','_color'}
            if set(obj)-allowed or obj.get('_font'):problems.append(dict(object=i,reason='Only explicit system-font Label subset supported'))
        if kind=='cc.Node' and source_version=='2.4.15':
            unknown=set(obj)-NODE_FIELDS
            if unknown or obj.get('_skewX',0) or obj.get('_skewY',0) or obj.get('_is3DNode') or obj.get('_groupIndex',obj.get('groupIndex',0)):problems.append(dict(object=i,reason='unknown Node fields or skew',fields=sorted(unknown)))
        for ref in refs(obj):
            if ref not in mappings:problems.append(dict(object=i,reason='unclosed asset reference',uuid=ref))
    def indices(v):
        if isinstance(v,dict):
            if '__id__' in v and (type(v['__id__']) is not int or not 0<=v['__id__']<len(graph)):raise ValueError('Dangling object index')
            for x in v.values():indices(x)
        elif isinstance(v,list):
            for x in v:indices(x)
    indices(graph)
    if output.exists():raise ValueError('Use a new candidate output')
    output.mkdir()
    result=dict(schema_version=1,source_sha256=hashlib.sha256(raw).hexdigest(),source_version=source_version,target_version='3.8.8',status='blocked_unsupported' if problems else 'serialized_candidate_not_imported',unsupported=problems,uuid_map=mappings,objects=len(graph),limitations=['No Creator import/browser acceptance. Unknown scripts, masks, animation, textures/atlas, trim/rotation/nine-slice and compiled formats are unsupported.','Same-generation support is limited to the listed basic types and closed explicit asset references.'])
    if not problems:
        out=copy.deepcopy(graph)
        def remap(v):
            if isinstance(v,dict):
                if '__uuid__' in v:v['__uuid__']=mappings[v['__uuid__']]
                for x in v.values():remap(x)
            elif isinstance(v,list):
                for x in v:remap(x)
        remap(out)
        for i,obj in enumerate(out[:]):
            kind=obj['__type__']
            if kind=='cc.Node' and source_version=='2.4.15':
                size=obj.pop('_contentSize',dict(width=0,height=0));anchor=obj.pop('_anchorPoint',dict(x=.5,y=.5));opacity=obj.pop('_opacity',255)
                trs=obj.pop('_trs',{}).get('array',[0,0,0,0,0,0,1,1,1,1])
                if len(trs)!=10:raise ValueError('Unsupported transform array')
                obj['_lpos']=dict(__type__='cc.Vec3',**dict(zip(('x','y','z'),trs[:3])));obj['_lrot']=dict(__type__='cc.Quat',**dict(zip(('x','y','z','w'),trs[3:7])));obj['_lscale']=dict(__type__='cc.Vec3',**dict(zip(('x','y','z'),trs[7:])))
                obj['_layer']=33554432
                for component_ref in obj.get('_components',[]):
                    component=out[component_ref['__id__']]
                    if component.get('__type__')=='cc.Label' and '_color' in obj:component['_color']=copy.deepcopy(obj['_color'])
                for field in ('_color','_groupIndex','groupIndex','_skewX','_skewY','_is3DNode','_eulerAngles','_cullingMask','_renderFlag'):obj.pop(field,None)
                for component in [dict(__type__='cc.UITransform',_enabled=True,node={'__id__':i},_contentSize=dict(__type__='cc.Size',width=size['width'],height=size['height']),_anchorPoint=dict(__type__='cc.Vec2',x=anchor['x'],y=anchor['y'])),*([dict(__type__='cc.UIOpacity',_enabled=True,node={'__id__':i},_opacity=opacity)] if opacity!=255 else [])]:
                    obj.setdefault('_components',[]).append({'__id__':len(out)});out.append(component)
        name='Converted.prefab' if source.suffix=='.prefab' else 'Converted.scene'
        p=output/name;p.write_text(json.dumps(out,indent=2)+'\n');(output/(name+'.meta')).write_text(json.dumps(meta(None,'prefab' if source.suffix=='.prefab' else 'scene',identity(result['source_sha256'])),indent=2))
        for row,p in assets:
            dest=output/row['target'];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes());(output/(row['target']+'.meta')).write_text(json.dumps(meta(None,'json' if p.suffix=='.json' else 'audio-clip' if p.suffix in ('.mp3','.wav','.ogg') else 'text',row['target_uuid']),indent=2))
        result['output']=name
    (output/'conversion.json').write_text(json.dumps(result,indent=2)+'\n');return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--source-version',required=True);p.add_argument('--asset-map',type=Path);a=p.parse_args()
    try:r=convert(a.input,a.output,a.source_version,a.asset_map);print(json.dumps(dict(status=r['status'],unsupported=len(r['unsupported']))));return 1 if r['unsupported'] else 0
    except (OSError,ValueError,KeyError,TypeError) as e:print(str(e));return 2
if __name__=='__main__':raise SystemExit(main())
