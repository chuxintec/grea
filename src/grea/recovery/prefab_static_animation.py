"""Source-bound, disabled native Animation component specifications.

The records in this module describe real target assets supplied by the target
import pipeline. This module never creates placeholder clips or evaluates a
timeline. Unsupported curve semantics remain per-clip gaps while successfully
lowered channels can still be bound to a real native clip.
"""
from __future__ import annotations

import re
import hashlib
import json
from pathlib import Path


SCHEMA = "monkey-prefab-static-animation/1"
ASSET_PLAN_SCHEMA = "monkey-static-animation-asset-plan/1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def plan_source_asset_animation_clips(ir: dict, selection: list[str], profile: str,
                                      naming=None) -> dict:
    """Plan real native clips for source asset refs without cc.Animation owners.

    This emits genuine lowered curves from normalized AnimationClip IR while
    keeping source engine graph and runtime playback out of the target. Curves
    retain their source-relative hierarchy path; `assetOnly` tells the owning
    Editor importer not to require a prefab node map during asset construction.
    """
    selected = set(selection)
    clips = [row for row in ir.get("animationClips", [])
             if isinstance(row, dict) and row.get("sourceId") in selected]
    found = {row.get("sourceId") for row in clips}
    unknown = selected - found
    if unknown:
        raise ValueError("PREFAB_STATIC_ANIMATION_SOURCE_CLIP_UNKNOWN:" + ",".join(sorted(unknown)))
    unity_target = profile.startswith("unity-")
    if not unity_target and not profile.startswith(("creator-", "cocos-")):
        raise ValueError("PREFAB_STATIC_ANIMATION_TARGET_PROFILE_UNSUPPORTED:" + str(profile))
    out = []
    diagnostics = []
    for clip in clips:
        tracks = []
        by_channel = {}
        for track in clip.get("tracks", []):
            prop = track.get("property")
            path = track.get("nodePath", "")
            if not isinstance(prop, str) or not isinstance(path, str):
                diagnostics.append({"code": "PREFAB_STATIC_ANIMATION_ASSET_TRACK_INVALID",
                                    "sourceClipId": clip["sourceId"], "sourceLocation": track.get("sourceLocation")})
                continue
            key = (path, prop)
            by_channel[key] = by_channel.get(key, 0) + 1
            value_scale = 1 / 255 if unity_target and prop == "opacity" else 1
            if unity_target:
                native_type = "CanvasGroup" if prop == "opacity" else "RectTransform" if prop.startswith("position.") else "Transform"
                native_property = {
                    "position.x": "m_AnchoredPosition.x",
                    "position.y": "m_AnchoredPosition.y",
                    "position.z": "m_LocalPosition.z",
                    "opacity": "m_Alpha",
                }.get(prop, "m_LocalScale." + prop[-1])
            else:
                native_type = "UIOpacity" if prop == "opacity" else "Node"
                native_property = prop
            keys = [{**keyframe, "value": keyframe["value"] * value_scale}
                    for keyframe in track.get("keys", []) if isinstance(keyframe, dict)]
            if not keys:
                diagnostics.append({"code": "PREFAB_STATIC_ANIMATION_ASSET_TRACK_EMPTY",
                                    "sourceClipId": clip["sourceId"], "sourceLocation": track.get("sourceLocation")})
                continue
            probes_at = sorted(set([keyframe["time"] for keyframe in keys]
                                   + [(left["time"] + right["time"]) / 2 for left, right in zip(keys, keys[1:])]))
            from .assets.animation import sample
            tracks.append({
                **track,
                "node": None,
                "path": path,
                "nativeType": native_type,
                "nativeProperty": native_property,
                "valueScale": value_scale,
                "keys": keys,
                "probes": [{"time": time, "value": sample(keys, time)} for time in probes_at],
            })
        collisions = [key for key, count in by_channel.items() if count > 1]
        if collisions:
            diagnostics.append({"code": "PREFAB_STATIC_ANIMATION_ASSET_CHANNEL_COLLISION",
                                "sourceClipId": clip["sourceId"], "channels": [list(key) for key in collisions]})
            tracks = [track for track in tracks if by_channel[(track["path"], track["property"])] == 1]
        source_id = clip["sourceId"]
        out.append({
            "id": source_id + "@source-asset",
            "sourceClipId": source_id,
            "name": clip.get("name", "Animation"),
            "duration": clip.get("duration", 0),
            "sample": clip.get("sample", 60),
            "wrap": clip.get("wrap", "normal"),
            "tracks": tracks,
            "convertible": bool(tracks) and clip.get("timingSupported") is True and not collisions,
            "partial": clip.get("partial") is True or len(tracks) != len(clip.get("tracks", [])) or bool(collisions),
            "events": list(clip.get("events", [])),
            "path": None,
            "autoPlay": False,
            "assetOnly": True,
            "root": None,
            "owner": "source-asset",
        })
    if naming is None:
        from .layout import LayoutPlanner
        naming = LayoutPlanner("unity" if unity_target else "creator", ir.get("sourceNames"))
    requests = []
    for spec in out:
        source_id = spec["sourceClipId"]
        metadata = dict(ir.get("sourceNames", {}).get(source_id, {}))
        metadata["sourceId"] = source_id
        metadata.setdefault("sourceName", spec["name"])
        requests.append((spec["id"], "animation", ".anim", "", metadata, "SourceAsset"))
    naming.reserve(requests)
    for spec in out:
        metadata = dict(ir.get("sourceNames", {}).get(spec["sourceClipId"], {}))
        metadata["sourceId"] = spec["sourceClipId"]
        metadata.setdefault("sourceName", spec["name"])
        base_path=Path(naming.path(spec["id"], "animation", ".anim", metadata=metadata))
        root="Assets/Game/Content" if unity_target else "assets/resources"
        spec["path"]=root+"/Animations/StaticReferences/"+base_path.stem+"_"+hashlib.sha256(spec["sourceClipId"].encode()).hexdigest()[:16]+".anim"
    return {"schema": ASSET_PLAN_SCHEMA, "status": "planned" if out and not diagnostics else "partial" if out or diagnostics else "not_run",
            "clips": out, "diagnostics": diagnostics, "nativePlaybackEnabled": False}


