"""Bounded, read-only PE/CLI metadata inspection. Never loads or executes assemblies.

``types`` lists all TypeDefs, while ``publicTypes`` contains externally visible
TypeDefs only. This metadata inventory does not prove Unity serialized references
or native asset bindings are valid.
"""
from __future__ import annotations

import hashlib
import struct

MAX_INPUT = 64 * 1024 * 1024
MAX_ROWS = 1_000_000
MAX_TYPES = 100_000


class _Reader:
    def __init__(self, data): self.data=data
    def check(self, off, size, limit=None):
        end_limit=len(self.data) if limit is None else min(len(self.data),limit)
        if type(off) is not int or type(size) is not int or off<0 or size<0 or off>end_limit or size>end_limit-off:
            raise ValueError("truncated or out-of-bounds PE/CLI metadata")
    def u16(self, off, limit=None): self.check(off,2,limit); return struct.unpack_from("<H",self.data,off)[0]
    def u32(self, off, limit=None): self.check(off,4,limit); return struct.unpack_from("<I",self.data,off)[0]
    def u64(self, off, limit=None): self.check(off,8,limit); return struct.unpack_from("<Q",self.data,off)[0]
    def bytes(self, off, size, limit=None): self.check(off,size,limit); return self.data[off:off+size]


# ECMA-335 tables 0..44. Entries are either fixed-width primitive names,
# heap names, table names, or coded-index names.
_SCHEMA={
0:("u2","str","guid","guid","guid"), 1:("coded:ResolutionScope","str","str"),
2:("u4","str","str","coded:TypeDefOrRef","table:Field","table:MethodDef"),
3:("table:Field",), 4:("u2","str","blob"), 5:("table:MethodDef",),
6:("u4","u2","u2","str","blob","table:Param"), 7:("table:Param",),
8:("u2","u2","str"), 9:("table:TypeDef","coded:TypeDefOrRef"),
10:("coded:MemberRefParent","str","blob"), 11:("u1","u1","coded:HasConstant","blob"),
12:("coded:HasCustomAttribute","coded:CustomAttributeType","blob"),
13:("coded:HasFieldMarshal","blob"), 14:("u2","coded:HasDeclSecurity","blob"),
15:("u2","u4","table:TypeDef"), 16:("u4","table:Field"), 17:("blob",),
18:("table:TypeDef","table:Event"), 19:("table:Event",), 20:("u2","str","coded:TypeDefOrRef"),
21:("table:TypeDef","table:Property"), 22:("table:Property",), 23:("u2","str","blob"),
24:("u2","table:MethodDef","coded:HasSemantics"),
25:("table:TypeDef","coded:MethodDefOrRef","coded:MethodDefOrRef"),
26:("str",), 27:("blob",), 28:("u2","coded:MemberForwarded","str","table:ModuleRef"),
29:("u4","table:Field"), 30:("u4","u4"), 31:("u4",),
32:("u4","u2","u2","u2","u2","u4","blob","str","str"),
33:("u4",), 34:("u4","u4","u4"),
35:("u2","u2","u2","u2","u4","blob","str","str","blob"),
36:("u4","table:AssemblyRef"), 37:("u4","u4","u4","table:AssemblyRef"),
38:("u4","str","blob"), 39:("u4","u4","str","str","coded:Implementation"),
40:("u4","u4","str","str","coded:Implementation"),
41:("table:TypeDef","table:TypeDef"),
42:("u2","u2","coded:TypeOrMethodDef","str"),
43:("coded:MethodDefOrRef","blob"), 44:("table:GenericParam","coded:TypeDefOrRef"),
}
_CODED={
"ResolutionScope":(2,(0,26,35,1)), "TypeDefOrRef":(2,(2,1,27)),
"MemberRefParent":(3,(2,1,26,6,27)), "HasConstant":(2,(4,8,23)),
"HasCustomAttribute":(5,(6,4,1,2,8,9,10,0,14,23,20,17,26,27,32,35,38,39,40,42,44,43)),
"CustomAttributeType":(3,(None,None,6,10,None)), "HasFieldMarshal":(1,(4,8)),
"HasDeclSecurity":(2,(2,6,32)), "HasSemantics":(1,(20,23)), "MethodDefOrRef":(1,(6,10)),
"MemberForwarded":(1,(4,6)), "Implementation":(2,(38,35,39)), "TypeOrMethodDef":(1,(2,6)),
}


