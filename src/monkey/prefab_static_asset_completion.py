"""Bounded source evidence and payloads for missing static SpriteFrame closure."""
from __future__ import annotations

import copy
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import uuid
from io import BytesIO
from urllib.parse import unquote, urlsplit

from PIL import Image

from . import io
from .normalize import open_texture, sprite as normalize_sprite
from .sources.bundle import Bundle


SCHEMA = "monkey-prefab-static-source-resource-completion/1"
_SAFE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_CACHE_BASENAME = re.compile(r"^[A-Za-z0-9_.-]{1,200}$")
_MAX_NATIVE = 32 * 1024 * 1024
_MAX_PIXELS = 16_777_216


class StaticAssetCompletionError(ValueError):
    pass


def _digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _load(plan: dict, source_manifest: str | Path):
    path = io.safe(source_manifest)
    raw = io.read(path, max_bytes=128 * 1024 * 1024)
    manifest = io.load(raw, max_nodes=16_000_000)
    digest = _digest(raw)
    if manifest.get("schemaVersion") != 1 or not isinstance(manifest.get("assets"), list):
        raise StaticAssetCompletionError("unsupported source-manifest schema")
    if plan.get("sourceManifestSha256") != digest:
        raise StaticAssetCompletionError("source manifest differs from frozen plan pin")
    if isinstance(plan.get("sourceManifestPath"), str) and io.safe(plan["sourceManifestPath"]) != path:
        raise StaticAssetCompletionError("source manifest path differs from frozen plan")
    return path, raw, manifest, digest


def _input_rows(manifest: dict) -> dict[tuple[str, str], dict]:
    result = {}
    for row in manifest.get("inputs") or []:
        if not isinstance(row, dict):
            continue
        key = (row.get("bundle"), row.get("path"))
        if not all(isinstance(value, str) for value in key) or key in result:
            raise StaticAssetCompletionError("source manifest has an invalid or duplicate input identity")
        result[key] = row
    return result


def _missing_refs(plan: dict, manifest: dict) -> tuple[list[str], list[dict]]:
    assets = {row.get("sourceId"): row for row in manifest.get("assets") or []
              if isinstance(row, dict) and isinstance(row.get("sourceId"), str)}
    refs: dict[str, list[dict]] = {}
    for component in plan.get("components") or []:
        if not isinstance(component, dict) or component.get("type") != "cc.Sprite":
            continue
        source_id = component.get("spriteFrame")
        if not isinstance(source_id, str) or not source_id:
            continue
        asset = assets.get(source_id)
        doc = asset.get("document") if isinstance(asset, dict) else None
        rows = doc.get("instances") if isinstance(doc, dict) else None
        root = doc.get("root") if isinstance(doc, dict) else None
        valid = (isinstance(rows, list) and type(root) is int and 0 <= root < len(rows)
                 and isinstance(rows[root], dict) and rows[root].get("__type__") == "cc.SpriteFrame")
        if not valid:
            refs.setdefault(source_id, []).append(component)
    return sorted(refs), [component for sid in sorted(refs) for component in refs[sid]]


def _source_parts(source_id: str) -> tuple[str, str]:
    if not isinstance(source_id, str) or ":" not in source_id:
        raise StaticAssetCompletionError("source asset ID must include a bundle")
    bundle, key = source_id.split(":", 1)
    if not _SAFE.fullmatch(bundle) or not _SAFE.fullmatch(key):
        raise StaticAssetCompletionError("source asset ID is not a safe config-declared token")
    return bundle, key


def _config_for(bundle_name: str, manifest: dict, rows: dict[tuple[str, str], dict]) -> tuple[Path, Bundle]:
    root_value = (manifest.get("sourceRoots") or {}).get(bundle_name)
    if not isinstance(root_value, str):
        raise StaticAssetCompletionError("source manifest has no selected bundle source root")
    matches = [(relative, row) for (bundle, relative), row in rows.items()
               if bundle == bundle_name and re.fullmatch(r"config\.[A-Za-z0-9_-]+\.json", PurePosixPath(relative).name)]
    if len(matches) != 1:
        raise StaticAssetCompletionError("source manifest must pin exactly one selected config for the bundle")
    relative, pin = matches[0]
    root = io.safe(root_value)
    path = io.inside(root, relative)
    raw = io.read(path, max_bytes=32 * 1024 * 1024)
    if len(raw) != pin.get("bytes") or _digest(raw) != pin.get("sha256"):
        raise StaticAssetCompletionError("bundle config differs from the old manifest input pin")
    reader = Bundle(path)
    if reader.config.get("name") != bundle_name:
        raise StaticAssetCompletionError("bundle config name differs from the source asset ID")
    return path, reader


def _config_index(reader: Bundle, key: str) -> int:
    value = reader.lookup.get(key)
    if type(value) is not int or not 0 <= value < len(reader.keys):
        raise StaticAssetCompletionError("asset ID is not declared exactly by bundle config: " + key)
    return value


def _root(asset: dict, kind: str, source_id: str) -> dict:
    doc = asset.get("document")
    rows = doc.get("instances") if isinstance(doc, dict) else None
    index = doc.get("root") if isinstance(doc, dict) else None
    if not isinstance(rows, list) or type(index) is not int or not 0 <= index < len(rows):
        raise StaticAssetCompletionError("bounded source reader returned no root document: " + source_id)
    value = rows[index]
    if not isinstance(value, dict) or value.get("__type__") != kind:
        raise StaticAssetCompletionError("bounded source reader returned wrong source type: " + source_id)
    return value


def _resource_cache_root(source_root: Path) -> Path:
    for parent in [source_root, *list(source_root.parents)[:8]]:
        candidate = parent / "resource-cache"
        if candidate.is_dir() and (candidate / "cacheList.json").is_file():
            return io.safe(candidate)
    raise StaticAssetCompletionError("bounded ancestor lookup found no resource-cache/cacheList.json")


