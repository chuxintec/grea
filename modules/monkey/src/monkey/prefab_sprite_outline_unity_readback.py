"""Verify the saved Unity readback for frozen source Sprite outline bindings."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from .io import diagnostic, inside, read


_SCHEMA = 'monkey-prefab-sprite-outline-binding/1'
_PROFILE = 'cocos24-sprite-alpha-outline-v1'
_PROGRAM_SHA = '53fbec41d8b524d31908b3b27f1b6cccbd2fcd1eb0be9ace5917be386dad4784'
_GUID = re.compile(r'^[0-9a-f]{32}$')
_SHA = re.compile(r'^[0-9a-f]{64}$')


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_file(root: Path, relative: str):
    if (not isinstance(relative, str) or not relative or Path(relative).is_absolute() or
            '..' in Path(relative).parts):
        return None
    try:
        path = inside(root, relative)
    except (OSError, ValueError):
        return None
    return path if path.is_file() else None


def _asset_guid(root: Path, asset_path: str):
    asset = _relative_file(root, asset_path)
    meta = _relative_file(root, asset_path + '.meta') if asset is not None else None
    if meta is None:
        return None
    try:
        lines = read(meta, max_bytes=1024 * 1024).decode('utf-8-sig').splitlines()
    except (OSError, UnicodeError):
        return None
    matches = [line[6:].strip() for line in lines if line.startswith('guid: ')]
    if len(matches) != 1 or not _GUID.fullmatch(matches[0]):
        return None
    return matches[0]


def _source_manifest_matches(instruction: dict, spec: dict):
    manifest_sha = instruction.get('sourceManifestSha256')
    ir_sha = instruction.get('sourceIrSha256')
    if (not isinstance(manifest_sha, str) or not _SHA.fullmatch(manifest_sha) or
            not isinstance(ir_sha, str) or not _SHA.fullmatch(ir_sha) or
            spec.get('sourceManifestSha256') != manifest_sha or spec.get('normalizedIrSha256') != ir_sha):
        return False
    manifest_path = instruction.get('sourceManifestPath')
    if not isinstance(manifest_path, str) or not Path(manifest_path).is_file():
        return False
    return _sha(Path(manifest_path)) == manifest_sha


def _read_spec(instruction):
    direct = instruction.get('spriteOutlineBinding')
    if isinstance(direct, dict):
        return direct
    raw = instruction.get('spriteOutlineBindingJson')
    if raw in (None, ''):
        return None
    if not isinstance(raw, str):
        return False
    try:
        value = json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        return False
    return value if isinstance(value, dict) else False


def _validate_properties(properties):
    if not isinstance(properties, dict):
        return False
    color, size = properties.get('outlineColor'), properties.get('outlineTextureSize')
    if not isinstance(color, list) or len(color) != 4 or not isinstance(size, list) or len(size) != 2:
        return False
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 or value > 1 for value in color):
        return False
    if any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0 for value in size):
        return False
    width, fill, threshold = (properties.get('outlineWidth'), properties.get('fillAlpha'), properties.get('alphaThreshold'))
    return (type(width) in (int, float) and math.isfinite(width) and 0 <= width <= 8 and
            type(fill) in (int, float) and math.isfinite(fill) and 0 <= fill <= 1 and
            type(threshold) in (int, float) and math.isfinite(threshold) and 0 <= threshold < 1)


def verify(instruction, root, editor_readback):
    """Verify exact outline owners, Sprite bindings and persistent native assets.

    Plans without an outline spec are a no-op. All checks are read-only and
    consume the frozen import plan, target .meta GUIDs and existing Editor
    readback; this function does not launch Unity.
    """
    if not isinstance(instruction, dict):
        return []
    spec = _read_spec(instruction)
    if spec is None:
        return []
    root = Path(root).resolve()
    failures = []

    def fail(message, source_id='sprite-outline'):
        failures.append(diagnostic('SPRITE_OUTLINE_READBACK_INVALID',
                                   'Analysis/Readback/sprite-outline-materials.json', message, source_id))

    if spec is False:
        fail('Frozen sprite outline binding JSON is malformed')
        return failures
    if (spec.get('schema') != _SCHEMA or spec.get('profile') != _PROFILE or
            spec.get('programCanonicalSha256') != _PROGRAM_SHA):
        fail('Frozen sprite outline schema/profile/program pin is unknown')
        return failures
    if not _source_manifest_matches(instruction, spec):
        fail('Sprite outline source manifest/normalized-IR pins are missing or mismatched')
        return failures
    if not _validate_properties(spec.get('properties')):
        fail('Frozen sprite outline properties are missing, malformed, or out of range')
        return failures
    unity = spec.get('unity')
    if not isinstance(unity, dict):
        fail('Frozen Unity material/shader identity is missing')
        return failures
    material_path, shader_path = unity.get('materialPath'), unity.get('shaderPath')
    material_guid, shader_guid = unity.get('materialGuid'), unity.get('shaderGuid')
    material_source_id = spec.get('materialSourceId')
    if (not isinstance(material_source_id, str) or not material_source_id or
            not isinstance(material_guid, str) or not _GUID.fullmatch(material_guid) or
            not isinstance(shader_guid, str) or not _GUID.fullmatch(shader_guid)):
        fail('Frozen Unity material/shader GUID is missing or malformed')
        return failures
    if _asset_guid(root, material_path) != material_guid or _asset_guid(root, shader_path) != shader_guid:
        fail('Imported Unity material/shader path or .meta GUID differs from the frozen spec')
        return failures

    bindings = spec.get('spriteBindings')
    component_ids = spec.get('sourceComponentIds')
    source_rows = spec.get('sourceBindings')
    if (not isinstance(bindings, list) or not bindings or not isinstance(component_ids, list) or
            not isinstance(source_rows, list) or len(bindings) != len(component_ids) or len(source_rows) != len(component_ids) or
            len(set(component_ids)) != len(component_ids) or
            component_ids != [row.get('sourceId') if isinstance(row, dict) else None for row in bindings] or
            component_ids != [row.get('componentSourceId') if isinstance(row, dict) else None for row in source_rows]):
        fail('Frozen sprite outline source component/binding denominator or ordering differs')
        return failures

    prefabs = {row.get('sourceId'): row for row in instruction.get('sourcePrefabs', []) if isinstance(row, dict)}
    components = {}
    for row in instruction.get('components', []):
        if isinstance(row, dict) and isinstance(row.get('sourceId'), str):
            components.setdefault(row['sourceId'], []).append(row)
    expected_by_owner = {}
    for binding, source in zip(bindings, source_rows):
        source_id = binding.get('sourceId') if isinstance(binding, dict) else None
        frame_id = binding.get('spriteFrameSourceId') if isinstance(binding, dict) else None
        frame_uuid = source.get('spriteFrameUuid') if isinstance(source, dict) else None
        owner = source.get('prefabSourceId') if isinstance(source, dict) else None
        if (not isinstance(source_id, str) or not isinstance(frame_id, str) or not isinstance(frame_uuid, str) or
                not isinstance(owner, str) or not source_id.startswith(owner + '#') or
                frame_id.rsplit(':', 1)[-1] != frame_uuid or owner not in prefabs):
            fail('Frozen outline component/frame/owner source identity is malformed', source_id or 'sprite-outline')
            continue
        matches = components.get(source_id, [])
        if len(matches) != 1:
            fail('Outline source component is absent or duplicated in the native plan', source_id)
            continue
        component = matches[0]
        owner_nodes = set(prefabs[owner].get('nodes', []))
        if (component.get('type') != 'cc.Sprite' or component.get('convertible') is not True or
                component.get('node') not in owner_nodes or component.get('spriteFrame') != frame_id or
                component.get('nativeSpriteOutlineMaterialSourceId') != spec.get('materialSourceId')):
            fail('Outline source component type/frame/material/node binding differs from frozen plan', source_id)
        expected_by_owner.setdefault(owner, []).append(source_id)

    native_files = editor_readback if isinstance(editor_readback, dict) else {}
    actual_prefabs_rows = native_files.get('sourcePrefabs')
    if not isinstance(actual_prefabs_rows, list):
        fail('Native editor readback has no source Prefab rows')
        return failures
    actual_prefabs = {}
    for row in actual_prefabs_rows:
        if not isinstance(row, dict) or not isinstance(row.get('sourceId'), str) or row['sourceId'] in actual_prefabs:
            fail('Native editor readback has malformed/duplicate source Prefab identity')
            return failures
        actual_prefabs[row['sourceId']] = row
    for owner in expected_by_owner:
        expected_prefab, actual_prefab = prefabs.get(owner), actual_prefabs.get(owner)
        if expected_prefab is None or actual_prefab is None:
            fail('Outline owner Prefab is missing from frozen/native Prefab identities', owner)
            continue
        if actual_prefab.get('path') != expected_prefab.get('path'):
            fail('Outline owner Prefab native path differs from the frozen plan', owner)
        guid = actual_prefab.get('guid')
        if not isinstance(guid, str) or _asset_guid(root, expected_prefab.get('path')) != guid.lower():
            fail('Outline owner Prefab GUID differs from its target .meta identity', owner)

    readback_path = _relative_file(root, 'Analysis/Readback/sprite-outline-materials.json')
    if readback_path is None:
        fail('Saved Unity sprite outline readback file is missing')
        return failures
    try:
        wrapper = json.loads(read(readback_path, max_bytes=16 * 1024 * 1024).decode('utf-8-sig'))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        fail('Saved Unity sprite outline readback JSON is malformed')
        return failures
    if not isinstance(wrapper, dict) or wrapper.get('schemaVersion') != 1 or not isinstance(wrapper.get('prefabs'), list):
        fail('Saved Unity sprite outline readback schema is invalid')
        return failures
    actual_rows = wrapper['prefabs']
    actual_owners = [row.get('sourcePrefabId') if isinstance(row, dict) else None for row in actual_rows]
    if (any(not isinstance(owner, str) for owner in actual_owners) or len(set(actual_owners)) != len(actual_owners) or
            set(actual_owners) != set(expected_by_owner)):
        fail('Saved Unity sprite outline owner set differs from frozen bound owners')
        return failures
    actual_by_owner = {row['sourcePrefabId']: row for row in actual_rows}
    for owner, expected_ids in expected_by_owner.items():
        row = actual_by_owner[owner]
        if (row.get('materialSourceId') != spec.get('materialSourceId') or
                row.get('materialGuid') != material_guid or row.get('shaderGuid') != shader_guid or
                row.get('propertiesVerified') is not True or
                row.get('boundSpriteComponentIds') != expected_ids):
            fail('Saved outline material/shader identity, properties, or bound Sprite set differs', owner)
    return failures