def _compressed(reader, pos, limit):
    first=reader.bytes(pos,1,limit)[0]
    if first&0x80==0: return first,pos+1
    if first&0xC0==0x80:
        second=reader.bytes(pos+1,1,limit)[0]
        return ((first&0x3F)<<8)|second,pos+2
    if first&0xE0==0xC0:
        b=reader.bytes(pos,4,limit)
        return ((b[0]&0x1F)<<24)|(b[1]<<16)|(b[2]<<8)|b[3],pos+4
    raise ValueError("invalid compressed metadata integer")


def _align4(n): return (n+3)&~3


def _metadata_root(r, off, size):
    end=off+size; r.check(off,size)
    if r.u32(off,end)!=0x424A5342: raise ValueError("invalid CLI metadata signature")
    ver_len=r.u32(off+12,end)
    if ver_len<1 or ver_len>1024 or off+16+ver_len>end: raise ValueError("invalid metadata version string")
    p=_align4(off+16+ver_len)
    _flags=r.u16(p,end); count=r.u16(p+2,end); p+=4
    if not 1<=count<=64: raise ValueError("invalid metadata stream count")
    streams={}
    for _ in range(count):
        so=r.u32(p,end); ss=r.u32(p+4,end); p+=8
        name_bytes=bytearray()
        for _n in range(32):
            b=r.bytes(p,1,end)[0];p+=1
            if b==0: break
            name_bytes.append(b)
        else: raise ValueError("unterminated metadata stream name")
        name=bytes(name_bytes).decode("ascii","strict")
        p=_align4(p)
        if name in streams or so>end-off or ss>end-off-so: raise ValueError("invalid or duplicate metadata stream")
        streams[name]=(off+so,off+so+ss)
    if "#Strings" not in streams or "#Blob" not in streams: raise ValueError("required metadata heaps missing")
    table_name="#~" if "#~" in streams else "#-" if "#-" in streams else None
    if table_name is None: raise ValueError("metadata tables stream missing")
    return streams,streams[table_name]


def _str_heap(r, stream, index):
    start,end=stream
    if index==0: return ""
    pos=start+index
    if pos<start or pos>=end: raise ValueError("string heap index out of range")
    stop=r.data.find(b"\0",pos,end)
    if stop<0: raise ValueError("unterminated metadata string")
    try: return r.bytes(pos,stop-pos,end).decode("utf-8","strict")
    except UnicodeDecodeError as e: raise ValueError("invalid metadata UTF-8 string") from e


def _blob_heap(r, stream, index):
    start,end=stream
    if index==0: return b""
    pos=start+index
    if pos<start or pos>=end: raise ValueError("blob heap index out of range")
    length,p=_compressed(r,pos,end)
    return r.bytes(p,length,end)


def _parse_tables(r, tables, streams):
    pos,end=tables
    r.check(pos,24,end)
    heap_flags=r.bytes(pos+6,1,end)[0]
    valid=r.u64(pos+8,end);pos+=24
    counts={};total=0
    for tid in range(64):
        if valid>>tid&1:
            n=r.u32(pos,end);pos+=4;counts[tid]=n;total+=n
            if total>MAX_ROWS: raise ValueError("metadata row budget exceeded")
    if any(tid not in _SCHEMA and n for tid,n in counts.items()): raise ValueError("unsupported metadata table schema")
    str_size=4 if heap_flags&1 else 2
    guid_size=4 if heap_flags&2 else 2
    blob_size=4 if heap_flags&4 else 2
    def idx_size(kind):
        if kind.startswith("table:"):
            t=_table_id(kind[6:]);return 4 if counts.get(t,0)>=65536 else 2
        if kind.startswith("coded:"):
            name=kind[6:];bits,targets=_CODED[name];maximum=max((counts.get(t,0) for t in targets if t is not None),default=0)
            return 4 if maximum >= (1<<(16-bits)) else 2
        return {"u1":1,"u2":2,"u4":4,"str":str_size,"guid":guid_size,"blob":blob_size}[kind]
    offsets={};sizes={};cur=pos
    for tid in sorted(counts):
        if tid>44: continue
        schema=_SCHEMA.get(tid)
        if schema is None:
            if counts[tid]: raise ValueError("unsupported metadata table schema")
            continue
        row_size=sum(idx_size(k) for k in schema);offsets[tid]=cur;sizes[tid]=row_size
        cur+=row_size*counts[tid]
        if cur>end or cur>len(r.data): raise ValueError(f"metadata table {tid} rows out of bounds")
    return counts,offsets,sizes,(str_size,guid_size,blob_size),pos,end


