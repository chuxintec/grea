"""Prepare native script identity reuse in a disposable source-project copy.

This is an intake preparation step, never a target-project writer or an owning
manifest exporter. The existing intake plan/apply transaction remains unchanged.
"""
from pathlib import Path
import re
import signal
import subprocess
import threading
import time

from .errors import fail
from .implementation import identity
from .io import safe, inside, read, load, sha, encoded, write_json, new_output
from .output_limits import digest_file, copy_verified
from .unity import source_files, editor_path
from .intake import GUID, REFERENCES, guid
from .intake_contract import _exact, _array, _asset_path, _hash, _guid, _string, _simple_assembly, _unique

CONTRACT = 'beaver-intake-bindings/1'
BRIDGE = 'Assets/BeaverIntakeBindings'
ASSEMBLY = 'Beaver.IntakeBindings'
HELPER = 'Assets/BeaverIntakeBindingTools'
VERSION = '6000.6.2f1'
SNAPSHOT_BYTES = 64*1024*1024
SNAPSHOT_NODES = 8_000_000
REPORT_BYTES = 1024*1024


def snapshot_reference(stage, report, mode):
    """A small native report binds one compact, independently bounded snapshot."""
    name = mode+'-snapshot.json'
    if (mode not in ('apply','verify') or report.get('snapshotFile') != name or type(report.get('snapshotBytes')) is not int
            or not 0 < report['snapshotBytes'] <= SNAPSHOT_BYTES
            or not isinstance(report.get('snapshotSha256'),str) or not re.fullmatch('[0-9a-f]{64}', report['snapshotSha256'])):
        fail('INTAKE_BINDING_SNAPSHOT', str(stage), 'Exact bounded native snapshot identity required')
    path = inside(stage, name)
    if not path.is_file() or path.stat().st_size != report['snapshotBytes'] or digest_file(path, max_bytes=SNAPSHOT_BYTES) != report['snapshotSha256']:
        fail('INTAKE_BINDING_SNAPSHOT', str(path), 'Native snapshot differs from its report')
    return path


def validate_spec(doc):
    _exact(doc, {'schemaVersion', 'operation', 'bindings', 'prefabs', 'bridgeReferences'}, '$')
    if type(doc['schemaVersion']) is not int or doc['schemaVersion'] != 1 or doc['operation'] != 'prepare-script-bindings':
        fail('INTAKE_BINDING_SPEC', '$', 'prepare-script-bindings schemaVersion 1 required')
    rows = _array(doc['bindings'], 'bindings', 1, 16)
    fields = {'source', 'sourceGuid', 'sourceSha256', 'sourceMetaSha256', 'sourceType', 'sourceAssembly',
              'sourceLocalId', 'target', 'targetGuid', 'targetSha256', 'targetMetaSha256',
              'targetType', 'targetAssembly', 'targetLocalId'}
    for n, row in enumerate(rows):
        where = f'bindings[{n}]'
        _exact(row, fields, where)
        for side in ('source', 'target'):
            _asset_path(row[side], where+'.'+side, {'.cs'})
            _guid(row[side+'Guid'], where+'.'+side+'Guid')
            for key in ('Sha256', 'MetaSha256'):
                _hash(row[side+key], where+'.'+side+key)
            _string(row[side+'Type'], where+'.'+side+'Type', max_length=512)
            _simple_assembly(row[side+'Assembly'], where+'.'+side+'Assembly')
            if type(row[side+'LocalId']) is not int or row[side+'LocalId'] != 11500000:
                fail('INTAKE_BINDING_LOCAL_ID', where, 'Only native C# MonoScripts with localID 11500000 are supported')
        if (row['sourceGuid'] == row['targetGuid'] or row['sourceType'] != row['targetType']
                or row['sourceSha256'] != row['targetSha256']):
            fail('INTAKE_BINDING_EQUIVALENCE', where, 'Different GUIDs, identical full type and byte-identical C# source required')
        if row['sourceAssembly'] == ASSEMBLY or row['targetAssembly'] == ASSEMBLY:
            fail('INTAKE_BINDING_ASSEMBLY', where, 'Preparation assembly cannot be an original source or target assembly')
    for key in ('source', 'target', 'sourceGuid', 'targetGuid', 'sourceType'):
        _unique([r[key] for r in rows], 'bindings.'+key)
    _unique([Path(r['source']).name for r in rows], 'bindings.bridgeBasename')
    if {r['sourceGuid'] for r in rows} & {r['targetGuid'] for r in rows}:
        fail('INTAKE_BINDING_ALIAS', 'bindings', 'Source and retained GUID sets must be disjoint')
    prefabs = _array(doc['prefabs'], 'prefabs', 1, 256)
    for p in prefabs:
        _asset_path(p, 'prefabs', {'.prefab'})
    _unique(prefabs, 'prefabs')
    refs = _array(doc['bridgeReferences'], 'bridgeReferences', 0, 16)
    for name in refs:
        _simple_assembly(name, 'bridgeReferences')
        if name in (ASSEMBLY, 'Assembly-CSharp', 'Assembly-CSharp-Editor'):
            fail('INTAKE_BINDING_ASSEMBLY', name, 'Bridge cannot reference predefined assemblies or itself')
    _unique(refs, 'bridgeReferences')
    return doc


