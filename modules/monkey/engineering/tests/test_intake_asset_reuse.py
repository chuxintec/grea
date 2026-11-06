import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from beaver.intake_asset_reuse import scan


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


class IntakeAssetReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/private/var/tmp")
        self.root = Path(self.temp.name)
        self.candidate = self.root / "candidate"
        self.target = self.root / "target"
        self.guid = "a" * 32
        self.asset = "Assets/Shared/sample.asset"
        self.asset_bytes = b"%YAML 1.1\n--- !u!114 &11400000\nMonoBehaviour: {}\n"
        self.meta_bytes = (f"fileFormatVersion: 2\nguid: {self.guid}\nNativeFormatImporter:\n"
                           "  externalObjects: {}\n  mainObjectFileID: 11400000\n  userData: \n").encode()
        write(self.candidate / self.asset, self.asset_bytes)
        write(self.candidate / (self.asset + ".meta"), self.meta_bytes)
        write(self.target / self.asset, self.asset_bytes)
        write(self.target / (self.asset + ".meta"), self.meta_bytes)
        self.oracle = {"planSha256": "b" * 64, "prefabs": [{"path": "Assets/UI.prefab", "owners": [{
            "guid": "c" * 32, "localId": 1001, "name": "View", "type": "Example.View",
            "properties": [{"path": "m_Asset", "type": "ObjectReference:PPtr<Example.Asset>",
                            "value": self.guid + "#11400000|Example.Asset@Example.Assembly|script:@",
                            "reference": {"guid": self.guid, "localId": 11400000, "type": "Example.Asset",
                                          "assembly": "Example.Assembly", "name": "sample",
                                          "assetPath": self.asset, "scriptType": "", "scriptAssembly": ""}}]
        }]}]}
        self.oracle_rel = "Analysis/BeaverIntakeBindings/serialized-oracle.json"
        raw = (json.dumps(self.oracle, sort_keys=True, separators=(",", ":")) + "\n").encode()
        write(self.candidate / self.oracle_rel, raw)
        self.files = {
            self.asset: {"path": self.asset, "bytes": len(self.asset_bytes), "sha256": sha(self.asset_bytes)},
            self.asset + ".meta": {"path": self.asset + ".meta", "bytes": len(self.meta_bytes), "sha256": sha(self.meta_bytes)},
            self.oracle_rel: {"path": self.oracle_rel, "bytes": len(raw), "sha256": sha(raw)},
        }
        self.additions = [{"source": self.asset, "target": "Assets/Adopted/sample.asset"}]

    def tearDown(self):
        self.temp.cleanup()

    def _bundle(self):
        source_stage = self.root / "source-stage"
        target_stage = self.root / "target-stage"
        object_row = {"guid": self.guid, "localId": 11400000, "type": "Example.Asset",
                      "assembly": "Example.Assembly", "name": "sample"}
        asset_row = {"path": self.asset, "guid": self.guid,
                     "contentSha256": sha(self.asset_bytes), "metaSha256": sha(self.meta_bytes),
                     "importerType": "UnityEditor.NativeFormatImporter",
                     "importerAssembly": "UnityEditor.CoreModule", "completeObjectSet": True,
                     "objects": [object_row]}

        def stage(root, project):
            before = {self.asset: {"sha256": sha(self.asset_bytes), "bytes": len(self.asset_bytes)},
                      self.asset + ".meta": {"sha256": sha(self.meta_bytes), "bytes": len(self.meta_bytes)}}
            plan = {"contract": "beaver-batch/2", "projectRoot": str(project),
                    "spec": {"schemaVersion": 2, "operation": "batch",
                             "steps": [{"kind": "asset.inspect", "assetPath": self.asset}]},
                    "writeSet": [], "before": before}
            plan_raw = (json.dumps(plan, sort_keys=True, indent=2) + "\n").encode()
            plan_sha = sha(plan_raw)
            write(root / "batch-plan.json", plan_raw)
            report = {"status": "verified", "planSha256": plan_sha, "editorVersion": "6000.6.2f1",
                      "completedSteps": 1, "assets": [asset_row]}
            write(root / "native-result.json", (json.dumps(report, sort_keys=True, indent=2) + "\n").encode())
            journal = {"status": "complete", "projectRoot": str(project), "planSha256": plan_sha,
                       "writeSet": [], "native": report, "recoveryWitnessMatches": True, "unplannedPaths": []}
            write(root / "journal.json", (json.dumps(journal, sort_keys=True, indent=2) + "\n").encode())
            return root

        stage(source_stage, self.candidate)
        stage(target_stage, self.target)
        bundle_path = self.root / "asset-evidence.json"
        bundle = {"contract": "beaver-native-asset-reuse-evidence/1",
                  "sourceStage": str(source_stage), "targetStage": str(target_stage)}
        raw = (json.dumps(bundle, sort_keys=True, indent=2) + "\n").encode()
        write(bundle_path, raw)
        return [{"path": str(bundle_path), "sha256": sha(raw)}]

    def test_exact_native_identity_produces_external_asset(self):
        result = scan(self.candidate, self.target, self.additions, self.files,
                      native_oracle=self.oracle, evidence_paths=self._bundle())
        self.assertEqual([], result["conflicts"])
        self.assertEqual([], result["additions"])
        row = result["externalAssets"][0]
        self.assertEqual(self.asset, row["target"])
        self.assertEqual(self.guid, row["guid"])
        self.assertEqual([{"localId": 11400000, "type": "Example.Asset", "assembly": "Example.Assembly",
                           "name": "sample", "fields": []}], row["objects"])

    def test_missing_native_type_proof_keeps_addition_and_conflict(self):
        self.oracle["prefabs"][0]["owners"][0]["properties"][0]["reference"]["guid"] = "d" * 32
        raw = (json.dumps(self.oracle, sort_keys=True, separators=(",", ":")) + "\n").encode()
        write(self.candidate / self.oracle_rel, raw)
        self.files[self.oracle_rel].update(bytes=len(raw), sha256=sha(raw))
        result = scan(self.candidate, self.target, self.additions, self.files, native_oracle=self.oracle)
        self.assertEqual([self.additions[0]], result["additions"])
        self.assertTrue(any(row["code"] == "needs_native_identity_evidence" for row in result["conflicts"]))
        self.assertEqual([], result["externalAssets"])

    def test_pptr_subset_alone_does_not_claim_complete_object_set(self):
        result = scan(self.candidate, self.target, self.additions, self.files, native_oracle=self.oracle)
        self.assertTrue(any(row["code"] == "needs_complete_native_object_set" for row in result["conflicts"]))
        self.assertEqual([], result["externalAssets"])

    def test_meta_and_importer_mismatch_are_reported(self):
        changed = self.meta_bytes.replace(b"NativeFormatImporter", b"ShaderImporter")
        write(self.target / (self.asset + ".meta"), changed)
        result = scan(self.candidate, self.target, self.additions, self.files, native_oracle=self.oracle)
        codes = {row["code"] for row in result["conflicts"]}
        self.assertIn("ASSET_REUSE_META_MISMATCH", codes)
        self.assertIn("ASSET_REUSE_IMPORTER_SCOPE_MISMATCH", codes)
        self.assertEqual([], result["externalAssets"])

    def test_content_mismatch_and_duplicate_guid_owner_are_reported(self):
        write(self.target / self.asset, b"changed asset bytes")
        write(self.target / "Assets/Elsewhere/duplicate.asset", b"duplicate")
        write(self.target / "Assets/Elsewhere/duplicate.asset.meta", self.meta_bytes)
        result = scan(self.candidate, self.target, self.additions, self.files, native_oracle=self.oracle)
        codes = {row["code"] for row in result["conflicts"]}
        self.assertIn("ASSET_REUSE_CONTENT_MISMATCH", codes)
        self.assertIn("ASSET_REUSE_DUPLICATE_GUID_OWNER", codes)

    def test_batch_reports_multiple_collisions_in_one_pass(self):
        write(self.target / self.asset, b"different sample asset")
        second = "Assets/Shared/second.mat"
        second_meta = f"fileFormatVersion: 2\nguid: {'e' * 32}\nNativeFormatImporter:\n".encode()
        write(self.candidate / second, b"source material")
        write(self.candidate / (second + ".meta"), second_meta)
        write(self.target / second, b"different material")
        write(self.target / (second + ".meta"), second_meta)
        self.files[second] = {"path": second, "bytes": len(b"source material"), "sha256": sha(b"source material")}
        self.files[second + ".meta"] = {"path": second + ".meta", "bytes": len(second_meta), "sha256": sha(second_meta)}
        result = scan(self.candidate, self.target,
                      self.additions + [{"source": second, "target": "Assets/Adopted/second.mat"}],
                      self.files, native_oracle=self.oracle)
        collisions = {row.get("source") for row in result["conflicts"] if row.get("collisionTarget")}
        self.assertEqual({self.asset, second}, collisions)
        self.assertEqual([], result["externalAssets"])

    def test_different_guid_at_source_path_is_observation_not_block(self):
        changed = self.meta_bytes.replace(self.guid.encode(), b"f" * 32)
        write(self.target / (self.asset + ".meta"), changed)
        result = scan(self.candidate, self.target, self.additions, self.files, native_oracle=self.oracle)
        self.assertEqual([], result["conflicts"])
        self.assertEqual([self.additions[0]], result["additions"])
        self.assertEqual("ASSET_REUSE_SOURCE_PATH_DIFFERENT_GUID", result["observations"][0]["code"])

    def test_same_guid_owner_at_another_path_is_inspected(self):
        changed = self.meta_bytes.replace(self.guid.encode(), b"f" * 32)
        write(self.target / (self.asset + ".meta"), changed)
        other = "Assets/Elsewhere/retained.asset"
        write(self.target / other, self.asset_bytes)
        write(self.target / (other + ".meta"), self.meta_bytes)
        result = scan(self.candidate, self.target, self.additions, self.files, native_oracle=self.oracle)
        row = next(x for x in result["conflicts"] if x.get("collisionTarget") == other)
        self.assertEqual("needs_complete_native_object_set", row["code"])

    def test_batch_evidence_drift_is_rejected(self):
        evidence = self._bundle()
        bundle_path = Path(evidence[0]["path"])
        bundle = json.loads(bundle_path.read_text())
        native = Path(bundle["targetStage"]) / "native-result.json"
        native.write_text("{}", encoding="utf-8")
        result = scan(self.candidate, self.target, self.additions, self.files,
                      native_oracle=self.oracle, evidence_paths=evidence)
        self.assertTrue(any(row["code"] == "ASSET_REUSE_BATCH_RECEIPT" for row in result["conflicts"]))
        self.assertEqual([], result["externalAssets"])

    def test_batch_evidence_requires_complete_object_set_and_bound_journal(self):
        evidence = self._bundle()
        bundle = json.loads(Path(evidence[0]["path"]).read_text())
        stage = Path(bundle["sourceStage"])
        native_path, journal_path = stage / "native-result.json", stage / "journal.json"
        native = json.loads(native_path.read_text())
        native["assets"][0]["completeObjectSet"] = False
        write(native_path, (json.dumps(native, sort_keys=True, indent=2) + "\n").encode())
        journal = json.loads(journal_path.read_text())
        journal["native"] = native
        write(journal_path, (json.dumps(journal, sort_keys=True, indent=2) + "\n").encode())
        result = scan(self.candidate, self.target, self.additions, self.files,
                      native_oracle=self.oracle, evidence_paths=evidence)
        self.assertTrue(any(row["code"] == "ASSET_REUSE_BATCH_OBJECTS" for row in result["conflicts"]))
        self.assertEqual([], result["externalAssets"])

    def test_guid_beyond_native_meta_prefix_fails_closed(self):
        late_meta = b"x: " + (b"x" * 5000) + b"\n" + self.meta_bytes
        write(self.target / (self.asset + ".meta"), late_meta)
        result = scan(self.candidate, self.target, self.additions, self.files, native_oracle=self.oracle)
        self.assertTrue(any(row["code"] == "ASSET_REUSE_GUID_POSITION" for row in result["conflicts"]))
        self.assertEqual([], result["externalAssets"])


if __name__ == "__main__":
    unittest.main()
