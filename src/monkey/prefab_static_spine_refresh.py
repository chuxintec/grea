"""Refresh package-owned static Spine helpers in a fresh frozen plan stage.

This module never reruns source conversion or texture decoding. It validates the
owning plan inventory, clones it into a new output, upgrades native atlas page
names using already decoded PNGs, and replaces only an allowlisted C# factory
payload when the package source hash has changed.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from . import __version__, io
from .output_limits import check_inventory, copy_verified, digest_file
from .prefab_static_spine_rendering import _DERIVED_HELPER, _RENDER_HELPERS


SCHEMA = "monkey-static-spine-helper-refresh/1"
_SHA = re.compile(r"^[0-9a-f]{64}$")
_RENDERING_CONTRACT = "monkey-static-spine-rendering/1"
_CONTINUATION_CONTRACT = "monkey-prefab-static-spine-continuation/1"
_MAX_REQUEST_BYTES = 1024 * 1024
_MAX_PLAN_BYTES = 128 * 1024 * 1024
_MAX_HELPER_BYTES = 16 * 1024 * 1024

# Refresh only the explicit shared factory/rendering adapters. Other sources are
# checked against the frozen payload and rejected if they drift unexpectedly.
_REFRESH_TARGETS = {
    "Assets/Game/Editor/Conversion/Spine/UnitySpineNativeFactory.cs": "targets/spine/UnitySpineNativeFactory.cs",
    "Assets/Game/Editor/Conversion/UnityStaticSpineRendering.cs": "targets/UnityStaticSpineRendering.cs",
    "Assets/Game/Editor/Conversion/UnityStaticSpineRenderingDerived.cs": "targets/UnityStaticSpineRenderingDerived.cs",
}
_CONTINUATION_SUPPORT_FILES = {
    "targets/NativeStaticSpineReference.cs": (
        "Assets/Game/Presentation/Common/Layout/NativeStaticSpineReference.cs", "nonrendering-static-component-carrier"),
    "targets/NativeStaticSpineData.cs": (
        "Assets/Game/Presentation/Common/Layout/NativeStaticSpineData.cs", "nonrendering-source-data-asset"),
    "targets/UnityStaticSpineContinuation.cs": (
        "Assets/Game/Editor/Conversion/UnityStaticSpineContinuation.cs", "editor-create-resolve-saved-readback-helper"),
}
_RENDER_EXTERNAL_DEPENDENCIES = {
    "Assets/Game/Scripts/Presentation/StaticMasks/NativeStaticMaskIdentity.cs": "targets/NativeStaticMaskIdentity.cs",
}


class StaticSpineRefreshError(ValueError):
    """A frozen static Spine stage is unsafe or inconsistent to refresh."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _input(request: dict, name: str) -> tuple[Path, bytes]:
    spec = request.get(name)
    if not isinstance(spec, dict) or set(spec) != {"path", "sha256"}:
        raise StaticSpineRefreshError(f"{name} must contain exactly path and sha256")
    if not isinstance(spec["path"], str) or not Path(spec["path"]).is_absolute():
        raise StaticSpineRefreshError(f"{name}.path must be absolute")
    if not isinstance(spec["sha256"], str) or not _SHA.fullmatch(spec["sha256"]):
        raise StaticSpineRefreshError(f"{name}.sha256 must be a lowercase SHA-256")
    path = io.safe(spec["path"])
    raw = io.read(path, max_bytes=_MAX_PLAN_BYTES)
    if io.sha(raw) != spec["sha256"]:
        raise StaticSpineRefreshError(f"{name} differs from its SHA-256 pin")
    return path, raw


def _load_json(raw: bytes, label: str, *, max_nodes: int = 8_000_000) -> dict:
    try:
        value = io.load(raw, max_nodes=max_nodes)
    except Exception as error:
        raise StaticSpineRefreshError(f"invalid strict JSON in {label}: {error}") from error
    if not isinstance(value, dict):
        raise StaticSpineRefreshError(f"{label} must be a JSON object")
    return value


