"""Freeze a saved Unity selection plus a static-font completion for isolated import.

This module stages files and emits a bounded Editor request. It never launches
Unity and never edits the frozen source candidate or its source manifest.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import uuid
from typing import Any, Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_NAMESPACE = uuid.UUID("785d49c2-2a0c-4e3e-9364-c01b09df359a")
_STATIC_INPUT_ROOT = "Analysis/NativeFontCompletion/Inputs"
_REQUEST_PATH = "Analysis/NativeFontCompletion/request.json"
_STAGE_MANIFEST_PATH = "manifest.json"


class NativeFontStageError(ValueError):
    """A pinned candidate/completion cannot be safely staged."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _read_json(path: Path, expected_sha256: str | None, label: str) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink() or not path.is_file():
        raise NativeFontStageError(f"{label} must be a regular file")
    raw = path.read_bytes()
    if expected_sha256 is not None:
        if not isinstance(expected_sha256, str) or not _SHA256.fullmatch(expected_sha256):
            raise NativeFontStageError(f"{label} expected SHA-256 is malformed")
        if _sha(raw) != expected_sha256:
            raise NativeFontStageError(f"{label} SHA-256 differs from its supplied pin")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NativeFontStageError(f"{label} is not UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise NativeFontStageError(f"{label} root must be a JSON object")
    return value, raw


def _rel(value: Any, label: str) -> str:
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value
            or PurePosixPath(value).is_absolute()
            or any(part in ("", ".", "..") for part in value.split("/"))
            or any(ord(ch) < 32 for ch in value)):
        raise NativeFontStageError(f"{label} is not a canonical relative path")
    return value


def _inside(root: Path, relative: str) -> Path:
    path = root / relative
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise NativeFontStageError(f"symbolic link is forbidden in selected input: {relative}")
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise NativeFontStageError(f"selected path escapes its candidate: {relative}")
    return path