def _pin(root, path, expected):
    p = inside(root, path)
    if not p.is_file() or digest_file(p) != expected:
        fail('INTAKE_BINDING_DRIFT', path, 'Reviewed source/target bytes changed or are missing')


def _assembly(root, path):
    parent = Path(path).parent
    while parent.as_posix() != '.':
        defs = list(inside(root, parent.as_posix()).glob('*.asmdef'))
        refs = list(inside(root, parent.as_posix()).glob('*.asmref'))
        if refs or len(defs) > 1:
            fail('INTAKE_BINDING_ASSEMBLY', path, 'Ambiguous/asmref compilation scope requires a separate supported contract')
        if defs:
            p = safe(defs[0]); return load(read(p))['name'], {str(p.relative_to(root)): digest_file(p)}
        parent = parent.parent
    return ('Assembly-CSharp-Editor' if 'Editor' in Path(path).parts else 'Assembly-CSharp'), {}


def build_plan(source, target, spec):
    source, target, spec = safe(source), safe(target), safe(spec)
    if source == target or source.is_relative_to(target) or target.is_relative_to(source):
        fail('OUTPUT_OVERLAP', str(target), 'Independent source and retained target projects required')
    doc = validate_spec(load(read(spec)))
    files = source_files(source)
    for root in (source, target):
        if not re.search(r'^m_EditorVersion: '+re.escape(VERSION)+r'\s*$', read(root/'ProjectSettings/ProjectVersion.txt').decode('utf-8'), re.M):
            fail('INTAKE_BINDING_VERSION', str(root), 'Unity '+VERSION+' required')
    if len(files) > 30000 or sum(r['bytes'] for r in files.values()) > 2*1024**3:
        fail('INTAKE_BINDING_BUDGET', str(source), 'Source copy exceeds 30000 files/2GiB')
    for folder in (BRIDGE, HELPER):
        if any(p.casefold() == folder.casefold()+'.meta' or p.casefold().startswith(folder.casefold()+'/') for p in files) or (source/folder).exists():
            fail('INTAKE_BINDING_RESERVED', folder, 'Owned preparation folder must be absent')
    all_guids = {}
    for p in files:
        if p.startswith('Assets/') and p.endswith('.meta'):
            match = GUID.search(read(source/p))
            if match:
                g = match.group(1).decode()
                if g in all_guids:
                    fail('INTAKE_BINDING_ALIAS', p, 'Duplicate source asset GUID')
                all_guids[g] = p[:-5]
    target_pins = {}
    for row in doc['bindings']:
        for side, root in [('source', source), ('target', target)]:
            for suffix, key in [('', 'Sha256'), ('.meta', 'MetaSha256')]:
                p = row[side]+suffix; _pin(root, p, row[side+key])
                if side == 'target': target_pins[p] = row[side+key]
            if guid(read(root/(row[side]+'.meta')), row[side]) != row[side+'Guid']:
                fail('INTAKE_BINDING_GUID', row[side], 'Pinned MonoScript metadata GUID differs')
            name, pins = _assembly(root, row[side])
            if name != row[side+'Assembly']:
                fail('INTAKE_BINDING_ASSEMBLY', row[side], 'Pinned compilation scope differs')
            if side == 'target': target_pins.update(pins)
        if row['targetGuid'] in all_guids:
            fail('INTAKE_BINDING_ALIAS', row['targetGuid'], 'Retained GUID is already present in the source project')
        for suffix in ('', '.meta'):
            if row['source']+suffix not in files:
                fail('INTAKE_BINDING_SOURCE', row['source'], 'Source MonoScript must belong to the source snapshot')
    selected = set(doc['prefabs']); used = set()
    for path in selected:
        if path not in files or path+'.meta' not in files:
            fail('INTAKE_BINDING_PREFAB', path, 'Selected Prefab and metadata required')
        refs = {x.decode() for x in REFERENCES.findall(read(source/path))}
        used |= refs & {r['sourceGuid'] for r in doc['bindings']}
        nested = {all_guids[g] for g in refs if all_guids.get(g, '').endswith('.prefab')}
        if nested-selected:
            fail('INTAKE_BINDING_CLOSURE', path, 'Select nested Prefab dependencies too: '+', '.join(sorted(nested-selected)))
    if used != {r['sourceGuid'] for r in doc['bindings']}:
        fail('INTAKE_BINDING_UNUSED', 'bindings', 'Every explicit mapping must occur in the selected Prefabs')
    origin = dict(productSnapshotSha256=sha(encoded(files)), owningManifest=None, owningStatus='not_supplied', evidence=[])
    from .candidate_snapshot import snapshot as owning_snapshot, verify as owning_verify
    from .errors import BeaverError
    for name in ('manifest.json', 'recovery-manifest.json'):
        path=source/name
        if path.is_file():
            raw=read(path);claims=load(raw)
            origin['owningManifest']=dict(path=str(path),sha256=sha(raw),bytes=len(raw),claims={k:claims.get(k) for k in ('namespace','native','diagnostics','source','producer')})
    if origin['owningManifest']:
        try:
            owned_root, owned_manifest, owned_files, _ = owning_snapshot(source);owning_verify(owned_root, owned_files)
            origin['owningStatus']='verified'
        except BeaverError as error:
            origin['owningStatus']='unverified_diagnostic_source';origin['diagnostic']=error.as_dict()
    for name in ('Analysis/Readback/source-prefabs-readback.json', 'Analysis/Readback/editor-readback.json'):
        path=source/name
        if path.is_file():origin['evidence'].append(dict(path=str(path),sha256=digest_file(path),bytes=path.stat().st_size))
    return dict(contract=CONTRACT, implementationSha256=identity(), sourceRoot=str(source), targetRoot=str(target), sourceOrigin=origin,
                specPath=str(spec), specSha256=digest_file(spec), spec=doc, sourceFiles=files, targetPins=target_pins,
                native='not_run', targetWrites=False, purpose='native preparation copy; GREA owning export and ordinary intake still required')


