"""Deterministic, read-only selection of reusable Monkey C# module files.

This module never writes to a candidate. Callers copy only the returned verified
bytes into a new candidate and build a fresh manifest themselves.
"""
from __future__ import annotations

import hashlib
import heapq
import json
import os
import re
import unicodedata
from pathlib import Path, PurePosixPath

from .io import load, read, safe, sha
from .output_limits import CHUNK_BYTES, WHOLE_BYTES, WHOLE_FILES
from .sources.compiled import ParseError, fail

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z_][A-Za-z0-9_.:-]{0,127}\Z")
_MAX_MANIFEST = 128 * 1024 * 1024
_MAX_FILES = 20_000
_MAX_TOTAL = 256 * 1024 * 1024
_MAX_FILE = 512 * 1024 * 1024
_MAX_EDGES = 200_000


def _digest(value: object, location: str) -> str:
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        fail('CODE_REGENERATION_FINGERPRINT', location, 'Expected lowercase SHA-256 hex')
    return value


def _path(value: object, location: str) -> str:
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value:
        fail('CODE_REGENERATION_PATH', location, 'Expected canonical project-relative POSIX path')
    if unicodedata.normalize('NFC', value) != value:
        fail('CODE_REGENERATION_PATH', location, 'Path must already be NFC-normalized')
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or any(part in ('', '.', '..') for part in value.split('/')):
        fail('CODE_REGENERATION_PATH', location, 'Absolute and traversal paths are forbidden')
    if parsed.as_posix() != value:
        fail('CODE_REGENERATION_PATH', location, 'Path is not canonical')
    return value


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def _file_digest(path: Path, declared_bytes: int, location: str) -> tuple[str, int]:
    if type(declared_bytes) is not int or not 0 <= declared_bytes <= _MAX_FILE:
        fail('CODE_REGENERATION_FILE_BUDGET', location, 'Invalid or oversized declared file size')
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        while True:
            chunk = stream.read(CHUNK_BYTES)
            if not chunk:
                break
            size += len(chunk)
            if size > declared_bytes or size > _MAX_FILE:
                fail('CODE_REGENERATION_FILE_CHANGED', location, 'File exceeds its declared size')
            digest.update(chunk)
    if size != declared_bytes:
        fail('CODE_REGENERATION_FILE_CHANGED', location, 'File size differs from manifest')
    return digest.hexdigest(), size


