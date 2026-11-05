"""Bounded Agent workspaces: exact sources -> reviewed patch -> existing native transaction.

The worker is the calling Agent. This module never launches a model or executes a
source program. Compilation proves API compatibility, never gameplay equivalence.
"""
from copy import deepcopy
import difflib
from pathlib import Path
import re
import tempfile

from . import csharp
from .errors import fail
from .io import safe, inside, read, load, encoded, sha, write_json, new_output
from .project_profile import relative
from .unity import identity

REQUEST = 'beaver-agent-rewrite/1'
PREPARED = 'beaver-agent-rewrite-workspace/1'
RESULT = 'beaver-agent-rewrite-result/1'
PLAN = 'beaver-agent-rewrite-plan/1'
MAX_FILES = 16
MAX_BYTES = 2 * 1024 * 1024
MAX_SOURCE_FILE_BYTES = 32 * 1024**2
MAX_SOURCE_BYTES = 64 * 1024**2


def _closed(value, keys, where):
    if not isinstance(value, dict) or set(value) != set(keys):
        fail('REWRITE_CONTRACT', where, 'Exact fields required: ' + ', '.join(sorted(keys)))


def _pin(path):
    path = safe(path)
    return dict(path=str(path), sha256=sha(read(path, max_bytes=512 * 1024**2)))


def _check_pins(rows):
    for row in rows:
        if _pin(row['path']) != row:
            fail('REWRITE_INPUT_DRIFT', row['path'], 'Pinned source, API, compiler or project input changed')


def _tree(root):
    paths = list(root.rglob('*'))
    for path in paths:
        if path.is_symlink():
            fail('REWRITE_WORKER_SCOPE', str(path), 'Workspace symlinks are forbidden')
    return {p.relative_to(root).as_posix(): sha(read(safe(p), max_bytes=64 * 1024**2))
            for p in paths if p.is_file()}


def _guid(project, path, expected_meta=None, expected_guid=None):
    meta = read(inside(project, path + '.meta'))
    found = re.findall(rb'(?m)^guid:\s*([0-9a-f]{32})\s*$', meta)
    if len(found) != 1 or expected_meta and sha(meta) != expected_meta or expected_guid and found[0].decode() != expected_guid:
        fail('REWRITE_SCRIPT_IDENTITY', path, 'Exact script metadata and one existing GUID required')
    return sha(meta), found[0].decode()


