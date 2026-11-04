"""Prepare recovery requests and freeze exact fixed native-saved selections.

Recovery and native execution are not exposed. Source graph, payload closure
and type semantics remain provider-owned.
"""
import re
from grea.common import hash_file
from grea.safe_paths import canonical_path
from .identity import read

CONTRACT = 'monkey-unity-prefab-recovery-request/1'
COMMAND = 'recover-unity-prefabs'


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('Expected lowercase SHA256')
    return value


def _pin(row):
    if not isinstance(row, dict) or not {'path', 'sha256'} <= row.keys() or set(row) - {'path', 'sha256', 'bytes'}:
        raise ValueError('Expected explicit input path/SHA pin')
    canonical_path(row['path'])
    _sha(row['sha256'])
    if 'bytes' in row and (type(row['bytes']) is not int or row['bytes'] < 0):
        raise ValueError('Invalid input byte count')


def prepare(request_path, expected_request):
    """Return named argv after request identity/shape checks; never invoke it.

    Only the request file is read. Pins of its potentially large dependencies
    are syntax-checked, not claimed as verified source/provider identities.
    """
    _sha(expected_request)
    path = canonical_path(request_path)
    identity = hash_file(path, 8 * 1024**2)
    if identity['sha256'] != expected_request:
        raise ValueError('Unity Prefab request identity differs')
    q = read(path)
    required = {'schemaVersion', 'contract', 'targetUnityVersion', 'roots', 'inputIndex', 'providerExport'}
    optional = {'selectionEvidence', 'sourceMetadata', 'typeEvidence', 'allowDisabledUnavailableCarriers', 'sourceMethodsExecuted'}
    if not isinstance(q, dict) or not required <= q.keys() or set(q) - required - optional:
        raise ValueError('Unsupported Unity Prefab request fields')
    if type(q['schemaVersion']) is not int or q['schemaVersion'] != 1 or q['contract'] != CONTRACT or q['targetUnityVersion'] != '6000.6.2f1':
        raise ValueError('Expected fixed Unity Prefab request contract and target')
    roots = q['roots']
    if not isinstance(roots, list) or not 1 <= len(roots) <= 256:
        raise ValueError('Explicit bounded source roots required')
    seen = set()
    for root in roots:
        if not isinstance(root, dict) or set(root) != {'sourceSha256', 'file', 'pathId'}:
            raise ValueError('Expected exact source root identity')
        _sha(root['sourceSha256'])
        if not isinstance(root['file'], str) or not re.fullmatch('0|[1-9][0-9]*', root['file']):
            raise ValueError('Expected serialized file index')
        value = root['pathId']
        if not isinstance(value, str) or not re.fullmatch('-?[1-9][0-9]*', value) or not -(2**63) <= int(value) < 2**63:
            raise ValueError('Expected nonzero signed int64 pathId string')
        key = (root['sourceSha256'], root['file'], value)
        if key in seen:
            raise ValueError('Duplicate source root')
        seen.add(key)
    for name in ('inputIndex', 'selectionEvidence', 'sourceMetadata'):
        if name in q:
            _pin(q[name])
    provider = q['providerExport']
    if not isinstance(provider, dict) or set(provider) != {'root', 'inventory', 'receipt', 'binding', 'prepared', 'prepareJob'}:
        raise ValueError('Expected fixed provider export lineage')
    canonical_path(provider['root'])
    for name in ('inventory', 'receipt', 'binding', 'prepared', 'prepareJob'):
        _pin(provider[name])
    types = q.get('typeEvidence', [])
    if not isinstance(types, list) or len(types) > 256:
        raise ValueError('Bounded type evidence required')
    for row in types:
        if not isinstance(row, dict) or set(row) != {'assembly', 'dummyDll', 'declarations'} or not isinstance(row['assembly'], str) or not re.fullmatch('[A-Za-z0-9_.-]+[.]dll', row['assembly']):
            raise ValueError('Expected assembly-qualified type evidence')
        _pin(row['dummyDll'])
        declarations = row['declarations']
        if not isinstance(declarations, list) or not 1 <= len(declarations) <= 1000:
            raise ValueError('Bounded declarations required')
        for declaration in declarations:
            _pin(declaration)
    if 'allowDisabledUnavailableCarriers' in q and type(q['allowDisabledUnavailableCarriers']) is not bool:
        raise ValueError('Expected explicit disabled-carrier boolean')
    if 'sourceMethodsExecuted' in q and q['sourceMethodsExecuted'] is not False:
        raise ValueError('Source methods must not be executed')
    if hash_file(path, 8 * 1024**2) != identity:
        raise ValueError('Unity Prefab request changed during preparation')
    return {'command': [COMMAND, '--request', str(path), '--expected-request', expected_request],
            'request': identity, 'source_root_count': len(roots), 'executed': False,
            'public_dispatch': 'not_adapted', 'dependency_identity': 'not_verified',
            'native': 'not_run', 'business': 'not_run'}


