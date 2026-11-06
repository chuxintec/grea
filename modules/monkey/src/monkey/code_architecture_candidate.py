"""Assemble an isolated native Unity candidate from validated architecture outputs.

This module copies only frozen project resources/settings and manifest-owned
architecture implementation files. It never runs source code, Unity, or Codex.
"""
from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

from .io import encoded, inside, load, read, safe, sha, write_json
from .output_limits import FILE_BYTES, WHOLE_BYTES, copy_verified
from .sources.compiled import fail

LAYERS = ('Domain', 'Gameplay', 'Presentation', 'Services', 'Bootstrap')
LAYER_REFS = {
    'Domain': (),
    'Gameplay': ('Game.Domain',),
    'Presentation': ('Game.Domain', 'Game.Gameplay'),
    'Services': ('Game.Domain', 'Game.Gameplay'),
    'Bootstrap': ('Game.Domain', 'Game.Gameplay', 'Game.Presentation', 'Game.Services'),
}
MAX_FILES = 200_000
MAX_MANIFEST = 128 * 1024 * 1024
SHA_RE = re.compile(r'^[0-9a-f]{64}$')
NATIVE_LAYOUT_SUPPORT = frozenset({
    'IntrinsicGridLayoutGroup', 'NativeLinearLayoutGroup',
    'NativeRectConstraints', 'NativeTextLineBox', 'NativeHorizontalProgressFill',
})
EXTERNAL_INIT_PROFILE_EVIDENCE = {
    'schemaVersion': 1,
    'targetProfile': 'unity-6000.6.2f1-ugui',
    'languageVersion': 9,
    'apiCompatibility': 'netstandard2.1',
    'defines': [],
    'isExternalInit': 'missing',
    'evidenceId': 'NativeAudioNativeProbe01/Evidence/editor-compile.rsp',
    'evidenceSha256': 'b9389a49a3c1afa8334ae777369c85bfe3b646f69dc201dc759b7e80b860932b',
}
EXTERNAL_INIT_PATH = 'Assets/Game/Domain/CompilerSupport/IsExternalInit.cs'
EXTERNAL_INIT_ID = 'compiler-compatibility:System.Runtime.CompilerServices.IsExternalInit'
EXTERNAL_INIT_SOURCE = (b'namespace System.Runtime.CompilerServices\n'
    b'{\n'
    b'    public static class IsExternalInit\n'
    b'    {\n'
    b'    }\n'
    b'}\n')


def script_guid(namespace, root_namespace, class_id):
    """Stable type identity, independent of output location or implementation bytes."""
    return uuid.uuid5(uuid.NAMESPACE_URL,
        f'monkey-native-architecture-script:{namespace}:{root_namespace}:{class_id}').hex


def _generated_meta(namespace, root_namespace, identity, script=False):
    guid = (script_guid(namespace, root_namespace, identity) if script else
        uuid.uuid5(uuid.NAMESPACE_URL,
            f'monkey-native-architecture-assembly:{namespace}:{root_namespace}:{identity}').hex)
    return f'fileFormatVersion: 2\nguid: {guid}\n'.encode('utf-8'), guid


def _fail(code, location, message):
    fail('ARCH_CANDIDATE_' + code, str(location), message)


def _pinned_json(path, expected, label):
    if not isinstance(expected, str) or not SHA_RE.fullmatch(expected):
        _fail('PIN', path, f'{label} requires an exact lowercase SHA-256')
    raw = read(safe(path), MAX_MANIFEST)
    if sha(raw) != expected:
        _fail('CHANGED', path, f'{label} bytes do not match the supplied SHA-256')
    return load(raw, max_nodes=8_000_000), raw


def _relative(value, location):
    if not isinstance(value, str) or not value or '\\' in value or value.startswith('/'):
        _fail('PATH', location, 'Expected a portable relative path')
    parts = value.split('/')
    if any(p in ('', '.', '..') for p in parts) or re.match(r'^[A-Za-z]:', value):
        _fail('PATH', location, 'Path must not traverse or contain empty components')
    return value


