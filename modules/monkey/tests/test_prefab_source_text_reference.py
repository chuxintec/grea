import base64
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import pytest

from monkey import prefab_source_text_reference as reference
from monkey import prefab_static_text_continuation as text_module


LABEL_ID = "fixture:root#0/components/0"
OUTLINE_ID = "fixture:root#0/components/1"
NODE_ID = "fixture:root#0"
TEXT = "继续"
FONT_ID = "fixture-font"
FONT_PATH = "Assets/Fonts/fixture.asset"


def _dump(path, value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(raw)
    return raw


@pytest.fixture
def fixture_inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(text_module, "_SOURCE_ENGINE_PINS", {})
    evidence_path = tmp_path / "engine-evidence.json"
    evidence = {"sourceVersion": "2.4.15", "sourceProfile": "cocos-2.4.15-bundle", "files": []}
    evidence_raw = _dump(evidence_path, evidence)
    label_raw = {"__type__": "cc.Label", "_string": TEXT, "_fontSize": 44, "_lineHeight": 44,
                 "_N$overflow": 2, "_enableWrapText": False, "_styleFlags": 1,
                 "_isSystemFontUsed": True, "_N$file": None, "node": {"__id__": 0}}
    outline_raw = {"__type__": "cc.LabelOutline", "_width": 5,
                   "_color": {"__value_type__": 4, "values": [0xff177750]}, "node": {"__id__": 0}}
    node_raw = {"__type__": "cc.Node", "_contentSize": {"__value_type__": 5, "values": [200, 80]},
                "_components": [label_raw, outline_raw]}
    manifest = {"schemaVersion": 1, "sourceProfile": "cocos-2.4.15-bundle", "sourceVersion": "2.4.15",
                "assets": [{"sourceId": "fixture:root", "kind": "cc.Prefab",
                            "document": {"instances": [node_raw]}}]}
    manifest_path = tmp_path / "source-manifest.json"
    manifest_raw = _dump(manifest_path, manifest)
    label_ir = {"sourceId": LABEL_ID, "node": NODE_ID, "type": "cc.Label", "text": TEXT,
                "fontSize": 44, "lineHeight": 44, "overflow": 2, "wrap": False,
                "bold": True, "italic": False, "underline": False, "font": None,
                "fontFamily": "Arial", "fontFamilyEvidence": "creator-label-default-Arial",
                "systemFont": True, "enabled": True}
    outline_ir = {"sourceId": OUTLINE_ID, "node": NODE_ID, "type": "cc.LabelOutline", "width": 5,
                  "outlineColor": [80, 119, 23, 255], "enabled": True}
    ir = {"sourceProfile": "cocos-2.4.15-bundle", "sourceManifestSha256": hashlib.sha256(manifest_raw).hexdigest(),
          "components": [label_ir, outline_ir]}
    ir_path = tmp_path / "source-ir.json"
    ir_raw = _dump(ir_path, ir)
    binding = {"sourceLabelId": LABEL_ID, "sourceSystemFont": True, "sourceText": TEXT,
               "sourceFontFamily": "Arial", "sourceFontFamilyEvidence": "creator-label-default-Arial",
               "pointSize": 44.0, "nativeFontAssetId": FONT_ID, "nativeFontAssetPath": FONT_PATH,
               "nativeFallbackAssetIds": [], "nativeFallbackAssetPaths": []}
    plan = {"projectLayout": "monkey-project/2.0.0", "sourceProfile": "cocos-2.4.15-bundle",
            "sourceManifestSha256": hashlib.sha256(manifest_raw).hexdigest(),
            "sourceIrSha256": hashlib.sha256(ir_raw).hexdigest(),
            "components": [dict(label_ir, sourceFont=None, nativeSystemFontBinding=binding,
                                nativeTextStylePolicy="tmp-font-style-flags-v1", convertible=False),
                           dict(outline_ir, convertible=False)],
            "nodes": [{"sourceId": NODE_ID, "size": [200, 80], "anchor": [0.5, 0.5],
                       "color": [255, 255, 255, 255]}],
            "systemFontBinding": {"labelBindings": [binding],
                                  "systemFonts": {"fonts": [{"assetId": FONT_ID, "assetPath": FONT_PATH,
                                                              "requiredGlyphs": [{"character": c} for c in TEXT]}]}},
            "staticFontInputs": {"status": "staged", "copies": [
                {"artifactKind": "glyph-atlas"}, {"artifactKind": "glyph-metrics"},
                {"artifactKind": "portable-generation-receipt"}]}, "bitmapFonts": [], "assets": [], "copies": []}
    plan_result = text_module.prepare(plan, ir, manifest, tmp_path, source_evidence=evidence)
    plan_path = tmp_path / "source-plan.json"
    plan_raw = _dump(plan_path, plan_result["plan"])
    runtime_path = tmp_path / "cocos-runtime.js"
    runtime_raw = b"// synthetic pinned Cocos 2.4.15 runtime fixture"
    runtime_path.write_bytes(runtime_raw)
    request = {
        "schemaVersion": 1, "contract": reference.SCHEMA, "sourceVersion": "2.4.15",
        "sourcePlan": {"path": str(plan_path), "sha256": hashlib.sha256(plan_raw).hexdigest()},
        "sourceIr": {"path": str(ir_path), "sha256": hashlib.sha256(ir_raw).hexdigest()},
        "sourceManifest": {"path": str(manifest_path), "sha256": hashlib.sha256(manifest_raw).hexdigest()},
        "sourceEngineEvidence": {"path": str(evidence_path), "sha256": hashlib.sha256(evidence_raw).hexdigest()},
        "cocosRuntime": {"path": str(runtime_path), "sha256": hashlib.sha256(runtime_raw).hexdigest(),
                         "bytes": len(runtime_raw), "engineVersion": "2.4.15"},
        "viewport": {"width": 640, "height": 360, "devicePixelRatio": 1},
        "sourceIds": [LABEL_ID],
    }
    request_path = tmp_path / "request.json"
    request_raw = _dump(request_path, request)
    return {"root": tmp_path, "request": request, "requestPath": request_path,
            "requestSha": hashlib.sha256(request_raw).hexdigest(), "runtimePath": runtime_path}


def test_prepares_single_pinned_source_case_and_offline_runner(fixture_inputs, tmp_path):
    result = reference.prepare(fixture_inputs["requestPath"], fixture_inputs["requestSha"], tmp_path / "prepared")
    assert result["status"] == "prepared"
    assert result["sourceCaseCount"] == 1
    prep = json.loads(Path(result["preparation"]).read_text())
    runner = Path(result["runner"]).read_text()
    assert prep["originalDeviceEquivalence"] == "not-claimed"
    assert prep["cases"][0]["sourceText"] == TEXT
    assert "cc.ENGINE_VERSION" in runner and "node.addComponent(cc.Label)" in runner
    assert "cc.LabelOutline" in runner and "cc.game.run(explicitGameConfig,cc.game.onStart)" in runner
    assert "main.js" not in runner and "game business" not in runner.lower()
    assert (Path(result["runner"]).parent / prep["cocosRuntime"]["path"]).read_bytes() == fixture_inputs["runtimePath"].read_bytes()


def test_requires_exactly_one_explicit_source_id(fixture_inputs, tmp_path):
    bad = dict(fixture_inputs["request"], sourceIds=[])
    raw = _dump(fixture_inputs["root"] / "bad-request.json", bad)
    with pytest.raises(reference.SourceTextReferenceError, match="REQUIRES_ONE_EXPLICIT_SOURCE_ID"):
        reference.prepare(fixture_inputs["root"] / "bad-request.json", hashlib.sha256(raw).hexdigest(), tmp_path / "bad-out")


def test_rejects_runtime_byte_drift(fixture_inputs, tmp_path):
    fixture_inputs["runtimePath"].write_bytes(b"changed runtime")
    with pytest.raises(reference.SourceTextReferenceError, match="cocosRuntime bytes differ"):
        reference.prepare(fixture_inputs["requestPath"], fixture_inputs["requestSha"], tmp_path / "bad-runtime")


def test_headless_capture_pins_actual_engine_row_and_rasters(fixture_inputs, tmp_path, monkeypatch):
    prepared = reference.prepare(fixture_inputs["requestPath"], fixture_inputs["requestSha"], tmp_path / "prepared")
    browser = tmp_path / "fake-chrome"
    browser.write_text("fixture executable")
    browser.chmod(0o755)
    tiny_png = base64.b64encode(b"PNG fixture").decode()
    captured_row = {
        "sourceLabelId": LABEL_ID, "sourceOutlineId": OUTLINE_ID, "sourceNodeId": NODE_ID,
        "sourceText": TEXT, "sourceTextSha256": hashlib.sha256(TEXT.encode()).hexdigest(),
        "measureText": {"width": 42.0}, "lines": [{"text": TEXT, "width": 42.0}],
        "actualFontSize": 44, "rasterDataUrl": "data:image/png;base64," + tiny_png,
    }
    page_result = {"status": "captured", "contract": "monkey-cocos-source-text-reference-capture/1",
                   "sourceVersion": "2.4.15", "sourceManifestSha256": prep_sha(prepared),
                   "actualRendererType": "canvas",
                   "browser": {"devicePixelRatio": 1, "innerWidth": 640, "innerHeight": 360},
                   "cases": [captured_row]}
    # Replace page's manifest pin with the exact prepared input pin.
    prep = json.loads(Path(prepared["preparation"]).read_text())
    page_result["sourceManifestSha256"] = prep["sourceManifestSha256"]
    stdout = '<body data-source-reference-result="' + quote(json.dumps(page_result, ensure_ascii=False), safe="") + '"></body>'

    def fake_run(args, **kwargs):
        if "--version" in args:
            return SimpleNamespace(returncode=0, stdout="Chrome fixture 1", stderr="")
        if any(arg.startswith("data:text/html,") for arg in args):
            return SimpleNamespace(returncode=0,
                stdout='<body data-source-reference-viewport="640,360"></body>', stderr="")
        screenshot = next(arg.split("=", 1)[1] for arg in args if arg.startswith("--screenshot="))
        Path(screenshot).write_bytes(b"browser screenshot")
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(reference.subprocess, "run", fake_run)
    result = reference.capture(prepared["preparation"], prepared["preparationSha256"], browser, tmp_path / "capture")
    assert result["status"] == "captured"
    report = json.loads(Path(result["capture"]).read_text())
    assert report["browserVersion"] == "Chrome fixture 1"
    assert report["browserWindowCalibration"]["status"] == "measured-and-adjusted"
    assert report["cases"][0]["sourceLabelId"] == LABEL_ID
    assert report["labelRasterFiles"][0]["sha256"] == hashlib.sha256(b"PNG fixture").hexdigest()
    assert report["originalDeviceEquivalence"] == "not-claimed"


def prep_sha(prepared):
    return json.loads(Path(prepared["preparation"]).read_text())["sourceManifestSha256"]
