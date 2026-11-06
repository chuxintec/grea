"""Build a bounded, source-pinned bridge from code owners to native asset identity.

This index is evidence for authoring/serialization context only. It does not
resolve runtime source UUIDs and it does not prove a Unity object reference.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .candidate_snapshot import snapshot
from .io import encoded, inside, load, read, safe, sha
from .sources.compiled import fail

SCHEMA = 'monkey-code-architecture-asset-context/1'
INDEX_SCHEMA = 'monkey-code-architecture-asset-context-index/1'
SHARD_SCHEMA = 'monkey-code-architecture-asset-context-shard/1'
ASSET_CONTEXT_SHARD_BYTES = 8 * 1024 * 1024
ASSET_CONTEXT_GROUP_BYTES = 64 * 1024 * 1024
ASSET_CONTEXT_MAX_SHARDS = 1024
MAPPING_PATHS = {
    'sourceMap': 'Analysis/Mappings/source-map.json',
    'cocosAssets': 'Analysis/Mappings/cocos-assets.json',
    'resourcePaths': 'Analysis/Mappings/resource-paths.json',
    'editorReadback': 'Analysis/Readback/editor-readback.json',
}
BINDING_PATH = 'Analysis/Code/component-code-bindings.json'
MAPPING_MAX_BYTES = 128 * 1024 * 1024
READBACK_MAX_NODES = 20_000_000
_GUID = re.compile(r'(?m)^guid:\s*([0-9a-f]{32})\s*$')


def _owned_bytes(root, owned, path, maximum=MAPPING_MAX_BYTES):
    row = owned.get(path)
    if row is None:
        return None
    raw = read(inside(root, path), max_bytes=maximum)
    if len(raw) != row.get('bytes') or sha(raw) != row.get('sha256'):
        fail('CODE_ARCH_ASSET_SOURCE', path, 'Frozen mapping bytes differ from owning manifest SHA/size')
    return raw


def _rows(document, key, source_path):
    rows = document.get(key)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        fail('CODE_ARCH_ASSET_SHAPE', source_path, f'Expected an array of objects at {key}')
    return rows


def _cache_load(cache_file, source_pin, pins):
    if not cache_file or not cache_file.is_file():
        return None
    try:
        raw = read(cache_file, max_bytes=MAPPING_MAX_BYTES)
        sidecar = read(cache_file.with_suffix(cache_file.suffix + '.sha256'), max_bytes=128).decode('ascii').strip()
        if sha(raw) != sidecar:
            return None
        value = load(raw, max_nodes=2_000_000)
        if value.get('schemaVersion') != 2 or value.get('sourceManifestSha256') != source_pin or value.get('mappingPins') != pins:
            return None
        return value
    except (OSError, UnicodeError, ValueError):
        return None


def _write_cache(cache_file, value):
    if not cache_file:
        return
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement keeps a partially written index from being reused.
    temp = inside(cache_file.parent, cache_file.name + '.tmp')
    temp.write_bytes(raw)
    temp.replace(cache_file)
    sidecar = cache_file.with_suffix(cache_file.suffix + '.sha256')
    sidecar = inside(cache_file.parent, sidecar.name)
    temp_sidecar = inside(cache_file.parent, sidecar.name + '.tmp')
    temp_sidecar.write_text(sha(raw) + '\n', encoding='ascii')
    temp_sidecar.replace(sidecar)


def _index_mappings(root, owned, source_pin, cache_root=None, *, binding_sha=None,
                    wanted_assets=(), wanted_nodes=(), wanted_components=()):
    paths = {key: path for key, path in MAPPING_PATHS.items() if path in owned}
    pins = {path: {'sha256': owned[path]['sha256'], 'bytes': owned[path]['bytes']} for path in paths.values()}
    pins['componentBindings'] = {'sha256': binding_sha} if binding_sha else None
    wanted_assets, wanted_nodes, wanted_components = set(wanted_assets), set(wanted_nodes), set(wanted_components)
    cache_file = None
    if cache_root is not None:
        cache_root = safe(cache_root)
        cache_file = inside(cache_root, f'asset-binding-index-{source_pin}.json')
    cached = _cache_load(cache_file, source_pin, pins)
    if cached is not None:
        return cached, pins, 'verified-cache'

    indexed = {'schemaVersion': 2, 'sourceManifestSha256': source_pin, 'mappingPins': pins,
               'sourceAssets': {}, 'sourceNodes': {}, 'sourceComponents': {}, 'resourcePaths': {},
               'sourceMapAssets': {}, 'readbackAssets': {}, 'readbackNodes': {}, 'viewReferences': {},
               'readbackSummary': None}
    for key, path in paths.items():
        raw = _owned_bytes(root, owned, path)
        document = load(raw, max_nodes=READBACK_MAX_NODES if key == 'editorReadback' else 4_000_000)
        if key == 'sourceMap':
            for row in _rows(document, 'assets', path):
                source_id = row.get('sourceId')
                if isinstance(source_id, str) and source_id in wanted_assets: indexed['sourceMapAssets'].setdefault(source_id, []).append(
                    {name: row.get(name) for name in ('sourceId', 'guid', 'path', 'target') if name in row})
            for row in _rows(document, 'nodes', path):
                source_id = row.get('sourceId')
                if isinstance(source_id, str) and source_id in wanted_nodes: indexed['sourceNodes'].setdefault(source_id, []).append(
                    {name: row.get(name) for name in ('sourceId', 'name', 'target') if name in row})
            for row in _rows(document, 'components', path):
                source_id = row.get('sourceId')
                if isinstance(source_id, str) and source_id in wanted_components: indexed['sourceComponents'].setdefault(source_id, []).append(
                    {name: row.get(name) for name in ('sourceId', 'node', 'target', 'type', 'viewField',
                        'convertible', 'bindingEvidence') if name in row})
        elif key == 'cocosAssets':
            for row in _rows(document, 'assets', path):
                source_id = row.get('sourceId')
                if isinstance(source_id, str) and source_id in wanted_assets: indexed['sourceAssets'].setdefault(source_id, []).append(
                    {name: row.get(name) for name in ('sourceId', 'uuid', 'sourceType', 'logicalKey', 'status') if name in row})
        elif key == 'resourcePaths':
            for row in _rows(document, 'assets', path):
                source_id = row.get('sourceId')
                if isinstance(source_id, str) and source_id in wanted_assets: indexed['resourcePaths'].setdefault(source_id, []).append(
                    {name: row.get(name) for name in ('sourceId', 'path', 'type', 'state', 'address',
                        'sourceLogicalKey', 'sourceBundle', 'entryKind') if name in row})
        elif key == 'editorReadback':
            indexed['readbackSummary'] = {key: document.get(key) for key in (
                'status', 'unityVersion', 'nativeScope', 'sourceGraphVerification', 'prefabGuid', 'sceneGuid',
                'nodeCount', 'missingScripts', 'editableRoundtrip', 'sceneReopened')}
            for row in _rows(document, 'sourcePrefabs', path):
                source_id = row.get('sourceId')
                if isinstance(source_id, str) and source_id in wanted_assets:
                    indexed['readbackAssets'].setdefault(source_id, []).append({key: row.get(key) for key in (
                        'sourceId', 'path', 'guid', 'nativePrefabType', 'nodeCount', 'missingScripts',
                        'savedReloaded', 'referencesVerified', 'geometryPhase')})
                for node in row.get('nodes', []):
                    node_id = node.get('sourceId') if isinstance(node, dict) else None
                    if isinstance(node_id, str) and node_id in wanted_nodes:
                        indexed['readbackNodes'].setdefault(node_id, []).append({
                            'sourceId': node_id, 'sourceAsset': source_id, 'hierarchy': node.get('hierarchy'),
                            'componentTypes': node.get('componentTypes', [])})
            for row in _rows(document, 'viewReferences', path):
                source_id = row.get('sourceId')
                if isinstance(source_id, str) and source_id in wanted_components: indexed['viewReferences'].setdefault(source_id, []).append({key: row.get(key) for key in (
                    'sourceId', 'field', 'index', 'prefabFileId', 'bound')})
    _write_cache(cache_file, indexed)
    return indexed, pins, 'rebuilt'


def _binding_file(stage, root, owned):
    task_request_path = stage['root'] / 'Task' / 'request.json'
    try:
        request = load(read(task_request_path, max_bytes=16 * 1024 * 1024), max_nodes=1_000_000)
    except OSError:
        request = {}
    context_pin = request.get('contextFiles', {}).get('__Context/component-code-bindings.json')
    raw = None
    if context_pin:
        raw = read(inside(stage['root'] / 'Evidence', 'component-code-bindings.json'), max_bytes=16 * 1024 * 1024)
        if len(raw) != context_pin.get('bytes') or sha(raw) != context_pin.get('sha256'):
            fail('CODE_ARCH_ASSET_SOURCE', 'component-code-bindings.json', 'Global stage binding evidence differs from worker context pin')
    else:
        # Older global stages may not carry contextFiles in request.json; use only
        # a candidate-owned copy, and never accept an unowned stage-side file.
        raw = _owned_bytes(root, owned, BINDING_PATH, maximum=16 * 1024 * 1024)
    if raw is None:
        return None, None
    candidate_row = owned.get(BINDING_PATH)
    if candidate_row and (len(raw) != candidate_row.get('bytes') or sha(raw) != candidate_row.get('sha256')):
        fail('CODE_ARCH_ASSET_SOURCE', BINDING_PATH, 'Component binding evidence differs from candidate-owned bytes')
    return load(raw, max_nodes=1_000_000), sha(raw)


def _asset_identity(source_asset, indexed, root, owned):
    path_rows = indexed['resourcePaths'].get(source_asset, [])
    cocos_rows = indexed['sourceAssets'].get(source_asset, [])
    source_map_rows = indexed['sourceMapAssets'].get(source_asset, [])
    result = {'sourceAsset': source_asset, 'cocosAssetEvidence': cocos_rows,
              'sourceMapAssetEvidence': source_map_rows, 'resourcePathEvidence': path_rows,
              'nativeTargets': [], 'unresolved': []}
    if not path_rows:
        result['unresolved'].append({'reason': 'no exact sourceId entry in owned resource-paths mapping'})
        return result
    seen_paths = set()
    for row in path_rows:
        target = row.get('path')
        if not isinstance(target, str) or target in seen_paths:
            continue
        seen_paths.add(target)
        target_row = owned.get(target)
        meta_row = owned.get(target + '.meta')
        native = {'path': target, 'state': row.get('state'), 'type': row.get('type'),
                  'mappingSourceId': row.get('sourceId'), 'targetOwned': bool(target_row),
                  'metaOwned': bool(meta_row)}
        if target_row:
            native['sha256'] = target_row.get('sha256')
            native['bytes'] = target_row.get('bytes')
        if meta_row:
            meta_raw = _owned_bytes(root, owned, target + '.meta', maximum=64 * 1024)
            match = _GUID.search(meta_raw.decode('utf-8', 'strict'))
            if match:
                native['guid'] = match.group(1)
                native['metaSha256'] = meta_row.get('sha256')
                native['metaBytes'] = meta_row.get('bytes')
        if native.get('guid') and native['targetOwned'] and target.endswith(('.prefab', '.unity')):
            native['identityStatus'] = 'owned-native-asset-guid-only'
            native['limitation'] = 'GUID identifies the asset; component/node localID or object reference is not present in these maps.'
        else:
            native['identityStatus'] = 'unresolved-native-object-identity'
            native['limitation'] = 'No owned native prefab/scene path plus verified .meta GUID was found.'
        result['nativeTargets'].append(native)
    if not result['nativeTargets']:
        result['unresolved'].append({'reason': 'resource-path row has no usable target path'})
    readback_rows = [dict(row) for row in indexed.get('readbackAssets', {}).get(source_asset, [])]
    result['sourcePrefabReadback'] = readback_rows
    if not readback_rows:
        result['unresolved'].append({'reason': 'no exact sourceAsset entry in manifest-owned editor-readback sourcePrefabs'})
    for row in readback_rows:
        matching_target = next((target for target in result['nativeTargets']
            if target.get('path') == row.get('path') and target.get('guid') == row.get('guid')), None)
        if matching_target is None:
            result['unresolved'].append({'reason': 'editor-readback sourcePrefab path/GUID does not match an owned resource-path target'})
        else:
            row['identityMatch'] = True
            row['identityMatchStatus'] = 'source-prefab-path-and-guid-match-owned-target'
    return result


def _preview_reference(references, source_map_components, indexed, root, owned, yaml_ids):
    """Validate a readback fileID only as a preview reference, never as a source prefab localID."""
    preview_targets = sorted({row.get('target') for row in source_map_components if isinstance(row.get('target'), str)})
    preview_meta = []
    readback_summary = indexed.get('readbackSummary') or {}
    invalid = False
    for reference in references:
        file_id = reference.get('prefabFileId')
        if not reference.get('bound') or type(file_id) not in (int, str) or isinstance(file_id, bool):
            invalid = True
            continue
        for path in preview_targets:
            meta_row = owned.get(path + '.meta')
            prefab_row = owned.get(path)
            if not meta_row or not prefab_row or not path.endswith('.prefab'):
                continue
            meta_raw = _owned_bytes(root, owned, path + '.meta', maximum=64 * 1024)
            match = _GUID.search(meta_raw.decode('utf-8', 'strict'))
            if not match or match.group(1) != readback_summary.get('prefabGuid'):
                continue
            if path not in yaml_ids:
                prefab_raw = _owned_bytes(root, owned, path, maximum=MAPPING_MAX_BYTES)
                ids = set(re.findall(rb'(?m)^--- !u!\d+ &(\d+)\s*$', prefab_raw))
                yaml_ids[path] = {value.decode('ascii') for value in ids}
            if str(file_id) not in yaml_ids[path]:
                continue
            preview_meta.append({'path': path, 'guid': match.group(1), 'prefabFileId': str(file_id),
                'field': reference.get('field'), 'index': reference.get('index'),
                'prefabSha256': prefab_row['sha256'], 'metaSha256': meta_row['sha256'],
                'status': 'verified-preview-object-reference-only'})
    unique = {(row['path'], row['guid'], row['prefabFileId'], row.get('field'), row.get('index')): row for row in preview_meta}
    preview_meta = list(unique.values())
    if len(preview_meta) == 1:
        return {**preview_meta[0], 'scope': 'editable preview prefab, not the final source-asset prefab'}
    if len(preview_meta) > 1:
        return {'status': 'ambiguous', 'candidates': preview_meta,
                'reason': 'more than one preview path has the pinned GUID and localID'}
    if invalid:
        return {'status': 'unresolved', 'reason': 'at least one readback view reference is not bound to a valid prefabFileId'}
    return {'status': 'unresolved', 'reason': 'readback prefabFileId is not declared in an owned preview prefab whose GUID matches readback'}


def build_asset_context(stage, module_classes, *, cache_root=None):
    """Return a compact module-local context joining exact code owners to mapped assets.

    ``stage`` is the checked result of ``code_architecture_modules._pin_stage``.
    Every candidate mapping is verified against the frozen candidate manifest.
    Component/node fileIDs are never inferred; rows without explicit serialized
    references stay unresolved.
    """
    source_root = stage['request'].get('sourceRoot')
    if not source_root:
        return {'context': {'schemaVersion': SCHEMA, 'status': 'unavailable', 'bindings': [],
            'unresolved': [{'reason': 'global architecture has no pinned candidate sourceRoot'}],
            'runtimeUse': 'source UUIDs are indexing evidence only; native serialized references are required'},
            'cache': {'status': 'not-used'}}
    root, manifest, owned, source_pin = snapshot(source_root)
    if source_pin != stage['pins']['sourceManifestSha256']:
        fail('CODE_ARCH_ASSET_SOURCE', str(root), 'Candidate manifest differs from global architecture source pin')
    binding_doc, binding_sha = _binding_file(stage, root, owned)
    if binding_doc is None:
        binding_rows = []
    else:
        binding_rows = _rows(binding_doc, 'bindings', BINDING_PATH)
    indexed, mapping_pins, cache_status = _index_mappings(root, owned, source_pin, cache_root,
        binding_sha=binding_sha,
        wanted_assets={row.get('sourceAsset') for row in binding_rows if isinstance(row.get('sourceAsset'), str)},
        wanted_nodes={row.get('sourceNode') for row in binding_rows if isinstance(row.get('sourceNode'), str)},
        wanted_components={row.get('sourceComponent') for row in binding_rows if isinstance(row.get('sourceComponent'), str)})

    units = {row['id']: row for row in stage['catalog'].get('sourceUnits', [])}
    selected_ids = sorted({unit_id for cls in module_classes for unit_id in cls.get('sourceUnitIds', [])})
    selected_source_ids = set()
    region_owners = {}
    source_owner_rows = []
    for unit_id in selected_ids:
        unit = units.get(unit_id)
        if unit is None:
            fail('CODE_ARCH_ASSET_OWNERSHIP', unit_id, 'Class references a source unit absent from the pinned catalog')
        ids = unit.get('sourceIds', [])
        source_owner_rows.append({'sourceUnitId': unit_id, 'sourceSha256': unit.get('sourceSha256'),
            'sourceBytes': unit.get('sourceBytes'), 'sourceIds': ids})
        class_ids = sorted(cls.get('id') for cls in module_classes if unit_id in cls.get('sourceUnitIds', []))
        for source_id in ids:
            if isinstance(source_id, str):
                selected_source_ids.add(source_id)
                owner = region_owners.setdefault(source_id, {'sourceUnitIds': [], 'classIds': []})
                owner['sourceUnitIds'].append(unit_id)
                owner['classIds'].extend(class_ids)

    selected_bindings = [row for row in binding_rows if row.get('codeRegion') in selected_source_ids]
    bindings = []
    unresolved = []
    yaml_ids = {}
    for row in selected_bindings:
        source_component = row.get('sourceComponent')
        source_node = row.get('sourceNode')
        component_rows = indexed['sourceComponents'].get(source_component, []) if isinstance(source_component, str) else []
        node_rows = indexed['sourceNodes'].get(source_node, []) if isinstance(source_node, str) else []
        asset = _asset_identity(row.get('sourceAsset'), indexed, root, owned) if isinstance(row.get('sourceAsset'), str) else None
        preview_ref = None
        view_rows = indexed.get('viewReferences', {}).get(source_component, []) if isinstance(source_component, str) else []
        if view_rows:
            preview_ref = _preview_reference(view_rows, component_rows, indexed, root, owned, yaml_ids)
        source_prefab_nodes = indexed.get('readbackNodes', {}).get(source_node, []) if isinstance(source_node, str) else []
        binding = {'codeRegion': row.get('codeRegion'), 'evidence': row.get('evidence'),
            'sourceOwnership': {'sourceUnitIds': sorted(region_owners.get(row.get('codeRegion'), {}).get('sourceUnitIds', [])),
                                'classesWithThisSourceUnit': sorted(set(region_owners.get(row.get('codeRegion'), {}).get('classIds', []))),
                                'classOwnershipResolution': 'shared-source-unit only; this does not prove a direct class-to-node/component relationship'},
            'sourceAsset': row.get('sourceAsset'), 'sourceComponent': source_component, 'sourceNode': source_node,
            'nativeComponentStatus': row.get('nativeComponent'),
            'sourceMapComponents': component_rows, 'sourceMapNodes': node_rows,
            'sourcePrefabNodeReadback': source_prefab_nodes, 'assetIdentity': asset,
            'previewReadbackReference': preview_ref,
            'serializedReference': None,
            'status': 'asset-identity-context-only' if asset and asset.get('nativeTargets') else 'unresolved'}
        missing = []
        if not component_rows:
            missing.append('no exact sourceComponent match in source-map.components')
        if not node_rows:
            missing.append('no exact sourceNode match in source-map.nodes')
        if not asset or not asset.get('nativeTargets'):
            missing.append('no exact mapped native asset identity')
        else:
            missing.append('source-prefab object localID is not provided; any readback prefabFileId is preview-only')
        if view_rows and (not preview_ref or preview_ref.get('status') != 'verified-preview-object-reference-only'):
            missing.append('preview readback view reference did not verify against the owned preview prefab YAML/GUID')
        binding['unresolvedReasons'] = missing
        bindings.append(binding)
        if missing:
            unresolved.append({'codeRegion': row.get('codeRegion'), 'sourceComponent': source_component,
                               'sourceNode': source_node, 'reasons': missing})

    status = 'mapped-with-unresolved-object-references' if bindings else ('no-code-bindings-for-selected-owners' if selected_source_ids else 'no-source-owned-classes')
    context = {'schemaVersion': SCHEMA, 'status': status, 'sourceManifestSha256': source_pin,
        'architectureSha256': stage['pins'].get('architectureSha256'), 'mappingPins': mapping_pins,
        'componentBindingsSha256': binding_sha, 'editorReadbackSummary': indexed.get('readbackSummary'),
        'sourceOwners': source_owner_rows,
        'bindings': bindings, 'unresolved': unresolved,
        'runtimeUse': 'Authoring/serialization identity evidence only. Do not look up source UUIDs at runtime; use typed serialized native references. Editor serialization/connection has not been executed.'}
    return {'context': context, 'cache': {'status': cache_status, 'sourceManifestSha256': source_pin,
        'mappingPins': mapping_pins}}


def write_module_context(stage, module_classes, context_root, files, *, cache_root=None):
    """Write the verified context, sharding oversized collections without truncation.

    Contexts up to 8 MiB retain the original single-file format. Larger contexts
    use an index at the same path and bounded JSON row shards listed by that index.
    """
    context_root = safe(context_root)
    result = build_asset_context(stage, module_classes, cache_root=cache_root)
    context = result['context']
    raw = encoded(context)
    existing = sum(row.get('bytes', 0) for row in files.values() if isinstance(row, dict))
    if existing + len(raw) > ASSET_CONTEXT_GROUP_BYTES:
        fail('CODE_ARCH_ASSET_BUDGET', 'module-asset-bindings.json',
             f'Complete module context group is at least {existing + len(raw)} bytes; limit is {ASSET_CONTEXT_GROUP_BYTES}')
    if len(raw) <= ASSET_CONTEXT_SHARD_BYTES:
        outputs = {'module-asset-bindings.json': raw}
        summary = {'format': 'single-json', 'sha256': sha(raw), 'bytes': len(raw)}
    else:
        outputs, summary = _shard_context(context, raw)

    # Account for all context already staged for this worker. Sharding must not
    # bypass its fixed 64 MiB aggregate input budget.
    total = existing + sum(len(data) for data in outputs.values())
    if total > ASSET_CONTEXT_GROUP_BYTES:
        fail('CODE_ARCH_ASSET_BUDGET', 'module-asset-bindings.json',
             f'Complete module context group is {total} bytes; limit is {ASSET_CONTEXT_GROUP_BYTES}')

    targets = [(relative, inside(context_root, relative), data) for relative, data in outputs.items()]
    for relative, path, _ in targets:
        if path.exists() or inside(path.parent, path.name + '.tmp').exists():
            fail('CODE_ARCH_ASSET_OUTPUT', relative, 'Refusing to overwrite an existing module context file')
    written = []
    for relative, path, data in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = inside(path.parent, path.name + '.tmp')
        temp.write_bytes(data)
        temp.replace(path)
        files[relative] = {'sha256': sha(data), 'bytes': len(data)}
        written.append(relative)
    return {'path': '__Context/module-asset-bindings.json', 'sha256': summary['sha256'],
            'bytes': summary['bytes'], 'format': summary['format'],
            'indexPath': summary.get('indexPath'), 'contextSha256': summary.get('contextSha256'),
            'contextBytes': summary.get('contextBytes'), 'shards': summary.get('shards', []),
            'shardBytes': summary.get('shardBytes', 0), 'groupBytes': sum(len(x) for x in outputs.values()),
            'workerContextBytes': total, 'workerContextBudgetBytes': ASSET_CONTEXT_GROUP_BYTES,
            'status': context['status'], 'unresolvedCount': len(context['unresolved']),
            'bindingCount': len(context['bindings']), 'sourceOwnerCount': len(context['sourceOwners']),
            'cache': result['cache']}


def _shard_context(context, context_raw):
    collections = {}
    metadata = {}
    for key, value in context.items():
        if isinstance(value, list):
            collections[key] = value
        else:
            metadata[key] = value

    outputs = {}
    shard_rows = []
    for kind in sorted(collections):
        rows = collections[kind]
        chunks = []
        chunk = []
        estimated = 1024
        for row in rows:
            row_raw = encoded(row)
            row_cost = len(row_raw) + row_raw.count(b'\n') * 2 + 8
            if row_cost + 1024 > ASSET_CONTEXT_SHARD_BYTES:
                fail('CODE_ARCH_ASSET_BUDGET', kind, 'One asset-context row exceeds the 8 MiB shard limit')
            if chunk and estimated + row_cost > ASSET_CONTEXT_SHARD_BYTES - 64 * 1024:
                chunks.append(chunk)
                chunk = []
                estimated = 1024
            chunk.append(row)
            estimated += row_cost
        if chunk:
            chunks.append(chunk)
        collections[kind] = chunks

    # Pretty-printed JSON adds indentation at each nesting level. The size
    # estimate above is intentionally conservative, but split again using the
    # exact serializer before assigning stable shard ordinals.
    for kind in sorted(collections):
        normalized = []
        for initial in collections[kind]:
            pending = [initial]
            while pending:
                rows = pending.pop()
                probe = encoded({'schemaVersion': SHARD_SCHEMA,
                    'sourceManifestSha256': context.get('sourceManifestSha256'),
                    'kind': kind, 'ordinal': 0, 'count': 1, 'rows': rows})
                if len(probe) <= ASSET_CONTEXT_SHARD_BYTES:
                    normalized.append(rows)
                elif len(rows) == 1:
                    fail('CODE_ARCH_ASSET_BUDGET', kind, 'One asset-context row exceeds the 8 MiB shard limit')
                else:
                    middle = len(rows) // 2
                    pending.append(rows[middle:])
                    pending.append(rows[:middle])
        collections[kind] = normalized

    shard_count = sum(len(chunks) for chunks in collections.values())
    if shard_count > ASSET_CONTEXT_MAX_SHARDS:
        fail('CODE_ARCH_ASSET_BUDGET', 'module-asset-bindings.json',
             f'Asset-context shard count {shard_count} exceeds limit {ASSET_CONTEXT_MAX_SHARDS}')
    for kind in sorted(collections):
        chunks = collections[kind]
        for ordinal, rows in enumerate(chunks):
            document = {'schemaVersion': SHARD_SCHEMA, 'sourceManifestSha256': context.get('sourceManifestSha256'),
                        'kind': kind, 'ordinal': ordinal, 'count': len(chunks), 'rows': rows}
            shard_raw = encoded(document)
            if len(shard_raw) > ASSET_CONTEXT_SHARD_BYTES:
                fail('CODE_ARCH_ASSET_BUDGET', kind, 'Serialized asset-context shard exceeds 8 MiB')
            relative = f'module-asset-bindings.shards/{kind}-{ordinal:04d}-{sha(shard_raw)[:12]}.json'
            outputs[relative] = shard_raw
            shard_rows.append({'path': relative, 'sha256': sha(shard_raw), 'bytes': len(shard_raw),
                               'kind': kind, 'ordinal': ordinal, 'count': len(chunks), 'rowCount': len(rows)})

    index = {'schemaVersion': INDEX_SCHEMA,
        'sourceManifestSha256': context.get('sourceManifestSha256'),
        'architectureSha256': context.get('architectureSha256'),
        'contextSchemaVersion': context.get('schemaVersion'), 'contextStatus': context.get('status'),
        'contextSha256': sha(context_raw), 'contextBytes': len(context_raw),
        'groupBudgetBytes': ASSET_CONTEXT_GROUP_BYTES, 'maxShardBytes': ASSET_CONTEXT_SHARD_BYTES,
        'shardCount': len(shard_rows), 'shardBytes': sum(row['bytes'] for row in shard_rows),
        'metadata': metadata,
        'collections': {kind: {'rowCount': len(rows), 'shards': [row['path'] for row in shard_rows if row['kind'] == kind]}
                        for kind, rows in ((kind, [row for chunk in chunks for row in chunk])
                                           for kind, chunks in collections.items())},
        'shards': shard_rows}
    index_raw = encoded(index)
    if len(index_raw) > ASSET_CONTEXT_SHARD_BYTES:
        fail('CODE_ARCH_ASSET_BUDGET', 'module-asset-bindings.json', 'Shard index exceeds 8 MiB')
    outputs['module-asset-bindings.json'] = index_raw
    group_bytes = sum(len(data) for data in outputs.values())
    if group_bytes > ASSET_CONTEXT_GROUP_BYTES:
        fail('CODE_ARCH_ASSET_BUDGET', 'module-asset-bindings.json',
             f'Indexed context group is {group_bytes} bytes; limit is {ASSET_CONTEXT_GROUP_BYTES}')
    return outputs, {'format': INDEX_SCHEMA, 'sha256': sha(index_raw), 'bytes': len(index_raw),
                     'contextSha256': sha(context_raw), 'contextBytes': len(context_raw),
                     'indexPath': 'module-asset-bindings.json', 'shards': shard_rows,
                     'shardBytes': index['shardBytes']}


def load_module_context(path):
    """Load a legacy single-file report or verify and reconstruct a sharded index."""
    index_path = safe(path)
    raw = read(index_path, max_bytes=ASSET_CONTEXT_SHARD_BYTES)
    document = load(raw, max_nodes=4_000_000, max_depth=128)
    if document.get('schemaVersion') != INDEX_SCHEMA:
        if not isinstance(document, dict) or document.get('schemaVersion') != SCHEMA:
            fail('CODE_ARCH_ASSET_INDEX', str(index_path), 'Unknown module asset-context schema')
        return document
    shard_rows = document.get('shards')
    collections = document.get('collections')
    metadata = document.get('metadata')
    if (not isinstance(shard_rows, list) or len(shard_rows) != document.get('shardCount') or
            len(shard_rows) > ASSET_CONTEXT_MAX_SHARDS or not isinstance(collections, dict) or
            not isinstance(metadata, dict) or document.get('groupBudgetBytes') != ASSET_CONTEXT_GROUP_BYTES or
            document.get('maxShardBytes') != ASSET_CONTEXT_SHARD_BYTES):
        fail('CODE_ARCH_ASSET_INDEX', str(index_path), 'Malformed shard index or unsupported group budget')
    index_root = index_path.parent
    assembled = dict(metadata)
    expected_manifest = document.get('sourceManifestSha256')
    listed_paths = set()
    grouped = {kind: [] for kind in collections}
    total_bytes = len(raw)
    for item in shard_rows:
        if not isinstance(item, dict):
            fail('CODE_ARCH_ASSET_INDEX', str(index_path), 'Malformed shard descriptor')
        relative = item.get('path')
        if not isinstance(relative, str) or relative in listed_paths:
            fail('CODE_ARCH_ASSET_INDEX', str(index_path), 'Duplicate or invalid shard path')
        listed_paths.add(relative)
        shard_path = inside(index_root, relative)
        shard_raw = read(shard_path, max_bytes=ASSET_CONTEXT_SHARD_BYTES)
        if len(shard_raw) != item.get('bytes') or sha(shard_raw) != item.get('sha256'):
            fail('CODE_ARCH_ASSET_INDEX', relative, 'Shard bytes differ from index SHA/size')
        total_bytes += len(shard_raw)
        shard = load(shard_raw, max_nodes=8_000_000, max_depth=128)
        if (len(shard_raw) > ASSET_CONTEXT_SHARD_BYTES or shard.get('schemaVersion') != SHARD_SCHEMA or
                shard.get('sourceManifestSha256') != expected_manifest or shard.get('kind') != item.get('kind') or
                shard.get('ordinal') != item.get('ordinal') or shard.get('count') != item.get('count') or
                not isinstance(shard.get('rows'), list) or len(shard['rows']) != item.get('rowCount')):
            fail('CODE_ARCH_ASSET_INDEX', relative, 'Shard identity or row count differs from index')
        if shard.get('kind') not in grouped:
            fail('CODE_ARCH_ASSET_INDEX', relative, 'Shard kind is absent from collection index')
        grouped[shard['kind']].append((shard['ordinal'], shard['rows']))
    if total_bytes > ASSET_CONTEXT_GROUP_BYTES:
        fail('CODE_ARCH_ASSET_BUDGET', str(index_path), 'Indexed asset-context group exceeds 64 MiB')
    for kind, descriptor in collections.items():
        if not isinstance(descriptor, dict) or type(descriptor.get('rowCount')) is not int:
            fail('CODE_ARCH_ASSET_INDEX', kind, 'Malformed collection descriptor')
        paths = descriptor.get('shards')
        if not isinstance(paths, list) or any(path not in listed_paths for path in paths):
            fail('CODE_ARCH_ASSET_INDEX', kind, 'Collection references an unlisted shard')
        parts = sorted(grouped[kind])
        if [next(row['path'] for row in shard_rows if row['kind'] == kind and row['ordinal'] == ordinal)
                for ordinal, _ in parts] != paths:
            fail('CODE_ARCH_ASSET_INDEX', kind, 'Collection shard order differs from index')
        if parts and ([ordinal for ordinal, _ in parts] != list(range(len(parts))) or
                      any(next(row['count'] for row in shard_rows if row['kind'] == kind and row['ordinal'] == ordinal) != len(parts)
                          for ordinal, _ in parts)):
            fail('CODE_ARCH_ASSET_INDEX', kind, 'Collection shard ordinals/counts are incomplete')
        rows = [row for _, part in parts for row in part]
        if len(rows) != descriptor['rowCount']:
            fail('CODE_ARCH_ASSET_INDEX', kind, 'Reconstructed collection count differs from index')
        assembled[kind] = rows
    if len(listed_paths) != len(shard_rows) or sum(row['bytes'] for row in shard_rows) != document.get('shardBytes'):
        fail('CODE_ARCH_ASSET_INDEX', str(index_path), 'Shard byte total differs from index')
    reconstructed = encoded(assembled)
    if len(reconstructed) != document.get('contextBytes') or sha(reconstructed) != document.get('contextSha256'):
        fail('CODE_ARCH_ASSET_INDEX', str(index_path), 'Reconstructed context differs from the complete context SHA/size')
    return assembled
