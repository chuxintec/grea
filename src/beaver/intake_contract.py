"""Closed, bounded contract for additive Unity asset intake.

This module validates only the declarative intake specification. It does not
inspect Unity projects, resolve compiler inputs, or perform filesystem writes.
"""

import math
import re
import unicodedata

from .errors import fail


_TOP_KEYS = {
    "schemaVersion", "operation", "candidateManifestSha256", "additions",
    "externalScripts", "omittedCompilerInputs", "verifications",
    "protectedAssets", "evidence",
}
_ASSET_EXTENSIONS = {".prefab", ".asset", ".mat", ".png", ".ttf", ".otf", ".shader", ".txt", ".json"}
_EXTERNAL_ASSET_EXTENSIONS = _ASSET_EXTENSIONS - {".prefab"}
_COMPILER_EXTENSIONS = {".cs", ".asmdef", ".asmref", ".rsp"}
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_GUID = re.compile(r"[0-9a-f]{32}\Z")
_INT64_MIN, _INT64_MAX = -(1 << 63), (1 << 63) - 1
_WIN_BAD = set('<>:"|?*')
_WIN_RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?\Z", re.IGNORECASE)
_SEMVER = re.compile(
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"(?:-(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?\Z"
)


def _bad(where, message, suffix="INVALID"):
    fail("INTAKE_SPEC_" + suffix, where, message)


def _exact(value, keys, where):
    if not isinstance(value, dict):
        _bad(where, "Object required")
    if set(value) != set(keys):
        missing = sorted(set(keys) - set(value))
        extra = sorted(set(value) - set(keys))
        _bad(where, f"Exact fields required (missing={missing}, extra={extra})", "FIELDS")


def _array(value, where, minimum=0, maximum=None):
    if not isinstance(value, list) or len(value) < minimum or (maximum is not None and len(value) > maximum):
        bound = f"{minimum}..{maximum}" if maximum is not None else f"at least {minimum}"
        _bad(where, f"Array with {bound} entries required", "BOUNDS")
    return value


def _string(value, where, *, nonempty=True, max_length=None):
    if not isinstance(value, str) or (nonempty and not value) or (max_length is not None and len(value) > max_length):
        _bad(where, "String value outside the permitted bounds", "TYPE")
    try:
        value.encode("utf-8")
    except UnicodeError:
        _bad(where, "Unicode scalar values required", "UNICODE")
    return value


def _hash(value, where):
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        _bad(where, "Lowercase 64-character SHA-256 required", "HASH")


def _guid(value, where):
    if not isinstance(value, str) or not _GUID.fullmatch(value):
        _bad(where, "Lowercase 32-character Unity GUID required", "GUID")


def _int64(value, where, *, nonzero=False):
    if isinstance(value, bool) or not isinstance(value, int) or not _INT64_MIN <= value <= _INT64_MAX or (nonzero and value == 0):
        _bad(where, "Signed 64-bit integer required" + (" (nonzero)" if nonzero else ""), "INTEGER")


def _asset_path(value, where, extensions, *, require_asset_root=True):
    _string(value, where)
    if "\\" in value or value.startswith("/") or ":" in value or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        _bad(where, "Canonical project-relative path required", "PATH")
    if unicodedata.normalize("NFC", value) != value:
        _bad(where, "Path must already be Unicode NFC", "PATH")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        _bad(where, "Empty, dot, and parent path components are forbidden", "PATH")
    if require_asset_root and (len(parts) < 2 or parts[0] != "Assets"):
        _bad(where, "Path must be rooted under Assets/", "PATH")
    for part in parts:
        if part.endswith((".", " ")) or any(ch in _WIN_BAD for ch in part) or _WIN_RESERVED.fullmatch(part):
            _bad(where, "Windows-invalid or aliased path component", "PATH")
    if value.lower().endswith(".meta"):
        _bad(where, "Unity .meta files are not asset paths", "PATH")
    suffix = value.rsplit("/", 1)[-1]
    if "." not in suffix or "." + suffix.rsplit(".", 1)[-1].lower() not in extensions:
        _bad(where, "File extension is outside the contract allowlist", "EXTENSION")
    return value


