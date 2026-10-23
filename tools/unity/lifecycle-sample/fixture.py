"""Create an owned, minimal Creator source fixture; never execute its JavaScript."""
import argparse,json
from pathlib import Path
from PIL import Image

def create(output):
 out=Path(output).resolve()
 if out.exists():raise ValueError("Use a fresh isolated output directory")
 out.mkdir()
 source=out/'source';assets=source/'assets';assets.mkdir(parents=True)
 def write(name,data):p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 write('project.json',dict(version='2.4.15',id='grea-owned-counter'))
 texture='10000000-0000-0000-0000-000000000001';frame='10000000-0000-0000-0000-000000000002';prefab='10000000-0000-0000-0000-000000000003'
 Image.new('RGBA',(8,8),(255,255,255,255)).save(assets/'white.png')
 write('assets/white.png.meta',dict(uuid=texture,subMetas=dict(white=dict(uuid=frame,importer='sprite-frame',rawTextureUuid=texture,trimX=0,trimY=0,width=8,height=8,rawWidth=8,rawHeight=8,offsetX=0,offsetY=0))))
 objects=[{'__type__':'cc.Prefab','data':{'__id__':1}},dict(__type__='cc.Node',_name='CounterPanel',_parent=None,_children=[{'__id__':2}],_components=[{'__id__':3}],_contentSize=dict(width=480,height=720),_anchorPoint=dict(x=.5,y=.5),_trs=[0,0,0,0,0,0,1,1,1,1],_color=dict(r=24,g=34,b=52,a=255)),dict(__type__='cc.Node',_name='AddCounter',_parent={'__id__':1},_children=[],_components=[{'__id__':4},{'__id__':5}],_contentSize=dict(width=320,height=100),_anchorPoint=dict(x=.5,y=.5),_trs=[0,-100,0,0,0,0,1,1,1,1],_color=dict(r=51,g=120,b=210,a=255)),dict(__type__='cc.Sprite',node={'__id__':1},_spriteFrame={'__uuid__':frame},_type=0,_sizeMode=0),dict(__type__='cc.Sprite',node={'__id__':2},_spriteFrame={'__uuid__':frame},_type=0,_sizeMode=0),dict(__type__='cc.Button',node={'__id__':2},_Ntarget=None,interactable=True,clickEvents=[])]
 # Only supported fields; the source Button uses its own node as the hit target.
 objects[5].pop('_Ntarget');objects[5]['_N$target']={'__id__':2};objects[5]['_N$transition']=0
 write('assets/Counter.prefab',objects);write('assets/Counter.prefab.meta',dict(uuid=prefab))
 write('counter.json',dict(schema_version=1,configVersion='lc1',step=1,goal=0))
 (source/'Counter.js').write_text('// Owned behavior evidence. Not executed by GREA.\nexport function addCount(saved, config) { return {...saved, count: saved.count + config.step}; }\n')
 return source

if __name__=="__main__":
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--output",required=True)
 print(create(parser.parse_args().output))
