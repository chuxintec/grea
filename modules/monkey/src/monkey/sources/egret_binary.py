"""Bounded reviewed Egret-custom binary resource/Plist records; no source runtime."""
import zlib
from ..io import sha
from .compiled import fail

PROFILE='egret-custom-resource-plist-v1'
TYPES=['image','json','text','xml','sheet','font','bin','sound','atlas','imageWithGrid','ktx']
MAX_BYTES=64*1024*1024
MAX_RECORDS=200_000


def inflate(raw):
    if len(raw)>32*1024*1024:fail('EGRET_BINARY_BUDGET','$','Compressed source exceeds 32 MiB')
    decoder=zlib.decompressobj()
    try:
        data=decoder.decompress(raw,MAX_BYTES+1)
        if len(data)>MAX_BYTES or decoder.unconsumed_tail:fail('EGRET_BINARY_BUDGET','$','Expanded source exceeds 64 MiB')
        if not decoder.eof or decoder.unused_data:fail('EGRET_BINARY_ZLIB','$','Expected one complete zlib stream with no suffix')
    except zlib.error:fail('EGRET_BINARY_ZLIB','$','Invalid declared zlib payload')
    return data


class Reader:
    def __init__(self,data,start=0,end=None):
        self.data=data;self.position=start;self.end=len(data)if end is None else end
    def take(self,count):
        if type(count)is not int or count<0 or self.position+count>self.end:fail('EGRET_BINARY_TRUNCATED',str(self.position),'Declared byte span exceeds bounded payload')
        start=self.position;self.position+=count;return self.data[start:self.position]
    def byte(self):return self.take(1)[0]
    def number(self,signed=False):
        result=0;multiplier=1;negative=False
        for index in range(8):
            value=self.byte();more=bool(value&128);value&=127
            if signed and index==0:negative=bool(value&64);result=value&63;multiplier=64
            else:result+=value*multiplier;multiplier*=128
            if result>2**53-1:fail('EGRET_BINARY_NUMBER',str(self.position),'Integer exceeds exact source Number range')
            if not more:return -result if negative else result
        fail('EGRET_BINARY_NUMBER',str(self.position),'Overlong variable integer')
    def count(self):
        value=self.number()
        if value>MAX_RECORDS:fail('EGRET_BINARY_BUDGET',str(self.position),'Record count exceeds limit')
        return value
    def text(self):
        size=self.number()
        if size>1024*1024:fail('EGRET_BINARY_BUDGET',str(self.position),'String exceeds 1 MiB')
        try:value=self.take(size).decode('utf-8')
        except UnicodeError:fail('EGRET_BINARY_UTF8',str(self.position),'Invalid source UTF-8 string')
        if '\x00'in value:fail('EGRET_BINARY_STRING',str(self.position),'NUL is not a resource identifier')
        return value
    def finish(self):
        if self.position!=self.end:fail('EGRET_BINARY_SUFFIX',str(self.position),'Unconsumed bytes in declared record')


def resource_manifest(raw):
    data=inflate(raw);reader=Reader(data);prefixes=[reader.text()for _ in range(int.from_bytes(reader.take(2),'big'))]
    kinds=[]
    for _ in range(reader.count()):
        kind=reader.number();count=reader.count()
        if kind>=len(TYPES):fail('EGRET_RESOURCE_TYPE',str(kind),'Unknown original resource enum')
        kinds.append((kind,count))
    if sum(n for _,n in kinds)>MAX_RECORDS:fail('EGRET_BINARY_BUDGET','$','Aggregate resources exceed limit')
    records=[];names=set()
    for kind,count in kinds:
        for _ in range(count):
            start=reader.position;name=reader.text();prefix=reader.number();tail=reader.text();size=reader.number()
            if not name or name in names:fail('EGRET_RESOURCE_DUPLICATE',name,'Empty or repeated original resource name')
            if prefix>=len(prefixes):fail('EGRET_RESOURCE_PREFIX',str(prefix),'Invalid original path prefix index')
            names.add(name);record=dict(name=name,type=TYPES[kind],url=prefixes[prefix]+tail,declaredBytes=size,sourceEnum=kind)
            if kind==4:record['subkeys']=reader.text().split(',')
            if kind==9:record['scale9grid']=reader.text()
            record['sourceBytes']=dict(start=start,end=reader.position);records.append(record)
    groups={}
    for _ in range(reader.count()):
        name=reader.text();count=reader.count()
        if name in groups:fail('EGRET_RESOURCE_GROUP',name,'Repeated group identity')
        indices=[reader.number()for _ in range(count)]
        if any(i>=len(records)for i in indices):fail('EGRET_RESOURCE_INDEX',name,'Group index outside exact resource table')
        groups[name]=[records[i]['name']for i in indices]
    reader.finish()
    return dict(schemaVersion=1,profile=PROFILE,kind='resource-manifest',sourceSha256=sha(raw),expandedSha256=sha(data),expandedBytes=len(data),prefixes=prefixes,resources=records,groups=groups,sourceExecuted=False)