def _copy_verified(source: Path, target: Path, digest: str, size: int | None = None) -> int:
    if source.is_symlink() or not source.is_file():
        raise NativeFontStageError(f"selected file is absent or symbolic: {source}")
    actual, actual_size = _hash_file(source)
    if actual != digest or (size is not None and actual_size != size):
        raise NativeFontStageError(f"selected file differs from frozen hash: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        raise NativeFontStageError(f"staged output path already exists: {target}")
    shutil.copyfile(source, target)
    return actual_size


def _write(path: Path, raw: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return _sha(raw)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _guid(seed: str) -> str:
    return uuid.uuid5(_NAMESPACE, seed).hex


def _meta_text(kind: str, guid: str) -> bytes:
    common = f"fileFormatVersion: 2\nguid: {guid}\n"
    if kind == "folder":
        text = common + "folderAsset: yes\nDefaultImporter:\n  externalObjects: {}\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n"
    elif kind == "script":
        text = common + "MonoImporter:\n  externalObjects: {}\n  serializedVersion: 2\n  defaultReferences: []\n  executionOrder: 0\n  icon: {instanceID: 0}\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n"
    else:
        text = common + "TextScriptImporter:\n  externalObjects: {}\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n"
    return text.encode("utf-8")


def _add_file(project: Path, relpath: str, raw: bytes, stage_role: str, files: dict[str, dict[str, Any]]) -> None:
    relpath = _rel(relpath, "generated path")
    if relpath in files:
        raise NativeFontStageError(f"generated file collides with source candidate path: {relpath}")
    target = project / relpath
    digest = _write(target, raw)
    files[relpath] = {"path": relpath, "sha256": digest, "bytes": len(raw),
                      "owner": "generated", "stageRole": stage_role}


def _add_builtin_editor_modules(project: Path, files: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    """Pin only the built-in modules required by the Editor-only helper."""
    required = ("com.unity.modules.jsonserialize", "com.unity.modules.imageconversion")
    manifest_rel = "Packages/manifest.json"
    lock_rel = "Packages/packages-lock.json"
    if manifest_rel not in files or lock_rel not in files:
        raise NativeFontStageError("Unity package manifest and lock are required for an isolated Editor stage")
    manifest_path, lock_path = project / manifest_rel, project / lock_rel
    manifest, _ = _read_json(manifest_path, files[manifest_rel]["sha256"], "staged package manifest")
    lock, _ = _read_json(lock_path, files[lock_rel]["sha256"], "staged package lock")
    declared = manifest.get("dependencies")
    locked = lock.get("dependencies")
    if not isinstance(declared, dict) or not isinstance(locked, dict):
        raise NativeFontStageError("staged package records require dependency objects")
    changed = []
    for name in required:
        request = declared.get(name)
        if request not in (None, "1.0.0"):
            raise NativeFontStageError(f"built-in Editor module has an incompatible existing request: {name}")
        row = locked.get(name)
        if row is not None and (row.get("version") != "1.0.0" or row.get("source") != "builtin"):
            raise NativeFontStageError(f"built-in Editor module has an incompatible lock pin: {name}")
        if request is None:
            declared[name] = "1.0.0"
            locked[name] = {"version": "1.0.0", "depth": 0, "source": "builtin", "dependencies": {}}
            changed.append({"name": name, "version": "1.0.0", "source": "builtin"})
    if changed:
        for relpath, value in ((manifest_rel, manifest), (lock_rel, lock)):
            raw = _json_bytes(value)
            path = project / relpath
            path.write_bytes(raw)
            files[relpath] = {"path": relpath, "sha256": _sha(raw), "bytes": len(raw),
                              "owner": files[relpath].get("owner", "generated"),
                              "stageRole": "editor-builtin-module-pin"}
    return changed


def stage(
    candidate: str | Path,
    expected_manifest: str,
    completion_dir: str | Path,
    expected_completion: str,
    out: str | Path,
) -> dict[str, Any]:
    """Create a new Unity project plus a hash-pinned native font upgrade request.

    The source candidate's root ``manifest.json`` must be an accepted saved
    selection manifest. ``out`` must not exist. The prepared tree is
    ``out/UnityProject`` and the out-of-project launch request is
    ``out/font-request.json``; the function never invokes the Editor.
    """
    source = Path(candidate).expanduser().resolve()
    manifest_path = source / "manifest.json"
    source_manifest, source_manifest_raw = _read_json(manifest_path, expected_manifest, "saved selection manifest")
    if (source_manifest.get("schemaVersion") != 1
            or source_manifest.get("targetProfile") != "unity-6000.6.2f1-ugui"
            or not isinstance(source_manifest.get("files"), list)):
        raise NativeFontStageError("candidate manifest is not a schema-1 frozen file inventory")
    completion_root = Path(completion_dir).expanduser().resolve()
    completion_path = completion_root / "font-completion.json"
    completion, completion_raw = _read_json(completion_path, expected_completion, "font completion")
    if completion.get("schema") != "monkey-native-font-completion/1" or completion.get("status") != "prepared":
        raise NativeFontStageError("completion receipt is not a prepared native font completion")
    if (completion.get("nativeImport") != "pending" or completion.get("saveReopenReadback") != "pending"
            or completion.get("playerGlyphCheck") != "pending"):
        raise NativeFontStageError("expected a generated but not yet natively imported font completion")

    binding_path = completion_root / "unity-static-font-binding.json"
    binding_sha = completion.get("bindingSha256")
    binding, binding_raw = _read_json(binding_path, binding_sha, "completed font binding")
    resolution_path = completion_root / "consumer-corpus-resolution.json"
    resolution, resolution_raw = _read_json(
        resolution_path, completion.get("consumerResolutionReceiptSha256"), "consumer corpus resolution")
    stage_report_path = completion_root / "staging-report.json"
    stage_report, stage_report_raw = _read_json(
        stage_report_path, completion.get("stagingReportSha256"), "static SDF staging report")
    if stage_report.get("schema") != "monkey-unity-static-sdf-staged-inputs/1" or stage_report.get("status") != "staged":
        raise NativeFontStageError("completion static-SDF files were not hash-verified and staged")
    if (resolution.get("schema") != "monkey-consumer-text-coretext-resolution/1"
            or resolution.get("corpusSha256") != completion.get("corpusSha256")
            or not isinstance(resolution.get("labels"), list) or not resolution.get("labels")):
        raise NativeFontStageError("consumer text resolution does not match the pinned completion corpus")
    if not binding.get("systemFonts") or not isinstance(binding.get("labelBindings"), list):
        raise NativeFontStageError("completed binding does not contain a Unity system-font binding set")
    generation_receipt, generation_receipt_raw = _read_json(
        completion_root / "generation-receipt.json", completion.get("generationReceiptSha256"),
        "completed font generation receipt")
    static_plan, static_plan_raw = _read_json(
        completion_root / "static-sdf-plan.json", completion.get("planSha256"), "completed static SDF plan")
    metrics_path = completion_root / "glyph-metrics.json"
    atlas_path = completion_root / "glyph-atlas.png"
    if (_hash_file(metrics_path)[0] != completion.get("metricsSha256")
            or _hash_file(atlas_path)[0] != completion.get("atlasSha256")):
        raise NativeFontStageError("completed SDF atlas or metrics differ from the receipt")

    selected = completion.get("selectedStaticFont")
    if not isinstance(selected, Mapping) or not isinstance(selected.get("assetId"), str):
        raise NativeFontStageError("completion lacks an exact selected static face identity")
    system = binding["systemFonts"]
    fonts = system.get("fonts")
    static_specs = [row for row in fonts or [] if isinstance(row, Mapping)
                    and row.get("assetId") == selected["assetId"]]
    if (len(static_specs) != 1 or static_specs[0].get("populationMode") != "StaticSDFRequired"
            or static_specs[0].get("assetPath") != selected.get("assetPath")
            or static_specs[0].get("targetSystemFontFileSha256") != selected.get("targetSystemFontFileSha256")):
        raise NativeFontStageError("completion face differs from its saved native font binding")
    if static_specs[0].get("requiredUnicode") is None or len(static_specs[0].get("requiredUnicode")) != completion.get("generatedGlyphCount"):
        raise NativeFontStageError("updated binding does not carry the complete generated static glyph set")

    source_files: dict[str, dict[str, Any]] = {}
    folded: set[str] = set()
    for row in source_manifest["files"]:
        if not isinstance(row, Mapping):
            raise NativeFontStageError("candidate manifest contains a malformed file row")
        relpath = _rel(row.get("path"), "candidate manifest path")
        folded_path = relpath.casefold()
        if relpath in source_files or folded_path in folded:
            raise NativeFontStageError(f"candidate manifest contains duplicate/case-colliding path: {relpath}")
        digest = row.get("sha256")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise NativeFontStageError(f"candidate file hash is malformed: {relpath}")
        owner = row.get("owner", "generated")
        if owner not in {"generated", "retained", "manual"}:
            raise NativeFontStageError(f"candidate owner is outside Beaver's fixed schema: {relpath}")
        source_row = dict(path=relpath, sha256=digest, bytes=row.get("bytes"), owner=owner)
        if isinstance(row.get("stageRole"), str):
            source_row["stageRole"] = row["stageRole"]
        source_files[relpath] = source_row
        folded.add(folded_path)

    files_by_path = source_files
    font_contract = source_manifest.get("nativeFontCoverageContract")
    if not isinstance(font_contract, Mapping):
        raise NativeFontStageError("saved selection has no native font coverage boundary")
    native_font_rows = font_contract.get("fonts")
    if not isinstance(native_font_rows, list):
        raise NativeFontStageError("saved font coverage contract has no font inventory")
    contract_by_id = {row.get("assetId"): row for row in native_font_rows if isinstance(row, Mapping)}
    selected_contract = contract_by_id.get(selected["assetId"])
    if not isinstance(selected_contract, Mapping):
        raise NativeFontStageError("selected static face is not in the frozen native font coverage contract")
    selected_path = selected["assetPath"]
    static_row = files_by_path.get(selected_path)
    static_meta = files_by_path.get(selected_path + ".meta")
    if not isinstance(static_row, Mapping) or not isinstance(static_meta, Mapping):
        raise NativeFontStageError("selected static font and its Unity metadata must be frozen together")
    if (selected_contract.get("assetPath") != selected_path
            or selected_contract.get("assetSha256") != static_row["sha256"]
            or selected_contract.get("assetGuid", "").lower() != _meta_guid(_inside(source, selected_path + ".meta"))):
        raise NativeFontStageError("selected static font identity/hash differs from the saved selection")
    if selected_contract.get("assetSha256") != static_row["sha256"]:
        raise NativeFontStageError("selected static font differs from the prepared completion base")

    primary_ids = set(completion.get("primaryFontAssetIdsPreserved") or [])
    primary_rows = [row for row in fonts if isinstance(row, Mapping) and row.get("role") == "primary"
                    and row.get("assetId") in primary_ids]
    if not primary_rows or {row.get("assetId") for row in primary_rows} != primary_ids:
        raise NativeFontStageError("completed binding does not preserve the full declared primary face set")
    selected_primary = []
    for row in primary_rows:
        contract = contract_by_id.get(row.get("assetId"))
        if not isinstance(contract, Mapping):
            # Other static sample primaries may not be part of this selected closure.
            continue
        if selected["assetId"] not in (row.get("fallbackAssetIds") or []):
            raise NativeFontStageError(f"primary face does not declare the selected static fallback: {row.get('assetId')}")
        asset_path = row.get("assetPath")
        inventory = files_by_path.get(asset_path)
        meta = files_by_path.get(asset_path + ".meta")
        if not isinstance(inventory, Mapping) or not isinstance(meta, Mapping):
            continue
        if contract.get("assetSha256") != inventory.get("sha256"):
            raise NativeFontStageError(f"primary DynamicOS asset differs from the saved selection: {asset_path}")
        if contract.get("assetGuid", "").lower() != _meta_guid(_inside(source, asset_path + ".meta")):
            raise NativeFontStageError(f"primary DynamicOS GUID differs from the saved selection: {asset_path}")
        selected_primary.append({
            "assetId": row["assetId"], "assetPath": asset_path, "assetGuid": contract["assetGuid"].lower(),
            "assetSha256": inventory["sha256"], "metaSha256": meta["sha256"],
        })
    if not selected_primary:
        raise NativeFontStageError("saved selection has no bound primary DynamicOS asset to guard")

    source_root = Path(__file__).parent / "targets"
    helper = source_root / "UnitySystemFonts.cs"
    runner = source_root / "UnityStaticFontCompletion.cs"
    generator = source_root / "GenerateCoreTextSdf.swift"
    if (helper.is_symlink() or not helper.is_file() or runner.is_symlink() or not runner.is_file()
            or generator.is_symlink() or not generator.is_file()):
        raise NativeFontStageError("Editor font helper or completion runner source is missing")
    helper_template_bytes = helper.read_bytes()
    helper_template_sha = _sha(helper_template_bytes)
    helper_profile = "font-only-completion-v1"
    helper_bytes = b"#define MONKEY_STATIC_FONT_COMPLETION_ONLY\n" + helper_template_bytes
    helper_emitted_sha = _sha(helper_bytes)
    runner_bytes = runner.read_bytes()
    generator_bytes = generator.read_bytes()
    if ("UpgradeStaticSdfAsset(BindingSet bindingSet" not in helper_bytes.decode("utf-8")
            or "StaticSdfUpgradeReadback" not in helper_bytes.decode("utf-8")):
        raise NativeFontStageError("UnitySystemFonts does not expose the reviewed isolated static font upgrade bridge")
    if _sha(generator_bytes) != generation_receipt.get("generatorSourceSha256"):
        raise NativeFontStageError("packaged CoreText generator differs from the completed font receipt")

    requested_output = Path(out).expanduser().absolute()
    if requested_output.exists() or requested_output.is_symlink():
        raise NativeFontStageError("output directory already exists; use a new stage identity")
    output = requested_output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    project = output / "UnityProject"
    project.mkdir(parents=True)

    project_files: dict[str, dict[str, Any]] = {}
    for relpath, row in sorted(source_files.items()):
        if relpath == "manifest.json":
            continue
        source_file = _inside(source, relpath)
        size = _copy_verified(source_file, project / relpath, row["sha256"], row.get("bytes"))
        project_files[relpath] = {**row, "bytes": size}

    package_changes = _add_builtin_editor_modules(project, project_files)

    if any("/GameFont/" in "/" + path or path.endswith("/GameFont.asset") for path in project_files):
        raise NativeFontStageError("raw GameFont must not be copied into this completion candidate")

    evidence_dir = project / "Analysis/NativeFontCompletion/evidence"
    evidence_sources = [
        ("source-selection-manifest.json", source_manifest_raw, "selection-evidence"),
        ("font-completion.json", completion_raw, "font-completion-evidence"),
        ("unity-static-font-binding.json", binding_raw, "font-binding-evidence"),
        ("consumer-corpus-resolution.json", resolution_raw, "consumer-resolution-evidence"),
        ("staging-report.json", stage_report_raw, "font-staging-evidence"),
        ("static-sdf-plan.json", static_plan_raw, "font-plan-evidence"),
        ("generation-receipt.json", generation_receipt_raw, "font-generation-evidence"),
        ("glyph-metrics.json", metrics_path.read_bytes(), "font-metrics-evidence"),
        ("glyph-atlas.png", atlas_path.read_bytes(), "font-atlas-evidence"),
        ("GenerateCoreTextSdf.swift", generator_bytes, "font-generator-evidence"),
    ]
    if package_changes:
        for relpath, evidence_name in (("Packages/manifest.json", "source-package-manifest.json"),
                                       ("Packages/packages-lock.json", "source-packages-lock.json")):
            original_row = source_files.get(relpath)
            if not isinstance(original_row, Mapping):
                raise NativeFontStageError(f"source selection does not freeze {relpath}")
            original_raw = _inside(source, relpath).read_bytes()
            if _sha(original_raw) != original_row["sha256"]:
                raise NativeFontStageError(f"source package file changed before staging: {relpath}")
            evidence_sources.append((evidence_name, original_raw, "source-package-file-evidence"))
    for name, raw, owner in evidence_sources:
        _add_file(project, f"Analysis/NativeFontCompletion/evidence/{name}", raw, owner, project_files)

    font_key = selected["assetId"].removeprefix("coretext-static-sdf-")
    system_input_root = _STATIC_INPUT_ROOT + "/" + font_key
    staging_input_root = "Assets/Game/Content/Fonts/System/StaticSdfInputs/" + font_key
    input_root = completion_root / "UnityStage" / staging_input_root
    staged_receipt = input_root / "generation-receipt.json"
    staged_receipt_raw = staged_receipt.read_bytes()
    staged_receipt_sha = stage_report.get("portableReceiptSha256")
    if _sha(staged_receipt_raw) != staged_receipt_sha:
        raise NativeFontStageError("portable generation receipt differs from its staging report")
    for filename in ("glyph-atlas.png", "glyph-metrics.json", "generation-receipt.json"):
        row = next((item for item in stage_report.get("copies", [])
                    if item.get("relativePath") == f"{staging_input_root}/{filename}"), None)
        if not isinstance(row, Mapping):
            raise NativeFontStageError(f"static staging report is missing {filename}")
        raw = (input_root / filename).read_bytes()
        if _sha(raw) != row.get("sha256"):
            raise NativeFontStageError(f"staged static SDF input changed: {filename}")
        _add_file(project, f"{system_input_root}/{filename}", raw, "font-input", project_files)

    # Add deterministic, stage-specific Unity metadata for every new folder and
    # native C# source. Existing asset GUIDs stay byte-identical.
    new_paths = ["Assets/Game/Editor", "Assets/Game/Editor/NativeFontCompletion"]
    for folder in new_paths:
        rel_meta = folder + ".meta"
        if rel_meta not in project_files:
            meta_raw = _meta_text("folder", _guid(f"{expected_manifest}:{expected_completion}:{folder}"))
            _add_file(project, rel_meta, meta_raw, "font-stage-folder-meta", project_files)
    editor_folder = "Assets/Game/Editor/NativeFontCompletion"
    for name, raw in (("UnitySystemFonts.cs", helper_bytes), ("UnityStaticFontCompletion.cs", runner_bytes)):
        relpath = f"{editor_folder}/{name}"
        _add_file(project, relpath, raw, "font-stage-editor-tool", project_files)
        _add_file(project, relpath + ".meta", _meta_text("script", _guid(f"{expected_manifest}:{expected_completion}:{relpath}")),
                  "font-stage-script-meta", project_files)

    # The selected TMP asset's existing meta/GUID is the identity to retain.
    selected_guid = _meta_guid(_inside(source, selected_path + ".meta"))
    font_source_sha = static_row["sha256"]
    corpus_runs = []
    for row in resolution["labels"]:
        if not isinstance(row, Mapping) or not isinstance(row.get("text"), str):
            raise NativeFontStageError("consumer resolution has a malformed text run")
        corpus_runs.append(row["text"])
    if not corpus_runs:
        raise NativeFontStageError("consumer text corpus is empty")
    if len(set(corpus_runs)) > 1000 or sum(map(len, corpus_runs)) > 250_000:
        raise NativeFontStageError("consumer runtime text exceeds the native validation budget")

    existing_manifest_sha = expected_manifest
    source_selection_contract = {key: value for key, value in source_manifest.items() if key != "files"}
    staged_manifest = {
        **source_selection_contract,
        "schemaVersion": 1,
        "targetProfile": source_manifest.get("targetProfile"),
        "namespace": source_manifest.get("namespace"),
        "sourceSelectionContract": source_selection_contract,
        "stageKind": "native-static-font-corpus-completion",
        "sourceSelectionManifestSha256": existing_manifest_sha,
        "sourceCandidateManifestSha256": source_manifest.get("sourceCandidateManifestSha256"),
        "completionReceiptSha256": expected_completion,
        "fontBindingSha256": completion.get("bindingSha256"),
        "fontGenerationReceiptSha256": completion.get("generationReceiptSha256"),
        "portableGenerationReceiptSha256": staged_receipt_sha,
        "fontAtlasSha256": completion.get("atlasSha256"),
        "fontMetricsSha256": completion.get("metricsSha256"),
        "generatorSourceSha256": generation_receipt.get("generatorSourceSha256"),
        "selectedStaticFont": {
            "assetId": selected["assetId"], "assetPath": selected_path,
            "assetGuid": selected_guid, "originalAssetSha256": font_source_sha,
            "originalMetaSha256": static_meta["sha256"],
            "targetSystemFontFileSha256": selected.get("targetSystemFontFileSha256"),
            "originalGlyphCount": completion.get("baseGlyphCount"),
            "requiredGlyphCount": completion.get("generatedGlyphCount"),
            "addedGlyphs": completion.get("addedGlyphs"),
        },
        "primaryFontAssets": selected_primary,
        "editorOnlyBuiltinModules": package_changes,
        "editorToolSources": [
            {"path": f"{editor_folder}/UnitySystemFonts.cs", "sha256": helper_emitted_sha,
             "templateSha256": helper_template_sha, "emittedSha256": helper_emitted_sha,
             "profile": helper_profile},
            {"path": f"{editor_folder}/UnityStaticFontCompletion.cs", "sha256": _sha(runner_bytes),
             "templateSha256": _sha(runner_bytes), "emittedSha256": _sha(runner_bytes),
             "profile": "static-font-completion-runner-v1"},
        ],
        "files": sorted(project_files.values(), key=lambda row: row["path"]),
        "coverageBoundary": "File hashes and GUIDs are frozen before the Editor operation. The operation upgrades one existing static TMP font and validates fixed corpus lookups; Player rendering remains separate.",
    }
    _validate_dependency_endpoints(staged_manifest.get("adoptionDependencies"), project_files)
    stage_manifest_raw = _json_bytes(staged_manifest)
    stage_manifest_sha = _write(project / "manifest.json", stage_manifest_raw)
    project_files["manifest.json"] = {"path": "manifest.json", "sha256": stage_manifest_sha,
                                      "bytes": len(stage_manifest_raw), "owner": "generated",
                                      "stageRole": "native-font-stage-manifest"}

    request = {
        "schema": "monkey-unity-static-font-completion-request/1", "status": "prepared",
        "projectRoot": str(project.resolve()), "stageManifestPath": "manifest.json",
        "stageManifestSha256": stage_manifest_sha,
        "sourceSelectionManifestSha256": expected_manifest,
        "completionReceiptSha256": expected_completion,
        "completionEvidencePath": "Analysis/NativeFontCompletion/evidence/font-completion.json",
        "fontBindingPath": "Analysis/NativeFontCompletion/evidence/unity-static-font-binding.json",
        "fontBindingSha256": completion["bindingSha256"],
        "generationReceiptPath": system_input_root + "/generation-receipt.json",
        "generationReceiptSha256": staged_receipt_sha,
        "consumerResolutionPath": "Analysis/NativeFontCompletion/evidence/consumer-corpus-resolution.json",
        "consumerResolutionSha256": completion["consumerResolutionReceiptSha256"],
        "corpusSha256": completion["corpusSha256"],
        "consumerTexts": corpus_runs,
        "staticFontAssetId": selected["assetId"], "staticFontAssetPath": selected_path,
        "staticFontAssetGuid": selected_guid, "staticFontAssetSha256Before": font_source_sha,
        "staticFontMetaSha256": static_meta["sha256"], "staticFontRequiredUnicode": static_specs[0]["requiredUnicode"],
        "staticFontAddedGlyphs": completion["addedGlyphs"],
        "staticFontBaseGlyphCount": completion["baseGlyphCount"],
        "staticFontRequiredGlyphCount": completion["generatedGlyphCount"],
        "primaryFontAssets": selected_primary,
        "forbiddenAssetPaths": ["Assets/Game/Content/Fonts/GameFont/GameFont.asset"],
        "nativeReadbackPath": "Analysis/NativeFontCompletion/native-readback.json",
    }
    request_raw = _json_bytes(request)
    request_path = output / "font-request.json"
    request_sha = _write(request_path, request_raw)
    report = {
        "schema": "monkey-native-font-stage/1", "status": "staged",
        "sourceSelectionManifestSha256": expected_manifest,
        "completionReceiptSha256": expected_completion,
        "outputRoot": str(output.resolve()), "projectRoot": str(project.resolve()),
        "stageManifestSha256": stage_manifest_sha,
        "requestPath": str(request_path.resolve()), "requestSha256": request_sha,
        "fileCount": len(project_files),
        "editorOnlyBuiltinModules": package_changes,
        "fontAsset": {"assetId": selected["assetId"], "path": selected_path,
                      "guid": selected_guid, "sha256Before": font_source_sha,
                      "metaSha256": static_meta["sha256"]},
        "primaryFontAssets": selected_primary,
        "nativeImport": "not_run", "saveReopenReadback": "not_run", "playerGlyphCheck": "not_run",
        "launchArguments": ["-projectPath", str(project.resolve()), "-batchmode", "-quit",
                            "-executeMethod", "Monkey.NativeEditor.UnityStaticFontCompletion.Run",
                            "-monkeyFontRequest", str(request_path.resolve()),
                            "-monkeyFontRequestSha256", request_sha],
    }
    _write(output / "stage-report.json", _json_bytes(report))
    return report


def _meta_guid(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise NativeFontStageError(f"Unity .meta file is missing: {path}")
    text = path.read_text(encoding="utf-8")
    match = re.search(r"(?m)^guid:\s*([0-9a-fA-F]{32})\s*$", text)
    if not match:
        raise NativeFontStageError(f"Unity .meta GUID is malformed: {path}")
    return match.group(1).lower()


def _validate_dependency_endpoints(dependencies: Any, files: Mapping[str, Mapping[str, Any]]) -> None:
    if dependencies is None:
        return
    if not isinstance(dependencies, Mapping) or not isinstance(dependencies.get("edges"), list):
        raise NativeFontStageError("adoption dependency contract has no edge list")
    available = set(files)
    for edge in dependencies["edges"]:
        if not isinstance(edge, Mapping) or not isinstance(edge.get("path"), str):
            raise NativeFontStageError("adoption dependency edge is malformed")
        required = edge.get("requires", [])
        if not isinstance(required, list):
            raise NativeFontStageError("adoption dependency edge requires must be a list")
        if any(not isinstance(path, str) or path not in available for path in [edge["path"], *required]):
            raise NativeFontStageError("adoption dependency edge endpoint is absent from the candidate inventory")


def _classify_final_files(
    stage_files: Mapping[str, Mapping[str, Any]],
    source_files: Mapping[str, Mapping[str, Any]],
    editor_tool_sources: Any,
) -> dict[str, str]:
    """Classify each staged file for the final adoption closure, without native claims."""
    helper_paths = {row.get("path") for row in editor_tool_sources or []
                    if isinstance(row, Mapping) and isinstance(row.get("path"), str)}
    helper_paths.update(path + ".meta" for path in tuple(helper_paths))
    generated_editor_meta = {
        path + ".meta" for path in ("Assets/Game/Editor", "Assets/Game/Editor/NativeFontCompletion")
        if stage_files.get(path + ".meta", {}).get("stageRole") == "font-stage-folder-meta"
    }
    excluded = helper_paths | generated_editor_meta
    result = {}
    for relpath in stage_files:
        if relpath in excluded:
            result[relpath] = "excluded-editor-execution-helper"
        elif relpath in source_files:
            result[relpath] = "retained-source-selection"
        elif relpath.startswith("Analysis/NativeFontCompletion/"):
            result[relpath] = "retained-stage-evidence"
        else:
            result[relpath] = "excluded-non-evidence-stage-addition"
    return result


def finish_stage(
    project: str | Path,
    expected_stage_manifest_sha256: str,
    native_readback_path: str | Path,
    expected_native_readback_sha256: str,
    out: str | Path,
) -> dict[str, Any]:
    """Freeze the Editor-updated font as a new Beaver-consumable candidate.

    Only the selected static font bytes may change. Primary DynamicOS assets,
    original Prefabs, their metadata/GUIDs, staged inputs, and editor tools must
    retain their staged hashes. The source selection is never rewritten.
    """
    root = Path(project).expanduser().resolve()
    stage_manifest, stage_manifest_raw = _read_json(root / "manifest.json", expected_stage_manifest_sha256,
                                                    "native font stage manifest")
    native_readback, native_raw = _read_json(Path(native_readback_path), expected_native_readback_sha256,
                                             "native font readback")
    if native_readback.get("schema") != "monkey-unity-static-font-completion-readback/1" or native_readback.get("status") != "pass":
        raise NativeFontStageError("Unity did not report a passing font save/reopen/corpus lookup readback")
    if (native_readback.get("stageManifestSha256") != expected_stage_manifest_sha256
            or native_readback.get("sourceSelectionManifestSha256") != stage_manifest.get("sourceSelectionManifestSha256")
            or native_readback.get("completionReceiptSha256") != stage_manifest.get("completionReceiptSha256")):
        raise NativeFontStageError("native font readback is bound to a different selection/completion stage")
    static = stage_manifest.get("selectedStaticFont")
    if not isinstance(static, Mapping):
        raise NativeFontStageError("stage manifest has no selected static font identity")
    if (native_readback.get("staticFontAssetGuid") != static.get("assetGuid")
            or native_readback.get("staticFontAssetPath") != static.get("assetPath")
            or native_readback.get("fontGuidBefore") != static.get("assetGuid")
            or native_readback.get("fontGuidAfter") != static.get("assetGuid")
            or native_readback.get("fontLocalIdBefore") != native_readback.get("fontLocalIdAfter")
            or native_readback.get("atlasGuidBefore") != native_readback.get("atlasGuidAfter")
            or native_readback.get("atlasLocalIdBefore") != native_readback.get("atlasLocalIdAfter")
            or native_readback.get("materialGuidBefore") != native_readback.get("materialGuidAfter")
            or native_readback.get("materialLocalIdBefore") != native_readback.get("materialLocalIdAfter")
            or native_readback.get("tryAddCharactersCalled") is not False
            or native_readback.get("missingRequiredUnicode") not in ([], None)
            or native_readback.get("missingCorpusUnicode") not in ([], None)):
        raise NativeFontStageError("native font readback does not preserve asset/subasset identity or glyph coverage")
    if native_readback.get("primaryAssetsUnchanged") is not True:
        raise NativeFontStageError("a primary DynamicOS font asset changed during Editor import")

    files = stage_manifest.get("files")
    if not isinstance(files, list):
        raise NativeFontStageError("stage manifest has no file inventory")
    selection_contract = stage_manifest.get("sourceSelectionContract")
    if not isinstance(selection_contract, Mapping):
        raise NativeFontStageError("stage manifest lost the frozen source selection contract")
    source_manifest_raw = _inside(root, "Analysis/NativeFontCompletion/evidence/source-selection-manifest.json").read_bytes()
    if _sha(source_manifest_raw) != stage_manifest.get("sourceSelectionManifestSha256"):
        raise NativeFontStageError("embedded source selection manifest differs from its pinned hash")
    try:
        source_selection = json.loads(source_manifest_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NativeFontStageError(f"embedded source selection manifest is invalid: {exc}") from exc
    if not isinstance(source_selection, Mapping) or not isinstance(source_selection.get("files"), list):
        raise NativeFontStageError("embedded source selection has no frozen file inventory")
    if {key: value for key, value in source_selection.items() if key != "files"} != dict(selection_contract):
        raise NativeFontStageError("source selection contract differs from the staged contract")
    original_files: dict[str, dict[str, Any]] = {}
    for row in source_selection["files"]:
        if not isinstance(row, Mapping):
            raise NativeFontStageError("source selection has a malformed file inventory row")
        relpath = _rel(row.get("path"), "source selection file path")
        if relpath in original_files:
            raise NativeFontStageError(f"source selection has a duplicate file path: {relpath}")
        if row.get("owner", "generated") not in {"generated", "retained", "manual"}:
            raise NativeFontStageError(f"source selection contains an invalid Beaver owner: {relpath}")
        original_files[relpath] = dict(row)
    static_path = static.get("assetPath")
    source_inventory: dict[str, dict[str, Any]] = {}
    final_inventory: list[dict[str, Any]] = []
    for row in files:
        if not isinstance(row, Mapping):
            raise NativeFontStageError("stage manifest contains a malformed file row")
        relpath = _rel(row.get("path"), "stage manifest path")
        if relpath == "manifest.json":
            continue
        source_inventory[relpath] = dict(row)
    updated_font_sha = native_readback.get("staticFontAssetSha256After")
    if not isinstance(updated_font_sha, str) or not _SHA256.fullmatch(updated_font_sha):
        raise NativeFontStageError("native readback omits the final static TMP asset hash")
    out_root = Path(out).expanduser().absolute()
    if out_root.exists() or out_root.is_symlink():
        raise NativeFontStageError("final output directory already exists; use a fresh candidate identity")
    out_root.mkdir(parents=True)
    project_out = out_root / "UnityProject"
    project_out.mkdir()
    classifications = _classify_final_files(source_inventory, original_files, stage_manifest.get("editorToolSources"))
    dispositions: list[dict[str, Any]] = []
    staged_paths = set(source_inventory)
    if not set(original_files).issubset(staged_paths):
        raise NativeFontStageError("stage dropped one or more source selection files")
    source_package_evidence = {
        "Packages/manifest.json": "Analysis/NativeFontCompletion/evidence/source-package-manifest.json",
        "Packages/packages-lock.json": "Analysis/NativeFontCompletion/evidence/source-packages-lock.json",
    }

    def retain_file(relpath: str, staged_row: Mapping[str, Any], original_row: Mapping[str, Any] | None = None) -> None:
        expected = (updated_font_sha if relpath == static_path else
                    original_row.get("sha256") if original_row is not None else staged_row.get("sha256"))
        evidence_path = source_package_evidence.get(relpath)
        source_file = (_inside(root, evidence_path)
                       if original_row is not None and evidence_path and (root / evidence_path).is_file()
                       else _inside(root, relpath))
        actual, size = _hash_file(source_file)
        if actual != expected:
            raise NativeFontStageError(f"unexpected post-Editor file change: {relpath}")
        _copy_verified(source_file, project_out / relpath, expected, size)
        inventory_row = original_row if original_row is not None else staged_row
        stage_role = inventory_row.get("stageRole", "source-selection-file") if original_row is not None else staged_row.get("stageRole", "stage-evidence")
        final_inventory.append({"path": relpath, "sha256": actual, "bytes": size,
                                "owner": inventory_row.get("owner", "generated"),
                                "stageRole": stage_role})
        dispositions.append({"path": relpath, "sha256": actual,
                             "stageRole": stage_role,
                             "classification": "retained-source-selection" if original_row is not None else "retained-stage-evidence"})

    for relpath, row in sorted(source_inventory.items()):
        classification = classifications[relpath]
        if classification.startswith("excluded-"):
            dispositions.append({"path": relpath, "sha256": row.get("sha256"),
                                 "stageRole": row.get("stageRole", "editor-tool-support"),
                                 "classification": classification})
            continue
        original_row = original_files.get(relpath)
        retain_file(relpath, row, original_row)

    native_readback_relative = "Analysis/NativeFontCompletion/native-readback.json"
    actual_native_readback = _inside(root, native_readback_relative)
    if actual_native_readback.resolve() != Path(native_readback_path).expanduser().resolve():
        raise NativeFontStageError("native readback must be written to the request-bound project location")
    _copy_verified(actual_native_readback, project_out / native_readback_relative, expected_native_readback_sha256)
    final_inventory.append({"path": native_readback_relative, "sha256": expected_native_readback_sha256,
                            "bytes": actual_native_readback.stat().st_size, "owner": "generated",
                            "stageRole": "native-font-readback"})
    dispositions.append({"path": native_readback_relative, "sha256": expected_native_readback_sha256,
                         "stageRole": "native-font-readback", "classification": "retained-native-validation-evidence"})
    source_stage_copy_rel = "Analysis/NativeFontCompletion/source-stage-manifest.json"
    _write(project_out / source_stage_copy_rel, stage_manifest_raw)
    final_inventory.append({"path": source_stage_copy_rel, "sha256": expected_stage_manifest_sha256,
                            "bytes": len(stage_manifest_raw), "owner": "generated",
                            "stageRole": "native-font-stage-evidence"})
    dispositions.append({"path": source_stage_copy_rel, "sha256": expected_stage_manifest_sha256,
                         "stageRole": "native-font-stage-evidence", "classification": "retained-native-validation-evidence"})
    final_file_map = {row["path"]: row for row in final_inventory}
    _validate_dependency_endpoints(selection_contract.get("adoptionDependencies"), final_file_map)
    derived = {
        **selection_contract,
        "schemaVersion": 1,
        "targetProfile": stage_manifest.get("targetProfile"),
        "namespace": selection_contract.get("namespace"),
        "sourceSelectionContract": dict(selection_contract),
        "stageKind": "native-static-font-corpus-completion",
        "sourceSelectionManifestSha256": stage_manifest.get("sourceSelectionManifestSha256"),
        "sourceCandidateManifestSha256": stage_manifest.get("sourceCandidateManifestSha256"),
        "sourceStageManifestSha256": expected_stage_manifest_sha256,
        "completionReceiptSha256": stage_manifest.get("completionReceiptSha256"),
        "nativeReadbackSha256": expected_native_readback_sha256,
        "selectedStaticFont": {
            **static, "assetSha256": updated_font_sha,
            "fontGuid": native_readback.get("fontGuidAfter"),
            "fontLocalId": native_readback.get("fontLocalIdAfter"),
            "atlasGuid": native_readback.get("atlasGuidAfter"),
            "atlasLocalId": native_readback.get("atlasLocalIdAfter"),
            "materialGuid": native_readback.get("materialGuidAfter"),
            "materialLocalId": native_readback.get("materialLocalIdAfter"),
            "glyphCount": native_readback.get("glyphCountAfter"),
            "characterCount": native_readback.get("characterCountAfter"),
        },
        "primaryFontAssets": stage_manifest.get("primaryFontAssets"),
        "nativeFontReadbackPath": native_readback_relative,
        "nativeFontCoverage": {"status": "saved_static_font_and_consumer_lookup_pass",
                               "requiredUnicode": native_readback.get("requiredUnicode"),
                               "consumerTextCount": native_readback.get("consumerTextCount"),
                               "playerVisualStatus": "not_run"},
        "files": sorted(final_inventory, key=lambda row: row["path"]),
        "coverageBoundary": "Native Editor save/reopen and TMP font-chain lookup passed for the pinned corpus. Player rendering and visual equivalence remain separate.",
    }
    manifest_raw = _json_bytes(derived)
    manifest_sha = _write(project_out / "manifest.json", manifest_raw)
    report = {"schema": "monkey-native-font-finalization/1", "status": "frozen",
              "outputRoot": str(out_root.resolve()), "projectRoot": str(project_out.resolve()),
              "manifestSha256": manifest_sha, "fileCount": len(final_inventory),
              "nativeReadbackSha256": expected_native_readback_sha256,
              "fileDisposition": sorted(dispositions, key=lambda row: row["path"]),
              "nativeImport": "pass", "saveReopenReadback": "pass", "playerGlyphCheck": "not_run"}
    _write(out_root / "finalization-report.json", _json_bytes(report))
    return report
