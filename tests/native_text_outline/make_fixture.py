"""Synthetic raw Cocos 2.4.15 source; shared font, glyphs, color and weight."""
from pathlib import Path
import uuid,json,argparse
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
w=parser.parse_args().out.resolve();w.mkdir(parents=True,exist_ok=False);root=w/'source';root.mkdir()
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
def compiled(objs):
 classes=[];masks=[];values=[]
 for i,o in enumerate(objs):
  keys=[k for k in o if k!='__type__'];classes.append([o['__type__'],keys,len(keys)+1])
  masks.append([i,*range(len(keys)),len(keys)+1]);values.append([i,*[o[k] for k in keys]])
 return [1,[],[],classes,masks,values,[],[],[],[],[]]
cases=[('plain',None,True,255),('disabled',3,False,255),('zero',0,True,255),('w25',2.5,True,255),('w30',3,True,255),('w36',3.6,True,255),('half',3,True,128),('clear',3,True,0)]
texts={name:'AB集齐奖励' for name,_,_,_ in cases}
for group,txt in [('latin','AB'),('cjk','集齐奖励')]:
 for n,wd,en,a in list(cases[:8]):
  if n in ('plain','w25','w30','w36'):
   name=group+'-'+n;texts[name]=txt;cases.append((name,wd,en,a))
ids=[];paths={};versions=[]
for i,(mode,width,enabled,alpha) in enumerate(cases):
 key=str(uuid.uuid5(uuid.NAMESPACE_URL,'monkey:generic-outline:'+mode));ids.append(key);paths[str(i)]=['UI/'+mode,0];versions.extend([i,'a'])
 node=dict(__type__='cc.Node',_name=mode,_parent=None,_children=[],_active=True,_components=[{'__id__':2}],_contentSize=dict(width=240,height=96),_anchorPoint=dict(x=.5,y=.5),_color=dict(r=193,g=121,b=47,a=255),_trs=[0,0,0,0,0,0,1,1,1,1])
 label=dict(__type__='cc.Label',node={'__id__':1},_string=texts[mode],_fontFamily='Arial',_fontSize=24,_lineHeight=32,_styleFlags=1,_isSystemFontUsed=True,_enableWrapText=False,_overflow=1,_horizontalAlign=1,_verticalAlign=1)
 data=[dict(__type__='cc.Prefab',data={'__id__':1}),node,label]
 if width is not None:
  node['_components'].append({'__id__':3});data.append(dict(__type__='cc.LabelOutline',node={'__id__':1},_width=width,_enabled=enabled,_color=dict(r=255,g=255,b=255,a=alpha)))
 write(root/'import'/key[:2]/(key+'.a.json'),compiled(data))
write(root/'config.json',dict(name='outline-fixture',engineVersion='2.4.15',uuids=ids,paths=paths,types=['cc.Prefab'],packs={},versions={'import':versions,'native':[]}))
write(w/'cases.json',[dict(name=c[0],text=texts[c[0]],sourceId='outline-fixture:'+i,width=c[1],enabled=c[2],alpha=c[3]) for c,i in zip(cases,ids)])