def _unique(values, where):
    seen = {}
    for value in values:
        key = unicodedata.normalize("NFC", value).casefold()
        if key in seen:
            _bad(where, f"Duplicate or case/Unicode alias of {seen[key]!r}: {value!r}", "DUPLICATE")
        seen[key] = value


def _unique_exact(values, where):
    seen = set()
    for value in values:
        if value in seen:
            _bad(where, f"Duplicate value: {value!r}", "DUPLICATE")
        seen.add(value)


def _simple_assembly(value, where):
    _string(value, where)
    if (not re.fullmatch(r"[A-Za-z0-9_.-]+", value) or value in (".", "..")
            or value.lower().endswith(".dll")):
        _bad(where, "Simple assembly name required; paths and .dll suffixes are forbidden", "ASSEMBLY")


def _field_value(kind, value, where):
    if kind == "integer":
        _int64(value, where)
    elif kind == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            _bad(where, "Finite numeric value required", "VALUE")
    elif kind == "boolean":
        if type(value) is not bool:
            _bad(where, "Boolean value required", "VALUE")
    elif kind == "string":
        _string(value, where, nonempty=False, max_length=16384)
    elif kind == "object":
        _exact(value, {"guid", "localId", "type", "assembly"}, where)
        guid, local_id, obj_type, assembly = (value[k] for k in ("guid", "localId", "type", "assembly"))
        if (guid, local_id, obj_type, assembly) == ("", 0, "", ""):
            return
        _guid(guid, where + ".guid")
        _int64(local_id, where + ".localId", nonzero=True)
        _string(obj_type, where + ".type")
        _simple_assembly(assembly, where + ".assembly")
    elif kind == "character":
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 65535:
            _bad(where, "UTF-16 code unit integer in 0..65535 required", "VALUE")
    else:
        _bad(where, "Field kind must be integer, float, boolean, string, or object", "ENUM")


def _owner_rows(objects, where, total_fields=None, allow_character=False):
    """Validate typed native owner observations; optionally enforce a shared field budget."""
    local_ids = []
    for obj_index, obj in enumerate(objects):
        obj_where = f"{where}[{obj_index}]"
        _exact(obj, {"localId", "type", "assembly", "name", "fields"}, obj_where)
        _int64(obj["localId"], obj_where + ".localId", nonzero=True)
        local_ids.append(obj["localId"])
        _string(obj["type"], obj_where + ".type")
        _simple_assembly(obj["assembly"], obj_where + ".assembly")
        _string(obj["name"], obj_where + ".name", nonempty=False)
        fields = _array(obj["fields"], obj_where + ".fields")
        if total_fields is not None:
            total_fields += len(fields)
            if total_fields > 250000:
                _bad(where, "Combined field count exceeds 250000", "BOUNDS")
        property_paths = []
        for field_index, field in enumerate(fields):
            field_where = f"{obj_where}.fields[{field_index}]"
            _exact(field, {"propertyPath", "kind", "value"}, field_where)
            property_paths.append(_string(field["propertyPath"], field_where + ".propertyPath"))
            kind = _string(field["kind"], field_where + ".kind")
            if kind == "character" and not allow_character:
                _bad(field_where + ".kind", "character kind is available only in schemaVersion 3", "ENUM")
            _field_value(kind, field["value"], field_where + ".value")
        _unique(property_paths, obj_where + ".fields.propertyPath")
    _unique([str(v) for v in local_ids], where + ".localId")
    return total_fields


