"""Prepare evidence-pinned static SkeletonGraphic renderers for Spine 3.8 data.

This stage operates on the exact source join already frozen by
``prefab_static_spine_continuation``. It decodes only the referenced ASTC atlas
pages, writes a separate renderer plan, and never runs source code or advances
an animation timeline.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from io import BytesIO
from pathlib import Path

from .io import encoded, inside, read, safe, sha, write_json
from .prefab_spine_materials import _binary_slot_blend_modes, _asset_rows, _resolve_uuid
from .prefab_spine_native_stage import _atlas_page_sampling, _meta_payload

CONTRACT = "monkey-static-spine-rendering/1"
_RUNTIME_COMMIT = "8b4844bd4b193ba9e54487ed397a777993cbad56"
_RUNTIME_PRODUCER = "cb453b884391dced615ab6c7d2d1407ca70bd7b49e5196020be4bb0fab8682a5"
_SHADERS = (
    ("targets/materials/spine/UnitySpineSourceProfile.shader", "Assets/Game/Content/Shaders/Spine/Static/SpineSourceProfile.shader"),
    ("targets/materials/spine/UnitySpineGraphicProfile.shader", "Assets/Game/Content/Shaders/Spine/Static/SpineSourceGraphicProfile.shader"),
)
_DERIVED_HELPER = ("targets/UnityStaticSpineRenderingDerived.cs",
                   "Assets/Game/Editor/Conversion/UnityStaticSpineRenderingDerived.cs")
_RENDER_HELPERS = (
    ("targets/UnityStaticSpineRendering.cs", "Assets/Game/Editor/Conversion/UnityStaticSpineRendering.cs"),
    ("targets/spine/UnitySpineBinding.cs", "Assets/Game/Editor/Conversion/Spine/UnitySpineBinding.cs"),
    ("targets/materials/spine/UnitySpineMaterialBindings.cs", "Assets/Game/Editor/Conversion/Spine/UnitySpineMaterialBindings.cs"),
    ("targets/spine/UnitySpineNativeFactory.cs", "Assets/Game/Editor/Conversion/Spine/UnitySpineNativeFactory.cs"),
    ("targets/spine/UnitySpineGraphicMaterialPresentation.cs", "Assets/Game/Scripts/Presentation/Recovered/Spine/UnitySpineGraphicMaterialPresentation.cs"),
    ("targets/spine/UnitySpineSourceIdentity.cs", "Assets/Game/Scripts/Presentation/Recovered/Spine/UnitySpineSourceIdentity.cs"),
)


class StaticSpineRenderingError(ValueError):
    """Pinned source or native render contract is incomplete."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _safe_stage_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise StaticSpineRenderingError(f"invalid staged payload path: {relative!r}")
    candidate = root / relative
    path = safe(candidate).resolve(strict=True)
    if not path.is_relative_to(root.resolve(strict=True)):
        raise StaticSpineRenderingError(f"staged payload escapes the frozen plan root: {relative}")
    return path


def _put_payload(output: Path, source: Path, target: str, role: str, expected_sha: str | None = None,
                 expected_bytes: int | None = None) -> dict:
    raw = read(source, max_bytes=128 * 1024 * 1024)
    digest = sha(raw)
    if expected_sha is not None and digest != expected_sha:
        raise StaticSpineRenderingError(f"source hash mismatch: {source}")
    if expected_bytes is not None and len(raw) != expected_bytes:
        raise StaticSpineRenderingError(f"source byte-count mismatch: {source}")
    return _store_payload(output, raw, target, role)


