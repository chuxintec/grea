import copy
import json
from pathlib import Path

import pytest

from monkey.io import encoded, sha
from monkey.sources.compiled import ParseError
from monkey.unity_prefab_recovery import recover, provider_lineage


def fixture(tmp_path):
    def put(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = data if isinstance(data, bytes) else encoded(data)
        path.write_bytes(raw)
        return dict(path=str(path), sha256=sha(raw), bytes=len(raw))

    original = put(tmp_path / "input/source.ab", b"UnityFS-neutral-source")
    ptr = lambda p: {"$type": "UnityPPtr", "fileId": "0", "pathId": str(p)}
    objects = [
        dict(file="0", pathId="1", type="GameObject", classId=1, rawSha256="1" * 64, status="parsed", name="Panel",
             data=dict(m_Name="Panel", m_IsActive=True, m_Layer=5, m_Tag=0, m_Component=[dict(component=ptr(2))]), references=[]),
        dict(file="0", pathId="2", type="Transform", classId=4, rawSha256="2" * 64, status="parsed", name=None,
             data=dict(m_GameObject=ptr(1), m_Father=ptr(0), m_Children=[], m_LocalPosition=dict(x=0.0, y=0.0, z=0.0)), references=[]),
        dict(file="0", pathId="3", type="AssetBundle", classId=142, rawSha256="3" * 64, status="parsed", name="neutral",
             data=dict(m_Container=[["assets/resources/panel.prefab", dict(asset=ptr(1))]]), references=[]),
    ]
    file = dict(id="0", name="CAB-neutral", serializedFileSha256="f" * 64, unityVersion="2021.3.30f1", externals=[])
    typed = dict(schemaVersion=1, sourceFamily="unity", source=original, sourceCodeExecuted=False,
                 files=[file], objects=objects, payloadFiles=[], embeddedSchemas={}, borrowedSchemas={})
    typed_pin = put(tmp_path / "cache/typed-objects.json", typed)
    receipt_pin = put(tmp_path / "cache/inspection.json", dict(status="inspected", source=original,
        sourceUnchanged=True, processExited=True, sourceCodeExecuted=False, typedObjectsSha256=typed_pin["sha256"]))
    combined = put(tmp_path / "combined/typed-objects.json", dict(files=[dict(file, containerSha256=original["sha256"])]))
    index_pin = put(tmp_path / "index.json", dict(indexFromPinnedExistingCombinedSource=str(tmp_path / "combined"),
        combinedTypedSha256=combined["sha256"], sourceInputs=[dict(source=original,
        inspection=receipt_pin["path"], inspectionSha256=receipt_pin["sha256"],
        typedObjects=typed_pin["path"], typedObjectsSha256=typed_pin["sha256"])]))
    source_row = dict(original, index=0)
    job_pin = put(tmp_path / "prepared/prepare-job.json", dict(sources=[source_row]))
    prepared_pin = put(tmp_path / "prepared/prepared.json", dict(status="prepared", jobSha256=job_pin["sha256"],
        prepared=1, rows=[dict(index=0, source=source_row, derived=None)]))
    binding_pin = put(tmp_path / "provider/bulk-export-binding.json", dict(preparedJobSha256=job_pin["sha256"],
        preparedSha256=prepared_pin["sha256"], sourceCodeExecuted=False))
    export_pin = put(tmp_path / "provider/export.json", dict(status="exported_partial", targetVersion="6000.6.2f1",
        sourceUnchanged=True, processExited=True, source=dict(bytes=original["bytes"], sha256=original["sha256"]), dependencies=[]))
    export_root = tmp_path / "provider/exported"
    payloads = {
        "ExportedProject/Assets/Resources/Panel.prefab": b"%YAML 1.1\n--- !u!1 &1\nGameObject:\n  m_Name: Panel\n",
        "ExportedProject/Assets/Resources/Panel.prefab.meta": b"fileFormatVersion: 2\nguid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n",
    }
    rows = []
    for path, data in payloads.items():
        pin = put(export_root / path, data)
        rows.append(dict(pin, path=path))
    inventory = put(tmp_path / "provider/output-files.json", dict(files=rows))
    request = dict(schemaVersion=1, contract="monkey-unity-prefab-recovery-request/1", targetUnityVersion="6000.6.2f1",
        inputIndex=index_pin, roots=[dict(sourceSha256=original["sha256"], file="0", pathId="1")],
        providerExport=dict(root=str(export_root), inventory=inventory, receipt=export_pin, binding=binding_pin,
                            prepared=prepared_pin, prepareJob=job_pin), typeEvidence=[])
    request_pin = put(tmp_path / "request.json", request)
    return request, request_pin, payloads


def test_selected_native_payload_is_immutable_and_does_not_claim_native_acceptance(tmp_path):
    request, pin, payloads = fixture(tmp_path)
    report = recover(pin["path"], pin["sha256"], tmp_path / "candidate")
    project = tmp_path / "candidate/UnityProject"
    assert report["native"] == report["business"] == "not_run"
    assert report["status"] == "needs_action"
    assert report["sourceCodeExecuted"] is False
    prefab, = project.rglob("*.prefab")
    assert prefab.read_bytes() == payloads["ExportedProject/Assets/Resources/Panel.prefab"]
    assert Path(str(prefab) + ".meta").read_bytes() == payloads["ExportedProject/Assets/Resources/Panel.prefab.meta"]
    assert not (project / "Library").exists()
    for path, raw in payloads.items():
        assert (Path(request["providerExport"]["root"]) / path).read_bytes() == raw


def test_provider_inventory_drift_fails_before_candidate_creation(tmp_path):
    request, pin, _ = fixture(tmp_path)
    path = Path(request["providerExport"]["root"]) / "ExportedProject/Assets/Resources/Panel.prefab.meta"
    path.write_text("guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n")
    with pytest.raises(ParseError, match="UNITY_PREFAB_INPUT_DRIFT"):
        recover(pin["path"], pin["sha256"], tmp_path / "candidate")
    assert not (tmp_path / "candidate").exists()


def test_changed_typed_snapshot_cannot_borrow_original_receipt(tmp_path):
    request, pin, _ = fixture(tmp_path)
    index = json.loads(Path(request["inputIndex"]["path"]).read_text())
    path = Path(index["sourceInputs"][0]["typedObjects"])
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ParseError, match="UNITY_PREFAB_INPUT_DRIFT"):
        recover(pin["path"], pin["sha256"], tmp_path / "candidate")
    assert not (tmp_path / "candidate").exists()


def test_completed_export_from_another_source_is_not_a_valid_cache(tmp_path):
    request, _, _ = fixture(tmp_path)
    provider = copy.deepcopy(request["providerExport"])
    path = Path(provider["receipt"]["path"])
    body = json.loads(path.read_text())
    body["source"]["sha256"] = "0" * 64
    raw = encoded(body)
    path.write_bytes(raw)
    provider["receipt"].update(sha256=sha(raw), bytes=len(raw))
    with pytest.raises(ParseError, match="UNITY_PREFAB_PROVIDER_SOURCE_MISSING"):
        provider_lineage(provider, [dict(sourceSha256=request["roots"][0]["sourceSha256"])])


def test_native_bridge_refuses_candidate_payload_drift_before_editor_launch(tmp_path):
    from monkey.unity_prefab_native import prepare
    _, pin, _ = fixture(tmp_path)
    recover(pin["path"], pin["sha256"], tmp_path / "candidate")
    project = tmp_path / "candidate/UnityProject"
    manifest_sha = sha((project / "manifest.json").read_bytes())
    prefab, = project.rglob("*.prefab")
    prefab.write_bytes(prefab.read_bytes() + b"# manual change\n")
    with pytest.raises(ParseError, match="UNITY_PREFAB_CANDIDATE_DRIFT"):
        prepare(project, manifest_sha)


@pytest.mark.parametrize("member,expected", [
    ("", "source-ui-behavior-unverified"),
    ("protected override void OnPopulateMesh(UnityEngine.UI.VertexHelper vh) { vh.Clear(); }",
     "source-ui-behavior-unverified"),
])
def test_schema_only_custom_image_carries_hash_pinned_source_presentation_classification(tmp_path, member, expected):
    from monkey.unity_prefab_recovery import script_proposals
    source_text = "public class CustomImage : UnityEngine.UI.Image { " + member + " }"
    source_path = tmp_path / "CustomImage.cs"
    source_path.write_text(source_text, encoding="utf-8")
    source_hash = sha(source_path.read_bytes())
    parsed, _ = type_models_for_test(source_text, source_path, source_hash)
    script_id = {"assembly": "Assembly-CSharp.dll", "namespace": "", "name": "CustomImage"}
    script_proposal = script_proposals([{
        "sourceSha256": "1" * 64,
        "document": {
            "files": [{"id": "0", "name": "CAB"}],
            "objects": [
                {"type": "MonoBehaviour", "status": "parsed", "file": "0", "pathId": "1",
                 "embeddedSchemaId": "schema", "borrowedSchemaId": None,
                 "data": {"m_Script": {"fileId": "0", "pathId": "2"}}},
                {"type": "MonoScript", "status": "parsed", "file": "0", "pathId": "2", "rawSha256": "2" * 64,
                 "data": {"m_AssemblyName": script_id["assembly"], "m_Namespace": "", "m_ClassName": script_id["name"]}},
            ],
            "embeddedSchemas": {"schema": {"children": []}}, "borrowedSchemas": {},
        },
    }], parsed, False)
    model = script_proposal[(script_id["assembly"], "", script_id["name"])]
    assert model["state"] == "native-base-schema-only"
    assert model["proposal"]["sourceUiStaticEvidence"]["status"] == expected


def type_models_for_test(source_text, source_path, source_hash):
    from monkey.unity_prefab_types import parse_declarations
    return parse_declarations(source_text, assembly="Assembly-CSharp.dll", source_path=str(source_path),
                              source_sha256=source_hash), []
