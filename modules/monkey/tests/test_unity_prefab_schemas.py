import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from monkey.sources.unity_prefab_schema_worker import extract
from monkey.unity_prefab_schemas import BuiltinSchemaError, _validate_report, extract_builtin_schemas, validate_wanted_objects


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def wanted(path_id="42", object_type="SpriteRenderer", raw=b"component", serialized_sha=None):
    row = {"serializedFile": "CAB-test", "pathId": path_id, "type": object_type, "rawSha256": sha(raw)}
    if serialized_sha:
        row["serializedFileSha256"] = serialized_sha
    return row


def test_wanted_selection_is_exact_bounded_and_excludes_monobehaviour():
    normalized = validate_wanted_objects([wanted(path_id=-42)])
    assert normalized[0]["pathId"] == "-42"
    for bad in (
        [],
        [wanted(), wanted()],
        [wanted(path_id="042")],
        [wanted(object_type="MonoBehaviour")],
        [dict(wanted(), rawSha256="not-a-hash")],
    ):
        with unittest.TestCase().assertRaises(BuiltinSchemaError):
            validate_wanted_objects(bad)


def fixture_node():
    children = [
        NS(m_Name="m_DynamicOccludee", m_Type="UInt8", m_Children=[], m_MetaFlag=0, m_Version=1, m_ByteSize=1),
    ]
    rows = [
        dict(m_Name="SpriteRenderer", m_Type="Base", m_Level=0, m_MetaFlag=0),
        dict(m_Name="m_DynamicOccludee", m_Type="UInt8", m_Level=1, m_MetaFlag=0),
    ]
    return NS(m_Name="SpriteRenderer", m_Type="Base", m_Children=children,
              to_dict_list=lambda: rows)


def worker_fixture(root, *, version="2021.3.30f1", node=None, objects=None, assets=None):
    source = root / "bundle.ab"
    source.write_bytes(b"pinned source bytes")
    source_sha = sha(source.read_bytes())
    serialized_raw = b"serialized file bytes"
    serialized_sha = sha(serialized_raw)
    node = fixture_node() if node is None else node
    component_raw = b"component"
    obj = NS(path_id=42, type=NS(name="SpriteRenderer", __int__=lambda self: 212),
             byte_size=len(component_raw), get_raw_data=lambda: component_raw,
             serialized_type=NS(node=node))
    # UnityPy's ObjectReader type is int-convertible; expose that contract on a small fixture class.
    class ClassId:
        name = "SpriteRenderer"
        def __int__(self):
            return 212
    obj.type = ClassId()
    asset = NS(name="CAB-test", unity_version=version, target_platform=20,
               reader=NS(bytes=serialized_raw), objects={42: obj})
    if objects is not None:
        asset.objects = objects
    if assets is not None:
        env_assets = assets
    else:
        env_assets = [asset]
    request = wanted(serialized_sha=serialized_sha)
    job = {"sourcePath": str(source), "sourceSha256": source_sha, "wantedObjects": [request]}
    env = NS(assets=env_assets)
    return source, job, env, serialized_sha, obj


def test_worker_returns_exact_identity_and_both_schema_hashes_without_coercion(tmp_path):
    source, job, env, serialized_sha, _ = worker_fixture(tmp_path)
    unitypy = NS(__version__="1.25.3", load=lambda raw: env)
    with patch.dict("sys.modules", UnityPy=unitypy):
        result = extract(job)
    _validate_report(result, validate_wanted_objects(job["wantedObjects"]), job["sourceSha256"])
    row = result["objects"][0]
    assert result["status"] == "schemas_read"
    assert row["identity"]["serializedFileSha256"] == serialized_sha
    assert row["identity"]["pathId"] == "42"
    assert row["identity"]["classId"] == 212
    dynamic = next(child for child in row["schemaNode"]["children"] if child["name"] == "m_DynamicOccludee")
    assert dynamic["type"] == "UInt8"
    assert len(row["schemaNodeSha256"]) == 64
    assert len(row["fullSchemaSha256"]) == 64
    assert result["sourceCodeExecuted"] is False
    assert "not asserted equivalent" in result["schemaReadRelation"]


def test_worker_rejects_source_drift_object_drift_missing_schema_and_bad_version(tmp_path):
    _, job, env, serialized_sha, obj = worker_fixture(tmp_path)
    unitypy = NS(__version__="1.25.3", load=lambda raw: env)
    with patch.dict("sys.modules", UnityPy=unitypy):
        bad_source = dict(job, sourceSha256="0" * 64)
        with unittest.TestCase().assertRaisesRegex(ValueError, "Source bundle SHA256 drift"):
            extract(bad_source)
        job["wantedObjects"][0]["serializedFileSha256"] = "0" * 64
        with unittest.TestCase().assertRaisesRegex(ValueError, "Serialized file SHA256 drift"):
            extract(job)
        job["wantedObjects"][0]["serializedFileSha256"] = serialized_sha
        env.assets[0].unity_version = "6000.6.2f1"
        with unittest.TestCase().assertRaisesRegex(ValueError, "Unsupported source Unity version"):
            extract(job)
        env.assets[0].unity_version = "2021.3.30f1"
        obj.serialized_type.node = None
        with unittest.TestCase().assertRaisesRegex(ValueError, "TypeTree schema missing"):
            extract(job)
        obj.serialized_type.node = fixture_node()
        job["wantedObjects"][0]["rawSha256"] = "f" * 64
        with unittest.TestCase().assertRaisesRegex(ValueError, "Object raw SHA256 drift"):
            extract(job)


def test_worker_rejects_missing_or_ambiguous_exact_object_and_serialized_file(tmp_path):
    _, job, env, _, obj = worker_fixture(tmp_path)
    unitypy = NS(__version__="1.25.3", load=lambda raw: env)
    with patch.dict("sys.modules", UnityPy=unitypy):
        env.assets[0].objects = {}
        with unittest.TestCase().assertRaisesRegex(ValueError, "Typed object not found"):
            extract(job)
        env.assets[0].objects = {1: obj, 2: obj}
        with unittest.TestCase().assertRaisesRegex(ValueError, "Ambiguous typed object"):
            extract(job)
        env.assets[0].objects = {42: obj}
        env.assets.append(env.assets[0])
        with unittest.TestCase().assertRaisesRegex(ValueError, "Ambiguous serialized file"):
            extract(job)


def test_api_records_timeout_and_child_exit_without_accepting_old_result(tmp_path):
    source = tmp_path / "input.bundle"
    source.write_bytes(b"pinned")

    class TimedOutProcess:
        pid = 12345
        returncode = None

        def __init__(self):
            self.wait_calls = 0

        def wait(self, timeout=None):
            self.wait_calls += 1
            if self.wait_calls == 1:
                raise subprocess.TimeoutExpired("worker", timeout)
            self.returncode = -15
            return self.returncode

        def terminate(self):
            pass

        def kill(self):
            self.returncode = -9

        def poll(self):
            return self.returncode

    fake = TimedOutProcess()
    with patch("monkey.unity_prefab_schemas.subprocess.Popen", return_value=fake):
        receipt = extract_builtin_schemas(
            source,
            sha(source.read_bytes()),
            sys.executable,
            [wanted()],
            tmp_path / "new-output",
            budget_seconds=1,
        )
    assert receipt["status"] == "timeout"
    assert receipt["timedOut"] is True
    assert receipt["processExited"] is True
    assert receipt["exitCode"] == -15
    assert receipt["sourceUnchanged"] is True
    assert "objects" not in receipt


if __name__ == "__main__":
    unittest.main()
