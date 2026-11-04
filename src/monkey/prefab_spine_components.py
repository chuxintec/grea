"""Build source-exact component binding specs for recovered Spine Prefabs.

This module stops before mutating a target Prefab. It resolves source component
records to separately prepared Creator and Unity SkeletonData identities, keeps
unknown/default-dependent fields explicit, and provides a small executable
adapter contract for target importers.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any


CACHE_MODE_SOURCE_VALUES = {
    0: "REALTIME",
    1: "SHARED_CACHE",
    2: "PRIVATE_CACHE",
}
CREATOR_24_CACHE_SOURCE = "https://raw.githubusercontent.com/cocos/cocos-engine/v2.4.15/extensions/spine/Skeleton.js"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_field(row: dict[str, Any], prop: str, key: str) -> tuple[bool, Any]:
    property_row = row.get("properties", {}).get(prop, {})
    fields = property_row.get("sourceFields", {})
    return key in fields, fields.get(key)


def _property_state(row: dict[str, Any], prop: str) -> str:
    return row.get("properties", {}).get(prop, {}).get("status", "not_accounted")


def _unity_guid(path: Path) -> str | None:
    if not path.is_file():
        return None
    match = re.search(r"(?m)^guid:\s*([0-9a-fA-F]{32})\s*$", path.read_text(encoding="utf-8"))
    return match.group(1).lower() if match else None


def _field_value(row: dict[str, Any], names: tuple[str, ...]) -> tuple[str, Any]:
    present = [(name, row.get("serializedFields", {})[name])
               for name in names if name in row.get("serializedFields", {})]
    if not present:
        return "not_serialized_default_unresolved", None
    values = [value for _, value in present]
    if any(value != values[0] for value in values[1:]):
        return "conflicting_source_fields", {name: value for name, value in present}
    return "explicit", values[0]


def build_component_binding_plan(
    source_contract: dict[str, Any],
    creator_readback: dict[str, Any],
    unity_closure_candidate: str | Path,
    *,
    creator_execution_result: dict[str, Any] | None = None,
    creator_verification: dict[str, Any] | None = None,
    creator_import_plan_sha256: str | None = None,
    creator_candidate_manifest_sha256: str | None = None,
    creator_cache_mode_evidence: dict[str, Any] | None = None,
    source_default_evidence: dict[str, Any] | None = None,
    creator_static_resource_proofs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve all source Skeleton components into dual-target binding records.

    Creator asset UUIDs are accepted only with the exact sourceId+binary hash
    present in native readback. Unity GUIDs come from the isolated candidate's
    generated .meta declarations and are deliberately not called native IDs.
    """
    if source_contract.get("contractSchema") != "prefab-spine-binding/1":
        raise ValueError("unsupported source Spine binding contract")
    unity_root = Path(unity_closure_candidate).resolve()
    closure_path = unity_root / "Analysis/Evidence/spine-closures.json"
    if not closure_path.is_file():
        raise ValueError(f"missing Unity Spine closure report: {closure_path}")
    closure_report = _load(closure_path)
    closure_rows = {row["sourceId"]: row for row in closure_report.get("skeletons", [])}
    native_rows = creator_readback.get("resourceProbes", {}).get("spines", [])
    creator_by_source: dict[str, dict[str, Any]] = {}
    for row in native_rows:
        source_id = row.get("sourceId")
        if not source_id or source_id in creator_by_source:
            raise ValueError(f"missing or duplicate Creator Spine readback sourceId: {source_id}")
        creator_by_source[source_id] = row

    static_resource_by_source: dict[str, dict[str, Any]] = {}
    for proof in creator_static_resource_proofs or []:
        if (not isinstance(proof, dict) or proof.get("schemaVersion") != 1
                or proof.get("profile") != "creator-spine-3.8-v1"
                or proof.get("status") != "static_resource_identity_verified"
                or proof.get("nativeImportCompleted") is not True
                or proof.get("sourceCodeExecuted") is not False
                or proof.get("dynamicAnimationComplete") is not False
                or not isinstance(proof.get("spines"), list)):
            raise ValueError("Creator static resource proof is incomplete or unsupported")
        for row in proof["spines"]:
            source_id = row.get("sourceId") if isinstance(row, dict) else None
            if (not isinstance(source_id, str) or source_id in static_resource_by_source
                    or row.get("savedReferenceVerified") is not True
                    or row.get("textureIdentitiesVerified") is not True
                    or row.get("dynamicPoseStatus") not in {"partial_no_observed_bone_motion", "not_assessed_by_static_proof"}):
                raise ValueError(f"Creator static resource proof has invalid or duplicate row: {source_id}")
            static_resource_by_source[source_id] = row

    execution_pass = bool(
        creator_execution_result
        and creator_execution_result.get("status") == "candidate"
        and creator_execution_result.get("verification", {}).get("editor") == "pass"
        and creator_execution_result.get("verification", {}).get("diagnostics") == 0
        and creator_execution_result.get("nativeProgress", {}).get("status") == "completed"
        and creator_execution_result.get("nativeProgress", {}).get("phase") == "complete"
        and (not creator_import_plan_sha256
             or creator_execution_result.get("importPlanSha256") == creator_import_plan_sha256)
    )
    verification_pass = bool(
        creator_verification
        and creator_verification.get("editorValidation") == "pass"
        and creator_verification.get("staticValidation") == "pass"
        and not creator_verification.get("diagnostics")
    )
    defaults_verified = bool(source_default_evidence
                             and source_default_evidence.get("status") == "verified_source_and_target_defaults"
                             and source_default_evidence.get("valuesMatch") is True)
    default_values = (source_default_evidence or {}).get("sourceValues", {}) if defaults_verified else {}
    default_evidence_reference = ({
        "status": source_default_evidence.get("status"),
        "sourceEngineVersion": source_default_evidence.get("sourceEngineVersion"),
        "sourceUrl": source_default_evidence.get("sourceUrl"),
        "targetEngineVersion": source_default_evidence.get("targetEngineVersion"),
        "targetSourceSha256": source_default_evidence.get("targetSourceSha256"),
        "valuesMatch": source_default_evidence.get("valuesMatch"),
    } if defaults_verified else None)

    data_specs: dict[str, dict[str, Any]] = {}
    for data in source_contract.get("skeletonData", []):
        source_id = data["sourceId"]
        creator = creator_by_source.get(source_id)
        creator_status = "not_in_native_readback"
        if creator is not None:
            source_hash_ok = creator.get("sourceSkeletonSha256") == data.get("skeletonBinarySha256")
            runtime_ok = (creator.get("version") == data.get("spineVersion")
                          and creator.get("savedReferenceVerified") is True
                          and creator.get("nativeStateAdvanced") is True
                          and creator.get("poseChanged") is True
                          and isinstance(creator.get("bones"), int) and creator["bones"] > 0
                          and not creator.get("diagnostics"))
            creator_status = ("native_readback_verified" if source_hash_ok and runtime_ok and execution_pass
                              else "readback_present_but_proof_incomplete")
        static_creator = static_resource_by_source.get(source_id)
        if static_creator is not None:
            if (static_creator.get("sourceSkeletonSha256") != data.get("skeletonBinarySha256")
                    or static_creator.get("version") != data.get("spineVersion")):
                raise ValueError(f"Creator static resource proof differs from source contract: {source_id}")
            if creator is not None:
                raise ValueError(f"Creator asset has both animation and static-only proof rows: {source_id}")
            creator_status = "native_static_resource_readback_verified"

        unity = closure_rows.get(source_id)
        unity_status = "source_id_not_in_unity_closure"
        unity_spec: dict[str, Any] = {"status": unity_status}
        if unity and unity.get("status") == "closure_recovered":
            skeleton_path = unity_root / unity["skeletonPath"]
            guid = _unity_guid(Path(str(skeleton_path) + ".meta"))
            source_hash_ok = unity.get("sourceSkeletonSha256") == data.get("skeletonBinarySha256")
            unity_status = ("candidate_guid_declared_source_hash_verified" if guid and source_hash_ok
                            else "candidate_guid_or_source_hash_unverified")
            unity_spec = {
                "status": unity_status,
                "targetObjectType": "Spine.Unity.SkeletonDataAsset",
                "candidateInputType": "Spine 3.8 binary input; not a Unity SkeletonDataAsset object",
                "candidateInputPath": unity["skeletonPath"],
                "candidateInputMetaGuid": guid,
                "candidateInputMetaGuidStatus": "generated_meta_declaration_for_raw_skeleton_file" if guid else "missing_meta_guid",
                "nativeSkeletonDataAssetGuid": None,
                "nativeSkeletonDataAssetStatus": "requires_import_by_bound_Spine_Unity_runtime; not_materialized_or_read_back",
                "skeletonSha256": unity.get("sourceSkeletonSha256"),
                "sourceHashMatchesFrozenBinary": source_hash_ok,
                "runtimeVersion": unity.get("skeletonVersion"),
                "runtimeCompatibility": "not_validated",
            }
        data_specs[source_id] = {
            "sourceId": source_id,
            "sourceLogicalPath": data.get("logicalPath"),
            "sourceSkeletonSha256": data.get("skeletonBinarySha256"),
            "sourceSpineVersion": data.get("spineVersion"),
            "creator": {
                "status": creator_status,
                "assetType": "sp.SkeletonData",
                "nativeUuid": (static_creator or creator or {}).get("skeletonUuid"),
                "sourceSkeletonSha256": (static_creator or creator or {}).get("sourceSkeletonSha256"),
                "version": (static_creator or creator or {}).get("version"),
                "savedReferenceVerified": (static_creator or creator or {}).get("savedReferenceVerified", False),
                "bones": (static_creator or creator or {}).get("bones"),
                "slots": (static_creator or creator or {}).get("slots"),
                "probeAnimation": creator.get("animation") if creator else None,
                "probeDuration": creator.get("duration") if creator else None,
                "nativePlaybackVerified": bool(creator and creator.get("nativeStateAdvanced") is True
                                               and creator.get("poseChanged") is True),
                "staticResourceVerified": bool(static_creator),
                "dynamicPoseStatus": static_creator.get("dynamicPoseStatus") if static_creator else None,
                "diagnostics": creator.get("diagnostics", []) if creator else [],
                "candidateManifestSha256": creator_candidate_manifest_sha256,
                "verificationPass": verification_pass,
            },
            "unity": unity_spec,
        }

    components = []
    seen_component_ids: set[str] = set()
    for row in source_contract.get("bindings", []) + source_contract.get("unbound", []):
        source_component_id = row.get("sourceComponentId")
        if not source_component_id or source_component_id in seen_component_ids:
            raise ValueError(f"missing or duplicate source component ID: {source_component_id}")
        seen_component_ids.add(source_component_id)
        source_data_id = row.get("dataAssetSourceId")
        data = data_specs.get(source_data_id) if source_data_id else None
        source_has_static_ref = bool(source_data_id and data)
        creator_data_status = data["creator"]["status"] if data else "no_static_source_data_reference"
        unity_data_status = data["unity"]["status"] if data else "no_static_source_data_reference"

        def mapped(prop: str, fields: tuple[str, ...], creator_name: str | None,
                   unity_name: str | None, default_key: str | None = None) -> dict[str, Any]:
            state, value = _field_value(row, fields)
            if state == "not_serialized_default_unresolved" and default_key in default_values:
                state = "resolved_source_engine_default"
                value = default_values[default_key]
            assignable = state in ("explicit", "resolved_source_engine_default")
            return {
                "sourceFields": [name for name in fields if name in row.get("serializedFields", {})],
                "sourceValue": value,
                "status": state,
                "sourceDefaultEvidence": (default_evidence_reference if state == "resolved_source_engine_default" else None),
                "creator": ({"member": creator_name, "value": value, "status": state}
                            if assignable and creator_name else
                            {"member": creator_name, "status": state} if creator_name else
                            {"status": "no_equivalent_field"}),
                "unity": ({"member": unity_name, "value": value, "status": state}
                          if assignable and unity_name else
                          {"member": unity_name, "status": state} if unity_name else
                          {"status": "no_equivalent_field"}),
            }

        # Creator 3.8's startup order is defaultSkin, then defaultAnimation;
        # _animationName is the exact fallback only when defaultAnimation is
        # absent. Keep its original value independently for readback.
        skin_state, skin_value = _field_value(row, ("defaultSkin", "_skinName"))
        if skin_state == "conflicting_source_fields":
            raw_skin = row.get("serializedFields", {})
            if raw_skin.get("defaultSkin"):
                skin_value = raw_skin["defaultSkin"]
                skin_state = "explicit"
                skin_source_fields = ["defaultSkin", "_skinName"]
                skin_source_precedence = "defaultSkin_nonempty_takes_precedence"
            elif raw_skin.get("_skinName"):
                skin_value = raw_skin["_skinName"]
                skin_state = "explicit"
                skin_source_fields = ["defaultSkin", "_skinName"]
                skin_source_precedence = "_skinName_fallback_when_defaultSkin_empty"
            else:
                skin_value = ""
                skin_state = "explicit"
                skin_source_fields = ["defaultSkin", "_skinName"]
                skin_source_precedence = "empty_source_values"
        else:
            skin_source_fields = [name for name in ("defaultSkin", "_skinName") if name in row.get("serializedFields", {})]
            skin_source_precedence = "source_field"
        if skin_state == "not_serialized_default_unresolved" and "defaultSkin" in default_values:
            skin_state = "resolved_source_engine_default"
            skin_value = default_values["defaultSkin"]
        skin = {
            "sourceFields": skin_source_fields,
            "sourceValue": skin_value,
            "status": skin_state,
            "sourceFieldPrecedence": skin_source_precedence,
            "sourceDefaultEvidence": default_evidence_reference if skin_state == "resolved_source_engine_default" else None,
            "creator": {"member": "defaultSkin", "value": skin_value, "status": skin_state}
                       if skin_state in ("explicit", "resolved_source_engine_default") else {"member": "defaultSkin", "status": skin_state},
            "unity": {"member": "initialSkinName", "value": skin_value, "status": skin_state}
                     if skin_state in ("explicit", "resolved_source_engine_default") else {"member": "initialSkinName", "status": skin_state},
        }
        animation = mapped("animation", ("defaultAnimation",), "defaultAnimation", "startingAnimation", "defaultAnimation")
        source_animation_state, source_animation_value = _field_value(row, ("_animationName",))
        if ((animation["status"] in ("not_serialized_default_unresolved", "resolved_source_engine_default")
             or animation.get("sourceValue") == "")
                and (source_animation_state == "explicit" and source_animation_value)):
            animation.update(sourceFields=list(dict.fromkeys(animation.get("sourceFields", []) + ["_animationName"])),
                             sourceValue=source_animation_value,
                             status="explicit", sourceFallback="_animationName")
            animation["creator"] = {"member": "defaultAnimation", "value": source_animation_value,
                                    "status": "explicit", "sourceFallback": "_animationName"}
            animation["unity"] = {"member": "startingAnimation", "value": source_animation_value,
                                  "status": "explicit", "sourceFallback": "_animationName"}
        animation["creatorCurrentAnimationSourceField"] = {
            "sourceFields": ["_animationName"] if "_animationName" in row.get("serializedFields", {}) else [],
            "value": source_animation_value,
            "status": source_animation_state,
        }
        native_animation = data["creator"].get("probeAnimation") if data else None
        if animation["status"] in ("explicit", "resolved_source_engine_default") and animation["sourceValue"] and native_animation:
            animation["nativeProbeComparison"] = (
                "same_name_observed_in_native_probe" if animation["sourceValue"] == native_animation
                else "different_animation_played; requested_source_name_existence_unverified"
            )
        else:
            animation["nativeProbeComparison"] = "not_verified"

        loop = mapped("loop", ("loop",), "loop", "startingLoop", "loop")
        times = mapped("playTimes", ("_playTimes",), None, None, "playTimes")
        if times["status"] in ("explicit", "resolved_source_engine_default"):
            times["creator"] = {"status": "source_only_no_same_component_field"}
            times["unity"] = {"status": "source_only_no_same_component_field"}
        time_scale = mapped("timeScale", ("timeScale",), "timeScale", "timeScale", "timeScale")
        pma = mapped("premultipliedAlpha", ("premultipliedAlpha",), "premultipliedAlpha", "pmaVertexColors", "premultipliedAlpha")
        tint = mapped("tint", ("useTint",), "useTint", None, "useTint")
        debug_slots = mapped("debugSlots", ("debugSlots",), "debugSlots", None, "debugSlots")
        debug_bones = mapped("debugBones", ("debugBones",), "debugBones", None, "debugBones")
        debug_mesh = mapped("debugMesh", ("debugMesh",), "debugMesh", None, "debugMesh")
        enable_batch = mapped("enableBatch", ("enableBatch",), "enableBatch", None, "enableBatch")
        caching = mapped("caching", ("_preCacheMode",), None, None, "cacheMode")
        if caching["status"] in ("explicit", "resolved_source_engine_default"):
            cache_value = caching["sourceValue"]
            proven_values = (creator_cache_mode_evidence or {}).get("values", {})
            enum_name = proven_values.get(str(cache_value)) if type(cache_value) is int else None
            if enum_name in CACHE_MODE_SOURCE_VALUES.values() and CACHE_MODE_SOURCE_VALUES.get(cache_value) == enum_name:
                caching["creator"] = {
                    "member": "defaultCacheMode",
                    "value": cache_value,
                    "enumName": enum_name,
                    "status": "explicit",
                    "enumEvidence": "verified_source_and_target_enum_values",
                }
                caching["unity"] = {"status": "source_only_runtime_cache_mapping_unresolved"}
            else:
                caching["creator"] = {"status": "enum_translation_unverified_blocked_no_assignment"}
                caching["unity"] = {"status": "source_only_runtime_cache_mapping_unresolved"}

        properties = {
            "skeletonData": {
                "sourceUuid": row.get("skeletonDataUuid"),
                "sourceAssetId": source_data_id,
                "status": row.get("status"),
                "sourceDefault": ((source_default_evidence or {}).get("sourceValues", {}).get("skeletonData")
                                  if defaults_verified and not source_data_id else None),
                "sourceDefaultEvidence": default_evidence_reference if defaults_verified and not source_data_id else None,
                "creator": {"assetType": "sp.SkeletonData", "nativeUuid": data["creator"].get("nativeUuid") if data else None,
                            "status": creator_data_status},
                "unity": {"assetType": "Spine.Unity.SkeletonDataAsset",
                          "candidateInputPath": data["unity"].get("candidateInputPath") if data else None,
                          "candidateInputMetaGuid": data["unity"].get("candidateInputMetaGuid") if data else None,
                          "nativeSkeletonDataAssetGuid": data["unity"].get("nativeSkeletonDataAssetGuid") if data else None,
                          "status": unity_data_status},
            },
            "skin": skin,
            "animation": animation,
            "loop": loop,
            "playTimes": times,
            "timeScale": time_scale,
            "premultipliedAlpha": pma,
            "tint": tint,
            "debugSlots": debug_slots,
            "debugBones": debug_bones,
            "debugMesh": debug_mesh,
            "enableBatch": enable_batch,
            "caching": caching,
        }
        unsupported_source_fields = {
            key: value for key, value in row.get("serializedFields", {}).items()
            if key not in {"_N$skeletonData", "defaultSkin", "_skinName", "defaultAnimation",
                           "_animationName", "loop", "_playTimes", "timeScale",
                           "premultipliedAlpha", "_preCacheMode", "useTint", "debugSlots",
                           "debugBones", "debugMesh", "enableBatch"}
        }
        # Material overrides are preserved as source evidence but not turned
        # into a guessed target Material reference.
        components.append({
            "sampleId": row.get("sampleId"),
            "sourcePrefabId": row.get("prefabSourceId"),
            "sourcePrefabPath": row.get("prefabLogicalPath"),
            "sourceComponentId": source_component_id,
            "sourceComponentType": row.get("sourceComponentType"),
            "sourceOrigin": row.get("sourceOrigin"),
            "sourceNodeId": row.get("nodeInstanceIndex"),
            "sourceNodePath": row.get("nodePath"),
            "sourceSerializedFields": row.get("serializedFields", {}),
            "sourceDataAssetId": source_data_id,
            "creator": {
                "componentType": "sp.Skeleton",
                "nativeComponentInstance": "requires sourceComponentId -> created native component mapping",
                "fields": properties,
                "runtimeBinding": "apply static asset only when source UUID exists; leave resource unset for unbound rows",
            },
            "unity": {
                "componentType": None,
                "componentTypeSelection": "caller must choose from exact target node UI context",
                "componentTypeChoices": ["Spine.Unity.SkeletonGraphic", "Spine.Unity.SkeletonAnimation"],
                "runtimePackage": "existing local Spine 3.8.99 branch3.8; not copied",
                "nativeComponentInstance": "requires sourceComponentId -> created native component mapping",
                "fields": properties,
                "runtimeBinding": "resolve SkeletonDataAsset by sourceDataAssetId from isolated candidate; do not assign a fallback",
            },
            "runtimeDynamicAssignment": {
                "status": "source_static_uuid_absent_runtime_assignment_unverified" if not source_has_static_ref else "source_static_uuid_bound",
                "dynamicCodeEvidence": "not_in_component_contract",
                "targetDefaultAssetFallback": False,
            },
            "unsupportedSourceFields": unsupported_source_fields,
        })

    if len(components) != source_contract.get("skeletonComponentCount"):
        raise ValueError("component denominator mismatch against frozen source contract")
    return {
        "schemaVersion": 1,
        "contract": "monkey-prefab-spine-components/1",
        "sourceContractSchema": source_contract.get("contractSchema"),
        "sourceProfile": source_contract.get("sourceProfile"),
        "sourceManifestSha256": source_contract.get("sourceManifestFileSha256"),
        "componentCount": len(components),
        "staticAssetBoundComponents": sum(bool(c["sourceDataAssetId"]) for c in components),
        "staticAssetUnboundComponents": sum(not c["sourceDataAssetId"] for c in components),
        "uniqueStaticDataAssets": len(data_specs),
        "creatorNativeReadback": {
            "verified": execution_pass and verification_pass and not creator_static_resource_proofs,
            "status": "partial_static_resource_readback" if creator_static_resource_proofs else None,
            "staticResourceProofSourceIds": sorted(static_resource_by_source),
            "executionResultStatus": creator_execution_result.get("status") if creator_execution_result else None,
            "verification": creator_verification.get("editorValidation") if creator_verification else None,
            "diagnostics": creator_verification.get("diagnostics") if creator_verification else None,
            "importPlanSha256": creator_import_plan_sha256,
            "candidateManifestSha256": creator_candidate_manifest_sha256,
            "resourceReadbackCount": len(native_rows),
        },
        "creatorCacheModeEnumEvidence": creator_cache_mode_evidence or {
            "status": "not_provided; source enum equality must be proven before assignment",
            "values": {},
        },
        "sourceDefaultEvidence": source_default_evidence or {
            "status": "not_provided; omitted source component fields remain unknown",
        },
        "unityRuntimeEvidence": {
            "runtimeVersion": "3.8.99 skeleton compatible branch3.8",
            "runtimeManifestStatus": "locally_declared_and_file_hashes_verified",
            "runtimeCopied": False,
            "unityNativeAssetIdsReadBack": False,
            "unityClosureReportSha256": _sha(closure_path),
        },
        "requiredImporterWiring": {
            "creator": "After source Prefab component creation, call applyCreatorSpineBindings with sourceComponentId->component and sourceAssetId->loaded sp.SkeletonData resolvers; after save/reopen call readCreatorSpineBindings with sourceComponentId->saved sp.Skeleton resolver. The reader compares native UUID, requested animation/skin existence, current animation/skin, loop, timeScale, PMA, and cache mode; apply only explicit or source-default-resolved fields.",
            "unity": "After source Prefab component creation, call targets/spine/UnitySpineBinding.cs with sourceComponentId->Component and sourceAssetId->isolated SkeletonDataAsset resolvers; apply only explicit or source-default-resolved fields. The Unity runtime DLL/license must be bound from an approved isolated candidate before native serialization.",
            "single_writer_files_unchanged": True,
        },
        "components": components,
        "dataAssets": list(data_specs.values()),
        "limitations": [
            "Three components have no serialized SkeletonData UUID; dynamic runtime assignment has not been proven and no fallback asset is assigned.",
            "Unity closure GUIDs are generated .meta declarations, not native AssetDatabase readback.",
            "Creator native readback proves resource loading and the observed probe animation; it does not prove every source component's requested animation name exists.",
            "Unknown source defaults, runtime code assignments, material overrides, callback behavior, visual parity, and Unity native Prefab serialization remain pending.",
        ],
    }


