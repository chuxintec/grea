"""Apply a pinned native architecture revision to a fresh candidate copy.

This module has no apply-to-existing-project path and performs no AI, Unity,
package, installation, or build operations.
"""
from __future__ import annotations

import re
import shutil
import uuid

from . import code_architecture_modules as modules
from .candidate_snapshot import snapshot, verify
from .io import encoded, inside, load, read, safe, sha, write_json
from .output_limits import FILE_BYTES, WHOLE_BYTES, copy_verified
from .sources.compiled import fail

SCHEMA = 'monkey-native-architecture-revision/1'
LAYERS = frozenset({'Bootstrap', 'Domain', 'Gameplay', 'Presentation', 'Services'})
ROLES = frozenset({'replace', 'new-helper'})
SHA_RE = re.compile(r'^[0-9a-f]{64}$')
MAX_PLAN_BYTES = 128 * 1024 * 1024
MAX_ROWS = 100_000


def _fail(code, location, message):
    fail('CODE_ARCH_REVISION_' + code, str(location), message)


def _relative(value, location):
    if (not isinstance(value, str) or not value or '\\' in value or value.startswith('/')
            or re.match(r'^[A-Za-z]:', value) or any(part in ('', '.', '..') for part in value.split('/'))):
        _fail('PATH', location, 'Expected a canonical relative path without traversal')
    return value


def _layer_module(path, location):
    path = _relative(path, location)
    parts = path.split('/')
    if len(parts) < 5 or parts[:2] != ['Assets', 'Game'] or parts[2] not in LAYERS or not path.endswith('.cs'):
        _fail('TARGET_PATH', path, 'Revision targets must be C# files within the five native architecture layers')
    module_parts = parts[3:-1]
    type_name = parts[-1][:-3]
    identifier = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
    if (not module_parts or any(not identifier.fullmatch(part) for part in module_parts)
            or not identifier.fullmatch(type_name)):
        _fail('TARGET_PATH', path, 'Class path must identify a semantic type in its owner module directory')
    return parts[2], '.'.join(module_parts), type_name


def _type_identity(raw, path, expected_name):
    code = modules._strip_csharp_comments_and_literals(raw)
    if code is None:
        _fail('UTF8', path, 'Revision C# files must be UTF-8')
    declaration = re.search(r'\b(class|struct|interface|enum|record)\s+' + re.escape(expected_name) + r'\b', code)
    if declaration is None:
        _fail('SEMANTIC_TYPE', path, f'File must declare its path-owned type {expected_name!r}')
    namespaces = modules._namespace_blocks(code)
    owners = [row for row in namespaces if row['open'] < declaration.start() < row['close']]
    namespace = modules._joined_namespace(owners)
    if not namespace:
        _fail('SEMANTIC_OWNER', path, 'Architecture type must be inside a block namespace')
    return declaration.group(1), namespace


def _architecture_root_namespace(root, owned):
    roots = set()
    for path, row in owned.items():
        if not path.endswith('.cs'):
            continue
        if row.get('owner') != 'generated' or row.get('sourceKind') not in (
                'architecture-module', 'architecture-revision', 'architecture-revision-helper'):
            continue
        provenance = row.get('provenance')
        if not isinstance(provenance, dict) or not isinstance(provenance.get('classId'), str):
            continue
        layer, module, type_name = _layer_module(path, path)
        source = read(inside(root, path), FILE_BYTES)
        kind, namespace = _type_identity(source, path, type_name)
        suffix = f'.{layer}.{module}'
        if not namespace.endswith(suffix):
            _fail('SEMANTIC_OWNER', path, 'Existing architecture source namespace differs from its layer/module path')
        markers = modules._implementation_markers(source, {
            'name': type_name, 'kind': kind, 'layer': layer, 'namespace': namespace,
            'fields': [], 'plannedMethods': [],
        })
        owner_errors = {'file-scoped-namespace-not-allowed', 'block-namespace-missing',
                        'planned-type-or-namespace-declaration-missing',
                        'planned-type-not-namespace-level', 'planned-type-body-missing'}
        if any(marker in owner_errors for marker in markers):
            _fail('SEMANTIC_OWNER', path, 'Existing architecture owner lacks a namespace-level block-namespace type')
        root_namespace = namespace[:-len(suffix)]
        if not root_namespace:
            _fail('SEMANTIC_OWNER', path, 'Architecture namespace must include its root before layer/module segments')
        roots.add(root_namespace)
    if len(roots) != 1:
        _fail('SEMANTIC_OWNER', root, 'Cannot establish one consistent root namespace from verified architecture C# files')
    return next(iter(roots))


