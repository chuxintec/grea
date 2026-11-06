"""Explicit editable Creator 2.4.15 project JSON/meta subset (separate from bundles)."""
from pathlib import Path
from .. import __version__
from ..io import safe, read, load, sha, new_output, finish, write_json, diagnostic
from .compiled import asset_key, budget, fail, at

PROFILE='cocos-2.4.15-project'


class Project:
    def __init__(self, root):
        self.root=safe(root);self.inputs={};self.name=""
        self.project=self.json(self.root/'project.json')
        if self.project.get('version')!='2.4.15':
            fail('UNSUPPORTED_VERSION','project.json/version','Editable project must declare version 2.4.15')
        self.name=self.project.get('id') or self.project.get('name')
        if not isinstance(self.name,str) or not self.name or ':' in self.name:
            fail('INVALID_PROJECT_ID','project.json','Expected stable project id or name without colon')
        for item in self.inputs.values():item['bundle']=self.name
        self.records={}
        metas=sorted((self.root/'assets').rglob('*.meta'))
        if len(metas)>50000:
            fail('ASSET_BUDGET','assets','Too many metadata files')
        for meta in metas:
            data=self.json(meta)
            if not isinstance(data,dict) or 'uuid' not in data:
                fail('INVALID_META',str(meta),'Metadata must declare UUID')
            key=asset_key(data['uuid'])
            self.add(key,dict(meta=meta,data=data,path=Path(str(meta)[:-5]),frame=None))
            if not isinstance(data.get('subMetas',{}),dict):fail('INVALID_META',str(meta),'Expected subMetas object')
            for name,sub in data.get('subMetas',{}).items():
                if not isinstance(sub,dict):fail('INVALID_META',str(meta),'Expected subMeta object')
                if sub.get('importer')=='sprite-frame':
                    self.add(asset_key(sub['uuid']),dict(meta=meta,data=data,path=Path(str(meta)[:-5]),frame=sub,
                                                        location='subMetas/'+name))
        self.keys=sorted(self.records)

    def add(self,key,record):
        if key in self.records:fail('DUPLICATE_UUID',str(record['meta']),key)
        self.records[key]=record

    def record(self,path):
        path=safe(path)
        if not path.is_relative_to(self.root):fail('UNSAFE_PATH',str(path),'Asset outside project')
        raw=read(path);relative=path.relative_to(self.root).as_posix()
        info=dict(path=relative,bytes=len(raw),sha256=sha(raw),bundle=self.name)
        if relative in self.inputs and self.inputs[relative]!=info:fail('SOURCE_CHANGED',relative,'Source changed during read')
        self.inputs[relative]=info
        if sum(v['bytes'] for v in self.inputs.values())>128*1024*1024:fail('BYTE_BUDGET','$','Source budget exceeded')
        return raw

    def json(self,path):return load(self.record(path))

    def asset(self,key):
        r=self.records[key];path=r['path'];sub=r['frame'];refs=set()
        native=None;doc=None;kind=None
        if sub is not None:
            required=['trimX','trimY','width','height','rawWidth','rawHeight','offsetX','offsetY']
            if any(k not in sub for k in required):fail('UNSUPPORTED_SPRITE_META',str(r['meta']),'Sprite meta geometry incomplete')
            texture=asset_key(sub.get('rawTextureUuid',r['data']['uuid']))
            frame=dict(rect=[sub['trimX'],sub['trimY'],sub['width'],sub['height']],
                       originalSize=[sub['rawWidth'],sub['rawHeight']],offset=[sub['offsetX'],sub['offsetY']],
                       rotated=1 if sub.get('rotated',False) else 0,
                       capInsets=[sub.get('borderLeft',0),sub.get('borderTop',0),sub.get('borderRight',0),sub.get('borderBottom',0)])
            doc=dict(root=0,instances=[{'__type__':'cc.SpriteFrame','data':frame,'_textureSetter':{'__uuid__':texture}}]);kind='cc.SpriteFrame';refs.add(texture)
        elif path.suffix in ('.prefab','.fire'):
            objects=self.json(path)
            if not isinstance(objects,list) or not objects or not isinstance(objects[0],dict):fail('UNSUPPORTED_SERIALIZATION',str(path),'Expected editable JSON object array')
            kind=objects[0].get('__type__')
            if kind not in ('cc.Prefab','cc.SceneAsset'):fail('UNSUPPORTED_SERIALIZATION',str(path),'Expected Prefab/SceneAsset root')
            doc=dict(root=0,instances=objects)
            pending=[objects]
            while pending:
                value=pending.pop()
                if isinstance(value,dict):
                    if '__uuid__' in value:
                        value['__uuid__']=asset_key(value['__uuid__']);refs.add(value['__uuid__'])
                    pending.extend(value.values())
                elif isinstance(value,list):pending.extend(value)
        else:
            kinds={'.png':'cc.Texture2D','.jpg':'cc.Texture2D','.jpeg':'cc.Texture2D',
                   '.ttf':'cc.TTFFont','.mp3':'cc.AudioClip','.ogg':'cc.AudioClip','.wav':'cc.AudioClip'}
            kind=kinds.get(path.suffix.lower())
            if kind:
                self.record(path);native=path.relative_to(self.root).as_posix()
                doc=dict(root=0,instances=[{'__type__':kind}])
        return dict(sourceId=self.name+':'+key,key=key,index=self.keys.index(key),kind=kind,bundle=self.name,
                    logicalPath=path.relative_to(self.root).as_posix(),references=sorted(refs),native=native,document=doc,
                    importPath=r['meta'].relative_to(self.root).as_posix()+'#'+r.get('location',''))


