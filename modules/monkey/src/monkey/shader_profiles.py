"""Exact, evidence-bound adapters for a deliberately small Cocos shader subset."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any


PROFILE = "cocos-2.4.15/builtin-2d-sprite/texture-vertex-color-v1"
SOURCE_ID = "internal:2874f8dd-416c-4440-81b7-555975426e93"
EFFECT_SHA256 = "d4fce14f78a0eba3c48a6d2e86408c724110bad7f9e2d075618f7a3d03ac6c26"
VERTEX_SHA256 = "3bb2a65a00f3d6de2dbbe654f9ebda74152bd3b83a8b8651f7b7c65fda7a1ef0"
FRAGMENT_SHA256 = "2bcdc12679e7a37a820c0de2e3f9c1197b11f11fa129896c6fc7364d3db10ce1"
_DEFINES = {
    "USE_TEXTURE": True,
    "CC_USE_MODEL": False,
    "USE_ALPHA_TEST": False,
    "CC_USE_ALPHA_ATLAS_texture": False,
    "INPUT_IS_GAMMA": False,
    "USE_BGRA": False,
}
_LIMITATIONS = [
    "Only this exact Cocos Creator 2.4.15 builtin-2d-sprite effect and glsl1 program is adapted.",
    "This profile fixes USE_TEXTURE=true and every other supported macro=false; all macro variants are rejected.",
    "Alpha test, alpha atlas, gamma input, BGRA swizzle, other programs, and arbitrary GLSL are not converted.",
    "The supplied source evidence does not establish a separate license for this extracted built-in effect.",
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _unsupported(reason: str, effect_sha256: str | None = None) -> dict[str, Any]:
    return {
        "supported": False,
        "profile": None,
        "sourceId": SOURCE_ID,
        "effectSha256": effect_sha256,
        "limitations": _LIMITATIONS,
        "reason": reason,
        "action": "Preserve source EffectDescription and GLSL; implement a reviewed adapter for this exact program.",
    }


def describe(effect: dict[str, Any], *, effect_sha256: str | None = None) -> dict[str, Any]:
    """Describe only the pinned source bytes and exact macro/property contract.

    The explicit raw-byte digest is necessary because callers pass a parsed JSON
    object, which cannot attest to the original serialization on its own.
    """
    if not isinstance(effect, dict):
        return _unsupported("EffectDescription must be a JSON object", effect_sha256)
    if effect_sha256 != EFFECT_SHA256:
        return _unsupported("EffectDescription raw SHA-256 is absent or differs from the pinned source", effect_sha256)
    try:
        shaders = effect["shaders"]
        if effect.get("__type__") != "cc.EffectAsset" or effect.get("_name") != "builtin-2d-sprite":
            return _unsupported("Effect identity differs from the pinned builtin program", effect_sha256)
        if len(shaders) != 1 or shaders[0].get("name") != "builtin-2d-sprite|vs|fs":
            return _unsupported("Shader program set differs from the pinned source", effect_sha256)
        shader = shaders[0]
        if shader.get("glsl1", {}).get("vert") is None or shader.get("glsl1", {}).get("frag") is None:
            return _unsupported("Pinned glsl1 stages are absent", effect_sha256)
        vertex_hash = _sha(shader["glsl1"]["vert"].encode("utf-8"))
        fragment_hash = _sha(shader["glsl1"]["frag"].encode("utf-8"))
        if (vertex_hash, fragment_hash) != (VERTEX_SHA256, FRAGMENT_SHA256):
            return _unsupported("Embedded glsl1 stage SHA-256 differs from the pinned program", effect_sha256)
        names = {item.get("name"): item for item in shader.get("defines", [])}
        if set(names) != set(_DEFINES) or any(names[k].get("type") != "boolean" for k in names):
            return _unsupported("Macro declaration set differs from the pinned source", effect_sha256)
        passes = [p for technique in effect.get("techniques", []) for p in technique.get("passes", [])]
        if len(passes) != 1 or passes[0].get("program") != "builtin-2d-sprite|vs|fs":
            return _unsupported("Technique/pass set differs from the pinned source", effect_sha256)
        render = passes[0]
        if render.get("blendState") != {"targets": [{"blend": True}]}:
            return _unsupported("Blend state differs from the pinned source", effect_sha256)
        props = render.get("properties", {})
        if props.get("texture", {}).get("value") != "white" or props.get("alphaThreshold", {}).get("value") != [0.5]:
            return _unsupported("Default properties differ from the pinned source", effect_sha256)
    except (KeyError, TypeError, AttributeError):
        return _unsupported("EffectDescription shape is incomplete", effect_sha256)
    return {
        "supported": True,
        "profile": PROFILE,
        "sourceId": SOURCE_ID,
        "effectSha256": effect_sha256,
        "sourceProgramSha256": {"glsl1.vert": vertex_hash, "glsl1.frag": fragment_hash},
        "defines": dict(_DEFINES),
        "parameters": {"texture": "white", "alphaThreshold": 0.5},
        "unityBlend": "SrcAlpha OneMinusSrcAlpha, SrcAlpha OneMinusSrcAlpha",
        "limitations": _LIMITATIONS,
    }


def _namespace_identity(namespace: str) -> str:
    if (not isinstance(namespace, str) or not namespace or len(namespace) > 4096
            or any(ord(char) < 32 or ord(char) == 127 for char in namespace)):
        raise ValueError("namespace must be a non-empty string of at most 4096 characters without control characters")
    return namespace


def _write_new(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite existing output: {path}")
    with path.open("xb") as stream:
        stream.write(data)


def _output_folder(root: Path, folder: str | Path | None) -> tuple[Path, str]:
    relative = Path("Assets/Game/Content/Shaders/RecoveredBuiltin2DSprite") if folder is None else Path(folder)
    raw = relative.as_posix()
    if (relative.is_absolute() or "\\" in raw or ":" in raw or any(part in ("", ".", "..") for part in raw.split("/"))
            or any(ord(char) < 32 or ord(char) == 127 for char in raw) or not raw.startswith("Assets/")):
        raise ValueError("folder must be a canonical project-relative path under Assets/")
    cursor = root
    for part in raw.split("/"):
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("folder path contains a symlink")
    if not cursor.resolve().is_relative_to(root.resolve()):
        raise ValueError("folder path escaped Unity project")
    return cursor, raw


def _csharp_literal_content(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)[1:-1]


def export_profile(
    effect: dict[str, Any], project: Path, namespace: str, source_id: str, *, effect_sha256: str,
    folder: str | Path | None = None,
) -> dict[str, Any]:
    """Write an isolated Unity shader/material pair and evidence report; never overwrite."""
    profile = describe(effect, effect_sha256=effect_sha256)
    if source_id != SOURCE_ID or not profile["supported"]:
        profile = _unsupported("Source identity or exact shader profile is unsupported", effect_sha256)
        profile["requestedSourceId"] = source_id
        return {"written": False, "profile": profile, "files": []}
    root = Path(project).expanduser().absolute()
    assets = root / "Assets"
    if not assets.is_dir():
        raise ValueError("project must be an existing Unity project with an Assets directory")
    module = _namespace_identity(namespace)
    output_dir, folder_relative = _output_folder(root, folder)
    shader_path = output_dir / "RecoveredSprite.shader"
    mat_path = output_dir / "RecoveredSprite.mat"
    meta_path = Path(str(shader_path) + ".meta")
    material_meta_path = Path(str(mat_path) + ".meta")
    report_path = output_dir / "shader-profile.json"
    report_meta_path = Path(str(report_path) + ".meta")
    guid = uuid.uuid5(uuid.NAMESPACE_URL, f"{source_id}:{module}:{PROFILE}:shader").hex
    material_guid = uuid.uuid5(uuid.NAMESPACE_URL, f"{source_id}:{module}:{PROFILE}:material").hex
    report_guid = uuid.uuid5(uuid.NAMESPACE_URL, f"{source_id}:{module}:{PROFILE}:report").hex
    shader = (Path(__file__).parent / "targets" / "RecoveredSprite.shader").read_bytes()
    shader_meta = f"fileFormatVersion: 2\nguid: {guid}\nShaderImporter:\n  externalObjects: {{}}\n  defaultTextures: []\n  nonModifiableTextures: []\n  preprocessorOverride: 0\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n".encode()
    material = ("%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n--- !u!21 &2100000\nMaterial:\n  serializedVersion: 8\n  m_ObjectHideFlags: 0\n  m_CorrespondingSourceObject: {fileID: 0}\n  m_PrefabInstance: {fileID: 0}\n  m_PrefabAsset: {fileID: 0}\n  m_Name: RecoveredSprite\n  m_Shader: {fileID: 4800000, guid: " + guid + ", type: 3}\n  m_Parent: {fileID: 0}\n  m_ModifiedSerializedProperties: 0\n  m_ValidKeywords: []\n  m_InvalidKeywords: []\n  m_LightmapFlags: 4\n  m_EnableInstancingVariants: 0\n  m_DoubleSidedGI: 0\n  m_CustomRenderQueue: -1\n  stringTagMap: {}\n  disabledShaderPasses: []\n  m_SavedProperties:\n    serializedVersion: 3\n    m_TexEnvs:\n    - _MainTex:\n        m_Texture: {fileID: 0}\n        m_Scale: {x: 1, y: 1}\n        m_Offset: {x: 0, y: 0}\n    m_Ints: []\n    m_Floats: []\n    m_Colors: []\n  m_BuildTextureStacks: []\n").encode()
    report = dict(schemaVersion=1, status="candidate-generated-native-validation-pending", nativeShader=True, namespace=module, **profile,
                  sourceLicense={"engineRuntimeCode": "MIT notice confirmed for the pinned Cocos 2.4.15 engine source file used to establish Sprite blend defaults.",
                                 "effectAsset": "The extracted EffectDescription contains no license notice; no separate rights conclusion is made for that asset.",
                                 "status": "engine-source-license-recorded-effect-asset-license-not-individually-marked"},
                  outputs={"folder": folder_relative, "shader": shader_path.relative_to(root).as_posix(), "shaderSha256": _sha(shader),
                           "shaderMeta": meta_path.relative_to(root).as_posix(), "shaderGuid": guid,
                           "material": mat_path.relative_to(root).as_posix(), "materialSha256": _sha(material),
                           "materialMeta": material_meta_path.relative_to(root).as_posix(),
                           "materialGuid": material_guid, "report": report_path.relative_to(root).as_posix(),
                           "reportGuid": report_guid})
    text_meta = lambda value: (f"fileFormatVersion: 2\nguid: {value}\nTextScriptImporter:\n  externalObjects: {{}}\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n").encode()
    material_meta = (f"fileFormatVersion: 2\nguid: {material_guid}\nNativeFormatImporter:\n  externalObjects: {{}}\n  mainObjectFileID: 2100000\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n").encode()
    outputs = [(shader_path, shader), (meta_path, shader_meta), (mat_path, material),
               (material_meta_path, material_meta), (report_path, _canonical(report) + b"\n"),
               (report_meta_path, text_meta(report_guid))]
    # Preflight the full write set before producing any part of the pair.
    for path, _ in outputs:
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"refusing to overwrite existing output: {path}")
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("output path escaped Unity project")
    for path, data in outputs:
        _write_new(path, data)
    return {"written": True, "files": [p.relative_to(root).as_posix() for p, _ in outputs], "profile": report}


def prepare_probe(candidate: Path, expected_manifest: Path | dict[str, Any], source_id: str, out: Path) -> dict[str, Any]:
    """Create an isolated minimal Unity project and bounded Editor probe plan."""
    if source_id != SOURCE_ID:
        raise ValueError("probe accepts only the pinned source identity")
    candidate = Path(candidate).expanduser().absolute()
    manifest = json.loads(Path(expected_manifest).read_text("utf-8")) if isinstance(expected_manifest, (str, Path)) else expected_manifest
    if not isinstance(manifest, dict) or manifest.get("status") != "candidate-generated-native-validation-pending":
        raise ValueError("expected manifest must be the exporter profile report")
    expected_shader = manifest.get("outputs", {}).get("shaderSha256")
    output = manifest.get("outputs", {})
    _, folder_relative = _output_folder(candidate, output.get("folder"))
    expected_paths = {
        "shader": f"{folder_relative}/RecoveredSprite.shader",
        "shaderMeta": f"{folder_relative}/RecoveredSprite.shader.meta",
        "material": f"{folder_relative}/RecoveredSprite.mat",
        "materialMeta": f"{folder_relative}/RecoveredSprite.mat.meta",
    }
    if any(output.get(key) != value for key, value in expected_paths.items()):
        raise ValueError("candidate manifest output paths do not match the profile's owned asset layout")
    shader = candidate / expected_paths["shader"]
    material = candidate / expected_paths["material"]
    shader_meta = candidate / expected_paths["shaderMeta"]
    material_meta = candidate / expected_paths["materialMeta"]
    if not shader.is_file() or _sha(shader.read_bytes()) != expected_shader:
        raise ValueError("candidate shader missing or differs from expected manifest")
    if not material.is_file() or _sha(material.read_bytes()) != output.get("materialSha256"):
        raise ValueError("candidate material missing or differs from expected manifest")
    for meta, guid, label in ((shader_meta, output.get("shaderGuid"), "shader"),
                              (material_meta, output.get("materialGuid"), "material")):
        if not meta.is_file() or f"guid: {guid}" not in meta.read_text("utf-8"):
            raise ValueError(f"candidate {label} GUID metadata missing or differs from manifest")
    if output.get("shaderGuid") not in material.read_text("utf-8"):
        raise ValueError("candidate material does not reference its generated shader GUID")
    out = Path(out).expanduser().absolute()
    if out.exists():
        raise FileExistsError(f"probe output already exists: {out}")
    project = out / "ShaderProbe"
    (project / "Assets" / "Editor").mkdir(parents=True)
    (project / "Packages").mkdir()
    (project / "ProjectSettings").mkdir()
    for source in (shader, shader_meta, material, material_meta):
        target = project / "Assets" / source.relative_to(candidate / "Assets")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    probe_source = (Path(__file__).parent / "targets" / "UnityShaderProbe.cs").read_text("utf-8")
    probe_source = probe_source.replace("__MONKEY_SHADER_ASSET_PATH__", _csharp_literal_content(expected_paths["shader"]))
    probe_source = probe_source.replace("__MONKEY_MATERIAL_ASSET_PATH__", _csharp_literal_content(expected_paths["material"]))
    (project / "Assets" / "Editor" / "UnityShaderProbe.cs").write_text(probe_source, "utf-8")
    (project / "Packages" / "manifest.json").write_text('{"dependencies":{}}\n', "utf-8")
    (project / "ProjectSettings" / "ProjectVersion.txt").write_text("m_EditorVersion: 6000.6.2f1\n", "utf-8")
    plan = {"schemaVersion": 1, "status": "prepared-not-run", "sourceId": source_id,
            "candidateShaderSha256": expected_shader, "editor": "Unity 6000.6.2f1",
            "executionBudgetSeconds": 1200, "externalWindowLimitMinutes": 30,
            "method": "MonkeyShaderProbe.Run", "probeProject": str(project),
            "checks": ["ShaderUtil shader compilation", "deterministic shader/material GUID readback", "material save/reimport shader-reference readback", "controlled RenderTexture render", "GPU pixel readback compared with CPU texture*vertexColor + source blend oracle"],
            "limitations": _LIMITATIONS}
    (out / "probe-plan.json").write_bytes(_canonical(plan) + b"\n")
    return plan