def _namespace_for_owner_module(root, owned, layer, module):
    root_namespace = _architecture_root_namespace(root, owned)
    return f'{root_namespace}.{layer}.{module}'


def _validate_csharp(raw, path, expected_type, layer, expected_namespace, expected_kind):
    kind, namespace = _type_identity(raw, path, expected_type)
    if kind != expected_kind or namespace != expected_namespace:
        _fail('SEMANTIC_OWNER', path, 'Type declaration kind or namespace differs from the verified original architecture owner')
    class_record = {'name': expected_type, 'kind': expected_kind, 'layer': layer,'module':_layer_module(path,path)[1],
                    'namespace': expected_namespace, 'fields': [], 'plannedMethods': []}
    markers = modules._implementation_markers(raw, class_record)
    owner_errors = {'invalid-utf8-csharp', 'file-scoped-namespace-not-allowed',
                    'block-namespace-missing', 'planned-type-or-namespace-declaration-missing',
                    'planned-type-not-namespace-level', 'planned-type-body-missing'}
    core_errors = ('core-engine-reference:', 'core-dynamic-keyword', 'core-untyped-string-object-dictionary','layer-dependency-reference:')
    if any(marker in owner_errors or marker.startswith(core_errors) for marker in markers):
        code = 'CORE_DEPENDENCY' if any(marker.startswith(core_errors) for marker in markers) else 'SEMANTIC_OWNER'
        _fail(code, path, 'Revision violates established architecture module checks: ' + ', '.join(markers))
    if expected_kind in ('class', 'struct'):
        code = modules._strip_csharp_comments_and_literals(raw)
        declaration = re.search(r'\b' + re.escape(expected_kind) + r'\s+' + re.escape(expected_type) + r'\b', code)
        body_open = code.find('{', declaration.end()) if declaration else -1
        body_close = modules._matching_brace(code, body_open) if body_open >= 0 else None
        if body_close is None or not code[body_open + 1:body_close].strip():
            _fail('EMPTY_TYPE', path, 'Revision may not replace/add an empty class or struct shell')


def _manifest_rows(manifest, location):
    rows = manifest.get('files') if isinstance(manifest, dict) else None
    if not isinstance(rows, list) or not rows or len(rows) > MAX_ROWS:
        _fail('MANIFEST', location, 'Expected a bounded non-empty candidate files array')
    result = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            _fail('MANIFEST', f'{location}[{index}]', 'File record must be an object')
        path = _relative(row.get('path'), f'{location}[{index}].path')
        if path in result:
            _fail('MANIFEST', path, 'Duplicate candidate file path')
        if not isinstance(row.get('sha256'), str) or not SHA_RE.fullmatch(row['sha256']):
            _fail('MANIFEST', path, 'Candidate file row requires lowercase SHA-256')
        if type(row.get('bytes')) is not int or not 0 <= row['bytes'] <= FILE_BYTES:
            _fail('MANIFEST', path, 'Candidate file row has invalid byte count')
        if row.get('owner') not in ('generated', 'retained', 'manual'):
            _fail('MANIFEST', path, 'Candidate file row has an unsupported owner')
        result[path] = row
    return result


def _read_pin(root, path, row, label):
    file_path = inside(root, path)
    raw = read(file_path, FILE_BYTES)
    if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
        _fail('SOURCE_CHANGED', path, f'{label} differs from its owning manifest')
    return file_path, raw


