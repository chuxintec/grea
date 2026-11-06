import json

import pytest

from monkey.io import sha
from monkey.native_selection import _carrier_profiles, _template_profile
from monkey.prefab_static_carriers import _unity_script
from monkey.sources.compiled import ParseError


def fixture(root):
    root = root.resolve()
    script = "Assets/Scripts/StaticFields_Example.cs"
    fields = [{"fieldName": "value", "storageType": "UnityEngine.Object"}]
    raw = _unity_script("Monkey.Example", "StaticFields_Example", fields).encode()
    binding = dict(scriptPath=script, scriptSha256=sha(raw), typeName="Monkey.Example.StaticFields_Example",
                   behavior="disabled", enabled=False, fields=fields)
    plan_path = "Assets/Game/Editor/Conversion/import-plan.json"
    plan = json.dumps(dict(components=[dict(staticFieldBinding=binding)])).encode()
    for path, data in ((plan_path, plan), (script, raw)):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    rows = {path: dict(sha256=sha(data), bytes=len(data)) for path, data in ((plan_path, plan), (script, raw))}
    return root, rows, dict(projectLayout="monkey-project/2.0.0"), script, plan_path


def test_exact_carrier_regeneration_proves_framework_only_dependency(tmp_path):
    root, rows, manifest, script, _ = fixture(tmp_path)
    profiles, evidence = _carrier_profiles(root, rows, manifest)
    assert profiles == {script: ("StaticFields_Example.cs", ())}
    assert evidence["behaviorRecovered"] is False


def test_modified_code_is_not_exempted_by_carrier_filename(tmp_path):
    root, rows, manifest, script, _ = fixture(tmp_path)
    rows[script]["sha256"] = sha(b"injected runtime behavior")
    assert _carrier_profiles(root, rows, manifest)[0] == {}


def test_carrier_plan_drift_rejected(tmp_path):
    root, rows, manifest, _, plan = fixture(tmp_path)
    (root / plan).write_text("{}")
    with pytest.raises(ParseError, match="IMPORT_PLAN_DRIFT"):
        _carrier_profiles(root, rows, manifest)


@pytest.mark.parametrize("change", ["callback", "identifier", "enabled"])
def test_rehashed_plan_cannot_authorize_behavior_or_injected_identifiers(tmp_path, change):
    root, rows, manifest, _, plan = fixture(tmp_path)
    payload = json.loads((root / plan).read_text())
    binding = payload["components"][0]["staticFieldBinding"]
    if change == "callback":
        binding["behavior"] = "recovered"
    elif change == "identifier":
        binding["fields"][0]["fieldName"] = "value; void Update() {} //"
    else:
        binding["enabled"] = True
    raw = json.dumps(payload).encode()
    (root / plan).write_bytes(raw)
    rows[plan] = dict(sha256=sha(raw), bytes=len(raw))
    assert _carrier_profiles(root, rows, manifest)[0] == {}


def test_framework_leaf_requires_exact_bundled_bytes():
    from pathlib import Path
    helper = Path(__file__).parents[1] / "src/monkey/targets/NativeLinearLayoutGroup.cs"
    assert _template_profile(helper.name, sha(helper.read_bytes())) == (helper.name, ())
    assert _template_profile(helper.name, sha(helper.read_bytes() + b"// changed")) is None


@pytest.mark.parametrize("changed", [False, True])
def test_supplement_binds_actual_target_and_preserves_original_warning(tmp_path, changed):
    from monkey.native_code_dependencies import audit
    root, rows, source_manifest, script, _ = fixture(tmp_path / "producer")
    source_manifest.update(targetProfile="unity-6000.6.2f1-ugui",
                           files=[dict(path=p, **r) for p, r in rows.items()])
    source_raw = json.dumps(source_manifest).encode()
    (root / "manifest.json").write_bytes(source_raw)
    target = tmp_path / "target"
    target.mkdir()
    data = (root / script).read_bytes() + (b"// changed" if changed else b"")
    payloads = {script: data, "Packages/manifest.json": b"{}", "Packages/packages-lock.json": b"{}"}
    for p, raw in payloads.items():
        path = target / p
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    warning = dict(path=script, code="UNANALYZED_CSHARP_DEPENDENCIES")
    original = json.dumps(dict(targetProfile="unity-6000.6.2f1-ugui",
        sourceCandidateManifestSha256=sha(source_raw), diagnostics=[warning],
        files=[dict(path=p, sha256=sha(raw), bytes=len(raw)) for p, raw in payloads.items()])).encode()
    (target / "manifest.json").write_bytes(original)
    result = audit(target, sha(original), root, sha(source_raw), tmp_path / "proof")
    assert result["originalDiagnostics"] == [warning]
    assert len(result["uncovered"]) == int(changed)
    assert (target / "manifest.json").read_bytes() == original
    if not changed:
        assert result["scripts"][0]["sha256"] == sha(data)
        assert result["carrierPlanEvidence"]["sha256"] == rows["Assets/Game/Editor/Conversion/import-plan.json"]["sha256"]
