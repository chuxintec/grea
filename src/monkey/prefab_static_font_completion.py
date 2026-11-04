"""Complete CoreText-backed TMP fallback glyphs for Cocos 2.4 null-font Labels.

The source Label state stays font=null / systemFont=false. Preparation-only
copies toggle that bit solely to reuse the existing CoreText binding API; the
returned target binding records the true source state and the separate
creator24-null-font-effective-family policy.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any

from PIL import Image, ImageChops

from .prefab_font_binding import resolve_macos_system_font_runs
from .prefab_system_fonts import prepare as prepare_system_fonts
from .prefab_system_fonts import prepare_static_coretext_sdf_plan, prepare_static_inputs


SCHEMA = "monkey-unity-static-font-completion/1"
SOURCE_EFFECTIVE_POLICY = "creator24-ttf-null-font-effective-family-arial-v1"
ENGINE_EVIDENCE = {
    "profile": "cocos-2.4.15-bundle",
    "sourceComponentState": {"font": None, "systemFont": False},
    "ttfAssembler": "cocos2d/core/renderer/utils/label/ttf.js::_updateProperties calls getFontFamily(comp)",
    "fontSelector": "cocos2d/core/renderer/utils/utils.js::getFontFamily returns Arial when !useSystemFont && !font",
    "upstream": [
        "https://raw.githubusercontent.com/cocos/cocos-engine/v2.4.15/cocos2d/core/renderer/utils/label/ttf.js",
        "https://raw.githubusercontent.com/cocos/cocos-engine/v2.4.15/cocos2d/core/renderer/utils/utils.js",
    ],
    "sourceSystemFontPreserved": False,
}


class FontCompletionError(ValueError):
    pass


def _bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read(path: str | Path) -> tuple[Any, bytes]:
    raw = Path(path).read_bytes()
    return json.loads(raw.decode("utf-8")), raw


def _write_json(path: Path, value: Any) -> str:
    raw = _bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return _sha(raw)


def _source_component(source_id: str, assets: dict[str, dict]) -> dict:
    match = re.fullmatch(r"([^:]+:[0-9a-fA-F-]+)#(\d+)/components/(\d+)", source_id or "")
    if not match:
        raise FontCompletionError("source Label ID is not a raw prefab component identity: " + str(source_id))
    asset_id = match.group(1)
    node_index, component_index = int(match.group(2)), int(match.group(3))
    asset = assets.get(asset_id)
    document = asset.get("document") if isinstance(asset, dict) else None
    instances = document.get("instances") if isinstance(document, dict) else None
    if not isinstance(instances, list) or node_index >= len(instances):
        raise FontCompletionError("source prefab instance is unavailable: " + source_id)
    node = instances[node_index]
    components = node.get("_components") if isinstance(node, dict) else None
    if not isinstance(components, list) or component_index >= len(components):
        raise FontCompletionError("source prefab component is unavailable: " + source_id)
    component = components[component_index]
    if not isinstance(component, dict) or component.get("__type__") != "cc.Label":
        raise FontCompletionError("source component is no longer cc.Label: " + source_id)
    if component.get("_isSystemFontUsed") is not False or component.get("_N$file") not in (None, {}):
        raise FontCompletionError("raw source font state differs from font=null/systemFont=false: " + source_id)
    return {"nodeInstance": node_index, "componentIndex": component_index,
            "text": component.get("_string"), "fontSize": component.get("_fontSize"),
            "rawFont": component.get("_N$file"), "rawSystemFont": component.get("_isSystemFontUsed"),
            "fontFamily": component.get("_fontFamily", "Arial")}


def _effectively_active(node_id: str, nodes: dict[str, dict]) -> bool:
    seen: set[str] = set()
    while node_id and node_id in nodes:
        if node_id in seen:
            raise FontCompletionError("candidate node parent graph contains a cycle: " + node_id)
        seen.add(node_id)
        node = nodes[node_id]
        if node.get("active") is False:
            return False
        node_id = node.get("parent")
    return True


def _select_labels(plan: dict, manifest: dict) -> list[dict]:
    node_by_id = {n.get("sourceId"): n for n in plan.get("nodes") or [] if isinstance(n, dict)}
    assets = {a.get("sourceId"): a for a in manifest.get("assets") or []
              if isinstance(a, dict) and isinstance(a.get("sourceId"), str)}
    selected: list[dict] = []
    for component in plan.get("components") or []:
        if (not isinstance(component, dict) or component.get("type") != "cc.Label"
                or component.get("font") is not None or component.get("systemFont") is not False):
            continue
        if not isinstance(component.get("text"), str):
            continue
        node = component.get("node")
        effective_active = _effectively_active(node, node_by_id)
        raw = _source_component(component.get("sourceId"), assets)
        if raw["text"] != component["text"] or (raw["fontSize"] is not None and raw["fontSize"] != component.get("fontSize")):
            raise FontCompletionError("normalized Label content differs from source serialization: " + component["sourceId"])
        selected.append({"sourceComponentId": component["sourceId"], "sourceNodeId": node,
                         "sourceText": component["text"], "fontSize": component["fontSize"],
                         "sourceEnabled": component.get("enabled") is True,
                         "sourceSystemFont": False, "sourceFont": None,
                         "sourceFontFamilyDefault": "Arial",
                         "sourceFontFamilyEvidence": component.get("fontFamilyEvidence") or "creator-label-default-Arial",
                         "sourceRawEvidence": raw, "effectiveActive": effective_active})
    return sorted(selected, key=lambda row: row["sourceComponentId"])


def _map_unique(rows: list[dict], key: str, label: str) -> dict:
    result: dict[str, dict] = {}
    for row in rows:
        value = row.get(key) if isinstance(row, dict) else None
        if not isinstance(value, str) or not value or value in result:
            raise FontCompletionError(f"{label} contains missing/duplicate {key}")
        result[value] = row
    return result


def _merge_grouped_rows(base_rows: list[dict], add_rows: list[dict], identity_keys: tuple[str, ...],
                        list_keys: tuple[str, ...]) -> list[dict]:
    groups: dict[tuple, dict] = {}
    for row in base_rows + add_rows:
        if not isinstance(row, dict):
            continue
        identity = tuple(json.dumps(row.get(k), sort_keys=True, separators=(",", ":")) for k in identity_keys)
        target = groups.setdefault(identity, deepcopy(row))
        if target != row and any(target.get(k) != row.get(k) for k in identity_keys):
            raise FontCompletionError("CoreText identity group collision")
        for key in list_keys:
            old, new = target.get(key), row.get(key)
            if isinstance(old, list) and isinstance(new, list):
                unique = {json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")): value
                          for value in old + new}
                target[key] = [unique[k] for k in sorted(unique)]
    return sorted(groups.values(), key=lambda row: tuple(str(row.get(k, "")) for k in identity_keys))


def _merge_resolution(base: dict, added: dict, labels: list[dict],
                      source_ir_path: Path, source_ir_sha: str, source_manifest_path: Path,
                      source_manifest_sha: str) -> dict:
    merged = deepcopy(base)
    base_labels = _map_unique(merged.get("labels") or [], "targetLabelId", "pinned CoreText labels")
    for row in added.get("labels") or []:
        sid = row.get("targetLabelId")
        if sid in base_labels:
            raise FontCompletionError("new Label already appears in pinned CoreText receipt: " + str(sid))
        base_labels[sid] = row
    merged["labels"] = [base_labels[k] for k in sorted(base_labels)]
    merged["resolvedPrimaryFonts"] = _merge_grouped_rows(
        merged.get("resolvedPrimaryFonts") or [], added.get("resolvedPrimaryFonts") or [],
        ("requestedFamily", "family", "styleName", "postScriptName", "systemFontFileUrl"),
        ("pointSizes",))
    merged["fallbackFonts"] = _merge_grouped_rows(
        merged.get("fallbackFonts") or [], added.get("fallbackFonts") or [],
        ("family", "styleName", "postScriptName", "systemFontFileUrl"),
        ("characters", "codepoints", "pointSizes", "requestedFamilies", "targetLabelIds"))
    merged["resolvedFontFiles"] = _merge_grouped_rows(
        merged.get("resolvedFontFiles") or [], added.get("resolvedFontFiles") or [],
        ("path",), ("faces",))
    for row in merged["resolvedFontFiles"]:
        versions = [x for x in (base.get("resolvedFontFiles") or []) + (added.get("resolvedFontFiles") or [])
                    if x.get("path") == row.get("path")]
        if len({(x.get("fileSha256"), x.get("fileSizeBytes")) for x in versions}) > 1:
            raise FontCompletionError("CoreText font-file identity/hash changed: " + str(row.get("path")))
    merged["coreTextToPhysicalFaceEvidence"] = _merge_grouped_rows(
        merged.get("coreTextToPhysicalFaceEvidence") or [], added.get("coreTextToPhysicalFaceEvidence") or [],
        ("family", "styleName", "postScriptName", "systemFontFileUrl"), ())
    old_cov, new_cov = merged.get("glyphCoverage") or {}, added.get("glyphCoverage") or {}
    merged["glyphCoverage"] = {
        "requiredUnicodeOccurrences": old_cov.get("requiredUnicodeOccurrences", 0) + new_cov.get("requiredUnicodeOccurrences", 0),
        "coveredUnicodeOccurrences": old_cov.get("coveredUnicodeOccurrences", 0) + new_cov.get("coveredUnicodeOccurrences", 0),
        "missingUnicodeOccurrences": old_cov.get("missingUnicodeOccurrences", 0) + new_cov.get("missingUnicodeOccurrences", 0),
        "missing": (old_cov.get("missing") or []) + (new_cov.get("missing") or []),
        "perUnicodeScalar": (old_cov.get("perUnicodeScalar") or []) + (new_cov.get("glyphCoverage", {}).get("perUnicodeScalar") or []),
    }
    if merged["glyphCoverage"]["missingUnicodeOccurrences"]:
        raise FontCompletionError("CoreText did not resolve every required source character")
    source_sample = merged.get("sourceSample")
    if not isinstance(source_sample, dict):
        raise FontCompletionError("pinned CoreText receipt lacks sourceSample")
    existing_family = _map_unique(source_sample.get("sourceFamilyBindings") or [], "sourceLabelId", "CoreText family bindings")
    for label in labels:
        sid = label["sourceComponentId"]
        existing_family[sid] = {
            "sourceLabelId": sid, "requestedFamily": "Arial", "familyBindingSource": label["sourceFontFamilyEvidence"],
            "fontSize": label["fontSize"], "sourceSystemFont": False,
            "sourceEffectiveFontPolicy": SOURCE_EFFECTIVE_POLICY,
            "sourceText": label["sourceText"],
        }
    source_sample["sourceFamilyBindings"] = [existing_family[k] for k in sorted(existing_family)]
    source_sample["normalizedSystemFontLabelCount"] = len(existing_family)
    source_sample["sourceStaticTextLabelCount"] = sum(bool(row.get("text")) for row in merged["labels"])
    source_sample["frozenInputs"] = {
        "ir": {"path": str(source_ir_path.resolve()), "sha256": source_ir_sha},
        "sourceManifest": {"path": str(source_manifest_path.resolve()), "sha256": source_manifest_sha},
    }
    source_sample["preparationOnlySystemFontOverrides"] = [
        {"sourceLabelId": label["sourceComponentId"], "sourceSystemFont": False,
         "sourceFont": None, "sourceEffectiveFontPolicy": SOURCE_EFFECTIVE_POLICY,
         "preparationInputSystemFont": True}
        for label in labels]
    source_sample["sourceEffectiveFontPolicyEvidence"] = ENGINE_EVIDENCE
    merged["sourceSample"] = source_sample
    merged["status"] = "resolved"
    merged["visualEquivalent"] = False
    return merged


def _build_augmented_ir(source_ir: dict, label_rows: list[dict]) -> dict:
    ir = deepcopy(source_ir)
    by_id = {row.get("sourceId"): row for row in ir.get("components") or [] if isinstance(row, dict)}
    for label in label_rows:
        sid = label["sourceComponentId"]
        component = by_id.get(sid)
        if not isinstance(component, dict) or component.get("font") is not None or component.get("systemFont") is not False:
            raise FontCompletionError("IR does not preserve the expected null-font source state: " + sid)
        component["systemFont"] = True  # preparation-only input required by prefab_system_fonts.prepare
        component["fontFamily"] = label["sourceFontFamilyDefault"]
        component["fontFamilyEvidence"] = label["sourceFontFamilyEvidence"]
    return ir


def _merge_glyph_rows(base: list[dict], additions: list[dict]) -> list[dict]:
    result = {row.get("unicode"): deepcopy(row) for row in base if isinstance(row, dict)}
    for row in additions:
        code = row.get("unicode") if isinstance(row, dict) else None
        if type(code) is not int:
            raise FontCompletionError("generated CoreText glyph has invalid Unicode")
        old = result.get(code)
        if old and old.get("character") != row.get("character"):
            raise FontCompletionError(f"CoreText glyph identity collision at U+{code:04X}")
        result.setdefault(code, deepcopy(row))
    return [result[code] for code in sorted(result)]


def _merge_static_plan(base_face: dict, fresh_plan: dict, binding_face: dict,
                       extra_label_ids: list[str]) -> dict:
    fresh_faces = fresh_plan.get("systemFonts") or []
    if len(fresh_faces) != 1:
        raise FontCompletionError("CoreText completion plan must contain one pinned fallback face")
    face = deepcopy(fresh_faces[0])
    if face.get("assetId") != base_face.get("assetId") or face.get("targetSystemFontFileSha256") != base_face.get("targetSystemFontFileSha256"):
        raise FontCompletionError("resolved fallback face differs from the existing pinned atlas face")
    face["requiredGlyphs"] = _merge_glyph_rows(base_face.get("requiredGlyphs") or [], face.get("requiredGlyphs") or [])
    face["requiredUnicode"] = [row["unicode"] for row in face["requiredGlyphs"]]
    face["sourceLabelIds"] = sorted(set(base_face.get("sourceLabelIds") or []) | set(face.get("sourceLabelIds") or []) | set(extra_label_ids))
    face["atlasContract"]["allowedCodepoints"] = face["requiredUnicode"]
    updated = deepcopy(fresh_plan)
    updated["systemFonts"] = [face]
    updated["newCharacterBoundary"] = "source Label receipt plus the pinned existing glyph atlas; future runtime/localized text remains outside coverage"
    updated["preservedBaseAtlas"] = {
        "assetId": base_face.get("assetId"), "requiredGlyphCount": len(base_face.get("requiredGlyphs") or []),
        "sourceLabelCount": len(base_face.get("sourceLabelIds") or []),
        "priorGenerationReceiptSha256": base_face.get("baseGenerationReceiptSha256"),
    }
    for override in updated.get("labelFallbackOverrides") or []:
        if override.get("sourceLabelId") in extra_label_ids:
            override["sourceSystemFont"] = False
            override["sourceEffectiveFontPolicy"] = SOURCE_EFFECTIVE_POLICY
    updated["sourceEffectiveFontPolicyEvidence"] = ENGINE_EVIDENCE
    return updated


def _same_glyph_metrics(old: dict, new: dict) -> bool:
    return {k: v for k, v in old.items() if k != "rect"} == {k: v for k, v in new.items() if k != "rect"}


def _validate_preserved_glyph_denominator(completion: dict, base_metrics: dict,
                                          expected_codes: list[int]) -> set[int]:
    base_rows = base_metrics.get("glyphs") or []
    base_codes = {row.get("unicode") for row in base_rows if isinstance(row, dict)}
    if len(base_codes) != len(base_rows):
        raise FontCompletionError("base glyph metrics contain duplicate or invalid Unicode identities")
    expected = set(expected_codes)
    supplemental = expected - base_codes
    declared_supplemental = {row.get("unicode") for row in completion.get("supplementalGlyphs") or []
                             if isinstance(row, dict)}
    if (not base_codes.issubset(expected)
            or completion.get("preservedGlyphCount") != len(base_codes)
            or completion.get("generatedGlyphCount") != len(expected)
            or declared_supplemental != supplemental):
        raise FontCompletionError("completion receipt does not preserve the source glyph denominator and supplemental set")
    return supplemental


def _font_fallback_mapping(binding: dict, label_id: str, source_text: str) -> dict:
    matches = [row for row in binding.get("labelBindings") or [] if row.get("sourceLabelId") == label_id]
    if len(matches) != 1:
        raise FontCompletionError("completed source Label has no unique native binding: " + label_id)
    row = matches[0]
    row["sourceSystemFont"] = False
    row["sourceSerializedFontUuid"] = None
    row["sourceEffectiveFontPolicy"] = SOURCE_EFFECTIVE_POLICY
    row["sourceEffectiveFamily"] = "Arial"
    row["sourceText"] = source_text
    row["font"] = None
    row["sourceFont"] = None
    row["sourceState"] = {"font": None, "systemFont": False}
    return row


def prepare(
    plan_path: str | Path,
    source_manifest_path: str | Path,
    ir_path: str | Path,
    resolution_receipt_path: str | Path,
    base_stage_root: str | Path,
    output_dir: str | Path,
    *,
    generator_path: str | Path,
    run_coretext_generator: bool = True,
) -> dict:
    """Resolve, extend, generate and stage an isolated static font completion.

    ``plan_path`` and all source artifacts are read-only. The only writes are
    below ``output_dir``. Existing Arial and CoreText fallback IDs and atlas
    tiles remain stable; new source text glyphs append to the old atlas.
    """
    plan, plan_raw = _read(plan_path)
    manifest, manifest_raw = _read(source_manifest_path)
    source_ir, source_ir_raw = _read(ir_path)
    base_resolution, base_resolution_raw = _read(resolution_receipt_path)
    plan_hash = _sha(plan_raw)
    manifest_sha = _sha(manifest_raw)
    source_ir_sha = _sha(source_ir_raw)
    resolution_sha = _sha(base_resolution_raw)
    if plan.get("sourceManifestSha256") != manifest_sha or source_ir.get("sourceManifestSha256") != manifest_sha:
        raise FontCompletionError("plan/IR does not pin the supplied source manifest")
    if plan.get("sourceIrSha256") != source_ir_sha:
        raise FontCompletionError("plan does not pin the supplied normalized source IR")
    base_binding = plan.get("systemFontBinding")
    if not isinstance(base_binding, dict) or base_binding.get("status") != "prepared":
        raise FontCompletionError("Unity plan has no prepared system-font binding")
    if base_binding.get("systemFonts", {}).get("resolutionReceiptSha256") != resolution_sha:
        raise FontCompletionError("Unity plan system-font binding pins a different CoreText receipt")

    labels = _select_labels(plan, manifest)
    if not labels:
        raise FontCompletionError("source plan/manifest denominator contains no null-font, non-system-font Labels")
    base_static_faces = [font for font in base_binding.get("systemFonts", {}).get("fonts") or []
                         if font.get("populationMode") == "StaticSDFRequired"]
    if len(base_static_faces) != 1:
        raise FontCompletionError("existing system-font binding must identify exactly one reusable static fallback face")
    base_fallback = base_static_faces[0]
    fallback_identity = {
        "family": base_fallback.get("familyName"),
        "styleName": base_fallback.get("styleName"),
        "postScriptName": base_fallback.get("targetPostScriptName"),
        "systemFontFileUrl": base_fallback.get("targetSystemFontFileUrl"),
        "variationAxes": base_fallback.get("targetVariationAxes", {}),
        "fileSha256": base_fallback.get("targetSystemFontFileSha256"),
    }
    if not all(fallback_identity[k] for k in ("family", "styleName", "postScriptName", "systemFontFileUrl", "fileSha256")):
        raise FontCompletionError("existing fallback face lacks its pinned CoreText identity/file hash")
    ids = [row["sourceComponentId"] for row in labels]
    runs = [{"id": row["sourceComponentId"], "text": row["sourceText"], "pointSize": row["fontSize"],
             "requestedFamily": "Arial"} for row in labels]
    resolved = resolve_macos_system_font_runs(runs, "Arial")
    if resolved.status != "resolved":
        raise FontCompletionError("CoreText could not resolve the exact source Label text set: " + str(resolved.record.get("reason") or resolved.record.get("glyphCoverage")))
    base_font_files = {row.get("path"): row for row in base_resolution.get("resolvedFontFiles") or []}
    for file_row in resolved.record.get("resolvedFontFiles") or []:
        old = base_font_files.get(file_row.get("path"))
        if old and (old.get("fileSha256"), old.get("fileSizeBytes")) != (file_row.get("fileSha256"), file_row.get("fileSizeBytes")):
            raise FontCompletionError("CoreText file SHA differs from existing pinned identity: " + str(file_row.get("path")))
    if (resolved.record.get("targetOS"), resolved.record.get("targetOSVersion"), resolved.record.get("targetOSBuild")) != (
            base_resolution.get("targetOS"), base_resolution.get("targetOSVersion"), base_resolution.get("targetOSBuild")):
        raise FontCompletionError("CoreText target OS identity differs from the existing receipt")
    base_labels_by_id = _map_unique(base_resolution.get("labels") or [], "targetLabelId", "pinned CoreText labels")
    for label in resolved.record.get("labels") or []:
        if label.get("resolvedPrimaryFamily") != "Arial":
            raise FontCompletionError("null-font TTF source did not resolve to Arial: " + str(label.get("targetLabelId")))
        for scalar in label.get("unicodeScalars") or []:
            if not scalar.get("requiredForVisualText") or scalar.get("glyphCovered") is not True:
                raise FontCompletionError("CoreText missing a rendered source scalar: " + str(scalar.get("codepoint")))
            if scalar.get("fallback") is not True:
                continue
            scalar_identity = {"family": scalar.get("family"), "styleName": scalar.get("styleName"),
                               "postScriptName": scalar.get("postScriptName"),
                               "systemFontFileUrl": scalar.get("systemFontFileUrl"),
                               "variationAxes": scalar.get("variationAxes", {})}
            if any(scalar_identity[k] != fallback_identity[k] for k in scalar_identity):
                raise FontCompletionError("new fallback scalar resolved to a different face than the existing static atlas")
            file_evidence = next((row for row in resolved.record.get("resolvedFontFiles") or []
                                  if row.get("path") == scalar_identity["systemFontFileUrl"]), None)
            if not isinstance(file_evidence, dict) or file_evidence.get("fileSha256") != fallback_identity["fileSha256"]:
                raise FontCompletionError("new fallback scalar does not match the existing pinned CoreText font bytes")

    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise FontCompletionError("output directory must be empty: " + str(output))
    source_ir_prep = _build_augmented_ir(source_ir, labels)
    prep_ir_path = output / "preparation-only-ir.json"
    prep_ir_sha = _write_json(prep_ir_path, source_ir_prep)
    merged_resolution = _merge_resolution(base_resolution, resolved.record, labels,
                                          prep_ir_path, prep_ir_sha, Path(source_manifest_path), manifest_sha)
    merged_resolution_path = output / "coretext-resolution-receipt.json"
    merged_resolution_sha = _write_json(merged_resolution_path, merged_resolution)

    dynamic = prepare_system_fonts(source_ir_prep, prep_ir_sha, merged_resolution_path, merged_resolution_sha)
    if dynamic.status != "prepared":
        raise FontCompletionError("existing prefab_system_fonts.prepare rejected the merged receipt: " + str(dynamic.record.get("reason")))
    static = prepare_static_coretext_sdf_plan(source_ir_prep, prep_ir_sha, merged_resolution_path, merged_resolution_sha)
    if static.status != "prepared":
        raise FontCompletionError("existing static CoreText plan rejected the merged receipt: " + str(static.record.get("reason")))

    binding = deepcopy(dynamic.record)
    base_fonts = {font.get("assetId"): font for font in base_binding.get("systemFonts", {}).get("fonts") or []}
    static_dynamic_specs = [font for font in binding.get("systemFonts", {}).get("fonts") or []
                            if font.get("populationMode") == "StaticSDFRequired"]
    if len(static_dynamic_specs) != 1:
        raise FontCompletionError("merged binding must have exactly one CoreText static fallback")
    dynamic_static = static_dynamic_specs[0]
    base_static = base_fonts.get(dynamic_static.get("assetId"))
    if not isinstance(base_static, dict):
        raise FontCompletionError("existing Unity plan does not contain the same static fallback asset ID")
    # Preserve the complete glyph contract in this candidate, including glyphs
    # supplied by renderer-specific preparation outside prefab_system_fonts.
    merged_static_glyphs = _merge_glyph_rows(base_static.get("requiredGlyphs") or [], dynamic_static.get("requiredGlyphs") or [])
    merged_static_ids = sorted(set(base_static.get("sourceLabelIds") or []) | set(dynamic_static.get("sourceLabelIds") or []))
    dynamic_static["requiredGlyphs"] = merged_static_glyphs
    dynamic_static["requiredUnicode"] = [row["unicode"] for row in merged_static_glyphs]
    dynamic_static["sourceLabelIds"] = merged_static_ids
    dynamic_static["baseGenerationReceiptSha256"] = (plan.get("staticFontInputs") or {}).get("sourceGenerationReceiptSha256")
    for label in labels:
        binding_row = _font_fallback_mapping(binding, label["sourceComponentId"], label["sourceText"])
        if (binding_row.get("sourceFontFamily") != "Arial" or
                binding_row.get("nativeFontAssetId") != next((x.get("nativeFontAssetId") for x in base_binding.get("labelBindings", [])
                                                            if x.get("sourceFontFamily") == "Arial" and x.get("nativeFallbackAssetIds")), None)):
            raise FontCompletionError("source-effective Arial mapping does not reuse the existing Arial primary font")
        if dynamic_static["assetId"] not in binding_row.get("nativeFallbackAssetIds", []):
            raise FontCompletionError("new source-effective Arial label is not bound to the existing CoreText fallback atlas")

    static_plan = deepcopy(static.record)
    new_face = static_plan["systemFonts"][0]
    base_face = base_static
    if new_face.get("assetId") != base_face.get("assetId"):
        raise FontCompletionError("static plan changed the existing CoreText fallback asset ID")
    # Preserve glyphs already present in the candidate-specific binding and
    # union the newly prepared CoreText face before rendering the merged plan.
    new_face["requiredGlyphs"] = _merge_glyph_rows(base_face.get("requiredGlyphs") or [], new_face.get("requiredGlyphs") or [])
    new_face["requiredUnicode"] = [row["unicode"] for row in new_face["requiredGlyphs"]]
    new_face["sourceLabelIds"] = sorted(set(base_face.get("sourceLabelIds") or []) | set(new_face.get("sourceLabelIds") or []))
    new_face["atlasContract"]["allowedCodepoints"] = new_face["requiredUnicode"]
    static_plan["newCharacterBoundary"] = "preserved candidate atlas plus exact CoreText glyphs for the selected source null-font Labels; later/runtime text remains outside coverage"
    static_plan["preservedExistingGlyphAtlas"] = {
        "candidateOutput": (plan.get("staticFontInputs") or {}).get("candidateOutput"),
        "sourceGenerationReceiptSha256": (plan.get("staticFontInputs") or {}).get("sourceGenerationReceiptSha256"),
        "requiredGlyphCount": len(base_static.get("requiredGlyphs") or []),
        "sourceLabelCount": len(base_static.get("sourceLabelIds") or []),
    }
    static_plan["sourceEffectiveFontPolicyEvidence"] = ENGINE_EVIDENCE
    static_plan_path = output / "static-sdf-plan.json"
    static_plan_sha = _write_json(static_plan_path, static_plan)

    # Record the actual source state on the new bindings, even though the
    # helper's private preparation IR temporarily marks these as system-font.
    for row in binding.get("labelBindings") or []:
        if row.get("sourceLabelId") in ids:
            row["sourceSystemFont"] = False
            row["sourceSerializedFontUuid"] = None
            row["sourceEffectiveFontPolicy"] = SOURCE_EFFECTIVE_POLICY
            row["sourceEffectiveFamily"] = "Arial"
            row["sourceState"] = {"font": None, "systemFont": False}
            row["preparationInputSystemFont"] = True
    binding["systemFonts"]["staticCompletionPlanSha256"] = static_plan_sha
    binding["systemFonts"]["sourceEffectiveFontPolicyEvidence"] = ENGINE_EVIDENCE
    binding["labelBindings"] = sorted(binding["labelBindings"], key=lambda row: row.get("sourceLabelId", ""))
    binding_path = output / "unity-static-font-binding.json"
    binding_sha = _write_json(binding_path, binding)

    base_root = Path(base_stage_root).expanduser().resolve()
    source_font_dir = (plan.get("staticFontInputs") or {}).get("candidateOutput")
    if not isinstance(source_font_dir, str) or not source_font_dir:
        raise FontCompletionError("plan has no candidate path for its existing atlas")
    asset_id = dynamic_static["assetId"]
    base_artifacts = base_root / source_font_dir / "Assets/Game/Content/Fonts/System/StaticSdfInputs" / asset_id.removeprefix("coretext-static-sdf-")
    base_atlas_path = base_artifacts / "glyph-atlas.png"
    base_metrics_path = base_artifacts / "glyph-metrics.json"
    base_portable_path = base_artifacts / "generation-receipt.json"
    base_atlas_raw = base_atlas_path.read_bytes()
    base_metrics, base_metrics_raw = _read(base_metrics_path)
    base_portable, base_portable_raw = _read(base_portable_path)
    base_metric_rows = base_metrics.get("glyphs") or []
    base_metric_codes = {row.get("unicode") for row in base_metric_rows if isinstance(row, dict)}
    base_binding_codes = {row.get("unicode") for row in base_static.get("requiredGlyphs") or [] if isinstance(row, dict)}
    if (len(base_metric_codes) != len(base_metric_rows)
            or len(base_binding_codes) != len(base_static.get("requiredGlyphs") or [])
            or base_metric_codes != base_binding_codes):
        raise FontCompletionError("original binding glyph set differs from the pinned atlas metrics")
    if set(base_metrics.get("sourceLabelIds") or []) != set(base_static.get("sourceLabelIds") or []):
        raise FontCompletionError("original binding source-label set differs from the pinned atlas metrics")
    copies = {row.get("artifactKind"): row for row in (plan.get("staticFontInputs") or {}).get("copies") or []}
    for name, raw in (("glyph-atlas", base_atlas_raw), ("glyph-metrics", base_metrics_raw), ("portable-generation-receipt", base_portable_raw)):
        expected = copies.get(name)
        if not isinstance(expected, dict) or _sha(raw) != expected.get("sha256"):
            raise FontCompletionError("existing pinned atlas staging changed: " + name)
    if base_metrics.get("staticPlanSha256") != base_portable.get("planSha256") or base_metrics.get("resolutionReceiptSha256") != merged_resolution_sha:
        # The portable candidate was generated with the original CoreText
        # receipt. Its immutable prior hash remains valid; this check compares
        # the source receipt identity below instead of rewriting its pin.
        if base_metrics.get("resolutionReceiptSha256") != resolution_sha:
            raise FontCompletionError("existing atlas uses a different source CoreText receipt")
    generator = Path(generator_path).expanduser().resolve()
    generator_sha = _sha(generator.read_bytes())
    if base_metrics.get("generatorSourceSha256") != generator_sha:
        raise FontCompletionError("CoreText generator differs from the existing atlas generator")
    if (base_metrics.get("fontFileSha256") != new_face.get("targetSystemFontFileSha256") or
            base_metrics.get("variationAxesCanonical") != json.dumps(new_face.get("targetVariationAxes", {}), sort_keys=True, separators=(",", ":")) or
            base_metrics.get("targetOSVersion") != static_plan.get("targetOSVersion") or
            base_metrics.get("targetOSBuild") != static_plan.get("targetOSBuild")):
        raise FontCompletionError("new CoreText face/file/build differs from the existing pinned atlas")

    generation_dir = output / "fresh-coretext-generation"
    if run_coretext_generator:
        proc = subprocess.run(["swift", str(generator), str(static_plan_path), str(generation_dir)],
                              capture_output=True, text=True, timeout=240, check=False)
        (output / "coretext-generation.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
        if proc.returncode:
            raise FontCompletionError("CoreText SDF generation failed; see coretext-generation.log")
    else:
        raise FontCompletionError("run_coretext_generator=False is only available to pure contract tests")
    fresh_atlas_path = generation_dir / "glyph-atlas.png"
    fresh_metrics, _ = _read(generation_dir / "glyph-metrics.json")
    fresh_image = Image.open(fresh_atlas_path).convert("RGBA")
    old_image = Image.open(base_atlas_path).convert("RGBA")
    if old_image.size != fresh_image.size or tuple(old_image.size) != (base_metrics.get("atlasWidth"), base_metrics.get("atlasHeight")):
        raise FontCompletionError("existing and fresh CoreText atlas dimensions differ")
    old_by_code = {row["unicode"]: row for row in base_metrics.get("glyphs") or []}
    fresh_by_code = {row["unicode"]: row for row in fresh_metrics.get("glyphs") or []}
    wanted_codes = set(new_face["requiredUnicode"])
    if set(fresh_by_code) != wanted_codes or not set(old_by_code).issubset(fresh_by_code):
        raise FontCompletionError("fresh CoreText output does not cover the merged exact glyph set")
    new_codes = sorted(wanted_codes - set(old_by_code))
    if not new_codes:
        raise FontCompletionError("no glyph is missing from the existing atlas; no supplemental run is needed")
    for code, old in old_by_code.items():
        fresh = fresh_by_code[code]
        if not _same_glyph_metrics(old, fresh):
            raise FontCompletionError(f"existing CoreText glyph metrics changed at U+{code:04X}")
        orow, nrow = old["rect"], fresh["rect"]
        old_tile = old_image.crop((orow["x"], orow["y"], orow["x"] + orow["width"], orow["y"] + orow["height"]))
        new_tile = fresh_image.crop((nrow["x"], nrow["y"], nrow["x"] + nrow["width"], nrow["y"] + nrow["height"]))
        if old_tile.size != new_tile.size or ImageChops.difference(old_tile, new_tile).getbbox() is not None:
            raise FontCompletionError(f"existing CoreText glyph pixels changed at U+{code:04X}")
    final_image = old_image.copy()
    draw_x = 0
    draw_y = max(row["rect"]["y"] + row["rect"]["height"] for row in old_by_code.values()) + 1
    row_h = 0
    new_metrics = []
    for code in new_codes:
        row = deepcopy(fresh_by_code[code])
        rect = row["rect"]
        if draw_x + rect["width"] > final_image.width:
            draw_x, draw_y, row_h = 0, draw_y + row_h + 1, 0
        if draw_y + rect["height"] > final_image.height:
            raise FontCompletionError(f"new glyph tiles do not fit in the existing {final_image.width}x{final_image.height} atlas")
        box = (draw_x, draw_y, draw_x + rect["width"], draw_y + rect["height"])
        if final_image.crop(box).getbbox() is not None:
            raise FontCompletionError("new glyph tile placement overlaps existing atlas data")
        fresh_box = (rect["x"], rect["y"], rect["x"] + rect["width"], rect["y"] + rect["height"])
        tile = fresh_image.crop(fresh_box)
        final_image.paste(tile, (draw_x, draw_y))
        row["rect"] = {**rect, "x": draw_x, "y": draw_y}
        new_metrics.append(row)
        draw_x += rect["width"] + 1
        row_h = max(row_h, rect["height"])
    final_atlas_path = output / "glyph-atlas.png"
    final_image.save(final_atlas_path, format="PNG", optimize=False)
    final_image = Image.open(final_atlas_path).convert("RGBA")
    for code, old in old_by_code.items():
        rect = old["rect"]
        if ImageChops.difference(final_image.crop((rect["x"], rect["y"], rect["x"] + rect["width"], rect["y"] + rect["height"])),
                                old_image.crop((rect["x"], rect["y"], rect["x"] + rect["width"], rect["y"] + rect["height"]))).getbbox() is not None:
            raise FontCompletionError(f"preserved glyph pixels changed in final atlas at U+{code:04X}")
    final_metrics = deepcopy(fresh_metrics)
    final_metrics["glyphs"] = sorted([deepcopy(old_by_code[code]) for code in old_by_code] + new_metrics,
                                     key=lambda row: row["unicode"])
    final_metrics["requiredGlyphCount"] = len(final_metrics["glyphs"])
    final_metrics["sourceLabelIds"] = sorted(set(base_metrics.get("sourceLabelIds") or []) | set(new_face.get("sourceLabelIds") or []))
    final_metrics["staticPlanSha256"] = static_plan_sha
    final_metrics["resolutionReceiptSha256"] = merged_resolution_sha
    final_metrics["preservedAtlas"] = {"baseAtlasSha256": _sha(base_atlas_raw),
                                       "baseMetricsSha256": _sha(base_metrics_raw),
                                       "preservedGlyphCount": len(old_by_code),
                                       "addedGlyphCodepoints": [f"U+{code:04X}" for code in new_codes]}
    final_metrics_path = output / "glyph-metrics.json"
    final_metrics_sha = _write_json(final_metrics_path, final_metrics)
    atlas_sha = _sha(final_atlas_path.read_bytes())
    receipt = {
        "schema": "monkey-coretext-static-sdf-generation-receipt/1", "status": "generated",
        "atlasPath": str(final_atlas_path), "atlasSha256": atlas_sha,
        "metricsPath": str(final_metrics_path), "metricsSha256": final_metrics_sha,
        "planSha256": static_plan_sha, "resolutionReceiptSha256": merged_resolution_sha,
        "targetOS": static_plan["targetOS"], "targetOSVersion": static_plan["targetOSVersion"],
        "targetOSBuild": static_plan.get("targetOSBuild"), "glyphCount": len(final_metrics["glyphs"]),
        "sourceLabelCount": len(new_face["sourceLabelIds"]), "fontFileCopiedOrExported": False,
        "fontFileIncluded": False, "editorImport": "not_run", "saveReopenReadback": "not_run",
        "playerPlatformEvidence": "not_run", "visualEquivalent": False,
        "preservedBase": final_metrics["preservedAtlas"],
        "generatorSourceSha256": generator_sha,
    }
    receipt_path = output / "generation-receipt.json"
    receipt_sha = _write_json(receipt_path, receipt)
    staging = prepare_static_inputs(receipt_path, receipt_sha, binding, output / "UnityStage")
    if staging.status != "staged":
        raise FontCompletionError("existing prepare_static_inputs rejected generated artifacts: " + str(staging.record.get("reason")))
    staging_sha = _write_json(output / "staging-report.json", staging.record)

    updates = []
    for label in labels:
        binding_row = next(row for row in binding["labelBindings"] if row.get("sourceLabelId") == label["sourceComponentId"])
        updates.append({"sourceComponentId": label["sourceComponentId"], "sourceNodeId": label["sourceNodeId"],
                        "sourceState": {"font": None, "systemFont": False},
                        "sourceEffectiveFontPolicy": SOURCE_EFFECTIVE_POLICY,
                        "sourceEffectiveFamily": "Arial", "nativeFontAssetId": binding_row["nativeFontAssetId"],
                        "nativeFontAssetPath": binding_row["nativeFontAssetPath"],
                        "nativeFallbackAssetIds": binding_row["nativeFallbackAssetIds"],
                        "nativeFallbackAssetPaths": binding_row["nativeFallbackAssetPaths"],
                        "sourceText": label["sourceText"], "sourceFontSize": label["fontSize"],
                        "effectiveActive": label["effectiveActive"]})
    result = {"schema": SCHEMA, "status": "prepared", "planPath": str(Path(plan_path).resolve()),
              "planSha256": plan_hash, "sourceManifestSha256": manifest_sha, "sourceIrSha256": source_ir_sha,
              "sourceResolutionReceiptSha256": resolution_sha, "mergedResolutionReceiptSha256": merged_resolution_sha,
              "sourceEffectiveFontPolicy": ENGINE_EVIDENCE,
              "labels": updates, "labelCount": len(updates), "sourceSystemFontFlagPreserved": True,
              "preservedGlyphCount": len(old_by_code), "supplementalGlyphs": [
                  {"unicode": code, "character": chr(code), "codepoint": f"U+{code:04X}"} for code in new_codes],
              "generatedGlyphCount": len(final_metrics["glyphs"]), "staticPlanSha256": static_plan_sha,
              "generationReceiptSha256": receipt_sha, "stagingReportSha256": staging_sha,
              "bindingPath": str(binding_path), "staticPlanPath": str(static_plan_path),
              "generationReceiptPath": str(receipt_path), "stagingRoot": staging.record.get("stageRoot"),
              "editorImport": "not_run", "saveReopenReadback": "not_run", "visualEquivalent": False}
    _write_json(output / "font-completion.json", result)
    return result


def apply_prepared(
    plan: dict,
    completion_receipt_path: str | Path,
    expected_receipt_sha256: str,
    expected_binding_sha256: str,
    out_stage: str | Path,
) -> dict:
    """Copy verified font inputs into a new candidate stage and update a plan.

    Existing staged font files may be replaced only when their bytes match the
    source plan's pinned old hash. The source candidate and its font stage are
    read-only; the returned plan is a copy and the only file writes are the
    three receipt-owned SDF artifacts under ``out_stage``.
    """
    if not isinstance(plan, dict):
        raise FontCompletionError("plan must be an object")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_receipt_sha256 or ""):
        raise FontCompletionError("expected generation receipt SHA-256 is invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_binding_sha256 or ""):
        raise FontCompletionError("expected binding SHA-256 is invalid")
    receipt_path = Path(completion_receipt_path).expanduser().resolve()
    completion_root = receipt_path.parent
    receipt, receipt_raw = _read(receipt_path)
    if _sha(receipt_raw) != expected_receipt_sha256:
        raise FontCompletionError("generation receipt SHA differs from the supplied pin")
    if receipt.get("schema") != "monkey-coretext-static-sdf-generation-receipt/1" or receipt.get("status") != "generated":
        raise FontCompletionError("completion receipt is not a generated CoreText SDF receipt")

    completion_path = completion_root / "font-completion.json"
    completion, completion_raw = _read(completion_path)
    if completion.get("schema") != SCHEMA or completion.get("status") != "prepared":
        raise FontCompletionError("font-completion receipt is missing or invalid")
    if completion.get("generationReceiptSha256") != expected_receipt_sha256:
        raise FontCompletionError("font-completion receipt does not pin the supplied generation receipt")
    binding_path = Path(completion.get("bindingPath") or completion_root / "unity-static-font-binding.json").expanduser().resolve()
    binding, binding_raw = _read(binding_path)
    if _sha(binding_raw) != expected_binding_sha256:
        raise FontCompletionError("source-effective binding SHA differs from the supplied pin")
    if completion.get("sourceManifestSha256") != plan.get("sourceManifestSha256"):
        raise FontCompletionError("font completion belongs to a different source manifest")
    if completion.get("sourceIrSha256") != plan.get("sourceIrSha256"):
        raise FontCompletionError("font completion belongs to a different normalized source IR")
    original_binding = plan.get("systemFontBinding")
    if not isinstance(original_binding, dict) or not isinstance(original_binding.get("systemFonts"), dict):
        raise FontCompletionError("target plan lacks the original prepared CoreText binding")
    if completion.get("sourceResolutionReceiptSha256") != original_binding["systemFonts"].get("resolutionReceiptSha256"):
        raise FontCompletionError("font completion was resolved against a different pinned source CoreText receipt")
    if binding.get("schema") != "monkey-unity-system-fonts/1" or binding.get("status") != "prepared":
        raise FontCompletionError("completed binding set has an invalid schema/status")
    binding_system = binding.get("systemFonts") or {}
    if (binding_system.get("resolutionReceiptSha256") != completion.get("mergedResolutionReceiptSha256")
            or binding_system.get("sourceManifestSha256") != plan.get("sourceManifestSha256")):
        raise FontCompletionError("completed binding's source/resolution receipt pins differ")

    static_plan_path = completion_root / "static-sdf-plan.json"
    static_plan, static_plan_raw = _read(static_plan_path)
    static_plan_sha = _sha(static_plan_raw)
    if static_plan_sha != completion.get("staticPlanSha256") or static_plan_sha != binding_system.get("staticCompletionPlanSha256"):
        raise FontCompletionError("static SDF plan SHA differs from completion/binding pins")
    if receipt.get("planSha256") != static_plan_sha or receipt.get("resolutionReceiptSha256") != binding_system.get("resolutionReceiptSha256"):
        raise FontCompletionError("generation receipt is bound to another SDF plan or CoreText receipt")
    if receipt.get("targetOS") != static_plan.get("targetOS") or receipt.get("targetOSVersion") != static_plan.get("targetOSVersion"):
        raise FontCompletionError("generation receipt target OS differs from the static plan")

    completion_labels = completion.get("labels")
    if not isinstance(completion_labels, list) or not completion_labels:
        raise FontCompletionError("font completion has no Label updates")
    update_by_id = _map_unique(completion_labels, "sourceComponentId", "font completion Label updates")
    component_by_id = {row.get("sourceId"): row for row in plan.get("components") or [] if isinstance(row, dict)}
    expected_source_ids = {row.get("sourceId") for row in plan.get("components") or []
                           if isinstance(row, dict) and row.get("type") == "cc.Label"
                           and row.get("font") is None and row.get("systemFont") is False}
    if set(update_by_id) != expected_source_ids:
        missing = sorted(expected_source_ids - set(update_by_id))
        extra = sorted(set(update_by_id) - expected_source_ids)
        raise FontCompletionError(f"font completion Label denominator differs from plan; missing={missing}, extra={extra}")
    if completion.get("labelCount") != len(expected_source_ids):
        raise FontCompletionError("font completion source Label denominator count differs")
    bindings_by_id = _map_unique(binding.get("labelBindings") or [], "sourceLabelId", "completed font Label bindings")
    target_static_id = next((font.get("assetId") for font in binding_system.get("fonts") or []
                             if font.get("populationMode") == "StaticSDFRequired"), None)
    if not target_static_id:
        raise FontCompletionError("completed binding has no StaticSDFRequired fallback")
    for sid, update in update_by_id.items():
        component = component_by_id.get(sid)
        binding_row = bindings_by_id.get(sid)
        if (not isinstance(component, dict) or component.get("type") != "cc.Label"
                or component.get("font") is not None or component.get("systemFont") is not False):
            raise FontCompletionError("source Label state changed before application: " + sid)
        if (not isinstance(binding_row, dict) or binding_row.get("sourceSystemFont") is not False
                or binding_row.get("sourceSerializedFontUuid") is not None
                or binding_row.get("sourceEffectiveFontPolicy") != SOURCE_EFFECTIVE_POLICY
                or binding_row.get("sourceEffectiveFamily") != "Arial"
                or binding_row.get("nativeFontAssetId") != update.get("nativeFontAssetId")
                or target_static_id not in (binding_row.get("nativeFallbackAssetIds") or [])):
            raise FontCompletionError("source-effective font binding does not match its source Label: " + sid)
        if component.get("text") != update.get("sourceText") or component.get("fontSize") != update.get("sourceFontSize"):
            raise FontCompletionError("source Label text/size differs from its font-completion pin: " + sid)

    fonts = [row for row in binding_system.get("fonts") or [] if row.get("populationMode") == "StaticSDFRequired"]
    if len(fonts) != 1:
        raise FontCompletionError("completed binding has an ambiguous static fallback face")
    static_font = fonts[0]
    metric_path = Path(receipt.get("metricsPath") or "").expanduser().resolve()
    atlas_path = Path(receipt.get("atlasPath") or "").expanduser().resolve()
    metrics, metrics_raw = _read(metric_path)
    atlas_raw = atlas_path.read_bytes()
    if _sha(metrics_raw) != receipt.get("metricsSha256") or _sha(atlas_raw) != receipt.get("atlasSha256"):
        raise FontCompletionError("generated atlas or metrics SHA differs from its receipt")
    expected_codes = sorted(row.get("unicode") for row in static_font.get("requiredGlyphs") or [])
    metric_codes = sorted(row.get("unicode") for row in metrics.get("glyphs") or [])
    if (metrics.get("staticPlanSha256") != static_plan_sha
            or metrics.get("resolutionReceiptSha256") != binding_system.get("resolutionReceiptSha256")
            or metrics.get("fontFileSha256") != static_font.get("targetSystemFontFileSha256")
            or metric_codes != expected_codes or receipt.get("glyphCount") != len(expected_codes)
            or receipt.get("sourceLabelCount") != len(static_font.get("sourceLabelIds") or [])):
        raise FontCompletionError("SDF metrics, source font identity, or generated glyph set does not match binding")

    old_inputs = plan.get("staticFontInputs") or {}
    old_copies = {row.get("relativePath"): row for row in old_inputs.get("copies") or [] if isinstance(row, dict)}
    old_stage_root_value = old_inputs.get("stageRoot")
    if not isinstance(old_stage_root_value, str) or not old_stage_root_value:
        raise FontCompletionError("source plan does not pin the existing static-font stage root")
    base_stage_root = Path(old_stage_root_value).expanduser().resolve()
    if not base_stage_root.is_dir():
        raise FontCompletionError("pinned source static-font stage root is missing")
    old_metrics_copy = next((row for row in old_copies.values() if row.get("artifactKind") == "glyph-metrics"), None)
    if not isinstance(old_metrics_copy, dict):
        raise FontCompletionError("source plan does not pin its previous glyph-metrics artifact")
    old_metrics_path = (base_stage_root / old_metrics_copy["relativePath"]).resolve()
    if base_stage_root not in old_metrics_path.parents or not old_metrics_path.is_file():
        raise FontCompletionError("source glyph-metrics artifact is missing or escapes its stage")
    old_metrics_raw = old_metrics_path.read_bytes()
    if (_sha(old_metrics_raw) != old_metrics_copy.get("sha256")
            or len(old_metrics_raw) != old_metrics_copy.get("sizeBytes")):
        raise FontCompletionError("source glyph-metrics artifact differs from its plan pin")
    old_metrics = json.loads(old_metrics_raw.decode("utf-8"))
    supplemental = _validate_preserved_glyph_denominator(completion, old_metrics, expected_codes)
    old_codes = {row.get("unicode") for row in old_metrics.get("glyphs") or [] if isinstance(row, dict)}
    old_binding_fonts = [font for font in original_binding["systemFonts"].get("fonts") or []
                         if font.get("populationMode") == "StaticSDFRequired"]
    if len(old_binding_fonts) != 1:
        raise FontCompletionError("source plan must identify exactly one existing static fallback face")
    old_binding_codes = {row.get("unicode") for row in old_binding_fonts[0].get("requiredGlyphs") or []
                         if isinstance(row, dict)}
    if (old_binding_codes != old_codes
            or len(old_binding_codes) != len(old_binding_fonts[0].get("requiredGlyphs") or [])):
        raise FontCompletionError("source plan fallback glyph set differs from its pinned prior metrics")

    staging_report_path = completion_root / "staging-report.json"
    staging_report, staging_raw = _read(staging_report_path)
    if (_sha(staging_raw) != completion.get("stagingReportSha256")
            or staging_report.get("schema") != "monkey-unity-static-sdf-staged-inputs/1"
            or staging_report.get("status") != "staged"
            or staging_report.get("sourceGenerationReceiptSha256") != expected_receipt_sha256):
        raise FontCompletionError("portable static SDF staging receipt is missing or changed")
    stage_root = Path(staging_report.get("stageRoot") or "").expanduser().resolve()
    destination_root = Path(out_stage).expanduser().resolve()
    if (destination_root == stage_root or stage_root in destination_root.parents
            or destination_root in stage_root.parents):
        raise FontCompletionError("new candidate stage must be separate from the generated font stage")
    destination_root.mkdir(parents=True, exist_ok=True)

    old_candidate = old_inputs.get("candidateOutput")
    source_plan_path = Path(completion.get("planPath") or "").expanduser().resolve()
    if not source_plan_path.is_file():
        raise FontCompletionError("font completion source plan is missing")
    source_plan_doc, source_plan_raw = _read(source_plan_path)
    if (_sha(source_plan_raw) != completion.get("planSha256")
            or source_plan_doc != plan):
        raise FontCompletionError("the supplied plan differs from its pinned source plan")
    if (destination_root == base_stage_root or base_stage_root in destination_root.parents
            or destination_root in base_stage_root.parents):
        raise FontCompletionError("new candidate stage must be separate from the source font stage")
    for relative, old in old_copies.items():
        old_path = (base_stage_root / relative).resolve()
        if base_stage_root not in old_path.parents or not old_path.is_file():
            raise FontCompletionError("original staged font artifact is missing or escapes its candidate root")
        if _sha(old_path.read_bytes()) != old.get("sha256") or old_path.stat().st_size != old.get("sizeBytes"):
            raise FontCompletionError("original staged font artifact no longer matches old plan pin: " + str(relative))

    new_copies = staging_report.get("copies") or []
    if len(new_copies) != 3 or {row.get("artifactKind") for row in new_copies} != {
            "glyph-atlas", "glyph-metrics", "portable-generation-receipt"}:
        raise FontCompletionError("staging report must contain exactly the three bounded SDF artifacts")
    verified_copies = []
    for row in new_copies:
        relative = row.get("relativePath")
        if not isinstance(relative, str) or relative.startswith("/") or ".." in Path(relative).parts:
            raise FontCompletionError("staged font artifact path is unsafe")
        source = (stage_root / relative).resolve()
        if stage_root not in source.parents or not source.is_file():
            raise FontCompletionError("staged font artifact source is missing or escapes its stage")
        raw = source.read_bytes()
        if _sha(raw) != row.get("sha256") or len(raw) != row.get("sizeBytes"):
            raise FontCompletionError("staged font artifact differs from its receipt: " + relative)
        target = (destination_root / relative).resolve()
        if destination_root not in target.parents:
            raise FontCompletionError("font artifact target escapes the new candidate stage")
        if target.exists():
            existing_sha = _sha(target.read_bytes())
            old = old_copies.get(relative)
            if existing_sha != row.get("sha256") and (not isinstance(old, dict) or existing_sha != old.get("sha256")):
                raise FontCompletionError("existing destination font artifact is neither the pinned old nor prepared new file")
        verified_copies.append((row, source, target))
    for row, source, target in verified_copies:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())

    updated = deepcopy(plan)
    updated["systemFontBinding"] = deepcopy(binding)
    updated_static_inputs = deepcopy(staging_report)
    updated_static_inputs["candidateOutput"] = destination_root.name
    updated_static_inputs["stageRoot"] = str(destination_root)
    updated_static_inputs["sourceBaseCandidate"] = old_candidate
    updated_static_inputs["sourceBasePlanSha256"] = completion.get("planSha256")
    updated["staticFontInputs"] = updated_static_inputs
    updated["staticFontReceiptPath"] = staging_report.get("portableReceiptRelativePath")
    updated["staticFontReceiptSha256"] = staging_report.get("portableReceiptSha256")
    for sid, update in update_by_id.items():
        component = next(row for row in updated["components"] if row.get("sourceId") == sid)
        component["sourceEffectiveFontPolicy"] = SOURCE_EFFECTIVE_POLICY
        component["nativeEffectiveFontBinding"] = {
            "schema": "monkey-unity-effective-font-binding/1",
            "sourceEffectiveFontPolicy": SOURCE_EFFECTIVE_POLICY,
            "sourceFont": None, "sourceSystemFont": False,
            "sourceEffectiveFamily": "Arial",
            "nativeFontAssetId": update["nativeFontAssetId"],
            "nativeFontAssetPath": update["nativeFontAssetPath"],
            "nativeFallbackAssetIds": update["nativeFallbackAssetIds"],
            "nativeFallbackAssetPaths": update["nativeFallbackAssetPaths"],
            "sourceText": update["sourceText"], "sourceFontSize": update["sourceFontSize"],
        }
        # The renderer recipe is now complete. The source component values
        # (`font` and `systemFont`) intentionally stay null/false.
        component["convertible"] = True
    return {"status": "applied", "plan": updated, "copiedArtifacts": [
                {"relativePath": row["relativePath"], "sha256": row["sha256"], "sizeBytes": row["sizeBytes"]}
                for row in new_copies],
            "updatedLabelCount": len(update_by_id), "sourceSystemFontFalsePreserved": True,
            "sourceEffectiveFontPolicy": SOURCE_EFFECTIVE_POLICY,
            "staticFontInputs": updated_static_inputs,
            "staticFontReceiptPath": updated["staticFontReceiptPath"],
            "staticFontReceiptSha256": updated["staticFontReceiptSha256"]}
