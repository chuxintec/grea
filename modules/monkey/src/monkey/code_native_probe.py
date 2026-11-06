"""Prepare a narrow native Unity probe for the recovered HealthState module.

This does not launch Unity. It copies only hash-verified source assets into a
new Unity 6 project and adds an explicitly new adapter/probe harness.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

from .io import load, new_output, safe, write_json
from .sources.compiled import fail
from .unity_code_il import parse_csharp, tokenize_csharp


EXPECTED_SOURCE_SHA256 = "21af08e48846f6ad1a2e0673b0c945358136723b1664f0cd1f6ec9b3df6c5cb5"
EXPECTED_SOURCE_BYTES = 7_147_892
MAX_MANIFEST_BYTES = 32 * 1024 * 1024
MAX_FILE_BYTES = 32 * 1024 * 1024
UNITY_VERSION = "6000.6.2f1"
HEALTH_FIELDS = {
    "atk": "double", "combo": "double", "currHp": "double", "def": "double",
    "delta": "double", "maxHp": "double", "onComboChange": "Action<HealthState>",
    "onHpChange": "Action<HealthState>",
}
REQUIRED_METHODS = {"DoDelta", "MaxHpDoDelta", "ComboDoDelta", "getPercent", "SetProperty", "clearCombo"}
HEALTH_SOURCE = "Assets/Game/Domain/Recovered/HealthState.cs"
HEALTH_META = HEALTH_SOURCE + ".meta"
COLLECTIONS_SOURCE = "Assets/Game/Domain/Recovered/CodeCollections.cs"
COLLECTIONS_META = COLLECTIONS_SOURCE + ".meta"
MODULE_REPORT = "Analysis/Code/code-modules.json"
RECIPE_CATALOG_SOURCE = "Assets/Game/Domain/Recovered/RecipeCatalog.cs"
RECIPE_CATALOG_META = RECIPE_CATALOG_SOURCE + ".meta"
RECIPE_RECORDS_SOURCE = "Assets/Game/Domain/Recovered/RecoveredRecords.cs"
RECIPE_RECORDS_META = RECIPE_RECORDS_SOURCE + ".meta"
RECIPE_CONFIG_SOURCE = "Assets/Game/Domain/Recovered/RecipeJsonConfiguration.cs"
RECIPE_CONFIG_META = RECIPE_CONFIG_SOURCE + ".meta"
RECIPE_JSON = "Assets/Game/Content/Config/Base/ElementMultiOrderPool.json"
RECIPE_JSON_META = RECIPE_JSON + ".meta"
EXPECTED_RECIPE_JSON_SHA256 = "ac76070e3347e32bb7149c049ab2477b1c46a8bb2768d21195100afd6d85e89d"
EXPECTED_RECIPE_JSON_BYTES = 212_601
RECIPE_LEAVES_2015015 = [1010204, 1005303, 1007206, 1002401, 1007204, 1010201, 1004302, 1005203, 1010303]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _safe_child(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        fail("CODE_NATIVE_UNSAFE_PATH", str(relative), "Expected a non-empty relative candidate path")
    path = safe(root / relative)
    if not path.is_relative_to(root):
        fail("CODE_NATIVE_UNSAFE_PATH", relative, "Candidate path escapes the input root")
    return path


def _read_manifest(root: Path, expected_sha256: str) -> tuple[bytes, dict[str, Any]]:
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        fail("CODE_NATIVE_MANIFEST_MISSING", str(root), "Candidate manifest is missing or not a regular file")
    raw = manifest_path.read_bytes()
    if len(raw) > MAX_MANIFEST_BYTES:
        fail("CODE_NATIVE_MANIFEST_BUDGET", "manifest.json", "Candidate manifest exceeds the read budget")
    if _sha(raw) != expected_sha256:
        fail("CODE_NATIVE_MANIFEST_HASH", "manifest.json", "Candidate manifest hash differs from the requested identity")
    try:
        manifest = load(raw, max_nodes=2_000_000, max_depth=96)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        fail("CODE_NATIVE_MANIFEST_INVALID", "manifest.json", f"Candidate manifest is not bounded JSON ({type(error).__name__})")
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != 1:
        fail("CODE_NATIVE_MANIFEST_SCHEMA", "manifest.json", "Only candidate schemaVersion 1 is supported")
    return raw, manifest


def _owned_bytes(root: Path, files: dict[str, dict[str, Any]], relative: str, expected_owner: str) -> bytes:
    row = files.get(relative)
    if not isinstance(row, dict) or type(row.get("bytes")) is not int or not isinstance(row.get("sha256"), str):
        fail("CODE_NATIVE_FILE_NOT_OWNED", relative, "Required source must have an owned hash/byte manifest record")
    if row.get("owner") != expected_owner:
        fail("CODE_NATIVE_OWNER_MISMATCH", relative, "Owned file owner differs from the approved HealthState/Recipe source contract")
    if row["bytes"] < 0 or row["bytes"] > MAX_FILE_BYTES:
        fail("CODE_NATIVE_FILE_BUDGET", relative, "Owned source exceeds the per-file byte budget")
    path = _safe_child(root, relative)
    if not path.is_file() or path.is_symlink():
        fail("CODE_NATIVE_FILE_MISSING", relative, "Owned source file is missing or not regular")
    raw = path.read_bytes()
    if len(raw) != row["bytes"] or _sha(raw) != row["sha256"]:
        fail("CODE_NATIVE_FILE_CHANGED", relative, "Owned source file differs from its exact manifest identity")
    return raw


def _check_health_contract(report: dict[str, Any], health_source: bytes) -> dict[str, Any]:
    source = report.get("source")
    if not isinstance(source, dict) or source.get("sha256") != EXPECTED_SOURCE_SHA256 or source.get("bytes") != EXPECTED_SOURCE_BYTES:
        fail("CODE_NATIVE_SOURCE_IDENTITY", MODULE_REPORT, "Only the explicitly pinned source identity is supported")
    if report.get("sourceExecuted") is not False:
        fail("CODE_NATIVE_SOURCE_EXECUTION", MODULE_REPORT, "Code-module report must affirm that source was not executed")
    if report.get("namespace") != "Game.Domain.Recovered":
        fail("CODE_NATIVE_NAMESPACE", MODULE_REPORT, "HealthState namespace differs from the approved candidate")
    methods = report.get("methods")
    if not isinstance(methods, list):
        fail("CODE_NATIVE_METHOD_REPORT", MODULE_REPORT, "Code-module report has no method inventory")
    recovered = {row.get("targetMethod") for row in methods if isinstance(row, dict) and row.get("targetClass") == "HealthState"}
    if not REQUIRED_METHODS.issubset(recovered):
        fail("CODE_NATIVE_METHOD_COVERAGE", MODULE_REPORT, "HealthState method set is incomplete")

    try:
        code = health_source.decode("utf-8-sig")
    except UnicodeDecodeError:
        fail("CODE_NATIVE_HEALTH_ENCODING", HEALTH_SOURCE, "HealthState source is not UTF-8")
    if "namespace Game.Domain.Recovered" not in code or not re.search(r"\bclass\s+HealthState\b", code):
        fail("CODE_NATIVE_HEALTH_TYPE", HEALTH_SOURCE, "Expected Game.Domain.Recovered.HealthState")
    tokens = tokenize_csharp(code)
    values = [row["value"] for row in tokens]
    type_index = next((index for index in range(len(values) - 1)
                       if values[index] == "class" and values[index + 1] == "HealthState"), None)
    open_index = next((index for index in range(type_index + 2, len(values)) if values[index] == "{"), None) if type_index is not None else None
    if open_index is None:
        fail("CODE_NATIVE_HEALTH_CLASS_PARSE", HEALTH_SOURCE, "Could not bound the HealthState class body")
    depth = 0
    close_index = None
    for index in range(open_index, len(values)):
        if values[index] == "{": depth += 1
        elif values[index] == "}":
            depth -= 1
            if depth == 0:
                close_index = index
                break
    if close_index is None:
        fail("CODE_NATIVE_HEALTH_CLASS_PARSE", HEALTH_SOURCE, "HealthState class braces are unbalanced")
    class_body = code[tokens[open_index]["end"]:tokens[close_index]["start"]]
    declared = {}
    for line in class_body.splitlines():
        stripped = line.strip()
        match = re.fullmatch(r"public\s+(double|Action<HealthState>)\s+([A-Za-z_][A-Za-z0-9_]*)\s*;", stripped)
        if match:
            name, type_name = match.group(2), match.group(1)
            if name in declared:
                fail("CODE_NATIVE_HEALTH_FIELD_DUPLICATE", name, "HealthState field is duplicated")
            declared[name] = type_name
    if declared != HEALTH_FIELDS:
        fail("CODE_NATIVE_HEALTH_FIELDS", HEALTH_SOURCE, "HealthState fields or field types differ from the approved eight-field contract")
    parsed_health = parse_csharp(code, HEALTH_SOURCE, _sha(health_source))
    methods_in_source = {row["name"] for row in parsed_health["methods"]
                         if row["declaringType"] == "Game.Domain.Recovered.HealthState"}
    if not REQUIRED_METHODS.issubset(methods_in_source):
        fail("CODE_NATIVE_HEALTH_METHODS", HEALTH_SOURCE, "HealthState C# methods do not satisfy the approved method subset")
    ctor = re.search(r"public\s+HealthState\s*\(([^)]*)\)", class_body)
    if not ctor:
        fail("CODE_NATIVE_HEALTH_CTOR", HEALTH_SOURCE, "HealthState constructor is missing")
    parameters = [part.strip() for part in ctor.group(1).split(",")]
    names = [re.sub(r".*\s+", "", part) for part in parameters]
    expected_names = ["initialAtk", "initialCombo", "initialCurrHp", "initialDef", "initialDelta",
                      "initialMaxHp", "initialOnComboChange", "initialOnHpChange"]
    if names != expected_names or parameters[-2:] != ["Action<HealthState> initialOnComboChange", "Action<HealthState> initialOnHpChange"]:
        fail("CODE_NATIVE_HEALTH_CTOR_ORDER", HEALTH_SOURCE, "HealthState constructor parameters do not match the explicit field-order contract")
    return {"namespace": report["namespace"], "fields": HEALTH_FIELDS, "methods": sorted(REQUIRED_METHODS),
            "constructorParameters": names}


def _check_recipe_contract(report: dict[str, Any], config_source: bytes, catalog_source: bytes,
                           recipe_json: bytes, recipe_json_meta: bytes) -> dict[str, Any]:
    methods = report.get("methods")
    catalog_methods = {row.get("targetMethod") for row in methods if isinstance(row, dict)
                       and row.get("targetClass") == "RecipeCatalog"} if isinstance(methods, list) else set()
    required = {"IsDish", "GetRecipeOf", "FlattenIngredientsOf"}
    if not required.issubset(catalog_methods):
        fail("CODE_NATIVE_RECIPE_METHODS", MODULE_REPORT, "RecipeCatalog method set is incomplete")
    try:
        config = config_source.decode("utf-8-sig")
        catalog = catalog_source.decode("utf-8-sig")
    except UnicodeDecodeError:
        fail("CODE_NATIVE_RECIPE_ENCODING", RECIPE_CONFIG_SOURCE, "Recipe source is not UTF-8")
    if ("namespace Game.Domain.Recovered" not in config or
            not re.search(r"public\s+static\s+OrderedMap<double,\s*Recipe>\s+Load\s*\(\s*TextAsset\s+asset\s*\)", config) or
            not re.search(r"public\s+static\s+OrderedMap<double,\s*Recipe>\s+Load\s*\(\s*string\s+json\s*\)", config)):
        fail("CODE_NATIVE_RECIPE_LOADER", RECIPE_CONFIG_SOURCE, "RecipeJsonConfiguration must expose the bounded TextAsset and string loaders")
    if (not re.search(r"public\s+static\s+List<double>\s+FlattenIngredientsOf\s*\(\s*double\s+\w+\s*\)", catalog)):
        fail("CODE_NATIVE_RECIPE_CATALOG", RECIPE_CATALOG_SOURCE, "RecipeCatalog flatten API differs from the approved probe contract")
    if len(recipe_json) != EXPECTED_RECIPE_JSON_BYTES or _sha(recipe_json) != EXPECTED_RECIPE_JSON_SHA256:
        fail("CODE_NATIVE_RECIPE_JSON_IDENTITY", RECIPE_JSON, "Recipe JSON differs from the approved exact fixture input")
    try:
        table = load(recipe_json, max_nodes=500_000, max_depth=96)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        fail("CODE_NATIVE_RECIPE_JSON_INVALID", RECIPE_JSON, f"Recipe JSON is not bounded JSON ({type(error).__name__})")
    probe_row = table.get("293") if isinstance(table, dict) else None
    if (not isinstance(table, dict) or len(table) != 732 or not isinstance(probe_row, dict) or
            probe_row.get("elementIdWeight", {}).get("2015015") != 0):
        fail("CODE_NATIVE_RECIPE_JSON_CONTRACT", RECIPE_JSON, "Expected 732 rows and row 293's elementIdWeight entry for probe dish 2015015")
    meta_match = re.search(rb"(?m)^guid: ([0-9a-f]{32})\r?$", recipe_json_meta)
    if not meta_match:
        fail("CODE_NATIVE_RECIPE_META", RECIPE_JSON_META, "Recipe TextAsset .meta has no valid GUID")
    return {"catalogMethods": sorted(required), "loaderOverloads": ["Load(TextAsset)", "Load(string)"],
            "json": {"path": RECIPE_JSON, "bytes": len(recipe_json), "sha256": _sha(recipe_json),
                     "guid": meta_match.group(1).decode("ascii")},
            "jsonRecordCount": 732, "verifiedSourceOrderRow": 293,
            "probeDishId": 2015015, "expectedFlattenedLeafIds": RECIPE_LEAVES_2015015}


def prepare(candidate: str | Path, expected_manifest_sha256: str, output: str | Path, *,
            health_module: str = "HealthState", recipe_module: bool = False) -> dict[str, Any]:
    """Create a fresh Unity 6 project for the approved HealthState subset and optional recipe-table path."""
    root = safe(candidate)
    if not root.is_dir() or root.is_symlink():
        fail("CODE_NATIVE_CANDIDATE_ROOT", str(root), "Candidate must be an existing non-symlink directory")
    if health_module != "HealthState":
        fail("CODE_NATIVE_MODULE_UNSUPPORTED", health_module, "This probe implements only the approved HealthState contract")
    if type(recipe_module) is not bool:
        fail("CODE_NATIVE_RECIPE_OPTION", "$", "recipe_module must be a boolean")
    manifest_raw, manifest = _read_manifest(root, expected_manifest_sha256)
    source = manifest.get("source")
    if not isinstance(source, dict) or source.get("sha256") != EXPECTED_SOURCE_SHA256 or source.get("bytes") != EXPECTED_SOURCE_BYTES:
        fail("CODE_NATIVE_SOURCE_IDENTITY", "manifest.json", "Candidate is not the explicitly approved source revision")
    file_rows = manifest.get("files")
    if not isinstance(file_rows, list):
        fail("CODE_NATIVE_FILE_INVENTORY", "manifest.json", "Candidate manifest lacks owned file inventory")
    files = {row.get("path"): row for row in file_rows if isinstance(row, dict) and isinstance(row.get("path"), str)}
    if len(files) != len(file_rows):
        fail("CODE_NATIVE_FILE_INVENTORY", "manifest.json", "Candidate file paths are missing or duplicated")
    report_raw = _owned_bytes(root, files, MODULE_REPORT, "SourceEvidence")
    health_source = _owned_bytes(root, files, HEALTH_SOURCE, "HealthState")
    health_meta = _owned_bytes(root, files, HEALTH_META, "HealthState")
    collections_source = _owned_bytes(root, files, COLLECTIONS_SOURCE, "RecoveryTypes")
    collections_meta = _owned_bytes(root, files, COLLECTIONS_META, "RecoveryTypes")
    report_hash = files[MODULE_REPORT]["sha256"]
    if hashlib.sha256(report_raw).hexdigest() != report_hash:
        fail("CODE_NATIVE_METHOD_REPORT_HASH", MODULE_REPORT, "Code-module report identity changed")
    try:
        code_report = load(report_raw, max_nodes=1_000_000, max_depth=96)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        fail("CODE_NATIVE_METHOD_REPORT_INVALID", MODULE_REPORT, f"Code-module report is not bounded JSON ({type(error).__name__})")
    contract = _check_health_contract(code_report, health_source)
    if b"public static class NumberMath" not in collections_source or b"namespace Game.Domain.Recovered" not in collections_source:
        fail("CODE_NATIVE_DEPENDENCY_CONTRACT", COLLECTIONS_SOURCE, "Expected the exact recovered NumberMath dependency in the same namespace")

    recipe_contract = None
    recipe_owned = []
    if recipe_module:
        recipe_catalog = _owned_bytes(root, files, RECIPE_CATALOG_SOURCE, "RecipeCatalog")
        recipe_catalog_meta = _owned_bytes(root, files, RECIPE_CATALOG_META, "RecipeCatalog")
        recipe_records = _owned_bytes(root, files, RECIPE_RECORDS_SOURCE, "RecoveryTypes")
        recipe_records_meta = _owned_bytes(root, files, RECIPE_RECORDS_META, "RecoveryTypes")
        recipe_config = _owned_bytes(root, files, RECIPE_CONFIG_SOURCE, "RecipeJsonConfiguration")
        recipe_config_meta = _owned_bytes(root, files, RECIPE_CONFIG_META, "RecipeJsonConfiguration")
        recipe_json = _owned_bytes(root, files, RECIPE_JSON, "RecipeJsonConfiguration")
        recipe_json_meta = _owned_bytes(root, files, RECIPE_JSON_META, "RecipeJsonConfiguration")
        recipe_contract = _check_recipe_contract(code_report, recipe_config, recipe_catalog, recipe_json, recipe_json_meta)
        recipe_owned = [(RECIPE_CATALOG_SOURCE, recipe_catalog), (RECIPE_CATALOG_META, recipe_catalog_meta),
                        (RECIPE_RECORDS_SOURCE, recipe_records), (RECIPE_RECORDS_META, recipe_records_meta),
                        (RECIPE_CONFIG_SOURCE, recipe_config), (RECIPE_CONFIG_META, recipe_config_meta),
                        (RECIPE_JSON, recipe_json), (RECIPE_JSON_META, recipe_json_meta)]

    output_path = new_output(output, [root])
    (output_path / "Assets/Game/Domain/Recovered").mkdir(parents=True)
    if recipe_module:
        (output_path / "Assets/Game/Content/Config/Base").mkdir(parents=True)
    (output_path / "Assets/CodeModuleProbe/Runtime").mkdir(parents=True)
    (output_path / "Assets/CodeModuleProbe/Data").mkdir(parents=True)
    (output_path / "Assets/Editor").mkdir(parents=True)
    (output_path / "ProjectSettings").mkdir()
    (output_path / "Packages").mkdir()
    copied = []
    for relative, raw in ((HEALTH_SOURCE, health_source), (HEALTH_META, health_meta),
                          (COLLECTIONS_SOURCE, collections_source), (COLLECTIONS_META, collections_meta), *recipe_owned):
        destination = output_path / "Assets" / relative.removeprefix("Assets/")
        destination.write_bytes(raw)
        copied.append({"sourcePath": relative, "projectPath": destination.relative_to(output_path).as_posix(),
                       "sha256": _sha(raw), "bytes": len(raw)})
    adapter_text = _runtime_probe_source(recipe_module)
    readout_text = _readout_probe_source()
    recipe_guid = recipe_contract["json"]["guid"] if recipe_contract else None
    editor_text = _editor_probe_source(expected_manifest_sha256, report_hash, recipe_module, recipe_guid)
    (output_path / "Assets/CodeModuleProbe/Runtime/CodeModuleProbeRuntime.cs").write_text(adapter_text, encoding="utf-8")
    (output_path / "Assets/CodeModuleProbe/Runtime/CodeModuleProbeReadout.cs").write_text(readout_text, encoding="utf-8")
    (output_path / "Assets/Editor/CodeModuleProbeEditor.cs").write_text(editor_text, encoding="utf-8")
    initial_state = {"atk": 10.0, "combo": 0.0, "currHp": 80.0, "def": 1.0, "delta": 0.0, "maxHp": 100.0}
    state_bytes = (json.dumps(initial_state, sort_keys=True, indent=2) + "\n").encode("utf-8")
    (output_path / "Assets/CodeModuleProbe/Data/InitialState.fixture.json").write_bytes(state_bytes)
    # Explicit deterministic GUIDs make asset identity stable in this disposable project.
    for relative, raw in (("Assets/CodeModuleProbe/Data/InitialState.fixture.json", state_bytes),):
        guid = hashlib.sha256(("monkey-v060-code-probe:" + relative + ":" + _sha(raw)).encode()).hexdigest()[:32]
        (output_path / (relative + ".meta")).write_text(
            "fileFormatVersion: 2\nguid: " + guid + "\nTextScriptImporter:\n  externalObjects: {}\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n",
            encoding="utf-8")
    (output_path / "ProjectSettings/ProjectVersion.txt").write_text("m_EditorVersion: " + UNITY_VERSION + "\n", encoding="utf-8")
    dependencies = {"com.unity.modules.imgui": "1.0.0", "com.unity.modules.jsonserialize": "1.0.0"}
    (output_path / "Packages/manifest.json").write_text(json.dumps({"dependencies": dependencies}, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    prep = {"schemaVersion": 1, "status": "prepared_not_run", "unityVersion": UNITY_VERSION,
            "candidate": {"root": str(root), "manifestSha256": expected_manifest_sha256,
                          "sourceSha256": source["sha256"], "codeModulesReportSha256": report_hash},
            "healthContract": contract, "recipeModule": {"enabled": recipe_module, "contract": recipe_contract},
            "copiedOwnedFiles": copied,
            "adapter": {"kind": "new-unity-native-probe-adapter", "doesNotClaimOriginalConstructorOrLifecycleOrUI": True,
                        "jsonFixturePath": "Assets/CodeModuleProbe/Data/InitialState.fixture.json",
                        "fixtureValuesAreOriginalGameValues": False},
            "project": {"path": str(output_path), "scenePath": "Assets/CodeModuleProbe/Scenes/CodeModuleProbe.unity",
                        "executeMethod": "MonkeyCodeModuleProbe.Run", "editorAutoStarted": False},
            "sourceExecuted": False, "sourceCodeExecuted": False,
            "validationStatus": {"compiled": "not_run", "unityBinding": "not_run", "playMode": "not_run",
                                 "render": "not_run", "physicalInput": "not_run", "playerBuild": "not_run"},
            "outputs": []}
    runtime_path = output_path / "Assets/CodeModuleProbe/Runtime/CodeModuleProbeRuntime.cs"
    readout_path = output_path / "Assets/CodeModuleProbe/Runtime/CodeModuleProbeReadout.cs"
    editor_path = output_path / "Assets/Editor/CodeModuleProbeEditor.cs"
    for path in (runtime_path, readout_path, editor_path, output_path / "Assets/CodeModuleProbe/Data/InitialState.fixture.json",
                 output_path / "Assets/CodeModuleProbe/Data/InitialState.fixture.json.meta",
                 output_path / "ProjectSettings/ProjectVersion.txt", output_path / "Packages/manifest.json"):
        raw = path.read_bytes()
        prep["outputs"].append({"path": path.relative_to(output_path).as_posix(), "sha256": _sha(raw), "bytes": len(raw)})
    write_json(output_path / "code-native-probe-plan.json", prep)
    return {"status": "prepared_not_run", "plan": str(output_path / "code-native-probe-plan.json"),
            "project": str(output_path), "outputs": prep["outputs"], "sourceExecuted": False,
            "sourceCodeExecuted": False}


def _runtime_probe_source(recipe_module: bool) -> str:
    template = r'''using System;
using Game.Domain.Recovered;
using UnityEngine;
using UnityEngine.Events;

namespace Monkey.CodeModuleProbe
{
    [Serializable]
    public sealed class ProbeInitialState
    {
        public double atk = double.NaN;
        public double combo = double.NaN;
        public double currHp = double.NaN;
        public double def = double.NaN;
        public double delta = double.NaN;
        public double maxHp = double.NaN;
    }

    [Serializable]
    public sealed class ProbeDoubleEvent : UnityEvent<double> { }

    public sealed class CodeModuleProbeRuntime : MonoBehaviour
    {
#pragma warning disable 0649
        [SerializeField] private TextAsset initialStateJson;
        [SerializeField] private CodeModuleProbeReadout readout;
__RECIPE_FIELD__
#pragma warning restore 0649
        [SerializeField] public ProbeDoubleEvent hpChanged = new ProbeDoubleEvent();
        [SerializeField] public ProbeDoubleEvent comboChanged = new ProbeDoubleEvent();
        [NonSerialized] public HealthState state;
        [NonSerialized] public bool probeOnEnable;
        [NonSerialized] public bool probeAwake;

        public HealthState State { get { return state; } }
        public CodeModuleProbeReadout Readout { get { return readout; } }
        public TextAsset InitialStateJson { get { return initialStateJson; } }
__RECIPE_PROPERTY__
__RECIPE_GUI_FIELD__

        private void OnEnable() { probeOnEnable = true; }

        private void Awake()
        {
            if (initialStateJson == null || readout == null)
                throw new InvalidOperationException("Probe scene references are not assigned.");
            ProbeInitialState values = new ProbeInitialState();
            JsonUtility.FromJsonOverwrite(initialStateJson.text, values);
            if (!Finite(values.atk) || !Finite(values.combo) || !Finite(values.currHp) || !Finite(values.def)
                || !Finite(values.delta) || !Finite(values.maxHp))
                throw new InvalidOperationException("Fixture JSON omitted a required numeric state field or contained a non-finite value.");
            if (values.maxHp <= 0d || values.currHp < 0d || values.currHp > values.maxHp)
                throw new InvalidOperationException("Fixture JSON HP state is outside the probe's explicit safe range.");
            state = new HealthState(values.atk, values.combo, values.currHp, values.def, values.delta,
                values.maxHp, null, null);
            state.onHpChange += ForwardHpChange;
            state.onComboChange += ForwardComboChange;
__RECIPE_AWAKE__
            probeAwake = true;
        }

        private void OnDestroy()
        {
            if (state != null)
            {
                state.onHpChange -= ForwardHpChange;
                state.onComboChange -= ForwardComboChange;
            }
        }

        private void ForwardHpChange(HealthState value) { hpChanged.Invoke(value.currHp); }
        private void ForwardComboChange(HealthState value) { comboChanged.Invoke(value.combo); }
__RECIPE_HELPER__
        private static bool Finite(double value) { return !double.IsNaN(value) && !double.IsInfinity(value); }

        private void OnGUI()
        {
            if (state == null) return;
            GUILayout.BeginArea(new Rect(16, 16, 360, 280), GUI.skin.box);
            GUILayout.Label("Native HealthState candidate probe");
            GUILayout.Label("HP " + state.currHp + " / " + state.maxHp + "  percent " + state.getPercent());
            GUILayout.Label("Combo " + state.combo + "  atk " + state.atk + "  def " + state.def);
            if (GUILayout.Button("Damage -10")) state.DoDelta(-10d);
            if (GUILayout.Button("Heal +10")) state.DoDelta(10d);
            if (GUILayout.Button("Max HP +10")) state.MaxHpDoDelta(10d);
            if (GUILayout.Button("Combo +1")) state.ComboDoDelta(1d);
            if (GUILayout.Button("Clear combo")) state.clearCombo();
__RECIPE_GUI__
            GUILayout.EndArea();
        }
    }
}
'''
    snippets = {
        "__RECIPE_FIELD__": "        [SerializeField] private TextAsset recipeTable;" if recipe_module else "",
        "__RECIPE_PROPERTY__": "        public TextAsset RecipeTable { get { return recipeTable; } }" if recipe_module else "",
        "__RECIPE_GUI_FIELD__": "        private string recipeReadout = \"not queried\";" if recipe_module else "",
        "__RECIPE_HELPER__": ("        private static string RecipeLabel() { var leaves = RecipeCatalog.FlattenIngredientsOf(2015015d); var labels = new string[leaves.Count]; for (int i = 0; i < leaves.Count; i++) labels[i] = leaves[i].ToString(System.Globalization.CultureInfo.InvariantCulture); return String.Join(\", \", labels); }"
                              if recipe_module else ""),
        "__RECIPE_AWAKE__": ("            if (recipeTable == null) throw new InvalidOperationException(\"Recipe fixture TextAsset is missing.\");\n"
                              "            RecipeCatalog._dishMap = RecipeJsonConfiguration.Load(recipeTable);" if recipe_module else ""),
        "__RECIPE_GUI__": ("            if (GUILayout.Button(\"Flatten probe dish 2015015\"))\n"
                           "                recipeReadout = RecipeLabel();\n"
                           "            GUILayout.Label(recipeReadout);"
                           if recipe_module else ""),
    }
    for marker, value in snippets.items():
        template = template.replace(marker, value)
    return template


def _readout_probe_source() -> str:
    return r'''using UnityEngine;

namespace Monkey.CodeModuleProbe
{
    public sealed class CodeModuleProbeReadout : MonoBehaviour
    {
        public int hpCallbacks;
        public int comboCallbacks;
        public double lastHp;
        public double lastCombo;

        public void OnHpChanged(double value) { hpCallbacks++; lastHp = value; }
        public void OnComboChanged(double value) { comboCallbacks++; lastCombo = value; }
    }
}
'''


def _editor_probe_source(manifest_sha256: str, code_report_sha256: str, recipe_module: bool,
                         recipe_guid: str | None = None) -> str:
    template = r'''using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Game.Domain.Recovered;
using Monkey.CodeModuleProbe;
using UnityEditor;
using UnityEditor.Events;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

[InitializeOnLoad]
public static class MonkeyCodeModuleProbe
{
    private const string ActiveKey = "Monkey.CodeModuleProbe.Active";
    private const string SceneSavedKey = "Monkey.CodeModuleProbe.SceneSaved";
    private const string ProjectKey = "Monkey.CodeModuleProbe.Project";
    private const string ReceiptKey = "Monkey.CodeModuleProbe.Receipt";
    private const string StartedKey = "Monkey.CodeModuleProbe.StartedUtc";
    private const string BindingsBeforeKey = "Monkey.CodeModuleProbe.BindingsBefore";
    private const string PlayResultKey = "Monkey.CodeModuleProbe.PlayResult";
    private const string PhaseKey = "Monkey.CodeModuleProbe.Phase";
    private const string ScenePath = "Assets/CodeModuleProbe/Scenes/CodeModuleProbe.unity";
    private const string RuntimePath = "Assets/CodeModuleProbe/Runtime/CodeModuleProbeRuntime.cs";
    private const string ReadoutPath = "Assets/CodeModuleProbe/Runtime/CodeModuleProbeReadout.cs";
    private const string JsonPath = "Assets/CodeModuleProbe/Data/InitialState.fixture.json";
__RECIPE_CONSTANTS__
    private const string CandidateManifestSha256 = "__CANDIDATE_MANIFEST_SHA256__";
    private const string CodeModulesReportSha256 = "__CODE_MODULES_REPORT_SHA256__";
    private static Dictionary<string, object> receipt;

    static MonkeyCodeModuleProbe()
    {
        EditorApplication.playModeStateChanged -= OnPlayModeStateChanged;
        EditorApplication.playModeStateChanged += OnPlayModeStateChanged;
        EditorApplication.update -= CheckTimeout;
        EditorApplication.update += CheckTimeout;
    }

    public static void Run()
    {
        try
        {
            var projectPath = Directory.GetParent(Application.dataPath).FullName;
            Directory.SetCurrentDirectory(projectPath);
            var receiptPath = Path.GetFullPath("code-native-probe-receipt.json");
            SessionState.SetString(ProjectKey, projectPath);
            SessionState.SetString(ReceiptKey, receiptPath);
            if (File.Exists(receiptPath) || File.Exists(ScenePath))
                throw new InvalidOperationException("Probe receipt or scene already exists; prepare a fresh probe project.");
            SessionState.EraseString(BindingsBeforeKey);
            SessionState.EraseString(PlayResultKey);
            SessionState.EraseString(PhaseKey);
            SessionState.SetBool(ActiveKey, true);
            SessionState.SetString(StartedKey, DateTime.UtcNow.ToString("o"));
            receipt = new Dictionary<string, object>();
            receipt["schemaVersion"] = 1;
            receipt["unityVersion"] = Application.unityVersion;
            receipt["startedUtc"] = SessionState.GetString(StartedKey, "");
            receipt["sourceExecuted"] = false;
            receipt["sourceCodeExecuted"] = false;
            receipt["originalConstructorClaimed"] = false;
            receipt["candidateManifestSha256"] = CandidateManifestSha256;
            receipt["codeModulesReportSha256"] = CodeModulesReportSha256;
            receipt["probePlanSha256"] = FileSha256("code-native-probe-plan.json");
            receipt["render"] = "not_run";
            receipt["physicalInput"] = "not_run";
            receipt["playerBuild"] = "not_run";
            PrepareAndSaveScene();
            SessionState.SetBool(SceneSavedKey, true);
            receipt["savedSceneReopened"] = true;
            var bindingIdentity = VerifySavedSceneAndBindings();
            SessionState.SetString(BindingsBeforeKey, ToJson(bindingIdentity));
            receipt["savedBindingsBeforePlay"] = bindingIdentity;
            EditorApplication.isPlaying = true;
        }
        catch (Exception error) { Fail(error); }
    }

    // Independent interactive proof reuses these exact scene/binding checks;
    // it does not run the automated sequence or exit the Editor.
    public static string PrepareInteractiveScene()
    {
        PrepareAndSaveScene();
        return ToJson(VerifySavedSceneAndBindings());
    }

    public static string ReopenInteractiveScene()
    {
        EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
        return ToJson(VerifySavedSceneAndBindings());
    }

    private static void PrepareAndSaveScene()
    {
        if (Application.unityVersion != "6000.6.2f1")
            throw new InvalidOperationException("Unexpected Unity editor version.");
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var root = new GameObject("HealthStateProbe");
        var readout = root.AddComponent<CodeModuleProbeReadout>();
        var runtime = root.AddComponent<CodeModuleProbeRuntime>();
        var serialized = new SerializedObject(runtime);
        serialized.FindProperty("initialStateJson").objectReferenceValue = AssetDatabase.LoadAssetAtPath<TextAsset>(JsonPath);
        serialized.FindProperty("readout").objectReferenceValue = readout;
__RECIPE_ASSIGN__
        serialized.ApplyModifiedPropertiesWithoutUndo();
        UnityEventTools.AddPersistentListener(runtime.hpChanged, readout.OnHpChanged);
        UnityEventTools.AddPersistentListener(runtime.comboChanged, readout.OnComboChanged);
        EditorUtility.SetDirty(runtime);
        EditorUtility.SetDirty(readout);
        Directory.CreateDirectory(Path.GetDirectoryName(ScenePath));
        if (!EditorSceneManager.SaveScene(SceneManager.GetActiveScene(), ScenePath))
            throw new InvalidOperationException("Could not save generated probe scene.");
        AssetDatabase.SaveAssets();
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var reopened = EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
        if (!reopened.IsValid() || !reopened.isLoaded) throw new InvalidOperationException("Saved probe scene did not reopen.");
    }

    private static Dictionary<string, object> VerifySavedSceneAndBindings()
    {
        var runtime = UnityEngine.Object.FindAnyObjectByType<CodeModuleProbeRuntime>();
        if (runtime == null || runtime.Readout == null || runtime.InitialStateJson == null)
            throw new InvalidOperationException("Reopened scene is missing serialized component references.");
        VerifyEvent(runtime.hpChanged, runtime.Readout, "OnHpChanged");
        VerifyEvent(runtime.comboChanged, runtime.Readout, "OnComboChanged");
        var readoutScript = MonoScript.FromMonoBehaviour(runtime.Readout);
        var runtimeScript = MonoScript.FromMonoBehaviour(runtime);
        var identity = new Dictionary<string, object>();
        identity["textAsset"] = AssetIdentity(runtime.InitialStateJson);
        identity["runtimeMonoScript"] = AssetIdentity(runtimeScript);
        identity["readoutMonoScript"] = AssetIdentity(readoutScript);
__RECIPE_BINDING_IDENTITY__
        identity["hpListener"] = PersistentEventIdentity(runtime.hpChanged);
        identity["comboListener"] = PersistentEventIdentity(runtime.comboChanged);
        return identity;
    }

    private static void VerifyEvent(ProbeDoubleEvent evt, CodeModuleProbeReadout target, string method)
    {
        if (evt == null || evt.GetPersistentEventCount() != 1 || evt.GetPersistentTarget(0) != target
            || evt.GetPersistentMethodName(0) != method)
            throw new InvalidOperationException("Persistent UnityEvent target/method differs from the saved contract.");
    }

    private static Dictionary<string, object> PersistentEventIdentity(ProbeDoubleEvent evt)
    {
        return new Dictionary<string, object> {
            ["count"] = evt.GetPersistentEventCount(),
            ["targetType"] = evt.GetPersistentTarget(0).GetType().FullName,
            ["method"] = evt.GetPersistentMethodName(0)
        };
    }

    private static Dictionary<string, object> AssetIdentity(UnityEngine.Object asset)
    {
        string guid; long localId;
        if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(asset, out guid, out localId))
            throw new InvalidOperationException("Asset GUID/localId readback failed.");
        if (String.IsNullOrEmpty(guid) || localId <= 0)
            throw new InvalidOperationException("Asset GUID/localId readback is empty or invalid.");
        return new Dictionary<string, object> {
            ["path"] = AssetDatabase.GetAssetPath(asset), ["guid"] = guid, ["localId"] = localId,
            ["type"] = asset.GetType().FullName
        };
    }

    private static void OnPlayModeStateChanged(PlayModeStateChange state)
    {
        if (!SessionState.GetBool(ActiveKey, false)) return;
        if (state == PlayModeStateChange.EnteredPlayMode) SessionState.SetString(PhaseKey, "play");
        else if (state == PlayModeStateChange.EnteredEditMode) SessionState.SetString(PhaseKey, "finish");
    }

    private static void RunPlayModeProbe()
    {
        try
        {
            EnsureReceipt();
            var runtime = UnityEngine.Object.FindAnyObjectByType<CodeModuleProbeRuntime>();
            if (runtime == null || !runtime.probeAwake || !runtime.probeOnEnable || runtime.State == null)
                throw new InvalidOperationException("PlayMode Awake/OnEnable did not initialize the adapter.");
            var state = runtime.State;
            var readout = runtime.Readout;
            if (state.atk != 10d || state.combo != 0d || state.currHp != 80d || state.def != 1d
                || state.delta != 0d || state.maxHp != 100d)
                throw new InvalidOperationException("JSON fixture did not initialize the expected typed state.");
            state.DoDelta(-10d);
            if (state.currHp != 79d || readout.hpCallbacks != 1 || readout.lastHp != 79d)
                throw new InvalidOperationException("DoDelta or persistent HP callback did not match expected fixture behavior.");
            state.DoDelta(10d);
            if (state.currHp != 89d || readout.hpCallbacks != 2 || readout.lastHp != 89d)
                throw new InvalidOperationException("Positive DoDelta/callback did not match expected fixture behavior.");
            state.MaxHpDoDelta(20d);
            if (state.currHp != 109d || state.maxHp != 120d || readout.hpCallbacks != 3 || readout.lastHp != 109d)
                throw new InvalidOperationException("MaxHpDoDelta/callback did not match expected fixture behavior.");
            state.ComboDoDelta(3d);
            if (state.combo != 3d || readout.comboCallbacks != 1 || readout.lastCombo != 3d)
                throw new InvalidOperationException("ComboDoDelta/callback did not match expected fixture behavior.");
            state.clearCombo();
            if (state.combo != 0d) throw new InvalidOperationException("clearCombo did not reset combo.");
            if (Math.Abs(state.getPercent() - (109d / 120d)) > 1e-9)
                throw new InvalidOperationException("getPercent differs from expected fixture behavior.");
            state.SetProperty(160d, 33d);
            if (state.maxHp != 160d || state.currHp != 160d || state.atk != 33d)
                throw new InvalidOperationException("SetProperty differs from expected fixture behavior.");
__RECIPE_PLAY__
            var playResult = new Dictionary<string, object> {
                ["status"] = "passed", ["awake"] = runtime.probeAwake, ["onEnable"] = runtime.probeOnEnable,
                ["hpCallbacks"] = readout.hpCallbacks, ["lastHp"] = readout.lastHp,
                ["comboCallbacks"] = readout.comboCallbacks, ["lastCombo"] = readout.lastCombo,
                ["finalState"] = new Dictionary<string, object> {
                    ["atk"] = state.atk, ["combo"] = state.combo, ["currHp"] = state.currHp,
                    ["def"] = state.def, ["delta"] = state.delta, ["maxHp"] = state.maxHp,
                    ["percentBeforeSetProperty"] = 109d / 120d
                }
            };
__RECIPE_PLAY_RECEIPT__
            UnityEngine.Object.DestroyImmediate(runtime);
            if (state.onHpChange != null || state.onComboChange != null)
                throw new InvalidOperationException("Destroyed adapter retained state callback subscriptions.");
            playResult["onDestroyUnsubscribed"] = true;
            SessionState.SetString(PlayResultKey, ToJson(playResult));
            receipt["playMode"] = playResult;
            EditorApplication.isPlaying = false;
        }
        catch (Exception error) { Fail(error); }
    }

    private static void FinishAfterPlay()
    {
        try
        {
            var project = SessionState.GetString(ProjectKey, "");
            Directory.SetCurrentDirectory(project);
            var scene = EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            if (!scene.IsValid() || !scene.isLoaded) throw new InvalidOperationException("Scene did not reopen after PlayMode.");
            EnsureReceipt();
            receipt["savedBindingsAfterPlay"] = VerifySavedSceneAndBindings();
            receipt["validationStatus"] = new Dictionary<string, object> {
                ["compiled"] = "passed", ["unityBinding"] = "passed", ["playMode"] = "passed",
                ["render"] = "not_run", ["physicalInput"] = "not_run", ["playerBuild"] = "not_run"
            };
            receipt["finishedUtc"] = DateTime.UtcNow.ToString("o");
            WriteReceipt(true, null);
            SessionState.SetBool(ActiveKey, false);
            EditorApplication.Exit(0);
        }
        catch (Exception error) { Fail(error); }
    }

    private static void CheckTimeout()
    {
        if (!SessionState.GetBool(ActiveKey, false)) return;
        DateTime started;
        if (!DateTime.TryParse(SessionState.GetString(StartedKey, ""), out started)) return;
        if ((DateTime.UtcNow - started).TotalSeconds > 900d)
        {
            Fail(new TimeoutException("Code module probe exceeded its 900 second method bound."));
            return;
        }
        // Editor delayCall is a shared one-shot multicast; an unrelated startup
        // callback exception can discard subsequent callbacks. Resume explicitly
        // from the persisted phase on a later update after each domain reload.
        if (EditorApplication.isCompiling || EditorApplication.isUpdating) return;
        var phase = SessionState.GetString(PhaseKey, "");
        if (phase == "play" && EditorApplication.isPlaying)
        {
            SessionState.EraseString(PhaseKey);
            RunPlayModeProbe();
        }
        else if (phase == "finish" && !EditorApplication.isPlayingOrWillChangePlaymode)
        {
            SessionState.EraseString(PhaseKey);
            FinishAfterPlay();
        }
    }

    private static void Fail(Exception error)
    {
        try
        {
            EnsureReceipt();
            receipt["status"] = "failed";
            receipt["errorType"] = error.GetType().FullName;
            receipt["error"] = error.Message;
            receipt["finishedUtc"] = DateTime.UtcNow.ToString("o");
            var receiptPath = SessionState.GetString(ReceiptKey, Path.GetFullPath("code-native-probe-receipt.json"));
            if (!File.Exists(receiptPath)) WriteReceipt(false, error.Message);
        }
        finally
        {
            SessionState.SetBool(ActiveKey, false);
            EditorApplication.Exit(1);
        }
    }

    private static void WriteReceipt(bool success, string error)
    {
        receipt["status"] = success ? "passed" : "failed";
        receipt["render"] = "not_run";
        receipt["physicalInput"] = "not_run";
        receipt["playerBuild"] = "not_run";
        var path = SessionState.GetString(ReceiptKey, Path.GetFullPath("code-native-probe-receipt.json"));
        File.WriteAllText(path, ToJson(receipt));
    }

    private static void EnsureReceipt()
    {
        if (receipt != null) return;
        var project = SessionState.GetString(ProjectKey, "");
        if (!String.IsNullOrEmpty(project) && Directory.Exists(project)) Directory.SetCurrentDirectory(project);
        receipt = new Dictionary<string, object>();
        receipt["schemaVersion"] = 1;
        receipt["unityVersion"] = Application.unityVersion;
        receipt["startedUtc"] = SessionState.GetString(StartedKey, "");
        receipt["sourceExecuted"] = false;
        receipt["sourceCodeExecuted"] = false;
        receipt["originalConstructorClaimed"] = false;
        receipt["candidateManifestSha256"] = CandidateManifestSha256;
        receipt["codeModulesReportSha256"] = CodeModulesReportSha256;
        receipt["probePlanSha256"] = FileSha256("code-native-probe-plan.json");
        receipt["savedSceneReopened"] = SessionState.GetBool(SceneSavedKey, false);
        receipt["render"] = "not_run";
        receipt["physicalInput"] = "not_run";
        receipt["playerBuild"] = "not_run";
        var bindings = SessionState.GetString(BindingsBeforeKey, "");
        var play = SessionState.GetString(PlayResultKey, "");
        if (!String.IsNullOrEmpty(bindings)) receipt["savedBindingsBeforePlay"] = new RawJson(bindings);
        if (!String.IsNullOrEmpty(play)) receipt["playMode"] = new RawJson(play);
    }

    private sealed class RawJson
    {
        public readonly string text;
        public RawJson(string value) { text = value; }
    }

    private static string ToJson(object value)
    {
        if (value == null) return "null";
        var raw = value as RawJson;
        if (raw != null) return raw.text;
        var text = value as string;
        if (text != null) return "\"" + Escape(text) + "\"";
        if (value is bool) return (bool)value ? "true" : "false";
        if (value is Dictionary<string, object>)
        {
            var rows = (Dictionary<string, object>)value;
            return "{" + String.Join(",", rows.OrderBy(x => x.Key).Select(x => "\"" + Escape(x.Key) + "\":" + ToJson(x.Value))) + "}";
        }
        if (value is IEnumerable<object>) return "[" + String.Join(",", ((IEnumerable<object>)value).Select(ToJson)) + "]";
        if (value is IFormattable) return ((IFormattable)value).ToString(null, System.Globalization.CultureInfo.InvariantCulture);
        return "\"" + Escape(value.ToString()) + "\"";
    }

    private static string Escape(string value)
    {
        var result = new StringBuilder(value.Length + 8);
        foreach (var character in value)
        {
            switch (character)
            {
                case '\\': result.Append("\\\\"); break;
                case '"': result.Append("\\\""); break;
                case '\r': result.Append("\\r"); break;
                case '\n': result.Append("\\n"); break;
                case '\t': result.Append("\\t"); break;
                default:
                    if (character < 0x20) result.Append("\\u" + ((int)character).ToString("x4"));
                    else result.Append(character);
                    break;
            }
        }
        return result.ToString();
    }

    private static string FileSha256(string path)
    {
        using (var sha = SHA256.Create())
        using (var stream = File.OpenRead(path))
            return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
    }
}
'''
    snippets = {
        "__RECIPE_CONSTANTS__": ("    private const string RecipeJsonPath = \"" + RECIPE_JSON + "\";\n"
                                  "    private const string RecipeJsonSha256 = \"" + EXPECTED_RECIPE_JSON_SHA256 + "\";\n"
                                  "    private const string RecipeJsonGuid = \"" + (recipe_guid or "") + "\";\n" if recipe_module else ""),
        "__RECIPE_ASSIGN__": ("        serialized.FindProperty(\"recipeTable\").objectReferenceValue = AssetDatabase.LoadAssetAtPath<TextAsset>(RecipeJsonPath);" if recipe_module else ""),
        "__RECIPE_BINDING_IDENTITY__": ("        if (runtime.RecipeTable == null) throw new InvalidOperationException(\"Reopened scene lost recipe TextAsset binding.\");\n"
                                        "        identity[\"recipeTextAsset\"] = AssetIdentity(runtime.RecipeTable);\n"
                                        "        identity[\"recipeJsonSha256\"] = FileSha256(AssetDatabase.GetAssetPath(runtime.RecipeTable));\n"
                                        "        if ((string)identity[\"recipeJsonSha256\"] != RecipeJsonSha256 || (string)((Dictionary<string, object>)identity[\"recipeTextAsset\"])[\"guid\"] != RecipeJsonGuid) throw new InvalidOperationException(\"Bound recipe JSON identity differs.\");"
                                        if recipe_module else ""),
        "__RECIPE_PLAY__": ("            var leaves = RecipeCatalog.FlattenIngredientsOf(2015015d);\n"
                            "            double[] expectedLeaves = new double[] { " + ", ".join(str(x) + "d" for x in RECIPE_LEAVES_2015015) + " };\n"
                            "            if (leaves.Count != expectedLeaves.Length) throw new InvalidOperationException(\"Recipe flatten leaf count differs.\");\n"
                            "            for (int i = 0; i < expectedLeaves.Length; i++) if (leaves[i] != expectedLeaves[i]) throw new InvalidOperationException(\"Recipe flatten order/value differs at index \" + i);\n"
                            "            receipt[\"recipeJsonSha256\"] = FileSha256(RecipeJsonPath);\n"
                            "            receipt[\"recipeTableRows\"] = 732;\n"
                            "            receipt[\"recipeFlatten2015015\"] = new List<object> { " + ", ".join(str(x) + "d" for x in RECIPE_LEAVES_2015015) + " };\n" if recipe_module else ""),
        "__RECIPE_PLAY_RECEIPT__": ("            playResult[\"recipeFlatten2015015\"] = new List<object> { " + ", ".join(str(x) + "d" for x in RECIPE_LEAVES_2015015) + " };\n" if recipe_module else ""),
    }
    for marker, value in snippets.items():
        template = template.replace(marker, value)
    return template.replace("__CANDIDATE_MANIFEST_SHA256__", manifest_sha256).replace(
        "__CODE_MODULES_REPORT_SHA256__", code_report_sha256)
