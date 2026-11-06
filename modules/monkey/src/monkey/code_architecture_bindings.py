"""Source-pinned Unity Prefab authoring plans for architecture View components.

This module validates references and emits an Editor-authoring intent document.
It never edits a Prefab and never interprets source UUIDs at runtime.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import PurePosixPath

from .sources.compiled import ADAPTERS, budget, decode_document, fail, uuid_full


SCHEMA = 'monkey-native-prefab-authoring-plan/1'
MODULE_SCHEMA = 'monkey-native-architecture-module/1'
ASSET_CONTEXT_SCHEMA = 'monkey-code-architecture-asset-context/1'
SHA256 = re.compile(r'^[0-9a-f]{64}$')
GUID = re.compile(r'^[0-9a-f]{32}$')
_SOURCE_DECORATOR = re.compile(
    rb'\w+\(\[\s*\w+\(([^()]+)\)\s*\],\s*\w+\.prototype,\s*"([A-Za-z_$][\w$]*)",\s*void\s+0\s*\)'
)
_CSHARP_FIELD = re.compile(
    rb'\[\s*SerializeField\s*\]\s*(?:private|protected|internal|public)\s+'
    rb'([A-Za-z_][A-Za-z0-9_\.<>?,\[\]]*)\s+([A-Za-z_][A-Za-z0-9_]*)\s*;'
)
_META_GUID = re.compile(rb'(?m)^guid:\s*([0-9a-f]{32})\s*$')
_NATIVE_SERIALIZED_BASE_TYPES = {
    'TMPro.TMP_Text': {'TMPro.TextMeshProUGUI', 'TMPro.TextMeshPro'},
}


def _reject(location: str, message: str) -> None:
    fail('CODE_ARCHITECTURE_BINDING', location, message)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _mapping(value, location):
    if not isinstance(value, dict):
        _reject(location, 'Expected an object')
    return value


def _list(value, location):
    if not isinstance(value, list):
        _reject(location, 'Expected an array')
    return value


def _string(value, location):
    if not isinstance(value, str) or not value.strip():
        _reject(location, 'Expected a non-empty string')
    try:
        value.encode('utf-8')
    except UnicodeError:
        _reject(location, 'Invalid Unicode string')
    return value


def _relative_path(value, location):
    value = _string(value, location)
    if '\\' in value or value.startswith('/') or re.match(r'^[A-Za-z]:', value):
        _reject(location, 'Expected a portable project-relative path')
    parts = value.split('/')
    if any(p in ('', '.', '..') for p in parts) or PurePosixPath(value).is_absolute():
        _reject(location, 'Path must not traverse or contain empty segments')
    return value


def _hash(value, location):
    value = _string(value, location)
    if not SHA256.fullmatch(value):
        _reject(location, 'Expected lowercase SHA-256 hex')
    return value


def _one(rows, predicate, location, description):
    matches = [row for row in rows if isinstance(row, dict) and predicate(row)]
    if len(matches) != 1:
        _reject(location, f'Expected exactly one {description}; found {len(matches)}')
    return matches[0]


def extract_source_component_fields(source_unit_bytes: bytes, *, base_offset: int = 0) -> list[dict]:
    """Extract literal Cocos property decorators from one pinned source unit.

    Only explicit decorator type expressions are surfaced; aliased expressions
    are retained as aliases and are not guessed or resolved.
    """
    if not isinstance(source_unit_bytes, bytes):
        _reject('sourceUnitBytes', 'Expected immutable source bytes')
    rows = []
    seen = set()
    for match in _SOURCE_DECORATOR.finditer(source_unit_bytes):
        type_expression = match.group(1).decode('utf-8', 'strict')
        name = match.group(2).decode('utf-8', 'strict')
        if name in seen:
            _reject(f'sourceUnitBytes@{base_offset + match.start()}', f'Duplicate source property {name!r}')
        seen.add(name)
        rows.append({
            'sourceProperty': name,
            'sourceTypeExpression': type_expression,
            'sourceTypeStatus': 'literal' if type_expression.startswith(('cc.', 'sp.')) else 'alias-unresolved',
            'sourceSpan': {'start': base_offset + match.start(), 'end': base_offset + match.end()},
            'sourceSpanSha256': _sha(match.group(0)),
        })
    return rows


def extract_serialized_csharp_fields(class_source_bytes: bytes) -> list[dict]:
    """Return exact [SerializeField] declarations from a generated class file."""
    if not isinstance(class_source_bytes, bytes):
        _reject('classSourceBytes', 'Expected immutable C# source bytes')
    try:
        class_source_bytes.decode('utf-8', 'strict')
    except UnicodeError:
        _reject('classSourceBytes', 'C# source must be UTF-8')
    rows = []
    seen = set()
    for match in _CSHARP_FIELD.finditer(class_source_bytes):
        field_type = match.group(1).decode('ascii')
        name = match.group(2).decode('ascii')
        if name in seen:
            _reject('classSourceBytes', f'Duplicate [SerializeField] field {name!r}')
        seen.add(name)
        rows.append({'field': name, 'fieldType': field_type,
                     'sourceSpan': {'start': match.start(), 'end': match.end()},
                     'sourceSpanSha256': _sha(match.group(0))})
    return rows


def _prefab_roots(prefab_bytes: bytes):
    """Read only Unity YAML GameObject/Transform identities needed for root pinning."""
    try:
        text = prefab_bytes.decode('utf-8', 'strict')
    except UnicodeError:
        _reject('prefabBytes', 'Unity Prefab YAML must be UTF-8')
    objects = {}
    object_re = re.compile(r'(?ms)^--- !u!1 &(\d+)\s*\nGameObject:\n(.*?)(?=^--- !u!|\Z)')
    for match in object_re.finditer(text):
        name = re.search(r'(?m)^  m_Name: (.*)$', match.group(2))
        if name:
            value = name.group(1).strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1].replace('\\"', '"')
            objects[match.group(1)] = value
    transforms = {}
    transform_re = re.compile(r'(?ms)^--- !u!(?:4|224) &(\d+)\s*\n(?:Transform|RectTransform):\n(.*?)(?=^--- !u!|\Z)')
    for match in transform_re.finditer(text):
        body = match.group(2)
        game_object = re.search(r'(?m)^  m_GameObject: \{fileID: (\d+)\}', body)
        parent = re.search(r'(?m)^  m_Father: \{fileID: (\d+)\}', body)
        if game_object and parent:
            transforms[match.group(1)] = {'gameObject': game_object.group(1), 'parent': parent.group(1)}
    roots = set()
    for transform in transforms.values():
        if transform['parent'] == '0' and transform['gameObject'] in objects:
            roots.add(transform['gameObject'])
    return objects, roots


def _unity_prefab_hierarchy(prefab_bytes: bytes, location: str):
    """Read the saved candidate Prefab's exact transform child ordering."""
    try:
        text = prefab_bytes.decode('utf-8', 'strict')
    except UnicodeError:
        _reject(location, 'Unity Prefab YAML must be UTF-8')
    blocks = list(re.finditer(r'(?ms)^--- !u!(\d+) &(\d+)\s*\n(.*?)(?=^--- !u!|\Z)', text))
    objects = {}
    transforms = {}
    for match in blocks:
        class_id, file_id, body = int(match.group(1)), match.group(2), match.group(3)
        if class_id == 1:
            name = re.search(r'(?m)^  m_Name: (.*)$', body)
            if not name or file_id in objects:
                _reject(location, 'GameObject name is missing or fileID is duplicated')
            value = name.group(1).strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1].replace('\\"', '"')
            component_ids = re.findall(r'(?m)^  - component: \{fileID: (-?\d+)\}', body)
            objects[file_id] = {'name': value, 'componentIds': component_ids}
        elif class_id in (4, 224):
            game_object = re.search(r'(?m)^  m_GameObject: \{fileID: (\d+)\}', body)
            parent = re.search(r'(?m)^  m_Father: \{fileID: (\d+)\}', body)
            children_block = re.search(
                r'(?ms)^  m_Children:\s*\n(.*?)(?=^  m_Father:|^  m_RootOrder:|^  m_LocalEulerAnglesHint:|\Z)',
                body,
            )
            if not game_object or not parent or game_object.group(1) in transforms:
                _reject(location, 'Transform has missing GameObject/parent or duplicate owner')
            children = re.findall(r'(?m)^  - \{fileID: (\d+)\}', children_block.group(1)) if children_block else []
            transforms[game_object.group(1)] = {
                'transformId': file_id, 'parentTransformId': parent.group(1), 'childTransformIds': children,
            }
    if not objects or set(objects) != set(transforms):
        _reject(location, 'Every candidate GameObject must have exactly one Transform or RectTransform')
    transform_owner = {row['transformId']: game_object for game_object, row in transforms.items()}
    if len(transform_owner) != len(transforms):
        _reject(location, 'Transform fileIDs must be unique')
    roots = [game_object for game_object, row in transforms.items() if row['parentTransformId'] == '0']
    if len(roots) != 1:
        _reject(location, f'Expected one candidate Prefab root; found {len(roots)}')
    paths = {}
    stack = [(roots[0], ())]
    while stack:
        game_object, path = stack.pop()
        if game_object in paths:
            _reject(location, 'Candidate Prefab has a repeated/cyclic hierarchy node')
        row = objects[game_object]
        paths[game_object] = {'path': path, 'name': row['name'], 'componentIds': row['componentIds']}
        transform = transforms[game_object]
        for child_index, transform_id in reversed(list(enumerate(transform['childTransformIds']))):
            child = transform_owner.get(transform_id)
            if child is None or transforms[child]['parentTransformId'] != transform['transformId']:
                _reject(location, 'Child transform reference does not agree with its parent')
            stack.append((child, path + (child_index,)))
    if len(paths) != len(objects):
        _reject(location, 'Candidate Prefab contains disconnected GameObjects')
    return {'rootGameObjectId': roots[0], 'objects': objects, 'transforms': transforms, 'paths': paths,
            'componentClassIds': {match.group(2): int(match.group(1)) for match in blocks}}