def _rows(manifest, location):
    rows = manifest.get('files') if isinstance(manifest, dict) else None
    if not isinstance(rows, list) or len(rows) > MAX_FILES:
        _fail('MANIFEST', location, 'Manifest must contain a bounded files array')
    result = {}
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            _fail('MANIFEST', f'{location}[{i}]', 'File row must be an object')
        path = _relative(row.get('path'), f'{location}[{i}].path')
        if path in result:
            _fail('MANIFEST', path, 'Duplicate manifest path')
        if not isinstance(row.get('sha256'), str) or not SHA_RE.fullmatch(row['sha256']):
            _fail('MANIFEST', path, 'File row needs a lowercase SHA-256')
        if type(row.get('bytes')) is not int or row['bytes'] < 0 or row['bytes'] > FILE_BYTES:
            _fail('MANIFEST', path, 'File row has invalid or oversized byte count')
        result[path] = row
    return result


def _read_owned(root, path, row, label):
    source = inside(root, path)
    raw = read(source, FILE_BYTES)
    if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
        _fail('SOURCE_CHANGED', path, f'{label} bytes differ from the pinned manifest')
    return source, raw


def _check_root_inventory(root, rows, label):
    actual = set()
    for item in root.rglob('*'):
        safe(item)
        if item.is_file():
            relative = item.relative_to(root).as_posix()
            if relative != 'manifest.json':
                actual.add(relative)
    if actual != set(rows):
        missing = sorted(set(rows) - actual)
        extra = sorted(actual - set(rows))
        _fail('INVENTORY', root, f'{label} differs from its manifest (missing={missing[:5]!r}, extra={extra[:5]!r})')


def _retained_project_path(path):
    """Keep Content resources (including metadata), ProjectSettings, and package locks."""
    if path.startswith('Assets/Game/Content/') or path in {
        'Assets.meta', 'Assets/Game.meta', 'Assets/Game/Content.meta',
    }:
        return True
    if path.startswith('ProjectSettings/'):
        return True
    return path in ('Packages/manifest.json', 'Packages/packages-lock.json')


def _class_name(plan):
    classes = plan.get('classes') if isinstance(plan, dict) else None
    if not isinstance(classes, list):
        _fail('PLAN', '$plan.classes', 'Architecture plan requires a classes array')
    result = {}
    for row in classes:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not isinstance(row.get('name'), str):
            _fail('PLAN', '$plan.classes', 'Each class requires string id and name')
        if row['id'] in result:
            _fail('PLAN', row['id'], 'Duplicate class id')
        result[row['id']] = row['name']
    return result


def _declares_type(raw, expected_name, path):
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        _fail('UTF8', path, 'Implementation file must be UTF-8')
    # A lexical declaration check prevents empty/comment-only placeholder files.
    text = re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', ' ', text)
    declaration = re.search(r'\b(class|struct|interface|enum|record)\s+' + re.escape(expected_name) + r'\b', text)
    if not declaration:
        return False
    if declaration.group(1) in ('class', 'struct'):
        tail = text[declaration.end():]
        if re.match(r'[^{};]*\{\s*\}', tail):
            return False
    return True


def _planned_member_ids(class_row):
    ids = set()
    for key in ('fields', 'methods'):
        rows = class_row.get(key)
        if not isinstance(rows, list):
            _fail('PLAN', class_row.get('id', '$plan.classes'), f'{key} must be an array')
        for row in rows:
            if not isinstance(row, dict):
                _fail('PLAN', class_row.get('id', '$plan.classes'), f'{key} entries must be objects')
            values = row.get('sourceMemberIds', [])
            if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
                _fail('PLAN', class_row.get('id', '$plan.classes'), 'sourceMemberIds must be string arrays')
            if len(values) != len(set(values)):
                _fail('PLAN', class_row.get('id', '$plan.classes'), 'sourceMemberIds cannot contain duplicates')
            ids.update(values)
    return ids


def _guid_from_meta(raw, path):
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        _fail('META', path, 'Unity .meta files must be UTF-8')
    match = re.search(r'^guid:\s*([0-9a-fA-F]{32})\s*$', text, re.MULTILINE)
    if not match:
        _fail('META', path, 'Unity resource meta requires a 32-hex GUID')
    return match.group(1).lower()


def _asmdef(layer, external_refs):
    refs = list(LAYER_REFS[layer]) + list(external_refs.get(layer, ()))
    doc = {
        'name': 'Game.' + layer,
        'rootNamespace': 'Game.' + layer,
        'references': refs,
        'includePlatforms': [],
        'excludePlatforms': [],
        'allowUnsafeCode': False,
        'overrideReferences': False,
        'precompiledReferences': [],
        'autoReferenced': True,
        'defineConstraints': [],
        'versionDefines': [],
        'noEngineReferences': layer in ('Domain', 'Gameplay'),
    }
    return encoded(doc)


