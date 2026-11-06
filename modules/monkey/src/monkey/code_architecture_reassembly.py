"""Safely reclassify finalized module outputs and assemble a fresh candidate.

This is a read-only consumer of the terminal architecture pipeline. It never
updates the old pipeline state or module manifests and never runs an AI or
engine process.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import code_architecture_modules as modules
from .code_architecture_candidate import assemble_native_candidate
from .io import encoded, inside, load, read, safe, sha, write_json
from .output_limits import FILE_BYTES, WHOLE_BYTES, copy_verified
from .sources.compiled import fail

TERMINAL_MODULE_STATES = {'generated_unreviewed', 'partial_unimplemented_seed', 'evidence_only'}
RECHECK_CLASSIFICATIONS = {'generated_unreviewed', 'unimplemented_seed',
                           'unimplemented_seed_residue', 'incomplete_contract'}
MAX_PIPELINE_JSON = 128 * 1024 * 1024


def _json(path, maximum=MAX_PIPELINE_JSON):
    return load(read(safe(path), maximum), max_nodes=8_000_000)


def _fail(code, location, message):
    fail('CODE_ARCH_REASSEMBLY_' + code, str(location), message)


def _digest_manifest(path):
    raw = read(safe(path), FILE_BYTES)
    return raw, sha(raw), load(raw, max_nodes=2_000_000)


def _expected_member_ids(class_row):
    return sorted({value for key in ('fields', 'methods')
                   for entry in class_row.get(key, [])
                   for value in entry.get('sourceMemberIds', [])})


def _pins_match(request, stage):
    pins = stage.get('pins')
    if not isinstance(pins, dict) or not pins:
        _fail('GLOBAL_PINS', stage.get('root', ''), 'Global architecture stage did not expose pins')
    for key, value in pins.items():
        if request.get(key) != value:
            _fail('GLOBAL_PINS', key, 'Pipeline request differs from its pinned architecture stage')
    return pins


def _validate_pipeline(root, allow_incomplete=False):
    request_raw = read(inside(root, 'request.json'), MAX_PIPELINE_JSON)
    state_raw = read(inside(root, 'state.json'), MAX_PIPELINE_JSON)
    request = load(request_raw, max_nodes=2_000_000)
    state = load(state_raw, max_nodes=2_000_000)
    architecture_root = safe(request.get('architectureStage'))
    stage = modules._pin_stage(architecture_root)
    if request.get('continuation'):
        from .code_architecture_pipeline import _stage
        _stage(root, request)
    pins = _pins_match(request, stage)
    state_modules = state.get('modules')
    requested_order = request.get('moduleOrder')
    if not isinstance(state_modules, list) or not isinstance(requested_order, list):
        _fail('STATE', root, 'Pipeline request/state require moduleOrder and modules arrays')
    ids = [row.get('id') if isinstance(row, dict) else None for row in state_modules]
    if ids != requested_order or len(set(ids)) != len(ids):
        _fail('STATE', root, 'Pipeline state module IDs/order differ from the pinned request')
    planned_module_ids = {row.get('id') for row in stage['plan'].get('modules', [])}
    if set(ids) != planned_module_ids:
        _fail('STATE', root, 'Pipeline module list does not cover the pinned architecture plan modules')
    all_terminal = all(isinstance(row, dict) and row.get('status') in TERMINAL_MODULE_STATES
                       for row in state_modules)
    if allow_incomplete and state.get('status') not in ('blocked','integration_checkpoint','prepared','candidate_assembled_unvalidated'):
        _fail('NOT_STOPPED', root, 'Checkpoint assembly requires a stopped supervisor')
    if not allow_incomplete and state.get('status') != 'candidate_assembled_unvalidated' and not all_terminal:
        _fail('NOT_TERMINAL', root, 'Pipeline is incomplete; no reassembly output was created')
    if not all_terminal and not allow_incomplete:
        _fail('NOT_TERMINAL', root, 'Every module must be terminal before reassembly')
    if request.get('sourceManifestSha256') != pins.get('sourceManifestSha256'):
        _fail('GLOBAL_PINS', root, 'Candidate source manifest pin differs from global stage')
    return request_raw, state_raw, request, state, stage, pins


def _recheck_module(root, row, stage):
    module_id = row['id']
    if row['status'] == 'evidence_only':
        return {'moduleId': module_id, 'priorState': row['status'],
                'oldManifestSha256': None, 'classification': 'evidence_only',
                'files': [], 'missingClassIds': []}, []
    if not isinstance(row.get('manifestSha256'), str):
        _fail('MODULE_PIN', module_id, 'Terminal implementation module lacks a manifest SHA pin')
    from .code_architecture_pipeline import task_root as resolve_task_root
    task_root = resolve_task_root(root,row)
    status = modules.status(task_root)
    if status.get('manifestSha256') != row['manifestSha256']:
        _fail('MODULE_PIN', module_id, 'Saved module manifest SHA differs from pipeline state')
    if status.get('status') != row['status']:
        _fail('MODULE_STATUS', module_id, 'Module status differs from pipeline state')
    manifest_raw, manifest_sha, manifest = _digest_manifest(task_root / modules.MANIFEST)
    if manifest_sha != row['manifestSha256']:
        _fail('MODULE_PIN', module_id, 'Module manifest bytes differ from the pipeline pin')
    receipt = modules.recheck(task_root)
    if receipt.get('oldManifestSha256') != manifest_sha:
        _fail('RECHECK_PIN', module_id, 'Read-only recheck classified a different old module manifest')
    if receipt.get('moduleId') != module_id or receipt.get('status') != 'rechecked':
        _fail('RECHECK', module_id, 'Read-only recheck did not return the expected finalized module receipt')
    task_manifest_path = inside(task_root, 'Task/manifest.json')
    task_manifest_raw = read(task_manifest_path, FILE_BYTES)
    task_manifest_sha = sha(task_manifest_raw)
    if receipt.get('taskManifestSha256') != task_manifest_sha:
        _fail('TASK_RECEIPT_PIN', module_id, 'Read-only recheck taskManifestSha256 differs from Task/manifest.json')
    task_receipt = load(task_manifest_raw, max_nodes=2_000_000)
    required_receipt_fields = ('status', 'outcome', 'responseSummary', 'unresolved')
    if any(key not in task_receipt for key in required_receipt_fields):
        _fail('TASK_RECEIPT_SCHEMA', module_id, 'Task manifest omits an actual worker status/outcome/summary/unresolved field')
    if (not isinstance(task_receipt['status'], str) or not isinstance(task_receipt['outcome'], str)
            or (task_receipt['responseSummary'] is not None and not isinstance(task_receipt['responseSummary'], str))
            or not isinstance(task_receipt['unresolved'], list)
            or any(not isinstance(value, str) for value in task_receipt['unresolved'])):
        _fail('TASK_RECEIPT_SCHEMA', module_id, 'Task receipt fields have invalid serialized types')
    task_receipt_fields = {key: task_receipt[key] for key in required_receipt_fields}

    class_rows = manifest.get('classes')
    artifact_rows = manifest.get('files')
    rechecked_rows = receipt.get('files')
    if not isinstance(class_rows, list) or not isinstance(artifact_rows, list) or not isinstance(rechecked_rows, list):
        _fail('MODULE_SCHEMA', module_id, 'Module manifest and recheck must include classes/files arrays')
    class_by_id = {}
    for item in class_rows:
        cid = item.get('classId') if isinstance(item, dict) else None
        if not isinstance(cid, str) or cid in class_by_id:
            _fail('MODULE_SCHEMA', module_id, 'Module class identities must be unique strings')
        class_by_id[cid] = item
    artifacts = {}
    for item in artifact_rows:
        path = item.get('targetPath') if isinstance(item, dict) else None
        if not isinstance(path, str) or path in artifacts:
            _fail('MODULE_SCHEMA', module_id, 'Module target paths must be unique strings')
        artifacts[path] = item
    actual_classes = {item.get('classId'): item for item in rechecked_rows if isinstance(item, dict)}
    if len(actual_classes) != len(rechecked_rows) or set(actual_classes) != set(class_by_id):
        _fail('RECHECK_COVERAGE', module_id, 'Recheck rows must cover each prior module class exactly once')

    class_plan = {item['id']: item for item in stage['plan']['classes']}
    validated_paths = stage['validation']['classPaths']
    file_pins = []
    copy_rows = []
    missing_class_ids = []
    for class_id in sorted(class_by_id):
        old = class_by_id[class_id]
        checked = actual_classes[class_id]
        planned = class_plan.get(class_id)
        if planned is None:
            _fail('CLASS_OWNERSHIP', class_id, 'Module contains a class absent from the global architecture plan')
        if planned.get('module') != module_id:
            _fail('CLASS_OWNERSHIP', class_id, 'Global plan assigns this class to a different module')
        path = checked.get('path')
        if path != validated_paths.get(class_id) or old.get('path') != path:
            _fail('CLASS_PATH', class_id, 'Rechecked class path differs from validated global classPaths')
        expected_units = sorted(planned.get('sourceUnitIds', []))
        expected_members = _expected_member_ids(planned)
        checked_units = checked.get('sourceUnitIds')
        checked_members = checked.get('sourceMemberIds')
        if (not isinstance(checked_units, list) or not isinstance(checked_members, list)
                or any(not isinstance(value, str) for value in checked_units + checked_members)
                or len(checked_units) != len(set(checked_units)) or len(checked_members) != len(set(checked_members))
                or set(checked_units) != set(expected_units) or set(checked_members) != set(expected_members)):
            _fail('CLASS_MAPPING', path, 'Rechecked source unit/member mapping differs from the global plan')
        artifact = artifacts.get(path)
        if not artifact or artifact.get('classId') != class_id:
            _fail('ARTIFACT_PIN', path, 'Module artifact row does not own the rechecked class')
        digest, size = checked.get('sha256'), checked.get('bytes')
        if (digest != old.get('sha256') or digest != artifact.get('sha256') or
                size != old.get('bytes') or size != artifact.get('bytes')):
            _fail('ARTIFACT_PIN', path, 'Recheck file identity differs from the old class and artifact pins')
        classification = checked.get('classification')
        if classification not in RECHECK_CLASSIFICATIONS:
            _fail('CLASSIFICATION', path, 'Unexpected recheck classification')
        artifact_path = artifact.get('artifactPath')
        if not isinstance(artifact_path, str):
            _fail('ARTIFACT_PIN', path, 'Module artifactPath is missing')
        source_path = inside(task_root, artifact_path)
        raw = read(source_path, FILE_BYTES)
        if len(raw) != size or sha(raw) != digest:
            _fail('ARTIFACT_PIN', path, 'Module output changed after read-only classification')
        record = {'classId': class_id, 'path': path, 'sha256': digest, 'bytes': size,
                  'classification': classification, 'sourceUnitIds': expected_units,
                  'sourceMemberIds': expected_members,
                  'priorStatus': checked.get('priorStatus'),
                  'completenessDiagnostics': checked.get('completenessDiagnostics', [])}
        file_pins.append(record)
        if classification == 'generated_unreviewed':
            copy_rows.append((source_path, record))
        else:
            missing_class_ids.append(class_id)
    summary = {'moduleId': module_id, 'priorState': row['status'], 'oldManifestSha256': manifest_sha,
               'taskManifestSha256': task_manifest_sha, 'taskReceipt': task_receipt_fields,
               'classification': receipt.get('classification'),
               'classificationCounts': receipt.get('classificationCounts', {}),
               'files': file_pins, 'missingClassIds': missing_class_ids,
               'compilation': manifest.get('compilation', 'unknown'),
               'runtime': manifest.get('runtime', 'unknown'),
               'acceptance': manifest.get('acceptance', 'unknown')}
    return summary, copy_rows


def reassemble(pipeline_root, output_root, *, allow_incomplete=False):
    """Reclassify terminal modules and assemble a new, unreviewed candidate.

    The pipeline, original module manifests, module files, and previous
    UnityProject are read-only inputs. Incomplete work is rejected before an
    output directory is created.
    """
    pipeline = safe(pipeline_root)
    output = safe(output_root)
    if output.exists():
        _fail('OUTPUT_EXISTS', output, 'Use a fresh output directory for reassembly')
    request_raw, state_raw, request, state, stage, pins = _validate_pipeline(pipeline,allow_incomplete)
    source_root = safe(stage['request']['sourceRoot'])
    for input_root in (pipeline, stage['root'], source_root):
        if output == input_root or output.is_relative_to(input_root) or input_root.is_relative_to(output):
            _fail('OUTPUT_OVERLAP', output, 'Reassembly output must not overlap pipeline, architecture, or source inputs')

    module_reports = []
    selected_rows = []
    seen_class_ids = set()
    seen_class_paths = set()
    for row in state['modules']:
        if row['status'] not in TERMINAL_MODULE_STATES:
            # Explicit integration checkpoint: keep every unfinished class in
            # coverage, without creating a type shell or upgrading its status.
            planned=[c for c in stage['plan']['classes'] if c['module']==row['id']]
            summary=dict(moduleId=row['id'],priorState=row['status'],classification='not_generated',
                files=[dict(classId=c['id'],path=stage['validation']['classPaths'][c['id']],
                    classification='not_generated',reason='Module has no terminal implementation receipt') for c in planned],
                missingClassIds=[c['id'] for c in planned])
            selected=[]
        else:
            summary, selected = _recheck_module(pipeline, row, stage)
        for item in summary['files']:
            if item['classId'] in seen_class_ids or item['path'] in seen_class_paths:
                _fail('DUPLICATE_OWNER', item['path'], 'Multiple module receipts claim a global class or target path')
            seen_class_ids.add(item['classId'])
            seen_class_paths.add(item['path'])
        module_reports.append(summary)
        selected_rows.extend(selected)
    planned_class_ids = {row['id'] for row in stage['plan']['classes']}
    if seen_class_ids != planned_class_ids:
        missing_ids = sorted(planned_class_ids - seen_class_ids)
        extra_ids = sorted(seen_class_ids - planned_class_ids)
        _fail('RECHECK_COVERAGE', pipeline, f'Module receipts differ from global plan classes (missing={missing_ids[:8]!r}, extra={extra_ids[:8]!r})')
    if len({item[1]['path'] for item in selected_rows}) != len(selected_rows):
        _fail('DUPLICATE_OWNER', pipeline, 'Two module receipts claim the same generated target path')
    from .code_architecture_pipeline import task_root as resolve_task_root
    for row in state['modules']:
        if row['status'] in TERMINAL_MODULE_STATES and row['status']!='evidence_only':
            task=resolve_task_root(pipeline,row,request)
            if output==task or output.is_relative_to(task) or task.is_relative_to(output):
                _fail('OUTPUT_OVERLAP',output,'Reassembly must not overlap reused module evidence')

    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700)
    try:
        aggregate = output / 'Implementation'
        aggregate.mkdir(mode=0o700)
        aggregate_files = []
        total_bytes = 0
        for source_path, pin in selected_rows:
            # The receipt was already checked. Re-read immediately before copy and
            # again after copy so classification cannot race a source mutation.
            raw = read(source_path, FILE_BYTES)
            if len(raw) != pin['bytes'] or sha(raw) != pin['sha256']:
                _fail('SOURCE_RACE', pin['path'], 'Module output changed after recheck')
            total_bytes += len(raw)
            if total_bytes > WHOLE_BYTES:
                _fail('OUTPUT_BUDGET', pin['path'], 'Reassembled generated implementation exceeds byte budget')
            target = inside(aggregate, pin['path'])
            copy_verified(source_path, target, pin['sha256'], pin['bytes'])
            if sha(read(source_path, FILE_BYTES)) != pin['sha256'] or sha(read(target, FILE_BYTES)) != pin['sha256']:
                _fail('SOURCE_RACE', pin['path'], 'Source or copied output changed during reassembly')
            aggregate_files.append({
                'path': pin['path'], 'sha256': pin['sha256'], 'bytes': pin['bytes'],
                'owner': 'generated', 'classId': pin['classId'],
                'sourceUnitIds': pin['sourceUnitIds'], 'sourceMemberIds': pin['sourceMemberIds'],
                'status': 'partial', 'unresolved': ['Generated output remains semantically unreviewed.'],
            })
        aggregate_manifest = {
            'schemaVersion': 1,
            'sourceManifestSha256': pins['sourceManifestSha256'],
            'architectureSha256': pins['architectureSha256'],
            'files': aggregate_files,
            'modules': [{'id': item['moduleId'],
                         'status': 'evidence_only' if item['priorState'] == 'evidence_only' else 'partial',
                         **({'taskManifestSha256': item['taskManifestSha256'],
                             'workerStatus': item['taskReceipt']['status'],
                             'outcome': item['taskReceipt']['outcome'],
                             'responseSummary': item['taskReceipt']['responseSummary'],
                             'unresolved': item['taskReceipt']['unresolved']}
                            if item.get('taskReceipt') else {})}
                        for item in module_reports],
            'compilation': 'not_run', 'runtime': 'not_run',
            'acceptance': 'generated_unreviewed_reclassified',
        }
        aggregate_raw = encoded(aggregate_manifest)
        (aggregate / 'manifest.json').write_bytes(aggregate_raw)
        aggregate_sha = sha(aggregate_raw)

        assembly = assemble_native_candidate(
            source_root, pins['sourceManifestSha256'], stage['root'] / 'architecture.json',
            pins['architectureSha256'], stage['root'] / 'validation.json', pins['validationSha256'],
            aggregate, aggregate_sha, output / 'UnityProject',
            external_references=request.get('externalReferences', {}),
            retained_support_paths=request.get('retainedSupportPaths', ()), allow_partial=True)

        # Carry the exact worker receipt limitations into the standard Unity
        # candidate manifest so downstream handoff does not lose per-module gaps.
        unity_manifest_path = output / 'UnityProject/manifest.json'
        unity_manifest = _json(unity_manifest_path, maximum=MAX_PIPELINE_JSON)
        unity_manifest['moduleReceipts'] = [
            {'moduleId': item['moduleId'], 'taskManifestSha256': item['taskManifestSha256'],
             **item['taskReceipt']}
            for item in module_reports if item.get('taskReceipt')
        ]
        write_json(unity_manifest_path, unity_manifest)

        # Revalidate the immutable global and per-module state after assembly.
        if read(inside(pipeline, 'request.json'), MAX_PIPELINE_JSON) != request_raw:
            _fail('SOURCE_RACE', pipeline, 'Pipeline request changed during reassembly')
        if read(inside(pipeline, 'state.json'), MAX_PIPELINE_JSON) != state_raw:
            _fail('SOURCE_RACE', pipeline, 'Pipeline state changed during reassembly')
        stage_after = modules._pin_stage(request['architectureStage'])
        if stage_after['pins'] != pins:
            _fail('SOURCE_RACE', stage['root'], 'Global architecture/source pins changed during reassembly')
        for row in state['modules']:
            if row['status'] == 'evidence_only' or row['status'] not in TERMINAL_MODULE_STATES:
                continue
            task = resolve_task_root(pipeline,row,request)
            raw = read(inside(task, modules.MANIFEST), FILE_BYTES)
            if sha(raw) != row['manifestSha256']:
                _fail('SOURCE_RACE', row['id'], 'Old module manifest changed during reassembly')
            module_summary = next(item for item in module_reports if item['moduleId'] == row['id'])
            task_raw = read(inside(task, 'Task/manifest.json'), FILE_BYTES)
            if sha(task_raw) != module_summary['taskManifestSha256']:
                _fail('TASK_RECEIPT_RACE', row['id'], 'Task manifest changed after read-only reclassification')
        for source_path, pin in selected_rows:
            source_raw = read(source_path, FILE_BYTES)
            copied_raw = read(inside(output / 'Implementation', pin['path']), FILE_BYTES)
            if (len(source_raw) != pin['bytes'] or sha(source_raw) != pin['sha256']
                    or len(copied_raw) != pin['bytes'] or sha(copied_raw) != pin['sha256']):
                _fail('SOURCE_RACE', pin['path'], 'Rechecked source or new aggregate changed before report publication')

        missing = [file for module in module_reports for file in module['files']
                   if file['classification'] != 'generated_unreviewed']
        report = {
            'schemaVersion': 'monkey-native-architecture-reclassification/1',
            'status': 'candidate_assembled_unvalidated',
            'implementationStatus': 'partial_unreviewed',
            'pipelineStatus': state.get('status'),
            'incompleteCheckpoint': any(row['status'] not in TERMINAL_MODULE_STATES for row in state['modules']),
            'globalPins': pins,
            'pipelineRequestSha256': sha(request_raw),
            'pipelineStateSha256': sha(state_raw),
            'modules': module_reports,
            'generatedFilePins': [row[1] for row in selected_rows],
            'missingOrRejectedFiles': missing,
            'implementationRoot': 'Implementation',
            'unityProjectRoot': 'UnityProject',
            'unityProjectManifestSha256': sha(read(output / 'UnityProject/manifest.json', MAX_PIPELINE_JSON)),
            'compileStatus': 'not_run',
            'runtimeStatus': 'not_run',
            'semanticReview': 'not_performed',
            'assemblyStatus': assembly['status'],
            'limitations': [
                'Generated code remains unreviewed; lexical reclassification does not prove behavior.',
                'Unity compilation, Editor integration, and runtime behavior were not run.',
            ],
        }
        write_json(output / 'reclassification.json', report)
        return report
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise
