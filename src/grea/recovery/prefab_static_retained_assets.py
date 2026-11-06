"""Source-pinned references for static fields whose native asset adapter is absent.

This module retains BufferAsset bytes, decoded Texture2D pixels, and source
material/effect evidence. Non-profiled materials become non-rendering records;
the exact built-in 2D sprite material gets a separate native-default mapping.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from pathlib import Path

from PIL import Image

from . import io
from .normalize import open_texture
from .shader_profiles import EFFECT_SHA256, SOURCE_ID as BUILTIN_EFFECT_SOURCE_ID, describe as describe_shader


SCHEMA = "monkey-prefab-static-retained-assets/1"
_SUPPORTED = {"cc.BufferAsset", "cc.Texture2D", "cc.Material", "cc.ParticleAsset"}
_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class RetainedAssetError(ValueError):
    """Invalid source manifest, reference, or retained native asset payload."""


def _canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _root_object(asset: dict) -> dict:
    document = asset.get("document")
    if not isinstance(document, dict):
        raise RetainedAssetError("source asset document is missing")
    instances = document.get("instances")
    root = document.get("root")
    if not isinstance(instances, list) or type(root) is not int or not 0 <= root < len(instances):
        raise RetainedAssetError("source asset document has an invalid root instance")
    value = instances[root]
    if not isinstance(value, dict):
        raise RetainedAssetError("source asset root is not an object")
    return value


def _safe_id(source_id: str) -> str:
    if not isinstance(source_id, str) or ":" not in source_id:
        raise RetainedAssetError("source asset identity must include its bundle")
    bundle, key = source_id.split(":", 1)
    value = bundle + "_" + key
    if not _SAFE.fullmatch(value):
        raise RetainedAssetError("source asset identity cannot be used in an owned filename")
    return value


def _native_identity(namespace: str, target: str, source_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"monkey/{namespace}/static-retained-assets/{target}/{source_id}"))


def _creator_meta(uid: str, importer: str) -> bytes:
    if importer == 'texture':
        texture_uuid=uid+'@6c48a'
        return io.encoded({'ver':'1.0.27','uuid':uid,'importer':'image','imported':False,'files':[],
            'userData':{'type':'texture','fixAlphaTransparencyArtifacts':False,'hasAlpha':True,'redirect':texture_uuid},
            'subMetas':{'6c48a':{'ver':'1.0.22','uuid':texture_uuid,'importer':'texture','imported':False,'files':[],
                'displayName':'texture','id':'6c48a','name':'texture','userData':{'wrapModeS':'clamp-to-edge','wrapModeT':'clamp-to-edge',
                    'imageUuidOrDatabaseUri':uid,'isUuid':True,'visible':False,'minfilter':'linear','magfilter':'linear','mipfilter':'none','anisotropy':0}}}})
    return io.encoded({"ver": "1.0.6", "uuid": uid, "importer": importer,
                       "imported": False, "files": [], "subMetas": {}, "userData": {}})


def _unity_meta(guid: str, importer: str) -> bytes:
    if importer in ("native-material", "native-asset"):
        file_id = "2100000" if importer == "native-material" else "11400000"
        body = f"NativeFormatImporter:\n  externalObjects: {{}}\n  mainObjectFileID: {file_id}\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n"
        return (f"fileFormatVersion: 2\nguid: {guid}\n" + body).encode("utf-8")
    if importer == "texture":
        body = (
            "TextureImporter:\n  internalIDToNameTable: []\n  externalObjects: {}\n"
            "  serializedVersion: 13\n  mipmaps:\n    mipMapMode: 0\n    enableMipMap: 0\n"
            "    sRGBTexture: 1\n  isReadable: 1\n  streamingMipmaps: 0\n"
            "  textureType: 0\n  textureShape: 1\n  alphaSource: 1\n"
            "  alphaIsTransparency: 0\n  textureCompression: 0\n  maxTextureSize: 16384\n"
            "  userData: \n  assetBundleName: \n  assetBundleVariant: \n"
        )
    else:
        body = "TextScriptImporter:\n  externalObjects: {}\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n"
    return (f"fileFormatVersion: 2\nguid: {guid}\n" + body).encode("utf-8")


def _references(plan: dict) -> tuple[list[dict], list[dict]]:
    found, gaps = [], []
    for component in plan.get("components") or []:
        binding = component.get("staticFieldBinding")
        if not isinstance(binding, dict):
            continue
        for field in binding.get("fields") or []:
            if not isinstance(field, dict) or field.get("storageType") not in ("UnityEngine.Object", "UnityEngine.Object[]"):
                continue
            if field.get('kind') in ('node_ref', 'component_ref') or field.get('elementKind') in ('node_ref', 'component_ref'):
                continue
            values = []
            if field.get("storageType") == "UnityEngine.Object":
                if not field.get("nullExpected"):
                    values.append((None, field.get("refValue")))
            else:
                values.extend((index, value) for index, value in enumerate(field.get("refValues") or []))
            for index, source_id in values:
                if not isinstance(source_id, str) or not source_id:
                    gaps.append({"code": "RETAINED_ASSET_REFERENCE_ID_MISSING", "sourceComponentId": component.get("sourceId"),
                                 "field": field.get("sourceFieldName"), "index": index})
                    continue
                found.append({"sourceComponentId": component.get("sourceId"), "sourceNodeId": component.get("node"),
                              "field": field.get("sourceFieldName"), "index": index,
                              "sourceDeclaredType": field.get("sourceDeclaredType") or "",
                              "creatorFieldType": "Asset[]" if field.get("storageType") == "UnityEngine.Object[]"
                                  and field.get("elementKind") == "asset_ref" and not field.get("sourceDeclaredType") else None,
                              "storageType": field.get("storageType"), "sourceAssetId": source_id})
    return found, gaps


def _asset_source(manifest: dict, source_id: str, assets: dict[str, dict], inputs: dict[tuple[str, str], dict]):
    asset = assets.get(source_id)
    if asset is None:
        return None, None, None
    bundle, relative = asset.get("bundle"), asset.get("importPath")
    roots = manifest.get("sourceRoots")
    if not isinstance(bundle, str) or not isinstance(relative, str) or not isinstance(roots, dict) or bundle not in roots:
        raise RetainedAssetError(f"source import identity is incomplete: {source_id}")
    input_row = inputs.get((bundle, relative))
    if input_row is None:
        raise RetainedAssetError(f"source import bytes are not pinned: {source_id}")
    root = io.safe(roots[bundle])
    path = io.inside(root, relative)
    raw = io.read(path, max_bytes=128 * 1024 * 1024)
    if len(raw) != input_row.get("bytes") or _sha(raw) != input_row.get("sha256"):
        raise RetainedAssetError(f"source import bytes/hash differ: {source_id}")
    return asset, path, {"bundle": bundle, "path": relative, "bytes": len(raw), "sha256": _sha(raw)}


def _native_bytes(manifest: dict, asset: dict, inputs: dict[tuple[str, str], dict]):
    relative = asset.get("native")
    if not isinstance(relative, str) or not relative:
        raise RetainedAssetError(f"source native bytes are absent: {asset.get('sourceId')}")
    bundle = asset.get("bundle")
    input_row = inputs.get((bundle, relative))
    root = (manifest.get("sourceRoots") or {}).get(bundle)
    if input_row is None or not isinstance(root, str):
        raise RetainedAssetError(f"source native byte hash is not pinned: {asset.get('sourceId')}")
    path = io.inside(io.safe(root), relative)
    raw = io.read(path, max_bytes=128 * 1024 * 1024)
    if len(raw) != input_row.get("bytes") or _sha(raw) != input_row.get("sha256"):
        raise RetainedAssetError(f"source native bytes/hash differ: {asset.get('sourceId')}")
    return path, raw, {"bundle": bundle, "path": relative, "bytes": len(raw), "sha256": _sha(raw)}


def _builtin_default_material(manifest: dict, material_asset: dict, asset_by_uuid: dict[str, list[dict]],
                              assets: dict[str, dict], inputs: dict[tuple[str, str], dict]):
    material = _root_object(material_asset)
    if (material_asset.get("bundle") != "internal" or material.get("__type__") != "cc.Material" or
            material.get("_name") != "builtin-2d-sprite" or
            material.get("_techniqueData", {}).get("0", {}).get("defines") != {"USE_TEXTURE": True}):
        return None
    ref = material.get("_effectAsset")
    effect_uuid = ref.get("__uuid__") if isinstance(ref, dict) else None
    rows = asset_by_uuid.get(effect_uuid, [])
    if len(rows) != 1 or rows[0].get("kind") != "cc.EffectAsset":
        raise RetainedAssetError("built-in sprite material has no unique source EffectAsset")
    effect_asset, _, effect_pack_hash = _asset_source(manifest, rows[0]["sourceId"], assets, inputs)
    effect = _root_object(effect_asset)
    # The pack SHA pins this recovered subasset; the stage hashes and exact
    # declarations are checked by the existing narrow shader profile.
    profile = describe_shader(effect, effect_sha256=EFFECT_SHA256)
    if not profile.get("supported") or effect_asset.get("sourceId") != BUILTIN_EFFECT_SOURCE_ID:
        raise RetainedAssetError("built-in sprite material/effect is outside the exact default profile")
    return {"effectAsset": effect_asset, "effect": effect, "effectPackHash": effect_pack_hash,
            "profile": profile}


def _prepare(plan: dict, manifest, output: str | Path) -> dict:
    """Copy hash-pinned referenced sources and attach target-retention contracts.

    ``manifest`` should be the frozen source-manifest path. A dictionary is
    accepted for in-memory tests, but the caller's plan source-manifest hash is
    retained as the input pin and every referenced input/native file is still
    checked against its manifest byte count and SHA-256.
    """
    if not isinstance(plan, dict) or not isinstance(plan.get("namespace"), str):
        raise RetainedAssetError("plan namespace is required")
    manifest_path = None
    manifest_raw = None
    if isinstance(manifest, (str, Path)):
        manifest_path = io.safe(manifest)
        manifest_raw = io.read(manifest_path, max_bytes=128 * 1024 * 1024)
        manifest_doc = io.load(manifest_raw, max_nodes=16_000_000)
        actual_manifest_sha = _sha(manifest_raw)
        expected_manifest_sha = plan.get("sourceManifestSha256")
        if expected_manifest_sha and expected_manifest_sha != actual_manifest_sha:
            raise RetainedAssetError("source-manifest hash differs from plan pin")
    elif isinstance(manifest, dict):
        manifest_doc = manifest
        actual_manifest_sha = plan.get("sourceManifestSha256")
        if not isinstance(actual_manifest_sha, str) or not re.fullmatch("[a-f0-9]{64}", actual_manifest_sha):
            raise RetainedAssetError("in-memory manifest requires the plan source-manifest SHA pin")
    else:
        raise RetainedAssetError("manifest must be a source-manifest path or object")
    if manifest_doc.get("schemaVersion") != 1 or not isinstance(manifest_doc.get("assets"), list):
        raise RetainedAssetError("unsupported source-manifest schema")
    assets = {asset.get("sourceId"): asset for asset in manifest_doc["assets"] if isinstance(asset, dict)
              and isinstance(asset.get("sourceId"), str)}
    inputs = {(row.get("bundle"), row.get("path")): row for row in manifest_doc.get("inputs", []) if isinstance(row, dict)}
    asset_by_uuid: dict[str, list[dict]] = {}
    for source_id, asset in assets.items():
        if ":" in source_id:
            asset_by_uuid.setdefault(source_id.split(":", 1)[1], []).append(asset)

    field_references, gaps = _references(plan)
    wanted = sorted({row["sourceAssetId"] for row in field_references})
    selected = []
    for source_id in wanted:
        asset = assets.get(source_id)
        if asset is None:
            gaps.append({"code": "RETAINED_ASSET_SOURCE_ID_UNRESOLVED", "sourceAssetId": source_id})
            continue
        kind = asset.get("kind")
        if kind not in _SUPPORTED:
            continue
        selected.append(asset)

    output_root = io.new_output(output, [manifest_path] if manifest_path else [])
    payloads, evidence_copies, entries = [], {}, []
    out_payloads = output_root / "payloads"
    out_evidence = output_root / "source-evidence"

    def write_payload(source_data: bytes, target: str, description: str):
        safe_rel = Path(target)
        if safe_rel.is_absolute() or any(part in ("", ".", "..") for part in safe_rel.as_posix().split("/")):
            raise RetainedAssetError("payload target is not a canonical project-relative path")
        rel = "payloads/" + safe_rel.as_posix()
        path = io.inside(output_root, rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() or path.is_symlink():
            raise RetainedAssetError(f"payload path collision: {target}")
        path.write_bytes(source_data)
        payloads.append({"source": rel, "target": target, "bytes": len(source_data), "sha256": _sha(source_data),
                         "kind": description})
        return {"path": target, "bytes": len(source_data), "sha256": _sha(source_data)}

    def copy_evidence(bundle: str, relative: str, raw: bytes, digest: str):
        key = (bundle, relative)
        if key in evidence_copies:
            return evidence_copies[key]
        safe_bundle = _safe_id(bundle + ":x").split("_", 1)[0]
        rel = f"source-evidence/{safe_bundle}/{relative}"
        dest = io.inside(output_root, rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() or dest.is_symlink():
            raise RetainedAssetError(f"source evidence path collision: {relative}")
        dest.write_bytes(raw)
        evidence_copies[key] = {"path": rel, "bytes": len(raw), "sha256": digest}
        return evidence_copies[key]

    for asset in selected:
        source_id, kind = asset["sourceId"], asset["kind"]
        ident = _safe_id(source_id)
        _, import_path, import_hash = _asset_source(manifest_doc, source_id, assets, inputs)
        import_raw = io.read(import_path, max_bytes=128 * 1024 * 1024)
        import_evidence = copy_evidence(asset["bundle"], asset["importPath"], import_raw, import_hash["sha256"])
        root_object = _root_object(asset)
        entry = {"sourceId": source_id, "sourceType": kind, "logicalPath": asset.get("logicalPath"),
                 "sourceDocumentSha256": _sha(_canonical(root_object)), "sourceImport": import_hash,
                 "sourceImportEvidenceCopy": import_evidence, "fieldReferences": [r for r in field_references if r["sourceAssetId"] == source_id]}

        if kind in ("cc.BufferAsset", "cc.ParticleAsset"):
            _, raw, native_hash = _native_bytes(manifest_doc, asset, inputs)
            native_path = asset["native"]
            evidence = copy_evidence(asset["bundle"], native_path, raw, native_hash["sha256"])
            guid = _native_identity(plan["namespace"], "unity", source_id).replace("-", "")
            creator_uuid = _native_identity(plan["namespace"], "creator", source_id)
            unity_path = f"Assets/Game/Content/RetainedAssets/Buffers/{ident}.bytes"
            creator_path = f"assets/resources/RetainedAssets/Buffers/{ident}.bin"
            write_payload(raw, unity_path, "unity-buffer-bytes")
            write_payload(_unity_meta(guid, "text"), unity_path + ".meta", "unity-text-asset-meta")
            write_payload(raw, creator_path, "creator-buffer-asset-bytes")
            write_payload(_creator_meta(creator_uuid, "buffer"), creator_path + ".meta", "creator-buffer-asset-meta")
            entry.update({"retentionKind": "buffer-asset", "sourceNative": native_hash,
                          "sourceNativeEvidenceCopy": evidence, "contentSha256": _sha(raw),
                          "unity": {"path": unity_path, "guid": guid, "type": "TextAsset"},
                          "creator": {"path": creator_path, "uuid": creator_uuid, "type": "cc.BufferAsset"}})
            if kind == "cc.ParticleAsset":
                entry.update(renderingRecovered=False, particleSimulationRecovered=False,
                             retentionPolicy='exact-source-particle-file-bytes')

        elif kind == "cc.Texture2D":
            _, raw, native_hash = _native_bytes(manifest_doc, asset, inputs)
            native_path = asset["native"]
            evidence = copy_evidence(asset["bundle"], native_path, raw, native_hash["sha256"])
            try:
                image = open_texture(raw, Path(native_path).suffix.lower())
            except Exception as error:
                raise RetainedAssetError(f"source Texture2D decode failed for {source_id}: {error}") from error
            with image.convert("RGBA") as rgba:
                width, height = rgba.size
                rgba_bytes = rgba.tobytes()
                rgba_sha = _sha(rgba_bytes)
                unity_image = rgba.copy()
                unity_png = __import__("io").BytesIO()
                unity_image.save(unity_png, format="PNG", optimize=False)
                creator_png = __import__("io").BytesIO()
                rgba.save(creator_png, format="PNG", optimize=False)
            unity_guid = _native_identity(plan["namespace"], "unity", source_id).replace("-", "")
            creator_uuid = _native_identity(plan["namespace"], "creator", source_id)
            unity_path = f"Assets/Game/Content/RetainedAssets/Textures/{ident}.png"
            creator_path = f"assets/resources/RetainedAssets/Textures/{ident}.png"
            unity_copy = write_payload(unity_png.getvalue(), unity_path, "unity-texture2d-decoded-png")
            write_payload(_unity_meta(unity_guid, "texture"), unity_path + ".meta", "unity-texture2d-meta")
            creator_copy = write_payload(creator_png.getvalue(), creator_path, "creator-texture2d-decoded-png")
            write_payload(_creator_meta(creator_uuid, "texture"), creator_path + ".meta", "creator-texture2d-meta")
            entry.update({"retentionKind": "texture-asset", "sourceNative": native_hash,
                          "sourceNativeEvidenceCopy": evidence, "dimensions": [width, height],
                          "rgbaSha256": rgba_sha, "unityPngSha256": unity_copy["sha256"],
                          "creatorPngSha256": creator_copy["sha256"],
                          "unity": {"path": unity_path, "guid": unity_guid, "type": "Texture2D",
                                    "pixelOrientation": "unity-bottom-up-to-source-top-down-readback"},
                          "creator": {"path": creator_path, "uuid": creator_uuid+"@6c48a", "imageUuid": creator_uuid, "type": "cc.Texture2D",
                                      "pixelOrientation": "source-top-down"}})

        else:
            effect_info = _builtin_default_material(manifest_doc, asset, asset_by_uuid, assets, inputs)
            material_doc_raw = _canonical(root_object)
            material_doc_hash = _sha(material_doc_raw)
            material_uuid = source_id.split(":", 1)[1]
            if effect_info is not None:
                effect_asset, effect_obj = effect_info["effectAsset"], effect_info["effect"]
                effect_doc_raw = _canonical(effect_obj)
                effect_doc_hash = _sha(effect_doc_raw)
                effect_evidence = effect_info["effectPackHash"]
                unity_guid = _native_identity(plan["namespace"], "unity", source_id).replace("-", "")
                creator_uuid = _native_identity(plan["namespace"], "creator", source_id)
                unity_path = f"Assets/Game/Content/RetainedAssets/Materials/{ident}.mat"
                creator_path = f"assets/resources/RetainedAssets/Materials/{ident}.mtl"
                entry.update({"retentionKind": "builtin-default-material", "nonRendering": False,
                              "profile": effect_info["profile"]["profile"], "effectSourceId": effect_asset["sourceId"],
                              "effectDocumentSha256": effect_doc_hash, "effectPack": effect_evidence,
                              "sourceMaterialName": root_object.get("_name", ""),
                              "nativePolicy": "source-builtin-2d-sprite-to-explicit-native-ui-default-material-v1",
                              "unity": {"path": unity_path, "guid": unity_guid, "type": "Material",
                                        "shader": "UI/Default",
                                        "materialDocumentPath": f"Assets/Game/Content/RetainedAssets/MaterialEvidence/{ident}.material.json",
                                        "effectDocumentPath": f"Assets/Game/Content/RetainedAssets/MaterialEvidence/{ident}.effect.json"},
                              "creator": {"path": creator_path, "uuid": creator_uuid, "type": "cc.Material",
                                          "effectName": "builtin-sprite", "defines": {"USE_TEXTURE": True}}})
                write_payload(material_doc_raw, f"Assets/Game/Content/RetainedAssets/MaterialEvidence/{ident}.material.json",
                              "source-material-document-evidence")
                write_payload(effect_doc_raw, f"Assets/Game/Content/RetainedAssets/MaterialEvidence/{ident}.effect.json",
                              "source-effect-document-evidence")
                write_payload(_unity_meta(unity_guid, "native-material"), unity_path + ".meta", "unity-default-material-meta")
                write_payload(_creator_meta(creator_uuid, "material"), creator_path + ".meta", "creator-default-material-meta")
            else:
                effect_ref = root_object.get("_effectAsset")
                effect_uuid = effect_ref.get("__uuid__") if isinstance(effect_ref, dict) else None
                effect_rows = asset_by_uuid.get(effect_uuid, [])
                if len(effect_rows) != 1 or effect_rows[0].get("kind") != "cc.EffectAsset":
                    raise RetainedAssetError(f"source material effect identity is unresolved: {source_id}")
                effect_asset, _, effect_pack = _asset_source(manifest_doc, effect_rows[0]["sourceId"], assets, inputs)
                effect_obj = _root_object(effect_asset)
                effect_raw = _canonical(effect_obj)
                effect_hash = _sha(effect_raw)
                effect_pack_copy = copy_evidence(effect_asset["bundle"], effect_asset["importPath"],
                    io.read(_asset_source(manifest_doc, effect_asset["sourceId"], assets, inputs)[1], max_bytes=128 * 1024 * 1024),
                    effect_pack["sha256"])
                envelope = {"schema": "monkey-retained-source-material/1", "retentionOnly": True,
                            "renderingRecovered": False, "sourceMaterialId": source_id,
                            "sourceMaterialUuid": material_uuid, "sourceMaterialName": root_object.get("_name", ""),
                            "sourceMaterialDocumentSha256": material_doc_hash, "sourceEffectId": effect_asset["sourceId"],
                            "sourceEffectName": effect_obj.get("_name", ""), "sourceEffectDocumentSha256": effect_hash,
                            "sourceDocumentEncoding": "opaque-json-text-v1",
                            "sourceMaterialJson": material_doc_raw.decode("utf-8"), "sourceEffectJson": effect_raw.decode("utf-8")}
                envelope_raw = _canonical(envelope)
                unity_guid = _native_identity(plan["namespace"], "unity", source_id).replace("-", "")
                creator_uuid = _native_identity(plan["namespace"], "creator", source_id)
                evidence_prefix = f"Assets/Game/Content/RetainedAssets/MaterialEvidence/{ident}"
                unity_material_doc = evidence_prefix + ".material.json"
                unity_effect_doc = evidence_prefix + ".effect.json"
                unity_path = f"Assets/Game/Content/RetainedAssets/Materials/{ident}.asset"
                creator_path = f"assets/resources/RetainedAssets/Materials/{ident}.json"
                write_payload(material_doc_raw, unity_material_doc, "source-material-document")
                write_payload(effect_raw, unity_effect_doc, "source-effect-document")
                write_payload(_unity_meta(unity_guid, "native-asset"), unity_path + ".meta", "unity-retained-material-meta")
                write_payload(envelope_raw, creator_path, "creator-retained-source-material-jsonasset")
                write_payload(_creator_meta(creator_uuid, "json"), creator_path + ".meta", "creator-jsonasset-meta")
                entry.update({"retentionKind": "retained-source-material", "nonRendering": True,
                              "renderingRecovered": False, "sourceMaterialUuid": material_uuid,
                              "sourceMaterialName": root_object.get("_name", ""),
                              "sourceMaterialDocumentSha256": material_doc_hash,
                              "sourceEffectId": effect_asset["sourceId"], "sourceEffectName": effect_obj.get("_name", ""),
                              "sourceEffectDocumentSha256": effect_hash, "sourceEffectImport": effect_pack,
                              "sourceEffectImportEvidenceCopy": effect_pack_copy,
                              "unity": {"path": unity_path, "guid": unity_guid, "type": "NativeRetainedMaterial",
                                        "materialDocumentPath": unity_material_doc, "effectDocumentPath": unity_effect_doc},
                              "creator": {"path": creator_path, "uuid": creator_uuid, "type": "cc.JsonAsset",
                                          "contentSha256": _sha(envelope_raw)}})

        hashes = {"sourceDocumentSha256": entry["sourceDocumentSha256"],
                  "sourceImportSha256": entry["sourceImport"]["sha256"]}
        if isinstance(entry.get("sourceNative"), dict):
            hashes["sourceNativeSha256"] = entry["sourceNative"]["sha256"]
        if entry.get("sourceEffectDocumentSha256"):
            hashes["sourceEffectDocumentSha256"] = entry["sourceEffectDocumentSha256"]
        effect_import = entry.get("sourceEffectImport") or entry.get("effectPack")
        if isinstance(effect_import, dict):
            hashes["sourceEffectImportSha256"] = effect_import["sha256"]
        entry["sourceHashes"] = hashes
        entries.append(entry)

    reference_index = {row["sourceAssetId"]: next((asset for asset in entries if asset["sourceId"] == row["sourceAssetId"]), None)
                       for row in field_references}
    for row in field_references:
        entry = reference_index.get(row["sourceAssetId"])
        if entry is not None:
            row["retentionKind"] = entry["retentionKind"]
            row["targetUnityType"] = entry["unity"]["type"]
            row["targetCreatorType"] = entry["creator"]["type"]

    contract = {"schema": SCHEMA, "sourceManifestSha256": actual_manifest_sha,
                "sourceManifestPath": str(manifest_path) if manifest_path else None,
                "sourceVersion": manifest_doc.get("sourceVersion"), "targetNamespace": plan["namespace"],
                "assets": entries, "references": field_references, "gaps": gaps,
                "creatorFieldTypeRules": [{"sourceFieldName": "_materials", "condition": "unknown source declaration + UnityEngine.Object[] asset refs",
                                           "creatorFieldType": "Asset[]", "rationale": "Cocos 3.8.8 JsonAsset and Material both extend Asset"}],
                "sourceEvidenceCopies": list(evidence_copies.values()), "payloads": payloads,
                "copies": [{key: row[key] for key in ("source", "target", "sha256")} for row in payloads]}
    attached_plan = copy.deepcopy(plan)
    attached_plan["staticRetainedAssets"] = contract
    io.write_json(output_root / "retained-assets.json", contract)
    output_manifest = io.finish(output_root, {"schemaVersion": 1, "schema": SCHEMA,
        "sourceManifestSha256": actual_manifest_sha, "assetCount": len(entries), "referenceCount": len(field_references),
        "gapCount": len(gaps), "payloadCount": len(payloads)})
    return {"plan": attached_plan, "contract": contract, "payloads": payloads,
            "output": str(output_root), "manifest": output_manifest}


def prepare(plan: dict, manifest, output: str | Path) -> dict:
    """Build an isolated payload set, removing only this call's failed output."""
    output_path = Path(output).absolute()
    existed = output_path.exists() or output_path.is_symlink()
    try:
        return _prepare(plan, manifest, output_path)
    except Exception:
        if not existed and output_path.is_dir() and not output_path.is_symlink():
            import shutil
            shutil.rmtree(output_path)
        raise


def emit(contract, stage_root, output_root, target):
    """Emit hash-pinned target payloads without treating .meta as another asset."""
    from .output_limits import copy_verified
    prefix='Assets/Game/Content/' if target=='unity' else 'assets/resources/'
    seen=set()
    for row in contract.get('payloads',[]):
        if not row['target'].startswith(prefix):continue
        if row['target'] in seen:raise RetainedAssetError('duplicate native retained payload')
        seen.add(row['target'])
        source=io.inside(Path(stage_root),row['source']);dest=io.inside(Path(output_root),row['target'])
        if dest.exists():raise RetainedAssetError('native retained payload collision: '+row['target'])
        copy_verified(source,dest,row['sha256'],row['bytes'])
