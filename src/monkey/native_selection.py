"""Freeze a selected Unity Prefab dependency closure after native save.

This is intentionally a bounded handoff builder, not a general C# analyzer. YAML
asset references are resolved by GUID and the small generated runtime graph below
is producer-declared for the current static-sort templates.
"""
from __future__ import annotations

import re
import tempfile
import posixpath
from pathlib import Path, PurePosixPath

from .io import encoded, inside, load, new_output, read, safe, sha, write_json
from .sources.compiled import fail
from .unity_verification_contract import NATIVE_IMPORT_STATUSES, SAVED_SOURCE_SCOPES

_GUID_REF = re.compile(r"\bguid:\s*([0-9a-fA-F]{32})\b")
_ZERO_GUIDS = {"0" * 32, "0" * 16 + "e000000000000000"}
_DYNAMIC_ONLY = {"SPINE_DYNAMIC_BEHAVIOR_INCOMPLETE", "ANIMATION_DYNAMIC_CURVES_NOT_LOWERED"}
_BUILTIN_SHADER_INCLUDES = {'UnityCG.cginc', 'UnityUI.cginc', 'HLSLSupport.cginc',
    'UnityShaderVariables.cginc', 'Lighting.cginc', 'AutoLight.cginc', 'UnityPBSLighting.cginc',
    'UnityStandardUtils.cginc', 'UnityStandardBRDF.cginc', 'UnityStandardConfig.cginc'}


def _shader_include_paths(raw, path, root):
    if PurePosixPath(path).suffix not in {'.shader', '.cginc', '.hlsl', '.compute'}:
        return [], []
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        fail('SHADER_INCLUDE_UNSUPPORTED', path, 'Shader source is not UTF-8 text')
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    project, builtin = [], []
    for line in text.splitlines():
        if not re.match(r'^\s*#\s*include(?:_with_pragmas)?\b', line): continue
        match = re.match(r'^\s*#\s*include(?:_with_pragmas)?\s*["<]([^">]+)[">]', line)
        if not match:
            fail('SHADER_INCLUDE_UNSUPPORTED', path, 'Only literal include paths have a frozen closure')
        include = match[1]
        if '\\' in include or include.startswith('/') or ':' in include:
            fail('SHADER_INCLUDE_UNSAFE', path, 'Shader include path is not project-relative')
        relative = posixpath.normpath(include if include.startswith('Assets/') else
            posixpath.join(posixpath.dirname(path), include))
        if relative.startswith('Assets/') and (root / relative).is_file():
            project.append(_relative(relative, path))
        elif include in _BUILTIN_SHADER_INCLUDES:
            builtin.append(include)
        else:
            fail('SHADER_INCLUDE_UNRESOLVED', path, 'No frozen project include or declared Unity built-in: ' + include)
    return sorted(set(project)), sorted(set(builtin))

# The old v0.7.0.dev1 Presenter/Graphic templates are pinned as historical
# producer identities. Current templates are accepted only when their bytes
# match the corresponding source bundled with this exact monkey checkout.
_LEGACY_TEMPLATE_PROFILES = {
    "1187615f570d8656835fa7db90cddbe56f4648ec6d3e2ebaab6731bca8a1a348": (
        "NativeStaticSortQueueProxyPresenter.cs",
        ("NativeStaticSortQueueProxyMarker.cs", "NativeStaticSortQueueProxyGraphic.cs",
         "NativeInputBlocker.cs", "NativeInputBlockerSurface.cs")),
    "3dd77464106afce1e1438cd62af16453427372530db92c2406ab2929887bbcb3":
        ("NativeStaticSortQueueProxyGraphic.cs", ()),
    "aa54cccc69d675ea69f15b8ccf40d0ae1ca0d21837d6a5dc68f9b3f88f4610d3":
        ("NativeStaticButtonTarget.cs", ()),
}
_CURRENT_TEMPLATE_DEPENDENCIES = {
    "NativeStaticSortQueueProxyPresenter.cs": (
        "NativeStaticSortQueueProxyMarker.cs", "NativeStaticSortQueueProxyGraphic.cs",
        "NativeInputBlocker.cs", "NativeInputBlockerSurface.cs", "NativeStaticSortQueueRuntime.cs"),
    "NativeStaticSortQueueRuntime.cs": (
        "NativeStaticSortQueueProxyPresenter.cs", "NativeStaticSortQueueProxyGraphic.cs",
        "NativeStaticSortTextSource.cs", "NativeStaticSortQueueProxyRaycaster.cs",
        "NativeStaticSortInputSurface.cs", "NativeStaticButtonTargetContract.cs"),
    "NativeStaticSortQueueProxyRaycaster.cs": (
        "NativeStaticSortQueueProxyPresenter.cs", "NativeStaticSortQueueProxyGraphic.cs",
        "NativeStaticSortInputSurface.cs"),
    "NativeStaticSortInputSurface.cs": (),
    "NativeStaticButtonTarget.cs": ("NativeStaticButtonTargetContract.cs",),
    "NativeStaticButtonTargetContract.cs": (),
    "NativeStaticSortQueueProxyGraphic.cs": (),
    "NativeStaticSortQueueProxyMarker.cs": ("NativeStaticSortQueueProxyPresenter.cs",),
    "NativeStaticSortTextSource.cs": (),
    "NativeInputBlocker.cs": ("NativeInputBlockerSurface.cs",),
    "NativeInputBlockerSurface.cs": (),
    # These exact bundled sources depend only on framework/locked uGUI types.
    # NativeChildLayoutGroup is declared in NativeLinearLayoutGroup.cs itself.
    "NativeLinearLayoutGroup.cs": (),
    "NativeTextLineBox.cs": (),
    "NativeStaticLabelStyle.cs": (),
    "NativeStaticAnimationBinding.cs": (),
    "NativeStaticSpineReference.cs": ("NativeStaticSpineData.cs", "NativeRetainedMaterial.cs"),
    "NativeStaticSpineData.cs": (),
    "NativeRetainedMaterial.cs": (),
    "NativeHorizontalProgressFill.cs": (),
    "UnitySpineGraphicMaterialPresentation.cs": ("NativeStaticMaskIdentity.cs",),
    "UnitySpineSourceIdentity.cs": (),
    "NativeStaticMaskIdentity.cs": (),
}


