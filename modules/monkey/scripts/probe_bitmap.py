"""Offline glyph geometry evidence only. This is not a Unity page preview."""
import argparse
from pathlib import Path
from PIL import Image,ImageDraw
from monkey.io import safe,inside,load,read,sha,new_output,write_json
from monkey.assets.bitmap import single_line

p=argparse.ArgumentParser();p.add_argument('--ir',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();source=safe(a.ir);ir=load(read(source));out=new_output(a.out,[source.parent])
by_id={f['sourceId']:f for f in ir['bitmapFonts']}
aliases=ir.get('aliases',{})
records=[]
for label in ir['components']:
    if label['type']!='cc.Label':continue
    key=label['font'];seen=set()
    while key in aliases:
        if key in seen:raise ValueError('alias cycle')
        seen.add(key);key=aliases[key]
    if key not in by_id:continue
    font=by_id[key];probe=single_line(font,label['text'],label['fontSize'],label.get('spacing',0))
    path=inside(source.parent,font['atlasImage'])
    expected=next(i['sha256'] for i in load(read(source.parent/'manifest.json'))['files'] if i['path']==font['atlasImage'])
    if sha(read(path))!=expected:raise ValueError('atlas changed')
    with Image.open(path) as image:
        sheet=Image.new('RGBA',(640,220),(35,35,40,255));draw=ImageDraw.Draw(sheet)
        draw.text((12,10),'OFFLINE GLYPH METRIC PROBE - NOT UNITY',fill='white')
        draw.text((12,28),'Colored source atlas; red = ink right, blue = advance',fill='white')
        scale=3;origin=(30,65)
        for box in probe['boxes']:
            x,y,w,h=box['sourceRect']
            if not w or not h:continue
            crop=image.crop((x,y,x+w,y+h)).convert('RGBA')
            crop=crop.resize((max(1,round(box['width']*scale)),max(1,round(box['height']*scale))),Image.Resampling.BILINEAR)
            sheet.alpha_composite(crop,(round(origin[0]+box['x']*scale),round(origin[1]+box['top']*scale)))
        for width,color in ((probe['advance'],'cyan'),(probe['inkRight'],'red')):
            x=origin[0]+round(width*scale);draw.line((x,55,x,195),fill=color,width=1)
        target=sha(label['sourceId'].encode())[:12]+'.png';sheet.save(out/target)
    records.append(dict(sourceId=label['sourceId'],image=target,probe=probe,atlasSha256=expected))
write_json(out/'metric-probe.json',dict(level='offline glyph metric probe; not Unity',records=records))
print('Offline glyph evidence:',out,'labels:',len(records))
