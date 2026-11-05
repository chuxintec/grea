"""Offline export/source-set compile matrix for the optional Spine adapter.

The first two cases call the real exporter with create-only synthetic plans.
The third reuses the frozen actual-export19 source tree, replaces only the
nine listed current package templates under test, and keeps the plan-owned Spine 3.8
factory/runtime closure byte-for-byte. No Editor or product stage is launched.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess

import pytest

from monkey.io import encoded, sha, write_json
from monkey.targets import unity


REPO = Path(__file__).resolve().parents[1]
UNITY_RESOURCES = Path(os.environ.get(
    "MONKEY_GREA65_UNITY_RESOURCES",
    "/Applications/Unity/Hub/Editor/6000.6.2f1/Unity.app/Contents/Resources",
)).resolve()
UNITY_CSC = UNITY_RESOURCES / "Scripting/DotNetSdk/sdk/8.0.318/Roslyn/bincore/csc.dll"
UNITY_REFERENCE_RESPONSE_ENV = os.environ.get("MONKEY_GREA65_UNITY_REFERENCE_RESPONSE")
_STANDARD_REFERENCE_ROOT = os.environ.get("MONKEY_GREA65_STANDARD_REFERENCE_ROOT")
STANDARD_REFERENCE_ROOT = Path(_STANDARD_REFERENCE_ROOT).resolve() if _STANDARD_REFERENCE_ROOT else None
ACTUAL_EXPORT19 = Path(os.environ.get("MONKEY_GREA65_ACTUAL_EXPORT19", "")).resolve()
ACTUAL_PLAN19 = Path(os.environ.get("MONKEY_GREA65_ACTUAL_PLAN19", "")).resolve()
ACTUAL_NATIVE19 = Path(os.environ.get("MONKEY_GREA65_ACTUAL_NATIVE19", "")).resolve()
EVIDENCE_DIR_ENV = os.environ.get("MONKEY_GREA65_EVIDENCE_DIR")


def _write_plan_stage(root: Path, *, scenario: str) -> Path:
    """Write a tiny complete plan/manifest pair consumed by targets.unity.export."""
    stage = root / "plan-stage"
    stage.mkdir(parents=True)
    component = {
        "sourceId": "fixture:root/components/sprite0",
        "node": "fixture:root",
        "type": "cc.Sprite",
        "convertible": True,
    }
    plan = {
        "schemaVersion": 1,
        "targetProfile": unity.PROFILE,
        "namespace": "OptionalSpine" + scenario,
        "copies": [],
        "nodes": [{"sourceId": "fixture:root", "parent": None, "name": "Root"}],
        "components": [component],
        "textures": [],
        "assets": [],
        "bitmapFonts": [],
        "animations": [],
        "diagnostics": [],
        "galleryOnly": False,
        "sourceRoots": {},
        "sourceLocations": {},
        "designSize": [750, 1334],
        "pixelsPerUnit": 100,
        "staticSpineRendering": None,
    }
    if scenario == "OrdinarySortNoSpine":
        plan["staticSortQueue"] = [{
            "sourceComponentId": component["sourceId"],
            "sourceType": "cc.Sprite",
            "node": component["node"],
        }]
    plan_path = stage / "plan.json"
    raw = encoded(plan)
    plan_path.write_bytes(raw)
    write_json(stage / "manifest.json", {
        "files": [{"path": "plan.json", "sha256": sha(raw), "bytes": len(raw)}],
    })
    return plan_path


def _export_fixture(tmp: Path, scenario: str) -> tuple[Path, dict]:
    plan_path = _write_plan_stage(tmp, scenario=scenario)
    output = tmp / "exported"
    report = unity.export(plan_path, output)
    assert report["status"] in ("candidate", "partial")
    return output, report


def _manifest_sources(project: Path) -> list[Path]:
    manifest = json.loads((project / "manifest.json").read_text(encoding="utf-8"))
    source_rows = []
    for row in manifest.get("files", []):
        if not row.get("path", "").startswith("Assets/") or not row["path"].endswith(".cs"):
            continue
        source = project / row["path"]
        assert source.is_file(), "manifest-owned C# source missing: " + row["path"]
        raw = source.read_bytes()
        assert len(raw) == row["bytes"] and sha(raw) == row["sha256"], "manifest source pin changed: " + row["path"]
        source_rows.append(source)
    observed = sorted(path.relative_to(project).as_posix() for path in (project / "Assets").rglob("*.cs"))
    assert observed == sorted(path.relative_to(project).as_posix() for path in source_rows), \
        "compiler source list must be the complete exported Assets/**/*.cs manifest set"
    return sorted(source_rows)


def _standard_references(*, reference_root: Path | None = None, spine_dlls: tuple[Path, ...] = ()) -> list[Path]:
    """Build the pinned Unity 6000.6.2f1 + uGUI/TMP reference set.

    The existing Unity compiler response contributes only editor-install refs;
    project ScriptAssemblies are explicitly selected from the named reference
    root so case 1/2 cannot inherit a Spine DLL from an unrelated project.
    """
    if not UNITY_CSC.is_file():
        pytest.skip("fixed Unity 6000.6.2f1 Roslyn response/compiler is unavailable")
    reference_root = reference_root or STANDARD_REFERENCE_ROOT
    if reference_root is None or not reference_root.is_dir():
        pytest.skip("set MONKEY_GREA65_STANDARD_REFERENCE_ROOT to the no-Spine Unity project's Library/ScriptAssemblies")
    response = (Path(UNITY_REFERENCE_RESPONSE_ENV).resolve() if UNITY_REFERENCE_RESPONSE_ENV else None)
    if response is None:
        candidates = sorted((reference_root.parent / "Bee/artifacts").glob("*/Assembly-CSharp-Editor.rsp"))
        response = candidates[0] if candidates else None
    if response is None or not response.is_file():
        pytest.skip("fixed Unity project Assembly-CSharp-Editor.rsp is unavailable")
    editor_root = UNITY_RESOURCES.resolve()
    refs: dict[str, Path] = {}
    for line in response.read_text(encoding="utf-8").splitlines():
        try:
            args = shlex.split(line)
        except ValueError:
            continue
        if not args or not args[0].startswith("-r:"):
            continue
        candidate = Path(args[0][3:]).resolve()
        # Unity Bee's reference response lists project ScriptAssemblies too;
        # those are replaced below from the pinned reference project. Keep
        # only this exact Editor's managed and BCL reference closure here.
        if candidate.is_file() and candidate.is_relative_to(editor_root):
            refs[str(candidate)] = candidate
    required_names = ("UnityEngine.UI.dll", "UnityEditor.UI.dll", "Unity.TextMeshPro.dll", "Unity.TextMeshPro.Editor.dll")
    for name in required_names:
        candidate = reference_root / name
        if not candidate.is_file():
            pytest.skip("standard Unity project reference missing: " + str(candidate))
        refs[str(candidate.resolve())] = candidate.resolve()
    for candidate in spine_dlls:
        if not candidate.is_file():
            raise AssertionError("actual Spine SDK reference missing: " + str(candidate))
        refs[str(candidate.resolve())] = candidate.resolve()
    return sorted(refs.values(), key=lambda path: str(path))


def _compile(project: Path, *, references: list[Path], case: str, evidence_dir: Path) -> dict:
    dotnet = shutil.which("dotnet")
    if not dotnet:
        pytest.skip("dotnet SDK runtime required to invoke Unity Roslyn offline")
    sources = _manifest_sources(project)
    response = evidence_dir / (case + ".rsp")
    assembly = evidence_dir / (case + ".dll")
    lines = ["-nologo", "-nostdlib+", "-target:library", "-langversion:latest", "-deterministic+",
             "-out:" + str(assembly)]
    lines.extend("-r:" + str(path) for path in references)
    lines.extend(str(path) for path in sources)
    response.write_text("\n".join('"' + line.replace('"', '\\"') + '"' for line in lines) + "\n", encoding="utf-8")
    completed = subprocess.run([dotnet, str(UNITY_CSC), "@" + str(response)], capture_output=True,
                               text=True, timeout=180, check=False)
    result = {
        "case": case,
        "exitCode": completed.returncode,
        "sources": [{"path": path.relative_to(project).as_posix(), "sha256": sha(path.read_bytes())} for path in sources],
        "references": [{"path": str(path), "sha256": sha(path.read_bytes())} for path in references],
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    (evidence_dir / (case + ".json")).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


@pytest.mark.parametrize("scenario", ["OneSpriteNoSpine", "OrdinarySortNoSpine", "StaticCodeBindingsNoSpine"])
def test_real_exported_no_spine_source_set_compiles_without_spine_sdk(tmp_path, scenario):
    """Both no-Spine export source sets compile with only standard Unity refs."""
    resolved = tmp_path.resolve()
    # Keep each scenario in an explicit fresh parent directory.
    case_root = resolved / scenario
    case_root.mkdir()
    project, report = _export_fixture(case_root, scenario)
    if scenario == "StaticCodeBindingsNoSpine":
        # The optional binding stage installs this helper after base export.
        # Compile its shared partial-class API against the current exporter;
        # this is an offline source-set check, not a stage or Editor receipt.
        relative="Assets/Game/Editor/Conversion/UnityStaticCodeBindings.cs"
        helper=REPO/"src/monkey/targets/UnityStaticCodeBindings.cs"
        raw=helper.read_bytes();(project/relative).write_bytes(raw)
        manifest=json.loads((project/"manifest.json").read_bytes())
        manifest["files"].append(dict(path=relative,sha256=sha(raw),bytes=len(raw)))
        write_json(project/"manifest.json",manifest)
    sources = _manifest_sources(project)
    csharp_paths = [path.relative_to(project).as_posix() for path in sources]
    assert "Assets/Game/Editor/Conversion/UnityStaticSortSpineBinding.cs" not in csharp_paths
    evidence_dir = Path(EVIDENCE_DIR_ENV).resolve() / scenario if EVIDENCE_DIR_ENV else case_root / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "export-source-set.json").write_text(json.dumps({
        "contract": "grea65-optional-spine-export-source-set/1",
        "scenario": scenario,
        "exportReportStatus": report["status"],
        "sourceFiles": [{"path": path.relative_to(project).as_posix(), "sha256": sha(path.read_bytes()),
                         "bytes": path.stat().st_size} for path in sources],
        "optionalSpineBindingExported": False,
        "optionalStaticCodeHelperAddedForOfflineCompile":scenario == "StaticCodeBindingsNoSpine",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (evidence_dir / "export-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    references = _standard_references()
    assert not any("spine" in path.name.lower() for path in references)
    result = _compile(project, references=references, case=scenario, evidence_dir=evidence_dir)
    assert result["exitCode"] == 0, result["stdout"] + result["stderr"]


def _copy_current_spine_templates(source_root: Path, temp_root: Path) -> list[dict]:
    """Substitute current package-owned Proxy/Spine binding templates offline."""
    mapping = {
        "Assets/Game/Editor/Conversion/UnitySourceComponentCoverage.cs": REPO / "src/monkey/targets/UnitySourceComponentCoverage.cs",
        "Assets/Game/Editor/Conversion/MonkeyImporter.cs": REPO / "src/monkey/targets/UnityImporter.cs",
        "Assets/Game/Editor/Conversion/UnityStaticFieldIntegration.cs": REPO / "src/monkey/targets/UnityStaticFieldIntegration.cs",
        "Assets/Game/Editor/Conversion/UnityStaticMaskIntegration.cs": REPO / "src/monkey/targets/UnityStaticMaskIntegration.cs",
        "Assets/Game/Editor/Conversion/UnityStaticMaskSort.cs": REPO / "src/monkey/targets/UnityStaticMaskSort.cs",
        "Assets/Game/Editor/Conversion/UnityStaticProgressIntegration.cs": REPO / "src/monkey/targets/UnityStaticProgressIntegration.cs",
        "Assets/Game/Scripts/Presentation/StaticMasks/NativeStaticMaskIdentity.cs": REPO / "src/monkey/targets/NativeStaticMaskIdentity.cs",
        "Assets/Game/Editor/Conversion/UnityStaticSortQueueProxy.cs": REPO / "src/monkey/targets/UnityStaticSortQueueProxy.cs",
        "Assets/Game/Editor/Conversion/UnityStaticSortSpineBinding.cs": REPO / "src/monkey/targets/UnityStaticSortSpineBinding.cs",
        "Assets/Game/Editor/Conversion/UnityStaticSortTextSource.cs": REPO / "src/monkey/targets/UnityStaticSortTextSource.cs",
        "Assets/Game/Scripts/Presentation/StaticSort/NativeStaticSortTextSource.cs": REPO / "src/monkey/targets/NativeStaticSortTextSource.cs",
        "Assets/Game/Scripts/Presentation/StaticSort/NativeStaticSortTextSlotEnumerationIdentity.cs": REPO / "src/monkey/targets/NativeStaticSortTextSlotEnumerationIdentity.cs",
    }
    rows = []
    for relative, template in mapping.items():
        source = source_root / relative
        if not source.is_file() or not template.is_file():
            raise AssertionError("real Spine export/template pair unavailable: " + relative)
        original = source.read_bytes()
        target = temp_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(template.read_bytes())
        rows.append({"path": relative, "exportedSha256": sha(original), "currentTemplateSha256": sha(template.read_bytes()),
                     "templateSubstitution": True})
    return rows


def test_real_spine_export_requires_and_compiles_with_pinned_runtime_factory_closure(tmp_path):
    """Actual-export19 source set fails closed without, then compiles with its Spine 3.8 closure."""
    if not (ACTUAL_EXPORT19.is_dir() and ACTUAL_PLAN19.is_file() and ACTUAL_NATIVE19.is_dir()):
        pytest.skip("set GREA65 actual-export19/plan19/native19 paths for the real Spine source-set matrix")
    plan = json.loads(ACTUAL_PLAN19.read_text(encoding="utf-8"))
    rendering = plan.get("staticSpineRendering")
    assert isinstance(rendering, dict) and rendering.get("contract") == "monkey-static-spine-rendering/1"
    actual_root = ACTUAL_EXPORT19.resolve()
    actual_sources = _manifest_sources(actual_root)
    temp_root = tmp_path.resolve() / "actual-spine-template-substitution"
    temp_root.mkdir()
    (temp_root / "Assets").mkdir()
    # Copy only exported source files. This is an offline source-set replay,
    # not a new export or an Editor project mutation.
    for source in actual_sources:
        target = temp_root / source.relative_to(actual_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    substitutions = _copy_current_spine_templates(actual_root, temp_root)
    test_manifest_rows = []
    for path in sorted((temp_root / "Assets").rglob("*.cs")):
        raw = path.read_bytes()
        test_manifest_rows.append({"path": path.relative_to(temp_root).as_posix(), "sha256": sha(raw), "bytes": len(raw)})
    write_json(temp_root / "manifest.json", {"files": test_manifest_rows})
    runtime_record = (plan.get("staticSpineContinuation") or {}).get("runtimeDependency")
    assert isinstance(runtime_record, dict) and runtime_record.get("status") == "optional_backup_read_only_verified_not_used"
    backup_manifest = Path(runtime_record["manifestPath"]).resolve()
    backup_bytes = backup_manifest.read_bytes()
    assert sha(backup_bytes) == runtime_record["manifestSha256"], "pinned Spine backup manifest changed"
    backup_doc = json.loads(backup_bytes)
    assert backup_doc.get("upstream", {}).get("sourceVersion") == "3.8.99 skeleton compatible branch3.8"
    verified = {row["path"]: row for row in runtime_record.get("verifiedFiles", []) if isinstance(row, dict)}
    candidates = [Path(runtime_record["assetsRoot"]) / "Assets/Plugins/Spine38/EditorRuntime/spine-csharp.dll",
                  Path(runtime_record["assetsRoot"]) / "Assets/Plugins/Spine38/EditorRuntime/spine-unity.dll"]
    export_manifest = json.loads((actual_root / "manifest.json").read_text(encoding="utf-8"))
    export_files = {row["path"]: row for row in export_manifest.get("files", [])}
    for dll in candidates:
        key = dll.relative_to(Path(runtime_record["assetsRoot"]).resolve()).as_posix()
        pin = verified.get(key)
        exported = actual_root / key
        output_pin = export_files.get(key)
        assert pin and dll.is_file() and sha(dll.read_bytes()) == pin["sha256"] and len(dll.read_bytes()) == pin["bytes"], \
            "Spine runtime DLL differs from the pinned read-only backup: " + key
        assert output_pin and exported.is_file() and sha(exported.read_bytes()) == pin["sha256"], \
            "actual-export19 did not preserve the pinned Spine runtime file: " + key
    standard_reference_root = ACTUAL_NATIVE19 / "Library/ScriptAssemblies"
    standard_references = _standard_references(reference_root=standard_reference_root)
    assert not any("spine" in path.name.lower() for path in standard_references)
    evidence_dir = Path(EVIDENCE_DIR_ENV).resolve() / "ActualSpineExport19" if EVIDENCE_DIR_ENV else temp_root / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "template-substitution.json").write_text(json.dumps({
        "contract": "actual-export19-source-template-substitution/1",
        "actualExportRoot": str(actual_root),
        "planPath": str(ACTUAL_PLAN19),
        "planStaticSpineRenderingContract": rendering.get("contract"),
        "sourceCountBeforeSubstitution": len(actual_sources),
        "substitutions": substitutions,
        "spineBackupManifestSha256": sha(backup_bytes),
        "boundary": "source files are copied from existing actual-export19; only twelve listed current package templates substituted; no new game plan export or Editor run",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    no_sdk = _compile(temp_root, references=standard_references, case="ActualSpineWithoutSdk", evidence_dir=evidence_dir)
    assert no_sdk["exitCode"] != 0, "real Spine export unexpectedly compiled without Spine SDK references"
    assert "Spine" in no_sdk["stdout"] + no_sdk["stderr"] or "spine" in no_sdk["stdout"] + no_sdk["stderr"].lower(), \
        "SDK-free rejection must identify the missing Spine adapter/runtime dependency"
    with_sdk = _compile(temp_root, references=_standard_references(spine_dlls=tuple(candidates)),
                        case="ActualSpineWithSdk", evidence_dir=evidence_dir)
    assert with_sdk["exitCode"] == 0, with_sdk["stdout"] + with_sdk["stderr"]
