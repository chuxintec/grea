"""Independent checks for disabled progress fields and actual native Sprite references."""
import math
from .io import diagnostic


def verify(components, rows, target, owner):
    specs={c['sourceId']:c['staticProgressBinding'] for c in components
           if c.get('staticProgressBinding') and not c.get('convertible')}
    if not specs and not rows:return []
    def gap(message):return diagnostic('STATIC_PROGRESS_NATIVE_MISMATCH',owner,message,owner)
    if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows):return [gap('Static progress readback missing')]
    actual={r.get('sourceComponentId'):r for r in rows}
    if len(actual)!=len(rows) or set(actual)!=set(specs):return [gap('Static progress source identities differ')]
    errors=[]
    for sid,spec in specs.items():
        row=actual[sid]
        for key in ('sourceNodeId','barSpriteSourceId','mode','reverse') + (('sourceEnabled',) if target=='unity' else ()):
            if type(row.get(key)) is not type(spec.get(key)) or row.get(key)!=spec.get(key):errors.append(gap(sid+': '+key+' differs'))
        for key in ('progress','totalLength'):
            v=row.get(key);e=spec[key]
            if type(v) not in (float,int) or not math.isfinite(v) or abs(v-e)>max(1e-6,abs(e)*1e-7):errors.append(gap(sid+': '+key+' differs'))
        if row.get('verified') is not True:errors.append(gap(sid+': native comparison failed'))
        if target=='unity':
            if row.get('carrierDisabled') is not True or row.get('barSpritePersistent') is not True:errors.append(gap(sid+': enabled/persistent policy differs'))
            for key in ('carrier','barSprite'):
                if not row.get(key+'Guid') or type(row.get(key+'LocalFileId')) is not int or not row[key+'LocalFileId']:errors.append(gap(sid+': missing persistent '+key))
        elif row.get('carrierEnabled') is not False or not row.get('barSpriteUuid'):errors.append(gap(sid+': native Sprite identity/disabled policy differs'))
    return errors