def _validate(spec):
    _closed(spec, ('contract', 'sources', 'scripts', 'instances', 'expectedBehavior', 'profile'), 'request')
    if spec['contract'] != REQUEST:
        fail('REWRITE_CONTRACT', 'contract', REQUEST + ' required')
    if not isinstance(spec['sources'], list) or not 1 <= len(spec['sources']) <= 128:
        fail('REWRITE_SOURCES', 'sources', '1..128 exact source identities required')
    ids = set(); source_bytes = 0
    for row in spec['sources']:
        _closed(row, ('path', 'sha256', 'sourceId'), 'sources')
        if not isinstance(row['sourceId'], str) or not row['sourceId'] or row['sourceId'] in ids:
            fail('REWRITE_SOURCE_ID', 'sources', 'Unique nonempty source IDs required')
        ids.add(row['sourceId'])
        size = safe(row['path']).stat().st_size
        source_bytes += size
        if size > MAX_SOURCE_FILE_BYTES or source_bytes > MAX_SOURCE_BYTES:
            fail('REWRITE_SOURCE_BUDGET', row['path'], 'Source evidence is limited to 32 MiB per file / 64 MiB aggregate')
        if not Path(row['path']).is_absolute() or _pin(row['path'])['sha256'] != row['sha256']:
            fail('REWRITE_SOURCE_HASH', row['path'], 'Exact absolute source and SHA256 required')
    if not isinstance(spec['scripts'], list) or not 1 <= len(spec['scripts']) <= MAX_FILES:
        fail('REWRITE_BUDGET', 'scripts', '1..16 existing script files required')
    paths = set()
    for row in spec['scripts']:
        _closed(row, ('path', 'sha256', 'metaSha256', 'guid', 'assembly', 'fullType'), 'scripts')
        path = relative(row['path'])
        if not path.startswith('Assets/') or not path.endswith('.cs') or path in paths:
            fail('REWRITE_WRITE_SCOPE', path, 'Unique existing Assets C# scripts only; no metadata or asset writes')
        paths.add(path)
        if any(not isinstance(row[k], str) or not row[k] for k in ('assembly', 'fullType')):
            fail('REWRITE_TYPE', path, 'Explicit assembly and full type required')
        if any(not isinstance(row[k], str) or not re.fullmatch('[a-f0-9]{64}', row[k]) for k in ('sha256', 'metaSha256')):
            fail('REWRITE_HASH', path, 'Full SHA256 required')
        if not isinstance(row['guid'], str) or not re.fullmatch('[a-f0-9]{32}', row['guid']):
            fail('REWRITE_GUID', path, 'Full script GUID required')
    if len({r['fullType'] for r in spec['scripts']}) != len(spec['scripts']) or len({r['guid'] for r in spec['scripts']}) != len(spec['scripts']):
        fail('REWRITE_TYPE', 'scripts', 'Each selected script requires a distinct full type and GUID')
    if not isinstance(spec['expectedBehavior'], list) or not 1 <= len(spec['expectedBehavior']) <= 32:
        fail('REWRITE_BEHAVIOR', 'expectedBehavior', 'Source-backed expected behavior required')
    for row in spec['expectedBehavior']:
        _closed(row, ('description', 'sourceIds'), 'expectedBehavior')
        if not isinstance(row['description'], str) or not row['description'].strip() or not isinstance(row['sourceIds'], list) or not row['sourceIds'] or not set(row['sourceIds']) <= ids:
            fail('REWRITE_BEHAVIOR', 'expectedBehavior', 'Each behavior must cite supplied source IDs')
    if not isinstance(spec['profile'], str) or not Path(spec['profile']).is_absolute():
        fail('REWRITE_PROFILE', 'profile', 'Existing explicit project binding required')
    if not isinstance(spec['instances'], list) or len(spec['instances']) > 512:
        fail('REWRITE_INSTANCES', 'instances', 'Explicit bounded native instance list required (empty means compile-only)')
    seen = set()
    for row in spec['instances']:
        _closed(row, ('prefabPath', 'prefabGuid', 'nodeLocalId', 'componentLocalId', 'fullType', 'sourceIdField', 'sourceId'), 'instances')
        path = relative(row['prefabPath'])
        if not path.startswith('Assets/') or not path.endswith('.prefab') or row['fullType'] not in {s['fullType'] for s in spec['scripts']}:
            fail('REWRITE_INSTANCES', path, 'Instance must belong to a declared script and Prefab')
        if not isinstance(row['prefabGuid'], str) or not re.fullmatch('[a-f0-9]{32}', row['prefabGuid']):
            fail('REWRITE_INSTANCES', path, 'Exact Prefab GUID required')
        if any(type(row[k]) is not int or row[k] == 0 or not -2**63 <= row[k] < 2**63 for k in ('nodeLocalId', 'componentLocalId')):
            fail('REWRITE_INSTANCES', path, 'Nonzero signed 64-bit native identities required')
        key = (path, row['componentLocalId'])
        if key in seen or not isinstance(row['sourceIdField'], str) or not row['sourceIdField'] or not isinstance(row['sourceId'], str) or not row['sourceId']:
            fail('REWRITE_INSTANCES', path, 'Unique component and explicit source provenance property required')
        seen.add(key)
    if spec['instances'] and {r['fullType'] for r in spec['instances']} != {r['fullType'] for r in spec['scripts']}:
        fail('REWRITE_INSTANCE_COVERAGE', 'instances', 'Every declared script type requires an explicit instance baseline')


def _semantic_type(report, script):
    matches = [t for a in report.get('assemblies', []) if a['name'] == script['assembly']
               for source in a.get('sourceSemantics', []) if source['path'] == script['path']
               for t in source['types'] if t['fullName'] == script['fullType']]
    if len(matches) != 1 or not matches[0].get('unityObject'):
        fail('REWRITE_TYPE_IDENTITY', script['path'], 'Exactly one matching compiled Unity object type required')
    return matches[0]