def _template_profile(path, digest):
    legacy = _LEGACY_TEMPLATE_PROFILES.get(digest)
    if legacy:
        return legacy
    name = PurePosixPath(path).name
    dependencies = _CURRENT_TEMPLATE_DEPENDENCIES.get(name)
    if dependencies is None:
        return None
    template_root = Path(__file__).parent / "targets"
    if name in {"UnitySpineGraphicMaterialPresentation.cs", "UnitySpineSourceIdentity.cs"}:
        template_root = template_root / "spine"
    template = template_root / name
    if not template.is_file() or sha(read(template, max_bytes=16 * 1024 * 1024)) != digest:
        return None
    return name, dependencies


def _carrier_profiles(root, rows, manifest):
    """Recognize generated carriers by exact regeneration from the owned plan.

    This is a producer proof, not C# parsing or a filename-based exemption.
    """
    from .layout import standard
    from .prefab_static_carriers import _unity_script
    plan_path = standard.locate(manifest, "importPlan")
    row = rows.get(plan_path)
    if row is None:
        return {}, None
    digest, size, raw = _hash_file(root, plan_path)
    if digest != row["sha256"] or size != row["bytes"]:
        fail("IMPORT_PLAN_DRIFT", plan_path, "Carrier proof requires the original manifest-owned plan")
    plan = load(raw, max_nodes=8_000_000)
    profiles = {}
    identifier = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
    def safe_identifier(value):
        return isinstance(value, str) and identifier.fullmatch(value) is not None
    for component in plan.get("components", []):
        spec = component.get("staticFieldBinding") or {}
        path = spec.get("scriptPath")
        if path not in rows or spec.get("behavior") != "disabled" or spec.get("enabled") is not False:
            continue
        typename = spec.get("typeName", "")
        if not isinstance(typename, str) or not all(safe_identifier(part) for part in typename.split(".")):
            continue
        namespace, _, name = typename.rpartition(".")
        if not namespace or PurePosixPath(path).name != name + ".cs":
            continue
        fields = spec.get("fields")
        if not isinstance(fields, list):
            continue
        valid = True
        for field in fields:
            if not isinstance(field, dict):
                valid = False; break
            record_schema = field.get("recordSchema") or []
            if not isinstance(record_schema, list):
                valid = False; break
            for member in [field, *record_schema]:
                if not isinstance(member, dict) or not safe_identifier(member.get("fieldName")):
                    valid = False; break
                record_name = member.get("recordTypeName")
                if record_name is not None and not safe_identifier(record_name):
                    valid = False; break
                if member.get("storageType") == "Color" and any(
                    type(member.get(key)) is not int or not 0 <= member[key] <= 255
                    for key in ("colorR", "colorG", "colorB", "colorA")):
                    valid = False; break
        if not valid:
            continue
        try:
            generated = _unity_script(namespace, name, fields).encode("utf-8")
        except (ValueError, KeyError, TypeError):
            continue
        generated_sha = sha(generated)
        if generated_sha == rows[path]["sha256"] == spec.get("scriptSha256"):
            profiles[path] = (name + ".cs", ())
    return profiles, dict(path=plan_path, sha256=digest, bytes=size,
        profile="exact-generated-disabled-static-field-carrier", behaviorRecovered=False)