def _check_inventory(root, manifest_rows):
    actual = set()
    for path in root.rglob('*'):
        safe(path)
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            if relative != 'manifest.json':
                actual.add(relative)
    if actual != set(manifest_rows):
        _fail('INVENTORY', root, 'Candidate filesystem differs from its complete owning manifest')


def _verify_native_candidate(root, expected_manifest_sha256):
    base, manifest, owned, current_sha = snapshot(root)
    if current_sha != expected_manifest_sha256:
        _fail('BASE_PIN', base, 'Candidate manifest differs from the supplied base pin')
    provenance = manifest.get('provenance')
    if (manifest.get('schemaVersion') != 1 or manifest.get('targetProfile') != 'unity-6000.6.2f1-ugui'
            or manifest.get('architectureSchemaVersion') != 'monkey-native-architecture-candidate/1'
            or not isinstance(provenance, dict)
            or provenance.get('kind') != 'native-architecture-assembly'):
        _fail('CANDIDATE_KIND', base, 'Only an unadopted native architecture assembly candidate is supported')
    if any((base / path).exists() for path in (
            '.monkey/adoption/state.json', 'adoption-plan.json', 'adoption-result.json')):
        _fail('CANDIDATE_KIND', base, 'Adopted/formal project roots cannot be revised through this candidate API')
    architecture_sha = manifest['provenance'].get('architecturePlanSha256')
    if not isinstance(architecture_sha, str) or not SHA_RE.fullmatch(architecture_sha):
        _fail('CANDIDATE_KIND', base, 'Native candidate lacks its architecture plan identity')
    _check_inventory(base, owned)
    verify(base, owned)
    class_paths = manifest.get('classPaths')
    if class_paths is not None:
        if not isinstance(class_paths, dict) or any(not isinstance(cid, str) or not isinstance(path, str)
                                                    for cid, path in class_paths.items()):
            _fail('CLASS_PATHS', base, 'Candidate classPaths must map class IDs to relative paths')
        if len(set(class_paths.values())) != len(class_paths):
            _fail('CLASS_PATHS', base, 'Candidate classPaths contains duplicate target paths')
        for path in class_paths.values():
            _relative(path, 'classPaths')
        for path, row in owned.items():
            provenance = row.get('provenance')
            if (path.endswith('.cs') and row.get('owner') == 'generated'
                    and row.get('sourceKind') in ('architecture-module', 'architecture-revision', 'architecture-revision-helper')
                    and isinstance(provenance, dict) and isinstance(provenance.get('classId'), str)):
                if class_paths.get(provenance['classId']) != path:
                    _fail('CLASS_PATHS', path, 'Generated class file differs from its reserved classPaths identity')
    for key in ('implementedClassPaths', 'missingClassPaths'):
        paths = manifest.get(key)
        if paths is not None and (not isinstance(paths, list) or any(not isinstance(path, str) for path in paths)
                                  or len(paths) != len(set(paths))):
            _fail('CLASS_PATHS', base, f'{key} must be a unique path list when present')
        if paths is not None and class_paths is not None and not set(paths).issubset(set(class_paths.values())):
            _fail('CLASS_PATHS', base, f'{key} contains paths absent from classPaths')
    implemented_paths = manifest.get('implementedClassPaths')
    missing_paths = manifest.get('missingClassPaths')
    if implemented_paths is not None and missing_paths is not None and set(implemented_paths) & set(missing_paths):
        _fail('CLASS_PATHS', base, 'A class path cannot be both implemented and missing')
    if class_paths is not None:
        if implemented_paths is not None:
            for path in implemented_paths:
                row = owned.get(path)
                if (not row or row.get('owner') != 'generated'
                        or row.get('sourceKind') not in ('architecture-module', 'architecture-revision', 'architecture-revision-helper')):
                    _fail('CLASS_PATHS', path, 'implementedClassPaths must refer to an owned generated architecture class file')
        if missing_paths is not None:
            for path in missing_paths:
                if path in owned:
                    _fail('CLASS_PATHS', path, 'missingClassPaths must not refer to an existing owned file')
        if implemented_paths is not None and missing_paths is not None:
            if set(implemented_paths) | set(missing_paths) != set(class_paths.values()):
                _fail('CLASS_PATHS', base, 'implementedClassPaths and missingClassPaths must cover classPaths exactly')
    return base, manifest, owned, architecture_sha


