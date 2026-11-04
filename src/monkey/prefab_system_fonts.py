"""Prepare evidence-pinned Unity TMP DynamicOS system-font bindings.

This module consumes an IR and a macOS CoreText resolution receipt. It creates
Unity-facing font specifications only; the Unity Editor helper owns native
TMP asset creation and readback.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping


SCHEMA = "monkey-unity-system-fonts/1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class SystemFontPreparation:
    status: str
    record: dict[str, Any]


@dataclass(frozen=True)
class StaticSdfInputStaging:
    status: str
    record: dict[str, Any]


def _needs_action(reason: str, *, receipt_sha256: str | None = None) -> SystemFontPreparation:
    return SystemFontPreparation("needs_action", {
        "schema": SCHEMA,
        "status": "needs_action",
        "reason": reason,
        "resolutionReceiptSha256": receipt_sha256,
        "systemFonts": None,
        "labelBindings": [],
    })


def _font_key(family: str, style: str, role: str, fallbacks: list[str] | None = None) -> str:
    identity = {
        "schema": SCHEMA,
        "familyName": family,
        "styleName": style,
        "role": role,
        "fallbackAssetIds": list(fallbacks or []),
    }
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"system-font-{digest[:24]}"


def _asset_path(asset_id: str) -> str:
    return f"Assets/Game/Content/Fonts/System/{asset_id.removeprefix('system-font-')}.asset"


def _font_spec(asset_id: str, family: str, style: str, role: str, point_size: int = 90,
               population_mode: str = "DynamicOS") -> dict[str, Any]:
    asset_path = (f"Assets/Game/Content/Fonts/System/Static/{asset_id.removeprefix('coretext-static-sdf-')}.asset"
                  if population_mode == "StaticSDFRequired" else _asset_path(asset_id))
    return {
        "assetId": asset_id,
        "assetPath": asset_path,
        "familyName": family,
        "styleName": style,
        "role": role,
        "pointSize": point_size,
        "populationMode": population_mode,
        "fallbackAssetIds": [],
        "requiredGlyphs": [],
        "requiredGlyphMap": {},
        "sourceLabelIds": set(),
    }


def _add_glyph(font: dict[str, Any], scalar: Mapping[str, Any], label_id: str) -> None:
    codepoint = scalar.get("scalarValue")
    character = scalar.get("character")
    if isinstance(codepoint, bool) or not isinstance(codepoint, int) or not isinstance(character, str) or len(character) == 0:
        raise ValueError(f"invalid CoreText scalar record for {label_id}")
    font["requiredGlyphMap"][codepoint] = {"unicode": codepoint, "codepoint": scalar.get("codepoint"), "character": character}
    font["sourceLabelIds"].add(label_id)


def prepare(
    ir: Mapping[str, Any],
    ir_sha256: str,
    resolution_path: str | Path,
    expected_resolution_sha256: str,
) -> SystemFontPreparation:
    """Prepare per-label native TMP bindings from the exact current resolution receipt.

    The source font fields remain unchanged in the returned declaration. Native
    binding is separate, per-label, and keyed by the CoreText primary/fallback
    family+style combination so distinct fallback chains never get merged.
    """
    receipt_path = Path(resolution_path)
    if not _SHA256.fullmatch(ir_sha256) or not _SHA256.fullmatch(expected_resolution_sha256):
        return _needs_action("IR and resolution receipt SHA-256 values must be lowercase 64-character hashes")
    try:
        receipt_raw = receipt_path.read_bytes()
        receipt_sha256 = hashlib.sha256(receipt_raw).hexdigest()
        if receipt_sha256 != expected_resolution_sha256:
            return _needs_action("resolution receipt SHA-256 drifted from the supplied pin", receipt_sha256=receipt_sha256)
        receipt = json.loads(receipt_raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _needs_action(f"cannot read the pinned CoreText resolution receipt: {exc}")

    if not isinstance(receipt, dict):
        return _needs_action("resolution receipt root must be a JSON object", receipt_sha256=receipt_sha256)
    source_sample = receipt.get("sourceSample") if isinstance(receipt, dict) else None
    frozen_inputs = source_sample.get("frozenInputs") if isinstance(source_sample, dict) else None
    frozen_ir = frozen_inputs.get("ir") if isinstance(frozen_inputs, dict) else None
    frozen_manifest = frozen_inputs.get("sourceManifest") if isinstance(frozen_inputs, dict) else None
    if receipt.get("schema") != "monkey-macos-system-font-resolution/1" or receipt.get("status") != "resolved":
        return _needs_action("resolution receipt is not a resolved system-font receipt", receipt_sha256=receipt_sha256)
    if receipt.get("targetOS") != "macOS" or not receipt.get("targetOSVersion"):
        return _needs_action("resolution receipt does not declare a macOS target and version", receipt_sha256=receipt_sha256)
    source_defaults = receipt.get("sourceDefaultEvidence", {})
    if not isinstance(source_defaults, dict):
        return _needs_action("resolution receipt is missing source default evidence", receipt_sha256=receipt_sha256)
    if (source_defaults.get("sourceProfile") != "cocos-2.4.15-bundle"
            or source_defaults.get("sourceVersion") != "2.4.15"
            or source_defaults.get("sourceFontFamilyDefault") != "Arial"
            or source_defaults.get("sourceSystemFontDefault") is not True):
        return _needs_action("resolution receipt does not carry the pinned Cocos 2.4.15 system-font defaults", receipt_sha256=receipt_sha256)
    if (source_sample.get("sourceProfile") != source_defaults.get("sourceProfile")
            or source_sample.get("sourceVersion") != source_defaults.get("sourceVersion")):
        return _needs_action("resolution receipt source version/profile drifted from its default evidence", receipt_sha256=receipt_sha256)
    if source_defaults.get("sourceOSIdentityVerified") is not False or receipt.get("visualEquivalent") is not False:
        return _needs_action("resolution receipt must preserve unverified source OS and visual-equivalence boundaries", receipt_sha256=receipt_sha256)
    if not isinstance(source_sample, dict) or not isinstance(frozen_ir, dict) or frozen_ir.get("sha256") != ir_sha256:
        return _needs_action("resolution receipt is bound to a different IR SHA-256", receipt_sha256=receipt_sha256)
    if source_sample.get("sourceProfile") != ir.get("sourceProfile"):
        return _needs_action("resolution receipt source profile drifted from the current IR", receipt_sha256=receipt_sha256)
    source_manifest_sha256 = source_sample.get("sourceManifestSha256")
    if (not isinstance(source_manifest_sha256, str) or not _SHA256.fullmatch(source_manifest_sha256)
            or not isinstance(frozen_ir.get("path"), str)
            or not isinstance(frozen_manifest, dict) or frozen_manifest.get("sha256") != source_manifest_sha256):
        return _needs_action("source manifest receipt hash is absent or internally inconsistent", receipt_sha256=receipt_sha256)
    if ir.get("sourceManifestSha256") != source_manifest_sha256:
        return _needs_action("IR sourceManifestSha256 does not match the resolution receipt", receipt_sha256=receipt_sha256)
    if not isinstance(ir.get("components"), list):
        return _needs_action("IR does not contain a components array", receipt_sha256=receipt_sha256)

    system_labels = [component for component in ir["components"]
                     if component.get("type") == "cc.Label"
                     and component.get("systemFont") is True
                     and component.get("font") is None]
    explicit_labels = [component for component in ir["components"]
                       if component.get("type") == "cc.Label" and component.get("font") is not None]
    expected_by_id: dict[str, dict[str, Any]] = {}
    for index, label in enumerate(system_labels):
        label_id = label.get("sourceId")
        if not isinstance(label_id, str) or not label_id or label_id in expected_by_id:
            return _needs_action(f"system-font IR Label {index} has a missing or duplicate sourceId", receipt_sha256=receipt_sha256)
        text = label.get("text")
        if not isinstance(text, str):
            return _needs_action(f"system-font Label {label_id} has no static source text field", receipt_sha256=receipt_sha256)
        family = label.get("fontFamily")
        if family is None or family == "":
            family = receipt.get("sourceDefaultEvidence", {}).get("sourceFontFamilyDefault")
        if not isinstance(family, str) or not family.strip():
            return _needs_action(f"system-font Label {label_id} has an invalid source/default font family", receipt_sha256=receipt_sha256)
        size = label.get("fontSize")
        if isinstance(size, bool) or not isinstance(size, (int, float)) or not 0 < size <= 512:
            return _needs_action(f"system-font Label {label_id} has an invalid point size", receipt_sha256=receipt_sha256)
        expected_by_id[label_id] = {"component": label, "text": text, "fontFamily": family, "pointSize": float(size)}

    receipt_labels = receipt.get("labels")
    family_bindings = source_sample.get("sourceFamilyBindings")
    if not isinstance(receipt_labels, list) or not isinstance(family_bindings, list):
        return _needs_action("receipt is missing label resolutions or per-label family provenance", receipt_sha256=receipt_sha256)
    resolved_by_id = {label.get("targetLabelId"): label for label in receipt_labels if isinstance(label, dict)}
    binding_by_id = {binding.get("sourceLabelId"): binding for binding in family_bindings if isinstance(binding, dict)}
    if len(resolved_by_id) != len(receipt_labels) or set(resolved_by_id) != set(expected_by_id) or set(binding_by_id) != set(expected_by_id):
        return _needs_action("resolution receipt Label ID set drifted from the current IR", receipt_sha256=receipt_sha256)
    if source_sample.get("normalizedSystemFontLabelCount") != len(expected_by_id):
        return _needs_action("resolution receipt Label count drifted from the current IR", receipt_sha256=receipt_sha256)

    physical_face_evidence = {
        (row.get("family"), row.get("styleName"), row.get("postScriptName"), row.get("systemFontFileUrl")): row
        for row in receipt.get("coreTextToPhysicalFaceEvidence", []) if isinstance(row, dict)
    }
    resolved_font_files = {
        row.get("path"): row for row in receipt.get("resolvedFontFiles", []) if isinstance(row, dict)
    }
    font_specs: dict[str, dict[str, Any]] = {}
    label_bindings: list[dict[str, Any]] = []

    def register_font(family: str, style: str, role: str, fallback_ids: list[str],
                      scalar_rows: list[Mapping[str, Any]], label_id: str,
                      face_identity: Mapping[str, Any]) -> str:
        postscript = face_identity.get("postScriptName")
        system_url = face_identity.get("systemFontFileUrl")
        variations = face_identity.get("variationAxes", {})
        physical = physical_face_evidence.get((family, style, postscript, system_url))
        if not isinstance(physical, dict):
            raise ValueError(f"CoreText physical face identity is missing for {family} / {style}")
        file_evidence = resolved_font_files.get(system_url)
        if not isinstance(file_evidence, dict) or file_evidence.get("status") != "inspected":
            raise ValueError(f"font file evidence is missing for {family} / {style}")
        identity_fields = {"targetPostScriptName": postscript,
                           "targetVariationAxes": variations,
                           "targetVariationAxesJson": json.dumps(variations, sort_keys=True, separators=(",", ":")),
                           "targetSystemFontFileUrl": system_url,
                           "targetSystemFontFileSha256": file_evidence.get("fileSha256"),
                           "matchingPhysicalFaces": physical.get("exactPostScriptFaces", []),
                           "fontFileCopiedOrExported": False}
        if physical.get("exactPostScriptFaceCount") == 1:
            asset_id = _font_key(family, style, role, fallback_ids if role == "primary" else [])
            mode = "DynamicOS"
        else:
            identity = {"family": family, "style": style, "postScriptName": postscript,
                        "variationAxes": variations, "systemFontFileUrl": system_url,
                        "systemFontFileSha256": file_evidence.get("fileSha256")}
            digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            asset_id = f"coretext-static-sdf-{digest[:24]}"
            mode = "StaticSDFRequired"
            identity_fields["generationMode"] = "CoreTextRasterizedStaticSDF"
        font = font_specs.setdefault(asset_id, _font_spec(
            asset_id, family, style, role, population_mode=mode))
        if role == "primary":
            font["fallbackAssetIds"] = list(fallback_ids)
        if identity_fields:
            font.update(identity_fields)
        for scalar in scalar_rows:
            if (scalar.get("requiredForVisualText") is True and scalar.get("glyphCovered") is True
                    and scalar.get("family") == family and scalar.get("styleName") == style):
                _add_glyph(font, scalar, label_id)
        return asset_id

    for label_id in sorted(expected_by_id):
        expected = expected_by_id[label_id]
        source_label = expected["component"]
        resolution = resolved_by_id[label_id]
        family_binding = binding_by_id[label_id]
        if resolution.get("text") != expected["text"]:
            return _needs_action(f"CoreText receipt text drifted for Label {label_id}", receipt_sha256=receipt_sha256)
        try:
            receipt_size = float(resolution.get("pointSize"))
        except (TypeError, ValueError):
            return _needs_action(f"CoreText receipt point size is invalid for Label {label_id}", receipt_sha256=receipt_sha256)
        if receipt_size != expected["pointSize"]:
            return _needs_action(f"CoreText receipt point size drifted for Label {label_id}", receipt_sha256=receipt_sha256)
        if resolution.get("requestedFamily") != expected["fontFamily"] or family_binding.get("requestedFamily") != expected["fontFamily"]:
            return _needs_action(f"CoreText receipt requested family drifted for Label {label_id}", receipt_sha256=receipt_sha256)
        source_family_evidence = source_label.get("fontFamilyEvidence")
        if not isinstance(source_family_evidence, str) or not source_family_evidence:
            source_family_evidence = ("official-source-default"
                                      if source_label.get("fontFamily") in (None, "")
                                      else "normalized-value-source-unverified")
        if family_binding.get("familyBindingSource") != source_family_evidence:
            return _needs_action(f"CoreText receipt fontFamily provenance drifted for Label {label_id}", receipt_sha256=receipt_sha256)
        if not isinstance(resolution.get("resolvedPrimaryFamily"), str) or not isinstance(resolution.get("resolvedPrimaryStyleName"), str) or not resolution.get("resolvedPrimaryStyleName"):
            return _needs_action(f"CoreText receipt lacks primary family/style for Label {label_id}", receipt_sha256=receipt_sha256)
        scalar_rows = resolution.get("unicodeScalars")
        if not isinstance(scalar_rows, list):
            return _needs_action(f"CoreText receipt lacks Unicode scalar mappings for Label {label_id}", receipt_sha256=receipt_sha256)
        source_scalars = [ord(char) for char in expected["text"]]
        receipt_scalars = [row.get("scalarValue") for row in scalar_rows if isinstance(row, dict)]
        if receipt_scalars != source_scalars:
            return _needs_action(f"CoreText receipt Unicode scalar sequence drifted for Label {label_id}", receipt_sha256=receipt_sha256)
        for scalar in scalar_rows:
            if not isinstance(scalar, dict) or not scalar.get("family") or not scalar.get("styleName"):
                return _needs_action(f"CoreText receipt lacks exact family/style on a Unicode scalar for Label {label_id}", receipt_sha256=receipt_sha256)
            if scalar.get("requiredForVisualText") and scalar.get("glyphCovered") is not True:
                return _needs_action(f"CoreText receipt has an uncovered required glyph for Label {label_id}: {scalar.get('codepoint')}", receipt_sha256=receipt_sha256)

        fallback_faces: list[tuple[str, str, str, str, Mapping[str, Any]]] = []
        for scalar in scalar_rows:
            if scalar.get("requiredForVisualText") is True and scalar.get("fallback") is True:
                face = (scalar["family"], scalar["styleName"], scalar.get("postScriptName", ""),
                        scalar.get("systemFontFileUrl", ""), scalar.get("variationAxes", {}))
                if face not in fallback_faces:
                    fallback_faces.append(face)
        fallback_asset_ids: list[str] = []
        for family, style, postscript, system_url, variations in fallback_faces:
            try:
                fallback_asset_id = register_font(family, style, "fallback", [], scalar_rows, label_id,
                                                  {"postScriptName": postscript, "systemFontFileUrl": system_url,
                                                   "variationAxes": variations})
            except ValueError as exc:
                return _needs_action(str(exc), receipt_sha256=receipt_sha256)
            if fallback_asset_id not in fallback_asset_ids:
                fallback_asset_ids.append(fallback_asset_id)
        primary_family = resolution["resolvedPrimaryFamily"]
        primary_style = resolution["resolvedPrimaryStyleName"]
        try:
            primary_asset_id = register_font(primary_family, primary_style, "primary", fallback_asset_ids,
                                             scalar_rows, label_id,
                                             {"postScriptName": resolution.get("resolvedPrimaryPostScriptName"),
                                              "systemFontFileUrl": resolution.get("resolvedPrimarySystemFontFileUrl"),
                                              "variationAxes": resolution.get("resolvedPrimaryVariationAxes", {})})
        except ValueError as exc:
            return _needs_action(str(exc), receipt_sha256=receipt_sha256)
        label_bindings.append({
            "sourceLabelId": label_id,
            "sourceText": expected["text"],
            "pointSize": expected["pointSize"],
            "sourceFontFamily": expected["fontFamily"],
            "sourceFontFamilyEvidence": source_family_evidence,
            "sourceSerializedFontUuid": None,
            "sourceSystemFont": True,
            "nativeFontAssetId": primary_asset_id,
            "nativeFontAssetPath": font_specs[primary_asset_id]["assetPath"],
            "nativeFallbackAssetIds": fallback_asset_ids,
            "nativeFallbackAssetPaths": [font_specs[asset_id]["assetPath"] for asset_id in fallback_asset_ids],
            "resolvedPrimaryFamily": primary_family,
            "resolvedPrimaryStyleName": primary_style,
            "resolvedFallbackFaces": [{"familyName": family, "styleName": style}
                                       for family, style, _postscript, _system_url, _variations in fallback_faces],
            "newCharacterBoundary": "receipt text only; other runtime characters are outside the tested codepoint set",
        })

    finalized_fonts = []
    for asset_id, font in sorted(font_specs.items()):
        glyphs = sorted(font.pop("requiredGlyphMap").values(), key=lambda item: item["unicode"])
        font["requiredGlyphs"] = glyphs
        font["requiredUnicode"] = [glyph["unicode"] for glyph in glyphs]
        font["sourceLabelIds"] = sorted(font["sourceLabelIds"])
        finalized_fonts.append(font)

    modes = {font["populationMode"] for font in finalized_fonts}
    system_fonts = {
        "schema": SCHEMA,
        "status": "prepared",
        "targetOS": receipt["targetOS"],
        "targetOSVersion": receipt["targetOSVersion"],
        "targetOSBuild": receipt.get("targetOSBuild"),
        "runtimePlatformConstraint": "macOS Player target only; native asset creation requires macOS Editor",
        "playerTargetEvidence": "not_run",
        "sourceOSIdentityVerified": False,
        "visualEquivalent": False,
        "irSha256": ir_sha256,
        "irPath": frozen_ir["path"],
        "sourceManifestSha256": source_manifest_sha256,
        "sourceManifestPath": frozen_manifest.get("path"),
        "resolutionReceiptSha256": receipt_sha256,
        "resolutionReceiptPath": str(receipt_path.resolve()),
        "sourceProfile": source_sample.get("sourceProfile"),
        "sourceVersion": source_sample.get("sourceVersion"),
        "fontAssetDirectory": "Assets/Game/Content/Fonts/System",
        "fontAssetPathRule": "DynamicOS: role/family/style/ordered fallback IDs; StaticSDFRequired: CoreText face, variation axes, and target system-font SHA-256",
        "populationMode": next(iter(modes)) if len(modes) == 1 else "Mixed",
        "pointSize": 90,
        "glyphCoverageScope": "only Unicode scalars present in the pinned source Label text receipt",
        "newCharacterBoundary": "characters outside the receipt have not been analyzed; DynamicOS runtime lookup does not prove source equivalence or coverage; StaticSDFRequired faces have no glyphs beyond the listed source text",
        "fonts": finalized_fonts,
        "explicitFontLabelsReplaced": [],
        "explicitFontLabelCountExcluded": len(explicit_labels),
    }
    return SystemFontPreparation("prepared", {
        "schema": SCHEMA,
        "status": "prepared",
        "systemFonts": system_fonts,
        "labelBindings": label_bindings,
        "diagnostics": [],
    })


def prepare_static_coretext_sdf_plan(
    ir: Mapping[str, Any],
    ir_sha256: str,
    resolution_path: str | Path,
    expected_resolution_sha256: str,
) -> SystemFontPreparation:
    """Describe bounded static SDF faces when CoreText has no exact physical face.

    This creates a generation/import plan, not a font or atlas. Only characters
    in the frozen source Label text receipt are included. The CoreText-selected
    font remains the glyph source; a nearby physical face is never substituted.
    """
    dynamic_plan = prepare(ir, ir_sha256, resolution_path, expected_resolution_sha256)
    if dynamic_plan.status != "prepared":
        return dynamic_plan
    try:
        raw = Path(resolution_path).read_bytes()
        receipt = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _needs_action(f"cannot read CoreText receipt for static SDF planning: {exc}")
    system_labels = {row.get("sourceLabelId"): row for row in dynamic_plan.record["labelBindings"]}
    face_evidence = receipt.get("coreTextToPhysicalFaceEvidence")
    if not isinstance(face_evidence, list):
        return _needs_action("receipt lacks CoreText-to-physical-face evidence", receipt_sha256=expected_resolution_sha256)
    evidence_by_key = {
        (row.get("family"), row.get("styleName"), row.get("postScriptName"), row.get("systemFontFileUrl")) : row
        for row in face_evidence if isinstance(row, dict)
    }
    files_by_path = {
        row.get("path"): row for row in receipt.get("resolvedFontFiles", []) if isinstance(row, dict)
    }
    labels_by_id = {row.get("targetLabelId"): row for row in receipt.get("labels", []) if isinstance(row, dict)}
    static_faces: dict[str, dict[str, Any]] = {}
    label_overrides: list[dict[str, Any]] = []
    for label_id in sorted(system_labels):
        label = labels_by_id.get(label_id)
        if not isinstance(label, dict):
            return _needs_action(f"CoreText receipt lost Label {label_id}", receipt_sha256=expected_resolution_sha256)
        static_fallback_ids: list[str] = []
        for scalar in label.get("unicodeScalars", []):
            if scalar.get("requiredForVisualText") is not True or scalar.get("fallback") is not True:
                continue
            family, style, postscript, url = (scalar.get("family"), scalar.get("styleName"),
                                               scalar.get("postScriptName"), scalar.get("systemFontFileUrl"))
            evidence = evidence_by_key.get((family, style, postscript, url))
            if not isinstance(evidence, dict):
                return _needs_action(f"physical face evidence is missing for {scalar.get('codepoint')}", receipt_sha256=expected_resolution_sha256)
            if evidence.get("exactPostScriptFaceCount") == 1:
                continue
            file_evidence = files_by_path.get(url)
            if not isinstance(file_evidence, dict) or file_evidence.get("status") != "inspected":
                return _needs_action(f"CoreText font file could not be inspected for {scalar.get('codepoint')}", receipt_sha256=expected_resolution_sha256)
            identity = {
                "family": family, "style": style, "postScriptName": postscript,
                "variationAxes": scalar.get("variationAxes", {}),
                "systemFontFileUrl": url, "systemFontFileSha256": file_evidence.get("fileSha256"),
            }
            digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            face_id = f"coretext-static-sdf-{digest[:24]}"
            face = static_faces.setdefault(face_id, {
                "assetId": face_id,
                "assetPath": f"Assets/Game/Content/Fonts/System/Static/{digest[:24]}.asset",
                "generationMode": "CoreTextRasterizedStaticSDF",
                "targetFamily": family,
                "targetStyleName": style,
                "targetPostScriptName": postscript,
                "targetVariationAxes": scalar.get("variationAxes", {}),
                "targetSystemFontFileUrl": url,
                "targetSystemFontFileSha256": file_evidence.get("fileSha256"),
                "targetSystemFontFileSizeBytes": file_evidence.get("fileSizeBytes"),
                "matchingPhysicalFaceCount": evidence.get("exactPostScriptFaceCount"),
                "matchingPhysicalFaces": evidence.get("exactPostScriptFaces", []),
                "requiredGlyphMap": {},
                "sourceLabelIds": set(),
                "sourceOnly": True,
                "fontBytesCopiedOrExported": False,
                "fontFileDistribution": "none",
                "visualEquivalent": False,
            })
            face["requiredGlyphMap"][scalar["scalarValue"]] = {
                "unicode": scalar["scalarValue"], "codepoint": scalar["codepoint"],
                "character": scalar["character"],
            }
            face["sourceLabelIds"].add(label_id)
            if face_id not in static_fallback_ids:
                static_fallback_ids.append(face_id)
        if static_fallback_ids:
            label_overrides.append({
                "sourceLabelId": label_id,
                "sourceText": label.get("text", ""),
                "pointSize": label.get("pointSize"),
                "staticSdfFallbackAssetIds": static_fallback_ids,
                "scope": "literal source text scalars in the pinned IR and receipt only",
                "newCharacterBoundary": "runtime-created or translated characters outside this set are not covered; route them through an explicitly verified font source before use",
            })
    if not static_faces:
        return _needs_action("all CoreText selected faces have exact physical-face identities; static SDF plan is unnecessary", receipt_sha256=expected_resolution_sha256)
    finalized = []
    for face_id, face in sorted(static_faces.items()):
        face["requiredGlyphs"] = sorted(face.pop("requiredGlyphMap").values(), key=lambda row: row["unicode"])
        face["requiredUnicode"] = [row["unicode"] for row in face["requiredGlyphs"]]
        face["sourceLabelIds"] = sorted(face["sourceLabelIds"])
        face["atlasContract"] = {
            "input": "CTFont resolved by targetPostScriptName at the receipt's targetVariationAxes",
            "raster": "CoreText glyph outlines/metrics only; generate a local SDF texture and glyph metrics table",
            "outputFiles": ["glyph-atlas.png", "glyph-metrics.json"],
            "fontBytesIncluded": False,
            "allowedCodepoints": face["requiredUnicode"],
            "glyphRunShapingRequired": False,
            "shapingBoundary": "one scalar maps to one glyph; non-BMP, combining, and shaping sequences are unsupported by this bounded generator",
            "fontFileLicenseReviewRequiredBeforeDistribution": True,
        }
        finalized.append(face)
    return SystemFontPreparation("prepared", {
        "schema": "monkey-unity-coretext-static-sdf-plan/1",
        "status": "prepared",
        "targetOS": receipt.get("targetOS"),
        "targetOSVersion": receipt.get("targetOSVersion"),
        "targetOSBuild": receipt.get("targetOSBuild"),
        "irSha256": ir_sha256,
        "sourceManifestSha256": receipt.get("sourceSample", {}).get("sourceManifestSha256"),
        "resolutionReceiptSha256": expected_resolution_sha256,
        "sourceOSIdentityVerified": False,
        "visualEquivalent": False,
        "fontAssetDirectory": "Assets/Game/Content/Fonts/System/Static",
        "fontFilesCopiedOrExported": False,
        "systemFonts": finalized,
        "labelFallbackOverrides": label_overrides,
        "nativeImportApi": {
            "editorOnly": True,
            "operation": "Import local glyph-atlas.png and glyph-metrics.json into a Static TMP_FontAsset, attach bounded fallback references, save and reopen/read back atlas dimensions/glyph tables/required Unicode",
            "sourceFontFilePathRetainedInAsset": False,
            "dynamicModeClaimed": False,
        },
        "newCharacterBoundary": "The generated atlas covers only the literal source text scalars listed per face. Other runtime, localized, user-generated, or newly introduced characters have no coverage evidence.",
        "diagnostics": [
            "Static SDF artifacts are not generated by this API; it returns only the pinned raster/import contract.",
            "No source OS font identity or visual equivalence is established.",
            "Review the target system-font license before distributing derived glyph atlases.",
        ],
    })


def prepare_static_inputs(
    generation_receipt_path: str | Path,
    expected_sha: str,
    binding_set: Mapping[str, Any],
    out_stage: str | Path,
) -> StaticSdfInputStaging:
    """Stage hash-pinned SDF atlas/metrics under fixed portable relative paths.

    The original generated receipt SHA is retained as provenance. Only the
    derived atlas and metrics are copied; the operating system font is never
    copied or included. Existing identical staged files are reusable, while
    differing files fail closed instead of being overwritten.
    """
    if not _SHA256.fullmatch(expected_sha):
        return StaticSdfInputStaging("needs_action", {"status": "needs_action", "reason": "generation receipt SHA-256 is invalid"})
    receipt_source = Path(generation_receipt_path)
    try:
        receipt_raw = receipt_source.read_bytes()
        original_receipt_sha = hashlib.sha256(receipt_raw).hexdigest()
        if original_receipt_sha != expected_sha:
            return StaticSdfInputStaging("needs_action", {"status": "needs_action", "reason": "generation receipt SHA-256 drifted", "actualSha256": original_receipt_sha})
        original = json.loads(receipt_raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return StaticSdfInputStaging("needs_action", {"status": "needs_action", "reason": f"cannot read generated SDF receipt: {exc}"})
    if not isinstance(original, dict) or original.get("schema") != "monkey-coretext-static-sdf-generation-receipt/1" or original.get("status") != "generated":
        return StaticSdfInputStaging("needs_action", {"status": "needs_action", "reason": "input is not a generated CoreText SDF receipt", "actualSha256": original_receipt_sha})
    if original.get("targetOS") != "macOS" or not original.get("targetOSVersion") or original.get("fontFileCopiedOrExported") is not False or original.get("fontFileIncluded") is not False:
        return StaticSdfInputStaging("needs_action", {"status": "needs_action", "reason": "receipt target or font-file boundary is invalid", "actualSha256": original_receipt_sha})
    if not isinstance(binding_set, Mapping) or binding_set.get("schema") != SCHEMA or binding_set.get("status") != "prepared":
        return StaticSdfInputStaging("needs_action", {"status": "needs_action", "reason": "binding set is not prepared"})
    system_fonts = binding_set.get("systemFonts")
    if not isinstance(system_fonts, Mapping) or system_fonts.get("resolutionReceiptSha256") != original.get("resolutionReceiptSha256"):
        return StaticSdfInputStaging("needs_action", {"status": "needs_action", "reason": "binding set and static receipt use different resolution receipts"})
    static_specs = [font for font in system_fonts.get("fonts", [])
                    if isinstance(font, dict) and font.get("populationMode") == "StaticSDFRequired"]
    if len(static_specs) != 1:
        return StaticSdfInputStaging("needs_action", {"status": "needs_action", "reason": "binding set must declare exactly one StaticSDFRequired face"})
    static_spec = static_specs[0]
    try:
        atlas_source = Path(original["atlasPath"])
        metrics_source = Path(original["metricsPath"])
        atlas_size = atlas_source.stat().st_size
        metrics_size = metrics_source.stat().st_size
        if not atlas_source.is_file() or not metrics_source.is_file() or atlas_size <= 0 or atlas_size > 32 * 1024 * 1024 or metrics_size <= 0 or metrics_size > 16 * 1024 * 1024:
            raise ValueError("atlas or metrics file is absent or exceeds the bounded size")
        atlas_bytes = atlas_source.read_bytes()
        metrics_bytes = metrics_source.read_bytes()
    except (KeyError, OSError, ValueError) as exc:
        return StaticSdfInputStaging("needs_action", {"status": "needs_action", "reason": f"cannot read bounded SDF inputs: {exc}", "sourceGenerationReceiptSha256": original_receipt_sha})
    atlas_sha = hashlib.sha256(atlas_bytes).hexdigest()
    metrics_sha = hashlib.sha256(metrics_bytes).hexdigest()
    if atlas_sha != original.get("atlasSha256") or metrics_sha != original.get("metricsSha256"):
        return StaticSdfInputStaging("needs_action", {"status": "needs_action", "reason": "atlas or metrics SHA-256 drifted", "sourceGenerationReceiptSha256": original_receipt_sha})
    try:
        metrics = json.loads(metrics_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return StaticSdfInputStaging("needs_action", {"status": "needs_action", "reason": f"invalid SDF metrics JSON: {exc}", "sourceGenerationReceiptSha256": original_receipt_sha})
    if not isinstance(metrics, dict) or metrics.get("schema") != "monkey-coretext-static-sdf-glyph-metrics/1" or metrics.get("status") != "generated":
        return StaticSdfInputStaging("needs_action", {"status": "needs_action", "reason": "metrics are not generated CoreText SDF metrics", "sourceGenerationReceiptSha256": original_receipt_sha})
    expected_axes = static_spec.get("targetVariationAxesJson")
    glyphs = static_spec.get("requiredGlyphs")
    expected_unicode = sorted(glyph.get("unicode") for glyph in glyphs if isinstance(glyph, dict)) if isinstance(glyphs, list) else []
    metrics_glyphs = metrics.get("glyphs")
    metrics_unicode = sorted(glyph.get("unicode") for glyph in metrics_glyphs if isinstance(glyph, dict)) if isinstance(metrics_glyphs, list) else []
    if (metrics.get("resolutionReceiptSha256") != original.get("resolutionReceiptSha256")
            or metrics.get("staticPlanSha256") != original.get("planSha256")
            or metrics.get("targetOS") != original.get("targetOS")
            or metrics.get("targetOSVersion") != original.get("targetOSVersion")
            or metrics.get("targetOSBuild") != original.get("targetOSBuild")
            or metrics.get("family") != static_spec.get("familyName")
            or metrics.get("styleName") != static_spec.get("styleName")
            or metrics.get("postScriptName") != static_spec.get("targetPostScriptName")
            or metrics.get("variationAxesCanonical") != expected_axes
            or metrics.get("fontFileSha256") != static_spec.get("targetSystemFontFileSha256")
            or metrics.get("fontFileCopiedOrExported") is not False
            or metrics.get("fontFileIncluded") is not False
            or metrics.get("sourceLabelIds") != sorted(static_spec.get("sourceLabelIds", []))
            or metrics_unicode != expected_unicode
            or original.get("glyphCount") != len(expected_unicode)
            or original.get("sourceLabelCount") != len(static_spec.get("sourceLabelIds", []))):
        return StaticSdfInputStaging("needs_action", {"status": "needs_action", "reason": "SDF receipt, metrics and binding set identities do not agree", "sourceGenerationReceiptSha256": original_receipt_sha})

    asset_id = static_spec.get("assetId")
    if not isinstance(asset_id, str) or not re.fullmatch(r"coretext-static-sdf-[0-9a-f]{24}", asset_id):
        return StaticSdfInputStaging("needs_action", {"status": "needs_action", "reason": "static SDF asset ID is invalid"})
    relative_dir = Path("Assets/Game/Content/Fonts/System/StaticSdfInputs") / asset_id.removeprefix("coretext-static-sdf-")
    relative_paths = {
        "atlas": relative_dir / "glyph-atlas.png",
        "metrics": relative_dir / "glyph-metrics.json",
        "receipt": relative_dir / "generation-receipt.json",
    }
    portable = {
        "schema": "monkey-coretext-static-sdf-portable-generation-receipt/1",
        "status": "portable_staged",
        "sourceGenerationReceiptSha256": original_receipt_sha,
        "targetOS": original["targetOS"],
        "targetOSVersion": original["targetOSVersion"],
        "targetOSBuild": original.get("targetOSBuild"),
        "resolutionReceiptSha256": original["resolutionReceiptSha256"],
        "planSha256": original["planSha256"],
        "atlasPath": "glyph-atlas.png",
        "atlasSha256": atlas_sha,
        "metricsPath": "glyph-metrics.json",
        "metricsSha256": metrics_sha,
        "glyphCount": original["glyphCount"],
        "sourceLabelCount": original["sourceLabelCount"],
        "fontFileCopiedOrExported": False,
        "fontFileIncluded": False,
    }
    portable_bytes = (json.dumps(portable, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    stage_root = Path(out_stage).expanduser().resolve()
    files = [
        (atlas_bytes, relative_paths["atlas"], atlas_sha, "glyph-atlas"),
        (metrics_bytes, relative_paths["metrics"], metrics_sha, "glyph-metrics"),
        (portable_bytes, relative_paths["receipt"], hashlib.sha256(portable_bytes).hexdigest(), "portable-generation-receipt"),
    ]
    copies: list[dict[str, Any]] = []
    try:
        stage_root.mkdir(parents=True, exist_ok=True)
        for content, relative_path, digest, artifact_kind in files:
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise ValueError("internal stage path was not relative and bounded")
            destination = (stage_root / relative_path).resolve()
            if destination == stage_root or not destination.is_relative_to(stage_root):
                raise ValueError("stage destination escapes its root")
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if not destination.is_file() or hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                    raise ValueError(f"refusing to overwrite staged file with different bytes: {relative_path.as_posix()}")
            else:
                with tempfile.NamedTemporaryFile(prefix=".sdf-stage-", dir=destination.parent, delete=False) as stream:
                    temp_path = Path(stream.name)
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp_path, destination)
            copies.append({"artifactKind": artifact_kind, "relativePath": relative_path.as_posix(), "sha256": digest, "sizeBytes": len(content)})
    except (OSError, ValueError) as exc:
        return StaticSdfInputStaging("needs_action", {"status": "needs_action", "reason": f"cannot stage portable SDF inputs: {exc}", "sourceGenerationReceiptSha256": original_receipt_sha, "copies": copies})

    receipt_relative = relative_paths["receipt"].as_posix()
    return StaticSdfInputStaging("staged", {
        "schema": "monkey-unity-static-sdf-staged-inputs/1",
        "status": "staged",
        "sourceGenerationReceiptSha256": original_receipt_sha,
        "portableReceiptRelativePath": receipt_relative,
        "portableReceiptSha256": hashlib.sha256(portable_bytes).hexdigest(),
        "stageRoot": str(stage_root),
        "copies": copies,
        "fontFileCopiedOrExported": False,
        "fontFileIncluded": False,
    })
