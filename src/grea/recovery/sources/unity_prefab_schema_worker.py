"""One-source, one-process, read-only Unity built-in TypeTree extractor."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from grea.recovery.sources.unity_worker import PROVIDER_VERSION, full_schema, schema_node


MAX_SOURCE_BYTES = 128 * 1024 * 1024
MAX_RESULT_BYTES = 16 * 1024 * 1024
MAX_SERIALIZED_FILES = 64
MAX_SOURCE_OBJECTS = 250000
SUPPORTED_UNITY_VERSIONS = {"2021.3.30f1"}
MAX_WANTED_OBJECTS = 32
MAX_SCHEMA_NODES = 20000


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_sha(value) -> str:
    return _sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _read_source(path: Path, expected_sha: str) -> bytes:
    with path.open("rb") as stream:
        raw = stream.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError("Source bundle byte budget exceeded")
    if _sha(raw) != expected_sha:
        raise ValueError("Source bundle SHA256 drift")
    return raw


def extract(job: dict) -> dict:
    import UnityPy

    if UnityPy.__version__ != PROVIDER_VERSION:
        raise ValueError(f"Expected UnityPy {PROVIDER_VERSION}, got {UnityPy.__version__}")
    source = Path(job["sourcePath"])
    expected_source_sha = job["sourceSha256"]
    raw = _read_source(source, expected_source_sha)
    env = UnityPy.load(raw)
    assets = list(env.assets)
    if not assets:
        raise ValueError("Source bundle contains no serialized files")
    if len(assets) > MAX_SERIALIZED_FILES:
        raise ValueError("Serialized file count budget exceeded")
    if sum(len(asset.objects) for asset in assets) > MAX_SOURCE_OBJECTS:
        raise ValueError("Source object count budget exceeded")
    unsupported = sorted({asset.unity_version for asset in assets if asset.unity_version not in SUPPORTED_UNITY_VERSIONS})
    if unsupported:
        raise ValueError("Unsupported source Unity version(s): " + ", ".join(unsupported))

    results = []
    for requested in job["wantedObjects"]:
        file_matches = [asset for asset in assets if asset.name == requested["serializedFile"]]
        if not file_matches:
            raise ValueError(f"Serialized file not found: {requested['serializedFile']}")
        if len(file_matches) != 1:
            raise ValueError(f"Ambiguous serialized file name: {requested['serializedFile']}")
        asset = file_matches[0]
        serialized_raw = bytes(asset.reader.bytes)
        serialized_sha = _sha(serialized_raw)
        if requested.get("serializedFileSha256") and serialized_sha != requested["serializedFileSha256"]:
            raise ValueError(f"Serialized file SHA256 drift: {requested['serializedFile']}")

        wanted_path_id = int(requested["pathId"])
        object_matches = [obj for obj in asset.objects.values()
                          if obj.path_id == wanted_path_id and obj.type.name == requested["type"]]
        if not object_matches:
            raise ValueError(f"Typed object not found: {requested['serializedFile']}:{requested['pathId']}:{requested['type']}")
        if len(object_matches) != 1:
            raise ValueError(f"Ambiguous typed object: {requested['serializedFile']}:{requested['pathId']}:{requested['type']}")
        obj = object_matches[0]
        if obj.type.name == "MonoBehaviour":
            raise ValueError("MonoBehaviour schema extraction is excluded; use the existing exact schema path")
        raw_object = obj.get_raw_data()
        raw_object_sha = _sha(raw_object)
        if raw_object_sha != requested["rawSha256"]:
            raise ValueError(f"Object raw SHA256 drift: {requested['serializedFile']}:{requested['pathId']}")
        serialized_type = getattr(obj, "serialized_type", None)
        node = getattr(serialized_type, "node", None) if serialized_type is not None else None
        if node is None:
            raise ValueError(f"Built-in TypeTree schema missing: {requested['type']}")

        shaped = schema_node(node)
        flattened = full_schema(node)
        if len(flattened) > MAX_SCHEMA_NODES:
            raise ValueError(f"TypeTree node budget exceeded: {requested['type']}")
        shaped_sha = _canonical_sha(shaped)
        full_sha = _canonical_sha(flattened)
        results.append({
            "identity": {
                "sourceSha256": expected_source_sha,
                "serializedFile": asset.name,
                "serializedFileSha256": serialized_sha,
                "unityVersion": asset.unity_version,
                "targetPlatform": str(asset.target_platform),
                "pathId": str(obj.path_id),
                "type": obj.type.name,
                "classId": int(obj.type),
                "rawSha256": raw_object_sha,
            },
            "schemaNode": shaped,
            "schemaNodeSha256": shaped_sha,
            "fullSchema": flattened,
            "fullSchemaSha256": full_sha,
        })

    after = _read_source(source, expected_source_sha)
    if _sha(after) != expected_source_sha:
        raise ValueError("Source bundle changed during schema extraction")
    encoded = json.dumps(results, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_RESULT_BYTES:
        raise ValueError("Schema result byte budget exceeded")
    return {
        "schemaVersion": 1,
        "status": "schemas_read",
        "provider": {"name": "UnityPy", "version": UnityPy.__version__},
        "source": {"path": str(source), "bytes": len(raw), "sha256": expected_source_sha},
        "schemaReadRelation": "fresh pinned-bundle TypeTree read; not asserted equivalent to prior cached reader output",
        "sourceCodeExecuted": False,
        "objects": results,
    }


def main() -> int:
    if len(sys.argv) != 4 or sys.argv[1] != "--extract-builtin-schemas":
        raise SystemExit("usage: worker --extract-builtin-schemas JOB.json RESULT.json")
    job_path, result_path = Path(sys.argv[2]), Path(sys.argv[3])
    started = time.monotonic()
    try:
        job = json.loads(job_path.read_text(encoding="utf-8"))
        result = extract(job)
        result["performance"] = {"elapsedSeconds": round(time.monotonic() - started, 3)}
        encoded = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
        if len(encoded) > MAX_RESULT_BYTES:
            raise ValueError("Schema result byte budget exceeded")
        result_path.write_bytes(encoded)
        return 0
    except Exception as exc:
        error = {
            "schemaVersion": 1,
            "status": "failed",
            "error": {"type": type(exc).__name__, "message": str(exc).splitlines()[0][:500]},
            "sourceCodeExecuted": False,
            "performance": {"elapsedSeconds": round(time.monotonic() - started, 3)},
        }
        result_path.write_text(json.dumps(error, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