def _cache_evidence(cache_root: Path, bundle: str, native_relative: str, native_raw: bytes) -> dict:
    index_path = io.inside(cache_root, "cacheList.json")
    index_raw = io.read(index_path, max_bytes=32 * 1024 * 1024)
    index = io.load(index_raw, max_nodes=2_000_000)
    files = index.get("files") if isinstance(index, dict) else None
    if not isinstance(files, dict) or len(files) > 200_000:
        raise StaticAssetCompletionError("cacheList is absent or exceeds bounded entry count")
    suffix = "/" + bundle + "/" + native_relative
    matches = []
    for url, value in files.items():
        parsed = urlsplit(url) if isinstance(url, str) else None
        path = unquote(parsed.path) if parsed else ""
        if isinstance(value, dict) and value.get("bundle") == bundle and path.endswith(suffix):
            matches.append((url, value))
    if len(matches) != 1:
        raise StaticAssetCompletionError("no unique cacheList entry for config-selected native version")
    source_url, value = matches[0]
    cached_url = value.get("url")
    parsed = urlsplit(cached_url) if isinstance(cached_url, str) else None
    if parsed is None or (parsed.scheme, parsed.netloc, parsed.query, parsed.fragment) != ("wxfile", "usr", "", ""):
        raise StaticAssetCompletionError("cacheList destination is not a supported wxfile path")
    parts = PurePosixPath(unquote(parsed.path)).parts
    if (len(parts) != 4 or parts[:3] != ("/", "gamecaches", bundle)
            or not _CACHE_BASENAME.fullmatch(parts[3]) or parts[3] in (".", "..")):
        raise StaticAssetCompletionError("cacheList destination escapes the selected bundle cache")
    relative = bundle + "/" + parts[3]
    payload_path = io.inside(cache_root, relative)
    payload = io.read(payload_path, max_bytes=_MAX_NATIVE)
    if payload != native_raw:
        raise StaticAssetCompletionError("source native file and exact cacheList payload differ")
    return {"cacheListPath": str(index_path), "cacheListBytes": len(index_raw),
            "cacheListSha256": _digest(index_raw), "cacheListRaw": index_raw,
            "sourceCdnUrl": source_url, "cacheEntry": copy.deepcopy(value),
            "cachedPayloadPath": str(payload_path), "cachedPayloadRelativePath": relative,
            "cachedPayloadBytes": len(payload), "cachedPayloadSha256": _digest(payload),
            "cachedPayloadRaw": payload}


def _safe_logical_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value or "\x00" in value or ":" in value:
        raise StaticAssetCompletionError("config-declared texture path is absent or unsafe")
    parts = PurePosixPath(value).parts
    if not parts or any(part in ("", ".", "..") or any(ord(ch) < 32 for ch in part) for part in parts):
        raise StaticAssetCompletionError("config-declared texture path contains traversal or control characters")
    if parts[0] in ("Texture", "Textures"):
        parts = parts[1:]
    if not parts:
        raise StaticAssetCompletionError("config-declared texture path has no filename")
    return PurePosixPath(*parts)


def _unique_target(target: PurePosixPath, identity: str, occupied: dict[str, str]) -> str:
    value = target.as_posix()
    previous = occupied.get(value)
    if value in occupied and previous != identity:
        suffix = _digest(identity.encode("utf-8"))[:10]
        value = target.with_name(target.stem + "__" + suffix + target.suffix).as_posix()
        if value in occupied and occupied[value] != identity:
            raise StaticAssetCompletionError("target path remains ambiguous after identity suffix")
    occupied[value] = identity
    return value


def _unity_guid(namespace: str, source_id: str) -> str:
    """Match the existing Unity target contract: guid(namespace, sourceId)."""
    return uuid.uuid5(uuid.NAMESPACE_URL, "monkey/" + namespace + "/" + source_id).hex


