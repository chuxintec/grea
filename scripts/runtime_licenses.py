"""Preserve license material omitted by the stripped CPython install archive."""
import hashlib
import json
from pathlib import Path
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
    # One bounded streaming pass. Re-spawning tar for every license repeatedly
    # decompresses the full Windows archive and makes builds needlessly slow.
    import tarfile
    import zstandard
    values={};total=0;count=0;expanded=0
    with Path(archive).open('rb') as source, zstandard.ZstdDecompressor().stream_reader(source) as decoded:
        with tarfile.open(fileobj=decoded,mode='r|') as tar:
            for item in tar:
                count+=1;expanded+=max(0,item.size)
                if expanded>2*1024**3:raise ValueError("Expanded license archive budget exceeded")
                if count>100000:raise ValueError('License archive entry budget exceeded')
                if item.name!='python/PYTHON.json' and not item.name.startswith('python/licenses/'):continue
                if item.isdir():continue
                safe_name(item.name)
                if not item.isfile() or item.name in values or item.size>5*1024**2:
                    raise ValueError('Invalid license entry')
                total+=item.size
                if total>20*1024**2:raise ValueError('License archive text budget exceeded')
                value=tar.extractfile(item).read(item.size+1)
                if len(value)!=item.size:raise ValueError('Truncated license entry')
                values[item.name]=value
    raw=values['python/PYTHON.json'];metadata=json.loads(raw)
    if (metadata['python_version'],metadata['target_triple'])!=(lock['pythonVersion'],TARGETS[lock['target']]['triple']):
        raise ValueError('License archive does not match the runtime')
    names=sorted(name for name in values if name.startswith('python/licenses/'))
    if not names:raise ValueError('Missing runtime licenses')
    records={}
    for name in names:
        relative=name.removeprefix('python/');value=values[name]
        path=Path(runtime)/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value)
        records[relative]={'sha256':hashlib.sha256(value).hexdigest(),'bytes':len(value)}
    exceptions = check_license_closure(metadata, set(records))
    (Path(runtime)/'PYTHON.json').write_bytes(raw)
    report = {'source_archive_sha256':lock['licenseArchive']['sha256'],
              'metadata_sha256':hashlib.sha256(raw).hexdigest(),'files':records,
              'metadata_exceptions':exceptions,'target_triple':metadata['target_triple'],
              'minimum_macos':metadata.get('apple_sdk_deployment_target')}
    (Path(runtime)/'license-manifest.json').write_bytes(encoded(report))
    return report
