"""Preserve license material omitted by the stripped CPython install archive."""
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
from plugin_targets import TARGETS

from plugin_bundle import encoded, safe_name, sha256


def check_license_closure(metadata, available):
    paths = set()
    def collect(value):
        if isinstance(value, dict):
            if value.get('license_path'): paths.add(value['license_path'])
            paths.update(value.get('license_paths', []))
            for child in value.values(): collect(child)
        elif isinstance(value, list):
            for child in value: collect(child)
    collect(metadata)
    missing = paths - set(available)
    if not missing: return []
    # This pinned macOS distribution's metadata lists zlib-ng as an alternative,
    # while these four extensions actually link Apple's system libz.
    exception = 'licenses/LICENSE.zlib-ng.txt'
    if metadata.get('target_triple','aarch64-apple-darwin') != 'aarch64-apple-darwin' or missing != {exception}: raise ValueError('Unaccounted runtime licenses: '+str(sorted(missing)))
    refs = []
    for name, variants in metadata['build_info']['extensions'].items():
        for value in variants:
            if exception not in value.get('license_paths', []): continue
            links = [link for link in value.get('links', []) if link.get('name') in ('z', 'zlib-ng')]
            if value.get('variant') != 'default' or links != [{'name':'z','system':True}]:
                raise ValueError('zlib-ng exception no longer represents a system libz link')
            refs.append(name)
    if sorted(refs) != ['_sqlite3','_tkinter','binascii','zlib']:
        raise ValueError('Unexpected zlib-ng metadata reference set')
    return [{'path':exception,'system_library':'z','extensions':sorted(refs),
             'reason':'Upstream metadata lists an alternative license absent from the archive; each referenced macOS extension links system libz, not a bundled zlib-ng.'}]


def install_licenses(archive, runtime, lock):
    if sha256(archive) != lock['licenseArchive']['sha256']:
        raise ValueError('Full Python archive checksum mismatch')
    def read(name):
        safe_name(name)
        value = subprocess.check_output([shutil.which('tar') or 'tar','-xOf',str(archive),name], timeout=60)
        if len(value) > 5 * 1024**2: raise ValueError('Unexpected license metadata size')
        return value
    raw = read('python/PYTHON.json'); metadata = json.loads(raw)
    if (metadata['python_version'], metadata['target_triple']) != (lock['pythonVersion'],TARGETS[lock['target']]['triple']):
        raise ValueError('License archive does not match the runtime')
    listing = subprocess.check_output([shutil.which('tar') or 'tar','-tf',str(archive)], text=True, timeout=60).splitlines()
    names = sorted(name for name in listing if name.startswith('python/licenses/') and not name.endswith('/'))
    if not names or len(names) != len(set(names)): raise ValueError('Missing or duplicate runtime licenses')
    records = {}
    for name in names:
        safe_name(name)
        relative = name.removeprefix('python/')
        value = read(name)
        path = Path(runtime)/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
        records[relative] = {'sha256':hashlib.sha256(value).hexdigest(),'bytes':len(value)}
    exceptions = check_license_closure(metadata, set(records))
    (Path(runtime)/'PYTHON.json').write_bytes(raw)
    report = {'source_archive_sha256':lock['licenseArchive']['sha256'],
              'metadata_sha256':hashlib.sha256(raw).hexdigest(),'files':records,
              'metadata_exceptions':exceptions,'target_triple':metadata['target_triple'],
              'minimum_macos':metadata.get('apple_sdk_deployment_target')}
    (Path(runtime)/'license-manifest.json').write_bytes(encoded(report))
    return report