def _read_json(path, max_bytes=128 * 1024 * 1024):
    return load(read(path, max_bytes=max_bytes), max_nodes=8_000_000)


def _relative(value, location):
    if (not isinstance(value, str) or not value or "\\" in value
            or PurePosixPath(value).is_absolute()
            or any(p in ("", ".", "..") for p in value.split("/"))
            or ":" in value or any(ord(ch) < 32 for ch in value)):
        fail("UNSAFE_PATH", location, "Expected a canonical project-relative path")
    return value


def _hash_file(root, relative):
    path = inside(root, relative)
    if not path.is_file():
        fail("SELECTION_FILE_MISSING", relative, "Required candidate file is missing")
    raw = read(path, max_bytes=256 * 1024 * 1024)
    return sha(raw), len(raw), raw


def _guid_meta(path):
    try:
        text = read(path, max_bytes=2 * 1024 * 1024).decode("utf-8")
    except (UnicodeDecodeError, OSError):
        return None
    match = re.search(r"(?m)^guid:\s*([0-9a-fA-F]{32})\s*$", text)
    return match.group(1).lower() if match else None


def _native_verification(root, output, expected_manifest, expected_readback):
    """Use Unity's existing full verifier, keeping its report outside the output."""
    rb_path = inside(root, "Analysis/Readback/editor-readback.json")
    rb_raw = read(rb_path, max_bytes=128 * 1024 * 1024)
    if sha(rb_raw) != expected_readback:
        fail("READBACK_SHA_MISMATCH", str(rb_path), "Readback differs from the pinned SHA256")
    rb = load(rb_raw, max_nodes=8_000_000)
    if (rb.get("unityVersion") != "6000.6.2f1" or type(rb.get("missingScripts")) is not int or rb.get("missingScripts") != 0
            or rb.get("status") not in NATIVE_IMPORT_STATUSES
            or rb.get("nativeScope") not in SAVED_SOURCE_SCOPES
            or rb.get("sourceGraphVerification") != "saved-source-node-subset"):
        fail("NATIVE_READBACK_INVALID", str(rb_path), "Unity version, import status, missing-script count or saved source-graph scope is invalid")
    native_files = rb.get("nativeFiles")
    if not isinstance(native_files, list) or not native_files:
        fail("NATIVE_READBACK_INCOMPLETE", str(rb_path), "Native saved-file inventory is empty")
    seen = set()
    for row in native_files:
        if not isinstance(row, dict):
            fail("NATIVE_READBACK_INVALID", str(rb_path), "Native file entry is malformed")
        relative = _relative(row.get("path"), "nativeFiles.path")
        digest = row.get("sha256")
        if relative in seen or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            fail("NATIVE_READBACK_INVALID", relative, "Duplicate path or malformed native digest")
        seen.add(relative)
        actual, _, _ = _hash_file(root, relative)
        if actual != digest:
            fail("NATIVE_READBACK_DRIFT", relative, "Saved native file differs from the pinned readback")
    if rb.get("editableRoundtrip") is not True or rb.get("sceneReopened") is not True:
        fail("NATIVE_READBACK_INCOMPLETE", str(rb_path), "Editable roundtrip and scene reopen are required")

    with tempfile.TemporaryDirectory(prefix="monkey-native-selection-", dir="/private/tmp") as temp:
        verify_out = Path(temp) / "verification"
        from .targets.unity import verify
        verify(root, verify_out, level="editor")
        result = load(read(verify_out / "verification.json"), max_nodes=8_000_000)
        if result.get("candidateManifestSha256") != expected_manifest:
            fail("CANDIDATE_SHA_MISMATCH", str(root / "manifest.json"), "Verifier saw a different candidate manifest")
        if result.get("staticValidation") != "pass" or result.get("nativeStaticValidation") != "pass":
            fail("NATIVE_STATIC_VERIFY_FAILED", str(verify_out / "verification.json"), "Unity static/native static verification did not pass")
        coverage=result.get("componentCoverage") or {}
        component_rows=coverage.get('components')
        source_count=coverage.get('sourceComponentCount')
        full_coverage=(coverage.get('schema')=='monkey-prefab-component-coverage/1'
            and isinstance(component_rows,list)and type(source_count)is int
            and all(isinstance(row,dict)for row in component_rows)
            and source_count==len(component_rows)==coverage.get('uniqueSourceComponentCount')
            and len({row.get('sourceId')for row in component_rows})==source_count
            and all(isinstance(row.get('sourceId'),str)and row['sourceId']and row.get('nativeStatus')=='pass'for row in component_rows))
        if result.get("staticPresentationValidation")!="pass" or not full_coverage:
            fail("NATIVE_SOURCE_COVERAGE_INCOMPLETE", str(verify_out / "verification.json"),
                 "Full source component coverage and static presentation must be independently verified")
        if result.get("editorValidation") not in ("pass", "partial"):
            fail("NATIVE_EDITOR_VERIFY_FAILED", str(verify_out / "verification.json"), "Unity Editor verification failed")
        unexpected = [d for d in result.get("diagnostics", []) if d.get("code") not in _DYNAMIC_ONLY]
        if unexpected:
            fail("NATIVE_VERIFY_DIAGNOSTICS", str(verify_out / "verification.json"),
                 "Only the known dynamic Spine/animation boundaries may remain")
        verification = load(read(verify_out / "verification.json"), max_nodes=8_000_000)
    return rb, rb_raw, verification