def _inventory_rows(manifest: dict, plan_root: Path) -> dict[str, dict]:
    rows = manifest.get("files")
    if not isinstance(rows, list):
        raise StaticSpineRefreshError("owning plan manifest has no files list")
    try:
        check_inventory(rows, manifest, str(plan_root))
    except Exception as error:
        raise StaticSpineRefreshError(f"owning plan inventory violates output limits: {error}") from error
    result = {}
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get("path"), str) or
                not isinstance(row.get("sha256"), str) or not _SHA.fullmatch(row["sha256"]) or
                type(row.get("bytes")) is not int):
            raise StaticSpineRefreshError("owning plan inventory row is malformed")
        relative = row["path"]
        if Path(relative).is_absolute() or ".." in Path(relative).parts or relative in result:
            raise StaticSpineRefreshError(f"unsafe or duplicate inventory path: {relative}")
        path = io.inside(plan_root, relative)
        if not path.is_file() or digest_file(path) != row["sha256"] or path.stat().st_size != row["bytes"]:
            raise StaticSpineRefreshError(f"owned plan file differs from inventory: {relative}")
        result[relative] = row
    if "plan.json" not in result:
        raise StaticSpineRefreshError("owning inventory omits plan.json")
    return result


def _validate_plan(plan: dict, manifest: dict, inventory: dict[str, dict], plan_root: Path,
                   plan_path: Path, manifest_path: Path, plan_raw: bytes) -> tuple[dict, Path]:
    if plan_path != plan_root / "plan.json" or manifest_path != plan_root / "manifest.json":
        raise StaticSpineRefreshError("request must pin the owning plan.json and sibling manifest.json")
    if io.sha(plan_raw) != inventory["plan.json"]["sha256"] or len(plan_raw) != inventory["plan.json"]["bytes"]:
        raise StaticSpineRefreshError("plan.json pin differs from its owning inventory")
    if manifest.get("staticSpineRendering") != plan.get("staticSpineRendering"):
        raise StaticSpineRefreshError("owning manifest and plan rendering fragments differ")
    if manifest.get("sourceManifestSha256") != plan.get("sourceManifestSha256"):
        raise StaticSpineRefreshError("plan source-manifest binding differs from owning manifest")
    continuation = plan.get("staticSpineContinuation")
    fragment = plan.get("staticSpineRendering")
    if not isinstance(continuation, dict) or continuation.get("contract") != _CONTINUATION_CONTRACT:
        raise StaticSpineRefreshError("plan lacks the supported static Spine continuation")
    if manifest.get("staticSpineContinuation") != continuation:
        raise StaticSpineRefreshError("owning manifest and plan source continuation fragments differ")
    if (not isinstance(fragment, dict) or fragment.get("contract") != _RENDERING_CONTRACT or
            type(fragment.get("schemaVersion")) is not int or fragment.get("schemaVersion") != 1):
        raise StaticSpineRefreshError("plan lacks the supported static Spine rendering fragment")
    if fragment.get("sourceManifestSha256") != plan.get("sourceManifestSha256") or continuation.get("sourceManifestSha256") != plan.get("sourceManifestSha256"):
        raise StaticSpineRefreshError("rendering, continuation, and plan source-manifest pins differ")
    if fragment.get("sourceContinuationSha256") != io.sha(_canonical(continuation)):
        raise StaticSpineRefreshError("rendering fragment no longer binds the exact continuation")
    module_stage = fragment.get("moduleStage")
    if not isinstance(module_stage, str) or Path(module_stage).is_absolute() or ".." in Path(module_stage).parts:
        raise StaticSpineRefreshError("rendering moduleStage is missing or unsafe")
    module_root = io.inside(plan_root, module_stage)
    if not module_root.is_dir():
        raise StaticSpineRefreshError("rendering moduleStage directory is missing")
    module_json = io.inside(module_root, "spine-static-rendering.json")
    if not module_json.is_file() or io.read(module_json, max_bytes=_MAX_PLAN_BYTES) != io.encoded(fragment):
        raise StaticSpineRefreshError("module rendering JSON differs from the owning plan fragment")
    return fragment, module_root


