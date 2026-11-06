"""Synthetic protocol data; no game resources."""
from pathlib import Path
from PIL import Image
from monkey.io import write_json

FRAME = '00000000-0000-0000-0000-000000000001'
TEXTURE = '00000000-0000-0000-0000-000000000002'
PREFAB = '00000000-0000-0000-0000-000000000003'
FONT = '00000000-0000-0000-0000-000000000004'


def custom(typ, data, deps=()):
    return [1,list(deps),[],[typ],[],[data],[0],[],[0]*len(deps),['texture']*len(deps),list(range(len(deps)))]


def normal(objects):
    classes, masks, values = [], [], []
    for i, obj in enumerate(objects):
        keys = [k for k in obj if k != '__type__']
        classes.append([obj['__type__'], keys, len(keys)+1])
        masks.append([i, *range(len(keys)), len(keys)+1])
        values.append([i, *[obj[k] for k in keys]])
    return [1,[],[],classes,masks,values,[],[],[],[],[]]


def fixture(root):
    root.mkdir()
    def imported(key, data):
        path=root/'import'/key[:2]/(key+'.a.json'); path.parent.mkdir(parents=True,exist_ok=True);write_json(path,data)
    frame = custom('cc.SpriteFrame', dict(name='panel',rect=[1,1,3,2], originalSize=[7,6],
                   offset=[1,-1],rotated=1, capInsets=[1,0,1,1]), [TEXTURE])
    imported(FRAME,frame)
    imported(TEXTURE,custom('cc.Texture2D','0,9729,9729,33071,33071,0,0,1'))
    node=dict(__type__='cc.Node',_name='测试面板',_parent=None,_children=[],_active=True,
              _components=[{'__id__':2},{'__id__':3}],_contentSize={'width':210,'height':180},
              _anchorPoint={'x':.25,'y':.75},_trs=[0,0,0,0,0,0,1,1,1,1])
    imported(PREFAB,normal([{'__type__':'cc.Prefab','data':{'__id__':1}},node,
        dict(__type__='cc.Sprite',node={'__id__':1},_spriteFrame={'__uuid__':FRAME},_type=1,_sizeMode=0),
        dict(__type__='cc.Label',node={'__id__':1},_string='你好\nMonkey',_fontSize=24,**{'_N$file':{'__uuid__':FONT}})]))
    imported(FONT,custom('cc.TTFFont',{'name':'missing-native-font'}))
    path=root/'native'/TEXTURE[:2]/(TEXTURE+'.b.png');path.parent.mkdir(parents=True)
    image=Image.new('RGBA',(6,6))
    # Target unrotated rows: red green blue / yellow magenta cyan.
    plain=Image.new('RGBA',(3,2));plain.putdata([(255,0,0,255),(0,255,0,255),(0,0,255,255),
                                             (255,255,0,255),(255,0,255,255),(0,255,255,255)])
    image.paste(plain.transpose(Image.Transpose.ROTATE_270),(1,1));image.save(path)
    config=dict(name='synthetic',engineVersion='2.4.15',uuids=[FRAME,TEXTURE,PREFAB,FONT],
                paths={'0':['UI/panel',0],'2':['UI/fixture',1]},types=['cc.SpriteFrame','cc.Prefab'],
                packs={},versions={'import':[0,'a',1,'a',2,'a',3,'a'],'native':[1,'b']})
    write_json(root/'config.json',config)
    return root/'config.json'
