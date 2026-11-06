"""Prepare source-backed static SpriteFrame projections for scene-local previews.

This module is intentionally independent from the import/preview entry points.
It validates a bounded recipe against a frozen target plan and a raw source
manifest, then emits a target-neutral projection plan. It never opens an
Editor, loads a source script, edits a Prefab asset, or invents image content.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from pathlib import Path

from . import io

_SCHEMA = "monkey-prefab-static-sprite-projection/1"
_PLAN_SCHEMA = "monkey-prefab-static-sprite-projection-plan/1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_ENTRIES = 64


class SpriteProjectionError(ValueError):
    """Invalid source asset identity, projection geometry, or target parent."""


def _need(value, label):
    if not isinstance(value, str) or not value.strip():
        raise SpriteProjectionError(f"{label} must be a non-empty string")
    return value


def _digest(value, label):
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise SpriteProjectionError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _vec(value, size, label, *, positive=False):
    if (not isinstance(value, list) or len(value) != size or
            any(type(x) not in (int, float) or not math.isfinite(x) for x in value)):
        raise SpriteProjectionError(f"{label} must be a finite {size}-number vector")
    if positive and any(x <= 0 for x in value):
        raise SpriteProjectionError(f"{label} values must be positive")
    return list(value)


def _source_asset(manifest, asset_id):
    rows = [row for row in manifest.get("assets", [])
            if isinstance(row, Mapping) and row.get("sourceId") == asset_id]
    if len(rows) != 1:
        raise SpriteProjectionError(f"source SpriteFrame must resolve exactly once: {asset_id}")
    row = rows[0]
    if row.get("kind") != "cc.SpriteFrame":
        raise SpriteProjectionError(f"source asset is not a cc.SpriteFrame: {asset_id}")
    document = row.get("document")
    instances = document.get("instances") if isinstance(document, Mapping) else None
    if not isinstance(instances, list) or len(instances) != 1:
        raise SpriteProjectionError(f"SpriteFrame source document is not a single instance: {asset_id}")
    frame = instances[0]
    if frame.get("__type__") != "cc.SpriteFrame" or not isinstance(frame.get("data"), Mapping):
        raise SpriteProjectionError(f"SpriteFrame source document has an unsupported shape: {asset_id}")
    texture_uuid = frame.get("_textureSetter", {}).get("__uuid__")
    if not isinstance(texture_uuid, str) or not texture_uuid:
        raise SpriteProjectionError(f"SpriteFrame has no source Texture2D identity: {asset_id}")
    rect = frame["data"].get("rect")
    original = frame["data"].get("originalSize")
    if (not isinstance(rect, list) or len(rect) != 4 or
            any(type(x) not in (int, float) or not math.isfinite(x) for x in rect) or
            rect[2] <= 0 or rect[3] <= 0 or
            not isinstance(original, list) or len(original) != 2 or
            any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0 for x in original)):
        raise SpriteProjectionError(f"SpriteFrame geometry is invalid: {asset_id}")
    return row, frame, texture_uuid, list(rect), list(original)


def prepare(recipe_path, expected_sha256, plan_path, source_asset_manifest_path, source_js_path, out):
    """Validate a pinned recipe and emit ``projection-plan.json``.

    ``source_asset_manifest_path`` is the raw source manifest containing the
    asset document; ``plan_path`` is the owned target-plan stage used to bind
    the source parent. A missing target texture is reported as a resource
    closure gap, while malformed or mismatched source evidence is rejected.
    """
    recipe_path = io.safe(recipe_path)
    plan_path = io.safe(plan_path)
    source_asset_manifest_path = io.safe(source_asset_manifest_path)
    source_js_path = io.safe(source_js_path)
    expected_sha256 = _digest(expected_sha256, "expected_sha256")

    recipe_raw = io.read(recipe_path)
    if io.sha(recipe_raw) != expected_sha256:
        raise SpriteProjectionError("recipe SHA-256 differs from expected_sha256")
    recipe = io.load(recipe_raw, max_nodes=100_000, max_depth=48)
    if not isinstance(recipe, Mapping) or recipe.get("schema") != _SCHEMA:
        raise SpriteProjectionError(f"expected recipe schema {_SCHEMA}")

    try:
        plan_raw = io.stage_bytes(plan_path)
        plan = io.stage_document(plan_path)
    except Exception as error:
        raise SpriteProjectionError("target plan is not an intact owned stage document") from error
    plan_sha = io.sha(plan_raw)
    if plan_sha != _digest(recipe.get("sourcePlanSha256"), "sourcePlanSha256"):
        raise SpriteProjectionError("target plan SHA-256 differs from the pinned recipe")
    if plan.get("sourceManifestSha256") != recipe.get("sourceManifestSha256"):
        raise SpriteProjectionError("target plan sourceManifestSha256 differs from the recipe")

    # Frozen inspection manifests may be larger than the ordinary JSON input
    # budget. Keep the expanded limit local to this explicitly pinned source
    # artifact rather than widening the global reader budget.
    source_manifest_raw = io.read(source_asset_manifest_path, max_bytes=128 * 1024 * 1024)
    source_manifest_sha = io.sha(source_manifest_raw)
    if source_manifest_sha != _digest(recipe.get("sourceAssetManifestSha256"), "sourceAssetManifestSha256"):
        raise SpriteProjectionError("raw source asset manifest SHA-256 differs from the recipe")
    source_manifest = io.load(source_manifest_raw, max_nodes=16_000_000, max_depth=128)

    source_js_raw = io.read(source_js_path)
    source_js_sha = io.sha(source_js_raw)
    if source_js_sha != _digest(recipe.get("sourceGameJsSha256"), "sourceGameJsSha256"):
        raise SpriteProjectionError("source game.js SHA-256 differs from the recipe")

    source_prefabs = plan.get("sourcePrefabs")
    prefab_id = _need(recipe.get("sourcePrefabId"), "sourcePrefabId")
    if not isinstance(source_prefabs, list) or not any(
            isinstance(row, Mapping) and row.get("sourceId") == prefab_id for row in source_prefabs):
        raise SpriteProjectionError("source prefab identity is absent from the target plan")

    nodes = plan.get("nodes")
    if not isinstance(nodes, list):
        raise SpriteProjectionError("target plan nodes must be an array")
    node_by_id = {row.get("sourceId"): row for row in nodes if isinstance(row, Mapping)}
    if len(node_by_id) != len(nodes):
        raise SpriteProjectionError("target plan contains missing or duplicate node source IDs")

    evidence_rows = recipe.get("evidenceFiles")
    if not isinstance(evidence_rows, list) or not evidence_rows:
        raise SpriteProjectionError("evidenceFiles must be a non-empty array")
    evidence_paths = []
    normalized_evidence = []
    seen_evidence_ids = set()
    for row in evidence_rows:
        if not isinstance(row, Mapping):
            raise SpriteProjectionError("evidence row must be an object")
        evidence_id = _need(row.get("id"), "evidence.id")
        relative = _need(row.get("path"), "evidence.path")
        digest = _digest(row.get("sha256"), "evidence.sha256")
        if evidence_id in seen_evidence_ids:
            raise SpriteProjectionError(f"duplicate evidence id: {evidence_id}")
        seen_evidence_ids.add(evidence_id)
        try:
            evidence_path = io.inside(recipe_path.parent, relative)
            raw = io.read(evidence_path)
        except Exception as error:
            raise SpriteProjectionError(f"evidence file is missing or unsafe: {evidence_id}") from error
        if io.sha(raw) != digest:
            raise SpriteProjectionError(f"evidence SHA-256 mismatch: {evidence_id}")
        evidence_paths.append(evidence_path)
        normalized_evidence.append({"id": evidence_id, "path": relative, "sha256": digest})

    entries = recipe.get("entries")
    if not isinstance(entries, list) or not entries or len(entries) > _MAX_ENTRIES:
        raise SpriteProjectionError(f"entries must contain 1..{_MAX_ENTRIES} projections")
    asset_rows = {row.get("sourceId"): row for row in source_manifest.get("assets", [])
                  if isinstance(row, Mapping)}
    texture_rows = {row.get("id"): row for row in plan.get("textures", [])
                    if isinstance(row, Mapping)}
    if plan.get("targetProfile")=="cocos-3.8.8":
        texture_rows={row.get("sourceId"):row for row in plan.get("assets",[]) if isinstance(row,Mapping) and row.get("kind")=="sprite"}
    projection_ids = set()
    normalized_entries = []
    diagnostics = []
    required_assets = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise SpriteProjectionError(f"entries[{index}] must be an object")
        projection_id = _need(entry.get("projectionId"), f"entries[{index}].projectionId")
        if projection_id in projection_ids:
            raise SpriteProjectionError(f"duplicate projectionId: {projection_id}")
        projection_ids.add(projection_id)
        parent_id = _need(entry.get("parentSourceId"), f"entries[{index}].parentSourceId")
        if not parent_id.startswith(prefab_id + "#") or parent_id not in node_by_id:
            raise SpriteProjectionError(f"projection parent is outside source prefab: {parent_id}")
        parent = node_by_id[parent_id]
        expected_children = entry.get("expectedParentChildSourceIds")
        if not isinstance(expected_children, list) or parent.get("children") != expected_children:
            raise SpriteProjectionError(f"projection parent children differ from source plan: {parent_id}")

        root = entry.get("root")
        child = entry.get("spriteChild")
        if not isinstance(root, Mapping) or not isinstance(child, Mapping):
            raise SpriteProjectionError(f"entries[{index}] requires root and spriteChild objects")
        root_name = _need(root.get("name"), f"entries[{index}].root.name")
        child_name = _need(child.get("name"), f"entries[{index}].spriteChild.name")
        root_size = _vec(root.get("size"), 2, "root.size", positive=True)
        root_position = _vec(root.get("localPosition"), 3, "root.localPosition")
        root_scale = _vec(root.get("localScale"), 3, "root.localScale", positive=True)
        child_position = _vec(child.get("localPosition"), 3, "spriteChild.localPosition")
        child_anchor = _vec(child.get("anchor"), 2, "spriteChild.anchor")
        if any(x < 0 or x > 1 for x in child_anchor):
            raise SpriteProjectionError("spriteChild.anchor must be in [0,1]")
        if child.get("sizeMode") != "TRIMMED":
            raise SpriteProjectionError("only source Sprite.SizeMode.TRIMMED is supported")
        sprite_id = _need(child.get("spriteFrameSourceId"), f"entries[{index}].spriteFrameSourceId")
        requested_path = _need(child.get("logicalPath"), f"entries[{index}].logicalPath")
        asset, frame, texture_id, rect, original_size = _source_asset(source_manifest, sprite_id)
        if asset.get("logicalPath") != requested_path:
            raise SpriteProjectionError(f"SpriteFrame logical path differs from source manifest: {sprite_id}")
        offset = frame["data"].get("offset", [0, 0])
        if (rect[:2] != [0, 0] or rect[2:] != original_size or offset != [0, 0]):
            raise SpriteProjectionError(
                f"SpriteFrame trim/atlas offsets are not supported by this native projection: {sprite_id}")
        requested_rect = child.get("sourceRect")
        if requested_rect != rect:
            raise SpriteProjectionError(f"spriteChild.sourceRect differs from frozen source frame: {sprite_id}")
        requested_original = child.get("originalSize")
        if requested_original != original_size:
            raise SpriteProjectionError(f"spriteChild.originalSize differs from frozen source frame: {sprite_id}")
        color = _vec(child.get("color"), 4, "spriteChild.color")
        if any(type(x) is not int or x < 0 or x > 255 for x in color):
            raise SpriteProjectionError("spriteChild.color must contain four integer byte values")
        target_row = texture_rows.get(sprite_id)
        if target_row is None:
            required_assets.append({"sourceId": sprite_id, "logicalPath": requested_path,
                                    "textureSourceId": "gameAsset:" + texture_id,
                                    "status": "source_verified_target_texture_not_in_plan"})
            diagnostics.append(io.diagnostic("SPRITE_FRAME_TARGET_RESOURCE_NOT_BOUND", sprite_id,
                "Source SpriteFrame is verified, but target plan.textures has no matching source ID.", sprite_id))
        else:
            if target_row.get("size") != [rect[2], rect[3]] or target_row.get("originalSize") != original_size:
                raise SpriteProjectionError(f"target texture geometry differs from source SpriteFrame: {sprite_id}")
        normalized_entries.append({
            "projectionId": projection_id, "parentSourceId": parent_id,
            "expectedParentChildSourceIds": list(expected_children),
            "root": {"name": root_name, "size": root_size, "localPosition": root_position,
                     "localScale": root_scale, "active": root.get("active") is True,
                     "color": root.get("color", [255, 255, 255, 255]),
                     "zIndex": root.get("sourceZIndex")},
            "spriteChild": {"name": child_name, "spriteFrameSourceId": sprite_id,
                            "logicalPath": requested_path, "textureSourceId": "gameAsset:" + texture_id,
                            "sourceRect": rect, "originalSize": original_size,
                            "localPosition": child_position, "anchor": child_anchor,
                            "sizeMode": "TRIMMED", "color": color,
                            "enabled": child.get("enabled") is True},
            "sourceAssetIndex": asset.get("index"),
            "targetResourceBound": target_row is not None
        })

    render_plan = {
        "schema": _PLAN_SCHEMA,
        "recipeId": _need(recipe.get("recipeId"), "recipeId"),
        "recipeSha256": expected_sha256,
        "sourcePrefabId": prefab_id,
        "sourceManifestSha256": plan.get("sourceManifestSha256"),
        "sourcePlanSha256": plan_sha,
        "sourceAssetManifestSha256": source_manifest_sha,
        "sourceGameJsSha256": source_js_sha,
        "sourceVersion": _need(recipe.get("sourceVersion"), "sourceVersion"),
        "referenceVersion": _need(recipe.get("referenceVersion"), "referenceVersion"),
        "evidence": normalized_evidence,
        "entries": normalized_entries,
        "requiredTargetResources": required_assets,
        "sourceBehaviorsExecuted": False,
        "diagnostics": diagnostics
    }
    out = io.new_output(out, [recipe_path, plan_path, source_asset_manifest_path, source_js_path, *evidence_paths])
    io.write_json(out / "projection-plan.json", render_plan)
    report = {
        "schema": "monkey-prefab-static-sprite-projection-report/1",
        "recipeId": render_plan["recipeId"],
        "recipeSha256": expected_sha256,
        "sourcePlanSha256": plan_sha,
        "sourceManifestSha256": plan.get("sourceManifestSha256"),
        "sourceAssetManifestSha256": source_manifest_sha,
        "entryCount": len(normalized_entries),
        "sourceSpriteFramesVerified": len(normalized_entries),
        "targetResourceBoundCount": sum(row["targetResourceBound"] for row in normalized_entries),
        "requiredTargetResources": required_assets,
        "diagnostics": diagnostics,
        "sourceBehaviorsExecuted": False
    }
    return io.finish(out, report)
