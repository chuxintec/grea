"""Evidence-driven Unity Prefab type/schema carriers from decompiler text.

This module parses C# text only. It never loads assemblies or executes source code.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from .unity_code_il import _pairs, _scopes, _ident, tokenize_csharp
from .unity_code_model import CORE_FIELDS, CS_KEYWORDS, field_type, identifier
from .sources.compiled import fail


MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_DECLARATIONS = 100_000

# Deliberately narrow. These are native Unity types with stable public names in
# the source's UnityEngine.UI namespace; they are never shadowed by generated code.
# Source version is part of this allowlist identity; expanding it requires
# reviewed TypeTree metadata from that exact engine version.
NATIVE_SCHEMA_VERSION = "source-2021.3.30f1_target-6000.6.2f1_ugui-2.6.0"
NATIVE_BASES = {
    "UnityEngine.MonoBehaviour": "UnityEngine.MonoBehaviour",
    "UnityEngine.ScriptableObject": "UnityEngine.ScriptableObject",
    "UnityEngine.UI.Image": "UnityEngine.UI.Image",
    "UnityEngine.UI.Text": "UnityEngine.UI.Text",
    "UnityEngine.UI.RawImage": "UnityEngine.UI.RawImage",
    "UnityEngine.UI.Graphic": "UnityEngine.UI.Graphic",
    "UnityEngine.UI.GridLayoutGroup": "UnityEngine.UI.GridLayoutGroup",
    "UnityEngine.UI.BaseMeshEffect": "UnityEngine.UI.BaseMeshEffect",
    "UnityEngine.EventSystems.UIBehaviour": "UnityEngine.EventSystems.UIBehaviour",
}
_NATIVE_COMPONENT_CHAINS = {
    "UnityEngine.MonoBehaviour": ["UnityEngine.MonoBehaviour"],
    "UnityEngine.EventSystems.UIBehaviour": ["UnityEngine.EventSystems.UIBehaviour", "UnityEngine.MonoBehaviour"],
    "UnityEngine.UI.Image": ["UnityEngine.UI.Image", "UnityEngine.UI.MaskableGraphic", "UnityEngine.UI.Graphic",
                              "UnityEngine.EventSystems.UIBehaviour", "UnityEngine.MonoBehaviour"],
    "UnityEngine.UI.Text": ["UnityEngine.UI.Text", "UnityEngine.UI.MaskableGraphic", "UnityEngine.UI.Graphic",
                            "UnityEngine.EventSystems.UIBehaviour", "UnityEngine.MonoBehaviour"],
    "UnityEngine.UI.RawImage": ["UnityEngine.UI.RawImage", "UnityEngine.UI.MaskableGraphic", "UnityEngine.UI.Graphic",
                                "UnityEngine.EventSystems.UIBehaviour", "UnityEngine.MonoBehaviour"],
    "UnityEngine.UI.Graphic": ["UnityEngine.UI.Graphic", "UnityEngine.EventSystems.UIBehaviour", "UnityEngine.MonoBehaviour"],
    "UnityEngine.UI.GridLayoutGroup": ["UnityEngine.UI.GridLayoutGroup", "UnityEngine.UI.LayoutGroup", "UnityEngine.EventSystems.UIBehaviour", "UnityEngine.MonoBehaviour"],
    "UnityEngine.UI.BaseMeshEffect": ["UnityEngine.UI.BaseMeshEffect", "UnityEngine.EventSystems.UIBehaviour",
                                      "UnityEngine.MonoBehaviour"],
}

# TypeTree members inherited from these native UI bases are retained as evidence,
# but not redeclared on a generated derived class. This is a bounded common set;
# anything else must be declared by the source class or remains a gap.
_UI_INHERITED_FIELDS = {
    "UnityEngine.UI.Image": {
        "m_Material": ("PPtr<$Material>", "UnityEngine.Material"),
        "m_Color": ("ColorRGBA", "UnityEngine.Color"),
        "m_RaycastTarget": ("UInt8", "bool"),
        "m_RaycastPadding": ("Vector4f", "UnityEngine.Vector4"),
        "m_Maskable": ("UInt8", "bool"),
        "m_OnCullStateChanged": ("CullStateChangedEvent", "UnityEngine.UI.MaskableGraphic.CullStateChangedEvent"),
        "m_Sprite": ("PPtr<$Sprite>", "UnityEngine.Sprite"),
        "m_Type": ("int", "UnityEngine.UI.Image.Type"),
        "m_PreserveAspect": ("UInt8", "bool"),
        "m_FillCenter": ("UInt8", "bool"),
        "m_FillMethod": ("int", "UnityEngine.UI.Image.FillMethod"),
        "m_FillAmount": ("float", "float"),
        "m_FillClockwise": ("UInt8", "bool"),
        "m_FillOrigin": ("int", "int"),
        "m_UseSpriteMesh": ("UInt8", "bool"),
        "m_PixelsPerUnitMultiplier": ("float", "float"),
    },
    "UnityEngine.UI.Text": {
        "m_Material": ("PPtr<$Material>", "UnityEngine.Material"),
        "m_Color": ("ColorRGBA", "UnityEngine.Color"),
        "m_RaycastTarget": ("UInt8", "bool"),
        "m_RaycastPadding": ("Vector4f", "UnityEngine.Vector4"),
        "m_Maskable": ("UInt8", "bool"),
        "m_OnCullStateChanged": ("CullStateChangedEvent", "UnityEngine.UI.MaskableGraphic.CullStateChangedEvent"),
        "m_FontData": ("FontData", "UnityEngine.UI.FontData"),
        "m_Text": ("string", "string"),
    },
}


# Bounded source 2021.3 declaration/TypeTree profiles. Common Graphic fields
# were checked in original DummyDLL declarations and target uGUI 2.6.0 sources.
_UI_INHERITED_FIELDS["UnityEngine.UI.Graphic"] = {
    k: v for k, v in _UI_INHERITED_FIELDS["UnityEngine.UI.Image"].items()
    if k in ("m_Material", "m_Color", "m_RaycastTarget", "m_RaycastPadding")
}
_UI_INHERITED_FIELDS["UnityEngine.UI.RawImage"] = {
    **{k: v for k, v in _UI_INHERITED_FIELDS["UnityEngine.UI.Image"].items()
       if k in ("m_Material", "m_Color", "m_RaycastTarget", "m_RaycastPadding", "m_Maskable", "m_OnCullStateChanged")},
    "m_Texture": ("PPtr<$Texture>", "UnityEngine.Texture"),
    "m_UVRect": ("Rectf", "UnityEngine.Rect"),
}
_UI_INHERITED_FIELDS["UnityEngine.UI.GridLayoutGroup"] = {
    "m_Padding": ("RectOffset", "UnityEngine.RectOffset"),
    "m_ChildAlignment": ("int", "UnityEngine.TextAnchor"),
    "m_StartCorner": ("int", "UnityEngine.UI.GridLayoutGroup.Corner"),
    "m_StartAxis": ("int", "UnityEngine.UI.GridLayoutGroup.Axis"),
    "m_CellSize": ("Vector2f", "UnityEngine.Vector2"),
    "m_Spacing": ("Vector2f", "UnityEngine.Vector2"),
    "m_Constraint": ("int", "UnityEngine.UI.GridLayoutGroup.Constraint"),
    "m_ConstraintCount": ("int", "int"),
}

from .unity_prefab_input_profiles import merge_inputfield_native_profile

_input_profile = merge_inputfield_native_profile(NATIVE_BASES, _NATIVE_COMPONENT_CHAINS, _UI_INHERITED_FIELDS)
NATIVE_BASES = _input_profile["nativeBases"]
_NATIVE_COMPONENT_CHAINS = _input_profile["nativeComponentChains"]
_UI_INHERITED_FIELDS = _input_profile["uiInheritedFields"]

def _source_identity(assembly: str, namespace: str, name: str) -> tuple[str, str, str]:
    if not isinstance(assembly, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+(?:\.dll)?", assembly):
        fail("UNITY_PREFAB_ASSEMBLY", str(assembly), "Unsafe or missing source assembly identity")
    for part in namespace.split(".") if namespace else []:
        identifier(part)
    for part in name.split("+"):
        identifier(part)
    return assembly, namespace, name


def _type_expr(values: list[str], start: int, end: int) -> str | None:
    """Accept a plain or qualified type name; reject aliases/generics here."""
    if start >= end:
        return None
    suffix = ""
    if end - start >= 3 and values[end-2:end] == ["[", "]"]:
        suffix = "[]"
        end -= 2
    out = []
    expect_name = True
    for value in values[start:end]:
        if expect_name and _ident(value):
            out.append(value.removeprefix("@")); expect_name = False
        elif not expect_name and value == ".":
            out.append(value); expect_name = True
        else:
            return None
    return "".join(out) + suffix if out and not expect_name else None


def _parse_using(values: list[str]) -> list[str]:
    imports = []
    for i, value in enumerate(values):
        if value != "using" or i + 1 >= len(values):
            continue
        end = i + 1
        while end < len(values) and values[end] != ";":
            end += 1
        if end < len(values):
            raw = _type_expr(values, i + 1, end)
            if raw:
                imports.append(raw)
    return sorted(set(imports))


def _member_segments(values: list[str], open_index: int, close_index: int,
                     braces: dict[int, int], parens: dict[int, int], brackets: dict[int, int]):
    """Yield top-level member token ranges, skipping method/property bodies."""
    start = open_index + 1
    i = start
    while i < close_index:
        value = values[i]
        if value == "(" and i in parens:
            i = parens[i] + 1
            continue
        if value == "[" and i in brackets:
            i = brackets[i] + 1
            continue
        if value == "{" and i in braces:
            i = braces[i] + 1
            if start < i:
                start = i
            continue
        if value == ";":
            if start < i:
                yield start, i
            start = i + 1
        i += 1


def _field_from_segment(values: list[str], start: int, end: int) -> dict[str, str] | None:
    segment = values[start:end]
    if not segment or "{" in segment or "=>" in segment:
        return None
    if any(value in segment for value in ("class", "struct", "enum", "interface")):
        return None
    original = list(segment)
    serialized_attribute = "SerializeField" in original
    nonserialized_attribute = "NonSerialized" in original
    public_field = "public" in original
    readonly_field = "readonly" in original
    # Drop attributes and modifiers; one declarator only, and no initializer is
    # carried into output. Exact declaration type/name still comes from this text.
    while segment and segment[0] == "[":
        depth = 1; j = 1
        while j < len(segment) and depth:
            depth += (segment[j] == "[") - (segment[j] == "]")
            j += 1
        if depth:
            return None
        segment = segment[j:]
    if "(" in segment:
        return None
    modifiers = {"public", "private", "protected", "internal", "readonly", "volatile", "new", "unsafe"}
    while segment and segment[0] in modifiers:
        if segment[0] in {"static", "const", "event"}:
            return None
        segment = segment[1:]
    if not segment:
        return None
    if any(value in segment for value in ("static", "const", "event")):
        return None
    # Remove initializer expression; this module never copies initializers.
    if "=" in segment:
        segment = segment[:segment.index("=")]
    if len(segment) < 2 or not _ident(segment[-1]):
        return None
    name = segment[-1].removeprefix("@")
    typ = _type_expr(segment, 0, len(segment) - 1)
    if not typ:
        return None
    return {"name": name, "type": typ,
            "unitySerializedCandidate": bool((public_field or serialized_attribute) and not (readonly_field or nonserialized_attribute))}


def _enum_values(values: list[str], type_row: dict[str, Any], braces: dict[int, int]) -> list[dict[str, Any]] | None:
    body = values[type_row["open"] + 1:type_row["close"]]
    result = []
    start = 0
    for i in range(len(body) + 1):
        if i < len(body) and body[i] != ",":
            continue
        item = body[start:i]; start = i + 1
        if not item:
            continue
        # Strip attributes emitted by ILSpy (for example [Token(...)]) before
        # interpreting the enum member declaration.
        while item and item[0] == "[":
            depth = 1
            j = 1
            while j < len(item) and depth:
                depth += (item[j] == "[") - (item[j] == "]")
                j += 1
            if depth:
                return None
            item = item[j:]
        if not item or not _ident(item[0]):
            return None
        member_name = item[0].removeprefix("@")
        if len(item) == 1:
            value = result[-1]["value"] + 1 if result else 0
        elif len(item) >= 3 and item[1] == "=":
            raw = "".join(item[2:])
            match = re.fullmatch(r"(-?)(0[xX][0-9a-fA-F]+|0[bB][01]+|[0-9]+)([uU]?[lL]?|[lL]?[uU]?)", raw)
            if not match:
                return None
            sign, digits, _suffix = match.groups()
            radix = 16 if digits.lower().startswith("0x") else 2 if digits.lower().startswith("0b") else 10
            value = int(digits, radix) * (-1 if sign else 1)
        else:
            return None
        result.append({"name": member_name, "value": value})
    return result or None


def _enum_value_range(underlying: str) -> tuple[int, int] | None:
    return {
        "sbyte": (-(2**7), 2**7 - 1), "byte": (0, 2**8 - 1),
        "short": (-(2**15), 2**15 - 1), "ushort": (0, 2**16 - 1),
        "int": (-(2**31), 2**31 - 1), "uint": (0, 2**32 - 1),
        "long": (-(2**63), 2**63 - 1), "ulong": (0, 2**64 - 1),
    }.get(underlying)


def _evaluate_enum_values(values: list[str] | None, underlying: str) -> list[dict[str, Any]] | None:
    bounds = _enum_value_range(underlying)
    if not values or bounds is None:
        return None
    low, high = bounds
    if any(not isinstance(item.get("value"), int) or not low <= item["value"] <= high for item in values):
        return None
    return values


def parse_declarations(source_text: str, *, assembly: str, source_path: str = "<memory>",
                       source_sha256: str | None = None, top_level_only: bool = False) -> dict[str, Any]:
    """Parse type/base/field/enum declarations from hash-pinned decompiler text."""
    if not isinstance(source_text, str) or len(source_text.encode("utf-8")) > MAX_SOURCE_BYTES:
        fail("UNITY_PREFAB_SOURCE_BUDGET", source_path, "Decompiler text exceeds the static parsing budget")
    raw = source_text.encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    if source_sha256 is not None and source_sha256 != digest:
        fail("UNITY_PREFAB_SOURCE_HASH", source_path, "Decompiler text does not match the supplied SHA256")
    tokens = tokenize_csharp(source_text)
    values = [row["value"] for row in tokens]
    braces, parens, brackets = (_pairs(tokens, l, r) for l, r in (("{", "}"), ("(", ")"), ("[", "]")))
    for left, pairs in (("{", braces), ("(", parens), ("[", brackets)):
        if len(pairs) != sum(value == left for value in values):
            fail("UNITY_PREFAB_CSHARP_DELIMITER", source_path, "Unbalanced C# declaration delimiters")
    namespaces, type_rows = _scopes(tokens, braces)
    if len(type_rows) > MAX_DECLARATIONS:
        fail("UNITY_PREFAB_DECLARATION_BUDGET", source_path, "Too many type declarations")
    imports = _parse_using(values)
    declarations = []
    for row in type_rows:
        namespace_rows = sorted((ns for ns in namespaces if ns["start"] < row["declIndex"] < ns["end"]), key=lambda ns: ns["start"])
        namespace = ".".join(ns["name"] for ns in namespace_rows)
        parents = sorted((parent for parent in type_rows if parent["open"] < row["declIndex"] < parent["close"]), key=lambda p: p["open"])
        if top_level_only and parents:
            continue
        name = "+".join([*(parent["name"] for parent in parents), row["name"]])
        source_id = _source_identity(assembly, namespace, name)
        kind = row["kind"]
        base = None
        enum_underlying = "int"
        if kind == "class":
            header_start = row["nameIndex"] + 1
            colon = header_start
            while colon < row["open"] and values[colon] != ":":
                colon += 1
            if colon < row["open"]:
                end = colon + 1
                while end < row["open"] and values[end] != "," and values[end] != "where":
                    end += 1
                base = _type_expr(values, colon + 1, end)
                if not base:
                    fail("UNITY_PREFAB_BASE_SYNTAX", ".".join(source_id), "Could not parse class base declaration")
        elif kind == "enum":
            colon = row["nameIndex"] + 1
            while colon < row["open"] and values[colon] != ":":
                colon += 1
            if colon < row["open"]:
                enum_underlying = _type_expr(values, colon + 1, row["open"]) or ""
        fields = []
        enums = _enum_values(values, row, braces) if kind == "enum" else None
        if kind == "enum":
            enums = _evaluate_enum_values(enums, enum_underlying)
        if kind in ("class", "struct"):
            for start, end in _member_segments(values, row["open"], row["close"], braces, parens, brackets):
                field = _field_from_segment(values, start, end)
                if field:
                    fields.append(field)
        declarations.append({"identity": {"assembly": source_id[0], "namespace": source_id[1], "name": source_id[2]},
                             "kind": kind, "base": base, "imports": imports, "fields": fields,
                             "enumUnderlyingType": enum_underlying, "enumValues": enums,
                             "source": {"path": source_path, "sha256": digest}})
    return {"schemaVersion": 1, "assembly": assembly, "sourceSha256": digest,
            "sourcePath": source_path, "declarations": declarations}


def _resolve_name(raw: str, namespace: str, imports: list[str], declarations: list[dict[str, Any]]) -> str | None:
    if raw in NATIVE_BASES:
        return raw
    if raw.startswith("UnityEngine."):
        return raw if raw in NATIVE_BASES else None
    matches = [decl for decl in declarations if decl["identity"]["name"].split("+")[-1] == raw]
    if "." in raw:
        full = raw
        matches = [decl for decl in declarations if decl["identity"]["namespace"] + "." + decl["identity"]["name"] == full]
    else:
        imported = [decl for decl in matches if decl["identity"]["namespace"] in imports]
        local = [decl for decl in matches if decl["identity"]["namespace"] == namespace]
        matches = local or imported
    identities = {(d["identity"]["assembly"], d["identity"]["namespace"], d["identity"]["name"]) for d in matches}
    return next(iter(identities))[1] + "." + next(iter(identities))[2] if len(identities) == 1 else None


def _resolve_base(decl: dict[str, Any], parsed: dict[str, Any]) -> tuple[str | None, str | None]:
    raw = decl.get("base")
    if raw is None:
        return None, "source class has no explicit base declaration"
    if "." in raw:
        resolved = raw
        if resolved not in NATIVE_BASES:
            return None, "custom base lacks an independently proven native carrier: " + resolved
    else:
        declarations = parsed.get("declarations", [])

        def candidates_in(prefix: str) -> list[tuple[str, str]]:
            full = prefix + "." + raw if prefix else raw
            found = []
            # A same-assembly declaration shadows imported framework types with
            # the same qualified name, so it cannot accidentally become a native base.
            if any(d["identity"]["assembly"] == decl["identity"]["assembly"]
                   and d["identity"]["namespace"] + "." + d["identity"]["name"].split("+")[-1] == full
                   for d in declarations):
                found.append((full, "custom"))
            if full in NATIVE_BASES:
                found.append((full, "native"))
            return found

        local = candidates_in(decl["identity"]["namespace"])
        imported = [candidate for namespace in decl["imports"] for candidate in candidates_in(namespace)]
        candidates = local or imported
        unique = sorted(set(candidates))
        if len(unique) != 1:
            return None, "base is unknown or ambiguous under explicit imports: " + raw
        resolved, kind = unique[0]
        if kind != "native":
            return None, "custom base lacks an independently proven native carrier: " + resolved
    if resolved not in NATIVE_BASES:
        return None, "custom base lacks an independently proven native carrier: " + resolved
    return NATIVE_BASES[resolved], None


def propose_schema(parsed: dict[str, Any], script_identity: dict[str, str], typed_schema: dict[str, Any]) -> dict[str, Any]:
    """Join exact MonoScript identity to declarations and a strict TypeTree shape."""
    assembly = script_identity.get("assembly", "")
    namespace = script_identity.get("namespace", "") or ""
    name = script_identity.get("name", "")
    wanted = _source_identity(assembly, namespace, name)
    found = [d for d in parsed.get("declarations", [])
             if (d["identity"]["assembly"], d["identity"]["namespace"], d["identity"]["name"]) == wanted]
    if len(found) != 1:
        return {"status": "gap", "identity": dict(assembly=assembly, namespace=namespace, name=name),
                "reason": "exact MonoScript assembly/namespace/type declaration is missing or duplicated"}
    decl = found[0]
    base, base_gap = _resolve_base(decl, parsed)
    if decl["kind"] != "class" or base_gap:
        return {"status": "gap", "identity": decl["identity"], "reason": base_gap or "MonoScript type is not a class"}
    children = typed_schema.get("children")
    if not isinstance(children, list):
        return {"status": "gap", "identity": decl["identity"], "reason": "typed schema has no child field list"}
    own = {field["name"]: field for field in decl["fields"]}
    enum_decls = [d for d in parsed.get("declarations", []) if d.get("kind") == "enum"]
    emitted_enums: list[dict[str, Any]] = []
    output_fields, inherited, gaps = [], [], []
    native_ui = base.startswith("UnityEngine.UI.")
    for node in children:
        if not isinstance(node, dict) or not isinstance(node.get("name"), str):
            gaps.append("malformed TypeTree child")
            continue
        field_name = node["name"]
        if field_name in CORE_FIELDS:
            continue
        source_field = own.get(field_name)
        if source_field is None:
            native_field = _UI_INHERITED_FIELDS.get(base, {}).get(field_name)
            if native_ui and native_field is not None and native_field[0] == node.get("type"):
                inherited_cs_type = native_field[1]
                inherited.append({"name": field_name, "sourceType": node.get("type"),
                                  "csType": inherited_cs_type, "owner": base})
            else:
                gaps.append("TypeTree field has no exact source declaration or native inheritance proof: " + field_name)
            continue
        ref = decl.get("fieldTypeReferences", {}).get(field_name)
        enum_matches = [e for e in enum_decls if (e["identity"] == ref["targetType"] if ref else e["identity"]["assembly"] == assembly)
                        and e["identity"]["name"].split("+")[-1] == source_field["type"].split(".")[-1]
                        and (e["identity"]["namespace"] == namespace
                             or e["identity"]["namespace"] in decl["imports"]
                             or source_field["type"] == e["identity"]["namespace"] + "." + e["identity"]["name"])]
        if enum_matches:
            if len(enum_matches) != 1 or enum_matches[0].get("enumValues") is None:
                gaps.append("enum declaration is ambiguous or lacks exact numeric constants: " + field_name)
                continue
            enum = enum_matches[0]
            try:
                enum_name = identifier(enum["identity"]["name"])
            except ValueError:
                gaps.append("unsafe enum type name: " + field_name)
                continue
            underlying = enum.get("enumUnderlyingType") or "int"
            expected = {"int": "int", "uint": "uint", "short": "short", "ushort": "ushort",
                        "byte": "byte", "sbyte": "sbyte", "long": "long", "ulong": "ulong"}.get(underlying)
            if expected != node.get("type"):
                gaps.append("enum storage differs from TypeTree: " + field_name)
                continue
            cs_type = enum_name
            if enum["identity"]["namespace"] != namespace:
                cs_type = "global::" + (enum["identity"]["namespace"] + "." if enum["identity"]["namespace"] else "") + enum_name
            record = {"name": enum_name, "namespace": enum["identity"]["namespace"],
                      "underlyingType": underlying, "values": enum["enumValues"],
                      "identity": enum["identity"], "sourceEvidence": enum["source"]}
            if record not in emitted_enums:
                emitted_enums.append(record)
            output_fields.append({"name": field_name, "sourceType": node["type"], "csType": cs_type,
                                  "declarationType": source_field["type"], "schemaEvidence": "strict-TypeTree+exact-source-declaration"})
            continue
        try:
            if ref and ref.get("fieldTypeKind") == "class" and not ref["targetType"]["assembly"].startswith("UnityEngine."):
                fail("UNITY_PREFAB_FIELD_CLASS_ASSEMBLY", field_name, "A custom source class cannot be replaced by a same-name native type")
            try:
                cs_type = "bool" if source_field["type"] == "bool" and node.get("type") in ("bool", "UInt8") else field_type(node)
            except ValueError:
                if not ref or ref.get("fieldTypeKind") != "class":
                    raise
                target = ref["targetType"]
                if not target["assembly"].startswith("UnityEngine.") or target["namespace"] not in ("UnityEngine", "UnityEngine.UI", "UnityEngine.EventSystems"):
                    raise
                pointer = node
                if ref.get("arrayRank", 0) == 1 and node.get("type") == "vector":
                    arrays = [n for n in node.get("children", []) if n.get("type") == "Array"]
                    values = [n for n in arrays[0].get("children", []) if n.get("name") == "data"] if len(arrays) == 1 else []
                    if len(values) != 1:
                        raise
                    pointer = values[0]
                elif ref.get("arrayRank", 0) != 0:
                    raise
                if pointer.get("type") not in ("PPtr<" + target["name"] + ">", "PPtr<$" + target["name"] + ">"):
                    raise
                cs_type = target["namespace"] + "." + target["name"] + ("[]" if ref.get("arrayRank", 0) else "")
            identifier(field_name)
        except ValueError as error:
            gaps.append(getattr(error, "code", "unsupported") + ":" + field_name)
            continue
        declared = source_field["type"]
        declared_simple = declared.rsplit(".", 1)[-1].removesuffix("[]")
        cs_simple = cs_type.rsplit(".", 1)[-1].removesuffix("[]")
        if declared.endswith("[]") != cs_type.endswith("[]") or (declared_simple != cs_simple and not (declared == "int" and cs_type == "int")):
            gaps.append("source and TypeTree field types differ: " + field_name)
            continue
        output_fields.append({"name": field_name, "sourceType": node["type"], "csType": cs_type,
                              "declarationType": declared, "schemaEvidence": "strict-TypeTree+exact-source-declaration"})
    # Every source declaration that the TypeTree identifies as a field must be present.
    schema_names = {n.get("name") for n in children if isinstance(n, dict)}
    missing = sorted(field["name"] for field in decl["fields"]
                     if field.get("unitySerializedCandidate") and field["name"] not in schema_names)
    if missing:
        gaps.extend("source field absent from TypeTree: " + value for value in missing)
    if base == "UnityEngine.UI.BaseMeshEffect":
        gaps.append("native abstract base requires ModifyMesh(VertexHelper); original behavior unavailable, no fake override emitted")
    return {"status": "schema_only" if not gaps else "gap", "identity": decl["identity"], "base": base,
            "fields": output_fields, "inheritedFields": inherited, "gaps": gaps,
            "enums": emitted_enums,
            "nativeSchemaVersion": NATIVE_SCHEMA_VERSION,
            "sourceBaseChain": _NATIVE_COMPONENT_CHAINS.get(base),
            "sourceEvidence": decl["source"], "methodBodies": "unavailable-not-emitted",
            "initializers": "not-emitted", "callbacks": "not-emitted"}


def emit_schema(proposal: dict[str, Any]) -> str:
    """Emit a schema-only C# carrier. Gaps are fatal; no methods are fabricated."""
    if proposal.get("status") != "schema_only":
        fail("UNITY_PREFAB_SCHEMA_GAP", proposal.get("identity", {}).get("name", "?"),
             "Cannot emit a carrier with unresolved type or field evidence")
    ident = proposal["identity"]
    assembly, namespace, name = _source_identity(ident["assembly"], ident.get("namespace", ""), ident["name"])
    if "+" in name:
        fail("UNITY_PREFAB_NESTED_CLASS_UNSUPPORTED", name, "Nested MonoScript classes are not emitted as top-level carriers")
    lines = ["// Schema-only carrier. Original source methods, initializers, and callbacks are unavailable.",
             "// Source assembly: " + assembly]
    if namespace:
        lines += ["namespace " + ".".join(identifier(part) for part in namespace.split(".")) + " {"]
    for enum in proposal.get("enums", []):
        if enum["namespace"] != namespace:
            fail("UNITY_PREFAB_ENUM_NAMESPACE", enum["name"], "Cross-namespace enum needs a separately emitted exact declaration")
        lines += ["public enum " + identifier(enum["name"]) + " : " + enum["underlyingType"] + " {"]
        lines += ["    " + identifier(item["name"]) + " = " + str(item["value"]) + "," for item in enum["values"]]
        lines += ["}"]
    lines += ["public class " + identifier(name) + " : " + proposal["base"] + " {"]
    lines += ["    public " + field["csType"] + " " + identifier(field["name"]) + ";" for field in proposal["fields"]]
    lines += ["}"]
    if namespace:
        lines += ["}"]
    return "\n".join(lines) + "\n"