def _compatibility(before, after, scripts):
    mappings = []
    for script in scripts:
        old, new = _semantic_type(before, script), _semantic_type(after, script)
        if any(old[k] != new[k] for k in ('assembly', 'fullName', 'baseType', 'baseAssembly')):
            fail('REWRITE_TYPE_MIGRATION', script['path'], 'Type/base migration requires a separately reviewed native migration')
        old_fields, new_fields = old['serializedFields'], new['serializedFields']
        # This first entry point preserves the entire serialized schema. Renaming,
        # conversion and schema additions need a native migration, never a guessed map.
        if old_fields != new_fields:
            fail('REWRITE_FIELD_MIGRATION', script['path'], 'Serialized fields changed; explicit native migration required')
        method_keys = lambda rows: {encoded(row) for row in rows}
        if not method_keys(old['eventMethods']) <= method_keys(new['eventMethods']):
            fail('REWRITE_EVENT_METHOD', script['path'], 'Existing public instance method signatures must remain callable')
        mappings.append(dict(path=script['path'], assembly=script['assembly'], fullType=script['fullType'],
                             guid=script['guid'], fieldMappings=[dict(source=f, target=f, conversion='identity') for f in old_fields],
                             preservedEventMethods=old['eventMethods']))
    return mappings


def _compile(project, assemblies, compiler, replacements=None):
    """Compile copies of every modeled source, without touching target or drafts."""
    with tempfile.TemporaryDirectory(prefix='beaver-rewrite-compile-') as temp:
        root = Path(temp).resolve()
        compiled = deepcopy(assemblies)
        for row in compiled:
            sources = []
            for raw in row['sources']:
                rel = Path(raw).relative_to(project).as_posix()
                dest = root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes((replacements or {}).get(rel, read(raw)))
                sources.append(str(dest))
            row['sources'] = sources
        return csharp._run_semantic(root, 'inspect', compiled, compiler)[0]


def prepare(project, spec_path, output, toolchain=None):
    project, spec_path = safe(project), safe(spec_path)
    spec = load(read(spec_path))
    _validate(spec)
    compiler = csharp._resolve_toolchain(toolchain)
    assemblies = csharp._compile_inputs(project, toolchain or {})
    if csharp._incomplete_compile_context(assemblies):
        fail('REWRITE_COMPILE_CONTEXT', str(project), 'Unsupported compiler inputs block rewrite')
    source_paths = {p for a in assemblies for p in a['sources']}
    total = 0
    for row in spec['scripts']:
        path = inside(project, row['path'])
        raw = read(path, max_bytes=MAX_BYTES)
        total += len(raw)
        if str(path) not in source_paths or sha(raw) != row['sha256']:
            fail('REWRITE_TARGET_HASH', row['path'], 'Exact existing modeled script bytes required')
        _guid(project, row['path'], row['metaSha256'], row['guid'])
    if total > MAX_BYTES:
        fail('REWRITE_BUDGET', 'scripts', 'Aggregate editable source limit is 2 MiB')
    from .project_profile import check
    check(project, spec['profile'], writes=[r['path'] for r in spec['scripts']])
    # Pin before compilation and recheck afterward; compilation is never an
    # opportunity to substitute newer API/source bytes into the frozen context.
    inputs = {str(spec_path), str(safe(spec['profile'])), compiler['dotnet'], compiler['compiler'],
              str(Path(compiler['roslynDirectory']) / 'Microsoft.CodeAnalysis.dll'),
              str(Path(compiler['roslynDirectory']) / 'Microsoft.CodeAnalysis.CSharp.dll')}
    for row in spec['sources']:
        inputs.add(str(safe(row['path'])))
    for row in spec['scripts']:
        inputs.add(str(inside(project, row['path'] + '.meta')))
    for row in assemblies:
        inputs.update(row['sources']); inputs.update(row['references'])
        for kind in ('analyzerInputs', 'additionalFileInputs'):
            inputs.update(v['path'] for v in row.get(kind, []))
        for key in ('responseFile', 'inputData', 'projectFile'):
            if row.get(key): inputs.add(row[key])
    for name in ('Packages/manifest.json', 'Packages/packages-lock.json', 'ProjectSettings/ProjectVersion.txt'):
        if (project / name).is_file(): inputs.add(str(project / name))
    pins = [_pin(p) for p in sorted(inputs)]
    baseline = _compile(project, assemblies, compiler)
    _check_pins(pins)
    if baseline.get('status') != 'ok':
        fail('REWRITE_BASELINE_COMPILE', str(project), str(baseline.get('diagnostics', []))[:4000])
    for row in spec['scripts']: _semantic_type(baseline, row)
    out = new_output(output, inputs=[project, spec_path, *[r['path'] for r in spec['sources']]])
    for row in spec['scripts']:
        dest = out / 'files' / row['path']; dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(read(project / row['path']))
    write_json(out / 'context/request.json', spec)
    write_json(out / 'context/baseline.json', baseline)
    for n, row in enumerate(spec['sources']):
        dest = out / 'context/sources' / (str(n) + Path(row['path']).suffix)
        dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(read(row['path']))
    (out / 'INSTRUCTIONS.md').write_text(
        'Rewrite only files/ paths selected in context/request.json. Read every supplied source. '
        'Keep script/type/assembly identities and the complete serialized schema. Preserve existing public instance method signatures. '
        'Do not edit context, project assets, metadata, packages, services, credentials or model settings. '
        'Do not run original source or invoke another model. Produce a real implementation for the cited behavior; '
        'record unresolved semantics rather than inventing services or success. '
        'Create result.json with exactly contract, changedPaths, limitations, behaviorEvidence. '
        'contract=beaver-agent-rewrite-result/1; changedPaths are actual modified Assets paths; '
        'limitations is a string array; behaviorEvidence is the source-backed expectedBehavior array. '
        'Compilation and schema compatibility do not prove visible behavior.\n', encoding='utf-8')
    _check_pins(pins)
    immutable = {k: v for k, v in _tree(out).items() if not k.startswith('files/')}
    report = dict(contract=PREPARED, implementationSha256=identity(), projectRoot=str(project),
                  spec=spec, compiler=compiler, assemblies=assemblies, pins=pins, immutable=immutable,
                  directories=sorted(p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_dir()),
                  status='prepared', native='not_run', behavior='not_verified')
    write_json(out / 'workspace.json', report)
    return dict(status='prepared', workspace=str(out / 'workspace.json'), workspaceSha256=sha(encoded(report)),
                editableFiles=len(spec['scripts']), native='not_run', behavior='not_verified')


