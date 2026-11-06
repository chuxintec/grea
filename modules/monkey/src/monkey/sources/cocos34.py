"""Creator 3.4.1 resource serialization; separate from later mesh/pivot formats.

Version baseline: cocos-engine v3.4.1 cocos/2d/assets/sprite-frame.ts and
cocos/core/assets/{texture-2d,image-asset}.ts. Graphs need their own version audit.
"""
import copy
import re
from .compiled import asset_key,fail

PROFILE='cocos-3.4.1-bundle'


def image_formats(value,location):
    fmt=value.get('fmt')if isinstance(value,dict)else value
    names=['.png','.jpg','.jpeg','.bmp','.webp','.pvr','.pkm','.astc']
    if not isinstance(fmt,str)or not re.fullmatch(r'[0-7](?:@[0-9]+)?(?:_[0-7](?:@[0-9]+)?)*',fmt):
        fail('COCOS34_IMAGE_FORMAT',location,'Expected declared 3.4.1 image extension indices')
    result=[names[int(token.split('@')[0])]for token in fmt.split('_')]
    if len(set(result))!=len(result):fail('COCOS34_IMAGE_FORMAT',location,'Duplicate image formats')
    return result


def texture(value,location):
    if not isinstance(value,dict) or set(value)-{'base','mipmaps'} or not isinstance(value.get('base'),str) or not re.fullmatch(r'\d+,\d+,\d+,\d+,\d+,\d+',value['base']):
        fail('COCOS34_TEXTURE_LAYOUT',location,'Expected 3.4.1 named base/mipmaps texture data')
    levels=value.get('mipmaps')
    if not isinstance(levels,list) or len(levels)!=1 or not isinstance(levels[0],str):
        fail('COCOS34_MIPMAP_PROFILE',location,'Only one explicitly identified source image is supported')
    return value['base'],asset_key(levels[0])


def texture_sections(raw,ordinal=None):
    if not isinstance(raw,dict) or set(raw)!={'type','data'} or raw['type']!='cc.Texture2D' or not isinstance(raw['data'],list) or not 1<=len(raw['data'])<=50000:
        fail('COCOS34_TEXTURE_PACK','$','Expected bounded named Texture2D array pack')
    if ordinal is not None and (type(ordinal)is not int or not 0<=ordinal<len(raw['data'])):
        fail('COCOS34_TEXTURE_INDEX',str(ordinal),'Section ordinal out of range')
    rows=enumerate(raw['data'])if ordinal is None else[(ordinal,raw['data'][ordinal])]
    result=[]
    for index,value in rows:
        texture(value,str(index))
        result.append(dict(root=0,instances=[dict(__type__='cc.Texture2D',data=copy.deepcopy(value))]))
    return result


def frame(asset,by_id,resolve):
    value=asset['document']['instances'][asset['document']['root']]
    payload=copy.deepcopy(value.get('data',{}));tx=value.get('_textureSource',{}).get('__uuid__')
    if not tx:fail('COCOS34_TEXTURE_EDGE',asset['sourceId'],'Missing explicit SpriteFrame texture source')
    texture_id=resolve(asset['bundle']+':'+tx);source_texture=by_id.get(texture_id,{})
    doc=source_texture.get('document')
    if source_texture.get('kind')!='cc.Texture2D' or not doc:
        fail('COCOS34_TEXTURE_EDGE',texture_id,'Exact supplied Texture2D metadata unavailable')
    sampler,image=texture(doc['instances'][doc['root']].get('data'),texture_id)
    image_id=resolve(source_texture['bundle']+':'+image);source=by_id.get(image_id,{})
    if source.get('kind')!='cc.ImageAsset':fail('COCOS34_IMAGE_EDGE',image_id,'Exact source ImageAsset identity unavailable')
    if payload.get('vertices'):
        fail('COCOS34_CUSTOM_MESH',asset['sourceId'],'Source polygon mesh needs a dedicated adapter')
    for field,keys in [('rect',('x','y','width','height')),('offset',('x','y')),('originalSize',('width','height'))]:
        item=payload.get(field)
        if not isinstance(item,dict)or any(k not in item for k in keys):fail('COCOS34_FRAME_LAYOUT',asset['sourceId'],'Expected named '+field+' fields')
        payload[field]=[item[k]for k in keys]
    if type(payload.get('rotated'))is not bool:fail('COCOS34_FRAME_LAYOUT',asset['sourceId'],'Expected explicit boolean rotation')
    payload['rotated']=int(payload['rotated']);payload['texture']={'__uuid__':source['key']}
    return payload,source,dict(sourceTexture=texture_id,sourceImage=image_id,sampler=sampler,samplerConversion='pending',resourceProfile=PROFILE,nativeVariantSelection=source.get('nativeVariantSelection'))