def _package_inventory(root):
    lock_path = root / "Packages" / "packages-lock.json"
    packages = {}
    if lock_path.is_file():
        lock = _read_json(lock_path)
        for name, row in lock.get("dependencies", {}).items():
            if isinstance(row, dict) and isinstance(row.get("version"), str):
                packages[name] = row["version"]
    cache = root / "Library" / "PackageCache"
    if cache.is_symlink():
        fail("SYMLINK_PATH", str(cache), "Package cache root is symbolic")
    guid_to_package = {}
    if cache.is_dir():
        for package_dir in cache.iterdir():
            if package_dir.is_symlink() or not package_dir.is_dir():
                continue
            package_name = package_dir.name.rsplit("@", 1)[0]
            version = packages.get(package_name, package_dir.name.rsplit("@", 1)[-1])
            for meta in package_dir.rglob("*.meta"):
                if meta.is_symlink():
                    fail("SYMLINK_PATH", str(meta), "Package metadata path is symbolic")
                guid = _guid_meta(meta)
                if guid:
                    previous = guid_to_package.get(guid)
                    record = dict(package=package_name, version=version,
                                  path=meta.relative_to(root).as_posix())
                    if previous and previous != record:
                        fail("DUPLICATE_PACKAGE_GUID", guid, "Package GUID resolves more than once")
                    guid_to_package[guid] = record
    return packages, guid_to_package


def _yaml_guid_refs(raw, location):
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return set()
    return {m.group(1).lower() for m in _GUID_REF.finditer(text)}