def _clip_asset_index(source_manifest: dict | None) -> dict:
    result = {}
    if not isinstance(source_manifest, dict):
        return result
    for asset in source_manifest.get("assets", []):
        if not isinstance(asset, dict) or asset.get("kind") != "cc.AnimationClip":
            continue
        sid = asset.get("sourceId")
        if not isinstance(sid, str) or not sid:
            continue
        # Keep identity/provenance only. The source document itself is never
        # copied into a target project or treated as a native AnimationClip.
        result.setdefault(sid, []).append({
            "sourceAssetId": sid,
            "sourceBundle": asset.get("bundle"),
            "sourceKey": asset.get("key"),
            "sourceImportPath": asset.get("importPath"),
            "sourceLogicalPath": asset.get("logicalPath"),
            "sourceIndex": asset.get("index"),
            "sourceNativePath": asset.get("native"),
            "sourceDocument": asset.get("document"),
        })
    return result


def prepare_static_animation_assets(plan: dict, source_manifest: dict,
                                    output_root: str | Path,
                                    native_assets: dict | None = None) -> dict:
    """Prepare immutable per-clip source-evidence JsonAssets for native binding.

    Files are a deterministic extraction of the exact cc.AnimationClip object
    stored in the frozen source manifest. They are evidence/provenance assets,
    never parsed as target animation data and never reported as curve recovery.
    The caller imports these files and supplies their real native object identity
    (GUID/path/hash) to :func:`build_prefab_static_animation_bindings`.
    """
    root = Path(output_root)
    manifest_path = plan.get("sourceManifestPath")
    if not isinstance(manifest_path, str) or not manifest_path:
        raise ValueError("PREFAB_STATIC_ANIMATION_SOURCE_MANIFEST_PATH_MISSING")
    manifest_sha = plan.get("sourceManifestSha256")
    if not isinstance(manifest_sha, str) or not _SHA256.fullmatch(manifest_sha):
        raise ValueError("PREFAB_STATIC_ANIMATION_SOURCE_MANIFEST_HASH_MISSING")
    assets = _clip_asset_index(source_manifest)
    usages: dict[str, list[dict]] = {}
    for component in plan.get("components", []):
        if not isinstance(component, dict):
            continue
        if component.get("type") == "cc.Animation":
            component_id = component.get("sourceId")
            for order, clip_id in enumerate(component.get("clips", [])):
                if isinstance(clip_id, str):
                    usages.setdefault(clip_id, []).append({"kind": "component_clip", "sourceComponentId": component_id, "order": order})
            default_id = component.get("defaultClip")
            if isinstance(default_id, str):
                usages.setdefault(default_id, []).append({"kind": "component_default_clip", "sourceComponentId": component_id})
        static_fields = component.get("staticFieldBinding", {}).get("fields", [])
        for field in static_fields if isinstance(static_fields, list) else []:
            if not isinstance(field, dict) or field.get("sourceDeclaredType") != "cc.AnimationClip":
                continue
            references = []
            if isinstance(field.get("refValue"), str) and field["refValue"]:
                references.append(field["refValue"])
            references.extend(value for value in field.get("refValues", []) if isinstance(value, str) and value)
            for reference in references:
                usages.setdefault(reference, []).append({
                    "kind": "static_field_asset_ref",
                    "sourceComponentId": component.get("sourceId"),
                    "fieldName": field.get("name"),
                })
    referenced = sorted(usages)
    prepared = []
    diagnostics = []
    for source_id in referenced:
        rows = assets.get(source_id, [])
        if len(rows) != 1 or not isinstance(rows[0].get("sourceDocument"), dict):
            diagnostics.append({"code": "PREFAB_STATIC_ANIMATION_SOURCE_DOCUMENT_UNAVAILABLE", "sourceClipId": source_id})
            continue
        document = rows[0]["sourceDocument"]
        instances = document.get("instances")
        root_index = document.get("root")
        if (not isinstance(instances, list) or type(root_index) is not int
                or root_index < 0 or root_index >= len(instances)
                or not isinstance(instances[root_index], dict)
                or instances[root_index].get("__type__") != "cc.AnimationClip"):
            diagnostics.append({"code": "PREFAB_STATIC_ANIMATION_SOURCE_OBJECT_INVALID", "sourceClipId": source_id})
            continue
        source_object = instances[root_index]
        data = (json.dumps(source_object, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        source_document_sha=hashlib.sha256(data).hexdigest()
        if plan.get("targetProfile", "").startswith(("cocos-", "creator-")):
            # Creator's JsonAsset importer strips reserved __type__/__uuid__
            # keys recursively. Keep original source documents opaque, so the
            # native data asset cannot reinterpret or discard source identity.
            envelope={"schema":"monkey-source-animation-evidence/1","sourceClipId":source_id,
                "sourceDocumentSha256":source_document_sha,"sourceDocumentJson":data.decode("utf-8")}
            data=(json.dumps(envelope,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode("utf-8")
        content_sha = hashlib.sha256(data).hexdigest()
        key = hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:24]
        profile = str(plan.get("targetProfile", "unity"))
        evidence_root = "Assets/Game/Content/SourceEvidence/Animations" if profile.startswith("unity-") else "assets/resources/SourceEvidence/Animations"
        relative_path = Path(evidence_root) / f"{key}.json"
        destination = root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() != content_sha:
            raise ValueError("PREFAB_STATIC_ANIMATION_EVIDENCE_ASSET_COLLISION:" + source_id)
        if not destination.exists():
            destination.write_bytes(data)
        prepared.append({
            "sourceClipId": source_id,
            "sourceBundle": rows[0].get("sourceBundle"),
            "sourceKey": rows[0].get("sourceKey"),
            "sourceIndex": rows[0].get("sourceIndex"),
            "sourceImportPath": rows[0].get("sourceImportPath"),
            "sourceLogicalPath": rows[0].get("sourceLogicalPath"),
            "sourceNativePath": rows[0].get("sourceNativePath"),
            "sourceEvidenceStagePath": rows[0].get("sourceImportPath"),
            "sourceManifestPath": manifest_path,
            "sourceManifestSha256": manifest_sha,
            "sourceDocumentSha256": source_document_sha,
            "path": relative_path.as_posix(),
            "guid": None,
            "nativeAssetSha256": content_sha,
            "nativeAssetType": "TextAsset",
            "nativeType": "TextAsset",
            "status": "prepared_source_evidence_not_imported",
            "runtimeCurveData": False,
            "usages": usages[source_id],
        })
    return {
        "schema": "monkey-prefab-static-animation-evidence/1",
        "status": "prepared" if prepared and not diagnostics else "partial" if prepared or diagnostics else "not_run",
        "assets": prepared,
        "diagnostics": diagnostics,
        "sourceManifestPath": manifest_path,
        "sourceManifestSha256": manifest_sha,
        "sourceClipUsages": usages,
        "sourceClipNativeAssets": resolve_source_clip_native_assets(plan.get("animations", []), native_assets or {}),
        "runtimeCurveData": False,
    }


def _canonical_curve_signature(animation: dict) -> str:
    """Stable signature for deciding whether component-bound plans are reusable."""
    tracks = []
    for track in animation.get("tracks", []):
        if not isinstance(track, dict):
            continue
        tracks.append({
            "path": track.get("path"),
            "property": track.get("nativeProperty", track.get("property")),
            "nativeType": track.get("nativeType"),
            "keys": [{"time": key.get("time"), "value": key.get("value"),
                      "interpolation": key.get("interpolation")}
                     for key in track.get("keys", []) if isinstance(key, dict)],
        })
    body = {"duration": animation.get("duration"), "wrap": animation.get("wrap"), "tracks": tracks}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def resolve_source_clip_native_assets(animations: list, native_assets: dict) -> dict:
    """Resolve source-ID-level refs only when every candidate is equivalent.

    A single candidate is preferred. Multiple component-bound plans may be
    reused only when their lowered curve signatures and their verified native
    asset identity are equivalent. Otherwise the source ID remains explicitly
    ambiguous; dictionary iteration order never selects a winner.
    """
    groups: dict[str, list[dict]] = {}
    for animation in animations if isinstance(animations, list) else []:
        if not isinstance(animation, dict) or not isinstance(animation.get("id"), str):
            continue
        source_id = animation["id"].split("@", 1)[0]
        if source_id in native_assets:
            evidence = _native_asset_binding(native_assets[source_id], "AnimationClip")
            if evidence["status"] == "native_asset_reference_resolved":
                groups.setdefault(source_id, []).append({
                    "animation": animation,
                    "asset": evidence["nativeAsset"],
                    "signature": _canonical_curve_signature(animation),
                })
        plan_id = animation["id"]
        if plan_id in native_assets:
            evidence = _native_asset_binding(native_assets[plan_id], "AnimationClip")
            if evidence["status"] == "native_asset_reference_resolved":
                groups.setdefault(source_id, []).append({
                    "animation": animation,
                    "asset": evidence["nativeAsset"],
                    "signature": _canonical_curve_signature(animation),
                })
    result = {}
    for source_id, candidates in groups.items():
        by_plan = {row["animation"]["id"]: row for row in candidates}
        candidates = list(by_plan.values())
        signatures = {row["signature"] for row in candidates}
        if len(candidates) == 1:
            chosen = candidates[0]
            result[source_id] = {**chosen["asset"], "resolution": "single_native_animation_plan",
                                 "planAnimationId": chosen["animation"]["id"]}
        elif len(signatures) == 1:
            chosen = min(candidates, key=lambda row: (row["asset"]["path"], row["animation"]["id"]))
            result[source_id] = {**chosen["asset"], "resolution": "canonical_curve_equivalence",
                                 "planAnimationId": chosen["animation"]["id"],
                                 "equivalentPlanAnimationIds": sorted(row["animation"]["id"] for row in candidates),
                                 "canonicalCurveSha256": next(iter(signatures))}
        else:
            result[source_id] = {"status": "source_clip_native_plan_ambiguous",
                                 "candidatePlanAnimationIds": sorted(row["animation"]["id"] for row in candidates),
                                 "canonicalCurveSha256s": sorted(signatures)}
    return result


def _native_asset_binding(evidence: dict | None, expected_type: str) -> dict:
    """Validate explicit importer evidence; never infer an object reference."""
    if not isinstance(evidence, dict):
        return {"status": "native_asset_evidence_missing", "nativeAsset": None}
    required = ("path", "guid", "assetSha256", "nativeType")
    if any(not isinstance(evidence.get(key), str) or not evidence[key] for key in required):
        return {"status": "native_asset_evidence_incomplete", "nativeAsset": None}
    if not _SHA256.fullmatch(evidence["assetSha256"]):
        return {"status": "native_asset_hash_invalid", "nativeAsset": None}
    if evidence["nativeType"] != expected_type:
        return {"status": "native_asset_type_mismatch", "nativeAsset": None}
    guid = evidence["guid"].lower()
    if not re.fullmatch(r"(?:[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", guid):
        return {"status": "native_asset_guid_invalid", "nativeAsset": None}
    path = evidence["path"]
    if not (path.startswith("Assets/") or path.startswith("assets/")) or path.startswith("/") or ".." in path.split("/"):
        return {"status": "native_asset_path_invalid", "nativeAsset": None}
    if "metaSha256" in evidence and evidence["metaSha256"] is not None and not _SHA256.fullmatch(str(evidence["metaSha256"])):
        return {"status": "native_asset_meta_hash_invalid", "nativeAsset": None}
    native = {"path": path, "guid": guid, "assetSha256": evidence["assetSha256"], "nativeType": expected_type}
    for key in ("metaSha256", "localFileId", "contentReadbackStatus"):
        if key in evidence:
            native[key] = evidence[key]
    return {"status": "native_asset_reference_resolved", "nativeAsset": native}


def _source_asset_public(source_asset: dict | None) -> dict | None:
    if not isinstance(source_asset, dict):
        return None
    return {key: value for key, value in source_asset.items() if key != "sourceDocument"}


def build_prefab_static_animation_bindings(ir: dict, animations: list,
                                           source_manifest: dict | None = None,
                                           native_assets: dict | None = None,
                                           source_evidence_assets: dict | None = None,
                                           target_node_ids: dict | None = None,
                                           target_component_ids: dict | None = None,
                                           sync_prefab_bindings: list | None = None) -> dict:
    """Build source ordered component/clip bindings from normalized IR.

    `native_assets` is keyed by the exact animation plan ID
    ``sourceClipId@sourceComponentId`` and contains importer-verified target
    object identity. `target_*_ids` must be supplied by the prefab sync origin
    map when binding a cloned target hierarchy; names and UUID fragments are
    intentionally not used as fallbacks.
    """
    native_assets = native_assets or {}
    source_evidence_assets = source_evidence_assets or {}
    node_map = target_node_ids or {}
    component_map = target_component_ids or {}
    source_assets = _clip_asset_index(source_manifest)
    source_clip_native_assets = resolve_source_clip_native_assets(animations, native_assets)
    source_field_references = []
    for component in ir.get("components", []):
        if not isinstance(component, dict):
            continue
        binding = component.get("staticFieldBinding") or {}
        for field in binding.get("fields", []) if isinstance(binding.get("fields", []), list) else []:
            if not isinstance(field, dict) or field.get("sourceDeclaredType") != "cc.AnimationClip":
                continue
            references = []
            if isinstance(field.get("refValue"), str) and field["refValue"]:
                references.append((0, field["refValue"]))
            references.extend((index, value) for index, value in enumerate(field.get("refValues", []))
                              if isinstance(value, str) and value)
            for index, source_id in references:
                direct_evidence = native_assets.get(source_id)
                if not isinstance(direct_evidence, dict):
                    resolved_by_source = source_clip_native_assets.get(source_id)
                    if isinstance(resolved_by_source, dict) and resolved_by_source.get("status") != "source_clip_native_plan_ambiguous":
                        direct_evidence = resolved_by_source
                direct = _native_asset_binding(direct_evidence, "AnimationClip")
                evidence = _native_asset_binding(source_evidence_assets.get(source_id), "TextAsset")
                source_field_references.append({
                    "sourceComponentId": component.get("sourceId"),
                    "fieldName": field.get("name"),
                    "sourceDeclaredType": field.get("sourceDeclaredType"),
                    "elementIndex": index,
                    "sourceAssetId": source_id,
                    "sourceAssetIdentityStatus": "verified_source_asset_identity" if len(source_assets.get(source_id, [])) == 1 else
                                                "source_asset_identity_missing_or_ambiguous",
                    "nativeAsset": direct["nativeAsset"],
                    "sourceEvidenceAsset": evidence["nativeAsset"],
                    "representation": "native_animation_clip" if direct["nativeAsset"] else
                                     "source_evidence_asset_only" if evidence["nativeAsset"] else "unresolved",
                    "status": "resolved_native_asset" if direct["nativeAsset"] else
                             "retained_source_evidence_type_limited" if evidence["nativeAsset"] else "partial",
                })
    clips_by_id: dict[str, list[dict]] = {}
    for clip in animations if isinstance(animations, list) else []:
        if isinstance(clip, dict) and isinstance(clip.get("id"), str):
            clips_by_id.setdefault(clip["id"], []).append(clip)

    components = [row for row in ir.get("components", [])
                  if isinstance(row, dict) and row.get("type") == "cc.Animation"]
    component_ids = [row.get("sourceId") for row in components]
    duplicate_ids = {sid for sid in component_ids if component_ids.count(sid) > 1}
    bindings = []
    diagnostics = []
    for component in components:
        component_id = component.get("sourceId")
        source_node_id = component.get("node")
        if not isinstance(component_id, str) or not component_id or not isinstance(source_node_id, str):
            diagnostics.append({"code": "PREFAB_STATIC_ANIMATION_COMPONENT_ID_INVALID", "sourceComponentId": component_id})
            continue
        if component_id in duplicate_ids:
            diagnostics.append({"code": "PREFAB_STATIC_ANIMATION_COMPONENT_ID_AMBIGUOUS", "sourceComponentId": component_id})
            continue
        target_pairs = []
        for sync in sync_prefab_bindings or []:
            if not isinstance(sync, dict):
                continue
            node_matches = [row.get("instanceSourceId") for row in sync.get("origins", [])
                            if isinstance(row, dict) and row.get("templateSourceId") == source_node_id
                            and isinstance(row.get("instanceSourceId"), str)]
            for origin in sync.get("componentOrigins", []):
                if isinstance(origin, dict) and origin.get("templateSourceId") == component_id and isinstance(origin.get("instanceSourceId"), str):
                    target_pairs.append((origin["instanceSourceId"], node_matches[0] if len(node_matches) == 1 else None))
        if component_id in component_map:
            target_pairs.append((component_map[component_id], node_map.get(source_node_id)))
        if not target_pairs:
            target_pairs = [(None, node_map.get(source_node_id))]
        # Keep one spec per exact origin row. Repeated identical mappings in a
        # plan are deduplicated but ambiguous source-template clones are retained.
        target_pairs = list(dict.fromkeys(target_pairs))
        clip_ids = component.get("clips")
        if not isinstance(clip_ids, list) or any(not isinstance(sid, str) or not sid for sid in clip_ids):
            diagnostics.append({"code": "PREFAB_STATIC_ANIMATION_CLIP_ORDER_INVALID", "sourceComponentId": component_id})
            clip_ids = [sid for sid in clip_ids if isinstance(sid, str) and sid] if isinstance(clip_ids, list) else []

        slots = []
        for order, clip_id in enumerate(clip_ids):
            plan_id = clip_id + "@" + component_id
            candidates = clips_by_id.get(plan_id, [])
            source_rows = source_assets.get(clip_id, [])
            slot = {
                "order": order,
                "sourceClipId": clip_id,
                "planAnimationId": plan_id,
                "sourceAsset": _source_asset_public(source_rows[0]) if len(source_rows) == 1 else None,
                "sourceAssetIdentityStatus": (
                    "verified_source_asset_identity" if len(source_rows) == 1 else
                    "source_asset_identity_missing" if not source_rows else "source_asset_identity_ambiguous"
                ),
                "nativeAsset": None,
                "sourceEvidenceAsset": None,
                "nativeReferenceStatus": "animation_plan_missing",
                "curveStatus": "unknown",
                "partial": True,
                "gaps": [],
            }
            if len(candidates) == 1:
                clip = candidates[0]
                slot["curveStatus"] = "converted_curves" if clip.get("convertible") is True else "partial_curves"
                slot["name"] = clip.get("name")
                slot["partial"] = clip.get("partial") is True or clip.get("convertible") is not True
                slot["gaps"] = list(clip.get("gaps", [])) if isinstance(clip.get("gaps"), list) else []
                resolved = _native_asset_binding(native_assets.get(plan_id), "AnimationClip")
                slot["nativeReferenceStatus"] = resolved["status"]
                slot["nativeAsset"] = resolved["nativeAsset"]
            elif len(candidates) > 1:
                slot["nativeReferenceStatus"] = "animation_plan_ambiguous"
            if slot["nativeAsset"] is None:
                source_evidence = source_evidence_assets.get(clip_id)
                if isinstance(source_evidence, dict):
                    resolved_evidence = _native_asset_binding(source_evidence, "TextAsset")
                    slot["sourceEvidenceAsset"] = resolved_evidence["nativeAsset"]
                    slot["sourceEvidenceReferenceStatus"] = resolved_evidence["status"]
                else:
                    slot["sourceEvidenceReferenceStatus"] = "source_evidence_asset_missing"
                slot["bindingObjectType"] = "TextAsset" if slot["sourceEvidenceAsset"] is not None else None
            else:
                source_evidence = source_evidence_assets.get(clip_id)
                if isinstance(source_evidence, dict):
                    resolved_evidence = _native_asset_binding(source_evidence, "TextAsset")
                    slot["sourceEvidenceAsset"] = resolved_evidence["nativeAsset"]
                    slot["sourceEvidenceReferenceStatus"] = resolved_evidence["status"]
                else:
                    slot["sourceEvidenceReferenceStatus"] = "not_required_native_clip_bound"
                slot["bindingObjectType"] = "AnimationClip"
            if slot["sourceAssetIdentityStatus"] != "verified_source_asset_identity":
                diagnostics.append({"code": "PREFAB_STATIC_ANIMATION_SOURCE_ASSET_IDENTITY_GAP",
                                    "sourceComponentId": component_id, "sourceClipId": clip_id,
                                    "status": slot["sourceAssetIdentityStatus"]})
            if slot["bindingObjectType"] is None:
                diagnostics.append({"code": "PREFAB_STATIC_ANIMATION_NATIVE_REFERENCE_GAP",
                                    "sourceComponentId": component_id, "sourceClipId": clip_id,
                                    "status": slot["nativeReferenceStatus"],
                                    "sourceEvidenceStatus": slot["sourceEvidenceReferenceStatus"]})
            slots.append(slot)

        default_id = component.get("defaultClip")
        enabled = component.get("enabled") if type(component.get("enabled")) is bool else None
        play_on_load = component.get("playOnLoad") if type(component.get("playOnLoad")) is bool else None
        default_slot = next((row for row in slots if row["sourceClipId"] == default_id), None) if isinstance(default_id, str) else None
        default_status = (
            "no_source_default" if default_id is None else
            "native_default_reference_resolved" if default_slot and default_slot["nativeReferenceStatus"] == "native_asset_reference_resolved" else
            "source_default_reference_retained" if default_slot and default_slot["sourceEvidenceAsset"] is not None else
            "source_default_clip_not_in_order" if default_slot is None else "source_default_reference_unresolved"
        )
        fields_known = enabled is not None and play_on_load is not None
        refs_complete = all(row["nativeReferenceStatus"] == "native_asset_reference_resolved"
                            or row["sourceEvidenceAsset"] is not None for row in slots)
        status = "verified_static_references" if fields_known and refs_complete and default_status in (
            "no_source_default", "native_default_reference_resolved", "source_default_reference_retained") else "partial"
        binding = {
            "sourceComponentId": component_id,
            "targetComponentId": None,
            "sourceNodeId": source_node_id,
            "targetNodeId": None,
            "sourceEnabled": enabled,
            "sourcePlayOnLoad": play_on_load,
            "sourceDefaultClipId": default_id,
            "sourceDefaultClipKnown": "defaultClip" in component,
            "sourceClipOrder": list(clip_ids),
            "clips": slots,
            "nativeComponentType": "cc.Animation",
            "nativeComponentMustBeDisabled": True,
            "playbackExecuted": False,
            "curveCompleteness": "complete" if all(not row["partial"] for row in slots) else "partial",
            "nativePlaybackEnabled": False,
            "staticReferenceStatus": status,
        }
        for target_component_id, exact_target_node_id in target_pairs:
            bindings.append({**binding, "targetComponentId": target_component_id,
                             "targetNodeId": exact_target_node_id})
    return {
        "schema": SCHEMA,
        "status": "verified_static_references" if bindings and not diagnostics else "partial" if bindings or diagnostics else "not_run",
        "bindings": bindings,
        "sourceClipFieldReferences": source_field_references,
        "sourceClipNativeAssets": source_clip_native_assets,
        "diagnostics": diagnostics,
        "playbackExecuted": False,
        "placeholderClipsCreated": False,
    }


def to_native_static_animation_specs(binding_result: dict) -> dict:
    """Flatten verified per-slot objects into the Editor adapter DTO."""
    specs = []
    for binding in binding_result.get("bindings", []):
        clips = []
        for slot in binding.get("clips", []):
            native = slot.get("nativeAsset") or {}
            evidence = slot.get("sourceEvidenceAsset") or {}
            clips.append({
                "order": slot.get("order"),
                "sourceClipId": slot.get("sourceClipId"),
                "planAnimationId": slot.get("planAnimationId"),
                "status": "native_clip_reference_resolved" if native else slot.get("nativeReferenceStatus"),
                "nativeClipPath": native.get("path"),
                "nativeClipGuid": native.get("guid"),
                "assetSha256": native.get("assetSha256"),
                "metaSha256": native.get("metaSha256"),
                "nativeName": native.get("nativeName") or slot.get("name"),
                "nativeNameMatchesPlan": bool(native) and (not native.get("nativeName") or native.get("nativeName") == slot.get("name")),
                "convertible": slot.get("curveStatus") == "converted_curves",
                "nativeClipReadbackStatus": "not_run",
                "nativeClipContentStatus": native.get("contentReadbackStatus", "not_run"),
                "sourceEvidencePath": evidence.get("path"),
                "sourceEvidenceGuid": evidence.get("guid"),
                "sourceEvidenceSha256": evidence.get("assetSha256"),
                "sourceEvidenceType": evidence.get("nativeType"),
                "bindingObjectType": slot.get("bindingObjectType"),
                "curveStatus": slot.get("curveStatus"),
                "partial": slot.get("partial", True),
                "gaps": slot.get("gaps", []),
            })
        specs.append({
            "schema": "monkey-static-animation-bindings/1",
            "sourceComponentId": binding.get("sourceComponentId"),
            "targetComponentId": binding.get("targetComponentId"),
            "sourceNodeId": binding.get("sourceNodeId"),
            "targetNodeId": binding.get("targetNodeId"),
            "sourceEnabled": binding.get("sourceEnabled") is True,
            "sourceEnabledKnown": binding.get("sourceEnabledKnown") is True,
            "sourcePlayOnLoad": binding.get("sourcePlayOnLoad") is True,
            "sourcePlayOnLoadKnown": binding.get("sourcePlayOnLoadKnown") is True,
            "sourceDefaultClipId": binding.get("sourceDefaultClipId"),
            "sourceDefaultClipKnown": binding.get("sourceDefaultClipKnown") is True,
            "hasSourceDefaultClip": isinstance(binding.get("sourceDefaultClipId"), str),
            "defaultClipReferenceStatus": "resolved" if binding.get("sourceDefaultClipId")
                                          and any(row.get("sourceClipId") == binding.get("sourceDefaultClipId")
                                                  and row.get("nativeAsset") for row in binding.get("clips", []))
                                          else "source_default_reference_retained" if binding.get("sourceDefaultClipId")
                                          else "no_source_default",
            "sourceClipOrder": binding.get("sourceClipOrder", []),
            "clips": clips,
            "nativePlaybackEnabled": False,
            "nativeAnimatorEnabled": False,
            "curveCompleteness": binding.get("curveCompleteness", "partial"),
            "status": "resolved" if binding.get("staticReferenceStatus") == "verified_static_references" else "partial",
        })
    return {"schema": "monkey-static-animation-bindings/1", "bindings": specs,
            "playbackExecuted": False, "placeholderClipsCreated": False}


def verify_prefab_static_animation_readback(expected_bindings: dict,
                                             actual_bindings: list,
                                             expected_field_references: list | None = None,
                                             actual_field_references: list | None = None) -> dict:
    """Strictly verify static clip/resource identity while keeping curve gaps separate."""
    failures = []
    expected_rows = expected_bindings.get("bindings", []) if isinstance(expected_bindings, dict) else []
    actual_rows = actual_bindings if isinstance(actual_bindings, list) else []
    def key(row):
        return (row.get("sourceComponentId"), row.get("targetComponentId") or row.get("targetNodeId"))
    expected_by_key = {key(row): row for row in expected_rows if isinstance(row, dict)}
    actual_by_key = {key(row): row for row in actual_rows if isinstance(row, dict)}
    if len(expected_by_key) != len(expected_rows):
        failures.append("expected_component_binding_identity_duplicate_or_missing")
    if len(actual_by_key) != len(actual_rows):
        failures.append("actual_component_binding_identity_duplicate_or_missing")
    if set(expected_by_key) != set(actual_by_key):
        failures.append("component_binding_identity_set_mismatch")
    dynamic_gaps = []
    for identity, expected in expected_by_key.items():
        actual = actual_by_key.get(identity)
        if actual is None:
            continue
        saved = actual.get("binding") if isinstance(actual.get("binding"), dict) else actual
        if actual.get("playbackExecuted") is True or saved.get("playbackExecuted") is True:
            failures.append(f"{identity}:playback_was_executed")
        expected_ids = expected.get("sourceClipOrder", [])
        actual_ids = saved.get("sourceClipOrder")
        if actual_ids is None:
            actual_ids = [row.get("sourceClipId") for row in saved.get("clips", []) if isinstance(row, dict)]
        if expected_ids != actual_ids:
            failures.append(f"{identity}:source_clip_order_mismatch")
        exp_slots = expected.get("clips", [])
        act_slots = saved.get("clips", [])
        if len(exp_slots) != len(act_slots):
            failures.append(f"{identity}:clip_slot_count_mismatch")
        for index, exp in enumerate(exp_slots):
            if index >= len(act_slots):
                break
            act = act_slots[index]
            if act.get("sourceClipId") != exp.get("sourceClipId") or act.get("order", index) != exp.get("order", index):
                failures.append(f"{identity}:clip_slot_identity_mismatch:{index}")
                continue
            object_type = exp.get("bindingObjectType")
            if object_type not in ("AnimationClip", "TextAsset"):
                failures.append(f"{identity}:clip_slot_has_no_expected_asset_object:{index}")
            if act.get("referenceMatches") is False:
                failures.append(f"{identity}:native_asset_reference_mismatch:{index}")
            if object_type == "AnimationClip" and act.get("bindingObjectType") not in (None, "AnimationClip"):
                failures.append(f"{identity}:native_animation_clip_type_mismatch:{index}")
            if object_type == "TextAsset" and act.get("bindingObjectType") not in (None, "TextAsset"):
                failures.append(f"{identity}:source_evidence_object_type_mismatch:{index}")
            if exp.get("partial") is True:
                dynamic_gaps.append({"sourceComponentId": identity[0], "sourceClipId": exp.get("sourceClipId"),
                                     "curveStatus": exp.get("curveStatus"), "gaps": exp.get("gaps", [])})
        status = actual.get("staticReferenceStatus", saved.get("status"))
        if status in ("mismatch", "failed", "partial") and expected.get("staticReferenceStatus") == "verified_static_references":
            failures.append(f"{identity}:static_reference_readback_not_verified")
    expected_fields = expected_field_references or []
    actual_fields = actual_field_references or []
    actual_field_map = {}
    for row in actual_fields:
        if not isinstance(row, dict):
            continue
        actual_field_map.setdefault((row.get("sourceComponentId"), row.get("fieldName"), row.get("sourceClipId")), []).append(row)
    for row in expected_fields:
        if not isinstance(row, dict):
            continue
        identity = (row.get("sourceComponentId"), row.get("fieldName"), row.get("sourceAssetId"))
        matches = actual_field_map.get(identity, [])
        if len(matches) != 1 or matches[0].get("status") not in ("resolved_native_animation_clip", "reference_fields_verified"):
            failures.append(f"static_animation_field_reference_unresolved:{identity}")
        elif matches[0].get("objectType") not in (None, "AnimationClip"):
            failures.append(f"static_animation_field_reference_type_mismatch:{identity}")
    return {
        "status": "verified_static_references" if not failures else "mismatch",
        "staticReferenceFailures": failures,
        "dynamicCurveGaps": dynamic_gaps,
        "playbackExecuted": False,
        "staticReferenceCount": sum(len(row.get("clips", [])) for row in expected_rows if isinstance(row, dict)),
        "staticFieldReferenceCount": len(expected_fields),
    }
