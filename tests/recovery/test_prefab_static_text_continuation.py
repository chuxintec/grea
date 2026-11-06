import hashlib
import json
from pathlib import Path

import pytest

from grea.recovery import prefab_static_text_continuation as text_module


TEXT_ID = "fixture:root#0/components/0"
OUTLINE_ID = "fixture:root#0/components/1"
NODE_ID = "fixture:root#0"
TEXT = "继续"
PRIMARY_ID = "system-font-primary"
FALLBACK_ID = "coretext-static-sdf-fallback"
PRIMARY_PATH = "Assets/Fonts/primary.asset"
FALLBACK_PATH = "Assets/Fonts/fallback.asset"


@pytest.fixture
def engine_evidence(tmp_path, monkeypatch):
    pins = {logical: hashlib.sha256(("fixture:" + logical).encode()).hexdigest()
            for logical in text_module._SOURCE_ENGINE_PINS}
    monkeypatch.setattr(text_module, "_SOURCE_ENGINE_PINS", pins)
    files = []
    for logical, digest in pins.items():
        path = tmp_path / Path(logical).name
        raw = ("fixture:" + logical).encode()
        path.write_bytes(raw)
        files.append({"logicalPath": logical, "path": str(path), "sha256": digest,
                      "bytes": len(raw), "originUrl": text_module._RAW_BASE + logical})
    return {"sourceProfile": text_module.SOURCE_PROFILE, "sourceVersion": text_module.SOURCE_VERSION, "files": files}


def fixture_documents(*, font_kind="system-font", overflow=2, wrap=False):
    label_raw = {
        "__type__": "cc.Label", "_string": TEXT, "_fontSize": 44, "_lineHeight": 44,
        "_N$overflow": overflow, "_enableWrapText": wrap, "_styleFlags": 1,
        "node": {"__id__": 0},
    }
    if font_kind == "system-font":
        label_raw["_isSystemFontUsed"] = True
        label_raw["_N$file"] = None
        font = None
        system_font = True
        binding = {
            "sourceLabelId": TEXT_ID, "sourceSystemFont": True, "sourceFontFamily": "Arial",
            "sourceFontFamilyEvidence": "official-source-default", "sourceText": TEXT,
            "pointSize": 44.0, "nativeFontAssetId": PRIMARY_ID, "nativeFontAssetPath": PRIMARY_PATH,
            "nativeFallbackAssetIds": [FALLBACK_ID], "nativeFallbackAssetPaths": [FALLBACK_PATH],
            "resolvedPrimaryFamily": "Arial", "resolvedPrimaryStyleName": "Regular",
            "resolvedFallbackFaces": [{"familyName": "PingFang SC", "styleName": "Regular"}],
        }
        system_fonts = [{"assetId": PRIMARY_ID, "assetPath": PRIMARY_PATH, "requiredGlyphs": []},
                        {"assetId": FALLBACK_ID, "assetPath": FALLBACK_PATH,
                         "requiredGlyphs":[{"character": char} for char in TEXT]}]
        bitmap_fonts = []
        native_font_binding = binding
    else:
        label_raw["_isSystemFontUsed"] = False
        label_raw["_N$file"] = "bitmap-font-id"
        font = "bitmap-font-id"
        system_font = False
        bitmap_fonts = [{"id": font, "fontPath": "Assets/Fonts/bitmap.asset",
                         "atlasGuid": "0123456789abcdef0123456789abcdef",
                         "glyphs": [{"unicode": ord(char)} for char in TEXT]}]
        system_fonts = []
        native_font_binding = None
    outline_raw = {
        "__type__": "cc.LabelOutline", "_width": 5,
        "_color": {"__value_type__": 4, "values": [0xff177750]},
        "node": {"__id__": 0},
    }
    node_raw = {"__type__": "cc.Node", "_name": "label-node",
                "_contentSize": {"__value_type__": 5, "values": [200, 80]},
                "_components": [label_raw, outline_raw]}
    manifest = {
        "schemaVersion": 1, "sourceProfile": text_module.SOURCE_PROFILE, "sourceVersion": text_module.SOURCE_VERSION,
        "assets": [{"sourceId": "fixture:root", "kind": "cc.Prefab", "document": {"instances": [node_raw]}}],
    }
    label_ir = {
        "sourceId": TEXT_ID, "node": NODE_ID, "type": "cc.Label", "text": TEXT,
        "fontSize": 44, "lineHeight": 44, "overflow": overflow, "wrap": wrap,
        "bold": True, "italic": False, "underline": False, "font": font,
        "fontFamily": "Arial", "fontFamilyEvidence": "creator-label-default-Arial",
        "systemFont": system_font, "enabled": True,
    }
    outline_ir = {
        "sourceId": OUTLINE_ID, "node": NODE_ID, "type": "cc.LabelOutline", "width": 5,
        "outlineColor": [80, 119, 23, 255], "enabled": True,
    }
    plan_label = dict(label_ir, sourceFont=font, font=PRIMARY_ID if font_kind == "system-font" else font,
                      convertible=False, nativeId="label-native", nativeTextStylePolicy="tmp-font-style-flags-v1")
    if native_font_binding:
        plan_label["nativeSystemFontBinding"] = native_font_binding
    outline = dict(outline_ir, convertible=False, nativeId="outline-native")
    plan = {
        "projectLayout": "monkey-project/2.0.0", "sourceProfile": text_module.SOURCE_PROFILE,
        "sourceManifestSha256": "a" * 64, "sourceIrSha256": "b" * 64,
        "sourcePrefabs": [{"sourceId": "fixture:root"}],
        "components": [plan_label, outline],
        "nodes": [{"sourceId": NODE_ID, "size": [200, 80], "anchor": [0.5, 0.5],
                   "color": [255, 255, 255, 255], "position": [0, 0], "scale": [1, 1, 1]}],
        "bitmapFonts": bitmap_fonts,
        "assets": [],
        "systemFontBinding": {"labelBindings": [native_font_binding] if native_font_binding else [],
                              "systemFonts": {"fonts": system_fonts}},
        "staticFontInputs": {"status": "staged", "copies": [
            {"artifactKind": "glyph-atlas"}, {"artifactKind": "glyph-metrics"},
            {"artifactKind": "portable-generation-receipt"}]},
        "copies": [{"sourceId": "keep-me", "source": "resources/unchanged.bin", "target": "Assets/unchanged.bin"}],
    }
    ir = {"sourceProfile": text_module.SOURCE_PROFILE, "sourceManifestSha256": "a" * 64,
          "components": [label_ir, outline_ir]}
    return plan, ir, manifest


