"""Read-only path lookup for frozen legacy and typed manifests.

v0.2 writers use ProjectModel slots and explicit host locations. The old recursive
string/JSON/code substitution formatter is intentionally retired.
"""


def translate(path,pairs):
    """Legacy root-path compatibility only; never walk JSON or replace embedded text."""
    if not isinstance(path,str):raise TypeError('Legacy lookup expects one physical path')
    if path in pairs:return pairs[path]
    if path.endswith('.meta')and path[:-5]in pairs:return pairs[path[:-5]]+'.meta'
    for prefix in sorted(pairs,key=len,reverse=True):
        if path.startswith(prefix)and(prefix.endswith('/')or len(path)>len(prefix)and path[len(prefix)]=='/'):
            return pairs[prefix]+path[len(prefix):]
    return path


def lookup(path,manifest):
    pairs=manifest.get('pathMap',{})
    return pairs.get(path,path)if manifest.get('pathMappingMode')=='exact'else translate(path,pairs)
