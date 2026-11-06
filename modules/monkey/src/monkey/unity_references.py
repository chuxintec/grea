"""Exact serialized-file / signed PPtr reference resolution. Metadata only, never pixels."""
import re
from .sources.compiled import fail


def file_table(index):
    by_name={};by_key={}
    for container in index['containers']:
        if container['status']!='indexed':continue
        for f in container['files']:
            if f['key'] in by_key:continue
            by_key[f['key']]=f;by_name.setdefault(f['name'].casefold(),[]).append(f)
    return by_key,by_name


def resolve(index,source_key,file_id,path_id):
    by_key,by_name=file_table(index)
    if not isinstance(path_id,str) or len(path_id)>20 or path_id=='-0' or not re.fullmatch(r'-?(0|[1-9][0-9]*)',path_id) or not -(1<<63)<=int(path_id)<(1<<63):
        fail('UNITY_PPTR_PATH_ID',str(path_id),'Expected signed64 decimal string')
    if not isinstance(file_id,str) or len(file_id)>10 or not re.fullmatch(r'0|[1-9][0-9]*',file_id) or int(file_id)>(1<<31)-1:
        fail('UNITY_PPTR_FILE_ID',str(file_id),'Expected nonnegative decimal fileId string')
    if path_id=='0':return dict(status='null')
    source=by_key.get(source_key)
    if source is None:return dict(status='unresolved',reason='source-file-missing')
    target=source
    if file_id!='0':
        entries=[e for e in source['externals'] if e['fileId']==file_id]
        if len(entries)!=1:return dict(status='unresolved',reason='external-fileId-out-of-range')
        name=entries[0]['path']
        if name.startswith('archive:/'):
            parts=name.removeprefix('archive:/').split('/')
            if len(parts)!=2 or parts[0]!=parts[1]:return dict(status='unresolved',reason='archive-path-contract-unknown')
            name=parts[1]
        if '/'in name or '\\'in name:return dict(status='unresolved',reason='external-alias-contract-unknown')
        candidates=by_name.get(name.casefold(),[])
        if len(candidates)!=1:return dict(status='unresolved',reason='external-file-missing'if not candidates else'external-file-ambiguous',name=name)
        target=candidates[0]
    objects=[o for o in target['objects'] if o['pathId']==path_id]
    if len(objects)!=1:return dict(status='unresolved',reason='target-object-missing-or-ambiguous')
    return dict(status='metadata-resolved',file=target['key'],pathId=path_id,type=objects[0]['type'],nativeReference='not_verified')
