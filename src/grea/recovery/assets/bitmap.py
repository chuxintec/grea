"""Typed bitmap glyph metrics; only offline conversion, no source runtime."""
import math
from ..sources.compiled import fail


def finite(value, location):
    if type(value) not in (float,int) or not math.isfinite(value):
        fail('INVALID_BITMAP_METRIC',location,'Expected finite number')
    return value


def normalize_font(value, source_id, atlas_ref, size):
    config=value.get('_fntConfig')
    if not isinstance(config,dict):fail('INVALID_BITMAP_FONT',source_id,'Missing fntConfig')
    point=finite(config.get('fontSize',value.get('fontSize')),source_id)
    height=finite(config.get('commonHeight'),source_id)
    if min(point,height)<=0:fail('INVALID_BITMAP_FONT',source_id,'Font dimensions must be positive')
    glyphs=[];ids=set()
    for key,definition in config.get('fontDefDictionary',{}).items():
        code=int(key)
        if not 0<=code<=0x10ffff or 0xd800<=code<=0xdfff or code in ids:
            fail('INVALID_BITMAP_CODEPOINT',source_id,str(key))
        ids.add(code);rect=definition['rect']
        x,y,w,h=[finite(rect[k],source_id) for k in ('x','y','width','height')]
        if any(v!=int(v) for v in (x,y,w,h)) or min(x,y,w,h)<0 or x+w>size[0] or y+h>size[1]:
            fail('BITMAP_GLYPH_BOUNDS',source_id,str(key))
        xo,yo,advance=[finite(definition[k],source_id) for k in ('xOffset','yOffset','xAdvance')]
        glyphs.append(dict(unicode=code,index=code,rect=list(map(int,[x,size[1]-y-h,w,h])),sourceRect=[x,y,w,h],
                           metrics=[w,h,xo,point-yo,advance]))
    kernings=[]
    for key,amount in config.get('kerningDict',{}).items():
        packed=int(key)&0xffffffff;left,right=packed>>16,packed&0xffff
        if left not in ids or right not in ids:
            fail('BITMAP_KERNING_GLYPH_MISSING',source_id,str(key))
        kernings.append(dict(first=left,second=right,advance=finite(amount,source_id)))
    return dict(sourceId=source_id,atlasRef=atlas_ref,pointSize=point,lineHeight=height,ascent=point,
                descent=0,baselineConvention="logical point-size box; glyph yOffset is authoritative",kerningConvention="source-2.4-unscaled-pair-offset",atlasSize=size,glyphs=sorted(glyphs,key=lambda g:g['unicode']),
                kernings=sorted(kernings,key=lambda k:(k['first'],k['second'])),colored=True)


def single_line(font,text,font_size,spacing=0):
    """Return evidence-checkable glyph boxes, preserving negative bearings/kerning."""
    if '\n' in text:fail('UNSUPPORTED_BITMAP_LAYOUT','$','Single-line probe only')
    glyphs={g['unicode']:g for g in font['glyphs']}
    pairs={(p['first'],p['second']):p['advance'] for p in font['kernings']}
    scale=font_size/font['pointSize'];cursor=0;boxes=[];previous=None
    for char in text:
        code=ord(char)
        if code not in glyphs:fail('BITMAP_GLYPH_MISSING','$',str(code))
        glyph=glyphs[code];w,h,xo,bearing,advance=glyph['metrics']
        cursor+=pairs.get((previous,code),0)
        boxes.append(dict(unicode=code,x=cursor+xo*scale,top=(font['ascent']-bearing)*scale,
                          width=w*scale,height=h*scale,sourceRect=glyph['sourceRect']))
        cursor+=advance*scale+spacing;previous=code
    return dict(boxes=boxes,advance=cursor-spacing if text else 0,inkRight=max((b['x']+b['width'] for b in boxes),default=0))
