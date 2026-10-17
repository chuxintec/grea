"""Source identity and deterministic, verified portable plugin archives."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import stat
import subprocess
import tarfile
import time
import zipfile

from audit_public_tree import inspect


def sha256(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()


def safe_name(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name or str(path) != name:
        raise ValueError('Unsafe archive path: ' + name)
    for part in path.parts:
        if (part.endswith((' ','.')) or re.search(r'[<>"|?*\x00-\x1f]',part)
                or part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}):
            raise ValueError('Nonportable archive path: '+name)
    return path


def linked(path):
    return path.is_symlink() or bool(getattr(path.lstat(),'st_file_attributes',0)&0x400)


def read_source(root, worktree=False):
    root = Path(root).resolve()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args])
    revision = git('rev-parse', 'HEAD').decode().strip()
    dirty = bool(git('status', '--porcelain', '--untracked-files=all'))
    if dirty and not worktree:
        raise ValueError('Committed plugin builds require a clean tree; use --worktree for an unpublished preview.')
    files = {}
    if worktree:
        for raw in sorted(set(git('ls-files', '-c', '-o', '--exclude-standard', '-z').split(b'\0')) - {b''}):
            name = raw.decode(); path = root / name
            safe_name(name)
            if path.is_symlink(): raise ValueError('Source symlink: ' + name)
            if not path.exists(): continue  # Staged renames/deletions in the current worktree.
            if not path.is_file(): raise ValueError('Non-file source: ' + name)
            files[name] = (path.read_bytes(), 0o100755 if path.stat().st_mode & 0o111 else 0o100644)
    else:
        for entry in filter(None, git('ls-tree', '-rz', '--full-tree', revision).split(b'\0')):
            info, raw = entry.split(b'\t', 1)
            mode, kind, oid = info.decode().split(); name = raw.decode()
            safe_name(name)
            if kind != 'blob' or mode not in ('100644', '100755'):
                raise ValueError('Non-file source: ' + name)
            files[name] = (git('cat-file', 'blob', oid), int(mode, 8))
    for name, (data, mode) in files.items():
        issues = inspect(name, data, format(mode, 'o'))
        if issues: raise ValueError('Public source audit failed: ' + name + ' ' + str(issues))
    content = {n: {'sha256': hashlib.sha256(d).hexdigest(), 'mode': m} for n, (d, m) in sorted(files.items())}
    return files, {'source_revision': revision, 'source_dirty': dirty,
                   'source_kind': 'worktree-preview' if worktree else 'commit',
                   'source_tree_sha256': hashlib.sha256(encoded(content)).hexdigest(),
                   'source_timestamp': int(git('show', '-s', '--format=%ct', revision))}


def extract_runtime(archive, destination, expected_sha256):
    destination = Path(destination)
    if destination.exists() or destination.is_symlink(): raise FileExistsError(destination)
    if sha256(archive) != expected_sha256: raise ValueError('Python distribution checksum mismatch')
    with tarfile.open(archive, 'r:gz') as tar:
        members = {}; targets = {}
        for item in tar.getmembers():
            name = item.name.rstrip('/')
            path = safe_name(name)
            if path.parts[0] != 'python' or name in members:
                raise ValueError('Unexpected/duplicate Python archive member: ' + name)
            if not (item.isfile() or item.isdir() or item.issym() or item.islnk()):
                raise ValueError('Unsupported Python archive entry')
            if item.issym() or item.islnk():
                target = posixpath.normpath(posixpath.join(posixpath.dirname(name), item.linkname)) if item.issym() else item.linkname
                if PurePosixPath(safe_name(target)).parts[0] != 'python':
                    raise ValueError('Python archive link escapes runtime')
                targets[name] = target
            members[name] = item
        if sum(m.size for m in members.values()) > 2 * 1024**3 or len(members) > 100000:
            raise ValueError('Python archive exceeds limits')
        def resolve(name, seen=()):
            if name in seen or name not in members: raise ValueError('Broken/cyclic runtime link')
            return resolve(targets[name], (*seen, name)) if name in targets else members[name]
        for name in targets:
            if not resolve(name).isfile(): raise ValueError('Runtime links must resolve to regular files')
        # Validate parent types before creating anything, including links used as parents.
        for name in members:
            for parent in PurePosixPath(name).parents:
                if str(parent) in members and not members[str(parent)].isdir():
                    raise ValueError('Runtime parent is not a directory')
        destination.mkdir(parents=True)
        for name, item in sorted(members.items()):
            relative = PurePosixPath(name).parts[1:]
            if not relative: continue
            path = destination.joinpath(*relative)
            if item.isdir(): path.mkdir(parents=True, exist_ok=True); continue
            value = resolve(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(value) as source, path.open('xb') as output:
                shutil.copyfileobj(source, output)
            path.chmod(0o755 if value.mode & 0o111 else 0o644)


def inventory(root, target=None):
    result = {}
    for path in sorted(Path(root).rglob('*')):
        if linked(path): raise ValueError('Installed plugin must contain regular files only')
        if not path.is_file(): continue
        name = path.relative_to(root).as_posix(); safe_name(name)
        if name == 'plugin-manifest.json': continue
        result[name] = {'sha256': sha256(path), 'bytes': path.stat().st_size,
                        'mode': 0o644 if target=='windows-x64' else (0o755 if path.stat().st_mode & 0o111 else 0o644)}
    return result


def write_archive(root, archive, timestamp):
    stamp = time.gmtime(max(315532800, timestamp))[:6]
    declared=json.loads((Path(root)/'plugin-manifest.json').read_text(encoding='utf-8'))['files']
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as zip_file:
        for path in sorted(Path(root).rglob('*')):
            if path.is_symlink(): raise ValueError('Plugin symlink')
            if not path.is_file(): continue
            name = path.relative_to(root).as_posix(); safe_name(name)
            info = zipfile.ZipInfo('grea/' + name, stamp)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | declared.get(name,{'mode':0o644})['mode']) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with path.open('rb') as source, zip_file.open(info, 'w') as output:
                shutil.copyfileobj(source, output)


def verify_archive(archive, extract=None):
    with zipfile.ZipFile(archive) as zip_file:
        names = zip_file.namelist()
        for name in names:
            safe_name(name)
            if not name.startswith('grea/'): raise ValueError('Unexpected plugin root')
        if len(names)>100000 or len(names) != len(set(n.casefold() for n in names)): raise ValueError('Duplicate ZIP entry')
        if sum(x.file_size for x in zip_file.infolist()) > 2 * 1024**3:
            raise ValueError('Plugin archive exceeds limit')
        manifest = json.loads(zip_file.read('grea/plugin-manifest.json'))
        expected = {'grea/' + n for n in manifest['files']} | {'grea/plugin-manifest.json'}
        if set(names) != expected: raise ValueError('Plugin archive inventory mismatch')
        for name in names:
            info = zip_file.getinfo(name)
            mode = info.external_attr >> 16
            if stat.S_IFMT(mode) != stat.S_IFREG: raise ValueError('Non-file ZIP entry')
            if name.endswith('/plugin-manifest.json') and name == 'grea/plugin-manifest.json': continue
            record = manifest['files'][name[5:]]
            with zip_file.open(info) as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if (digest, info.file_size, mode & 0o777) != (record['sha256'], record['bytes'], record['mode']):
                raise ValueError('Plugin content mismatch: ' + name)
        if extract is not None:
            extract = Path(extract).absolute()
            if extract.exists() or extract.is_symlink():
                raise ValueError('Extraction requires a new directory')
            extract = extract.parent.resolve() / extract.name
            extract.mkdir(parents=True)
            for name in names:
                info = zip_file.getinfo(name)
                path = extract / name
                path.parent.mkdir(parents=True, exist_ok=True)
                with zip_file.open(info) as source, path.open('xb') as output:
                    shutil.copyfileobj(source, output)
                path.chmod((info.external_attr >> 16) & 0o777)
    return manifest