def _validate_continuation_files(plan: dict, inventory: dict[str, dict], plan_root: Path) -> None:
    continuation = plan["staticSpineContinuation"]
    module_stage = continuation.get("moduleStage")
    if not isinstance(module_stage, str) or Path(module_stage).is_absolute() or ".." in Path(module_stage).parts:
        raise StaticSpineRefreshError("continuation moduleStage is missing or unsafe")
    module_root = io.inside(plan_root, module_stage)
    if not module_root.is_dir():
        raise StaticSpineRefreshError("continuation moduleStage directory is missing")
    copies = continuation.get("payloadCopies")
    if not isinstance(copies, list):
        raise StaticSpineRefreshError("continuation payloadCopies is missing")
    seen_sources = set()
    for row in copies:
        if not isinstance(row, dict):
            raise StaticSpineRefreshError("continuation payload copy row is malformed")
        source = row.get("source")
        if (not isinstance(source, str) or Path(source).is_absolute() or ".." in Path(source).parts or
                source in seen_sources or not _SHA.fullmatch(str(row.get("sha256", ""))) or type(row.get("bytes")) is not int):
            raise StaticSpineRefreshError("continuation payload copy identity is unsafe, duplicated, or incomplete")
        seen_sources.add(source)
        inventory_path = f"{module_stage}/{source}"
        owned = inventory.get(inventory_path)
        if not owned or owned["sha256"] != row["sha256"] or owned["bytes"] != row["bytes"]:
            raise StaticSpineRefreshError(f"continuation payload copy is outside or differs from owning inventory: {inventory_path}")
        path = io.inside(module_root, source)
        if digest_file(path) != row["sha256"] or path.stat().st_size != row["bytes"]:
            raise StaticSpineRefreshError(f"continuation payload copy bytes differ from their pin: {source}")

    support_files = continuation.get("supportFiles")
    if not isinstance(support_files, list):
        raise StaticSpineRefreshError("continuation supportFiles is missing")
    package_root = Path(__file__).resolve().parent
    if len({row.get("source") for row in support_files if isinstance(row, dict)}) != len(support_files):
        raise StaticSpineRefreshError("continuation support-file sources are duplicated")
    if {row.get("source") for row in support_files if isinstance(row, dict)} != set(_CONTINUATION_SUPPORT_FILES):
        raise StaticSpineRefreshError("continuation support-file closure differs from the package-owned ABI")
    for row in support_files:
        if not isinstance(row, dict):
            raise StaticSpineRefreshError("continuation support-file row is malformed")
        source, target = row.get("source"), row.get("target")
        expected_target, expected_role = _CONTINUATION_SUPPORT_FILES.get(source, (None, None))
        if (not isinstance(source, str) or Path(source).is_absolute() or ".." in Path(source).parts or
                not isinstance(target, str) or not target.startswith("Assets/") or ".." in Path(target).parts or
                not _SHA.fullmatch(str(row.get("sha256", ""))) or type(row.get("bytes")) is not int):
            raise StaticSpineRefreshError("continuation support-file identity is unsafe or incomplete")
        if target != expected_target or row.get("role") != expected_role:
            raise StaticSpineRefreshError(f"continuation support-file target/role differs from package ABI: {source}")
        source_path = io.safe(package_root / source)
        raw = io.read(source_path, max_bytes=_MAX_HELPER_BYTES)
        if io.sha(raw) != row["sha256"] or len(raw) != row["bytes"]:
            raise StaticSpineRefreshError(f"continuation support-file source differs from its pin: {source}")


def _helper_sources() -> dict[str, str]:
    result = {}
    for relative, target in (*_RENDER_HELPERS, _DERIVED_HELPER):
        if target in result:
            raise StaticSpineRefreshError(f"package helper target is duplicated: {target}")
        result[target] = relative
    return result


def _package_helper_bytes(target: str) -> tuple[Path, bytes]:
    relative = _helper_sources().get(target)
    if relative is None:
        raise StaticSpineRefreshError(f"render helper target is outside the package allowlist: {target}")
    path = io.safe(Path(__file__).resolve().parent / relative)
    raw = io.read(path, max_bytes=_MAX_HELPER_BYTES)
    return path, raw