def _table_id(name):
    # ECMA table identifiers used by schemas above.
    names={"Module":0,"TypeRef":1,"TypeDef":2,"Field":4,"MethodDef":6,"Param":8,"InterfaceImpl":9,"MemberRef":10,"Constant":11,"CustomAttribute":12,"FieldMarshal":13,"DeclSecurity":14,"ClassLayout":15,"FieldLayout":16,"StandAloneSig":17,"EventMap":18,"Event":20,"PropertyMap":21,"Property":23,"MethodSemantics":24,"MethodImpl":25,"ModuleRef":26,"TypeSpec":27,"ImplMap":28,"FieldRVA":29,"Assembly":32,"AssemblyRef":35,"AssemblyRefProcessor":36,"AssemblyRefOS":37,"File":38,"ExportedType":39,"ManifestResource":40,"NestedClass":41,"GenericParam":42,"MethodSpec":43,"GenericParamConstraint":44}
    if name not in names: raise ValueError("unknown metadata table " + name)
    return names[name]


def _row_reader(r, tid, index, counts, offsets, sizes, heap_sizes, end):
    if index<0 or index>=counts.get(tid,0): raise ValueError("metadata row index out of range")
    p=offsets[tid]+index*sizes[tid]; limit=p+sizes[tid]
    str_size,guid_size,blob_size=heap_sizes
    schema=_SCHEMA[tid]; values=[]
    for kind in schema:
        n=({"u1":1,"u2":2,"u4":4,"str":str_size,"guid":guid_size,"blob":blob_size}.get(kind))
        if kind.startswith(("table:","coded:")):
            if kind.startswith("table:"): n=4 if counts.get(_table_id(kind[6:]),0)>=65536 else 2
            else:
                bits,targets=_CODED[kind[6:]];n=4 if max((counts.get(t,0) for t in targets if t is not None),default=0)>=(1<<(16-bits)) else 2
        values.append(r.u32(p,limit) if n==4 else r.u16(p,limit) if n==2 else r.bytes(p,1,limit)[0]);p+=n
    return values


def _pe_metadata(r):
    if r.bytes(0,2)!=b"MZ": raise ValueError("not a PE image")
    pe=r.u32(0x3c)
    if r.bytes(pe,4)!=b"PE\0\0": raise ValueError("invalid PE signature")
    r.check(pe+4,20)
    sections=r.u16(pe+6); opt_size=r.u16(pe+20); opt=pe+24;r.check(opt,opt_size)
    if sections<1 or sections>96: raise ValueError("invalid PE section count")
    magic=r.u16(opt)
    if magic==0x10b: dd=opt+96
    elif magic==0x20b: dd=opt+112
    else: raise ValueError("unsupported PE optional header")
    if dd+15*8>opt+opt_size: raise ValueError("truncated PE data directories")
    cli_rva=r.u32(dd+14*8);cli_size=r.u32(dd+14*8+4)
    if cli_rva==0 or cli_size<24: raise ValueError("PE has no CLI header")
    sec_pos=opt+opt_size; mappings=[]
    for i in range(sections):
        sh=sec_pos+i*40;r.check(sh,40)
        vsize=r.u32(sh+8);va=r.u32(sh+12);raw_size=r.u32(sh+16);raw_ptr=r.u32(sh+20)
        if raw_size: r.check(raw_ptr,raw_size)
        mappings.append((va,max(vsize,raw_size),raw_ptr,raw_size))
    def rva_offset(rva,size):
        for va,span,raw,raw_size in mappings:
            if va<=rva and size<=raw_size and rva-va<=raw_size-size:
                out=raw+(rva-va);r.check(out,size);return out
        raise ValueError("RVA is not backed by section data")
    cli=rva_offset(cli_rva,24);meta_rva=r.u32(cli+8);meta_size=r.u32(cli+12)
    if meta_size<32 or meta_size>MAX_INPUT: raise ValueError("invalid CLI metadata size")
    return rva_offset(meta_rva,meta_size),meta_size


def inspect_managed(data: bytes) -> dict:
    """Read assembly identity, all TypeDefs and public TypeDefs without loading code.

    Assembly/type identity from this result is not evidence of native serialized
    binding validity.
    """
    if not isinstance(data,(bytes,bytearray,memoryview)): raise ValueError("input must be bytes-like")
    if len(data)>MAX_INPUT: raise ValueError("input exceeds 64 MiB budget")
    r=_Reader(bytes(data))
    root,size=_pe_metadata(r);streams,tables=_metadata_root(r,root,size)
    counts,offsets,sizes,heap_sizes,_,table_end=_parse_tables(r,tables,streams)
    if counts.get(32,0)!=1: raise ValueError("expected exactly one Assembly row")
    assembly=_row_reader(r,32,0,counts,offsets,sizes,heap_sizes,table_end)
    name=_str_heap(r,streams["#Strings"],assembly[7]);culture=_str_heap(r,streams["#Strings"],assembly[8])
    version=list(assembly[1:5]);flags=assembly[5];key=_blob_heap(r,streams["#Blob"],assembly[6])
    if not name or len(version)!=4: raise ValueError("invalid Assembly identity")
    public_hash=hashlib.sha256(key).hexdigest() if key else None
    type_count=counts.get(2,0)
    if type_count>MAX_TYPES: raise ValueError("TypeDef count exceeds 100,000 type budget")
    raw_types=[]
    for i in range(type_count):
        row=_row_reader(r,2,i,counts,offsets,sizes,heap_sizes,table_end)
        raw_types.append((row[0],_str_heap(r,streams["#Strings"],row[2]),_str_heap(r,streams["#Strings"],row[1])))
    parents={}
    for i in range(counts.get(41,0)):
        nested,enclosing=_row_reader(r,41,i,counts,offsets,sizes,heap_sizes,table_end)
        nested-=1;enclosing-=1
        if not 0<=nested<type_count or not 0<=enclosing<type_count or nested in parents: raise ValueError("invalid NestedClass relation")
        parents[nested]=enclosing
    cache={};active=set()
    def full_name(i):
        if i in cache:return cache[i]
        if i in active:raise ValueError("cyclic NestedClass relation")
        if len(active)>=128:raise ValueError("NestedClass depth exceeds bounded inspection")
        active.add(i);_flags,ns,n=raw_types[i]
        if not n: raise ValueError("TypeDef has empty name")
        if i in parents:
            parent=full_name(parents[i]);result=parent+"+"+n
        else: result=(ns+"." if ns else "")+n
        active.remove(i);cache[i]=result;return result
    # ECMA-335's <Module> TypeDef is the module pseudo-type, not a CLR type name.
    types=[full_name(i) for i in range(type_count) if raw_types[i][2]!="<Module>"]
    if len(types)!=len(set(types)):raise ValueError("duplicate TypeDef identity")
    visibility_cache={};visiting=set()
    def externally_visible(i):
        if i in visibility_cache:return visibility_cache[i]
        if i in visiting:raise ValueError("cyclic TypeDef visibility relation")
        visiting.add(i);visibility=raw_types[i][0]&0x7
        if i in parents: visible=visibility==2 and externally_visible(parents[i])
        else: visible=visibility==1
        visiting.remove(i);visibility_cache[i]=visible;return visible
    public_types=[full_name(i) for i in range(type_count) if raw_types[i][2]!="<Module>" and externally_visible(i)]
    return {"name":name,"version":version,"culture":culture or "neutral","publicKeySha256":public_hash,"types":types,"publicTypes":public_types}