def _guid(raw, path):
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        _fail('META', path, 'Unity meta must be UTF-8')
    match = re.search(r'^guid:\s*([0-9a-fA-F]{32})\s*$', text, re.MULTILINE)
    if not match:
        _fail('META', path, 'Unity meta needs a 32-hex GUID')
    return match.group(1).lower()


def _derived_meta(namespace, revision_id, path, plan_sha, used_guids):
    identity = f'monkey-native-revision:{namespace}:{revision_id}:{path}:{plan_sha}'
    guid = uuid.uuid5(uuid.NAMESPACE_URL, identity).hex
    if guid in used_guids:
        _fail('DUPLICATE_GUID', path, 'Deterministic helper GUID collides with an existing Unity asset GUID')
    return f'fileFormatVersion: 2\nguid: {guid}\n'.encode('utf-8'), guid


def _load_revision_plan(revision_root, expected_sha):
    root = safe(revision_root)
    plan_path = inside(root, 'revision-plan.json')
    raw = read(plan_path, MAX_PLAN_BYTES)
    if not isinstance(expected_sha, str) or not SHA_RE.fullmatch(expected_sha) or sha(raw) != expected_sha:
        _fail('REVISION_PIN', plan_path, 'Revision plan differs from its exact SHA-256 pin')
    plan = load(raw, max_nodes=2_000_000)
    if plan.get('schemaVersion') != SCHEMA:
        _fail('REVISION_SCHEMA', plan_path, f'Expected {SCHEMA!r}')
    required = {'schemaVersion', 'baseManifestSha256', 'architecturePlanSha256', 'revisionId', 'files'}
    optional = {'sourceEvidencePins'}
    if set(plan) - required - optional or required - set(plan):
        _fail('REVISION_SCHEMA', plan_path, 'Revision plan fields do not match the strict schema')
    rows = plan.get('files')
    if not isinstance(rows, list) or not rows or len(rows) > MAX_ROWS:
        _fail('REVISION_SCHEMA', plan_path, 'Revision plan requires a bounded non-empty files list')
    actual = set()
    for path in root.rglob('*'):
        safe(path)
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            if relative != 'revision-plan.json':
                actual.add(relative)
    declared = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            _fail('REVISION_SCHEMA', f'files[{index}]', 'Change row must be an object')
        artifact = _relative(row.get('artifactPath'), f'files[{index}].artifactPath')
        if artifact in declared:
            _fail('REVISION_SCHEMA', artifact, 'Duplicate revision artifact path')
        declared.add(artifact)
    if actual != declared:
        _fail('REVISION_INVENTORY', root, 'Revision artifact directory contains missing or undeclared files')
    return root, plan, raw, rows


