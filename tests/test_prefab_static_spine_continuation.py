import hashlib
import json
from pathlib import Path

from monkey import prefab_static_spine_continuation as spine


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _fragment(raw: bytes) -> dict:
    return {
        "schemaVersion": 1,
        "contract": spine.CONTRACT,
        "namespace": "spine-tests",
        "sourceManifestSha256": "a" * 64,
        "sourceIrSha256": "b" * 64,
        "payloadCopies": [{
            "source": "payloads/source.bin.bytes",
            "target": "Assets/Game/Content/Spine/SourceData/source.bin.bytes",
            "sha256": _sha(raw), "bytes": len(raw), "role": "opaque-source", "sourceId": "bundle:data",
        }],
        "components": [{
            "sourceComponentId": "bundle:prefab#0/components/0",
            "sourceTemplateComponentId": "bundle:prefab#0/components/0",
            "sourceNodeId": "bundle:prefab#0",
            "sourceFieldsSha256": "c" * 64,
            "sourceComponentEnvelopeSha256": "d" * 64,
            "sourceDataReference": {"sourceDataAssetId": None},
            "sourceObjectReferences": [],
            "renderingStatus": "not_rendered",
            "dynamicBehaviorStatus": "not_restored",
        }],
        "dataAssets": [], "supportFiles": [],
    }


def test_verify_loads_canonical_sidecar_and_accepts_exact_saved_identity(tmp_path):
    raw = b"frozen source payload\x00"
    fragment = _fragment(raw)
    payload = tmp_path / fragment["payloadCopies"][0]["target"]
    payload.parent.mkdir(parents=True)
    payload.write_bytes(raw)
    payload_meta_guid = spine.guid(fragment["namespace"], "static-spine-source-text-asset/" +
                                  fragment["payloadCopies"][0]["sourceId"] + "/" + fragment["payloadCopies"][0]["target"])
    Path(str(payload) + ".meta").write_bytes(spine._text_asset_meta(payload_meta_guid))
    sidecar = tmp_path / "Analysis/Readback/spine-static-continuation.json"
    sidecar.parent.mkdir(parents=True)
    component = fragment["components"][0]
    sidecar.write_text(json.dumps({
        "schemaVersion": 1,
        "contract": spine.READBACK_CONTRACT,
        "sourceManifestSha256": fragment["sourceManifestSha256"],
        "sourceIrSha256": fragment["sourceIrSha256"],
        "status": "saved_static_references_verified",
        "components": [{
            "sourceComponentId": component["sourceComponentId"],
            "sourceTemplateComponentId": component["sourceTemplateComponentId"],
            "sourceNodeId": component["sourceNodeId"],
            "sourceFieldsSha256": component["sourceFieldsSha256"],
            "sourceComponentEnvelopeSha256": component["sourceComponentEnvelopeSha256"],
            "savedComponent": True,
            "persistedGuidStatus": "verified", "persistedGuid": "e" * 32, "persistedLocalFileId": 11400000,
            "renderingStatus": "not_rendered", "dynamicBehaviorStatus": "not_restored",
            "sourceObjectReferences": [],
        }],
    }), encoding="utf-8")

    assert spine.verify(fragment, tmp_path, {"status": "ignored-generic-readback"}) == []
    receipt = json.loads(sidecar.read_text())
    receipt['components'][0]['persistedLocalFileId'] = -(1 << 63) + 1
    sidecar.write_text(json.dumps(receipt))
    native = {'components': [{'sourceId': component['sourceComponentId'], 'guid': 'e' * 32,
        'localFileId': -(1 << 63) + 1, 'persistent': True, 'sourceIdentityVerified': True,
        'nativeType':'NativeStaticSpineReference', 'status':'retained',
        'representation':'disabled-source-data-carrier'}]}
    assert spine.verify(fragment, tmp_path, native) == []
    renderer = dict(native['components'][0], nativeType='Spine.Unity.SkeletonGraphic',
                    status='native', representation='native-component', localFileId=42)
    native['components'].append(renderer)
    assert spine.verify(fragment, tmp_path, native) == []
    native['components'].append(dict(native['components'][0]))
    assert spine.verify(fragment, tmp_path, native)[0]['code'] == 'STATIC_SPINE_PERSISTENT_IDENTITY_MISMATCH'
    native['components'].pop()
    native['components'][0]['localFileId'] = 42
    assert spine.verify(fragment, tmp_path, native)[0]['code'] == 'STATIC_SPINE_PERSISTENT_IDENTITY_MISMATCH'
    for invalid in (True, 0, 1 << 63, -(1 << 63) - 1, '123'):
        receipt['components'][0]['persistedLocalFileId'] = invalid
        sidecar.write_text(json.dumps(receipt))
        assert spine.verify(fragment, tmp_path)[0]['code'] == 'STATIC_SPINE_SAVED_REFERENCE_MISMATCH'