def _creator_uuid(namespace: str, source_id: str) -> str:
    """Match targets.cocos.identity for the configured Creator 3.8.8 target."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "monkey/" + namespace + "/creator-3.8.8/" + source_id))


def _unity_meta(guid: str, sprite: bool, border: list[int] | None = None) -> bytes:
    left, top, right, bottom = border or [0, 0, 0, 0]
    type_id = 8 if sprite else 0
    sprite_fields = ("  spriteMode: 1\n  spriteExtrude: 1\n  spriteMeshType: 0\n"
                     "  alignment: 0\n  spritePivot: {x: 0.5, y: 0.5}\n"
                     "  spritePixelsToUnits: 100\n"
                     f"  spriteBorder: {{x: {left}, y: {bottom}, z: {right}, w: {top}}}\n"
                     "  spriteGenerateFallbackPhysicsShape: 1\n") if sprite else ""
    return (f"fileFormatVersion: 2\nguid: {guid}\nTextureImporter:\n"
            "  internalIDToNameTable: []\n  externalObjects: {}\n  serializedVersion: 13\n"
            "  mipmaps:\n    mipMapMode: 0\n    enableMipMap: 0\n    sRGBTexture: 1\n"
            "  isReadable: 0\n  streamingMipmaps: 0\n  textureShape: 1\n"
            "  textureSettings:\n    serializedVersion: 2\n    filterMode: 1\n    aniso: 1\n"
            "    mipBias: 0\n    wrapU: 1\n    wrapV: 1\n    wrapW: 1\n" + sprite_fields +
            f"  textureType: {type_id}\n  alphaUsage: 1\n  alphaIsTransparency: 1\n"
            "  textureCompression: 0\n  maxTextureSize: 16384\n  userData: \n"
            "  assetBundleName: \n  assetBundleVariant: \n").encode("utf-8")


def _creator_meta(image_uuid: str, name: str, size: list[int] | None = None,
                  insets: list[int] | None = None) -> bytes:
    if size is not None:
        if (len(size) != 2 or not insets or len(insets) != 4
                or any(type(value) is not int or value < 0 for value in size + insets)):
            raise StaticAssetCompletionError("Creator SpriteFrame source geometry is invalid")
        user_data = {"type": "sprite-frame", "fixAlphaTransparencyArtifacts": False, "hasAlpha": True}
        sub = {}
    else:
        sub = {"6c48a": {"ver": "1.0.22", "uuid": image_uuid + "@6c48a", "importer": "texture",
                           "imported": False, "files": [], "displayName": name, "id": "6c48a", "name": "texture",
                           "userData": {"wrapModeS": "clamp-to-edge", "wrapModeT": "clamp-to-edge",
                               "imageUuidOrDatabaseUri": image_uuid, "isUuid": True, "visible": False,
                               "minfilter": "linear", "magfilter": "linear", "mipfilter": "none", "anisotropy": 0},
                           "subMetas": {}}}
        user_data = {"type": "texture", "fixAlphaTransparencyArtifacts": False,
                     "hasAlpha": True, "redirect": image_uuid + "@6c48a"}
    value = {"ver": "1.0.27", "importer": "image", "imported": False, "uuid": image_uuid,
             "files": [], "subMetas": sub, "userData": user_data}
    return io.encoded(value)


def _write(out: Path, raw: bytes, target: str, kind: str) -> dict:
    target_path = PurePosixPath(target)
    if target_path.is_absolute() or any(part in ("", ".", "..") for part in target_path.parts):
        raise StaticAssetCompletionError("target payload path is unsafe")
    target_kind = "unity" if target.startswith("Assets/Game/Content/") else "creator"
    path = PurePosixPath("payloads") / target_kind / target_path
    dest = io.inside(out, path.as_posix())
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() or dest.is_symlink():
        raise StaticAssetCompletionError("target payload collision: " + relative)
    dest.write_bytes(raw)
    return {"source": path.as_posix(), "target": target,
            "bytes": len(raw), "sha256": _digest(raw), "kind": kind}


def _copy_evidence(out: Path, relative: str, raw: bytes) -> dict:
    path = PurePosixPath(relative)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise StaticAssetCompletionError("source evidence path is unsafe")
    rel = "source-evidence/" + path.as_posix()
    dest = io.inside(out, rel)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() or dest.is_symlink():
        raise StaticAssetCompletionError("source evidence path collision: " + relative)
    dest.write_bytes(raw)
    return {"path": rel, "bytes": len(raw), "sha256": _digest(raw)}


def _png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    with image.convert("RGBA") as rgba:
        rgba.save(buffer, format="PNG", optimize=False)
    return buffer.getvalue()


def _verify_reader_inputs(reader: Bundle, rows: dict[tuple[str, str], dict], native_relative: str) -> list[dict]:
    result = []
    for relative, observed in sorted(reader.inputs.items()):
        expected = rows.get((reader.config["name"], relative))
        if expected is None and relative == native_relative:
            result.append({"bundle": reader.config["name"], **observed, "status": "newly-bound-native-input"})
            continue
        if (expected is None or expected.get("sha256") != observed.get("sha256")
                or expected.get("bytes") != observed.get("bytes")):
            raise StaticAssetCompletionError("bounded source reader input differs from the old manifest: " + relative)
        result.append({"bundle": reader.config["name"], **observed, "status": "old-manifest-pinned"})
    return result


def apply(plan: dict, source_manifest: str | Path, out: str | Path) -> dict:
    """Emit an immutable SpriteFrame/Texture2D completion stage and plan copy."""
    if not isinstance(plan, dict) or not isinstance(plan.get("namespace"), str) or not plan["namespace"]:
        raise StaticAssetCompletionError("frozen target plan namespace is required")
    if plan.get("sourceResourceCompletion"):
        raise StaticAssetCompletionError("plan already has a sourceResourceCompletion attachment")
    manifest_path, manifest_raw, manifest, manifest_sha = _load(plan, source_manifest)
    missing_ids, _ = _missing_refs(plan, manifest)
    if not missing_ids:
        raise StaticAssetCompletionError("plan has no missing referenced SpriteFrame")
    rows = _input_rows(manifest)
    bundles = {_source_parts(source_id)[0] for source_id in missing_ids}
    if len(bundles) != 1:
        raise StaticAssetCompletionError("one bounded completion stage must use one source bundle")
    bundle_name = next(iter(bundles))
    config_path, reader = _config_for(bundle_name, manifest, rows)
    source_root = reader.root
    cache_root = _resource_cache_root(source_root)
    output = io.new_output(out, [manifest_path, config_path, source_root, cache_root])

    occupied = {row.get("target"): row.get("sourceId") for row in plan.get("copies") or []
                if isinstance(row, dict) and isinstance(row.get("target"), str)}
    existing_texture_rows = {row.get("id"): row for row in plan.get("textures") or []
                             if isinstance(row, dict) and isinstance(row.get("id"), str)}
    contract_assets, texture_bindings, references, payloads, evidence = [], [], [], [], []
    native_pins: dict[tuple[str, str], dict] = {}
    evidence.append(_copy_evidence(output, "source-manifest.json", manifest_raw))

    for frame_id in missing_ids:
        bundle, frame_key = _source_parts(frame_id)
        if bundle != bundle_name:
            raise StaticAssetCompletionError("SpriteFrame identity escaped the selected bundle")
        frame_index = _config_index(reader, frame_key)
        frame_asset = reader.asset(frame_index)
        frame_root = _root(frame_asset, "cc.SpriteFrame", frame_id)
        frame_data = frame_root.get("data")
        texture_ref = frame_root.get("_textureSetter")
        texture_key = texture_ref.get("__uuid__") if isinstance(texture_ref, dict) else None
        if not isinstance(frame_data, dict) or not isinstance(texture_key, str):
            raise StaticAssetCompletionError("SpriteFrame document lacks exact geometry or Texture2D reference")
        if frame_asset.get("references") != [texture_key]:
            raise StaticAssetCompletionError("SpriteFrame does not have exactly one matching texture reference")

        texture_id = bundle + ":" + texture_key
        texture_index = _config_index(reader, texture_key)
        texture_asset = reader.asset(texture_index)
        texture_root = _root(texture_asset, "cc.Texture2D", texture_id)
        native_version = reader.version("native", texture_index, texture_key)
        if not isinstance(native_version, str):
            raise StaticAssetCompletionError("Texture2D config does not declare a native version")
        native_path = reader.native_file(texture_asset, native_version)
        native_relative = native_path.relative_to(reader.root).as_posix()
        native_raw = reader.record(native_path, max_bytes=_MAX_NATIVE)
        if not native_relative.startswith("native/") or Path(native_relative).suffix.lower() not in (".png", ".jpg", ".jpeg", ".astc"):
            raise StaticAssetCompletionError("Texture2D native source path/format is outside the image contract")
        pins = _verify_reader_inputs(reader, rows, native_relative)
        for pin in pins:
            native_pins[(pin["bundle"], pin["path"])] = pin
        pin_by_path = {pin["path"]: pin for pin in pins}
        config_relative = config_path.relative_to(reader.root).as_posix()
        import_relative = frame_asset.get("importPath")
        if config_relative not in pin_by_path or not isinstance(import_relative, str) or import_relative not in pin_by_path:
            raise StaticAssetCompletionError("bundle config or pack input was not verified against the frozen manifest")
        if texture_asset.get("importPath") != import_relative:
            raise StaticAssetCompletionError("Texture2D and SpriteFrame are not bound to the same verified pack")
        config_pin, pack_pin = pin_by_path[config_relative], pin_by_path[import_relative]

        cache = _cache_evidence(cache_root, bundle, native_relative, native_raw)
        cache_list_raw = cache.pop("cacheListRaw")
        cached_payload_raw = cache.pop("cachedPayloadRaw")
        evidence.append(_copy_evidence(output, bundle + "/" + config_relative,
                                       io.read(config_path, max_bytes=32 * 1024 * 1024)))
        evidence.append(_copy_evidence(output, bundle + "/" + import_relative,
                                       io.read(reader.root / import_relative, max_bytes=32 * 1024 * 1024)))
        evidence.append(_copy_evidence(output, bundle + "/" + native_relative, native_raw))
        evidence.append(_copy_evidence(output, "resource-cache/cacheList.json", cache_list_raw))
        evidence.append(_copy_evidence(output, "resource-cache/" + cache["cachedPayloadRelativePath"], cached_payload_raw))

        with open_texture(native_raw, Path(native_relative).suffix.lower()) as source_texture:
            if source_texture.width <= 0 or source_texture.height <= 0 or source_texture.width * source_texture.height > _MAX_PIXELS:
                raise StaticAssetCompletionError("decoded Texture2D exceeds the bounded pixel budget")
            trimmed, full_frame, geometry = normalize_sprite(source_texture, frame_data)
            texture_png, frame_png, original_frame_png = _png(source_texture), _png(trimmed), _png(full_frame)
            width, height = source_texture.size
            rgba_sha = _digest(source_texture.convert("RGBA").tobytes())

        frame_path_value = (reader.config.get("paths") or {}).get(str(frame_index))
        texture_path_value = (reader.config.get("paths") or {}).get(str(texture_index))
        frame_logical = frame_path_value[0] if isinstance(frame_path_value, list) and frame_path_value else None
        texture_logical = texture_path_value[0] if isinstance(texture_path_value, list) and texture_path_value else None
        logical = _safe_logical_path(frame_logical or texture_logical)
        frame_stem = logical
        texture_stem = logical
        unity_frame_path = _unique_target(PurePosixPath("Assets/Game/Content/Textures") / frame_stem.with_suffix(".png"), frame_id, occupied)
        unity_original_path = _unique_target(PurePosixPath("Assets/Game/Content/Textures/@original/Frames") / frame_stem.with_suffix(".png"), frame_id + "@original", occupied)
        unity_source_texture_path = _unique_target(PurePosixPath("Assets/Game/Content/Textures/@original/Textures") / texture_stem.with_suffix(".png"), texture_id, occupied)
        creator_frame_path = unity_frame_path.replace("Assets/Game/Content/", "assets/resources/")
        creator_original_path = unity_original_path.replace("Assets/Game/Content/", "assets/resources/")
        creator_texture_path = unity_source_texture_path.replace("Assets/Game/Content/", "assets/resources/")

        left, top, right, bottom = geometry["capInsets"]
        unity_frame_guid = _unity_guid(plan["namespace"], frame_id)
        unity_original_guid = _unity_guid(plan["namespace"], frame_id + "@original")
        unity_texture_guid = _unity_guid(plan["namespace"], texture_id)
        creator_frame_image_uuid = _creator_uuid(plan["namespace"], frame_id)
        creator_original_image_uuid = _creator_uuid(plan["namespace"], frame_id + "@original")
        creator_texture_uuid = _creator_uuid(plan["namespace"], texture_id)
        # Creator 3.8.8 assigns SpriteFrame subresource IDs during native import.
        # Keep them unknown here; never predict a subresource UUID from source IDs.
        creator_frame_uuid = None
        creator_original_uuid = None

        frame_size = geometry["rect"][2:4]
        original_size = geometry["originalSize"]
        offset = geometry["offset"]
        bottom_border = [left, bottom, right, top]
        original_border = bottom_border if frame_size == original_size and offset == [0, 0] else [0, 0, 0, 0]
        target_files = [
            (unity_frame_path, frame_png, "unity-sprite-png"),
            (unity_frame_path + ".meta", _unity_meta(unity_frame_guid, True, [left, top, right, bottom]), "unity-sprite-meta"),
            (unity_original_path, original_frame_png, "unity-original-sprite-png"),
            (unity_original_path + ".meta", _unity_meta(unity_original_guid, True, original_border), "unity-original-sprite-meta"),
            (unity_source_texture_path, texture_png, "unity-source-texture-png"),
            (unity_source_texture_path + ".meta", _unity_meta(unity_texture_guid, False), "unity-texture-meta"),
            (creator_frame_path, frame_png, "creator-sprite-png"),
            (creator_frame_path + ".meta", _creator_meta(creator_frame_image_uuid, logical.name, frame_size, geometry["capInsets"]), "creator-sprite-meta"),
            (creator_original_path, original_frame_png, "creator-original-sprite-png"),
            (creator_original_path + ".meta", _creator_meta(creator_original_image_uuid, logical.name, original_size, geometry["capInsets"]), "creator-original-sprite-meta"),
            (creator_texture_path, texture_png, "creator-source-texture-png"),
            (creator_texture_path + ".meta", _creator_meta(creator_texture_uuid, logical.name), "creator-texture-meta"),
        ]
        for target, raw, kind in target_files:
            payloads.append(_write(output, raw, target, kind))

        frame_document_sha = _digest(_canonical(frame_asset["document"]))
        texture_document_sha = _digest(_canonical(texture_asset["document"]))
        native_info = {"bundle": bundle, "path": native_relative, "bytes": len(native_raw),
                       "sha256": _digest(native_raw), "format": Path(native_relative).suffix.lower(),
                       "configNativeVersion": native_version,
                       "oldManifestInput": "present" if (bundle, native_relative) in rows else "absent-and-added-to-completion"}
        reference_rows = [component for component in plan.get("components") or []
                          if isinstance(component, dict) and component.get("type") == "cc.Sprite"
                          and component.get("spriteFrame") == frame_id]
        references.extend({"sourceComponentId": component.get("sourceId"), "sourceNodeId": component.get("node"),
            "sourceSpriteFrameId": frame_id, "sourceEnabled": component.get("enabled") is True,
            "sourceMode": component.get("mode"), "sourceTrim": component.get("trim"),
            "unitySpritePath": unity_frame_path, "unitySpriteGuid": unity_frame_guid,
            "creatorSpriteFrameUuid": creator_frame_uuid} for component in reference_rows)
        texture_bindings.extend([
            {"id": frame_id, "path": unity_frame_path, "border": bottom_border,
             "size": frame_size, "originalSize": original_size, "offset": offset,
             "unityGuid": unity_frame_guid, "creatorImageUuid": creator_frame_image_uuid,
             "creatorSpriteFrameUuid": creator_frame_uuid,
             "creatorSpriteFrameUuidPolicy": "creator-native-importer-assigned-v1"},
            {"id": frame_id + "@original", "path": unity_original_path, "border": original_border,
             "size": original_size, "originalSize": original_size, "offset": [0, 0],
             "unityGuid": unity_original_guid, "creatorImageUuid": creator_original_image_uuid,
             "creatorSpriteFrameUuid": creator_original_uuid,
             "creatorSpriteFrameUuidPolicy": "creator-native-importer-assigned-v1"},
        ])
        contract_assets.extend([
            {"sourceId": frame_id, "sourceType": "cc.SpriteFrame", "configIndex": frame_index,
             "sourceIdentityEncoding": "config-declared-opaque" if frame_index in reader.invalid_keys else "uuid",
             "sourceLogicalPath": frame_logical, "packId": frame_asset.get("pack"),
             "packOrdinal": frame_asset.get("packOrdinal"), "sourceDocumentSha256": frame_document_sha,
             "sourceGeometry": {"rect": geometry["rect"], "originalSize": original_size, "offset": offset,
                                "rotated": geometry["rotated"], "trimOrigin": geometry["trimOrigin"],
                                "capInsets": geometry["capInsets"]}, "textureSourceId": texture_id,
             "unity": {"type": "Sprite", "path": unity_frame_path, "guid": unity_frame_guid,
                       "nativeImport": "not_run"},
             "creator": {"type": "cc.SpriteFrame", "path": creator_frame_path,
                         "imageUuid": creator_frame_image_uuid, "spriteFrameUuid": creator_frame_uuid,
                         "spriteFrameUuidPolicy": "creator-native-importer-assigned-v1",
                         "nativeImport": "not_run"}},
            {"sourceId": texture_id, "sourceType": "cc.Texture2D", "configIndex": texture_index,
             "sourceIdentityEncoding": "config-declared-opaque" if texture_index in reader.invalid_keys else "uuid",
             "sourceLogicalPath": texture_logical, "packId": texture_asset.get("pack"),
             "packOrdinal": texture_asset.get("packOrdinal"), "sourceDocumentSha256": texture_document_sha,
             "sourceDocumentData": texture_root.get("data"), "sourceNative": native_info,
             "sourceCacheEvidence": {key: value for key, value in cache.items() if key.endswith(("Path", "Sha256", "Bytes", "Url")) or key == "sourceCdnUrl"},
             "decodedSize": [width, height], "decodedRgbaSha256": rgba_sha,
             "unity": {"type": "Texture2D", "path": unity_source_texture_path, "guid": unity_texture_guid,
                       "nativeImport": "not_run"},
             "creator": {"type": "cc.Texture2D", "path": creator_texture_path,
                         "imageUuid": creator_texture_uuid, "textureUuid": creator_texture_uuid + "@6c48a",
                         "nativeImport": "not_run"}},
        ])
    if len(references) != len([c for c in plan.get("components") or [] if isinstance(c, dict)
                               and c.get("type") == "cc.Sprite" and c.get("spriteFrame") in set(missing_ids)]):
        raise StaticAssetCompletionError("not every source SpriteFrame reference received a target mapping")

    contract = {"schema": SCHEMA, "status": "prepared", "sourceManifestPath": str(manifest_path),
        "sourceManifestSha256": manifest_sha, "sourceIrSha256": plan.get("sourceIrSha256"),
        "sourcePlanCanonicalSha256": _digest(_canonical(plan)), "bundleConfigPath": str(config_path),
        "bundleConfigSha256": next((pin["sha256"] for pin in native_pins.values()
                                     if pin["path"] == config_path.relative_to(reader.root).as_posix()), None),
        "oldManifestInputPins": [pin for pin in native_pins.values() if pin["status"] == "old-manifest-pinned"],
        "newNativePins": [pin for pin in native_pins.values() if pin["status"] != "old-manifest-pinned"],
        "assets": contract_assets, "textureBindings": texture_bindings, "references": references,
        "payloads": payloads, "evidenceCopies": evidence, "sourceFilesImmutable": True,
        "sourceManifestAndIrUnchanged": True, "editorImport": "not_run", "saveReopenReadback": "not_run"}
    contract["nativeAcceptance"] = {
        "unity": [
            {"check": "Texture2D image import", "status": "not_run", "sourceAssetId": contract_assets[1]["sourceId"],
             "targetPath": contract_assets[1]["unity"]["path"], "expectedGuid": contract_assets[1]["unity"]["guid"],
             "expectedObjectType": "Texture2D", "decodedRgbaSha256": contract_assets[1]["decodedRgbaSha256"]},
            {"check": "SpriteFrame import and Image reference resolution", "status": "not_run",
             "sourceFrameId": contract_assets[0]["sourceId"], "targetPath": contract_assets[0]["unity"]["path"],
             "expectedGuid": contract_assets[0]["unity"]["guid"], "expectedObjectType": "Sprite",
             "sourceReferenceCount": len(references), "preserveDisabledReferences": True},
            {"check": "Prefab save/reopen non-null Sprite persistence", "status": "not_run",
             "sourceComponentIds": [row["sourceComponentId"] for row in references],
             "sourceEnabledValues": [row["sourceEnabled"] for row in references]},
        ],
        "creator": [
            {"check": "Texture2D image and texture subMeta import", "status": "not_run",
             "sourceAssetId": contract_assets[1]["sourceId"],
             "imageUuid": contract_assets[1]["creator"]["imageUuid"],
             "textureUuid": contract_assets[1]["creator"]["textureUuid"]},
            {"check": "SpriteFrame subMeta reference resolution", "status": "not_run",
             "sourceFrameId": contract_assets[0]["sourceId"],
             "spriteFrameUuid": contract_assets[0]["creator"]["spriteFrameUuid"],
             "sourceReferenceCount": len(references), "preserveDisabledReferences": True},
            {"check": "Prefab save/reopen source reference persistence", "status": "not_run",
             "sourceComponentIds": [row["sourceComponentId"] for row in references],
             "sourceEnabledValues": [row["sourceEnabled"] for row in references]},
        ],
    }
    contract_path = output / "source-resource-completion.json"
    io.write_json(contract_path, contract)
    contract_hash = _digest(io.read(contract_path, max_bytes=128 * 1024 * 1024))
    report = {"schemaVersion": 1, "contract": SCHEMA, "status": "prepared",
        "sourceManifestSha256": manifest_sha, "sourceResourceCompletionSha256": contract_hash,
        "completedAssets": len(contract_assets), "references": len(references), "payloads": len(payloads),
        "evidenceCopies": len(evidence), "sourceFilesImmutable": True, "editorImport": "not_run"}
    report = io.finish(output, report)

    updated = copy.deepcopy(plan)
    texture_map = {row.get("id"): row for row in updated.get("textures") or [] if isinstance(row, dict)}
    for row in texture_bindings:
        old = texture_map.get(row["id"])
        if old is not None and any(old.get(key) != row.get(key) for key in ("path", "size", "originalSize", "offset", "border")):
            raise StaticAssetCompletionError("existing target texture mapping conflicts with source completion")
        if old is None:
            texture_map[row["id"]] = {key: row.get(key) for key in ("id", "path", "border", "size", "originalSize", "offset")}
    updated["textures"] = [texture_map[key] for key in sorted(texture_map)]
    updated["sourceResourceCompletion"] = {"schema": SCHEMA, "contractPath": "source-resource-completion.json",
        "sha256": contract_hash, "sourceManifestSha256": manifest_sha,
        "completedSourceAssetIds": sorted({row["sourceId"] for row in contract_assets}),
        "payloadPrefix": "payloads/"}
    return {"status": "prepared", "plan": updated, "contract": contract,
            "contractPath": str(contract_path),
            "contractSha256": contract_hash, "output": str(output), "manifest": report}


def _append_descriptor(rows: list[dict], key: str, descriptor: dict, error: str) -> None:
    previous = next((row for row in rows if isinstance(row, dict) and row.get(key) == descriptor.get(key)), None)
    if previous is None:
        rows.append(descriptor)
    elif previous != descriptor:
        raise StaticAssetCompletionError(error)


def prepare_for_target(plan: dict, source_manifest: str | Path, out_stage: str | Path) -> dict:
    """Prepare source closure and attach descriptors matching the selected target schema."""
    profile = plan.get("targetProfile") if isinstance(plan, dict) else None
    if isinstance(profile, str) and profile.startswith("unity-"):
        target = "unity"
    elif isinstance(profile, str) and profile.startswith("cocos-3.8.8"):
        target = "creator"
    else:
        raise StaticAssetCompletionError("plan targetProfile must identify Unity or Creator 3.8.8")
    result = apply(plan, source_manifest, out_stage)
    updated = result["plan"]
    contract = result["contract"]
    if not contract.get("assets") or len(contract["assets"]) != 2:
        raise StaticAssetCompletionError("source closure must have one SpriteFrame and its Texture2D")
    frame_asset, texture_asset = contract["assets"]
    bindings = {row["id"]: row for row in contract["textureBindings"]}
    completion = copy.deepcopy(updated["sourceResourceCompletion"])
    completion["target"] = target
    target_assets = {"unity": [], "creator": [], "creatorTexture2D": []}

    if target == "unity":
        from .targets.unity import guid as unity_guid

        for identity in (frame_asset["sourceId"], frame_asset["sourceId"] + "@original"):
            binding = bindings.get(identity)
            if not isinstance(binding, dict):
                raise StaticAssetCompletionError("Unity texture binding is missing: " + identity)
            expected_guid = unity_guid(updated["namespace"], identity)
            if binding.get("unityGuid") != expected_guid:
                raise StaticAssetCompletionError("Unity TextureSpec guid differs from native importer identity rule")
            binding["guid"] = expected_guid
            texture_row = next((row for row in updated.get("textures", []) if row.get("id") == identity), None)
            if texture_row is None or texture_row.get("path") != binding.get("path"):
                raise StaticAssetCompletionError("Unity continuation plan lacks the exact Sprite texture row")
            texture_row["guid"] = expected_guid
            target_assets["unity"].append({"id": identity, "path": binding["path"], "guid": expected_guid,
                "kind": "Sprite", "border": binding["border"], "size": binding["size"],
                "originalSize": binding["originalSize"], "offset": binding["offset"]})
        texture_binding = texture_asset["unity"]
        expected_texture_guid = unity_guid(updated["namespace"], texture_asset["sourceId"])
        if texture_binding.get("guid") != expected_texture_guid:
            raise StaticAssetCompletionError("Unity Texture2D guid differs from native importer identity rule")
        asset_row = {"id": texture_asset["sourceId"], "kind": "cc.Texture2D",
                     "path": texture_binding["path"], "guid": expected_texture_guid,
                     "sourceResourceRole": "source-Texture2D-closure"}
        _append_descriptor(updated.setdefault("assets", []), "id", asset_row,
                           "Unity Texture2D source asset descriptor conflicts with the frozen plan")
        target_assets["unity"].append(asset_row)

    else:
        from .targets.cocos import identity as creator_identity

        creator_rows = []
        for identity in (frame_asset["sourceId"], frame_asset["sourceId"] + "@original"):
            binding = bindings.get(identity)
            if not isinstance(binding, dict):
                raise StaticAssetCompletionError("Creator SpriteFrame texture binding is missing: " + identity)
            image_uuid = creator_identity(updated["namespace"], identity)
            if binding.get("creatorImageUuid") != image_uuid:
                raise StaticAssetCompletionError("Creator image UUID differs from native target identity rule")
            if identity.endswith("@original"):
                creator_path = next((p.get("target") for p in contract["payloads"]
                                     if p.get("kind") == "creator-original-sprite-png"), None)
                creator_sha = next((p.get("sha256") for p in contract["payloads"]
                                    if p.get("kind") == "creator-original-sprite-png"), None)
                size = binding["size"]
                trim_origin = [0, 0]
            else:
                creator_path = frame_asset["creator"]["path"]
                creator_sha = next((p.get("sha256") for p in contract["payloads"]
                                    if p.get("kind") == "creator-sprite-png"), None)
                size = binding["size"]
                trim_origin = frame_asset["sourceGeometry"]["trimOrigin"]
            if not creator_path or not creator_sha:
                raise StaticAssetCompletionError("Creator PNG payload mapping is missing")
            row = {"sourceId": identity, "uuid": image_uuid, "spriteFrameUuid": binding["creatorSpriteFrameUuid"],
                   "spriteFrameUuidPolicy": binding["creatorSpriteFrameUuidPolicy"],
                   "textureUuid": image_uuid + "@6c48a", "path": creator_path, "kind": "sprite",
                   "sha256": creator_sha, "size": size, "trimOrigin": trim_origin,
                   "originalSize": binding["originalSize"], "offset": binding["offset"],
                   "border": frame_asset["sourceGeometry"]["capInsets"], "subresource": "spriteFrame"}
            _append_descriptor(updated.setdefault("assets", []), "sourceId", row,
                               "Creator SpriteFrame descriptor conflicts with the frozen plan")
            creator_rows.append(row)
            texture_row = next((item for item in updated.get("textures", []) if item.get("id") == identity), None)
            if texture_row is not None:
                texture_row["path"] = creator_path
                texture_row.pop("guid", None)
        creator_texture = texture_asset["creator"]
        creator_texture_asset = {"sourceId": texture_asset["sourceId"], "uuid": creator_texture["imageUuid"],
            "textureUuid": creator_texture["textureUuid"], "path": creator_texture["path"],
            "sha256": next((p["sha256"] for p in contract["payloads"] if p.get("kind") == "creator-source-texture-png"), None),
            "kind": "cc.Texture2D", "sourceIdentityEncoding": texture_asset["sourceIdentityEncoding"]}
        if creator_texture_asset["uuid"] != creator_identity(updated["namespace"], texture_asset["sourceId"]):
            raise StaticAssetCompletionError("Creator Texture2D image UUID differs from target identity rule")
        target_assets["creator"] = creator_rows
        target_assets["creatorTexture2D"] = [creator_texture_asset]

    completion["targetAssets"] = target_assets
    updated["sourceResourceCompletion"] = completion
    result["plan"] = updated
    result["target"] = target
    return result


def emit(plan: dict, plan_root: str | Path, out: str | Path, target: str) -> dict:
    """Copy only the selected target's hash-pinned PNG/meta payloads.

    `.meta` files are direct receipt payloads; this routine never derives a
    second `.meta` suffix or invokes the ordinary plan-copy metadata writer.
    """
    if target not in ("unity", "creator"):
        raise StaticAssetCompletionError("target must be unity or creator")
    pointer = plan.get("sourceResourceCompletion") if isinstance(plan, dict) else None
    if not isinstance(pointer, dict) or pointer.get("schema") != SCHEMA:
        raise StaticAssetCompletionError("plan lacks the source-resource completion attachment")
    if pointer.get("target") not in (None, target):
        raise StaticAssetCompletionError("prepared target differs from requested emit target")
    stage_root = io.safe(plan_root)
    contract_rel = pointer.get("contractPath", "source-resource-completion.json")
    if (not isinstance(contract_rel, str) or PurePosixPath(contract_rel).is_absolute()
            or any(part in ("", ".", "..") for part in PurePosixPath(contract_rel).parts)):
        raise StaticAssetCompletionError("source-resource contract path is unsafe")
    contract_path = io.inside(stage_root, contract_rel)
    contract_raw = io.read(contract_path, max_bytes=128 * 1024 * 1024)
    if _digest(contract_raw) != pointer.get("sha256"):
        raise StaticAssetCompletionError("source-resource contract SHA differs from prepared plan")
    contract = io.load(contract_raw, max_nodes=2_000_000)
    if (contract.get("schema") != SCHEMA or contract.get("status") != "prepared"
            or contract.get("sourceManifestSha256") != pointer.get("sourceManifestSha256")):
        raise StaticAssetCompletionError("source-resource contract does not match plan/manifest pins")
    stage_manifest = io.load(io.read(io.inside(stage_root, "manifest.json"), max_bytes=128 * 1024 * 1024),
                             max_nodes=8_000_000)
    owned = {row.get("path"): row for row in stage_manifest.get("files") or [] if isinstance(row, dict)}
    prefix = pointer.get("payloadPrefix", "payloads/")
    if prefix != "payloads/":
        raise StaticAssetCompletionError("payload prefix differs from the portable contract")
    native_prefix = "Assets/Game/Content/Textures/" if target == "unity" else "assets/resources/Textures/"
    kind_prefix = "unity-" if target == "unity" else "creator-"
    target_payload_prefix = "payloads/" + target + "/"
    selected = []
    for row in contract.get("payloads") or []:
        if not isinstance(row, dict) or not str(row.get("kind", "")).startswith(kind_prefix):
            continue
        source_rel, target_rel = row.get("source"), row.get("target")
        for value in (source_rel, target_rel):
            path = PurePosixPath(value) if isinstance(value, str) else None
            if (path is None or path.is_absolute() or "\\" in value
                    or any(part in ("", ".", "..") for part in path.parts)):
                raise StaticAssetCompletionError("payload source/target path is unsafe")
        if not source_rel.startswith(target_payload_prefix) or not target_rel.startswith(native_prefix):
            raise StaticAssetCompletionError("payload source/target is outside the declared target namespace")
        if target_rel.endswith(".meta.meta"):
            raise StaticAssetCompletionError("target metadata path has a duplicated .meta suffix")
        source = io.inside(stage_root, source_rel)
        ownership = owned.get(source_rel)
        raw = io.read(source, max_bytes=512 * 1024 * 1024)
        digest = _digest(raw)
        if (ownership is None or ownership.get("sha256") != digest or ownership.get("bytes") != len(raw)
                or row.get("sha256") != digest or row.get("bytes") != len(raw)):
            raise StaticAssetCompletionError("payload differs from completion/stage SHA pins: " + source_rel)
        selected.append((row, source, raw))
    if not selected:
        raise StaticAssetCompletionError("completion has no payloads for requested target")
    target_root = io.safe(out)
    output_manifest_path = target_root / "manifest.json"
    output_manifest = None
    manifest_paths = set()
    if output_manifest_path.is_file():
        output_manifest = io.load(io.read(output_manifest_path, max_bytes=128 * 1024 * 1024), max_nodes=8_000_000)
        rows = output_manifest.get("files") if isinstance(output_manifest, dict) else None
        if not isinstance(rows, list):
            raise StaticAssetCompletionError("target output manifest has no owned-files list")
        manifest_paths = {row.get("path") for row in rows if isinstance(row, dict)}
    destinations = []
    seen = set()
    for row, source, raw in selected:
        relative = row["target"]
        if relative in seen:
            raise StaticAssetCompletionError("duplicate target payload path: " + relative)
        seen.add(relative)
        dest = io.inside(target_root, relative)
        if relative in manifest_paths:
            raise StaticAssetCompletionError("target path is already owned by output manifest: " + relative)
        if dest.exists() or dest.is_symlink():
            raise StaticAssetCompletionError("target payload filename collision: " + relative)
        destinations.append((row, source, dest, raw))
    from .output_limits import copy_verified
    copied = []
    for row, source, dest, raw in destinations:
        copy_verified(source, dest, row["sha256"], row["bytes"])
        copied.append({"path": row["target"], "bytes": row["bytes"], "sha256": row["sha256"], "kind": row["kind"]})
    output_manifest_sha = None
    if output_manifest is not None:
        output_manifest["files"].extend({"path": row["path"], "bytes": row["bytes"],
                                        "sha256": row["sha256"], "owner": "generated"}
                                       for row in copied)
        output_manifest["files"] = sorted(output_manifest["files"], key=lambda row: row.get("path", ""))
        from .output_limits import check_inventory
        output_manifest["limits"] = check_inventory(output_manifest["files"], output_manifest, str(target_root))
        io.write_json(output_manifest_path, output_manifest)
        output_manifest_sha = _digest(io.read(output_manifest_path, max_bytes=128 * 1024 * 1024))
    return {"status": "emitted", "target": target, "contractSha256": pointer["sha256"],
            "payloadPrefix": prefix, "files": copied, "outputManifestSha256": output_manifest_sha}