def test_prepares_system_font_shrink_and_outline_without_claiming_visual_parity(tmp_path, engine_evidence):
    plan, ir, manifest = fixture_documents()
    before = json.dumps(plan, sort_keys=True)
    result = text_module.prepare(plan, ir, manifest, tmp_path, source_evidence=engine_evidence)
    group = result["continuation"]["components"][0]
    assert group["sourceLabelId"] == TEXT_ID
    assert group["sourceOutlineId"] == OUTLINE_ID
    assert group["sourceText"] == TEXT
    assert group["layoutPolicy"]["shrinkPolicy"] == "unwrapped-scale-floor-v2.4.15"
    assert group["layoutPolicy"]["targetAutoSizing"] is True
    assert group["layoutPolicy"]["targetAutoSizeMin"] == 0.0
    assert group["layoutPolicy"]["targetAutoSizeMax"] == 44.0
    assert group["sourceCanvasMeasurement"]["status"] == "source-canvas-context-and-measureText-unavailable"
    assert group["sourceRasterization"]["status"] == "unknown-source-platform-and-renderer"
    assert result["summary"]["sourceMetricWarningsResolved"] is False
    assert result["plan"]["components"][0]["convertible"] is True
    assert result["plan"]["components"][1]["staticPresentationPolicy"] == "source-evidenced-native-renderer-v1"
    assert result["plan"]["copies"] == plan["copies"]
    assert json.dumps(plan, sort_keys=True) == before
    assert set(tmp_path.iterdir()) == {Path(row["path"]) for row in engine_evidence["files"]}


def test_keeps_bitmap_outline_distinct_from_ttf_system_outline(tmp_path, engine_evidence):
    plan, ir, manifest = fixture_documents(font_kind="bitmap", overflow=2, wrap=False)
    result = text_module.prepare(plan, ir, manifest, tmp_path, source_evidence=engine_evidence)
    group = result["continuation"]["components"][0]
    assert group["fontKind"] == "bitmap-font"
    assert group["layoutPolicy"]["profile"] == "cocos-2.4.15-bitmap-label-v1"
    assert group["layoutPolicy"]["targetAutoSizing"] is False
    assert group["layoutPolicy"]["sourceShrinkLowerBound"] == 0.1
    assert result["plan"]["components"][1]["staticBitmapOutline"] is True


