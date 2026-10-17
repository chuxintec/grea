"""Verify portable assets against the exact release source and native acceptance."""
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile

from build_plugin import ARCHIVE, write_product
from plugin_targets import TARGETS, runtime_lock, archive_name, report_name
from plugin_bundle import encoded, inventory, sha256, verify_archive

REPORT = 'plugin-acceptance-macos-arm64.json'
ISOLATION = {'moved_unicode_space_path', 'independent_home', 'minimal_path', 'source_read_denied',
             'network_denied', 'install_write_denied', 'installation_unchanged'}


def validate(archive, report, source, version, revision):
    manifest = verify_archive(archive)
    target=manifest.get('target')
    if target not in TARGETS:raise ValueError('Unknown native target')
    artifact=archive_name(target);report_file=report_name(target)
    content = {n: {'sha256':hashlib.sha256(d).hexdigest(), 'mode':m} for n,(d,m) in sorted(source.items())}
    source_digest = hashlib.sha256(encoded(content)).hexdigest()
    if (manifest.get('kind'), manifest.get('version'), manifest.get('target'), manifest.get('source_revision'),
        manifest.get('source_kind'), manifest.get('source_dirty'), manifest.get('source_tree_sha256')) != (
        'complete-plugin', version, target, revision, 'commit', False, source_digest):
        raise ValueError('Portable plugin is not built from this committed release')
    with zipfile.ZipFile(archive) as payload:
        runtime = json.loads(payload.read('grea/runtime-manifest.json'))
        lock = runtime_lock(source,target)
        requirements = payload.read('grea/runtime-requirements.txt')
        if (runtime != manifest.get('runtime') or runtime.get('python') != lock
                or runtime.get('uvLockSha256') != hashlib.sha256(source['uv.lock'][0]).hexdigest()
                or runtime.get('requirementsSha256') != hashlib.sha256(requirements).hexdigest()):
            raise ValueError('Runtime provenance and locked source are inconsistent')
        if 'licenseArchive' in lock:
            licenses = json.loads(payload.read('grea/runtime/license-manifest.json'))
            if (runtime.get('licenses') != licenses
                    or licenses['source_archive_sha256'] != lock['licenseArchive']['sha256']
                    or licenses['metadata_sha256'] != hashlib.sha256(payload.read('grea/runtime/PYTHON.json')).hexdigest()):
                raise ValueError('Runtime license provenance is inconsistent')
            for name, record in licenses['files'].items():
                data = payload.read('grea/runtime/'+name)
                if record != {'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}:
                    raise ValueError('Runtime license bytes differ')
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp)/'grea'
        write_product(source, tree, target, revision)
        expected = inventory(tree,target)
    actual = manifest['files']
    if any(actual.get(name) != record for name,record in expected.items()):
        raise ValueError('Portable product bytes differ from the release source')
    if any(name not in expected and not name.startswith('runtime/') and name not in
           ('runtime-requirements.txt','runtime-manifest.json') for name in actual):
        raise ValueError('Unexpected portable product payload')
    acceptance = json.loads(Path(report).read_text(encoding='utf-8'))
    if (acceptance.get('status'), acceptance.get('target'), acceptance.get('archive_sha256'),
        acceptance.get('source_tree_sha256')) != ('pass',target,sha256(archive),source_digest):
        raise ValueError('Native acceptance does not match the plugin artifact')
    if not all(acceptance.get('isolation',{}).get(key) is True for key in ISOLATION):
        raise ValueError('Native acceptance isolation is incomplete')
    if not all(acceptance.get('clients',{}).get(client,{}).get('status') == 'pass' for client in ('codex','claude')):
        raise ValueError('Both MCP launch configurations must pass')
    return ({'name':artifact,'kind':'plugin','version':version,'target':target,
             'bytes':Path(archive).stat().st_size,'sha256':sha256(archive),'files':len(actual),'root_directory':'grea'},
            {'name':report_file,'bytes':Path(report).stat().st_size,'sha256':sha256(report)})


def validate_client(report, archive, target, version, name=None):
    value=json.loads(Path(report).read_text(encoding='utf-8'))
    manifest=verify_archive(archive)
    if (value.get('status'),value.get('archive_sha256'),value.get('source_tree_sha256'),value.get('version'),value.get('model_requests_sent')) != ('pass',sha256(archive),manifest['source_tree_sha256'],version,0):
        raise ValueError('Native client acceptance identity mismatch')
    client=value.get('clients',{}).get('codex',{})
    required=('version','entrypoint','install','registration','initialize','skills','tools','installed_session')
    if client.get('status')!='pass' or any(client.get('layers',{}).get(k,{}).get('status')!='pass' for k in required):
        raise ValueError('Native Codex installation/discovery incomplete')
    if client['layers']['skills'].get('count')!=8 or client['layers']['tools'].get('count')!=21:
        raise ValueError('Native Codex catalog incomplete')
    if manifest['target']!=target:raise ValueError('Native client target mismatch')
    return {'name':name or Path(report).name,'bytes':Path(report).stat().st_size,'sha256':sha256(report)}
