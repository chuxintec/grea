"""Prepare the existing native static carrier for source ``cc.Animation``.

This focused continuation deliberately does not set ``staticCompletion``. It
adds only source-bound clip evidence and the exact component-origin map needed
by the existing disabled native Animation binding. Curves already present in
the frozen plan are left intact, including their partial/incomplete status.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import uuid

from .prefab_static_animation import prepare_static_animation_assets


SCHEMA = "monkey-prefab-static-animation-continuation/1"


def _canonical_component_origins(plan: dict) -> list[dict]:
    """Flatten only explicit sync-prefab component origins; reject ambiguity."""
    direct: dict[str, str] = {}
    for relation in plan.get("syncPrefabBindings", []):
        if not isinstance(relation, dict):
            continue
        for row in relation.get("componentOrigins", []):
            if not isinstance(row, dict):
                continue
            instance, template = row.get("instanceSourceId"), row.get("templateSourceId")
            if not isinstance(instance, str) or not instance or not isinstance(template, str) or not template:
                raise ValueError("STATIC_ANIMATION_COMPONENT_ORIGIN_INVALID")
            previous = direct.get(instance)
            if previous is not None and previous != template:
                raise ValueError("STATIC_ANIMATION_COMPONENT_ORIGIN_AMBIGUOUS:" + instance)
            direct[instance] = template

    def root(source_id: str) -> str:
        seen: set[str] = set()
        current = source_id
        while current in direct:
            if current in seen:
                raise ValueError("STATIC_ANIMATION_COMPONENT_ORIGIN_CYCLE:" + source_id)
            seen.add(current)
            current = direct[current]
        return current

    return [
        {"instanceSourceId": source_id, "templateSourceId": root(source_id)}
        for source_id in sorted(direct)
    ]


def _component_clip_usage(plan: dict, ir: dict) -> tuple[list[dict], list[dict]]:
    plan_components = [row for row in plan.get("components", [])
                       if isinstance(row, dict) and row.get("type") == "cc.Animation"]
    ir_components = [row for row in ir.get("components", [])
                     if isinstance(row, dict) and row.get("type") == "cc.Animation"]
    ir_by_id: dict[str, list[dict]] = {}
    for row in ir_components:
        if isinstance(row.get("sourceId"), str):
            ir_by_id.setdefault(row["sourceId"], []).append(row)
    origins = {row["instanceSourceId"]: row["templateSourceId"]
               for row in _canonical_component_origins(plan)}
    errors = []
    for component in plan_components:
        source_id = component.get("sourceId")
        if not isinstance(source_id, str) or not source_id:
            errors.append({"code": "STATIC_ANIMATION_COMPONENT_ID_INVALID", "sourceComponentId": source_id})
            continue
        template_id = origins.get(source_id, source_id)
        matches = ir_by_id.get(template_id, [])
        if len(matches) != 1 or matches[0].get("node") != component.get("node") and source_id == template_id:
            errors.append({"code": "STATIC_ANIMATION_COMPONENT_SOURCE_UNRESOLVED",
                           "sourceComponentId": source_id, "templateComponentId": template_id,
                           "matchCount": len(matches)})
            continue
        source = matches[0]
        for field in ("clips", "defaultClip", "enabled", "playOnLoad"):
            if (field in source) != (field in component) or source.get(field) != component.get(field):
                errors.append({"code": "STATIC_ANIMATION_COMPONENT_FIELD_CHANGED",
                               "sourceComponentId": source_id, "field": field})
        clips = component.get("clips")
        if not isinstance(clips, list) or any(not isinstance(value, str) or not value for value in clips):
            errors.append({"code": "STATIC_ANIMATION_CLIP_ORDER_INVALID", "sourceComponentId": source_id})
    return plan_components, errors


def _animation_component_references(plan: dict) -> list[dict]:
    """Record exact static fields whose object target is a planned cc.Animation."""
    by_id: dict[str, list[dict]] = {}
    for component in plan.get("components", []):
        if isinstance(component, dict) and isinstance(component.get("sourceId"), str):
            by_id.setdefault(component["sourceId"], []).append(component)
    references = []
    for owner in plan.get("components", []):
        if not isinstance(owner, dict):
            continue
        binding = owner.get("staticFieldBinding")
        if not isinstance(binding, dict):
            continue
        for field in binding.get("fields", []):
            if not isinstance(field, dict) or field.get("kind") != "component_ref":
                continue
            targets = []
            if isinstance(field.get("refValue"), str) and field["refValue"]:
                targets.append((None, field["refValue"]))
            targets.extend((index, value) for index, value in enumerate(field.get("refValues", []))
                           if isinstance(value, str) and value)
            for index, source_id in targets:
                matches = by_id.get(source_id, [])
                if not matches or any(row.get("type") != "cc.Animation" for row in matches):
                    continue
                if len(matches) != 1:
                    raise ValueError("STATIC_ANIMATION_FIELD_TARGET_AMBIGUOUS:" + source_id)
                references.append({
                    "ownerSourceComponentId": owner.get("sourceId"),
                    "fieldName": field.get("sourceFieldName") or field.get("name"),
                    "elementIndex": index,
                    "sourceAnimationComponentId": source_id,
                    "carrierType": "NativeStaticAnimationBinding",
                    "playbackEnabled": False,
                })
    return references


def prepare(plan: dict, ir: dict, source_manifest: dict, output: str | Path) -> dict:
    """Add exact source evidence/identities required by disabled Animation carriers.

    The caller owns plan/IR/manifest pin verification and copies frozen plan
    payloads to ``output``. The return value includes a patched plan and a
    bounded summary; no Unity Editor is launched and playback remains disabled.
    """
    if not isinstance(plan, dict) or not isinstance(ir, dict) or not isinstance(source_manifest, dict):
        raise ValueError("STATIC_ANIMATION_INPUT_DOCUMENT_INVALID")
    profile = plan.get("targetProfile")
    if not isinstance(profile, str) or not profile.startswith("unity-"):
        raise ValueError("STATIC_ANIMATION_TARGET_PROFILE_UNSUPPORTED:" + str(profile))
    if plan.get("sourceProfile") not in (None, source_manifest.get("sourceProfile")):
        raise ValueError("STATIC_ANIMATION_SOURCE_PROFILE_MISMATCH")
    if plan.get("sourceIrSha256") and ir.get("sourceManifestSha256") != plan.get("sourceManifestSha256"):
        raise ValueError("STATIC_ANIMATION_IR_MANIFEST_IDENTITY_MISMATCH")

    patched = copy.deepcopy(plan)
    components, component_errors = _component_clip_usage(patched, ir)
    if component_errors:
        raise ValueError("STATIC_ANIMATION_SOURCE_COMPONENTS_UNRESOLVED:" + json.dumps(component_errors, sort_keys=True))

    # This helper writes the exact cc.AnimationClip source objects as opaque
    # evidence TextAssets. It never treats those JSON records as native curves.
    evidence = prepare_static_animation_assets(patched, source_manifest, output)
    evidence_rows = evidence.get("assets", [])
    diagnostics = list(evidence.get("diagnostics", []))
    if diagnostics:
        raise ValueError("STATIC_ANIMATION_SOURCE_EVIDENCE_UNAVAILABLE:" + json.dumps(diagnostics, sort_keys=True))

    def guid(namespace: str, identity: str) -> str:
        # Match targets.unity.guid without importing the wider target stack.
        return uuid.uuid5(uuid.NAMESPACE_URL, "monkey/" + namespace + "/" + identity).hex

    existing_evidence = {row.get("sourceClipId"): row for row in patched.get("staticAnimationEvidence", [])
                         if isinstance(row, dict)}
    copies = patched.setdefault("copies", [])
    for row in evidence_rows:
        source_id = row["sourceClipId"]
        spec = {"sourceClipId": source_id, "path": row["path"], "sha256": row["nativeAssetSha256"]}
        previous = existing_evidence.get(source_id)
        if previous is not None and previous != spec:
            raise ValueError("STATIC_ANIMATION_EVIDENCE_IDENTITY_CONFLICT:" + source_id)
        if previous is None:
            patched.setdefault("staticAnimationEvidence", []).append(spec)
        copy_row = {
            "source": row["path"], "target": row["path"], "sha256": row["nativeAssetSha256"],
            "guid": guid(patched["namespace"], source_id + "@static-animation-evidence"),
            "sourceId": source_id + "@static-animation-evidence",
            "role": "static-animation-source-evidence",
        }
        matching = [item for item in copies if isinstance(item, dict) and item.get("sourceId") == copy_row["sourceId"]]
        if matching and matching[0] != copy_row:
            raise ValueError("STATIC_ANIMATION_COPY_IDENTITY_CONFLICT:" + source_id)
        if not matching:
            copies.append(copy_row)

    origins = _canonical_component_origins(patched)
    patched["staticAnimationComponentOrigins"] = origins
    component_references = _animation_component_references(patched)
    for component in components:
        component["defaultClipKnown"] = "defaultClip" in component

    source_clips = evidence.get("sourceClipUsages", {})
    clip_order_count = sum(len(row.get("clips", [])) for row in components)
    clip_assets = {row["sourceClipId"] for row in evidence_rows}
    missing = sorted(set(source_clips) - clip_assets)
    if missing:
        raise ValueError("STATIC_ANIMATION_SOURCE_CLIP_EVIDENCE_INCOMPLETE:" + ",".join(missing))

    # Respect the frozen curve plans. A source-evidence TextAsset may preserve
    # identity when a native motion is unavailable; it does not complete curves.
    bound = []
    curve_complete = 0
    curve_partial = 0
    motion_by_id: dict[str, list[dict]] = {}
    for motion in patched.get("animations", []):
        if isinstance(motion, dict) and isinstance(motion.get("id"), str):
            motion_by_id.setdefault(motion["id"], []).append(motion)
    for component in components:
        sid = component["sourceId"]
        for order, clip_id in enumerate(component.get("clips", [])):
            motion_id = clip_id + "@" + sid
            origins_for_component = [row["templateSourceId"] for row in origins
                                     if row["instanceSourceId"] == sid]
            candidate_ids = [motion_id] + [clip_id + "@" + origin for origin in origins_for_component]
            exact = motion_by_id.get(motion_id, [])
            motions = exact if exact else [motion for candidate in candidate_ids[1:]
                                           for motion in motion_by_id.get(candidate, [])]
            signatures = {hashlib.sha256(json.dumps({"id": row["id"], "path": row.get("path"),
                        "tracks": row.get("tracks"), "convertible": row.get("convertible")},
                        ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
                        for row in motions}
            if len(signatures) > 1:
                # Origin reuse is ambiguous: do not select by list order.
                motions = []
            motion = motions[0] if len(motions) == 1 else None
            if motion and motion.get("convertible") is True and motion.get("partial") is not True:
                curve_complete += 1
                curve_status = "converted_curves"
            else:
                curve_partial += 1
                curve_status = "partial_curves" if motion else "source_evidence_only"
            bound.append({"sourceComponentId": sid, "order": order, "sourceClipId": clip_id,
                          "planAnimationId": motion.get("id") if motion else None,
                          "curveStatus": curve_status,
                          "sourceEvidencePath": next(row["path"] for row in evidence_rows if row["sourceClipId"] == clip_id),
                          "playbackEnabled": False})

    continuation = {
        "schema": SCHEMA,
        "status": "prepared" if curve_partial == 0 else "partial",
        "enabled": True,
        "nativePlaybackEnabled": False,
        "nativeAnimatorEnabled": False,
        "sourceManifestPath": patched.get("sourceManifestPath"),
        "sourceManifestSha256": patched.get("sourceManifestSha256"),
        "sourceIrSha256": patched.get("sourceIrSha256"),
        "componentCount": len(components),
        "componentReferenceCount": len(component_references),
        "componentReferences": component_references,
        "clipSlotCount": clip_order_count,
        "sourceEvidenceAssetCount": len(evidence_rows),
        "convertedCurveSlotCount": curve_complete,
        "partialOrEvidenceOnlyCurveSlotCount": curve_partial,
        "bindings": bound,
        "limitations": ["playback_disabled", "no_source_runtime_execution", "partial_curves_remain_partial"],
    }
    patched["staticAnimationContinuation"] = continuation
    # Existing Unity bridge field names are retained for a small importer
    # enable-gate change. They are deliberately independent of staticCompletion.
    patched["staticAnimationBindingsEnabled"] = True
    result = {"schema": SCHEMA, "status": continuation["status"], "plan": patched,
              "evidence": evidence, "continuation": continuation}
    return result
