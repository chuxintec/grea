"""Static presentation bindings for existing native animation assets.

This module preserves source Animation component state and exact native clip
asset references. It does not create/rewrite clips or advance animation time.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from ..io import write_json


SCHEMA = "monkey-static-animation-bindings/1"
_GUID = re.compile(r"(?m)^guid:\s*([0-9a-fA-F]{32})\s*$")
_CLIP_HEADER = re.compile(r"(?m)^--- !u!74 &\d+\s*$")
_CLIP_NAME = re.compile(r"(?m)^  m_Name:\s*(.*?)\s*$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _native_clip_asset(project_root: Path, animation: dict) -> dict:
    path_value = animation.get("path")
    if not isinstance(path_value, str) or not path_value.startswith("Assets/") or ".." in Path(path_value).parts:
        return {"status": "invalid_target_path", "path": path_value}
    if animation.get("convertible") is not True:
        return {"status": "source_animation_not_convertible", "path": path_value}
    relative = Path(path_value)
    asset_path = project_root / relative
    meta_path = Path(str(asset_path) + ".meta")
    try:
        asset_path.resolve().relative_to(project_root.resolve())
        meta_path.resolve().relative_to(project_root.resolve())
    except (OSError, ValueError):
        return {"status": "target_path_escapes_project", "path": path_value}
    if not asset_path.is_file():
        return {"status": "native_clip_asset_missing", "path": path_value}
    if not meta_path.is_file():
        return {"status": "native_clip_meta_missing", "path": path_value}
    try:
        meta = meta_path.read_text(encoding="utf-8")
        clip_text = asset_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return {"status": "native_clip_asset_unreadable", "path": path_value}
    guid_matches = _GUID.findall(meta)
    clip_names = _CLIP_NAME.findall(clip_text) if _CLIP_HEADER.search(clip_text) else []
    if len(guid_matches) != 1 or len(clip_names) != 1:
        return {"status": "native_clip_identity_mismatch", "path": path_value}
    return {
        "status": "native_clip_reference_resolved",
        "path": path_value,
        "guid": guid_matches[0].lower(),
        "assetSha256": _sha256(asset_path),
        "metaSha256": _sha256(meta_path),
        "nativeName": clip_names[0],
        "nativeNameMatchesPlan": clip_names[0] == animation.get("name"),
        "planAnimationId": animation.get("id"),
    }


def build_static_animation_bindings(plan: dict, project_root: str | Path,
                                    target_node_ids: dict | None = None,
                                    target_component_ids: dict | None = None,
                                    source_plan_sha256: str | None = None) -> dict:
    """Build disabled, source-ordered animation binding records from a native plan.

    `target_node_ids` and `target_component_ids` are explicit origin-map results
    supplied by the preview owner. They allow sync-prefab clones to resolve back
    to the frozen source component without guessing from names or UUID fragments.
    Native .anim paths are only referenced when the current asset and .meta GUID
    exist and the asset's native clip name matches its exact plan entry.
    """
    project = Path(project_root)
    node_map = target_node_ids or {}
    component_map = target_component_ids or {}
    components = [row for row in plan.get("components", [])
                  if isinstance(row, dict) and row.get("type") == "cc.Animation"]
    animations = [row for row in plan.get("animations", []) if isinstance(row, dict)]
    by_animation_id = {}
    for animation in animations:
        animation_id = animation.get("id")
        if isinstance(animation_id, str):
            by_animation_id.setdefault(animation_id, []).append(animation)

    bindings = []
    diagnostics = []
    if not isinstance(source_plan_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", source_plan_sha256):
        diagnostics.append({"code": "ANIMATION_BINDING_SOURCE_PLAN_HASH_MISSING"})
    component_ids = [row.get("sourceId") for row in components]
    duplicate_components = {sid for sid in component_ids if component_ids.count(sid) > 1}
    for component in components:
        source_component_id = component.get("sourceId")
        source_node_id = component.get("node")
        if not isinstance(source_component_id, str) or not isinstance(source_node_id, str):
            diagnostics.append({"code": "ANIMATION_BINDING_SOURCE_ID_MISSING", "sourceComponentId": source_component_id})
            continue
        if source_component_id in duplicate_components:
            diagnostics.append({"code": "ANIMATION_BINDING_SOURCE_COMPONENT_AMBIGUOUS", "sourceComponentId": source_component_id})
            continue
        clip_ids = component.get("clips")
        clip_order_valid = isinstance(clip_ids, list) and not any(
            not isinstance(clip_id, str) or not clip_id for clip_id in clip_ids
        )
        if not clip_order_valid:
            diagnostics.append({"code": "ANIMATION_BINDING_SOURCE_CLIP_ORDER_INVALID", "sourceComponentId": source_component_id})
            clip_ids = [clip_id for clip_id in clip_ids if isinstance(clip_id, str) and clip_id] if isinstance(clip_ids, list) else []

        clip_rows = []
        for index, source_clip_id in enumerate(clip_ids):
            plan_id = source_clip_id + "@" + source_component_id
            candidates = by_animation_id.get(plan_id, [])
            if len(candidates) != 1:
                clip_rows.append({
                    "order": index,
                    "sourceClipId": source_clip_id,
                    "planAnimationId": plan_id,
                    "status": "plan_animation_missing" if not candidates else "plan_animation_ambiguous",
                    "nativeClipPath": None,
                    "nativeClipGuid": None,
                })
                continue
            animation = candidates[0]
            asset = _native_clip_asset(project, animation)
            clip_rows.append({
                "order": index,
                "sourceClipId": source_clip_id,
                "planAnimationId": plan_id,
                "status": asset["status"],
                "nativeClipPath": asset.get("path") if asset.get("status") == "native_clip_reference_resolved" else None,
                "nativeClipGuid": asset.get("guid"),
                "assetSha256": asset.get("assetSha256"),
                "metaSha256": asset.get("metaSha256"),
                "nativeName": asset.get("nativeName"),
                "nativeNameMatchesPlan": asset.get("nativeNameMatchesPlan"),
                "convertible": animation.get("convertible") is True,
                "nativeClipReadbackStatus": "not_run",
                "nativeClipContentStatus": "not_run",
            })
            if asset["status"] != "native_clip_reference_resolved":
                diagnostics.append({"code": "ANIMATION_BINDING_CLIP_UNRESOLVED", "sourceComponentId": source_component_id,
                                    "sourceClipId": source_clip_id, "status": asset["status"]})
            else:
                diagnostics.append({"code": "ANIMATION_BINDING_NATIVE_CONTENT_READBACK_NOT_RUN",
                                    "sourceComponentId": source_component_id, "sourceClipId": source_clip_id,
                                    "planAnimationId": plan_id})
                if not asset.get("nativeNameMatchesPlan"):
                    diagnostics.append({"code": "ANIMATION_BINDING_NATIVE_NAME_DIFFERS_FROM_PLAN",
                                        "sourceComponentId": source_component_id, "sourceClipId": source_clip_id,
                                        "planName": animation.get("name"), "nativeName": asset.get("nativeName")})

        default_clip = component.get("defaultClip")
        default_slot = next((row for row in clip_rows if row["sourceClipId"] == default_clip), None) if default_clip else None
        source_enabled = component.get("enabled") if type(component.get("enabled")) is bool else None
        source_play_on_load = component.get("playOnLoad") if type(component.get("playOnLoad")) is bool else None
        unresolved = [row for row in clip_rows if row["status"] != "native_clip_reference_resolved"]
        fields_complete = source_enabled is not None and source_play_on_load is not None
        default_status = (
            "no_source_default" if default_clip is None else
            "resolved" if default_slot and default_slot["status"] == "native_clip_reference_resolved" else
            "unresolved_source_default" if default_slot else "default_clip_not_in_source_order"
        )
        if default_clip is not None and default_status != "resolved":
            diagnostics.append({"code": "ANIMATION_BINDING_DEFAULT_CLIP_UNRESOLVED",
                                "sourceComponentId": source_component_id, "sourceClipId": default_clip,
                                "status": default_status})
        status = "resolved" if fields_complete and clip_order_valid and not unresolved and default_status in ("no_source_default", "resolved") else "partial"
        bindings.append({
            "sourceComponentId": source_component_id,
            "targetComponentId": component_map.get(source_component_id, source_component_id),
            "sourceNodeId": source_node_id,
            "targetNodeId": node_map.get(source_node_id, source_node_id),
            "sourceEnabled": source_enabled if source_enabled is not None else False,
            "sourceEnabledKnown": source_enabled is not None,
            "sourcePlayOnLoad": source_play_on_load if source_play_on_load is not None else False,
            "sourcePlayOnLoadKnown": source_play_on_load is not None,
            "sourceDefaultClipId": default_clip if isinstance(default_clip, str) else None,
            "sourceDefaultClipKnown": "defaultClip" in component,
            "hasSourceDefaultClip": isinstance(default_clip, str),
            "defaultClipReferenceStatus": default_status,
            "sourceClipOrder": list(clip_ids),
            "clips": clip_rows,
            "nativePlaybackEnabled": False,
            "nativeAnimatorEnabled": False,
            "status": status,
        })

    return {
        "schema": SCHEMA,
        "status": "resolved" if bindings and not diagnostics else "partial" if bindings or diagnostics else "not_run",
        "sourcePlanSha256": source_plan_sha256,
        "bindings": bindings,
        "diagnostics": diagnostics,
        "playbackExecuted": False,
        "nativeClipsCreated": False,
    }


def emit_static_animation_bindings(plan: dict, project_root: str | Path, output_path: str | Path,
                                   target_node_ids: dict | None = None,
                                   target_component_ids: dict | None = None,
                                   source_plan_sha256: str | None = None) -> dict:
    """Write the detached binding instruction; the editor adapter owns attachment."""
    result = build_static_animation_bindings(plan, project_root, target_node_ids, target_component_ids,
                                             source_plan_sha256)
    write_json(Path(output_path), result)
    return result
