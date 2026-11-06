"""Explicit Creator 3.8.7 resource serialization; graphs use cocos38_graphs."""
import copy
from .compiled import asset_key, fail

PROFILE='cocos-3.8.7-bundle'


def texture_sections(raw, ordinal=None):
    if not isinstance(raw,dict)or set(raw)!={'type','data'}or raw['type']!='cc.Texture2D' or not isinstance(raw['data'],list) or not 1<=len(raw['data'])<=50000:
        fail('COCOS3_TEXTURE_PACK','$','Expected bounded 3.8 Texture2D array pack')
    if ordinal is not None and (type(ordinal)is not int or not 0<=ordinal<len(raw['data'])):fail('COCOS3_TEXTURE_INDEX',str(ordinal),'Section ordinal out of range')
    result=[]
    values=enumerate(raw['data'])if ordinal is None else [(ordinal,raw['data'][ordinal])]
    for i,value in values:
        if not isinstance(value,list)or len(value)!=2 or not isinstance(value[0],str)or len(value[0].split(','))!=6 or any(not x.isdigit()for x in value[0].split(',')) or not isinstance(value[1],list)or len(value[1])!=1:
            fail('COCOS3_TEXTURE_LAYOUT',str(i),'Only explicit single-image 2D texture sections supported')
        image=asset_key(value[1][0])
        result.append(dict(root=0,instances=[dict(__type__='cc.Texture2D',data=dict(sourceSampler=value[0],image={'__uuid__':image}),sourceData=copy.deepcopy(value))]))
    return result


def frame(asset, by_id, resolve):
    """Canonical resource projection with an exact frame -> texture -> image edge."""
    value=asset['document']['instances'][asset['document']['root']];payload=copy.deepcopy(value['data'])
    texture=value.get('_textureSource',{}).get('__uuid__')
    if not texture:fail('COCOS3_TEXTURE_EDGE',asset['sourceId'],'Missing explicit SpriteFrame texture source')
    texture_id=resolve(asset['bundle']+':'+texture);source_texture=by_id.get(texture_id,{})
    doc=source_texture.get('document')
    if source_texture.get('kind')!='cc.Texture2D'or not doc:fail('COCOS3_TEXTURE_EDGE',texture_id,'Exact supplied Texture2D metadata unavailable')
    texture_value=doc['instances'][doc['root']]
    image=texture_value.get('data',{}).get('image',{}).get('__uuid__')
    if not image:fail('COCOS3_IMAGE_EDGE',texture_id,'Missing supported single-image texture metadata')
    image_id=resolve(source_texture['bundle']+':'+image);image_asset=by_id.get(image_id,{})
    if image_asset.get('kind')!='cc.ImageAsset':fail('COCOS3_IMAGE_EDGE',image_id,'Exact source ImageAsset identity unavailable')
    for field,keys in [('rect',('x','y','width','height')),('offset',('x','y')),('originalSize',('width','height'))]:
        item=payload.get(field)
        if not isinstance(item,dict)or any(k not in item for k in keys):fail('COCOS3_FRAME_LAYOUT',asset['sourceId'],'Expected named '+field+' fields')
        payload[field]=[item[k]for k in keys]
    if type(payload.get('rotated'))is not bool:fail('COCOS3_FRAME_LAYOUT',asset['sourceId'],'Expected explicit boolean rotation')
    if payload.get('pivot')!={'x':.5,'y':.5}or payload.get('meshType')!=0 or payload.get('pixelsToUnit')!=100:
        fail('COCOS3_FRAME_GEOMETRY',asset['sourceId'],'Custom pivot/mesh/pixel units need a separate adapter')
    payload['rotated']=int(payload['rotated']);payload['texture']={'__uuid__':image_asset['key']}
    return payload,image_asset,dict(sourceTexture=texture_id,sourceImage=image_id,sampler=texture_value['data']['sourceSampler'],samplerConversion='pending')