def test_verify_requires_canonical_sidecar_even_if_generic_readback_is_supplied(tmp_path):
    fragment = _fragment(b"bytes")
    diagnostics = spine.verify(fragment, tmp_path, {"status": "saved_static_references_verified"})
    assert len(diagnostics) == 1
    assert diagnostics[0]["code"] == "STATIC_SPINE_READBACK_MISSING"
    assert diagnostics[0]["severity"] == "error"


def test_retained_meta_accepts_only_source_pinned_recipe_and_saved_hash():
    from monkey.prefab_static_retained_assets import _unity_meta
    import pytest
    uid='a'*32
    target='Assets/Game/Content/RetainedAssets/example.asset.meta'
    original=_unity_meta(uid,'native-asset')
    saved=original.replace(b'  userData: \n',b'').replace(b'  assetBundleName: \n',b'').replace(b'  assetBundleVariant: \n',b'')
    row={'target':target,'kind':'unity-retained-material-meta','sha256':spine._sha(original),'bytes':len(original)}
    contract={'assets':[{'unity':{'path':target[:-5],'guid':uid}}]}
    readback={'nativeFiles':[{'path':target,'sha256':spine._sha(saved)}]}
    assert spine._saved_retained_meta(row,contract,saved,readback)['path']==target
    for pins in ({'nativeFiles':[]},{'nativeFiles':readback['nativeFiles']*2},
                 {'nativeFiles':[{'path':target,'sha256':'0'*64}]}):
        with pytest.raises(ValueError):
            spine._saved_retained_meta(row,contract,saved,pins)
    with pytest.raises(ValueError,match='frozen original'):
        spine._saved_retained_meta(dict(row,sha256='0'*64),contract,saved,readback)
    changed=saved.replace(b'mainObjectFileID: 11400000',b'mainObjectFileID: 1')
    with pytest.raises(ValueError):
        spine._saved_retained_meta(row,contract,changed,
            {'nativeFiles':[{'path':target,'sha256':spine._sha(changed)}]})


def test_typed_source_field_keeps_absence_distinct_from_default():
    unknown = spine._typed_field("premultipliedAlpha", {"present": False, "status": "not_serialized_unknown"})
    explicit_false = spine._typed_field("premultipliedAlpha", {"present": True, "value": False, "status": "serialized"})
    assert unknown["present"] is False
    assert explicit_false["present"] is True
    assert explicit_false["boolValue"] is False


def test_optional_runtime_backup_reads_exact_namespace_and_preserves_bytes(tmp_path):
    import pytest
    root=tmp_path/'sdk';relative='Assets/Plugins/Spine38/EditorRuntime/provider.dll';dll=root/relative
    dll.parent.mkdir(parents=True);dll.write_bytes(b'synthetic provider fixture')
    manifest=dict(producerManifestSHA256=spine.RUNTIME_REFERENCE_BACKUP,
        upstream=dict(upstreamCommit='8b4844bd4b193ba9e54487ed397a777993cbad56',
                      sourceVersion='3.8.99 skeleton compatible branch3.8',compiledAgainst='Unity6000.6.2f1'),
        files=[dict(path=relative,sha256=_sha(dll.read_bytes()),bytes=dll.stat().st_size)])
    path=tmp_path/'sdk-manifest.json';path.write_text(json.dumps(manifest));pin=_sha(path.read_bytes())
    result=spine._pinned_runtime_record(manifest,path,pin,root)
    assert len(result['verifiedFiles'])==1 and result['copied']is False
    dll.write_bytes(b'changed')
    with pytest.raises(spine.StaticSpineContinuationError,match='differs from its manifest'):
        spine._pinned_runtime_record(manifest,path,pin,root)


def test_payload_copy_writes_named_file_under_private_module_stage(tmp_path):
    row = spine._write_payload_copy(tmp_path, tmp_path / "unused", "spine_static_continuation/payloads/item",
                                    "source.bin.bytes", "Assets/Game/Content/Spine/SourceData/source.bin.bytes",
                                    b"opaque", "source-spine-skeleton-textasset", "bundle:data", "/pinned/source.bin")
    assert row["source"] == "spine_static_continuation/payloads/item/source.bin.bytes"
    assert (tmp_path / row["source"]).read_bytes() == b"opaque"