def _store_payload(output, raw, target, role):
    digest = sha(raw)
    if not target.startswith("Assets/") or ".." in Path(target).parts:
        raise StaticSpineRenderingError(f"invalid Unity output path: {target}")
    relative = f"spine-static-rendering-payloads/{digest}/{Path(target).name}"
    destination = inside(output, relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and read(destination, max_bytes=128 * 1024 * 1024) != raw:
        raise StaticSpineRenderingError(f"payload collision: {relative}")
    if not destination.exists():
        destination.write_bytes(raw)
    return {"source": relative, "target": target, "sha256": digest, "bytes": len(raw), "role": role}


def _adapt_animation_curves(value):
    """Translate four Bezier controls from an array to Spine-C# 3.8 fields."""
    changed = 0
    if isinstance(value, list):
        for frame in value:
            if not isinstance(frame, dict) or not isinstance(frame.get('curve'), list):
                continue
            controls = frame['curve']
            if (len(controls) != 4 or any(type(x) not in (int, float) or not math.isfinite(x) for x in controls)
                    or any(k in frame for k in ('c2', 'c3', 'c4'))):
                raise StaticSpineRenderingError('Ambiguous Spine JSON Bezier controls')
            frame.update(zip(('curve', 'c2', 'c3', 'c4'), controls))
            changed += 1
    elif isinstance(value, dict):
        changed = sum(_adapt_animation_curves(child) for child in value.values())
    return changed


def _source_payload(stage_root: Path, copy_row: dict) -> Path:
    relative = copy_row.get("source")
    path = _safe_stage_path(stage_root, relative)
    raw = read(path, max_bytes=128 * 1024 * 1024)
    if sha(raw) != copy_row.get("sha256") or len(raw) != copy_row.get("bytes"):
        raise StaticSpineRenderingError(f"continuation payload pin mismatch: {relative}")
    return path


def rewrite_native_atlas(raw: bytes, pages: list[dict]) -> tuple[bytes, list[dict]]:
    """Change page headers only, to match the SDK's texture-file-name lookup.

    Region names, coordinates, BOM and line endings remain byte-identical.
    The immutable original atlas is retained by staticSpineContinuation.
    """
    lines = raw.splitlines(keepends=True)
    headers = []
    blank = True
    for index, line in enumerate(lines):
        content = line.rstrip(b'\r\n')
        if index == 0:
            content = content.removeprefix(b'\xef\xbb\xbf')
        if not content.strip():
            blank = True
        elif blank:
            headers.append((index, content.decode('utf-8')))
            blank = False
    expected = [page['nativeAtlasPage'] for page in pages]
    if not pages or [name for _, name in headers] != expected:
        raise StaticSpineRenderingError('native atlas page headers differ from the exact ordered page mapping')
    targets = [Path(page['textureAssetPath']).name for page in pages]
    if len(set(targets)) != len(targets):
        raise StaticSpineRenderingError('native atlas texture file names are ambiguous')
    mapping = []
    for (index, previous), page, target in zip(headers, pages, targets):
        if not target.endswith('.png') or any(c in target for c in '\r\n\\:'):
            raise StaticSpineRenderingError('native atlas texture file name is invalid')
        old = lines[index]
        prefix = b'\xef\xbb\xbf' if index == 0 and old.startswith(b'\xef\xbb\xbf') else b''
        ending = old[len(old.rstrip(b'\r\n')):]
        lines[index] = prefix + target.encode('utf-8') + ending
        mapping.append({'sourceAtlasPage': page['sourceAtlasPage'], 'previousNativeAtlasPage': previous,
                        'nativeAtlasPage': target, 'textureAssetPath': page['textureAssetPath']})
        page['nativeAtlasPage'] = target
    return b''.join(lines), mapping


def upgrade_atlas_mapping(plan: dict, stage_root: Path) -> list[dict]:
    """Rebind native atlas text in a fresh owned stage; never decode textures."""
    fragment = plan['staticSpineRendering']
    module = inside(stage_root, fragment['moduleStage'])
    payloads = fragment['payloads']
    retained = plan['staticSpineContinuation']
    retained_root = inside(stage_root, retained['moduleStage'])
    evidence = []
    for data in fragment['dataAssets']:
        spec = data.get('factorySpec')
        if not isinstance(spec, dict):
            continue
        target = spec['atlasTextAssetPath']
        matches = [row for row in payloads if row['target'] == target]
        if len(matches) != 1:
            raise StaticSpineRenderingError('native atlas payload identity is ambiguous')
        old = matches[0]
        raw = read(_source_payload(module, old))
        if sha(raw) != spec['atlasSha256']:
            raise StaticSpineRenderingError('native atlas factory hash differs from payload')
        sources = [row for row in retained['dataAssets'] if row['sourceDataAssetId'] == spec['sourceAssetId']]
        if len(sources) != 1:
            raise StaticSpineRenderingError('native atlas source data identity is ambiguous')
        source = sources[0]
        source_payloads = [row for row in retained['payloadCopies']
                           if row['target'] == source['sourceAtlasTextAssetPath']]
        if len(source_payloads) != 1:
            raise StaticSpineRenderingError('native atlas original payload identity is ambiguous')
        source_raw = read(_source_payload(retained_root, source_payloads[0]))
        if sha(source_raw) != source['sourceAtlasSha256']:
            raise StaticSpineRenderingError('native atlas original source hash differs')
        if [(p['sourceAtlasPage'], p['sourceTextureSourceId']) for p in spec['pages']] != [
            (p['sourcePageName'], p['sourceTextureSourceId']) for p in source['sourceAtlasPages']]:
            raise StaticSpineRenderingError('native atlas page/texture source mapping differs')
        for page in spec['pages']:
            textures = [row for row in payloads if row['target'] == page['textureAssetPath']
                        and row.get('role') in ('decoded-source-astc-spine-page', 'decoded-source-png-spine-page')]
            if len(textures) != 1:
                raise StaticSpineRenderingError('native atlas decoded texture identity is ambiguous')
            _source_payload(module, textures[0])
            page['textureSha256'] = textures[0]['sha256']
        derived, mapping = rewrite_native_atlas(raw, spec['pages'])
        original_pages = [{**page, 'nativeAtlasPage': page['sourceAtlasPage']} for page in spec['pages']]
        source_derived, _ = rewrite_native_atlas(source_raw, original_pages)
        if derived != source_derived:
            raise StaticSpineRenderingError('native atlas rewrite differs beyond original page headers')
        relative = f"spine-static-rendering-payloads/{sha(derived)}/{Path(target).name}"
        destination = inside(module, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and read(destination) != derived:
            raise StaticSpineRenderingError('native atlas derived payload collision')
        destination.write_bytes(derived)
        replacement = {**old, 'source': relative, 'sha256': sha(derived), 'bytes': len(derived),
                       'role': 'derived-native-spine-atlas-page-map'}
        for row in [*payloads, *data.get('payloads', [])]:
            if row.get('target') == target:
                if row != old:
                    raise StaticSpineRenderingError('native atlas duplicated payload pins differ')
        # These are separate JSON objects after loading a frozen stage.
        for collection in (payloads, data.get('payloads', [])):
            for index, row in enumerate(collection):
                if row.get('target') == target:
                    collection[index] = replacement.copy()
        spec['atlasSha256'] = sha(derived)
        record = {'sourceDataAssetId': spec['sourceAssetId'], 'sourceAtlasSha256': source['sourceAtlasSha256'],
                  'previousNativeAtlasSha256': sha(raw), 'nativeAtlasSha256': sha(derived),
                  'pages': mapping, 'textureBytesChanged': False, 'textureDecodeInvoked': False}
        data['nativeAtlasMapping'] = record
        evidence.append(record)
    return evidence


def _source_field(component: dict, name: str):
    state = component.get("sourceFieldStates", {}).get(name)
    if not isinstance(state, dict):
        return None, False
    return state.get("value"), state.get("present") is True


def _source_scale(asset_rows: dict[str, list[dict]], source_data_id: str) -> dict:
    matches = asset_rows.get(source_data_id, [])
    if len(matches) != 1:
        raise StaticSpineRenderingError(f"SkeletonData source identity is missing or ambiguous: {source_data_id}")
    instances = matches[0].get("document", {}).get("instances", [])
    objects = [row for row in instances if isinstance(row, dict) and row.get("__type__") == "sp.SkeletonData"]
    if len(objects) != 1:
        raise StaticSpineRenderingError(f"SkeletonData decoded source object is missing or ambiguous: {source_data_id}")
    obj = objects[0]
    present = [(key, obj[key]) for key in ("scale", "_scale") if key in obj]
    if len(present) > 1 and present[0][1] != present[1][1]:
        raise StaticSpineRenderingError(f"conflicting serialized SkeletonData scale fields: {source_data_id}")
    if not present:
        return {"value": 1.0, "status": "pinned-source-engine-default", "field": None}
    key, value = present[0]
    if type(value) not in (int, float) or value <= 0 or value != value or value in (float("inf"), float("-inf")):
        raise StaticSpineRenderingError(f"serialized SkeletonData scale is invalid: {source_data_id}:{key}")
    return {"value": float(value), "status": "serialized-source-value", "field": key}


def _visible(plan: dict, component: dict) -> bool:
    """Read explicit source visibility through the source-plan node ancestry."""
    nodes = {row.get("sourceId"): row for row in plan.get("nodes", []) if isinstance(row, dict)}
    node_id = component.get("sourceNodeId")
    seen = set()
    while node_id:
        if node_id in seen or node_id not in nodes:
            return False
        seen.add(node_id)
        node = nodes[node_id]
        if node.get("active") is False or type(node.get('opacity'))in(int,float)and node['opacity']<=0:
            return False
        parent = node.get("parent")
        node_id = parent if isinstance(parent, str) else None
    return component.get("sourceComponentEnabled") is True


def _runtime_inputs(runtime_record: dict) -> dict:
    if not isinstance(runtime_record, dict) or runtime_record.get("status") not in (
        "optional_backup_read_only_verified_not_used", "verified", "pinned"):
        raise StaticSpineRenderingError("Spine runtime record is not a verified pinned backup")
    if runtime_record.get("upstreamCommit", _RUNTIME_COMMIT) != _RUNTIME_COMMIT:
        raise StaticSpineRenderingError("Spine runtime commit differs from the supported 3.8.99 source")
    if runtime_record.get("producerManifestSha256", _RUNTIME_PRODUCER) != _RUNTIME_PRODUCER:
        raise StaticSpineRenderingError("Spine runtime producer manifest pin differs")
    root = runtime_record.get("assetsRoot")
    files = runtime_record.get("verifiedFiles")
    manifest_path = runtime_record.get("manifestPath")
    manifest_sha = runtime_record.get("manifestSha256")
    if (not isinstance(root, str) or not Path(root).is_absolute() or not isinstance(files, list) or
            not isinstance(manifest_path, str) or not Path(manifest_path).is_absolute() or
            not isinstance(manifest_sha, str)):
        raise StaticSpineRenderingError("verified runtime assetsRoot/files are absent")
    manifest_raw = read(safe(manifest_path), max_bytes=16 * 1024 * 1024)
    if sha(manifest_raw) != manifest_sha:
        raise StaticSpineRenderingError("pinned Spine runtime backup manifest hash changed")
    backup = json.loads(manifest_raw.decode("utf-8-sig"))
    if backup.get("producerManifestSHA256") != _RUNTIME_PRODUCER or backup.get("upstream", {}).get("upstreamCommit") != _RUNTIME_COMMIT:
        raise StaticSpineRenderingError("runtime backup manifest producer or source commit differs")
    expected_files = {row.get("path"): row for row in backup.get("files", []) if isinstance(row, dict)}
    by_path = {row.get("path"): row for row in files if isinstance(row, dict)}
    if len(by_path) != len(files) or set(by_path) != set(expected_files):
        raise StaticSpineRenderingError("runtime file identities are missing, duplicated, or differ from the pinned manifest")
    for path, row in by_path.items():
        expected = expected_files[path]
        if row.get("sha256") != expected.get("sha256") or row.get("bytes") != expected.get("bytes"):
            raise StaticSpineRenderingError(f"runtime file receipt differs from pinned backup manifest: {path}")
    return {"root": Path(root), "files": by_path, "manifestPath": manifest_path, "manifestSha256": manifest_sha}


def _copy_runtime(runtime_record: dict, output: Path) -> list[dict]:
    inputs = _runtime_inputs(runtime_record)
    result = []
    for relative, spec in sorted(inputs["files"].items()):
        source = (inputs["root"] / relative).resolve(strict=True)
        if not source.is_relative_to(inputs["root"].resolve(strict=True)):
            raise StaticSpineRenderingError(f"runtime path escapes backup root: {relative}")
        result.append(_put_payload(output, source, relative, "pinned-spine-runtime", spec.get("sha256"), spec.get("bytes")))
    if not any("EditorRuntime/spine-unity.dll" in row["target"] for row in result):
        raise StaticSpineRenderingError("verified runtime backup omits Editor Spine Unity runtime")
    return result


def _source_engine(path, expected_sha256):
    engine_path = Path(path).resolve(strict=True)
    engine_raw = read(engine_path, max_bytes=8 * 1024 * 1024)
    engine_sha = sha(engine_raw)
    if engine_sha != expected_sha256 or engine_sha != "d0a4b5323687196dc5ee3ff8fcdc328e49148c1cf523b08b542e63dfb97b1329":
        raise StaticSpineRenderingError("pinned Cocos 2.4.15 skeleton-data.js source identity mismatch")
    engine_text = engine_raw.decode("utf-8", "strict")
    compact_engine = "".join(engine_text.split())
    if "scale:1" not in compact_engine or "reader.scale=this.scale;" not in compact_engine:
        raise StaticSpineRenderingError("pinned source engine bytes do not establish the Spine scale default")
    return engine_path, engine_sha


def prepare_rendering(plan: dict, stage_root: str | Path, runtime_record: dict, output: str | Path,
                      *, source_engine_file: str | Path, expected_source_engine_sha256: str,
                      reuse_rendering: dict | None = None) -> dict:
    """Build a complete source-component renderer plan and decoded page stage."""
    stage_root = Path(stage_root).resolve(strict=True)
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise StaticSpineRenderingError("rendering module output already exists; choose a fresh plan")
    output.resolve().relative_to(stage_root)
    output.mkdir(parents=True)
    fragment = plan.get("staticSpineContinuation")
    from .prefab_static_spine_continuation import CONTRACT as STATIC_CONTINUATION_CONTRACT
    if not isinstance(fragment, dict) or fragment.get("contract") != STATIC_CONTINUATION_CONTRACT:
        raise StaticSpineRenderingError("frozen plan lacks the static Spine source continuation")
    source_stage=inside(stage_root,fragment['moduleStage']).resolve(strict=True)
    engine_path,engine_sha=_source_engine(source_engine_file,expected_source_engine_sha256)
    if fragment.get("sourceProfile") != "cocos-2.4.15-bundle" or fragment.get("sourceVersion") != "2.4.15":
        raise StaticSpineRenderingError("unsupported source Spine profile")
    target_units = plan.get("staticSpineRenderingTargetUnits")
    importer_source = Path(__file__).resolve().parent / "targets" / "UnityImporter.cs"
    importer_sha = sha(read(importer_source, max_bytes=32 * 1024 * 1024))
    if (not isinstance(target_units, dict) or target_units.get("status") != "declared_generator_mapping_requires_native_verification" or
            target_units.get("targetUnitsPerSourcePixel") != 1.0 or
            target_units.get("coordinateSpace") != "source-pixels-to-ugui-local-units" or
            target_units.get("runtimeCheck") != "exact-plan-node-RectTransform-fields-and-actual-canvas-reference-ppu" or
            target_units.get("generatorSourceSha256") != importer_sha):
        raise StaticSpineRenderingError("declared source-pixel to uGUI unit mapping does not pin the actual generator source")

    source_manifest_path = Path(fragment.get("sourceManifestPath", "")).resolve(strict=True)
    manifest_raw = read(source_manifest_path, max_bytes=512 * 1024 * 1024)
    if sha(manifest_raw) != fragment.get("sourceManifestSha256"):
        raise StaticSpineRenderingError("frozen source manifest changed")
    manifest = json.loads(manifest_raw.decode("utf-8-sig"))
    assets_by_id = _asset_rows(manifest)
    components = fragment.get("components")
    data_assets = fragment.get("dataAssets")
    copies = fragment.get("payloadCopies")
    if not all(isinstance(x, list) for x in (components, data_assets, copies)):
        raise StaticSpineRenderingError("continuation component/data/payload rows are malformed")
    if len({row.get("sourceComponentId") for row in components}) != len(components):
        raise StaticSpineRenderingError("Spine component identities are missing or duplicated")
    copy_by_target = {row.get("target"): row for row in copies if isinstance(row, dict)}
    if len(copy_by_target) != len(copies):
        raise StaticSpineRenderingError("continuation payload target identities are ambiguous")
    data_by_id = {row.get("sourceDataAssetId"): row for row in data_assets}
    if len(data_by_id) != len(data_assets):
        raise StaticSpineRenderingError("SkeletonData source identities are missing or duplicated")

    # Exact runtime material profile: resolve source refs in the manifest and
    # reject any effect/material variation from the fixed Cocos Spine profile.
    from .prefab_spine_materials import _material, _program, _source_semantics
    material_refs = {ref.get("sourceAssetId") for comp in components for ref in comp.get("sourceObjectReferences", [])
                     if ref.get("targetReferenceKind") == "retained-source-material"}
    implicit_material = not material_refs
    if implicit_material:
        defaults = [a["sourceId"] for rows in assets_by_id.values() for a in rows
                    if a.get("bundle") == "internal" and a.get("kind") == "cc.Material"
                    and a.get("logicalPath") == "materials/builtin-2d-spine"]
        if len(defaults) != 1:
            raise StaticSpineRenderingError("source Skeleton components have no exact retained material references or unique source builtin")
        material_refs.add(defaults[0])
    material_profiles = []
    for material_id in sorted(material_refs):
        matches = assets_by_id.get(material_id, [])
        if len(matches) != 1:
            raise StaticSpineRenderingError(f"source material identity is missing or ambiguous: {material_id}")
        material = matches[0]
        doc = material.get("document", {})
        instances = doc.get("instances", [])
        material_obj = next((x for x in instances if isinstance(x, dict) and x.get("__type__") == "cc.Material"), None)
        if material_obj is None:
            raise StaticSpineRenderingError(f"source material document is missing: {material_id}")
        effect_uuid = material_obj.get("_effectAsset", {}).get("__uuid__")
        bundle = material.get("bundle", manifest.get("bundle"))
        effect, redirects = _resolve_uuid(assets_by_id, bundle, effect_uuid, "cc.EffectAsset")
        effect_obj = next((x for x in effect.get("document", {}).get("instances", [])
                           if isinstance(x, dict) and x.get("__type__") == "cc.EffectAsset"), None)
        if effect_obj is None:
            raise StaticSpineRenderingError(f"source effect document is missing: {effect['sourceId']}")
        shader, stage_hashes = _program(effect_obj)
        profile = _material(effect_uuid, material_obj)
        semantics = _source_semantics(effect_obj, shader)
        material_profiles.append({"sourceBinding": "creator-2.4.15-builtin-default" if implicit_material else "serialized",
                                  "sourceMaterialId": material_id, "sourceEffectId": effect["sourceId"],
                                  "redirects": redirects, "material": profile, "stageSha256": stage_hashes,
                                  "semantics": semantics})
    if len({json.dumps(x["stageSha256"], sort_keys=True) for x in material_profiles}) != 1:
        raise StaticSpineRenderingError("Spine source material references do not share one verified shader profile")

    # Reuse only pages joined by exact source texture identity and source hash.
    reusable={};reused_pages=set();decoded_pages=set();generated_pages={}
    if reuse_rendering is not None:
        if reuse_rendering.get('contract')!=CONTRACT or reuse_rendering.get('sourceManifestSha256')!=fragment['sourceManifestSha256']:
            raise StaticSpineRenderingError('reused rendering belongs to another source contract')
        for payload in reuse_rendering.get('payloads',[]):
            if payload.get('role') not in ('decoded-source-astc-spine-page', 'decoded-source-png-spine-page'):continue
            key=(payload.get('sourceTextureSourceId'),payload.get('sourceTextureSha256'))
            if key in reusable and reusable[key]['sha256']!=payload.get('sha256'):
                raise StaticSpineRenderingError('reused decoded page source identity is ambiguous')
            reusable[key]=payload
    from .prefab_static_spine_defaults import render_pma
    data_render = {}
    missing_animations = set()
    for data_id, row in data_by_id.items():
        scale_source = _source_scale(assets_by_id, data_id)
        skeleton_copy = copy_by_target.get(row.get("sourceSkeletonTextAssetPath"))
        atlas_copy = copy_by_target.get(row.get("sourceAtlasTextAssetPath"))
        if not skeleton_copy or not atlas_copy:
            raise StaticSpineRenderingError(f"source payload rows are incomplete: {data_id}")
        skeleton_path = _source_payload(source_stage, skeleton_copy)
        atlas_path = _source_payload(source_stage, atlas_copy)
        raw_skeleton = read(skeleton_path, max_bytes=128 * 1024 * 1024)
        embedded_json = row.get("sourceSkeletonEncoding") == "embedded-json"
        if embedded_json:
            skeleton = json.loads(raw_skeleton)
            slots = skeleton.get("slots", [])
            counts = dict.fromkeys(("normal", "additive", "multiply", "screen"), 0)
            for slot in slots:
                mode = slot.get("blend", "normal")
                if mode not in counts:
                    raise StaticSpineRenderingError(f"Unknown Spine JSON blend mode: {mode}")
                counts[mode] += 1
            blend = dict(spineVersion=skeleton["skeleton"]["spine"], boneCount=len(skeleton["bones"]),
                         slotCount=len(slots), blendModeCounts=counts)
        else:
            blend = _binary_slot_blend_modes(raw_skeleton)
        # Spine 3.8 binary animation names are literal UTF-8 strings. Absence
        # disproves a requested name; Unity still checks every admitted name.
        for component in components:
            if component.get("sourceDataReference", {}).get("sourceDataAssetId") != data_id:
                continue
            for key in ("_animationName", "defaultAnimation"):
                name, present = _source_field(component, key)
                if present and isinstance(name, str) and name:
                    absent = name not in skeleton.get("animations", {}) if embedded_json else name.encode("utf-8") not in raw_skeleton
                    if absent:
                        missing_animations.add((data_id, name))
        if blend.get("spineVersion") != row.get("sourceSpineVersion"):
            raise StaticSpineRenderingError(f"Spine source binary version drift: {data_id}")
        effective_pma=render_pma(row)
        if effective_pma is None:
            data_render[data_id] = {"eligible": False, "gap": "SOURCE_PMA_UNKNOWN_OR_TRUE", "blendEvidence": blend}
            continue
        atlas_text = read(atlas_path, max_bytes=16 * 1024 * 1024).decode("utf-8-sig")
        source_data_token = hashlib.sha256(data_id.encode()).hexdigest()[:20]
        base = f"Assets/Game/Content/Spine/Static/{source_data_token}"
        # The native factory requires the imported TextAsset name to contain
        # '.skel'; copy identical bytes under a distinct native import name.
        skel_target = base + ("/source.json.bytes" if embedded_json else "/source.skel.bytes")
        curves = _adapt_animation_curves(skeleton.get("animations", {})) if embedded_json else 0
        if curves:
            normalized = json.dumps(skeleton, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
            skeleton_target = _store_payload(output, normalized, skel_target, "unity-spine-json-curve-controls")
            skeleton_target.update(sourceSkeletonSha256=row["sourceNativeSha256"], convertedCurveCount=curves)
        else:
            skeleton_target = _put_payload(output, skeleton_path, skel_target, "source-spine-skeleton-bytes", row["sourceNativeSha256"], row["sourceNativeBytes"])
        atlas_target = base + "/source.atlas.txt"
        atlas_output = _put_payload(output, atlas_path, atlas_target, "source-spine-atlas-text", row["sourceAtlasSha256"], row["sourceAtlasBytes"])
        page_specs = []
        for page in row.get("sourceAtlasPages", []):
            texture_id = page.get("sourceTextureSourceId")
            source_page_copy = next((copy for copy in copies if copy.get("sourceId") == texture_id and copy.get("role") in ("opaque-source-astc-page-textasset-not-decoded", "opaque-source-png-page-textasset-not-decoded")), None)
            if source_page_copy is None:
                raise StaticSpineRenderingError(f"opaque ASTC page payload is absent: {data_id}:{texture_id}")
            source_page_path = _source_payload(source_stage, source_page_copy)
            page_format = "png" if source_page_copy["role"] == "opaque-source-png-page-textasset-not-decoded" else "astc"
            key=(texture_id,page['sourceTextureSha256']);cached=reusable.get(key)
            if cached is not None:
                cached_path=inside(inside(stage_root,reuse_rendering['moduleStage']),cached['source'])
                png_raw=read(cached_path,max_bytes=128*1024*1024)
                import struct
                if (sha(png_raw)!=cached.get('sha256')or len(png_raw)!=cached.get('bytes')or
                    png_raw[:8]!=b'\x89PNG\r\n\x1a\n'or png_raw[12:16]!=b'IHDR'):
                    raise StaticSpineRenderingError('reused decoded PNG bytes differ from source pin')
                width,height=struct.unpack('>II',png_raw[16:24])
                if (width,height)!=(cached.get('width'),cached.get('height')):
                    raise StaticSpineRenderingError('reused decoded PNG dimensions differ from source pin')
                reused_pages.add(key)
            elif key in generated_pages:
                png_raw,width,height=generated_pages[key]
            else:
                from .normalize import open_texture
                try:
                    image=open_texture(read(source_page_path,max_bytes=128*1024*1024),'.' + page_format).convert('RGBA')
                except Exception as error:
                    raise StaticSpineRenderingError(f'{page_format} page decode failed: {texture_id}:{type(error).__name__}:{error}')from error
                png_buffer=BytesIO();image.save(png_buffer,format='PNG',optimize=False)
                png_raw=png_buffer.getvalue();width,height=image.size;decoded_pages.add(key)
                generated_pages[key]=(png_raw,width,height)
            sampling = _atlas_page_sampling(atlas_text, page["sourcePageName"], data_id)
            png_target = f"{base}/pages/{hashlib.sha256(texture_id.encode()).hexdigest()[:20]}.png"
            png_relative = f"spine-static-rendering-payloads/decoded/{hashlib.sha256((texture_id+page['sourceTextureSha256']).encode()).hexdigest()[:24]}.png"
            png_file = inside(output, png_relative)
            png_file.parent.mkdir(parents=True, exist_ok=True)
            if png_file.exists() and read(png_file, max_bytes=128 * 1024 * 1024) != png_raw:
                raise StaticSpineRenderingError(f"decoded page payload collision: {png_relative}")
            if not png_file.exists():
                png_file.write_bytes(png_raw)
            png_record = {"source": png_relative, "target": png_target, "sha256": sha(png_raw), "bytes": len(png_raw),
                          "role": f"decoded-source-{page_format}-spine-page", "sourceTextureSourceId": texture_id,
                          "sourceTextureSha256": page["sourceTextureSha256"], "width": width, "height": height,
                          "sampling": sampling}
            meta = _meta_payload("spine-static-rendering", png_target, output, "texture",
                                 identity=texture_id, texture_profile=sampling)
            page_token = hashlib.sha256((texture_id + data_id).encode()).hexdigest()[:20]
            page_specs.append({"sourceAtlasPage": page["sourcePageName"], "nativeAtlasPage": page["sourcePageName"],
                               "sourceTextureSourceId": texture_id, "textureAssetPath": png_target,
                               "normalMaterialAssetPath": f"{base}/materials/{page_token}-normal.mat",
                               "graphicNormalMaterialAssetPath": f"{base}/materials/{page_token}-graphic-normal.mat",
                               "variants": [{"blendMode": mode, "sourceSlotCountAcrossAsset": blend["blendModeCounts"][mode],
                                             "sourceSlotCountScope": "whole_skeleton_atlas_pages_not_per_page_count",
                                             "materialAssetPath": f"{base}/materials/{page_token}-{mode}.mat",
                                             "graphicMaterialAssetPath": f"{base}/materials/{page_token}-graphic-{mode}.mat"}
                                            for mode in ("additive", "multiply", "screen") if blend["blendModeCounts"].get(mode, 0) > 0],
                               "sampling": sampling})
            data_render.setdefault(data_id, {"eligible": True, "blendEvidence": blend, "sourceTextureSha256": page["sourceTextureSha256"]})
            data_render[data_id].setdefault("pagePayloads", []).extend([png_record, meta])
        shader_target = _SHADERS[0][1]
        graphic_shader_target = _SHADERS[1][1]
        graphic_raw = (Path(__file__).resolve().parent / _SHADERS[1][0]).read_bytes()
        shader_row = _put_payload(output, Path(__file__).resolve().parent / _SHADERS[0][0], shader_target,
                                  "pinned-spine-source-profile-shader", "0fe1ea3481787d0de2bd7545c8e77d769c681a7d30ca48d6ad56482bdeec549b")
        graphic_row = _put_payload(output, Path(__file__).resolve().parent / _SHADERS[1][0], graphic_shader_target,
                                   "pinned-spine-graphic-profile-shader", "d2b845c11354f91bbf3fb793d82a2024e38a0a31a4665043c4a17a06cb57e964")
        if not graphic_raw:
            raise StaticSpineRenderingError("Spine Graphic profile shader is empty")
        spec = {"sourceAssetId": data_id, "skeletonTextAssetPath": skel_target,
                "skeletonSha256": skeleton_target["sha256"], "atlasTextAssetPath": atlas_target,
                "atlasSha256": row["sourceAtlasSha256"], "atlasAssetPath": base + "/SpineAtlas.asset",
                "skeletonDataAssetPath": base + "/SkeletonData.asset", "shaderAssetPath": shader_target,
                "shaderSha256": shader_row["sha256"], "graphicShaderAssetPath": graphic_shader_target,
                "graphicShaderSha256": graphic_row["sha256"],
                "graphicShaderName": "Monkey/SpineSourceGraphicProfile/Colored", "expectedSpineVersion": blend["spineVersion"],
                "sourceDefaultScale": scale_source["value"], "targetUnitsPerSourcePixel": target_units["targetUnitsPerSourcePixel"],
                "scaleEvidenceSha256": engine_sha, "unitMappingEvidence": target_units,
                "premultipliedAlpha": effective_pma, "pages": page_specs,
                "requiredAnimations": [], "requiredSkins": []}
        page_payloads = data_render[data_id].get("pagePayloads", [])
        data_render[data_id].update({"eligible": True, "factorySpec": spec,
                                     "payloads": [skeleton_target, atlas_output, shader_row, graphic_row, *page_payloads],
                                     "sourceScaleEvidence": scale_source,
                                     "dataAssetGuidPolicy": "Unity AssetDatabase persistent identity readback"})
        if row.get('effectivePma')is not None:data_render[data_id]['effectivePma']=row['effectivePma']

    # Eligibility is capability/data/context based, not activeInHierarchy:
    # templates and their sync instances must have matching renderer topology.
    rows = []
    for component in components:
        data_id = component.get("sourceDataReference", {}).get("sourceDataAssetId")
        data_fact = data_render.get(data_id, {"eligible": False, "gap": "SOURCE_DATA_REFERENCE_MISSING"})
        known = data_fact.get("eligible") is True
        skin, skin_present = _source_field(component, "_skinName")
        default_skin, default_skin_present = _source_field(component, "defaultSkin")
        if not skin_present:
            skin, skin_present = default_skin, default_skin_present
        animation, animation_present = _source_field(component, "_animationName")
        default_animation, default_animation_present = _source_field(component, "defaultAnimation")
        if not animation_present:
            animation, animation_present = default_animation, default_animation_present
        loop, loop_present = _source_field(component, "loop")
        field_gap = None
        if skin_present and default_skin_present and skin != default_skin:
            field_gap = "SOURCE_SKIN_FIELDS_CONFLICT"
        if animation_present and default_animation_present and animation != default_animation:
            field_gap = "SOURCE_ANIMATION_FIELDS_CONFLICT"
        if skin_present and skin is not None and not isinstance(skin, str):
            field_gap = "SOURCE_SKIN_FIELD_INVALID"
        if animation_present and animation is not None and not isinstance(animation, str):
            field_gap = "SOURCE_ANIMATION_FIELD_INVALID"
        if loop_present and type(loop) is not bool:
            field_gap = "SOURCE_LOOP_FIELD_INVALID"
        if isinstance(animation, str) and (data_id, animation) in missing_animations:
            field_gap = "SOURCE_ANIMATION_ABSENT_FROM_SKELETON"
        eligible = known and field_gap is None
        enabled = component.get("sourceComponentEnabled") is True
        node = next((x for x in plan.get("nodes", []) if isinstance(x, dict) and x.get("sourceId") == component.get("sourceNodeId")), None)
        if node is None:raise StaticSpineRenderingError(f"source node is absent: {component.get('sourceNodeId')}")
        color = node.get("color")
        if not (isinstance(color, list) and len(color) == 4 and all(type(x) is int and 0 <= x <= 255 for x in color)):
            raise StaticSpineRenderingError(f"source node color is malformed: {component.get('sourceNodeId')}")
        source_visible = _visible(plan, component)
        gap = field_gap or data_fact.get("gap")
        if not known and not gap:
            gap = "SOURCE_DATA_REFERENCE_MISSING"
        rows.append({"sourceComponentId": component["sourceComponentId"], "sourceNodeId": component["sourceNodeId"],
                     "sourcePrefabId": component.get("sourcePrefabId"),
                     "sourceDataAssetId": data_id, "eligible": known, "sourceVisible": source_visible,
                     "sourceComponentEnabled": enabled, "renderingStatus": "pending-native-readback" if known else "not_rendered",
                     "gap": gap, "sourceSkin": skin if skin_present else None,
                     "sourceSkinSerialized": skin_present, "sourceAnimation": animation if animation_present else None,
                     "sourceAnimationSerialized": animation_present, "sourceLoop": loop if loop_present else False,
                     "sourceLoopSerialized": loop_present, "timeZeroOnly": True, "sourceCodeExecuted": False,
                     "sourceNodeColorRgba8": color, "templateComponentId": component.get("sourceTemplateComponentId"),
                     "sourceComponentEnabledStatus": component.get("sourceComponentEnabledStatus")})
        rows[-1]["eligible"] = eligible
    if len(rows) != len(components) or {r["sourceComponentId"] for r in rows} != {c["sourceComponentId"] for c in components}:
        raise StaticSpineRenderingError("renderer plan does not preserve the full source component denominator")
    for data_id, facts in data_render.items():
        spec = facts.get("factorySpec")
        if not isinstance(spec, dict):
            continue
        spec["requiredAnimations"] = sorted({r["sourceAnimation"] for r in rows
            if r["eligible"] and r["sourceDataAssetId"] == data_id and r["sourceAnimationSerialized"] and r["sourceAnimation"]})
        spec["requiredSkins"] = sorted({r["sourceSkin"] for r in rows
            if r["eligible"] and r["sourceDataAssetId"] == data_id and r["sourceSkinSerialized"] and r["sourceSkin"]})
    rows_by_id = {row["sourceComponentId"]: row for row in rows}
    for row in rows:
        template_id = row.get("templateComponentId")
        if template_id in rows_by_id and rows_by_id[template_id]["eligible"] != row["eligible"]:
            raise StaticSpineRenderingError(f"template/instance renderer topology differs: {row['sourceComponentId']}")

    # Runtime/plugin files and source helper closure are emitted as stage
    # payloads; importer meta files preserve editor/player assembly scopes.
    payloads = []
    for data in data_render.values():
        payloads.extend(data.get("payloads", []))
    payloads.extend(_copy_runtime(runtime_record, output))
    for source_rel, target in _RENDER_HELPERS:
        source = Path(__file__).resolve().parent / source_rel
        payloads.append(_put_payload(output, source, target, "pinned-spine-native-helper"))
        payloads.append(_meta_payload("spine-static-rendering", target, output, "script", identity=source_rel))
    derived_source, derived_target = _DERIVED_HELPER
    payloads.append(_put_payload(output, Path(__file__).resolve().parent / derived_source, derived_target,
                                 "pinned-spine-rendering-derived-helper"))
    payloads.append(_meta_payload("spine-static-rendering", derived_target, output, "script", identity=derived_source))
    for source_rel, target in _SHADERS:
        payloads.append(_meta_payload("spine-static-rendering", target, output, "shader", identity=source_rel))
    # Remove duplicate payload records while preserving all exact target pins.
    unique = {}
    for row in payloads:
        key = (row["target"], row["sha256"])
        unique[key] = row
    try:
        module_stage = output.resolve().relative_to(stage_root).as_posix()
    except ValueError as error:
        raise StaticSpineRenderingError("rendering output must stay inside the frozen plan stage") from error
    shared_mask_identity = Path(__file__).resolve().parent / "targets" / "NativeStaticMaskIdentity.cs"
    blend_totals = {mode: sum(row.get("blendEvidence", {}).get("blendModeCounts", {}).get(mode, 0)
                              for row in data_render.values()) for mode in ("normal", "additive", "multiply", "screen")}
    pma_gaps = sorted(data_id for data_id, facts in data_render.items() if facts.get("eligible") is not True)
    rendering = {"schemaVersion": 1, "contract": CONTRACT, "status": "prepared_static_spine_renderers",
                 "moduleStage": module_stage,
                 "sourceManifestSha256": fragment["sourceManifestSha256"],
                 "sourceContinuationSha256": sha(_canonical(fragment)),
                 "sourceEngine": {"path": str(engine_path), "sha256": engine_sha,
                                  "sourceDefaultScale": 1.0,
                                  "evidence": ["skeleton-data.js scale: 1", "reader.scale=this.scale"]},
                 "unitMapping": target_units,
                 "runtime": {"upstreamCommit": _RUNTIME_COMMIT, "producerManifestSha256": _RUNTIME_PRODUCER,
                             "status": runtime_record.get("status")},
                 "materialProfiles": material_profiles, "components": rows,
                 "dataAssets": [dict(sourceDataAssetId=data_id, **facts) for data_id, facts in data_render.items()],
                 "externalDependencies": [{"target": "Assets/Game/Scripts/Presentation/StaticMasks/NativeStaticMaskIdentity.cs",
                                            "sha256": sha(read(shared_mask_identity, max_bytes=4 * 1024 * 1024)),
                                            "providedBy": "standard-unity-static-mask-export", "copy": False}],
                 "payloads": list(unique.values()), "native": "not_run", "visual": "not_run",
                 "dynamicBehavior": "not_restored", "sourceCodeExecuted": False,
                 "summary": {"sourceComponentCount": len(rows), "eligibleComponentCount": sum(r["eligible"] for r in rows),
                             "sourceVisibleEligibleCount": sum(r["eligible"] and r["sourceVisible"] for r in rows),
                             "pmaOrReferenceGapCount": sum(not r["eligible"] for r in rows),
                             "dataAssetCount": len(data_render), "pmaOrScaleGapSourceDataIds": pma_gaps,
                             "sourceSlotBlendModeCounts": blend_totals,
                             "decodedPageCount": sum(1 for p in unique.values() if p.get("role") in ("decoded-source-astc-spine-page", "decoded-source-png-spine-page")),
                             "reusedDecodedSourceTextureCount":len(reused_pages),
                             "newlyDecodedSourceTextureCount":len(decoded_pages)}}
    patched = dict(plan)
    patched["staticSpineRendering"] = rendering
    upgrade_atlas_mapping(patched, stage_root)
    write_json(output / "spine-static-rendering.json", rendering)
    return {"plan": patched, "rendering": rendering, "status": rendering["status"]}


def verify_rendering(plan: dict, readback: dict) -> list[dict]:
    """Validate the complete 75-row native readback without promoting gaps."""
    fragment = plan.get("staticSpineRendering")
    if not isinstance(fragment, dict):
        return [{"code": "SPINE_RENDERING_PLAN_MISSING"}]
    expected = {row.get("sourceComponentId"): row for row in fragment.get("components", []) if isinstance(row, dict)}
    actual_rows = readback.get("components") if isinstance(readback, dict) else None
    actual = {row.get("sourceComponentId"): row for row in actual_rows or [] if isinstance(row, dict)}
    gaps = []
    if len(actual)!=len(actual_rows or []):gaps.append({'code':'SPINE_RENDERING_SIDECAR_DUPLICATE_COMPONENT_ID'})
    if set(actual) != set(expected):
        gaps.append({"code": "SPINE_RENDERING_COMPONENT_DENOMINATOR_MISMATCH",
                     "missing": sorted(set(expected) - set(actual)), "extra": sorted(set(actual) - set(expected))})
    data_assets = {row.get("sourceDataAssetId"): row for row in fragment.get("dataAssets", []) if isinstance(row, dict)}
    for source_id, row in expected.items():
        saved = actual.get(source_id)
        if not row.get("eligible"):
            if saved and saved.get("rendererCreated"):
                gaps.append({"code": "SPINE_RENDERING_INELIGIBLE_HAS_RENDERER", "sourceId": source_id})
            continue
        if not saved or saved.get("verified") is not True:
            gaps.append({"code": "SPINE_RENDERING_NATIVE_READBACK_UNVERIFIED", "sourceId": source_id})
            continue
        if row.get("sourceVisible") and any(type(saved.get(key))is not int or saved[key]<=0 for key in ('meshVertexCount','meshTriangleCount')):
            gaps.append({"code": "SPINE_RENDERING_VISIBLE_MESH_MISSING", "sourceId": source_id})
        for guid_key,id_key in (('rendererGuid','rendererLocalId'),('dataAssetGuid','dataAssetLocalId')):
            guid_value=saved.get(guid_key);local=saved.get(id_key)
            if (not isinstance(guid_value,str)or re.fullmatch(r'[0-9a-f]{32}',guid_value)is None
                    or type(local)is not int or not -(1<<63)<=local<(1<<63)or local==0):
                gaps.append({'code':'SPINE_RENDERING_PERSISTENT_IDENTITY_INVALID','sourceId':source_id,'field':guid_key})
        for key in ("poseVerified",
                    "colorVerified", "materialReferencesVerified", "unitMappingVerified", "sourceVisibleVerified",
                    "serializedFieldsVerified", "persistent", "dataPersistent"):
            if saved.get(key)is not True:
                gaps.append({"code": "SPINE_RENDERING_READBACK_FIELD_MISSING", "sourceId": source_id, "field": key})
        if saved.get("sourceCodeExecuted") is not False:
            gaps.append({"code": "SPINE_RENDERING_SOURCE_CODE_EXECUTION_NOT_EXCLUDED", "sourceId": source_id})
        if saved.get("sourceDataAssetId") != row.get("sourceDataAssetId"):
            gaps.append({"code": "SPINE_RENDERING_SOURCE_DATA_IDENTITY_MISMATCH", "sourceId": source_id})
        if saved.get("sourceVisible") != row.get("sourceVisible"):
            gaps.append({"code": "SPINE_RENDERING_SOURCE_VISIBILITY_MISMATCH", "sourceId": source_id})
        if saved.get("rendererEnabled") is not row.get("sourceComponentEnabled"):
            gaps.append({"code": "SPINE_RENDERING_COMPONENT_ENABLE_MISMATCH", "sourceId": source_id})
        expected_scale = saved.get("sourceDefaultScale") * saved.get("targetUnitsPerSourcePixel") / saved.get("canvasReferencePixelsPerUnit") if (
            all(type(saved.get(key)) in (int, float) and math.isfinite(saved[key]) and saved[key]>0 for key in ("sourceDefaultScale", "targetUnitsPerSourcePixel", "canvasReferencePixelsPerUnit")) and
            saved.get("canvasReferencePixelsPerUnit", 0) > 0) else None
        if (expected_scale is None or type(saved.get("dataScale")) not in (int, float) or not math.isfinite(saved['dataScale']) or
                abs(saved["dataScale"] - expected_scale) > 0.000001):
            gaps.append({"code": "SPINE_RENDERING_SCALE_FORMULA_MISMATCH", "sourceId": source_id})
        if row.get("sourceSkinSerialized") and row.get("sourceSkin") and saved.get("actualSkin") != row.get("sourceSkin"):
            gaps.append({"code": "SPINE_RENDERING_SAVED_SKIN_MISMATCH", "sourceId": source_id})
        if row.get("sourceAnimationSerialized") and row.get("sourceAnimation") and saved.get("actualAnimation") != row.get("sourceAnimation"):
            gaps.append({"code": "SPINE_RENDERING_SAVED_ANIMATION_MISMATCH", "sourceId": source_id})
        if row.get("sourceLoopSerialized") and saved.get("actualLoop") is not row.get("sourceLoop"):
            gaps.append({"code": "SPINE_RENDERING_SAVED_LOOP_MISMATCH", "sourceId": source_id})
        time_scale = saved.get("timeScale")
        if type(time_scale) not in (int, float) or not math.isfinite(time_scale) or abs(time_scale) > 0.000001:
            gaps.append({"code": "SPINE_RENDERING_TIME_SCALE_NOT_FROZEN", "sourceId": source_id})
        track_time=saved.get('trackTime')
        if type(track_time)not in(int,float)or not math.isfinite(track_time)or abs(track_time)>0.000001:
            gaps.append({'code':'SPINE_RENDERING_TRACK_TIME_NOT_ZERO','sourceId':source_id})
        unit_contract = fragment.get("unitMapping", {})
        expected_source_scale = data_assets.get(row.get("sourceDataAssetId"), {}).get("factorySpec", {}).get("sourceDefaultScale")
        if (saved.get("sourceDefaultScale") != expected_source_scale or
                saved.get("targetUnitsPerSourcePixel") != unit_contract.get("targetUnitsPerSourcePixel")):
            gaps.append({"code": "SPINE_RENDERING_SCALE_INPUT_EVIDENCE_MISMATCH", "sourceId": source_id})
    return gaps


def emit(plan: dict, plan_root: str | Path, output: str | Path) -> dict:
    """Copy every pinned module payload into a candidate Unity project tree."""
    rendering = plan.get("staticSpineRendering")
    if not isinstance(rendering, dict) or rendering.get("contract") != CONTRACT:
        raise StaticSpineRenderingError("plan has no static Spine rendering contract")
    plan_root = Path(plan_root).resolve(strict=True)
    module_stage = rendering.get("moduleStage")
    if not isinstance(module_stage, str):
        raise StaticSpineRenderingError("rendering moduleStage is missing")
    module_root = (plan_root / module_stage).resolve(strict=True)
    if not module_root.is_relative_to(plan_root) or module_root.is_symlink():
        raise StaticSpineRenderingError("rendering moduleStage escapes frozen plan root")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    emitted = []
    for row in rendering.get("payloads", []):
        if not isinstance(row, dict):
            raise StaticSpineRenderingError("rendering payload row is malformed")
        source = _safe_stage_path(module_root, row.get("source"))
        raw = read(source, max_bytes=128 * 1024 * 1024)
        if sha(raw) != row.get("sha256") or len(raw) != row.get("bytes"):
            raise StaticSpineRenderingError(f"rendering payload changed before emit: {row.get('source')}")
        target = row.get("target")
        if not isinstance(target, str) or not target.startswith("Assets/") or ".." in Path(target).parts:
            raise StaticSpineRenderingError(f"invalid emitted target: {target!r}")
        destination = inside(output, target)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and read(destination, max_bytes=128 * 1024 * 1024) != raw:
            raise StaticSpineRenderingError(f"candidate asset collision: {target}")
        if not destination.exists():
            destination.write_bytes(raw)
        emitted.append({"target": target, "sha256": sha(read(destination, max_bytes=128 * 1024 * 1024)),
                        "bytes": destination.stat().st_size, "role": row.get("role")})
    config_raw = encoded(rendering)
    config_target = "Assets/Game/Editor/Conversion/spine-static-rendering.json"
    config_path = inside(output, config_target)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists() and read(config_path, max_bytes=32 * 1024 * 1024) != config_raw:
        raise StaticSpineRenderingError("candidate rendering plan collision")
    if not config_path.exists():
        config_path.write_bytes(config_raw)
    emitted.append({"target": config_target, "sha256": sha(config_raw), "bytes": len(config_raw),
                    "role": "static-spine-rendering-plan"})
    return {"contract": CONTRACT, "status": "emitted", "payloadCount": len(emitted), "payloads": emitted}


def verify(plan: dict, candidate_root: str | Path, readback_path: str | Path | None = None) -> list[dict]:
    """Verify emitted candidate bytes and a real Unity saved-readback sidecar."""
    candidate_root = Path(candidate_root).resolve(strict=True)
    rendering = plan.get("staticSpineRendering")
    if not isinstance(rendering, dict):
        return [{"code": "SPINE_RENDERING_PLAN_MISSING"}]
    gaps = []
    for row in rendering.get("payloads", []):
        try:
            target = row["target"]
            path = (candidate_root / target).resolve(strict=True)
            if not path.is_relative_to(candidate_root) or path.is_symlink():
                raise StaticSpineRenderingError("candidate payload path escapes candidate root")
            raw = read(path, max_bytes=128 * 1024 * 1024)
            if sha(raw) != row.get("sha256") or len(raw) != row.get("bytes"):
                gaps.append({"code": "SPINE_RENDERING_CANDIDATE_PAYLOAD_PIN_MISMATCH", "target": target})
        except (KeyError, OSError, StaticSpineRenderingError) as error:
            gaps.append({"code": "SPINE_RENDERING_CANDIDATE_PAYLOAD_MISSING", "target": row.get("target"), "message": str(error)})
    for dependency in rendering.get("externalDependencies", []):
        try:
            target = dependency["target"]
            path = (candidate_root / target).resolve(strict=True)
            if not path.is_relative_to(candidate_root) or path.is_symlink():
                raise StaticSpineRenderingError("external dependency escapes candidate root")
            raw = read(path, max_bytes=4 * 1024 * 1024)
            if sha(raw) != dependency.get("sha256") or dependency.get("copy") is not False:
                gaps.append({"code": "SPINE_RENDERING_EXTERNAL_DEPENDENCY_PIN_MISMATCH", "target": target})
        except (KeyError, OSError, StaticSpineRenderingError) as error:
            gaps.append({"code": "SPINE_RENDERING_EXTERNAL_DEPENDENCY_MISSING", "target": dependency.get("target"), "message": str(error)})
    config_path = candidate_root / "Assets/Game/Editor/Conversion/spine-static-rendering.json"
    try:
        config_raw = read(config_path, max_bytes=32 * 1024 * 1024)
        if config_raw != encoded(rendering) or json.loads(config_raw.decode("utf-8")) != rendering:
            gaps.append({"code": "SPINE_RENDERING_CANDIDATE_PLAN_MISMATCH"})
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        gaps.append({"code": "SPINE_RENDERING_CANDIDATE_PLAN_MISSING", "message": str(error)})
    sidecar = Path(readback_path) if readback_path is not None else candidate_root / "Analysis/Readback/SpineRendering"
    try:
        documents = []
        if sidecar.is_dir():
            for path in sorted(sidecar.glob("*.json")):
                if path.name in ("prepare.json", "source-canvas-context.json", "owner-context-lifecycle.json"):
                    continue
                raw = read(path, max_bytes=16 * 1024 * 1024)
                documents.append(json.loads(raw.decode("utf-8-sig")))
        else:
            raw = read(sidecar, max_bytes=16 * 1024 * 1024)
            documents.append(json.loads(raw.decode("utf-8-sig")))
        rows = [row for document in documents if isinstance(document, dict)
                for row in document.get("components", []) if isinstance(row, dict)]
        plan_sha = sha(encoded(rendering))
        for document in documents:
            if not isinstance(document, dict) or document.get("contract") != "monkey-static-spine-rendering-readback/1":
                gaps.append({"code": "SPINE_RENDERING_SIDECAR_CONTRACT_INVALID"})
                continue
            if document.get("phase") != "saved-prefab-reopen":
                gaps.append({"code": "SPINE_RENDERING_SIDECAR_PHASE_INVALID", "sourcePrefabId": document.get("sourcePrefabId")})
            if document.get("sourceManifestSha256") != rendering.get("sourceManifestSha256"):
                gaps.append({"code": "SPINE_RENDERING_SIDECAR_SOURCE_MANIFEST_MISMATCH", "sourcePrefabId": document.get("sourcePrefabId")})
            if document.get("renderingPlanSha256") != plan_sha:
                gaps.append({"code": "SPINE_RENDERING_SIDECAR_PLAN_MISMATCH", "sourcePrefabId": document.get("sourcePrefabId")})
            if document.get("unityVersion")!="6000.6.2f1":
                gaps.append({"code": "SPINE_RENDERING_SIDECAR_UNITY_VERSION_MISSING", "sourcePrefabId": document.get("sourcePrefabId")})
            expected_assemblies={row['target']:row['sha256'] for row in rendering.get('payloads',[])
                if row.get('target')in('Assets/Plugins/Spine38/EditorRuntime/spine-csharp.dll','Assets/Plugins/Spine38/EditorRuntime/spine-unity.dll')}
            assemblies=document.get('runtimeAssemblies')
            if (len(expected_assemblies)!=2 or not isinstance(assemblies,list)or len(assemblies)!=2
                    or any(not isinstance(row,dict)for row in assemblies)
                    or {row.get('target')for row in assemblies}!=set(expected_assemblies)):
                gaps.append({'code':'SPINE_RENDERING_LOADED_SDK_EVIDENCE_MISSING'})
            elif any(row.get('verified')is not True or row.get('expectedSha256')!=expected_assemblies[row['target']]
                     or row.get('loadedSha256')!=expected_assemblies[row['target']]or not row.get('loadedPath')for row in assemblies):
                gaps.append({'code':'SPINE_RENDERING_LOADED_SDK_BYTES_MISMATCH'})
            if not isinstance(document.get("sourcePrefabId"), str) or not document.get("sourcePrefabId"):
                gaps.append({"code": "SPINE_RENDERING_SIDECAR_PREFAB_ID_MISSING"})
            expected_for_prefab = {row.get("sourceComponentId") for row in rendering.get("components", [])
                                   if isinstance(row, dict) and row.get("sourcePrefabId") == document.get("sourcePrefabId")}
            actual_for_prefab = {row.get("sourceComponentId") for row in document.get("components", []) if isinstance(row, dict)}
            if actual_for_prefab != expected_for_prefab:
                gaps.append({"code": "SPINE_RENDERING_SIDECAR_PREFAB_DENOMINATOR_MISMATCH",
                             "sourcePrefabId": document.get("sourcePrefabId"),
                             "missing": sorted(expected_for_prefab - actual_for_prefab),
                             "extra": sorted(actual_for_prefab - expected_for_prefab)})
        if len({row.get("sourceComponentId") for row in rows}) != len(rows):
            gaps.append({"code": "SPINE_RENDERING_SIDECAR_DUPLICATE_COMPONENT_ID"})
        expected_ids = {row.get("sourceComponentId") for row in rendering.get("components", []) if isinstance(row, dict)}
        actual_ids = {row.get("sourceComponentId") for row in rows}
        if expected_ids != actual_ids:
            gaps.append({"code": "SPINE_RENDERING_SIDECAR_DENOMINATOR_MISMATCH",
                         "missing": sorted(expected_ids - actual_ids), "extra": sorted(actual_ids - expected_ids)})
        from .spine_canvas_context_readback import verify_context_evidence
        gaps.extend(verify_context_evidence(rendering, candidate_root, documents))
        from .spine_owner_lifecycle_readback import verify_lifecycle_evidence
        gaps.extend(verify_lifecycle_evidence(rendering, candidate_root))
        gaps.extend(verify_rendering(plan, {"components": rows}))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        gaps.append({"code": "SPINE_RENDERING_SIDECAR_UNREADABLE", "message": str(error)})
    return gaps


# Public names used by the shared static continuation dispatcher.
prepare = prepare_rendering
