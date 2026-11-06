"""Compile and exercise production C# static-Spine spec readers without Unity."""
from __future__ import annotations

import os
import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

import pytest


ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "tests/recovery/native/StaticSpineCanvasScaleHarness.cs"


def _project_from_existing_compile(temp_root: Path, generated_project: Path) -> Path:
    original = ET.parse(generated_project).getroot()
    compile_paths = []
    references = []
    for item_group in original.findall("ItemGroup"):
        for item in item_group:
            if item.tag == "Compile":
                compile_paths.append(item.attrib["Include"])
            elif item.tag == "Reference":
                hint = item.find("HintPath")
                if hint is not None and hint.text:
                    references.append((item.attrib.get("Include", Path(hint.text).stem), hint.text))
    if not compile_paths or not references:
        raise AssertionError("existing compile-current project omitted production sources or references")

    project = ET.Element("Project", {"Sdk": "Microsoft.NET.Sdk"})
    props = ET.SubElement(project, "PropertyGroup")
    for name, value in (
        ("OutputType", "Exe"), ("TargetFramework", "net8.0"),
        ("EnableDefaultCompileItems", "false"), ("DefineConstants", "UNITY_EDITOR"),
        ("ImplicitUsings", "enable"), ("Nullable", "disable"),
        ("NoWarn", "CS0649;CS0618;CS0169;CS0414"),
    ):
        ET.SubElement(props, name).text = value
    sources = ET.SubElement(project, "ItemGroup")
    for source in compile_paths:
        ET.SubElement(sources, "Compile", {"Include": source})
    ET.SubElement(sources, "Compile", {"Include": str(HARNESS)})
    refs = ET.SubElement(project, "ItemGroup")
    for name, hint_path in references:
        reference = ET.SubElement(refs, "Reference", {"Include": name})
        ET.SubElement(reference, "HintPath").text = hint_path
    path = temp_root / "OfflineSpineCanvasScaleHarness.csproj"
    ET.ElementTree(project).write(path, encoding="utf-8", xml_declaration=True)
    (temp_root / "NuGet.Config").write_text(
        "<configuration><packageSources><clear /></packageSources></configuration>", encoding="utf-8")
    return path


def test_production_cocos_static_spine_canvas_scale_closure_and_refusals():
    dotnet = shutil.which("dotnet") or ("/opt/homebrew/bin/dotnet"
        if Path("/opt/homebrew/bin/dotnet").is_file() else None)
    if not dotnet:
        pytest.skip(".NET SDK unavailable")
    compile_script_value = os.environ.get("MONKEY_SPINE_CANVAS_COMPILE_SCRIPT")
    project_root_value = os.environ.get("MONKEY_NATIVE13_UNITY_PROJECT")
    if not compile_script_value or not project_root_value:
        pytest.skip("set MONKEY_SPINE_CANVAS_COMPILE_SCRIPT and MONKEY_NATIVE13_UNITY_PROJECT for the offline production harness")
    compile_script = Path(compile_script_value).resolve()
    if not compile_script.is_file():
        pytest.skip("production compile-current.py input is unavailable")
    project_root = Path(project_root_value).resolve()
    import_plan = project_root / "Assets/Game/Editor/Conversion/import-plan.json"
    rendering = project_root / "Assets/Game/Editor/Conversion/spine-static-rendering.json"
    if not import_plan.is_file() or not rendering.is_file():
        pytest.skip("native-13 read-only Unity project is unavailable; set MONKEY_NATIVE13_UNITY_PROJECT")

    pinned_inputs = [import_plan, rendering, project_root / "Analysis/Readback/SpineRendering/prepare.json"]
    pin = lambda path: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    before = [pin(path) for path in pinned_inputs]

    production_build = subprocess.run(
        [sys.executable, str(compile_script)], cwd=ROOT, capture_output=True, text=True, timeout=180)
    assert production_build.returncode == 0, production_build.stdout + production_build.stderr
    generated_project = compile_script.parent / "compile/Contract.csproj"
    assert generated_project.is_file(), production_build.stdout + production_build.stderr

    with tempfile.TemporaryDirectory(prefix="monkey-spine-canvas-harness-") as temporary:
        output_root = Path(temporary)
        harness_project = _project_from_existing_compile(output_root, generated_project)
        build = subprocess.run(
            [dotnet, "build", str(harness_project), "--configfile", str(output_root / "NuGet.Config"),
             "--nologo", "-v:q"], cwd=output_root, capture_output=True, text=True, timeout=240)
        assert build.returncode == 0, build.stdout + build.stderr
        assembly = output_root / "bin/Debug/net8.0/OfflineSpineCanvasScaleHarness.dll"
        run = subprocess.run(
            [dotnet, str(assembly), str(import_plan), str(project_root)],
            cwd=output_root, capture_output=True, text=True, timeout=180,
            env={**os.environ, "MONKEY_DUMP_SPINE_DEFAULTS": "1"} if os.environ.get("MONKEY_DUMP_SPINE_DEFAULTS") == "1" else None)
        assert run.returncode == 0, run.stdout + run.stderr
        assert "components=75 dataAssets=18 uniqueDataAssets=18 canvasPpu=100 resolvedScale=0.01 persistedScale=0.01" in run.stdout
        assert "invalid PPU, mappings, eligibility, paths, payloads, pages, source scale and explicit scale rejected" in run.stdout
        assert "Unity AssetDatabase GUID persistence remains Editor-only" in run.stdout

        after = [pin(path) for path in pinned_inputs]
        assert after == before, "read-only native inputs changed during offline integration"
        receipt = os.environ.get("MONKEY_SPINE_CANVAS_RECEIPT")
        if receipt:
            Path(receipt).write_text(json.dumps({
                "schema": "monkey-offline-static-spine-input-integration/1",
                "inputs": before, "inputsUnchanged": after == before,
                "productionBuild": production_build.stdout.strip(),
                "harnessBuildExitCode": build.returncode,
                "harnessExitCode": run.returncode,
                "output": run.stdout.strip(),
                "nativeEditorExecuted": False,
                "persistentGuidAcceptance": "Editor-only; not claimed",
            }, indent=2) + "\n", encoding="utf-8")
