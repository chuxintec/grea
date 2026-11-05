"""Explicit local input-set contract; no sibling discovery or network resolution."""
import re
from pathlib import Path
from .io import safe, read, load, sha, inside
from .sources.compiled import fail


def input_set(path):
    path=safe(path);raw=read(path);data=load(raw)
    if data.get('schemaVersion')!=1 or data.get('sourceProfile') not in ('cocos-2.4.15-bundle','cocos-2.4.15-project','cocos-3.8.7-bundle','cocos-3.4.1-bundle','cocos-2.4.11-bundle','cocos-2.1.2-resource','generic-image-resources-v1','egret-custom-resource-plist-v1'):
        fail('INPUT_SET_SCHEMA',str(path),'Expected input-set schema 1 and explicit supported sourceProfile')
    from .sources.containers import MAX_TOTAL,MAX_EXPLICIT_TOTAL
    limits=data.get('limits',{})
    if not isinstance(limits,dict) or set(limits)-{'maxInputBytes'}:
        fail('INPUT_SET_LIMITS',str(path),'Only limits.maxInputBytes is supported')
    max_input_bytes=limits.get('maxInputBytes',MAX_TOTAL)
    if type(max_input_bytes)is not int or not 1<=max_input_bytes<=MAX_EXPLICIT_TOTAL:
        fail('INPUT_SET_LIMITS',str(path),'maxInputBytes must be an integer in 1..8GiB; default 2048 MiB')
    inputs=data.get('inputs')
    if not isinstance(inputs,list) or not 1<=len(inputs)<=16:
        fail('INPUT_SET_SCHEMA',str(path),'Expected 1..16 explicit local inputs')
    known={};seen=set();roots=[]
    game=data.get('game',{})
    if not isinstance(game,dict): fail('INPUT_SET_SCHEMA','game','Expected identity object')
    for field in ('gameId','appId','version','engineVersion'):
        if game.get(field) is not None: known[field]=game[field]
    for entry in inputs:
        name=entry.get('id')
        if not isinstance(name,str) or not re.fullmatch('[A-Za-z0-9_-]{1,64}',name) or name.casefold() in seen:
            fail('INPUT_SET_ID',str(name),'Expected unique simple root ID')
        seen.add(name.casefold());root=safe(path.parent/entry['path'])
        identity=entry.get('identity',{})
        if not isinstance(identity,dict): fail('INPUT_SET_SCHEMA',name,'Expected identity object')
        for field in ('gameId','appId','version','engineVersion'):
            value=identity.get(field)
            if value is not None:
                if not isinstance(value,str) or not value: fail('INPUT_SET_SCHEMA',name,'Identity values must be nonempty strings or null')
                if field in known and known[field]!=value:
                    fail('INPUT_IDENTITY_CONFLICT',name,'Conflicting '+field+' across explicit roots')
                known[field]=value
        config=entry.get('config')
        if config is not None:
            config=inside(root,config)
            if not config.is_file(): fail('INPUT_CONFIG_MISSING',name,'Declared config is unavailable')
        cache=entry.get('cacheList')
        cache_path=inside(root,cache) if cache else None
        cache_kind=entry.get('cacheKind') or ('temp' if cache_path and cache_path.name=='tempFileList.json' else 'cache')
        if cache_path and (not cache_path.is_file() or cache_kind not in ('cache','temp','legacy-flat')):
            fail('INPUT_CACHE_SCHEMA',name,'Expected an existing explicit cache/temp list')
        roots.append(dict(id=name,path=root,config=config,cacheList=cache_path,cacheKind=cache_kind))
    for i,root in enumerate(roots):
        for other in roots[i+1:]:
            a,b=root['path'],other['path']
            if a==b or a.is_relative_to(b) or b.is_relative_to(a):
                fail('INPUT_ROOT_OVERLAP',root['id'],'Explicit roots must not overlap')
    provenance=data.get('provenance');verified_relation=False
    if provenance:
        evidence=safe(path.parent/provenance['sourceManifest'])
        raw_evidence=read(evidence)
        if sha(raw_evidence)!=provenance.get('sha256'): fail('INPUT_PROVENANCE_CHANGED',str(evidence),'Source receipt differs')
        prior=load(raw_evidence)
        for root in roots:
            if safe(prior.get('sourceRoots',{}).get(root['id'],'/nonexistent'))!=root['path']:
                fail('INPUT_PROVENANCE_MISMATCH',root['id'],'Root absent from declared frozen source relation')
        verified_relation=True
    return dict(path=path,sha256=sha(raw),sourceProfile=data['sourceProfile'],inputs=roots,identity=known,maxInputBytes=max_input_bytes,
                identityStatus='declared' if known.get('appId') and known.get('version') else 'identity_unknown',
                frozenRelationVerified=verified_relation)
