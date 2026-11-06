"""Exact frozen texture bindings; bucket names are source data, not dimensions."""
import re


def cache_parts(path):
    if not isinstance(path,str):raise ValueError('Expected literal texture cache logical path')
    parts=path.split('/')
    if len(parts)!=5 or parts[:2]!=['Assets','Textures'] or parts[2]not in ('astc','dds') or any(p in ('','.','..')or '\\'in p or '\x00'in p for p in parts):
        raise ValueError('Expected Assets/Textures/{astc,dds}/<literal-bucket>/<exact-key>.txt')
    if not parts[4].endswith('.txt'):raise ValueError('Expected exact .txt cache filename')
    return parts


def validate_selection(data,source_sha):
    if not isinstance(data,dict)or set(data)!={'schemaVersion','sourceSha256','objects'}or type(data['schemaVersion'])is not int or data['schemaVersion']!=1:
        raise ValueError('Expected selection schemaVersion 1, sourceSha256 and objects')
    if data['sourceSha256']!=source_sha:raise ValueError('Selection source SHA-256 differs from the current input')
    rows=data['objects']
    if not isinstance(rows,list)or not 1<=len(rows)<=256:raise ValueError('Select 1..256 exact Texture2D objects')
    seen=set()
    for row in rows:
        if not isinstance(row,dict)or set(row)!={'file','pathId','rawSha256','logicalPath'}:raise ValueError('Each selection needs file/pathId/rawSha256/logicalPath')
        file,path_id=row['file'],row['pathId']
        if not isinstance(file,str)or not 1<=len(file)<=512 or any(c in file for c in ('/','\\','\x00')):raise ValueError('Expected exact serialized-file name')
        if not isinstance(path_id,str)or not re.fullmatch(r'-?(0|[1-9][0-9]{0,18})',path_id)or not -(1<<63)<=int(path_id)<(1<<63)or str(int(path_id))!=path_id:
            raise ValueError('Expected canonical signed int64 decimal pathId string')
        if not isinstance(row['rawSha256'],str)or not re.fullmatch('[0-9a-f]{64}',row['rawSha256']):raise ValueError('Expected exact raw object SHA-256')
        cache_parts(row['logicalPath'])
        key=(file,path_id)
        if key in seen:raise ValueError('Duplicate selected source object')
        seen.add(key)
    return rows


def cache_index(pool):
    index={}
    for path,row in pool.items():
        parts=cache_parts(path);index.setdefault(parts[4],[]).append((parts[2],path,row))
    return index


def matching_cache(pool,key,explicit=None,index=None):
    """Match a literal token filename; never synthesize bucket aliases or decode keys."""
    if explicit is not None:
        parts=cache_parts(explicit)
        if parts[4]!=key+'.txt':raise ValueError('Selected logical path does not match the exact source token filename')
        return [(parts[2],explicit,pool[explicit])]if explicit in pool else []
    return (cache_index(pool)if index is None else index).get(key+'.txt',[])