def _open(workspace, expected):
    path = safe(workspace); raw = read(path, max_bytes=64 * 1024**2); data = load(raw)
    if sha(raw) != expected or data.get('contract') != PREPARED or data.get('implementationSha256') != identity():
        fail('REWRITE_WORKSPACE_IDENTITY', str(path), 'Exact prepared workspace and current implementation required')
    _validate(data['spec']); _check_pins(data['pins'])
    return path.parent, data


def plan(workspace, expected_workspace, output):
    root, data = _open(workspace, expected_workspace)
    project, spec = safe(data['projectRoot']), data['spec']
    current = _tree(root)
    allowed = {'workspace.json', 'result.json'} | set(data['immutable']) | {'files/' + s['path'] for s in spec['scripts']}
    if (set(current) != allowed or any(current.get(k) != v for k, v in data['immutable'].items()) or
            sorted(p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_dir()) != data['directories']):
        fail('REWRITE_WORKER_SCOPE', str(root), 'Only selected files and result.json may change; no missing/context/extra files')
    def snapshot(relative_path, maximum=64 * 1024**2):
        raw = read(root / relative_path, max_bytes=maximum)
        if sha(raw) != current[relative_path]:
            fail('REWRITE_WORKER_DRIFT', relative_path, 'Worker changed after the verified workspace snapshot')
        return raw
    result = load(snapshot('result.json'))
    _closed(result, ('contract', 'changedPaths', 'limitations', 'behaviorEvidence'), 'result')
    if result['contract'] != RESULT or result['behaviorEvidence'] != spec['expectedBehavior']:
        fail('REWRITE_RESULT', 'result', 'Worker must account for the exact source-backed expected behavior')
    if not isinstance(result['limitations'], list) or any(not isinstance(x, str) or not x for x in result['limitations']):
        fail('REWRITE_RESULT', 'limitations', 'Explicit string-array limitations required')
    changed = [s['path'] for s in spec['scripts'] if current['files/' + s['path']] != s['sha256']]
    if not changed or result['changedPaths'] != changed:
        fail('REWRITE_CHANGED_PATHS', 'changedPaths', 'Actual nonempty changed paths must equal the ordered worker ledger')
    replacements = {p: snapshot('files/' + p, MAX_BYTES) for p in changed}
    if sum(len(raw) for raw in replacements.values()) > MAX_BYTES:
        fail('REWRITE_BUDGET', 'files', 'Aggregate patch limit is 2 MiB')
    baseline = load(snapshot('context/baseline.json'))
    compiled = _compile(project, data['assemblies'], data['compiler'], replacements)
    _check_pins(data['pins'])
    if _tree(root) != current:
        fail('REWRITE_WORKER_DRIFT', str(root), 'Worker workspace changed during compilation')
    if compiled.get('status') != 'ok':
        fail('REWRITE_PATCH_COMPILE', str(root), str(compiled.get('diagnostics', []))[:5000])
    mappings = _compatibility(baseline, compiled, spec['scripts'])
    out = new_output(output, inputs=[project, root])
    edits, patch = [], []
    for p, raw in replacements.items():
        dest = out / 'files' / p; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(raw)
        before_bytes = read(project / p)
        original = next(s for s in spec['scripts'] if s['path'] == p)
        if sha(before_bytes) != original['sha256']:
            fail('REWRITE_INPUT_DRIFT', p, 'Target script changed after compilation')
        before = before_bytes.decode('utf-8'); after = raw.decode('utf-8')
        patch.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/' + p, tofile='b/' + p))
        edits.append(dict(path=p, source=str(dest), sha256=sha(raw), expectedSha256=original['sha256']))
    (out / 'changes.patch').write_text(''.join(patch), encoding='utf-8')
    write_json(out / 'compile.json', compiled)
    groups = {}
    for row in spec['instances']: groups.setdefault(row['prefabPath'], set()).add(row['fullType'])
    steps = [dict(kind='prefab.scripts.inspect', assetPath=p, types=sorted(types)) for p, types in sorted(groups.items())]
    production = dict(schemaVersion=3, operation='production', profile=spec['profile'], steps=steps, fileEdits=edits,
                      readPaths=sorted(s['path'] + '.meta' for s in spec['scripts']))
    write_json(out / 'production-spec.json', production)
    from .production import plan as production_plan
    native = production_plan(project, out / 'production-spec.json', out / 'native-plan')
    report = dict(contract=PLAN, status='planned', implementationSha256=identity(), projectRoot=str(project),
                  workspace=dict(path=str(safe(workspace)), sha256=expected_workspace), pins=data['pins'],
                  workerResult=result, compatibility=mappings, fileEdits=edits, production=native,
                  instances=spec['instances'],
                  native='not_run', behavior='not_verified', formalAdoption='not_permitted_by_plan',
                  limitations=['Schema-preserving existing scripts only; type/field migration needs a separate native migration',
                               'Prefab instances, references and persistent events require native save and cold-reopen checks',
                               'Project owner must validate one visible action and effect on the fixed B-line candidate'])
    write_json(out / 'rewrite-plan.json', report)
    return dict(status='planned', report=str(out / 'rewrite-plan.json'), planSha256=sha(encoded(report)),
                patches=len(edits), native='not_run', behavior='not_verified')