def emit_disabled_carrier(proposal: dict[str, Any]) -> dict[str, Any]:
    """Explicitly emit a MonoBehaviour carrier while retaining source behavior gaps.

    This is only for a fully field-proven class whose source base chain is known
    to end in MonoBehaviour, when the original base's required behavior cannot
    be restored. It never substitutes implicitly for emit_schema.
    """
    identity = proposal.get("identity", {})
    name = identity.get("name", "?")
    blocker = "native abstract base requires ModifyMesh(VertexHelper); original behavior unavailable, no fake override emitted"
    if proposal.get("status") != "gap" or proposal.get("gaps") != [blocker]:
        fail("UNITY_PREFAB_DISABLED_CARRIER_GAPS", name,
             "Disabled carrier requires complete field/type proof and only the known unavailable-base-behavior gap")
    base = proposal.get("base")
    chain = proposal.get("sourceBaseChain")
    if base != "UnityEngine.UI.BaseMeshEffect" or not isinstance(chain, list) or not chain or chain[-1] != "UnityEngine.MonoBehaviour":
        fail("UNITY_PREFAB_DISABLED_CARRIER_BASE", name,
             "Source inheritance is not proven to be a MonoBehaviour component")
    assembly, namespace, source_name = _source_identity(identity.get("assembly", ""),
                                                        identity.get("namespace", ""), name)
    if "+" in source_name:
        fail("UNITY_PREFAB_NESTED_CLASS_UNSUPPORTED", source_name,
             "Nested MonoScript classes are not emitted as top-level carriers")
    fields = list(proposal.get("fields", [])) + list(proposal.get("inheritedFields", []))
    emitted_names = set()
    for field in fields:
        field_name = identifier(field.get("name"))
        if field_name in emitted_names or not isinstance(field.get("csType"), str):
            fail("UNITY_PREFAB_DISABLED_CARRIER_FIELD", source_name,
                 "Disabled carrier field proof is incomplete or contains a name collision")
        emitted_names.add(field_name)
    lines = ["// Disabled schema carrier. Source base behavior is unavailable and must remain disabled.",
             "// Source assembly: " + assembly]
    if namespace:
        lines += ["namespace " + ".".join(identifier(part) for part in namespace.split(".")) + " {"]
    for enum in proposal.get("enums", []):
        if enum["namespace"] != namespace:
            fail("UNITY_PREFAB_ENUM_NAMESPACE", enum["name"],
                 "Cross-namespace enum needs a separately emitted exact declaration")
        lines += ["public enum " + identifier(enum["name"]) + " : " + enum["underlyingType"] + " {"]
        lines += ["    " + identifier(item["name"]) + " = " + str(item["value"]) + "," for item in enum["values"]]
        lines += ["}"]
    lines += ["public class " + identifier(source_name) + " : UnityEngine.MonoBehaviour {"]
    lines += ["    public " + field["csType"] + " " + identifier(field["name"]) + ";" for field in fields]
    lines += ["}"]
    if namespace:
        lines += ["}"]
    metadata = {
        "status": "disabled_schema_carrier",
        "sourceIdentity": dict(assembly=assembly, namespace=namespace, name=source_name),
        "declaredSourceBase": base,
        "sourceBaseChain": list(chain),
        "nativeTargetBase": "UnityEngine.MonoBehaviour",
        "nativeSchemaVersion": proposal.get("nativeSchemaVersion"),
        "sourceEvidence": proposal.get("sourceEvidence"),
        "behavior": "disabled-required",
        "staticPresentation": "unsupported",
        "sourceBaseRestored": False,
        "nativeValidation": "not_run",
        "fields": [{"name": field["name"], "csType": field["csType"],
                    "sourceType": field.get("sourceType"), "schemaEvidence": field.get("schemaEvidence", "native-inherited-TypeTree")}
                   for field in fields],
        "gaps": list(proposal["gaps"]),
        "methodsImplemented": 0,
        "callbacksEmitted": False,
    }
    return {"source": "\n".join(lines) + "\n", "metadata": metadata}

