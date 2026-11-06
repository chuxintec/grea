"""Attach and emit the evidence-pinned Unity Spine native stage.

The ordinary target planner remains engine-agnostic.  This module adds the
already-validated Spine native factory payload to a completed Unity target
plan and materializes it beside the target's normal export files.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from .io import inside, read, sha, write_json
from .prefab_spine_native import SOURCE_SCALE_EVIDENCE, _verified_editor_variant
from .sources.compiled import fail


CONTRACT = "monkey-spine-native-stage/1"
NATIVE_CONTRACT = "monkey-spine-native-binding/1"
EMISSION_CONTRACT = "monkey-spine-emission/1"
MATERIAL_PROFILE = "cocos24-builtin-spine-material-v1"
_HELPERS = (
    ("targets/spine/UnitySpineBinding.cs", "Assets/Game/Editor/Conversion/Spine/UnitySpineBinding.cs"),
    ("targets/materials/spine/UnitySpineMaterialBindings.cs", "Assets/Game/Editor/Conversion/Spine/UnitySpineMaterialBindings.cs"),
    ("targets/spine/UnitySpineNativeFactory.cs", "Assets/Game/Editor/Conversion/Spine/UnitySpineNativeFactory.cs"),
    ("targets/spine/UnitySpineGraphicMaterialPresentation.cs", "Assets/Game/Scripts/Presentation/Recovered/Spine/UnitySpineGraphicMaterialPresentation.cs"),
    ("targets/spine/UnitySpineNativeStage.cs", "Assets/Game/Editor/Conversion/Spine/UnitySpineNativeStage.cs"),
    ("targets/spine/UnitySpineImporterIntegration.cs", "Assets/Game/Editor/Conversion/Spine/UnitySpineImporterIntegration.cs"),
    ("targets/spine/UnitySpineSourceIdentity.cs", "Assets/Game/Scripts/Presentation/Recovered/Spine/UnitySpineSourceIdentity.cs"),
)


class SpineNativeStageError(ValueError):
    """A frozen input does not satisfy the native Spine stage contract."""


def _document(path: str | Path) -> tuple[dict, bytes]:
    path = Path(path).resolve(strict=True)
    raw = read(path, max_bytes=128 * 1024 * 1024)
    try:
        result = json.loads(raw.decode("utf-8-sig"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise SpineNativeStageError(f"invalid JSON document {path}: {error}") from error
    if not isinstance(result, dict):
        raise SpineNativeStageError(f"expected JSON object: {path}")
    return result, raw


def _record(output: Path, source: str | Path, target: str, role: str,
            expected_sha256: str | None = None, expected_bytes: int | None = None) -> dict:
    source_path = Path(source)
    raw = read(source_path, max_bytes=128 * 1024 * 1024)
    digest = sha(raw)
    if expected_sha256 is not None and digest != expected_sha256:
        raise SpineNativeStageError(f"source hash changed for {source_path}")
    if expected_bytes is not None and len(raw) != expected_bytes:
        raise SpineNativeStageError(f"source size changed for {source_path}")
    if not target.startswith("Assets/") or ".." in Path(target).parts:
        raise SpineNativeStageError(f"invalid Unity target path {target!r}")
    relative = f"spine-native-stage-payloads/{digest}/{Path(target).name}"
    payload = inside(output, relative)
    payload.parent.mkdir(parents=True, exist_ok=True)
    if payload.exists():
        if read(payload, max_bytes=128 * 1024 * 1024) != raw:
            raise SpineNativeStageError(f"payload collision at {relative}")
    else:
        payload.write_bytes(raw)
    return {"source": relative, "target": target, "sha256": digest, "bytes": len(raw), "role": role}


def _unity_guid(namespace: str, identity: str) -> str:
    return uuid5_hex(f"monkey/{namespace}/{identity}")


def uuid5_hex(name: str) -> str:
    import uuid
    return uuid.uuid5(uuid.NAMESPACE_URL, name).hex


def _meta_payload(namespace: str, target: str, output: Path, kind: str, identity: str | None = None,
                  texture_profile: dict | None = None, plugin_scope: str | None = None) -> dict:
    target_meta = target + ".meta"
    guid = _unity_guid(namespace, "spine-native-stage/" + (identity or target))
    if kind == "plugin":
        # Keep the stock player DLLs out of the Editor when a source-built
        # Editor pair is supplied. The Editor pair is explicitly Editor-only.
        if plugin_scope is None:
            body = "fileFormatVersion: 2\n" + f"guid: {guid}\n"
        elif plugin_scope in ("player_exclude_editor", "editor_only"):
            any_enabled = 0 if plugin_scope == "editor_only" else 1
            editor_enabled = 1 if plugin_scope == "editor_only" else 0
            any_settings = " {}\n" if plugin_scope == "editor_only" else "\n        Exclude Editor: 1\n"
            body = (
                "fileFormatVersion: 2\n" + f"guid: {guid}\n" +
                "PluginImporter:\n  externalObjects: {}\n  serializedVersion: 2\n"
                "  iconMap: {}\n  executionOrder: {}\n  isPreloaded: 0\n  isOverridable: 0\n"
                "  platformData:\n"
                "  - first:\n      Any:\n"
                f"    second:\n      enabled: {any_enabled}\n      settings:"
                + any_settings +
                "  - first:\n      Editor: Editor\n"
                f"    second:\n      enabled: {editor_enabled}\n      settings:\n        DefaultValueInitialized: true\n        CPU: AnyCPU\n"
                "  userData: \n  assetBundleName: \n  assetBundleVariant: \n"
            )
        else:
            raise SpineNativeStageError(f"unsupported managed-plugin platform scope: {plugin_scope}")
    elif kind == "shader":
        body = ("fileFormatVersion: 2\n" + f"guid: {guid}\n" +
                "ShaderImporter:\n  externalObjects: {}\n  defaultTextures: []\n"
                "  nonModifiableTextures: []\n  preprocessorOverride: 0\n"
                "  userData: \n  assetBundleName: \n  assetBundleVariant: \n")
    elif kind == "texture":
        if (not isinstance(texture_profile, dict) or texture_profile.get("filterMode") not in (0, 1) or
                texture_profile.get("wrapU") not in (0, 1) or texture_profile.get("wrapV") not in (0, 1) or
                texture_profile.get("alphaSourceEnum") != 1 or texture_profile.get("mipMaps") is not False or
                texture_profile.get("preservePixelDimensions") is not True or
                texture_profile.get("textureCompressionEnum") != 0 or
                texture_profile.get("textureImporterPremultipliesAlpha") is not False):
            raise SpineNativeStageError(f"missing pinned 2D TextureImporter sampling profile: {target}")
        max_texture_size = int(texture_profile.get("maxTextureSize", 16384))
        if max_texture_size != 16384:
            raise SpineNativeStageError(f"Spine page must retain source dimensions without importer downscale: {target}")
        platform_settings = "".join(
            "  - serializedVersion: 4\n" + f"    buildTarget: {build_target}\n" +
            f"    maxTextureSize: {max_texture_size}\n    resizeAlgorithm: 0\n    textureFormat: -1\n" +
            "    textureCompression: 0\n    compressionQuality: 50\n    crunchedCompression: 0\n" +
            "    allowsAlphaSplitting: 0\n    overridden: 0\n    ignorePlatformSupport: 0\n" +
            "    androidETC2FallbackOverride: 0\n    forceMaximumCompressionQuality_BC6H_BC7: 0\n"
            for build_target in ("DefaultTexturePlatform", "Standalone", "Android", "WebGL", "iPhone"))
        # Spine atlas pages are native texture assets, not Cubemaps or Sprite
        # frame projections. Pin a supported 2D TextureImporter profile so a
        # missing/minimal GUID-only meta cannot inherit Unity's legacy Cube
        # defaults on first import.
        body = ("fileFormatVersion: 2\n" + f"guid: {guid}\n" +
                "TextureImporter:\n  internalIDToNameTable: []\n  externalObjects: {}\n  serializedVersion: 13\n"
                "  mipmaps:\n    mipMapMode: 0\n    enableMipMap: 0\n    sRGBTexture: 1\n    linearTexture: 0\n"
                "    fadeOut: 0\n    borderMipMap: 0\n    mipMapsPreserveCoverage: 0\n    alphaTestReferenceValue: 0.5\n"
                "    mipMapFadeDistanceStart: 1\n    mipMapFadeDistanceEnd: 3\n"
                "  bumpmap:\n    convertToNormalMap: 0\n    externalNormalMap: 0\n    heightScale: 0.25\n"
                "    normalMapFilter: 0\n    flipGreenChannel: 0\n"
                "  isReadable: 0\n  streamingMipmaps: 0\n  streamingMipmapsPriority: 0\n  vTOnly: 0\n"
                "  ignoreMipmapLimit: 0\n  grayScaleToAlpha: 0\n  generateCubemap: 0\n"
                "  cubemapConvolution: 0\n  seamlessCubemap: 0\n  textureFormat: 1\n"
                f"  maxTextureSize: {max_texture_size}\n"
                "  textureSettings:\n    serializedVersion: 2\n"
                f"    filterMode: {texture_profile['filterMode']}\n"
                "    aniso: 1\n    mipBias: 0\n"
                f"    wrapU: {texture_profile['wrapU']}\n    wrapV: {texture_profile['wrapV']}\n    wrapW: 1\n"
                "  nPOTScale: 0\n  lightmap: 0\n  compressionQuality: 50\n"
                "  spriteMode: 0\n  spriteExtrude: 1\n  spriteMeshType: 1\n  alignment: 0\n"
                "  spritePivot: {x: 0.5, y: 0.5}\n  spritePixelsToUnits: 100\n"
                "  spriteBorder: {x: 0, y: 0, z: 0, w: 0}\n  spriteGenerateFallbackPhysicsShape: 1\n"
                "  alphaUsage: 1\n  alphaIsTransparency: 0\n  spriteTessellationMethod: 0\n"
                "  spriteTessellationDetail: -1\n  spriteGeometrySubdivision: -1\n"
                "  textureType: 0\n  textureShape: 1\n  singleChannelComponent: 0\n"
                "  flipbookRows: 1\n  flipbookColumns: 1\n  maxTextureSizeSet: 0\n"
                "  compressionQualitySet: 0\n  textureFormatSet: 0\n  ignorePngGamma: 0\n"
                "  applyGammaDecoding: 1\n  swizzle: 50462976\n  cookieLightType: 0\n"
                "  platformSettings:\n" + platform_settings)
    else:
        body = ("fileFormatVersion: 2\n" + f"guid: {guid}\n" +
                "MonoImporter:\n  externalObjects: {}\n  serializedVersion: 2\n"
                "  defaultReferences: []\n  executionOrder: 0\n  icon: {instanceID: 0}\n"
                "  userData: \n  assetBundleName: \n  assetBundleVariant: \n")
    relative = f"spine-native-stage-payloads/generated/{hashlib.sha256(target_meta.encode()).hexdigest()[:16]}.meta"
    payload = inside(output, relative)
    payload.parent.mkdir(parents=True, exist_ok=True)
    raw = body.encode("utf-8")
    payload.write_bytes(raw)
    return {"source": relative, "target": target_meta, "sha256": sha(raw), "bytes": len(raw),
            "role": "spine-page-texture-meta" if kind == "texture" else "unity-meta"}


def _atlas_page_sampling(atlas_text: str, source_page: str, asset_id: str) -> dict:
    lines = atlas_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    pages: dict[str, dict] = {}
    current = None
    for index, line in enumerate(lines):
        if (line and not line[0].isspace() and ":" not in line and index + 1 < len(lines) and
                (lines[index + 1].startswith("size:") or lines[index + 1].startswith("format:"))):
            current = line.strip()
            if current in pages:
                raise SpineNativeStageError(f"duplicate Spine atlas page declaration: {asset_id}:{current}")
            pages[current] = {}
            continue
        if current and ":" in line:
            key, value = line.strip().split(":", 1)
            if key in ("filter", "repeat"):
                pages[current][key] = value.strip()
    row = pages.get(source_page)
    if row is None or row.get("filter") is None or row.get("repeat") is None:
        raise SpineNativeStageError(f"Spine atlas sampling evidence missing: {asset_id}:{source_page}")

    filters = [token.strip() for token in row["filter"].split(",")]
    if filters != ["Linear", "Linear"]:
        raise SpineNativeStageError(f"unsupported or ambiguous Spine atlas filter for Unity TextureImporter: {asset_id}:{source_page}:{row['filter']}")
    repeat = row["repeat"]
    wrap = {"none": (1, 1), "x": (0, 1), "y": (1, 0), "xy": (0, 0)}
    if repeat not in wrap:
        raise SpineNativeStageError(f"unsupported Spine atlas repeat for Unity TextureImporter: {asset_id}:{source_page}:{repeat}")
    wrap_u, wrap_v = wrap[repeat]
    return {
        "atlasFilter": row["filter"], "atlasRepeat": repeat,
        "filterMode": 1, "filterModeName": "Bilinear",
        "wrapU": wrap_u, "wrapV": wrap_v,
        "wrapUName": "Clamp" if wrap_u == 1 else "Repeat",
        "wrapVName": "Clamp" if wrap_v == 1 else "Repeat",
        "mipMaps": False, "alphaSource": "FromInput", "alphaSourceEnum": 1,
        "alphaIsTransparency": False, "textureType": "Default", "textureTypeEnum": 0,
        "textureShape": "Texture2D", "textureShapeEnum": 1,
        "npotScale": "None", "npotScaleEnum": 0,
        "textureCompression": "Uncompressed", "textureCompressionEnum": 0,
        "maxTextureSize": 16384, "preservePixelDimensions": True,
        "sourcePremultipliedAlpha": None,
        "textureImporterPremultipliesAlpha": False,
    }


def _expand_target_component_rows(target_plan: dict, native_plan: dict) -> tuple[dict, dict]:
    """Expand source-template Spine rows over exact sync-prefab origin edges.

    The source native binding plan remains untouched.  Returned component rows
    are stage-owned copies whose source identities and nodes are the exact IDs
    in target_plan; each carries the complete template-origin proof used for
    saved native-prefab marker readback.
    """
    target_prefabs = target_plan.get("sourcePrefabs")
    target_components = target_plan.get("components")
    target_nodes = target_plan.get("nodes")
    sync_groups = target_plan.get("syncPrefabBindings")
    source_rows = native_plan.get("components")
    if (not isinstance(target_prefabs, list) or not isinstance(target_components, list)
            or not isinstance(target_nodes, list) or not isinstance(sync_groups, list)
            or not isinstance(source_rows, list)):
        raise SpineNativeStageError("Unity target plan lacks source-prefab, component, node, or sync-origin arrays")

    prefabs = {row.get("sourceId"): row for row in target_prefabs if isinstance(row, dict)}
    nodes = {row.get("sourceId"): row for row in target_nodes if isinstance(row, dict)}
    target_spines = {row.get("sourceId"): row for row in target_components
                     if isinstance(row, dict) and row.get("type") == "sp.Skeleton"}
    templates = {row.get("sourceComponentId"): row for row in source_rows if isinstance(row, dict)}
    if len(prefabs) != len(target_prefabs) or len(nodes) != len(target_nodes):
        raise SpineNativeStageError("duplicate source prefab or node identity in Unity target plan")
    if len(templates) != len(source_rows) or not target_spines:
        raise SpineNativeStageError("duplicate source Spine template identity or no target Spine components")

    component_origins: dict[str, str] = {}
    node_origins: dict[str, str] = {}
    relation_by_component: dict[str, dict] = {}
    for group in sync_groups:
        if not isinstance(group, dict):
            raise SpineNativeStageError("malformed sync-prefab binding group")
        owner, root, template_prefab = group.get("owner"), group.get("root"), group.get("template")
        if not all(isinstance(value, str) and value for value in (owner, root, template_prefab)):
            raise SpineNativeStageError("sync-prefab binding lacks exact owner/root/template identities")
        if owner not in prefabs:
            raise SpineNativeStageError(f"sync-prefab owner is absent from target sourcePrefabs: {owner}")
        for relation, destination, label in ((group.get("componentOrigins"), component_origins, "component"),
                                             (group.get("origins"), node_origins, "node")):
            if not isinstance(relation, list):
                raise SpineNativeStageError(f"sync-prefab {label} origin list is missing")
            for row in relation:
                if (not isinstance(row, dict) or not isinstance(row.get("instanceSourceId"), str)
                        or not isinstance(row.get("templateSourceId"), str)):
                    raise SpineNativeStageError(f"malformed sync-prefab {label} origin row")
                instance_id, template_id = row["instanceSourceId"], row["templateSourceId"]
                if instance_id in destination and destination[instance_id] != template_id:
                    raise SpineNativeStageError(f"ambiguous sync-prefab {label} origin: {instance_id}")
                destination[instance_id] = template_id
                if label == "component":
                    prior = relation_by_component.get(instance_id)
                    current = {"owner": owner, "root": root, "templatePrefab": template_prefab}
                    if prior is not None and prior != current:
                        raise SpineNativeStageError(f"ambiguous sync-prefab owner for component: {instance_id}")
                    relation_by_component[instance_id] = current

    def resolve_origin(identity: str, origins: dict[str, str], terminals: set[str], label: str) -> tuple[str, list[str]]:
        current = identity
        chain = [identity]
        seen = {identity}
        while current not in terminals and current in origins:
            current = origins[current]
            if current in seen:
                raise SpineNativeStageError(f"cycle in sync-prefab {label} origins at {current}")
            seen.add(current)
            chain.append(current)
        return current, chain

    expanded = []
    for instance_id, target_row in target_spines.items():
        template_id, component_chain = resolve_origin(instance_id, component_origins, set(templates), "component")
        template = templates.get(template_id)
        if template is None:
            raise SpineNativeStageError(f"target Spine component has no exact native source template: {instance_id}")
        node_id = target_row.get("node")
        if not isinstance(node_id, str) or node_id not in nodes:
            raise SpineNativeStageError(f"target Spine node is absent from target plan: {instance_id}")
        source_prefab_id = relation_by_component.get(instance_id, {}).get("owner", template.get("sourcePrefabId"))
        if source_prefab_id not in prefabs:
            raise SpineNativeStageError(f"Spine source prefab owner is absent from target plan: {instance_id}")
        if node_id not in (prefabs[source_prefab_id].get("nodes") or []):
            raise SpineNativeStageError(f"Spine component node does not belong to its mapped owner prefab: {instance_id}")
        template_prefab_id = template.get("sourcePrefabId")
        template_source_node = template.get("sourceNodeId")
        template_node_id = (template_source_node if isinstance(template_source_node, str)
                            and template_source_node.startswith(str(template_prefab_id) + "#")
                            else str(template_prefab_id) + "#" + str(template_source_node))
        terminal_nodes = {template_node_id}
        resolved_node, node_chain = resolve_origin(node_id, node_origins, terminal_nodes, "node")
        if resolved_node != template_node_id:
            raise SpineNativeStageError(f"target Spine node origin does not match component template node: {instance_id}")

        copy_row = dict(template)
        copy_row["sourceComponentId"] = instance_id
        copy_row["sourcePrefabId"] = source_prefab_id
        copy_row["sourceNodeId"] = node_id
        copy_row["templateOrigin"] = {
            "sourceComponentId": template_id,
            "sourcePrefabId": template_prefab_id,
            "sourceNodeId": template_node_id,
            "componentOriginChain": component_chain,
            "nodeOriginChain": node_chain,
        }
        expanded.append(copy_row)

    if len(expanded) != len(target_spines) or len({row["sourceComponentId"] for row in expanded}) != len(expanded):
        raise SpineNativeStageError("expanded stage-owned Spine component denominator is inconsistent")
    if set(templates) - {row["templateOrigin"]["sourceComponentId"] for row in expanded}:
        raise SpineNativeStageError("target plan omits a native Spine source template")

    stage_plan = dict(native_plan)
    stage_plan["sourceTemplateComponentCount"] = len(templates)
    stage_plan["expandedInstanceComponentCount"] = len(expanded)
    stage_plan["sourceNativeBindingPlanSha256"] = None  # Filled by the caller from exact native-plan bytes.
    stage_plan["components"] = expanded
    stage_plan["componentCount"] = len(expanded)
    stage_plan["sourceStaticDataBoundCount"] = sum(bool(row.get("sourceHasStaticDataReference")) for row in expanded)
    stage_plan["sourceStaticDataUnboundCount"] = len(expanded) - stage_plan["sourceStaticDataBoundCount"]
    return stage_plan, {"targetSpineComponentCount": len(target_spines), "sourceTemplateComponentCount": len(templates),
                        "mappedInstanceCount": len(expanded), "unmappedInstanceCount": 0,
                        "syncComponentOriginCount": len(component_origins), "syncNodeOriginCount": len(node_origins)}


def prepare_unity_stage(target_plan: dict, native_plan_path: str | Path,
                        emission_path: str | Path, source_ir_path: str | Path,
                        closure_root: str | Path,
                        closure_freeze_path: str | Path,
                        runtime_evidence_path: str | Path,
                        runtime_stage_evidence_path: str | Path,
                        runtime_stage_root: str | Path, output: str | Path) -> dict:
    """Prepare an attachable stage and its payloads from pinned frozen inputs.

    `output` is the existing target plan directory. The function writes only a
    new `spine-native-stage-payloads/` subdirectory there.
    """
    if not isinstance(target_plan, dict) or target_plan.get("targetProfile") != "unity-6000.6.2f1-ugui":
        raise SpineNativeStageError("a completed Unity target plan is required")
    plan_path = Path(output).resolve()
    if not isinstance(target_plan.get("namespace"), str) or not target_plan["namespace"]:
        raise SpineNativeStageError("target plan namespace is missing")
    native_plan, native_raw = _document(native_plan_path)
    emission, _ = _document(emission_path)
    closure_freeze, closure_freeze_raw = _document(closure_freeze_path)
    runtime_evidence, _ = _document(runtime_evidence_path)
    runtime_stage, _ = _document(runtime_stage_evidence_path)

    if native_plan.get("contract") != NATIVE_CONTRACT or native_plan.get("schemaVersion") != 1:
        raise SpineNativeStageError("unsupported native Spine binding plan")
    if emission.get("contract") != EMISSION_CONTRACT or emission.get("schemaVersion") != 1:
        raise SpineNativeStageError("unsupported Spine emission receipt")
    pins = emission.get("pins", {})
    for key, plan_key in (("sourceManifestSha256", "sourceManifestSha256"), ("normalizedIrSha256", "sourceIrSha256")):
        expected = target_plan.get(plan_key)
        if not isinstance(expected, str) or pins.get(key) != expected or native_plan.get(key) != expected:
            raise SpineNativeStageError(f"target plan/emission/native plan source pin mismatch: {key}")
    if sha(closure_freeze_raw) != pins.get("unityClosureReceiptSha256"):
        raise SpineNativeStageError("Unity closure freeze receipt differs from Spine emission pin")
    manifest_path = target_plan.get("sourceManifestPath")
    if not isinstance(manifest_path, str) or sha(read(Path(manifest_path), max_bytes=128 * 1024 * 1024)) != target_plan["sourceManifestSha256"]:
        raise SpineNativeStageError("source manifest is missing or does not match target plan pin")
    if sha(read(Path(source_ir_path), max_bytes=128 * 1024 * 1024)) != target_plan["sourceIrSha256"]:
        raise SpineNativeStageError("source IR is missing or does not match target plan pin")

    components = native_plan.get("components")
    data_assets = native_plan.get("dataAssets")
    if not isinstance(components, list) or not isinstance(data_assets, list):
        raise SpineNativeStageError("native Spine plan lacks component or data asset arrays")
    scale_summary = native_plan.get("scaleEvidence")
    scale_by_asset = scale_summary.get("resolvedSkeletonDataAssetScales") if isinstance(scale_summary, dict) else None
    if (not isinstance(scale_summary, dict) or
            scale_summary.get("status") != "verified_source_renderer_unit_mapping" or
            not isinstance(scale_by_asset, dict)):
        raise SpineNativeStageError("native Spine plan lacks verified renderer-aware scale evidence")
    target_component_ids = {row.get("sourceId") for row in target_plan.get("components", []) if isinstance(row, dict)}
    target_prefab_ids = {row.get("sourceId") for row in target_plan.get("sourcePrefabs", []) if isinstance(row, dict)}
    renderer_context_by_component = {}
    for row in components:
        if not isinstance(row, dict) or row.get("sourceComponentId") not in target_component_ids:
            raise SpineNativeStageError("native Spine component is absent from the existing target plan")
        if row.get("sourcePrefabId") not in target_prefab_ids:
            raise SpineNativeStageError("native Spine component source prefab is absent from the target plan")
        if row.get("behavior") != "disabled" or row.get("sourceCallbacksExecuted") is not False:
            raise SpineNativeStageError("Spine source behavior must remain disabled")
        context = row.get("rendererSelection")
        component_id = row.get("sourceComponentId")
        if (not isinstance(context, dict) or context.get("sourceComponentId") != component_id or
                context.get("status") != "declared_not_native_readback" or
                context.get("nativeRendererReadback") != "pending" or
                context.get("rendererKind") not in {"SkeletonGraphic", "SkeletonAnimation"}):
            raise SpineNativeStageError("native Spine component lacks an exact declared renderer context")
        expected_transform = "RectTransform" if context["rendererKind"] == "SkeletonGraphic" else "Transform"
        if context.get("targetNodeTransform") != expected_transform:
            raise SpineNativeStageError("native Spine renderer context transform differs from renderer kind")
        if context["rendererKind"] == "SkeletonGraphic":
            if (type(context.get("canvasReferencePixelsPerUnit")) not in (int, float) or
                    not math.isfinite(float(context["canvasReferencePixelsPerUnit"])) or
                    float(context["canvasReferencePixelsPerUnit"]) <= 0 or
                    not isinstance(context.get("canvasIdentity"), str) or not context["canvasIdentity"]):
                raise SpineNativeStageError("SkeletonGraphic renderer context lacks positive finite Canvas PPU")
        elif context.get("canvasReferencePixelsPerUnit") is not None or context.get("canvasIdentity") not in (None, ""):
            raise SpineNativeStageError("SkeletonAnimation renderer context unexpectedly declares Canvas PPU")
        renderer_context_by_component[component_id] = context
    source_evidence = scale_summary.get("source")
    source_scale = source_evidence.get("sourceDefaultScale") if isinstance(source_evidence, dict) else None
    target_evidence = scale_summary.get("target")
    target_units = target_evidence.get("targetUnitsPerSourcePixel") if isinstance(target_evidence, dict) else None
    world_scale = target_evidence.get("worldSpaceCanvasScale") if isinstance(target_evidence, dict) else None
    pixels_conversion = target_evidence.get("pixelsPerUnitConversion") if isinstance(target_evidence, dict) else None
    if (source_evidence != SOURCE_SCALE_EVIDENCE or
            type(source_scale) not in (int, float) or not math.isfinite(float(source_scale)) or float(source_scale) <= 0 or
            not isinstance(target_evidence, dict) or target_evidence.get("status") != "verified_unit_mapping" or
            type(target_units) not in (int, float) or target_units != 1.0 or
            type(world_scale) not in (int, float) or world_scale != 1.0 or
            (pixels_conversion is not None and
             (type(pixels_conversion) not in (int, float) or pixels_conversion != 1.0))):
        raise SpineNativeStageError("native Spine source/target base unit evidence differs from the supported mapping")
    referenced_components_by_asset = {}
    for row in components:
        if row.get("sourceHasStaticDataReference") is True and row.get("sourceDataAssetId"):
            referenced_components_by_asset.setdefault(row["sourceDataAssetId"], []).append(row)
    if set(scale_by_asset) != {row.get("sourceAssetId") for row in data_assets}:
        raise SpineNativeStageError("native Spine scale evidence asset denominator differs")
    for row in data_assets:
        asset_id, scale, evidence = row.get("sourceAssetId"), row.get("scale"), row.get("scaleEvidence")
        expected = scale_by_asset.get(asset_id)
        if (type(scale) not in (int, float) or not math.isfinite(float(scale)) or float(scale) <= 0 or
                type(expected) not in (int, float) or not math.isfinite(float(expected)) or float(expected) <= 0 or
                scale != expected or not isinstance(evidence, dict) or
                evidence.get("status") != "verified_source_renderer_unit_mapping" or
                evidence.get("source") != SOURCE_SCALE_EVIDENCE or
                evidence.get("resolvedSkeletonDataAssetScale") != expected):
            raise SpineNativeStageError("native Spine asset scale differs from frozen renderer-aware scale evidence: " + str(asset_id))
        factory_input = row.get("factoryInput")
        factory_scale = factory_input.get("scale") if isinstance(factory_input, dict) else None
        if (type(factory_scale) not in (int, float) or not math.isfinite(float(factory_scale)) or
                float(factory_scale) <= 0 or factory_scale != expected):
            raise SpineNativeStageError("native Spine factory scale differs from frozen renderer-aware scale evidence: " + str(asset_id))
        used = referenced_components_by_asset.get(asset_id, [])
        contexts = evidence.get("rendererContexts")
        if (not used or not isinstance(contexts, list) or
                {context.get("sourceComponentId") for context in contexts if isinstance(context, dict)} !=
                {component.get("sourceComponentId") for component in used}):
            raise SpineNativeStageError("native Spine asset renderer-context denominator differs: " + str(asset_id))
        signatures = set()
        for context in contexts:
            if not isinstance(context, dict):
                raise SpineNativeStageError("native Spine asset renderer context is malformed: " + str(asset_id))
            kind = context.get("rendererKind")
            ppu = context.get("canvasReferencePixelsPerUnit")
            component_context = renderer_context_by_component.get(context.get("sourceComponentId"))
            if (component_context is None or component_context.get("rendererKind") != kind or
                    component_context.get("canvasReferencePixelsPerUnit") != ppu or
                    context.get("targetNodeTransform") != component_context.get("targetNodeTransform") or
                    context.get("canvasIdentity") != component_context.get("canvasIdentity")):
                raise SpineNativeStageError("native Spine asset context differs from the exact component renderer context: " + str(asset_id))
            signatures.add((kind, ppu))
        if len(signatures) != 1:
            raise SpineNativeStageError("shared native Spine asset has conflicting renderer/Canvas PPU contexts: " + str(asset_id))
        kind, ppu = next(iter(signatures))
        divisor = ppu if kind == "SkeletonGraphic" else 1.0
        recomputed = float(source_scale) * float(target_units) / float(divisor)
        if scale != recomputed:
            raise SpineNativeStageError("native Spine asset scale does not match its renderer-context formula: " + str(asset_id))
    if len(data_assets) != native_plan.get("dataAssetCount") or len(components) != native_plan.get("componentCount"):
        raise SpineNativeStageError("native Spine plan counts do not match its rows")
    if (native_plan.get("persistentVisiblePose") is not True or
        native_plan.get("visualPolicy") != "native_renderer_enabled_timeScale_zero_source_timeScale_retained" or
        native_plan.get("persistentVisiblePoseEvidence", {}).get("status") != "verified_pinned_spine_unity_3_8_runtime_source" or
        native_plan.get("persistentVisiblePoseEvidence", {}).get("upstreamCommit") != "8b4844bd4b193ba9e54487ed397a777993cbad56" or
        any(row.get("persistentVisiblePose") is not True or row.get("sourceTimeScaleVerified") is not True
            for row in components)):
        raise SpineNativeStageError("persistent visible native pose or original timeScale is not proven")

    if (native_plan.get("sourceMaterialProfile", {}).get("creatorMappingStatus") != "exact_source_builtin_profile_mapping" or
        not native_plan.get("sourceMaterialProfile", {}).get("creatorTargetMaterialUuid")):
        raise SpineNativeStageError("Creator exact built-in Spine material mapping is not proven")

    stage_native_plan, expansion = _expand_target_component_rows(target_plan, native_plan)
    stage_native_plan["sourceNativeBindingPlanSha256"] = sha(native_raw)
    stage_native_raw = (json.dumps(stage_native_plan, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")

    runtime_profile = runtime_evidence.get("unity", {}).get("spinePlugin", {})
    copied_files = runtime_stage.get("copiedFiles", {})
    runtime_root = Path(runtime_stage_root).resolve(strict=True)
    if (not runtime_stage.get("verified") or runtime_profile.get("manifestSha256") != runtime_stage.get("sourceManifestSha256") or
        runtime_profile.get("compiledAgainst") != "Unity6000.6.2f1"):
        raise SpineNativeStageError("Unity Spine runtime/license stage is not verified")
    for relative, proof in runtime_profile.get("fileChecks", {}).items():
        staged = copied_files.get(relative, {})
        if not proof.get("verified") or staged.get("verified") is not True or staged.get("sha256") != proof.get("expectedSha256"):
            raise SpineNativeStageError(f"runtime stage file is not hash-verified: {relative}")
    required_runtime = {"spine-csharp.dll", "spine-unity.dll", "Shaders/Spine-SkeletonGraphic.shader", "LICENSE"}
    if not required_runtime.issubset(copied_files):
        raise SpineNativeStageError("runtime stage lacks required DLL/shader/license files")
    editor_runtime_summary = _verified_editor_variant(runtime_profile, runtime_stage)
    editor_runtime_profile = runtime_profile.get("editorVariant")
    if editor_runtime_summary is not None:
        evidence_path = Path(editor_runtime_profile.get("evidencePath", "")).resolve(strict=True)
        evidence_raw = read(evidence_path, max_bytes=128 * 1024 * 1024)
        if sha(evidence_raw) != editor_runtime_profile.get("evidenceSha256"):
            raise SpineNativeStageError("Editor Spine source-build evidence file hash differs")
        editor_evidence, _ = _document(evidence_path)
        if (editor_evidence.get("status") != "verified_editor_source_build" or
                editor_evidence.get("sourceManifestSha256") != editor_runtime_profile.get("sourceManifestSha256") or
                editor_evidence.get("upstreamCommit") != runtime_profile.get("upstreamCommit") or
                editor_evidence.get("cocosCompatibilityFallbacksIncluded") is not False):
            raise SpineNativeStageError("Editor Spine source-build evidence content differs from runtime pin")
        for assembly in ("spine-csharp.dll", "spine-unity.dll"):
            proof = editor_runtime_profile["assemblies"][assembly]
            staged = runtime_stage["editorVariant"]["copiedFiles"].get(assembly, {})
            if staged.get("target") != "Assets/Plugins/Spine38/EditorRuntime/" + assembly:
                raise SpineNativeStageError("Editor Spine runtime staged path differs: " + assembly)
            source = inside(runtime_root, "EditorRuntime/" + assembly)
            if sha(read(source, max_bytes=128 * 1024 * 1024)) != proof.get("sha256"):
                raise SpineNativeStageError("Editor Spine runtime stage bytes differ: " + assembly)

    closure = Path(closure_root).resolve(strict=True)
    if Path(closure_freeze.get("candidatePath", "")).resolve() != closure:
        raise SpineNativeStageError("Unity closure freeze candidate path differs")
    closure_files = {row.get("path"): row for row in closure_freeze.get("files", []) if isinstance(row, dict)}
    closure_report_path = inside(closure, "Analysis/Evidence/spine-closures.json")
    closure_report_pin = closure_files.get("Analysis/Evidence/spine-closures.json", {})
    if sha(read(closure_report_path, max_bytes=128 * 1024 * 1024)) != closure_report_pin.get("sha256"):
        raise SpineNativeStageError("Unity closure report differs from frozen receipt")

    page_textures: dict[str, dict] = {}
    for asset in data_assets:
        atlas_path = asset.get("atlasTextAssetPath") if isinstance(asset, dict) else None
        if not isinstance(atlas_path, str) or atlas_path not in closure_files:
            raise SpineNativeStageError("Spine atlas sampling source is absent from the frozen Unity closure")
        atlas_bytes = read(inside(closure, atlas_path), max_bytes=128 * 1024 * 1024)
        if sha(atlas_bytes) != closure_files[atlas_path].get("sha256"):
            raise SpineNativeStageError(f"Spine atlas sampling source changed: {atlas_path}")
        atlas_text = atlas_bytes.decode("utf-8-sig")
        pma = asset.get("premultipliedAlpha")
        if type(pma) is not bool:
            raise SpineNativeStageError(f"Spine source PMA profile is not explicit: {asset.get('sourceAssetId')}")
        for page in asset.get("pages", []) if isinstance(asset, dict) else []:
            if not isinstance(page, dict):
                raise SpineNativeStageError("malformed Spine atlas page row")
            path, source_id = page.get("textureAssetPath"), page.get("sourceTextureSourceId")
            if (not isinstance(path, str) or not path.startswith("Assets/Game/Content/Spine/") or
                    ".." in Path(path).parts or not isinstance(source_id, str) or not source_id):
                raise SpineNativeStageError("Spine atlas page lacks a safe exact target texture path and source identity")
            prior = page_textures.get(path)
            if prior and prior["sourceTextureSourceId"] != source_id:
                raise SpineNativeStageError(f"ambiguous source texture identity for page path {path}")
            frozen_texture = closure_files.get(path)
            if not frozen_texture:
                raise SpineNativeStageError(f"Spine atlas page is absent from the frozen Unity closure: {path}")
            expected_texture_sha = page.get("textureSha256")
            if expected_texture_sha and frozen_texture.get("sha256") != expected_texture_sha:
                raise SpineNativeStageError(f"Spine atlas page hash differs from its frozen page record: {path}")
            sampling = _atlas_page_sampling(atlas_text, page.get("sourceAtlasPage"), asset.get("sourceAssetId", "unknown"))
            prior_profile = page_textures.get(path)
            if prior_profile:
                if prior_profile["sourceTextureSourceId"] != source_id or prior_profile["sampling"] != sampling:
                    raise SpineNativeStageError(f"shared Spine texture has conflicting source identity or sampling profile: {path}")
                if pma not in prior_profile["sourcePremultipliedAlphaProfiles"]:
                    prior_profile["sourcePremultipliedAlphaProfiles"].append(pma)
                prior_profile["sourceAtlasPages"].append(page.get("sourceAtlasPage"))
            else:
                page_textures[path] = {
                    "sourceTextureSourceId": source_id,
                    "sampling": sampling,
                    "sourcePremultipliedAlphaProfiles": [pma],
                    "sourceAtlasPages": [page.get("sourceAtlasPage")],
                }
    replaced_page_meta = {path + ".meta" for path in page_textures}

    payload_root = inside(plan_path, "spine-native-stage-payloads")
    if payload_root.exists():
        raise SpineNativeStageError("Spine payload staging directory already exists; use a fresh target plan")
    payload_root.mkdir(parents=True)
    copies = []
    seen_targets = set()
    ignored_page_meta_targets = set()
    for row in emission.get("copies", []):
        if row.get("target") != "unity":
            continue
        target = row.get("path")
        frozen_file = closure_files.get(target)
        if not frozen_file or frozen_file.get("sha256") != row.get("sha256") or frozen_file.get("bytes") != row.get("bytes"):
            raise SpineNativeStageError(f"Unity closure copy is not covered by frozen receipt: {target}")
        if target in replaced_page_meta:
            # The source sidecar is evidence only. Emit a new target Texture2D
            # importer profile below, never the absent/legacy Cubemap profile.
            ignored_page_meta_targets.add(target)
            continue
        if target in seen_targets:
            raise SpineNativeStageError(f"duplicate Unity closure target {target}")
        seen_targets.add(target)
        copies.append(_record(plan_path, inside(closure, target), target,
                              "source-spine-closure", row.get("sha256"), row.get("bytes")))

    for target, page in sorted(page_textures.items()):
        if target not in seen_targets:
            raise SpineNativeStageError(f"Spine atlas page bytes were not included in the Unity closure emission: {target}")
        texture_meta = _meta_payload(target_plan["namespace"], target, plan_path, "texture",
                                     "spine-page-texture/" + page["sourceTextureSourceId"], page["sampling"])
        if texture_meta["target"] in seen_targets:
            raise SpineNativeStageError(f"Spine page importer metadata collides with a closure asset: {texture_meta['target']}")
        seen_targets.add(texture_meta["target"])
        copies.append(texture_meta)

    runtime_manifest = runtime_profile.get("path")
    if not isinstance(runtime_manifest, str):
        raise SpineNativeStageError("verified runtime manifest path is missing")
    runtime_manifest_path = Path(runtime_manifest).resolve(strict=True)
    runtime_manifest_raw = read(runtime_manifest_path, max_bytes=128 * 1024 * 1024)
    if sha(runtime_manifest_raw) != runtime_profile.get("manifestSha256"):
        raise SpineNativeStageError("runtime manifest source hash changed")
    stage_manifest_path = inside(runtime_root, "manifest.json")
    if read(stage_manifest_path, max_bytes=128 * 1024 * 1024) != runtime_manifest_raw:
        raise SpineNativeStageError("isolated runtime manifest does not match verified source manifest")
    runtime_target_root = "Assets/Plugins/Spine38"
    copies.append(_record(plan_path, stage_manifest_path, runtime_target_root + "/manifest.json", "runtime-manifest",
                          runtime_profile["manifestSha256"], len(runtime_manifest_raw)))
    for relative, expected in runtime_profile.get("fileChecks", {}).items():
        source = inside(runtime_root, relative)
        target = runtime_target_root + "/" + relative
        record = _record(plan_path, source, target, "verified-runtime-license-or-shader",
                         expected.get("expectedSha256"), expected.get("expectedBytes"))
        copies.append(record)
        if target.endswith(".dll"):
            plugin_scope = "player_exclude_editor" if editor_runtime_summary is not None and relative in ("spine-csharp.dll", "spine-unity.dll") else None
            copies.append(_meta_payload(target_plan["namespace"], target, plan_path, "plugin", plugin_scope=plugin_scope))

    if editor_runtime_summary is not None:
        for assembly in ("spine-csharp.dll", "spine-unity.dll"):
            proof = editor_runtime_profile["assemblies"][assembly]
            target = "Assets/Plugins/Spine38/EditorRuntime/" + assembly
            record = _record(plan_path, inside(runtime_root, "EditorRuntime/" + assembly), target,
                             "verified-editor-only-spine-runtime", proof["sha256"], proof["bytes"])
            copies.append(record)
            copies.append(_meta_payload(target_plan["namespace"], target, plan_path, "plugin",
                                        identity="editor-variant/" + assembly, plugin_scope="editor_only"))

    native_plan_rel = "Assets/Game/Editor/Conversion/spine-native-binding-plan.json"
    native_source_plan_rel = "Assets/Game/Editor/Conversion/spine-native-source-binding-plan.json"
    copies.append(_record(plan_path, native_plan_path, native_source_plan_rel, "source-native-binding-plan",
                          sha(native_raw), len(native_raw)))
    stage_plan_digest = sha(stage_native_raw)
    stage_plan_payload = f"spine-native-stage-payloads/generated/{stage_plan_digest}.json"
    stage_plan_path = inside(plan_path, stage_plan_payload)
    stage_plan_path.parent.mkdir(parents=True, exist_ok=True)
    stage_plan_path.write_bytes(stage_native_raw)
    copies.append({"source": stage_plan_payload, "target": native_plan_rel,
                   "sha256": stage_plan_digest, "bytes": len(stage_native_raw), "role": "expanded-stage-native-binding-plan"})
    source_root = Path(__file__).resolve().parent
    for relative, target in _HELPERS:
        source = source_root / relative
        copies.append(_record(plan_path, source, target, "unity-native-spine-helper"))
        copies.append(_meta_payload(target_plan["namespace"], target, plan_path, "script"))

    shader = native_plan.get("unityShader", {})
    shader_source = Path(shader.get("sourcePath", ""))
    if shader.get("sha256") != sha(read(shader_source)):
        raise SpineNativeStageError("Unity source profile shader hash differs from native plan")
    copies.append(_record(plan_path, shader_source, shader.get("targetPath"), "source-profile-shader", shader["sha256"]))
    copies.append(_meta_payload(target_plan["namespace"], shader["targetPath"], plan_path, "shader"))

    graphic_shader = native_plan.get("unityGraphicShader", {})
    graphic_shader_source = Path(graphic_shader.get("sourcePath", ""))
    if graphic_shader.get("sha256") != sha(read(graphic_shader_source)):
        raise SpineNativeStageError("Unity Spine UI graphic shader hash differs from native plan")
    if graphic_shader.get("shaderName") != "Monkey/SpineSourceGraphicProfile/Colored":
        raise SpineNativeStageError("Unity Spine UI graphic shader identity differs from pinned helper")
    copies.append(_record(plan_path, graphic_shader_source, graphic_shader.get("targetPath"),
                          "source-profile-ui-graphic-shader", graphic_shader["sha256"]))
    copies.append(_meta_payload(target_plan["namespace"], graphic_shader["targetPath"], plan_path, "shader"))

    # The native-plan file, helpers, DLLs and closure are all explicit in the
    # export plan; callers can attach this object and call emit_unity_stage.
    stage = {
        "schemaVersion": 1,
        "contract": CONTRACT,
        "target": "unity",
        "sourceManifestSha256": native_plan["sourceManifestSha256"],
        "sourceIrSha256": native_plan["normalizedIrSha256"],
        "emissionReceiptSha256": sha(read(Path(emission_path), max_bytes=128 * 1024 * 1024)),
        "nativeBindingPlanSha256": stage_plan_digest,
        "sourceNativeBindingPlanSha256": sha(native_raw),
        "expandedStagePlanSha256": stage_plan_digest,
        "nativeBindingPlanPath": native_plan_rel,
        "runtimeManifestSha256": runtime_profile["manifestSha256"],
        "runtimeFilesVerified": len(required_runtime),
        "editorRuntimeVariant": editor_runtime_summary,
        "runtimeLicenseIncluded": True,
        "resolvedSkeletonDataScale": (next(iter({row["scale"] for row in data_assets}))
                                       if len({row["scale"] for row in data_assets}) == 1 else None),
        "resolvedSkeletonDataScales": dict(scale_by_asset),
        "persistentVisiblePose": True,
        "visualPolicy": native_plan["visualPolicy"],
        "persistentVisiblePoseEvidence": native_plan["persistentVisiblePoseEvidence"],
        "scaleEvidenceStatus": native_plan["scaleEvidence"]["status"],
        "rendererSelection": "actual target node RectTransform => SkeletonGraphic; otherwise SkeletonAnimation",
        "componentCount": len(stage_native_plan["components"]),
        "sourceTemplateComponentCount": expansion["sourceTemplateComponentCount"],
        "expandedInstanceComponentCount": expansion["mappedInstanceCount"],
        "instanceExpansion": expansion,
        "boundComponentCount": stage_native_plan["sourceStaticDataBoundCount"],
        "unboundComponentCount": stage_native_plan["sourceStaticDataUnboundCount"],
        "dataAssetCount": len(data_assets),
        "pageTextureCount": len(page_textures),
        "pageTextureImporterProfile": "Unity6000.6.2f1-TextureImporter-v13-Default-Texture2D-from-source-atlas",
        "pageTextureProfiles": [
            {"textureAssetPath": path, **row} for path, row in sorted(page_textures.items())
        ],
        "pageTextureSourceMetasIgnored": sorted(ignored_page_meta_targets),
        "creatorMaterialProfile": native_plan["sourceMaterialProfile"],
        "importHook": [
            "var spinePlan = UnitySpineNativeStage.Parse(File.ReadAllText(\"Assets/Game/Editor/Conversion/spine-native-binding-plan.json\"));",
            "var spineAssets = UnitySpineNativeStage.CreateDataAssets(spinePlan);",
            "var spineComponents = UnitySpineNativeStage.CreateComponents(spinePlan, spineAssets, ResolveSourceNode, currentSourcePrefabId);",
            "SavePrefabAndReopen();",
            "var spineReadback = UnitySpineNativeStage.ReadSaved(spinePlan, ResolveSavedSpineComponent, currentSourcePrefabId);",
        ],
        "copies": copies,
        "nativeImport": "not_run",
        "sourceBehaviorExecuted": False,
    }
    write_json(plan_path / "spine-native-stage.json", stage)
    return stage


def attach_unity_stage(target_plan: dict, stage: dict) -> dict:
    """Attach stage metadata to a completed Unity target plan in memory."""
    if not isinstance(target_plan, dict) or not isinstance(stage, dict) or stage.get("contract") != CONTRACT:
        raise SpineNativeStageError("invalid target plan or Spine native stage")
    if target_plan.get("sourceManifestSha256") != stage.get("sourceManifestSha256") or target_plan.get("sourceIrSha256") != stage.get("sourceIrSha256"):
        raise SpineNativeStageError("stage source pins differ from Unity target plan")
    if target_plan.get("spineNativeStage") is not None:
        raise SpineNativeStageError("Unity target plan already has a Spine native stage")
    target_plan["spineNativeStage"] = stage
    return target_plan


def refresh_unity_stage_helpers(plan_file: str | Path, output: str | Path) -> dict:
    """Freeze current owned helper implementations in a new, verified plan.

    Source closure, runtime binaries, identities and binding plans are copied
    byte-for-byte. Existing plans and exported candidates remain immutable.
    """
    from copy import deepcopy
    from . import io
    from .output_limits import copy_verified

    source = Path(plan_file).resolve(strict=True)
    plan = io.stage_document(source)
    stage = plan.get('spineNativeStage')
    if (plan.get('targetProfile') != 'unity-6000.6.2f1-ugui' or
            not isinstance(stage, dict) or stage.get('contract') != CONTRACT or
            stage.get('target') != 'unity' or
            stage.get('sourceManifestSha256') != plan.get('sourceManifestSha256') or
            stage.get('sourceIrSha256') != plan.get('sourceIrSha256')):
        raise SpineNativeStageError('helper refresh requires a source-bound Unity Spine stage')
    helpers = {target: Path(__file__).resolve().parent / relative for relative, target in _HELPERS}
    copies = stage.get('copies', [])
    seen = set()
    for row in copies:
        if row['target'] in seen:
            raise SpineNativeStageError('duplicate staged helper refresh target')
        seen.add(row['target'])
        raw = read(inside(source.parent, row['source']), max_bytes=128 * 1024 * 1024)
        if sha(raw) != row['sha256'] or len(raw) != row['bytes']:
            raise SpineNativeStageError('helper refresh input payload changed')
        if (row['target'] in helpers) != (row.get('role') == 'unity-native-spine-helper'):
            raise SpineNativeStageError('helper refresh ownership differs')
    if not set(helpers).issubset(seen):
        raise SpineNativeStageError('helper refresh target set incomplete')
    out = io.new_output(output, [source.parent])
    for row in io.stage_manifest(source.parent)['files']:
        if row['path'] not in (source.name, 'spine-native-stage.json'):
            copy_verified(inside(source.parent, row['path']), inside(out, row['path']), row['sha256'], row['bytes'])
    stage = deepcopy(stage)
    changes = []
    for index, row in enumerate(stage['copies']):
        if row['target'] not in helpers:
            continue
        updated = _record(out, helpers[row['target']], row['target'], row['role'])
        stage['copies'][index] = updated
        changes.append({'target': row['target'], 'previousSha256': row['sha256'], 'sha256': updated['sha256']})
    plan['spineNativeStage'] = stage
    plan['nativeHelperRefresh'] = {'parentPlanSha256': sha(source.read_bytes()), 'helpers': changes,
                                  'sourceAssetsChanged': False, 'nativeImport': 'not_run'}
    write_json(out / 'spine-native-stage.json', stage)
    write_json(out / 'plan.json', plan)
    return io.finish(out, plan)


def emit_unity_stage(stage: dict, plan_root: str | Path, output: str | Path) -> dict:
    """Emit verified payload files into a fresh or partially assembled Unity candidate."""
    if not isinstance(stage, dict) or stage.get("contract") != CONTRACT or stage.get("target") != "unity":
        raise SpineNativeStageError("invalid Unity Spine native stage")
    plan_root, output = Path(plan_root).resolve(), Path(output).resolve()
    emitted = []
    seen = set()
    for row in stage.get("copies", []):
        target = row.get("target")
        if target in seen:
            raise SpineNativeStageError(f"duplicate emitted target path {target}")
        seen.add(target)
        raw = read(inside(plan_root, row["source"]), max_bytes=128 * 1024 * 1024)
        if sha(raw) != row.get("sha256") or len(raw) != row.get("bytes"):
            raise SpineNativeStageError(f"staged payload changed: {row.get('source')}")
        dest = inside(output, target)
        if dest.exists():
            if read(dest, max_bytes=128 * 1024 * 1024) != raw:
                raise SpineNativeStageError(f"refuse to replace different existing target file: {target}")
            status = "already_present_identical"
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
            status = "emitted"
        emitted.append({"target": target, "sha256": row["sha256"], "bytes": len(raw), "status": status})
    return {"contract": "monkey-spine-native-stage-emission/1", "fileCount": len(emitted),
            "files": emitted, "componentCount": stage["componentCount"], "dataAssetCount": stage["dataAssetCount"],
            "nativeImport": "not_run"}


def creator_profile_handoff(native_plan: dict) -> dict:
    """Return the exact material-profile assertion consumed by Creator planning.

    Creator assets/components remain emitted by `prefab_spine_pipeline`; this
    helper makes the profile condition explicit to callers sharing the stage.
    """
    profile = native_plan.get("sourceMaterialProfile", {}) if isinstance(native_plan, dict) else {}
    if (profile.get("creatorMappingStatus") != "exact_source_builtin_profile_mapping" or
        not profile.get("sourceReferenceSourceId") or not profile.get("resolvedSourceMaterialId") or
        not profile.get("creatorTargetMaterialUuid")):
        raise SpineNativeStageError("Creator source material does not have an exact built-in profile mapping")
    return {"profile": MATERIAL_PROFILE, "status": profile["creatorMappingStatus"],
            "sourceReferenceSourceId": profile["sourceReferenceSourceId"],
            "resolvedSourceMaterialId": profile["resolvedSourceMaterialId"],
            "targetMaterialUuid": profile["creatorTargetMaterialUuid"],
            "pipeline": "prefab_spine_pipeline.prepare/emit", "sourceScriptsExecuted": False}