def freeze(candidate, prefabs, output, expected_manifest, expected_readback):
    """Create a clean Unity project containing only selected Prefabs and closure.

    `prefabs` are canonical project-relative paths such as
    `Assets/Game/Content/Prefabs/UI/Home/MainUI.prefab`.
    """
    root = safe(candidate)
    output_path = safe(output)
    if output_path == root or output_path.is_relative_to(root) or root.is_relative_to(output_path):
        fail("OUTPUT_OVERLAP", str(output_path), "Output overlaps the input candidate")
    if output_path.exists():
        fail("OUTPUT_EXISTS", str(output_path), "Use a fresh output directory")
    manifest_path = inside(root, "manifest.json")
    manifest_raw = read(manifest_path, max_bytes=128 * 1024 * 1024)
    if sha(manifest_raw) != expected_manifest:
        fail("CANDIDATE_SHA_MISMATCH", str(manifest_path), "Candidate manifest differs from the pinned SHA256")
    manifest = load(manifest_raw, max_nodes=8_000_000)
    if manifest.get("schemaVersion") != 1 or manifest.get("targetProfile") != "unity-6000.6.2f1-ugui":
        fail("UNSUPPORTED_CANDIDATE", str(manifest_path), "Expected Unity 6000.6.2f1 uGUI candidate schema 1")
    rows = {}
    folded = set()
    for row in manifest.get("files", []):
        path = _relative(row.get("path"), "manifest.files.path")
        if path in rows or path.casefold() in folded:
            fail("INVALID_MANIFEST", path, "Duplicate or case-colliding candidate file")
        folded.add(path.casefold())
        if row.get("owner", "generated") not in ("generated", "retained", "manual"):
            fail("INVALID_MANIFEST", path, "Unsupported file owner")
        digest = row.get("sha256")
        size = row.get("bytes")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest) or type(size) is not int:
            fail("INVALID_MANIFEST", path, "Malformed file digest or byte count")
        rows[path] = dict(path=path, sha256=digest, bytes=size, owner=row.get("owner", "generated"))
    if not rows:
        fail("INVALID_MANIFEST", str(manifest_path), "Candidate inventory is empty")

    rb, rb_raw, verification = _native_verification(root, output, expected_manifest, expected_readback)
    native = {row["path"]: row["sha256"] for row in rb["nativeFiles"]}

    # Every manifest-owned file is checked. Native-saved files use the exact
    # readback digest; all others must remain byte-identical to the generation.
    normalized_native_files = []
    for path, row in rows.items():
        actual, size, _ = _hash_file(root, path)
        expected = native.get(path, row["sha256"])
        normalized_version = False
        if path == "ProjectSettings/ProjectVersion.txt" and path not in native and actual != row["sha256"]:
            from .targets.common import normalized_unity_version
            normalized_version = normalized_unity_version(read(inside(root, path)), "6000.6.2f1")
        if ((actual != expected and not normalized_version)
                or (path not in native and size != row["bytes"] and not normalized_version)):
            fail("CANDIDATE_FILE_DRIFT", path, "File differs from its generated or native-saved authority")
        if normalized_version:
            normalized_native_files.append(dict(path=path, generatedSha256=row["sha256"], savedSha256=actual,
                                                normalizedEditorVersion="6000.6.2f1"))
    native_only = set(native) - set(rows)
    for path in native_only:
        if not path.startswith("Assets/"):
            fail("UNOWNED_NATIVE_FILE", path, "Native-only saved files must be under Assets/")
    package_lock_path = "Packages/packages-lock.json"
    supplemental = {}
    if package_lock_path not in rows:
        lock_raw = read(inside(root, package_lock_path), max_bytes=16 * 1024 * 1024)
        supplemental[package_lock_path] = dict(sha256=sha(lock_raw), bytes=len(lock_raw),
                                              owner="retained", authority="package-lock")
    authorized_files = set(rows) | native_only | {
        "manifest.json", "recovery-manifest.json", "Analysis/Readback/editor-readback.json",
        "Analysis/Readback/system-fonts.json", package_lock_path
    }
    # Enforce carried project/evidence scopes; Library, logs, temp, caches and
    # UserSettings are deliberately outside the adoption inventory.
    for scope in ("Assets", "Packages", "ProjectSettings", "Analysis/Readback"):
        scope_root = root / scope
        if scope_root.is_symlink():
            fail("SYMLINK_PATH", str(scope_root), "Project/evidence root is symbolic")
        if not scope_root.exists():
            continue
        for actual_path in scope_root.rglob("*"):
            if actual_path.is_symlink():
                fail("SYMLINK_PATH", str(actual_path), "Project/evidence scope contains a symbolic link")
            if not actual_path.is_file():
                continue
            relative_actual = actual_path.relative_to(root).as_posix()
            if relative_actual in authorized_files or scope == "Analysis/Readback":
                continue
            if scope == "Assets" and relative_actual.endswith(".meta") and (root / relative_actual[:-5]).is_dir():
                continue
            if scope == "Assets":
                continue  # unrelated project files are checked for authority if reached by selection
            if scope == "ProjectSettings":
                continue  # only the pinned Editor version is selected below
            fail("CANDIDATE_UNOWNED", relative_actual,
                 "Unknown file is outside the candidate and native readback inventories")

    guid_to_path = {}
    all_meta = sorted((root / "Assets").rglob("*.meta"))
    for meta in all_meta:
        if meta.is_symlink():
            fail("SYMLINK_PATH", str(meta), "Candidate metadata path is symbolic")
        rel_meta = meta.relative_to(root).as_posix()
        guid = _guid_meta(meta)
        if not guid:
            continue
        if guid in guid_to_path:
            fail("DUPLICATE_TARGET_GUID", rel_meta, "GUID duplicates " + guid_to_path[guid])
        guid_to_path[guid] = rel_meta[:-5] if (root / rel_meta[:-5]).is_file() else None

    package_versions, package_guids = _package_inventory(root)
    duplicate_package_project = set(guid_to_path) & set(package_guids)
    if duplicate_package_project:
        guid = sorted(duplicate_package_project)[0]
        fail("DUPLICATE_TARGET_GUID", guid, "GUID is assigned to both a project asset and an installed package")
    selected = []
    for item in prefabs:
        path = _relative(item, "prefabs")
        if not path.startswith("Assets/") or not path.endswith(".prefab"):
            fail("INVALID_PREFAB_SELECTION", path, "Selection must name an Assets .prefab")
        if path not in native:
            fail("SELECTION_NOT_SAVED", path, "Selected Prefab has no native saved-file identity")
        selected.append(path)
    if not selected or len(selected) != len(set(selected)):
        fail("INVALID_PREFAB_SELECTION", str(root), "Select one or more unique Prefab paths")

    included = set()
    pending = list(selected)
    external = {}
    shader_edges = []
    shader_builtins = set()
    while pending:
        path = pending.pop()
        if path in included:
            continue
        if path not in rows and path not in native:
            fail("DEPENDENCY_NOT_OWNED", path, "Referenced project asset is absent from both frozen authorities")
        digest, _, raw = _hash_file(root, path)
        if path in native and digest != native[path]:
            fail("NATIVE_FILE_CHANGED", path, "Referenced native file differs from readback")
        if path in rows and path not in native and digest != rows[path]["sha256"]:
            fail("CANDIDATE_FILE_DRIFT", path, "Referenced generated file differs from manifest")
        included.add(path)
        shader_files, builtin_includes = _shader_include_paths(raw, path, root)
        if shader_files:
            shader_edges.append(dict(path=path, requires=shader_files, kind='shader-include'))
            pending.extend(shader_files)
        shader_builtins.update(builtin_includes)

        # Meta accompanies project assets and provides Unity identity.
        meta_path = path + ".meta"
        if meta_path in rows or meta_path in native:
            included.add(meta_path)

        for guid in _yaml_guid_refs(raw, path):
            if guid in _ZERO_GUIDS:
                continue
            target = guid_to_path.get(guid)
            if target:
                if target + ".meta" not in rows and target + ".meta" not in native:
                    fail("TARGET_GUID_METADATA_UNOWNED", path,
                         "Referenced Unity GUID metadata is outside the owner/native inventories: " + target + ".meta")
                pending.append(target)
                continue
            package = package_guids.get(guid)
            if package:
                external[guid] = package
                continue
            fail("UNRESOLVED_GUID", path, "GUID " + guid + " has no project or installed-package identity")

        # Include the metadata for every containing folder when available.
        parent = PurePosixPath(path).parent
        while str(parent) not in (".", "Assets") and str(parent).startswith("Assets/"):
            folder_meta = str(parent) + ".meta"
            if folder_meta in rows or folder_meta in native:
                included.add(folder_meta)
            parent = parent.parent

    spine_runtime_evidence = None
    spine_related = bool(included & {
        "Assets/Game/Scripts/Presentation/Recovered/Spine/UnitySpineGraphicMaterialPresentation.cs",
        "Assets/Game/Scripts/Presentation/Recovered/Spine/UnitySpineSourceIdentity.cs",
    }) or any(path.startswith("Assets/Plugins/Spine38/") for path in included)
    if spine_related:
        from .native_code_dependencies import spine_runtime_closure
        spine_runtime_evidence = spine_runtime_closure(root, rows, native, manifest, included)
        if spine_runtime_evidence:
            included.update(row["path"] for row in spine_runtime_evidence["files"])

    by_name = {}
    for path in rows:
        by_name.setdefault(PurePosixPath(path).name, []).append(path)
    code_edges = []
    code_queue = sorted(p for p in included if p.endswith(".cs"))
    seen_code = set()
    diagnostics = []
    code_analysis = []
    carrier_profiles = None
    carrier_evidence = None
    while code_queue:
        path = code_queue.pop()
        name = PurePosixPath(path).name
        if name in seen_code:
            continue
        seen_code.add(name)
        digest, _, _ = _hash_file(root, path)
        source_code_digest = digest
        profile = _template_profile(path, digest)
        proof_kind = "exact-producer-template"
        if profile is None and name.startswith("StaticFields_"):
            if carrier_profiles is None:
                carrier_profiles, carrier_evidence = _carrier_profiles(root, rows, manifest)
            profile = carrier_profiles.get(path)
            proof_kind = "exact-generated-disabled-static-field-carrier"
        if profile is None:
            diagnostics.append(dict(code="UNANALYZED_CSHARP_DEPENDENCIES", path=path,
                                    severity="warning", reason="No exact producer-template hash has a declared compile dependency graph"))
            continue
        if profile[0] != name:
            fail("PRODUCER_TEMPLATE_IDENTITY_MISMATCH", path,
                 "Known template hash is attached to a differently named file")
        deps = []
        for dependency in profile[1]:
            matches = by_name.get(dependency, [])
            if len(matches) > 1:
                fail("AMBIGUOUS_CODE_DEPENDENCY", dependency, "More than one candidate script has this declared template name")
            if not matches:
                fail("DECLARED_CODE_DEPENDENCY_MISSING", path,
                     "Producer-declared compile dependency is absent: " + dependency)
            dep_path = matches[0]
            if dep_path not in rows:
                fail("DEPENDENCY_NOT_OWNED", dep_path, "Declared script is absent from candidate manifest")
            digest, size, _ = _hash_file(root, dep_path)
            if digest != rows[dep_path]["sha256"] or size != rows[dep_path]["bytes"]:
                fail("CANDIDATE_FILE_DRIFT", dep_path, "Declared script differs from candidate generation")
            included.add(dep_path)
            if dep_path + ".meta" in rows or dep_path + ".meta" in native:
                included.add(dep_path + ".meta")
            deps.append(dep_path)
            code_queue.append(dep_path)
        if deps:
            code_edges.append(dict(path=path, requires=sorted(set(deps)), kind="csharp-compile"))
        code_analysis.append(dict(path=path, sha256=source_code_digest, profile=proof_kind,
            requires=sorted(set(deps)), externalDependencies="System/UnityEngine/locked-uGUI",
            scope="compile-only; no recovered business behavior claimed"))

    # Fixed Editor/package inputs needed to open this Unity project. Exact
    # package versions remain authoritative in manifest + lock files.
    for fixed in ("ProjectSettings/ProjectVersion.txt", "Packages/manifest.json", package_lock_path):
        if fixed in rows or fixed in supplemental:
            included.add(fixed)
    if "Packages/manifest.json" not in included or package_lock_path not in included:
        fail("PACKAGE_LOCK_MISSING", str(root / "Packages"), "Project manifest and lock must accompany adoption")

    package_manifest = _read_json(inside(root, "Packages/manifest.json"), max_bytes=16 * 1024 * 1024)
    package_lock = _read_json(inside(root, package_lock_path), max_bytes=16 * 1024 * 1024)
    declared_dependencies = package_manifest.get("dependencies")
    lock_dependencies = package_lock.get("dependencies")
    if not isinstance(declared_dependencies, dict) or not isinstance(lock_dependencies, dict):
        fail("PACKAGE_LOCK_INVALID", package_lock_path, "Package manifest and lock require dependency objects")
    dependency_pins = []
    for package_name, request in sorted(declared_dependencies.items()):
        lock_row = lock_dependencies.get(package_name)
        if not isinstance(lock_row, dict) or not isinstance(lock_row.get("version"), str):
            fail("PACKAGE_LOCK_MISMATCH", package_name, "Declared package is absent from exact lockfile")
        locked_version = lock_row["version"]
        if isinstance(request, str) and re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", request):
            if locked_version != request:
                fail("PACKAGE_LOCK_MISMATCH", package_name, "Exact manifest version differs from package lock")
        dependency_pins.append(dict(name=package_name, requested=request, version=locked_version,
                                   source=lock_row.get("source"), hash=lock_row.get("hash")))

    out = new_output(output_path, [root])
    files = []
    for path in sorted(included):
        digest, size, raw = _hash_file(root, path)
        source_row = rows.get(path) or supplemental.get(path)
        expected = native.get(path, source_row.get("sha256") if source_row else None)
        if path in {row["path"] for row in normalized_native_files}:
            expected = digest
        if expected is None or digest != expected:
            fail("UNOWNED_SELECTION_FILE", path, "Selected closure file is not hash-bound by either authority")
        target = inside(out, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        files.append(dict(path=path, sha256=digest, bytes=size,
                          owner=rows.get(path, supplemental.get(path, {})).get("owner", "generated")))

    identity_evidence = dict(schemaVersion=1, candidateManifestSha256=expected_manifest,
                             nativeReadbackSha256=expected_readback,
                             targetProfile=manifest["targetProfile"], namespace=manifest.get("namespace", ""),
                             assignedAssetIdentities=manifest.get("assignedAssetIdentities"),
                             selectedPrefabs=sorted(selected))
    verification_evidence = dict(schemaVersion=1, candidateManifestSha256=expected_manifest,
                                 readbackSha256=expected_readback, verification=verification)
    for evidence_path, evidence_value in (
            ("Analysis/Adoption/source-identity.json", identity_evidence),
            ("Analysis/Adoption/source-verification.json", verification_evidence)):
        raw = encoded(evidence_value)
        target = inside(out, evidence_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        files.append(dict(path=evidence_path, sha256=sha(raw), bytes=len(raw), owner="generated"))

    manifest_out = dict(
        schemaVersion=1,
        targetProfile=manifest["targetProfile"],
        namespace=manifest.get("namespace", ""),
        sourceCandidateManifestSha256=expected_manifest,
        sourceNativeReadbackSha256=expected_readback,
        sourceCandidateIdentity=manifest.get("assignedAssetIdentities"),
        sourceIdentityEvidencePath="Analysis/Adoption/source-identity.json",
        sourceVerificationEvidencePath="Analysis/Adoption/source-verification.json",
        selection=dict(prefabs=sorted(selected), coverage="selected-prefab-guid-closure+producer-declared-csharp"),
        externalPackageReferences=[dict(guid=g, **external[g]) for g in sorted(external)],
        packageVersions=package_versions,
        shaderDependencies=dict(coverage='literal-project-includes+declared-unity-builtins',
            edges=sorted(shader_edges, key=lambda e:e['path']),
            builtinIncludes=sorted(shader_builtins), targetUnityVersion='6000.6.2f1',
            targetShaderCompilation='not_run'),
        packageDependencyPins=dependency_pins,
        supplementalFileAuthorities=supplemental,
        normalizedNativeFiles=normalized_native_files,
        spineRuntimeClosure=spine_runtime_evidence,
        adoptionDependencies=dict(schemaVersion=1, coverage="producer-declared", edges=sorted(code_edges, key=lambda x:x["path"])),
        codeDependencyAnalysis=dict(schemaVersion=1, coverage="exact-producer-proofs",
            scripts=sorted(code_analysis, key=lambda x:x["path"]), carrierPlanEvidence=carrier_evidence,
            spineRuntimeClosure=spine_runtime_evidence),
        coverageBoundary="Unity YAML GUID references are resolved. C# dependencies are producer-declared only for exact bundled templates, exact regenerated disabled carriers, and the manifest-pinned Spine runtime stage; other scripts remain explicitly unanalyzed.",
        diagnostics=sorted(diagnostics, key=lambda d:(d.get('path', ''), d.get('code', ''))),
        files=files,
    )
    font_readback_path = root / "Analysis/Readback/system-fonts.json"
    if font_readback_path.is_file():
        font_raw = read(font_readback_path, max_bytes=128 * 1024 * 1024)
        font_readback = load(font_raw, max_nodes=8_000_000)
        from .layout import standard
        plan_path = inside(root, standard.locate(manifest, "importPlan"))
        plan_relative = plan_path.relative_to(root).as_posix()
        plan_row = rows.get(plan_relative)
        if not plan_row:
            fail("IMPORT_PLAN_UNOWNED", plan_relative, "Font parent evidence requires a manifest-owned import plan")
        plan_raw = read(plan_path, max_bytes=128 * 1024 * 1024)
        if sha(plan_raw) != plan_row["sha256"] or len(plan_raw) != plan_row["bytes"]:
            fail("IMPORT_PLAN_DRIFT", plan_relative, "Import plan differs from its candidate manifest owner")
        import_plan = load(plan_raw, max_nodes=8_000_000)
        font_binding = import_plan.get("systemFontBinding") or {}
        producer = font_binding.get("systemFonts") or {}
        pinned_fields = {
            "sourceManifestSha256": import_plan.get("sourceManifestSha256"),
            "irSha256": producer.get("irSha256"),
            "resolutionReceiptSha256": producer.get("resolutionReceiptSha256"),
            "targetOS": producer.get("targetOS"),
            "targetVersion": producer.get("targetOSVersion"),
            "targetBuild": producer.get("targetOSBuild"),
        }
        for key, expected in pinned_fields.items():
            if not expected or font_readback.get(key) != expected:
                fail("FONT_READBACK_PARENT_MISMATCH", str(font_readback_path),
                     "System-font readback does not match import-plan identity: " + key)
        if font_readback.get("schemaVersion") != 1 or font_readback.get("status") != "readback_pass":
            fail("FONT_READBACK_INVALID", str(font_readback_path), "Expected schema-1 readback_pass evidence")
        expected_static = import_plan.get("staticFontReceiptSha256")
        if expected_static and font_readback.get("staticSdfGenerationReceiptSha256") != expected_static:
            fail("FONT_READBACK_PARENT_MISMATCH", str(font_readback_path),
                 "Static-SDF receipt differs from the pinned import plan")
        selected_font_ids = [row.get("assetId") for row in font_readback.get("fonts", [])
                             if isinstance(row, dict) and row.get("assetPath") in included
                             and row.get("assetPath") in native
                             and isinstance(row.get("assetId"), str)]
        from .native_font_contract import audit_saved_font_coverage
        manifest_out["nativeFontCoverageContract"] = audit_saved_font_coverage(
            font_readback, [row for row in files if row["path"] in native], selected_asset_ids=selected_font_ids,
            producer_contract=producer)
        manifest_out["fontReadbackEvidence"] = dict(
            path="Analysis/Readback/system-fonts.json", sha256=sha(font_raw), bytes=len(font_raw),
            binding="importPlan.systemFontBinding.systemFonts + importPlan.staticFontReceiptSha256",
            copiedIntoSelection=False)
    write_json(out / "manifest.json", manifest_out)
    return manifest_out