def apply(plan_path, expected, output, editor, timeout=600):
    path = safe(plan_path); raw = read(path, max_bytes=64 * 1024**2); data = load(raw)
    if sha(raw) != expected or data.get('contract') != PLAN or data.get('implementationSha256') != identity():
        fail('REWRITE_PLAN_IDENTITY', str(path), 'Exact reviewed patch plan and implementation required')
    _check_pins(data['pins'])
    for row in data['fileEdits']:
        if _pin(row['source'])['sha256'] != row['sha256']:
            fail('REWRITE_PATCH_DRIFT', row['source'], 'Reviewed patch changed')
    if not data['instances']:
        fail('REWRITE_INSTANCE_BASELINE_REQUIRED', str(path), 'Compile-only plan has no native instance baseline')
    out = new_output(output, inputs=[safe(data['projectRoot']), path.parent])
    from . import batch
    production_spec = load(read(Path(data['production']['report'])))['spec']
    readonly_spec = dict(schemaVersion=2, operation='batch', steps=production_spec['steps'])
    write_json(out / 'inspection-spec.json', readonly_spec)
    def observe(name):
        inspection = batch.plan(data['projectRoot'], out/'inspection-spec.json', out/(name+'-plan'))
        result = batch.apply(inspection['report'], out/name, editor, inspection['planSha256'], timeout)
        journal = load(read(Path(result['transaction'])/'journal.json'))
        if journal['writeSet']:
            fail('REWRITE_INSPECTION_WRITES', str(out/name), 'Native compatibility observation must be read-only')
        _instances(journal['native'], data, after=False if name == 'before' else True)
        return journal['native']
    before = observe('before')
    from .production import apply as production_apply
    native = data['production']
    result = production_apply(native['report'], out/'transaction', editor, native['planSha256'], timeout)
    try:
        after = observe('cold-after')
        _compare_native(before, after)
    except Exception as error:
        write_json(out/'verification.json', dict(status='recovery-required', transaction=result['transaction'], error=str(error)))
        fail('REWRITE_NATIVE_COMPATIBILITY', result['transaction'], 'Patch applied but cold compatibility failed; inspect and recover exact transaction: '+str(error))
    report = dict(contract='beaver-agent-rewrite-verification/1', status='verified', transaction=result['transaction'],
                  planSha256=expected, scriptsCompiled=True, instances=len(data['instances']),
                  fieldsReferencesEvents='equal_before_and_cold_reopen', behavior='not_verified', formalAdoption='not_permitted_by_plan')
    write_json(out/'verification.json', report)
    return dict(status='verified', report=str(out/'verification.json'), transaction=result['transaction'], behavior='not_verified')


