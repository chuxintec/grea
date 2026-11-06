"""Strict offline mapping from serialized Unity script identities to pinned SDK sources.

This plans expected AssetDatabase tuples only. It does not import assets or claim that
Unity's AssetDatabase.LoadAssetAtPath/GetClass has been executed.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from .unity_prefab_types import parse_declarations


class SDKBindingError(ValueError):
    """Input evidence is incomplete, inconsistent, or ambiguous."""


_GUID = re.compile(r"^[0-9a-fA-F]{32}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_PINNED_FILES = 256
_MAX_PINNED_FILE_BYTES = 4 * 1024 * 1024
_MAX_PINNED_TOTAL_BYTES = 16 * 1024 * 1024
_MAX_ASSEMBLY_SCOPE_DEPTH = 64
_MAX_ASSEMBLY_SCOPE_ENTRIES = 4096
_UNITY_SCRIPT_FILE_ID = 11500000
_UNITY_SCRIPT_OBJECT_TYPE = 3


def _identity(value: Mapping[str, Any], label: str) -> tuple[str, str, str]:
    try:
        assembly = value["assembly"]
        namespace = value["namespace"]
        name = value.get("class", value.get("name"))
    except (KeyError, TypeError) as exc:
        raise SDKBindingError(f"{label}: identity requires assembly, namespace and class") from exc
    if not all(isinstance(v, str) and v.strip() for v in (assembly, name)) or not isinstance(namespace, str):
        raise SDKBindingError(f"{label}: malformed full assembly/namespace/class identity")
    if "." in name or "+" in name:
        raise SDKBindingError(f"{label}: class must be a simple class name")
    return assembly.strip(), namespace.strip(), name.strip()


def _assembly_key(name: str) -> str:
    # Serialized MonoScript tables commonly include the .dll suffix while asmdef
    # names do not. No other fuzzy matching or basename fallback is allowed.
    return name[:-4] if name.lower().endswith(".dll") else name


def _read_pin(root: Path, rel: str, expected_sha: str, *, label: str) -> bytes:
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise SDKBindingError(f"{label}: path must be a safe relative SDK path")
    if not isinstance(expected_sha, str) or not _SHA256.fullmatch(expected_sha):
        raise SDKBindingError(f"{label}: expected a lowercase SHA256 pin")
    path = (root / rel).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise SDKBindingError(f"{label}: path escapes SDK root") from exc
    try:
        size = path.stat().st_size
        if size > _MAX_PINNED_FILE_BYTES:
            raise SDKBindingError(f"{label}: pinned file exceeds byte budget: {rel}")
        raw = path.read_bytes()
    except OSError as exc:
        raise SDKBindingError(f"{label}: pinned file is missing or unreadable: {rel}") from exc
    if len(raw) > _MAX_PINNED_FILE_BYTES:
        raise SDKBindingError(f"{label}: pinned file exceeds byte budget: {rel}")
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_sha:
        raise SDKBindingError(f"{label}: pinned file changed: {rel}")
    return raw


def _guid_from_meta(raw: bytes, rel: str) -> str:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SDKBindingError(f"{rel}: meta is not UTF-8") from exc
    matches = re.findall(r"(?m)^guid:\s*([0-9a-fA-F]{32})\s*$", text)
    if len(matches) != 1:
        raise SDKBindingError(f"{rel}: expected exactly one valid GUID declaration")
    return matches[0].lower()


def _asmdef_name(raw: bytes, rel: str) -> str:
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SDKBindingError(f"{rel}: invalid asmdef JSON") from exc
    name = data.get("name") if isinstance(data, dict) else None
    if not isinstance(name, str) or not name.strip():
        raise SDKBindingError(f"{rel}: asmdef has no nonempty name")
    return name.strip()


def _nearest_asmdef(root: Path, rel: str, pinned_paths: set[str]) -> str:
    root = root.resolve()
    directory = (root / rel).parent.resolve()
    try:
        directory.relative_to(root)
    except ValueError as exc:
        raise SDKBindingError(f"{rel}: source directory escapes SDK root") from exc

    depth = 0
    while True:
        try:
            asmdefs = []
            asmrefs = []
            entry_count = 0
            for entry in directory.iterdir():
                entry_count += 1
                if entry_count > _MAX_ASSEMBLY_SCOPE_ENTRIES:
                    raise SDKBindingError(f"{rel}: assembly scope entry budget exceeded at {directory}")
                if not entry.is_file():
                    continue
                if entry.name.endswith(".asmdef"):
                    asmdefs.append(entry)
                elif entry.name.endswith(".asmref"):
                    asmrefs.append(entry)
        except OSError as exc:
            raise SDKBindingError(f"{rel}: cannot inspect SDK assembly scope {directory}") from exc
        actual_asmdefs = sorted(asmdefs)
        actual_asmrefs = sorted(asmrefs)
        if actual_asmrefs:
            raise SDKBindingError(f"{rel}: asmref assembly scope is unsupported: {actual_asmrefs[0].name}")
        if actual_asmdefs:
            if len(actual_asmdefs) != 1:
                raise SDKBindingError(f"{rel}: multiple asmdefs in nearest assembly directory")
            actual = actual_asmdefs[0]
            candidate = actual.relative_to(root).as_posix()
            if candidate not in pinned_paths:
                raise SDKBindingError(f"{rel}: nearest asmdef is not pinned: {candidate}")
            return candidate
        if directory == root:
            break
        depth += 1
        if depth > _MAX_ASSEMBLY_SCOPE_DEPTH:
            raise SDKBindingError(f"{rel}: assembly scope ancestor depth exceeds budget")
        directory = directory.parent
    raise SDKBindingError(f"{rel}: no actual parent asmdef proves the target assembly within SDK root")


def plan_sdk_script_bindings(
    scripts: Iterable[Mapping[str, Any]],
    *,
    sdk_root: str | Path,
    pinned_files: Mapping[str, str],
    native_types: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Return deterministic source-to-SDK MonoScript tuple plans.

    Each script row has ``identity`` (assembly/namespace/class) and ``sourceTuple``
    (guid/fileID and optional type). ``pinned_files`` maps relative SDK paths to
    their expected SHA256; only those exact files are read. Native types, if any,
    are exact full identities in a separate table and produce no SDK GUID mapping.
    """
    root = Path(sdk_root)
    if not root.is_dir():
        raise SDKBindingError("sdk_root must be an existing SDK directory")
    if not isinstance(pinned_files, Mapping) or not pinned_files:
        raise SDKBindingError("pinned_files must be a nonempty path-to-SHA256 map")
    if len(pinned_files) > _MAX_PINNED_FILES:
        raise SDKBindingError(f"pinned file count exceeds budget of {_MAX_PINNED_FILES}")

    pin_bytes: dict[str, bytes] = {}
    pinned_total_bytes = 0
    for rel, digest in pinned_files.items():
        if rel in pin_bytes:
            raise SDKBindingError(f"duplicate pinned path: {rel}")
        raw = _read_pin(root, rel, digest, label="SDK pin")
        pinned_total_bytes += len(raw)
        if pinned_total_bytes > _MAX_PINNED_TOTAL_BYTES:
            raise SDKBindingError(f"pinned file bytes exceed budget of {_MAX_PINNED_TOTAL_BYTES}")
        pin_bytes[rel] = raw
    pinned_paths = set(pin_bytes)

    asmdefs: dict[str, str] = {}
    for rel, raw in pin_bytes.items():
        if rel.endswith(".asmdef"):
            asmdefs[rel] = _asmdef_name(raw, rel)

    declarations: list[dict[str, Any]] = []
    for rel, raw in pin_bytes.items():
        if not rel.endswith(".cs"):
            continue
        meta_rel = rel + ".meta"
        if meta_rel not in pin_bytes:
            raise SDKBindingError(f"{rel}: matching pinned .meta is required for GUID evidence")
        asmdef = _nearest_asmdef(root, rel, pinned_paths)
        assembly = asmdefs.get(asmdef)
        if not assembly:
            raise SDKBindingError(f"{asmdef}: assembly evidence is unavailable")
        try:
            parsed = parse_declarations(raw.decode("utf-8"), assembly=assembly, source_path=rel, top_level_only=True)
        except (UnicodeDecodeError, ValueError) as exc:
            raise SDKBindingError(f"{rel}: cannot parse pinned C# declarations: {exc}") from exc
        guid = _guid_from_meta(pin_bytes[meta_rel], meta_rel)
        for declaration in parsed["declarations"]:
            # A MonoScript .meta identifies the script class matching the .cs
            # basename. Secondary and nested declarations in the same source
            # file do not each get an independent MonoScript GUID.
            if (declaration.get("kind") == "class"
                    and "+" not in declaration["identity"]["name"]
                    and declaration["identity"]["name"] == Path(rel).stem):
                declarations.append({
                    "identity": declaration["identity"],
                    "guid": guid,
                    "path": rel,
                    "assemblyDefinition": asmdef,
                    "assemblyDefinitionName": assembly,
                    "sourceSha256": hashlib.sha256(raw).hexdigest(),
                    "metaSha256": hashlib.sha256(pin_bytes[meta_rel]).hexdigest(),
                })

    guid_paths: dict[str, set[str]] = {}
    for declaration in declarations:
        guid_paths.setdefault(declaration["guid"], set()).add(declaration["path"])
    repeated_guids = {guid: paths for guid, paths in guid_paths.items() if len(paths) > 1}
    if repeated_guids:
        guid = sorted(repeated_guids)[0]
        raise SDKBindingError(f"duplicate target MonoScript GUID {guid}: {sorted(repeated_guids[guid])}")

    native_ids: set[tuple[str, str, str]] = set()
    for row in native_types:
        if not isinstance(row, Mapping):
            raise SDKBindingError("native_types entries must be exact identities")
        native_ids.add(_identity(row, "native type"))

    seen_sources: set[tuple[str, str, str, str, int]] = set()
    plans: list[dict[str, Any]] = []
    for index, row in enumerate(scripts):
        if not isinstance(row, Mapping):
            raise SDKBindingError(f"scripts[{index}]: expected object")
        identity = _identity(row.get("identity", {}), f"scripts[{index}]")
        original = row.get("sourceTuple")
        if not isinstance(original, Mapping):
            raise SDKBindingError(f"scripts[{index}]: sourceTuple is required")
        guid, file_id = original.get("guid"), original.get("fileID")
        if not isinstance(guid, str) or not _GUID.fullmatch(guid):
            raise SDKBindingError(f"scripts[{index}]: source tuple has invalid GUID")
        if isinstance(file_id, bool) or not isinstance(file_id, int):
            raise SDKBindingError(f"scripts[{index}]: source tuple fileID must be an integer")
        if "type" in original and (isinstance(original["type"], bool) or not isinstance(original["type"], int)):
            raise SDKBindingError(f"scripts[{index}]: source tuple type must be an integer when present")
        source_key = (*identity, guid.lower(), file_id)
        if source_key in seen_sources:
            raise SDKBindingError(f"scripts[{index}]: duplicate source type/GUID/fileID tuple")
        seen_sources.add(source_key)

        if identity in native_ids:
            plans.append({
                "identity": dict(assembly=identity[0], namespace=identity[1], **{"class": identity[2]}),
                "sourceTuple": dict(original),
                "status": "native_exact",
                "evidence": "explicit exact identity in native_types table",
                "expectedTuple": None,
            })
            continue

        same_full_name = [d for d in declarations
                          if d["identity"]["namespace"] == identity[1]
                          and d["identity"]["name"] == identity[2]]
        matches = [d for d in same_full_name
                   if _assembly_key(d["identity"]["assembly"]) == _assembly_key(identity[0])]
        if len(matches) != 1:
            if len(matches) > 1:
                reason = "duplicate target type declaration in pinned SDK files"
            elif same_full_name:
                reason = "target type exists only under a different assembly"
            else:
                reason = "target type has no declaration in pinned SDK files"
            raise SDKBindingError(f"{identity[0]}:{identity[1]}.{identity[2]}: {reason}")
        target = matches[0]
        target_tuple = {
            "guid": target["guid"],
            "fileID": _UNITY_SCRIPT_FILE_ID,
            "type": _UNITY_SCRIPT_OBJECT_TYPE,
        }
        plans.append({
            "identity": dict(assembly=identity[0], namespace=identity[1], **{"class": identity[2]}),
            "sourceTuple": dict(original),
            "status": "planned_sdk_binding",
            "targetSource": {k: target[k] for k in (
                "path", "guid", "assemblyDefinition", "assemblyDefinitionName", "sourceSha256", "metaSha256")},
            "expectedTuple": target_tuple,
            "verification": "expected tuple only; native AssetDatabase GUID/GetClass not run",
        })

    return {
        "schemaVersion": 1,
        "status": "offline_plan",
        "sdkRoot": str(root.resolve()),
        "pinnedFileCount": len(pin_bytes),
        "declarationCount": len(declarations),
        "bindings": plans,
        "nativeGetClassVerified": False,
    }
