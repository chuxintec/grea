"""Compatibility contract extracted without changing existing tool IDs."""
import json,os
from grea.host.paths import Path
from grea.common import digest,hash_file,write_new,GreaError
from grea.safe_paths import canonical_path,disjoint,relative_name
from grea import runner,artifacts


def read(path,limit=8*1024**2):
    path=canonical_path(path)
    if not path.is_file() or path.stat().st_size>limit:raise ValueError('Missing or oversized JSON')
    return json.loads(path.read_text(encoding='utf-8'),parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))

def pinned(config):
    cfg=read(config)
    if set(cfg)!={'schema_version','version','capabilities_sha256','identity_files'} or (type(cfg['schema_version']) is not int or cfg['schema_version']!=1) or not cfg['identity_files']:raise ValueError('Expected pinned provider config v1')
    for row in cfg['identity_files']:
        if hash_file(row['path'],16*1024**2)['sha256']!=row['sha256']:raise ValueError('Provider implementation identity changed')
    return cfg


def create_lock(root, output):
    """Pin an explicitly installed package tree and configured launcher, without installing."""
    from grea import registry
    root=canonical_path(root)
    out=disjoint(output,root)
    if not root.is_dir() or not (root/'cli.py').is_file() or not (root/'__init__.py').is_file():
        raise ValueError('Identity root must be the installed monkey Python package directory')
    if out.exists() or not out.parent.is_dir():raise ValueError('Use a fresh lock output')
    out.mkdir()
    entry=registry.tool('monkey');command=registry.command(entry);probe=registry.command(entry,probe=True)
    # Bind the same real launcher, not a separate capability impersonator.
    if probe!=command+['capabilities','--json']:raise ValueError('Probe must use the configured monkey command')
    receipt,_,error=runner.execute('monkey',[],out/'probe',probe=True,timeout_seconds=20,max_output_bytes=1024**2,max_inline_bytes=1024**2)
    cap=receipt.get('parsed_stdout')
    if error or not isinstance(cap,dict) or cap.get('schemaVersion')!=1:raise ValueError('Capability probe failed')
    files=package_files(root)
    for arg in command:
        path=Path(arg)
        if path.is_absolute() and path.is_file():files[str(path.resolve())]=hash_file(path.resolve(),128*1024**2)['sha256']
    cfg=dict(schema_version=2,version=cap['version'],capabilities_sha256=digest(cap),identity_root=str(root),
             command=command,probe=probe,package_files=package_files(root),
             identity_files=[dict(path=p,sha256=s) for p,s in sorted(files.items())])
    write_new(out/'monkey-lock.json',cfg)
    return cfg


def package_files(root):
    files={};size=0
    for folder,dirs,names in os.walk(root,followlinks=False):
        dirs[:]=sorted(d for d in dirs if d!='__pycache__')
        if any((Path(folder)/d).is_symlink() for d in dirs):raise ValueError('Linked package directory')
        for name in sorted(names):
            if name.endswith(('.pyc','.pyo')):continue
            p=Path(folder)/name;identity=hash_file(p,128*1024**2);size+=identity['bytes']
            if size>512*1024**2 or len(files)>=20000:raise ValueError('Provider package budget exceeded')
            files[str(p)]=identity['sha256']
    return files


_legacy_pinned=pinned

def pinned(config):
    cfg=read(config)
    if cfg.get('schema_version')==1:return _legacy_pinned(config)
    from grea import registry
    required={'schema_version','version','capabilities_sha256','identity_files','identity_root','command','probe','package_files'}
    if set(cfg)!=required or cfg['schema_version']!=2:raise ValueError('Expected provider lock v1 or v2')
    entry=registry.tool('monkey')
    if registry.command(entry)!=cfg['command'] or registry.command(entry,probe=True)!=cfg['probe']:raise ValueError('Provider launcher changed')
    if package_files(canonical_path(cfg['identity_root']))!=cfg['package_files']:raise ValueError('Provider package changed')
    for row in cfg['identity_files']:
        if hash_file(row['path'],128*1024**2)['sha256']!=row['sha256']:raise ValueError('Provider implementation changed')
    return cfg