def _decode_packed_source_prefab(pack_bytes: bytes, config_bytes: bytes, *, source_asset_id: str,
                                source_component_id: str, pack_id: str,
                                expected_pack_sha256: str, expected_config_sha256: str):
    """Decode exactly one Cocos 2.4 packed Prefab section via the existing reader."""
    if not isinstance(pack_bytes, bytes) or not isinstance(config_bytes, bytes):
        _reject('sourcePrefabPack', 'Packed Prefab and project config must be immutable bytes')
    if len(pack_bytes) > 64 * 1024 * 1024 or len(config_bytes) > 8 * 1024 * 1024:
        _reject('sourcePrefabPack', 'Packed Prefab/config exceeds the bounded input budget')
    pack_sha = _hash(expected_pack_sha256, 'sourcePrefabPack.expectedSha256')
    config_sha = _hash(expected_config_sha256, 'sourceProjectConfig.expectedSha256')
    if _sha(pack_bytes) != pack_sha or _sha(config_bytes) != config_sha:
        _reject('sourcePrefabPack', 'Packed Prefab or project config bytes differ from their supplied pins')
    try:
        packed = json.loads(pack_bytes)
        config = json.loads(config_bytes)
    except (UnicodeError, json.JSONDecodeError):
        _reject('sourcePrefabPack', 'Packed Prefab and project config must be valid UTF-8 JSON')
    budget(config, max_depth=64, max_nodes=500_000)
    if not isinstance(packed, list) or len(packed) != 6 or packed[0] != 1 or not isinstance(packed[5], list):
        _reject('sourcePrefabPack', 'Expected the pinned Cocos 2.4 pack-v1 six-section envelope')
    if not isinstance(config, dict) or not isinstance(config.get('uuids'), list) or not isinstance(config.get('packs'), dict):
        _reject('sourceProjectConfig', 'Expected UUID and pack membership tables')
    source_asset_id = _string(source_asset_id, 'sourceAssetId')
    source_component_id = _string(source_component_id, 'sourceComponentId')
    match = re.fullmatch(re.escape(source_asset_id) + r'#(\d+)/components/(\d+)', source_component_id)
    if not match:
        _reject('sourceComponentId', 'Expected sourceAssetId#nodeIndex/components/componentOrdinal')
    node_index, component_ordinal = map(int, match.groups())
    if not re.fullmatch(r'[0-9a-f]{9}', pack_id):
        _reject('sourcePrefabPack.packId', 'Expected exact lower-case Cocos pack UUID prefix')
    members = config['packs'].get(pack_id)
    if not isinstance(members, list) or len(members) != len(packed[5]):
        _reject('sourceProjectConfig.packs', 'Pack membership must align one-to-one with encoded sections')
    try:
        source_uuid = source_asset_id.split(':', 1)[1]
    except IndexError:
        _reject('sourceAssetId', 'Expected a namespaced UUID')
    uuid_indexes = []
    for index, value in enumerate(config['uuids']):
        try:
            if uuid_full(value, f'sourceProjectConfig.uuids[{index}]') == source_uuid:
                uuid_indexes.append(index)
        except ValueError:
            continue
    if len(uuid_indexes) != 1:
        _reject('sourceProjectConfig.uuids', f'Expected one exact UUID for source asset; found {len(uuid_indexes)}')
    source_uuid_index = uuid_indexes[0]
    section_indexes = [index for index, value in enumerate(members) if value == source_uuid_index]
    if len(section_indexes) != 1:
        _reject('sourceProjectConfig.packs.' + pack_id, 'Source UUID must occur exactly once in the selected pack')
    section_index = section_indexes[0]
    decoded = decode_document(packed[:5] + packed[5][section_index], ADAPTERS[0])
    instances = decoded['instances']
    prefab_root = instances[decoded['root']]
    if not isinstance(prefab_root, dict) or prefab_root.get('__type__') != 'cc.Prefab':
        _reject('sourcePrefabPack.section', 'Exact UUID section did not decode to a cc.Prefab root')
    data_ref = prefab_root.get('data')
    root_node_index = data_ref.get('__id__') if isinstance(data_ref, dict) and set(data_ref) == {'__id__'} else None
    if type(root_node_index) is not int or not 0 <= root_node_index < len(instances):
        _reject('sourcePrefabPack.section.root', 'Prefab data does not reference one exact root node')
    root_node = instances[root_node_index]
    if not isinstance(root_node, dict) or root_node.get('__type__') != 'cc.Node':
        _reject('sourcePrefabPack.section.root', 'Prefab data target is not a cc.Node')
    if node_index != root_node_index:
        _reject('sourceComponentId', 'Pinned source component node index differs from the decoded Prefab root')
    components = root_node.get('_components')
    if not isinstance(components, list) or component_ordinal >= len(components):
        _reject('sourceComponentId', 'Pinned component ordinal is outside root _components')
    component = components[component_ordinal]
    if isinstance(component, dict) and set(component) == {'__id__'}:
        component_index = component['__id__']
        if type(component_index) is not int or not 0 <= component_index < len(instances):
            _reject('sourceComponentId', 'Root component index is outside the decoded Prefab')
        component = instances[component_index]
    if not isinstance(component, dict) or not isinstance(component.get('__type__'), str):
        _reject('sourceComponentId', 'Pinned root component is not a typed component object')

    paths = {root_node_index: []}
    parent = {root_node_index: None}
    child_indexes = {root_node_index: None}
    stack = [root_node_index]
    while stack:
        current = stack.pop()
        node = instances[current]
        if not isinstance(node, dict) or node.get('__type__') != 'cc.Node':
            _reject('sourcePrefabPack.nodes', f'Object {current} is not a cc.Node')
        children = node.get('_children', [])
        if not isinstance(children, list):
            _reject('sourcePrefabPack.nodes', f'Node {current} children are not an array')
        for child_index, reference in reversed(list(enumerate(children))):
            target = reference.get('__id__') if isinstance(reference, dict) and set(reference) == {'__id__'} else None
            if type(target) is not int or not 0 <= target < len(instances):
                _reject('sourcePrefabPack.nodes', f'Child of node {current} is not an exact object reference')
            if target in paths:
                _reject('sourcePrefabPack.nodes', 'Source Prefab has a repeated/cyclic node reference')
            child_node = instances[target]
            if not isinstance(child_node, dict) or child_node.get('__type__') != 'cc.Node':
                _reject('sourcePrefabPack.nodes', f'Child reference {target} does not point to cc.Node')
            paths[target] = paths[current] + [child_index]
            parent[target] = current
            child_indexes[target] = child_index
            stack.append(target)

    component_owners = {}
    for owner_index, node in enumerate(instances):
        if not isinstance(node, dict) or node.get('__type__') != 'cc.Node':
            continue
        for ordinal, reference in enumerate(node.get('_components', [])):
            target = reference.get('__id__') if isinstance(reference, dict) and set(reference) == {'__id__'} else None
            if type(target) is int:
                if target in component_owners and component_owners[target] != (owner_index, ordinal):
                    _reject('sourcePrefabPack.components', f'Component object {target} has multiple node owners')
                component_owners[target] = (owner_index, ordinal)
    source_nodes = []
    root_source_node_id = source_asset_id + '#' + str(root_node_index)
    for object_index, path in paths.items():
        node = instances[object_index]
        source_nodes.append({
            'sourceNodeId': source_asset_id + '#' + str(object_index),
            'name': _string(node.get('_name'), f'sourcePrefabPack.nodes[{object_index}]._name'),
            'parentSourceNodeId': None if parent[object_index] is None else source_asset_id + '#' + str(parent[object_index]),
            'childIndex': child_indexes[object_index],
            'sourcePath': list(path),
        })
    component_properties = []
    for property_name, value in component.items():
        if property_name in ('__type__', 'node'):
            continue
        evidence = {
            'sourceComponentId': source_component_id,
            'sourceProperty': property_name,
            'sourcePropertyValueSha256': _sha(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')),
            'sourcePropertyValue': value,
        }
        if isinstance(value, dict) and set(value) == {'__id__'} and type(value['__id__']) is int and 0 <= value['__id__'] < len(instances):
            target_index = value['__id__']
            target_object = instances[target_index]
            if isinstance(target_object, dict) and target_object.get('__type__') == 'cc.Node' and target_index in paths:
                evidence.update(targetSourceNodeId=source_asset_id + '#' + str(target_index), targetKind='node')
            elif target_index in component_owners:
                owner_index, target_ordinal = component_owners[target_index]
                if owner_index in paths:
                    evidence.update(targetSourceNodeId=source_asset_id + '#' + str(owner_index),
                                    targetSourceComponentId=source_asset_id + '#' + str(owner_index) + '/components/' + str(target_ordinal),
                                    targetSourceComponentType=target_object.get('__type__'), targetKind='component')
            else:
                evidence['unresolvedReason'] = 'The referenced object is neither a reachable source node nor an owned node component.'
        elif isinstance(value, dict) and set(value) == {'__uuid__'} and isinstance(value['__uuid__'], str):
            evidence.update(targetAssetId=value['__uuid__'], targetKind='asset')
        else:
            evidence['unresolvedReason'] = 'Serialized value is not an exact __id__ or __uuid__ reference.'
        component_properties.append(evidence)
    section_hash = _sha(json.dumps(packed[5][section_index], sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))
    graph = {
        'sourceAssetId': source_asset_id,
        'rootSourceNodeId': root_source_node_id,
        'sourceComponentId': source_component_id,
        'sourceComponentType': component.get('__type__'),
        'sourceComponentNodeId': source_asset_id + '#' + str(node_index),
        'nodes': source_nodes,
        'componentProperties': component_properties,
        'sourceEvidence': {
            'reader': 'monkey.sources.compiled.decode_document/cocos-2.4-compiled-v1-selected-pack-section',
            'sourceProfile': 'cocos-2.4.15-compiled-pack-v1',
            'sourcePackId': pack_id,
            'sourcePackSha256': pack_sha,
            'sourceProjectConfigSha256': config_sha,
            'sourceUuidIndex': source_uuid_index,
            'sourcePackSectionIndex': section_index,
            'sourcePackSectionSha256': section_hash,
            'decodedObjectCount': len(instances),
            'reachableNodeCount': len(paths),
        },
    }
    return graph


def _native_readback_nodes(readback_bytes: bytes, *, expected_sha256: str, source_asset: str,
                           prefab_path: str, prefab_guid: str):
    if not isinstance(readback_bytes, bytes) or len(readback_bytes) > 256 * 1024 * 1024:
        _reject('nativeReadbackBytes', 'Pinned Editor readback must be bounded immutable bytes')
    expected_sha256 = _hash(expected_sha256, 'nativeReadbackSha256')
    actual_sha256 = _sha(readback_bytes)
    if actual_sha256 != expected_sha256:
        _reject('nativeReadbackBytes', 'Editor readback bytes differ from their supplied pin')
    try:
        report = json.loads(readback_bytes)
    except (UnicodeError, json.JSONDecodeError):
        _reject('nativeReadbackBytes', 'Editor readback must be valid UTF-8 JSON')
    matches = [row for row in report.get('sourcePrefabs', []) if isinstance(row, dict) and row.get('sourceId') == source_asset]
    if len(matches) != 1:
        _reject('nativeReadbackBytes.sourcePrefabs', f'Expected one exact source Prefab readback; found {len(matches)}')
    prefab = matches[0]
    if prefab.get('path') != prefab_path or prefab.get('guid') != prefab_guid:
        _reject('nativeReadbackBytes.sourcePrefabs', 'Editor readback does not match the pinned candidate Prefab path/GUID')
    if prefab.get('savedReloaded') is not True or prefab.get('referencesVerified') is not True:
        _reject('nativeReadbackBytes.sourcePrefabs', 'Editor readback lacks saved/reloaded reference verification')
    rows = prefab.get('nodes')
    if not isinstance(rows, list) or len(rows) != prefab.get('nodeCount'):
        _reject('nativeReadbackBytes.sourcePrefabs.nodes', 'Node readback count differs from the saved Prefab receipt')
    seen = set()
    result = []
    for index, row in enumerate(rows):
        row = _mapping(row, f'nativeReadbackBytes.sourcePrefabs.nodes[{index}]')
        source_id = _string(row.get('sourceId'), f'nativeReadbackBytes.sourcePrefabs.nodes[{index}].sourceId')
        if not source_id.startswith(source_asset + '#') or source_id in seen:
            _reject(f'nativeReadbackBytes.sourcePrefabs.nodes[{index}]', 'Node identity is foreign or duplicated')
        seen.add(source_id)
        types = _list(row.get('componentTypes'), f'nativeReadbackBytes.sourcePrefabs.nodes[{index}].componentTypes')
        if any(not isinstance(value, str) for value in types):
            _reject(f'nativeReadbackBytes.sourcePrefabs.nodes[{index}].componentTypes', 'Expected exact Unity type names')
        result.append({'sourceId': source_id, 'prefabPath': prefab_path, 'prefabGuid': prefab_guid,
                       'hierarchy': _string(row.get('hierarchy'), f'nativeReadbackBytes.sourcePrefabs.nodes[{index}].hierarchy'),
                       'componentTypes': list(types)})
    return result, {'sha256': actual_sha256, 'sourcePrefabNodeCount': len(result),
                    'savedReloaded': prefab.get('savedReloaded'), 'referencesVerified': prefab.get('referencesVerified')}


def _native_field_type_match(field_type: str, component_types: list[str]) -> str:
    if field_type in component_types:
        return 'exact'
    if any(actual in _NATIVE_SERIALIZED_BASE_TYPES.get(field_type, set()) for actual in component_types):
        return 'known-derived-type'
    return 'missing'


def _source_path(graph: dict, target_id: str, location: str):
    nodes = _list(graph.get('nodes'), location + '.nodes')
    table = {}
    for index, row in enumerate(nodes):
        row = _mapping(row, f'{location}.nodes[{index}]')
        source_id = _string(row.get('sourceNodeId'), f'{location}.nodes[{index}].sourceNodeId')
        if source_id in table:
            _reject(f'{location}.nodes[{index}]', f'Duplicate source node {source_id!r}')
        name = _string(row.get('name'), f'{location}.nodes[{index}].name')
        parent = row.get('parentSourceNodeId')
        child_index = row.get('childIndex')
        if parent is not None and (type(child_index) is not int or child_index < 0):
            _reject(f'{location}.nodes[{index}].childIndex', 'Child nodes need a non-negative exact integer index')
        table[source_id] = {'sourceNodeId': source_id, 'name': name,
                            'parentSourceNodeId': parent, 'childIndex': child_index}
    root_id = _string(graph.get('rootSourceNodeId'), location + '.rootSourceNodeId')
    if root_id not in table or table[root_id]['parentSourceNodeId'] is not None:
        _reject(location + '.rootSourceNodeId', 'Source graph root is missing or has a parent')
    if target_id not in table:
        _reject(location + '.targetSourceNodeId', f'Unknown source node {target_id!r}')
    steps = []
    current = target_id
    visited = set()
    while current != root_id:
        if current in visited:
            _reject(location + '.nodes', 'Source hierarchy contains a cycle')
        visited.add(current)
        row = table[current]
        parent_id = row['parentSourceNodeId']
        if parent_id not in table:
            _reject(location + '.nodes', f'Node {current!r} has an unknown parent')
        steps.append({'childIndex': row['childIndex'], 'expectedName': row['name'], 'sourceNodeId': current})
        current = parent_id
    root = table[root_id]
    steps.reverse()
    return [{'root': True, 'expectedName': root['name'], 'sourceNodeId': root_id,
             'sourceNodeType': 'cc.Node'}] + [dict(step, sourceNodeType='cc.Node') for step in steps]


def _annotate_native_node_types(path_steps: list[dict], readback_by_source: dict) -> list[dict]:
    result = []
    for step in path_steps:
        row = readback_by_source.get(step['sourceNodeId'])
        if row:
            types = row.get('componentTypes', [])
            step = dict(step, candidateNodeTypes=list(types),
                        candidateNodeType='UnityEngine.RectTransform' if 'UnityEngine.RectTransform' in types else None)
        result.append(step)
    return result


def _script_identity(value):
    if not isinstance(value, str):
        return None
    try:
        return uuid_full(value, 'scriptIdentity').lower()
    except (ValueError, TypeError):
        return None


def _has_monobehaviour_declaration(class_source_bytes, class_name):
    """Recognize the class declaration only in C# code, never in trivia/literals."""
    from .code_architecture_modules import _strip_csharp_comments_and_literals

    cleaned = _strip_csharp_comments_and_literals(class_source_bytes)
    if cleaned is None:
        return False
    declaration = re.compile(rb'\bclass\s+' + re.escape(class_name.encode('utf-8')) +
        rb'\b[^{};]*:\s*(?:(?:global::)?(?:UnityEngine\.)?MonoBehaviour)\b')
    return declaration.search(cleaned.encode('utf-8')) is not None


def _source_class_identity_proof(architecture, plan_class, receipt_class, module_manifest,
                                source_context, source_unit_id, code_region, binding,
                                source_component_type, class_path, class_sha,
                                class_source_bytes, source_file_bytes, source_start):
    """Verify the exact source class binding; source-unit sharing is insufficient."""
    binding_evidence = plan_class.get('bindingEvidence')
    proof = {
        'schemaVersion': 'monkey-source-class-identity-proof/1',
        'status': 'unresolved',
        'targetClass': {'classId': plan_class.get('id'), 'className': plan_class.get('name'),
            'moduleId': plan_class.get('module'), 'classPath': class_path,
            'classSha256': class_sha, 'classBytes': len(class_source_bytes),
            'moduleReceiptSourceUnitIds': receipt_class.get('sourceUnitIds', [])},
        'sourceUnit': {'sourceUnitId': source_unit_id, 'sourcePath': source_context.get('sourcePath'),
            'sourceSha256': source_context.get('sourceSha256'), 'sourceBytes': source_context.get('sourceBytes'),
            'spanSha256': source_context.get('spanSha256')},
        'sourceCodeRegion': code_region,
        'sourceBinding': {'evidence': binding.get('evidence'), 'sourceAsset': binding.get('sourceAsset'),
            'sourceComponent': binding.get('sourceComponent'), 'sourceNode': binding.get('sourceNode')},
        'architectureSha256': module_manifest.get('architectureSha256'),
        'moduleReceiptSha256': module_manifest.get('receiptSha256'),
        'sourceManifestSha256': module_manifest.get('sourceManifestSha256'),
    }
    if not isinstance(binding_evidence, dict) or not binding_evidence.get('sourceIds'):
        proof['reason'] = 'Legacy architecture class lacks exact bindingEvidence.sourceIds; shared source-unit ownership cannot establish a script-to-View identity.'
        return proof
    if type(binding_evidence.get('literalBindingCount')) is not int:
        proof['reason'] = 'Legacy architecture class lacks a pinned literalBindingCount for its source identity.'
        return proof
    source_ids = binding_evidence.get('sourceIds')
    if not isinstance(source_ids, list) or any(not isinstance(value, str) for value in source_ids):
        _reject('architecture.classes.bindingEvidence.sourceIds', 'Expected source identity strings')
    if binding_evidence.get('literalBindingCount') != 1:
        _reject('architecture.classes.bindingEvidence.literalBindingCount', 'Expected exactly one literal source binding for the target MonoBehaviour')
    if code_region not in source_ids:
        _reject('architecture.classes.bindingEvidence.sourceIds', 'Target View does not declare the exact selected codeRegion')
    if source_ids.count(code_region) != 1:
        _reject('architecture.classes.bindingEvidence.sourceIds', 'Exact codeRegion must occur once in target class identity evidence')
    if binding.get('evidence') != 'exact_literal_script_identity':
        _reject('assetContext.binding.evidence', 'Source script component must have exact literal identity evidence')
    match = re.search(r'#([^#@]+)@([0-9]+)$', code_region)
    if not match:
        _reject('codeRegion', 'Expected exact source class identity with a class name and byte offset')
    source_class_name, offset = match.group(1), int(match.group(2))
    if source_start != offset:
        _reject('moduleManifest.sourceContexts.sourceBytes.start', 'Source unit start does not equal the exact codeRegion byte offset')
    code_path = code_region.rsplit('#', 1)[0].split(':', 1)[-1]
    source_path = source_context.get('sourcePath')
    if not isinstance(source_path, str) or not source_path.replace('\\', '/').endswith(code_path):
        _reject('moduleManifest.sourceContexts.sourcePath', 'Pinned source file does not match the exact codeRegion locator')
    if source_unit_id not in receipt_class.get('sourceUnitIds', []):
        _reject('moduleManifest.classes.sourceUnitIds', 'Module receipt class does not own the exact selected source unit')
    if plan_class.get('layer') != 'Presentation' or plan_class.get('kind') != 'class' or plan_class.get('baseType') != 'UnityEngine.MonoBehaviour':
        _reject('architecture.classes.' + str(plan_class.get('id')), 'Exact source script identity must map to a Presentation MonoBehaviour class')

    source_prefix = source_file_bytes[source_start:source_start + 2048]
    rf_match = re.match(rb'''cc\._RF\.push\(\s*\{\s*exports\s*:\s*\{\s*\}\s*\}\s*,\s*(["'])([^"']+)\1\s*,\s*(["'])([^"']+)\3\s*\)''', source_prefix)
    if not rf_match:
        _reject('sourceFileBytes', 'Exact source unit does not start with a literal Cocos cc._RF.push script identity')
    registered_script_id = rf_match.group(2).decode('utf-8', 'strict')
    registered_class_name = rf_match.group(4).decode('utf-8', 'strict')
    if registered_class_name != source_class_name:
        _reject('sourceFileBytes', 'Literal Cocos script class name differs from codeRegion identity')
    if _script_identity(registered_script_id) != _script_identity(source_component_type):
        _reject('assetContext.binding.sourceMapComponents.type', 'Literal Cocos script identity differs from the exact source component type')

    matching_classes = []
    for index, row in enumerate(_list(architecture.get('classes'), 'architecture.classes')):
        row = _mapping(row, f'architecture.classes[{index}]')
        evidence = row.get('bindingEvidence')
        if isinstance(evidence, dict) and isinstance(evidence.get('sourceIds'), list) and code_region in evidence['sourceIds']:
            matching_classes.append(row)
    match_ids = sorted(row.get('id') for row in matching_classes if isinstance(row.get('id'), str))
    if len(matching_classes) != 1 or matching_classes[0].get('id') != plan_class.get('id'):
        _reject('architecture.classes.bindingEvidence.sourceIds',
                'Exact source class identity must map to exactly one planned architecture class; source-unit sharing is not a substitute')

    class_name = plan_class.get('name')
    if not isinstance(class_name, str) or not class_name:
        _reject('architecture.classes.name', 'Exact target class identity lacks a class name')
    if not _has_monobehaviour_declaration(class_source_bytes, class_name):
        _reject('classSourceBytes', 'Pinned C# file does not declare the planned MonoBehaviour class')

    proof.update(status='verified-exact-source-script-to-monoBehaviour', sourceClassName=source_class_name,
        sourceByteOffset=offset, sourceIdentityEvidence={'literalBindingCount': 1,
            'sourceIds': list(source_ids)}, literalScriptRegistration={'scriptId': registered_script_id,
            'normalizedScriptId': _script_identity(registered_script_id), 'className': registered_class_name,
            'sourcePrefixSha256': _sha(source_prefix[:rf_match.end()])},
        sourceComponentType=source_component_type, architectureClassMatches=match_ids,
        targetUnityBaseType='UnityEngine.MonoBehaviour')
    proof['proofSha256'] = _sha(json.dumps(proof, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8'))
    return proof


def _assembled_script_meta(raw, expected_sha, architecture, architecture_sha, class_id,
                           class_path, class_sha, class_size, meta_bytes):
    """Accept new Script metadata only from an exact, unchanged assembled class."""
    from .io import load
    from .code_architecture_candidate import script_guid
    expected_sha = _hash(expected_sha, 'nativeCandidateManifestSha256')
    if not isinstance(raw, bytes) or len(raw)>128*1024*1024 or _sha(raw)!=expected_sha:
        _reject('nativeCandidateManifestBytes', 'Candidate manifest bytes/hash differ or exceed budget')
    candidate = _mapping(load(raw,max_nodes=8_000_000), 'nativeCandidateManifest')
    provenance = _mapping(candidate.get('provenance'), 'nativeCandidateManifest.provenance')
    if (candidate.get('schemaVersion')!=1 or
        candidate.get('targetProfile')!='unity-6000.6.2f1-ugui' or
        candidate.get('architectureSchemaVersion')!='monkey-native-architecture-candidate/1' or
        candidate.get('scriptIdentitySchema')!='monkey-native-script-identities/1' or
        provenance.get('kind')!='native-architecture-assembly' or
        provenance.get('architecturePlanSha256')!=architecture_sha or
        provenance.get('sourceCandidateManifestSha256')!=architecture.get('sourceManifestSha256')):
        _reject('nativeCandidateManifest', 'Candidate is not the exact architecture/source assembly')
    if _mapping(candidate.get('classPaths'),'nativeCandidateManifest.classPaths').get(class_id)!=class_path:
        _reject('nativeCandidateManifest.classPaths', 'Candidate class owner path differs')
    rows = _list(candidate.get('files'), 'nativeCandidateManifest.files')
    owned = {}
    folded = set()
    for row in rows:
        row = _mapping(row,'nativeCandidateManifest.files[]')
        path = _relative_path(row.get('path'),'nativeCandidateManifest.files.path')
        if path.casefold() in folded:
            _reject('nativeCandidateManifest.files', 'Candidate contains duplicate or case-colliding paths')
        folded.add(path.casefold());owned[path]=row
    code = _mapping(owned.get(class_path),'nativeCandidateManifest.classSource')
    owner = _mapping(code.get('provenance'),'nativeCandidateManifest.classSource.provenance')
    if (code.get('owner')!='generated' or code.get('sourceKind')!='architecture-module' or
        code.get('sha256')!=class_sha or code.get('bytes')!=class_size or owner.get('classId')!=class_id):
        _reject('nativeCandidateManifest.classSource', 'Candidate class differs from exact module bytes/owner; revised code requires its own new receipt')
    meta = _mapping(owned.get(class_path+'.meta'),'nativeCandidateManifest.scriptMeta')
    meta_owner = _mapping(meta.get('provenance'),'nativeCandidateManifest.scriptMeta.provenance')
    if (meta.get('owner')!='generated' or meta.get('sourceKind')!='architecture-script-meta' or
        meta_owner.get('classId')!=class_id or meta_owner.get('scriptPath')!=class_path or
        meta_owner.get('scriptSha256')!=class_sha):
        _reject('nativeCandidateManifest.scriptMeta', 'Script metadata belongs to another type or implementation')
    if not isinstance(meta_bytes, bytes) or _sha(meta_bytes)!=meta.get('sha256') or len(meta_bytes)!=meta.get('bytes'):
        _reject('scriptMetaBytes', 'Script metadata bytes differ from the assembled candidate')
    match = _META_GUID.search(meta_bytes)
    expected_guid = script_guid(_string(candidate.get('namespace'),'nativeCandidateManifest.namespace'),
        architecture.get('rootNamespace'),class_id)
    if match is None or match.group(1).decode('ascii')!=expected_guid or meta_owner.get('guid')!=expected_guid:
        _reject('nativeCandidateManifest.scriptMeta', 'Script GUID differs from deterministic architecture type identity')
    identity = _mapping(_mapping(candidate.get('scriptIdentities'), 'nativeCandidateManifest.scriptIdentities').get(class_id),
        'nativeCandidateManifest.scriptIdentity')
    if any(identity.get(key)!=value for key,value in dict(path=class_path,sha256=class_sha,
        metaPath=class_path+'.meta',metaSha256=meta['sha256'],guid=expected_guid).items()):
        _reject('nativeCandidateManifest.scriptIdentity', 'Script identity index differs from owned class/meta bytes')
    return {'manifestSha256':expected_sha,'scriptPath':class_path,'scriptSha256':class_sha,
            'metaPath':class_path+'.meta','metaSha256':meta['sha256'],'guid':expected_guid,
            'unityTypeStatus':'pending-whole-project-compile'}, meta


def build_prefab_authoring_plan(
    architecture: dict,
    module_manifest: dict,
    asset_context: dict,
    class_id: str,
    *,
    architecture_sha256: str,
    code_region: str,
    source_unit_id: str,
    source_file_bytes: bytes,
    class_source_bytes: bytes,
    prefab_bytes: bytes,
    prefab_meta_bytes: bytes,
    field_mappings: list | None = None,
    source_reference_graph: dict | None = None,
    target_node_readback: list | None = None,
    script_meta_bytes: bytes | None = None,
    source_prefab_pack_bytes: bytes | None = None,
    source_project_config_bytes: bytes | None = None,
    source_pack_id: str | None = None,
    source_prefab_pack_sha256: str | None = None,
    source_project_config_sha256: str | None = None,
    native_readback_bytes: bytes | None = None,
    native_readback_sha256: str | None = None,
    native_candidate_manifest_bytes: bytes | None = None,
    native_candidate_manifest_sha256: str | None = None,
) -> dict:
    """Build a fail-closed authoring plan from pinned module and asset evidence.

    Missing source property references or a missing Script meta create explicit
    unresolved entries. Preview fileIDs are never used as source prefab IDs.
    """
    architecture = _mapping(architecture, 'architecture')
    module_manifest = _mapping(module_manifest, 'moduleManifest')
    if isinstance(asset_context, dict) and 'context' in asset_context:
        asset_context = asset_context['context']
    asset_context = _mapping(asset_context, 'assetContext')
    class_id = _string(class_id, 'classId')
    architecture_sha256 = _hash(architecture_sha256, 'architectureSha256')
    if module_manifest.get('schemaVersion') != MODULE_SCHEMA:
        _reject('moduleManifest.schemaVersion', f'Expected {MODULE_SCHEMA!r}')
    if asset_context.get('schemaVersion') != ASSET_CONTEXT_SCHEMA:
        _reject('assetContext.schemaVersion', f'Expected {ASSET_CONTEXT_SCHEMA!r}')
    source_pin = _hash(architecture.get('sourceManifestSha256'), 'architecture.sourceManifestSha256')
    if module_manifest.get('sourceManifestSha256') != source_pin or asset_context.get('sourceManifestSha256') != source_pin:
        _reject('sourceManifestSha256', 'Architecture, module receipt, and asset context must share one source manifest')
    if module_manifest.get('architectureSha256') != architecture_sha256 or asset_context.get('architectureSha256') != architecture_sha256:
        _reject('architectureSha256', 'Module receipt or asset context does not match the pinned architecture plan')

    class_rows = _list(architecture.get('classes'), 'architecture.classes')
    plan_class = _one(class_rows, lambda row: row.get('id') == class_id, 'architecture.classes', f'class {class_id!r}')
    receipt_class = _one(_list(module_manifest.get('classes'), 'moduleManifest.classes'),
                         lambda row: row.get('classId') == class_id, 'moduleManifest.classes', f'class receipt {class_id!r}')
    if plan_class.get('layer') != 'Presentation' or plan_class.get('kind') != 'class':
        _reject('architecture.classes.' + class_id, 'Only a Presentation class View can receive this Prefab authoring plan')
    if plan_class.get('module') != module_manifest.get('moduleId') or receipt_class.get('module') != plan_class.get('module'):
        _reject('moduleManifest.moduleId', 'View class is not owned by the pinned module')
    class_path = _relative_path(receipt_class.get('path'), 'moduleManifest.classes.path')
    if _relative_path(plan_class.get('path', class_path), 'architecture.classes.path') != class_path:
        _reject('architecture.classes.path', 'Architecture class path and module receipt path differ')
    file_row = _one(_list(module_manifest.get('files'), 'moduleManifest.files'),
                    lambda row: row.get('targetPath') == class_path or row.get('path') == class_path,
                    'moduleManifest.files', 'C# View artifact')
    class_sha = _hash(file_row.get('sha256'), 'moduleManifest.files.sha256')
    if not isinstance(class_source_bytes, bytes) or len(class_source_bytes) != receipt_class.get('bytes') or _sha(class_source_bytes) != class_sha:
        _reject('classSourceBytes', 'C# View bytes differ from the module receipt')
    if file_row.get('sha256') != class_sha or file_row.get('bytes') != len(class_source_bytes):
        _reject('moduleManifest.files', 'C# View artifact and class receipt pins disagree')

    source_units = _list(plan_class.get('sourceUnitIds'), f'architecture.classes.{class_id}.sourceUnitIds')
    if source_unit_id not in source_units:
        _reject('sourceUnitId', 'Selected source unit is not owned by this View class')
    source_context = _one(_list(module_manifest.get('sourceContexts'), 'moduleManifest.sourceContexts'),
                          lambda row: row.get('sourceUnitId') == source_unit_id,
                          'moduleManifest.sourceContexts', 'source unit context')
    source_file_sha = _hash(source_context.get('sourceSha256'), 'moduleManifest.sourceContexts.sourceSha256')
    if not isinstance(source_file_bytes, bytes) or _sha(source_file_bytes) != source_file_sha:
        _reject('sourceFileBytes', 'Original source file differs from the module source pin')
    span = _mapping(source_context.get('sourceBytes'), 'moduleManifest.sourceContexts.sourceBytes')
    start, end = span.get('start'), span.get('end')
    if type(start) is not int or type(end) is not int or start < 0 or end <= start or end > len(source_file_bytes):
        _reject('moduleManifest.sourceContexts.sourceBytes', 'Invalid source unit byte span')
    source_unit_bytes = source_file_bytes[start:end]
    if _sha(source_unit_bytes) != _hash(source_context.get('spanSha256'), 'moduleManifest.sourceContexts.spanSha256'):
        _reject('sourceFileBytes', 'Source unit span differs from the module span SHA-256')
    source_fields = extract_source_component_fields(source_unit_bytes, base_offset=start)

    if not isinstance(asset_context.get('bindings'), list):
        _reject('assetContext.bindings', 'Expected source-component identity bindings')
    binding = _one(asset_context['bindings'], lambda row: row.get('codeRegion') == code_region,
                   'assetContext.bindings', f'codeRegion {code_region!r}')
    ownership = _mapping(binding.get('sourceOwnership'), 'assetContext.binding.sourceOwnership')
    if class_id not in ownership.get('classesWithThisSourceUnit', []):
        _reject('assetContext.binding.sourceOwnership', 'Exact code region is not associated with this View class')
    if source_unit_id not in ownership.get('sourceUnitIds', []):
        _reject('assetContext.binding.sourceOwnership', 'Exact code region is not associated with the selected source unit')
    if binding.get('evidence') != 'exact_literal_script_identity':
        _reject('assetContext.binding.evidence', 'Source script component must have exact literal identity evidence')
    source_component = _string(binding.get('sourceComponent'), 'assetContext.binding.sourceComponent')
    source_node = _string(binding.get('sourceNode'), 'assetContext.binding.sourceNode')
    source_asset = _string(binding.get('sourceAsset'), 'assetContext.binding.sourceAsset')
    source_component_row = _one(_list(binding.get('sourceMapComponents'), 'assetContext.binding.sourceMapComponents'),
                                lambda row: row.get('sourceId') == source_component,
                                'assetContext.binding.sourceMapComponents', 'source component mapping')
    if source_component_row.get('node') != source_node:
        _reject('assetContext.binding.sourceMapComponents', 'Source component is attached to a different source node')
    source_class_identity = _source_class_identity_proof(
        architecture, plan_class, receipt_class, module_manifest, source_context,
        source_unit_id, code_region, binding, source_component_row.get('type'),
        class_path, class_sha, class_source_bytes, source_file_bytes, start)
    identities = _mapping(binding.get('assetIdentity'), 'assetContext.binding.assetIdentity')
    native_targets = _list(identities.get('nativeTargets'), 'assetContext.binding.assetIdentity.nativeTargets')
    target = _one(native_targets, lambda row: row.get('type') == 'prefab' and isinstance(row.get('guid'), str),
                  'assetContext.binding.assetIdentity.nativeTargets', 'owned native Prefab target')
    prefab_path = _relative_path(target.get('path'), 'assetContext.nativePrefab.path')
    prefab_sha = _hash(target.get('sha256'), 'assetContext.nativePrefab.sha256')
    meta_sha = _hash(target.get('metaSha256'), 'assetContext.nativePrefab.metaSha256')
    prefab_guid = _string(target.get('guid'), 'assetContext.nativePrefab.guid')
    if not GUID.fullmatch(prefab_guid):
        _reject('assetContext.nativePrefab.guid', 'Expected a 32-character Unity asset GUID')
    if not isinstance(prefab_bytes, bytes) or len(prefab_bytes) != target.get('bytes') or _sha(prefab_bytes) != prefab_sha:
        _reject('prefabBytes', 'Native Prefab bytes differ from the owned asset manifest')
    if not isinstance(prefab_meta_bytes, bytes) or len(prefab_meta_bytes) != target.get('metaBytes') or _sha(prefab_meta_bytes) != meta_sha:
        _reject('prefabMetaBytes', 'Native Prefab .meta bytes differ from the owned asset manifest')
    meta_match = _META_GUID.search(prefab_meta_bytes)
    if not meta_match or meta_match.group(1).decode('ascii') != prefab_guid:
        _reject('prefabMetaBytes', 'Prefab meta GUID differs from the pinned native asset identity')

    prefab_readback_rows = binding.get('sourcePrefabReadback', identities.get('sourcePrefabReadback'))
    prefab_readback = _one(_list(prefab_readback_rows, 'assetContext.binding.sourcePrefabReadback'),
                           lambda row: row.get('sourceId') == source_asset and row.get('path') == prefab_path,
                           'assetContext.binding.sourcePrefabReadback', 'native Prefab readback identity')
    if prefab_readback.get('guid') != prefab_guid or prefab_readback.get('identityMatch') is not True:
        _reject('assetContext.binding.sourcePrefabReadback', 'Saved/reloaded Prefab readback is not bound to the pinned GUID')

    source_map_nodes = _list(binding.get('sourceMapNodes'), 'assetContext.binding.sourceMapNodes')
    source_node_row = _one(source_map_nodes, lambda row: row.get('sourceId') == source_node,
                           'assetContext.binding.sourceMapNodes', 'source root node')
    readback_root = _one(_list(binding.get('sourcePrefabNodeReadback'), 'assetContext.binding.sourcePrefabNodeReadback'),
                         lambda row: row.get('sourceId') == source_node,
                         'assetContext.binding.sourcePrefabNodeReadback', 'native root readback node')
    root_name = _string(source_node_row.get('name'), 'assetContext.binding.sourceMapNodes.name')
    if readback_root.get('hierarchy') != root_name:
        _reject('assetContext.binding.sourcePrefabNodeReadback', 'Source root identity and native readback root name differ')
    if readback_root.get('sourceAsset') != source_asset:
        _reject('assetContext.binding.sourcePrefabNodeReadback', 'Root readback belongs to a different source asset')
    objects, root_object_ids = _prefab_roots(prefab_bytes)
    matching_roots = [gid for gid in root_object_ids if objects.get(gid) == root_name]
    if len(matching_roots) != 1:
        _reject('prefabBytes', f'Expected one pinned Prefab root named {root_name!r}; found {len(matching_roots)}')
    root_component_types = readback_root.get('componentTypes', [])
    if not isinstance(root_component_types, list) or any(not isinstance(value, str) for value in root_component_types):
        _reject('assetContext.binding.sourcePrefabNodeReadback.componentTypes', 'Expected component type names')
    root_component_types = list(root_component_types)

    csharp_fields = {row['field']: row for row in extract_serialized_csharp_fields(class_source_bytes)}
    planned_fields = {row.get('name'): row.get('type') for row in _list(plan_class.get('fields'), f'architecture.classes.{class_id}.fields')}
    for name, field_type in planned_fields.items():
        if name in csharp_fields and csharp_fields[name]['fieldType'] != field_type:
            _reject(f'classSourceBytes.{name}', 'Serialized C# field type differs from architecture plan')

    mapping_rows = _list(field_mappings or [], 'fieldMappings')
    explicit_maps = {}
    for index, row in enumerate(mapping_rows):
        row = _mapping(row, f'fieldMappings[{index}]')
        source_property = _string(row.get('sourceProperty'), f'fieldMappings[{index}].sourceProperty')
        target_field = _string(row.get('csharpField'), f'fieldMappings[{index}].csharpField')
        if source_property in explicit_maps:
            _reject(f'fieldMappings[{index}].sourceProperty', 'Duplicate source property mapping')
        explicit_maps[source_property] = target_field
    source_by_name = {row['sourceProperty']: row for row in source_fields}
    packed_inputs = (source_prefab_pack_bytes, source_project_config_bytes, source_pack_id,
                     source_prefab_pack_sha256, source_project_config_sha256)
    if any(value is not None for value in packed_inputs):
        if any(value is None for value in packed_inputs):
            _reject('sourcePrefabPack', 'Pack bytes, project config bytes, pack ID, and both SHA-256 pins are required together')
        if source_reference_graph is not None:
            _reject('sourceReferenceGraph', 'Do not mix a caller graph with exact packed source decoding')
        source_reference_graph = _decode_packed_source_prefab(
            source_prefab_pack_bytes, source_project_config_bytes, source_asset_id=source_asset,
            source_component_id=source_component, pack_id=source_pack_id,
            expected_pack_sha256=source_prefab_pack_sha256,
            expected_config_sha256=source_project_config_sha256,
        )
    source_reference_graph = source_reference_graph if source_reference_graph is not None else {}
    source_reference_graph = _mapping(source_reference_graph, 'sourceReferenceGraph')
    if source_reference_graph and source_reference_graph.get('sourceAssetId') != source_asset:
        _reject('sourceReferenceGraph.sourceAssetId', 'Source reference graph belongs to a different Prefab')
    if source_reference_graph and source_reference_graph.get('sourceComponentId') not in (None, source_component):
        _reject('sourceReferenceGraph.sourceComponentId', 'Decoded source component identity differs from the exact code-binding component')
    if source_reference_graph.get('sourceEvidence'):
        if source_reference_graph.get('sourceComponentId') != source_component:
            _reject('sourceReferenceGraph.sourceComponentId', 'Packed source component ID differs from asset-context identity')
        if source_reference_graph.get('sourceComponentNodeId') != source_node:
            _reject('sourceReferenceGraph.sourceComponentNodeId', 'Packed source component is not attached to the bound source node')
        if source_reference_graph.get('sourceComponentType') != source_component_row.get('type'):
            _reject('sourceReferenceGraph.sourceComponentType', 'Packed component type differs from the exact component identity map')
    reference_rows = source_reference_graph.get('componentProperties', [])
    if not isinstance(reference_rows, list):
        _reject('sourceReferenceGraph.componentProperties', 'Expected an array')
    native_readback_evidence = None
    if native_readback_bytes is not None or native_readback_sha256 is not None:
        if native_readback_bytes is None or native_readback_sha256 is None:
            _reject('nativeReadbackBytes', 'Readback bytes and SHA-256 pin are required together')
        target_node_readback, native_readback_evidence = _native_readback_nodes(
            native_readback_bytes, expected_sha256=native_readback_sha256, source_asset=source_asset,
            prefab_path=prefab_path, prefab_guid=prefab_guid,
        )
    target_node_readback = target_node_readback or []
    if not isinstance(target_node_readback, list):
        _reject('targetNodeReadback', 'Expected an array')
    readback_by_source = {row.get('sourceId'): row for row in target_node_readback if isinstance(row, dict)}

    structure_evidence = None
    structure_verified = False
    if source_reference_graph.get('sourceEvidence'):
        native_hierarchy = _unity_prefab_hierarchy(prefab_bytes, 'prefabBytes.hierarchy')
        source_nodes = _list(source_reference_graph.get('nodes'), 'sourceReferenceGraph.nodes')
        source_by_path = {}
        for index, row in enumerate(source_nodes):
            row = _mapping(row, f'sourceReferenceGraph.nodes[{index}]')
            path_value = _list(row.get('sourcePath'), f'sourceReferenceGraph.nodes[{index}].sourcePath')
            if any(type(part) is not int or part < 0 for part in path_value):
                _reject(f'sourceReferenceGraph.nodes[{index}].sourcePath', 'Expected non-negative child indices')
            key = tuple(path_value)
            if key in source_by_path:
                _reject('sourceReferenceGraph.nodes', 'Source hierarchy has duplicate child-index paths')
            source_by_path[key] = row
        target_by_path = {row['path']: row for row in native_hierarchy['paths'].values()}
        names_match = (set(source_by_path) == set(target_by_path) and
                       all(source_by_path[path].get('name') == target_by_path[path]['name'] for path in source_by_path))
        readback_matches = native_readback_evidence is not None
        if readback_matches:
            for row in source_nodes:
                readback = readback_by_source.get(row.get('sourceNodeId'))
                if not readback or readback.get('hierarchy') != row.get('name'):
                    readback_matches = False
                    break
            readback_matches = readback_matches and len(readback_by_source) == len(source_nodes)
        structure_verified = bool(names_match and readback_matches and len(source_nodes) == len(native_hierarchy['paths']))
        structure_evidence = {
            'sourceNodeCount': len(source_nodes), 'candidateNodeCount': len(native_hierarchy['paths']),
            'sourceCandidateChildIndexPathsMatch': names_match,
            'savedPrefabReadbackMatchesSourceNodeIdentities': readback_matches,
            'status': 'verified-isomorphic-child-index-hierarchy' if structure_verified else 'unresolved-hierarchy-mismatch',
        }

    fields = []
    unresolved = []
    if source_class_identity.get('status') != 'verified-exact-source-script-to-monoBehaviour':
        unresolved.append({'class': class_id, 'reason': source_class_identity.get('reason',
            'Exact source class identity is unresolved; shared source-unit ownership cannot authorize attachment.')})
    operations = []
    for source_name, target_name in explicit_maps.items():
        source_field = source_by_name.get(source_name)
        if source_field is None:
            _reject(f'fieldMappings.{source_name}', 'Source property was not found in the pinned source component decorators')
        target_field = csharp_fields.get(target_name)
        if target_field is None:
            _reject(f'fieldMappings.{source_name}', f'C# target {target_name!r} is not a [SerializeField] field')
        planned_type = planned_fields.get(target_name)
        if planned_type is not None and planned_type != target_field['fieldType']:
            _reject(f'fieldMappings.{source_name}', 'C# field type differs from architecture class field type')
        evidence = next((row for row in reference_rows
                         if row.get('sourceComponentId') == source_component and row.get('sourceProperty') == source_name), None)
        field_row = {
            'sourceProperty': source_name,
            'sourcePropertyType': source_field['sourceTypeExpression'],
            'sourcePropertyTypeStatus': source_field['sourceTypeStatus'],
            'sourcePropertySpan': source_field['sourceSpan'],
            'sourcePropertySpanSha256': source_field['sourceSpanSha256'],
            'sourceComponentId': source_component,
            'csharpField': target_name,
            'csharpFieldType': target_field['fieldType'],
            'serializedSourceValue': evidence.get('sourcePropertyValue') if evidence and source_reference_graph.get('sourceEvidence') else None,
            'serializedSourceValueSha256': evidence.get('sourcePropertyValueSha256') if evidence and source_reference_graph.get('sourceEvidence') else None,
            'referenceStatus': 'unresolved',
            'reference': None,
        }
        if evidence is None:
            field_row['unresolvedReason'] = 'No exact serialized source component property reference is present in the pinned asset context/source graph.'
        else:
            if source_reference_graph.get('sourceEvidence'):
                evidence_path = 'packed-source-prefab-section:' + str(source_reference_graph['sourceEvidence']['sourcePackSectionIndex'])
                evidence_sha = _hash(evidence.get('sourcePropertyValueSha256'), f'fieldMappings.{source_name}.sourcePropertyValueSha256')
            else:
                evidence_path = _relative_path(evidence.get('evidencePath'), f'fieldMappings.{source_name}.evidencePath')
                evidence_sha = _hash(evidence.get('evidenceSha256'), f'fieldMappings.{source_name}.evidenceSha256')
            target_id = evidence.get('targetSourceNodeId')
            if target_id:
                declared_source_type = source_field['sourceTypeExpression']
                source_type_matches = (None if not source_reference_graph.get('sourceEvidence') else
                    (
                    evidence.get('targetKind') == 'node' if declared_source_type == 'cc.Node'
                    else evidence.get('targetKind') == 'component' and evidence.get('targetSourceComponentType') == declared_source_type
                    if declared_source_type.startswith(('cc.', 'sp.')) else None
                    ))
                path_steps = _source_path(source_reference_graph, _string(target_id, f'fieldMappings.{source_name}.targetSourceNodeId'),
                                          'sourceReferenceGraph')
                path_steps = _annotate_native_node_types(path_steps, readback_by_source)
                readback = readback_by_source.get(target_id)
                if not readback:
                    field_row['unresolvedReason'] = 'No candidate native readback exists for the exact source node identity.'
                elif source_type_matches is False:
                    field_row['unresolvedReason'] = 'Decoded source reference target type disagrees with the exact source decorator type.'
                elif source_reference_graph.get('sourceEvidence') and not structure_verified:
                    field_row['unresolvedReason'] = 'Source component reference is decoded, but the complete source/candidate hierarchy is not proven isomorphic.'
                else:
                    readback_guid = readback.get('prefabGuid')
                    readback_path = readback.get('prefabPath')
                    types = readback.get('componentTypes', [])
                    if readback_guid != prefab_guid or readback_path != prefab_path:
                        _reject(f'fieldMappings.{source_name}', 'Target node readback is not pinned to the owned native Prefab')
                    source_target_type = evidence.get('targetSourceComponentType')
                    native_type_match = _native_field_type_match(target_field['fieldType'], types)
                    reference = {
                        'kind': 'component' if source_target_type else 'node',
                        'targetSourceNodeId': target_id,
                        'nodePath': path_steps,
                        'sourceComponentType': source_target_type,
                        'sourceTypeMatchesDecorator': source_type_matches,
                        'targetComponentType': target_field['fieldType'],
                        'targetNativeTypePresent': native_type_match != 'missing',
                        'targetNativeTypeMatch': native_type_match,
                        'targetNativeComponentTypes': list(types),
                        'evidencePath': evidence_path,
                        'evidenceSha256': evidence_sha,
                    }
                    field_row['reference'] = reference
                    if native_type_match == 'missing':
                        field_row['referenceStatus'] = 'source-reference-and-node-path-verified-target-component-missing'
                        field_row['unresolvedReason'] = f'Target node does not have the required {target_field["fieldType"]} component.'
                    else:
                        field_row['referenceStatus'] = 'verified-node-reference'
            elif evidence.get('targetAssetId'):
                target_asset_id = evidence.get('targetAssetId')
                pinned_asset = next((row for row in identities.get('nativeTargets', [])
                                     if row.get('mappingSourceId') == target_asset_id), None)
                if not pinned_asset:
                    field_row['unresolvedReason'] = 'Source asset reference has no exact native target in the pinned asset context.'
                else:
                    field_row.update(referenceStatus='verified-asset-reference', reference={
                        'kind': 'asset', 'sourceAssetId': target_asset_id,
                        'path': _relative_path(pinned_asset.get('path'), f'fieldMappings.{source_name}.nativeAsset.path'),
                        'guid': _string(pinned_asset.get('guid'), f'fieldMappings.{source_name}.nativeAsset.guid'),
                        'sha256': _hash(pinned_asset.get('sha256'), f'fieldMappings.{source_name}.nativeAsset.sha256'),
                        'evidencePath': evidence_path, 'evidenceSha256': evidence_sha,
                    })
            if field_row['referenceStatus'] == 'unresolved':
                field_row.setdefault('unresolvedReason', 'Serialized source reference target is incomplete.')
        if field_row['referenceStatus'] != 'verified-node-reference' and field_row['referenceStatus'] != 'verified-asset-reference':
            unresolved.append({'sourceProperty': source_name, 'csharpField': target_name,
                               'reason': field_row['unresolvedReason']})
        else:
            operations.append({'kind': 'set-serialized-reference', 'sourceProperty': source_name,
                               'csharpField': target_name, 'reference': field_row['reference']})
        fields.append(field_row)

    mapped_sources = set(explicit_maps)
    mapped_targets = set(explicit_maps.values())
    unmapped_source_properties = []
    for source_name, source_field in source_by_name.items():
        if source_name not in mapped_sources:
            row = {'sourceProperty': source_name, 'sourcePropertyType': source_field['sourceTypeExpression'],
                   'sourcePropertySpan': source_field['sourceSpan'], 'sourcePropertySpanSha256': source_field['sourceSpanSha256'],
                   'referenceStatus': 'unresolved', 'reference': None,
                   'unresolvedReason': 'Source property has no exact same-name or explicit C# field mapping.'}
            evidence = next((item for item in reference_rows if item.get('sourceComponentId') == source_component and
                             item.get('sourceProperty') == source_name), None)
            if evidence and source_reference_graph.get('sourceEvidence'):
                row['serializedSourceValue'] = evidence.get('sourcePropertyValue')
                row['serializedSourceValueSha256'] = evidence.get('sourcePropertyValueSha256')
            if evidence and evidence.get('targetSourceNodeId'):
                target_id = evidence['targetSourceNodeId']
                native_node = readback_by_source.get(target_id)
                if structure_verified and native_node and native_node.get('prefabGuid') == prefab_guid and native_node.get('prefabPath') == prefab_path:
                    row['reference'] = {
                        'kind': 'component' if evidence.get('targetSourceComponentType') else 'node',
                        'targetSourceNodeId': target_id,
                        'nodePath': _source_path(source_reference_graph, target_id, 'sourceReferenceGraph'),
                        'sourceComponentType': evidence.get('targetSourceComponentType'),
                        'sourceTypeMatchesDecorator': (
                            evidence.get('targetKind') == 'node' if source_field['sourceTypeExpression'] == 'cc.Node'
                            else evidence.get('targetKind') == 'component' and evidence.get('targetSourceComponentType') == source_field['sourceTypeExpression']
                            if source_field['sourceTypeExpression'].startswith(('cc.', 'sp.')) else None
                        ),
                        'nativeComponentTypes': native_node.get('componentTypes', []),
                        'evidencePath': ('packed-source-prefab-section:' + str(source_reference_graph['sourceEvidence']['sourcePackSectionIndex'])
                                         if source_reference_graph.get('sourceEvidence') else evidence.get('evidencePath')),
                        'evidenceSha256': (evidence.get('sourcePropertyValueSha256') if source_reference_graph.get('sourceEvidence')
                                           else evidence.get('evidenceSha256')),
                    }
                    row['reference']['nodePath'] = _annotate_native_node_types(row['reference']['nodePath'], readback_by_source)
                    row['referenceStatus'] = 'source-reference-and-node-path-verified-no-target-csharp-field'
            unmapped_source_properties.append(row)
            unresolved.append({'sourceProperty': source_name, 'reason': row['unresolvedReason']})
    for target_name in csharp_fields:
        if target_name not in mapped_targets:
            unresolved.append({'csharpField': target_name, 'reason': 'Serialized C# field has no exact source property mapping.'})

    field_operations = list(operations)
    operations = []
    meta_path = class_path + '.meta'
    meta_row = next((row for row in module_manifest.get('files', [])
                     if isinstance(row, dict) and (row.get('targetPath') == meta_path or row.get('path') == meta_path)), None)
    script_guid = None
    assembled_script_identity = None
    if native_candidate_manifest_bytes is not None or native_candidate_manifest_sha256 is not None:
        if native_candidate_manifest_bytes is None or native_candidate_manifest_sha256 is None or script_meta_bytes is None:
            _reject('nativeCandidateManifest', 'Candidate manifest bytes/hash and Script meta bytes are required together')
        assembled_script_identity, assembled_meta_row = _assembled_script_meta(
            native_candidate_manifest_bytes,native_candidate_manifest_sha256,architecture,architecture_sha256,
            class_id,class_path,class_sha,len(class_source_bytes),script_meta_bytes)
        if meta_row is not None and (meta_row.get('sha256')!=assembled_meta_row['sha256'] or meta_row.get('bytes')!=assembled_meta_row['bytes']):
            _reject('scriptMetaBytes', 'Module and assembled candidate disagree about Script meta identity')
        meta_row = assembled_meta_row
    if script_meta_bytes is not None:
        if meta_row is None:
            _reject('scriptMetaBytes', 'Script .meta bytes are not owned by the module receipt')
        if len(script_meta_bytes) != meta_row.get('bytes') or _sha(script_meta_bytes) != meta_row.get('sha256'):
            _reject('scriptMetaBytes', 'Script .meta bytes differ from module receipt')
        match = _META_GUID.search(script_meta_bytes)
        if not match:
            _reject('scriptMetaBytes', 'Script .meta lacks a 32-character GUID')
        script_guid = match.group(1).decode('ascii')
    elif meta_row is not None:
        unresolved.append({'script': class_path, 'reason': 'Pinned deterministic Script meta bytes were not supplied.'})
    else:
        unresolved.append({'script': class_path, 'reason': 'Module receipt has no deterministic Script .meta GUID yet.'})

    component_plan = {
        'sourceCodeRegion': code_region,
        'sourceComponentId': source_component,
        'sourceNodeId': source_node,
        'sourceAssetId': source_asset,
        'sourceComponentEvidence': binding.get('evidence'),
        'nativeComponentStatus': binding.get('nativeComponentStatus'),
        'target': {'prefabPath': prefab_path, 'prefabGuid': prefab_guid, 'prefabSha256': prefab_sha,
                   'prefabMetaSha256': meta_sha, 'nodePath': [{'root': True, 'expectedName': root_name}],
                   'rootReadbackComponentTypes': root_component_types},
        'attachStatus': 'candidate-component-identity-pinned; MonoScript GUID/type unresolved',
    }
    can_attach = (binding.get('nativeComponentStatus') == 'not_implemented' and
        source_class_identity.get('status') == 'verified-exact-source-script-to-monoBehaviour')
    if source_class_identity.get('status') != 'verified-exact-source-script-to-monoBehaviour':
        component_plan['attachStatus'] = 'source-class-identity-unresolved'
    if not can_attach:
        if binding.get('nativeComponentStatus') != 'not_implemented':
            unresolved.append({'component': source_component,
                               'reason': 'Native component status is not explicitly not_implemented; duplicate attachment is blocked.'})
            component_plan['attachStatus'] = 'unresolved-native-component-status'
    if script_guid:
        component_plan['target']['scriptGuid'] = script_guid
        if can_attach:
            component_plan['attachStatus'] = 'Script GUID pinned; MonoScript.GetClass() pending whole-project compile'
            operations.insert(0, {'kind': 'attach-component-to-root', 'classId': class_id,
                                  'scriptPath': class_path, 'scriptGuid': script_guid,
                                  'nodePath': component_plan['target']['nodePath']})
            operations.extend(field_operations)

    ready = (bool(script_guid) and not unresolved and
             source_class_identity.get('status') == 'verified-exact-source-script-to-monoBehaviour')
    return {
        'schemaVersion': SCHEMA,
        'status': 'ready-for-editor-authoring-after-whole-project-compile' if ready else 'partial-unresolved-evidence',
        'sourceManifestSha256': source_pin,
        'architectureSha256': architecture_sha256,
        'moduleId': module_manifest.get('moduleId'),
        'moduleReceiptSha256': module_manifest.get('receiptSha256'),
        'class': {'classId': class_id, 'path': class_path, 'sha256': class_sha,
                  'bytes': len(class_source_bytes), 'unityTypeStatus': 'pending-whole-project-compile'},
        'sourceClassIdentityProof': source_class_identity,
        'assembledScriptIdentity': assembled_script_identity,
        'sourceUnit': {'sourceUnitId': source_unit_id, 'sourcePath': source_context.get('sourcePath'),
                       'sourceSha256': source_file_sha, 'sourceBytes': {'start': start, 'end': end},
                       'spanSha256': source_context.get('spanSha256')},
        'component': component_plan,
        'sourcePrefabStructure': structure_evidence,
        'sourceReferenceEvidence': source_reference_graph.get('sourceEvidence'),
        'fieldMappings': fields,
        'unmappedSourceProperties': unmapped_source_properties,
        'operations': operations,
        'unresolved': unresolved,
        'runtimeUse': 'Authoring metadata only. Source component UUIDs are not runtime lookup keys; only typed serialized Unity references may be used.',
        'previewReferencePolicy': 'Preview prefab fileIDs are ignored and cannot satisfy a source Prefab localID or field reference.',
        'validationScope': 'Source identities, class/source hashes, native Prefab GUID/hash, and explicit field/reference evidence only; no Editor serialization was run.',
    }