def test_does_not_select_outline_when_native_font_binding_is_incomplete(tmp_path, engine_evidence):
    plan, ir, manifest = fixture_documents()
    plan["components"][0]["nativeSystemFontBinding"]["nativeFallbackAssetPaths"] = []
    result = text_module.prepare(plan, ir, manifest, tmp_path, source_evidence=engine_evidence)
    assert result["continuation"]["components"] == []
    assert result["continuation"]["gaps"][0]["code"] == "STATIC_TEXT_NATIVE_FONT_BINDING_INCOMPLETE"
    assert result["plan"]["components"][0]["convertible"] is False


def test_rejects_source_field_drift_and_source_engine_bytes_change(tmp_path, engine_evidence):
    plan, ir, manifest = fixture_documents()
    ir["components"][0]["wrap"] = True
    result = text_module.prepare(plan, ir, manifest, tmp_path, source_evidence=engine_evidence)
    assert result["continuation"]["components"] == []
    assert result["continuation"]["gaps"][0]["code"] == "STATIC_TEXT_PLAN_IR_FIELD_DRIFT:wrap"

    source = Path(engine_evidence["files"][0]["path"])
    source.write_bytes(b"tampered-source-engine")
    with pytest.raises(text_module.StaticTextContinuationError, match="SOURCE_ENGINE_BYTES_CHANGED"):
        text_module.prepare(plan, ir, manifest, tmp_path, source_evidence=engine_evidence)


def test_reports_ambiguous_same_node_label_without_promoting_either(tmp_path, engine_evidence):
    plan, ir, manifest = fixture_documents()
    duplicate = dict(plan["components"][0], sourceId="fixture:root#0/components/2")
    plan["components"].append(duplicate)
    ir["components"].append(dict(ir["components"][0], sourceId=duplicate["sourceId"]))
    result = text_module.prepare(plan, ir, manifest, tmp_path, source_evidence=engine_evidence)
    assert result["continuation"]["components"] == []
    assert result["continuation"]["gaps"][0]["code"] == "STATIC_TEXT_SAME_NODE_LABEL_OUTLINE_AMBIGUOUS"


def test_rejects_wrong_engine_version_and_unpinned_source_profile(tmp_path, engine_evidence):
    plan, ir, manifest = fixture_documents()
    bad_evidence = dict(engine_evidence, sourceVersion="2.4.14")
    with pytest.raises(text_module.StaticTextContinuationError, match="SOURCE_ENGINE_VERSION_UNSUPPORTED"):
        text_module.prepare(plan, ir, manifest, tmp_path, source_evidence=bad_evidence)
    with pytest.raises(text_module.StaticTextContinuationError, match="SOURCE_PROFILE_OR_VERSION_MISMATCH"):
        text_module.prepare(plan, ir, dict(manifest, sourceVersion="3.8.8"), tmp_path, source_evidence=engine_evidence)


def test_resolves_sync_component_origins_to_pinned_template_source(tmp_path, engine_evidence):
    plan, ir, manifest = fixture_documents()
    instance_label = "fixture:instance#7::sync-component-label"
    instance_outline = "fixture:instance#7::sync-component-outline"
    plan["components"][0]["sourceId"] = instance_label
    plan["components"][0]["nativeSystemFontBinding"]["sourceLabelId"] = instance_label
    plan["components"][1]["sourceId"] = instance_outline
    plan["systemFontBinding"]["labelBindings"][0]["sourceLabelId"] = instance_label
    plan["syncPrefabBindings"] = [{"componentOrigins": [
        {"instanceSourceId": instance_label, "templateSourceId": TEXT_ID},
        {"instanceSourceId": instance_outline, "templateSourceId": OUTLINE_ID},
    ]}]
    result = text_module.prepare(plan, ir, manifest, tmp_path, source_evidence=engine_evidence)
    assert len(result["continuation"]["components"]) == 1
    assert result["continuation"]["components"][0]["sourceLabelId"] == instance_label
    assert result["continuation"]["components"][0]["sourceOutlineId"] == instance_outline


