"""Plan exact native Sprite reconstruction for a source-embedded Sprite object.

This module reuses pinned source-graph, hydration and unity_sprite geometry evidence.
It never turns Sprite.m_RenderDataKey or a basename into a native asset identity.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

from .io import encoded, load, safe, read


MAX_GRAPH_BYTES = 64 * 1024 * 1024
MAX_SOURCE_INPUTS_BYTES = 16 * 1024 * 1024
MAX_TYPED_RECEIPT_BYTES = 64 * 1024 * 1024
MAX_SOURCE_CONTAINER_BYTES = 128 * 1024 * 1024
MAX_PREPARED_BYTES = 16 * 1024 * 1024
MAX_PREPARE_JOB_BYTES = 16 * 1024 * 1024
MAX_CACHE_BYTES = 4 * 1024 * 1024
MAX_OBJECT_ROWS = 250_000
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class EmbeddedSpritePlanError(ValueError):
    """Exact source/pixel/geometry evidence is missing or inconsistent."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pinned_json(path: str | Path, expected_sha256: str, max_bytes: int, label: str) -> tuple[dict[str, Any], bytes, Path]:
    path = safe(path)
    if not path.is_file():
        raise EmbeddedSpritePlanError(f"{label}: expected one file")
    size = path.stat().st_size
    if size > max_bytes:
        raise EmbeddedSpritePlanError(f"{label}: byte budget exceeded")
    raw = read(path, max_bytes=max_bytes)
    if _sha(raw) != expected_sha256:
        raise EmbeddedSpritePlanError(f"{label}: pinned SHA256 drift")
    try:
        data = load(raw, max_nodes=8_000_000)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EmbeddedSpritePlanError(f"{label}: invalid JSON") from exc
    if not isinstance(data, dict):
        raise EmbeddedSpritePlanError(f"{label}: root must be an object")
    return data, raw, path


def _read_pinned_list(path: str | Path, expected_sha256: str, max_bytes: int, label: str) -> tuple[list[Any], bytes, Path]:
    path = safe(path)
    if not path.is_file() or path.stat().st_size > max_bytes:
        raise EmbeddedSpritePlanError(f"{label}: missing file or byte budget exceeded")
    raw = read(path, max_bytes=max_bytes)
    if _sha(raw) != expected_sha256:
        raise EmbeddedSpritePlanError(f"{label}: pinned SHA256 drift")
    try:
        data = load(raw, max_nodes=8_000_000)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EmbeddedSpritePlanError(f"{label}: invalid JSON") from exc
    if not isinstance(data, list):
        raise EmbeddedSpritePlanError(f"{label}: root must be a list")
    return data, raw, path


def _pinned_bytes(path: str | Path, expected_sha256: str, expected_bytes: int | None, max_bytes: int, label: str) -> tuple[bytes, Path]:
    path = safe(path)
    size = path.stat().st_size if path.is_file() else -1
    if not path.is_file() or (expected_bytes is not None and size != expected_bytes) or size > max_bytes:
        raise EmbeddedSpritePlanError(f"{label}: missing file or byte budget/length mismatch")
    raw = read(path, max_bytes=max_bytes)
    if _sha(raw) != expected_sha256:
        raise EmbeddedSpritePlanError(f"{label}: pinned SHA256 drift")
    return raw, path


def _hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise EmbeddedSpritePlanError(f"{label}: expected lowercase SHA256")
    return value


