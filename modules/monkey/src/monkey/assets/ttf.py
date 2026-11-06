"""Bounded SFNT Unicode cmap coverage, for font preflight only (no rasterizer)."""
import struct
from ..sources.compiled import fail


def coverage(raw):
    def u16(offset):
        if offset<0 or offset+2>len(raw):fail('INVALID_TTF','$','Truncated uint16')
        return struct.unpack_from('>H',raw,offset)[0]
    def u32(offset):
        if offset<0 or offset+4>len(raw):fail('INVALID_TTF','$','Truncated uint32')
        return struct.unpack_from('>I',raw,offset)[0]
    if len(raw)<12 or raw[:4] not in (b'\x00\x01\x00\x00',b'OTTO'):
        fail('INVALID_TTF','$','Expected SFNT 1.0/OTTO header')
    count=u16(4)
    if not 1<=count<=256 or 12+count*16>len(raw):fail('INVALID_TTF','$','Invalid table directory')
    tables={}
    for i in range(count):
        start=12+16*i;tag=bytes(raw[start:start+4]);offset,size=u32(start+8),u32(start+12)
        if tag in tables or offset+size>len(raw):fail('INVALID_TTF','$','Duplicate or out-of-bounds table')
        tables[tag]=(offset,size)
    if b'cmap' not in tables or b'maxp' not in tables:fail('INVALID_TTF','$','cmap/maxp required')
    maxp,msize=tables[b'maxp']
    if msize<6:fail('INVALID_TTF','$','Truncated maxp')
    glyph_count=u16(maxp+4);base,size=tables[b'cmap'];end=base+size
    if size<4 or u16(base+2)>256 or base+4+8*u16(base+2)>end:fail('INVALID_TTF','$','Truncated cmap records')
    mappings={};formats=set();seen_subtables=set()
    for i in range(u16(base+2)):
        record=base+4+i*8;platform,encoding=u16(record),u16(record+2)
        if platform!=0 and not (platform==3 and encoding in (1,10)):continue
        sub=base+u32(record+4)
        if sub<base or sub+2>end:fail('INVALID_TTF','$','Invalid cmap subtable offset')
        if sub in seen_subtables:continue
        seen_subtables.add(sub)
        fmt=u16(sub)
        if fmt==4:
            if sub+8>end:fail('INVALID_TTF','$','Truncated cmap format 4 header')
            length=u16(sub+2);segments=u16(sub+6)//2
            if sub+length>end or segments==0 or 16+segments*8>length:fail('INVALID_TTF','$','Invalid cmap format 4 shape')
            ends=sub+14;starts=ends+2*segments+2;deltas=starts+2*segments;ranges=deltas+2*segments
            previous_hi=-1
            for j in range(segments):
                lo,hi=u16(starts+2*j),u16(ends+2*j)
                if hi<lo or lo<=previous_hi:fail('INVALID_TTF','$','Overlapping/descending cmap segment')
                previous_hi=hi
                delta,offset=u16(deltas+2*j),u16(ranges+2*j)
                for code in range(lo,min(hi,0xfffe)+1):
                    if offset:
                        address=ranges+2*j+offset+2*(code-lo)
                        if address+2>sub+length:fail('INVALID_TTF','$','Glyph index outside cmap')
                        glyph=u16(address);glyph=(glyph+delta)&0xffff if glyph else 0
                    else:glyph=(code+delta)&0xffff
                    if glyph>=glyph_count:fail('INVALID_TTF','$','Glyph index outside maxp')
                    if glyph and not 0xd800<=code<=0xdfff:mappings[code]=glyph
            formats.add(4)
        elif fmt==12:
            if sub+16>end:fail('INVALID_TTF','$','Truncated cmap format 12 header')
            length=u32(sub+4);groups=u32(sub+12)
            if sub+length>end or groups>65536 or 16+12*groups>length:fail('INVALID_TTF','$','Invalid cmap format 12 shape')
            previous_hi=-1
            for j in range(groups):
                address=sub+16+j*12;lo,hi,glyph=u32(address),u32(address+4),u32(address+8)
                if hi<lo or lo<=previous_hi or hi>0x10ffff or glyph+hi-lo>=glyph_count:fail('INVALID_TTF','$','Invalid cmap group')
                previous_hi=hi
                for code in range(lo,hi+1):
                    if glyph and not 0xd800<=code<=0xdfff:mappings[code]=glyph
                    glyph+=1
            formats.add(12)
    if not formats:fail('UNSUPPORTED_TTF_CMAP','$','Only Unicode format 4/12 are supported')
    ranges=[]
    for code in sorted(mappings):
        if ranges and ranges[-1][1]+1==code:ranges[-1][1]=code
        else:ranges.append([code,code])
    return dict(glyphCount=glyph_count,cmapFormats=sorted(formats),unicodeRanges=ranges)


def missing(metadata,text):
    return sorted({ord(ch) for ch in text if not ch.isspace() and not any(lo<=ord(ch)<=hi for lo,hi in metadata['unicodeRanges'])})