def test_retained_contract_merge_rejects_changed_payload_for_same_target():
    base = {"schema": "monkey-prefab-static-retained-assets/1", "sourceManifestSha256": "a" * 64,
            "targetNamespace": "demo", "assets": [], "payloads": [{"target": "Assets/Game/Content/x.bytes",
            "sha256": "1" * 64, "bytes": 3}], "copies": [], "sourceEvidenceCopies": [], "references": [], "gaps": []}
    added = {**base, "payloads": [{"target": "Assets/Game/Content/x.bytes", "sha256": "2" * 64, "bytes": 3}]}
    try:
        spine._merge_retained_contracts(base, added)
    except spine.StaticSpineContinuationError as error:
        assert "collision" in str(error)
    else:
        raise AssertionError("changed retained payload collision was accepted")


def test_source_uuid_resolver_follows_exact_redirect_target_and_keeps_chain():
    alias = {"sourceId": "gameAsset:asset-guid", "kind": "redirect", "redirectTarget": "spineAsset:data-guid"}
    target = {"sourceId": "spineAsset:data-guid", "kind": "sp.SkeletonData"}
    result, evidence = spine._resolve_source_uuid("asset-guid", {"asset-guid": [alias]},
                                                   {alias["sourceId"]: alias, target["sourceId"]: target})
    assert result is target
    assert evidence["canonicalSourceAssetId"] == target["sourceId"]
    assert evidence["redirectChains"] == [[alias["sourceId"], target["sourceId"]]]


def test_source_uuid_resolver_rejects_redirect_cycles_and_dangling_targets():
    first = {"sourceId": "gameAsset:a", "kind": "redirect", "redirectTarget": "gameAsset:b"}
    second = {"sourceId": "gameAsset:b", "kind": "redirect", "redirectTarget": "gameAsset:a"}
    try:
        spine._resolve_source_uuid("a", {"a": [first]}, {first["sourceId"]: first, second["sourceId"]: second})
    except spine.StaticSpineContinuationError as error:
        assert "cycle" in str(error)
    else:
        raise AssertionError("redirect cycle was accepted")
    try:
        spine._resolve_source_uuid("a", {"a": [first]}, {first["sourceId"]: first})
    except spine.StaticSpineContinuationError as error:
        assert "missing" in str(error)
    else:
        raise AssertionError("dangling redirect was accepted")


def _minimal_full_fixture(root):
    import copy

    source = root / "source"
    source.mkdir()
    (source / "import").mkdir()
    (source / "native").mkdir()
    skeleton_bytes = b"\x02x\x073.8.99\x00binary-tail"
    page_bytes = b"opaque-astc-page-bytes\x00"
    (source / "native/skeleton.bin").write_bytes(skeleton_bytes)
    (source / "native/page.astc").write_bytes(page_bytes)
    material_import = b"material-import-source"
    effect_import = b"effect-import-source"
    (source / "import/material.json").write_bytes(material_import)
    (source / "import/effect.json").write_bytes(effect_import)

    skeleton_id = "gameAsset:data-guid"
    material_id = "gameAsset:material-guid"
    page_id = "gameAsset:page-guid"
    effect_id = "gameAsset:effect-guid"
    prefab_id = "gameAsset:prefab-guid"
    component = {
        "__type__": "sp.Skeleton", "node": {"__id__": 0},
        "_N$skeletonData": {"__uuid__": "data-guid"},
        "_materials": [{"__uuid__": "material-guid"}],
        "defaultSkin": "default", "_animationName": "idle", "loop": True,
    }
    prefab_doc = {"root": 0, "instances": [
        {"__type__": "cc.Node", "_components": [{"__id__": 1}]}, component,
    ]}
    atlas = "page.png\nsize: 8,8\nformat: RGBA8888\nfilter: Linear,Linear\nrepeat: none\n"
    data_doc = {"root": 0, "instances": [{"__type__": "sp.SkeletonData", "_atlasText": atlas,
        "textureNames": ["page.png"], "textures": [{"__uuid__": "page-guid"}]}]}
    assets = [
        {"sourceId": prefab_id, "kind": "cc.Prefab", "bundle": "gameAsset", "document": prefab_doc},
        {"sourceId": skeleton_id, "kind": "sp.SkeletonData", "bundle": "gameAsset", "native": "native/skeleton.bin", "document": data_doc},
        {"sourceId": page_id, "kind": "cc.Texture2D", "bundle": "gameAsset", "native": "native/page.astc",
         "document": {"root": 0, "instances": [{"__type__": "cc.Texture2D"}]}},
        {"sourceId": material_id, "kind": "cc.Material", "bundle": "gameAsset", "importPath": "import/material.json",
         "document": {"root": 0, "instances": [{"__type__": "cc.Material", "_name": "dynamic-source-material",
             "_effectAsset": {"__uuid__": "effect-guid"}, "_techniqueData": {"0": {"defines": {"DYNAMIC": True}}}}]}},
        {"sourceId": effect_id, "kind": "cc.EffectAsset", "bundle": "gameAsset", "importPath": "import/effect.json",
         "document": {"root": 0, "instances": [{"__type__": "cc.EffectAsset", "_name": "source-effect"}]}},
    ]
    source_values = {"native/skeleton.bin": skeleton_bytes, "native/page.astc": page_bytes,
                     "import/material.json": material_import, "import/effect.json": effect_import}
    inputs = [{"bundle": "gameAsset", "path": path, "bytes": len(raw), "sha256": _sha(raw)}
              for path, raw in source_values.items()]
    manifest = {"schemaVersion": 1, "sourceVersion": "2.4.15", "bundle": "gameAsset",
                "sourceRoots": {"gameAsset": str(source)}, "assets": assets, "inputs": inputs}
    manifest_path = root / "source-manifest.json"
    manifest_path.write_bytes(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode())
    manifest_sha = _sha(manifest_path.read_bytes())
    template_id = prefab_id + "#0/components/0"
    clone_id = prefab_id + "#syncA::sync-component-0"
    plan = {"projectLayout": "monkey-project/2.0.0", "namespace": "spine-synthetic",
            "sourceManifestPath": str(manifest_path), "sourceManifestSha256": manifest_sha,
            "sourceIrSha256": "b" * 64,
            "components": [
                {"sourceId": template_id, "type": "sp.Skeleton", "node": prefab_id + "#0", "enabled": True, "convertible": False},
                {"sourceId": clone_id, "type": "sp.Skeleton", "node": prefab_id + "#syncA", "enabled": True, "convertible": False},
            ],
            "syncPrefabBindings": [{"componentOrigins": [{"instanceSourceId": clone_id, "templateSourceId": template_id}]}],
            "sourcePrefabs": [{"sourceId": prefab_id, "path": "Assets/Game/Content/Prefabs/Synthetic.prefab"}]}
    ir = {"sourceManifestPath": str(manifest_path), "sourceManifestSha256": manifest_sha}
    return plan, ir, manifest, manifest_path, page_bytes, material_id


def test_prepare_emit_chain_preserves_stage_merges_retained_assets_and_rejects_changed_source(tmp_path):
    from monkey.prefab_static_retained_assets import emit as emit_retained

    plan, ir, manifest, manifest_path, page_bytes, material_id = _minimal_full_fixture(tmp_path)
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "prior-module.txt").write_text("owned by a sibling module", encoding="utf-8")
    original_convertible = [row["convertible"] for row in plan["components"]]

    prepared = spine.prepare(plan, ir, manifest, stage,
                             source_manifest_path=manifest_path,
                             source_manifest_sha256=plan["sourceManifestSha256"],
                             source_ir_sha256=plan["sourceIrSha256"])
    patched = prepared["plan"]
    fragment = prepared["continuation"]
    assert patched["staticSpineContinuation"] is fragment
    assert [row["convertible"] for row in patched["components"]] == original_convertible
    assert (stage / "prior-module.txt").read_text(encoding="utf-8") == "owned by a sibling module"
    assert fragment["summary"]["sourceSpineComponentCount"] == 2
    assert fragment["summary"]["syncInstanceComponentCount"] == 1
    assert fragment["summary"]["sourceSkeletonDataAssetCount"] == 1
    assert fragment["summary"]["sourceAstcPagesDecoded"] == 0
    assert len(patched["staticRetainedAssets"]["assets"]) == 1
    assert patched["staticRetainedAssets"]["assets"][0]["sourceId"] == material_id
    evidence_rows = patched["staticRetainedAssets"]["sourceEvidenceCopies"]
    material_evidence = patched["staticRetainedAssets"]["assets"][0]["sourceImportEvidenceCopy"]
    assert material_evidence in evidence_rows
    evidence_path = stage / material_evidence["path"]
    assert evidence_path.is_file()
    assert _sha(evidence_path.read_bytes()) == material_evidence["sha256"]
    source_page = next(row for row in fragment["payloadCopies"] if row["sourceId"] == "gameAsset:page-guid")
    assert (stage / fragment["moduleStage"] / source_page["source"]).read_bytes() == page_bytes
    assert source_page["sha256"] == _sha(page_bytes)
    assert source_page["target"].endswith(".astc.bytes")

    candidate = tmp_path / "candidate"
    candidate.mkdir()
    emitted = spine.emit(patched, stage, candidate)
    assert emitted["sourceAstcPagesDecoded"] == 0
    assert emitted["retainedAssetsEmission"] == "owned by shared staticRetainedAssets exporter"
    for row in fragment["payloadCopies"]:
        staged = stage / fragment["moduleStage"] / row["source"]
        emitted_path = candidate / row["target"]
        assert _sha(staged.read_bytes()) == row["sha256"]
        assert _sha(emitted_path.read_bytes()) == row["sha256"]
    material_path = next(row["unity"]["path"] for row in patched["staticRetainedAssets"]["assets"]
                         if row["sourceId"] == material_id)
    assert not (candidate / material_path).exists()
    emit_retained(patched["staticRetainedAssets"], stage, candidate, "unity")
    retained_targets = [row["target"] for row in patched["staticRetainedAssets"]["payloads"]
                        if row["target"].startswith("Assets/Game/Content/")]
    assert retained_targets and all((candidate / target).is_file() for target in retained_targets)
    try:
        emit_retained(patched["staticRetainedAssets"], stage, candidate, "unity")
    except Exception:
        pass
    else:
        raise AssertionError("shared retained emitter accepted a duplicate copy")
    data_record = fragment["dataAssets"][0]
    data_asset_path = candidate / data_record["nativeStaticSpineDataAssetPath"]
    data_meta = Path(str(data_asset_path) + ".meta")
    assert not data_asset_path.exists() and not data_meta.exists()
    data_asset_path.parent.mkdir(parents=True, exist_ok=True)
    data_asset_path.write_text("%YAML 1.1\n# synthetic Editor-created ScriptableObject\n", encoding="utf-8")
    data_asset_guid = "a" * 32
    data_meta.write_text(f"fileFormatVersion: 2\nguid: {data_asset_guid}\nNativeFormatImporter:\n  externalObjects: {{}}\n  mainObjectFileID: 11400000\n",
                         encoding="utf-8")
    retained_material = next(row for row in patched["staticRetainedAssets"]["assets"] if row["sourceId"] == material_id)
    readback_components = []
    for component in fragment["components"]:
        references = []
        for reference in component["sourceObjectReferences"]:
            if reference["targetReferenceKind"] == "source-spine-data":
                ref_guid = data_asset_guid
            else:
                ref_guid = retained_material["unity"]["guid"]
            references.append({"fieldPath": reference["fieldPath"], "sourceAssetId": reference["sourceAssetId"],
                               "sourceUuid": reference["sourceUuid"], "resolved": True,
                               "persistedGuid": ref_guid, "persistedLocalFileId": 11400000})
        readback_components.append({"sourceComponentId": component["sourceComponentId"],
            "sourceTemplateComponentId": component["sourceTemplateComponentId"], "sourceNodeId": component["sourceNodeId"],
            "sourceFieldsSha256": component["sourceFieldsSha256"],
            "sourceComponentEnvelopeSha256": component["sourceComponentEnvelopeSha256"], "savedComponent": True,
            "persistedGuidStatus": "verified", "persistedGuid": "f" * 32, "persistedLocalFileId": 11400000,
            "sourceDataAssetId": component["sourceDataReference"]["sourceDataAssetId"],
            "dataAssetGuidStatus": "verified", "dataAssetGuid": data_asset_guid,
            "dataAssetLocalFileId": 11400000, "renderingStatus": "not_rendered",
            "dynamicBehaviorStatus": "not_restored", "sourceObjectReferences": references})
    readback = candidate / "Analysis/Readback/spine-static-continuation.json"
    readback.parent.mkdir(parents=True)
    readback.write_text(json.dumps({"schemaVersion": 1, "contract": spine.READBACK_CONTRACT,
        "sourceManifestSha256": fragment["sourceManifestSha256"], "sourceIrSha256": fragment["sourceIrSha256"],
        "status": "saved_static_references_verified", "components": readback_components}), encoding="utf-8")
    assert spine.verify(fragment, candidate) == []

    source_root = Path(manifest["sourceRoots"]["gameAsset"])
    (source_root / "native/page.astc").write_bytes(page_bytes + b"changed")
    changed_stage = tmp_path / "changed-stage"
    changed_stage.mkdir()
    try:
        spine.prepare(plan, ir, manifest, changed_stage,
                      source_manifest_path=manifest_path,
                      source_manifest_sha256=plan["sourceManifestSha256"],
                      source_ir_sha256=plan["sourceIrSha256"])
    except spine.StaticSpineContinuationError as error:
        assert "hash differs" in str(error)
    else:
        raise AssertionError("changed source page bytes were accepted")
    assert not (changed_stage / "spine_static_continuation").exists()