def _requires_external_init(raw, path):
    from .code_architecture_modules import _strip_csharp_comments_and_literals
    code = _strip_csharp_comments_and_literals(raw)
    if code is None:
        _fail('UTF8', path, 'Architecture source must be UTF-8')
    record = re.search(r'\brecord\s+(?:(?:class|struct)\s+)?[A-Za-z_][A-Za-z0-9_]*\b', code)
    init_accessor = re.search(r'\binit\s*(?:;|\{)', code)
    return bool(record or init_accessor)


def _declares_external_init(raw, path):
    from .code_architecture_modules import _strip_csharp_comments_and_literals, _namespace_blocks, _joined_namespace
    code = _strip_csharp_comments_and_literals(raw)
    if code is None:
        _fail('UTF8', path, 'Architecture source must be UTF-8')
    for namespace in _namespace_blocks(code):
        if _joined_namespace([namespace]) != 'System.Runtime.CompilerServices':
            continue
        if re.search(r'\b(?:class|struct)\s+IsExternalInit\b', code[namespace['open']:namespace['close']]):
            return True
    return False


def assemble_native_candidate(candidate_root, candidate_manifest_sha256,
                              plan_path, plan_sha256,
                              validation_path, validation_sha256,
                              module_root, module_manifest_sha256,
                              output_root, *, external_references=None,
                              allow_partial=False, retained_support_paths=()):
    """Build a new Unity candidate from pinned plan/validation/module outputs.

    Module manifest file rows use ``path``, ``sha256``, ``bytes``, ``classId``,
    ``sourceUnitIds``, ``sourceMemberIds`` and ``status``. Status is ``complete``
    or explicit ``partial``. A partial result is never presented as compiled.
    """
    candidate = safe(candidate_root)
    modules_root = safe(module_root)
    output = safe(output_root)
    candidate_manifest, candidate_manifest_raw = _pinned_json(
        candidate / 'manifest.json', candidate_manifest_sha256, 'candidate manifest')
    plan, plan_raw = _pinned_json(plan_path, plan_sha256, 'architecture plan')
    validation, validation_raw = _pinned_json(validation_path, validation_sha256, 'architecture validation')
    module_manifest, module_manifest_raw = _pinned_json(
        modules_root / 'manifest.json', module_manifest_sha256, 'module manifest')
    if plan.get('schemaVersion') != 'monkey-native-code-architecture/1':
        _fail('PLAN', plan_path, 'Unsupported architecture plan schema')
    if (candidate_manifest.get('schemaVersion') != 1
            or candidate_manifest.get('targetProfile') != 'unity-6000.6.2f1-ugui'
            or not isinstance(candidate_manifest.get('namespace'), str)
            or not candidate_manifest['namespace'].strip()):
        _fail('CANDIDATE_PROFILE', candidate, 'Pinned input must be a schema-1 Unity candidate with a non-empty namespace')
    source_manifest_pin = plan.get('sourceManifestSha256')
    if not isinstance(source_manifest_pin, str) or not SHA_RE.fullmatch(source_manifest_pin):
        _fail('PLAN', plan_path, 'Architecture plan must pin its source manifest SHA-256')
    if source_manifest_pin != candidate_manifest_sha256:
        _fail('PLAN_SOURCE_PIN', plan_path, 'Architecture plan sourceManifestSha256 differs from Candidate07 manifest pin')
    if module_manifest.get('sourceManifestSha256') != candidate_manifest_sha256:
        _fail('MODULE_SOURCE_PIN', module_root, 'Module manifest sourceManifestSha256 differs from the Candidate07 manifest pin')
    if module_manifest.get('architectureSha256') != plan_sha256:
        _fail('MODULE_ARCHITECTURE_PIN', module_root, 'Module manifest architectureSha256 differs from the pinned plan')
    if validation.get('valid') is not True or not isinstance(validation.get('classPaths'), dict):
        _fail('VALIDATION', validation_path, 'Validation must be successful and provide classPaths')
    candidate_rows = _rows(candidate_manifest, 'candidate manifest.files')
    module_rows = _rows(module_manifest, 'module manifest.files')
    _check_root_inventory(candidate, candidate_rows, 'Candidate file inventory')
    _check_root_inventory(modules_root, module_rows, 'Module file inventory')
    paths = validation['classPaths']
    class_names = _class_name(plan)
    if set(paths) != set(class_names):
        _fail('CLASS_PATHS', validation_path, 'Validated classPaths must cover exactly the planned classes')

    expected_class_paths = {}
    planned_classes = {row['id']: row for row in plan['classes']}
    for class_id, path in paths.items():
        path = _relative(path, f'classPaths.{class_id}')
        match = re.fullmatch(r'Assets/Game/(Domain|Gameplay|Presentation|Services|Bootstrap)/([A-Za-z0-9_./]+)/([A-Za-z_][A-Za-z0-9_]*).cs', path)
        if not match or any(part in ('.', '..') for part in path.split('/')):
            _fail('CLASS_PATHS', path, 'Class path must be planned under a native layer directory')
        planned = planned_classes[class_id]
        planned_units = planned.get('sourceUnitIds')
        if not isinstance(planned_units, list) or any(not isinstance(value, str) or not value for value in planned_units):
            _fail('PLAN', class_id, 'Planned class sourceUnitIds must be a string array')
        expected = ('Assets/Game/' + planned['layer'] + '/' + planned['module'].replace('.', '/')
                    + '/' + planned['name'] + '.cs')
        if path != expected:
            _fail('CLASS_PATHS', path, f'Validated class path differs from deterministic plan path {expected!r}')
        expected_class_paths[class_id] = path
    expected_assembly_refs = {
        'Domain': [], 'Gameplay': ['Domain'], 'Presentation': ['Domain', 'Gameplay'],
        'Services': ['Domain', 'Gameplay'], 'Bootstrap': ['Domain', 'Gameplay', 'Presentation', 'Services'],
    }
    if validation.get('assemblyReferences') != expected_assembly_refs:
        _fail('VALIDATION', validation_path, 'Validation assembly reference matrix differs from the fixed five-layer graph')

    module_records = module_manifest.get('modules', [])
    if not isinstance(module_records, list):
        _fail('MODULES', module_root, 'modules must be an array when present')
    module_status = {}
    for row in module_records:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str):
            _fail('MODULES', module_root, 'Module status row requires an id')
        if row['id'] in module_status:
            _fail('MODULES', row['id'], 'Duplicate module status')
        module_status[row['id']] = row.get('status')

    implementations = {}
    partials = []
    for path, row in module_rows.items():
        if row.get('owner', 'generated') != 'generated':
            _fail('MODULE_OWNER', path, 'Module outputs must be generated-owned')
        if not path.endswith('.cs') or path not in expected_class_paths.values():
            _fail('MODULE_PATH', path, 'Module manifest may contain only validated planned class paths')
        class_id = row.get('classId')
        if not isinstance(class_id, str) or expected_class_paths.get(class_id) != path:
            _fail('MODULE_CLASS', path, 'classId must map to this validated class path')
        status = row.get('status')
        if status not in ('complete', 'partial'):
            _fail('MODULE_STATUS', path, 'Class status must be complete or explicit partial')
        for key in ('sourceUnitIds', 'sourceMemberIds'):
            values = row.get(key)
            if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
                _fail('MODULE_MAPPING', path, f'{key} must be a string array')
            if len(values) != len(set(values)):
                _fail('MODULE_MAPPING', path, f'{key} cannot contain duplicates')
        class_row = planned_classes[class_id]
        expected_units = set(class_row.get('sourceUnitIds', []))
        actual_units = set(row['sourceUnitIds'])
        if not actual_units.issubset(expected_units):
            _fail('MODULE_MAPPING', path, 'sourceUnitIds may not exceed planned class source units')
        expected_members = _planned_member_ids(class_row)
        actual_members = set(row['sourceMemberIds'])
        if not actual_members.issubset(expected_members):
            _fail('MODULE_MAPPING', path, 'sourceMemberIds may not exceed planned class field/method source members')
        missing_units = expected_units - actual_units
        missing_members = expected_members - actual_members
        for key, missing_ids in (('unresolvedSourceUnitIds', missing_units),
                                 ('unresolvedSourceMemberIds', missing_members)):
            declared = row.get(key, [])
            if (not isinstance(declared, list) or any(not isinstance(value, str) for value in declared)
                    or set(declared) != missing_ids or len(declared) != len(set(declared))):
                _fail('MODULE_MAPPING', path, f'{key} must exactly list the omitted planned IDs')
        if status == 'complete' and (missing_units or missing_members):
            _fail('MODULE_MAPPING', path, 'Complete implementation must cover every planned source unit and member')
        unresolved_reasons = row.get('unresolved', [])
        if not isinstance(unresolved_reasons, list) or any(not isinstance(value, str) or not value.strip() for value in unresolved_reasons):
            _fail('MODULE_MAPPING', path, 'unresolved must be an array of specific text reasons')
        if status == 'partial' and not (missing_units or missing_members or unresolved_reasons):
            _fail('MODULE_MAPPING', path, 'Partial implementation must record specific unresolved IDs or reasons')
        source_path, raw = _read_owned(modules_root, path, row, 'Module source')
        if not raw.strip() or not _declares_type(raw, class_names[class_id], path):
            _fail('EMPTY_IMPLEMENTATION', path, 'Output must declare its planned type; empty placeholders are rejected')
        implementations[path] = (source_path, row, raw)
        if status == 'partial':
            partials.append(path)
    missing = sorted(set(expected_class_paths.values()) - set(implementations))
    if missing and not allow_partial:
        _fail('MISSING_IMPLEMENTATION', output, f'Module outputs omit planned class files: {missing[:12]!r}')

    needs_external_init = any(_requires_external_init(raw, path)
                              for path, (_source, _row, raw) in implementations.items())
    duplicate_external_init = any(_declares_external_init(raw, path)
                                  for path, (_source, _row, raw) in implementations.items())
    if duplicate_external_init:
        _fail('COMPILER_SUPPORT_DUPLICATE', output,
              'Compiler compatibility types must not be declared inside planned or retained implementation files')
    if needs_external_init and EXTERNAL_INIT_PROFILE_EVIDENCE['isExternalInit'] != 'missing':
        _fail('COMPILER_SUPPORT_PROFILE', output, 'Pinned compiler profile does not authorize the IsExternalInit shim')
    compiler_support = None
    if needs_external_init:
        support_meta_path = EXTERNAL_INIT_PATH + '.meta'
        if (EXTERNAL_INIT_PATH in candidate_rows or support_meta_path in candidate_rows
                or EXTERNAL_INIT_PATH in module_rows or support_meta_path in module_rows
                or EXTERNAL_INIT_PATH in expected_class_paths.values()):
            _fail('COMPILER_SUPPORT_PATH', EXTERNAL_INIT_PATH,
                  'Compiler support path is reserved and cannot be a candidate resource or planned class')
        compiler_support = {'kind': 'compiler-compatibility-support',
                            'status': 'generated',
                            'profileEvidence': dict(EXTERNAL_INIT_PROFILE_EVIDENCE),
                            'featureUse': 'record-or-init', 'path': EXTERNAL_INIT_PATH}

    if (not isinstance(retained_support_paths, (list, tuple))
            or any(not isinstance(value, str) for value in retained_support_paths)
            or len(set(retained_support_paths)) != len(retained_support_paths)):
        _fail('SUPPORT_PATHS', output, 'retained_support_paths must be a unique list of candidate paths')
    support_pairs = {}
    for value in retained_support_paths:
        path = _relative(value, 'retained_support_paths')
        match = re.fullmatch(r'Assets/Game/Presentation/Common/Layout/([A-Za-z_][A-Za-z0-9_]*)(\.cs(?:\.meta)?|\.meta)', path)
        if not match or match.group(1) not in NATIVE_LAYOUT_SUPPORT:
            _fail('SUPPORT_PATHS', path, 'Only approved native Presentation/Common/Layout helpers may be retained')
        support_pairs.setdefault(match.group(1), set()).add(match.group(2))
    for name, suffixes in support_pairs.items():
        if suffixes != {'.cs', '.cs.meta'}:
            _fail('SUPPORT_PATHS', name, 'Native support scripts must be selected with their adjacent .cs.meta')
    support_files = []
    for name in sorted(support_pairs):
        for suffix in ('.cs', '.cs.meta'):
            path = f'Assets/Game/Presentation/Common/Layout/{name}{suffix}'
            row = candidate_rows.get(path)
            if not row:
                _fail('SUPPORT_PATHS', path, 'Selected native support file must be in the frozen Candidate07 manifest')
            source_path, raw = _read_owned(candidate, path, row, 'Native support source')
            if suffix == '.cs' and (not raw.strip() or not re.search(rb'\b(?:class|struct)\b', raw)):
                _fail('SUPPORT_PATHS', path, 'Native support source must contain a native helper type')
            support_files.append((path, source_path, row, raw))
    if any(_declares_external_init(raw, path) for path, _source, _row, raw in support_files if path.endswith('.cs')):
        _fail('COMPILER_SUPPORT_DUPLICATE', output,
              'Compiler compatibility types must not be declared inside planned or retained implementation files')
    collisions = set(expected_class_paths.values()) & {path for path, *_ in support_files}
    if collisions:
        _fail('SUPPORT_PATHS', output, f'Native support files collide with planned class outputs: {sorted(collisions)!r}')

    if external_references is None:
        external_references = {}
    if not isinstance(external_references, dict) or set(external_references) - set(LAYERS):
        _fail('EXTERNAL_REFERENCES', output, 'External references must be explicitly keyed by architecture layer')
    normalized_refs = {}
    for layer, values in external_references.items():
        if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
            _fail('EXTERNAL_REFERENCES', layer, 'External assembly references must be explicit non-empty strings')
        normalized_refs[layer] = sorted(set(values))

    if output.exists():
        _fail('OUTPUT_EXISTS', output, 'Assembly requires a fresh output directory; existing output may contain manual edits')
    inputs = (candidate, modules_root, safe(plan_path), safe(validation_path))
    if any(output == root or output.is_relative_to(root) or root.is_relative_to(output) for root in inputs):
        _fail('OUTPUT_OVERLAP', output, 'Output must not overlap any input tree')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700)

    inventory = []
    script_identities = {}
    total_bytes = 0
    try:
        for path, row in candidate_rows.items():
            if not _retained_project_path(path):
                continue
            source_path, raw = _read_owned(candidate, path, row, 'Candidate resource')
            total_bytes += len(raw)
            if total_bytes > WHOLE_BYTES:
                _fail('OUTPUT_BUDGET', path, 'Assembled project exceeds byte budget')
            target = inside(output, path)
            copy_verified(source_path, target, row['sha256'], row['bytes'])
            inventory.append(dict(path=path, sha256=row['sha256'], bytes=row['bytes'], owner='retained',
                                  sourceKind='candidate-resource', provenance=dict(inputPath=path, inputOwner=row.get('owner', 'generated'))))
        guid_paths = {}
        for item in inventory:
            if item['path'].endswith('.meta'):
                guid = _guid_from_meta(read(inside(output, item['path']), FILE_BYTES), item['path'])
                if guid in guid_paths:
                    _fail('DUPLICATE_GUID', item['path'], f'GUID duplicates {guid_paths[guid]!r}')
                guid_paths[guid] = item['path']
        for path, source_path, row, raw in support_files:
            total_bytes += len(raw)
            if total_bytes > WHOLE_BYTES:
                _fail('OUTPUT_BUDGET', path, 'Assembled project exceeds byte budget')
            target = inside(output, path)
            copy_verified(source_path, target, row['sha256'], row['bytes'])
            if path.endswith('.meta'):
                guid = _guid_from_meta(raw, path)
                if guid in guid_paths:
                    _fail('DUPLICATE_GUID', path, f'GUID duplicates {guid_paths[guid]!r}')
                guid_paths[guid] = path
            inventory.append(dict(path=path, sha256=row['sha256'], bytes=row['bytes'], owner='retained',
                                  sourceKind='existing-implementation',
                                  provenance=dict(kind='native-layout-support', inputPath=path,
                                                  inputOwner=row.get('owner', 'generated'))))
        for path, (source_path, row, raw) in implementations.items():
            total_bytes += len(raw)
            if total_bytes > WHOLE_BYTES:
                _fail('OUTPUT_BUDGET', path, 'Assembled project exceeds byte budget')
            target = inside(output, path)
            copy_verified(source_path, target, row['sha256'], row['bytes'])
            inventory.append(dict(path=path, sha256=row['sha256'], bytes=row['bytes'], owner='generated',
                                  sourceKind='architecture-module',
                                  provenance=dict(classId=row['classId'], sourceUnitIds=row['sourceUnitIds'],
                                                  sourceMemberIds=row['sourceMemberIds'], status=row['status'],
                                                  unresolvedSourceUnitIds=row.get('unresolvedSourceUnitIds', []),
                                                  unresolvedSourceMemberIds=row.get('unresolvedSourceMemberIds', []),
                                                  unresolved=row.get('unresolved', []))))
            meta_path = path + '.meta'
            meta_raw, guid = _generated_meta(candidate_manifest['namespace'], plan.get('rootNamespace'), row['classId'], script=True)
            if guid in guid_paths:
                _fail('DUPLICATE_GUID', meta_path, f'Generated Script GUID duplicates {guid_paths[guid]!r}')
            guid_paths[guid] = meta_path
            total_bytes += len(meta_raw)
            if total_bytes > WHOLE_BYTES:
                _fail('OUTPUT_BUDGET', meta_path, 'Assembled project exceeds byte budget')
            inside(output, meta_path).write_bytes(meta_raw)
            inventory.append(dict(path=meta_path, sha256=sha(meta_raw), bytes=len(meta_raw), owner='generated',
                sourceKind='architecture-script-meta', provenance=dict(classId=row['classId'],
                    scriptPath=path, scriptSha256=row['sha256'], guid=guid)))
            script_identities[row['classId']] = dict(path=path, sha256=row['sha256'],
                metaPath=meta_path, metaSha256=sha(meta_raw), guid=guid, unityTypeStatus='not_compiled')
        if compiler_support is not None:
            path = EXTERNAL_INIT_PATH
            meta_path = path + '.meta'
            support_guid = script_guid(candidate_manifest['namespace'], plan.get('rootNamespace'), EXTERNAL_INIT_ID)
            if support_guid in guid_paths:
                _fail('DUPLICATE_GUID', meta_path,
                      f'Compiler support GUID duplicates {guid_paths[support_guid]!r}')
            source_raw = EXTERNAL_INIT_SOURCE
            source_path = inside(output, path); source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_bytes(source_raw)
            inventory.append(dict(path=path, sha256=sha(source_raw), bytes=len(source_raw), owner='generated',
                sourceKind='compiler-compatibility-support',
                provenance=dict(kind='compiler-compatibility-support', type='System.Runtime.CompilerServices.IsExternalInit',
                                profile=EXTERNAL_INIT_PROFILE_EVIDENCE['targetProfile'],
                                policy='emit-domain-shim-when-record-or-init-is-used')))
            meta_raw, meta_guid = _generated_meta(candidate_manifest['namespace'], plan.get('rootNamespace'),
                                                  EXTERNAL_INIT_ID, script=True)
            if meta_guid != support_guid:
                _fail('COMPILER_SUPPORT_GUID', meta_path, 'Compiler support GUID is not stable for its type identity')
            if meta_guid in guid_paths:
                _fail('DUPLICATE_GUID', meta_path, f'Compiler support GUID duplicates {guid_paths[meta_guid]!r}')
            guid_paths[meta_guid] = meta_path
            inside(output, meta_path).write_bytes(meta_raw)
            inventory.append(dict(path=meta_path, sha256=sha(meta_raw), bytes=len(meta_raw), owner='generated',
                sourceKind='compiler-compatibility-support-meta',
                provenance=dict(kind='compiler-compatibility-support-meta', scriptPath=path,
                                scriptSha256=sha(source_raw), guid=meta_guid)))
            compiler_support.update({'metaPath': meta_path, 'sha256': sha(source_raw),
                                     'metaSha256': sha(meta_raw), 'guid': meta_guid})
            total_bytes += len(source_raw) + len(meta_raw)
            if total_bytes > WHOLE_BYTES:
                _fail('OUTPUT_BUDGET', meta_path, 'Assembled project exceeds byte budget')
        for layer in LAYERS:
            path = f'Assets/Game/{layer}/{layer}.asmdef'
            raw = _asmdef(layer, normalized_refs)
            target = inside(output, path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            inventory.append(dict(path=path, sha256=sha(raw), bytes=len(raw), owner='generated',
                                  sourceKind='architecture-assembly', provenance=dict(layer=layer)))
            meta_path = path + '.meta'
            meta_raw, guid = _generated_meta(candidate_manifest['namespace'], plan.get('rootNamespace'), layer)
            if guid in guid_paths:
                _fail('DUPLICATE_GUID', meta_path, f'Generated assembly GUID duplicates {guid_paths[guid]!r}')
            guid_paths[guid] = meta_path
            total_bytes += len(raw) + len(meta_raw)
            if total_bytes > WHOLE_BYTES:
                _fail('OUTPUT_BUDGET', meta_path, 'Assembled project exceeds byte budget')
            inside(output, meta_path).write_bytes(meta_raw)
            inventory.append(dict(path=meta_path, sha256=sha(meta_raw), bytes=len(meta_raw), owner='generated',
                sourceKind='architecture-assembly-meta', provenance=dict(layer=layer, guid=guid)))

        if len(inventory)>MAX_FILES or len({row['path'].casefold() for row in inventory})!=len(inventory):
            _fail('OUTPUT_INVENTORY', output, 'Output file count or unique path ownership is invalid')

        # Recheck every source identity after copying, before publishing the manifest.
        if sha(read(candidate / 'manifest.json', MAX_MANIFEST)) != candidate_manifest_sha256:
            _fail('SOURCE_RECHECK', candidate, 'Candidate owning manifest changed during assembly')
        if sha(read(modules_root / 'manifest.json', MAX_MANIFEST)) != module_manifest_sha256:
            _fail('SOURCE_RECHECK', modules_root, 'Module owning manifest changed during assembly')
        if sha(read(safe(plan_path), MAX_MANIFEST)) != plan_sha256 or sha(read(safe(validation_path), MAX_MANIFEST)) != validation_sha256:
            _fail('SOURCE_RECHECK', output, 'Architecture plan or validation changed during assembly')
        for path, row in candidate_rows.items():
            if _retained_project_path(path):
                _read_owned(candidate, path, row, 'Candidate resource recheck')
        for path, (source_path, row, _raw) in implementations.items():
            _read_owned(modules_root, path, row, 'Module source recheck')
        for path, source_path, row, _raw in support_files:
            _read_owned(candidate, path, row, 'Native support source recheck')

        status = 'partial' if missing or partials or any(v in ('partial', 'blocked', 'missing') for v in module_status.values()) else 'assembled'
        report = {
            'schemaVersion': 1,
            'targetProfile': candidate_manifest['targetProfile'],
            'namespace': candidate_manifest['namespace'],
            'scopeMode': 'whole-input',
            'projectLayout': candidate_manifest.get('projectLayout', 'monkey-project/2.0.0'),
            'architectureSchemaVersion': 'monkey-native-architecture-candidate/1',
            'provenance': {
                'kind': 'native-architecture-assembly',
                'sourceCandidateManifestSha256': candidate_manifest_sha256,
                'architecturePlanSha256': plan_sha256,
                'architectureValidationSha256': validation_sha256,
                'moduleManifestSha256': module_manifest_sha256,
                'sourceManifestSha256': source_manifest_pin,
            },
            'status': status,
            'compiled': False,
            'compileStatus': 'not_run',
            'classPaths': expected_class_paths,
            'scriptIdentitySchema': 'monkey-native-script-identities/1',
            'scriptIdentities': script_identities,
            'compilerSupport': (compiler_support or {
                'kind': 'compiler-compatibility-support', 'status': 'not_required',
                'profileEvidence': dict(EXTERNAL_INIT_PROFILE_EVIDENCE),
                'featureUse': 'no-record-or-init-in-planned-source'}),
            'implementedClassPaths': sorted(implementations),
            'retainedSupportPaths': sorted(path for path, *_ in support_files),
            'missingClassPaths': missing,
            'partialClassPaths': sorted(partials),
            'moduleStatuses': module_status,
            'externalReferences': normalized_refs,
            'files': sorted(inventory, key=lambda row: row['path']),
            'excludedLegacyProductionCode': True,
            'sourceEvidenceInProductionPaths': False,
            'limitations': (["Some planned classes are missing implementations."] if missing else [])
                           + (["Some module outputs are explicitly partial."] if partials else [])
                           + ["Unity compilation and runtime behavior were not run or proven."],
        }
        write_json(output / 'manifest.json', report)
        return report
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise
