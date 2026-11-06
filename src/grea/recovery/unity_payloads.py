"""Source-schema-bound streaming of large Unity byte/PPtr arrays into sealed chunks."""
import hashlib
import json
import re
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path
from .io import inside,read,load,sha
from .unity_parse_limits import MAX_DOCUMENT_BYTES,MAX_DOCUMENT_NODES

CHUNK_ELEMENTS=8192
MAX_PAYLOAD_BYTES=256*1024**2


@dataclass
class StreamedArray:
    descriptor: dict


class PayloadWriter:
    def __init__(self,root,source_hash):
        self.root=Path(root);self.source_hash=source_hash;self.files=[];self.total=0

    def rollback(self,start):
        for row in self.files[start:]:inside(self.root,row['path']).unlink()
        del self.files[start:];self.total=sum(r['bytes'] for r in self.files)

    def write_array(self,reader,length,stride,endian,key,encoding):
        if length<0 or self.total+length*stride>MAX_PAYLOAD_BYTES:raise ValueError('Streamed payload byte budget exceeded')
        chunks=[];digest=hashlib.sha256()
        for offset in range(0,length,CHUNK_ELEMENTS):
            count=min(CHUNK_ELEMENTS,length-offset);raw=reader.read_bytes(count*stride)
            if len(raw)!=count*stride:raise ValueError('Truncated streamed array')
            rel=f'typed-data/{self.source_hash}/{key}/{offset:010d}.bin';path=inside(self.root,rel);path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as stream:stream.write(raw)
            row=dict(path=rel,bytes=len(raw),sha256=sha(raw));self.files.append(row);self.total+=len(raw)
            chunks.append(dict(row,start=offset,count=count));digest.update(raw)
        return StreamedArray(dict(typeVersion=1,**{'$type':'UnityArrayChunks'},encoding=encoding,endian=endian,
                                  length=length,bytes=length*stride,sha256=digest.hexdigest(),chunks=chunks))


def array_shape(field,kind):
    """Accept only the exact fixed-width layouts; no guessing of versions/field widths."""
    if len(field.m_Children)!=1:return None
    array=field.m_Children[0]
    if array.m_Type!='Array' or len(array.m_Children)!=2:return None
    size,data=array.m_Children
    if size.m_Type!='int' or size.m_ByteSize!=4 or size.m_Children or (size.m_MetaFlag or 0)&0x4000:return None
    if (data.m_MetaFlag or 0)&0x4000:return None
    if kind=='Font' and field.m_Name=='m_FontData' and data.m_Type in ('char','UInt8','unsigned char') and data.m_ByteSize==1 and not data.m_Children:
        return (array,1,'uint8')
    if kind=='AssetBundle' and field.m_Name=='m_PreloadTable' and data.m_Type=='PPtr<Object>' and data.m_ByteSize==12:
        children=data.m_Children
        if [(c.m_Name,c.m_Type,c.m_ByteSize) for c in children]==[('m_FileID','int',4),('m_PathID','SInt64',8)] and all(not c.m_Children and not (c.m_MetaFlag or 0)&0x4000 for c in children):
            return (array,12,'unity-pptr-i32-i64')
    return None


def read_streamed(obj,writer,file_id):
    if writer is None or obj.type.name not in ('Font','AssetBundle'):return None
    from UnityPy.helpers.TypeTreeHelper import TypeTreeConfig,read_value,metaflag_is_aligned
    from UnityPy.streams import EndianBinaryReader
    node=obj._get_typetree_node()
    if not any(array_shape(c,obj.type.name) for c in node.m_Children):return None
    # A bounded object-local reader cannot consume bytes from the next object.
    raw=obj.get_raw_data();reader=EndianBinaryReader(raw,endian=obj.reader.endian);config=TypeTreeConfig(True,obj.assets_file,False)
    typed={};blocks=[]
    for field in node.m_Children:
        shape=array_shape(field,obj.type.name);start=reader.Position
        if shape:
            array,stride,encoding=shape;length=reader.read_int()
            if length<0 or length*stride>len(raw)-reader.Position:raise ValueError('Streamed array length exceeds exact object boundary')
            if length>=CHUNK_ELEMENTS:
                value=writer.write_array(reader,length,stride,reader.endian,f'{file_id}-{obj.path_id}-{field.m_Name}',encoding)
                if metaflag_is_aligned(field.m_MetaFlag) or metaflag_is_aligned(array.m_MetaFlag):reader.align_stream()
                typed[field.m_Name]=value;blocks.append(dict(location='$/'+field.m_Name,**value.descriptor));continue
            reader.Position=start
        typed[field.m_Name]=read_value(field,reader,config)
    if metaflag_is_aligned(node.m_MetaFlag):reader.align_stream()
    if reader.Position!=len(raw):raise ValueError(f'Expected to read {len(raw)} bytes, but only read {reader.Position} bytes')
    return typed,blocks


