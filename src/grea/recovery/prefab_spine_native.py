"""Evidence-joined native factory input for the existing Cocos -> Unity Spine stage.

This does not import or mutate a Unity project. It joins the already-frozen
component, material, closure, and runtime evidence into the exact factory input
shape consumed by targets/spine/UnitySpineNativeFactory.cs.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any


PROFILE = "cocos24-builtin-spine-material-v1"
SHADER = "Monkey/SpineSourceProfile/Colored"
SOURCE_SCALE_EVIDENCE = {
    "status": "verified_source_default",
    "sourceEngineVersion": "Cocos Creator 2.4.15",
    "sourcePath": "extensions/spine/skeleton-data.js",
    "sourceUrl": "https://raw.githubusercontent.com/cocos/cocos-engine/v2.4.15/extensions/spine/skeleton-data.js",
    "sourceSha256": "d0a4b5323687196dc5ee3ff8fcdc328e49148c1cf523b08b542e63dfb97b1329",
    "sourceDefaultScale": 1.0,
    "sourceUse": "SkeletonData.getRuntimeData assigns this.scale to SkeletonJson/SkeletonBinary.reader.scale",
}
PERSISTENT_VISIBLE_POSE_EVIDENCE = {
    "status": "verified_pinned_spine_unity_3_8_runtime_source",
    "upstreamCommit": "8b4844bd4b193ba9e54487ed397a777993cbad56",
    "runtimeVersion": "3.8.99",
    "sourceEvidence": [
        {"path": "Unity/Components/SkeletonGraphic.cs", "sha256": "ce83a9686b6d79f94ad7bc4ff06c6d732dbca194ae921abfd0a69bc28df7afb4",
         "facts": ["OnDisable clears CanvasRenderer", "Update multiplies deltaTime by timeScale", "LateUpdate updates mesh while enabled"]},
        {"path": "Unity/Components/SkeletonAnimation.cs", "sha256": "91674944a815287a9f7ef4f242d9f748db71d5585f2d36bce7559208948b1339",
         "facts": ["Update multiplies deltaTime by timeScale", "LateUpdate updates the mesh while enabled"]},
        {"path": "Unity/Components/SkeletonRenderer.cs", "sha256": "a56bc75ccd170f3cbb6523e318e02a99fb0af41713836cbd12df3b10e0971525",
         "facts": ["pinned official upstream renderer source"]},
    ],
    "targetPolicy": "keep_native_renderer_enabled_and_set_timeScale_zero; preserve verified sourceTimeScale in identity/readback; no recovered game behavior",
}
_SHA = re.compile(r"^[0-9a-f]{64}$")
_RENDERER_CONTEXT_CONTRACT = "monkey-unity-spine-renderer-context/1"
_RENDERER_KINDS = {"SkeletonGraphic", "SkeletonAnimation"}


def _finite_positive(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(float(value)) and float(value) > 0


class SpineNativePlanError(ValueError):
    pass


def _hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise SpineNativePlanError(f"{label} must be a lowercase SHA-256")
    return value


def _array(obj: dict, key: str) -> list[dict]:
    value = obj.get(key)
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise SpineNativePlanError(f"{key} must be an array of objects")
    return value


def _asset_stem(path: str) -> str:
    name = Path(path).name
    if name.endswith(".skel.bytes"):
        return name[:-len(".skel.bytes")]
    return Path(name).stem


def _safe_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _verified_editor_variant(runtime: dict, stage: dict) -> dict | None:
    """Validate an optional, paired Editor-only Spine runtime.

    The player pair remains the authority for non-Editor platforms. The
    separate Editor pair must be compiled from the pinned source and refer to
    its paired core assembly; matching assembly names alone is insufficient.
    """
    evidence = runtime.get("editorVariant")
    if evidence is None:
        return None
    if not isinstance(evidence, dict) or evidence.get("status") != "verified_editor_source_build":
        raise SpineNativePlanError("Editor Spine runtime variant is not source-build verified")
    if (evidence.get("upstreamCommit") != runtime.get("upstreamCommit") or
        evidence.get("compiledAgainst") != "Unity6000.6.2f1" or
        evidence.get("importPolicy") != "paired_editor_only_assemblies_player_pair_excludes_editor" or
        evidence.get("cocosCompatibilityFallbacksIncluded") is not False):
        raise SpineNativePlanError("Editor Spine runtime pin, import policy, or source profile differs")
    defines = evidence.get("compileDefines")
    if not isinstance(defines, list) or "UNITY_EDITOR" not in defines:
        raise SpineNativePlanError("Editor Spine runtime was not compiled with UNITY_EDITOR")
    hashes = evidence.get("playerAssemblyHashes")
    if not isinstance(hashes, dict):
        raise SpineNativePlanError("Editor Spine runtime lacks frozen player assembly hashes")
    assemblies = evidence.get("assemblies")
    staged = stage.get("editorVariant")
    if not isinstance(assemblies, dict) or not isinstance(staged, dict) or staged.get("status") != "verified_editor_source_build":
        raise SpineNativePlanError("Editor Spine assembly pair or stage copy is missing")
    staged_files = staged.get("copiedFiles")
    base_checks = runtime.get("fileChecks", {})
    for filename in ("spine-csharp.dll", "spine-unity.dll"):
        row = assemblies.get(filename)
        stage_row = staged_files.get(filename) if isinstance(staged_files, dict) else None
        if (not isinstance(row, dict) or not isinstance(stage_row, dict) or stage_row.get("verified") is not True or
            stage_row.get("sha256") != row.get("sha256") or hashes.get(filename) != base_checks.get(filename, {}).get("expectedSha256") or
            row.get("assemblyName") != filename[:-4] or row.get("assemblyVersion") != "0.0.0.0" or
            row.get("playerReferenceIdentity") != {"name": filename[:-4], "version": "0.0.0.0"}):
            raise SpineNativePlanError("Editor Spine assembly does not have a verified matching player assembly identity: " + filename)
        if row.get("runtimeImportPath") != "Assets/Plugins/Spine38/EditorRuntime/" + filename:
            raise SpineNativePlanError("Editor Spine assembly import path must avoid Unity's special Editor folder: " + filename)
    unity_refs = assemblies["spine-unity.dll"].get("references")
    core_refs = assemblies["spine-csharp.dll"].get("references")
    if (not isinstance(unity_refs, list) or {row.get("name") for row in unity_refs if isinstance(row, dict)}.isdisjoint({"spine-csharp"}) or
        not any(isinstance(row, dict) and row.get("name") == "spine-csharp" and row.get("version") == "0.0.0.0" for row in unity_refs) or
        not any(isinstance(row, dict) and row.get("name") == "UnityEditor.CoreModule" for row in unity_refs) or
        not isinstance(core_refs, list) or any(isinstance(row, dict) and row.get("name") == "UnityEditor.CoreModule" for row in core_refs)):
        raise SpineNativePlanError("Editor Spine unity/core assembly reference pairing is invalid")
    if staged.get("sourceManifestSha256") != evidence.get("sourceManifestSha256"):
        raise SpineNativePlanError("Editor Spine stage source manifest differs from its build evidence")
    return {
        "status": evidence["status"],
        "sourceEvidencePath": evidence.get("evidencePath"),
        "sourceEvidenceSha256": evidence.get("evidenceSha256"),
        "sourceManifestSha256": evidence.get("sourceManifestSha256"),
        "importPolicy": evidence["importPolicy"],
        "assemblies": {
            name: {"sha256": assemblies[name]["sha256"], "bytes": assemblies[name]["bytes"],
                   "assemblyName": assemblies[name]["assemblyName"],
                   "assemblyVersion": assemblies[name]["assemblyVersion"],
                   "references": assemblies[name]["references"],
                   "runtimeImportPath": assemblies[name]["runtimeImportPath"]}
            for name in ("spine-csharp.dll", "spine-unity.dll")
        },
        "assemblyLoadVerification": {
            "status": "not_run",
            "expectedAssemblyPath": assemblies["spine-unity.dll"]["runtimeImportPath"],
            "expectedAssemblySha256": assemblies["spine-unity.dll"]["sha256"],
            "expectedCoreAssemblyPath": assemblies["spine-csharp.dll"]["runtimeImportPath"],
            "expectedCoreAssemblySha256": assemblies["spine-csharp.dll"]["sha256"],
            "expectedUnityEditorReference": True,
            "requiredActualFields": ["typeof(SkeletonGraphic).Assembly.Location", "assemblySha256",
                                     "referencedAssemblies", "unityEditorReferencePresent"]},
    }


def _load_renderer_contexts(target_unit_evidence: dict | None, components: list[dict],
                            source_manifest_sha256: str, normalized_ir_sha256: str):
    """Load explicit target renderer/Canvas declarations with byte-verified evidence.

    These rows are frozen planning inputs, not actual native Canvas readback. The
    final Editor verifier must still compare the declared kind with the saved
    renderer; Canvas PPU is verified by the integrating owner's native QA.
    """
    expected = {row.get("sourceComponentId"): row for row in components}
    pin = target_unit_evidence.get("rendererContexts") if isinstance(target_unit_evidence, dict) else None
    if not isinstance(pin, dict):
        return {}, {"status": "missing", "nativeReadback": "not_run"}
    source_value, expected_sha = pin.get("sourcePath"), pin.get("sha256")
    if not isinstance(source_value, str) or not source_value:
        raise SpineNativePlanError("renderer context pin requires sourcePath")
    _hash(expected_sha, "rendererContexts.sha256")
    source_path = Path(source_value).expanduser().resolve(strict=True)
    raw = source_path.read_bytes()
    if len(raw) > 8 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != expected_sha:
        raise SpineNativePlanError("renderer context source bytes differ from its SHA-256 pin")
    try:
        document = json.loads(raw.decode("utf-8-sig"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise SpineNativePlanError("renderer context source is not strict UTF-8 JSON") from error
    if (not isinstance(document, dict) or document.get("schemaVersion") != 1 or
            document.get("contract") != _RENDERER_CONTEXT_CONTRACT or
            document.get("status") != "declared" or document.get("nativeReadback") != "not_run" or
            document.get("sourceManifestSha256") != source_manifest_sha256 or
            document.get("normalizedIrSha256") != normalized_ir_sha256):
        raise SpineNativePlanError("renderer context source contract/status/source pins differ")
    context_rows = document.get("contexts")
    if not isinstance(context_rows, list):
        raise SpineNativePlanError("renderer context source requires a contexts array")
    contexts: dict[str, dict] = {}
    for row in context_rows:
        if not isinstance(row, dict):
            raise SpineNativePlanError("renderer context entry must be an object")
        source_id = row.get("sourceComponentId")
        if not isinstance(source_id, str) or source_id not in expected:
            raise SpineNativePlanError("renderer context sourceComponentId is outside the exact plan denominator")
        if source_id in contexts:
            raise SpineNativePlanError("duplicate renderer context for source component: " + source_id)
        if row.get("sourceNodeId") != expected[source_id].get("sourceNodeId"):
            raise SpineNativePlanError("renderer context source node differs from its exact component: " + source_id)
        renderer = row.get("rendererKind")
        if renderer not in _RENDERER_KINDS:
            raise SpineNativePlanError("renderer context kind is unsupported: " + source_id)
        expected_transform = "RectTransform" if renderer == "SkeletonGraphic" else "Transform"
        if row.get("targetNodeTransform") != expected_transform:
            raise SpineNativePlanError("renderer context node type conflicts with renderer kind: " + source_id)

        required_roles = {"target-node-transform"}
        if renderer == "SkeletonGraphic":
            if not _finite_positive(row.get("canvasReferencePixelsPerUnit")):
                raise SpineNativePlanError("SkeletonGraphic Canvas PPU must be positive and finite: " + source_id)
            if not isinstance(row.get("canvasIdentity"), str) or not row["canvasIdentity"]:
                raise SpineNativePlanError("SkeletonGraphic context requires an exact canvasIdentity: " + source_id)
            required_roles.add("canvas-reference-pixels-per-unit")
        elif row.get("canvasReferencePixelsPerUnit") is not None or row.get("canvasIdentity") not in (None, ""):
            raise SpineNativePlanError("SkeletonAnimation context cannot declare a Canvas PPU: " + source_id)

        evidence_sources = row.get("evidenceSources")
        if not isinstance(evidence_sources, list):
            raise SpineNativePlanError("renderer context requires hash-pinned evidenceSources: " + source_id)
        roles = set()
        verified_sources = []
        for source in evidence_sources:
            if not isinstance(source, dict):
                raise SpineNativePlanError("renderer context evidence source must be an object: " + source_id)
            role, path_value, source_sha = source.get("role"), source.get("sourcePath"), source.get("sha256")
            if role not in {"target-node-transform", "canvas-reference-pixels-per-unit"} or role in roles:
                raise SpineNativePlanError("renderer context evidence role is missing, duplicated, or unsupported: " + source_id)
            if not isinstance(path_value, str) or not path_value:
                raise SpineNativePlanError("renderer context evidence sourcePath is required: " + source_id)
            _hash(source_sha, "rendererContext.evidenceSources.sha256")
            evidence_path = Path(path_value).expanduser()
            if not evidence_path.is_absolute():
                evidence_path = source_path.parent / evidence_path
            evidence_path = evidence_path.resolve(strict=True)
            evidence_raw = evidence_path.read_bytes()
            if len(evidence_raw) > 128 * 1024 * 1024 or hashlib.sha256(evidence_raw).hexdigest() != source_sha:
                raise SpineNativePlanError("renderer context evidence source bytes differ from SHA-256: " + role)
            roles.add(role)
            verified_sources.append({"role": role, "sourcePath": str(evidence_path), "sha256": source_sha})
        if not required_roles.issubset(roles):
            raise SpineNativePlanError("renderer context lacks exact transform/Canvas evidence: " + source_id)
        contexts[source_id] = dict(row, evidenceSources=verified_sources)
    receipt = {"status": "declared_not_native_readback", "contract": _RENDERER_CONTEXT_CONTRACT,
               "sourcePath": str(source_path), "sha256": expected_sha,
               "sourceManifestSha256": source_manifest_sha256, "normalizedIrSha256": normalized_ir_sha256,
               "nativeReadback": "not_run", "contextCount": len(contexts)}
    return contexts, receipt


def build_unity_native_binding_plan(emission: dict, material_contract: dict,
                                    unity_closure: dict, runtime_evidence: dict,
                                    runtime_stage_evidence: dict,
                                    target_unit_evidence: dict | None = None) -> dict:
    """Join frozen inputs with hash-pinned renderer/unit context evidence.

    Target renderer context remains a declared, exact-component input; it is
    not native Unity readback. SkeletonDataAsset.scale is derived from that
    context and the pinned source/target unit mapping, with conflicts left
    unresolved instead of receiving an implicit scale.
    """
    if emission.get("contract") != "monkey-spine-emission/1":
        raise SpineNativePlanError("unsupported Spine emission contract")
    if emission.get("sourceVersion") != "2.4.15":
        raise SpineNativePlanError("Cocos Spine source scale evidence applies only to the pinned 2.4.15 source profile")
    if material_contract.get("schema") != "monkey-spine-material-contract/1" or material_contract.get("profile") != PROFILE:
        raise SpineNativePlanError("unsupported Spine material contract/profile")
    if material_contract.get("creatorBindingStatus") != "source-semantics-exact-builtin-spine":
        raise SpineNativePlanError("Creator source material profile is not proven")
    pins = emission.get("pins")
    material_pins = material_contract.get("pins")
    if not isinstance(pins, dict) or not isinstance(material_pins, dict):
        raise SpineNativePlanError("source pins missing")
    for key in ("sourceManifestSha256", "normalizedIrSha256"):
        if _hash(pins.get(key), "emission." + key) != _hash(material_pins.get(key), "material." + key):
            raise SpineNativePlanError(f"source pin mismatch: {key}")

    comp_rows = _array(emission, "components")
    asset_rows = _array(emission, "assets")
    copy_rows = _array(emission, "copies")
    expected_count = emission.get("sourceComponentCount")
    if type(expected_count) is not int or expected_count != len(comp_rows) or expected_count < 1:
        raise SpineNativePlanError("frozen source component denominator mismatch")
    ids = [row.get("sourceComponentId") for row in comp_rows]
    if any(not isinstance(sid, str) or not sid for sid in ids) or len(set(ids)) != len(ids):
        raise SpineNativePlanError("missing or duplicate source component identity")
    data_by_id = {row.get("sourceId"): row for row in asset_rows}
    if len(data_by_id) != len(asset_rows) or any(not isinstance(key, str) for key in data_by_id):
        raise SpineNativePlanError("missing or duplicate source SkeletonData identity")
    closure_rows = _array(unity_closure, "skeletons")
    closure_by_id = {row.get("sourceId"): row for row in closure_rows}
    if len(closure_by_id) != len(closure_rows):
        raise SpineNativePlanError("duplicate Unity closure data identity")
    material_rows = material_contract.get("spec", {}).get("creator38", {}).get("perComponent")
    unity_material_rows = material_contract.get("spec", {}).get("unity", {}).get("perComponent")
    if not isinstance(material_rows, list) or not isinstance(unity_material_rows, list):
        raise SpineNativePlanError("material component maps missing")
    material_by_component = {row.get("sourceComponentId"): row for row in material_rows if isinstance(row, dict)}
    unity_material_by_component = {row.get("sourceComponentId"): row for row in unity_material_rows if isinstance(row, dict)}
    if set(material_by_component) != set(ids) or set(unity_material_by_component) != set(ids):
        raise SpineNativePlanError("material contract component denominator differs")
    shader_path = Path(__file__).resolve().parent / "targets/materials/spine/UnitySpineSourceProfile.shader"
    graphic_shader_path = Path(__file__).resolve().parent / "targets/materials/spine/UnitySpineGraphicProfile.shader"
    graphic_shader_sha = hashlib.sha256(graphic_shader_path.read_bytes()).hexdigest()
    shader_sha = hashlib.sha256(shader_path.read_bytes()).hexdigest()
    pinned_shader_sha = _hash(material_contract.get("spec", {}).get("unity", {}).get("shaderSourceSha256"),
                              "material.unity.shaderSourceSha256")
    if shader_sha != pinned_shader_sha:
        raise SpineNativePlanError("Unity Spine source-profile shader hash differs from material contract")

    runtime = runtime_evidence.get("unity", {}).get("spinePlugin", {})
    stage = runtime_stage_evidence
    runtime_checks = runtime.get("fileChecks", {})
    copied_checks = stage.get("copiedFiles", {})
    if (runtime.get("compiledAgainst") != "Unity6000.6.2f1" or not runtime_checks or not stage.get("verified") or
        runtime.get("manifestSha256") != stage.get("sourceManifestSha256")):
        raise SpineNativePlanError("Unity runtime/license evidence or isolated stage copy is unverified")
    for rel, row in runtime_checks.items():
        if not row.get("verified") or copied_checks.get(rel, {}).get("sha256") != row.get("expectedSha256"):
            raise SpineNativePlanError("isolated Spine runtime copy differs from verified source: " + rel)
    for required in ("spine-csharp.dll", "spine-unity.dll", "Shaders/Spine-SkeletonGraphic.shader", "LICENSE"):
        if required not in copied_checks:
            raise SpineNativePlanError("isolated runtime stage lacks required file: " + required)
    editor_variant = _verified_editor_variant(runtime, stage)

    unity_copies = {(row.get("sourceId"), row.get("path")): row for row in copy_rows
                    if row.get("target") == "unity"}
    if any(not row.get("path", "").startswith("Assets/") for row in unity_copies.values()):
        raise SpineNativePlanError("Unity Spine closure contains a non-Assets path")

    renderer_contexts, renderer_context_receipt = _load_renderer_contexts(
        target_unit_evidence, comp_rows, pins["sourceManifestSha256"], pins["normalizedIrSha256"])
    target_units = target_unit_evidence.get("targetUnitsPerSourcePixel") if isinstance(target_unit_evidence, dict) else None
    base_unit_mapping_verified = bool(
        isinstance(target_unit_evidence, dict) and target_unit_evidence.get("status") == "verified_unit_mapping" and
        target_units == 1.0 and target_unit_evidence.get("worldSpaceCanvasScale") == 1.0 and
        target_unit_evidence.get("pixelsPerUnitConversion") in (None, 1.0))
    scale_evidence = {
        "source": SOURCE_SCALE_EVIDENCE,
        "target": target_unit_evidence,
        "rendererContextEvidence": renderer_context_receipt,
        "status": "renderer_unit_mapping_pending",
        "resolvedSkeletonDataAssetScales": {},
    }
    if len(data_by_id) == 1:
        scale_evidence["resolvedSkeletonDataAssetScale"] = None
    if not isinstance(target_unit_evidence, dict):
        scale_evidence["status"] = "target_unit_evidence_missing"
    elif not base_unit_mapping_verified:
        scale_evidence["status"] = "target_unit_mapping_differs_or_is_unverified"

    # Verify the nonempty source _materials field is the exact known built-in
    # profile mapping, rather than rejecting all nonempty material references.
    source_material_reference = material_pins.get("materialReferenceSourceId")
    resolved_material_source = material_pins.get("materialSourceId")
    if not isinstance(source_material_reference, str) or not isinstance(resolved_material_source, str):
        raise SpineNativePlanError("source material identity pins are missing")

    components = []
    data_components: dict[str, list[dict]] = {}
    for component in comp_rows:
        sid = component["sourceComponentId"]
        source_data_id = component.get("sourceDataAssetId")
        material_binding = material_by_component[sid]
        expected_ref = material_binding.get("sourceMaterialReferenceSourceId")
        expected_target = material_binding.get("sourceMaterialSourceId")
        source_binding = material_binding.get("sourceMaterialBinding") or ({"status": "explicit"}
            if isinstance(expected_ref, str) and isinstance(expected_target, str) else {})
        material_state = source_binding.get("status")
        if material_state == "explicit":
            if expected_ref != source_material_reference or expected_target != resolved_material_source:
                raise SpineNativePlanError(f"component {sid} source material profile identity differs")
        elif material_state == "resolved_source_engine_default":
            if (expected_ref is not None or expected_target is not None
                    or source_binding.get("sourceEngineVersion") != "2.4.15"
                    or source_binding.get("sourcePath") != "extensions/spine/Skeleton.js"
                    or source_binding.get("sourceSha256") != "7cdc119e26aa6dceec4bd78ae30dd08f39daa2f0da5d914d2197a730b558a5e8"
                    or source_binding.get("method") != "Skeleton._getDefaultMaterial -> cc.Material.getBuiltinMaterial('2d-spine')"):
                raise SpineNativePlanError(f"component {sid} source engine default material evidence differs")
        else:
            raise SpineNativePlanError(f"component {sid} source material state is not supported")
        serialized_materials = component.get("sourceSerializedFields", {}).get("_materials", [])
        if serialized_materials is None:
            serialized_materials = []
        if not isinstance(serialized_materials, list):
            raise SpineNativePlanError(f"component {sid} has malformed serialized material references")
        actual_refs = [f"{component.get('sourcePrefabId', '').split(':', 1)[0]}:{row.get('__uuid__')}"
                       for row in serialized_materials if isinstance(row, dict) and isinstance(row.get("__uuid__"), str)]
        if material_state == "explicit":
            if actual_refs != [expected_ref]:
                raise SpineNativePlanError(f"component {sid} has missing/extra/changed serialized material references")
        elif "_materials" in component.get("sourceSerializedFields", {}):
            raise SpineNativePlanError(f"component {sid} source engine default is not backed by an omitted _materials field")

        creator = {
            "sourceMaterialReferenceSourceId": expected_ref,
            "sourceMaterialSourceId": expected_target,
            "targetMaterialUuid": material_contract["spec"]["creator38"]["targetMaterialUuid"],
            "sourceMaterialBinding": source_binding,
            "status": "exact_source_builtin_profile_mapping" if material_state == "explicit" else "resolved_source_engine_default",
        }
        unity_material = unity_material_by_component[sid]
        data_asset = data_by_id.get(source_data_id) if source_data_id else None
        if source_data_id and data_asset is None:
            raise SpineNativePlanError(f"component {sid} references unknown source SkeletonData {source_data_id}")
        if data_asset:
            data_components.setdefault(source_data_id, []).append(component)
        component_fields = component.get("unity", {}).get("fields", {})
        time_scale_field = component_fields.get("timeScale", {})
        time_scale_unity = time_scale_field.get("unity", {}) if isinstance(time_scale_field, dict) else {}
        source_time_scale_status = time_scale_unity.get("status")
        source_time_scale = time_scale_unity.get("value")
        source_time_scale_verified = (source_time_scale_status in ("explicit", "resolved_source_engine_default") and
                                      type(source_time_scale) in (int, float) and math.isfinite(float(source_time_scale)))
        field_bindings = []
        field_gaps = []
        for property_name, row in component_fields.items():
            unity_field = row.get("unity", {}) if isinstance(row, dict) else {}
            status = unity_field.get("status")
            member = unity_field.get("member")
            if status in ("explicit", "resolved_source_engine_default") and isinstance(member, str) and "value" in unity_field:
                value = unity_field["value"]
                if type(value) is bool:
                    value_type = "bool"; encoded = {"boolValue": value}
                elif type(value) in (int, float):
                    value_type = "number"; encoded = {"numberValue": float(value)}
                elif isinstance(value, str):
                    value_type = "string"; encoded = {"stringValue": value}
                else:
                    field_gaps.append({"sourceProperty": property_name, "status": "unsupported_static_value_type"})
                    continue
                field_bindings.append({"sourceProperty": property_name, "member": member,
                                       "status": status, "valueType": value_type, **encoded})
            elif (status in ("source_only_no_same_component_field", "source_only_runtime_cache_mapping_unresolved") or
                  (status == "no_equivalent_field" and row.get("sourceValue") not in (None, False, 0, ""))):
                field_gaps.append({"sourceProperty": property_name, "status": status})
        source_has_data = bool(source_data_id)
        context = renderer_contexts.get(sid)
        renderer_selection = {
            "status": "declared_not_native_readback" if context else "renderer_context_missing",
            "sourceComponentId": sid,
            "rendererKind": context.get("rendererKind") if context else None,
            "targetNodeTransform": context.get("targetNodeTransform") if context else None,
            "canvasIdentity": context.get("canvasIdentity") if context else None,
            "canvasReferencePixelsPerUnit": context.get("canvasReferencePixelsPerUnit") if context else None,
            "evidencePath": renderer_context_receipt.get("sourcePath"),
            "evidenceSha256": renderer_context_receipt.get("sha256"),
            "evidenceSources": context.get("evidenceSources", []) if context else [],
            "nativeRendererReadback": "pending",
        }
        components.append({
            "sourceComponentId": sid,
            "sourcePrefabId": component.get("sourcePrefabId"),
            "sourceNodeId": component.get("sourceNodeId"),
            "sourceNodePath": component.get("sourceNodePath"),
            "sourceDataAssetId": source_data_id,
            "sourceHasStaticDataReference": source_has_data,
            "sourceTimeScale": float(source_time_scale) if source_time_scale_verified else 0.0,
            "sourceTimeScaleVerified": source_time_scale_verified,
            "rendererSelection": renderer_selection,
            "rendererKind": "derive_from_target_node_transform",
            "creatorMaterialBinding": creator,
            "unityMaterialProfile": unity_material,
            "fields": {key: value.get("unity", {}) for key, value in component_fields.items()
                       if isinstance(value, dict)},
            "targetFieldBindings": field_bindings,
            "fieldGaps": field_gaps,
            "behavior": "disabled",
            "nativeRendererEnabled": True,
            "sourceBusinessBehaviorDisabled": True,
            "sourceCallbacksExecuted": False,
            "persistentVisiblePose": True,
            "nativeTimeScale": 0.0,
            "staticDataState": "exact_data_asset_required" if source_has_data else "source_uuid_absent_component_preserved_unbound",
        })

    data_assets = []
    diagnostics = []
    if not base_unit_mapping_verified:
        diagnostics.append({"code": "UNITY_SPINE_SCALE_EVIDENCE_MISSING",
                            "source": SOURCE_SCALE_EVIDENCE, "target": target_unit_evidence})
    for component in comp_rows:
        if component.get("sourceComponentId") not in renderer_contexts:
            diagnostics.append({"sourceId": component.get("sourceComponentId"),
                                "code": "UNITY_SPINE_RENDERER_UNIT_CONTEXT_MISSING"})
    for source_id, asset in data_by_id.items():
        rows = data_components.get(source_id, [])
        closure = closure_by_id.get(source_id)
        if not rows or closure is None or closure.get("status") != "closure_recovered":
            diagnostics.append({"sourceId": source_id, "code": "UNITY_SPINE_CLOSURE_UNAVAILABLE"})
            continue
        unity_asset = asset.get("unity", {})
        if unity_asset.get("candidateInputPath") != closure.get("skeletonPath") or unity_asset.get("atlasPath") != closure.get("atlasPath"):
            raise SpineNativePlanError(f"Unity closure path differs for source data {source_id}")
        if asset.get("sourceSkeletonSha256") != closure.get("sourceSkeletonSha256"):
            raise SpineNativePlanError(f"Unity closure binary hash differs for source data {source_id}")
        data_copy = unity_copies.get((source_id, closure.get("skeletonPath")))
        atlas_copy = unity_copies.get((source_id, closure.get("atlasPath")))
        if not data_copy or not atlas_copy or data_copy.get("sha256") != closure.get("sourceSkeletonSha256") or atlas_copy.get("sha256") != closure.get("sourceAtlasSha256"):
            raise SpineNativePlanError(f"Unity closure output receipt differs for source data {source_id}")

        profiles = [unity_material_by_component[row["sourceComponentId"]] for row in rows]
        if any(profile.get("status") != "profile-materials-defined" for profile in profiles):
            raise SpineNativePlanError(f"Unity material profile is unresolved for source data {source_id}")
        canonical_profiles = {json.dumps({k: profile.get(k) for k in ("pmaVertexColors", "sourceAtlasPages", "variants")}, sort_keys=True)
                              for profile in profiles}
        if len(canonical_profiles) != 1:
            raise SpineNativePlanError(f"shared source data {source_id} needs conflicting serialized material variants")
        profile = profiles[0]
        dependencies = {row.get("page"): row for row in closure.get("dependencies", []) if isinstance(row, dict)}
        if len(dependencies) != len(closure.get("dependencies", [])):
            raise SpineNativePlanError(f"source Atlas page identity is duplicate for {source_id}")

        stem = _asset_stem(closure["skeletonPath"])
        folder = str(Path(closure["skeletonPath"]).parent)
        key = _safe_key(source_id)
        page_specs = []
        for page in profile.get("sourceAtlasPages", []):
            source_page = page.get("pageName")
            dependency = dependencies.get(source_page)
            if dependency is None or page.get("sourceTextureSourceId") != dependency.get("sourceId"):
                raise SpineNativePlanError(f"source Atlas page/texture identity differs for {source_id}:{source_page}")
            target_page = dependency.get("targetPage")
            target_texture_path = f"{folder}/{target_page}"
            page_copy = unity_copies.get((source_id, target_texture_path))
            if page_copy is None:
                raise SpineNativePlanError(f"Unity page texture output missing for {source_id}:{target_page}")
            normal = f"Assets/Game/Content/Spine/GeneratedMaterials/{key}/{page.get('pageIndex')}_normal.mat"
            graphic_normal = f"Assets/Game/Content/Spine/GeneratedMaterials/{key}/{page.get('pageIndex')}_normal_graphic.mat"
            variants = []
            page_variant_modes = set((page.get("materialIdentitySeeds") or {}).keys())
            for variant in profile.get("variants", []):
                if variant.get("blendMode") == "normal": continue
                if variant.get("blendMode") not in page_variant_modes: continue
                if variant.get("sourceSlotCount", 0) <= 0: continue
                variants.append({"blendMode": variant["blendMode"],
                                 "sourceSlotCountAcrossAsset": variant["sourceSlotCount"],
                                 "sourceSlotCountScope": "whole_skeleton_atlas_pages_not_per_page_count",
                                 "materialAssetPath": f"Assets/Game/Content/Spine/GeneratedMaterials/{key}/{page.get('pageIndex')}_{variant['blendMode']}.mat",
                                 "graphicMaterialAssetPath": f"Assets/Game/Content/Spine/GeneratedMaterials/{key}/{page.get('pageIndex')}_{variant['blendMode']}_graphic.mat"})
            page_specs.append({"sourceAtlasPage": source_page, "nativeAtlasPage": target_page,
                               "sourceTextureSourceId": page["sourceTextureSourceId"],
                               "textureAssetPath": target_texture_path,
                               "textureSha256": page_copy["sha256"],
                               "normalMaterialAssetPath": normal, "graphicNormalMaterialAssetPath": graphic_normal,
                               "variants": variants})

        requested_animations = sorted({prop.get("sourceValue") for row in rows
                                       for prop in [row.get("unity", {}).get("fields", {}).get("animation", {})]
                                       if prop.get("status") in ("explicit", "resolved_source_engine_default") and prop.get("sourceValue")})
        requested_skins = sorted({prop.get("sourceValue") for row in rows
                                  for prop in [row.get("unity", {}).get("fields", {}).get("skin", {})]
                                  if prop.get("status") in ("explicit", "resolved_source_engine_default") and prop.get("sourceValue")})
        source_component_ids = [row["sourceComponentId"] for row in rows]
        component_contexts = [renderer_contexts.get(component_id) for component_id in source_component_ids]
        data_scale = None
        asset_scale_evidence = {
            "status": "renderer_unit_mapping_unverified",
            "source": SOURCE_SCALE_EVIDENCE,
            "targetUnitsPerSourcePixel": target_units,
            "rendererContextEvidence": renderer_context_receipt,
            "sourceDataAssetId": source_id,
            "sourceComponentIds": source_component_ids,
        }
        if any(context is None for context in component_contexts):
            diagnostics.append({"sourceId": source_id, "code": "UNITY_SPINE_RENDERER_UNIT_CONTEXT_MISSING",
                                "componentIds": [component_id for component_id, context in zip(source_component_ids, component_contexts)
                                                 if context is None]})
        elif base_unit_mapping_verified:
            signatures = {(context["rendererKind"], context.get("canvasReferencePixelsPerUnit"))
                          for context in component_contexts}
            if len(signatures) != 1:
                diagnostics.append({"sourceId": source_id, "code": "UNITY_SPINE_RENDERER_CONTEXT_CONFLICT",
                                    "componentIds": source_component_ids,
                                    "contexts": [{"sourceComponentId": component_id,
                                                  "rendererKind": context["rendererKind"],
                                                  "canvasReferencePixelsPerUnit": context.get("canvasReferencePixelsPerUnit")}
                                                 for component_id, context in zip(source_component_ids, component_contexts)]})
            else:
                renderer_kind, canvas_ppu = next(iter(signatures))
                divisor = canvas_ppu if renderer_kind == "SkeletonGraphic" else 1.0
                data_scale = SOURCE_SCALE_EVIDENCE["sourceDefaultScale"] * float(target_units) / float(divisor)
                formula = ("sourceDefaultScale * targetUnitsPerSourcePixel / canvasReferencePixelsPerUnit"
                           if renderer_kind == "SkeletonGraphic" else
                           "sourceDefaultScale * targetUnitsPerSourcePixel")
                asset_scale_evidence = {
                    "status": "verified_source_renderer_unit_mapping",
                    "formula": formula,
                    "source": SOURCE_SCALE_EVIDENCE,
                    "targetUnitsPerSourcePixel": target_units,
                    "rendererKind": renderer_kind,
                    "canvasReferencePixelsPerUnit": canvas_ppu,
                    "rendererContexts": [
                        {"sourceComponentId": component_id,
                         "rendererKind": context["rendererKind"],
                         "targetNodeTransform": context["targetNodeTransform"],
                         "canvasIdentity": context.get("canvasIdentity"),
                         "canvasReferencePixelsPerUnit": context.get("canvasReferencePixelsPerUnit"),
                         "evidenceSources": context["evidenceSources"]}
                        for component_id, context in zip(source_component_ids, component_contexts)],
                    "rendererContextEvidence": renderer_context_receipt,
                    "resolvedSkeletonDataAssetScale": data_scale,
                }
                scale_evidence["resolvedSkeletonDataAssetScales"][source_id] = data_scale
        else:
            asset_scale_evidence["status"] = "target_unit_mapping_differs_or_is_unverified"
        if data_scale is None and source_id not in scale_evidence["resolvedSkeletonDataAssetScales"]:
            scale_evidence["resolvedSkeletonDataAssetScales"][source_id] = None
        factory_input = {
            "sourceAssetId": source_id,
            "sourceSpineVersion": asset.get("sourceSpineVersion"),
            "skeletonTextAssetPath": closure["skeletonPath"], "skeletonSha256": closure["sourceSkeletonSha256"],
            "atlasTextAssetPath": closure["atlasPath"], "atlasSha256": closure["sourceAtlasSha256"],
            "atlasAssetPath": f"{folder}/{stem}_SpineAtlas.asset",
            "skeletonDataAssetPath": f"{folder}/{stem}_SkeletonData.asset",
            "shaderName": SHADER, "shaderAssetPath": "Assets/Game/Content/Shaders/UnitySpineSourceProfile.shader",
            "shaderSha256": material_contract.get("spec", {}).get("unity", {}).get("shaderSourceSha256"),
            "graphicShaderName": "Monkey/SpineSourceGraphicProfile/Colored",
            "graphicShaderAssetPath": "Assets/Game/Content/Shaders/UnitySpineGraphicProfile.shader",
            "graphicShaderSha256": graphic_shader_sha,
            "premultipliedAlpha": profile.get("pmaVertexColors"),
            "scale": data_scale,
            "expectedSpineVersion": asset.get("sourceSpineVersion"),
            "pages": page_specs, "requiredAnimations": requested_animations, "requiredSkins": requested_skins,
        }
        data_assets.append({**factory_input, "factoryInput": factory_input,
                            "scaleEvidence": asset_scale_evidence,
                            "nativeDataAssetGuid": None, "nativeAssetReadback": "pending_unity_asset_database_import"})

    resolved_scales = scale_evidence["resolvedSkeletonDataAssetScales"]
    all_scales_verified = (len(resolved_scales) == len(data_by_id) and
                           all(_finite_positive(value) for value in resolved_scales.values()))
    if all_scales_verified:
        scale_evidence["status"] = "verified_source_renderer_unit_mapping"
    elif base_unit_mapping_verified:
        scale_evidence["status"] = "renderer_unit_mapping_unverified"
    if len(resolved_scales) == 1:
        scale_evidence["resolvedSkeletonDataAssetScale"] = next(iter(resolved_scales.values()))

    if len(data_assets) != len(data_by_id):
        diagnostics.append({"code": "UNITY_SPINE_DATA_ASSET_COUNT_INCOMPLETE", "expected": len(data_by_id), "planned": len(data_assets)})
    return {
        "schemaVersion": 1,
        "contract": "monkey-spine-native-binding/1",
        "sourceManifestSha256": pins["sourceManifestSha256"],
        "normalizedIrSha256": pins["normalizedIrSha256"],
        "runtime": {"sourceVersion": runtime.get("sourceVersion"), "upstreamCommit": runtime.get("upstreamCommit"),
                    "compiledAgainst": runtime.get("compiledAgainst"),
                    "isolatedStagePath": stage.get("destination"), "manifestSha256": stage.get("sourceManifestSha256"),
                    "runtimeFilesVerified": len(copied_checks), "licenseIncluded": "LICENSE" in copied_checks,
                    "targetCandidatePath": "Assets/Plugins/Spine38", "editorImport": "not_run",
                    "editorVariant": editor_variant},
        "sourceMaterialProfile": {"sourceReferenceSourceId": source_material_reference,
                                  "resolvedSourceMaterialId": resolved_material_source,
                                  "creatorTargetMaterialUuid": material_contract["spec"]["creator38"]["targetMaterialUuid"],
                                  "creatorMappingStatus": "exact_source_builtin_profile_mapping"},
        "unityShader": {"sourcePath": str(shader_path),
                        "targetPath": "Assets/Game/Content/Shaders/UnitySpineSourceProfile.shader",
                        "shaderName": SHADER, "sha256": shader_sha, "status": "source_hash_verified_target_copy_required"},
        "unityGraphicShader": {"sourcePath": str(graphic_shader_path),
                               "targetPath": "Assets/Game/Content/Shaders/UnitySpineGraphicProfile.shader",
                               "shaderName": "Monkey/SpineSourceGraphicProfile/Colored",
                               "sha256": graphic_shader_sha, "status": "native_ui_shader_source_hash_verified"},
        "unityFactoryContract": {
            "helperPath": "src/grea/recovery/targets/spine/UnitySpineNativeFactory.cs",
            "stageHelperPath": "src/grea/recovery/targets/spine/UnitySpineNativeStage.cs",
            "createDataAsset": "UnitySpineNativeFactory.CreateDataAsset(DataAssetSpec) -> DataAssetReadback",
            "createComponent": "UnitySpineNativeFactory.CreateComponent(node, sourceComponentId, rendererKind)",
            "apply": "UnitySpineNativeFactory.ApplyComponent(component, sourceComponentId, sourceDataAssetId, exactDataAsset, explicitTargetFields, sourceHasStaticDataReference, exactDataAssetReadback)",
            "savedReadback": "UnitySpineNativeFactory.ReadComponent(sourceComponentId, sourceDataAssetId, savedComponent, exactDataAsset, sourceHasStaticDataReference, expectedTargetFields, exactDataAssetReadback)",
            "rendererKind": "must be selected from the actual created target node type; SkeletonGraphic requires RectTransform",
            "disabled": True,
            "unboundSourceData": "create the native renderer with null data and retain dynamic_assignment_unverified gap",
            "initialPose": "optional SampleInitialPoseAtZero; no Update/event queue/source code/full timeline",
        },
        "scaleEvidence": scale_evidence,
        "componentCount": len(components), "sourceStaticDataBoundCount": sum(bool(row["sourceHasStaticDataReference"]) for row in components),
        "sourceStaticDataUnboundCount": sum(not row["sourceHasStaticDataReference"] for row in components),
        "dataAssetCount": len(data_assets), "components": components, "dataAssets": data_assets,
        "diagnostics": diagnostics,
        "nativeImport": "not_run", "sourceCodeExecuted": False, "dynamicAnimationTimeline": "not_implemented",
        "persistentVisiblePose": True,
        "visualPolicy": "native_renderer_enabled_timeScale_zero_source_timeScale_retained",
        "persistentVisiblePoseEvidence": PERSISTENT_VISIBLE_POSE_EVIDENCE,
    }


def write_unity_native_binding_plan(plan: dict, path: str | Path) -> str:
    raw = (json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()