def preview(source, target, spec, output):
    plan = build_plan(source, target, spec)
    out = new_output(output, [safe(source), safe(target), safe(spec)])
    write_json(out/'binding-plan.json', plan)
    digest = digest_file(out/'binding-plan.json')
    return dict(status='planned', report=str(out/'binding-plan.json'), planSha256=digest, native='not_run', targetWrites=False)


def _run(stage, project, editor, mode, budget):
    from .native_environment import editor_environment
    path = stage/'binding-job.json'
    job = load(read(path)); job['mode'] = mode; write_json(path, job)
    args = [str(editor), '-batchmode', '-nographics', '-projectPath', str(project), '-executeMethod',
            'BeaverIntakeBindings.Run', '-logFile', str(stage/(mode+'.log'))]
    handlers = {}; interrupted = []
    with (stage/(mode+'-console.log')).open('w') as log:
        process = subprocess.Popen(args, cwd=project, env=editor_environment('BEAVER_INTAKE_BINDINGS_JOB', path), stdout=log, stderr=subprocess.STDOUT)
        try:
            for n in (signal.SIGINT, signal.SIGTERM): handlers[n] = signal.signal(n, lambda n, f: interrupted.append(n))
            deadline = time.monotonic()+budget
            while process.poll() is None and time.monotonic() < deadline and not interrupted: time.sleep(.2)
        finally:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=30)
                except subprocess.TimeoutExpired: pass
            for n, handler in handlers.items(): signal.signal(n, handler)
            write_json(stage/(mode+'-process.json'), dict(pid=process.pid, exited=process.poll() is not None, exitCode=process.poll(), interrupted=bool(interrupted)))
    if process.poll() is None:
        fail('INTAKE_BINDING_EXIT_PENDING', str(stage), 'Owned preparation Editor has not exited; preserve output, do not replay')
    report = stage/(mode+'-report.json')
    result = load(read(report, max_bytes=REPORT_BYTES), max_nodes=10000) if report.is_file() else {}
    if interrupted or process.returncode != 0 or result.get('status') != 'verified' or result.get('planSha256') != job['planSha256'] or result.get('mode') != mode:
        fail('INTAKE_BINDING_NATIVE_FAILED', str(stage), 'Preparation gate failed; preserve isolated copy/logs; no target writes')
    snapshot_reference(stage, result, mode)
    return result