def revise_native_candidate(candidate_root, expected_manifest_sha256,
                            revision_root, expected_revision_plan_sha256,
                            output_root):
    """Apply explicit C# changes to a new copy of a native assembly candidate.

    Revision plan schema `monkey-native-architecture-revision/1` requires
    ``baseManifestSha256``, ``architecturePlanSha256``, ``revisionId``, and
    ``files``. Each row pins ``path``, ``artifactPath``, ``oldSha256`` (null
    only for a new helper), ``newSha256``, ``bytes``, ``classId``, ``module``,
    ``layer``, ``role`` (`replace` or `new-helper`), and a non-empty
    ``provenance`` object.
    """
    base_root, base_manifest, owned, architecture_sha = _verify_native_candidate(
        candidate_root, expected_manifest_sha256)
    revision_dir, plan, plan_raw, changes = _load_revision_plan(
        revision_root, expected_revision_plan_sha256)
    if plan.get('baseManifestSha256') != expected_manifest_sha256:
        _fail('BASE_PIN', revision_dir, 'Revision plan baseManifestSha256 differs from the supplied candidate pin')
    if plan.get('architecturePlanSha256') != architecture_sha:
        _fail('ARCHITECTURE_PIN', revision_dir, 'Revision plan architecture pin differs from the native candidate')
    revision_id = plan.get('revisionId')
    if not isinstance(revision_id, str) or not revision_id.strip() or len(revision_id) > 256:
        _fail('REVISION_ID', revision_dir, 'revisionId must be a bounded non-empty string')
    output = safe(output_root)
    if output.exists():
        _fail('OUTPUT_EXISTS', output, 'Revision requires a fresh output directory')
    for input_root in (base_root, revision_dir):
        if output == input_root or output.is_relative_to(input_root) or input_root.is_relative_to(output):
            _fail('OUTPUT_OVERLAP', output, 'Output must not overlap the native candidate or revision inputs')
    if revision_dir == base_root or revision_dir.is_relative_to(base_root) or base_root.is_relative_to(revision_dir):
        _fail('INPUT_OVERLAP', revision_dir, 'Revision artifacts must be separate from the frozen base candidate')

    source_evidence_pins = plan.get('sourceEvidencePins', {})
    if not isinstance(source_evidence_pins, dict):
        _fail('SOURCE_EVIDENCE', revision_dir, 'sourceEvidencePins must map candidate relative paths to hashes')
    for path, digest in source_evidence_pins.items():
        path = _relative(path, 'sourceEvidencePins')
        row = owned.get(path)
        if not row or not isinstance(digest, str) or digest != row.get('sha256'):
            _fail('SOURCE_EVIDENCE', path, 'Evidence pin must match a file in the frozen candidate manifest')

    change_by_path = {}
    artifact_by_path = {}
    changed_class_ids = set()
    existing_class_ids = {row.get('provenance', {}).get('classId')
                          for path, row in owned.items() if path.endswith('.cs') and isinstance(row.get('provenance'), dict)}
    base_class_paths = base_manifest.get('classPaths')
    if base_class_paths is not None and not isinstance(base_class_paths, dict):
        _fail('CLASS_PATHS', base_root, 'classPaths must be an object when present')
    new_class_ids = set()
    prepared = []
    revision_bytes = 0
    verified_root_namespace = None
    for index, change in enumerate(changes):
        required = {'path', 'artifactPath', 'oldSha256', 'newSha256', 'bytes', 'classId',
                    'module', 'layer', 'role', 'provenance'}
        if set(change) != required:
            _fail('REVISION_SCHEMA', f'files[{index}]', 'Change row must have exactly the versioned revision fields')
        path = _relative(change['path'], f'files[{index}].path')
        artifact = _relative(change['artifactPath'], f'files[{index}].artifactPath')
        if path in change_by_path or artifact in artifact_by_path:
            _fail('REVISION_SCHEMA', path, 'Duplicate change path or artifact path')
        change_by_path[path] = change
        artifact_by_path[artifact] = change
        layer, module, type_name = _layer_module(path, path)
        if change['layer'] != layer or change['module'] != module:
            _fail('OWNER_PATH', path, 'Declared layer/module owner differs from the semantic target directory')
        if not isinstance(change['classId'], str) or not change['classId'].strip():
            _fail('OWNER', path, 'classId must be explicitly declared')
        if change['classId'] in changed_class_ids:
            _fail('OWNER', path, 'Each classId may appear in only one revision row')
        changed_class_ids.add(change['classId'])
        if not isinstance(change['provenance'], dict) or not change['provenance']:
            _fail('PROVENANCE', path, 'Every revision row requires non-empty source provenance')
        if not isinstance(change['newSha256'], str) or not SHA_RE.fullmatch(change['newSha256']):
            _fail('REVISION_SCHEMA', path, 'newSha256 must be lowercase SHA-256')
        if type(change['bytes']) is not int or not 1 <= change['bytes'] <= FILE_BYTES:
            _fail('REVISION_SCHEMA', path, 'Revision C# byte size is invalid')
        if change['role'] not in ROLES:
            _fail('REVISION_SCHEMA', path, 'role must be replace or new-helper')
        if change['role'] == 'replace':
            old = owned.get(path)
            if not old or old.get('owner') != 'generated' or old.get('sourceKind') not in ('architecture-module', 'architecture-revision', 'architecture-revision-helper'):
                _fail('OWNER', path, 'Only generated architecture-owned classes can be replaced')
            provenance = old.get('provenance')
            if not isinstance(provenance, dict) or provenance.get('classId') != change['classId']:
                _fail('OWNER', path, 'Replacement classId differs from the original file owner')
            if provenance.get('module') not in (None, module) or provenance.get('layer') not in (None, layer):
                _fail('OWNER', path, 'Replacement module/layer differs from the original owner')
            if not isinstance(change['oldSha256'], str) or change['oldSha256'] != old['sha256']:
                _fail('OLD_HASH', path, 'Replacement oldSha256 must equal the original candidate file hash')
            if base_class_paths is not None and base_class_paths.get(change['classId']) != path:
                _fail('CLASS_PATHS', path, 'Replacement must follow its original classPaths reservation')
            old_raw = read(inside(base_root, path), FILE_BYTES)
            expected_kind, expected_namespace = _type_identity(old_raw, path, type_name)
            if not expected_namespace.endswith(f'.{layer}.{module}'):
                _fail('SEMANTIC_OWNER', path, 'Original class namespace differs from its layer/module owner path')
        else:
            if path in owned or change['oldSha256'] is not None:
                _fail('HELPER_COLLISION', path, 'A new helper must have no prior C# owner or old SHA')
            if change['classId'] in existing_class_ids or change['classId'] in new_class_ids:
                _fail('HELPER_OWNER', path, 'New helper classId is already owned by another candidate class')
            reserved_path = base_class_paths.get(change['classId']) if base_class_paths is not None else None
            if reserved_path is not None and reserved_path != path:
                _fail('CLASS_PATHS', path, 'A reserved missing class may only be completed at its original classPaths path')
            new_class_ids.add(change['classId'])
            # Every helper shares this immutable, manifest-pinned base. Establish
            # its root once; all source hashes are still checked before copying.
            if verified_root_namespace is None:
                verified_root_namespace = _architecture_root_namespace(base_root, owned)
            expected_namespace = f'{verified_root_namespace}.{layer}.{module}'
            expected_kind = None
        artifact_path = inside(revision_dir, artifact)
        raw = read(artifact_path, FILE_BYTES)
        if len(raw) != change['bytes'] or sha(raw) != change['newSha256']:
            _fail('NEW_HASH', artifact, 'Revision artifact differs from its planned hash/byte count')
        if expected_kind is None:
            expected_kind, actual_namespace = _type_identity(raw, path, type_name)
            if actual_namespace != expected_namespace:
                _fail('SEMANTIC_OWNER', path, 'New helper namespace must exactly match its verified owner module namespace')
        _validate_csharp(raw, path, type_name, layer, expected_namespace, expected_kind)
        revision_bytes += len(raw)
        if revision_bytes > WHOLE_BYTES:
            _fail('OUTPUT_BUDGET', revision_dir, 'Revision artifacts exceed whole-project byte budget')
        prepared.append((path, artifact, change, artifact_path, type_name))

    # Validate every original owned file before making any output.
    total = 0
    for path, row in owned.items():
        source_path = inside(base_root, path)
        raw = read(source_path, FILE_BYTES)
        if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
            _fail('SOURCE_CHANGED', path, 'Frozen candidate file differs from its pinned manifest')
        total += len(raw)
        if total > WHOLE_BYTES:
            _fail('OUTPUT_BUDGET', base_root, 'Frozen candidate exceeds whole-project byte budget')
    used_guids = set()
    original_meta_bytes = {}
    for path, row in owned.items():
        if path.endswith('.meta'):
            raw = read(inside(base_root, path), FILE_BYTES)
            guid = _guid(raw, path)
            if guid in used_guids:
                _fail('DUPLICATE_GUID', path, 'Frozen candidate already contains duplicate Unity meta GUIDs')
            used_guids.add(guid)
            original_meta_bytes[path] = raw

    new_meta = {}
    for path, _artifact, change, _artifact_path, _type_name in prepared:
        if change['role'] != 'new-helper':
            continue
        meta_path = path + '.meta'
        if meta_path in owned:
            # Preserve an existing orphan meta exactly; do not assign a new GUID.
            guid = _guid(original_meta_bytes[meta_path], meta_path)
            new_meta[path] = (meta_path, original_meta_bytes[meta_path], guid, False)
        else:
            raw, guid = _derived_meta(base_manifest['namespace'], revision_id, path,
                                      expected_revision_plan_sha256, used_guids)
            used_guids.add(guid)
            new_meta[path] = (meta_path, raw, guid, True)

    added_bytes = sum(change['bytes'] for _path, _artifact, change, *_rest in prepared)
    replaced_bytes = sum(owned[path]['bytes'] for path, change in change_by_path.items() if change['role'] == 'replace')
    added_bytes += sum(len(raw) for _meta_path, raw, _guid_value, created in new_meta.values() if created)
    if total - replaced_bytes + added_bytes > WHOLE_BYTES:
        _fail('OUTPUT_BUDGET', output, 'Revised candidate exceeds whole-project byte budget')

    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700)
    try:
        # Byte-copy the full original standard candidate before applying explicit
        # rows; no packages, resources, JSON, scenes, or settings are regenerated.
        for path, row in owned.items():
            source_path = inside(base_root, path)
            target = inside(output, path)
            copy_verified(source_path, target, row['sha256'], row['bytes'])

        output_rows = {path: dict(row) for path, row in owned.items()}
        changes_report = []
        for path, artifact, change, artifact_path, type_name in prepared:
            target = inside(output, path)
            target.parent.mkdir(parents=True, exist_ok=True)
            copy_verified(artifact_path, target, change['newSha256'], change['bytes'])
            prior = output_rows.get(path)
            new_row = dict(prior or {}, path=path, sha256=change['newSha256'], bytes=change['bytes'],
                           owner='generated', sourceKind=('architecture-revision-helper' if change['role'] == 'new-helper'
                                                          else 'architecture-revision'),
                           provenance={**change['provenance'], 'classId': change['classId'],
                                       'module': change['module'], 'layer': change['layer'],
                                       'role': change['role'], 'revisionId': revision_id,
                                       'previousSha256': change['oldSha256'],
                                       'previousOwner': prior.get('owner') if prior else None,
                                       'previousSourceKind': prior.get('sourceKind') if prior else None,
                                       'previousProvenance': prior.get('provenance') if prior else None})
            output_rows[path] = new_row
            report_row = {
                'path': path, 'artifactPath': artifact, 'classId': change['classId'],
                'module': change['module'], 'layer': change['layer'], 'role': change['role'],
                'oldSha256': change['oldSha256'], 'newSha256': change['newSha256'],
                'bytes': change['bytes'], 'oldOwner': prior.get('owner') if prior else None,
                'newOwner': 'generated', 'oldSourceKind': prior.get('sourceKind') if prior else None,
                'oldProvenance': prior.get('provenance') if prior else None,
                'newProvenance': change['provenance'],
            }
            if change['role'] == 'new-helper':
                meta_path, meta_raw, guid, created = new_meta[path]
                if created:
                    meta_target = inside(output, meta_path)
                    meta_target.parent.mkdir(parents=True, exist_ok=True)
                    meta_target.write_bytes(meta_raw)
                    output_rows[meta_path] = {
                        'path': meta_path, 'sha256': sha(meta_raw), 'bytes': len(meta_raw),
                        'owner': 'generated', 'sourceKind': 'architecture-revision-meta',
                        'provenance': {'classId': change['classId'], 'module': change['module'],
                                       'layer': change['layer'], 'revisionId': revision_id,
                                       'helperPath': path, 'guid': guid},
                    }
                report_row.update(metaPath=meta_path, metaSha256=sha(meta_raw), metaGuid=guid,
                                  generatedMeta=created)
            changes_report.append(report_row)

        updated_manifest = dict(base_manifest)
        updated_manifest['files'] = [output_rows[path] for path in sorted(output_rows)]
        revised_class_paths = set()
        if isinstance(updated_manifest.get('classPaths'), dict):
            for path, _artifact, change, _artifact_path, _type_name in prepared:
                reserved = updated_manifest['classPaths'].get(change['classId'])
                if reserved is not None and reserved != path:
                    _fail('CLASS_PATHS', path, 'Revision classId conflicts with its reserved target path')
                updated_manifest['classPaths'][change['classId']] = path
                revised_class_paths.add(path)
        if isinstance(updated_manifest.get('implementedClassPaths'), list):
            updated_manifest['implementedClassPaths'] = sorted(set(updated_manifest['implementedClassPaths']) | revised_class_paths)
        if isinstance(updated_manifest.get('missingClassPaths'), list):
            updated_manifest['missingClassPaths'] = sorted(set(updated_manifest['missingClassPaths']) - revised_class_paths)
        if isinstance(base_manifest.get('scriptIdentities'), dict):
            identities = {key: dict(value) for key, value in base_manifest['scriptIdentities'].items()}
            for path, _artifact, change, _artifact_path, _type_name in prepared:
                meta_path = path + '.meta'
                meta_row = output_rows.get(meta_path)
                if meta_row is None:
                    identities.pop(change['classId'], None)
                    continue
                meta_raw = read(inside(output, meta_path), FILE_BYTES)
                guid = _guid(meta_raw, meta_path)
                identities[change['classId']] = dict(path=path, sha256=change['newSha256'],
                    metaPath=meta_path, metaSha256=sha(meta_raw), guid=guid, unityTypeStatus='not_compiled')
                if meta_row.get('sourceKind') == 'architecture-script-meta':
                    output_rows[meta_path] = {**meta_row, 'provenance': {
                        **meta_row.get('provenance', {}), 'scriptSha256': change['newSha256']}}
            updated_manifest['scriptIdentities'] = identities
            updated_manifest['files'] = [output_rows[path] for path in sorted(output_rows)]
        updated_manifest['status'] = 'partial'
        updated_manifest['implementationStatus'] = 'partial_unreviewed'
        updated_manifest['compiled'] = False
        updated_manifest['compileStatus'] = 'not_run'
        updated_manifest['runtime'] = 'not_run'
        updated_manifest['runtimeStatus'] = 'not_run'
        updated_manifest['architectureRevision'] = {
            'schemaVersion': SCHEMA, 'revisionId': revision_id,
            'revisionPlanSha256': expected_revision_plan_sha256,
            'baseManifestSha256': expected_manifest_sha256,
            'architecturePlanSha256': architecture_sha,
            'sourceEvidencePins': source_evidence_pins,
            'changes': changes_report,
        }
        write_json(output / 'manifest.json', updated_manifest)

        # Recheck every old source and revision artifact after writing. The output
        # must remain a standard, fully verifiable candidate snapshot.
        if sha(read(base_root / 'manifest.json', MAX_PLAN_BYTES)) != expected_manifest_sha256:
            _fail('SOURCE_RACE', base_root, 'Base candidate manifest changed during revision')
        if sha(read(revision_dir / 'revision-plan.json', MAX_PLAN_BYTES)) != expected_revision_plan_sha256:
            _fail('REVISION_RACE', revision_dir, 'Revision plan changed during output creation')
        for path, row in owned.items():
            _read_path = inside(base_root, path)
            raw = read(_read_path, FILE_BYTES)
            if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
                _fail('SOURCE_RACE', path, 'Base candidate file changed during revision')
        for path, artifact, change, _artifact_path, _type_name in prepared:
            raw = read(inside(revision_dir, artifact), FILE_BYTES)
            if len(raw) != change['bytes'] or sha(raw) != change['newSha256']:
                _fail('REVISION_RACE', artifact, 'Revision artifact changed during output creation')
        output_root, output_manifest, output_owned, _ = snapshot(output)
        verify(output_root, output_owned)
        for path, row in output_owned.items():
            raw = read(inside(output_root, path), FILE_BYTES)
            if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
                _fail('OUTPUT_VERIFY', path, 'Output candidate inventory differs after revision')
        return output_manifest
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise
