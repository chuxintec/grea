"""Offline harness for the production text-slot lifecycle against actual17 inventory.

Unity/TMP objects are represented by deterministic providers. The checked
production call chain and lifecycle hash/denominator code are extracted from
the current C# source, while the fixture supplies only source identities and
the previously observed slot inventory. It does not claim TMP rendering or
Editor persistence was executed.
"""
from __future__ import annotations

import hashlib
import collections
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = ROOT / ".private/foodstreet-four-activity-20261104/dev23-text-slot-lifecycle/actual17-text-lifecycle-inventory.json"
DEFAULT_ACTUAL18_FAILURE = ROOT / ".private/foodstreet-four-activity-20261104/dev24-text-context-capture/actual18-text-context-failure.json"
DEFAULT_SAVED_TEXT_CONTEXTS = ROOT / ".private/foodstreet-four-activity-20261104/dev24-text-context-capture/actual17-saved-text-contexts.json"
DEFAULT_ACTUAL19_FAILURE = Path("/Users/wangmeng/MyProjects/Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-native-19-dev24/provider-output/UnityProject/Analysis/Readback/StaticSortTextCapture/bf29560baaf53dca5a378d073b0431da7e28a4c5209d18f557722c0c31351b52-33be207229f64e30a2eeac55696ddc5c.json")
DEFAULT_ACTUAL19_INDEX = Path("/Users/wangmeng/MyProjects/Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-native-19-dev24-index.json")


def _declaration(source: str, signature: str) -> str:
    start = source.index(signature)
    opening = source.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
        end += 1
    return source[start:end]


def _member(source: str, signature: str) -> str:
    """Extract a block or expression-bodied C# member without consuming its neighbors."""
    start = source.index(signature)
    arrow = source.find("=>", start)
    opening = source.find("{", start)
    if arrow >= 0 and (opening < 0 or arrow < opening):
        return source[start:source.index(";", arrow) + 1]
    return _declaration(source, signature)


def _inventory_path() -> Path:
    return Path(os.environ.get("MONKEY_ACTUAL17_TEXT_INVENTORY", DEFAULT_INVENTORY))


def _inventory():
    path = _inventory_path()
    if not path.is_file():
        pytest.skip("actual17 read-only inventory fixture is not present")
    return path, json.loads(path.read_text(encoding="utf-8"))


def _verify_readonly_pins(inv):
    failures = []
    for pin in inv["pins"]:
        path = Path(pin["path"])
        if not path.is_file():
            failures.append((str(path), "missing"))
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != pin["sha256"]:
            failures.append((str(path), digest))
    return failures


def _verify_actual18_pins(fixture):
    failures = []
    for pin in fixture["inputPins"]:
        path = Path(pin["path"])
        if not path.is_file():
            failures.append((str(path), "missing"))
        elif hashlib.sha256(path.read_bytes()).hexdigest() != pin["sha256"]:
            failures.append((str(path), "changed"))
    return failures


def _yaml_ref(block: str, field: str):
    match = re.search(rf"^  {re.escape(field)}: \{{fileID: (-?\d+)(?:, guid: ([^,}}]*), type: \d+)?\}}$", block, re.MULTILINE)
    if not match:
        return None
    return {"localFileId": int(match.group(1)), "guid": match.group(2) or None}


def _yaml_scalar(block: str, field: str):
    match = re.search(rf"^  {re.escape(field)}: ?(.*)$", block, re.MULTILINE)
    return match.group(1).strip() if match else None


def _saved_text_source_yaml_block(project_root: Path, prefab_relative: str, source_id: str, slot: int):
    prefab = project_root / prefab_relative
    text = prefab.read_text(encoding="utf-8")
    docs = re.split(r"(?=^--- !u!\d+ &)", text, flags=re.MULTILINE)
    matches = []
    for doc in docs:
        if "Assembly-CSharp::Monkey.StaticSortQueueProxy.NativeStaticSortTextSource" not in doc:
            continue
        if re.search(rf"^  sourceComponentId: {re.escape(source_id)}$", doc, re.MULTILINE) is None:
            continue
        if re.search(rf"^  materialSlot: {slot}$", doc, re.MULTILINE) is None:
            continue
        matches.append(doc)
    if len(matches) != 1:
        raise AssertionError(f"expected one saved text source row for {source_id} slot {slot}, found {len(matches)}")
    return matches[0]


def _font_asset_metadata(project_root: Path, asset_paths):
    metadata = {}
    for relative in asset_paths:
        path = project_root / relative
        text = path.read_text(encoding="utf-8", errors="ignore")
        meta = path.with_suffix(path.suffix + ".meta").read_text(encoding="utf-8", errors="ignore")
        guid_match = re.search(r"^guid: ([0-9a-fA-F]{32})$", meta, re.MULTILINE)
        mode_match = re.search(r"^  m_AtlasRenderMode: (-?\d+)\s*$", text, re.MULTILINE)
        if not guid_match or not mode_match:
            continue
        metadata[guid_match.group(1)] = {"path": relative, "renderMode": int(mode_match.group(1)),
                                         "assetSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                         "metaSha256": hashlib.sha256(path.with_suffix(path.suffix + ".meta").read_bytes()).hexdigest()}
    return metadata


def _asset_file_index(project_root: Path):
    result = {}
    assets = project_root / "Assets"
    for meta_path in assets.rglob("*.meta"):
        meta_bytes = meta_path.read_bytes()
        match = re.search(rb"^guid: ([0-9a-fA-F]{32})$", meta_bytes, re.MULTILINE)
        if not match:
            continue
        asset_path = meta_path.with_suffix("")
        if asset_path.is_file():
            result[match.group(1).decode("ascii")] = {
                "path": asset_path.relative_to(project_root).as_posix(),
                "assetSha256": hashlib.sha256(asset_path.read_bytes()).hexdigest(),
                "metaSha256": hashlib.sha256(meta_bytes).hexdigest(),
            }
    return result


def _role_matrix_input(inventory, saved, actual19, saved_project_root: Path, actual19_project_root: Path):
    source_groups = {row["sourceLabelId"]: row for row in inventory["textGroups"]}
    enum_by_source = {}
    slot_evidence_by_source_slot = {}
    for readback in inventory["slotReadbacks"]:
        enum_by_source.setdefault(readback["sourceComponentId"], readback["enumeration"])
        if isinstance(readback.get("slotEvidence"), dict):
            slot_evidence_by_source_slot[(readback["sourceComponentId"], readback["materialSlot"])] = readback["slotEvidence"]
    saved_by_source_slot = {(row["sourceComponentId"], row["materialSlot"]): row for row in saved["rows"]}
    asset_paths = {path for group in inventory["textGroups"] for path in group.get("nativeFontAssetPaths", [])}
    asset_meta = _font_asset_metadata(saved_project_root, sorted(asset_paths))
    actual19_font_path = "Assets/Game/Content/Fonts/FontGYM/FontGYM.asset"
    asset_meta_19 = _font_asset_metadata(actual19_project_root, [actual19_font_path])
    assets17 = _asset_file_index(saved_project_root)
    assets19 = _asset_file_index(actual19_project_root)
    actual19_font_meta = next(iter(asset_meta_19.values()), {})
    font_asset_pins = {row["path"]: {"assetSha256": row["assetSha256"], "metaSha256": row["metaSha256"]}
                       for row in asset_meta.values()}
    actual19_font_pins = ({actual19_font_path: {"assetSha256": actual19_font_meta["assetSha256"],
                                               "metaSha256": actual19_font_meta["metaSha256"]}}
                          if actual19_font_meta else {})
    role_rows = []
    empty_routes = []
    unresolved_rows = []
    observed_roles = collections.Counter()
    registration_rows = collections.Counter()
    for source_id in inventory["queueRendererSourceIds"]:
        group = source_groups[source_id]
        enumeration = enum_by_source.get(source_id)
        if enumeration is None:
            unresolved_rows.append({"sourceComponentId": source_id, "sourceFontKind": group["fontKind"], "reason": "no-prior-slot-readback-or-persistent-owner-refs"})
            continue
        for slot_row in enumeration["rows"]:
            if slot_row["disposition"] == "empty-placeholder":
                empty_routes.append({"sourceComponentId": source_id, "slot": slot_row["slot"], "sourceFontKind": group["fontKind"], "role": "empty-placeholder"})
                continue
            saved_row = saved_by_source_slot.get((source_id, slot_row["slot"]))
            if saved_row is None:
                unresolved_rows.append({"sourceComponentId": source_id, "slot": slot_row["slot"], "sourceFontKind": group["fontKind"], "reason": "no-saved-native-owner-profile"})
                continue
            identity = saved_row["sourceIdentityAndResourceIds"]
            owner_refs = saved_row["sourceOwnerSerializedFontAndMaterial"] or {}
            block = _saved_text_source_yaml_block(saved_project_root, saved_row["sourcePrefabPath"], source_id, slot_row["slot"])
            source_material = identity["sourceMaterial"]
            owner_material = identity["ownerFontMaterial"]
            fallback_font = identity["fallbackFontAsset"]
            fallback_material = identity["fallbackFontMaterial"]
            if source_material["guid"] == owner_material["guid"] and source_material["localFileId"] == owner_material["localFileId"]:
                role = "primary-font"
            elif fallback_font["guid"] and fallback_material["guid"] and not source_material["guid"] and source_material["localFileId"] == 0:
                role = "fallback-font-transient"
            elif fallback_font["guid"] and fallback_material["guid"] and source_material["guid"] and source_material["localFileId"] != 0:
                role = "fallback-font-persistent"
            elif identity["serializedSlotSpriteAsset"]["guid"]:
                role = "sprite"
            else:
                unresolved_rows.append({"sourceComponentId": source_id, "slot": slot_row["slot"], "sourceFontKind": group["fontKind"], "reason": "role-refs-do-not-close"})
                continue
            observed_roles[role] += 1
            owner_font_ref = owner_refs.get("fontAssetRef") or {"guid": enumeration["rows"][0]["sourceAssetGuid"], "fileID": enumeration["rows"][0]["sourceAssetLocalFileId"]}
            group_meta = asset_meta.get(owner_font_ref["guid"], {})
            slot_meta = asset_meta.get(identity["serializedSlotFontAsset"]["guid"], {})
            # Normalize this same prefab's typed native references into a temporary DTO.
            normalized_enum = json.loads(json.dumps(enumeration))
            normalized_enum["evidenceContract"] = "monkey-static-sort-text-slot-enumeration/2"
            for normalized_row in normalized_enum["rows"]:
                normalized_row["evidenceContract"] = "monkey-static-sort-text-slot-evidence/2"
            target_row = normalized_enum["rows"][slot_row["slot"]]
            target_row["sourceGraphicMaterialGuid"] = source_material["guid"]
            target_row["sourceGraphicMaterialLocalFileId"] = source_material["localFileId"]
            target_row["sourceGraphicMaterialFingerprint"] = source_material["fingerprint"]
            role_rows.append({
                "sourceComponentId": source_id, "sourceText": group["sourceText"], "sourceFontKind": group["fontKind"],
                "slot": slot_row["slot"], "expectedRole": role, "enumeration": normalized_enum,
                "sourceOutlineEnabled": bool(group["sourceOutlineEnabled"]), "sourceOutlineId": group.get("sourceOutlineId"),
                "ownerFont": {"guid": owner_font_ref["guid"], "localFileId": owner_font_ref["fileID"], "path": group_meta.get("path"), "renderMode": group_meta.get("renderMode")},
                "ownerMaterial": {**owner_material, "path": assets17.get(owner_material["guid"], {}).get("path")},
                "slotFont": {"guid": identity["serializedSlotFontAsset"]["guid"], "localFileId": identity["serializedSlotFontAsset"]["localFileId"], "path": slot_meta.get("path"), "renderMode": slot_meta.get("renderMode")},
                "fallbackFont": {**fallback_font, "path": assets17.get(fallback_font["guid"], {}).get("path")},
                "fallbackMaterial": {**fallback_material, "path": assets17.get(fallback_material["guid"], {}).get("path")},
                "sourceMaterial": {**source_material, "path": assets17.get(source_material["guid"], {}).get("path")},
                "sourceTexture": {**identity["sourceTexture"], "path": assets17.get(identity["sourceTexture"]["guid"], {}).get("path")},
                "sourceShader": identity["sourceShader"],
                "textInfoCharacterMaterialFingerprint": slot_evidence_by_source_slot.get(
                    (source_id, slot_row["slot"]), {}).get("textInfoCharacterMaterialFingerprint"),
                "spriteAsset": identity["serializedSlotSpriteAsset"],
                "nativeSourceSlot": {"generatedSubmesh": _yaml_scalar(block, "generatedSubmesh") == "1",
                                     "tmpFallbackMaterialBaked": _yaml_scalar(block, "tmpFallbackMaterialBaked") == "1",
                                     "persistentFallbackVariantRegistered": _yaml_scalar(block, "persistentFallbackVariantRegistered") == "1",
                                     "bakedProxyMaterial": _yaml_ref(block, "proxyMaterial"),
                                     "bakedProxyMaterialGuid": _yaml_scalar(block, "bakedProxyMaterialGuid"),
                                     "bakedProxyMaterialLocalFileId": int(_yaml_scalar(block, "bakedProxyMaterialLocalFileId") or 0),
                                     "bakedProxyMaterialFingerprint": _yaml_scalar(block, "bakedProxyMaterialFingerprint"),
                                     "bakedProxyMaterialPath": assets17.get((_yaml_ref(block, "proxyMaterial") or {}).get("guid"), {}).get("path"),
                                     "tmpFallbackAlgorithm": _yaml_scalar(block, "tmpFallbackAlgorithm")},
            })
            if role == "fallback-font-transient":
                registration_rows["registered" if _yaml_scalar(block, "persistentFallbackVariantRegistered") == "1" else "skipped"] += 1

    actual_enum = actual19["expectedEnumeration"]
    actual_row = actual_enum["rows"][0]
    lifecycle = actual19["lifecycle"]
    actual19_row = {
        "sourceComponentId": actual19["sourceComponentId"], "sourceText": source_groups[actual19["sourceComponentId"]]["sourceText"],
        "sourceFontKind": "bitmap-font", "slot": 0, "expectedRole": "primary-font", "enumeration": actual_enum,
        "sourceOutlineEnabled": False, "sourceOutlineId": None,
        "ownerFont": {"guid": lifecycle["ownerFontAssetGuid"], "localFileId": lifecycle["ownerFontAssetLocalFileId"],
                      "path": actual19_font_path, "renderMode": actual19_font_meta.get("renderMode")},
        "ownerMaterial": {"guid": lifecycle["ownerFontMaterialGuid"], "localFileId": lifecycle["ownerFontMaterialLocalFileId"],
                          "fingerprint": lifecycle["ownerFontMaterialFingerprint"], "path": assets19.get(lifecycle["ownerFontMaterialGuid"], {}).get("path")},
        "slotFont": {"guid": actual_row["sourceAssetGuid"], "localFileId": actual_row["sourceAssetLocalFileId"],
                     "path": actual19_font_path, "renderMode": actual19_font_meta.get("renderMode")},
        "fallbackFont": {"guid": None, "localFileId": 0, "path": None}, "fallbackMaterial": {"guid": None, "localFileId": 0, "fingerprint": None, "path": None},
        "sourceMaterial": {"guid": actual_row["sourceGraphicMaterialGuid"], "localFileId": actual_row["sourceGraphicMaterialLocalFileId"],
                           "fingerprint": actual_row["sourceGraphicMaterialFingerprint"], "path": assets19.get(actual_row["sourceGraphicMaterialGuid"], {}).get("path")},
        "sourceTexture": {"guid": actual_row["sourceTextureGuid"], "localFileId": actual_row["sourceTextureLocalFileId"], "path": assets19.get(actual_row["sourceTextureGuid"], {}).get("path")},
        "sourceShader": {"guid": actual_row["sourceShaderGuid"], "localFileId": actual_row["sourceShaderLocalFileId"], "fingerprint": None},
        "spriteAsset": {"guid": None, "localFileId": 0},
        "nativeSourceSlot": {"generatedSubmesh": False, "tmpFallbackMaterialBaked": False,
                             "persistentFallbackVariantRegistered": False, "bakedProxyMaterial": None,
                             "bakedProxyMaterialGuid": actual_row["sourceGraphicMaterialGuid"],
                             "bakedProxyMaterialLocalFileId": actual_row["sourceGraphicMaterialLocalFileId"],
                             "bakedProxyMaterialFingerprint": actual_row["sourceGraphicMaterialFingerprint"],
                             "bakedProxyMaterialPath": assets19.get(actual_row["sourceGraphicMaterialGuid"], {}).get("path"),
                             "tmpFallbackAlgorithm": None},
        "actual19Failure": {"code": actual19["code"], "phase": actual19["phase"], "diagnostic": actual19["diagnostic"]},
    }
    role_rows.append(actual19_row)
    return {"contract": "monkey-text-slot-role-matrix-input/1", "queueSourceCount": len(inventory["queueRendererSourceIds"]),
            "fontAssetPins": {"actual17": font_asset_pins, "actual19": actual19_font_pins},
            "assetFilePins": {"actual17": assets17, "actual19": assets19},
            "queueSourceIds": inventory["queueRendererSourceIds"], "sourceFontKindCounts": dict(collections.Counter(source_groups[s]["fontKind"] for s in inventory["queueRendererSourceIds"])),
            "observedDrawableRoleCounts": dict(observed_roles), "observedTransientRegistrationOutcomes": dict(registration_rows),
            "emptySlotRoutes": empty_routes, "unresolvedRows": unresolved_rows, "roleRows": role_rows}


def _normalize_saved_context_fixture(source: Path, output: Path):
    """Decode Unity YAML bool/int-array scalar forms for the in-memory DTO adapter."""
    fixture = json.loads(source.read_text(encoding="utf-8"))
    bool_fields = (
        "worldCameraAssigned", "ownerAutoSizing", "textLineBoxPresent", "textLineBoxActive",
        "contentSizeFitterPresent", "contentSizeFitterActive", "textLineBoxHeightProvenanceVerified",
        "autoSizing", "extraPadding", "richText", "parseControlCharacters", "rightToLeft",
        "useMaxVisibleDescender", "visible", "usingAlternateTypeface",
    )
    rows = []
    for row in fixture["rows"]:
        context = json.loads(json.dumps(row["textScaleContext"]))
        for field in bool_fields:
            if field in context:
                context[field] = bool(context[field])
            if field in context.get("textLayoutInputs", {}):
                context["textLayoutInputs"][field] = bool(context["textLayoutInputs"][field])
        raw_features = context["textLayoutInputs"].get("fontFeatures")
        if isinstance(raw_features, str) and raw_features.endswith("i"):
            raw_hex = raw_features[:-1]
            if not raw_hex or len(raw_hex) % 2:
                raise ValueError(f"unsupported Unity packed fontFeatures value: {raw_features}")
            context["textLayoutInputs"]["fontFeatures"] = [int.from_bytes(bytes.fromhex(raw_hex), "little", signed=True)]
        elif raw_features is None:
            context["textLayoutInputs"]["fontFeatures"] = []
        elif not isinstance(raw_features, list):
            raise ValueError(f"unsupported fontFeatures shape: {type(raw_features).__name__}")
        authored_height = context["textLayoutInputs"].get("textLineBoxAuthoredPreferredHeight")
        if authored_height is not None and not isinstance(authored_height, str):
            context["textLayoutInputs"]["textLineBoxAuthoredPreferredHeight"] = format(float(authored_height), ".17g")
        for character in context.get("characters", []):
            for field in ("visible", "usingAlternateTypeface"):
                character[field] = bool(character[field])
        rows.append({"sourceComponentId": row["sourceComponentId"], "materialSlot": row["materialSlot"],
                     "textScaleContext": context})
    output.write_text(json.dumps({"contract": "monkey-actual17-context-operands-adapter/1",
                                  "sourceFixtureSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                                  "fontFeaturesDecode": "Unity little-endian signed int32 bytes plus i postfix",
                                  "storedEvidenceHashesAreNotUsedAsCurrentEvidence": True,
                                  "rows": rows}, indent=2) + "\n", encoding="utf-8")


def _csharp_program(proxy_source: str, text_source: str, native_source: str) -> str:
    capture_method = _declaration(proxy_source, "static List<TextSlotBinding> CaptureAndRebindTextSlots(")
    # The 87-row operand harness uses a deterministic material-profile and
    # registration provider. Exact production classification/registration are
    # executed by the separate role matrix path in this same generated program.
    capture_method = capture_method.replace(
        "UnityStaticSortTextSource.RegisterCapturedFallbackVariant(binding,",
        "UnityStaticSortTextSource.RegisterCapturedFallbackVariantForModeledLifecycle(binding,",
    )
    proxy_helpers = "\n".join(_declaration(proxy_source, s) for s in (
        "static bool CaptureOwnerSourceStateMatches(",
        "static KeyValuePair<string, long> CapturePersistentUnityIdentity(",
        "static string IdentitySummary(",
        "static bool TextBindingPersistentReferencesVerified(",
        "static bool CapturedTextSlotSourceIdentityMatches(",
        "static string TextSlotBindingSummary(",
        "static InvalidOperationException TextSlotCaptureRefusal(",
        "static string TextSlotEnumerationSummary(",
        "static void ValidateTextSlotEnumeration(",
        "static bool SameTextSlotEnumeration(",
        "static bool IsExactEmptyTextSource(",
        "static bool CarryTextCaptureRoutes(",
    ))
    # These are the production lifecycle builder, verifier and source-denominator
    # methods. The harness provider supplies only TMP/Unity object operations.
    text_methods = "\n".join(_member(text_source, s) for s in (
        "static string HashText(",
        "static NativeStaticSortTextLayoutEvidence TextLayoutEvidence(",
        "static decimal? DecimalFloat(",
        "static string TextLineBoxSemanticHeight(",
        "static bool HasVerifiedTextLineBoxHeight(",
        "static string TextLayoutEvidenceSha256(",
        "static string FloatEvidence(",
        "static bool Finite(",
        "static void AppendVector(",
        "static int UvDimension(",
        "static bool TryBuildTextScaleContext(",
        "static bool IsValidTextScaleContext(",
        "static bool TextScaleContextUvMatchesMesh(",
        "static float ComputeTmpUvScale(",
        "static bool VerifyTextScaleFormulaAgainstMesh(",
        "public static bool CaptureCurrentTextScaleContext(",
        "public static string MeshFingerprint(",
        "public static NativeStaticSortTextCaptureLifecycle BeginCaptureLifecycle(",
        "public static NativeStaticSortTextCapturePhase CaptureLifecyclePhase(",
        "public static void AppendCaptureLifecyclePhase(",
        "static NativeStaticSortTextCaptureSlot CaptureLifecycleSlot(",
        "public static bool TextSlotDenominatorMatches(",
        "public static int[] TextSlotDrawableIds(",
        "static string TextSlotEvidenceSummary(",
        "public static bool TextLayoutContextMatches(",
        "static string TextLayoutEvidenceDifference(",
        "public static bool ValidateCapturedSlotTransition(",
        "static string SlotBindingTransitionSummary(",
        "public static bool CaptureLifecycleReadyForRebind(",
        "public static string CaptureLifecycleHash(",
        "public static bool ValidateCaptureLifecycle(",
        "static bool CapturePhaseSlotsMatchEnumeration(",
        "public static bool FinalizeCaptureLifecycle(",
        "static bool PersistentAsset(",
        "static bool AssetIdentity(",
        "static bool CaptureFallbackMaterial(TextSlotBinding binding, string persistentAssetPath,\n            bool registerPersistentVariants, out string diagnostic)",
        "static bool PersistentAssetPath(",
        "static bool CapturedMaterialIdentityMatches(",
        "public static bool TryClassifyCaptureSlotRole(",
        "static void SetRegistrationRoute(",
        "static bool RequiresFallbackVariantRegistration(",
        "static string RegistrationSkipReason(",
        "static void SetDesiredRegistrationRoute(",
        "static void SetRegistrationRouteAfterProfile(",
        "public static bool RegisterCapturedFallbackVariant(",
        "public static bool CarryCaptureSlotRoute(",
        "static bool EmptySlotRoutesMatch(",
        "static string ExpectedRegistrationSkipReason(",
        "static bool CaptureLifecycleRoutesMatch(",
        "static string TextSlotRowHash(",
        "static string TextSlotEnumerationHash(",
        "static bool IsValidTextSlotEnumeration(",
        "static bool IsSha256(",
    ))
    native_types = "\n".join(_declaration(native_source, s) for s in (
        "public sealed class NativeStaticSortTextSlotEvidence",
        "public sealed class NativeStaticSortTextSlotEnumeration",
        "public sealed class NativeStaticSortTextCaptureLifecycle",
        "public sealed class NativeStaticSortTextCapturePhase",
        "public sealed class NativeStaticSortTextCaptureSlot",
        "public sealed class NativeStaticSortTextCaptureRoute",
        "public sealed class NativeStaticSortTextScaleContext",
        "public sealed class NativeStaticSortTextLayoutEvidence",
        "public sealed class NativeStaticSortTextScaleCharacter",
    ))
    return r'''#nullable disable
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Reflection;
using Monkey.StaticSortQueueProxy;
using Monkey.StaticMaskSort;
using TMPro;
using UnityEngine;
using UnityEditor;
using UnityEngine.UI;
using UnityEngine.Rendering;

namespace Monkey.StaticSortQueueProxy {
''' + native_types + r'''
public sealed class TextSlotBinding {
 public string sourceComponentId,sourceTextSha256,textInfoCharacterEvidenceSha256,textInfoCharacterAssetEvidenceSha256,
  textInfoCharacterMaterialFingerprint,sourceMeshSha256,sourceTextureGuid,sourceMaterialGuid,sourceShaderGuid,
  fontAssetGuid,spriteAssetGuid,ownerFontMaterialGuid,ownerFontMaterialFingerprint,fallbackFontAssetGuid,
  fallbackFontMaterialGuid,fallbackFontMaterialFingerprint,fallbackAtlasGuid,transientFallbackFingerprint,
  sourceMaterialFingerprint,proxyMaterialFingerprint,proxyMaterialGuid,bakedProxyMaterialFingerprint,bakedProxyMaterialGuid;
 public long sourceTextureLocalFileId,sourceMaterialLocalFileId,sourceShaderLocalFileId,fontAssetLocalFileId,
  spriteAssetLocalFileId,ownerFontMaterialLocalFileId,fallbackFontAssetLocalFileId,fallbackFontMaterialLocalFileId,
  fallbackAtlasLocalFileId,proxyMaterialLocalFileId,bakedProxyMaterialLocalFileId,ownerFontAssetLocalFileId;
 public int materialSlot,textInfoCharacterCount,textInfoVisibleCharacterCount;
 public uint textInfoTriangleIndexCount,canvasTriangleIndexCount;
 public bool generatedSubmesh,sourceGraphicEnabled=true,sourceGraphicActiveSelf=true,textInfoMaterialMissing,
  tmpFallbackMaterialBaked,requiresPersistentFallbackRegistration,persistentFallbackVariantRegistered,
  textInfoCharacterSlotVerified=true,textInfoCharacterMaterialVerified=true,textInfoFontAssetVerified=true,textInfoAtlasVerified=true,
  captureRoleVerified,observedRoleVerified,fontAssetIsRasterBitmap,outlineDriverPresent,outlineTargetMatchesOwner;
 public string tmpFallbackAlgorithm,captureRole,observedRole,roleTransition,registrationDisposition,registrationOutcome,registrationSkipReason;
 public int fontAtlasRenderMode=-1,tmpFallbackAtlasIndex=-1;
 public string ownerFontAssetGuid;
 public TMP_Text owner; public Graphic sourceGraphic; public Mesh sourceMesh;
 public TMP_FontAsset fontAsset,fallbackFontAsset; public TMP_SpriteAsset spriteAsset;
 public Material ownerFontSharedMaterial,fallbackFontMaterial,sourceMaterial,proxyMaterial;
 public Texture sourceTexture; public NativeStaticSortTextSlotEnumeration textSlotEnumeration;
 public NativeStaticSortTextCaptureLifecycle captureLifecycle; public object ownerStyle;
 public NativeStaticSortTextScaleContext currentTextScaleContext;
 public TextSlotBinding Copy()=>(TextSlotBinding)MemberwiseClone();
}
public sealed class OwnerFontStyleDescriptor {}
public sealed class ProxyQueueSpec { public string meshAssetFolder="Assets/Generated"; }
public sealed class ProxyRendererSpec {
 public string sourceComponentId,sourceText,nativeTextExpectation; public bool sourceTextEmpty;
}

static class UnityStaticSortTextSource {
 const string TEXT_SLOT_ENUMERATION_CONTRACT_V2="monkey-static-sort-text-slot-enumeration/2";
 const string TEXT_SLOT_EVIDENCE_CONTRACT_V2="monkey-static-sort-text-slot-evidence/2";
 const string MainTex="_MainTex";
 static readonly MethodInfo MultiAtlasFallbackMethod=null;
 static readonly FieldInfo CharacterWidthAdjustmentField=typeof(TMP_Text).GetField("m_charWidthAdjDelta",BindingFlags.Instance|BindingFlags.NonPublic);
 static readonly FieldInfo CharacterHorizontalScaleField=typeof(TMP_Text).GetField("m_characterHorizontalScale",BindingFlags.Instance|BindingFlags.NonPublic);
 public static int PrepareCalls, CaptureCalls, RegisterCalls, RebindCalls;
 public static bool failRegistration, driftText, driftAtlas, driftCharacters, driftFont, driftLayout, driftMesh, driftMaterial, driftCount, driftScale;
 public static bool skipContextCapture;
 public static void ResetProvider(){PrepareCalls=CaptureCalls=RegisterCalls=RebindCalls=0;failRegistration=driftText=driftAtlas=driftCharacters=driftFont=driftLayout=driftMesh=driftMaterial=driftCount=driftScale=skipContextCapture=false;}
 public static bool GetCurrentSlots(TMP_Text owner,string sid,out List<TextSlotBinding> slots,
   out NativeStaticSortTextSlotEnumeration enumeration,out string diagnostic) {
   slots=owner.finalSnapshot?owner.finalBindings:owner.bindings; enumeration=owner.finalSnapshot?owner.finalEnumeration:owner.enumeration; diagnostic=null;
   if(owner.finalSnapshot && owner.driftSlotCount) { enumeration=CloneEnum(enumeration); enumeration.slotCount++; enumeration.rows=enumeration.rows.Concat(new[]{enumeration.rows.Last()}).ToArray(); Rehash(enumeration); }
   if(owner.finalSnapshot && driftText){owner.text+="_drift";enumeration=CloneEnum(enumeration,HashText(owner.text));}
   if(owner.finalSnapshot && (driftAtlas||driftCharacters||driftFont)) {
    enumeration=CloneEnum(enumeration);
    if(driftAtlas) enumeration.rows[0].atlasGuid="foreign-atlas";
    if(driftCharacters) enumeration.rows[0].characterAssetEvidenceSha256=new string('0',64);
    if(driftFont) enumeration.rows[0].sourceAssetGuid="foreign-font";
    Rehash(enumeration);
   }
   if(owner.finalSnapshot && (driftLayout||driftMesh||driftMaterial)) {
    slots=owner.finalBindings;
    foreach(var b in slots.Where(x=>x!=null)) {
     if(driftMesh)b.sourceMeshSha256=new string('d',64);
     if(driftMaterial)b.sourceMaterialFingerprint=new string('e',64);
    }
    enumeration=CloneEnum(enumeration);
    foreach(var b in slots.Where(x=>x!=null)){if(driftMesh)enumeration.rows[b.materialSlot].sourceMeshSha256=b.sourceMeshSha256;if(driftMaterial)enumeration.rows[b.materialSlot].sourceGraphicMaterialFingerprint=b.sourceMaterialFingerprint;}
    Rehash(enumeration);
   }
   if(owner.finalSnapshot&&driftLayout&&!owner.layoutGeometryDrifted){((RectTransform)owner.transform).rect.width+=1;owner.layoutGeometryDrifted=true;}
   if(owner.finalSnapshot&&driftScale){
    foreach(var b in slots.Where(x=>x!=null)){
     var character=owner.textInfo.characterInfo.First(x=>x.materialReferenceIndex==b.materialSlot&&x.isVisible);character.scale+=0.125f;
     var formulaCharacter=new NativeStaticSortTextScaleCharacter{scale=character.scale,usingAlternateTypeface=character.isUsingAlternateTypeface,fontStyle=(int)character.style,textElementType=(int)character.elementType};
     var formula=typeof(UnityStaticSortTextSource).GetMethod("ComputeTmpUvScale",BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,new object[]{formulaCharacter,0f,1f,(int)owner.canvas.renderMode,owner.canvas.worldCamera!=null,owner.transform.lossyScale.y,owner.canvas.scaleFactor});
     for(int vertex=character.vertexIndex;vertex<character.vertexIndex+4;vertex++){var uv=b.sourceMesh.uv0[vertex];uv.w=(float)formula;b.sourceMesh.uv0[vertex]=uv;}
     b.sourceMeshSha256=UnityStaticSortTextSource.MeshFingerprint(b.sourceMesh);enumeration.rows[b.materialSlot].sourceMeshSha256=b.sourceMeshSha256;
    }
    Rehash(enumeration);
   }
   foreach(var b in slots.Where(x=>x!=null))b.textSlotEnumeration=enumeration;
  if(!skipContextCapture)foreach(var binding in slots)if(!CaptureCurrentTextScaleContext(binding,out diagnostic))return false;
   return true;
 }
 public static bool PrepareSource(TMP_Text owner,string sid,out string d) { PrepareCalls++; if(owner.finalEnumeration!=null){owner.finalSnapshot=true;foreach(var b in owner.finalBindings.Where(x=>x!=null))b.textSlotEnumeration=owner.finalEnumeration;if(driftLayout&&!owner.layoutGeometryDrifted){((RectTransform)owner.transform).rect.width+=1;owner.layoutGeometryDrifted=true;}} d=null; return true; }
 public static bool CaptureFallbackMaterialProfile(TextSlotBinding b,string path,out string d) {
   CaptureCalls++; b.transientFallbackFingerprint=b.sourceMaterialFingerprint;
   if(b.owner.finalEnumeration==null)b.owner.finalEnumeration=CloneEnum(b.owner.enumeration);
   if(b.captureRole=="primary-font"||b.captureRole=="sprite"||b.captureRole=="fallback-font-same-asset-multi-atlas"){
    b.tmpFallbackMaterialBaked=false;b.requiresPersistentFallbackRegistration=false;b.proxyMaterial=b.sourceMaterial;b.proxyMaterialGuid=b.sourceMaterialGuid;b.proxyMaterialLocalFileId=b.sourceMaterialLocalFileId;b.proxyMaterialFingerprint=b.sourceMaterialFingerprint;
    b.bakedProxyMaterialGuid=b.sourceMaterialGuid;b.bakedProxyMaterialLocalFileId=b.sourceMaterialLocalFileId;b.bakedProxyMaterialFingerprint=b.sourceMaterialFingerprint;
   }else{
    b.tmpFallbackMaterialBaked=true;b.bakedProxyMaterialGuid=HashText("baked|"+b.sourceComponentId+"|"+b.materialSlot).Substring(0,32); b.bakedProxyMaterialLocalFileId=100+b.materialSlot;
    b.bakedProxyMaterialFingerprint=b.transientFallbackFingerprint;
    b.proxyMaterial=new Material{guid=b.bakedProxyMaterialGuid,localFileId=b.bakedProxyMaterialLocalFileId,assetPath="Assets/baked.mat",fingerprint=b.bakedProxyMaterialFingerprint};b.proxyMaterialGuid=b.bakedProxyMaterialGuid;b.proxyMaterialLocalFileId=b.bakedProxyMaterialLocalFileId;b.proxyMaterialFingerprint=b.bakedProxyMaterialFingerprint;
   }
   typeof(UnityStaticSortTextSource).GetMethod("SetRegistrationRouteAfterProfile",BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,new object[]{b});d=null;return true;
 }
 public static bool RegisterCapturedFallbackVariantForModeledLifecycle(TextSlotBinding b,out string d) {
   RegisterCalls++; d=failRegistration?"injected registration failure":null;
   if(failRegistration)return false;if(!b.requiresPersistentFallbackRegistration)return true;b.requiresPersistentFallbackRegistration=false; b.persistentFallbackVariantRegistered=true;b.registrationOutcome="registered";b.registrationSkipReason=null;
   var next=b.Copy(); next.sourceMaterial=b.proxyMaterial; next.sourceMaterialGuid=b.bakedProxyMaterialGuid;
   next.sourceMaterialLocalFileId=b.bakedProxyMaterialLocalFileId; next.sourceMaterialFingerprint=b.bakedProxyMaterialFingerprint;next.observedRole="fallback-font-persistent";next.observedRoleVerified=true;next.roleTransition="transient-to-persistent-registered";
   next.textSlotEnumeration=null; var bindingIndex=b.owner.finalBindings.FindIndex(x=>x!=null&&x.materialSlot==b.materialSlot);b.owner.finalBindings[bindingIndex]=next;
   var e=CloneEnum(b.owner.finalEnumeration??b.owner.enumeration);
   var r=e.rows[b.materialSlot];r.sourceGraphicMaterialGuid=b.bakedProxyMaterialGuid;
   r.sourceGraphicMaterialLocalFileId=b.bakedProxyMaterialLocalFileId;r.sourceGraphicMaterialFingerprint=b.bakedProxyMaterialFingerprint;
   Rehash(e);b.owner.finalEnumeration=e;return true;
 }
 public static bool RebindCapturedSlot(TextSlotBinding captured,TMP_Text owner,Graphic graphic,out TextSlotBinding rebound,out string d) {
   RebindCalls++; GetCurrentSlots(owner,captured.sourceComponentId,out var rows,out var e,out d);
   var current=rows.SingleOrDefault(x=>x.materialSlot==captured.materialSlot);
   if(current==null||!VerifyTextScaleFormulaAgainstMesh(captured.currentTextScaleContext,captured.sourceMesh,out d)||
      !VerifyTextScaleFormulaAgainstMesh(current.currentTextScaleContext,current.sourceMesh,out d)||
      !ValidateCapturedSlotTransition(captured,current,e,out d)){rebound=null;return false;}
   rebound=current;return true;
 }
''' + text_methods + r'''
 static string MaterialFingerprint(Material m)=>m==null?null:m.fingerprint;
 static bool Fail(string s,out string d){d=s;return false;}
 static NativeStaticSortTextSlotEnumeration CloneEnum(NativeStaticSortTextSlotEnumeration e,string sourceTextSha256=null){var x=JsonSerializer.Deserialize<NativeStaticSortTextSlotEnumeration>(JsonSerializer.Serialize(e,new JsonSerializerOptions{IncludeFields=true}),new JsonSerializerOptions{IncludeFields=true});if(sourceTextSha256!=null)x.sourceTextSha256=sourceTextSha256;Rehash(x);return x;}
 static void Rehash(NativeStaticSortTextSlotEnumeration e){foreach(var r in e.rows)r.evidenceSha256=TextSlotRowHash(r);e.evidenceSha256=TextSlotEnumerationHash(e);}
}

static class ProxyHarness {
 static string HashText(string s){using var sha=SHA256.Create();return Convert.ToHexString(sha.ComputeHash(Encoding.UTF8.GetBytes(s??""))).ToLowerInvariant();}
 static void WriteTextSlotCaptureFailure(string code,string sourceComponentId,string phase,string sourceTextSha256,string diagnostic,NativeStaticSortTextSlotEnumeration initial,NativeStaticSortTextSlotEnumeration current,NativeStaticSortTextCaptureLifecycle lifecycle){}

''' + proxy_helpers + r'''
''' + capture_method + r'''
 public static List<TextSlotBinding> Run(ProxyQueueSpec s,ProxyRendererSpec r,TMP_Text o,out NativeStaticSortTextSlotEnumeration e)=>CaptureAndRebindTextSlots(s,r,o,null,out e);
}

class Program {
 static void Need(bool x,string m){if(!x)throw new Exception(m);}
 static string H(string s){using var sha=SHA256.Create();return Convert.ToHexString(sha.ComputeHash(Encoding.UTF8.GetBytes(s))).ToLowerInvariant();}
 static string GuidFor(string s)=>H("guid|"+s).Substring(0,32);
 static Dictionary<string,Dictionary<int,NativeStaticSortTextScaleContext>> ObservedContexts=new();
 static Dictionary<string,JsonElement> ObservedRoleMetadata=new();
 static int modeledUnobservedCharacterPlaceholders=0;
 static object RoleMatrixSummary;
 static object Refusal(string name,Action configure,string expected,string sid,string text){
  UnityStaticSortTextSource.ResetProvider();configure();var owner=Owner(sid,text,1,new[]{0},new[]{1},new[]{1},GuidFor("font|"+sid),GuidFor("atlas|"+sid),H("characters|"+sid));owner.driftSlotCount=UnityStaticSortTextSource.driftCount;
  try{ProxyHarness.Run(new ProxyQueueSpec(),new ProxyRendererSpec{sourceComponentId=sid,sourceText=text},owner,out _);throw new Exception("expected refusal did not occur: "+name);}
  catch(InvalidOperationException ex){if(!ex.Message.Contains(expected,StringComparison.Ordinal))throw new Exception("wrong refusal for "+name+": "+ex.Message);return new{name,refusal=expected};}
 }
 static NativeStaticSortTextSlotEnumeration MakeEnum(string sid,string text,int count,int[] drawableSlots,int[] charCounts,int[] visibleCounts,string asset,string atlas,string charAsset) {
  var e=new NativeStaticSortTextSlotEnumeration{evidenceContract="monkey-static-sort-text-slot-enumeration/2",sourceComponentId=sid,sourceTextSha256=H(text),slotCount=count,verified=true,rows=new NativeStaticSortTextSlotEvidence[count]};
  for(int i=0;i<count;i++){bool draw=drawableSlots.Contains(i);int chars=charCounts[i],visible=visibleCounts[i];var r=e.rows[i]=new NativeStaticSortTextSlotEvidence{evidenceContract="monkey-static-sort-text-slot-evidence/2",slot=i,characterReferences=chars,visibleCharacterReferences=visible,disposition=draw?"drawable":"empty-placeholder",sourceAssetKind="font",sourceAssetGuid=asset,sourceAssetLocalFileId=101,atlasGuid=atlas,atlasLocalFileId=200+i,characterEvidenceSha256=H(sid+"c"+i),characterAssetEvidenceSha256=charAsset,sourceMeshSha256=draw?H(sid+"m"+i):null,textInfoVertexCount=visible*4,textInfoTriangleIndexCount=(uint)(visible*6),textInfoNondegenerateTriangleCount=visible*2,canvasVertexCount=visible*4,canvasTriangleIndexCount=(uint)(visible*6),canvasNondegenerateTriangleCount=visible*2,sourceGraphicMaterialGuid=GuidFor("source-mat|"+sid+"|"+i),sourceGraphicMaterialLocalFileId=300+i,textInfoMaterialGuid=GuidFor("text-mat|"+sid+"|"+i),textInfoMaterialLocalFileId=400+i,sourceShaderGuid=GuidFor("shader|"+sid),sourceShaderLocalFileId=1,sourceTextureGuid=atlas,sourceTextureLocalFileId=200+i,sourceGraphicMaterialFingerprint=H("sm"+sid+"|"+i),textInfoMaterialFingerprint=H("tm"+i)};}
  foreach(var r in e.rows)r.evidenceSha256=typeof(UnityStaticSortTextSource).GetMethod("TextSlotRowHash",BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,new object[]{r}).ToString();
  var hash=typeof(UnityStaticSortTextSource).GetMethod("TextSlotEnumerationHash",BindingFlags.NonPublic|BindingFlags.Static);e.evidenceSha256=hash.Invoke(null,new object[]{e}).ToString();return e;
 }
 static Mesh MakeMesh(int visible)=>MakeMesh(Enumerable.Repeat(1f,visible*4).ToArray());
 static Mesh MakeMesh(float[] observedW){int vertexCount=observedW.Length;var triangles=new List<int>();for(int i=0;i+3<vertexCount;i+=4)triangles.AddRange(new[]{i,i+1,i+2,i+2,i+1,i+3});return new Mesh{vertexCount=vertexCount,subMeshCount=1,vertices=Enumerable.Range(0,vertexCount).Select(i=>new Vector3(i%2,i/2,0)).ToArray(),colors32=Enumerable.Range(0,vertexCount).Select(i=>new Color32{r=255,g=255,b=255,a=255}).ToArray(),normals=Enumerable.Range(0,vertexCount).Select(i=>new Vector3(0,0,-1)).ToArray(),tangents=Enumerable.Range(0,vertexCount).Select(i=>new Vector4{w=1}).ToArray(),uv0=Enumerable.Range(0,vertexCount).Select(i=>new Vector4{x=(i%2),y=(i/2)%2,w=observedW[i]}).ToArray(),triangles=triangles.ToArray()};}
 static TMP_Text Owner(string sid,string text,int slots,int[] drawableSlots,int[] charCounts,int[] visibleCounts,string asset,string atlas,string chars,Dictionary<int,NativeStaticSortTextScaleContext> actualContexts=null) {
  var ownerRoleMeta=ObservedRoleMetadata.FirstOrDefault(pair=>pair.Key.StartsWith(sid+"|",StringComparison.Ordinal)).Value;
  var ownerFontSpec=ownerRoleMeta.ValueKind==JsonValueKind.Object?JP(ownerRoleMeta,"ownerFont"):default;
  var ownerMaterialSpec=ownerRoleMeta.ValueKind==JsonValueKind.Object?JP(ownerRoleMeta,"ownerMaterial"):default;
  var font=ownerRoleMeta.ValueKind==JsonValueKind.Object?RoleFont(ownerFontSpec):new TMP_FontAsset{guid=asset,localFileId=101,assetPath="Assets/font.asset"};
  var mat=ownerRoleMeta.ValueKind==JsonValueKind.Object?RoleMaterial(ownerMaterialSpec):new Material{guid=GuidFor("font-mat|"+sid),localFileId=102,assetPath="Assets/font.mat",fingerprint=H("fm|"+sid)};
  var seed=actualContexts?.Values.FirstOrDefault();var layout=seed?.textLayoutInputs;
  var owner=new TextMeshProUGUI{text=text,font=font,fontSharedMaterial=mat,bindings=new List<TextSlotBinding>(),finalBindings=new List<TextSlotBinding>(),canvas=new Canvas{renderMode=(RenderMode)(seed?.canvasRenderMode??(int)RenderMode.ScreenSpaceOverlay),scaleFactor=seed?.canvasScaleFactor??1f,worldCamera=(seed!=null&&seed.worldCameraAssigned?new UnityEngine.Object():null)},transform=new RectTransform{rect=new Rect(layout?.rectSize.x??100f,layout?.rectSize.y??28f),pivot=layout==null?new Vector2(.5f,.5f):new Vector2(layout.pivot.x,layout.pivot.y),lossyScale=new Vector3(1,seed?.ownerLossyScaleY??1f,1)}};
  if(seed!=null)owner.transform.lossyScale=new Vector3(1,seed.ownerLossyScaleY,1);
  if(ObservedRoleMetadata.Any(pair=>pair.Key.StartsWith(sid+"|",StringComparison.Ordinal)&&JB(pair.Value,"sourceOutlineEnabled")))owner.outline=new NativeStaticTextOutline{Target=owner};
  if(seed!=null){owner.margin=layout.margin;owner.fontSize=seed.ownerFontSize;owner.fontSizeMin=seed.ownerFontSizeMin;owner.fontSizeMax=seed.ownerFontSizeMax;owner.fontStyle=(FontStyles)seed.ownerFontStyle;owner.enableAutoSizing=seed.ownerAutoSizing;owner.fontWeight=layout.fontWeight;owner.alignment=layout.alignment;owner.textWrappingMode=layout.wrappingMode;owner.overflowMode=layout.overflowMode;owner.maxVisibleCharacters=layout.maxVisibleCharacters;owner.maxVisibleWords=layout.maxVisibleWords;owner.maxVisibleLines=layout.maxVisibleLines;owner.pageToDisplay=layout.pageToDisplay;owner.characterSpacing=layout.characterSpacing;owner.wordSpacing=layout.wordSpacing;owner.lineSpacing=layout.lineSpacing;owner.lineSpacingAdjustment=layout.lineSpacingAdjustment;owner.paragraphSpacing=layout.paragraphSpacing;owner.extraPadding=layout.extraPadding;owner.richText=layout.richText;owner.parseCtrlCharacters=layout.parseControlCharacters;owner.isRightToLeftText=layout.rightToLeft;owner.useMaxVisibleDescender=layout.useMaxVisibleDescender;owner.fontFeatures=layout.fontFeatures??Array.Empty<int>();owner.SetScaleInternals(seed.charWidthAdjustmentDelta,seed.characterHorizontalScale);owner.textInfo.lineCount=layout.textLineBoxLineCount;if(layout.textLineBoxPresent)owner.lineBox=new Monkey.StaticMaskSort.NativeTextLineBox{LineHeight=layout.textLineBoxLineHeight,ExtraLineFraction=layout.textLineBoxExtraLineFraction,preferredHeight=layout.textLineBoxNativePreferredHeight,isActiveAndEnabled=layout.textLineBoxActive};if(layout.contentSizeFitterPresent)owner.fitter=new ContentSizeFitter{horizontalFit=(ContentSizeFitter.FitMode)layout.contentSizeFitterHorizontalFit,verticalFit=(ContentSizeFitter.FitMode)layout.contentSizeFitterVerticalFit,isActiveAndEnabled=layout.contentSizeFitterActive};}
  owner.enumeration=MakeEnum(sid,text,slots,drawableSlots,charCounts,visibleCounts,asset,atlas,chars);
  if(ownerRoleMeta.ValueKind==JsonValueKind.Object){
   owner.enumeration=JsonSerializer.Deserialize<NativeStaticSortTextSlotEnumeration>(JP(ownerRoleMeta,"enumeration").GetRawText(),new JsonSerializerOptions{IncludeFields=true});
   if(owner.enumeration.rows.Length>0)font.atlasTextures=new[]{new Texture{guid=owner.enumeration.rows[0].atlasGuid,localFileId=owner.enumeration.rows[0].atlasLocalFileId}};
  }
  owner.textInfo.materialCount=slots;owner.textInfo.lineCount=layout?.textLineBoxLineCount??1;
  var characters=new List<TMP_CharacterInfo>();if(actualContexts!=null){foreach(var context in actualContexts.Values)foreach(var c in context.characters)characters.Add(new TMP_CharacterInfo{characterIndex=c.characterIndex,materialReferenceIndex=c.materialSlot,vertexIndex=c.vertexIndex,character=c.unicode<=65535?(char)c.unicode:'?',textElement=new TMP_TextElement{unicode=(uint)c.unicode},scale=c.scale,isVisible=c.visible,elementType=(TMP_TextElementType)c.textElementType,style=(FontStyles)c.fontStyle,isUsingAlternateTypeface=c.usingAlternateTypeface});characters=characters.OrderBy(x=>x.characterIndex).ToList();}
  else for(int slot=0;slot<slots;slot++)for(int ci=0;ci<charCounts[slot];ci++)characters.Add(new TMP_CharacterInfo{materialReferenceIndex=slot,vertexIndex=ci<visibleCounts[slot]?ci*4:0,character=(char)('A'+ci%26),scale=1,isVisible=ci<visibleCounts[slot],elementType=TMP_TextElementType.Character,style=FontStyles.Normal});
  if(actualContexts!=null&&characters.Count>0){var dense=new List<TMP_CharacterInfo>();for(int i=0;i<=characters.Max(x=>x.characterIndex);i++){var existing=characters.SingleOrDefault(x=>x.characterIndex==i);if(existing==null)modeledUnobservedCharacterPlaceholders++;dense.Add(existing??new TMP_CharacterInfo{characterIndex=i,materialReferenceIndex=-1,vertexIndex=0,character='?',textElement=new TMP_TextElement{unicode=0},scale=1,isVisible=false});}characters=dense;}
  owner.textInfo.characterInfo=characters.ToArray();owner.textInfo.characterCount=characters.Count;
  foreach(int i in drawableSlots){
   var roleMeta=ObservedRoleMetadata.GetValueOrDefault(sid+"|"+i);var hasObservedRole=roleMeta.ValueKind==JsonValueKind.Object;
   var modeledRole=hasObservedRole?JS(roleMeta,"expectedRole"):(i==0?"primary-font":"fallback-font-transient");
   var roleOutline=hasObservedRole&&JB(roleMeta,"sourceOutlineEnabled");
   var texture=new Texture{guid=atlas,localFileId=200+i,assetPath="Assets/atlas.asset"};var slotContext=actualContexts!=null?actualContexts.GetValueOrDefault(i):null;
   Graphic graphic=i==0?owner:new Graphic{transform=new RectTransform{rect=new Rect(layout?.rectSize.x??100f,layout?.rectSize.y??28f),pivot=layout==null?new Vector2(.5f,.5f):new Vector2(layout.pivot.x,layout.pivot.y),lossyScale=new Vector3(1,slotContext?.graphicLossyScaleY??1f,1)}};
   if(i==0&&slotContext!=null)graphic.transform.lossyScale=new Vector3(1,slotContext.graphicLossyScaleY,1);
   var mesh=slotContext==null?MakeMesh(visibleCounts[i]):MakeMesh(slotContext.meshUv0W);var meshSha=UnityStaticSortTextSource.MeshFingerprint(mesh);
   var sourceMaterial=new Material{guid=GuidFor("source-mat|"+sid+"|"+i),localFileId=300+i,assetPath="Assets/source.mat",fingerprint=H("sm"+sid+"|"+i),shader=new Shader{guid=GuidFor("shader|"+sid),localFileId=1,assetPath="Assets/shader.shader"}};
   var binding=new TextSlotBinding{sourceComponentId=sid,sourceTextSha256=H(text),owner=owner,sourceGraphic=graphic,sourceMesh=mesh,sourceMeshSha256=meshSha,materialSlot=i,generatedSubmesh=i>0,fontAsset=font,fontAssetGuid=asset,fontAssetLocalFileId=101,ownerFontSharedMaterial=mat,ownerFontMaterialGuid=mat.guid,ownerFontMaterialLocalFileId=mat.localFileId,ownerFontMaterialFingerprint=mat.fingerprint,ownerFontAssetGuid=asset,ownerFontAssetLocalFileId=101,sourceTexture=texture,sourceTextureGuid=atlas,sourceTextureLocalFileId=200+i,textInfoCharacterCount=charCounts[i],textInfoVisibleCharacterCount=visibleCounts[i],textInfoTriangleIndexCount=(uint)(visibleCounts[i]*6),canvasTriangleIndexCount=(uint)(visibleCounts[i]*6),textInfoCharacterSlotVerified=true,textInfoCharacterMaterialVerified=true,textInfoFontAssetVerified=true,textInfoAtlasVerified=true,textInfoCharacterEvidenceSha256=H(sid+"c"+i),textInfoCharacterAssetEvidenceSha256=chars,textInfoCharacterMaterialFingerprint=H("tm"+i),sourceMaterial=sourceMaterial,sourceMaterialGuid=sourceMaterial.guid,sourceMaterialLocalFileId=sourceMaterial.localFileId,sourceMaterialFingerprint=sourceMaterial.fingerprint,sourceShaderGuid=sourceMaterial.shader.guid,sourceShaderLocalFileId=sourceMaterial.shader.localFileId,fallbackFontAssetGuid=GuidFor("fallback-font|"+sid),fallbackFontAssetLocalFileId=500+i,fallbackFontMaterialGuid=GuidFor("fallback-mat|"+sid),fallbackFontMaterialLocalFileId=600+i,fallbackFontMaterialFingerprint=H("fbm"),fallbackAtlasGuid=atlas,tmpFallbackAlgorithm="offline-provider-v1",transientFallbackFingerprint=sourceMaterial.fingerprint,textSlotEnumeration=owner.enumeration};
   binding.captureRole=modeledRole;binding.captureRoleVerified=true;binding.observedRole=modeledRole;binding.observedRoleVerified=true;binding.roleTransition="same";binding.outlineDriverPresent=roleOutline;binding.outlineTargetMatchesOwner=roleOutline;
   binding.fontAtlasRenderMode=hasObservedRole&&JP(roleMeta.GetProperty("slotFont"),"renderMode").ValueKind==JsonValueKind.Number?JP(roleMeta.GetProperty("slotFont"),"renderMode").GetInt32():0;
   binding.fontAssetIsRasterBitmap=binding.fontAtlasRenderMode==(int)UnityEngine.TextCore.LowLevel.GlyphRenderMode.RASTER;
   binding.tmpFallbackAtlasIndex=modeledRole=="sprite"?-1:0;
   if(hasObservedRole){
    var slotFontSpec=JP(roleMeta,"slotFont");var slotFont=JS(slotFontSpec,"guid")==font.guid?font:RoleFont(slotFontSpec);
    var fallbackFontSpec=JP(roleMeta,"fallbackFont");var fallbackFont=JS(fallbackFontSpec,"guid")==font.guid?font:(JS(fallbackFontSpec,"guid")==slotFont?.guid?slotFont:RoleFont(fallbackFontSpec));
    var fallbackMaterial=fallbackFont==null?null:RoleMaterial(JP(roleMeta,"fallbackMaterial"));var sourceMaterialSpec=JP(roleMeta,"sourceMaterial");
    var observedSourceMaterial=JS(sourceMaterialSpec,"guid")==mat.guid&&JL(sourceMaterialSpec,"localFileId")==mat.localFileId?mat:RoleMaterial(sourceMaterialSpec);
    var sourceTexture=RoleTexture(JP(roleMeta,"sourceTexture"));var enumSource=JsonSerializer.Deserialize<NativeStaticSortTextSlotEnumeration>(JP(roleMeta,"enumeration").GetRawText(),new JsonSerializerOptions{IncludeFields=true});
    var sourceRow=enumSource.rows[i];var modeledRow=owner.enumeration.rows[i];
    binding.fontAsset=slotFont;binding.fontAssetGuid=JS(slotFontSpec,"guid");binding.fontAssetLocalFileId=JL(slotFontSpec,"localFileId");
    binding.ownerFontAssetGuid=font.guid;binding.ownerFontAssetLocalFileId=font.localFileId;
    binding.fallbackFontAsset=fallbackFont;binding.fallbackFontAssetGuid=JS(fallbackFontSpec,"guid");binding.fallbackFontAssetLocalFileId=JL(fallbackFontSpec,"localFileId");
    binding.fallbackFontMaterial=fallbackMaterial;binding.fallbackFontMaterialGuid=JS(JP(roleMeta,"fallbackMaterial"),"guid");binding.fallbackFontMaterialLocalFileId=JL(JP(roleMeta,"fallbackMaterial"),"localFileId");binding.fallbackFontMaterialFingerprint=JS(JP(roleMeta,"fallbackMaterial"),"fingerprint");
    if(fallbackFont!=null)fallbackFont.material=fallbackMaterial;
    binding.sourceMaterial=observedSourceMaterial;binding.sourceMaterialGuid=JS(sourceMaterialSpec,"guid");binding.sourceMaterialLocalFileId=JL(sourceMaterialSpec,"localFileId");binding.sourceMaterialFingerprint=JS(sourceMaterialSpec,"fingerprint");
    binding.sourceTexture=sourceTexture;binding.sourceTextureGuid=sourceTexture.guid;binding.sourceTextureLocalFileId=sourceTexture.localFileId;
    binding.fallbackAtlasGuid=fallbackFont==null?null:sourceTexture.guid;binding.fallbackAtlasLocalFileId=fallbackFont==null?0:sourceTexture.localFileId;
    binding.transientFallbackFingerprint=binding.sourceMaterialFingerprint;
    var shaderSpec=JP(roleMeta,"sourceShader");binding.sourceShaderGuid=JS(shaderSpec,"guid");binding.sourceShaderLocalFileId=JL(shaderSpec,"localFileId");
    var sourceShader=new Shader{guid=binding.sourceShaderGuid,localFileId=binding.sourceShaderLocalFileId,assetPath="Assets/source.shader"};
    if(binding.sourceMaterial!=null)binding.sourceMaterial.shader=sourceShader;
    if(mat!=null)mat.shader=sourceShader;
    binding.textInfoMaterialMissing=sourceRow.textInfoMaterialMissing;
    binding.textInfoCharacterCount=sourceRow.characterReferences;binding.textInfoVisibleCharacterCount=sourceRow.visibleCharacterReferences;
    binding.textInfoCharacterEvidenceSha256=sourceRow.characterEvidenceSha256;
    binding.textInfoCharacterAssetEvidenceSha256=sourceRow.characterAssetEvidenceSha256;
    var observedCharacterMaterialFingerprint=JS(roleMeta,"textInfoCharacterMaterialFingerprint");
    binding.textInfoCharacterMaterialFingerprint=!String.IsNullOrWhiteSpace(observedCharacterMaterialFingerprint)
     ?observedCharacterMaterialFingerprint
     :!String.IsNullOrWhiteSpace(sourceRow.textInfoMaterialFingerprint)?sourceRow.textInfoMaterialFingerprint
     :fallbackMaterial!=null?fallbackMaterial.fingerprint:binding.sourceMaterialFingerprint;
    modeledRow.sourceShaderGuid=binding.sourceShaderGuid;modeledRow.sourceShaderLocalFileId=binding.sourceShaderLocalFileId;
    modeledRow.sourceAssetKind=sourceRow.sourceAssetKind;modeledRow.sourceAssetGuid=sourceRow.sourceAssetGuid;modeledRow.sourceAssetLocalFileId=sourceRow.sourceAssetLocalFileId;
    modeledRow.atlasGuid=sourceRow.atlasGuid;modeledRow.atlasLocalFileId=sourceRow.atlasLocalFileId;
    modeledRow.sourceTextureGuid=sourceTexture.guid;modeledRow.sourceTextureLocalFileId=sourceTexture.localFileId;
    modeledRow.sourceGraphicMaterialGuid=sourceRow.sourceGraphicMaterialGuid;modeledRow.sourceGraphicMaterialLocalFileId=sourceRow.sourceGraphicMaterialLocalFileId;
    modeledRow.sourceGraphicMaterialFingerprint=sourceRow.sourceGraphicMaterialFingerprint;
    modeledRow.textInfoMaterialGuid=sourceRow.textInfoMaterialGuid;modeledRow.textInfoMaterialLocalFileId=sourceRow.textInfoMaterialLocalFileId;
    modeledRow.textInfoMaterialFingerprint=sourceRow.textInfoMaterialFingerprint;modeledRow.textInfoMaterialMissing=sourceRow.textInfoMaterialMissing;
    if(i==0)font.atlasTextures=new[]{sourceTexture};
    if(slotFont!=null)slotFont.atlasTextures=new[]{sourceTexture};
    if(fallbackFont!=null)fallbackFont.atlasTextures=new[]{sourceTexture};
   }else if(modeledRole=="primary-font"){
    binding.fallbackFontAsset=null;binding.fallbackFontAssetGuid=null;binding.fallbackFontAssetLocalFileId=0;
    binding.fallbackFontMaterial=null;binding.fallbackFontMaterialGuid=null;binding.fallbackFontMaterialLocalFileId=0;binding.fallbackFontMaterialFingerprint=null;
    binding.fallbackAtlasGuid=null;binding.fallbackAtlasLocalFileId=0;binding.sourceMaterial=mat;binding.sourceMaterialGuid=mat.guid;binding.sourceMaterialLocalFileId=mat.localFileId;binding.sourceMaterialFingerprint=mat.fingerprint;
    owner.enumeration.rows[i].sourceGraphicMaterialGuid=mat.guid;owner.enumeration.rows[i].sourceGraphicMaterialLocalFileId=mat.localFileId;owner.enumeration.rows[i].sourceGraphicMaterialFingerprint=mat.fingerprint;
    font.atlasTextures=new[]{texture};
   }else if(modeledRole=="fallback-font-transient"){
    var fallbackFont=new TMP_FontAsset{guid=GuidFor("fallback-font|"+sid+"|"+i),localFileId=500+i,assetPath="Assets/fallback-font.asset",atlasTextures=new[]{texture}};
    var fallbackMat=new Material{guid=GuidFor("fallback-mat|"+sid+"|"+i),localFileId=600+i,assetPath="Assets/fallback-font.mat",fingerprint=H("fallback-mat|"+sid+"|"+i)};fallbackFont.material=fallbackMat;
    binding.fontAsset=fallbackFont;binding.fontAssetGuid=fallbackFont.guid;binding.fontAssetLocalFileId=fallbackFont.localFileId;binding.fallbackFontAsset=fallbackFont;binding.fallbackFontAssetGuid=fallbackFont.guid;binding.fallbackFontAssetLocalFileId=fallbackFont.localFileId;
    binding.fallbackFontMaterial=fallbackMat;binding.fallbackFontMaterialGuid=fallbackMat.guid;binding.fallbackFontMaterialLocalFileId=fallbackMat.localFileId;binding.fallbackFontMaterialFingerprint=fallbackMat.fingerprint;binding.fallbackAtlasGuid=texture.guid;binding.fallbackAtlasLocalFileId=texture.localFileId;
    binding.sourceMaterial=new Material{fingerprint=binding.sourceMaterialFingerprint,shader=sourceMaterial.shader};binding.sourceMaterialGuid=null;binding.sourceMaterialLocalFileId=0;
    owner.enumeration.rows[i].sourceAssetGuid=fallbackFont.guid;owner.enumeration.rows[i].sourceAssetLocalFileId=fallbackFont.localFileId;owner.enumeration.rows[i].atlasGuid=texture.guid;owner.enumeration.rows[i].atlasLocalFileId=texture.localFileId;
    owner.enumeration.rows[i].sourceGraphicMaterialGuid=null;owner.enumeration.rows[i].sourceGraphicMaterialLocalFileId=0;
    font.atlasTextures=new[]{texture};
   }
   SetInitialProviderRoute(binding);
   owner.bindings.Add(binding);
  }
  foreach(var b in owner.bindings)owner.enumeration.rows[b.materialSlot].sourceMeshSha256=UnityStaticSortTextSource.MeshFingerprint(b.sourceMesh);
  RehashEnum(owner.enumeration);foreach(var b in owner.bindings){b.textSlotEnumeration=owner.enumeration;owner.finalBindings.Add(b.Copy());}
  return owner;
 }
 static void RehashEnum(NativeStaticSortTextSlotEnumeration e){foreach(var r in e.rows)r.evidenceSha256=typeof(UnityStaticSortTextSource).GetMethod("TextSlotRowHash",BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,new object[]{r}).ToString();var hash=typeof(UnityStaticSortTextSource).GetMethod("TextSlotEnumerationHash",BindingFlags.NonPublic|BindingFlags.Static);e.evidenceSha256=hash.Invoke(null,new object[]{e}).ToString();}
 static JsonElement JP(JsonElement x,string k)=>x.ValueKind==JsonValueKind.Object&&x.TryGetProperty(k,out var v)?v:default;
 static string JS(JsonElement x,string k){var v=JP(x,k);return v.ValueKind==JsonValueKind.String?v.GetString():null;}
 static long JL(JsonElement x,string k){var v=JP(x,k);return v.ValueKind==JsonValueKind.Number?v.GetInt64():0;}
 static bool JB(JsonElement x,string k){var v=JP(x,k);return v.ValueKind==JsonValueKind.True;}
 static bool HasGuid(JsonElement x)=>!String.IsNullOrWhiteSpace(JS(x,"guid"))&&JL(x,"localFileId")!=0;
 static TMP_FontAsset RoleFont(JsonElement x){var guid=JS(x,"guid");if(String.IsNullOrEmpty(guid))return null;return new TMP_FontAsset{guid=guid,localFileId=JL(x,"localFileId"),assetPath=JS(x,"path"),atlasRenderMode=(int)(JP(x,"renderMode").ValueKind==JsonValueKind.Number?JP(x,"renderMode").GetInt32():0)};}
 static Material RoleMaterial(JsonElement x){var guid=JS(x,"guid");if(String.IsNullOrEmpty(guid))return new Material{fingerprint=JS(x,"fingerprint")};return new Material{guid=guid,localFileId=JL(x,"localFileId"),assetPath=JS(x,"path"),fingerprint=JS(x,"fingerprint")};}
 static Texture RoleTexture(JsonElement x)=>new Texture{guid=JS(x,"guid"),localFileId=JL(x,"localFileId"),assetPath=JS(x,"path")};
 static TextSlotBinding MakeRoleBinding(JsonElement x){
  var sid=JS(x,"sourceComponentId");var text=JS(x,"sourceText")??"";var enumValue=JsonSerializer.Deserialize<NativeStaticSortTextSlotEnumeration>(JP(x,"enumeration").GetRawText(),new JsonSerializerOptions{IncludeFields=true});
  var ownerFontSpec=JP(x,"ownerFont");var ownerFont=RoleFont(ownerFontSpec);var ownerMaterial=RoleMaterial(JP(x,"ownerMaterial"));if(ownerFont==null||ownerMaterial==null)throw new Exception("role fixture missing persistent owner font/material: "+sid);
  ownerFont.material=ownerMaterial;var slotFontSpec=JP(x,"slotFont");var slotFont=JS(slotFontSpec,"guid")==ownerFont.guid?ownerFont:RoleFont(slotFontSpec);
  var sourceTexture=RoleTexture(JP(x,"sourceTexture"));var fallbackFontSpec=JP(x,"fallbackFont");var fallbackFont=JS(fallbackFontSpec,"guid")==ownerFont.guid?ownerFont:(JS(fallbackFontSpec,"guid")==JS(slotFontSpec,"guid")?slotFont:RoleFont(fallbackFontSpec));
  var fallbackMaterial=RoleMaterial(JP(x,"fallbackMaterial"));if(fallbackFont!=null)fallbackFont.material=fallbackMaterial;
  if(slotFont!=null)slotFont.atlasTextures=new[]{sourceTexture};if(fallbackFont!=null)fallbackFont.atlasTextures=new[]{sourceTexture};if(ownerFont.atlasTextures==null||ownerFont.atlasTextures.Length==0)ownerFont.atlasTextures=new[]{sourceTexture};
  var owner=new TextMeshProUGUI{text=text,font=ownerFont,fontSharedMaterial=ownerMaterial,bindings=new List<TextSlotBinding>(),finalBindings=new List<TextSlotBinding>(),canvas=new Canvas(),transform=new RectTransform()};owner.textInfo.materialCount=enumValue.slotCount;owner.textInfo.lineCount=1;
  if(JB(x,"sourceOutlineEnabled"))owner.outline=new NativeStaticTextOutline{Target=owner};
  var sourceMaterial=RoleMaterial(JP(x,"sourceMaterial"));var sourceGraphic=JL(x,"slot")==0?owner:new Graphic{transform=new RectTransform()};
  var profile=JP(x,"nativeSourceSlot");var bakedRef=JP(profile,"bakedProxyMaterial");var proxyMaterial=JB(profile,"tmpFallbackMaterialBaked")?RoleMaterial(new JsonObjectProxy{guid=JS(bakedRef,"guid"),localFileId=JL(bakedRef,"localFileId"),path=JS(profile,"bakedProxyMaterialPath"),fingerprint=JS(profile,"bakedProxyMaterialFingerprint")}.ToElement()):sourceMaterial;
  var slot=JL(x,"slot");var row=enumValue.rows[slot];var generated=JB(profile,"generatedSubmesh");
  var binding=new TextSlotBinding{sourceComponentId=sid,sourceTextSha256=H(text),owner=owner,sourceGraphic=sourceGraphic,materialSlot=(int)slot,generatedSubmesh=generated,
   fontAsset=slotFont,fontAssetGuid=slotFont?.guid,fontAssetLocalFileId=slotFont?.localFileId??0,
   spriteAsset=HasGuid(JP(x,"spriteAsset"))?new TMP_SpriteAsset{guid=JS(JP(x,"spriteAsset"),"guid"),localFileId=JL(JP(x,"spriteAsset"),"localFileId"),assetPath=JS(JP(x,"spriteAsset"),"path")}:null,
   ownerFontSharedMaterial=ownerMaterial,ownerFontMaterialGuid=ownerMaterial.guid,ownerFontMaterialLocalFileId=ownerMaterial.localFileId,ownerFontMaterialFingerprint=ownerMaterial.fingerprint,
   fallbackFontAsset=fallbackFont,fallbackFontAssetGuid=fallbackFont?.guid,fallbackFontAssetLocalFileId=fallbackFont?.localFileId??0,
   fallbackFontMaterial=fallbackMaterial,fallbackFontMaterialGuid=fallbackMaterial?.guid,fallbackFontMaterialLocalFileId=fallbackMaterial?.localFileId??0,fallbackFontMaterialFingerprint=fallbackMaterial?.fingerprint,
   fallbackAtlasGuid=JS(JP(x,"sourceTexture"),"guid"),fallbackAtlasLocalFileId=JL(JP(x,"sourceTexture"),"localFileId"),sourceTexture=sourceTexture,sourceTextureGuid=sourceTexture.guid,sourceTextureLocalFileId=sourceTexture.localFileId,
   sourceMaterial=sourceMaterial,sourceMaterialGuid=JS(JP(x,"sourceMaterial"),"guid"),sourceMaterialLocalFileId=JL(JP(x,"sourceMaterial"),"localFileId"),sourceMaterialFingerprint=JS(JP(x,"sourceMaterial"),"fingerprint"),
   proxyMaterial=proxyMaterial,proxyMaterialGuid=proxyMaterial.guid,proxyMaterialLocalFileId=proxyMaterial.localFileId,proxyMaterialFingerprint=proxyMaterial.fingerprint,
   tmpFallbackMaterialBaked=JB(profile,"tmpFallbackMaterialBaked"),transientFallbackFingerprint=JS(JP(x,"sourceMaterial"),"fingerprint"),
   bakedProxyMaterialGuid=JS(profile,"bakedProxyMaterialGuid"),bakedProxyMaterialLocalFileId=JL(profile,"bakedProxyMaterialLocalFileId"),bakedProxyMaterialFingerprint=JS(profile,"bakedProxyMaterialFingerprint"),tmpFallbackAlgorithm=JS(profile,"tmpFallbackAlgorithm"),
   requiresPersistentFallbackRegistration=false,persistentFallbackVariantRegistered=false,textSlotEnumeration=enumValue,textInfoCharacterEvidenceSha256=row.characterEvidenceSha256,textInfoCharacterAssetEvidenceSha256=row.characterAssetEvidenceSha256,
   sourceMeshSha256=row.sourceMeshSha256,sourceGraphicEnabled=true,sourceGraphicActiveSelf=true};
  RehashEnum(enumValue);binding.textSlotEnumeration=enumValue;return binding;
 }
 sealed class JsonObjectProxy{public string guid,path,fingerprint;public long localFileId;public JsonElement ToElement()=>JsonDocument.Parse(JsonSerializer.Serialize(this,new JsonSerializerOptions{IncludeFields=true})).RootElement.Clone();}
 static bool Classify(TextSlotBinding binding,out string role,out int renderMode,out bool raster,out string diagnostic){var args=new object[]{binding,null,-1,false,null};var ok=(bool)typeof(UnityStaticSortTextSource).GetMethod("TryClassifyCaptureSlotRole",BindingFlags.Public|BindingFlags.Static).Invoke(null,args);role=args[1]?.ToString();renderMode=(int)args[2];raster=(bool)args[3];diagnostic=args[4]?.ToString();return ok;}
 static bool RegisterRole(TextSlotBinding binding,out string diagnostic){var args=new object[]{binding,null};var ok=(bool)typeof(UnityStaticSortTextSource).GetMethod("RegisterCapturedFallbackVariant",BindingFlags.Public|BindingFlags.Static).Invoke(null,args);diagnostic=args[1]?.ToString();return ok;}
 static void FinalizeProfileRoute(TextSlotBinding binding)=>typeof(UnityStaticSortTextSource).GetMethod("SetRegistrationRouteAfterProfile",BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,new object[]{binding});
 static bool CaptureDirectProfile(TextSlotBinding binding,bool register,out string diagnostic){var args=new object[]{binding,"Assets/Synthetic/Fallback.mat",register,null};var ok=(bool)typeof(UnityStaticSortTextSource).GetMethod("CaptureFallbackMaterial",BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,args);diagnostic=args[3]?.ToString();return ok;}
 static TextSlotBinding MakePersistentFallback(JsonElement row,string tag){var b=MakeRoleBinding(row);var mat=new Material{guid=GuidFor("synthetic-fallback-source|"+tag),localFileId=9001,assetPath="Assets/Synthetic/Fallback.mat",fingerprint=b.sourceMaterialFingerprint,shader=b.sourceMaterial.shader};b.sourceMaterial=mat;b.sourceMaterialGuid=mat.guid;b.sourceMaterialLocalFileId=mat.localFileId;var evidence=b.textSlotEnumeration.rows[b.materialSlot];evidence.sourceGraphicMaterialGuid=mat.guid;evidence.sourceGraphicMaterialLocalFileId=mat.localFileId;RehashEnum(b.textSlotEnumeration);return b;}
 static void SyntheticRoleControls(string roleMatrixPath,out int controls,out int denied){using var doc=JsonDocument.Parse(File.ReadAllText(roleMatrixPath));var rows=doc.RootElement.GetProperty("roleRows").EnumerateArray().ToArray();var transient=rows.First(x=>JS(x,"expectedRole")=="fallback-font-transient"&&JB(x,"sourceOutlineEnabled"));var primary=rows.First(x=>JS(x,"expectedRole")=="primary-font");controls=0;denied=0;
  var persistent=MakePersistentFallback(transient,"persistent-outline");Need(Classify(persistent,out var role,out _,out _,out var diagnostic)&&role=="fallback-font-persistent","synthetic persistent fallback exact role: "+diagnostic);Need(CaptureDirectProfile(persistent,false,out diagnostic),"production persistent direct-profile capture: "+diagnostic);Need(persistent.requiresPersistentFallbackRegistration&&persistent.registrationDisposition=="required"&&persistent.registrationOutcome=="pending","production profile route marks required fallback pending");Need(RegisterRole(persistent,out diagnostic),"production registration accepts valid pending persistent fallback: "+diagnostic);Need(persistent.persistentFallbackVariantRegistered&&persistent.registrationOutcome=="registered"&&persistent.owner.outline.registrationCount==1,"production profile registration selected exact variant");var persistentCurrent=persistent.Copy();Need(Classify(persistentCurrent,out _,out _,out _,out diagnostic),"persistent final role resampled");Need((bool)typeof(UnityStaticSortTextSource).GetMethod("CarryCaptureSlotRoute",BindingFlags.Public|BindingFlags.Static).Invoke(null,new object[]{persistent,persistentCurrent,null}),"production CarryCaptureSlotRoute accepts exact persistent role");controls++;
  var selected=MakePersistentFallback(transient,"preselected-outline");Need(CaptureDirectProfile(selected,true,out diagnostic),"production direct profile with preselected registration: "+diagnostic);Need(selected.persistentFallbackVariantRegistered&&selected.registrationOutcome=="registered","profile captures selected variant proof");Need(RegisterRole(selected,out diagnostic),"production registration accepts exact already-selected variant: "+diagnostic);controls++;var unselected=MakePersistentFallback(transient,"unselected-outline");Need(CaptureDirectProfile(unselected,true,out diagnostic),"production profile creates candidate then selects: "+diagnostic);unselected.owner.outline.selected=false;Need(!RegisterRole(unselected,out diagnostic)&&diagnostic.Contains("EXISTING_FALLBACK_REGISTRATION_NOT_VERIFIED",StringComparison.Ordinal),"unselected existing variant is rejected");denied++;
  var diffGuid=MakePersistentFallback(transient,"different-guid-same-fingerprint");Need(CaptureDirectProfile(diffGuid,false,out diagnostic),"direct profile for GUID counterexample");diffGuid.sourceMaterial=new Material{guid=GuidFor("other-guid-same-fingerprint"),localFileId=9002,assetPath="Assets/Synthetic/Other.mat",fingerprint=diffGuid.sourceMaterialFingerprint};Need(!RegisterRole(diffGuid,out diagnostic),"different persistent GUID with same fingerprint is rejected");denied++;
  var contradictory=MakeRoleBinding(primary);Need(CaptureDirectProfile(contradictory,false,out diagnostic),"primary direct profile");contradictory.requiresPersistentFallbackRegistration=true;Need(!RegisterRole(contradictory,out diagnostic)&&diagnostic.Contains("UNEXPECTED_REGISTRATION_FLAG",StringComparison.Ordinal),"contradictory primary requires flag rejected");denied++;
  var sprite=MakePersistentFallback(transient,"sprite");var spriteAsset=new TMP_SpriteAsset{guid=GuidFor("synthetic-sprite"),localFileId=9100,assetPath="Assets/Synthetic/sprite.asset"};sprite.spriteAsset=spriteAsset;sprite.spriteAssetGuid=spriteAsset.guid;sprite.spriteAssetLocalFileId=spriteAsset.localFileId;sprite.fontAsset=null;sprite.fontAssetGuid=null;sprite.fontAssetLocalFileId=0;sprite.fallbackFontAsset=null;sprite.fallbackFontAssetGuid=null;sprite.fallbackFontAssetLocalFileId=0;sprite.fallbackFontMaterial=null;sprite.fallbackFontMaterialGuid=null;sprite.fallbackFontMaterialLocalFileId=0;sprite.generatedSubmesh=true;sprite.textSlotEnumeration.rows[sprite.materialSlot].sourceAssetKind="sprite";sprite.textSlotEnumeration.rows[sprite.materialSlot].sourceAssetGuid=spriteAsset.guid;sprite.textSlotEnumeration.rows[sprite.materialSlot].sourceAssetLocalFileId=spriteAsset.localFileId;RehashEnum(sprite.textSlotEnumeration);Need(Classify(sprite,out role,out _,out _,out diagnostic)&&role=="sprite","synthetic sprite classifier: "+diagnostic);Need(CaptureDirectProfile(sprite,false,out diagnostic)&&RegisterRole(sprite,out diagnostic),"synthetic sprite direct profile and strict no-registration dispatch: "+diagnostic);var spriteCurrent=sprite.Copy();Need(Classify(spriteCurrent,out _,out _,out _,out diagnostic),"sprite final classifier");Need((bool)typeof(UnityStaticSortTextSource).GetMethod("CarryCaptureSlotRoute",BindingFlags.Public|BindingFlags.Static).Invoke(null,new object[]{sprite,spriteCurrent,null}),"sprite carry accepts exact same-node identity");controls++;
  var multi=MakePersistentFallback(transient,"same-font-multi-atlas");multi.fontAsset=multi.owner.font;multi.fontAssetGuid=multi.owner.font.guid;multi.fontAssetLocalFileId=multi.owner.font.localFileId;multi.fallbackFontAsset=multi.owner.font;multi.fallbackFontAssetGuid=multi.owner.font.guid;multi.fallbackFontAssetLocalFileId=multi.owner.font.localFileId;multi.fallbackFontMaterial=multi.owner.fontSharedMaterial;multi.fallbackFontMaterialGuid=multi.owner.fontSharedMaterial.guid;multi.fallbackFontMaterialLocalFileId=multi.owner.fontSharedMaterial.localFileId;multi.fallbackFontMaterialFingerprint=multi.owner.fontSharedMaterial.fingerprint;multi.owner.font.atlasTextures=new[]{new Texture{guid=GuidFor("primary-atlas"),localFileId=9200,assetPath="Assets/Synthetic/primary.png"},multi.sourceTexture};multi.textSlotEnumeration.rows[multi.materialSlot].sourceAssetKind="font";multi.textSlotEnumeration.rows[multi.materialSlot].sourceAssetGuid=multi.owner.font.guid;multi.textSlotEnumeration.rows[multi.materialSlot].sourceAssetLocalFileId=multi.owner.font.localFileId;RehashEnum(multi.textSlotEnumeration);Need(Classify(multi,out role,out _,out _,out diagnostic)&&role=="fallback-font-same-asset-multi-atlas"&&multi.tmpFallbackAtlasIndex==1,"same-font multi-atlas role and index proof: "+diagnostic);Need(CaptureDirectProfile(multi,false,out diagnostic)&&RegisterRole(multi,out diagnostic),"multi-atlas direct profile and exact skip: "+diagnostic);var multiCurrent=multi.Copy();Need(Classify(multiCurrent,out _,out _,out _,out diagnostic),"multi-atlas final classifier");Need((bool)typeof(UnityStaticSortTextSource).GetMethod("CarryCaptureSlotRoute",BindingFlags.Public|BindingFlags.Static).Invoke(null,new object[]{multi,multiCurrent,null}),"multi-atlas carry exact route");controls++;
 }
 static void SetInitialProviderRoute(TextSlotBinding binding)=>typeof(UnityStaticSortTextSource).GetMethod("SetDesiredRegistrationRoute",BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,new object[]{binding});
 static object RunRoleMatrix(string roleMatrixPath){
  using var matrixDoc=JsonDocument.Parse(File.ReadAllText(roleMatrixPath));var matrix=matrixDoc.RootElement;
  Need(matrix.GetProperty("contract").GetString()=="monkey-text-slot-role-matrix-input/1","role matrix adapter contract");
  var rows=matrix.GetProperty("roleRows").EnumerateArray().ToArray();var counts=new Dictionary<string,int>();var kinds=new Dictionary<string,int>();var perSource=new Dictionary<string,TextSlotBinding>();int registered=0,skippedPrimary=0,skippedOutlineAbsent=0,actualObserved=0;bool actual19PrimarySkip=false;var phases=new List<NativeStaticSortTextCapturePhase>();
  var begin=(Func<string,TMP_Text,NativeStaticSortTextSlotEnumeration,NativeStaticSortTextCaptureLifecycle>)((sid,owner,enumeration)=>UnityStaticSortTextSource.BeginCaptureLifecycle(sid,owner,enumeration));
  foreach(var item in rows){
   var binding=MakeRoleBinding(item);var expected=JS(item,"expectedRole");var kind=JS(item,"sourceFontKind");
   Need(Classify(binding,out var role,out var mode,out var raster,out var classDiagnostic),"production role classification refused evidenced row "+binding.sourceComponentId+" slot="+binding.materialSlot+" expected="+expected+" diagnostic="+classDiagnostic);
   Need(role==expected,"role mismatch "+binding.sourceComponentId+" slot="+binding.materialSlot+" expected="+expected+" actual="+role);
   Need(binding.captureRoleVerified&&binding.observedRoleVerified&&binding.captureRole==role&&binding.observedRole==role,"production classifier role evidence flags");
   counts[role]=counts.GetValueOrDefault(role)+1;kinds[kind]=kinds.GetValueOrDefault(kind)+1;if(!item.TryGetProperty("actual19Failure",out _))actualObserved++;
   perSource.TryAdd(binding.sourceComponentId,binding);
   FinalizeProfileRoute(binding);
   var expectedRequires=(role=="fallback-font-transient"||role=="fallback-font-persistent")&&binding.outlineDriverPresent&&binding.outlineTargetMatchesOwner;
   Need(binding.requiresPersistentFallbackRegistration==expectedRequires,"production profile route requirement "+binding.sourceComponentId+"/"+binding.materialSlot);
   var registeredOk=RegisterRole(binding,out var registerDiagnostic);
   Need(registeredOk,"production registration dispatch failed role="+role+" source="+binding.sourceComponentId+" slot="+binding.materialSlot+" diagnostic="+registerDiagnostic);
   if(expectedRequires){Need(binding.registrationOutcome=="registered"&&binding.registrationDisposition=="required"&&binding.persistentFallbackVariantRegistered&&!binding.requiresPersistentFallbackRegistration,"fallback registration producer state");registered++;}
   else {Need(binding.registrationOutcome=="skipped"&&binding.registrationDisposition=="not-required"&&!binding.persistentFallbackVariantRegistered,"nonregistration route outcome");if(role=="primary-font"){Need(binding.registrationSkipReason=="primary-font-slot-does-not-use-fallback-variant","primary font explicit skip reason");skippedPrimary++;}else if(role.StartsWith("fallback-font-",StringComparison.Ordinal)){Need(binding.registrationSkipReason=="outline-driver-absent","fallback without outline skip reason");skippedOutlineAbsent++;}}
   var enumValid=(bool)typeof(UnityStaticSortTextSource).GetMethod("IsValidTextSlotEnumeration",BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,new object[]{binding.textSlotEnumeration});
   Need(enumValid&&binding.textSlotEnumeration.evidenceContract=="monkey-static-sort-text-slot-enumeration/2"&&binding.textSlotEnumeration.sourceComponentId==binding.sourceComponentId,"role phase enumeration contract is valid: "+binding.sourceComponentId+"/"+binding.textSlotEnumeration.sourceComponentId+"/"+binding.textSlotEnumeration.evidenceContract);
   var phase=UnityStaticSortTextSource.CaptureLifecyclePhase("role-routing-result",binding.materialSlot,binding.owner,binding.sourceComponentId,new[]{binding},binding.textSlotEnumeration);
   Need(phase!=null,"production phase snapshot constructed for role route "+binding.sourceComponentId+";enum="+(binding.textSlotEnumeration?.evidenceSha256??"null"));
   Need(phase.slots!=null&&phase.slots.Length==1&&phase.slots[0]!=null&&phase.slots[0].captureRole==role&&phase.slots[0].registrationDisposition==binding.registrationDisposition&&phase.slots[0].registrationOutcome==binding.registrationOutcome,"production phase snapshot includes role and dispatch outcome");phases.Add(phase);
   if(item.TryGetProperty("actual19Failure",out var actualFailure)){
    Need(actualFailure.GetProperty("code").GetString()=="STATIC_SORT_PROXY_TEXT_FALLBACK_VARIANT_REGISTRATION_FAILED","actual19 pinned failure code");
    Need(role=="primary-font"&&binding.fallbackFontAsset==null&&binding.owner.font.guid==binding.sourceMaterial.guid&&binding.owner.fontSharedMaterial.guid==binding.sourceMaterial.guid,"actual19 FontGYM row is a direct primary font source");
    Need(binding.registrationSkipReason=="primary-font-slot-does-not-use-fallback-variant","actual19 primary registration skip verified");actual19PrimarySkip=true;
   }
  }
  int emptyRoutes=0;foreach(var pair in perSource){var lifecycle=begin(pair.Key,pair.Value.owner,pair.Value.textSlotEnumeration);Need(lifecycle!=null&&lifecycle.slotRoleRoutingContract=="monkey-static-sort-text-slot-role-routing/1","production empty slot route lifecycle contract");foreach(var route in lifecycle.emptySlotRoutes){Need(route.captureRoleVerified&&route.captureRole=="empty-placeholder"&&route.registrationDisposition=="not-required"&&route.registrationOutcome=="skipped"&&route.registrationSkipReason=="empty-placeholder-has-no-drawable-binding","production empty placeholder skip reason");emptyRoutes++;}}
  int unknownRefusals=0;foreach(var unknown in matrix.GetProperty("unresolvedRows").EnumerateArray()){var binding=new TextSlotBinding{sourceComponentId=JS(unknown,"sourceComponentId")};Need(!Classify(binding,out _,out _,out _,out var d)&&!String.IsNullOrEmpty(d),"unobserved source role must fail closed: "+binding.sourceComponentId);unknownRefusals++;}
  // Adversarial checks use copies of exact observed refs; every mismatch must be rejected by production gates.
  var primary=MakeRoleBinding(rows.First(x=>JS(x,"expectedRole")=="primary-font"&&x.TryGetProperty("actual19Failure",out _)));
  var falseFlag=primary.Copy();falseFlag.requiresPersistentFallbackRegistration=true;falseFlag.registrationDisposition="required";falseFlag.registrationOutcome="pending";Need(!RegisterRole(falseFlag,out var falseFlagDiagnostic),"primary false-requires flag rejected");
  var fallbackRow=rows.First(x=>JS(x,"expectedRole")=="fallback-font-transient"&&JB(x,"sourceOutlineEnabled"));var fallback=MakeRoleBinding(fallbackRow);
  var transientSlot=MakeRoleBinding(fallbackRow);
  transientSlot.sourceMaterial.guid=new string('0',32);
  transientSlot.sourceMaterial.localFileId=0;
  var apiIdentity=new object[]{transientSlot.sourceMaterial,null,0L};
  var getIdentity=typeof(UnityStaticSortTextSource).GetMethod("AssetIdentity",BindingFlags.NonPublic|BindingFlags.Static);
  Need(!(bool)getIdentity.Invoke(null,apiIdentity),"transient fallback has no persistent identity");
  var slotRow=transientSlot.textSlotEnumeration.rows[transientSlot.materialSlot];
  slotRow.sourceGraphicMaterialGuid=(string)apiIdentity[1];
  slotRow.sourceGraphicMaterialLocalFileId=(long)apiIdentity[2];
  RehashEnum(transientSlot.textSlotEnumeration);
  Need(Classify(transientSlot,out var sentinelRole,out _,out _,out var sentinelDiagnostic)&&sentinelRole=="fallback-font-transient",
       "Unity empty GUID/0 fallback must classify: "+sentinelDiagnostic);
  slotRow.sourceGraphicMaterialGuid=GuidFor("unexpected-transient-material");
  RehashEnum(transientSlot.textSlotEnumeration);
  Need(!Classify(transientSlot,out _,out _,out _,out var conflict)&&conflict.StartsWith("TMP_SORT_CAPTURE_SLOT_ROLE_TRANSIENT_MATERIAL_IDENTITY_CONFLICT"),
       "conflicting GUID on a transient material must still fail");
  var foreignMaterial=fallback.Copy();foreignMaterial.sourceMaterial=new Material{guid=GuidFor("foreign-fallback-material"),localFileId=9001,assetPath="Assets/foreign.mat",fingerprint=fallback.sourceMaterialFingerprint};foreignMaterial.sourceMaterialGuid=foreignMaterial.sourceMaterial.guid;foreignMaterial.sourceMaterialLocalFileId=9001;Need(!Classify(foreignMaterial,out _,out _,out _,out _),"foreign transient source material rejected");
  var foreignAtlas=fallback.Copy();foreignAtlas.sourceTexture=new Texture{guid=GuidFor("foreign-atlas"),localFileId=fallback.sourceTextureLocalFileId,assetPath=fallback.sourceTexture.assetPath};Need(!Classify(foreignAtlas,out _,out _,out _,out _),"foreign atlas identity rejected");
  var foreignFallback=fallback.Copy();foreignFallback.fallbackFontAsset=new TMP_FontAsset{guid=GuidFor("foreign-font"),localFileId=fallback.fallbackFontAssetLocalFileId,assetPath=fallback.fallbackFontAsset.assetPath};foreignFallback.fallbackFontAssetGuid=foreignFallback.fallbackFontAsset.guid;Need(!Classify(foreignFallback,out _,out _,out _,out _),"foreign fallback font identity rejected");
  var foreignFallbackMaterial=fallback.Copy();foreignFallbackMaterial.registrationDisposition="required";foreignFallbackMaterial.registrationOutcome="pending";foreignFallbackMaterial.fallbackFontMaterial=new Material{guid=GuidFor("foreign-fallback-material"),localFileId=fallback.fallbackFontMaterialLocalFileId,assetPath=fallback.fallbackFontMaterial.assetPath,fingerprint=fallback.fallbackFontMaterialFingerprint};foreignFallbackMaterial.fallbackFontAsset.material=foreignFallbackMaterial.fallbackFontMaterial;Need(!RegisterRole(foreignFallbackMaterial,out var foreignFallbackMaterialDiagnostic),"foreign fallback material identity rejected");
  var falseFallbackFlag=fallback.Copy();falseFallbackFlag.requiresPersistentFallbackRegistration=false;falseFallbackFlag.registrationDisposition="not-required";falseFallbackFlag.registrationOutcome="skipped";falseFallbackFlag.registrationSkipReason="outline-driver-absent";Need(!RegisterRole(falseFallbackFlag,out var falseFallbackDiagnostic),"fallback false-requires route with live outline rejected");
  var foreignOutline=fallback.Copy();foreignOutline.owner.outline=new NativeStaticTextOutline{Target=new TextMeshProUGUI()};Need(!Classify(foreignOutline,out _,out _,out _,out var foreignOutlineDiagnostic)&&foreignOutlineDiagnostic.Contains("OUTLINE_TARGET_MISMATCH",StringComparison.Ordinal),"foreign outline target rejected");
  SyntheticRoleControls(roleMatrixPath,out var syntheticControls,out var syntheticDenied);
  return new{actualObservedSlotsClassified=actualObserved,roleCounts=counts,fontKindCounts=kinds,actual19PrimaryFontSkipVerified=actual19PrimarySkip,emptyPlaceholderRoutes=emptyRoutes,unobservedSlotsRefused=unknownRefusals,fallbackRoutesRegistered=registered,primaryFontRoutesSkipped=skippedPrimary,outlineAbsentFallbacksSkipped=skippedOutlineAbsent,syntheticRoleControls=new{accepted=syntheticControls,denied=syntheticDenied,scope="synthetic identity fixtures; not counted as native source rows"},negativeCases=new[]{"primary-requires-flag", "foreign-transient-material", "foreign-atlas", "foreign-fallback-font", "foreign-fallback-material", "false-fallback-requires-flag", "foreign-outline-target","different-guid-same-fingerprint","unselected-existing-variant","contradictory-requires-flag"},productionMethodsExecuted=new[]{"TryClassifyCaptureSlotRole","CaptureFallbackMaterial direct persistent profile branch","SetRegistrationRouteAfterProfile","RegisterCapturedFallbackVariant","CapturedMaterialIdentityMatches","CarryCaptureSlotRoute","CaptureLifecyclePhase","BeginCaptureLifecycle"}};
 }
 static void Main(string[] args){
  var path=args[0];var inventory=JsonDocument.Parse(File.ReadAllText(path)).RootElement;
  if(args.Length>4){using var roleDoc=JsonDocument.Parse(File.ReadAllText(args[4]));foreach(var roleRow in roleDoc.RootElement.GetProperty("roleRows").EnumerateArray())if(!roleRow.TryGetProperty("actual19Failure",out _))ObservedRoleMetadata.TryAdd(JS(roleRow,"sourceComponentId")+"|"+JL(roleRow,"slot"),roleRow.Clone());RoleMatrixSummary=RunRoleMatrix(args[4]);}
  if(args.Length>3){using var contextsDoc=JsonDocument.Parse(File.ReadAllText(args[3]));Need(contextsDoc.RootElement.GetProperty("storedEvidenceHashesAreNotUsedAsCurrentEvidence").GetBoolean(),"operand adapter explicitly excludes stored evidence hashes");foreach(var row in contextsDoc.RootElement.GetProperty("rows").EnumerateArray()){var sid=row.GetProperty("sourceComponentId").GetString();var slot=row.GetProperty("materialSlot").GetInt32();var context=JsonSerializer.Deserialize<NativeStaticSortTextScaleContext>(row.GetProperty("textScaleContext").GetRawText(),new JsonSerializerOptions{IncludeFields=true});if(!ObservedContexts.TryGetValue(sid,out var bySlot))ObservedContexts[sid]=bySlot=new Dictionary<int,NativeStaticSortTextScaleContext>();Need(!bySlot.ContainsKey(slot),"duplicate observed operand source slot");bySlot.Add(slot,context);}}
  var queue=inventory.GetProperty("queueRendererSourceIds").EnumerateArray().Select(x=>x.GetString()).ToArray();
  Need(queue.Length==87,"actual queue denominator");
  var slotsById=new Dictionary<string,int>();var drawableById=new Dictionary<string,int[]>();var charsById=new Dictionary<string,int[]>();var visibleById=new Dictionary<string,int[]>();
  foreach(var row in inventory.GetProperty("slotReadbacks").EnumerateArray()){var id=row.GetProperty("sourceComponentId").GetString();if(slotsById.ContainsKey(id))continue;var enumeration=row.GetProperty("enumeration");var rows=enumeration.GetProperty("rows").EnumerateArray().ToArray();slotsById[id]=enumeration.GetProperty("slotCount").GetInt32();drawableById[id]=rows.Where(x=>x.GetProperty("disposition").GetString()=="drawable").Select(x=>x.GetProperty("slot").GetInt32()).Distinct().OrderBy(x=>x).ToArray();charsById[id]=rows.Select(x=>x.GetProperty("characterReferences").GetInt32()).ToArray();visibleById[id]=rows.Select(x=>x.GetProperty("visibleCharacterReferences").GetInt32()).ToArray();}
  var groupById=inventory.GetProperty("textGroups").EnumerateArray().ToDictionary(x=>x.GetProperty("sourceLabelId").GetString());
  int observed=0,modeled=0,operandRows=0,modeledOperandGroups=0,totalDrawable=0,phaseRows=0;var receiptRows=new List<object>();bool phaseContextMutationDenied=false;
  foreach(var sid in queue){var g=groupById[sid];var text=g.GetProperty("sourceText").GetString()??"";var n=slotsById.GetValueOrDefault(sid,1);var drawable=drawableById.GetValueOrDefault(sid,new[]{0});if(slotsById.ContainsKey(sid))observed++;else modeled++;
   var refs=charsById.GetValueOrDefault(sid,new[]{1});var visible=visibleById.GetValueOrDefault(sid,new[]{1});var asset=GuidFor("font|"+sid);var atlas=GuidFor("atlas|"+sid);var chars=H("characters|"+sid);ObservedContexts.TryGetValue(sid,out var actualContexts);if(actualContexts!=null){operandRows+=actualContexts.Count;Need(actualContexts.Values.All(c=>c.sourceTextSha256==H(text)),"observed operand text SHA matches inventory source text: "+sid);foreach(var pair in actualContexts){Need(pair.Key<refs.Length&&pair.Value.characters.Length==refs[pair.Key],"observed character reference count matches source slot inventory: "+sid+" slot "+pair.Key);Need(pair.Value.characters.Count(c=>c.visible)==visible[pair.Key],"observed visible character count matches source slot inventory: "+sid+" slot "+pair.Key);}}else if(slotsById.ContainsKey(sid))modeledOperandGroups++;var owner=Owner(sid,text,n,drawable,refs,visible,asset,atlas,chars,actualContexts);Need(owner.bindings.Count==drawable.Length,"provider binding setup has expected drawable rows "+sid+" binds="+owner.bindings.Count+" drawable="+String.Join(",",drawable));if(actualContexts!=null)Need(Math.Abs(owner.transform.lossyScale.y-actualContexts.Values.First().ownerLossyScaleY)<0.000001f,"observed owner scale hydrated: "+sid+" actual="+actualContexts.Values.First().ownerLossyScaleY+" stub="+owner.transform.lossyScale.y);
   var result=ProxyHarness.Run(new ProxyQueueSpec(),new ProxyRendererSpec{sourceComponentId=sid,sourceText=text},owner,out var enumeration);
   Need(result.Count==drawable.Length,"rebound denominator "+sid);Need(UnityStaticSortTextSource.ValidateCaptureLifecycle(result[0].captureLifecycle),"lifecycle receipt "+sid);
   if(!phaseContextMutationDenied){var mutated=JsonSerializer.Deserialize<NativeStaticSortTextCaptureLifecycle>(JsonSerializer.Serialize(result[0].captureLifecycle,new JsonSerializerOptions{IncludeFields=true}),new JsonSerializerOptions{IncludeFields=true});var phase=mutated.phases.First(p=>p.slots!=null&&p.slots.Length>0);phase.slots[0].textScaleContext=null;mutated.evidenceSha256=(string)typeof(UnityStaticSortTextSource).GetMethod("CaptureLifecycleHash",BindingFlags.Public|BindingFlags.Static).Invoke(null,new object[]{mutated});Need(!UnityStaticSortTextSource.ValidateCaptureLifecycle(mutated),"rehashing outer lifecycle cannot legitimize blank per-phase scale context");phaseContextMutationDenied=true;}
   totalDrawable+=result.Count;phaseRows+=result[0].captureLifecycle.phases.Length;
   foreach(var b in result)receiptRows.Add(new{sourceComponentId=sid,materialSlot=b.materialSlot,captureLifecycle=b.captureLifecycle});
  }
  string actual18Refusal=null;
  if(args.Length>2){
   using var failureDoc=JsonDocument.Parse(File.ReadAllText(args[2]));var failureRoot=failureDoc.RootElement;var actualFailure=failureRoot.GetProperty("failure");
   Need(failureRoot.GetProperty("capturedReadOnly").GetBoolean(),"actual18 failure fixture is read-only");
   Need(actualFailure.GetProperty("code").GetString()=="STATIC_SORT_PROXY_TEXT_SLOT_SOURCE_IDENTITY_CHANGED","actual18 failure code");
   Need(actualFailure.GetProperty("phase").GetString()=="final-prepare-pass2","actual18 failure phase");
   Need(failureRoot.GetProperty("contextSnapshot").GetProperty("allContextsBlank").GetBoolean(),"actual18 all phase contexts blank");
   var sid=actualFailure.GetProperty("sourceComponentId").GetString();var sha=actualFailure.GetProperty("sourceTextSha256").GetString();
   var contextArgs=new object[]{null,null,null};
   var contextAccepted=(bool)typeof(UnityStaticSortTextSource).GetMethod("TextLayoutContextMatches",BindingFlags.Public|BindingFlags.Static).Invoke(null,contextArgs);
   var contextDiagnostic=contextArgs[2]?.ToString()??"";
   Need(!contextAccepted && contextDiagnostic=="context-validity=False/False","actual18 blank saved context fails real context validator: "+contextDiagnostic);
   actual18Refusal="source="+sid+";sourceTextSha256="+sha+";phase="+actualFailure.GetProperty("phase").GetString()+";"+contextDiagnostic+";observedCode="+actualFailure.GetProperty("code").GetString();
  }
  var failure=inventory.GetProperty("failure");var failedId=failure.GetProperty("sourceLabelId").GetString();var failureText=groupById[failedId].GetProperty("sourceText").GetString();
  var refusals=new[]{
   Refusal("fallback-registration",()=>UnityStaticSortTextSource.failRegistration=true,"STATIC_SORT_PROXY_TEXT_FALLBACK_VARIANT_REGISTRATION_FAILED",failedId,failureText),
   Refusal("source-text-drift",()=>UnityStaticSortTextSource.driftText=true,"STATIC_SORT_PROXY_TEXT_FINAL_SLOTS_FAILED",failedId,failureText),
   Refusal("font-identity-drift",()=>UnityStaticSortTextSource.driftFont=true,"STATIC_SORT_PROXY_TEXT_FINAL_SOURCE_DENOMINATOR_CHANGED",failedId,failureText),
   Refusal("atlas-identity-drift",()=>UnityStaticSortTextSource.driftAtlas=true,"STATIC_SORT_PROXY_TEXT_FINAL_SOURCE_DENOMINATOR_CHANGED",failedId,failureText),
   Refusal("character-asset-drift",()=>UnityStaticSortTextSource.driftCharacters=true,"STATIC_SORT_PROXY_TEXT_FINAL_SOURCE_DENOMINATOR_CHANGED",failedId,failureText),
   Refusal("slot-count-drift",()=>UnityStaticSortTextSource.driftCount=true,"STATIC_SORT_PROXY_TEXT_FINAL_SLOTS_FAILED",failedId,failureText),
   Refusal("layout-geometry-drift",()=>UnityStaticSortTextSource.driftLayout=true,"STATIC_SORT_PROXY_TEXT_SLOT_SOURCE_IDENTITY_CHANGED",failedId,failureText),
   Refusal("source-mesh-only-drift",()=>UnityStaticSortTextSource.driftMesh=true,"STATIC_SORT_PROXY_TEXT_FINAL_SLOTS_FAILED",failedId,failureText),
   Refusal("fallback-material-profile-drift",()=>UnityStaticSortTextSource.driftMaterial=true,"STATIC_SORT_PROXY_TEXT_SLOT_SOURCE_IDENTITY_CHANGED",failedId,failureText),
   Refusal("scale-operand-drift-with-valid-new-uv",()=>UnityStaticSortTextSource.driftScale=true,"textLayoutContext=",failedId,failureText),
  };
  UnityStaticSortTextSource.ResetProvider();
  var counts=inventory.GetProperty("counts");
  var receipt=new{contract="monkey-actual17-offline-text-capture-receipt/1",evidenceBoundary=new{unityEditorExecuted=false,tmpNativeRenderingExecuted=false,assetDatabaseExecuted=false,persistentReferences="simulated-valid-identities-only",phaseDeltas="synthetic-provider-stimuli;actual17 failure had no captured field delta",observedSourceInventory=true,roleProvenance="This 87-label lifecycle harness models role inputs for schema coverage; those modeled roles are not native source classifications. The separate roleMatrix classifies 59 pinned actual17 saved slots plus the actual19 #20 primary slot, and refuses all 30 remaining actual source groups as role-unresolved."},textSources=receiptRows};
  if(args.Length>1)File.WriteAllText(args[1],JsonSerializer.Serialize(receipt,new JsonSerializerOptions{IncludeFields=true}));
  var report=new {contract="offline-production-method-extraction/1",actualInputs=new{textGroups=counts.GetProperty("textGroups").GetInt32(),queueRendererRows=queue.Length,observedSlotReadbackLabels=observed,modeledQueueLabels=modeled,observedOperandReplayGroups=ObservedContexts.Count,observedOperandReplayRows=operandRows,modeledOperandGroups=modeledOperandGroups,modeledOperandLabels=modeled,modeledUnobservedCharacterPlaceholders=modeledUnobservedCharacterPlaceholders,nonQueueLabels=inventory.GetProperty("notInQueueRendererInputs").GetArrayLength(),actual18ZeroContextRefusal=actual18Refusal!=null},execution=new{queueRowsSucceeded=queue.Length,totalDrawableSlots=totalDrawable,lifecyclePhaseRows=phaseRows,negativeRefusals=refusals.Length+(actual18Refusal==null?0:1)+(phaseContextMutationDenied?1:0),phaseContextMutationDenied=phaseContextMutationDenied,editorExecuted=false,tmpNativeRenderingExecuted=false,assetDatabaseExecuted=false},productionMethodsExecuted=new[]{"CaptureAndRebindTextSlots","GetCurrentSlotsCore context-capture helper surface","CaptureCurrentTextScaleContext","TryBuildTextScaleContext","IsValidTextScaleContext","TextLayoutEvidenceSha256","TextScaleContextUvMatchesMesh","VerifyTextScaleFormulaAgainstMesh","MeshFingerprint","TextLayoutContextMatches","ValidateCapturedSlotTransition","CaptureLifecycleReadyForRebind","CapturePhaseSlotsMatchEnumeration","CaptureLifecycleHash","ValidateCaptureLifecycle","FinalizeCaptureLifecycle","TextSlotRowHash(v2)","TextSlotEnumerationHash(v2)"},providerBoundaries=new[]{"Observed 57-group/59-slot layout, Canvas, TMP character, and UV0.w operands are hydrated from pinned saved native17 evidence; current contexts and hashes are recomputed by production builder","Unity/TMP object creation, mesh positions/topology, asset identities, and persistence remain deterministic stubs","GetCurrentSlots, PrepareSource, fallback profile bake/registration, and RebindCapturedSlot surface are providers","The 87-row lifecycle assigns modeled role inputs solely to exercise lifecycle shape; those role values are not actual source classifications. The separate roleMatrix executes production classification, direct persistent profile, strict registration and carry on 59 pinned actual17 slots plus actual19 #20, and refuses the other 30 unknown groups","RebindCapturedSlot provider calls exact production VerifyTextScaleFormulaAgainstMesh and ValidateCapturedSlotTransition; full RebindCapturedSlot body is not invoked","Production context capture, validity, layout hash, UV0 comparison, and TMP equation execute against hydrated or explicitly modeled operands","30 queue groups without saved slot inputs use modeled TMP/Canvas/UV operands; no stored context hash is reused","Gaps in observed global character indices are filled with invisible materialSlot=-1 placeholders and filtered out by production slot-context sampling"},actual18ZeroContextDiagnostic=actual18Refusal,roleMatrix=RoleMatrixSummary,refusals,failureBoundary=inventory.GetProperty("observedPhaseDeltaBoundary").Clone()};
  Console.WriteLine(JsonSerializer.Serialize(report));
 }
}
}
''' + r'''
namespace UnityEngine {
 public enum HideFlags {None=0,HideAndDontSave=1}
 public class Object {public string guid,assetPath,name;public long localFileId;public HideFlags hideFlags;public static void DestroyImmediate(Object o){}}
 public struct Vector2 {public float x,y;public Vector2(float a,float b){x=a;y=b;}}
 public struct Vector3 {public float x,y,z;public Vector3(float a,float b,float c){x=a;y=b;z=c;}public static implicit operator Vector4(Vector3 x)=>new Vector4{x=x.x,y=x.y,z=x.z,w=0};}
 public struct Vector4 {public float x,y,z,w;}
 public struct Rect {public float width,height;public Rect(float w,float h){width=w;height=h;}}
 public struct Color32 {public byte r,g,b,a;}
 public class Transform {public Vector3 lossyScale=new Vector3(1,1,1);}
 public class RectTransform:Transform {public Rect rect=new Rect(100,28);public Vector2 pivot=new Vector2(.5f,.5f);}
 public enum RenderMode {ScreenSpaceOverlay=0,ScreenSpaceCamera=1,WorldSpace=2}
 public class Canvas:Object {public RenderMode renderMode=RenderMode.ScreenSpaceOverlay;public float scaleFactor=1;public Object worldCamera;public static void ForceUpdateCanvases(){}}
 public static class Mathf {public static bool Approximately(float a,float b)=>Math.Abs(a-b)<0.0001f;public static float Abs(float x)=>Math.Abs(x);}
 public class Material:Object {public string fingerprint;public Shader shader;readonly Dictionary<string,Texture> textures=new();public Material(){}public Material(Material other){if(other!=null){fingerprint=other.fingerprint;shader=other.shader;guid=other.guid;localFileId=other.localFileId;assetPath=other.assetPath;foreach(var pair in other.textures)textures[pair.Key]=pair.Value;}}public Texture GetTexture(string key)=>textures.GetValueOrDefault(key);}
 public class Shader:Object {}
 public class Texture:Object {}
 public class Mesh:Object {public int vertexCount,subMeshCount=1;public Vector3[] vertices=Array.Empty<Vector3>(),normals=Array.Empty<Vector3>();public Color32[] colors32=Array.Empty<Color32>();public Vector4[] tangents=Array.Empty<Vector4>();public Vector4[] uv0=Array.Empty<Vector4>();public int[] triangles=Array.Empty<int>();public bool HasVertexAttribute(UnityEngine.Rendering.VertexAttribute a)=>a==UnityEngine.Rendering.VertexAttribute.TexCoord0;public int GetVertexAttributeDimension(UnityEngine.Rendering.VertexAttribute a)=>a==UnityEngine.Rendering.VertexAttribute.TexCoord0?4:0;public void GetUVs(int channel,List<Vector4> result){result.Clear();if(channel==0)result.AddRange(uv0);}public int[] GetTriangles(int submesh)=>triangles;}
}
namespace UnityEngine.Rendering {public enum VertexAttribute {TexCoord0=0}}
namespace UnityEngine.TextCore.LowLevel {public enum GlyphRenderMode {RASTER=32}}
namespace UnityEngine.UI {
 public class Graphic:UnityEngine.Object {public UnityEngine.Transform transform=new UnityEngine.RectTransform();}
 public class ContentSizeFitter:UnityEngine.Object {public enum FitMode{Unconstrained=0,MinSize=1,PreferredSize=2}public FitMode horizontalFit,verticalFit;public bool isActiveAndEnabled=true;}
}
namespace TMPro {
 public enum TMP_TextElementType {Character=0,Sprite=1}
 public enum FontStyles {Normal=0,Bold=1,Italic=2,Underline=4,UpperCase=8,LowerCase=16,SmallCaps=32}
 public class TMP_FontAsset:UnityEngine.Object{public UnityEngine.Material material;public UnityEngine.Texture[] atlasTextures=Array.Empty<UnityEngine.Texture>();public int atlasRenderMode;}
 public class TMP_SpriteAsset:UnityEngine.Object{}
 public sealed class TMP_TextElement {public uint unicode;}
 public sealed class TMP_CharacterInfo {public int characterIndex,materialReferenceIndex,vertexIndex;public TMP_TextElement textElement;public char character;public float scale=1;public bool isVisible=true,isUsingAlternateTypeface;public TMP_TextElementType elementType=TMP_TextElementType.Character;public FontStyles style=FontStyles.Normal;}
 public sealed class TMP_TextInfo {public int lineCount=1,materialCount,characterCount;public TMP_CharacterInfo[] characterInfo=Array.Empty<TMP_CharacterInfo>();}
  public class TMP_Text:UnityEngine.UI.Graphic {
  private float m_charWidthAdjDelta=0,m_characterHorizontalScale=1;
  public string text;public TMP_FontAsset font;public UnityEngine.Material fontSharedMaterial;public UnityEngine.Canvas canvas=new UnityEngine.Canvas();public TMP_TextInfo textInfo=new TMP_TextInfo();
  public Monkey.StaticMaskSort.NativeTextLineBox lineBox;public UnityEngine.UI.ContentSizeFitter fitter;public void SetScaleInternals(float widthAdj,float horizontal){m_charWidthAdjDelta=widthAdj;m_characterHorizontalScale=horizontal;}
  public bool isUsingBold;public List<Monkey.StaticSortQueueProxy.TextSlotBinding> bindings,finalBindings;public Monkey.StaticSortQueueProxy.NativeStaticSortTextSlotEnumeration enumeration,finalEnumeration;
  public Monkey.StaticSortQueueProxy.NativeStaticTextOutline outline;public bool finalSnapshot,driftSlotCount,layoutGeometryDrifted;public UnityEngine.Vector4 margin;public float fontSize=28,fontSizeMin=0,fontSizeMax=0,characterSpacing,wordSpacing,lineSpacing,lineSpacingAdjustment,paragraphSpacing;public bool enableAutoSizing,extraPadding,richText=true,parseCtrlCharacters=true,isRightToLeftText,useMaxVisibleDescender;public FontStyles fontStyle=FontStyles.Normal;public int fontWeight=400,alignment,textWrappingMode,overflowMode,maxVisibleCharacters=99999,maxVisibleWords=99999,maxVisibleLines=99999,pageToDisplay=1;public int[] fontFeatures=Array.Empty<int>();
  public T GetComponent<T>() where T:class {if(typeof(T)==typeof(Monkey.StaticMaskSort.NativeTextLineBox))return lineBox as T;if(typeof(T)==typeof(UnityEngine.UI.ContentSizeFitter))return fitter as T;if(typeof(T)==typeof(Monkey.StaticSortQueueProxy.NativeStaticTextOutline))return outline as T;return null;}public string GetParsedText()=>text;
 }
 public class TextMeshProUGUI:TMP_Text{}
 public static class ShaderUtilities {public static float GetPadding(UnityEngine.Material material,bool extraPadding,bool bold)=>0f;}
 public static class TMP_MaterialManager {public static UnityEngine.Material GetFallbackMaterial(UnityEngine.Material source,UnityEngine.Material fallback)=>new UnityEngine.Material(source);}
}
namespace Monkey.StaticMaskSort {public class NativeTextLineBox:UnityEngine.Object {public float LineHeight,ExtraLineFraction,preferredHeight;public bool isActiveAndEnabled=true;}}
namespace Monkey.StaticSortQueueProxy {public sealed class NativeStaticTextOutline:UnityEngine.Object {public TMPro.TMP_Text Target;public int registrationCount;public bool selected;public bool RegisterPersistentMaterialVariant(TMPro.TMP_FontAsset font,UnityEngine.Material material,UnityEngine.Material parentFontMaterial,float fontSize,UnityEngine.Texture atlas,out string diagnostic){registrationCount++;diagnostic=null;selected=font!=null&&material!=null&&atlas!=null;return selected;}public bool IsPersistentMaterialVariantSelected(TMPro.TMP_FontAsset font,UnityEngine.Material parentFontMaterial,UnityEngine.Texture atlas,UnityEngine.Material material)=>selected&&font!=null&&atlas!=null&&material!=null;public bool ConfigureCaptureCandidate(UnityEngine.Material material,TMPro.TMP_FontAsset font,float size,out string diagnostic){diagnostic=null;return material!=null&&font!=null;}}}
namespace UnityEditor {
 public enum SerializedPropertyType {Enum=0}
 public sealed class SerializedProperty {public SerializedPropertyType propertyType=SerializedPropertyType.Enum;public int intValue;public SerializedProperty(int value){intValue=value;}}
 public sealed class SerializedObject {readonly TMPro.TMP_FontAsset font;public SerializedObject(UnityEngine.Object o){font=o as TMPro.TMP_FontAsset;}public SerializedProperty FindProperty(string name)=>name=="m_AtlasRenderMode"&&font!=null?new SerializedProperty(font.atlasRenderMode):null;}
 public static class EditorUtility {public static void SetDirty(UnityEngine.Object o){}}
 public static class PrefabUtility {public static void RecordPrefabInstancePropertyModifications(UnityEngine.Object o){}}
 public static class AssetDatabase {public static bool TryGetGUIDAndLocalFileIdentifier(UnityEngine.Object x,out string g,out long id){g=x?.guid;id=x?.localFileId??0;return x!=null;}public static string GetAssetPath(UnityEngine.Object x)=>x?.assetPath;public static bool IsValidFolder(string path)=>true;public static T LoadAssetAtPath<T>(string path) where T:UnityEngine.Object=>null;public static void CreateAsset(UnityEngine.Object asset,string path){asset.assetPath=path;}}}
static class JsonUtility {public static string ToJson(object x,bool pretty=false)=>JsonSerializer.Serialize(x,new JsonSerializerOptions{IncludeFields=true});}
'''


def test_actual17_text_slot_inventory_and_unknown_phase_delta():
    _, inv = _inventory()
    assert inv["capturedReadOnly"] is True
    assert inv["counts"]["textGroups"] == 119
    assert inv["counts"]["queuedTextGroups"] == 87
    assert inv["counts"]["queuedObservedSlotGroups"] == 57
    assert len(inv["slotReadbacks"]) == 118
    assert len(inv["queuedUnobservedSlotLabels"]) == 30
    assert len(inv["notInQueueRendererInputs"]) == 32
    assert inv["observedPhaseDeltaBoundary"]["capturedPerPhaseDelta"] is False
    assert inv["failure"]["sourceLabelId"] in inv["queueRendererSourceIds"]
    assert _verify_readonly_pins(inv) == []


def test_actual19_fontgym_registration_failure_and_full_role_denominator():
    _, inventory = _inventory()
    failure_path = Path(os.environ.get("MONKEY_ACTUAL19_TEXT_FAILURE", DEFAULT_ACTUAL19_FAILURE))
    index_path = Path(os.environ.get("MONKEY_ACTUAL19_TEXT_INDEX", DEFAULT_ACTUAL19_INDEX))
    saved_path = Path(os.environ.get("MONKEY_ACTUAL17_SAVED_TEXT_CONTEXTS", DEFAULT_SAVED_TEXT_CONTEXTS))
    assert failure_path.is_file() and index_path.is_file() and saved_path.is_file()
    fixture_sha_before = hashlib.sha256(failure_path.read_bytes()).hexdigest()
    failure = json.loads(failure_path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    saved = json.loads(saved_path.read_text(encoding="utf-8"))
    sid = "gameAsset:353b7dbc-149d-49d5-9422-f71874ff1eab#20"
    assert failure["code"] == "STATIC_SORT_PROXY_TEXT_FALLBACK_VARIANT_REGISTRATION_FAILED"
    assert failure["phase"] == "register-fallback-variant-refused"
    assert failure["sourceComponentId"] == sid == index["sourceId"]
    assert index["failureSnapshot"] == str(failure_path)
    assert index["diagnostic"] == failure["diagnostic"]
    assert failure["diagnostic"].endswith("TMP_SORT_CAPTURED_FALLBACK_REGISTRATION_INPUT_INVALID")
    row = failure["expectedEnumeration"]["rows"][0]
    owner = failure["lifecycle"]
    assert row["disposition"] == "drawable" and row["sourceAssetKind"] == "font"
    assert row["sourceAssetGuid"] == row["sourceGraphicMaterialGuid"] == row["textInfoMaterialGuid"]
    assert row["sourceAssetLocalFileId"] == owner["ownerFontAssetLocalFileId"]
    assert row["sourceGraphicMaterialLocalFileId"] == row["textInfoMaterialLocalFileId"] == owner["ownerFontMaterialLocalFileId"]
    assert row["sourceGraphicMaterialFingerprint"] == row["textInfoMaterialFingerprint"] == owner["ownerFontMaterialFingerprint"]
    assert owner["ownerFontAssetGuid"] == owner["ownerFontMaterialGuid"] == row["sourceAssetGuid"]
    assert owner["ownerFontAssetLocalFileId"] == 11400000
    assert owner["ownerFontMaterialLocalFileId"] == row["sourceGraphicMaterialLocalFileId"] != 0
    assert owner["phases"][2]["slots"][0]["tmpFallbackMaterialBaked"] is False
    assert owner["phases"][2]["slots"][0]["requiresPersistentFallbackRegistration"] is False

    groups = {group["sourceLabelId"]: group for group in inventory["textGroups"]}
    queue = inventory["queueRendererSourceIds"]
    assert len(queue) == 87
    assert collections.Counter(groups[source_id]["fontKind"] for source_id in queue) == {
        "system-font": 48,
        "bitmap-font": 26,
        "explicit-ttf": 13,
    }
    enum_by_source = {}
    for readback in inventory["slotReadbacks"]:
        enum_by_source.setdefault(readback["sourceComponentId"], readback["enumeration"])
    saved_by_source_slot = {(row["sourceComponentId"], row["materialSlot"]): row for row in saved["rows"]}
    primary = collections.Counter()
    observed_roles = collections.Counter()
    actual_drawable = 0
    empty_placeholders = 0
    unresolved = 0
    for source_id in queue:
        enumeration = enum_by_source.get(source_id)
        if enumeration is None:
            # These 30 rows have no prior slot readback. Keep their role unknown.
            unresolved += 1
            continue
        for slot_row in enumeration["rows"]:
            if slot_row["disposition"] == "empty-placeholder":
                empty_placeholders += 1
                continue
            actual_drawable += 1
            saved_row = saved_by_source_slot.get((source_id, slot_row["slot"]))
            if saved_row is None:
                unresolved += 1
                continue
            identity = saved_row["sourceIdentityAndResourceIds"]
            owner_material = identity["ownerFontMaterial"]
            source_material = identity["sourceMaterial"]
            fallback_font = identity["fallbackFontAsset"]
            fallback_material = identity["fallbackFontMaterial"]
            assert identity["serializedSlotFontAsset"]["guid"] == slot_row["sourceAssetGuid"]
            assert identity["serializedSlotFontAsset"]["localFileId"] == slot_row["sourceAssetLocalFileId"]
            assert identity["sourceTexture"]["guid"] == slot_row["atlasGuid"]
            assert identity["sourceTexture"]["localFileId"] == slot_row["atlasLocalFileId"]
            if source_material["guid"] == owner_material["guid"] and source_material["localFileId"] == owner_material["localFileId"]:
                role = "primary-font"
                primary[groups[source_id]["fontKind"]] += 1
            elif fallback_font["guid"] and fallback_material["guid"] and not source_material["guid"] and source_material["localFileId"] == 0:
                role = "fallback-font-transient"
                assert fallback_font["guid"] == slot_row["sourceAssetGuid"]
                observed_roles[groups[source_id]["fontKind"]] += 1
            elif fallback_font["guid"] and fallback_material["guid"] and source_material["guid"] and source_material["localFileId"] != 0:
                role = "fallback-font-persistent"
                observed_roles["persistent"] += 1
            elif identity["serializedSlotSpriteAsset"]["guid"]:
                role = "sprite"
                observed_roles["sprite"] += 1
            else:
                role = "unresolved"
                unresolved += 1
            if role == "primary-font":
                assert source_material["guid"] == owner_material["guid"]
                assert source_material["localFileId"] == owner_material["localFileId"]
    assert actual_drawable == 59
    assert empty_placeholders == 21
    assert unresolved == 30
    assert primary == {"bitmap-font": 15, "explicit-ttf": 13, "system-font": 8}
    assert observed_roles == {"system-font": 23}
    saved_project_root = Path(os.environ.get(
        "MONKEY_ACTUAL17_SAVED_PROJECT_ROOT",
        "/Users/wangmeng/MyProjects/Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/" + saved["source"]["unityProjectRoot"],
    ))
    actual19_project_root = failure_path.parents[3]
    matrix_input = _role_matrix_input(inventory, saved, failure, saved_project_root, actual19_project_root)
    assert len(matrix_input["roleRows"]) == 60
    assert len(matrix_input["emptySlotRoutes"]) == 21
    assert len(matrix_input["unresolvedRows"]) == 30
    assert matrix_input["observedDrawableRoleCounts"] == {"primary-font": 36, "fallback-font-transient": 23}
    assert hashlib.sha256(failure_path.read_bytes()).hexdigest() == fixture_sha_before


def test_actual17_saved_fallback_profiles_are_persistent_and_exact():
    saved_path = Path(os.environ.get("MONKEY_ACTUAL17_SAVED_TEXT_CONTEXTS", DEFAULT_SAVED_TEXT_CONTEXTS))
    saved = json.loads(saved_path.read_text(encoding="utf-8"))
    project_root = Path(os.environ.get(
        "MONKEY_ACTUAL17_SAVED_PROJECT_ROOT",
        "/Users/wangmeng/MyProjects/Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/" + saved["source"]["unityProjectRoot"],
    ))
    source_hash_before = hashlib.sha256(saved_path.read_bytes()).hexdigest()
    pinned = saved["inputPinsBefore"]
    profile_asset_hashes = {}
    asset_paths_by_guid = {}
    for meta_path in (project_root / "Assets").rglob("*.meta"):
        meta_text = meta_path.read_text(encoding="utf-8", errors="ignore")
        guid_match = re.search(r"^guid: ([0-9a-fA-F]{32})$", meta_text, re.MULTILINE)
        if guid_match:
            asset_paths_by_guid[guid_match.group(1)] = meta_path.with_suffix("")
    actual_roles = collections.Counter()
    registration_rows = collections.Counter()
    groups, _ = _inventory()
    inventory = json.loads(groups.read_text(encoding="utf-8"))
    source_groups = {row["sourceLabelId"]: row for row in inventory["textGroups"]}
    for saved_row in saved["rows"]:
        prefab_relative = saved_row["sourcePrefabPath"]
        assert prefab_relative in pinned
        prefab_path = project_root / prefab_relative
        assert hashlib.sha256(prefab_path.read_bytes()).hexdigest() == pinned[prefab_relative]
        block = _saved_text_source_yaml_block(project_root, prefab_relative, saved_row["sourceComponentId"], saved_row["materialSlot"])
        identity = saved_row["sourceIdentityAndResourceIds"]
        owner_material = identity["ownerFontMaterial"]
        source_material = identity["sourceMaterial"]
        fallback_font = identity["fallbackFontAsset"]
        slot_font = identity["serializedSlotFontAsset"]
        assert _yaml_ref(block, "fontAsset") == slot_font
        assert _yaml_ref(block, "ownerFontSharedMaterial") == {"localFileId": owner_material["localFileId"], "guid": owner_material["guid"]}
        assert _yaml_ref(block, "sourceTexture") == identity["sourceTexture"]
        assert _yaml_ref(block, "fallbackFontAsset") == fallback_font
        if source_material["guid"] == owner_material["guid"] and source_material["localFileId"] == owner_material["localFileId"]:
            role = "primary-font"
            actual_roles[role] += 1
            assert _yaml_ref(block, "sourceMaterial") == {"localFileId": source_material["localFileId"], "guid": source_material["guid"]}
            assert _yaml_ref(block, "proxyMaterial") == _yaml_ref(block, "sourceMaterial")
            assert "  tmpFallbackMaterialBaked: 0" in block
            assert "  persistentFallbackVariantRegistered: 0" in block
        elif fallback_font["guid"] and identity["fallbackFontMaterial"]["guid"] and not source_material["guid"]:
            role = "fallback-font-transient"
            actual_roles[role] += 1
            assert _yaml_ref(block, "sourceMaterial")["localFileId"] == 0
            assert _yaml_ref(block, "proxyMaterial")["guid"]
            assert _yaml_ref(block, "proxyMaterial")["localFileId"] != 0
            assert "  tmpFallbackMaterialBaked: 1" in block
            assert _yaml_ref(block, "proxyMaterial")["guid"] == _yaml_scalar(block, "bakedProxyMaterialGuid")
            assert _yaml_ref(block, "proxyMaterial")["localFileId"] == int(_yaml_scalar(block, "bakedProxyMaterialLocalFileId"))
            assert _yaml_scalar(block, "bakedProxyMaterialFingerprint") == source_material["fingerprint"]
            registration_rows["registered" if _yaml_scalar(block, "persistentFallbackVariantRegistered") == "1" else "skipped"] += 1
        else:
            raise AssertionError(f"unclassified saved slot role at {saved_row['sourceComponentId']} slot {saved_row['materialSlot']}")

        proxy_guid = _yaml_ref(block, "proxyMaterial")["guid"]
        profile_path = asset_paths_by_guid.get(proxy_guid)
        assert profile_path is not None and profile_path.is_file()
        profile_asset_hashes[str(profile_path)] = hashlib.sha256(profile_path.read_bytes()).hexdigest()
    assert actual_roles == {"primary-font": 36, "fallback-font-transient": 23}
    assert registration_rows == {"registered": 22, "skipped": 1}
    for raw_path, expected_sha in profile_asset_hashes.items():
        assert hashlib.sha256(Path(raw_path).read_bytes()).hexdigest() == expected_sha
    assert hashlib.sha256(saved_path.read_bytes()).hexdigest() == source_hash_before


def test_current_production_capture_chain_against_all_actual17_queue_ids(tmp_path):
    dotnet = shutil.which("dotnet") or ("/opt/homebrew/bin/dotnet" if Path("/opt/homebrew/bin/dotnet").exists() else None)
    if not dotnet:
        pytest.skip(".NET SDK unavailable")
    inventory_path, inv = _inventory()
    inventory_sha_before = hashlib.sha256(inventory_path.read_bytes()).hexdigest()
    assert _verify_readonly_pins(inv) == []
    actual18_path = Path(os.environ.get("MONKEY_ACTUAL18_TEXT_CONTEXT_FAILURE", DEFAULT_ACTUAL18_FAILURE))
    saved_context_path = Path(os.environ.get("MONKEY_ACTUAL17_SAVED_TEXT_CONTEXTS", DEFAULT_SAVED_TEXT_CONTEXTS))
    assert actual18_path.is_file(), "pinned actual18 context failure fixture is required for the lifecycle regression"
    assert saved_context_path.is_file(), "pinned native17 saved contexts are required for scale-context replay"
    actual18_fixture = json.loads(actual18_path.read_text(encoding="utf-8"))
    saved_fixture = json.loads(saved_context_path.read_text(encoding="utf-8"))
    actual19_path = Path(os.environ.get("MONKEY_ACTUAL19_TEXT_FAILURE", DEFAULT_ACTUAL19_FAILURE))
    actual19_fixture = json.loads(actual19_path.read_text(encoding="utf-8"))
    assert actual18_fixture["contextSnapshot"]["allContextsBlank"] is True
    assert len(saved_fixture["rows"]) == 59
    saved_project_root = Path(os.environ.get(
        "MONKEY_ACTUAL17_SAVED_PROJECT_ROOT",
        "/Users/wangmeng/MyProjects/Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/" + saved_fixture["source"]["unityProjectRoot"],
    ))
    for relative, expected_sha in saved_fixture["inputPinsBefore"].items():
        source = saved_project_root / relative
        assert source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest() == expected_sha
    normalized_contexts_path = tmp_path / "actual17-context-operands-adapter.json"
    _normalize_saved_context_fixture(saved_context_path, normalized_contexts_path)
    actual19_project_root = actual19_path.parents[3]
    role_matrix = _role_matrix_input(inv, saved_fixture, actual19_fixture, saved_project_root, actual19_project_root)
    role_matrix_path = tmp_path / "actual19-role-matrix-input.json"
    role_matrix_path.write_text(json.dumps(role_matrix, indent=2) + "\n", encoding="utf-8")
    role_asset_hashes_before = {}
    for project_key, project_root in (("actual17", saved_project_root), ("actual19", actual19_project_root)):
        for _, hashes in role_matrix["assetFilePins"][project_key].items():
            relative = hashes["path"]
            asset = project_root / relative
            assert asset.is_file() and hashlib.sha256(asset.read_bytes()).hexdigest() == hashes["assetSha256"]
            assert asset.with_suffix(asset.suffix + ".meta").is_file()
            assert hashlib.sha256(asset.with_suffix(asset.suffix + ".meta").read_bytes()).hexdigest() == hashes["metaSha256"]
            role_asset_hashes_before[(project_key, relative)] = hashes
    proxy = (ROOT / "src/monkey/targets/UnityStaticSortQueueProxy.cs").read_text(encoding="utf-8")
    text = (ROOT / "src/monkey/targets/UnityStaticSortTextSource.cs").read_text(encoding="utf-8")
    native = (ROOT / "src/monkey/targets/NativeStaticSortTextSource.cs").read_text(encoding="utf-8")
    harness = tmp_path / "Harness.cs"
    harness.write_text(_csharp_program(proxy, text, native), encoding="utf-8")
    (tmp_path / "Harness.csproj").write_text(
        '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><Nullable>disable</Nullable><EnableDefaultCompileItems>true</EnableDefaultCompileItems><NoWarn>CS0649;CS0169;CS0414</NoWarn></PropertyGroup></Project>',
        encoding="utf-8",
    )
    (tmp_path / "NuGet.Config").write_text('<configuration><packageSources><clear /></packageSources></configuration>', encoding="utf-8")
    build = subprocess.run([dotnet, "build", str(tmp_path / "Harness.csproj"), "--configfile", str(tmp_path / "NuGet.Config"), "--nologo", "-v:q"], capture_output=True, text=True, timeout=120)
    assert build.returncode == 0, build.stdout + build.stderr
    receipt_path = Path(os.environ.get("MONKEY_TEXT_SLOT_LIFECYCLE_RECEIPT", tmp_path / "actual17-modeled-text-sources.json"))
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([dotnet, "exec", str(tmp_path / "bin/Debug/net8.0/Harness.dll"), str(inventory_path), str(receipt_path), str(actual18_path), str(normalized_contexts_path), str(role_matrix_path)], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report["execution"]["queueRowsSucceeded"] == 87
    assert report["execution"]["editorExecuted"] is False
    assert report["execution"]["tmpNativeRenderingExecuted"] is False
    assert report["execution"]["assetDatabaseExecuted"] is False
    assert report["actualInputs"]["observedSlotReadbackLabels"] == 57
    assert report["actualInputs"]["modeledQueueLabels"] == 30
    assert report["actualInputs"]["observedOperandReplayGroups"] == 57
    assert report["actualInputs"]["observedOperandReplayRows"] == 59
    assert report["actualInputs"]["modeledOperandGroups"] == 0
    assert report["actualInputs"]["modeledOperandLabels"] == 30
    assert report["failureBoundary"]["capturedPerPhaseDelta"] is False
    assert report["execution"]["negativeRefusals"] == 12
    assert report["execution"]["phaseContextMutationDenied"] is True
    assert report["actualInputs"]["actual18ZeroContextRefusal"] is True
    assert "context-validity=False/False" in report["actual18ZeroContextDiagnostic"]
    assert any(row["name"] == "scale-operand-drift-with-valid-new-uv" for row in report["refusals"])
    assert report["roleMatrix"]["actualObservedSlotsClassified"] == 59
    assert report["roleMatrix"]["actual19PrimaryFontSkipVerified"] is True
    assert report["roleMatrix"]["unobservedSlotsRefused"] == 30
    assert report["roleMatrix"]["syntheticRoleControls"] == {
        "accepted": 4, "denied": 3, "scope": "synthetic identity fixtures; not counted as native source rows"
    }
    assert {"different-guid-same-fingerprint", "unselected-existing-variant", "contradictory-requires-flag"}.issubset(
        set(report["roleMatrix"]["negativeCases"])
    )
    assert "CaptureFallbackMaterial direct persistent profile branch" in report["roleMatrix"]["productionMethodsExecuted"]
    assert "CarryCaptureSlotRoute" in report["roleMatrix"]["productionMethodsExecuted"]
    assert "ValidateCapturedSlotTransition" in report["productionMethodsExecuted"]
    assert "full RebindCapturedSlot body is not invoked" in " ".join(report["providerBoundaries"])
    exported = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert len(exported["textSources"]) == report["execution"]["totalDrawableSlots"]
    assert exported["evidenceBoundary"]["persistentReferences"] == "simulated-valid-identities-only"
    assert hashlib.sha256(inventory_path.read_bytes()).hexdigest() == inventory_sha_before
    assert _verify_readonly_pins(inv) == []
    assert _verify_actual18_pins(actual18_fixture) == []
    for relative, expected_sha in saved_fixture["inputPinsBefore"].items():
        source = saved_project_root / relative
        assert hashlib.sha256(source.read_bytes()).hexdigest() == expected_sha
    for (project_key, relative), hashes in role_asset_hashes_before.items():
        project_root = saved_project_root if project_key == "actual17" else actual19_project_root
        asset = project_root / relative
        assert hashlib.sha256(asset.read_bytes()).hexdigest() == hashes["assetSha256"]
        assert hashlib.sha256(asset.with_suffix(asset.suffix + ".meta").read_bytes()).hexdigest() == hashes["metaSha256"]
    report_path = os.environ.get("MONKEY_TEXT_SLOT_LIFECYCLE_REPORT")
    if report_path:
        destination = Path(report_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
