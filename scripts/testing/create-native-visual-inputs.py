#!/usr/bin/env python3
"""Create ONLY self-owned nine-slice test pixels and an explicit converter recipe."""
import argparse
import json
from pathlib import Path
from PIL import Image


def create(output):
    output=Path(output).absolute()
    if any(p.is_symlink() for p in (output,*output.parents)):raise ValueError('Linked output rejected')
    output.mkdir(parents=True,exist_ok=False)
    image=Image.new('RGBA',(9,9),(102,102,102,255))
    for y in range(9):
        for x in range(9):
            if 2<=x<7 and 2<=y<7:color=(255,255,255,255)
            elif x<2 and y<2:color=(255,0,0,255)
            elif x>=7 and y<2:color=(0,255,0,255)
            elif x<2 and y>=7:color=(0,0,255,255)
            elif x>=7 and y>=7:color=(255,255,0,255)
            else:color=(102,102,102,255)
            image.putpixel((x,y),color)
    image.save(output/'nine.png')
    recipe=dict(schema_version=1,sprites=[dict(name='Nine',image='nine.png',rect=[0,0,9,9],rotated_cw=False,original_size=[9,9],offset=[0,0],pivot=[0.5,0.5],border=[2,2,2,2],pixels_per_unit=10)],targets=[],clips=[])
    (output/'nine.recipe.json').write_text(json.dumps(recipe,indent=2)+'\n', encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();create(a.output)
