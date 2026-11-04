"""Source-bound static bindings for the residual Cocos mask/sort components.

This module intentionally emits an auditable native presentation contract. It
does not reinterpret arbitrary source render graphs: the target helpers reject
sort layouts that cannot be expressed by stable sibling order.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from pathlib import Path


_UNITY_MASK_SHADER = "Assets/Game/Content/Materials/StaticMasks/NativeStaticImageMask.shader"


class StaticMaskSortError(ValueError):
    pass


def _bound_manifest(plan: Mapping, manifest: Mapping) -> None:
    path = plan.get("sourceManifestPath")
    expected = plan.get("sourceManifestSha256")
    if not isinstance(path, str) or not isinstance(expected, str):
        raise StaticMaskSortError("plan lacks source manifest binding")
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise StaticMaskSortError(f"bound source manifest unavailable: {path}") from exc
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise StaticMaskSortError(f"source manifest SHA-256 mismatch: {actual}")
    try:
        frozen = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StaticMaskSortError("bound source manifest is invalid JSON") from exc
    # A caller may pass the parsed manifest, but it must still match the exact
    # bytes to which the plan was bound.
    if json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) != json.dumps(
        frozen, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ):
        raise StaticMaskSortError("in-memory manifest differs from hash-bound manifest")


def _raw_component(manifest: Mapping, source_id: str) -> Mapping:
    asset_id, sep, suffix = source_id.partition("#")
    if not sep:
        raise StaticMaskSortError(f"invalid component source identity: {source_id}")
    asset = next((a for a in manifest.get("assets", []) if a.get("sourceId") == asset_id), None)
    if not isinstance(asset, Mapping) or asset.get("kind") not in ("cc.Prefab", "cc.SceneAsset"):
        raise StaticMaskSortError(f"component source asset missing: {asset_id}")
    instances = asset.get("document", {}).get("instances")
    if not isinstance(instances, list):
        raise StaticMaskSortError(f"component source has no frozen instances: {asset_id}")
    parts = suffix.split("/components/")
    try:
        node_index = int(parts[0])
        if len(parts) == 1:
            raw = instances[node_index]
        else:
            ordinal = int(parts[1])
            node = instances[node_index]
            ref = node.get("_components", [])[ordinal]
            if isinstance(ref, Mapping) and type(ref.get("__id__")) is int:
                raw = instances[ref["__id__"]]
            elif isinstance(ref, Mapping):
                raw = ref
            else:
                raise TypeError
    except (IndexError, TypeError, ValueError) as exc:
        raise StaticMaskSortError(f"component identity does not resolve in source document: {source_id}") from exc
    if not isinstance(raw, Mapping):
        raise StaticMaskSortError(f"malformed component object: {source_id}")
    return raw


def _uuid_asset(manifest: Mapping, bundle: str, uuid: str) -> tuple[str, Mapping]:
    assets = manifest.get("assets", [])
    matches = [asset for asset in assets if asset.get("sourceId", "").split(":", 1)[-1] == uuid]
    preferred = [asset for asset in matches if asset.get("sourceId", "").startswith(bundle + ":")]
    candidates = preferred or matches
    if len(candidates) != 1:
        raise StaticMaskSortError(f"source UUID is absent or ambiguous: {uuid}")
    original = candidates[0]
    asset = original
    seen = set()
    while asset.get("kind") == "redirect":
        source_id = asset.get("sourceId")
        if source_id in seen:
            raise StaticMaskSortError(f"source UUID redirect cycle: {source_id}")
        seen.add(source_id)
        target = asset.get("redirectTarget")
        asset = next((candidate for candidate in assets if candidate.get("sourceId") == target), None)
        if asset is None:
            raise StaticMaskSortError(f"source UUID redirect target missing: {target}")
    return original["sourceId"], asset


def _mask_material_proof(manifest: Mapping, bundle: str, raw: Mapping) -> dict:
    from .shader_profiles import FRAGMENT_SHA256, VERTEX_SHA256

    material_refs = raw.get("_materials")
    if not isinstance(material_refs, list) or len(material_refs) != 1 or not isinstance(material_refs[0], Mapping):
        raise StaticMaskSortError("mask source must have one exact source material reference")
    material_uuid = material_refs[0].get("__uuid__")
    if not isinstance(material_uuid, str):
        raise StaticMaskSortError("mask source material is not a UUID reference")
    material_id, material_asset = _uuid_asset(manifest, bundle, material_uuid)
    material_doc = material_asset.get("document")
    material_rows = material_doc.get("instances") if isinstance(material_doc, Mapping) else None
    root = material_rows[material_doc.get("root", 0)] if isinstance(material_rows, list) and material_rows else None
    if (material_asset.get("kind") != "cc.Material" or not isinstance(root, Mapping) or
            root.get("__type__") != "cc.Material" or root.get("_name") != "builtin-2d-sprite"):
        raise StaticMaskSortError(f"mask source material is outside the reviewed profile: {material_id}")
    # The pinned Creator material has one technique, only USE_TEXTURE enabled,
    # and no serialized property overrides. Any additional define/property is a
    # distinct source material profile and must not borrow the builtin adapter.
    if set(root) != {"__type__", "_effectAsset", "_name", "_techniqueData"}:
        raise StaticMaskSortError(f"mask source material fields differ from the pinned profile: {material_id}")
    technique_data = root.get("_techniqueData")
    if (not isinstance(technique_data, Mapping) or set(technique_data) != {"0"} or
            technique_data.get("0") != {"defines": {"USE_TEXTURE": True}}):
        raise StaticMaskSortError(f"mask source material defines/properties differ from the pinned profile: {material_id}")
    effect_ref = root.get("_effectAsset")
    if not isinstance(effect_ref, Mapping) or not isinstance(effect_ref.get("__uuid__"), str):
        raise StaticMaskSortError("mask source material has no exact effect reference")
    effect_id, effect_asset = _uuid_asset(manifest, material_asset.get("bundle", bundle), effect_ref["__uuid__"])
    effect_rows = effect_asset.get("document", {}).get("instances", [])
    effect_root = effect_rows[0] if effect_rows else None
    if (effect_asset.get("kind") != "cc.EffectAsset" or not isinstance(effect_root, Mapping) or
            effect_root.get("__type__") != "cc.EffectAsset" or effect_root.get("_name") != "builtin-2d-sprite"):
        raise StaticMaskSortError(f"mask source effect is outside the reviewed profile: {effect_id}")
    shaders = effect_root.get("shaders")
    if not isinstance(shaders, list) or len(shaders) != 1 or not isinstance(shaders[0], Mapping):
        raise StaticMaskSortError(f"mask source effect shader set differs from the pinned profile: {effect_id}")
    shader = shaders[0]
    glsl = shader.get("glsl1")
    if (shader.get("name") != "builtin-2d-sprite|vs|fs" or not isinstance(glsl, Mapping) or
            not isinstance(glsl.get("vert"), str) or not isinstance(glsl.get("frag"), str)):
        raise StaticMaskSortError(f"mask source effect GLSL profile is incomplete: {effect_id}")
    vertex_sha = hashlib.sha256(glsl["vert"].encode("utf-8")).hexdigest()
    fragment_sha = hashlib.sha256(glsl["frag"].encode("utf-8")).hexdigest()
    if vertex_sha != VERTEX_SHA256 or fragment_sha != FRAGMENT_SHA256:
        raise StaticMaskSortError(f"mask source effect GLSL hashes differ from the pinned profile: {effect_id}")
    expected_defines = {
        "USE_TEXTURE": {"defines": [], "name": "USE_TEXTURE", "type": "boolean"},
        "CC_USE_MODEL": {"defines": [], "name": "CC_USE_MODEL", "type": "boolean"},
        "USE_ALPHA_TEST": {"defines": [], "name": "USE_ALPHA_TEST", "type": "boolean"},
        "CC_USE_ALPHA_ATLAS_texture": {"defines": ["USE_TEXTURE"], "name": "CC_USE_ALPHA_ATLAS_texture", "type": "boolean"},
        "INPUT_IS_GAMMA": {"defines": ["USE_TEXTURE"], "name": "INPUT_IS_GAMMA", "type": "boolean"},
        "USE_BGRA": {"defines": [], "name": "USE_BGRA", "type": "boolean"},
    }
    define_rows = shader.get("defines")
    if (not isinstance(define_rows, list) or len(define_rows) != len(expected_defines) or
            {row.get("name"): row for row in define_rows if isinstance(row, Mapping)} != expected_defines):
        raise StaticMaskSortError(f"mask source effect macro declarations differ from the pinned profile: {effect_id}")
    techniques = effect_root.get("techniques")
    expected_properties = {"alphaThreshold": {"type": 13, "value": [0.5]},
                           "texture": {"type": 29, "value": "white"}}
    if (not isinstance(techniques, list) or len(techniques) != 1 or
            not isinstance(techniques[0], Mapping) or not isinstance(techniques[0].get("passes"), list) or
            len(techniques[0]["passes"]) != 1):
        raise StaticMaskSortError(f"mask source effect technique set differs from the pinned profile: {effect_id}")
    source_pass = techniques[0]["passes"][0]
    if (not isinstance(source_pass, Mapping) or source_pass.get("program") != "builtin-2d-sprite|vs|fs" or
            source_pass.get("blendState") != {"targets": [{"blend": True}]} or
            source_pass.get("rasterizerState") != {"cullMode": 0} or
            source_pass.get("properties") != expected_properties):
        raise StaticMaskSortError(f"mask source effect properties/render state differ from the pinned profile: {effect_id}")
    effect_sha = hashlib.sha256(json.dumps(effect_root, ensure_ascii=False, sort_keys=True,
                                           separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"sourceMaterialId": material_id, "resolvedSourceMaterialId": material_asset.get("sourceId"),
            "sourceMaterialName": root.get("_name"), "sourceEffectId": effect_id,
            "sourceEffectName": effect_root.get("_name"), "sourceEffectDocumentSha256": effect_sha,
            "sourceEffectProgramSha256": {"glsl1.vert": vertex_sha, "glsl1.frag": fragment_sha}}


def _origin_rows(plan: Mapping, manifest: Mapping, source_type: str) -> list[dict]:
    rows = [row for row in plan.get("components", []) if row.get("type") == source_type]
    unique: dict[str, dict] = {}
    origins={r['instanceSourceId']:r['templateSourceId'] for r in plan.get('staticAnimationComponentOrigins',[])}
    def origin(sid):
        seen=set()
        while sid in origins:
            if sid in seen:raise StaticMaskSortError('component origin cycle')
            seen.add(sid);sid=origins[sid]
        return sid
    for row in rows:
        source_id = row.get("sourceId")
        root_id=origin(source_id)
        native_id = row.get("nativeId") or uuid.uuid5(uuid.NAMESPACE_URL,'monkey/static-mask/'+str(plan.get('namespace'))+'/'+str(root_id)).hex
        if not isinstance(source_id, str) or not isinstance(native_id, str):
            raise StaticMaskSortError(f"{source_type} plan row lacks source identity")
        if source_type == "cc.Mask" and row.get("convertible") is True:
            continue
        # Prefab sync copies have generated sourceIds, but retain the source
        # nativeId. Resolve the original source row once and keep every plan
        # occurrence separately in the target bindings below.
        raw = _raw_component(manifest, root_id)
        if raw.get("__type__") != source_type:
            raise StaticMaskSortError(f"{source_type} source identity resolves to {raw.get('__type__')!r}")
        binding = {"sourceId": source_id, "sourceOriginId": root_id, "nativeId": native_id,
                   "node": row.get("node"), "enabled": row.get("enabled") is True}
        if source_type == "cc.Mask":
            mask_type = raw.get("_type", 0)
            # Cocos 2.4 serialized inspector keys carry the `_N$` prefix.
            inverted = raw.get("_N$inverted", False)
            threshold = raw.get("_N$alphaThreshold", 0.1)
            if type(mask_type) is not int or mask_type not in (0, 1, 2) or type(inverted) is not bool:
                raise StaticMaskSortError(f"unsupported or missing source mask fields: {source_id}")
            if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
                raise StaticMaskSortError(f"invalid source alpha threshold: {source_id}")
            sprite = raw.get("_spriteFrame")
            if mask_type == 2 and (not isinstance(sprite, Mapping) or not isinstance(sprite.get("__uuid__"), str)):
                raise StaticMaskSortError(f"image stencil has no exact SpriteFrame UUID: {source_id}")
            if row.get("maskType") != mask_type or row.get("inverted") is not inverted:
                raise StaticMaskSortError(f"plan mask identity/fields differ from source: {source_id}")
            material = _mask_material_proof(manifest, source_id.partition(":")[0], raw)
            if mask_type == 2:
                shader_path = Path(__file__).parent / "targets/materials/static_mask/NativeStaticImageMask.shader"
                try:
                    shader_bytes = shader_path.read_bytes()
                except OSError as exc:
                    raise StaticMaskSortError("Unity image-mask shader payload is unavailable") from exc
                material["unityMaskShaderPath"] = _UNITY_MASK_SHADER
                material["unityMaskShaderSha256"] = hashlib.sha256(shader_bytes).hexdigest()
                material["unityMaskMaterialGuid"] = uuid.uuid5(uuid.NAMESPACE_URL,
                    "monkey/static-mask/image/" + material["sourceEffectDocumentSha256"] + "/" + str(threshold)).hex
                material["unityMaskMaterialPath"] = "Assets/Game/Content/Materials/StaticMasks/NativeStaticImageMask_" + str(threshold).replace(".", "_") + ".mat"
            binding.update({"maskType": mask_type, "inverted": inverted, "alphaThreshold": threshold,
                            "spriteFrameUuid": sprite.get("__uuid__") if isinstance(sprite, Mapping) else None,
                            "sourceFields": dict(raw),
                            **material})
        else:
            if source_type == "cc.SortOrder":
                value = raw.get("_sortOrder", 0)
                if type(value) not in (int, float):
                    raise StaticMaskSortError(f"invalid source sortOrder value: {source_id}")
                binding["sortOrder"] = value
            else:
                binding["sortRoot"] = True
        prior = unique.get(root_id)
        if prior is not None:
            compare = {k: v for k, v in binding.items() if k not in ("sourceId", "node")}
            prior_compare = {k: v for k, v in prior.items() if k not in ("sourceId", "node")}
            if compare != prior_compare:
                raise StaticMaskSortError(f"plan clones disagree on source-native identity {native_id}")
        else:
            unique[root_id] = binding
    occurrences = []
    for row in rows:
        if source_type == "cc.Mask" and row.get("convertible") is True:
            continue
        base = unique[origin(row["sourceId"])]
        occurrence = dict(base)
        occurrence.update(sourceId=row["sourceId"], node=row.get("node"), enabled=row.get("enabled") is True)
        occurrences.append(occurrence)
    return occurrences


def _check_sort_scope(plan: Mapping, sort_orders: list[dict], sort_roots: list[dict]) -> None:
    """Reject cross-parent source ordering that sibling-order mapping cannot preserve."""
    nodes = {n["sourceId"]: n for n in plan.get("nodes", [])}
    order_by_node = {r["node"]: r["sortOrder"] for r in sort_orders}
    roots = {r["node"] for r in sort_roots}
    # SortOrder changes render-leaf order in the nearest SortRoot queue. A
    # stable sibling sort is sound only when each sibling subtree is a
    # contiguous interval in the flattened source order.
    # Explicit contract/data shape currently supports same-parent reordering.
    # Do not silently flatten nested SortRoot queues or interleave render leaves.
    by_parent: dict[str | None, list[tuple[str, float]]] = {}
    for node_id, value in order_by_node.items():
        if node_id in nodes:
            by_parent.setdefault(nodes[node_id].get("parent"), []).append((node_id, value))
    for parent, entries in by_parent.items():
        if len(entries) < 2:
            continue
        # Ordering renderers from different source parents is not representable
        # by moving whole child transforms without changing the source tree.
        # This module sorts sibling nodes only and preserves stable source ties.
        if any(node not in nodes for node, _ in entries):
            raise StaticMaskSortError(f"sort node missing from plan under {parent}")


def _sort_groups(plan: Mapping, sort_orders: list[dict], sort_roots: list[dict]) -> list[dict]:
    nodes = {n["sourceId"]: n for n in plan.get("nodes", [])}
    by_node = {row["node"]: row for row in sort_orders}
    root_nodes = {row["node"] for row in sort_roots}
    components_by_node: dict[str, list[dict]] = {}
    for component in plan.get("components", []):
        components_by_node.setdefault(component.get("node"), []).append(component)
    render_types = {"cc.Sprite", "cc.Label", "cc.RichText", "cc.Graphics", "cc.ParticleSystem",
                    "sp.Skeleton", "sp.SkeletonAnimation", "cc.MeshRenderer", "cc.TiledMap"}
    groups = []
    parents = {nodes[node].get("parent") for node in by_node if node in nodes and nodes[node].get("parent") is not None}
    for parent_id in sorted(parents, key=lambda x: "" if x is None else x):
        parent = nodes.get(parent_id)
        child_ids = list(parent.get("children", []))
        entries = [{"node": child, "sourceSiblingIndex": index,
                    "sortOrder": by_node[child]["sortOrder"] if child in by_node else 0,
                    "explicit": child in by_node}
                   for index, child in enumerate(child_ids)]
        expected = sorted(entries, key=lambda e: (e["sortOrder"], e["sourceSiblingIndex"]))
        issues = []
        for child in child_ids:
            descendants = []
            stack = [child]
            while stack:
                current = stack.pop()
                descendants.append(current)
                stack.extend(nodes.get(current, {}).get("children", []))
            rendered = [(n, c) for n in descendants for c in components_by_node.get(n, []) if c.get("type") in render_types]
            if any(n != child for n, _ in rendered):
                issues.append("renderable-descendant-requires-cross-parent-sort")
            if any(n != child for n in descendants if n in by_node):
                issues.append("nested-sortorder-requires-cross-parent-sort")
            if any(n != child for n in descendants if n in root_nodes):
                issues.append("nested-sortroot-is-a-separate-queue")
        issues = sorted(set(issues))
        # nearest SortRoot at or above this sibling queue is recorded so an
        # adapter never merges two nested render queues.
        scope = parent_id
        while scope is not None and scope not in root_nodes:
            scope = nodes.get(scope, {}).get("parent")
        groups.append({"parent": parent_id, "sortRootScope": scope,
                       "children": entries,
                       "expectedSiblingOrder": [e["node"] for e in expected],
                       "changed": [e["node"] for e in entries] != [e["node"] for e in expected],
                       "representableBySiblingOrder": not issues, "limitations": issues})
    return groups


def prepare(plan: Mapping, manifest: Mapping) -> dict:
    """Return source-bound mask/sort specs for Unity and Creator native helpers."""
    _bound_manifest(plan, manifest)
    masks = _origin_rows(plan, manifest, "cc.Mask")
    orders = _origin_rows(plan, manifest, "cc.SortOrder")
    roots = _origin_rows(plan, manifest, "cc.SortRoot")
    _check_sort_scope(plan, orders, roots)
    groups = _sort_groups(plan, orders, roots)
    return {"schemaVersion": 1, "sourceManifestSha256": plan["sourceManifestSha256"],
            "masks": masks, "sortOrders": orders, "sortRoots": roots, "sortGroups": groups,
            "sortSemantics": "Cocos RenderFlow numeric render-leaf ordering inside nearest nested SortRoot queue; equal values retain traversal order",
            "sortLimitations": ["sortGroups are analysis proposals only; no source hierarchy mutation is applied",
                                "Unity target requires a global queue adapter with ancestor stencil propagation",
                                "Creator target requires render-queue ordering rather than sibling-only reordering",
                                "SortRoot is a nested queue boundary and must remain intact"]}