def failed_native_attempts(stage):
    """Report only bounded owned process receipts; never infer Editor from files."""
    stage = safe(stage)
    attempts = []
    for mode in ('apply', 'verify'):
        path = stage/(mode+'-process.json')
        if not path.is_file(): continue
        row = load(read(path, max_bytes=4096))
        if type(row.get('pid')) is not int or row['pid'] <= 0 or type(row.get('exited')) is not bool:
            fail('INTAKE_BINDING_PROCESS_RECEIPT', str(path), 'Malformed owned native process receipt')
        attempts.append(dict(mode=mode, processReceipt=str(path), pid=row['pid'], exited=row['exited'], exitCode=row.get('exitCode'), interrupted=row.get('interrupted', False)))
    return attempts


def export_existing(preparation, expected_plan, native_runtime, expected_native_producer, output):
    """Continue a failed Python export without replaying verified Editor gates.

    The complete original producer and identical native helper are pinned. This
    operation reads the original stage and writes only a new export directory.
    """
    stage, runtime = safe(preparation), safe(native_runtime)
    plan_file = inside(stage, 'preparation-plan.json')
    if digest_file(plan_file) != expected_plan:
        fail('INTAKE_BINDING_PLAN', str(plan_file), 'Exact original native plan hash required')
    plan = load(read(plan_file))
    if plan.get('contract') != CONTRACT or plan.get('implementationSha256') != expected_native_producer:
        fail('INTAKE_BINDING_IMPLEMENTATION', str(plan_file), 'Explicit original native producer required')
    inventory = {}; total = 0
    for path in sorted(runtime.rglob('*')):
        if path.is_symlink(): fail('SYMLINK_PATH', str(path), 'Original runtime inventory cannot contain links')
        if not path.is_file() or '__pycache__' in path.parts or path.suffix in ('.pyc','.pyo'): continue
        total += path.stat().st_size
        if len(inventory) >= 1024 or total > 64*1024*1024:
            fail('INTAKE_BINDING_RUNTIME_BUDGET', str(runtime), 'Original runtime exceeds1024 files/64MiB')
        inventory[path.relative_to(runtime).as_posix()] = digest_file(path)
    if sha(encoded(inventory)) != expected_native_producer:
        fail('INTAKE_BINDING_IMPLEMENTATION', str(runtime), 'Original native runtime bytes differ from pinned producer')
    helper = 'targets/BeaverIntakeBindings.cs'
    if inventory.get(helper) != digest_file(Path(__file__).parent/helper):
        fail('INTAKE_BINDING_NATIVE_CHANGED', str(runtime), 'Native helper changed; fresh Editor gates are required')
    fresh = build_plan(plan['sourceRoot'], plan['targetRoot'], plan['specPath'])
    if dict(plan, implementationSha256=identity()) != fresh:
        fail('INTAKE_BINDING_PRECONDITION', str(stage), 'Original source, target pins or spec changed')
    attempts = failed_native_attempts(stage)
    if len(attempts) != 2 or any(not p['exited'] or p['exitCode'] != 0 or p['interrupted'] for p in attempts):
        fail('INTAKE_BINDING_NATIVE_FAILED', str(stage), 'Both original native processes must have reaped successful exits')
    hashes = []
    verified = None
    for mode in ('apply','verify'):
        report = load(read(inside(stage, mode+'-report.json'), max_bytes=REPORT_BYTES), max_nodes=10000)
        if report.get('status') != 'verified' or report.get('planSha256') != expected_plan or report.get('mode') != mode:
            fail('INTAKE_BINDING_NATIVE_FAILED', str(stage), 'Both original native gates must have verified the exact plan')
        snapshot_reference(stage, report, mode); hashes.append(report['snapshotSha256']); verified = report
    if hashes[0] != hashes[1] or digest_file(stage/'binding-before.json', max_bytes=SNAPSHOT_BYTES) != hashes[1]:
        fail('INTAKE_BINDING_CHECKPOINT', str(stage), 'Before/apply/cold snapshots differ')
    project = inside(stage, 'UnityProject')
    if (project/HELPER).exists() or (project/(HELPER+'.meta')).exists():
        fail('INTAKE_BINDING_HELPER_DRIFT', str(project), 'Original preparation must have removed its owned helper')
    snapshot = load(read(snapshot_reference(stage, verified, 'verify'), max_bytes=SNAPSHOT_BYTES), max_nodes=SNAPSHOT_NODES)
    from .intake_binding_export import export_prepared
    result = export_prepared(stage, project, plan, source_files(project), snapshot, output=safe(output))
    result.update(report=str(safe(output)/'export-receipt.json'), native='verified-original-gates-reused',
                  originalNativeProducer=expected_native_producer, nativeProcesses=attempts, editorStarted=False)
    return result


