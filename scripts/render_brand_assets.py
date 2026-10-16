#!/usr/bin/env python3
"""Deterministically rasterize ONLY grea's restricted rect/polygon SVG brand sources."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from grea.brand_assets import validate_asset,SIZES

ROOT=Path(__file__).resolve().parents[1]


def render(raw,size):
    image=Image.new('RGBA',(size*4,size*4));draw=ImageDraw.Draw(image);scale=size*4/512
    for node in ET.fromstring(raw):
        tag=node.tag.rsplit('}',1)[-1];color=node.attrib['fill']
        if tag=='polygon':
            values=[float(v)*scale for v in node.attrib['points'].replace(',',' ').split()];draw.polygon(list(zip(values[::2],values[1::2])),fill=color)
        elif tag=='rect':
            x,y,w,h=[float(node.get(k,'0'))*scale for k in ('x','y','width','height')];draw.rounded_rectangle((x,y,x+w,y+h),radius=float(node.get('rx','0'))*scale,fill=color)
        else:raise ValueError('Unsupported own SVG primitive')
    return image.resize((size,size),Image.Resampling.LANCZOS)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');parser.add_argument('--preview',type=Path);args=parser.parse_args();assets=ROOT/'plugin/assets';expected={};identity={}
    for name in ('icon','logo_light','logo_dark'):
        raw=(assets/(name+'.svg')).read_bytes();validate_asset('plugin/assets/'+name+'.svg',raw);identity[name+'.svg']=hashlib.sha256(raw).hexdigest()
        for size in SIZES:
            image=render(raw,size);assert image.getextrema()[3]==(0,255);stream=io.BytesIO();image.save(stream,format='PNG');data=stream.getvalue();path=name+'_'+str(size)+'.png';validate_asset('plugin/assets/'+path,data);expected[path]=data;identity[path]=hashlib.sha256(data).hexdigest()
    expected['brand.json']=(json.dumps(dict(schema_version=1,author='grea contributors',license='MIT',design='Original geometric G with reassembled tiles; no game/vendor trademark assets',renderer='restricted SVG rect/polygon, Pillow 12.2.0, 4x antialias; deterministic',files=identity),indent=2,sort_keys=True)+'\n').encode()
    for name,data in expected.items():
        target=assets/name
        if args.check:
            if not target.is_file() or target.read_bytes()!=data:raise ValueError('Brand export drift: '+name)
        else:target.write_bytes(data)
    if args.preview:
        canvas=Image.new('RGB',(820,380),'white');draw=ImageDraw.Draw(canvas)
        for row,(background,variant) in enumerate([('#F1F5F9','logo_light'),('#0B1220','logo_dark')]):
            draw.rectangle((0,row*190,820,(row+1)*190),fill=background)
            for col,size in enumerate(SIZES):
                image=render((assets/(variant+'.svg')).read_bytes(),size);shown=image if size<=128 else image.resize((144,144),Image.Resampling.LANCZOS);canvas.paste(shown,(col*164+12,row*190+12),shown);draw.text((col*164+12,row*190+164),str(size),fill='#64748B')
        args.preview.parent.mkdir(parents=True,exist_ok=True)
        with args.preview.open('xb') as f:canvas.save(f,format='PNG')
    print(json.dumps(dict(status='verified' if args.check else 'rendered',exports=len(expected))))


if __name__=='__main__':main()
