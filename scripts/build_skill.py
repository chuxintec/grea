#!/usr/bin/env python3
"""Build a relocatable documentation-only Skill from immutable release inputs."""
import hashlib
import json
import posixpath
import re
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, quote, urlsplit

LINK = re.compile(r'(\]\()(<[^>]+>|[^\s)]+)(\))')
REPOSITORY = 'https://github.com/chuxintec/grea'


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def render(source, version, revision):
    """source maps committed repository paths to (bytes, Git mode)."""
    metadata = json.loads(source['skill/version.json'][0])
    if metadata['version'] != version or metadata['greaVersion'] != version:
        raise ValueError('Skill, grea and release versions must agree')
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Expected a full source commit')
    files = {}
    for name, (data, mode) in source.items():
        if not name.startswith('skill/'):
            continue
        local = name[len('skill/'):]
        if any(part.startswith('.') for part in PurePosixPath(local).parts):
            continue  # Repository configuration is not installed Skill content.
        if mode != 0o100644 or local.startswith('/') or '..' in PurePosixPath(local).parts:
            raise ValueError('Skill accepts regular documentation files only')
        if not local.endswith(('.md', '.json', '.yaml', '.yml')):
            raise ValueError('Unexpected Skill payload: ' + local)
        if local.endswith('.md'):
            def link(match):
                raw = match[2]; target = raw.strip('<>'); url = urlsplit(target)
                if url.scheme or url.netloc or not url.path:
                    return match[0]
                if url.path.startswith('/') or '\\' in url.path:
                    raise ValueError('Absolute/local-machine Skill link')
                dest = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(url.path)))
                if dest not in source and not any(x.startswith(dest.rstrip('/') + '/') for x in source):
                    raise ValueError('Missing linked source: ' + dest)
                if dest.startswith('skill/'):
                    return match[0]
                # Optional implementation/evidence references become immutable source URLs.
                kind = 'blob' if dest in source else 'tree'
                remote = f'{REPOSITORY}/{kind}/{revision}/' + quote(dest, safe='/')
                if url.fragment: remote += '#' + quote(unquote(url.fragment), safe='-')
                return match[1] + remote + match[3]
            data = LINK.sub(link, data.decode('utf-8')).encode('utf-8')
        files['grea/' + local] = data
    if 'grea/SKILL.md' not in files:
        raise ValueError('Missing Skill entry')
    files['grea/LICENSE.md'] = source['LICENSE'][0]
    manifest = {'schemaVersion': 1, 'name': 'grea', 'version': version,
                'greaVersion': version, 'sourceRevision': revision,
                'requiredOperations': metadata['requiredOperations'],
                'files': {name: {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
                          for name, data in sorted(files.items())},
                'limits': 'Workflow documentation is local; optional implementation/evidence links need network. Tool execution requires a compatible grea installation.'}
    files['grea/skill-manifest.json'] = encoded(manifest)
    validate_local_links(files)
    return files


def validate_local_links(files):
    """No local link may escape the installed Skill, including directory links."""
    for name, data in files.items():
        if not name.endswith('.md'): continue
        for match in LINK.finditer(data.decode('utf-8')):
            url = urlsplit(match[2].strip('<>'))
            if url.scheme or url.netloc or not url.path: continue
            dest = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(url.path)))
            if not dest.startswith('grea/') or (dest not in files and not any(x.startswith(dest.rstrip('/') + '/') for x in files)):
                raise ValueError('Skill link escapes or is missing: ' + dest)


def write_archive(path, files, timestamp):
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, timestamp.timetuple()[:6]); info.create_system = 3
            info.external_attr = 0o100644 << 16; info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)


def verify_archive(path, expected, extract=None):
    with zipfile.ZipFile(path) as z:
        if len(z.namelist()) != len(expected) or set(z.namelist()) != set(expected):
            raise ValueError('Skill archive inventory differs from source')
        for name, data in expected.items():
            info = z.getinfo(name)
            if z.read(info) != data or info.external_attr >> 16 != 0o100644:
                raise ValueError('Skill archive identity mismatch: ' + name)
        # Verification completes before any extraction write.
        if extract is not None:
            extract = Path(extract).absolute()
            if extract.exists() or extract.is_symlink() or any(p.is_symlink() and not p.exists() for p in extract.parents):
                raise ValueError('Skill extraction requires a new non-symlink directory')
            extract = extract.resolve()
            extract.mkdir(parents=True)
            for name, data in expected.items():
                target = extract / name; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data); target.chmod(0o644)


if __name__ == '__main__':
    import argparse
    from datetime import datetime, timezone
    import release
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--extract', type=Path)
    args = parser.parse_args()
    version, _, revision, _ = release.identity(args.tag)
    files = render(release.source_files(), version, revision)
    archive = args.out / ('grea-skill-' + args.tag + '.zip')
    if not args.verify:
        args.out.mkdir(parents=True, exist_ok=False)
        timestamp = datetime.fromtimestamp(int(release.git('show', '-s', '--format=%ct', 'HEAD')), timezone.utc)
        write_archive(archive, files, timestamp)
        (args.out/'SHA256SUMS').write_text(release.sha256(archive)+'  '+archive.name+'\n')
    if (args.out/'SHA256SUMS').read_text() != release.sha256(archive)+'  '+archive.name+'\n':
        raise ValueError('Skill checksum mismatch')
    verify_archive(archive, files, args.extract)
    print(json.dumps({'version': version, 'sourceRevision': revision, 'files': len(files), 'verified': True}))