def _validate_payloads(fragment: dict, module_root: Path, inventory: dict[str, dict], *, refresh_external_dependencies: bool = False) -> tuple[dict[str, dict], dict[str, dict]]:
    rows = fragment.get("payloads")
    if not isinstance(rows, list) or not rows:
        raise StaticSpineRefreshError("rendering fragment payload list is missing")
    targets: dict[str, dict] = {}
    helper_rows: dict[str, dict] = {}
    helper_sources = _helper_sources()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("source"), str) or not isinstance(row.get("target"), str):
            raise StaticSpineRefreshError("rendering payload row is malformed")
        target, source = row["target"], row["source"]
        if target in targets or not target.startswith("Assets/") or ".." in Path(target).parts:
            raise StaticSpineRefreshError(f"render payload target is duplicated or unsafe: {target}")
        targets[target] = row
        if Path(source).is_absolute() or ".." in Path(source).parts:
            raise StaticSpineRefreshError(f"render payload source is unsafe: {source}")
        path = io.inside(module_root, source)
        if not path.is_file():
            raise StaticSpineRefreshError(f"render payload source is missing: {source}")
        digest = digest_file(path)
        size = path.stat().st_size
        if digest != row.get("sha256") or size != row.get("bytes"):
            raise StaticSpineRefreshError(f"render payload bytes differ from pinned row: {target}")
        inventory_path = f"{fragment['moduleStage']}/{source}"
        owned = inventory.get(inventory_path)
        if not owned or owned["sha256"] != digest or owned["bytes"] != size:
            raise StaticSpineRefreshError(f"render payload differs from owner inventory: {target}")
        role = row.get("role", "")
        if role in ("pinned-spine-native-helper", "pinned-spine-rendering-derived-helper"):
            if target not in helper_sources:
                raise StaticSpineRefreshError(f"render helper target is outside the package allowlist: {target}")
            if target in helper_rows:
                raise StaticSpineRefreshError(f"render helper target occurs more than once: {target}")
            helper_rows[target] = row
    if set(helper_rows) != set(helper_sources):
        raise StaticSpineRefreshError("render helper closure differs from the supported package-owned helper set")
    external = fragment.get("externalDependencies", [])
    if not isinstance(external, list) or any(not isinstance(row, dict) for row in external):
        raise StaticSpineRefreshError("rendering externalDependencies must be a list")
    targets_external = [row.get("target") for row in external]
    if len(set(targets_external)) != len(targets_external) or set(targets_external) != set(_RENDER_EXTERNAL_DEPENDENCIES):
        raise StaticSpineRefreshError("rendering external dependency closure differs from the supported package ABI")
    package_root = Path(__file__).resolve().parent
    for dependency in external:
        target = dependency["target"]
        if dependency.get("copy") is not False or dependency.get("providedBy") != "standard-unity-static-mask-export":
            raise StaticSpineRefreshError(f"rendering external dependency ownership changed: {target}")
        source = io.safe(package_root / _RENDER_EXTERNAL_DEPENDENCIES[target])
        raw = io.read(source, max_bytes=_MAX_HELPER_BYTES)
        if not isinstance(dependency.get("sha256"), str) or not _SHA.fullmatch(dependency["sha256"]):
            raise StaticSpineRefreshError(f"rendering external dependency pin is malformed: {target}")
        if io.sha(raw) != dependency.get("sha256") and not refresh_external_dependencies:
            raise StaticSpineRefreshError(f"rendering external dependency differs from package source: {target}")
    return targets, helper_rows