def _validate_requests(modules: object, generator_signature: str, *, whole_input=False) -> tuple[dict, list[str], dict]:
    max_files = WHOLE_FILES if whole_input else _MAX_FILES
    if not isinstance(modules, list) or len(modules) > max_files:
        fail('CODE_REGENERATION_REQUESTS', '$.modules', 'Expected a bounded module array')
    _digest(generator_signature, '$.generator_signature')
    specs: dict[str, dict] = {}
    path_owners: dict[str, str] = {}
    folded: dict[str, str] = {}
    edge_count = 0
    target_count = 0
    for i, module in enumerate(modules):
        loc = f'$.modules[{i}]'
        if not isinstance(module, dict):
            fail('CODE_REGENERATION_REQUESTS', loc, 'Expected an object')
        mid = module.get('id')
        if not isinstance(mid, str) or not _ID.fullmatch(mid):
            fail('CODE_REGENERATION_ID', loc, 'Invalid module id')
        if mid in specs:
            fail('CODE_REGENERATION_DUPLICATE_ID', mid, 'Module ids must be unique')
        source_fp = _digest(module.get('sourceFingerprint'), loc + '.sourceFingerprint')
        deps = module.get('dependencies')
        targets = module.get('targetPaths')
        if not isinstance(deps, list) or not all(isinstance(x, str) and _ID.fullmatch(x) for x in deps):
            fail('CODE_REGENERATION_DEPENDENCIES', mid, 'Dependencies must be module ids')
        edge_count += len(deps)
        if edge_count > _MAX_EDGES:
            fail('CODE_REGENERATION_GRAPH_BUDGET', mid, 'Dependency graph exceeds 200,000 declared edges')
        deps = sorted(set(x for x in deps if x != mid))  # self-recursion is internal to a module
        if not isinstance(targets, list) or not targets:
            fail('CODE_REGENERATION_TARGETS', mid, 'At least one output path is required')
        target_count += len(targets)
        if target_count > max_files:
            fail('CODE_REGENERATION_GRAPH_BUDGET', mid, 'Module request exceeds its target path budget')
        canonical = sorted(_path(x, mid) for x in targets)
        if len(set(canonical)) != len(canonical):
            fail('CODE_REGENERATION_PATH_COLLISION', mid, 'Repeated target path')
        for target in canonical:
            key = target.casefold()
            if key in folded and folded[key] != target:
                fail('CODE_REGENERATION_PATH_COLLISION', target, 'Case-fold path collision')
            folded[key] = target
            if target in path_owners and path_owners[target] != mid:
                fail('CODE_REGENERATION_PATH_COLLISION', target, 'Two modules claim the same target')
            path_owners[target] = mid
        specs[mid] = dict(id=mid, sourceFingerprint=source_fp,
                          dependencies=deps, targetPaths=canonical)
    # Kahn's algorithm produces deterministic dependency-first order without
    # recursion. Remaining nodes are precisely cyclic nodes plus their callers.
    callers: dict[str, list[str]] = {mid: [] for mid in specs}
    pending: dict[str, int] = {}
    missing = {}
    for mid, spec in specs.items():
        internal = [dep for dep in spec['dependencies'] if dep in specs]
        pending[mid] = len(internal)
        for dep in internal:
            callers[dep].append(mid)
        absent = [dep for dep in spec['dependencies'] if dep not in specs]
        if absent:
            missing[mid] = absent
    ready = [mid for mid, count in pending.items() if count == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        mid = heapq.heappop(ready)
        order.append(mid)
        for caller in callers[mid]:
            pending[caller] -= 1
            if pending[caller] == 0:
                heapq.heappush(ready, caller)

    # Iterative Kosaraju identifies actual cycle members. This keeps a
    # downstream caller blocked without misreporting it as part of the cycle.
    graph = {mid: [dep for dep in specs[mid]['dependencies'] if dep in specs] for mid in specs}
    visited: set[str] = set()
    finished = []
    for start in sorted(specs):
        if start in visited:
            continue
        visited.add(start)
        frames = [(start, 0)]
        while frames:
            node, index = frames[-1]
            neighbours = graph[node]
            if index < len(neighbours):
                neighbour = neighbours[index]
                frames[-1] = (node, index + 1)
                if neighbour not in visited:
                    visited.add(neighbour)
                    frames.append((neighbour, 0))
            else:
                frames.pop()
                finished.append(node)
    reverse_graph: dict[str, list[str]] = {mid: [] for mid in specs}
    for mid, dependencies in graph.items():
        for dep in dependencies:
            reverse_graph[dep].append(mid)
    assigned: set[str] = set()
    cyclic: set[str] = set()
    for start in reversed(finished):
        if start in assigned:
            continue
        component = []
        assigned.add(start)
        stack = [start]
        while stack:
            node = stack.pop()
            component.append(node)
            for neighbour in reverse_graph[node]:
                if neighbour not in assigned:
                    assigned.add(neighbour)
                    stack.append(neighbour)
        if len(component) > 1:
            cyclic.update(component)
    # For blocked cycle/cycle-dependent records, stable fallback fingerprints
    # are useful for diagnostics but are never eligible for reuse.
    order.extend(sorted(set(specs) - set(order)))
    return specs, order, dict(cyclic=cyclic, missing=missing)


def _fingerprints(specs: dict, order: list[str], generator_signature: str) -> dict[str, dict]:
    result = {}
    for mid in order:
        spec = specs[mid]
        dep_rows = []
        for dep in spec['dependencies']:
            if dep not in specs:
                dep_rows.append({'id': dep, 'missing': True})
            elif dep in result:
                dep_rows.append({'id': dep, 'sourceFingerprint': specs[dep]['sourceFingerprint'],
                                 'cacheKey': result[dep]['cacheKey']})
            else:
                dep_rows.append({'id': dep, 'sourceFingerprint': specs[dep]['sourceFingerprint'],
                                 'unresolvedGraph': True})
        dependency_fp = sha(_canonical({'schemaVersion': 1, 'dependencies': dep_rows}))
        cache_key = sha(_canonical({'schemaVersion': 1, 'id': mid,
                                     'sourceFingerprint': spec['sourceFingerprint'],
                                     'dependencyFingerprint': dependency_fp,
                                     'generatorSignature': generator_signature,
                                     'targetPaths': spec['targetPaths']}))
        result[mid] = dict(dependencyFingerprint=dependency_fp, cacheKey=cache_key)
    return result


def _graph_blocking(specs: dict, graph_issues: dict) -> tuple[dict[str, str], list[dict]]:
    blocked: dict[str, str] = {}
    diagnostics = []
    queue = []
    for mid, missing in sorted(graph_issues['missing'].items()):
        blocked[mid] = 'missing_dependency:' + ','.join(missing)
        diagnostics.append(dict(code='missing_dependency', moduleId=mid, dependencies=missing))
        queue.append(mid)
    for mid in sorted(graph_issues['cyclic']):
        blocked[mid] = 'dependency_cycle'
        diagnostics.append(dict(code='dependency_cycle', moduleId=mid))
        queue.append(mid)
    callers: dict[str, list[str]] = {mid: [] for mid in specs}
    for mid, spec in specs.items():
        for dep in spec['dependencies']:
            if dep in callers:
                callers[dep].append(mid)
    cursor = 0
    while cursor < len(queue):
        failed = queue[cursor]
        cursor += 1
        for caller in callers[failed]:
            if caller not in blocked:
                affected = [dep for dep in specs[caller]['dependencies'] if dep in blocked]
                blocked[caller] = 'blocked_dependency:' + ','.join(affected)
                queue.append(caller)
    return blocked, diagnostics


def plan_modules(modules, generator_signature, *, whole_input=False) -> dict:
    """Plan a fresh generation pass without reading an existing candidate."""
    specs, order, graph_issues = _validate_requests(modules, generator_signature, whole_input=whole_input)
    fingerprints = _fingerprints(specs, order, generator_signature)
    blocked, diagnostics = _graph_blocking(specs, graph_issues)
    actions = {}
    records = []
    for mid in sorted(specs):
        spec = specs[mid]
        if mid in blocked:
            action, reason = 'blocked', blocked[mid]
        else:
            action, reason = 'regenerate', 'fresh_candidate_required'
        actions[mid] = dict(action=action, reason=reason)
        records.append(dict(id=mid, sourceFingerprint=spec['sourceFingerprint'],
                            dependencyFingerprint=fingerprints[mid]['dependencyFingerprint'],
                            cacheKey=fingerprints[mid]['cacheKey'], dependencies=spec['dependencies'],
                            targetPaths=spec['targetPaths'], action=action, reason=reason, files=[]))
    return dict(status='partial' if blocked else 'planned', generatorSignature=generator_signature,
                moduleRecords=records, actions=actions, diagnostics=diagnostics)


def _full_drafts(manifest):
    return manifest.get('scopeMode') == 'whole-input' and manifest.get('candidateKind') == 'full-source-csharp-drafts'


def _candidate_inventory(root: Path, manifest: dict) -> tuple[dict[str, dict], dict[str, dict], list[str]]:
    whole = _full_drafts(manifest)
    if manifest.get('schemaVersion') != 1 or not (whole or manifest.get('scopeMode') == 'code-modules-only'):
        fail('CODE_REGENERATION_MANIFEST', str(root), 'Expected code module candidate or explicitly identified full-source drafts')
    max_files, max_total = (WHOLE_FILES, WHOLE_BYTES) if whole else (_MAX_FILES, _MAX_TOTAL)
    rows = manifest.get('files')
    records = manifest.get('codeModules')
    if not isinstance(rows, list) or len(rows) > max_files or not isinstance(records, list) or len(records) > max_files:
        fail('CODE_REGENERATION_MANIFEST', str(root), 'Invalid or oversized files/codeModules arrays')
    files: dict[str, dict] = {}
    folded = {}
    total = 0
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            fail('CODE_REGENERATION_MANIFEST', f'files[{i}]', 'Expected file record')
        path = _path(row.get('path'), f'files[{i}].path')
        key = path.casefold()
        if key in folded:
            fail('CODE_REGENERATION_PATH_COLLISION', path, 'Duplicate/case-fold file path')
        folded[key] = path
        _digest(row.get('sha256'), path)
        size = row.get('bytes')
        if type(size) is not int or not 0 <= size <= _MAX_FILE:
            fail('CODE_REGENERATION_FILE_BUDGET', path, 'Invalid or oversized file record')
        total += size
        if total > max_total:
            fail('CODE_REGENERATION_TOTAL_BUDGET', str(root), 'Candidate exceeds its bounded read budget')
        files[path] = row
    modules = {}
    for i, rec in enumerate(records):
        if not isinstance(rec, dict) or not isinstance(rec.get('id'), str) or not _ID.fullmatch(rec['id']):
            fail('CODE_REGENERATION_MANIFEST', f'codeModules[{i}]', 'Invalid module record')
        mid = rec['id']
        if mid in modules:
            fail('CODE_REGENERATION_DUPLICATE_ID', mid, 'Candidate module ids must be unique')
        _digest(rec.get('sourceFingerprint'), mid + '.sourceFingerprint')
        _digest(rec.get('dependencyFingerprint'), mid + '.dependencyFingerprint')
        _digest(rec.get('cacheKey'), mid + '.cacheKey')
        targets = rec.get('targetPaths')
        if not isinstance(targets, list):
            fail('CODE_REGENERATION_MANIFEST', mid, 'Missing targetPaths')
        targets = sorted(_path(path, mid) for path in targets)
        if targets != sorted(set(targets)):
            fail('CODE_REGENERATION_PATH_COLLISION', mid, 'Duplicate module target path')
        record_paths = rec.get('files')
        if not isinstance(record_paths, list) or sorted(record_paths) != targets:
            fail('CODE_REGENERATION_MANIFEST', mid, 'Module files must equal targetPaths')
        modules[mid] = dict(rec, targetPaths=targets)
    return files, modules, []


def select_reuse(candidate, expected_manifest_sha256, modules, generator_signature) -> dict:
    """Choose reusable code and return verified bytes without modifying the input.

    File owner in manifest ``files`` must be the owning module id. Each
    ``codeModules`` record has id, sourceFingerprint, dependencyFingerprint,
    cacheKey, targetPaths, dependencies, files and optional sourceMethodMappings.
    A matching module is reused only when every owned file is present and its
    current bytes match manifest hash and size.
    """
    _digest(expected_manifest_sha256, '$.expected_manifest_sha256')
    _digest(generator_signature, '$.generator_signature')
    root = safe(Path(candidate))
    manifest_path = safe(root / 'manifest.json')
    raw_manifest = read(manifest_path, max_bytes=_MAX_MANIFEST)
    if sha(raw_manifest) != expected_manifest_sha256:
        fail('CODE_REGENERATION_IDENTITY', str(manifest_path), 'Candidate manifest does not match expected SHA-256')
    manifest = load(raw_manifest, max_nodes=8_000_000, max_depth=128)
    whole = _full_drafts(manifest)
    specs, order, graph_issues = _validate_requests(modules, generator_signature, whole_input=whole)
    fingerprints = _fingerprints(specs, order, generator_signature)
    files, old_modules, _ = _candidate_inventory(root, manifest)

    blocked, diagnostics = _graph_blocking(specs, graph_issues)

    # Ensure the candidate directory has no unmanifested file and no symlink.
    actual = set()
    for directory, dirs, names in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in list(dirs):
            path = base / name
            if path.is_symlink():
                fail('CODE_REGENERATION_SYMLINK', str(path), 'Symlink in candidate is forbidden')
        for name in names:
            path = base / name
            if path.is_symlink():
                fail('CODE_REGENERATION_SYMLINK', str(path), 'Symlink in candidate is forbidden')
            rel = path.relative_to(root).as_posix()
            if rel != 'manifest.json':
                actual.add(_path(rel, str(path)))
    manifest_paths = set(files)
    extras = sorted(actual - manifest_paths)
    absent = sorted(manifest_paths - actual)
    if extras or absent:
        diagnostics.append(dict(code='candidate_inventory_mismatch', extraFiles=extras, missingFiles=absent))
        for mid in specs:
            blocked.setdefault(mid, 'candidate_inventory_mismatch')

    known_old_paths = {path: mid for mid, rec in old_modules.items() for path in rec['targetPaths']}
    for path, row in files.items():
        owner = row.get('owner')
        if owner != 'manual' and (owner not in old_modules or path not in known_old_paths or known_old_paths.get(path) != owner):
            diagnostics.append(dict(code='unknown_candidate_file', path=path, owner=owner))
            for mid in specs:
                blocked.setdefault(mid, 'unknown_candidate_file:' + path)

    # A manual or unknown file in the requested ownership region blocks all
    # affected module reuse. It never becomes an implicit overwrite target.
    requested_paths = {path: mid for mid, spec in specs.items() for path in spec['targetPaths']}
    for path, row in files.items():
        owner = row.get('owner')
        if owner == 'manual' or (path in requested_paths and owner != requested_paths[path]):
            mid = requested_paths.get(path, owner if owner in specs else None)
            if mid in specs:
                blocked[mid] = 'manual_or_wrong_owner_file:' + path
            elif path in requested_paths:
                blocked[requested_paths[path]] = 'manual_or_wrong_owner_file:' + path
        if path in requested_paths and owner not in (requested_paths[path], 'manual'):
            blocked[requested_paths[path]] = 'unknown_file_owner:' + path

    actions = {}
    reusable_files: dict[str, bytes] = {}
    module_records = []
    reusable_total = 0
    for mid in sorted(specs):
        spec = specs[mid]
        old = old_modules.get(mid)
        reason = ''
        action = 'regenerate'
        if mid in blocked:
            action, reason = 'blocked', blocked[mid]
        elif old is None:
            reason = 'module_not_in_candidate'
        elif old.get('sourceFingerprint') != spec['sourceFingerprint']:
            reason = 'source_fingerprint_changed'
        elif old.get('targetPaths') != spec['targetPaths']:
            reason = 'target_paths_changed'
        elif old.get('dependencies') != spec['dependencies']:
            reason = 'dependency_list_changed'
        elif old.get('dependencyFingerprint') != fingerprints[mid]['dependencyFingerprint']:
            reason = 'dependency_fingerprint_changed'
        elif manifest.get('codeGeneratorSignature') != generator_signature:
            reason = 'generator_signature_changed'
        elif old.get('cacheKey') != fingerprints[mid]['cacheKey']:
            reason = 'cache_key_changed'
        else:
            invalid = None
            for path in spec['targetPaths']:
                row = files.get(path)
                if row is None:
                    invalid = 'candidate_file_missing:' + path
                    break
                if row.get('owner') != mid:
                    invalid = 'unknown_file_owner:' + path
                    break
                full = safe(root / path)
                if not full.is_relative_to(root):
                    fail('CODE_REGENERATION_PATH', path, 'Resolved file escapes candidate root')
                try:
                    actual_hash, actual_size = _file_digest(full, row['bytes'], path)
                except ParseError as exc:
                    if exc.code == 'CODE_REGENERATION_FILE_CHANGED':
                        invalid = 'candidate_file_hash_changed:' + path
                        break
                    raise
                if actual_hash != row['sha256']:
                    invalid = 'candidate_file_hash_changed:' + path
                    break
                reusable_total += actual_size
                if reusable_total > (WHOLE_BYTES if whole else _MAX_TOTAL):
                    fail('CODE_REGENERATION_TOTAL_BUDGET', str(root), 'Reusable bytes exceed the candidate read budget')
            if invalid:
                action, reason = 'blocked', invalid
            else:
                action, reason = 'reuse', 'all_fingerprints_paths_ownership_and_file_hashes_match'
                for path in spec['targetPaths']:
                    row = files[path]
                    data = read(safe(root / path), max_bytes=row['bytes'])
                    if len(data) != row['bytes'] or sha(data) != row['sha256']:
                        fail('CODE_REGENERATION_FILE_CHANGED', path, 'File changed after hash verification')
                    reusable_files[path] = data
        actions[mid] = dict(action=action, reason=reason)
        record = dict(id=mid, sourceFingerprint=spec['sourceFingerprint'],
                      dependencyFingerprint=fingerprints[mid]['dependencyFingerprint'],
                      cacheKey=fingerprints[mid]['cacheKey'], dependencies=spec['dependencies'],
                      targetPaths=spec['targetPaths'], action=action, reason=reason)
        if action == 'reuse' and old:
            record['sourceMethodMappings'] = old.get('sourceMethodMappings', [])
            record['files'] = [{k: files[path][k] for k in ('path', 'sha256', 'bytes', 'owner')}
                               for path in spec['targetPaths']]
        else:
            record['files'] = []
        module_records.append(record)
    return dict(status='partial' if any(x['action'] == 'blocked' for x in actions.values()) else 'planned',
                candidateManifestSha256=expected_manifest_sha256,
                generatorSignature=generator_signature, moduleRecords=module_records,
                actions=actions, reusableFiles=reusable_files, diagnostics=diagnostics)
