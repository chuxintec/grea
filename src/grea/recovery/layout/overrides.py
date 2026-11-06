"""Game layout.json (PROJECT-SPEC 7): changes paths and names only, never identities, content, numbers or dynamic keys."""
import re
from ..io import read,load,sha
from ..sources.compiled import fail

KEYS={'schemaVersion','rootNamespace','defaultLocale','bundles','stripSegments','modules','renames','code'}
LAYERS={'Bootstrap','Domain','Gameplay','Presentation','Services'}
_NAMESPACE=re.compile(r'[A-Z][A-Za-z0-9]*(\.[A-Z][A-Za-z0-9]*)*')
_LOCALE=re.compile(r'[a-z]{2,3}(-[A-Za-z0-9]{2,8})*')
_SEGMENT=re.compile(r'[^/\\:\x00-\x1f*?"<>|]{1,64}')


def _segments(value,location,allow_glob=False,allow_capture=False):
    if not isinstance(value,str) or not value or value.startswith('/') or '\\' in value:fail('LAYOUT_OVERRIDES_PATH',location,'Expected relative slash path')
    for part in value.split('/'):
        if part in ('','.','..'):fail('LAYOUT_OVERRIDES_PATH',location,'Unsafe path segment')
        check=part
        if allow_glob:check=check.replace('*','x').replace('?','x')
        if allow_capture:check=re.sub(r'\{[1-9]\}','x',check)
        if not _SEGMENT.fullmatch(check):fail('LAYOUT_OVERRIDES_PATH',location,'Unsafe path segment: '+part)


def validate(data,location='layout.json'):
    if not isinstance(data,dict) or data.get('schemaVersion')!=1:fail('LAYOUT_OVERRIDES_SCHEMA',location,'Expected layout.json schemaVersion 1')
    if set(data)-KEYS:fail('LAYOUT_OVERRIDES_SCHEMA',location,'Unknown fields: '+','.join(sorted(set(data)-KEYS)))
    if 'rootNamespace' in data and not (isinstance(data['rootNamespace'],str) and _NAMESPACE.fullmatch(data['rootNamespace'])):
        fail('LAYOUT_OVERRIDES_NAMESPACE',location,'rootNamespace must be a PascalCase C# namespace')
    if 'defaultLocale' in data and not (isinstance(data['defaultLocale'],str) and _LOCALE.fullmatch(data['defaultLocale'].lower())):
        fail('LAYOUT_OVERRIDES_LOCALE',location,'defaultLocale must be a BCP 47 tag')
    for name,spec in (data.get('bundles') or {}).items():
        if not isinstance(spec,dict) or spec.get('role') not in ('packaging','minigame','locale') or set(spec)-{'role','locale'}:
            fail('LAYOUT_OVERRIDES_BUNDLE',location+'#bundles/'+str(name),'Bundle role must be packaging, minigame or locale')
        if 'locale' in spec and not (isinstance(spec['locale'],str) and _LOCALE.fullmatch(spec['locale'].lower())):
            fail('LAYOUT_OVERRIDES_LOCALE',location+'#bundles/'+str(name),'Locale must be a BCP 47 tag')
    strip=data.get('stripSegments',[])
    if not isinstance(strip,list) or any(not isinstance(s,str) or '/' in s or not s for s in strip):
        fail('LAYOUT_OVERRIDES_STRIP',location,'stripSegments must be single folder names')
    rules=data.get('modules',[])
    if not isinstance(rules,list):fail('LAYOUT_OVERRIDES_MODULES',location,'modules must be a list')
    for i,rule in enumerate(rules):
        where=location+'#modules/'+str(i)
        if not isinstance(rule,dict) or set(rule)!={'match','module'}:fail('LAYOUT_OVERRIDES_MODULES',where,'Each rule needs exactly match and module')
        _segments(rule['match'],where,allow_glob=True);_segments(rule['module'],where,allow_capture=True)
        captures=rule['match'].count('*')-2*rule['match'].count('**')
        if any(int(n)>captures for n in re.findall(r'\{([1-9])\}',rule['module'])):fail('LAYOUT_OVERRIDES_MODULES',where,'Module uses a capture the match does not define')
    for sid,stem in (data.get('renames') or {}).items():
        if not isinstance(stem,str) or not _SEGMENT.fullmatch(stem) or '.' in stem:fail('LAYOUT_OVERRIDES_RENAME',location+'#renames/'+str(sid),'Rename must be one file stem without extension')
    for name,spec in (data.get('code') or {}).items():
        if not isinstance(spec,dict) or spec.get('layer') not in LAYERS or set(spec)-{'layer','module'}:
            fail('LAYOUT_OVERRIDES_CODE',location+'#code/'+str(name),'Code override needs a five-layer name and optional module')
        if 'module' in spec:_segments(spec['module'],location+'#code/'+str(name))
    return data


def load_overrides(path):
    """(overrides, sha256) for an explicit layout.json; ({}, None) when absent."""
    if path is None:return {},None
    raw=read(path,max_bytes=4*1024*1024)
    return validate(load(raw),str(path)),sha(raw)
