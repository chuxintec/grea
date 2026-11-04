"""Finite, nonexecuting evidence for static presentation of custom Unity UI types."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import read, safe, sha
from .unity_code_il import _pairs, _scopes, parse_csharp, tokenize_csharp
from .unity_prefab_types import NATIVE_SCHEMA_VERSION, _NATIVE_COMPONENT_CHAINS, _resolve_base


CONTRACT = "monkey-unity-source-ui-static-evidence/1"
UI_BASES = {
    "UnityEngine.UI.Graphic", "UnityEngine.UI.Image", "UnityEngine.UI.RawImage", "UnityEngine.UI.Text",
}
_LIFECYCLE_MARKERS = {"ExecuteAlways", "ExecuteInEditMode", "DefaultExecutionOrder"}


def _full_type_name(row: dict, namespaces: list[dict], types: list[dict]) -> str:
    namespace_rows = sorted((ns for ns in namespaces if ns["start"] < row["declIndex"] < ns["end"]),
                            key=lambda ns: ns["start"])
    parents = sorted((parent for parent in types if parent["open"] < row["declIndex"] < parent["close"]),
                     key=lambda parent: parent["open"])
    namespace = ".".join(ns["name"] for ns in namespace_rows)
    nested = "+".join([*(parent["name"] for parent in parents), row["name"]])
    return namespace + ("." if namespace else "") + nested


def _member_inventory(tokens: list[dict], type_row: dict, type_rows: list[dict]) -> tuple[bool, list[str], list[str]]:
    """Prove a class body contains only field declarations with no initializer."""
    values = [row["value"] for row in tokens]
    brace_pairs = _pairs(tokens, "{", "}")
    other_nested = [row for row in type_rows if row is not type_row and
                    type_row["open"] < row["declIndex"] < type_row["close"]]
    if other_nested:
        return False, [], ["nested-type-inventory-unverified"]
    fields: list[str] = []
    reasons: list[str] = []
    start = type_row["open"] + 1
    index = start
    depth_paren = depth_bracket = 0
    while index < type_row["close"]:
        value = values[index]
        if value == "(" : depth_paren += 1
        elif value == ")": depth_paren -= 1
        elif value == "[": depth_bracket += 1
        elif value == "]": depth_bracket -= 1
        elif value == "{" and depth_paren == 0 and depth_bracket == 0:
            reasons.append("method-property-or-block-member-present")
            close = brace_pairs.get(index)
            if close is None or close > type_row["close"]:
                return False, fields, reasons + ["unbalanced-member-body"]
            index = close + 1
            start = index
            continue
        elif value == ";" and depth_paren == 0 and depth_bracket == 0:
            member = values[start:index]
            if not member:
                start = index + 1
                index += 1
                continue
            if any(token in member for token in ("=", "=>", "event", "static", "const", "operator", "~")):
                reasons.append("field-initializer-or-executable-member-present")
            elif "(" in member or ")" in member:
                reasons.append("method-or-constructor-declaration-present")
            else:
                # A terminated, non-executable declaration is conservatively
                # accepted only when it has a name after a plausible type.
                identifiers = [item for item in member if item.isidentifier() or item.startswith("@")]
                if len(identifiers) < 2:
                    reasons.append("unknown-class-member-shape")
                else:
                    fields.append(identifiers[-1].removeprefix("@"))
            start = index + 1
        index += 1
    trailing = values[start:type_row["close"]]
    if any(value not in ("\n",) for value in trailing):
        reasons.append("unterminated-or-unknown-class-member")
    return not reasons, fields, reasons


def classify_source_ui_static(parsed: dict[str, Any], identity: dict[str, str], base: str) -> dict[str, Any] | None:
    """Return bounded source-text evidence and fail-closed static classification.

    Only a hash-pinned, uniquely declared class directly inheriting one of the
    supported native UI rendering bases can qualify. Any custom methods,
    accessors, initializers, partial declaration, or unknown member shape keeps
    source semantics partial. The current request contract does not carry an
    independent original-assembly method inventory, so a field-only text scan
    is never promoted to ``staticSemanticsProven``. This routine never executes
    or emits source code.
    """
    if base not in UI_BASES:
        return None
    wanted = (identity.get("assembly"), identity.get("namespace") or "", identity.get("name"))
    rows = [row for row in parsed.get("declarations", []) if
            (row.get("identity", {}).get("assembly"), row.get("identity", {}).get("namespace") or "",
             row.get("identity", {}).get("name")) == wanted]
    base_result = {"contract": CONTRACT, "sourceIdentity": dict(assembly=wanted[0], namespace=wanted[1], name=wanted[2]),
                   "sourceBase": base, "sourceCodeExecuted": False, "targetRenderingIsSeparate": True,
                   "staticSemanticsProven": False, "status": "source-ui-behavior-unverified",
                   "nativeSchemaVersion": NATIVE_SCHEMA_VERSION,
                   "sourceBaseChain": [((wanted[1] + ".") if wanted[1] else "") + str(wanted[2]),
                                       *(_NATIVE_COMPONENT_CHAINS.get(base) or [])],
                   "methodInventoryStatus": "unknown", "sourceMethods": [], "reasons": []}
    if len(rows) != 1:
        base_result["reasons"] = ["source-class-declaration-missing-or-ambiguous"]
        return base_result
    declaration = rows[0]
    resolved_source_base, base_gap = _resolve_base(declaration, parsed)
    if base_gap or resolved_source_base != base:
        base_result["reasons"] = ["source-base-chain-is-not-exactly-proven-to-native-ui-base"]
        return base_result
    source = declaration.get("source", {})
    path, expected_sha = source.get("path"), source.get("sha256")
    if not isinstance(path, str) or not isinstance(expected_sha, str):
        base_result["reasons"] = ["hash-pinned-source-declaration-absent"]
        return base_result
    try:
        source_path = safe(path)
        raw = read(source_path, max_bytes=8 * 1024 * 1024)
        if sha(raw) != expected_sha:
            base_result["reasons"] = ["source-declaration-hash-changed"]
            return base_result
        text = raw.decode("utf-8-sig")
    except (OSError, UnicodeError, ValueError):
        base_result["reasons"] = ["source-declaration-unavailable-or-invalid"]
        return base_result

    token_rows = tokenize_csharp(text)
    values = [row["value"] for row in token_rows]
    brace_pairs = _pairs(token_rows, "{", "}")
    namespaces, type_rows = _scopes(token_rows, brace_pairs)
    full_name = (wanted[1] + "." if wanted[1] else "") + wanted[2]
    exact_types = [row for row in type_rows if _full_type_name(row, namespaces, type_rows) == full_name and row["kind"] == "class"]
    if len(exact_types) != 1:
        base_result.update(sourceDeclarationPath=str(source_path), sourceDeclarationSha256=expected_sha,
                           reasons=["exact-source-class-body-missing-or-ambiguous"])
        return base_result
    type_row = exact_types[0]
    # Declarations spanning multiple partial files cannot be proven from one body.
    previous_type_close = max((row["close"] for row in type_rows if row["close"] < type_row["declIndex"]), default=-1)
    header = values[previous_type_close + 1:type_row["open"]]
    reasons = []
    if "partial" in header:
        reasons.append("partial-class-can-have-additional-source-behavior")
    if "[" in header:
        reasons.append("source-class-attributes-unverified")
    if ":" in header and "," in header[header.index(":") + 1:]:
        reasons.append("additional-interface-or-base-type-unverified")
    if any(marker in header for marker in _LIFECYCLE_MARKERS):
        reasons.append("lifecycle-or-rendering-attribute-present")
    member_complete, source_fields, member_reasons = _member_inventory(token_rows, type_row, type_rows)
    reasons.extend(member_reasons)
    csharp = parse_csharp(text, str(source_path), expected_sha)
    methods = [row for row in csharp.get("methods", []) if row.get("declaringType") == full_name]
    source_methods = [{"name": method.get("name"), "signature": method.get("signature"),
                       "status": method.get("status"), "sourceFileSha256": expected_sha,
                       "bodyEvidenceSha256": (method.get("bodyEvidence") or {}).get("sha256"),
                       "bodyVerifiedAgainstOriginalIL": False} for method in methods]
    if methods:
        reasons.append("custom-methods-present;static-effects-not-proven-neutral")
    text_inventory_complete = member_complete and not reasons
    # The source request currently pins TypeTree/dummy-schema declarations, not
    # an independent original assembly method table. A field-only decompiler
    # text dump is therefore never promoted into a complete source-method proof.
    reasons.append("independent-complete-original-method-inventory-provenance-absent")
    base_result.update(sourceDeclarationPath=str(source_path), sourceDeclarationSha256=expected_sha,
        sourceClassMemberInventoryComplete=member_complete, sourceTextMemberScanStatus="complete" if text_inventory_complete else "partial",
        sourceFieldNames=source_fields,
        sourceMethods=source_methods, sourceMethodCount=len(source_methods),
        methodInventoryStatus="unproven-without-independent-original-method-metadata",
        sourceMethodInventoryProvenanceStatus="missing-independent-original-method-metadata",
        reasons=sorted(set(reasons)))
    return base_result
