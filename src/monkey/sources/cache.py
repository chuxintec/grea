"""Explicit WeChat cache/temp manifests, independently implemented in Python.

Behavior reference is limited to pinned external binary fixture outputs; no original implementation is included.
Only declared wxfile paths are read; remote URLs are identifiers, never requests.
"""
import re
from urllib.parse import urlsplit,unquote
from ..io import safe,inside,read,load,sha,diagnostic
from .containers import relative,MAX_FILE
from ..byte_budgets import enforce
from .compiled import fail


def _read_entry(path):
    enforce('packageFile', path.stat().st_size, MAX_FILE, path, 'ARCHIVE_BUDGET', basis='file size')
    return read(path, max_bytes=MAX_FILE)


def plan(root,manifest,kind):
    root=safe(root);manifest=safe(manifest)
    if kind=='legacy-flat':
        raw=read(manifest);data=load(raw)
        if not isinstance(data,dict)or len(data)>50000:fail('CACHE_SCHEMA',str(manifest),'Expected bounded legacy filename/timestamp map')
        records=[];missing=[]
        for name,stamp in sorted(data.items()):
            if not isinstance(name,str)or not re.fullmatch(r'res-(?:import|raw-assets)-[A-Za-z0-9_.-]{1,240}',name)or type(stamp)is not int:fail('CACHE_SCHEMA',str(name),'Expected exact legacy filename/timestamp')
            disk=inside(root,name);logical='LegacyCache/'+name
            if disk.is_file():records.append(dict(path=logical,disk=disk,sourceKeys=[sha(name.encode())]))
            else:missing.append(dict(sourceKey=sha(name.encode()),path=logical,reason='input_not_provided'))
        return dict(records=records,missing=missing,version='unknown',manifestSha256=sha(raw),manifest=manifest,declaredEntries=len(data),availableMappings=len(records))
    if kind not in ('cache','temp'):fail('CACHE_SCHEMA',str(kind),'Expected cache or temp')
    raw=read(manifest);data=load(raw);files=data.get('files')
    if not isinstance(files,dict) or len(files)>50000:fail('CACHE_SCHEMA',str(manifest),'Expected bounded files object')
    records=[];missing=[];seen={}
    for remote,entry in sorted(files.items()):
        if not isinstance(entry,dict):fail('CACHE_SCHEMA','files','Expected entry object')
        bundle=entry.get('bundle')
        if not isinstance(bundle,str) or not re.fullmatch('[A-Za-z0-9_-]{1,128}',bundle):
            fail('CACHE_BUNDLE','files','Invalid bundle identity')
        parsed=urlsplit(remote)
        if parsed.scheme not in ('http','https') or not parsed.netloc or parsed.username or parsed.password:
            fail('CACHE_REMOTE_IDENTITY','files','Expected HTTP(S) resource identity without credentials')
        parts=unquote(parsed.path).split('/')
        if parts.count(bundle)!=1:fail('CACHE_REMOTE_IDENTITY',bundle,'Bundle must occur once as a complete URL path segment')
        suffix=relative('/'.join(parts[parts.index(bundle)+1:]))
        logical=relative(bundle+'/'+suffix)
        location=entry.get('url' if kind=='cache' else 'path')
        if not isinstance(location,str):fail('CACHE_LOCAL_PATH',bundle,'Missing declared local wxfile path')
        local=urlsplit(location)
        if local.scheme!='wxfile' or local.query or local.fragment:
            fail('CACHE_LOCAL_PATH',bundle,'Only explicit local wxfile identifiers are accepted')
        disk=inside(root,relative(unquote(local.netloc+local.path)))
        key=sha(remote.encode())
        if not disk.is_file():
            missing.append(dict(sourceKey=key,path=logical,reason='input_not_provided'));continue
        info=dict(path=logical,disk=disk,sourceKeys=[key])
        if logical in seen:
            previous=seen[logical]
            if sha(_read_entry(previous['disk']))!=sha(_read_entry(disk)):
                fail('CACHE_MAPPING_CONFLICT',logical,'Different local content claims the same bundle path')
            previous['sourceKeys'].append(key)
        else:
            seen[logical]=info;records.append(info)
    return dict(records=records,missing=missing,version=data.get('version'),manifestSha256=sha(raw),manifest=manifest,
                declaredEntries=len(files),availableMappings=len(records))


def entries(root,manifest,kind):
    mapping=plan(root,manifest,kind)
    yield 'CacheEvidence/'+mapping['manifest'].name,read(mapping['manifest'])
    for record in mapping['records']:
        yield record['path'],_read_entry(record['disk'])