def _refresh_helper_payloads(fragment: dict, module_root: Path, helper_rows: dict[str, dict]) -> list[dict]:
    replacements = []
    for target, row in sorted(helper_rows.items()):
        source_path, current = _package_helper_bytes(target)
        current_sha = io.sha(current)
        prior_sha = row["sha256"]
        if current_sha == prior_sha:
            replacements.append({"target": target, "packageSource": str(source_path),
                                 "previousSha256": prior_sha, "currentSha256": current_sha,
                                 "previousBytes": row["bytes"], "currentBytes": len(current),
                                 "status": "already_current", "replaced": False})
            continue
        if target not in _REFRESH_TARGETS:
            raise StaticSpineRefreshError(f"unapproved package helper source changed: {target}")
        relative = f"spine-static-rendering-payloads/{current_sha}/{Path(target).name}"
        destination = io.inside(module_root, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            existing = io.read(destination, max_bytes=_MAX_HELPER_BYTES)
            if existing != current:
                raise StaticSpineRefreshError(f"refreshed helper payload path collision: {target}")
        else:
            destination.write_bytes(current)
        replacement = dict(row, source=relative, sha256=current_sha, bytes=len(current))
        for index, payload in enumerate(fragment["payloads"]):
            if payload is row or (payload.get("target") == target and payload.get("role") == row.get("role")):
                fragment["payloads"][index] = replacement.copy()
                break
        replacements.append({"target": target, "packageSource": str(source_path),
                             "previousSource": row["source"], "currentSource": relative,
                             "previousSha256": prior_sha, "currentSha256": current_sha,
                             "previousBytes": row["bytes"], "currentBytes": len(current),
                             "status": "replaced", "replaced": True})
    return replacements


def _upgrade_atlas_mapping(plan: dict, stage_root: Path) -> list[dict]:
    from .prefab_static_spine_rendering import upgrade_atlas_mapping
    return upgrade_atlas_mapping(plan, stage_root)


def prepare(request_path: str | Path, expected_request_sha256: str, output: str | Path) -> dict:
    """Create a fresh plan stage with pinned atlas/helper readback fixes."""
    if not isinstance(expected_request_sha256, str) or not _SHA.fullmatch(expected_request_sha256):
        raise StaticSpineRefreshError("expected request SHA-256 is invalid")
    request_path = io.safe(request_path)
    request_raw = io.read(request_path, max_bytes=_MAX_REQUEST_BYTES)
    if io.sha(request_raw) != expected_request_sha256:
        raise StaticSpineRefreshError("request bytes differ from the expected SHA-256")
    request = _load_json(request_raw, "request", max_nodes=100_000)
    allowed = {"schema", "schemaVersion", "plan", "planManifest"}
    if (set(request) not in (allowed, allowed | {"refreshExternalDependencies"}) or request.get("schema") != SCHEMA or
            type(request.get("schemaVersion")) is not int or request["schemaVersion"] != 1):
        raise StaticSpineRefreshError("request schema or fields are unsupported")
    refresh_external = request.get("refreshExternalDependencies", False)
    if type(refresh_external) is not bool:
        raise StaticSpineRefreshError("refreshExternalDependencies must be a boolean")

    plan_path, plan_raw = _input(request, "plan")
    manifest_path, manifest_raw = _input(request, "planManifest")
    if manifest_path != plan_path.parent / "manifest.json":
        raise StaticSpineRefreshError("planManifest must be the exact sibling manifest.json")
    plan_root = plan_path.parent
    plan = _load_json(plan_raw, "plan")
    manifest = _load_json(manifest_raw, "plan manifest")
    inventory = _inventory_rows(manifest, plan_root)
    fragment, module_root = _validate_plan(plan, manifest, inventory, plan_root,
                                           plan_path, manifest_path, plan_raw)
    _validate_continuation_files(plan, inventory, plan_root)
    _, helper_rows = _validate_payloads(fragment, module_root, inventory, refresh_external_dependencies=refresh_external)

    out = io.new_output(output, [request_path, plan_root, manifest_path])
    stage = out / "plan"
    stage.mkdir()
    for relative, row in inventory.items():
        if relative == "plan.json":
            continue
        copy_verified(io.inside(plan_root, relative), io.inside(stage, relative),
                      row["sha256"], row["bytes"])

    refreshed = copy.deepcopy(plan)
    refreshed_fragment = refreshed["staticSpineRendering"]
    from .spine_canvas_context_readback import CONTRACT as canvas_context_contract
    refreshed_fragment["sourceCanvasContextEvidenceContract"] = canvas_context_contract
    from .spine_owner_lifecycle_readback import CONTRACT as owner_lifecycle_contract
    refreshed_fragment["ownerContextLifecycleEvidenceContract"] = owner_lifecycle_contract
    if isinstance(refreshed.get("staticTextContinuation"), dict):
        refreshed["staticTextSlotCaptureLifecycleContract"] = "monkey-static-sort-text-capture-lifecycle/1"
        from .prefab_static_text_continuation import SAMPLING_CONTRACT
        refreshed["staticTextContinuation"]["nativeSamplingContract"] = SAMPLING_CONTRACT
        refreshed["staticTextContinuationJson"] = json.dumps(
            refreshed["staticTextContinuation"], ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    refreshed_module = io.inside(stage, refreshed_fragment["moduleStage"])
    atlas_evidence = _upgrade_atlas_mapping(refreshed, stage)
    helper_replacements = _refresh_helper_payloads(refreshed_fragment, refreshed_module, helper_rows)
    external_replacements = []
    if refresh_external:
        for dependency in refreshed_fragment.get("externalDependencies", []):
            source = Path(__file__).parent / _RENDER_EXTERNAL_DEPENDENCIES[dependency["target"]]
            current = io.sha(io.read(source, max_bytes=_MAX_HELPER_BYTES))
            if current != dependency["sha256"]:
                external_replacements.append(dict(target=dependency["target"], previousSha256=dependency["sha256"],
                                                  currentSha256=current, providedBy=dependency["providedBy"]))
                dependency["sha256"] = current
    generator_refresh = None
    if isinstance(refreshed_fragment.get("unitMapping"), dict):
        from .prefab_static_continuation import _refresh_existing_spine_generator
        generator_refresh = _refresh_existing_spine_generator(refreshed, stage)
    refresh_evidence = {
        "schema": SCHEMA,
        "status": "prepared_fresh_static_spine_stage",
        "parentPlanPath": str(plan_path),
        "parentPlanSha256": io.sha(plan_raw),
        "parentPlanManifestPath": str(manifest_path),
        "parentPlanManifestSha256": io.sha(manifest_raw),
        "parentToolVersion": plan.get("toolVersion"),
        "toolVersion": __version__,
        "requestSha256": expected_request_sha256,
        "helperReplacements": helper_replacements,
        "externalDependencyReplacements": external_replacements,
        "generatorUnitMappingRefresh": generator_refresh,
        "atlasMapping": atlas_evidence,
        "sourceCodeExecuted": False,
        "textureDecodeInvoked": False,
        "nativeImport": "not_run",
        "visual": "not_run",
    }
    refreshed["staticSpineHelperRefresh"] = refresh_evidence
    refreshed["toolVersion"] = __version__
    io.write_json(refreshed_module / "spine-static-rendering.json", refreshed_fragment)
    io.write_json(stage / "plan.json", refreshed)

    owner_manifest = dict(manifest)
    owner_manifest["staticSpineRendering"] = refreshed_fragment
    for key in ("staticTextContinuation", "staticTextContinuationJson", "staticTextSlotCaptureLifecycleContract"):
        if key in refreshed:
            owner_manifest[key] = refreshed[key]
    if "staticSpineRenderingTargetUnits" in refreshed:
        owner_manifest["staticSpineRenderingTargetUnits"] = refreshed["staticSpineRenderingTargetUnits"]
    owner_manifest["staticSpineHelperRefresh"] = refresh_evidence
    owner_manifest["toolVersion"] = __version__
    if (io.sha(io.read(request_path, max_bytes=_MAX_REQUEST_BYTES)) != expected_request_sha256 or
            io.sha(io.read(plan_path, max_bytes=_MAX_PLAN_BYTES)) != io.sha(plan_raw) or
            io.sha(io.read(manifest_path, max_bytes=_MAX_PLAN_BYTES)) != io.sha(manifest_raw)):
        raise StaticSpineRefreshError("a pinned request/plan/manifest changed during refresh")
    io.finish(stage, owner_manifest)
    refreshed_manifest = _load_json(io.read(stage / "manifest.json", max_bytes=_MAX_PLAN_BYTES), "refreshed plan manifest")
    refreshed_inventory = _inventory_rows(refreshed_manifest, stage)
    if refreshed_inventory["plan.json"]["sha256"] != io.sha(io.read(stage / "plan.json", max_bytes=_MAX_PLAN_BYTES)):
        raise StaticSpineRefreshError("regenerated plan inventory does not bind its plan.json")
    report = {
        "schema": SCHEMA,
        "schemaVersion": 1,
        "preparationStatus": "prepared",
        "toolVersion": __version__,
        "requestSha256": expected_request_sha256,
        "parentPlanSha256": io.sha(plan_raw),
        "parentPlanManifestSha256": io.sha(manifest_raw),
        "planPath": str(stage / "plan.json"),
        "planManifestPath": str(stage / "manifest.json"),
        "helperReplacements": helper_replacements,
        "externalDependencyReplacements": external_replacements,
        "generatorUnitMappingRefresh": generator_refresh,
        "atlasMapping": atlas_evidence,
        "sourceCodeExecuted": False,
        "textureDecodeInvoked": False,
        "native": "not_run",
        "nativeImport": "not_run",
        "visual": "not_run",
        "diagnostics": [],
    }
    io.finish(out, report)
    return report
