"""One exact runtime product projection, shared by builder and release verifier."""
import posixpath
import re
from urllib.parse import unquote,urlsplit,quote


# Internal implementations and historical source material belong to the local
# maintenance repository. Both projection and public-tree audit use this rule.
INTERNAL_PREFIXES = (
    'src/grea/recovery/', 'src/grea/development/', 'src/grea/features/',
    'tests/recovery/', 'tests/development/', 'docs/archive/', 'docs/history/',
    'examples/development/', 'schemas/development/', 'schemas/recovery/',
    'scripts/recovery/', 'scripts/development/', 'modules/monkey/',
)


def internal_source(name):
    return any(name == prefix.rstrip('/') or name.startswith(prefix) for prefix in INTERNAL_PREFIXES)


def included(name):
    if name == 'scripts/sync_skill.py':
        return True
    return not (internal_source(name) or name.endswith('.gitignore') or
                name.startswith(('.github/', 'scripts/', 'proposals/', 'validation/')) or
                name.startswith('tests/') and not name.startswith('tests/unity/'))


def project(source, revision):
    files={name:value for name,value in source.items() if included(name) or name=='scripts/sync_skill.py'}
    for name,(raw,mode) in list(files.items()):
        if not name.endswith('.md'):continue
        def link(match):
            url=urlsplit(match[1].strip('<>'))
            if url.scheme or url.netloc or not url.path:return match[0]
            dest=posixpath.normpath(posixpath.join(posixpath.dirname(name),unquote(url.path)))
            if internal_source(dest):
                raise ValueError(f'Public document links to internal source: {name} -> {dest}')
            exists=dest in source or any(p.startswith(dest.rstrip('/')+'/') for p in source)
            retained=dest in files or any(p.startswith(dest.rstrip('/')+'/') for p in files)
            if not exists or retained:return match[0]
            return ']('+'https://github.com/chuxintec/grea/'+('blob' if dest in source else 'tree')+'/'+revision+'/'+quote(dest,safe='/')+('#'+url.fragment if url.fragment else '')+')'
        files[name]=(re.sub(r'\]\((<[^>]+>|[^\s)]+)\)',link,raw.decode('utf-8')).encode('utf-8'),mode)
    return files