def test_prepares_standalone_label_with_complete_font_binding(tmp_path, engine_evidence):
    plan, ir, manifest = fixture_documents()
    plan["components"] = plan["components"][:1]
    ir["components"] = ir["components"][:1]
    manifest["assets"][0]["document"]["instances"][0]["_components"] = \
        manifest["assets"][0]["document"]["instances"][0]["_components"][:1]
    result = text_module.prepare(plan, ir, manifest, tmp_path, source_evidence=engine_evidence)
    assert len(result["continuation"]["components"]) == 1
    assert result["continuation"]["components"][0]["sourceOutlineId"] is None
    assert len(result["continuation"]["componentDeltas"]) == 1


def test_layout_whitespace_does_not_require_visible_font_glyph_records(tmp_path, engine_evidence):
    plan, ir, manifest = fixture_documents()
    label = plan["components"][0]
    label["text"] = "继续\n "
    label["nativeSystemFontBinding"]["sourceText"] = label["text"]
    plan["systemFontBinding"]["labelBindings"][0]["sourceText"] = label["text"]
    for font in plan["systemFontBinding"]["systemFonts"]["fonts"]:
        font["requiredGlyphs"] = [{"character": char} for char in "继续"] if font["assetId"] == FALLBACK_ID else []
    ir["components"][0]["text"] = label["text"]
    manifest["assets"][0]["document"]["instances"][0]["_components"][0]["_string"] = label["text"]
    result = text_module.prepare(plan, ir, manifest, tmp_path, source_evidence=engine_evidence)
    assert result["continuation"]["components"][0]["sourceText"] == "继续\n "


def test_verifies_bound_saved_prefab_metrics_without_claiming_source_visual_parity(tmp_path, engine_evidence):
    plan, ir, manifest = fixture_documents()
    prepared = text_module.prepare(plan, ir, manifest, tmp_path, source_evidence=engine_evidence)
    candidate = tmp_path / "candidate"
    sidecar_path = candidate / "Analysis/Readback/TextMetrics" / \
        (hashlib.sha256(b"fixture:root").hexdigest() + ".json")
    sidecar_path.parent.mkdir(parents=True)
    group = prepared["continuation"]["components"][0]
    config_raw = prepared["plan"]["staticTextContinuationJson"].encode()
    row = {
        "sourceLabelId": TEXT_ID, "sourceOutlineId": OUTLINE_ID, "sourceNodeId": NODE_ID,
        "status": "native-configuration-metrics-verified", "fontKind": "system-font",
        "labelGuid": "a" * 32, "labelLocalFileId": 10, "outlineGuid": "b" * 32,
        "outlineNativeType": "NativeStaticTextOutline",
        "outlineLocalFileId": 11, "fontGuid": "c" * 32, "fontLocalFileId": 12,
        "persistentLabel": True, "persistentOutline": True,
        "sourceTextSha256": hashlib.sha256(TEXT.encode()).hexdigest(),
        "nativeText": TEXT, "nativeTextSha256": hashlib.sha256(TEXT.encode()).hexdigest(),
        "sourceTextMatches": True, "sourceStyleMatches": True,
        "nativeFontStyle": 1, "nativeOverflowMode": 0, "nativeWrappingMode": 0,
        "autoSizingConfigVerified": True, "fontBindingVerified": True,
        "glyphFontChainVerified": True, "lineHeightConfigVerified": True,
        "nativeFontAssetPath": PRIMARY_PATH, "nativeFontPointSize": 44,
        "nativeFaceLineHeight": 44, "nativeLineSpacing": 0,
        "nativeFontSizeMin": 0, "nativeFontSizeMax": 44, "actualFontSize": 44,
        "glyphFontAssets": [{"guid": "c" * 32, "localFileId": 12, "assetPath": PRIMARY_PATH}],
        "configuredFontAssets": [{"guid": "c" * 32, "localFileId": 12, "assetPath": PRIMARY_PATH},
                                 {"guid": "d" * 32, "localFileId": -13, "assetPath": FALLBACK_PATH}],
        "outlineConfigVerified": True, "outlineMaterialReadbackVerified": True,
        "nativeMeshMeasured": True, "inkBounds": {"hasVisibleGeometry": True},
        "nativeBoundsKind": "tmp-character-quad-local-bounds-not-pixel-ink",
        "sampleContext": "isolated-active-label-clone", "sourceNodeActiveSelf": True,
        "sourceNodeActiveInHierarchy": False, "sourceLabelEnabled": True,
        "sourceLabelEnabledUnchanged": True,
        "sampleCloneIsolated": True, "sampleAncestorActivationOverride": False,
        "sampleCloneActivationOverride": True, "sampleSourceAncestorInactive": True,
        "sampleStateRestored": True, "sourceActivityUnchanged": True,
        "sampleRectTransformVerified": True, "sampleCanvasReferencePixelsPerUnit": 100,
    }
    report = {
        "schemaVersion": 1, "contract": "monkey-static-text-metrics-readback/1",
        "phase": "saved-prefab-reopen", "sourceManifestSha256": plan["sourceManifestSha256"],
        "sourcePrefabId": "fixture:root", "continuationJsonSha256": hashlib.sha256(config_raw).hexdigest(),
        "status": "verified", "components": [row],
    }
    raw = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    sidecar_path.write_bytes(raw)
    relative = sidecar_path.relative_to(candidate).as_posix()
    result = text_module.verify(prepared["plan"], candidate, {
        "staticTextReadbackFiles": [{"path": relative, "sha256": hashlib.sha256(raw).hexdigest()}]
    })
    assert result["status"] == "verified-native-configuration-only"
    assert result["family_proofs"][TEXT_ID]["status"] == "native-configuration-metrics-verified"
    assert result["family_proofs"][TEXT_ID]["sourceCanvasMetric"] == "unknown"
    assert result["visualEquivalent"] is False
    from grea.recovery.unity_diagnostic_resolution import reconcile
    native=dict(sourceId=OUTLINE_ID,guid='b'*32,localFileId=11,nativeType='NativeStaticTextOutline',
        representation='native-component',persistent=True,sourceIdentityVerified=True,nativeStaticFieldsVerified=True)
    coverage=dict(components=[dict(sourceId=OUTLINE_ID,disposition='native',nativeStatus='pass',
        nativeStaticFieldsVerified=True,nativeComponentReadback=native)])
    resolved=reconcile([dict(code='MISSING_OUTLINE_LABEL',sourceId=OUTLINE_ID),
        dict(code='OUTLINE_METRICS_NOT_VERIFIED',sourceId=OUTLINE_ID)],coverage,family_proofs=result['family_proofs'])
    assert [d['resolved']for d in resolved['diagnostics']]==[True,False]
    row['configuredFontAssets'].reverse()
    changed=json.dumps(report,sort_keys=True,separators=(',',':')).encode();sidecar_path.write_bytes(changed)
    rejected=text_module.verify(prepared['plan'],candidate,{'staticTextReadbackFiles':[
        dict(path=relative,sha256=hashlib.sha256(changed).hexdigest())]})
    assert rejected['status']=='partial'
    assert any('glyphFallbackChain'in d['message']for d in rejected['diagnostics'])


def test_verifier_requires_isolated_sample_provenance_and_original_activity_preservation(tmp_path, engine_evidence):
    plan, ir, manifest = fixture_documents()
    prepared = text_module.prepare(plan, ir, manifest, tmp_path, source_evidence=engine_evidence)
    candidate = tmp_path / "candidate"
    sidecar = candidate / "Analysis/Readback/TextMetrics" / (hashlib.sha256(b"fixture:root").hexdigest() + ".json")
    sidecar.parent.mkdir(parents=True)
    config = prepared["plan"]["staticTextContinuationJson"].encode()
    row = {
        "sourceLabelId": TEXT_ID, "sourceOutlineId": OUTLINE_ID, "sourceNodeId": NODE_ID,
        "status": "native-configuration-metrics-verified", "fontKind": "system-font",
        "labelGuid": "a" * 32, "labelLocalFileId": 10, "outlineGuid": "b" * 32,
        "outlineNativeType": "NativeStaticTextOutline", "outlineLocalFileId": 11,
        "fontGuid": "c" * 32, "fontLocalFileId": 12, "persistentLabel": True, "persistentOutline": True,
        "sourceTextSha256": hashlib.sha256(TEXT.encode()).hexdigest(), "nativeText": TEXT,
        "nativeTextSha256": hashlib.sha256(TEXT.encode()).hexdigest(), "sourceTextMatches": True,
        "sourceStyleMatches": True, "nativeFontStyle": 1, "nativeOverflowMode": 0,
        "nativeWrappingMode": 0, "autoSizingConfigVerified": True, "fontBindingVerified": True,
        "glyphFontChainVerified": True, "lineHeightConfigVerified": True,
        "nativeFontAssetPath": PRIMARY_PATH, "nativeFontPointSize": 44, "nativeFaceLineHeight": 44,
        "nativeLineSpacing": 0, "nativeFontSizeMin": 0, "nativeFontSizeMax": 44, "actualFontSize": 44,
        "glyphFontAssets": [{"guid": "c" * 32, "localFileId": 12, "assetPath": PRIMARY_PATH}],
        "configuredFontAssets": [{"guid": "c" * 32, "localFileId": 12, "assetPath": PRIMARY_PATH},
                                 {"guid": "d" * 32, "localFileId": -13, "assetPath": FALLBACK_PATH}],
        "outlineConfigVerified": True, "outlineMaterialReadbackVerified": True,
        "nativeMeshMeasured": True, "inkBounds": {"hasVisibleGeometry": True},
        "nativeBoundsKind": "tmp-character-quad-local-bounds-not-pixel-ink",
        "sampleContext": "isolated-active-label-clone", "sourceNodeActiveSelf": True,
        "sourceNodeActiveInHierarchy": False, "sourceLabelEnabled": True,
        "sourceLabelEnabledUnchanged": True,
        "sampleCloneIsolated": True, "sampleAncestorActivationOverride": False,
        "sampleCloneActivationOverride": True, "sampleSourceAncestorInactive": True,
        "sampleStateRestored": True, "sourceActivityUnchanged": True,
        "sampleRectTransformVerified": True, "sampleCanvasReferencePixelsPerUnit": 100,
    }
    report = {"schemaVersion": 1, "contract": "monkey-static-text-metrics-readback/1",
              "phase": "saved-prefab-reopen", "sourceManifestSha256": plan["sourceManifestSha256"],
              "sourcePrefabId": "fixture:root", "continuationJsonSha256": hashlib.sha256(config).hexdigest(),
              "status": "verified", "components": [row]}
    raw = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    sidecar.write_bytes(raw)
    relative = sidecar.relative_to(candidate).as_posix()
    main = {"staticTextReadbackFiles": [{"path": relative, "sha256": hashlib.sha256(raw).hexdigest()}]}
    assert text_module.verify(prepared["plan"], candidate, main)["status"] == "verified-native-configuration-only"

    row.update({"sampleContext": "reopened-active-prefab-instance", "sourceNodeActiveSelf": True,
                "sourceNodeActiveInHierarchy": True, "sampleCloneIsolated": False,
                "sampleAncestorActivationOverride": False, "sampleCloneActivationOverride": False,
                "sampleSourceAncestorInactive": False})
    raw = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    sidecar.write_bytes(raw)
    main["staticTextReadbackFiles"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
    assert text_module.verify(prepared["plan"], candidate, main)["status"] == "verified-native-configuration-only"

    row["sourceActivityUnchanged"] = False
    raw = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    sidecar.write_bytes(raw)
    main["staticTextReadbackFiles"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
    result = text_module.verify(prepared["plan"], candidate, main)
    assert any("isolatedSampleContext" in item["message"] for item in result["diagnostics"])


def test_verifier_rejects_sidecar_pin_change_and_never_resolves_source_gaps(tmp_path, engine_evidence):
    plan, ir, manifest = fixture_documents()
    prepared = text_module.prepare(plan, ir, manifest, tmp_path, source_evidence=engine_evidence)
    candidate = tmp_path / "candidate"
    sidecar_path = candidate / "Analysis/Readback/TextMetrics" / \
        (hashlib.sha256(b"fixture:root").hexdigest() + ".json")
    sidecar_path.parent.mkdir(parents=True)
    sidecar_path.write_text("{}")
    result = text_module.verify(prepared["plan"], candidate, {
        "staticTextReadbackFiles": [{"path": sidecar_path.relative_to(candidate).as_posix(), "sha256": "c" * 64}]
    })
    assert result["status"] == "partial"
    assert any(row["code"] == "STATIC_TEXT_READBACK_SIDECAR_BYTES_CHANGED" for row in result["diagnostics"])


def test_verifier_accepts_exact_empty_text_prefab_sidecar_and_optional_outline_identity(tmp_path, engine_evidence):
    # Cocos overflow=NONE forces TTF no-wrap even when enableWrapText is true.
    plan, ir, manifest = fixture_documents(overflow=0, wrap=True)
    plan["components"] = plan["components"][:1]
    ir["components"] = ir["components"][:1]
    manifest["assets"][0]["document"]["instances"][0]["_components"] = \
        manifest["assets"][0]["document"]["instances"][0]["_components"][:1]
    plan["sourcePrefabs"].append({"sourceId": "fixture:empty-prefab"})
    prepared = text_module.prepare(plan, ir, manifest, tmp_path, source_evidence=engine_evidence)
    candidate = tmp_path / "candidate"
    sidecar_dir = candidate / "Analysis/Readback/TextMetrics"
    sidecar_dir.mkdir(parents=True)
    group = prepared["continuation"]["components"][0]
    config_sha = hashlib.sha256(prepared["plan"]["staticTextContinuationJson"].encode()).hexdigest()
    row = {
        "sourceLabelId": TEXT_ID, "sourceOutlineId": "", "sourceNodeId": NODE_ID,
        "sourceTextSha256": hashlib.sha256(TEXT.encode()).hexdigest(),
        "nativeTextSha256": hashlib.sha256(TEXT.encode()).hexdigest(), "nativeText": TEXT,
        "sourceTextMatches": True, "sourceStyleMatches": True, "nativeFontStyle": 1,
        "nativeOverflowMode": 0, "nativeWrappingMode": 0,
        "persistentLabel": True, "labelGuid": "a" * 32, "labelLocalFileId": 10,
        "fontGuid": "c" * 32, "fontLocalFileId": 12,
        "nativeFontAssetPath": PRIMARY_PATH, "nativeFontPointSize": 44, "nativeFaceLineHeight": 44,
        "nativeLineSpacing": 0, "actualFontSize": 44, "nativeFontSizeMin": 0, "nativeFontSizeMax": 44,
        "autoSizingConfigVerified": True, "fontBindingVerified": True, "glyphFontChainVerified": True,
        "lineHeightConfigVerified": True, "nativeMeshMeasured": True,
        "inkBounds": {"hasVisibleGeometry": True}, "nativeBoundsKind": "tmp-character-quad-local-bounds-not-pixel-ink",
        "sampleContext": "isolated-active-label-clone", "sourceNodeActiveSelf": True,
        "sourceNodeActiveInHierarchy": False, "sourceLabelEnabled": True,
        "sourceLabelEnabledUnchanged": True,
        "sampleCloneIsolated": True, "sampleAncestorActivationOverride": False,
        "sampleCloneActivationOverride": True, "sampleSourceAncestorInactive": True,
        "sampleStateRestored": True, "sourceActivityUnchanged": True,
        "sampleRectTransformVerified": True, "sampleCanvasReferencePixelsPerUnit": 100,
        "glyphFontAssets": [{"guid": "c" * 32, "localFileId": 12, "assetPath": PRIMARY_PATH}],
        "configuredFontAssets": [{"guid": "c" * 32, "localFileId": 12, "assetPath": PRIMARY_PATH},
                                 {"guid": "d" * 32, "localFileId": -13, "assetPath": FALLBACK_PATH}],
        "outlineConfigVerified": True,
    }

    def write_report(prefab_id, components, status="verified"):
        report = {"schemaVersion": 1, "contract": "monkey-static-text-metrics-readback/1",
                  "phase": "saved-prefab-reopen", "sourceManifestSha256": prepared["plan"]["sourceManifestSha256"],
                  "sourcePrefabId": prefab_id, "continuationJsonSha256": config_sha,
                  "status": status, "components": components}
        raw = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
        path = sidecar_dir / (hashlib.sha256(prefab_id.encode()).hexdigest() + ".json")
        path.write_bytes(raw)
        return {"path": path.relative_to(candidate).as_posix(), "sha256": hashlib.sha256(raw).hexdigest()}, path

    group_descriptor, _ = write_report("fixture:root", [row])
    empty_descriptor, empty_path = write_report("fixture:empty-prefab", [], "no-groups-for-prefab")
    main = {"staticTextReadbackFiles": [group_descriptor, empty_descriptor]}
    result = text_module.verify(prepared["plan"], candidate, main)
    assert result["status"] == "verified-native-configuration-only"
    assert not any(item["code"] in ("STATIC_TEXT_READBACK_FILE_SET_MISMATCH",
                                    "STATIC_TEXT_SIDECAR_DIRECTORY_SET_MISMATCH",
                                    "STATIC_TEXT_NATIVE_METRIC_OR_IDENTITY_UNVERIFIED")
                   for item in result["diagnostics"])

    # The same path/hash is not enough if a prefab that should be empty contains rows.
    empty_descriptor, _ = write_report("fixture:empty-prefab", [{"sourceLabelId": "unplanned-label"}], "verified")
    result = text_module.verify(prepared["plan"], candidate, {"staticTextReadbackFiles": [group_descriptor, empty_descriptor]})
    assert any(item["code"] == "STATIC_TEXT_EMPTY_PREFAB_SIDECAR_NOT_EMPTY" for item in result["diagnostics"])

    # An unlisted source prefab's empty sidecar is rejected when it is not in the plan inventory.
    prepared["plan"]["sourcePrefabs"] = prepared["plan"]["sourcePrefabs"][:1]
    result = text_module.verify(prepared["plan"], candidate, {"staticTextReadbackFiles": [group_descriptor, empty_descriptor]})
    assert any(item["code"] == "STATIC_TEXT_READBACK_FILE_SET_MISMATCH" for item in result["diagnostics"])


def test_verifier_uses_persistent_font_asset_identity_for_bitmap_font_binding(tmp_path, engine_evidence):
    plan, ir, manifest = fixture_documents(font_kind="bitmap", overflow=0, wrap=True)
    prepared = text_module.prepare(plan, ir, manifest, tmp_path, source_evidence=engine_evidence)
    candidate = tmp_path / "bitmap-candidate"
    group = prepared["continuation"]["components"][0]
    relative = "Analysis/Readback/TextMetrics/" + hashlib.sha256(b"fixture:root").hexdigest() + ".json"
    sidecar_path = candidate / relative
    sidecar_path.parent.mkdir(parents=True)
    font_path = group["nativeFontBinding"]["assetPaths"][0]
    font_id = "e" * 32
    row = {
        "sourceLabelId": TEXT_ID, "sourceOutlineId": OUTLINE_ID, "sourceNodeId": NODE_ID,
        "sourceTextSha256": hashlib.sha256(TEXT.encode()).hexdigest(),
        "nativeTextSha256": hashlib.sha256(TEXT.encode()).hexdigest(), "nativeText": TEXT,
        "sourceTextMatches": True, "sourceStyleMatches": True, "nativeFontStyle": 0,
        "nativeOverflowMode": 0, "nativeWrappingMode": 0,
        "persistentLabel": True, "labelGuid": "a" * 32, "labelLocalFileId": 10,
        "fontGuid": font_id, "fontLocalFileId": -12, "nativeFontAssetPath": font_path,
        "nativeFontPointSize": 44, "nativeFaceLineHeight": 44, "nativeLineSpacing": 0,
        "actualFontSize": 44, "nativeFontSizeMin": 0.1, "nativeFontSizeMax": 44,
        "autoSizingConfigVerified": True, "fontBindingVerified": False,
        "glyphFontChainVerified": True, "lineHeightConfigVerified": True,
        "nativeMeshMeasured": True, "inkBounds": {"hasVisibleGeometry": True},
        "nativeBoundsKind": "tmp-character-quad-local-bounds-not-pixel-ink",
        "sampleContext": "isolated-active-label-clone", "sourceNodeActiveSelf": True,
        "sourceNodeActiveInHierarchy": False, "sourceLabelEnabled": True,
        "sourceLabelEnabledUnchanged": True,
        "sampleCloneIsolated": True, "sampleAncestorActivationOverride": False,
        "sampleCloneActivationOverride": True, "sampleSourceAncestorInactive": True,
        "sampleStateRestored": True, "sourceActivityUnchanged": True,
        "sampleRectTransformVerified": True, "sampleCanvasReferencePixelsPerUnit": 100,
        "glyphFontAssets": [{"guid": font_id, "localFileId": -12, "assetPath": font_path}],
        "configuredFontAssets": [{"guid": font_id, "localFileId": -12, "assetPath": font_path}],
        "outlineConfigVerified": True,
    }
    config_raw = prepared["plan"]["staticTextContinuationJson"].encode()
    report = {"schemaVersion": 1, "contract": "monkey-static-text-metrics-readback/1",
              "phase": "saved-prefab-reopen", "sourceManifestSha256": plan["sourceManifestSha256"],
              "sourcePrefabId": "fixture:root", "continuationJsonSha256": hashlib.sha256(config_raw).hexdigest(),
              "status": "partial", "components": [row]}
    raw = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    sidecar_path.write_bytes(raw)
    result = text_module.verify(prepared["plan"], candidate, {"staticTextReadbackFiles": [
        {"path": relative, "sha256": hashlib.sha256(raw).hexdigest()}]})
    assert result["status"] == "verified-native-configuration-only"
    assert not any("primaryFontBinding" in item["message"] or "glyphFallbackChain" in item["message"]
                   for item in result["diagnostics"])
