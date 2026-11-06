"""Static, source-driven plans for uGUI Slider-owned fill layout fields.

This module creates expectations only. It never edits Prefabs, calls Unity, runs
recovered source methods, or treats a native readback as already verified.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import struct
from pathlib import Path
from typing import Any, Mapping, Sequence

from .unity_prefab_types import parse_declarations

CONTRACT = "monkey-unity-prefab-slider-layout-plan/1"
MAX_GRAPH_OBJECTS = 50_000
MAX_SDK_BYTES = 4 * 1024 * 1024
MAX_SOURCE_CARRIER_BYTES = 4 * 1024 * 1024
_SHA = re.compile(r"^[0-9a-f]{64}$")
_GUID = re.compile(r"^[0-9a-f]{32}$")


class SliderLayoutError(ValueError):
    """Missing, ambiguous, unsupported, or drifting layout evidence."""


def _need(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise SliderLayoutError(f"{code}: {message}")


def _sid(value: Any) -> str:
    return str(value)


def _ptr(data: Any, label: str, *, optional: bool = False) -> str | None:
    _need(isinstance(data, Mapping), "SLIDER_LAYOUT_POINTER", f"{label} is not a PPtr")
    file_id, path_id = data.get("fileId"), data.get("pathId")
    if optional and str(file_id) == "0" and str(path_id) == "0":
        return None
    _need(str(file_id) == "0" and str(path_id) != "0", "SLIDER_LAYOUT_POINTER",
          f"{label} must resolve within the exact serialized file")
    return str(path_id)


def _f32(value: float) -> float:
    try:
        return struct.unpack("<f", struct.pack("<f", float(value)))[0]
    except (OverflowError, struct.error) as exc:
        raise SliderLayoutError("SLIDER_LAYOUT_NUMBER: value is outside float32") from exc


def _normalised(value: float, minimum: float, maximum: float) -> float:
    value, minimum, maximum = _f32(value), _f32(minimum), _f32(maximum)
    span = _f32(maximum - minimum)
    scale = max(abs(minimum), abs(maximum), 1.0)
    _need(math.isfinite(span) and span > 1e-6 * scale, "SLIDER_LAYOUT_RANGE",
          "min/max span is zero, reversed, or too close for the supported normalized-value profile")
    _need(minimum <= value <= maximum, "SLIDER_LAYOUT_RANGE",
          "stored value is outside min/max; this profile does not assume a clamp transition")
    numerator = _f32(value - minimum)
    ratio = _f32(numerator / span)
    return _f32(min(max(ratio, 0.0), 1.0))


def _read_pinned(root: Path, rel: str, expected: str, limit: int) -> bytes:
    _need(isinstance(rel, str) and rel and not Path(rel).is_absolute() and ".." not in Path(rel).parts,
          "SLIDER_LAYOUT_SDK_PATH", f"unsafe pinned path {rel!r}")
    _need(isinstance(expected, str) and _SHA.fullmatch(expected) is not None,
          "SLIDER_LAYOUT_SDK_PIN", f"invalid SHA256 pin for {rel}")
    path = (root / rel).resolve()
    try:
        path.relative_to(root.resolve())
        if path.stat().st_size > limit:
            raise SliderLayoutError(f"SLIDER_LAYOUT_BUDGET: {rel} exceeds byte budget")
        raw = path.read_bytes()
    except (OSError, ValueError) as exc:
        if isinstance(exc, SliderLayoutError):
            raise
        raise SliderLayoutError(f"SLIDER_LAYOUT_SDK_FILE: cannot read {rel}") from exc
    actual = hashlib.sha256(raw).hexdigest()
    _need(len(raw) <= limit and actual == expected, "SLIDER_LAYOUT_SDK_DRIFT", f"pinned file changed: {rel}")
    return raw


def _meta_guid(raw: bytes, path: str) -> str:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SliderLayoutError(f"SLIDER_LAYOUT_SDK_META: {path} is not UTF-8") from exc
    rows = re.findall(r"(?m)^guid:\s*([0-9a-fA-F]{32})\s*$", text)
    _need(len(rows) == 1, "SLIDER_LAYOUT_SDK_META", f"{path} must have exactly one GUID")
    return rows[0].lower()


def _brace_body(text: str, signature: str) -> str:
    starts = [m.start() for m in re.finditer(re.escape(signature), text)]
    _need(len(starts) == 1, "SLIDER_LAYOUT_SDK_CODE", f"expected one {signature!r} declaration")
    opening = text.find("{", starts[0] + len(signature))
    _need(opening >= 0, "SLIDER_LAYOUT_SDK_CODE", f"missing body for {signature}")
    depth, i, state = 0, opening, "code"
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if state == "line":
            if ch == "\n":
                state = "code"
        elif state == "block":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 1
        elif state in ("string", "char"):
            if ch == "\\":
                i += 1
            elif (state == "string" and ch == '"') or (state == "char" and ch == "'"):
                state = "code"
        else:
            if ch == "/" and nxt == "/":
                state = "line"
                i += 1
            elif ch == "/" and nxt == "*":
                state = "block"
                i += 1
            elif ch == '"':
                state = "string"
            elif ch == "'":
                state = "char"
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[opening + 1:i]
        i += 1
    raise SliderLayoutError(f"SLIDER_LAYOUT_SDK_CODE: unterminated body for {signature}")


def _line_numbers(text: str, token: str) -> list[int]:
    return [index for index, line in enumerate(text.splitlines(), 1) if token in line]


def _verify_slider_sdk(binding_plan: Mapping[str, Any], sdk_root: str | Path | None) -> dict[str, Any]:
    bindings = [b for b in binding_plan.get("bindings", [])
                if b.get("identity") == dict(assembly="UnityEngine.UI.dll", namespace="UnityEngine.UI", **{"class": "Slider"})]
    _need(len(bindings) == 1, "SLIDER_LAYOUT_SDK_BINDING", "exact UnityEngine.UI.dll/UnityEngine.UI.Slider binding required")
    binding = bindings[0]
    _need(binding.get("status") == "planned_sdk_binding" and binding.get("verification") ==
          "expected tuple only; native AssetDatabase GUID/GetClass not run", "SLIDER_LAYOUT_SDK_BINDING",
          "planned exact SDK tuple, not an assumed native GetClass result, required")
    target = binding.get("targetSource", {})
    tuple_ = binding.get("expectedTuple", {})
    _need(target.get("path") == "Runtime/UGUI/UI/Core/Slider.cs"
          and target.get("assemblyDefinition") == "Runtime/UGUI/UnityEngine.UI.asmdef"
          and target.get("assemblyDefinitionName") == "UnityEngine.UI"
          and tuple_.get("guid") == target.get("guid") and _GUID.fullmatch(str(tuple_.get("guid", "")))
          and tuple_.get("fileID") == 11500000 and tuple_.get("type") == 3,
          "SLIDER_LAYOUT_SDK_BINDING", "target SDK source identity/expected MonoScript tuple is inconsistent")
    root = Path(sdk_root or binding_plan.get("sdkRoot", "")).resolve()
    _need(root.is_dir(), "SLIDER_LAYOUT_SDK_ROOT", "pinned SDK package root is unavailable")
    package_raw = (root / "package.json").read_bytes()
    _need(len(package_raw) <= 256 * 1024, "SLIDER_LAYOUT_BUDGET", "package.json exceeds budget")
    try:
        package = json.loads(package_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SliderLayoutError("SLIDER_LAYOUT_PACKAGE: invalid package.json") from exc
    _need(package.get("name") == "com.unity.ugui" and package.get("version") == "2.6.0",
          "SLIDER_LAYOUT_PACKAGE", "target package must be the pinned uGUI 2.6.0 source")
    asmdef_raw = _read_pinned(root, target["assemblyDefinition"], hashlib.sha256(
        (root / target["assemblyDefinition"]).read_bytes()).hexdigest(), MAX_SDK_BYTES)
    try:
        asmdef = json.loads(asmdef_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SliderLayoutError("SLIDER_LAYOUT_ASMDEF: invalid UnityEngine.UI asmdef") from exc
    _need(asmdef.get("name") == "UnityEngine.UI", "SLIDER_LAYOUT_ASMDEF", "Slider source is not in UnityEngine.UI assembly")
    slider_path = target["path"]
    slider_raw = _read_pinned(root, slider_path, target["sourceSha256"], MAX_SDK_BYTES)
    slider_meta_path = slider_path + ".meta"
    slider_meta_raw = _read_pinned(root, slider_meta_path, target["metaSha256"], 1024 * 1024)
    _need(_meta_guid(slider_meta_raw, slider_meta_path) == tuple_["guid"], "SLIDER_LAYOUT_SDK_GUID",
          "Slider.cs.meta GUID differs from exact planned source tuple")
    image_path = "Runtime/UGUI/UI/Core/Image.cs"
    image_raw = (root / image_path).read_bytes()
    _need(len(image_raw) <= MAX_SDK_BYTES, "SLIDER_LAYOUT_BUDGET", "Image.cs exceeds byte budget")
    image_sha = hashlib.sha256(image_raw).hexdigest()
    image_meta_path = image_path + ".meta"
    image_meta = (root / image_meta_path).read_bytes()
    _need(len(image_meta) <= 1024 * 1024, "SLIDER_LAYOUT_BUDGET", "Image.cs.meta exceeds byte budget")
    image_guid = _meta_guid(image_meta, image_meta_path)
    try:
        slider_text, image_text = slider_raw.decode("utf-8"), image_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SliderLayoutError("SLIDER_LAYOUT_SDK_CODE: uGUI source is not UTF-8") from exc
    _need(re.search(r"(?m)^\s*namespace\s+UnityEngine\.UI\s*\{", slider_text) is not None
          and len(re.findall(r"(?m)^\s*public\s+class\s+Slider\s*:\s*Selectable\b", slider_text)) == 1,
          "SLIDER_LAYOUT_SDK_TYPE", "pinned Slider.cs does not declare one UnityEngine.UI.Slider : Selectable")
    image_class = re.findall(r"(?m)^\s*public\s+class\s+Image\s*:\s*([A-Za-z_][A-Za-z0-9_.]*)\b", image_text)
    _need(re.search(r"(?m)^\s*namespace\s+UnityEngine\.UI\s*\{", image_text) is not None
          and image_class == ["MaskableGraphic"], "SLIDER_LAYOUT_SDK_TYPE", "pinned Image.cs type identity/base differs")
    enum_body = _brace_body(image_text, "public enum Type")
    enum_body = re.sub(r"/\*.*?\*/|//[^\n]*", "", enum_body, flags=re.S)
    enum_names = []
    for item in enum_body.split(","):
        item = item.strip()
        if not item:
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)(?:\s*=\s*([0-9]+))?", item)
        _need(match is not None, "SLIDER_LAYOUT_SDK_IMAGE_ENUM", "Image.Type contains unsupported enum syntax")
        enum_names.append((match.group(1), int(match.group(2)) if match.group(2) is not None else None))
    enum_values = {name: (explicit if explicit is not None else index) for index, (name, explicit) in enumerate(enum_names)}
    enums = {name: enum_values[name] for name in ("Simple", "Sliced", "Tiled", "Filled") if name in enum_values}
    _need(enums == {"Simple": 0, "Sliced": 1, "Tiled": 2, "Filled": 3},
          "SLIDER_LAYOUT_SDK_IMAGE_ENUM", "Image.Type numeric values differ from the supported source profile")
    update_body = _brace_body(slider_text, "private void UpdateVisuals()")
    required_update = [
        "if (m_FillContainerRect != null)",
        "m_Tracker.Add(this, m_FillRect, DrivenTransformProperties.Anchors);",
        "Vector2 anchorMin = Vector2.zero;",
        "Vector2 anchorMax = Vector2.one;",
        "if (m_FillImage != null && m_FillImage.type == Image.Type.Filled)",
        "m_FillImage.fillAmount = normalizedValue;",
        "if (reverseValue)",
        "anchorMin[(int)axis] = 1 - normalizedValue;",
        "anchorMax[(int)axis] = normalizedValue;",
        "m_FillRect.anchorMin = anchorMin;",
        "m_FillRect.anchorMax = anchorMax;",
    ]
    _need(all(fragment in update_body for fragment in required_update), "SLIDER_LAYOUT_SDK_CODE",
          "pinned Slider.UpdateVisuals does not prove the supported fill/anchor branches")
    normalized_start = slider_text.find("public float normalizedValue")
    normalized_end = slider_text.find("[Space]", normalized_start)
    _need(normalized_start >= 0 and normalized_end > normalized_start, "SLIDER_LAYOUT_SDK_CODE",
          "normalizedValue property source region missing")
    normalized_body = slider_text[normalized_start:normalized_end]
    _need("Mathf.Approximately(minValue, maxValue)" in normalized_body
          and "return 0;" in normalized_body
          and "Mathf.InverseLerp(minValue, maxValue, value)" in normalized_body,
          "SLIDER_LAYOUT_SDK_CODE", "normalizedValue range semantics are unsupported")
    on_enable = _brace_body(slider_text, "protected override void OnEnable()")
    _need(all(fragment in on_enable for fragment in ("UpdateCachedReferences();", "Set(m_Value, false);", "UpdateVisuals();")),
          "SLIDER_LAYOUT_SDK_CODE", "OnEnable does not prove the serialized value drives layout")
    # axis/reverseValue are expression-bodied properties, so verify their pinned source exactly.
    _need("Axis axis { get { return (m_Direction == Direction.LeftToRight || m_Direction == Direction.RightToLeft) ? Axis.Horizontal : Axis.Vertical; } }" in slider_text
          and "bool reverseValue { get { return m_Direction == Direction.RightToLeft || m_Direction == Direction.TopToBottom; } }" in slider_text,
          "SLIDER_LAYOUT_SDK_CODE", "direction-to-axis source mapping differs from the supported profile")
    code_lines = dict(sliderClass=_line_numbers(slider_text, "public class Slider : Selectable"),
        normalizedValue=_line_numbers(slider_text, "public float normalizedValue"),
        normalizedRangeGuard=_line_numbers(slider_text, "Mathf.Approximately(minValue, maxValue)"),
        normalizedInverseLerp=_line_numbers(slider_text, "Mathf.InverseLerp(minValue, maxValue, value)"),
        onEnable=_line_numbers(slider_text, "protected override void OnEnable()"),
        updateVisuals=_line_numbers(slider_text, "private void UpdateVisuals()"),
        fillTypeBranch=_line_numbers(slider_text, "m_FillImage.type == Image.Type.Filled"),
        fillAmountWrite=_line_numbers(slider_text, "m_FillImage.fillAmount = normalizedValue;"),
        fillAnchorMaxWrite=_line_numbers(slider_text, "m_FillRect.anchorMax = anchorMax;"),
        imageTypeEnum=_line_numbers(image_text, "public enum Type"))
    return dict(packageVersion=package["version"], packageName=package["name"], sdkRoot=str(root),
        sliderIdentity=dict(assembly="UnityEngine.UI.dll", namespace="UnityEngine.UI", **{"class": "Slider"}),
        sliderSource=dict(path=slider_path, sha256=target["sourceSha256"], metaSha256=target["metaSha256"], guid=tuple_["guid"],
                          assemblyDefinition=target["assemblyDefinition"], assemblyDefinitionName=asmdef["name"]),
        imageSource=dict(path=image_path, sha256=image_sha, metaPath=image_meta_path, metaSha256=hashlib.sha256(image_meta).hexdigest(),
                         guid=image_guid, classBase=image_class[0], typeEnum=dict(sorted(enums.items()))),
        proofs=dict(updateVisuals="m_FillImage Filled -> fillAmount=normalizedValue; otherwise exact fill anchors derived from direction/value",
                    normalizedValue="Approximately equal range -> 0; otherwise Mathf.InverseLerp(min,max,value)",
                    enable="OnEnable refreshes cached references, applies value without callback, then calls UpdateVisuals",
                    direction="pinned Slider.axis/reverseValue source expressions"),
        codeLines=code_lines,
        nativeGetClass="not_run; expected SDK tuple only")


def _source_identity(script: Mapping[str, Any]) -> dict[str, str]:
    data = script.get("data", {})
    return dict(assembly=str(data.get("m_AssemblyName", "")), namespace=str(data.get("m_Namespace", "")),
                **{"class": str(data.get("m_ClassName", ""))})


def _candidate_objects(graph: Mapping[str, Any]) -> tuple[dict[str, Mapping[str, Any]], dict[tuple[str, str, str], Mapping[str, Any]]]:
    objects = graph.get("reachableObjects")
    _need(isinstance(objects, list) and len(objects) <= MAX_GRAPH_OBJECTS, "SLIDER_LAYOUT_GRAPH", "bounded reachableObjects list required")
    by_id: dict[str, Mapping[str, Any]] = {}
    by_identity: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for obj in objects:
        if not isinstance(obj, Mapping) or not isinstance(obj.get("sourceObjectId"), str):
            raise SliderLayoutError("SLIDER_LAYOUT_GRAPH: malformed source object row")
        sid = obj["sourceObjectId"]
        _need(sid not in by_id, "SLIDER_LAYOUT_GRAPH", f"duplicate sourceObjectId {sid}")
        by_id[sid] = obj
        ident = obj.get("identity", {})
        if isinstance(ident, Mapping) and all(k in ident for k in ("containerSha256", "serializedFile", "pathId")):
            key = (str(ident["containerSha256"]), str(ident["serializedFile"]), str(ident["pathId"]))
            _need(key not in by_identity, "SLIDER_LAYOUT_GRAPH", f"duplicate full source identity {key}")
            by_identity[key] = obj
    return by_id, by_identity


def _active_gameobject(graph: Mapping[str, Any], source_object_id: str, by_id: Mapping[str, Mapping[str, Any]]) -> tuple[bool, list[str]]:
    rows = [row for row in graph.get("gameObjects", []) if row.get("sourceObjectId") == source_object_id]
    _need(len(rows) == 1, "SLIDER_LAYOUT_GAMEOBJECT", f"expected one gameObjects row for {source_object_id}")
    chain, current, seen, active = [], rows[0], set(), True
    while current is not None:
        sid = current.get("sourceObjectId")
        _need(isinstance(sid, str) and sid not in seen, "SLIDER_LAYOUT_GAMEOBJECT", "broken or cyclic source hierarchy")
        seen.add(sid)
        chain.append(sid)
        _need(type(current.get("active")) is bool, "SLIDER_LAYOUT_GAMEOBJECT", f"active flag missing for {sid}")
        active = active and current["active"]
        parent = current.get("parentSourceObjectId")
        if parent is None:
            current = None
        else:
            parents = [row for row in graph.get("gameObjects", []) if row.get("sourceObjectId") == parent]
            _need(len(parents) == 1, "SLIDER_LAYOUT_GAMEOBJECT", f"parent GameObject missing: {parent}")
            current = parents[0]
        _need(len(seen) <= len(graph.get("gameObjects", [])), "SLIDER_LAYOUT_GAMEOBJECT", "hierarchy exceeds graph budget")
    return active, chain


def _go_for_component(component: Mapping[str, Any], by_identity: Mapping[tuple[str, str, str], Mapping[str, Any]]) -> Mapping[str, Any]:
    ptr = component.get("data", {}).get("m_GameObject")
    go_path = _ptr(ptr, "m_GameObject")
    ident = component["identity"]
    go = by_identity.get((str(ident["containerSha256"]), str(ident["serializedFile"]), str(go_path)))
    _need(go is not None and go.get("type") == "GameObject", "SLIDER_LAYOUT_GAMEOBJECT", "component GameObject is unresolved or ambiguous")
    return go


def _component_script(component: Mapping[str, Any], by_identity: Mapping[tuple[str, str, str], Mapping[str, Any]]) -> Mapping[str, Any]:
    ptr = _ptr(component.get("data", {}).get("m_Script"), "m_Script")
    ident = component["identity"]
    script = by_identity.get((str(ident["containerSha256"]), str(ident["serializedFile"]), str(ptr)))
    _need(script is not None and script.get("type") == "MonoScript", "SLIDER_LAYOUT_SCRIPT", "exact MonoScript identity is unresolved")
    return script


def _source_class_base(*, script: Mapping[str, Any], source_class_pins: Mapping[str, Mapping[str, Any]] | None,
                       source_candidate_root: str | Path | None,
                       source_candidate_manifest: Mapping[str, Any] | None) -> dict[str, Any]:
    identity = _source_identity(script)
    _need(all(identity.values()), "SLIDER_LAYOUT_SOURCE_TYPE", "source component MonoScript lacks full assembly/namespace/class identity")
    if identity == dict(assembly="UnityEngine.UI.dll", namespace="UnityEngine.UI", **{"class": "Image"}):
        return dict(sourceIdentity=identity, base="UnityEngine.UI.MaskableGraphic", evidence="exact source native Image identity")
    sid = script["sourceObjectId"]
    pin = (source_class_pins or {}).get(sid)
    _need(pin is not None and source_candidate_root is not None and source_candidate_manifest is not None,
          "SLIDER_LAYOUT_SOURCE_TYPE", f"{identity} is not native Image and has no pinned source class declaration")
    rel, expected = pin.get("path"), pin.get("sha256")
    _need(isinstance(rel, str) and rel.startswith("Assets/") and isinstance(expected, str) and _SHA.fullmatch(expected),
          "SLIDER_LAYOUT_SOURCE_TYPE", "source class pin must identify an exact candidate Assets file and SHA256")
    rows = [r for r in source_candidate_manifest.get("files", []) if r.get("path") == rel]
    _need(len(rows) == 1 and rows[0].get("sha256") == expected, "SLIDER_LAYOUT_SOURCE_TYPE",
          "candidate manifest does not own exact source class bytes")
    root = Path(source_candidate_root).resolve()
    path = (root / rel).resolve()
    try:
        path.relative_to(root)
        if path.stat().st_size > MAX_SOURCE_CARRIER_BYTES:
            raise SliderLayoutError("SLIDER_LAYOUT_BUDGET: source class carrier exceeds byte budget")
        raw = path.read_bytes()
    except (OSError, ValueError) as exc:
        if isinstance(exc, SliderLayoutError):
            raise
        raise SliderLayoutError("SLIDER_LAYOUT_SOURCE_TYPE: cannot read pinned source type carrier") from exc
    _need(hashlib.sha256(raw).hexdigest() == expected, "SLIDER_LAYOUT_SOURCE_TYPE", "source type carrier hash changed")
    try:
        parsed = parse_declarations(raw.decode("utf-8"), assembly=identity["assembly"], source_path=rel, source_sha256=expected)
    except (UnicodeDecodeError, ValueError) as exc:
        raise SliderLayoutError(f"SLIDER_LAYOUT_SOURCE_TYPE: cannot parse declaration: {exc}") from exc
    rows = [d for d in parsed["declarations"] if d.get("kind") == "class" and d.get("identity", {}).get("namespace") == identity["namespace"]
            and d.get("identity", {}).get("name") == identity["class"]]
    _need(len(rows) == 1 and isinstance(rows[0].get("base"), str) and rows[0]["base"], "SLIDER_LAYOUT_SOURCE_TYPE",
          "source class carrier does not provide one exact base type")
    return dict(sourceIdentity=identity, base=rows[0]["base"], imports=rows[0].get("imports", []),
                carrierPath=rel, carrierSha256=expected,
                evidence="candidate-manifest-pinned schema carrier declaration; source methods remain unavailable")


_KNOWN_UGUI_TYPES = {
    ("UnityEngine.UI", "MaskableGraphic"): "Runtime/UGUI/UI/Core/MaskableGraphic.cs",
    ("UnityEngine.UI", "Graphic"): "Runtime/UGUI/UI/Core/Graphic.cs",
    ("UnityEngine.UI", "BaseMeshEffect"): "Runtime/UGUI/UI/Core/VertexModifiers/BaseMeshEffect.cs",
    ("UnityEngine.EventSystems", "UIBehaviour"): "Runtime/UGUI/EventSystem/UIBehaviour.cs",
    ("UnityEngine.UI", "Selectable"): "Runtime/UGUI/UI/Core/Selectable.cs",
}


def _base_identity(raw_base: str, namespace: str, imports: Sequence[str]) -> tuple[str, str]:
    if "." in raw_base:
        full = raw_base
    elif raw_base == "UIBehaviour" and "UnityEngine.EventSystems" in imports:
        full = "UnityEngine.EventSystems.UIBehaviour"
    elif raw_base == "MonoBehaviour" and "UnityEngine" in imports:
        full = "UnityEngine.MonoBehaviour"
    else:
        full = namespace + "." + raw_base
    if full.startswith("UnityEngine.EventSystems."):
        return "UnityEngine.EventSystems", full.rsplit(".", 1)[1]
    if full.startswith("UnityEngine.UI."):
        return "UnityEngine.UI", full.rsplit(".", 1)[1]
    if full.startswith("UnityEngine."):
        return "UnityEngine", full.rsplit(".", 1)[1]
    parts = full.rsplit(".", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (namespace, full)


def _sdk_decl_base(*, identity: tuple[str, str], bindings: Mapping[str, Any], sdk_root: Path) -> tuple[str, dict[str, Any]]:
    namespace, name = identity
    rows = [row for row in bindings.get("bindings", []) if row.get("identity", {}).get("namespace") == namespace
            and row.get("identity", {}).get("class") == name and row.get("status") == "planned_sdk_binding"]
    if rows:
        _need(len(rows) == 1, "SLIDER_LAYOUT_SDK_TYPE", f"ambiguous SDK binding for {namespace}.{name}")
        row = rows[0]
        source = row.get("targetSource", {})
        path, digest = source.get("path"), source.get("sourceSha256")
        raw = _read_pinned(sdk_root, path, digest, MAX_SDK_BYTES)
        meta_path = path + ".meta"
        meta = _read_pinned(sdk_root, meta_path, source.get("metaSha256"), 1024 * 1024)
        _need(_meta_guid(meta, meta_path) == source.get("guid"), "SLIDER_LAYOUT_SDK_TYPE",
              f"SDK type meta GUID differs for {namespace}.{name}")
        assembly = source.get("assemblyDefinitionName")
        evidence = dict(identity=dict(assembly=row["identity"]["assembly"], namespace=namespace, **{"class": name}),
                        path=path, sha256=digest, metaSha256=source["metaSha256"], guid=source["guid"],
                        bindingStatus=row["status"])
    else:
        path = _KNOWN_UGUI_TYPES.get(identity)
        _need(path is not None, "SLIDER_LAYOUT_SDK_TYPE", f"no exact pinned SDK declaration for {namespace}.{name}")
        raw = (sdk_root / path).read_bytes()
        _need(len(raw) <= MAX_SDK_BYTES, "SLIDER_LAYOUT_BUDGET", f"SDK declaration exceeds budget: {path}")
        digest = hashlib.sha256(raw).hexdigest()
        assembly = "UnityEngine.UI" if namespace == "UnityEngine.UI" else "UnityEngine.UI"
        evidence = dict(identity=dict(assembly=assembly + ".dll", namespace=namespace, **{"class": name}),
                        path=path, sha256=digest, bindingStatus="fixed-package-declaration-path")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SliderLayoutError(f"SLIDER_LAYOUT_SDK_TYPE: {path} is not UTF-8") from exc
    _need(re.search(r"(?m)^\s*namespace\s+" + re.escape(namespace) + r"\s*\{", text) is not None,
          "SLIDER_LAYOUT_SDK_TYPE", f"{path} is not in exact namespace {namespace}")
    class_matches = re.findall(r"(?m)^\s*(?:public|internal|protected|private)?\s*(?:(?:abstract|sealed|partial)\s+)*class\s+"
                               + re.escape(name) + r"\s*:\s*([^\s,{]+)", text)
    _need(len(class_matches) == 1, "SLIDER_LAYOUT_SDK_TYPE", f"{path} must declare one exact {namespace}.{name} class with a simple base")
    base = class_matches[0]
    imports = re.findall(r"(?m)^\s*using\s+([A-Za-z_][\w.]*)\s*;", text)
    base_ns, base_name = _base_identity(base, namespace, imports)
    evidence["base"] = dict(namespace=base_ns, name=base_name)
    return base, evidence


def _classify_non_or_image_base(*, start: tuple[str, str], bindings: Mapping[str, Any], sdk_root: Path,
                                source_chain: list[dict[str, Any]] | None = None) -> tuple[str, list[dict[str, Any]]]:
    """Resolve exact single-inheritance bases until Image or a shared non-Image root."""
    chain = list(source_chain or [])
    current = start
    seen = set()
    while True:
        _need(current not in seen, "SLIDER_LAYOUT_TYPE_CHAIN", f"inheritance cycle while resolving {current}")
        seen.add(current)
        if current == ("UnityEngine.UI", "Image"):
            return "image", chain
        if current == ("UnityEngine", "MonoBehaviour"):
            chain.append(dict(identity={"namespace": current[0], "class": current[1]},
                              evidence="Unity root component class; separate branch from UnityEngine.UI.Image"))
            return "non_image", chain
        base, evidence = _sdk_decl_base(identity=current, bindings=bindings, sdk_root=sdk_root)
        chain.append(evidence)
        namespace, name = evidence["base"]["namespace"], evidence["base"]["name"]
        current = (namespace, name)
        _need(len(chain) <= 16, "SLIDER_LAYOUT_TYPE_CHAIN", "SDK base chain exceeds budget")


def _classify_fill_component(*, script: Mapping[str, Any], source_class_pins: Mapping[str, Mapping[str, Any]] | None,
                             source_candidate_root: str | Path | None,
                             source_candidate_manifest: Mapping[str, Any] | None,
                             sdk_bindings: Mapping[str, Any], sdk_root: Path) -> dict[str, Any]:
    identity = _source_identity(script)
    if identity == dict(assembly="UnityEngine.UI.dll", namespace="UnityEngine.UI", **{"class": "Image"}):
        return dict(classification="image", identity=identity, baseChain=[{"identity": identity, "evidence": "exact source Image identity"}])
    pin = (source_class_pins or {}).get(script["sourceObjectId"])
    if pin is not None:
        source = _source_class_base(script=script, source_class_pins=source_class_pins,
            source_candidate_root=source_candidate_root, source_candidate_manifest=source_candidate_manifest)
        base = _base_identity(source["base"], identity["namespace"], source.get("imports", []))
        classification, chain = _classify_non_or_image_base(start=base, bindings=sdk_bindings, sdk_root=sdk_root)
        return dict(classification=classification, identity=identity, declaration=source, baseChain=chain)
    # Native SDK scripts such as Outline/Shadow are excluded by their exact SDK
    # binding and pinned class declaration/base chain, never by short name.
    native_rows = [b for b in sdk_bindings.get("bindings", []) if b.get("identity") == identity
                   and script["sourceObjectId"] in b.get("sourceObjectIds", [])]
    _need(len(native_rows) == 1, "SLIDER_LAYOUT_SOURCE_TYPE",
          f"fill component {identity} has no unique source class carrier or exact SDK binding")
    base, evidence = _sdk_decl_base(identity=(identity["namespace"], identity["class"]), bindings=sdk_bindings, sdk_root=sdk_root)
    base_identity = _base_identity(base, identity["namespace"], [])
    start_evidence = dict(evidence, sourceComponentIdentity=identity)
    classification, chain = _classify_non_or_image_base(start=base_identity, bindings=sdk_bindings, sdk_root=sdk_root,
        source_chain=[start_evidence])
    return dict(classification=classification, identity=identity, baseChain=chain)


def _check_pointer_edge(graph: Mapping[str, Any], source_id: str, location: str, target_id: str) -> None:
    rows = [e for e in graph.get("referenceEdges", []) if e.get("sourceObjectId") == source_id and e.get("location") == location]
    _need(len(rows) == 1 and rows[0].get("status") == "resolved" and rows[0].get("targetSourceObjectId") == target_id,
          "SLIDER_LAYOUT_EDGE", f"{location} must resolve exactly to {target_id}")


def _attached_components(graph: Mapping[str, Any], gameobject: Mapping[str, Any],
                         by_identity: Mapping[tuple[str, str, str], Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    rows = gameobject.get("data", {}).get("m_Component")
    _need(isinstance(rows, list) and len(rows) <= 256, "SLIDER_LAYOUT_COMPONENTS",
          f"{gameobject['sourceObjectId']} needs a bounded complete m_Component list")
    result = []
    identity = gameobject["identity"]
    for index, row in enumerate(rows):
        _need(isinstance(row, Mapping), "SLIDER_LAYOUT_COMPONENTS", "malformed GameObject component row")
        path_id = _ptr(row.get("component"), f"m_Component[{index}].component")
        target = by_identity.get((str(identity["containerSha256"]), str(identity["serializedFile"]), str(path_id)))
        _need(target is not None, "SLIDER_LAYOUT_COMPONENTS", f"component {path_id} is unresolved")
        _check_pointer_edge(graph, gameobject["sourceObjectId"], f"$/m_Component/{index}/component", target["sourceObjectId"])
        result.append(target)
    _need(len({r["sourceObjectId"] for r in result}) == len(result), "SLIDER_LAYOUT_COMPONENTS",
          "GameObject component list contains duplicate identities")
    return result


def _f32_mapping(value: Any, label: str) -> float:
    _need(type(value) in (int, float) and math.isfinite(float(value)), "SLIDER_LAYOUT_NUMBER", f"{label} must be finite")
    return _f32(float(value))


def planned_slider_overrides(
    source_graph: Mapping[str, Any],
    *,
    sdk_bindings: Mapping[str, Any] | None = None,
    sdk_root: str | Path | None = None,
    source_candidate_root: str | Path | None = None,
    source_candidate_manifest: Mapping[str, Any] | None = None,
    source_class_pins: Mapping[str, Mapping[str, Any]] | None = None,
    source_slider_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Plan only source-proven active/enabled Slider fill overrides.

    ``sdk_bindings`` is the existing exact source-MonoScript to SDK mapping
    produced by :mod:`unity_prefab_sdk`. ``source_class_pins`` is needed only
    when the fill Image is a source subclass; each entry pins its MonoScript
    sourceObjectId to a candidate-manifest-owned C# schema carrier. Set
    ``source_slider_ids`` to plan a bounded exact instance subset; omitted means
    all exact Slider instances in the supplied source graph are selected.
    """
    _need(source_graph.get("contract") == "monkey-unity-prefab-source-graph/1", "SLIDER_LAYOUT_GRAPH",
          "exact monkey source graph required")
    _need(source_graph.get("sourceUnityVersions") == ["2021.3.30f1"], "SLIDER_LAYOUT_GRAPH",
          "source Unity version is outside the supported profile")
    _need(sdk_bindings is not None, "SLIDER_LAYOUT_SDK_BINDING", "pinned exact SDK script binding evidence is required")
    sdk_proof = _verify_slider_sdk(sdk_bindings, sdk_root)
    objects, by_identity = _candidate_objects(source_graph)
    slider_scripts = [o for o in objects.values() if o.get("type") == "MonoScript"
                      and _source_identity(o) == dict(assembly="UnityEngine.UI.dll", namespace="UnityEngine.UI", **{"class": "Slider"})]
    _need(len(slider_scripts) == 1, "SLIDER_LAYOUT_SOURCE_SCRIPT", "expected one exact source UnityEngine.UI.Slider MonoScript")
    script = slider_scripts[0]
    binding_rows = [b for b in sdk_bindings.get("bindings", []) if b.get("identity") ==
                    dict(assembly="UnityEngine.UI.dll", namespace="UnityEngine.UI", **{"class": "Slider"})]
    _need(len(binding_rows) == 1 and script["sourceObjectId"] in binding_rows[0].get("sourceObjectIds", []),
          "SLIDER_LAYOUT_SDK_BINDING", "SDK binding does not include this exact source MonoScript identity")
    source_tuple = binding_rows[0].get("sourceTuple", {})
    _need(_GUID.fullmatch(str(source_tuple.get("guid", ""))) and source_tuple.get("fileID") == 11500000
          and source_tuple.get("type") == 3, "SLIDER_LAYOUT_SDK_BINDING", "source Slider tuple is incomplete")

    slider_components = [o for o in objects.values() if o.get("type") == "MonoBehaviour"
                         and o.get("data", {}).get("m_Script", {}).get("pathId") == script.get("identity", {}).get("pathId")
                         and o.get("identity", {}).get("containerSha256") == script.get("identity", {}).get("containerSha256")
                         and o.get("identity", {}).get("serializedFile") == script.get("identity", {}).get("serializedFile")]
    _need(len(slider_components) <= 256, "SLIDER_LAYOUT_BUDGET", "too many source Slider components")
    _need(slider_components, "SLIDER_LAYOUT_SOURCE_SLIDER", "no component instance references the exact Slider MonoScript")
    if source_slider_ids is not None:
        _need(isinstance(source_slider_ids, Sequence) and not isinstance(source_slider_ids, (str, bytes))
              and 1 <= len(source_slider_ids) <= 256 and len(set(source_slider_ids)) == len(source_slider_ids)
              and all(isinstance(s, str) for s in source_slider_ids), "SLIDER_LAYOUT_SELECTION",
              "source_slider_ids must be 1..256 unique exact source object IDs")
        selected = {o["sourceObjectId"]: o for o in slider_components}
        _need(all(s in selected for s in source_slider_ids), "SLIDER_LAYOUT_SELECTION",
              "selected source object is not an exact Slider instance bound to the proven MonoScript")
        planned_components = [selected[s] for s in source_slider_ids]
    else:
        planned_components = slider_components
    activity: dict[str, dict[str, Any]] = {}
    for component in slider_components:
        component_go = _go_for_component(component, by_identity)
        active, chain = _active_gameobject(source_graph, component_go["sourceObjectId"], objects)
        enabled_raw = component.get("data", {}).get("m_Enabled")
        _need(enabled_raw in (0, 1, False, True), "SLIDER_LAYOUT_ENABLED",
              f"{component['sourceObjectId']} has unsupported m_Enabled")
        activity[component["sourceObjectId"]] = dict(gameObject=component_go, active=active, enabled=bool(enabled_raw),
                                                       enabledStored=enabled_raw, chain=chain)
    drivers_by_fill: dict[str, list[Mapping[str, Any]]] = {}
    for component in slider_components:
        active_row = activity[component["sourceObjectId"]]
        if not (active_row["active"] and active_row["enabled"]):
            continue
        fill_path = _ptr(component.get("data", {}).get("m_FillRect"), "Slider.m_FillRect", optional=True)
        if fill_path is not None:
            drivers_by_fill.setdefault(fill_path, []).append(component)

    planned = []
    for component in planned_components:
        data, ident = component["data"], component["identity"]
        slider_id = component["sourceObjectId"]
        active_row = activity[slider_id]
        go, go_active, go_chain = active_row["gameObject"], active_row["active"], active_row["chain"]
        enabled, enabled_raw = active_row["enabled"], active_row["enabledStored"]
        source_tuple_key = (str(ident["containerSha256"]), str(ident["serializedFile"]), str(data["m_Script"]["pathId"]))
        _need(source_tuple_key == (str(script["identity"]["containerSha256"]), str(script["identity"]["serializedFile"]),
                                   str(script["identity"]["pathId"])), "SLIDER_LAYOUT_SOURCE_SCRIPT", "Slider script pointer crosses identity scope")
        if not (go_active and enabled):
            planned.append(dict(sourceSliderId=slider_id, sourceSliderIdentity=ident, sourceMonoScriptId=script["sourceObjectId"],
                sourceScriptIdentity=_source_identity(script), sourceTuple=dict(source_tuple), status="inactive_or_disabled_no_visual_update",
                sourceGameObjectId=go["sourceObjectId"], sourceGameObjectActive=go_active, componentEnabled=enabled,
                activeHierarchy=go_chain, sourceFields={k: data.get(k) for k in ("m_Value", "m_MinValue", "m_MaxValue", "m_Direction", "m_WholeNumbers")},
                fillRectPointer=data.get("m_FillRect"), handleRectPointer=data.get("m_HandleRect"), overrides=[]))
            continue
        fill_path = _ptr(data.get("m_FillRect"), "Slider.m_FillRect", optional=True)
        handle_path = _ptr(data.get("m_HandleRect"), "Slider.m_HandleRect", optional=True)
        if fill_path is None:
            _need(handle_path is None, "SLIDER_LAYOUT_HANDLE", f"{slider_id} handle-only profile is unsupported")
            planned.append(dict(sourceSliderId=slider_id, sourceSliderIdentity=ident, status="no-fill-no-handle",
                                overrides=[], sourceCodeExecuted=False))
            continue
        _need(handle_path is None, "SLIDER_LAYOUT_HANDLE", f"{slider_id} non-null handleRect is outside this fill-only profile")
        fill_key = (str(ident["containerSha256"]), str(ident["serializedFile"]), fill_path)
        fill_rect = by_identity.get(fill_key)
        _need(fill_rect is not None and fill_rect.get("type") == "RectTransform", "SLIDER_LAYOUT_FILL_RECT",
              f"{slider_id}.m_FillRect does not resolve to an exact RectTransform")
        _check_pointer_edge(source_graph, slider_id, "$/m_FillRect", fill_rect["sourceObjectId"])
        _need(len(drivers_by_fill.get(fill_path, [])) == 1, "SLIDER_LAYOUT_MULTIPLE_DRIVERS",
              f"multiple source Sliders drive fill RectTransform {fill_path}")
        fill_go = _go_for_component(fill_rect, by_identity)
        fill_go_active, fill_go_chain = _active_gameobject(source_graph, fill_go["sourceObjectId"], objects)
        fill_gameobject_components = _attached_components(source_graph, fill_go, by_identity)
        images = []
        source_image_proofs = []
        excluded_non_image_components = []
        for candidate in fill_gameobject_components:
            if candidate.get("type") != "MonoBehaviour":
                continue
            fill_script = _component_script(candidate, by_identity)
            fill_type = _classify_fill_component(script=fill_script, source_class_pins=source_class_pins,
                source_candidate_root=source_candidate_root, source_candidate_manifest=source_candidate_manifest,
                sdk_bindings=sdk_bindings, sdk_root=Path(sdk_proof["sdkRoot"]))
            if fill_type["classification"] == "image":
                images.append(candidate)
                source_image_proofs.append(fill_type)
            else:
                excluded_non_image_components.append(dict(sourceObjectId=candidate["sourceObjectId"], typeProof=fill_type))
        _need(len(images) <= 1, "SLIDER_LAYOUT_FILL_IMAGE", f"{slider_id} has multiple exact Image/Image-derived components")
        fill_image = images[0] if images else None
        image_data = fill_image["data"] if fill_image is not None else None
        image_enabled_raw = image_data.get("m_Enabled") if image_data is not None else None
        if image_data is not None:
            _need(image_enabled_raw in (0, 1, False, True), "SLIDER_LAYOUT_IMAGE_ENABLED", "fill Image m_Enabled is unsupported")
        image_enabled = bool(image_enabled_raw) if image_data is not None else None
        image_type = image_data.get("m_Type") if image_data is not None else None
        if image_type is not None:
            _need(type(image_type) is int and image_type in (0, 1, 2, 3), "SLIDER_LAYOUT_IMAGE_TYPE",
                  "fill Image type must match the pinned uGUI Image.Type enum")
        source_direction = data.get("m_Direction")
        _need(type(source_direction) is int and source_direction in (0, 1, 2, 3), "SLIDER_LAYOUT_DIRECTION",
              f"{slider_id} Direction value is outside the pinned four-value enum")
        whole = data.get("m_WholeNumbers")
        _need(whole in (0, 1, False, True), "SLIDER_LAYOUT_WHOLE", "m_WholeNumbers is not an exact bool storage value")
        _need(not bool(whole), "SLIDER_LAYOUT_WHOLE", f"{slider_id} WholeNumbers=true is outside the source profile")
        value = _f32_mapping(data.get("m_Value"), "m_Value")
        minimum = _f32_mapping(data.get("m_MinValue"), "m_MinValue")
        maximum = _f32_mapping(data.get("m_MaxValue"), "m_MaxValue")
        normalized = _normalised(value, minimum, maximum)

        # Layout components on the fill object or its parent are competing drivers.
        father_path = _ptr(fill_rect["data"].get("m_Father"), "fill RectTransform.m_Father", optional=True)
        _need(father_path is not None, "SLIDER_LAYOUT_FILL_PARENT", "fill RectTransform has no parent container")
        parent_rect = by_identity.get((str(ident["containerSha256"]), str(ident["serializedFile"]), father_path))
        _need(parent_rect is not None and parent_rect.get("type") == "RectTransform", "SLIDER_LAYOUT_FILL_PARENT",
              "fill container is not an exact parent RectTransform")
        parent_go = _go_for_component(parent_rect, by_identity)
        parent_go_active, parent_go_chain = _active_gameobject(source_graph, parent_go["sourceObjectId"], objects)
        _check_pointer_edge(source_graph, fill_rect["sourceObjectId"], "$/m_Father", parent_rect["sourceObjectId"])
        forbidden_layout = {("UnityEngine.UI.dll", "UnityEngine.UI", name) for name in (
            "HorizontalLayoutGroup", "VerticalLayoutGroup", "GridLayoutGroup", "ContentSizeFitter", "AspectRatioFitter")}
        competing = []
        for candidate in [*_attached_components(source_graph, fill_go, by_identity),
                          *_attached_components(source_graph, parent_go, by_identity)]:
            if candidate.get("type") != "MonoBehaviour":
                continue
            script_candidate = _component_script(candidate, by_identity)
            type_identity = _source_identity(script_candidate)
            type_key = (type_identity["assembly"], type_identity["namespace"], type_identity["class"])
            if type_key in forbidden_layout:
                bound = [b for b in sdk_bindings.get("bindings", []) if b.get("identity") == type_identity
                         and script_candidate["sourceObjectId"] in b.get("sourceObjectIds", [])]
                _need(len(bound) == 1 and bound[0].get("status") == "planned_sdk_binding",
                      "SLIDER_LAYOUT_MULTIPLE_DRIVERS", f"layout-type driver lacks exact SDK source binding: {type_identity}")
                competing.append(dict(componentSourceId=candidate["sourceObjectId"], identity=type_identity,
                                      sdkSource=bound[0].get("targetSource")))
        _need(not competing, "SLIDER_LAYOUT_MULTIPLE_DRIVERS", f"layout driver competes with Slider on fill/container: {competing}")

        direction = {0: "LeftToRight", 1: "RightToLeft", 2: "BottomToTop", 3: "TopToBottom"}[source_direction]
        anchor_min = {"x": 0.0, "y": 0.0}
        anchor_max = {"x": 1.0, "y": 1.0}
        axis = "x" if source_direction in (0, 1) else "y"
        reverse = source_direction in (1, 3)
        if image_type != 3:
            if reverse:
                anchor_min[axis] = _f32(1.0 - normalized)
            else:
                anchor_max[axis] = normalized
        stored_min, stored_max = fill_rect["data"].get("m_AnchorMin"), fill_rect["data"].get("m_AnchorMax")
        _need(isinstance(stored_min, Mapping) and isinstance(stored_max, Mapping), "SLIDER_LAYOUT_FILL_RECT",
              "source fill anchor vectors are missing")
        fill_type_name = {0: "Simple", 1: "Sliced", 2: "Tiled", 3: "Filled"}.get(image_type)
        fill_branch = "Image.fillAmount" if image_type == 3 else "anchors"
        driver_evidence = dict(component=slider_id, monoScript=script["sourceObjectId"], sdkType="UnityEngine.UI.Slider",
            sourceStored=dict(value=data["m_Value"], min=data["m_MinValue"], max=data["m_MaxValue"], direction=source_direction,
                              directionName=direction, wholeNumbers=bool(whole), enabled=enabled, interactable=data.get("m_Interactable")),
            normalizedValue=normalized, fillRect=fill_rect["sourceObjectId"],
            fillImage=fill_image["sourceObjectId"] if fill_image is not None else None,
            fillImageType=image_type, fillImageTypeName=fill_type_name, fillBranch=fill_branch,
            fillImageEnabled=image_enabled, handleRect=None, sourceGameObjectActive=go_active,
            fillGameObjectActive=fill_go_active, parentGameObjectActive=parent_go_active,
            sourceImageTypeProof=source_image_proofs[0] if source_image_proofs else None,
            provenNonImageComponents=excluded_non_image_components, fillImageNullProven=fill_image is None,
            competingLayoutDrivers=competing,
            sdkCodeProof=sdk_proof["proofs"], sdkTuple=binding_rows[0]["expectedTuple"])
        overrides = []
        for vec, stored, expected in (("m_AnchorMin", stored_min, anchor_min), ("m_AnchorMax", stored_max, anchor_max)):
            for axis_name in ("x", "y"):
                old = _f32_mapping(stored.get(axis_name), f"{vec}.{axis_name}")
                new = _f32(expected[axis_name])
                overrides.append(dict(sourceObjectId=fill_rect["sourceObjectId"], path=f"{vec}.{axis_name}",
                    sourceStoredValue=old, expectedDrivenValue=new, differs=old != new,
                    mapping="Slider.UpdateVisuals -> fill RectTransform anchors",
                    formula=("0/1 default anchor" if image_type == 3 else
                             ("1-normalizedValue" if reverse and axis_name == axis else
                              "normalizedValue" if not reverse and axis_name == axis else "default anchor")),
                    driver=driver_evidence))
        if image_type == 3:
            fill_amount = _f32_mapping(image_data.get("m_FillAmount"), "Image.m_FillAmount")
            overrides.append(dict(sourceObjectId=fill_image["sourceObjectId"], path="m_FillAmount",
                sourceStoredValue=fill_amount, expectedDrivenValue=normalized, differs=fill_amount != normalized,
                mapping="Slider.UpdateVisuals -> Image.fillAmount = normalizedValue", formula="normalizedValue", driver=driver_evidence))
        status = "active_enabled_driver"
        planned.append(dict(sourceSliderId=slider_id, sourceSliderIdentity=ident, sourceMonoScriptId=script["sourceObjectId"],
            sourceScriptIdentity=_source_identity(script), sourceTuple=dict(source_tuple),
            status=status, sourceGameObjectId=go["sourceObjectId"], sourceGameObjectActive=go_active,
            activeHierarchy=go_chain, fillRectId=fill_rect["sourceObjectId"],
            fillImageId=fill_image["sourceObjectId"] if fill_image is not None else None,
            fillGameObjectId=fill_go["sourceObjectId"], fillActiveHierarchy=fill_go_chain,
            fillContainerRectId=parent_rect["sourceObjectId"], fillContainerActiveHierarchy=parent_go_chain,
            sourceFields=driver_evidence["sourceStored"], normalizedValue=normalized, direction=direction,
            fillImageType=driver_evidence["fillImageTypeName"] or "null", handleRect=None,
            sdkTarget=dict(identity=binding_rows[0]["identity"], expectedTuple=binding_rows[0]["expectedTuple"],
                           source=binding_rows[0]["targetSource"]), overrides=overrides))
    return dict(schemaVersion=1, contract=CONTRACT, status="offline-source-driven-plan", profile="ugui-2.6.0-slider-fill-v1",
        sourceUnityVersion="2021.3.30f1", targetPackageVersion=sdk_proof["packageVersion"], targetAssembly="UnityEngine.UI",
        sourceCodeExecuted=False, nativeGetClass="not_run; SDK expected tuple evidence only", sdkEvidence=sdk_proof,
        sliders=planned)
