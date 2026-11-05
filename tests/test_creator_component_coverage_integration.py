import tempfile
import unittest
from pathlib import Path

from fixtures import fixture
from monkey.io import finish, load, read, write_json
from monkey.normalize import normalize
from monkey.prefab_component_coverage import assess
from monkey.sources.bundle import inspect
from monkey.sources.containers import fingerprint
from monkey.targets import cocos
from monkey.targets.cocos import _creator_validation_summary


class CreatorComponentCoverageIntegrationTests(unittest.TestCase):
    def build_candidate(self, root):
        config = fixture(root / "source")
        inspect(config, [2], root / "inspect")
        normalize(root / "inspect/source-manifest.json", root / "ir")
        return cocos.plan(root / "ir/ir.json", "creator-component-coverage", root / "plan")

    def test_editor_verify_reports_nonconvertible_source_in_full_denominator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            plan = self.build_candidate(root)
            source_id = "fixture:custom-component#coverage"
            plan["components"].append({
                "sourceId": source_id,
                "node": plan["nodes"][0]["sourceId"],
                "type": "cc.CustomWidget",
                "nativeType": None,
                "convertible": False,
                "enabled": True,
            })
            plan["diagnostics"].append({
                "code": "COMPONENT_HANDOFF",
                "sourceId": source_id,
                "message": "Source component has no native Creator mapping",
            })
            write_json(root / "plan/plan.json", plan)
            finish(root / "plan", plan)
            cocos.export(root / "plan/plan.json", root / "candidate")

            import_plan = load(read(root / "candidate/extensions/monkey-import/import-plan.json"))
            self.assertEqual(len(import_plan["components"]), len(plan["components"]))
            self.assertEqual(sum(bool(row.get("convertible")) for row in import_plan["components"]),
                             sum(bool(row.get("convertible")) for row in plan["components"]))
            self.assertTrue(any(row.get("sourceId") == source_id
                                for row in import_plan["components"] if not row.get("convertible")))
            self.assertTrue(any(row.get("sourceId") == source_id
                                for row in import_plan["sourceDiagnostics"]))

            project = load(read(root / "candidate/manifest.json"))
            write_json(root / "candidate/Analysis/Readback/editor-readback.json", {
                "creatorVersion": "3.8.8",
                "projectUuid": project["projectUuid"],
                "manifestSha256": fingerprint(root / "candidate/manifest.json"),
                "assets": [],
                "nodeCount": len(import_plan["nodes"]),
                "components": [],
            })

            report = cocos.verify(root / "candidate", root / "verification", "editor")
            coverage = {row["sourceId"]: row for row in report["componentCoverage"]}
            self.assertEqual(report["componentCoverageSourceCount"], len(import_plan["components"]))
            self.assertEqual(len(coverage), len(import_plan["components"]))
            self.assertEqual(coverage[source_id]["disposition"], "unsupported")
            self.assertEqual(coverage[source_id]["sourceDiagnostics"][0]["code"], "COMPONENT_HANDOFF")
            self.assertEqual(report["nativeStaticValidation"], "fail")
            self.assertEqual(report["status"], "partial")
            self.assertNotEqual(report["staticPresentationValidation"]["status"], "pass")
            self.assertIn("SOURCE_COMPONENT_WITHOUT_NATIVE_DISPOSITION",
                          {row["code"] for row in report["diagnostics"]})

    def test_summary_gate_uses_real_whole_source_assessment_and_only_allows_dynamic_boundaries(self):
        plan = {
            "nodes": [{"sourceId": "node-source", "parent": None, "active": True}],
            "components": [{"sourceId": "sprite-source", "node": "node-source", "type": "cc.Sprite",
                            "nativeType": "cc.Sprite", "convertible": True, "enabled": True,
                            "spriteFrame": "asset:frame"}],
            "diagnostics": [],
        }
        readback = {
            "components": [{"sourceId": "sprite-source", "type": "cc.Sprite", "nativeType": "cc.Sprite",
                            "componentUuid": "creator-component-identity"}],
            "staticPresentationValidation": {"status": "pass", "components": [{
                "sourceId": "sprite-source", "sourceVisible": True, "verified": True, "rendered": True,
            }]},
        }
        coverage = assess(plan, readback, "creator")
        self.assertEqual(coverage["nativeStaticValidation"], "pass")
        self.assertEqual(coverage["staticPresentationValidation"]["status"], "pass")

        # The production aggregate accepts a complete static proof when the
        # only remaining evidence explicitly concerns dynamic behavior.
        allowed_dynamic = [
            {"code": "SPINE_SOURCE_UNBOUND_DYNAMIC_NOT_RUN", "severity": "warning"},
            {"code": "SPINE_DYNAMIC_BEHAVIOR_INCOMPLETE", "severity": "warning"},
            {"code": "ANIMATION_DYNAMIC_CURVES_NOT_LOWERED", "severity": "warning"},
        ]
        for editor_state in ("pass", "partial"):
            accepted = _creator_validation_summary(coverage, allowed_dynamic, editor_state)
            self.assertEqual(accepted, {"nativeStaticValidation": "pass", "staticPresentationStatus": "pass"})

        # Unknown/raw evidence and static resource, field, or file failures
        # downgrade a passing component coverage result.
        for raw in (
            "UNCLASSIFIED_CREATOR_DIAGNOSTIC",
            "MISSING_REFERENCE: asset:missing-frame",
            {"code": "NATIVE_STATIC_FIELD_READBACK_INCOMPLETE", "severity": "warning"},
            "NATIVE_FILE_CHANGED: assets/fixture.png",
        ):
            with self.subTest(diagnostic=raw):
                observed = assess(plan, {**readback, "diagnostics": [raw]}, "creator")
                self.assertEqual(observed["nativeStaticValidation"], "pass")
                for editor_state in ("pass", "partial"):
                    blocked = _creator_validation_summary(observed, observed["diagnostics"], editor_state)
                    self.assertNotEqual(blocked["nativeStaticValidation"], "pass")
                    self.assertNotEqual(blocked["staticPresentationStatus"], "pass")

        failed_execution = _creator_validation_summary(coverage, [], "fail")
        self.assertEqual(failed_execution["nativeStaticValidation"], "fail")
        self.assertEqual(failed_execution["staticPresentationStatus"], "partial")
        not_run = _creator_validation_summary(coverage, [], "not_run")
        self.assertEqual(not_run["nativeStaticValidation"], "not_run")
        self.assertEqual(not_run["staticPresentationStatus"], "not_run")


if __name__ == "__main__":
    unittest.main()
