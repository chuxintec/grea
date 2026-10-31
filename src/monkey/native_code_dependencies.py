"""Supplement immutable selections with exact producer compilation proofs."""
from pathlib import Path

from . import __version__
from .io import inside, load, new_output, read, safe, sha, write_json
from .native_selection import _relative, _template_profile, _carrier_profiles
from .sources.compiled import fail


def audit(candidate, expected_manifest, producer_candidate, expected_producer_manifest, output):
    root, producer = safe(candidate), safe(producer_candidate)
    raw = read(root / "manifest.json", max_bytes=128 * 1024 * 1024)
    source_raw = read(producer / "manifest.json", max_bytes=128 * 1024 * 1024)
    if sha(raw) != expected_manifest or sha(source_raw) != expected_producer_manifest:
        fail("CANDIDATE_SHA_MISMATCH", str(root), "Supplement requires exact target and original producer manifests")
    manifest, source = load(raw, max_nodes=8_000_000), load(source_raw, max_nodes=8_000_000)
    if (manifest.get("sourceCandidateManifestSha256") != expected_producer_manifest
            or manifest.get("targetProfile") != "unity-6000.6.2f1-ugui"
            or source.get("targetProfile") != manifest.get("targetProfile")):
        fail("PRODUCER_LINEAGE_MISMATCH", str(root), "Target must retain this exact original producer identity")
    files, names, folded = {}, {}, set()
    for row in manifest.get("files", []):
        path = _relative(row.get("path"), "files.path")
        if path == "manifest.json" or path.casefold() in folded:
            fail("INVALID_MANIFEST", path, "Duplicate or reserved path")
        folded.add(path.casefold())
        data = read(inside(root, path), max_bytes=256 * 1024 * 1024)
        if sha(data) != row.get("sha256") or len(data) != row.get("bytes"):
            fail("CANDIDATE_DRIFT", path, "Target differs from its frozen inventory")
        files[path] = row
        if path.endswith(".cs"):
            names.setdefault(Path(path).name, []).append(path)
    for path in root.rglob("*"):
        if path.is_symlink():
            fail("SYMLINK_PATH", str(path), "Frozen candidates cannot contain links")
        if path.is_file() and path.relative_to(root).as_posix() not in set(files) | {"manifest.json"}:
            fail("CANDIDATE_UNOWNED", str(path), "Use a clean frozen candidate")
    source_files = {row["path"]: row for row in source.get("files", [])}
    for path in ("Packages/manifest.json", "Packages/packages-lock.json"):
        if path not in files:
            fail("PACKAGE_LOCK_MISSING", path, "External package dependencies require their frozen manifest and lock")
    carrier_profiles, plan_evidence = _carrier_profiles(producer, source_files, source)
    scripts, uncovered = [], []
    for path, row in sorted(files.items()):
        if not path.endswith(".cs"):
            continue
        profile = _template_profile(path, row["sha256"])
        kind = "exact-producer-template"
        if profile is None and path in carrier_profiles:
            source_row = source_files[path]
            if row["sha256"] == source_row["sha256"] and row["bytes"] == source_row["bytes"]:
                profile, kind = carrier_profiles[path], "exact-generated-disabled-static-field-carrier"
        if profile is None:
            uncovered.append(dict(path=path, sha256=row["sha256"], code="UNANALYZED_CSHARP_DEPENDENCIES"))
            continue
        if profile[0] != Path(path).name:
            fail("PRODUCER_TEMPLATE_IDENTITY_MISMATCH", path, "Hash belongs to a differently named producer script")
        requires = []
        for name in profile[1]:
            matches = names.get(name, [])
            if len(matches) != 1:
                fail("DECLARED_CODE_DEPENDENCY_MISSING", path, "Expected exactly one project dependency: " + name)
            dependency = matches[0]
            requires.append(dict(path=dependency, sha256=files[dependency]["sha256"]))
        scripts.append(dict(path=path, sha256=row["sha256"], profile=kind,
            requires=requires, externalDependencies="System/UnityEngine/locked-uGUI"))
    result = dict(schema="monkey-native-code-dependency-supplement/1", toolVersion=__version__,
        producerImplementation=[dict(path=name, sha256=sha(read(Path(__file__).parent / name)))
            for name in ("native_code_dependencies.py", "native_selection.py", "prefab_static_carriers.py")],
        status="proven-subset" if uncovered else "all-inventoried-csharp-producer-proven",
        targetManifestSha256=expected_manifest, producerCandidateManifestSha256=expected_producer_manifest,
        carrierPlanEvidence=plan_evidence, packageFiles=[dict(path=path, sha256=files[path]["sha256"])
            for path in ("Packages/manifest.json", "Packages/packages-lock.json") if path in files],
        scripts=scripts, uncovered=uncovered,
        originalDiagnostics=manifest.get("diagnostics", []),
        boundary="Supplement only; original manifests/warnings unchanged. Compile proofs do not establish native compilation, physical input or recovered business behavior.")
    out = new_output(output, [root, producer])
    write_json(out / "code-dependency-supplement.json", result)
    return result
