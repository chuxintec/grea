import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from monkey.prefab_static_declarations import extract_declarations
from monkey.static_code_bindings import prepare, _compatible_catalog, write_destination_index, _selected_mapping_ids, record_destinations


class StaticCodeBindingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.raw = (b'cc._RF.push({exports:{}},"source-uuid","Panel");'
                    b'var p=cc._decorator.property;var A=function(e){function A(){'
                    b'var t=e.call(this)||this;return t.speed=0.7,t;}return '
                    b'n([p(cc.Float)],A.prototype,"speed",void 0),A;}(cc.Component);cc._RF.pop()')
        self.path = self.root / "source.js"
        self.path.write_bytes(self.raw)
        self.pin = hashlib.sha256(self.raw).hexdigest()
        self.result = extract_declarations(self.path, self.pin, ["source-uuid"])
        self.modules = [dict(sourceId="pkg:file.js#Panel@0", sourceSnapshotPath="file.js",
                             source_bytes=dict(start=0, end=len(self.raw)), sha256=self.pin, name="Panel", draft="outside/Panel.cs")]
        self.bindings, components, nodes = [], [], []
        for i in (1, 2):
            node = f"asset:one#{i}"
            sid = node + "/components/0"
            self.bindings.append(dict(sourceComponent=sid, sourceNode=node, sourceAsset="asset:one",
                                      codeRegion="pkg:file.js#Panel@0", evidence="exact_literal_script_identity"))
            components.append(dict(sourceId=sid, node=node, type="source-uuid", staticFieldSnapshot=dict(
                sourceId=sid, node=node, sourceType="source-uuid", declarationDefaults="unverified",
                gaps=["source_declaration_defaults_not_verified"], fields=[dict(name="speed", kind="float", value=i)])))
            nodes.append(dict(sourceId=node))
        self.ir = dict(components=components, nodes=nodes, sourceManifestSha256="a" * 64)
        self.declarations = {"file.js": dict(sha256=self.pin, result=self.result)}

    def tearDown(self):
        self.temp.cleanup()

    def run_prepare(self, **kwargs):
        return prepare(kwargs.get("ir", self.ir), kwargs.get("bindings", self.bindings), self.modules,
                       kwargs.get("files", {"file.js": self.raw}), self.declarations, self.root / "out")

    def test_one_type_multiple_instances_keep_values_and_source_ids(self):
        report = self.run_prepare()
        self.assertEqual(report["mappingCount"], 2)
        self.assertEqual(report["targetTypeCount"], 1)
        specs = [r["spec"] for r in report["mappings"]]
        self.assertEqual(specs[0]["scriptGuid"], specs[1]["scriptGuid"])
        self.assertNotEqual(specs[0]["sourceId"], specs[1]["sourceId"])
        self.assertEqual([s["fields"][0]["numberValue"] for s in specs], [1, 2])
        code = (self.root / "out/generated" / specs[0]["scriptPath"]).read_text()
        self.assertIn("class Panel : MonoBehaviour", code)
        self.assertNotIn("void OnEnable", code)
        self.assertTrue(all(r["nativeStatus"] == "not_executed" for r in report["mappings"]))

    def test_wrong_node_does_not_remove_denominator(self):
        bindings = copy.deepcopy(self.bindings)
        bindings[0]["sourceNode"] = "asset:one#2"
        report = self.run_prepare(bindings=bindings)
        self.assertEqual(len(report["mappings"]), 2)
        self.assertEqual(report["mappings"][0]["disposition"], "blocked")
        self.assertIn("source_node_mismatch", report["mappings"][0]["reasons"][0])

    def test_changed_source_refuses_preparation(self):
        report = self.run_prepare(files={"file.js": self.raw.replace(b"0.7", b"0.8")})
        self.assertTrue(all(r["disposition"] == "blocked" for r in report["mappings"]))

    def test_duplicate_input_is_not_coverage(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.run_prepare(bindings=[self.bindings[0], self.bindings[0]])

    def test_same_name_different_literal_regions_do_not_share_script(self):
        other = self.raw.replace(b"source-uuid", b"other--uuid")
        path = self.root / "other.js"
        path.write_bytes(other)
        pin = hashlib.sha256(other).hexdigest()
        self.modules.append(dict(self.modules[0], sourceId="pkg:other.js#Panel@0", sourceSnapshotPath="other.js", sha256=pin))
        self.declarations["other.js"] = dict(sha256=pin, result=extract_declarations(path, pin, ["other--uuid"]))
        self.ir["components"][1]["type"] = "other--uuid"
        self.ir["components"][1]["staticFieldSnapshot"]["sourceType"] = "other--uuid"
        self.bindings[1]["codeRegion"] = "pkg:other.js#Panel@0"
        report = self.run_prepare(files={"file.js": self.raw, "other.js": other})
        self.assertEqual(report["targetTypeCount"], 2)
        self.assertNotEqual(*[r["spec"]["scriptGuid"] for r in report["mappings"]])

    def test_unproven_empty_class_is_explicitly_blocked(self):
        self.declarations["file.js"]["result"]["components"]["source-uuid"]["fields"] = []
        for c in self.ir["components"]:
            c["staticFieldSnapshot"]["fields"] = []
        report = self.run_prepare()
        self.assertEqual(report["targetTypeCount"], 0)
        self.assertTrue(all("empty_class_not_coverage" in r["reasons"][0] for r in report["mappings"]))

    def test_unknown_source_decorator_alias_stays_a_gap(self):
        self.declarations["file.js"]["result"]["components"]["source-uuid"]["propertyTypes"][0]["types"] = ["UnresolvedAlias"]
        report = self.run_prepare()
        self.assertEqual(report["targetTypeCount"], 1)
        self.assertTrue(all("source_declared_type_alias_unresolved:speed:UnresolvedAlias" in r["spec"]["gaps"] for r in report["mappings"]))

    def test_conflicting_serialized_field_names_are_not_silently_merged(self):
        for c in self.ir["components"]:
            c["staticFieldSnapshot"]["fields"].append(dict(name="speed", kind="string", value="conflict"))
        report = self.run_prepare()
        self.assertTrue(all(r["reasons"] == ["source_snapshot_field_conflict"] for r in report["mappings"]))

    def test_compatible_evidence_allows_only_added_alias_diagnostics(self):
        old = self.run_prepare()
        current = copy.deepcopy(old)
        current["mappings"][0]["spec"]["gaps"].append("source_declared_type_alias_unresolved:owner:Alias")
        self.assertTrue(_compatible_catalog(old, current))
        current["mappings"][0]["spec"]["fields"][0]["numberValue"] = 999
        self.assertFalse(_compatible_catalog(old, current))

    def test_compatibility_cannot_remove_gaps_or_change_source_proof(self):
        old = self.run_prepare()
        current = copy.deepcopy(old)
        old["mappings"][0]["spec"]["gaps"].append("missing_reference")
        self.assertFalse(_compatible_catalog(old, current))
        current = copy.deepcopy(old)
        current["mappings"][0]["proof"]["moduleSha256"] = "b" * 64
        self.assertFalse(_compatible_catalog(old, current))

    def test_destination_index_preserves_every_row_and_enforces_hash_budget(self):
        rows = [dict(sourceComponent=f"asset:one#{i}/components/0", payload="x" * 250) for i in range(10)]
        ledger = dict(schemaVersion="monkey-static-code-destinations/1", mappingCount=len(rows), mappings=rows)
        index = write_destination_index(ledger, self.root / "index", max_bytes=4096)
        restored = []
        for shard in index["shards"]:
            raw = (self.root / "index" / shard["path"]).read_bytes()
            self.assertLessEqual(len(raw), 4096)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), shard["sha256"])
            restored.extend(json.loads(raw)["mappings"])
        self.assertEqual(restored, rows)

    def test_oversized_mapping_is_refused_without_a_partial_index(self):
        ledger = dict(mappingCount=1, mappings=[dict(sourceComponent="asset:one#1", payload="x" * 5000)])
        with self.assertRaisesRegex(ValueError, "exceeds"):
            write_destination_index(ledger, self.root / "index", max_bytes=4096)
        self.assertFalse((self.root / "index").exists())

    def test_scene_node_in_a_legacy_request_is_not_a_prefab_attempt(self):
        request = dict(prefabs=[dict(sourceId="asset:one", path="Assets/One.prefab")], mappings=[
            dict(sourceComponent="prefab-component", sourceNode="asset:one#1"),
            dict(sourceComponent="scene-component", sourceNode="scene:one#1")])
        plan = dict(sourcePrefabs=[dict(sourceId="asset:one", path="Assets/One.prefab", nodes=["asset:one#1"])])
        self.assertEqual(_selected_mapping_ids(request, plan), {"prefab-component"})
        request["prefabs"][0]["path"] = "Assets/Wrong.prefab"
        with self.assertRaisesRegex(ValueError, "scope"):
            _selected_mapping_ids(request, plan)

    def _native_fixture(self):
        # Protocol fixture only. Real Unity evidence is exercised separately;
        # these tiny YAML files let every missing/duplicate edge vary in tests.
        c = self.ir["components"][1]
        c["sourceId"], c["node"] = "asset:two#1/components/0", "asset:two#1"
        c["staticFieldSnapshot"].update(sourceId=c["sourceId"], node=c["node"])
        self.ir["nodes"][1]["sourceId"] = c["node"]
        self.bindings[1].update(sourceComponent=c["sourceId"], sourceNode=c["node"], sourceAsset="asset:two")
        report = self.run_prepare()
        prepared, candidate = self.root / "out", self.root / "native"
        folder = candidate / "Analysis/StaticCodeBindings"
        folder.mkdir(parents=True)
        (folder / "bindings.json").write_bytes((prepared / "bindings.json").read_bytes())
        for script in report["scripts"]:
            for relative in (script["target"], script["target"] + ".meta"):
                dest = candidate / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(prepared / "generated" / relative, dest)
        prefabs, plan_rows, observations = [], [], []
        for i, row in enumerate(report["mappings"], 1):
            guid = str(i) * 32
            path = f"Assets/P{i}.prefab"
            spec = row["spec"]
            raw = (f"%YAML 1.1\n--- !u!1 &{i}\nGameObject:\n  m_Name: N{i}\n"
                   f"--- !u!114 &{100+i}\nMonoBehaviour:\n  m_GameObject: {{fileID: {i}}}\n"
                   f"  m_Script: {{fileID: 11500000, guid: {spec['scriptGuid']}, type: 3}}\n"
                   f"  m_Enabled: 0\n  m_EditorClassIdentifier: Assembly-CSharp::{spec['typeName']}\n"
                   f"  __monkeySourceId: {row['sourceComponent']}\n").encode()
            target = candidate / path
            target.write_bytes(raw)
            Path(str(target) + ".meta").write_text("fileFormatVersion: 2\nguid: " + guid + "\n")
            prefabs.append(dict(sourceId=row["sourceAsset"], path=path, guid=guid, sha256=hashlib.sha256(raw).hexdigest()))
            plan_rows.append(dict(sourceId=row["sourceAsset"], path=path, nodes=[row["sourceNode"]]))
            read = dict(sourceId=row["sourceComponent"], typeName=spec["typeName"], nativeSourceId=row["sourceComponent"],
                        nativeScriptGuid=spec["scriptGuid"], fieldsVerified=True, nativeIdentityVerified=True,
                        nativeComplete=True, enabled=False, dynamicBehaviorComplete=False, gaps=[], fields=spec["fields"])
            observations.append(dict(sourceComponent=row["sourceComponent"], sourceNode=row["sourceNode"], sourceAsset=row["sourceAsset"],
                prefabPath=path, nodeGuid=guid, componentGuid=guid, nodeLocalId=i, componentLocalId=100+i,
                fullType=spec["typeName"], assembly="Assembly-CSharp", scriptGuid=spec["scriptGuid"],
                ownerVerified=True, persistent=True, identityStable=True, readback=read))
        plan = candidate / "Analysis/plan.json"
        plan.write_text(json.dumps(dict(sourcePrefabs=plan_rows)))
        request = dict(schemaVersion="monkey-static-code-bindings-request/1", stageId="protocol-test", planPath="Analysis/plan.json", planSha256=hashlib.sha256(plan.read_bytes()).hexdigest(),
                       bindingsSha256=hashlib.sha256((folder / "bindings.json").read_bytes()).hexdigest(),
                       prefabs=prefabs, mappings=report["mappings"], scripts=report["scripts"])
        request_path = folder / "request.json"
        request_path.write_text(json.dumps(request))
        receipt = dict(requestSha256=hashlib.sha256(request_path.read_bytes()).hexdigest(), prefabs=prefabs,
                       observations=observations, controls=[dict(sourceComponent=r["sourceComponent"], rejected=True) for r in report["mappings"]], errors=[])
        settings = candidate / "ProjectSettings"
        settings.mkdir()
        (settings / "ProjectVersion.txt").write_text("m_EditorVersion: 6000.6.2f1\n")
        for ordinal, phase in enumerate(("apply", "cold"), 1):
            receipt.update(schemaVersion="monkey-static-code-native/2", stageId="protocol-test", phase=phase,
                           unityVersion="6000.6.2f1", processId=ordinal, processStartUtcTicks=ordinal*10,
                           observedUtcTicks=ordinal*10+1)
            if phase == "cold":
                receipt["priorApplySha256"] = hashlib.sha256((folder/"apply.json").read_bytes()).hexdigest()
            (folder / (phase + ".json")).write_text(json.dumps(receipt))
        return prepared, candidate

    def test_wrong_cold_identity_blocks_every_observation(self):
        prepared, candidate = self._native_fixture()
        path = candidate / "Analysis/StaticCodeBindings/cold.json"
        original = json.loads(path.read_bytes())
        for key, value in (("phase", "apply"), ("schemaVersion", "legacy"), ("stageId", "other"),
                           ("unityVersion", "other"), ("processStartUtcTicks", 10), ("processId", 0), ("processId", 1),
                           ("priorApplySha256", "forged")):
            with self.subTest(key=key):
                path.write_text(json.dumps(dict(original, **{key: value})))
                ledger = record_destinations(prepared, [candidate], self.root / (key + ".json"))
                self.assertEqual(ledger["counts"], {"blocked": 2})
                self.assertTrue(ledger["hasEvidenceContractGaps"])

    def test_native_closure_positive_preserves_both_instances(self):
        prepared, candidate = self._native_fixture()
        result = record_destinations(prepared, [candidate], self.root / "ledger.json")
        self.assertEqual(result["counts"], {"success": 2})
        self.assertFalse(result["hasEvidenceContractGaps"])
        self.assertTrue(all(d["evidenceClosureVerified"] for r in result["mappings"] for d in r["destinations"]))

    def test_native_file_and_instance_tampering_is_local_to_affected_prefab(self):
        prepared, base = self._native_fixture()
        for change in ("delete-file-and-cold-row", "missing-cold-row", "missing-apply-row", "duplicate-cold-row",
                       "missing-cold-instance", "missing-apply-instance", "duplicate-cold-instance",
                       "wrong-instance-local-id", "wrong-node-local-id", "wrong-observation-path",
                       "wrong-disk-script", "wrong-disk-source", "wrong-assembly", "enabled-on-disk"):
            with self.subTest(change=change):
                candidate = self.root / change
                shutil.copytree(base, candidate)
                folder = candidate / "Analysis/StaticCodeBindings"
                apply = json.loads((folder / "apply.json").read_bytes())
                cold = json.loads((folder / "cold.json").read_bytes())
                if change in ("delete-file-and-cold-row", "missing-cold-row"):
                    cold["prefabs"] = cold["prefabs"][1:]
                    if change == "delete-file-and-cold-row":
                        (candidate / "Assets/P1.prefab").unlink()
                elif change == "missing-apply-row":
                    apply["prefabs"] = apply["prefabs"][1:]
                elif change == "duplicate-cold-row":
                    cold["prefabs"].append(cold["prefabs"][0])
                elif change == "missing-cold-instance":
                    cold["observations"] = cold["observations"][1:]
                elif change == "missing-apply-instance":
                    apply["observations"] = apply["observations"][1:]
                elif change == "duplicate-cold-instance":
                    cold["observations"].append(cold["observations"][0])
                elif change in ("wrong-instance-local-id", "wrong-node-local-id"):
                    key = "componentLocalId" if change == "wrong-instance-local-id" else "nodeLocalId"
                    for receipt in (apply, cold):
                        receipt["observations"][0][key] = 999
                elif change == "wrong-observation-path":
                    for receipt in (apply, cold):
                        receipt["observations"][0]["prefabPath"] = "Assets/P2.prefab"
                elif change == "wrong-assembly":
                    for receipt in (apply, cold):
                        receipt["observations"][0]["assembly"] = "WrongAssembly"
                else:
                    path = candidate / "Assets/P1.prefab"
                    raw = path.read_text()
                    if change == "wrong-disk-script":
                        raw = raw.replace(cold["observations"][0]["scriptGuid"], "0" * 32)
                    elif change == "wrong-disk-source":
                        raw = raw.replace("__monkeySourceId: asset:one#1/components/0", "__monkeySourceId: WRONG")
                    else:
                        raw = raw.replace("m_Enabled: 0", "m_Enabled: 1")
                    path.write_text(raw)
                    for receipt in (apply, cold):
                        receipt["prefabs"][0]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                for phase, receipt in (("apply", apply), ("cold", cold)):
                    if phase == "cold":
                        receipt["priorApplySha256"] = hashlib.sha256((folder/"apply.json").read_bytes()).hexdigest()
                    (folder / (phase + ".json")).write_text(json.dumps(receipt))
                result = record_destinations(prepared, [candidate], self.root / (change + ".json"))
                dispositions = {r["sourceComponent"]: r["disposition"] for r in result["mappings"]}
                self.assertEqual(dispositions["asset:one#1/components/0"], "blocked")
                self.assertEqual(dispositions["asset:two#1/components/0"], "success")
                self.assertTrue(result["hasEvidenceContractGaps"])
                affected = next(r for r in result["mappings"] if r["sourceComponent"] == "asset:one#1/components/0")
                self.assertFalse(affected["destinations"][0]["evidenceClosureVerified"])


if __name__ == "__main__":
    unittest.main()