def plist_pack(raw):
    data=inflate(raw);reader=Reader(data);sheets=[];names=set();total=0
    while reader.position<reader.end:
        start=reader.position;name=reader.text();size=reader.number();begin=reader.position
        reader.take(size);body=Reader(data,begin,begin+size)
        if not name or name in names:fail('EGRET_PLIST_DUPLICATE',name,'Empty or repeated original sheet identity')
        names.add(name);frames=[];keys=set()
        for _ in range(body.count()):
            at=body.position;key=body.text();x,y,w,h=[body.number()for _ in range(4)];flag=body.byte()
            if flag not in (0,1):fail('EGRET_PLIST_FLAG',str(flag),'Unknown trim flag')
            if not key or key in keys:fail('EGRET_PLIST_DUPLICATE',key,'Empty or repeated original frame key')
            keys.add(key)
            if flag:ox=body.number(True);oy=body.number(True);sw=body.number();sh=body.number()
            else:ox=oy=0;sw=w;sh=h
            if min(w,h,sw,sh)<=0:fail('EGRET_PLIST_GEOMETRY',key,'Zero-sized original frame unsupported')
            frames.append(dict(name=key,rect=[x,y,w,h],trimOrigin=[ox,oy],originalSize=[sw,sh],rotated=False,sourceBytes=dict(start=at,end=body.position)))
        body.finish();total+=len(frames)
        if len(sheets)>=MAX_RECORDS or total>MAX_RECORDS:fail('EGRET_BINARY_BUDGET','$','Aggregate sheet/frame count exceeds limit')
        sheets.append(dict(name=name+'_json',textureName=name+'_png',frames=frames,sourceBytes=dict(start=start,end=reader.position)))
    reader.finish()
    return dict(schemaVersion=1,profile=PROFILE,kind='plist-pack',sourceSha256=sha(raw),expandedSha256=sha(data),expandedBytes=len(data),sheets=sheets,sourceExecuted=False)


def bin_json(raw):
    """Decode reviewed BinJsonUtil VERSION=2 as data, retaining exact byte evidence."""
    import math
    import re
    data=inflate(raw);reader=Reader(data)
    version=int.from_bytes(reader.take(2),'big')
    if version!=2:fail('EGRET_BINJSON_VERSION',str(version),'Only reviewed BinJsonUtil VERSION 2 supported')
    strings=[reader.text()for _ in range(reader.count())];nodes=0
    def string(index):
        if index>=len(strings):fail('EGRET_BINJSON_STRING',str(index),'String index outside exact table')
        return strings[index]
    def integer(size):return int.from_bytes(reader.take(size),'big')
    def number(value,negative=False):
        if value>2**53-1:fail('EGRET_BINJSON_NUMBER',str(reader.position),'Source integer exceeds exact Number subset')
        return -0.0 if negative and value==0 else -value if negative else value
    def parse(depth=0):
        nonlocal nodes
        nodes+=1
        if nodes>4_000_000 or depth>128:fail('EGRET_BINJSON_BUDGET',str(reader.position),'Value/depth limit exceeded')
        tag=reader.byte()
        if tag==0:return None
        if tag==1:return 0
        if tag in (2,3,4):return number(integer({2:1,3:2,4:4}[tag]),True)
        if tag in (6,7,8):return number(integer({6:1,7:2,8:4}[tag]))
        if tag in (5,9):
            low=integer(4);high=integer(4);return number(high*2**32+low,tag==5)
        if tag==10:
            text=string(reader.number())
            if not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?',text):fail('EGRET_BINJSON_NUMBER',str(reader.position),'Non-finite or prefix-only parseFloat is outside numeric JSON subset')
            value=float(text)
            if not math.isfinite(value):fail('EGRET_BINJSON_NUMBER',str(reader.position),'Non-finite number cannot become formal JSON')
            return value
        if tag==11:return ''
        if tag in (12,13,14):return string(integer(1)if tag==12 else integer(2)if tag==13 else reader.number()+65536)
        if tag==15:return []
        if tag in (16,17,18,19):
            count=reader.count();nodes+=count if tag!=16 else 0
            if nodes>4_000_000:fail('EGRET_BINJSON_BUDGET',str(reader.position),'Aggregate array value limit exceeded')
            return [parse(depth+1)if tag==16 else reader.number(tag==18)if tag in (17,18)else string(reader.number())for _ in range(count)]
        if tag==20:return {}
        if tag in (21,22,23):
            result={}
            for _ in range(reader.count()):
                key=string(reader.number())if tag==21 else str(reader.number(tag==23))
                if key in result:fail('EGRET_BINJSON_DUPLICATE',key,'Repeated object key requires explicit source overwrite semantics')
                result[key]=parse(depth+1)
            return result
        if tag in (24,25):return tag==24
        fail('EGRET_BINJSON_TAG',str(tag),'Unknown source value tag')
    value=parse();reader.finish()
    return dict(schemaVersion=1,profile=PROFILE,kind='bin-json-v2',version=version,sourceSha256=sha(raw),expandedSha256=sha(data),expandedBytes=len(data),stringCount=len(strings),valueNodes=nodes,value=value,sourceExecuted=False)