def native_inputs(native_output, expected_execution):
    """Hash only receipt-owned saved inputs, never the Editor Library tree."""
    from grea.safe_paths import relative_name, unique_paths
    _sha(expected_execution)
    root = canonical_path(native_output)
    execution = hash_file(root/'execution-result.json', 128*1024**2)
    if execution['sha256'] != expected_execution:
        raise ValueError('Native execution identity differs')
    receipt = read(execution['path'], 128*1024**2)
    cold = receipt.get('independentReopen', {})
    if (receipt.get('status') not in ('native-partial', 'native-verified-subset')
            or receipt.get('processExited') is not True
            or receipt.get('sourceCodeExecuted') is not False
            or cold.get('status') != 'cold-reopen-verified-subset'
            or cold.get('processExited') is not True):
        raise ValueError('Completed native save and independent reopen required')
    work = root/'UnityProject'
    manifest = hash_file(work/'manifest.json', 128*1024**2)
    if manifest['sha256'] != receipt['sourceCandidateManifestSha256']:
        raise ValueError('Source candidate manifest differs')
    files = receipt['savedFiles']
    if not isinstance(files, list) or not 1 <= len(files) <= 20000:
        raise ValueError('Bounded saved file list required')
    unique_paths(row['path'] for row in files)
    identities = {execution['path']:execution, manifest['path']:manifest}
    remaining = 2*1024**3
    for row in files:
        path = canonical_path(work/relative_name(row['path']))
        if not path.is_relative_to(work) or row['path'].split('/')[0] not in ('Assets', 'Packages', 'ProjectSettings', 'Analysis'):
            raise ValueError('Saved input outside candidate payload')
        actual = hash_file(path, min(256*1024**2, remaining))
        remaining -= actual['bytes']
        if actual['sha256'] != row['sha256'] or actual['bytes'] != row['bytes']:
            raise ValueError('Saved input identity differs')
        identities[str(path)] = actual
    for r in (receipt, cold):
        path = canonical_path(r['readbackPath'])
        if not path.is_relative_to(work) or str(path) not in identities or identities[str(path)]['sha256'] != r['readbackSha256']:
            raise ValueError('Readback outside frozen saved files or identity differs')
    return receipt, identities


def freeze(config, native_output, expected_execution, output):
    """Thin, fixed freeze command. No recovery, Editor or game methods run."""
    from grea import runner
    from grea.common import write_new
    from grea.safe_paths import disjoint, relative_name, unique_paths
    from .identity import pinned
    from .pipeline import probe, UNITY_PREFAB_VERSIONS
    cfg = pinned(config)
    if cfg['schema_version'] != 2 or cfg['version'] not in UNITY_PREFAB_VERSIONS:
        raise ValueError('Exact supported Unity Prefab launcher lock required')
    receipt, identities = native_inputs(native_output, expected_execution)
    lock_identity = hash_file(config)
    root = canonical_path(native_output)
    out = disjoint(output, root, config, *[r['path'] for r in cfg['identity_files']])
    if out.exists() or not out.parent.is_dir():
        raise ValueError('Fresh output required')
    out.mkdir();executed=False
    try:
        _, cap = probe(config, out/'capabilities')
        if 'freeze-unity-prefabs' not in cap.get('implemented', []):
            raise ValueError('Fixed provider does not advertise freeze-unity-prefabs')
        argv = ['freeze-unity-prefabs', '--native-output', str(root), '--expected-execution', expected_execution, '--out', str(out/'provider-output')]
        actual, _, error = runner.execute('monkey', argv, out/'invocation', timeout_seconds=300, max_output_bytes=1024**2, max_inline_bytes=1024**2)
        executed=True;pinned(config)
        if hash_file(config) != lock_identity or native_inputs(root, expected_execution)[1] != identities:
            raise ValueError('Frozen input/provider identity changed')
        payload = actual.get('parsed_stdout')
        if error or actual.get('exit_code') != 1 or not actual.get('capture_complete') or not isinstance(payload,dict) or payload.get('status') != 'needs_action':
            raise ValueError('Freeze failed; inspect preserved provider receipt')
        target = out/'provider-output'
        manifest = hash_file(target/'manifest.json', 128*1024**2)
        m = read(manifest['path'], 128*1024**2)
        original = read(root/'UnityProject/manifest.json',128*1024**2)
        if (m.get('contract') != 'monkey-unity-prefab-recovery/1'
                or m.get('executionReceiptSha256') != expected_execution
                or m.get('sourceCandidateManifestSha256') != receipt['sourceCandidateManifestSha256']
                or m.get('native') != receipt['status']
                or m.get('independentReopen') != receipt['independentReopen']['status']
                or m.get('diagnostics') != original.get('diagnostics')
                or m.get('selectedSourceRoots') != original.get('selectedSourceRoots')
                or not isinstance(m.get('namespace'),str) or not m['namespace']
                or payload.get('manifestSha256') != manifest['sha256']):
            raise ValueError('Frozen selection lineage differs')
        rows = m['files'];unique_paths(r['path'] for r in rows)
        expected = {r['path']:r for r in receipt['savedFiles']}
        expected['Analysis/Native/execution-result.json'] = dict(execution=expected_execution)
        if {r['path'] for r in rows} != set(expected):
            raise ValueError('Frozen selection file set differs')
        for row in rows:
            path = canonical_path(target/relative_name(row['path']))
            if not path.is_relative_to(target):raise ValueError('Selection path escapes output')
            h = hash_file(path,256*1024**2)
            wanted = expected_execution if row['path']=='Analysis/Native/execution-result.json' else expected[row['path']]['sha256']
            if h['sha256'] != row['sha256'] or h['bytes'] != row['bytes'] or h['sha256'] != wanted:
                raise ValueError('Frozen selection content differs')
        result = dict(status='needs_action', executed=True, provider_version=cfg['version'], manifest=manifest,
                      files=len(rows), provider_result=payload, provider_exit_code=actual['exit_code'],
                      native_validation='existing_provider_evidence_reused', editor_started=False,
                      static_presentation=m.get('staticPresentation'), diagnostics=m.get('diagnostics'),
                      player_validation=m.get('player'), business_validation=m.get('business'), handoff_ready=False)
        write_new(out/'result.json',result);return result
    except Exception as error:
        write_new(out/'failure.json',dict(status='failed',message=str(error),executed=executed,partial_output_preserved=True));raise