def prepare_spine_emission(
    source_manifest: dict[str, Any],
    source_manifest_sha256: str,
    normalized_ir: dict[str, Any],
    normalized_ir_sha256: str,
    closure_receipts: dict[str, dict[str, Any]],
    component_plan: dict[str, Any],
    creator_material_contract: dict[str, Any] | None = None,
    creator_material_contract_sha256: str | None = None,
) -> dict[str, Any]:
    """Prepare a path-relative target emission payload from explicitly pinned inputs.

    Callers load and pin the original manifest, normalized IR, and both native
    closure receipts. This function reads no files and depends on no private
    fixture paths. Unity raw `.skel.bytes` declarations are kept distinct from
    imported `SkeletonDataAsset` objects.
    """
    if not isinstance(source_manifest_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", source_manifest_sha256):
        raise ValueError("an explicit lowercase source manifest SHA-256 pin is required")
    if not isinstance(normalized_ir_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", normalized_ir_sha256):
        raise ValueError("an explicit lowercase normalized IR SHA-256 pin is required")
    if normalized_ir.get("sourceManifestSha256") != source_manifest_sha256:
        raise ValueError("normalized IR is not pinned to the supplied original source manifest")
    if component_plan.get("sourceManifestSha256") != source_manifest_sha256:
        raise ValueError("component plan source manifest pin differs")
    if component_plan.get("componentCount") != len(component_plan.get("components", [])):
        raise ValueError("component plan denominator is inconsistent")

    selected_prefab_rows = component_plan.get("selectedSourcePrefabs") or []
    selected_prefabs = {row.get("sourcePrefabId") for row in selected_prefab_rows}
    selected_prefabs.discard(None)
    if not selected_prefabs:
        selected_prefabs = {row.get("sourcePrefabId") for row in component_plan["components"]}
        selected_prefabs.discard(None)
        selected_prefab_rows = [{"sourcePrefabId": prefab_id} for prefab_id in sorted(selected_prefabs)]
    selected_component_ids = {row["sourceComponentId"] for row in component_plan["components"]}
    ir_component_ids = {
        row.get("sourceId") for row in normalized_ir.get("components", [])
        if row.get("type") == "sp.Skeleton"
        and any(str(row.get("sourceId", "")).startswith(prefab_id + "#") for prefab_id in selected_prefabs)
    }
    if selected_component_ids != ir_component_ids:
        missing = sorted(selected_component_ids - ir_component_ids)
        extra = sorted(ir_component_ids - selected_component_ids)
        raise ValueError(f"source component denominator differs from the pinned IR: missing={missing}, extra={extra}")

    source_assets = {row.get("sourceId"): row for row in source_manifest.get("assets", []) if row.get("sourceId")}
    for prefab_id in selected_prefabs:
        if prefab_id not in source_assets:
            raise ValueError(f"selected Prefab source ID is absent from the pinned manifest: {prefab_id}")

    data_assets = component_plan.get("dataAssets", [])
    data_ids = {row.get("sourceId") for row in data_assets}
    for source_id in data_ids:
        if source_id not in source_assets:
            raise ValueError(f"SkeletonData source ID is absent from the pinned manifest: {source_id}")
    if set(closure_receipts) != {"creator", "unity"}:
        raise ValueError("provide exact Creator and Unity closure receipts")

    closure_rows: dict[str, dict[str, dict[str, Any]]] = {}
    receipt_files: dict[str, dict[str, dict[str, Any]]] = {}
    for engine, receipt in closure_receipts.items():
        if receipt.get("sourceManifestSha256") != source_manifest_sha256:
            raise ValueError(f"{engine} closure receipt is not pinned to the supplied source manifest")
        if not isinstance(receipt.get("receiptSha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", receipt["receiptSha256"]):
            raise ValueError(f"{engine} closure receipt requires an explicit SHA-256 pin")
        closure_rows[engine] = {row.get("sourceId"): row for row in receipt.get("skeletons", []) if row.get("sourceId")}
        receipt_files[engine] = {row.get("path"): row for row in receipt.get("files", []) if row.get("path")}
        for source_id in data_ids:
            row = closure_rows[engine].get(source_id)
            if not row or row.get("status") != "closure_recovered":
                raise ValueError(f"{engine} has no exact recovered closure for {source_id}")
            expected = next(asset for asset in data_assets if asset["sourceId"] == source_id)["sourceSkeletonSha256"]
            if row.get("sourceSkeletonSha256") != expected:
                raise ValueError(f"{engine} closure bytes differ from the frozen source binary for {source_id}")
            if engine == "creator":
                expected_uuid = next(asset for asset in data_assets if asset["sourceId"] == source_id).get("creator", {}).get("nativeUuid")
                observed_uuid = receipt.get("nativeAssetUuids", {}).get(source_id)
                if not expected_uuid or observed_uuid != expected_uuid:
                    raise ValueError(f"Creator closure asset UUID does not match native readback for {source_id}")

    copies = []
    prepared_assets = []
    for asset in data_assets:
        source_id = asset["sourceId"]
        creator_row = closure_rows["creator"][source_id]
        unity_row = closure_rows["unity"][source_id]
        creator_files = creator_row.get("files", [])
        unity_files = unity_row.get("files", [])
        for engine, row, selected_files in (("creator", creator_row, creator_files), ("unity", unity_row, unity_files)):
            owned = receipt_files[engine]
            for member in selected_files:
                relative = member.get("path")
                if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
                    raise ValueError(f"unsafe {engine} closure output path for {source_id}: {relative}")
                receipt_file = owned.get(relative)
                if not receipt_file or receipt_file.get("sha256") != member.get("sha256") or receipt_file.get("bytes") != member.get("bytes"):
                    raise ValueError(f"{engine} closure file is not covered by its explicit receipt: {relative}")
                copies.append({
                    "target": engine,
                    "sourceId": source_id,
                    "path": relative,
                    "sha256": member["sha256"],
                    "bytes": member["bytes"],
                })
                meta_path = relative + ".meta"
                meta = owned.get(meta_path)
                if meta:
                    copies.append({
                        "target": engine,
                        "sourceId": source_id,
                        "path": meta_path,
                        "sha256": meta["sha256"],
                        "bytes": meta["bytes"],
                    })
        creator_readback = asset.get("creator", {})
        unity_asset = asset.get("unity", {})
        prepared_assets.append({
            "sourceId": source_id,
            "sourceLogicalPath": asset.get("sourceLogicalPath"),
            "sourceSkeletonSha256": asset.get("sourceSkeletonSha256"),
            "sourceSpineVersion": asset.get("sourceSpineVersion"),
            "creator": {
                "type": "sp.SkeletonData",
                "nativeUuid": creator_readback.get("nativeUuid"),
                "status": creator_readback.get("status"),
                "skeletonPath": creator_row.get("skeletonPath"),
                "atlasPath": creator_row.get("atlasPath"),
            },
            "unity": {
                "targetObjectType": "Spine.Unity.SkeletonDataAsset",
                "candidateInputPath": unity_asset.get("candidateInputPath") or unity_row.get("skeletonPath"),
                "candidateInputMetaGuid": unity_asset.get("candidateInputMetaGuid"),
                "nativeObjectGuid": None,
                "nativeObjectStatus": "requires_isolated_runtime_importer_readback",
                "atlasPath": unity_row.get("atlasPath"),
            },
        })

    material_profile = None
    material_by_component: dict[str, dict[str, Any]] = {}
    if creator_material_contract is not None:
        if not isinstance(creator_material_contract_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", creator_material_contract_sha256):
            raise ValueError("Creator material contract requires an explicit SHA-256 pin")
        contract = creator_material_contract
        pins = contract.get("pins", {})
        profile = contract.get("spec", {}).get("creator38", {})
        if (contract.get("schema") != "monkey-spine-material-contract/1"
                or contract.get("profile") != "cocos24-builtin-spine-material-v1"
                or contract.get("creatorBindingStatus") != "source-semantics-exact-builtin-spine"
                or pins.get("sourceManifestSha256") != source_manifest_sha256
                or pins.get("normalizedIrSha256") != normalized_ir_sha256
                or profile.get("strategy") != "explicit-native-builtin-spine-material-reference"
                or profile.get("targetMaterialUuid") != "default-spine-material"
                or profile.get("effect") != "builtin-spine"):
            raise ValueError("Creator Spine material profile is not pinned to this source/IR and built-in material contract")
        rows = profile.get("perComponent")
        if not isinstance(rows, list):
            raise ValueError("Creator material profile has no per-component source mapping")
        material_by_component = {row.get("sourceComponentId"): row for row in rows if row.get("sourceComponentId")}
        expected_ids = {row["sourceComponentId"] for row in component_plan["components"]}
        if len(material_by_component) != len(rows) or set(material_by_component) != expected_ids:
            raise ValueError("Creator material profile component denominator differs from Spine emission")
        for source_id, row in material_by_component.items():
            source_binding = row.get("sourceMaterialBinding") or ({"status": "explicit"}
                if isinstance(row.get("sourceMaterialReferenceSourceId"), str) and isinstance(row.get("sourceMaterialSourceId"), str) else {})
            explicit = source_binding.get("status") == "explicit"
            source_default = source_binding.get("status") == "resolved_source_engine_default"
            if (row.get("targetMaterialUuid") != "default-spine-material"
                    or (explicit and (not isinstance(row.get("sourceMaterialReferenceSourceId"), str)
                                      or not isinstance(row.get("sourceMaterialSourceId"), str)))
                    or (source_default and (row.get("sourceMaterialReferenceSourceId") is not None
                                            or row.get("sourceMaterialSourceId") is not None
                                            or source_binding.get("sourcePath") != "extensions/spine/Skeleton.js"))
                    or not (explicit or source_default)
                    or row.get("runtimeMaterialStrategy") != "Creator Spine runtime creates per-slot MaterialInstance over builtin-spine and selects blend factors from component PMA"):
                raise ValueError(f"Creator material mapping is incomplete or ambiguous for {source_id}")
        material_profile = {
            "contract": contract["profile"],
            "contractSha256": creator_material_contract_sha256,
            "sourceMaterialReferenceSourceId": pins.get("materialReferenceSourceId"),
            "sourceMaterialSourceId": pins.get("materialSourceId"),
            "effectSourceId": pins.get("effectSourceId"),
            "effectProgramCanonicalSha256": pins.get("effectProgramCanonicalSha256"),
            "targetMaterialUuid": "default-spine-material",
            "targetEffect": "builtin-spine",
            "strategy": profile["strategy"],
            "evidenceStatus": "source_to_internal_to_creator_builtin_pinned",
        }

    component_specs = []
    for row in component_plan["components"]:
        spec = {
            "sampleId": row.get("sampleId"),
            "sourcePrefabId": row.get("sourcePrefabId"),
            "sourceComponentId": row.get("sourceComponentId"),
            "sourceNodeId": row.get("sourceNodeId"),
            "sourceNodePath": row.get("sourceNodePath"),
            "sourceDataAssetId": row.get("sourceDataAssetId"),
            "sourceSerializedFields": row.get("sourceSerializedFields", {}),
            "creator": row.get("creator"),
            "unity": row.get("unity"),
            "runtimeDynamicAssignment": row.get("runtimeDynamicAssignment"),
        }
        if material_profile:
            spec["creatorMaterialBinding"] = {
                **material_by_component[row["sourceComponentId"]],
                "contract": material_profile["contract"],
                "contractSha256": material_profile["contractSha256"],
                "evidenceStatus": material_profile["evidenceStatus"],
            }
            time_scale = row.get("creator", {}).get("fields", {}).get("timeScale", {})
            creator_time_scale = time_scale.get("creator") or {}
            if creator_time_scale.get("status") not in {"explicit", "resolved_source_engine_default"}:
                raise ValueError(f"Creator timeScale source/default is not evidenced for static visible pose: {row['sourceComponentId']}")
            source_scale = creator_time_scale.get("value")
            if isinstance(source_scale, bool) or not isinstance(source_scale, (int, float)) or not math.isfinite(source_scale):
                raise ValueError(f"Creator timeScale is not a finite evidenced number for {row['sourceComponentId']}")
            spec["creatorStaticPose"] = {
                "policy": "enabled_realtime_renderer_with_serialized_timeScale_zero",
                "nativeEnabled": True,
                "nativeTimeScale": 0,
                "sourceTimeScale": {"value": source_scale, "status": creator_time_scale["status"]},
                "sourceFieldValueRetainedInEmission": True,
                "sourceMaterialRoute": "Creator sp.Skeleton updateMaterial -> builtinResMgr.get(default-spine-material)",
                "targetEngineSource": "cocos/spine/skeleton.ts",
                "targetEngineSourceSha256": "2e86383e7e7dfb93bc40ec1d7e44c6bb2b8ebe4e95c100ad16620bd24114329",
                "animationFrozenBySerializedTimeScale": True,
                "businessCallbacksExecuted": False,
            }
        component_specs.append(spec)
    return {
        "schemaVersion": 1,
        "contract": "monkey-spine-emission/1",
        "pins": {
            "sourceManifestSha256": source_manifest_sha256,
            "normalizedIrSha256": normalized_ir_sha256,
            "creatorClosureReceiptSha256": closure_receipts["creator"].get("receiptSha256"),
            "unityClosureReceiptSha256": closure_receipts["unity"].get("receiptSha256"),
            **({"creatorMaterialContractSha256": creator_material_contract_sha256} if material_profile else {}),
        },
        "sourceProfile": source_manifest.get("sourceProfile"),
        "sourceVersion": source_manifest.get("sourceVersion"),
        "targetProfiles": {"creator": "cocos-3.8.8", "unity": "unity-6000.6.2f1"},
        "sourcePrefabCount": len(selected_prefabs),
        "selectedSourcePrefabs": [
            {
                "sampleId": row.get("sampleId"),
                "sourcePrefabId": row["sourcePrefabId"],
                "sourceLogicalPath": source_assets[row["sourcePrefabId"]].get("logicalPath"),
            }
            for row in selected_prefab_rows
        ],
        "selectedPrefabsWithNoSpineComponents": sorted(
            selected_prefabs - {row.get("sourcePrefabId") for row in component_plan["components"]}
        ),
        "sourceComponentCount": len(component_specs),
        "staticAssetBoundComponents": component_plan.get("staticAssetBoundComponents"),
        "staticAssetUnboundComponents": component_plan.get("staticAssetUnboundComponents"),
        "assets": prepared_assets,
        "copies": copies,
        "components": component_specs,
        **({"creatorMaterialProfile": material_profile} if material_profile else {}),
        "originalSourceCodeExecuted": False,
        "nativeImportStatus": {"creator": "resource_probe_verified; source_prefab_component_readback_pending", "unity": "not_run"},
    }


def emit_spine_emission(prepared: dict[str, Any], output_path: str | Path) -> str:
    """Write a prepared path-relative Spine emission document and return its SHA-256."""
    if prepared.get("contract") != "monkey-spine-emission/1":
        raise ValueError("unsupported Spine emission payload")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(prepared, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()