def _csharp_identifier(value, where):
    _string(value, where)
    if not value:
        _bad(where, "C# identifier required", "IDENTIFIER")
    def start(ch):
        category = unicodedata.category(ch)
        return ch == "_" or category in {"Lu", "Ll", "Lt", "Lm", "Lo", "Nl"}
    def part(ch):
        category = unicodedata.category(ch)
        return start(ch) or category in {"Mn", "Mc", "Nd", "Pc", "Cf"}
    if not start(value[0]) or any(not part(ch) for ch in value[1:]):
        _bad(where, "C# identifier required", "IDENTIFIER")
    return value


def validate_spec(doc):
    """Validate and return a v1, v2 or v3 additive intake spec without normalization."""
    if not isinstance(doc, dict):
        _bad("$", "Object required")
    version = doc.get("schemaVersion")
    if type(version) is not int or version not in (1, 2, 3):
        _bad("schemaVersion", "schemaVersion 1, 2, or 3 required", "VERSION")
    keys = _TOP_KEYS if version == 1 else _TOP_KEYS | {"externalAssets", "packageScripts"}
    if version == 3:
        keys = keys | {"newScripts"}
    _exact(doc, keys, "$")
    if doc["operation"] != "additive-intake":
        _bad("operation", "operation must be additive-intake", "OPERATION")
    _hash(doc["candidateManifestSha256"], "candidateManifestSha256")

    additions = _array(doc["additions"], "additions", 1, 256)
    addition_sources, addition_targets, prefab_sources = [], [], set()
    for index, item in enumerate(additions):
        where = f"additions[{index}]"
        _exact(item, {"source", "target"}, where)
        source = _asset_path(item["source"], where + ".source", _ASSET_EXTENSIONS)
        target = _asset_path(item["target"], where + ".target", _ASSET_EXTENSIONS)
        if source.rsplit(".", 1)[-1].casefold() != target.rsplit(".", 1)[-1].casefold():
            _bad(where, "Source and target extensions must match", "EXTENSION")
        addition_sources.append(source)
        addition_targets.append(target)
        if source.lower().endswith(".prefab"):
            prefab_sources.add(source)
    _unique(addition_sources, "additions.source")
    _unique(addition_targets, "additions.target")

    external = _array(doc["externalScripts"], "externalScripts")
    ext_sources, ext_targets, ext_guids = [], [], []
    ext_source_set = set()
    ext_keys = {"source", "sourceGuid", "sourceType", "sourceAssembly", "target", "targetGuid", "targetType", "targetAssembly", "targetLocalId", "targetSha256", "targetMetaSha256", "reason"}
    for index, item in enumerate(external):
        where = f"externalScripts[{index}]"
        _exact(item, ext_keys, where)
        source = _asset_path(item["source"], where + ".source", {".cs"})
        target = _asset_path(item["target"], where + ".target", {".cs"})
        _guid(item["sourceGuid"], where + ".sourceGuid")
        _guid(item["targetGuid"], where + ".targetGuid")
        if item["sourceGuid"] != item["targetGuid"]:
            _bad(where, "v1 preserves serialized m_Script references; source and target GUIDs must match", "GUID")
        _string(item["sourceType"], where + ".sourceType")
        _string(item["targetType"], where + ".targetType")
        if item["sourceType"] != item["targetType"]:
            _bad(where, "Reused external script type must remain identical", "TYPE")
        _simple_assembly(item["sourceAssembly"], where + ".sourceAssembly")
        _simple_assembly(item["targetAssembly"], where + ".targetAssembly")
        _int64(item["targetLocalId"], where + ".targetLocalId", nonzero=True)
        _hash(item["targetSha256"], where + ".targetSha256")
        _hash(item["targetMetaSha256"], where + ".targetMetaSha256")
        _string(item["reason"], where + ".reason")
        ext_sources.append(source); ext_targets.append(target); ext_guids.append(item["sourceGuid"])
        ext_source_set.add(source)
    _unique(ext_sources, "externalScripts.source")
    _unique(ext_targets, "externalScripts.target")
    _unique(ext_guids, "externalScripts.guid")
    addition_path_keys = {p.casefold() for p in addition_sources + addition_targets}
    if any(p.casefold() in addition_path_keys for p in ext_sources + ext_targets):
        _bad("externalScripts", "External script paths cannot overlap addition sources or targets", "OVERLAP")

    omitted = _array(doc["omittedCompilerInputs"], "omittedCompilerInputs")

    verifications = _array(doc["verifications"], "verifications")
    verified_assets, total_fields = [], 0
    for index, item in enumerate(verifications):
        where = f"verifications[{index}]"
        _exact(item, {"asset", "objects"}, where)
        asset = _asset_path(item["asset"], where + ".asset", {".prefab"})
        if asset not in prefab_sources:
            _bad(where + ".asset", "Verification asset must match an additions.source prefab", "REFERENCE")
        verified_assets.append(asset)
        objects = _array(item["objects"], where + ".objects", 1, 4096)
        total_fields = _owner_rows(objects, where + ".objects", total_fields, allow_character=(version == 3))
    _unique(verified_assets, "verifications.asset")

    external_asset_sources, external_asset_targets, external_asset_guids = [], [], []
    external_asset_paths = set()
    package_guids = []
    if version in (2, 3):
        external_assets = _array(doc["externalAssets"], "externalAssets", maximum=256)
        total_asset_objects = 0
        for index, item in enumerate(external_assets):
            where = f"externalAssets[{index}]"
            _exact(item, {"source", "target", "guid", "sha256", "metaSha256", "objects", "reason"}, where)
            source = _asset_path(item["source"], where + ".source", _EXTERNAL_ASSET_EXTENSIONS)
            target = _asset_path(item["target"], where + ".target", _EXTERNAL_ASSET_EXTENSIONS)
            if source.rsplit(".", 1)[-1].casefold() != target.rsplit(".", 1)[-1].casefold():
                _bad(where, "Source and target extensions must match", "EXTENSION")
            _guid(item["guid"], where + ".guid")
            _hash(item["sha256"], where + ".sha256")
            _hash(item["metaSha256"], where + ".metaSha256")
            _string(item["reason"], where + ".reason")
            objects = _array(item["objects"], where + ".objects", 1, 4096)
            total_asset_objects += len(objects)
            if total_asset_objects > 4096:
                _bad("externalAssets", "Combined object count exceeds 4096", "BOUNDS")
            total_fields = _owner_rows(objects, where + ".objects", total_fields, allow_character=(version == 3))
            external_asset_sources.append(source)
            external_asset_targets.append(target)
            external_asset_guids.append(item["guid"])
        _unique(external_asset_sources, "externalAssets.source")
        _unique(external_asset_targets, "externalAssets.target")
        _unique(external_asset_guids, "externalAssets.guid")
        external_asset_paths = {p.casefold() for p in external_asset_sources + external_asset_targets}
        if external_asset_paths & addition_path_keys:
            _bad("externalAssets", "External asset paths cannot overlap addition sources or targets", "OVERLAP")
        if external_asset_paths & {p.casefold() for p in ext_sources + ext_targets}:
            _bad("externalAssets", "External asset paths cannot overlap external script paths", "OVERLAP")
        if set(external_asset_guids) & set(ext_guids):
            _bad("externalAssets", "External asset GUID cannot overlap an external script GUID", "OVERLAP")

        package_scripts = _array(doc["packageScripts"], "packageScripts", maximum=64)
        package_targets = []
        for index, item in enumerate(package_scripts):
            where = f"packageScripts[{index}]"
            _exact(item, {"target", "guid", "type", "assembly", "localId", "name", "packageName", "packageVersion", "packageSource", "packageJsonSha256", "sha256", "metaSha256", "reason"}, where)
            target = _asset_path(item["target"], where + ".target", {".cs"}, require_asset_root=False)
            prefix = "Packages/com.unity.ugui/Runtime/"
            if not target.startswith(prefix):
                _bad(where + ".target", "Package script must be under the uGUI Runtime package", "PATH")
            _guid(item["guid"], where + ".guid")
            _string(item["type"], where + ".type")
            if not item["type"].startswith("UnityEngine.UI.") or len(item["type"]) == len("UnityEngine.UI."):
                _bad(where + ".type", "uGUI package script type must start with UnityEngine.UI.", "TYPE")
            if item["assembly"] != "UnityEngine.UI":
                _bad(where + ".assembly", "uGUI package assembly must be UnityEngine.UI", "ASSEMBLY")
            _int64(item["localId"], where + ".localId", nonzero=True)
            _string(item["name"], where + ".name", nonempty=False)
            if item["packageName"] != "com.unity.ugui":
                _bad(where + ".packageName", "Only com.unity.ugui package scripts are supported", "PACKAGE")
            version_string = _string(item["packageVersion"], where + ".packageVersion")
            if not _SEMVER.fullmatch(version_string):
                _bad(where + ".packageVersion", "Strict semantic version required", "PACKAGE")
            if item["packageSource"] not in ("registry", "builtin"):
                _bad(where + ".packageSource", "packageSource must be registry or builtin", "PACKAGE")
            _hash(item["packageJsonSha256"], where + ".packageJsonSha256")
            _hash(item["sha256"], where + ".sha256")
            _hash(item["metaSha256"], where + ".metaSha256")
            _string(item["reason"], where + ".reason")
            package_targets.append(target)
            package_guids.append(item["guid"])
        _unique(package_targets, "packageScripts.target")
        _unique(package_guids, "packageScripts.guid")
        if set(package_guids) & (set(ext_guids) | set(external_asset_guids)):
            _bad("packageScripts", "Package script GUID cannot overlap an external script or asset GUID", "OVERLAP")

    new_script_sources, new_script_targets, new_script_guids, new_script_types = [], [], [], []
    new_script_paths = set()
    if version == 3:
        new_scripts = _array(doc["newScripts"], "newScripts", maximum=16)
        keys = {"source", "target", "guid", "sha256", "metaSha256", "sourceType", "sourceAssembly", "targetType", "targetAssembly", "baseType", "baseAssembly", "localId", "fields", "reason"}
        for index, item in enumerate(new_scripts):
            where = f"newScripts[{index}]"
            _exact(item, keys, where)
            source = _asset_path(item["source"], where + ".source", {".cs"})
            target = _asset_path(item["target"], where + ".target", {".cs"})
            if any(part.casefold() == "editor" for part in target.split("/")[1:-1]):
                _bad(where + ".target", "New script target cannot be inside an Editor directory", "PATH")
            _guid(item["guid"], where + ".guid")
            _hash(item["sha256"], where + ".sha256")
            _hash(item["metaSha256"], where + ".metaSha256")
            source_type = _string(item["sourceType"], where + ".sourceType")
            target_type = _string(item["targetType"], where + ".targetType")
            if source_type != target_type:
                _bad(where, "Frozen source and target script types must match", "TYPE")
            class_name = target_type.rsplit(".", 1)[-1]
            _csharp_identifier(class_name, where + ".targetType")
            target_stem = target.rsplit("/", 1)[-1][:-3]
            if target_stem != class_name:
                _bad(where + ".target", "Target filename must match the target type's final class name", "TYPE")
            _simple_assembly(item["sourceAssembly"], where + ".sourceAssembly")
            if item["targetAssembly"] != "Assembly-CSharp":
                _bad(where + ".targetAssembly", "New scripts must target Assembly-CSharp", "ASSEMBLY")
            _string(item["baseType"], where + ".baseType")
            _simple_assembly(item["baseAssembly"], where + ".baseAssembly")
            _int64(item["localId"], where + ".localId", nonzero=True)
            fields = _array(item["fields"], where + ".fields", maximum=128)
            field_names = []
            for field_index, field in enumerate(fields):
                field_where = f"{where}.fields[{field_index}]"
                _exact(field, {"name", "type", "assembly"}, field_where)
                field_names.append(_csharp_identifier(field["name"], field_where + ".name"))
                _string(field["type"], field_where + ".type")
                _simple_assembly(field["assembly"], field_where + ".assembly")
            _unique_exact(field_names, where + ".fields.name")
            _string(item["reason"], where + ".reason")
            new_script_sources.append(source)
            new_script_targets.append(target)
            new_script_guids.append(item["guid"])
            new_script_types.append(target_type)
            row_paths = {source.casefold(), target.casefold()}
            if new_script_paths & row_paths:
                _bad(where, "New script paths cannot overlap paths from another newScripts row", "OVERLAP")
            new_script_paths.update(row_paths)

        _unique(new_script_sources, "newScripts.source")
        _unique(new_script_targets, "newScripts.target")
        _unique(new_script_guids, "newScripts.guid")
        _unique_exact(new_script_types, "newScripts.type")
        other_paths = addition_path_keys | {p.casefold() for p in ext_sources + ext_targets} | external_asset_paths
        if new_script_paths & other_paths:
            _bad("newScripts", "New script paths cannot overlap additions, external scripts, or external assets", "OVERLAP")
        if set(new_script_guids) & (set(ext_guids) | set(external_asset_guids) | set(package_guids)):
            _bad("newScripts", "New script GUID cannot overlap external script, external asset, or package script GUID", "OVERLAP")

    omitted_paths = []
    add_source_keys = {p.casefold() for p in addition_sources}
    external_script_sources = ext_source_set | set(new_script_sources)
    external_script_path_keys = {p.casefold() for p in ext_sources + new_script_sources}
    for index, item in enumerate(omitted):
        where = f"omittedCompilerInputs[{index}]"
        _exact(item, {"path", "reason", "coveredByExternalScript"}, where)
        path = _asset_path(item["path"], where + ".path", _COMPILER_EXTENSIONS)
        _string(item["reason"], where + ".reason")
        covered = _string(item["coveredByExternalScript"], where + ".coveredByExternalScript")
        if covered not in external_script_sources:
            _bad(where + ".coveredByExternalScript", "Must name a declared externalScripts.source or newScripts.source", "REFERENCE")
        if path.casefold() in add_source_keys or path.casefold() in external_script_path_keys:
            _bad(where + ".path", "Omitted compiler input cannot overlap an addition or declared script source", "OVERLAP")
        omitted_paths.append(path)
    _unique(omitted_paths, "omittedCompilerInputs.path")

    protected = _array(doc["protectedAssets"], "protectedAssets")
    protected_paths = []
    target_keys = {p.casefold() for p in addition_targets}
    for index, item in enumerate(protected):
        where = f"protectedAssets[{index}]"
        _exact(item, {"path", "sha256", "metaSha256"}, where)
        path = _asset_path(item["path"], where + ".path", _ASSET_EXTENSIONS)
        _hash(item["sha256"], where + ".sha256")
        _hash(item["metaSha256"], where + ".metaSha256")
        if path.casefold() in target_keys:
            _bad(where + ".path", "Protected asset cannot also be an addition target", "OVERLAP")
        protected_paths.append(path)
    _unique(protected_paths, "protectedAssets.path")

    evidence = _array(doc["evidence"], "evidence")
    evidence_paths = []
    for index, item in enumerate(evidence):
        where = f"evidence[{index}]"
        _exact(item, {"path", "sha256"}, where)
        path = _string(item["path"], where + ".path")
        components = path.split("/")[1:] if path.startswith("/") else []
        if (not path.startswith("/") or path.startswith("//") or "\\" in path
                or any(part in ("", ".", "..") for part in components)
                or any(ord(ch) < 32 or ord(ch) == 127 for ch in path)):
            _bad(where + ".path", "Canonical absolute evidence path required", "PATH")
        if unicodedata.normalize("NFC", path) != path:
            _bad(where + ".path", "Path must already be Unicode NFC", "PATH")
        _hash(item["sha256"], where + ".sha256")
        evidence_paths.append(path)
    _unique(evidence_paths, "evidence.path")

    return doc