def write_document(path,body):
    """Bound the JSON while writing, without a second full encoded document in RAM."""
    path=Path(path);temporary=path.with_suffix('.partial');h=hashlib.sha256();total=0;pending=[];size=0
    with temporary.open('xb') as stream:
        def flush():
            nonlocal total,size
            raw=''.join(pending).encode();total+=len(raw)
            if total>MAX_DOCUMENT_BYTES:raise ValueError('Typed output exceeds128MiB; reduce inline budget or add a supported streamed field')
            stream.write(raw);h.update(raw);pending.clear();size=0
        for part in json.JSONEncoder(ensure_ascii=False,allow_nan=False,separators=(',',':')).iterencode(body):
            pending.append(part);size+=len(part)
            if size>=65536:flush()
        if pending:flush()
    if path.exists():raise ValueError('Refusing to replace an existing typed document')
    temporary.rename(path);return h.hexdigest()


def validate_payloads(root,document):
    """Hash/length/path closure, also used before reuse, prepare and candidate copying."""
    root=Path(root);files=document.get('payloadFiles',[]);declared={}
    source_hash=document.get('source',{}).get('sha256')
    for row in files:
        rel=row['path']
        if not source_hash or not re.fullmatch(r'typed-data/'+re.escape(source_hash)+r'/[0-9]+--?[0-9]+-m_(?:FontData|PreloadTable)/[0-9]{10}\.bin',rel):
            raise ValueError('Invalid streamed payload path')
        if rel in declared or type(row['bytes'])is not int or not 0<row['bytes']<=CHUNK_ELEMENTS*12:raise ValueError('Duplicate or oversized payload chunk')
        raw=read(inside(root,rel),max_bytes=CHUNK_ELEMENTS*12)
        if len(raw)!=row['bytes'] or sha(raw)!=row['sha256']:raise ValueError('Streamed payload hash/size changed')
        declared[rel]=row
    if sum(r['bytes']for r in files)>MAX_PAYLOAD_BYTES:raise ValueError('Streamed payload total exceeds budget')
    used=set()
    for obj in document.get('objects',[]):
        for block in obj.get('payloads',[]):
            if obj.get('status')!='parsed':raise ValueError('Unparsed object cannot claim a decoded payload')
            field=block['location'].removeprefix('$/')
            if obj.get('data',{}).get(field)!={k:v for k,v in block.items()if k!='location'}:raise ValueError('Streamed field/descriptor mismatch')
            for chunk in block['chunks']:
                if declared.get(chunk['path'])!={k:chunk[k]for k in ('path','bytes','sha256')}:raise ValueError('Unsealed payload descriptor')
                if chunk['path']in used:raise ValueError('Payload chunk claimed twice')
                used.add(chunk['path'])
            # Verify ordering, complete count and the concatenated payload hash.
            for _ in iter_payload(root,block):pass
    if used!=set(declared):raise ValueError('Unreferenced streamed payload file')
    if source_hash:
        base=root/'typed-data'/source_hash
        actual={p.relative_to(root).as_posix()for p in base.rglob('*')if p.is_file()}if base.exists()else set()
        if actual!=set(declared):raise ValueError('Unknown or missing streamed payload files')
    return files


def iter_payload(root,block):
    stride={'uint8':1,'unity-pptr-i32-i64':12}.get(block.get('encoding'))
    if not stride or block.get('endian')not in ('<','>') or block.get('$type')!='UnityArrayChunks' or block.get('typeVersion')!=1:raise ValueError('Unsupported streamed payload encoding')
    count=0;total=0;h=hashlib.sha256()
    for row in block['chunks']:
        if row['start']!=count or type(row['count'])is not int or not 0<row['count']<=CHUNK_ELEMENTS:raise ValueError('Noncontiguous streamed payload')
        raw=read(inside(Path(root),row['path']),max_bytes=CHUNK_ELEMENTS*12)
        if len(raw)!=row['count']*stride or len(raw)!=row['bytes'] or sha(raw)!=row['sha256']:raise ValueError('Payload identity mismatch')
        count+=row['count'];total+=len(raw);h.update(raw);yield raw
    if count!=block['length'] or total!=block['bytes'] or h.hexdigest()!=block['sha256']:raise ValueError('Incomplete streamed payload')


def iter_references(root,block):
    if block['encoding']!='unity-pptr-i32-i64':raise ValueError('Expected PPtr block')
    index=0
    for raw in iter_payload(root,block):
        for file_id,path_id in struct.iter_unpack(block['endian']+'iq',raw):
            yield dict(location=block['location']+'/'+str(index),fileId=str(file_id),pathId=str(path_id));index+=1


def copy_payloads(source,target,document):
    files=validate_payloads(source,document)
    for row in files:
        src=inside(Path(source),row['path']);dest=inside(Path(target),row['path']);dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():
            if sha(read(dest,max_bytes=CHUNK_ELEMENTS*12))!=row['sha256']:raise ValueError('Payload copy collision')
        else:shutil.copyfile(src,dest)
    return len(files)


def load_typed(path):
    return load(read(path,max_bytes=MAX_DOCUMENT_BYTES),max_nodes=MAX_DOCUMENT_NODES,max_depth=128)