def execute(plan_path, expected, output, editor, budget=600):
    if threading.current_thread() is not threading.main_thread() or type(budget) is not int or not 1 <= budget <= 1200:
        fail('INTAKE_BINDING_BUDGET', str(budget), 'Main-thread owner and 1..1200 seconds per Editor phase required')
    plan_path = safe(plan_path)
    if digest_file(plan_path) != expected:
        fail('INTAKE_BINDING_PLAN', str(plan_path), 'Explicit exact plan hash required')
    plan = load(read(plan_path))
    if plan.get('contract') != CONTRACT or plan.get('implementationSha256') != identity():
        fail('INTAKE_BINDING_IMPLEMENTATION', str(plan_path), 'Exact original preparation implementation required')
    if build_plan(plan['sourceRoot'], plan['targetRoot'], plan['specPath']) != plan:
        fail('INTAKE_BINDING_PRECONDITION', str(plan_path), 'Source, retained pins, spec or implementation changed')
    editor = editor_path(editor)
    stage = new_output(output, [safe(plan['sourceRoot']), safe(plan['targetRoot']), plan_path.parent, safe(plan['specPath'])])
    project = stage/'UnityProject'; project.mkdir()
    for path, pin in plan['sourceFiles'].items():
        copy_verified(inside(safe(plan['sourceRoot']), path), project/path, pin['sha256'], pin['bytes'])
    bridge = project/BRIDGE; bridge.mkdir(parents=True)
    for row in plan['spec']['bindings']:
        for suffix, key in [('', 'Sha256'), ('.meta', 'MetaSha256')]:
            source = inside(safe(plan['targetRoot']), row['target']+suffix)
            copy_verified(source, bridge/(Path(row['source']).name+suffix), row['target'+key], source.stat().st_size)
    write_json(bridge/'Beaver.IntakeBindings.asmdef', dict(name=ASSEMBLY, references=plan['spec']['bridgeReferences'], autoReferenced=False))
    helper = project/HELPER/'Editor'; helper.mkdir(parents=True)
    (helper/'BeaverIntakeBindings.cs').write_bytes((Path(__file__).parent/'targets/BeaverIntakeBindings.cs').read_bytes())
    job = dict(projectRoot=str(project), stage=str(stage), planSha256=expected, bindings=plan['spec']['bindings'],
               bridgeRoot=BRIDGE, bridgeAssembly=ASSEMBLY, prefabs=plan['spec']['prefabs'])
    write_json(stage/'binding-job.json', job)
    write_json(stage/'preparation-plan.json', plan)
    applied = _run(stage, project, editor, 'apply', budget)
    if not 0 < (stage/'binding-before.json').stat().st_size <= SNAPSHOT_BYTES:
        fail('INTAKE_BINDING_SNAPSHOT', str(stage), 'Native before snapshot exceeds64MiB')
    checkpoint = digest_file(stage/'binding-before.json', max_bytes=SNAPSHOT_BYTES)
    verified = _run(stage, project, editor, 'verify', budget)
    if digest_file(stage/'binding-before.json', max_bytes=SNAPSHOT_BYTES) != checkpoint or applied['snapshotSha256'] != verified['snapshotSha256'] or checkpoint != verified['snapshotSha256']:
        fail('INTAKE_BINDING_CHECKPOINT', str(stage), 'Native preparation snapshots/checkpoint changed across cold reopen')
    # Only the disposable copy may change; source, target and ordinary intake
    # state are never mutated. Recheck original pins after both native gates.
    if build_plan(plan['sourceRoot'], plan['targetRoot'], plan['specPath']) != plan:
        fail('INTAKE_BINDING_PRECONDITION', str(stage), 'Original input changed during native preparation; do not consume output')
    current = source_files(project)
    mutable = set(plan['spec']['prefabs'])
    for path, pin in plan['sourceFiles'].items():
        if path not in mutable and current.get(path) != pin:
            fail('INTAKE_BINDING_UNPLANNED', path, 'Unselected source file/meta/settings changed in preparation copy')
    allowed_prefix = (BRIDGE+'/', HELPER+'/')
    allowed_folders = {BRIDGE+'.meta', HELPER+'.meta'}
    if any(p not in plan['sourceFiles'] and p not in allowed_folders and not p.startswith(allowed_prefix) for p in current):
        fail('INTAKE_BINDING_UNPLANNED', str(project), 'Unexpected preparation file was created')
    helper_file = helper/'BeaverIntakeBindings.cs'
    if digest_file(helper_file) != digest_file(Path(__file__).parent/'targets/BeaverIntakeBindings.cs'):
        fail('INTAKE_BINDING_HELPER_DRIFT', str(helper_file), 'Owned preparation helper changed')
    helper_root = project/HELPER
    allowed = {'Editor.meta', 'Editor/BeaverIntakeBindings.cs', 'Editor/BeaverIntakeBindings.cs.meta'}
    if any(p.is_symlink() or p.is_file() and p.relative_to(helper_root).as_posix() not in allowed for p in helper_root.rglob('*')):
        fail('INTAKE_BINDING_HELPER_DRIFT', str(helper_root), 'Unexpected helper content; preserve isolated output')
    for p in sorted(helper_root.rglob('*'), key=lambda p:len(p.parts), reverse=True):
        if p.is_file(): p.unlink()
        else: p.rmdir()
    helper_root.rmdir()
    if (project/(HELPER+'.meta')).exists(): (project/(HELPER+'.meta')).unlink()
    current = source_files(project)
    external = []
    omitted = []
    for row in plan['spec']['bindings']:
        prepared = BRIDGE+'/'+Path(row['source']).name
        external.append(dict(source=prepared, sourceGuid=row['targetGuid'], sourceType=row['sourceType'], sourceAssembly=ASSEMBLY,
                             target=row['target'], targetGuid=row['targetGuid'], targetType=row['targetType'], targetAssembly=row['targetAssembly'],
                             targetLocalId=row['targetLocalId'], targetSha256=row['targetSha256'], targetMetaSha256=row['targetMetaSha256'],
                             reason='Byte-identical script, native rebind in isolated source copy; target GetClass rechecked by ordinary intake preflight'))
        omitted.append(dict(path=row['source'], coveredByExternalScript=prepared, reason='Original source script is not imported; selected references were natively rebound and independently reopened'))
    omitted.append(dict(path=BRIDGE+'/Beaver.IntakeBindings.asmdef', coveredByExternalScript=external[0]['source'], reason='Preparation-only compilation scope; target scripts remain in their retained assemblies'))
    write_json(stage/'intake-binding-inputs.json', dict(externalScripts=external, omittedCompilerInputs=omitted,
               limitation='Partial intake input only: GREA saved-state owning export, selected asset mapping, remaining compiler coverage and typed target oracle are still required'))
    receipt = dict(status='prepared', contract=CONTRACT, planSha256=expected, project=str(project),
                   bindings=plan['spec']['bindings'], nativeReports=[str(stage/(mode+'-report.json')) for mode in ('apply', 'verify')],
                   selectedPrefabs=plan['spec']['prefabs'], fieldsAndReferencesPreserved=True, independentReopen=True,
                   originalSourceAndTargetUnchanged=True, sourceFilesSha256=sha(encoded(plan['sourceFiles'])),
                   preparedFiles=current, targetWrites=False, adoption='not_run', owningExport='required_GREA_freeze_native_selection')
    receipt['intakeBindingInputs'] = str(stage/'intake-binding-inputs.json')
    snapshot = load(read(snapshot_reference(stage, verified, 'verify'), max_bytes=SNAPSHOT_BYTES), max_nodes=SNAPSHOT_NODES)
    from .intake_binding_export import export_prepared
    receipt['consumerExport'] = export_prepared(stage, project, plan, current, snapshot)
    write_json(stage/'preparation-receipt.json', receipt)
    return dict(status='prepared', report=str(stage/'preparation-receipt.json'), project=str(project),
                bindings=len(plan['spec']['bindings']), prefabs=len(plan['spec']['prefabs']), native='verified-preparation-subset', targetWrites=False)