def catalog(root,output):
    project=Project(root);out=new_output(output,[project.root])
    result=dict(schemaVersion=1,sourceProfile=PROFILE,toolVersion=__version__,diagnostics=[],
                selection=[dict(index=i,key=k,path=project.records[k]['path'].relative_to(project.root).as_posix(),
                                spriteFrame=project.records[k]['frame'] is not None) for i,k in enumerate(project.keys)])
    write_json(out/'catalog.json',result);return finish(out,result)


def inspect(root,selection,output,*,max_assets=2048,whole_input=False):
    p=Project(root);pending=[at(p.keys,i,'$.selection') for i in selection];seen=set();assets=[];diagnostics=[]
    while pending:
        key=pending.pop(0)
        if key in seen:continue
        seen.add(key)
        if len(seen)>max_assets:fail('ASSET_BUDGET','$','Dependency closure exceeds declared asset budget')
        if key not in p.records:
            diagnostics.append(diagnostic('MISSING_REFERENCE',key,'UUID absent from project metadata',p.name+':'+key));continue
        try:
            asset=p.asset(key);assets.append(asset);pending.extend(asset['references'])
            if asset['kind'] is None:diagnostics.append(diagnostic('UNSUPPORTED_ASSET',asset['importPath'],'Unsupported editable asset type',asset['sourceId']))
        except (ValueError,OSError,KeyError) as error:
            diagnostics.append(diagnostic(getattr(error,'code','INVALID_ASSET'),str(p.records[key]['meta']),str(error),p.name+':'+key))
    for item in p.inputs.values():
        if sha(read(p.root/item['path']))!=item['sha256']:fail('SOURCE_CHANGED',item['path'],'Source changed during inspection')
    out=new_output(output,[p.root])
    report=dict(schemaVersion=1,toolVersion=__version__,sourceProfile=PROFILE,sourceVersion='2.4.15',
                versionEvidence='project.json/version exact match',sourceRoot=str(p.root),sourceRoots={p.name:str(p.root)},
                bundle=p.name,selection=selection,inputs=sorted(p.inputs.values(),key=lambda x:x['path']),assets=sorted(assets,key=lambda x:x['sourceId']),diagnostics=diagnostics)
    if whole_input:report['packageSelection']=dict(allProvidedAssets=True,maxAssets=max_assets)
    write_json(out/'source-manifest.json',report);return finish(out,report)
