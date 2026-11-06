"""Read-only audit of saved Unity font bindings for native selection handoff.

This module consumes UnitySystemFonts saved readbacks and the native file
inventory. It does not edit assets or infer coverage from a font family name.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


SCHEMA = "monkey-native-font-coverage/1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GUID = re.compile(r"^[0-9a-fA-F]{32}$")


def audit_saved_font_coverage(
    readback: Mapping[str, Any],
    native_files: Sequence[Mapping[str, Any]] | None,
    *,
    expected_target_os: str | None = None,
    selected_asset_ids: Sequence[str] | None = None,
    required_text_by_label_id: Mapping[str, str] | None = None,
    producer_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize saved font/label readbacks into explicit consumer boundaries.

    ``native_files`` is the saved candidate inventory (path + SHA-256), such
    as Unity's ``nativeFiles`` readback. Font GUIDs come only from the font
    readback. Missing identity or coverage fields remain unknown and become
    consumer actions; no font identity or glyph proof is synthesized.
    """
    diagnostics: list[str] = []
    rb = readback if isinstance(readback, Mapping) else {}
    selected = set(selected_asset_ids) if selected_asset_ids is not None else None
    dynamic_text = required_text_by_label_id if isinstance(required_text_by_label_id, Mapping) else {}
    font_rows = rb.get("fonts")
    label_rows = rb.get("labelBindings")
    file_by_path: dict[str, Mapping[str, Any]] = {}
    for row in native_files or ():
        if isinstance(row, Mapping) and isinstance(row.get("path"), str):
            file_by_path[row["path"]] = row

    normalized_fonts: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    if not isinstance(font_rows, list):
        diagnostics.append("font_readback_missing")
        font_rows = []
    for row in font_rows:
        if not isinstance(row, Mapping):
            diagnostics.append("font_readback_malformed")
            continue
        asset_id = row.get("assetId")
        if selected is not None and asset_id not in selected:
            continue
        path = row.get("assetPath")
        guid = row.get("assetGuid")
        file_row = file_by_path.get(path) if isinstance(path, str) else None
        digest = file_row.get("sha256") if file_row else None
        identity_ok = (isinstance(asset_id, str) and bool(asset_id)
                       and isinstance(path, str) and bool(path)
                       and isinstance(guid, str) and bool(_GUID.fullmatch(guid))
                       and isinstance(digest, str) and bool(_SHA256.fullmatch(digest)))

        saved = row.get("savedNativeGlyphState")
        saved = saved if isinstance(saved, Mapping) else {}
        mode = row.get("populationMode") or saved.get("atlasPopulationMode")
        dynamic = mode == "DynamicOS" or saved.get("internalDynamicOS") is True
        lookup = saved.get("lookupPresentUnicode")
        if not isinstance(lookup, list):
            # characterTableUnicode is a table inventory, not proof that
            # TMP's runtime lookup resolves those scalars; do not substitute.
            lookup = None
        coverage_known = lookup is not None and all(
            isinstance(value, int) and not isinstance(value, bool) and value >= 0
            for value in lookup
        )
        static_coverage = sorted(set(lookup)) if coverage_known else None
        source_present = saved.get("sourceFontFilePresent")
        source_guid = saved.get("sourceFontFileGuid")
        source_path = saved.get("sourceFontFilePath")
        if dynamic and saved.get("internalDynamicOS") is True and source_present is False:
            source_meaning = "DynamicOS resolves a platform system face; sourceFontFile is not an embedded font file"
        elif dynamic and source_present is False:
            source_meaning = "DynamicOS may be platform-backed; internal DynamicOS state is unverified"
        elif source_present is True:
            source_meaning = "saved readback reports a source font file; its bytes are not in this receipt"
        elif source_present is False:
            source_meaning = "saved readback reports no source font file; semantics are not established"
        else:
            source_meaning = "sourceFontFile state is unknown"

        font = {
            "assetId": asset_id if isinstance(asset_id, str) else None,
            "assetPath": path if isinstance(path, str) else None,
            "assetGuid": guid.lower() if isinstance(guid, str) and _GUID.fullmatch(guid) else None,
            "assetSha256": digest if isinstance(digest, str) and _SHA256.fullmatch(digest) else None,
            "identityComplete": identity_ok,
            "populationMode": mode if isinstance(mode, str) else None,
            "dynamicOS": dynamic,
            "staticCoverage": {
                "unicode": static_coverage,
                "status": "bounded" if coverage_known and not dynamic else "unknown",
                "scope": "saved TMP lookup readback only" if coverage_known and not dynamic else None,
            },
            "sourceFontFile": {
                "present": source_present if isinstance(source_present, bool) else None,
                "guid": source_guid if isinstance(source_guid, str) and source_guid else None,
                "path": source_path if isinstance(source_path, str) and source_path else None,
                "meaning": source_meaning,
            },
            "fallbackAssetIds": row.get("fallbackAssetIds") if isinstance(row.get("fallbackAssetIds"), list) else [],
            "clearDynamicDataOnBuild": row.get("clearDynamicDataOnBuild") if isinstance(row.get("clearDynamicDataOnBuild"), bool) else None,
            "requiredUnicode": sorted(set(v for v in row.get("requiredUnicode", [])
                                           if isinstance(v, int) and not isinstance(v, bool) and v >= 0))
                               if isinstance(row.get("requiredUnicode"), list) else None,
        }
        if not identity_ok:
            diagnostics.append(f"font_identity_incomplete:{asset_id or 'unknown'}")
        if dynamic:
            diagnostics.append(f"dynamic_coverage_unknown:{asset_id or 'unknown'}")
        elif not coverage_known:
            diagnostics.append(f"static_coverage_unknown:{asset_id or 'unknown'}")
        normalized_fonts.append(font)
        if isinstance(asset_id, str):
            by_id[asset_id] = font

    target_os = rb.get("targetOS") if isinstance(rb.get("targetOS"), str) else None
    target_platform = rb.get("targetPlatform") if isinstance(rb.get("targetPlatform"), str) else None
    constraint = rb.get("runtimePlatformConstraint")
    if not isinstance(constraint, str):
        system_fonts = rb.get("systemFonts")
        constraint = system_fonts.get("runtimePlatformConstraint") if isinstance(system_fonts, Mapping) else None
    if not isinstance(constraint, str) and isinstance(producer_contract, Mapping):
        system_fonts = producer_contract.get("systemFonts")
        constraint = system_fonts.get("runtimePlatformConstraint") if isinstance(system_fonts, Mapping) else None
    platform_status = "unknown"
    if expected_target_os and isinstance(constraint, str):
        if expected_target_os.casefold() in constraint.casefold():
            platform_status = "supported"
        elif "only" in constraint.casefold():
            platform_status = "unsupported"

    if not isinstance(label_rows, list):
        diagnostics.append("label_binding_readback_missing")
        label_rows = []
    normalized_labels: list[dict[str, Any]] = []
    for row in label_rows:
        if not isinstance(row, Mapping):
            diagnostics.append("label_binding_malformed")
            continue
        label_id = row.get("sourceLabelId")
        primary_id = row.get("primaryAssetId")
        fallback_ids = row.get("fallbackAssetIds") if isinstance(row.get("fallbackAssetIds"), list) else []
        binding_ids = [value for value in [primary_id, *fallback_ids] if isinstance(value, str)]
        bound_fonts = [by_id[value] for value in binding_ids if value in by_id]
        text = row.get("sourceText")
        readback_required = sorted({ord(ch) for ch in text}) if isinstance(text, str) else None
        additional_text = dynamic_text.get(label_id) if isinstance(label_id, str) else None
        consumer_required = sorted(set(readback_required or ()) | ({ord(ch) for ch in additional_text}
                                                                    if isinstance(additional_text, str) else set()))
        required = consumer_required if (readback_required is not None or isinstance(additional_text, str)) else None
        missing: list[int] | None = None
        coverage_status = "unknown"
        if required is not None and bound_fonts and all(
            not font["dynamicOS"] and font["staticCoverage"]["unicode"] is not None
            for font in bound_fonts
        ):
            present = {cp for font in bound_fonts for cp in font["staticCoverage"]["unicode"]}
            missing = [cp for cp in required if cp not in present]
            coverage_status = "covered" if not missing else "missing"
        dynamic_unknown = any(font["dynamicOS"] for font in bound_fonts)
        need_consumer: list[str] = []
        if not bound_fonts or any(not font["identityComplete"] for font in bound_fonts):
            need_consumer.append("fontbinding")
        if dynamic_unknown or coverage_status == "unknown" or platform_status == "unsupported":
            need_consumer.append("explicitdynamictextcheck")
        if coverage_status == "missing":
            need_consumer.append("fontbinding")
        normalized_labels.append({
            "sourceLabelId": label_id if isinstance(label_id, str) else None,
            "sourceText": text if isinstance(text, str) else None,
            "consumerRequiredText": additional_text if isinstance(additional_text, str) else None,
            "requiredUnicode": required,
            "primaryAssetId": primary_id if isinstance(primary_id, str) else None,
            "fallbackAssetIds": fallback_ids,
            "boundFontAssetIds": binding_ids,
            "staticCoverage": {"status": coverage_status, "missingUnicode": missing},
            "dynamicCoverage": "unknown" if dynamic_unknown else "not_applicable",
            "needConsumer": list(dict.fromkeys(need_consumer)),
        })

    if expected_target_os and platform_status == "unsupported":
        diagnostics.append("unsupported_target_os")
    return {
        "schema": SCHEMA,
        "status": "audited" if not diagnostics else "needs_action",
        "targetOS": target_os,
        "targetOSMeaning": "saved font resolution environment; not Player target proof",
        "targetPlatform": target_platform,
        "expectedTargetOS": expected_target_os,
        "platformConstraint": constraint if isinstance(constraint, str) else None,
        "platformStatus": platform_status,
        "fonts": normalized_fonts,
        "labelBindings": normalized_labels,
        "consumerActions": sorted({action for label in normalized_labels for action in label["needConsumer"]}),
        "diagnostics": diagnostics,
        "coverageBoundary": "Saved static lookup entries cover only the listed Unicode scalars. DynamicOS text beyond explicit checks is unknown; sourceFontFile may be null for a platform system face.",
    }
