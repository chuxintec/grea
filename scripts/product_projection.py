"""One exact runtime product projection, shared by builder and release verifier."""
import posixpath
import re
from urllib.parse import unquote,urlsplit,quote


def project(source, revision):
    def included(name):
        return not (name.startswith(('.github/','scripts/','docs/design/','proposals/','validation/'))
                    or name.startswith('tests/') and not name.startswith('tests/unity/'))
    files={name:value for name,value in source.items() if included(name)}
    for name,(raw,mode) in list(files.items()):
        if not name.endswith('.md'):continue
        def link(match):
            url=urlsplit(match[1].strip('<>'))
            if url.scheme or url.netloc or not url.path:return match[0]
            dest=posixpath.normpath(posixpath.join(posixpath.dirname(name),unquote(url.path)))
            exists=dest in source or any(p.startswith(dest.rstrip('/')+'/') for p in source)
            retained=dest in files or any(p.startswith(dest.rstrip('/')+'/') for p in files)
            if not exists or retained:return match[0]
            return ']('+'https://github.com/chuxintec/grea/'+('blob' if dest in source else 'tree')+'/'+revision+'/'+quote(dest,safe='/')+('#'+url.fragment if url.fragment else '')+')'
        files[name]=(re.sub(r'\]\((<[^>]+>|[^\s)]+)\)',link,raw.decode('utf-8')).encode('utf-8'),mode)
    return files
