import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from monkey.prefab_static_declarations import extract_declarations
from monkey.static_code_bindings import prepare


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


if __name__ == "__main__":
    unittest.main()
