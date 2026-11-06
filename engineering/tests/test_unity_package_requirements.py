import hashlib
import json
import plistlib
import tempfile
import unittest
from pathlib import Path

from beaver.unity_package_requirements import resolve_requirements


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


class UnityPackageRequirementsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/private/var/tmp")
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.target = self.root / "target"
        self.editor = self.root / "Unity.app"
        self.evidence_path = self.root / "evidence.json"
        self._project(self.source, "2.6.0")
        self._project(self.target, "2.0.0")
        self._editor()
        self._cache(self.source)
        self._cache(self.target)
        self.evidence = self._evidence()

    def tearDown(self):
        self.temp.cleanup()

    def _project(self, root, requested):
        write_json(root / "Packages/manifest.json", {"dependencies": {"com.unity.ugui": requested}})
        ugui = {"version": "2.6.0", "depth": 0, "source": "builtin", "dependencies": {
            "com.unity.modules.ui": "1.0.0"}}
        dep = {"version": "1.0.0", "depth": 1, "source": "builtin", "dependencies": {}}
        write_json(root / "Packages/packages-lock.json", {"dependencies": {
            "com.unity.ugui": ugui, "com.unity.modules.ui": dep}})
        (root / "ProjectSettings").mkdir(parents=True, exist_ok=True)
        (root / "ProjectSettings/ProjectVersion.txt").write_text(
            "m_EditorVersion: 6000.6.2f1\nm_EditorVersionWithRevision: 6000.6.2f1 (770e33f6875c)\n",
            encoding="utf-8")

    def _editor(self):
        info = {"CFBundleShortVersionString": "Unity version 6000.6.2f1",
                "CFBundleVersion": "6000.6.2f1", "UnityBuildNumber": "770e33f6875c"}
        path = self.editor / "Contents/Info.plist"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(plistlib.dumps(info))
        base = self.editor / "Contents/Resources/PackageManager/BuiltInPackages"
        ugui = {"name": "com.unity.ugui", "version": "2.6.0",
                "dependencies": {"com.unity.modules.ui": "1.0.0"}}
        module = {"name": "com.unity.modules.ui", "version": "1.0.0", "dependencies": {}}
        write_json(base / "com.unity.ugui/package.json", ugui)
        write_json(base / "com.unity.ugui/Runtime/Canvas.cs", {"text": "same"})
        write_json(base / "com.unity.modules.ui/package.json", module)
        pm = self.editor / "Contents/Resources/PackageManager/Editor/manifest.json"
        write_json(pm, {"packages": {"com.unity.ugui": {"version": "2.6.0"}}})

    def _cache(self, root):
        package = {"name": "com.unity.ugui", "version": "2.6.0",
                   "dependencies": {"com.unity.modules.ui": "1.0.0"},
                   "_fingerprint": "a" * 40}
        path = root / "Library/PackageCache/com.unity.ugui@aaaaaaaaaaaa"
        write_json(path / "package.json", package)
        write_json(path / "Runtime/Canvas.cs", {"text": "same"})

    def _evidence(self):
        rows = []
        for root, requested in ((self.source, "2.6.0"), (self.target, "2.0.0")):
            manifest_raw = (root / "Packages/manifest.json").read_bytes()
            lock_raw = (root / "Packages/packages-lock.json").read_bytes()
            project_raw = (root / "ProjectSettings/ProjectVersion.txt").read_bytes()
            cache = root / "Library/PackageCache/com.unity.ugui@aaaaaaaaaaaa"
            hashes = {p.relative_to(cache).as_posix(): sha(p.read_bytes()) for p in cache.rglob("*") if p.is_file()}
            # This evidence fixture uses package-manager cache metadata with the expected fingerprint.
            lock_entry = json.loads(lock_raw)["dependencies"]["com.unity.ugui"]
            package = json.loads((cache / "package.json").read_text())
            rows.append({"project": str(root), "manifestRequested": requested,
                         "lockResolved": lock_entry, "packageManifest": package,
                         "inputHashes": {"Packages/manifest.json": sha(manifest_raw),
                                         "Packages/packages-lock.json": sha(lock_raw),
                                         "ProjectSettings/ProjectVersion.txt": sha(project_raw)},
                         "cachePath": str(cache), "cacheFileHashes": hashes, "files": len(hashes)})
        doc = {"scope": "read-only package evidence", "projects": rows,
               "identicalCacheBytes": True, "cacheDifferences": [],
               "files": len(rows[0]["cacheFileHashes"])}
        raw = (json.dumps(doc, sort_keys=True, indent=2) + "\n").encode()
        self.evidence_path.write_bytes(raw)
        return {"path": str(self.evidence_path), "sha256": sha(raw)}

    def test_verified_ugui_builtin_override(self):
        requirements, conflicts = resolve_requirements(
            self.source, self.target, "unity-6000.6.2f1-ugui", source_project=self.source,
            editor_path=self.editor, evidence=self.evidence)
        self.assertEqual([], conflicts)
        self.assertEqual("verified", requirements["status"])
        row = requirements["resolvedPackages"]["com.unity.ugui"]
        self.assertEqual(("2.0.0", "2.6.0", "builtin"),
                         (row["requestedTarget"], row["resolvedVersion"], row["source"]))
        self.assertEqual(str(self.target / "Library/PackageCache/com.unity.ugui@aaaaaaaaaaaa"), row["targetRoot"])

    def test_evidence_and_cache_drift_block(self):
        path = self.target / "Library/PackageCache/com.unity.ugui@aaaaaaaaaaaa/Runtime/Canvas.cs"
        path.write_text("drift", encoding="utf-8")
        requirements, conflicts = resolve_requirements(
            self.source, self.target, "6000.6.2f1", source_project=self.source,
            editor_path=self.editor, evidence=self.evidence)
        self.assertEqual("blocked", requirements["status"])
        self.assertIn(conflicts[0]["code"], {"PACKAGE_CACHE_DIFFERENT", "PACKAGE_BUILTIN_BYTES", "PACKAGE_EVIDENCE_CACHE_DRIFT"})

    def test_registry_version_mismatch_is_not_relaxed(self):
        for root, version in ((self.source, "1.2.0"), (self.target, "1.3.0")):
            write_json(root / "Packages/manifest.json", {"dependencies": {"com.example.registry": version}})
            write_json(root / "Packages/packages-lock.json", {"dependencies": {
                "com.example.registry": {"version": version, "depth": 0, "source": "registry",
                                         "url": "https://packages.example", "dependencies": {}}}})
        requirements, conflicts = resolve_requirements(self.source, self.target, "6000.6.2f1",
                                                         source_project=self.source, editor_path=self.editor)
        self.assertEqual("blocked", requirements["status"])
        self.assertTrue(any(row.get("kind") in {"requestedVersion", "resolvedPackage"} for row in conflicts))

    def test_missing_builtin_dependency_lock_blocks(self):
        for root in (self.source, self.target):
            lock = json.loads((root / "Packages/packages-lock.json").read_text())
            del lock["dependencies"]["com.unity.modules.ui"]
            write_json(root / "Packages/packages-lock.json", lock)
        requirements, conflicts = resolve_requirements(
            self.source, self.target, "6000.6.2f1", source_project=self.source,
            editor_path=self.editor, evidence=self.evidence)
        self.assertEqual("blocked", requirements["status"])
        self.assertEqual("PACKAGE_LOCK_MISSING", conflicts[0]["code"])

    def test_incoming_bytes_must_match_explicit_source_project(self):
        incoming = self.root / "incoming"
        self._project(incoming, "2.6.0")
        (incoming / "ProjectSettings/ProjectVersion.txt").write_text(
            "m_EditorVersion: 6000.6.2f1\nm_EditorVersionWithRevision: 6000.6.2f1 (different)\n",
            encoding="utf-8")
        requirements, conflicts = resolve_requirements(
            incoming, self.target, "6000.6.2f1", source_project=self.source,
            editor_path=self.editor, evidence=self.evidence)
        self.assertEqual("blocked", requirements["status"])
        self.assertEqual("PACKAGE_INCOMING_SOURCE_DRIFT", conflicts[0]["code"])

    def test_profile_and_project_editor_revision_are_mandatory(self):
        requirements, conflicts = resolve_requirements(
            self.source, self.target, "6000.5.0f1", source_project=self.source,
            editor_path=self.editor, evidence=self.evidence)
        self.assertEqual("PACKAGE_PROFILE", conflicts[0]["code"])
        (self.target / "ProjectSettings/ProjectVersion.txt").write_text(
            "m_EditorVersion: 6000.5.0f1\nm_EditorVersionWithRevision: 6000.5.0f1 (old)\n",
            encoding="utf-8")
        requirements, conflicts = resolve_requirements(
            self.source, self.target, "6000.6.2f1", source_project=self.source,
            editor_path=self.editor, evidence=self.evidence)
        self.assertEqual("PACKAGE_EDITOR_REVISION", conflicts[0]["code"])

    def test_non_lower_or_non_numeric_ugui_request_is_refused(self):
        for requested in ("999.0.0", "file:../ugui", "git+https://example.invalid/ugui.git"):
            with self.subTest(requested=requested):
                write_json(self.target / "Packages/manifest.json",
                           {"dependencies": {"com.unity.ugui": requested}})
                requirements, conflicts = resolve_requirements(
                    self.source, self.target, "6000.6.2f1", source_project=self.source,
                    editor_path=self.editor, evidence=self.evidence)
                self.assertEqual("blocked", requirements["status"])
                self.assertEqual("PACKAGE_BUILTIN_OVERRIDE_SHAPE", conflicts[0]["code"])
        write_json(self.target / "Packages/manifest.json", {"dependencies": {"com.unity.ugui": "2.0.0"}})

    def test_evidence_cache_path_must_be_exact_resolved_directory(self):
        report = json.loads(self.evidence_path.read_text())
        report["projects"][1]["cachePath"] = str(self.root / "somewhere-else" / "com.unity.ugui@aaaaaaaaaaaa")
        raw = (json.dumps(report, sort_keys=True, indent=2) + "\n").encode()
        self.evidence_path.write_bytes(raw)
        bad_evidence = {"path": str(self.evidence_path), "sha256": sha(raw)}
        requirements, conflicts = resolve_requirements(
            self.source, self.target, "6000.6.2f1", source_project=self.source,
            editor_path=self.editor, evidence=bad_evidence)
        self.assertEqual("PACKAGE_EVIDENCE_CACHE_PATH", conflicts[0]["code"])


if __name__ == "__main__":
    unittest.main()