def _instances(native, data, after):
    rows = native.get('scriptInstances', [])
    expected = {(r['prefabPath'], r['componentLocalId']): r for r in data['instances']}
    if len(rows) != len(expected) or len({(r['prefabPath'], r['componentLocalId']) for r in rows}) != len(rows):
        fail('REWRITE_INSTANCE_COUNT', 'native', 'Missing, extra or duplicate script instances')
    scripts = {r['fullType']: r for r in data['compatibility']}
    coverage = {r['fullType']: r for r in native.get('scriptCoverage', [])}
    if set(coverage) != set(scripts) or any(not r.get('complete') for r in coverage.values()):
        fail('REWRITE_INSTANCE_COVERAGE', 'native', 'Native project-wide Prefab consumer discovery required')
    for full_type in scripts:
        declared = [r for r in data['instances'] if r['fullType'] == full_type]
        if (coverage[full_type]['prefabPaths'] != sorted({r['prefabPath'] for r in declared}) or
                coverage[full_type]['instanceCount'] != len(declared)):
            fail('REWRITE_INSTANCE_COVERAGE', full_type, 'Declared instances do not cover every project Prefab consumer')
    after_hash = {r['path']: r['sha256'] for r in data['fileEdits']}
    original_hash = {r['path']: r['sha256'] for r in data['pins']}
    for row in rows:
        key = (row['prefabPath'], row['componentLocalId']); target = expected.get(key)
        if target is None or any(row[k] != target[k] for k in ('prefabGuid', 'nodeLocalId', 'fullType')) or not row['getClassVerified']:
            fail('REWRITE_INSTANCE_IDENTITY', str(key), 'Wrong Prefab, node, component or GetClass identity')
        script = scripts[row['fullType']]
        if row['assembly'] != script['assembly'] or row['scriptGuid'] != script['guid'] or row['scriptPath'] != script['path']:
            fail('REWRITE_INSTANCE_SCRIPT', str(key), 'Wrong script GUID, path, assembly or type')
        code_hash = after_hash.get(script['path']) if after else None
        code_hash = code_hash or original_hash[str(Path(data['projectRoot']) / script['path'])]
        if row['scriptSha256'] != code_hash:
            fail('REWRITE_INSTANCE_SCRIPT', str(key), 'Compiled native script bytes differ from reviewed patch/baseline')
        props = [p for p in row['properties'] if p['path'] == target['sourceIdField']]
        if len(props) != 1 or props[0]['kind'] != 'String' or props[0]['value'] != target['sourceId']:
            fail('REWRITE_INSTANCE_PROVENANCE', str(key), 'Instance does not retain its exact source identity')


def _compare_native(before, after):
    if before.get('scriptCoverage') != after.get('scriptCoverage'):
        fail('REWRITE_INSTANCE_COVERAGE', 'native', 'Project-wide Prefab consumer set changed')
    def stable_rows(report):
        rows = []
        for row in report['scriptInstances']:
            value = dict(row); value.pop('scriptSha256')
            rows.append(value)
        return sorted(rows, key=lambda r: (r['prefabPath'], r['componentLocalId']))
    if stable_rows(before) != stable_rows(after):
        fail('REWRITE_NATIVE_VALUES', 'native', 'Instance, enabled state, field value, persistent reference or event target changed')
    prefab_keys = lambda report: {r['path']: {k: r[k] for k in ('guid','contentSha256','serializedTreeSha256','nodes','missingScripts')} for r in report['prefabs']}
    if prefab_keys(before) != prefab_keys(after):
        fail('REWRITE_NATIVE_PREFAB', 'native', 'Unchanged Prefab bytes, hierarchy, components and serialized event/reference tree required')


def recover(transaction, output, editor, timeout=600):
    from .production import recover as production_recover
    return production_recover(transaction, output, editor, timeout)
