"""Explicit binary provider identities, independent of historical Python package locks.

This module verifies artifacts only. Probes use the existing bounded runner and real
provider command; a manifest is never executable configuration or source fallback.
"""
import json
import os
import platform
import re
import struct
from pathlib import Path, PurePosixPath
from grea.common import digest, hash_file

CONTRACT = 'grea-binary-provider/1'
APPROVED_SOURCES = {
    ('monkey', '0.7.0'): '86d47f35744a5af91614c417b00c8eaa2345baad',
    ('beaver', '0.6.0'): '1074816d0e4c22940dea415754e587a6e8d29c3d',
}
APPROVED_ADAPTATIONS = {}  # (provider, version) -> {actual reviewed commit: stable base commit}
MAX_FILE = 256 * 1024**2
MAX_TOTAL = 1024**3


def relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError('Expected a relative binary resource path')
    p = PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or p.as_posix() != value or value == '.':
        raise ValueError('Unsafe binary resource path')
    return value


def _hash(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def capability_identity(provider, value):
    """Only the explicitly named stable projection; preserve raw receipts separately."""
    if provider == 'monkey':
        return value
    if (not isinstance(value, dict) or value.get('contract') != 'beaver-result/1'
            or value.get('status') != 'ok' or not isinstance(value.get('producer'),dict)
            or value['producer'].get('name') != 'beaver' or not isinstance(value.get('data'),dict)
            or value['data'].get('contract') != 'beaver-capabilities/1'):
        raise ValueError('Unsupported binary beaver capability envelope')
    return {key: value[key] for key in ('contract', 'status', 'producer', 'data')}


def runtime_identity(metadata):
    """Bind real compiled files without the capabilities hash/self-reference cycle."""
    value = {key: metadata[key] for key in ('provider', 'version', 'sourceCommit', 'target', 'entrypoint')}
    value['contract'] = 'grea-binary-runtime/1'
    value['files'] = sorted(({key: row[key] for key in ('path', 'sha256', 'bytes')} for row in metadata['files']), key=lambda row: row['path'])
    return digest(value)


def validate(manifest, expected_sha256, provider, *, command=None, capabilities=None):
    """Validate an explicitly hash-bound Mac standalone tree, without launching it."""
    if not _hash(expected_sha256):
        raise ValueError('An explicit lowercase binary manifest SHA256 is required')
    identity = hash_file(manifest, 8 * 1024**2)
    if identity['sha256'] != expected_sha256:
        raise ValueError('Binary provider manifest drift')
    path = Path(identity['path']); root = path.parent
    data = json.loads(path.read_text(encoding='utf-8'), parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite manifest')))
    required = {'schemaVersion', 'contract', 'provider', 'version', 'sourceCommit', 'target',
                'entrypoint', 'capabilitiesSha256', 'capabilitiesProjection', 'files', 'sourceBoundary'}
    if not isinstance(data, dict) or not required <= data.keys() or type(data['schemaVersion']) is not int or data['schemaVersion'] != 1 or data['contract'] != CONTRACT or data['provider'] != provider:
        raise ValueError('Unsupported binary provider manifest')
    if not isinstance(data['version'],str) or not isinstance(data['sourceCommit'],str) or not re.fullmatch('[0-9a-f]{40}',data['sourceCommit']):
        raise ValueError('Binary source/version identity is malformed')
    base = APPROVED_SOURCES.get((provider, data['version']))
    adapted = APPROVED_ADAPTATIONS.get((provider, data['version']), {}).get(data['sourceCommit'])
    if base is None or (data['sourceCommit'] != base and (adapted != base or data.get('baseSourceCommit') != base)):
        raise ValueError('Binary source/version is outside the approved stable input')
    projection = 'monkey-capabilities/1' if provider == 'monkey' else 'beaver-capabilities-stable/1'
    if data['capabilitiesProjection'] != projection:
        raise ValueError('Unsupported explicit binary capability projection')
    if data['target'] != {'system': 'Darwin', 'architecture': 'arm64'}:
        raise ValueError('Only the Mac ARM64 binary stage is supported')
    if platform.system() != 'Darwin' or platform.machine().lower() not in ('arm64', 'aarch64'):
        raise ValueError('Binary provider target differs from the actual host')
    if not _hash(data['capabilitiesSha256']) or not isinstance(data['sourceBoundary'], dict):
        raise ValueError('Binary capabilities/source boundary is incomplete')
    entry = root/relative(data['entrypoint'])
    if command is not None and command != [str(entry)]:
        raise ValueError('Configured command must be the actual binary entrypoint')
    rows = data['files']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 20000:
        raise ValueError('Binary resource inventory is empty or exceeds its budget')
    files = {}; total = 0
    for row in rows:
        if not isinstance(row, dict) or not {'path', 'sha256', 'bytes'} <= row.keys():
            raise ValueError('Invalid binary resource identity')
        name = relative(row['path'])
        if name == path.name or name in files or not _hash(row['sha256']) or type(row['bytes']) is not int or not 0 <= row['bytes'] <= MAX_FILE:
            raise ValueError('Invalid or duplicate binary resource identity')
        # No Python implementation or compiler source fallback in the new mode.
        if Path(name).suffix.lower() in {'.py', '.pyc', '.pyo', '.whl', '.c', '.cpp', '.cxx', '.map'}:
            raise ValueError('Source/bytecode/compiler fallback is forbidden in a binary provider')
        if any(p.is_symlink() for p in (root/name).parents if p != root and p.is_relative_to(root)):
            raise ValueError('Linked binary resource directory is forbidden')
        actual = hash_file(root/name, MAX_FILE)
        if actual['sha256'] != row['sha256'] or actual['bytes'] != row['bytes']:
            raise ValueError('Binary provider resource drift: ' + name)
        total += actual['bytes']
        if total > MAX_TOTAL:
            raise ValueError('Binary provider aggregate budget exceeded')
        with (root/name).open('rb') as stream:
            magic = stream.read(8)
        if (magic.startswith((b'PK\x03\x04', b'PK\x05\x06', b'\x1f\x8b', b'7z\xbc\xaf', b'Rar!', b'BZh', b'\xfd7zXZ'))
                or Path(name).suffix.lower() in {'.zip', '.tar', '.gz', '.xz', '.7z', '.bz2'}):
            raise ValueError('Nested archive/fallback requires a separately reviewed resource contract')
        files[name] = actual
    actual_names = set()
    for folder, dirs, names in os.walk(root, followlinks=False):
        if any((Path(folder)/name).is_symlink() for name in dirs + names):
            raise ValueError('Linked binary resource is forbidden')
        actual_names.update((Path(folder)/name).relative_to(root).as_posix() for name in names)
        if len(actual_names) > 20001:
            raise ValueError('Unlisted binary resources exceed inventory budget')
    if actual_names != set(files) | {path.name}:
        raise ValueError('Binary provider inventory is incomplete or contains unlisted files')
    if data['entrypoint'] not in files or not os.access(entry, os.X_OK):
        raise ValueError('Binary entrypoint is missing or not executable')
    with entry.open('rb') as stream:
        header = stream.read(8)
    if len(header) != 8 or header[:4] != b'\xcf\xfa\xed\xfe' or struct.unpack('<I', header[4:])[0] != 0x0100000c:
        raise ValueError('Expected an actual ARM64 Mach-O entrypoint, not a launcher or archive')
    if capabilities is not None:
        if digest(capability_identity(provider, capabilities)) != data['capabilitiesSha256']:
            raise ValueError('Actual binary capabilities differ from its manifest')
        if provider == 'beaver' and capabilities['producer'].get('implementationSha256') != runtime_identity(data):
            raise ValueError('Binary producer does not bind the actual runtime inventory')
    return dict(manifest=identity, root=str(root), command=[str(entry)], metadata=data,
                runtime_files={v['path']: v['sha256'] for v in files.values()})


def check_lock(cfg, provider, capabilities=None):
    """Recheck every real runtime file and the explicitly pinned manifest."""
    if cfg.get('identity_mode') != 'binary':
        raise ValueError('Expected an explicit binary identity lock')
    ref = cfg['binary_manifest']
    value = validate(ref['path'], ref['sha256'], provider, command=cfg['command'], capabilities=capabilities)
    if (value['manifest'] != ref or value['root'] != cfg['identity_root']
            or value['metadata']['version'] != cfg['version'] or value['runtime_files'] != cfg['runtime_files']):
        raise ValueError('Binary provider identity differs from lock')
    return value


def documents():
    resource = dict(type='object', required=['path', 'sha256', 'bytes'], properties={
        'path': dict(type='string', minLength=1), 'sha256': dict(type='string', pattern='^[0-9a-f]{64}$'),
        'bytes': dict(type='integer', minimum=0, maximum=MAX_FILE)})
    return {'binary-provider.schema.json': {
        '$schema': 'https://json-schema.org/draft/2020-12/schema', 'type': 'object',
        'title': 'Explicit binary provider identity; runtime host/path/inventory checks also required',
        'required': ['schemaVersion', 'contract', 'provider', 'version', 'sourceCommit', 'target',
                     'entrypoint', 'capabilitiesSha256', 'capabilitiesProjection', 'files', 'sourceBoundary'],
        'properties': {
            'schemaVersion': {'const': 1}, 'contract': {'const': CONTRACT},
            'provider': {'enum': ['monkey', 'beaver']}, 'version': {'type': 'string'},
            'sourceCommit': {'type': 'string', 'pattern': '^[0-9a-f]{40}$'},
            'target': {'const': {'system': 'Darwin', 'architecture': 'arm64'}},
            'entrypoint': {'type': 'string', 'minLength': 1},
            'capabilitiesSha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'},
            'capabilitiesProjection': {'enum': ['monkey-capabilities/1','beaver-capabilities-stable/1']},
            'files': {'type': 'array', 'minItems': 1, 'maxItems': 20000, 'items': resource},
            'sourceBoundary': {'type': 'object', 'description': 'Evidence for separate helper/template and embedded source audit; declaration alone is not approval.'}},
        'allOf': [
            {'if': {'properties': {'provider': {'const': name}}},
             'then': {'properties': {'version': {'const': version}, 'sourceCommit': {'enum': [commit, *APPROVED_ADAPTATIONS.get((name, version), {})]}}}}
            for (name, version), commit in APPROVED_SOURCES.items()]}}


def install_archive(provider, archive, expected_archive, expected_manifest, state, output):
    """Explicit local standalone install; no downloads, Python install or binding changes."""
    import shutil
    import stat
    import uuid
    import zipfile
    from grea.safe_paths import disjoint
    from grea.common import write_new
    if provider not in ('monkey', 'beaver') or not _hash(expected_archive) or not _hash(expected_manifest):
        raise ValueError('Expected provider and explicit archive/manifest SHA256')
    archive_identity = hash_file(archive, MAX_TOTAL)
    if archive_identity['sha256'] != expected_archive:
        raise ValueError('Binary archive differs from expected SHA256')
    state = Path(state).expanduser().resolve()
    out = disjoint(output, state, archive)
    if out.exists() or not out.parent.is_dir():
        raise ValueError('Use a fresh binary install receipt directory')
    state.mkdir(parents=True, exist_ok=True)
    staging = state/('.binary-staging-' + uuid.uuid4().hex)
    staging.mkdir()
    try:
        with zipfile.ZipFile(archive) as z:
            infos = z.infolist()
            manifests = [i for i in infos if PurePosixPath(i.filename).name == 'binary-provider.json' and not i.is_dir()]
            if len(manifests) != 1 or len(infos) > 40002:
                raise ValueError('Expected one binary manifest and bounded archive inventory')
            prefix = str(PurePosixPath(manifests[0].filename).parent)
            prefix = '' if prefix == '.' else relative(prefix) + '/'
            seen = set(); total = 0
            for info in infos:
                name = info.filename.rstrip('/')
                if name == prefix.rstrip('/') and info.is_dir():
                    continue
                if not info.filename.startswith(prefix):
                    raise ValueError('Binary archive member is outside its manifest root')
                name = relative(name[len(prefix):])
                if name.casefold() in seen:
                    raise ValueError('Duplicate binary archive path')
                seen.add(name.casefold())
                mode = info.external_attr >> 16
                if info.flag_bits & 1 or stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise ValueError('Encrypted/linked/special binary archive member')
                if info.is_dir():
                    (staging/name).mkdir(parents=True, exist_ok=True)
                    continue
                if not 0 <= info.file_size <= MAX_FILE:
                    raise ValueError('Binary archive member exceeds size budget')
                total += info.file_size
                if total > MAX_TOTAL:
                    raise ValueError('Binary archive exceeds aggregate budget')
                target = staging/name
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as source, target.open('xb') as dest:
                    copied = 0
                    while True:
                        block = source.read(1024 * 1024)
                        if not block: break
                        copied += len(block)
                        if copied > info.file_size:
                            raise ValueError('Binary archive member exceeded declared size')
                        dest.write(block)
                if copied != info.file_size:
                    raise ValueError('Binary archive member is truncated')
                target.chmod(0o755 if mode & 0o111 else 0o644)
        value = validate(staging/'binary-provider.json', expected_manifest, provider)
        target = state/provider/'binaries'/(value['metadata']['version'] + '-' + expected_archive[:12])
        target.parent.mkdir(parents=True, exist_ok=True)
        reused = target.exists()
        if reused:
            validate(target/'binary-provider.json', expected_manifest, provider)
        else:
            os.rename(staging, target)
        installed = validate(target/'binary-provider.json', expected_manifest, provider)
        result = dict(status='ok', installed=not reused, reused=reused, identity_mode='binary',
                      provider=provider, version=value['metadata']['version'], source_commit=value['metadata']['sourceCommit'],
                      archive=archive_identity, install_root=str(target), launcher=installed['command'][0],
                      binary_manifest=installed['manifest'], binding='not_changed', probe='not_run', native='not_run',
                      next_action='Bind and pin the real binary command explicitly; install integrity is not readiness or representative workflow acceptance.')
        out.mkdir()
        write_new(out/'result.json', result)
        return result
    finally:
        shutil.rmtree(staging, ignore_errors=True)
