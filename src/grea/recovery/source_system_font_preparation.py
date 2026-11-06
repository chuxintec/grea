"""Prepare pinned Cocos system-font bindings for a Unity recovery candidate.

This is a bounded adapter around the existing Cocos/CoreText resolver and
Unity system-font specification functions. Static glyph generation uses the
existing package-owned Swift helper. It never exports font files, runs source
scripts, or makes native Unity assets.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from . import io
from .prefab_font_binding import resolve_ir_macos_system_font_files
from .prefab_system_fonts import prepare as prepare_unity_system_fonts
from .prefab_system_fonts import prepare_static_coretext_sdf_plan, prepare_static_inputs
from .sources.compiled import fail


SCHEMA = "monkey-source-system-font-preparation/1"
SCHEMA_VERSION = 1
REQUEST_MAX_BYTES = 1024 * 1024
INPUT_MAX_BYTES = 128 * 1024 * 1024
TOTAL_INPUT_MAX_BYTES = 256 * 1024 * 1024
GENERATOR_ATLAS_MAX_BYTES = 32 * 1024 * 1024
GENERATOR_METRICS_MAX_BYTES = 16 * 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ASSET_ID = re.compile(r"^coretext-static-sdf-[0-9a-f]{24}$")


@dataclass(frozen=True)
class SourceSystemFontPreparation:
    """Result of one hash-pinned system-font preparation attempt."""

    status: str
    record: dict[str, Any]


@dataclass(frozen=True)
class SourceSystemFontGeneration:
    """Result of generating and staging one bounded CoreText SDF face."""

    status: str
    record: dict[str, Any]


def _request_error(code: str, location: str, message: str) -> None:
    fail(code, location, message)


def _digest_file(path: Path, limit: int) -> tuple[bytes, str]:
    raw = io.read(path, max_bytes=limit)
    return raw, io.sha(raw)


def _input_spec(request: dict[str, Any], name: str) -> tuple[Path, str]:
    value = request.get(name)
    if not isinstance(value, dict):
        _request_error("SOURCE_FONT_INPUT_INVALID", name, "Expected {path, sha256}")
    path_value, expected = value.get("path"), value.get("sha256")
    if not isinstance(path_value, str) or not path_value:
        _request_error("SOURCE_FONT_INPUT_INVALID", f"{name}.path", "Expected a non-empty absolute file path")
    if not Path(path_value).is_absolute():
        _request_error("SOURCE_FONT_INPUT_INVALID", f"{name}.path", "Input paths must be absolute")
    if not isinstance(expected, str) or not _SHA256.fullmatch(expected):
        _request_error("SOURCE_FONT_INPUT_INVALID", f"{name}.sha256", "Expected a lowercase SHA-256")
    path = io.safe(path_value)
    if not path.is_file():
        _request_error("SOURCE_FONT_INPUT_INVALID", f"{name}.path", "Input path must be an existing regular file")
    return path, expected


def _json(raw: bytes, location: str) -> dict[str, Any]:
    try:
        value = io.load(raw, max_nodes=8_000_000, max_depth=128)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        _request_error("SOURCE_FONT_JSON_INVALID", location, str(exc))
    if not isinstance(value, dict):
        _request_error("SOURCE_FONT_JSON_INVALID", location, "Expected a JSON object")
    return value


def _status_record(status: str, request_sha256: str, inputs: dict[str, dict[str, Any]],
                   reason: str, *, diagnostics: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "schemaVersion": SCHEMA_VERSION,
        "status": status,
        "requestSha256": request_sha256,
        "inputs": inputs,
        "sourceOSIdentityVerified": False,
        "visualEquivalent": False,
        "reason": reason,
        "diagnostics": diagnostics or [],
        "outputs": {},
        "nextAction": {"code": "REVIEW_SOURCE_FONT_EVIDENCE", "message": reason},
    }


def _write_failure(out: Path, record: dict[str, Any]) -> SourceSystemFontPreparation:
    io.write_json(out / "manifest.json", record)
    return SourceSystemFontPreparation(record["status"], record)


def prepare(
    request_path: str | Path,
    expected_request_sha256: str,
    output: str | Path,
) -> SourceSystemFontPreparation:
    """Resolve and prepare Unity bindings from an immutable JSON request.

    Request contract::

        {
          "schema": "monkey-source-system-font-preparation/1",
          "schemaVersion": 1,
          "ir": {"path": "/absolute/normalize/ir.json", "sha256": "..."},
          "sourceManifest": {"path": "/absolute/inspect/source-manifest.json", "sha256": "..."}
        }

    `resolution.json`, `unity-system-font-binding.json`, and an optional
    `static-sdf-plan.json` are written only to a new output directory. The
    returned status is `prepared`, `needs_static_generation`, or
    `needs_action`; `prepared` is a declaration, not native or visual proof.
    """
    if not isinstance(expected_request_sha256, str) or not _SHA256.fullmatch(expected_request_sha256):
        _request_error("SOURCE_FONT_REQUEST_HASH", "expected_request_sha256", "Expected a lowercase SHA-256")

    request_file = io.safe(request_path)
    request_raw, request_sha = _digest_file(request_file, REQUEST_MAX_BYTES)
    if request_sha != expected_request_sha256:
        _request_error("SOURCE_FONT_REQUEST_HASH", str(request_file), "Request SHA-256 differs from the supplied pin")
    request = _json(request_raw, str(request_file))
    if request.get("schema") != SCHEMA or type(request.get("schemaVersion")) is not int or request["schemaVersion"] != SCHEMA_VERSION:
        _request_error("SOURCE_FONT_REQUEST_SCHEMA", str(request_file), "Unsupported source system-font preparation contract")
    population_policy = request.get("unityPopulationPolicy", "dynamic-if-exact-v1")
    if population_policy not in {"dynamic-if-exact-v1", "coretext-static-fallbacks-v1"}:
        _request_error("SOURCE_FONT_POPULATION_POLICY", str(request_file), "Unsupported Unity population policy")

    ir_path, expected_ir_sha = _input_spec(request, "ir")
    manifest_path, expected_manifest_sha = _input_spec(request, "sourceManifest")
    ir_raw, ir_sha = _digest_file(ir_path, INPUT_MAX_BYTES)
    manifest_raw, manifest_sha = _digest_file(manifest_path, INPUT_MAX_BYTES)
    if len(ir_raw) + len(manifest_raw) + len(request_raw) > TOTAL_INPUT_MAX_BYTES:
        _request_error("SOURCE_FONT_BYTE_BUDGET", str(request_file), "Combined request and source evidence exceeds the byte budget")
    if ir_sha != expected_ir_sha:
        _request_error("SOURCE_FONT_INPUT_HASH", str(ir_path), "IR SHA-256 differs from the request pin")
    if manifest_sha != expected_manifest_sha:
        _request_error("SOURCE_FONT_INPUT_HASH", str(manifest_path), "Source-manifest SHA-256 differs from the request pin")

    ir = _json(ir_raw, str(ir_path))
    source_manifest = _json(manifest_raw, str(manifest_path))
    if (ir.get("sourceProfile") != "cocos-2.4.15-bundle"
            or source_manifest.get("sourceProfile") != "cocos-2.4.15-bundle"
            or source_manifest.get("sourceVersion") != "2.4.15"):
        _request_error("SOURCE_FONT_PROFILE_UNSUPPORTED", str(ir_path), "Inputs must declare Cocos Creator 2.4.15 bundle profile")
    if ir.get("sourceManifestSha256") != manifest_sha:
        _request_error("SOURCE_FONT_SOURCE_MANIFEST_MISMATCH", str(ir_path), "IR does not pin the exact source-manifest bytes")

    inputs = {
        "ir": {"path": str(ir_path), "bytes": len(ir_raw), "sha256": ir_sha},
        "sourceManifest": {"path": str(manifest_path), "bytes": len(manifest_raw), "sha256": manifest_sha},
    }
    out = io.new_output(output, [request_file, ir_path, manifest_path])

    # CoreText is a read-only query of this macOS host. Its own receipt freezes
    # the input hashes; these additional reads detect changes across the call.
    resolved = resolve_ir_macos_system_font_files(ir_path, manifest_path)
    raw_resolution_path = out / "coretext-resolution.json"
    io.write_json(raw_resolution_path, resolved.record)
    raw_resolution = io.read(raw_resolution_path, max_bytes=INPUT_MAX_BYTES)
    # Preserve the original CoreText evidence. The derived receipt carries the
    # explicit request-pinned native import policy without changing font faces.
    resolved_record = {**resolved.record, "unityPopulationPolicy": population_policy,
                       "coreTextResolutionSha256": io.sha(raw_resolution),
                       "unityPopulationPolicyRequestSha256": request_sha}
    resolution_path = out / "resolution.json"
    io.write_json(resolution_path, resolved_record)
    resolution_raw = io.read(resolution_path, max_bytes=INPUT_MAX_BYTES)
    resolution_sha = io.sha(resolution_raw)
    outputs: dict[str, dict[str, Any]] = {
        "resolution": {"path": "resolution.json", "bytes": len(resolution_raw), "sha256": resolution_sha},
        "coreTextResolution": {"path": "coretext-resolution.json", "bytes": len(raw_resolution), "sha256": io.sha(raw_resolution)},
    }
    try:
        after_request_raw, after_request_sha = _digest_file(request_file, REQUEST_MAX_BYTES)
        after_ir_raw, after_ir_sha = _digest_file(ir_path, INPUT_MAX_BYTES)
        after_manifest_raw, after_manifest_sha = _digest_file(manifest_path, INPUT_MAX_BYTES)
    except Exception as exc:
        failure = _status_record("needs_action", request_sha, inputs,
                                 f"Could not re-verify frozen inputs after CoreText resolution: {exc}")
        failure["resolutionStatus"] = resolved.status
        failure["outputs"] = outputs
        failure["diagnostics"] = [{"code": "SOURCE_FONT_INPUT_RECHECK_FAILED", "message": str(exc)}]
        return _write_failure(out, failure)
    if (after_request_sha != request_sha or after_ir_sha != ir_sha or after_manifest_sha != manifest_sha):
        failure = _status_record("needs_action", request_sha, inputs,
                                 "Request or source evidence changed during CoreText resolution")
        failure["resolutionStatus"] = resolved.status
        failure["outputs"] = outputs
        failure["observedAfterResolver"] = {
            "requestSha256": after_request_sha,
            "irSha256": after_ir_sha,
            "sourceManifestSha256": after_manifest_sha,
        }
        failure["diagnostics"] = [{"code": "SOURCE_FONT_INPUT_CHANGED", "message": failure["reason"]}]
        return _write_failure(out, failure)
    # Keep explicit variables live through the post-resolver identity check;
    # reading the bytes also exercises the same bounded decoder budget.
    del after_request_raw, after_ir_raw, after_manifest_raw

    if resolved.status != "resolved":
        reason = resolved.record.get("reason", f"CoreText resolver returned {resolved.status}")
        failure = _status_record("needs_action", request_sha, inputs, reason)
        failure["resolutionStatus"] = resolved.status
        failure["outputs"] = outputs
        failure["diagnostics"] = [{"code": "SOURCE_FONT_RESOLUTION_NEEDS_ACTION", "message": reason}]
        return _write_failure(out, failure)

    source_sample = resolved.record.get("sourceSample", {})
    frozen = source_sample.get("frozenInputs", {}) if isinstance(source_sample, dict) else {}
    frozen_ir = frozen.get("ir", {}) if isinstance(frozen, dict) else {}
    frozen_manifest = frozen.get("sourceManifest", {}) if isinstance(frozen, dict) else {}
    if (frozen_ir.get("sha256") != ir_sha or frozen_manifest.get("sha256") != manifest_sha):
        failure = _status_record("needs_action", request_sha, inputs,
                                 "CoreText receipt did not retain the exact requested source evidence hashes")
        failure["resolutionStatus"] = resolved.status
        failure["outputs"] = outputs
        failure["diagnostics"] = [{"code": "SOURCE_FONT_RESOLUTION_PIN_MISMATCH", "message": failure["reason"],
                                   "resolverReason": resolved.record.get("reason")}]
        return _write_failure(out, failure)

    binding = prepare_unity_system_fonts(ir, ir_sha, resolution_path, resolution_sha)
    binding_path = out / "unity-system-font-binding.json"
    io.write_json(binding_path, binding.record)
    binding_raw = io.read(binding_path, max_bytes=INPUT_MAX_BYTES)

    outputs.update({
        "unitySystemFontBinding": {"path": "unity-system-font-binding.json", "bytes": len(binding_raw),
                                   "sha256": io.sha(binding_raw)},
    })
    status = "needs_action"
    next_action: dict[str, str] = {"code": "REVIEW_SOURCE_FONT_EVIDENCE", "message": "Review resolver/binding diagnostics"}
    diagnostics: list[dict[str, Any]] = []
    static_plan = None
    if binding.status == "prepared":
        fonts = binding.record.get("systemFonts", {}).get("fonts", [])
        static_required = any(isinstance(font, dict) and font.get("populationMode") == "StaticSDFRequired"
                              for font in fonts)
        if static_required:
            static_plan = prepare_static_coretext_sdf_plan(ir, ir_sha, resolution_path, resolution_sha)
            static_path = out / "static-sdf-plan.json"
            io.write_json(static_path, static_plan.record)
            static_raw = io.read(static_path, max_bytes=INPUT_MAX_BYTES)
            outputs["staticSdfPlan"] = {"path": "static-sdf-plan.json", "bytes": len(static_raw),
                                         "sha256": io.sha(static_raw)}
            if static_plan.status == "prepared":
                status = "needs_static_generation"
                next_action = {
                    "code": "GENERATE_STATIC_SDF_INPUTS",
                    "message": "Generate only the bounded glyph atlas and metrics required by static-sdf-plan.json; this operation did not generate them",
                }
            else:
                diagnostics.append({"code": "STATIC_SDF_PLAN_NEEDS_ACTION", "message": static_plan.record.get("reason", static_plan.status)})
                next_action = {"code": "REVIEW_STATIC_SDF_PLAN", "message": static_plan.record.get("reason", static_plan.status)}
        else:
            status = "prepared"
            next_action = {
                "code": "NATIVE_FONT_IMPORT_PENDING",
                "message": "Create and read back native font assets through the target Editor; this operation only prepared binding declarations",
            }
    else:
        diagnostics.append({"code": "FONT_BINDING_NEEDS_ACTION", "message": binding.record.get("reason", binding.status)})
        next_action = {"code": "REVIEW_FONT_BINDING", "message": binding.record.get("reason", binding.status)}

    record = {
        "schema": SCHEMA,
        "schemaVersion": SCHEMA_VERSION,
        "status": status,
        "requestSha256": request_sha,
        "inputs": inputs,
        "sourceVersion": "2.4.15",
        "sourceProfile": "cocos-2.4.15-bundle",
        "sourceOSIdentityVerified": False,
        "visualEquivalent": False,
        "resolutionStatus": resolved.status,
        "unityBindingStatus": binding.status,
        "staticSdfPlanStatus": static_plan.status if static_plan is not None else "not_required",
        "unityPopulationPolicy": population_policy,
        "outputs": outputs,
        "diagnostics": diagnostics,
        "nextAction": next_action,
    }
    io.write_json(out / "manifest.json", record)
    return SourceSystemFontPreparation(status, record)


def _pinned_preparation(preparation: str | Path, expected_sha256: str):
    if not isinstance(expected_sha256, str) or not _SHA256.fullmatch(expected_sha256):
        _request_error("SOURCE_FONT_PREPARATION_HASH", "expected_preparation_sha256", "Expected a lowercase SHA-256")
    preparation_path = io.safe(preparation)
    raw = io.read(preparation_path, max_bytes=REQUEST_MAX_BYTES)
    actual_sha = io.sha(raw)
    if actual_sha != expected_sha256:
        _request_error("SOURCE_FONT_PREPARATION_HASH", str(preparation_path), "Preparation manifest SHA-256 differs from the supplied pin")
    manifest = _json(raw, str(preparation_path))
    if (manifest.get("schema") != SCHEMA or manifest.get("schemaVersion") != SCHEMA_VERSION
            or manifest.get("status") != "needs_static_generation"):
        _request_error("SOURCE_FONT_PREPARATION_INVALID", str(preparation_path), "Expected a needs_static_generation preparation manifest")
    if (manifest.get("resolutionStatus") != "resolved" or manifest.get("unityBindingStatus") != "prepared"
            or manifest.get("staticSdfPlanStatus") != "prepared"):
        _request_error("SOURCE_FONT_PREPARATION_INVALID", str(preparation_path), "Preparation outputs are not fully pinned and prepared")
    if manifest.get("sourceOSIdentityVerified") is not False or manifest.get("visualEquivalent") is not False:
        _request_error("SOURCE_FONT_PREPARATION_INVALID", str(preparation_path), "Preparation must preserve unverified source OS and visual equivalence")
    if not isinstance(manifest.get("requestSha256"), str) or not _SHA256.fullmatch(manifest["requestSha256"]):
        _request_error("SOURCE_FONT_PREPARATION_INVALID", str(preparation_path), "Preparation manifest has no valid request pin")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict) or not {"resolution", "unitySystemFontBinding", "staticSdfPlan"}.issubset(outputs):
        _request_error("SOURCE_FONT_PREPARATION_INVALID", str(preparation_path), "Preparation manifest is missing pinned output records")
    root = preparation_path.parent
    resolved_outputs: dict[str, Path] = {}
    for name, record in outputs.items():
        if not isinstance(record, dict):
            _request_error("SOURCE_FONT_PREPARATION_INVALID", f"outputs.{name}", "Expected a pinned output record")
        relative = record.get("path")
        if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
            _request_error("SOURCE_FONT_PREPARATION_INVALID", f"outputs.{name}.path", "Output paths must remain relative to preparation root")
        path = io.inside(root, relative)
        raw_output = io.read(path, max_bytes=INPUT_MAX_BYTES)
        if len(raw_output) != record.get("bytes") or io.sha(raw_output) != record.get("sha256"):
            _request_error("SOURCE_FONT_PREPARATION_DRIFT", str(path), "Preparation output differs from its hash/size pin")
        resolved_outputs[name] = path
    inputs = manifest.get("inputs")
    if not isinstance(inputs, dict) or not {"ir", "sourceManifest"}.issubset(inputs):
        _request_error("SOURCE_FONT_PREPARATION_INVALID", str(preparation_path), "Preparation manifest is missing frozen source input pins")
    total = len(raw)
    resolved_inputs: dict[str, Path] = {}
    for name in ("ir", "sourceManifest"):
        spec = inputs[name]
        if not isinstance(spec, dict) or not isinstance(spec.get("path"), str) or not Path(spec["path"]).is_absolute():
            _request_error("SOURCE_FONT_PREPARATION_INVALID", f"inputs.{name}", "Expected an absolute source evidence path")
        if not isinstance(spec.get("sha256"), str) or not _SHA256.fullmatch(spec["sha256"]):
            _request_error("SOURCE_FONT_PREPARATION_INVALID", f"inputs.{name}.sha256", "Expected a lowercase SHA-256")
        path = io.safe(spec["path"])
        source_raw = io.read(path, max_bytes=INPUT_MAX_BYTES)
        if io.sha(source_raw) != spec["sha256"] or len(source_raw) != spec.get("bytes"):
            _request_error("SOURCE_FONT_PREPARATION_DRIFT", str(path), "Source evidence differs from its frozen pin")
        total += len(source_raw)
        resolved_inputs[name] = path
    if total > TOTAL_INPUT_MAX_BYTES:
        _request_error("SOURCE_FONT_BYTE_BUDGET", str(preparation_path), "Preparation and frozen source evidence exceed the byte budget")
    return preparation_path, actual_sha, manifest, resolved_outputs, resolved_inputs


def _static_face_pair(plan: dict[str, Any], binding: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    plan_faces = plan.get("systemFonts")
    binding_system_fonts = binding.get("systemFonts")
    binding_fonts = binding_system_fonts.get("fonts") if isinstance(binding_system_fonts, dict) else None
    static_binding = [font for font in binding_fonts or [] if isinstance(font, dict) and font.get("populationMode") == "StaticSDFRequired"]
    if (plan.get("schema") != "monkey-unity-coretext-static-sdf-plan/1" or plan.get("status") != "prepared"
            or not isinstance(plan_faces, list) or len(plan_faces) != 1 or len(static_binding) != 1):
        _request_error("SOURCE_FONT_STATIC_PLAN_INVALID", "staticSdfPlan", "Exactly one prepared static CoreText SDF face is required")
    face, spec = plan_faces[0], static_binding[0]
    if not isinstance(face, dict):
        _request_error("SOURCE_FONT_STATIC_PLAN_INVALID", "staticSdfPlan.systemFonts[0]", "Expected a static face object")
    if not _ASSET_ID.fullmatch(str(spec.get("assetId", ""))):
        _request_error("SOURCE_FONT_BINDING_INVALID", "unitySystemFontBinding.systemFonts.fonts", "Static SDF asset ID is invalid")
    expected = {
        "familyName": face.get("targetFamily"),
        "styleName": face.get("targetStyleName"),
        "targetPostScriptName": face.get("targetPostScriptName"),
        "targetVariationAxes": face.get("targetVariationAxes"),
        "targetSystemFontFileSha256": face.get("targetSystemFontFileSha256"),
        "sourceLabelIds": sorted(face.get("sourceLabelIds", [])),
        "requiredGlyphs": sorted(face.get("requiredGlyphs", []), key=lambda item: item.get("unicode", -1)),
    }
    for key, value in expected.items():
        actual = spec.get(key)
        if key == "requiredGlyphs":
            actual = sorted(actual, key=lambda item: item.get("unicode", -1)) if isinstance(actual, list) else actual
        if actual != value:
            _request_error("SOURCE_FONT_STATIC_IDENTITY_MISMATCH", key, "Static plan and Unity binding identities differ")
    if (binding.get("schema") != "monkey-unity-system-fonts/1" or binding.get("status") != "prepared"
            or not isinstance(binding_system_fonts, dict)
            or binding_system_fonts.get("resolutionReceiptSha256") != plan.get("resolutionReceiptSha256")
            or plan.get("sourceOSIdentityVerified") is not False or plan.get("visualEquivalent") is not False):
        _request_error("SOURCE_FONT_STATIC_IDENTITY_MISMATCH", "staticSdfPlan", "Plan and binding status, receipt, or evidence boundaries disagree")
    return face, spec


def generate(
    preparation: str | Path,
    expected_preparation_sha256: str,
    output: str | Path,
    budget_seconds: int = 240,
) -> SourceSystemFontGeneration:
    """Generate and validate one pinned CoreText static-SDF face.

    `preparation` is the `manifest.json` produced by :func:`prepare`. The
    package-owned Swift generator is run with a bounded timeout. This function
    writes generator output and a generation receipt, then calls the existing
    `prepare_static_inputs` validator/stager. It never imports Unity assets.
    """
    if type(budget_seconds) is not int or not 1 <= budget_seconds <= 3600:
        _request_error("SOURCE_FONT_BUDGET_INVALID", "budget_seconds", "Expected an integer from 1 to 3600")
    preparation_path, preparation_sha, prep, prep_outputs, prep_inputs = _pinned_preparation(
        preparation, expected_preparation_sha256)
    plan_path = prep_outputs["staticSdfPlan"]
    binding_path = prep_outputs["unitySystemFontBinding"]
    plan_raw = io.read(plan_path, max_bytes=INPUT_MAX_BYTES)
    binding_raw = io.read(binding_path, max_bytes=INPUT_MAX_BYTES)
    plan = _json(plan_raw, str(plan_path))
    binding = _json(binding_raw, str(binding_path))
    face, spec = _static_face_pair(plan, binding)
    generator = Path(__file__).resolve().parent / "targets" / "GenerateCoreTextSdf.swift"
    generator_raw = io.read(generator, max_bytes=2 * 1024 * 1024)
    generator_sha = io.sha(generator_raw)
    swift_path_value = shutil.which("swift")
    if not swift_path_value:
        _request_error("SOURCE_FONT_SWIFT_UNAVAILABLE", "swift", "Swift is required to run the package-owned CoreText SDF generator")
    swift_path = io.safe(Path(swift_path_value).resolve())
    if not swift_path.is_file() or not os.access(swift_path, os.X_OK):
        _request_error("SOURCE_FONT_SWIFT_UNAVAILABLE", str(swift_path), "Swift path is not an executable file")

    out = io.new_output(output, [preparation_path, preparation_path.parent, *prep_inputs.values(),
                                 *prep_outputs.values(), generator, swift_path])
    generated_dir = out / "generated"
    try:
        proc = subprocess.run(
            [str(swift_path), str(generator), str(plan_path), str(generated_dir)],
            capture_output=True, text=True, timeout=budget_seconds, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        record = _generation_failure(preparation_path, preparation_sha, prep, "STATIC_SDF_TIMEOUT", f"Swift generator exceeded {budget_seconds}s", budget_seconds)
        record["stdout"] = _bounded_text(exc.stdout)
        record["stderr"] = _bounded_text(exc.stderr)
        io.write_json(out / "manifest.json", record)
        return SourceSystemFontGeneration("needs_action", record)
    except OSError as exc:
        record = _generation_failure(preparation_path, preparation_sha, prep, "STATIC_SDF_LAUNCH_FAILED", str(exc), budget_seconds)
        io.write_json(out / "manifest.json", record)
        return SourceSystemFontGeneration("needs_action", record)

    stdout, stderr = _bounded_text(proc.stdout), _bounded_text(proc.stderr)
    if proc.returncode != 0:
        record = _generation_failure(preparation_path, preparation_sha, prep, "STATIC_SDF_GENERATOR_FAILED",
                                     f"Swift generator exited {proc.returncode}", budget_seconds)
        record.update({"processExitCode": proc.returncode, "stdout": stdout, "stderr": stderr})
        io.write_json(out / "manifest.json", record)
        return SourceSystemFontGeneration("needs_action", record)

    atlas_path, metrics_path = generated_dir / "glyph-atlas.png", generated_dir / "glyph-metrics.json"
    try:
        atlas_raw = io.read(atlas_path, max_bytes=GENERATOR_ATLAS_MAX_BYTES)
        metrics_raw = io.read(metrics_path, max_bytes=GENERATOR_METRICS_MAX_BYTES)
    except Exception as exc:
        record = _generation_failure(preparation_path, preparation_sha, prep, "STATIC_SDF_OUTPUT_INVALID", str(exc), budget_seconds)
        record.update({"processExitCode": proc.returncode, "stdout": stdout, "stderr": stderr})
        io.write_json(out / "manifest.json", record)
        return SourceSystemFontGeneration("needs_action", record)
    atlas_sha, metrics_sha = io.sha(atlas_raw), io.sha(metrics_raw)
    try:
        metrics = _json(metrics_raw, str(metrics_path))
    except Exception as exc:
        record = _generation_failure(preparation_path, preparation_sha, prep, "STATIC_SDF_METRICS_INVALID",
                                     str(exc), budget_seconds)
        record.update({"processExitCode": proc.returncode, "stdout": stdout, "stderr": stderr,
                       "generatedAtlasSha256": atlas_sha, "generatedMetricsSha256": metrics_sha,
                       "generatedAtlasBytes": len(atlas_raw), "generatedMetricsBytes": len(metrics_raw)})
        io.write_json(out / "manifest.json", record)
        return SourceSystemFontGeneration("needs_action", record)
    required_unicode = sorted(item.get("unicode") for item in face.get("requiredGlyphs", []) if isinstance(item, dict))
    metrics_unicode = sorted(item.get("unicode") for item in metrics.get("glyphs", []) if isinstance(item, dict))
    expected_axes = spec.get("targetVariationAxesJson")
    expected_metrics = {
        "schema": "monkey-coretext-static-sdf-glyph-metrics/1",
        "status": "generated",
        "staticPlanSha256": io.sha(plan_raw),
        "generatorSourceSha256": generator_sha,
        "targetOS": plan.get("targetOS"),
        "targetOSVersion": plan.get("targetOSVersion"),
        "targetOSBuild": plan.get("targetOSBuild"),
        "resolutionReceiptSha256": plan.get("resolutionReceiptSha256"),
        "family": face.get("targetFamily"),
        "styleName": face.get("targetStyleName"),
        "postScriptName": face.get("targetPostScriptName"),
        "variationAxesCanonical": expected_axes,
        "fontFileSha256": face.get("targetSystemFontFileSha256"),
        "fontFileCopiedOrExported": False,
        "fontFileIncluded": False,
        "sourceLabelIds": sorted(face.get("sourceLabelIds", [])),
    }
    mismatches = [key for key, value in expected_metrics.items() if metrics.get(key) != value]
    if (mismatches or metrics_unicode != required_unicode or len(metrics_unicode) != len(set(metrics_unicode))
            or metrics.get("requiredGlyphCount") != len(required_unicode)
            or not metrics.get("atlasWidth") or not metrics.get("atlasHeight")):
        record = _generation_failure(preparation_path, preparation_sha, prep, "STATIC_SDF_METRICS_MISMATCH",
                                     "Generated metrics differ from the pinned plan/binding: " + ", ".join(mismatches or ["glyph set/atlas shape"]),
                                     budget_seconds)
        record.update({"processExitCode": proc.returncode, "stdout": stdout, "stderr": stderr,
                       "generatedAtlasSha256": atlas_sha, "generatedMetricsSha256": metrics_sha})
        io.write_json(out / "manifest.json", record)
        return SourceSystemFontGeneration("needs_action", record)

    receipt = {
        "schema": "monkey-coretext-static-sdf-generation-receipt/1",
        "status": "generated",
        "targetOS": plan.get("targetOS"),
        "targetOSVersion": plan.get("targetOSVersion"),
        "targetOSBuild": plan.get("targetOSBuild"),
        "resolutionReceiptSha256": plan.get("resolutionReceiptSha256"),
        "planSha256": io.sha(plan_raw),
        "atlasPath": str(atlas_path), "atlasSha256": atlas_sha,
        "metricsPath": str(metrics_path), "metricsSha256": metrics_sha,
        "generatorSourceSha256": generator_sha,
        "glyphCount": len(required_unicode),
        "sourceLabelCount": len(face.get("sourceLabelIds", [])),
        "fontFileCopiedOrExported": False,
        "fontFileIncluded": False,
        "visualEquivalent": False,
        "playerPlatformEvidence": "not_run",
    }
    receipt_path = out / "generation-receipt.json"
    io.write_json(receipt_path, receipt)
    receipt_raw = io.read(receipt_path, max_bytes=REQUEST_MAX_BYTES)
    receipt_sha = io.sha(receipt_raw)
    try:
        staging = prepare_static_inputs(receipt_path, receipt_sha, binding, out / "static-inputs-stage")
        staging_status, staging_record = staging.status, staging.record
    except Exception as exc:
        staging_status = "needs_action"
        staging_record = {"status": "needs_action", "reason": str(exc)}

    current_inputs: dict[str, str] = {}
    input_changed = False
    recheck_error = None
    try:
        for name, path in prep_inputs.items():
            raw = io.read(path, max_bytes=INPUT_MAX_BYTES)
            actual = io.sha(raw)
            current_inputs[name] = actual
            input_changed |= actual != prep["inputs"][name]["sha256"]
        current_preparation_sha = io.sha(io.read(preparation_path, max_bytes=REQUEST_MAX_BYTES))
        input_changed |= current_preparation_sha != preparation_sha
        for name, path in prep_outputs.items():
            raw = io.read(path, max_bytes=INPUT_MAX_BYTES)
            input_changed |= io.sha(raw) != prep["outputs"][name]["sha256"]
    except Exception as exc:
        input_changed = True
        recheck_error = str(exc)
    if input_changed:
        status = "needs_action"
        diagnostics = [{"code": "SOURCE_FONT_PREPARATION_CHANGED",
                        "message": recheck_error or "Pinned preparation or source inputs changed during generation"}]
        next_action = {"code": "REVIEW_GENERATION_INPUT_DRIFT", "message": diagnostics[0]["message"]}
    elif staging_status != "staged":
        status = "needs_action"
        diagnostics = [{"code": "STATIC_SDF_STAGING_NEEDS_ACTION", "message": staging_record.get("reason", staging_status)}]
        next_action = {"code": "REVIEW_STATIC_SDF_STAGING", "message": staging_record.get("reason", staging_status)}
    else:
        status = "prepared"
        diagnostics = []
        next_action = {"code": "NATIVE_STATIC_FONT_IMPORT_PENDING", "message": "Editor import/save/readback remains unrun"}

    static_stage = staging_record
    record = {
        "schema": "monkey-source-system-font-generation/1",
        "schemaVersion": 1,
        "status": status,
        "preparationPath": str(preparation_path),
        "preparationSha256": preparation_sha,
        "generator": {"path": str(generator), "sha256": generator_sha,
                      "swiftPath": str(swift_path), "budgetSeconds": budget_seconds,
                      "processExitCode": proc.returncode, "stdout": stdout, "stderr": stderr},
        "targetOS": plan.get("targetOS"),
        "targetOSVersion": plan.get("targetOSVersion"),
        "sourceOSIdentityVerified": False,
        "visualEquivalent": False,
        "fontFileCopiedOrExported": False,
        "fontFileIncluded": False,
        "generationReceipt": {"path": "generation-receipt.json", "sha256": receipt_sha,
                              "bytes": len(receipt_raw)},
        "generated": {
            "atlas": {"path": "generated/glyph-atlas.png", "sha256": atlas_sha, "bytes": len(atlas_raw)},
            "metrics": {"path": "generated/glyph-metrics.json", "sha256": metrics_sha, "bytes": len(metrics_raw)},
        },
        "stagingStatus": staging_status,
        "staticInputsStaging": staging_record,
        "sourceInputHashesAfterGeneration": current_inputs,
        "diagnostics": diagnostics,
        "nextAction": next_action,
    }
    io.write_json(out / "manifest.json", record)
    return SourceSystemFontGeneration(status, record)


def _bounded_text(value: str | bytes | None, limit: int = 16 * 1024) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return value[:limit]


def _generation_failure(preparation_path: Path, preparation_sha: str, prep: dict[str, Any], code: str,
                        reason: str, budget_seconds: int) -> dict[str, Any]:
    return {
        "schema": "monkey-source-system-font-generation/1",
        "schemaVersion": 1,
        "status": "needs_action",
        "preparationPath": str(preparation_path),
        "preparationSha256": preparation_sha,
        "inputPins": prep.get("inputs", {}),
        "generator": {"budgetSeconds": budget_seconds},
        "sourceOSIdentityVerified": False,
        "visualEquivalent": False,
        "fontFileCopiedOrExported": False,
        "fontFileIncluded": False,
        "diagnostics": [{"code": code, "message": reason}],
        "nextAction": {"code": "REVIEW_STATIC_SDF_GENERATION", "message": reason},
    }


def conversion_plan_inputs(ir_path, source_manifest, output):
    """Prepare verified Unity plan arguments for an explicit CoreText conversion."""
    from .sources.containers import fingerprint
    output = io.new_output(output, [ir_path, source_manifest])
    request = output / "request.json"
    io.write_json(request, {
        "schema": SCHEMA, "schemaVersion": SCHEMA_VERSION,
        "unityPopulationPolicy": "coretext-static-fallbacks-v1",
        "ir": {"path": str(ir_path), "sha256": fingerprint(ir_path)},
        "sourceManifest": {"path": str(source_manifest), "sha256": fingerprint(source_manifest)},
    })
    preparation = output / "preparation"
    prepared = prepare(request, fingerprint(request), preparation)
    if prepared.status not in ("prepared", "needs_static_generation"):
        _request_error("SYSTEM_FONT_BINDING_NOT_READY", str(request), prepared.record.get("reason") or prepared.status)
    resolution = preparation / "resolution.json"
    inputs = dict(system_font_resolution=resolution, expected_system_font_resolution=fingerprint(resolution))
    if prepared.status == "needs_static_generation":
        manifest = preparation / "manifest.json"
        generation = output / "generation"
        generated = generate(manifest, fingerprint(manifest), generation)
        if generated.status != "prepared":
            _request_error("STATIC_FONT_INPUTS_INVALID", str(manifest), generated.record.get("reason") or generated.status)
        receipt = generation / "generation-receipt.json"
        inputs.update(static_font_generation=receipt, expected_static_font_generation=fingerprint(receipt))
    return inputs
