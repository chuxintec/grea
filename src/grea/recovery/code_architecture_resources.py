"""Attach explicit local-test JSON assets to a fresh native candidate copy.

This producer only adds JSON under ``Assets/Game/Content/Config`` and Unity
metadata for those JSON files. It never edits a candidate in place or treats
self-authored test values as recovered original-game data.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import unicodedata
import uuid
from pathlib import Path

from . import code_architecture_revision as revision
from .candidate_snapshot import snapshot, verify
from .io import inside, read, safe, sha, write_json
from .output_limits import FILE_BYTES, MANIFEST_BYTES, WHOLE_BYTES, WHOLE_FILES, copy_verified
from .sources.compiled import ParseError, budget, fail


SCHEMA = 'monkey-native-json-assets/1'
RECEIPT_SCHEMA = 'monkey-native-json-asset-receipt/1'
MAX_SPEC_BYTES = 4 * 1024 * 1024
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_ASSETS = 128
SHA_RE = re.compile(r'^[0-9a-f]{64}$')
ROLE = 'derived-local-test'
PROVENANCE_KIND = 'self-authored-candidate-local-test'
PROVENANCE_STATEMENT = 'Self-authored test data; not recovered from the original game.'
_SPEC_FIELDS = {'schemaVersion', 'baseManifestSha256', 'architecturePlanSha256', 'revisionId', 'assets'}
_ASSET_FIELDS = {'path', 'artifactPath', 'sha256', 'bytes', 'role', 'provenance'}
_PROVENANCE_FIELDS = {'kind', 'sourceId', 'logicalKey', 'statement'}


def _fail(code: str, location, message: str):
    fail('CODE_ARCH_JSON_ASSET_' + code, str(location), message)


def _relative(value, location):
    if (not isinstance(value, str) or not value or '\\' in value or value.startswith('/')
            or re.match(r'^[A-Za-z]:', value) or ':' in value
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
            or unicodedata.normalize('NFC', value) != value
            or any(part in ('', '.', '..') for part in value.split('/'))):
        _fail('PATH', location, 'Expected a canonical NFC relative path without traversal')
    return value


def _strict_json(raw: bytes, location, max_bytes: int):
    if not isinstance(raw, bytes) or len(raw) > max_bytes:
        _fail('JSON_BUDGET', location, 'JSON bytes exceed the declared strict input budget')

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _fail('JSON_DUPLICATE_KEY', location, f'Duplicate JSON key {key!r}')
            result[key] = value
        return result

    def constant(value):
        _fail('JSON_NONFINITE', location, f'Non-finite JSON number {value!r} is forbidden')

    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as error:
        _fail('JSON_UTF8', location, f'JSON must use strict UTF-8: {error}')
    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except json.JSONDecodeError as error:
        _fail('JSON_INVALID', location, f'Invalid JSON: {error.msg}')
    except ParseError:
        raise
    except ValueError as error:
        _fail('JSON_INVALID', location, f'Invalid JSON value: {error}')
    except RecursionError:
        _fail('JSON_BUDGET', location, 'JSON nesting exceeds the parser recursion budget')
    try:
        budget(value, max_depth=96, max_nodes=2_000_000)
    except UnicodeEncodeError:
        _fail('JSON_UNICODE', location, 'JSON contains an unpaired Unicode surrogate')
    return value


def _artifact_inventory(root: Path, expected_files: set[str]):
    if not root.is_dir():
        _fail('ARTIFACT_ROOT', root, 'Spec and JSON artifacts must share an existing input directory')
    actual_files = set()
    for item in root.rglob('*'):
        if item.is_symlink():
            _fail('SYMLINK', item, 'Spec and artifact inventory cannot contain symbolic links')
        safe(item)
        if item.is_file():
            actual_files.add(item.relative_to(root).as_posix())
    if actual_files != expected_files:
        _fail('ARTIFACT_INVENTORY', root, 'Spec directory files must exactly match the spec and declared JSON artifacts')


def _validate_spec(spec_path: Path, raw: bytes, expected_manifest: str,
                   expected_spec: str, architecture_sha: str, base_root: Path,
                   spec_root: Path, manifest: dict, owned: dict):
    if not isinstance(expected_spec, str) or not SHA_RE.fullmatch(expected_spec) or sha(raw) != expected_spec:
        _fail('SPEC_PIN', spec_path, 'JSON asset spec differs from its exact SHA-256 pin')
    spec = _strict_json(raw, spec_path, MAX_SPEC_BYTES)
    if not isinstance(spec, dict) or set(spec) != _SPEC_FIELDS:
        _fail('SPEC_SCHEMA', spec_path, f'Spec must contain exactly {sorted(_SPEC_FIELDS)}')
    if spec.get('schemaVersion') != SCHEMA:
        _fail('SPEC_SCHEMA', spec_path, f'Expected schemaVersion {SCHEMA!r}')
    if spec.get('baseManifestSha256') != expected_manifest:
        _fail('BASE_PIN', spec_path, 'Spec baseManifestSha256 differs from the supplied candidate pin')
    if spec.get('architecturePlanSha256') != architecture_sha:
        _fail('ARCHITECTURE_PIN', spec_path, 'Spec architecturePlanSha256 differs from the native candidate')
    revision_id = spec.get('revisionId')
    if (not isinstance(revision_id, str) or not revision_id.strip() or len(revision_id) > 128
            or any(ord(char) < 32 or ord(char) == 127 for char in revision_id)):
        _fail('REVISION_ID', spec_path, 'revisionId must be a bounded non-empty string')

    rows = spec.get('assets')
    if not isinstance(rows, list) or not rows or len(rows) > MAX_ASSETS:
        _fail('SPEC_SCHEMA', spec_path, 'Spec requires a bounded non-empty assets array')
    paths, artifacts, source_ids = set(), set(), set()
    folded_artifacts, target_paths = set(), []
    prepared = []
    total_bytes = 0
    folded_owned = {unicodedata.normalize('NFC', path).casefold(): path for path in owned}
    folded_targets = set()
    for index, row in enumerate(rows):
        location = f'assets[{index}]'
        if not isinstance(row, dict) or set(row) != _ASSET_FIELDS:
            _fail('SPEC_SCHEMA', location, 'Asset row has missing or extra fields')
        path = _relative(row['path'], location + '.path')
        artifact = _relative(row['artifactPath'], location + '.artifactPath')
        parts = path.split('/')
        if (len(parts) < 5 or parts[:4] != ['Assets', 'Game', 'Content', 'Config']
                or not parts[-1].endswith('.json') or parts[-1] == '.json'):
            _fail('ASSET_PATH', path, 'Only Assets/Game/Content/Config/.../*.json targets are allowed')
        if path in paths or artifact in artifacts:
            _fail('SPEC_SCHEMA', location, 'Asset paths and artifact paths must be unique')
        folded_artifact = unicodedata.normalize('NFC', artifact).casefold()
        if folded_artifact in folded_artifacts or folded_artifact == unicodedata.normalize('NFC', spec_path.name).casefold():
            _fail('SPEC_SCHEMA', artifact, 'Artifact paths must be unique and must not collide with the pinned spec path')
        folded_artifacts.add(folded_artifact)
        paths.add(path)
        artifacts.add(artifact)
        for target in (path, path + '.meta'):
            key = unicodedata.normalize('NFC', target).casefold()
            if key in folded_owned or key in folded_targets:
                _fail('TARGET_COLLISION', target, 'JSON or generated meta collides with an existing candidate path')
            folded_targets.add(key)
            target_paths.append(target)
        if row.get('role') != ROLE:
            _fail('ROLE', path, f'JSON role must be exactly {ROLE!r}')
        digest = row.get('sha256')
        if not isinstance(digest, str) or not SHA_RE.fullmatch(digest):
            _fail('SPEC_SCHEMA', location, 'sha256 must be lowercase SHA-256')
        size = row.get('bytes')
        if type(size) is not int or not 1 <= size <= MAX_JSON_BYTES:
            _fail('JSON_BUDGET', location, f'bytes must be between 1 and {MAX_JSON_BYTES}')
        provenance = row.get('provenance')
        if not isinstance(provenance, dict) or set(provenance) != _PROVENANCE_FIELDS:
            _fail('PROVENANCE', location, 'provenance must contain exactly kind, sourceId, logicalKey, and statement')
        source_id = provenance.get('sourceId')
        if (provenance.get('kind') != PROVENANCE_KIND or not isinstance(source_id, str)
                or not source_id.startswith('candidate-local-test:') or len(source_id) > 512
                or not source_id[len('candidate-local-test:'):].strip()
                or any(ord(char) < 32 or ord(char) == 127 for char in source_id)):
            _fail('PROVENANCE', location, 'Provenance must identify a self-authored candidate-local-test source')
        if source_id in source_ids:
            _fail('PROVENANCE', location, 'Each JSON asset must have a unique sourceId')
        source_ids.add(source_id)
        logical_key = provenance.get('logicalKey')
        if (not isinstance(logical_key, str) or not logical_key.strip() or len(logical_key) > 4096
                or any(ord(char) < 32 or ord(char) == 127 for char in logical_key)):
            _fail('PROVENANCE', location, 'logicalKey must be a bounded non-empty string')
        if provenance.get('statement') != PROVENANCE_STATEMENT:
            _fail('PROVENANCE', location, 'Provenance must state that the values are self-authored and not recovered')
        total_bytes += size
        if total_bytes > WHOLE_BYTES:
            _fail('JSON_BUDGET', spec_path, 'JSON assets exceed the whole-candidate output byte budget')
        prepared.append({
            'path': path,
            'artifactPath': artifact,
            'sha256': digest,
            'bytes': size,
            'role': ROLE,
            'provenance': {
                'kind': PROVENANCE_KIND,
                'sourceId': source_id,
                'logicalKey': logical_key,
                'statement': PROVENANCE_STATEMENT,
            },
        })

    for target in target_paths:
        parts = target.split('/')
        for index in range(1, len(parts)):
            prefix = unicodedata.normalize('NFC', '/'.join(parts[:index])).casefold()
            if prefix in folded_owned or prefix in folded_targets:
                _fail('TARGET_COLLISION', target, 'A JSON/meta target would require a directory occupied by a candidate file')

    expected_files = artifacts | {spec_path.name}
    _artifact_inventory(spec_root, expected_files)
    if spec_path.name in artifacts:
        _fail('ARTIFACT_INVENTORY', spec_path, 'An artifact cannot overwrite the pinned spec file')

    used_guids = set()
    for path, row in owned.items():
        if path.casefold().endswith('.meta'):
            raw_meta = read(inside(base_root, path), FILE_BYTES)
            guid = revision._guid(raw_meta, path)
            if guid in used_guids:
                _fail('GUID_COLLISION', path, 'Frozen candidate already contains duplicate Unity asset GUIDs')
            used_guids.add(guid)
    for row in prepared:
        stable_namespace = uuid.uuid5(uuid.NAMESPACE_URL,
                                      'monkey-native-local-json-namespace:' + manifest['namespace'])
        guid = uuid.uuid5(stable_namespace, row['path']).hex
        if guid in used_guids:
            _fail('GUID_COLLISION', row['path'], 'Deterministic JSON GUID collides with an existing Unity asset GUID')
        used_guids.add(guid)
        row['guid'] = guid
    return spec, revision_id, prepared, total_bytes


def _json_meta(guid: str) -> bytes:
    return (f'fileFormatVersion: 2\nguid: {guid}\n'
            'TextScriptImporter:\n  externalObjects: {}\n  userData: \n'
            '  assetBundleName: \n  assetBundleVariant: \n').encode('utf-8')


def _overlaps(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def add_json_assets(candidate, expected_manifest, spec, expected_spec, out):
    """Add self-authored ``derived-local-test`` JSON to a fresh candidate copy.

    ``spec`` is a strictly pinned JSON document. Its parent directory is a
    closed input inventory containing only that spec and its declared JSON
    artifact files. ``out`` must be disjoint from the candidate and that input
    directory. The base candidate, spec, and artifact files are never written.
    """
    base_root, base_manifest, owned, architecture_sha = revision._verify_native_candidate(
        candidate, expected_manifest)
    if 'jsonAssetReceipt' in base_manifest:
        _fail('RECEIPT_COLLISION', base_root, 'Candidate already has a JSON asset receipt; use a fresh pre-resource base candidate')
    spec_path = safe(spec)
    if not spec_path.is_file():
        _fail('SPEC', spec_path, 'Pinned JSON asset spec must be an existing regular file')
    spec_root = spec_path.parent
    if _overlaps(base_root, spec_root):
        _fail('INPUT_OVERLAP', spec_root, 'Spec/artifact inputs must be separate from the frozen candidate')
    spec_raw = read(spec_path, MAX_SPEC_BYTES)
    parsed, revision_id, assets, asset_bytes = _validate_spec(
        spec_path, spec_raw, expected_manifest, expected_spec, architecture_sha,
        base_root, spec_root, base_manifest, owned)
    artifact_paths = {row['artifactPath'] for row in assets}

    output = safe(out)
    if output.exists():
        _fail('OUTPUT_EXISTS', output, 'JSON resource revision requires a fresh output directory')
    if _overlaps(output, base_root) or _overlaps(output, spec_root):
        _fail('OUTPUT_OVERLAP', output, 'Output must not overlap any candidate, spec, or JSON artifact input')
    total = sum(row['bytes'] for row in owned.values())
    if total + asset_bytes > WHOLE_BYTES or len(owned) + len(assets) * 2 > WHOLE_FILES:
        _fail('OUTPUT_BUDGET', output, 'JSON resource additions exceed the shared candidate output budget')

    # Check every base pin before allocating output; the module revision verifier
    # already checked the complete inventory, and this pass binds our copy to it.
    for path, row in owned.items():
        raw = read(inside(base_root, path), FILE_BYTES)
        if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
            _fail('BASE_CHANGED', path, 'Frozen candidate file differs from its owning manifest')
    prepared_assets = []
    for row in assets:
        artifact_path = inside(spec_root, row['artifactPath'])
        raw = read(artifact_path, MAX_JSON_BYTES)
        if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
            _fail('ARTIFACT_PIN', row['artifactPath'], 'JSON artifact differs from its declared SHA-256/byte count')
        value = _strict_json(raw, row['artifactPath'], MAX_JSON_BYTES)
        if not isinstance(value, dict):
            _fail('JSON_SHAPE', row['artifactPath'], 'Candidate-local-test JSON root must be an object')
        prepared_assets.append((row, raw))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700, exist_ok=False)
    created = True
    try:
        for path, row in owned.items():
            copy_verified(inside(base_root, path), inside(output, path), row['sha256'], row['bytes'])

        output_rows = {path: dict(row) for path, row in owned.items()}
        receipt_rows = []
        for row, raw in prepared_assets:
            json_target = inside(output, row['path'])
            json_target.parent.mkdir(parents=True, exist_ok=True)
            json_target.write_bytes(raw)
            meta_raw = _json_meta(row['guid'])
            meta_path = row['path'] + '.meta'
            inside(output, meta_path).parent.mkdir(parents=True, exist_ok=True)
            inside(output, meta_path).write_bytes(meta_raw)
            provenance = {
                'role': ROLE,
                'kind': PROVENANCE_KIND,
                'revisionId': revision_id,
                'specSha256': expected_spec,
                'artifactPath': row['artifactPath'],
                'artifactSha256': row['sha256'],
                'sourceId': row['provenance']['sourceId'],
                'logicalKey': row['provenance']['logicalKey'],
                'statement': PROVENANCE_STATEMENT,
                'guid': row['guid'],
            }
            output_rows[row['path']] = {
                'path': row['path'],
                'sha256': row['sha256'],
                'bytes': row['bytes'],
                'owner': 'generated',
                'sourceKind': 'candidate-local-test-json',
                'provenance': provenance,
            }
            output_rows[meta_path] = {
                'path': meta_path,
                'sha256': sha(meta_raw),
                'bytes': len(meta_raw),
                'owner': 'generated',
                'sourceKind': 'candidate-local-test-json-meta',
                'provenance': {
                    'role': ROLE,
                    'revisionId': revision_id,
                    'specSha256': expected_spec,
                    'resourcePath': row['path'],
                    'resourceSha256': row['sha256'],
                    'guid': row['guid'],
                },
            }
            receipt_rows.append({
                'path': row['path'],
                'sha256': row['sha256'],
                'bytes': row['bytes'],
                'artifactPath': row['artifactPath'],
                'metaPath': meta_path,
                'metaSha256': sha(meta_raw),
                'guid': row['guid'],
                'role': ROLE,
                'provenance': provenance,
            })

        updated = dict(base_manifest)
        updated.pop('_manifestName', None)
        updated.pop('limits', None)
        updated['files'] = [output_rows[path] for path in sorted(output_rows)]
        updated['status'] = 'partial'
        updated['implementationStatus'] = 'partial_unreviewed'
        updated['compiled'] = False
        updated['compileStatus'] = 'not_run'
        updated['runtime'] = 'not_run'
        updated['runtimeStatus'] = 'not_run'
        updated['jsonAssetReceipt'] = {
            'schemaVersion': RECEIPT_SCHEMA,
            'role': ROLE,
            'revisionId': revision_id,
            'baseManifestSha256': expected_manifest,
            'architecturePlanSha256': architecture_sha,
            'specSha256': expected_spec,
            'assets': receipt_rows,
            'semantics': 'self-authored candidate-local-test JSON added; original-game equivalence and runtime binding are not asserted',
        }
        write_json(output / 'manifest.json', updated)

        # Recheck all read-only inputs after writing and verify the complete output inventory.
        if sha(read(base_root / 'manifest.json', MANIFEST_BYTES)) != expected_manifest:
            _fail('BASE_RACE', base_root, 'Frozen candidate manifest changed during JSON asset addition')
        if sha(read(spec_path, MAX_SPEC_BYTES)) != expected_spec:
            _fail('SPEC_RACE', spec_path, 'Pinned JSON asset spec changed during output creation')
        _artifact_inventory(spec_root, artifact_paths | {spec_path.name})
        for path, row in owned.items():
            raw = read(inside(base_root, path), FILE_BYTES)
            if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
                _fail('BASE_RACE', path, 'Frozen candidate file changed during JSON asset addition')
        for row, _ in prepared_assets:
            raw = read(inside(spec_root, row['artifactPath']), MAX_JSON_BYTES)
            if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
                _fail('ARTIFACT_RACE', row['artifactPath'], 'JSON artifact changed during output creation')
        output_root, output_manifest, output_owned, _ = snapshot(output)
        verify(output_root, output_owned)
        for path, row in output_owned.items():
            raw = read(inside(output_root, path), FILE_BYTES)
            if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
                _fail('OUTPUT_VERIFY', path, 'Output candidate inventory differs after JSON asset addition')
        return output_manifest
    except BaseException:
        if created:
            shutil.rmtree(output, ignore_errors=True)
        raise