def _path_id(value: Any, label: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise EmbeddedSpritePlanError(f"{label}: expected signed 64-bit PathID")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise EmbeddedSpritePlanError(f"{label}: invalid PathID") from exc
    if str(number) != str(value) or not -(1 << 63) <= number < (1 << 63):
        raise EmbeddedSpritePlanError(f"{label}: noncanonical/out-of-range PathID")
    return str(number)


def _identity_key(identity: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    return tuple(str(identity.get(key, "")) for key in
                 ("containerSha256", "serializedFile", "serializedFileSha256", "pathId", "rawSha256"))


def _validate_geometry_descriptor(
    descriptor: Mapping[str, Any], *,
    sprite_data: Mapping[str, Any],
    sprite_raw_sha256: str,
    texture_rgba_sha256: str,
    texture_width: int,
    texture_height: int,
    pixels_per_unit: float,
    source_settings_raw: int,
) -> tuple[dict[str, Any], str]:
    if not isinstance(descriptor, Mapping):
        raise EmbeddedSpritePlanError("unpacked_tight_geometry descriptor is required")
    if descriptor.get("geometryProfile") != "unity-2021.3-unpacked-tight-v1":
        raise EmbeddedSpritePlanError("geometry descriptor is not the strict unpacked-tight profile")
    if source_settings_raw != 64:
        raise EmbeddedSpritePlanError("only the pinned unpacked source settingsRaw=64 profile is supported")
    expected_sprite_data_sha = _sha(encoded(dict(sprite_data)))
    if descriptor.get("sourceSpriteDataSha256") != expected_sprite_data_sha:
        raise EmbeddedSpritePlanError("geometry descriptor source Sprite data hash differs")
    if descriptor.get("textureRgbaRawSha256") != texture_rgba_sha256:
        raise EmbeddedSpritePlanError("geometry descriptor pixel hash differs from pinned hydration")
    if descriptor.get("textureWidth") != texture_width or descriptor.get("textureHeight") != texture_height:
        raise EmbeddedSpritePlanError("geometry descriptor texture dimensions differ")
    if type(descriptor.get("pixelsToUnits")) not in (int, float) or not math.isfinite(descriptor["pixelsToUnits"]) or not math.isclose(float(descriptor["pixelsToUnits"]), pixels_per_unit, rel_tol=0, abs_tol=1e-7):
        raise EmbeddedSpritePlanError("geometry descriptor pixels-per-unit differs from source Sprite")
    if descriptor.get("verifyMesh") is not True:
        raise EmbeddedSpritePlanError("geometry descriptor is not marked for exact mesh verification")
    vertices = descriptor.get("meshVertices")
    uv = descriptor.get("meshUv")
    triangles = descriptor.get("triangleIndices")
    if not isinstance(vertices, list) or not isinstance(uv, list) or not isinstance(triangles, list) or len(vertices) < 3 or len(vertices) != len(uv):
        raise EmbeddedSpritePlanError("geometry descriptor mesh arrays are malformed")
    if len(triangles) == 0 or len(triangles) % 3:
        raise EmbeddedSpritePlanError("geometry descriptor triangle index count is invalid")
    for index, row in enumerate(vertices):
        if not isinstance(row, Mapping) or any(type(row.get(k)) not in (int, float) or not math.isfinite(row[k]) for k in ("x", "y")):
            raise EmbeddedSpritePlanError(f"geometry vertex {index} is malformed")
    for index, row in enumerate(uv):
        if not isinstance(row, Mapping) or any(type(row.get(k)) not in (int, float) or not math.isfinite(row[k]) or not 0 <= row[k] <= 1 for k in ("x", "y")):
            raise EmbeddedSpritePlanError(f"geometry UV {index} is malformed/outside normalized texture bounds")
    if any(type(value) is not int or value < 0 or value >= len(vertices) for value in triangles):
        raise EmbeddedSpritePlanError("geometry triangle index is outside the vertex array")
    geometry_sha = _hash(descriptor.get("geometrySha256"), "geometrySha256")
    payload = {key: value for key, value in descriptor.items() if key != "geometrySha256"}
    if _sha(encoded(payload)) != geometry_sha:
        raise EmbeddedSpritePlanError("geometry descriptor hash does not match its fields")
    # The shared unpacked geometry profile must remain attached to this exact Sprite.
    if descriptor.get("sourceSpriteRawSha256", sprite_raw_sha256) != sprite_raw_sha256:
        raise EmbeddedSpritePlanError("geometry descriptor Sprite raw hash differs")
    return dict(payload), geometry_sha


def plan_embedded_sprite_rebuild(
    *,
    source_graph_path: str | Path,
    source_graph_sha256: str,
    source_inputs_path: str | Path,
    source_inputs_sha256: str,
    prepared_path: str | Path,
    prepared_sha256: str,
    prepare_job_path: str | Path,
    prepare_job_sha256: str,
    source_sprite_identity: Mapping[str, Any],
    source_settings_raw: int,
    geometry_descriptor_path: str | Path,
    geometry_descriptor_sha256: str,
    target_asset_root: str = "Assets/Game/Content/Images/EmbeddedSprites",
) -> dict[str, Any]:
    """Produce a deterministic independent native Sprite creation plan.

    The plan uses a source Sprite's exact local Texture2D PPtr, typed-object hash,
    prepared cache bytes and decoded RGBA hash, and strict unpacked mesh descriptor.
    Unity GUID/localID are left pending until the Editor creates and verifies the
    independent asset.
    """
    graph, _, graph_path = _pinned_json(source_graph_path, source_graph_sha256, MAX_GRAPH_BYTES, "source graph")
    source_inputs, _, source_inputs_file = _read_pinned_list(source_inputs_path, source_inputs_sha256,
                                                             MAX_SOURCE_INPUTS_BYTES, "source inputs receipt")
    prepared, _, prepared_file = _pinned_json(prepared_path, prepared_sha256, MAX_PREPARED_BYTES, "prepared hydration receipt")
    prepare_job, _, prepare_job_file = _pinned_json(prepare_job_path, prepare_job_sha256, MAX_PREPARE_JOB_BYTES, "prepare job")
    geometry_descriptor, _, geometry_path = _pinned_json(geometry_descriptor_path, geometry_descriptor_sha256,
                                                          1024 * 1024, "unpacked Sprite geometry descriptor")

    if graph.get("sourceUnityVersions") != ["2021.3.30f1"]:
        raise EmbeddedSpritePlanError("source graph must pin only Unity 2021.3.30f1")
    source_id = {
        "containerSha256": _hash(source_sprite_identity.get("containerSha256"), "source sprite containerSha256"),
        "serializedFile": source_sprite_identity.get("serializedFile"),
        "serializedFileSha256": _hash(source_sprite_identity.get("serializedFileSha256"), "source sprite serializedFileSha256"),
        "pathId": _path_id(source_sprite_identity.get("pathId"), "source sprite pathId"),
        "rawSha256": _hash(source_sprite_identity.get("rawSha256"), "source sprite rawSha256"),
        "type": "Sprite",
    }
    if not isinstance(source_id["serializedFile"], str) or not source_id["serializedFile"]:
        raise EmbeddedSpritePlanError("source Sprite serializedFile is required")
    input_rows = [row for row in source_inputs if isinstance(row, dict) and row.get("sourceSha256") == source_id["containerSha256"]]
    if len(input_rows) != 1:
        raise EmbeddedSpritePlanError(f"source inputs receipt has {len(input_rows)} exact container rows")
    source_input = input_rows[0]
    if source_input.get("sourcePath") is None:
        raise EmbeddedSpritePlanError("source inputs receipt lacks original container path")
    source_raw, source_path = _pinned_bytes(source_input["sourcePath"], source_id["containerSha256"],
                                           source_input.get("sourceBytes", source_input.get("bytes")), MAX_SOURCE_CONTAINER_BYTES,
                                           "original source container")
    typed_raw, typed_path = _pinned_bytes(source_input.get("typedObjectsPath", ""),
                                          source_input.get("typedObjectsSha256", ""),
                                          source_input.get("typedObjectsBytes"),
                                          MAX_TYPED_RECEIPT_BYTES, "prior typed-object receipt")
    try:
        typed_receipt = json.loads(typed_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EmbeddedSpritePlanError("prior typed-object receipt is invalid JSON") from exc
    if not isinstance(typed_receipt, dict) or typed_receipt.get("source", {}).get("sha256") != source_id["containerSha256"]:
        raise EmbeddedSpritePlanError("prior typed-object receipt container identity differs")
    if typed_receipt.get("provider") != {"name": "UnityPy", "version": "1.25.3"}:
        raise EmbeddedSpritePlanError("prior typed-object reader is not the pinned UnityPy 1.25.3")
    typed_files = [row for row in typed_receipt.get("files", []) if row.get("name") == source_id["serializedFile"]]
    if len(typed_files) != 1 or typed_files[0].get("serializedFileSha256") != source_id["serializedFileSha256"]:
        raise EmbeddedSpritePlanError("prior typed receipt lacks exact serializedFile SHA")
    typed_objects = [row for row in typed_receipt.get("objects", [])
                     if str(row.get("file")) == "0" and row.get("pathId") == source_id["pathId"]
                     and row.get("type") == "Sprite" and row.get("rawSha256") == source_id["rawSha256"]]
    if len(typed_objects) != 1:
        raise EmbeddedSpritePlanError(f"prior typed receipt has {len(typed_objects)} exact Sprite rows")
    reachable = graph.get("reachableObjects")
    if not isinstance(reachable, list) or len(reachable) > MAX_OBJECT_ROWS:
        raise EmbeddedSpritePlanError("source graph object list is missing or exceeds budget")
    def exact_rows(identity: Mapping[str, Any], object_type: str) -> list[dict[str, Any]]:
        return [row for row in reachable if isinstance(row, dict)
                and row.get("type") == object_type
                and _identity_key({**row.get("identity", {}), "rawSha256": row.get("rawSha256")}) ==
                    (source_id["containerSha256"], source_id["serializedFile"], source_id["serializedFileSha256"], identity["pathId"], identity["rawSha256"])]
    sprites = exact_rows(source_id, "Sprite")
    if len(sprites) != 1:
        raise EmbeddedSpritePlanError(f"source Sprite exact identity resolved {len(sprites)} graph rows")
    sprite = sprites[0]
    sprite_data = sprite.get("data")
    if not isinstance(sprite_data, dict):
        raise EmbeddedSpritePlanError("source Sprite typed data is missing")
    render = sprite_data.get("m_RD")
    texture_pointer = render.get("texture") if isinstance(render, dict) else None
    if not isinstance(texture_pointer, dict) or texture_pointer.get("$type") != "UnityPPtr":
        raise EmbeddedSpritePlanError("source Sprite m_RD.texture is not a typed PPtr")
    if _path_id(texture_pointer.get("fileId"), "source Sprite texture fileId") != "0":
        raise EmbeddedSpritePlanError("source Sprite texture is not local to the pinned serialized file")
    texture_path_id = _path_id(texture_pointer.get("pathId"), "source Sprite texture pathId")
    texture_candidates = [row for row in reachable if isinstance(row, dict) and row.get("type") == "Texture2D"
                          and row.get("identity", {}).get("containerSha256") == source_id["containerSha256"]
                          and row.get("identity", {}).get("serializedFile") == source_id["serializedFile"]
                          and row.get("identity", {}).get("serializedFileSha256") == source_id["serializedFileSha256"]
                          and _path_id(row.get("identity", {}).get("pathId"), "graph Texture2D pathId") == texture_path_id]
    if len(texture_candidates) != 1:
        raise EmbeddedSpritePlanError(f"source Sprite texture PPtr resolved {len(texture_candidates)} exact Texture2D rows")
    texture = texture_candidates[0]
    texture_id = {"containerSha256": source_id["containerSha256"], "serializedFile": source_id["serializedFile"],
                  "serializedFileSha256": source_id["serializedFileSha256"], "pathId": texture_path_id,
                  "rawSha256": _hash(texture.get("rawSha256"), "source Texture2D rawSha256"), "type": "Texture2D"}
    texture_data = texture.get("data")
    texture_payload = texture.get("texturePayload")
    if not isinstance(texture_data, dict) or not isinstance(texture_payload, dict):
        raise EmbeddedSpritePlanError("source Texture2D fields or texture payload receipt is missing")
    if texture_payload.get("kind") != "external-key-token-candidate" or texture_payload.get("nativePixelsVerified") is not False:
        raise EmbeddedSpritePlanError("source Texture2D does not have the expected unresolved external-key wire form")
    wire_key = texture_payload.get("key")
    logical_path = f"Assets/Textures/astc/{texture_data.get('m_Width')}/{wire_key}.txt"
    if not isinstance(wire_key, str) or not wire_key or texture_payload.get("wireKey") != wire_key:
        raise EmbeddedSpritePlanError("source Texture2D external key is malformed")
    width, height = texture_data.get("m_Width"), texture_data.get("m_Height")
    if (type(width) is not int or type(height) is not int or width <= 0 or height <= 0
            or texture_data.get("m_TextureFormat") != 34 or texture_data.get("m_MipCount") != 1):
        raise EmbeddedSpritePlanError("source Texture2D is outside the exact ASTC8x8 single-mip profile")
    if texture_data.get("m_StreamData", {}).get("size") != 0 or texture_data.get("m_StreamData", {}).get("path") != "":
        raise EmbeddedSpritePlanError("source Texture2D stream layout is unsupported")

    resolved_rows = []
    for container in prepared.get("rows", []):
        source = container.get("source", {}) if isinstance(container, dict) else {}
        if source.get("sha256") == source_id["containerSha256"]:
            resolved_rows.append(container)
    if len(resolved_rows) != 1:
        raise EmbeddedSpritePlanError(f"prepared receipt has {len(resolved_rows)} rows for exact source container")
    resolved = [row for row in resolved_rows[0].get("resolved", [])
                if row.get("file") == source_id["serializedFile"] and _path_id(row.get("pathId"), "hydration pathId") == texture_path_id]
    if len(resolved) != 1:
        raise EmbeddedSpritePlanError(f"prepared receipt has {len(resolved)} hydration rows for exact Sprite texture")
    hydration = resolved[0]
    if hydration.get("logicalPath") != logical_path:
        raise EmbeddedSpritePlanError("hydration logical key differs from source Texture2D wire key")
    if hydration.get("cacheBytes", 0) > MAX_CACHE_BYTES:
        raise EmbeddedSpritePlanError("hydration cache byte budget exceeded")
    cache_sha = _hash(hydration.get("cacheSha256"), "hydration cacheSha256")
    rgba_sha = _hash(hydration.get("rgbaRawSha256"), "hydration rgbaRawSha256")
    astc = hydration.get("astc", {})
    if astc.get("width") != width or astc.get("height") != height or astc.get("block") != 8:
        raise EmbeddedSpritePlanError("hydration ASTC block/dimensions differ from exact source Texture2D")

    cache_rows = [row for row in prepare_job.get("cache", []) if isinstance(row, dict) and row.get("logicalPath") == logical_path]
    if len(cache_rows) != 1:
        raise EmbeddedSpritePlanError(f"prepare job has {len(cache_rows)} exact cache-key entries")
    cache_row = cache_rows[0]
    if cache_row.get("sha256") != cache_sha or cache_row.get("bytes") != hydration.get("cacheBytes"):
        raise EmbeddedSpritePlanError("prepare job cache pin differs from prepared hydration receipt")
    cache_path = safe(cache_row.get("path", ""))
    cache_raw = read(cache_path, max_bytes=MAX_CACHE_BYTES)
    if len(cache_raw) > MAX_CACHE_BYTES or len(cache_raw) != cache_row["bytes"] or _sha(cache_raw) != cache_sha:
        raise EmbeddedSpritePlanError("exact hydration cache file bytes/hash differ from pinned receipt")
    if prepared.get("pixelsFabricated") is not False or resolved_rows[0].get("pixelsFabricated") is not False:
        raise EmbeddedSpritePlanError("prepared receipt does not prove source pixels were not fabricated")

    rect = sprite_data.get("m_Rect")
    pivot = sprite_data.get("m_Pivot")
    border = sprite_data.get("m_Border")
    pixels_per_unit = sprite_data.get("m_PixelsToUnits")
    if not isinstance(rect, dict) or not isinstance(pivot, dict) or not isinstance(border, dict):
        raise EmbeddedSpritePlanError("source Sprite rect/pivot/border evidence is incomplete")
    if any(type(rect.get(k)) not in (int, float) or not math.isfinite(rect[k]) for k in ("x", "y", "width", "height")):
        raise EmbeddedSpritePlanError("source Sprite rect is malformed")
    if type(pixels_per_unit) not in (int, float) or not math.isfinite(pixels_per_unit) or pixels_per_unit <= 0:
        raise EmbeddedSpritePlanError("source Sprite pixels-per-unit is invalid")
    if any(type(pivot.get(k)) not in (int, float) or not math.isfinite(pivot[k]) for k in ("x", "y")):
        raise EmbeddedSpritePlanError("source Sprite pivot is malformed")
    if any(type(border.get(k)) not in (int, float) or not math.isfinite(border[k]) for k in ("x", "y", "z", "w")):
        raise EmbeddedSpritePlanError("source Sprite border is malformed")
    if source_settings_raw != 64:
        raise EmbeddedSpritePlanError("only the pinned unpacked-tight Sprite settingsRaw=64 profile is supported")

    geometry_payload, geometry_sha = _validate_geometry_descriptor(
        geometry_descriptor, sprite_data=sprite_data, sprite_raw_sha256=source_id["rawSha256"],
        texture_rgba_sha256=rgba_sha, texture_width=width, texture_height=height,
        pixels_per_unit=float(pixels_per_unit), source_settings_raw=source_settings_raw)

    uses = []
    sprite_identity_json = json.dumps(source_id, sort_keys=True, separators=(",", ":"))
    for row in graph.get("reachableObjects", []):
        for edge in row.get("referenceEdges", []):
            if _path_id(edge.get("pathId"), "source edge pathId") != source_id["pathId"]:
                continue
            if not edge.get("location", "").endswith("m_Sprite"):
                continue
            if row.get("identity", {}).get("containerSha256") != source_id["containerSha256"]:
                continue
            uses.append({"sourceComponentIdentity": row.get("identity"), "sourceComponentType": row.get("type"),
                         "sourceComponentRawSha256": row.get("rawSha256"), "sourceFieldPath": edge.get("location"),
                         "sourceObjectId": edge.get("sourceObjectId"), "targetSourceObjectId": edge.get("targetSourceObjectId")})

    identity_payload = {
        "sourceSpriteIdentity": source_id,
        "sourceTextureIdentity": texture_id,
        "textureRgbaRawSha256": rgba_sha,
        "geometrySha256": geometry_sha,
        "sourceSettingsRaw": source_settings_raw,
        "sourcePixelsPerUnit": float(pixels_per_unit),
        "sourceRect": rect,
        "sourcePivot": pivot,
        "sourceBorder": border,
    }
    stable_key = _sha(encoded(identity_payload))
    if not isinstance(target_asset_root, str) or not target_asset_root.startswith("Assets/") or ".." in Path(target_asset_root).parts:
        raise EmbeddedSpritePlanError("target_asset_root must be a safe Assets-relative directory")
    target_dir = target_asset_root.rstrip("/")
    target_name = "embedded-sprite-" + stable_key
    texture_asset_path = f"{target_dir}/{target_name}-texture.asset"
    sprite_asset_path = f"{target_dir}/{target_name}-sprite.asset"
    return {
        "schemaVersion": 1,
        "status": "native_sprite_rebuild_plan",
        "sourceUnityVersion": "2021.3.30f1",
        "sourceSpriteIdentity": source_id,
        "sourceTextureIdentity": texture_id,
        "sourceTextureHydration": {"logicalPath": logical_path, "cachePath": str(cache_path),
                                   "cacheBytes": len(cache_raw), "cacheSha256": cache_sha,
                                   "rgbaRawSha256": rgba_sha, "width": width, "height": height,
                                   "textureFormat": texture_data["m_TextureFormat"], "mipCount": texture_data["m_MipCount"],
                                   "prepareJobPath": str(prepare_job_file), "prepareJobSha256": prepare_job_sha256,
                                   "preparedReceiptPath": str(prepared_file), "preparedReceiptSha256": prepared_sha256},
        "sourceSpriteDescriptor": {"name": sprite_data.get("m_Name"), "rect": rect, "pivot": pivot,
                                   "border": border, "pixelsPerUnit": float(pixels_per_unit),
                                   "extrude": sprite_data.get("m_Extrude"), "isPolygon": sprite_data.get("m_IsPolygon"),
                                   "settingsRaw": source_settings_raw, "geometry": geometry_payload,
                                   "geometrySha256": geometry_sha,
                                   "geometryDescriptorPath": str(geometry_path),
                                   "geometryDescriptorSha256": geometry_descriptor_sha256},
        "sourceFieldUses": uses,
        "identityKeySha256": stable_key,
        "target": {
            "texturePath": texture_asset_path,
            "spriteAssetPath": sprite_asset_path,
            "spriteName": sprite_data.get("m_Name"),
            "expectedTexture": {"rgbaRawSha256": rgba_sha, "width": width, "height": height,
                                "mipCount": 1, "pixelsPerUnit": float(pixels_per_unit)},
            "expectedSprite": {"rect": rect, "pivot": pivot, "border": border,
                               "meshVertices": geometry_payload["meshVertices"],
                               "triangleIndices": geometry_payload["triangleIndices"],
                               "meshUv": geometry_payload["meshUv"], "packing": "unpacked-tight"},
            "nativeGuid": None,
            "nativeLocalFileID": None,
            "nativeIdentityStatus": "pending_editor_createasset_and_readback",
            "creationContract": "independent decoded Texture2D plus native Sprite.Create and SerializedObject source buffers; do not copy source RenderDataKey",
        },
        "provenance": {"sourceGraphPath": str(graph_path), "sourceGraphSha256": source_graph_sha256,
                       "sourceInputsPath": str(source_inputs_file), "sourceInputsSha256": source_inputs_sha256,
                       "sourceContainerPath": str(source_path), "sourceContainerBytes": len(source_raw),
                       "priorTypedReceiptPath": str(typed_path), "priorTypedReceiptSha256": source_input["typedObjectsSha256"],
                       "priorReaderContractSha256": source_input.get("cacheReaderContractSha256"),
                       "priorCacheScope": source_input.get("cacheScope"),
                       "newReaderEquivalenceClaim": False,
                       "preparedPixelsWereFabricated": False, "sourceCodeExecuted": False,
                       "m_RenderDataKeyUsedAsIdentity": False},
        "nativeAssetDatabaseVerified": False,
        "limitations": ["This is a deterministic creation plan, not a created Unity asset or native GUID/localID receipt.",
                        "Unity import, Sprite geometry/pixel roundtrip, save and cold reopen remain Editor-owned verification."],
    }
