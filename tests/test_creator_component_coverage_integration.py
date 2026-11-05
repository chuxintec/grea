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
from monkey.targets.cocos import _creator_validation_summary, _creator_blocking_diagnostics
from monkey.io import finish
from test_creator_presentation_evidence import _sprite_fixture


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
        plan, readback, _, _ = _sprite_fixture()
        coverage = assess(plan, readback, "creator")
        self.assertEqual(coverage["nativeStaticValidation"], "pass")
        self.assertEqual(coverage["staticPresentationValidation"]["status"], "pass")

        # Dynamic classifications are joined to the exact source type and a
        # complete static native row. The Spine node is source-inactive, so it
        # has no presentation requirement in this static-only fixture.
        coverage["components"].extend([
            {"sourceId": "spine-source", "sourceType": "sp.Skeleton", "disposition": "native",
             "nativeStatus": "pass", "nativeStaticFieldsVerified": True,
             "nativeComponentReadback": {"sourceId": "spine-source", "componentUuid": "spine-uuid"}},
            {"sourceId": "button-source", "sourceType": "cc.Button", "disposition": "native",
             "nativeStatus": "pass", "nativeStaticFieldsVerified": True,
             "nativeComponentReadback": {"sourceId": "button-source", "componentUuid": "button-uuid"}},
            {"sourceId": "scroll-source", "sourceType": "cc.ScrollView", "disposition": "native",
             "nativeStatus": "pass", "nativeStaticFieldsVerified": True,
             "nativeComponentReadback": {"sourceId": "scroll-source", "componentUuid": "scroll-uuid"}},
        ])
        dynamic_plan = {**plan, "animations": [{"id": "animation-source", "curves": []}]}

        # The production aggregate accepts a complete static proof when the
        # only remaining evidence explicitly concerns dynamic behavior.
        allowed_dynamic = [
            {"code": "SPINE_SOURCE_UNBOUND_DYNAMIC_NOT_RUN", "sourceId": "spine-source", "severity": "warning"},
            {"code": "SPINE_DYNAMIC_BEHAVIOR_INCOMPLETE", "sourceId": "spine-source", "severity": "warning"},
            {"code": "ANIMATION_DYNAMIC_CURVES_NOT_LOWERED", "sourceId": "animation-source", "severity": "warning"},
            {"code": "BUTTON_BUSINESS_UNBOUND", "sourceId": "button-source",
             "message": "Native Button generated; original handlers remain AI work", "severity": "warning"},
        ]
        for editor_state in ("pass", "partial"):
            accepted = _creator_validation_summary(coverage, allowed_dynamic, editor_state, dynamic_plan)
            self.assertEqual(accepted, {"nativeStaticValidation": "pass", "staticPresentationStatus": "pass"})

        # Inactive/malformed component ownership and Scroll evidence cannot be
        # dismissed as dynamic merely from their diagnostic names.
        for raw in (
            {"code": "SPINE_SOURCE_UNBOUND_DYNAMIC_NOT_RUN", "sourceId": "button-source"},
            {"code": "BUTTON_BUSINESS_UNBOUND", "sourceId": "button-source", "message": "static target graphic is unsupported"},
            {"code": "SCROLL_PHYSICS_NOT_VERIFIED", "sourceId": "scroll-source"},
        ):
            blocked = _creator_validation_summary(coverage, [*allowed_dynamic, raw], "pass", dynamic_plan)
            self.assertNotEqual(blocked["nativeStaticValidation"], "pass")

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
                    blocked = _creator_validation_summary(observed, observed["diagnostics"], editor_state, plan)
                    self.assertNotEqual(blocked["nativeStaticValidation"], "pass")
                    self.assertNotEqual(blocked["staticPresentationStatus"], "pass")

        failed_execution = _creator_validation_summary(coverage, [], "fail", plan)
        self.assertEqual(failed_execution["nativeStaticValidation"], "fail")
        self.assertEqual(failed_execution["staticPresentationStatus"], "partial")
        not_run = _creator_validation_summary(coverage, [], "not_run", plan)
        self.assertEqual(not_run["nativeStaticValidation"], "not_run")
        self.assertEqual(not_run["staticPresentationStatus"], "not_run")

    def test_finish_keeps_dynamic_diagnostics_in_report_but_only_allows_exact_proven_boundaries(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "candidate"
            output.mkdir()
            dynamic_coverage = {
                "components": [{"sourceId": "spine-source", "sourceType": "sp.Skeleton",
                    "nativeStatus": "pass", "disposition": "native", "nativeStaticFieldsVerified": True,
                    "nativeComponentReadback": {"componentUuid": "creator-component"}}],
            }
            diagnostics = [{"code": "SPINE_DYNAMIC_BEHAVIOR_INCOMPLETE", "sourceId": "spine-source"}]
            plan = {"components": []}
            report = {"targetProfile": "cocos-3.8.8", "staticValidation": "pass", "editorValidation": "pass",
                "nativeStaticValidation": "pass", "staticPresentationValidation": {"status": "not_run",
                    "expectedSourceVisibleCount": 0}, "diagnostics": diagnostics}
            blockers = _creator_blocking_diagnostics(report, dynamic_coverage, diagnostics, plan)
            result = finish(output, report, blocking_diagnostics=blockers)
            self.assertEqual(result["status"], "candidate")
            self.assertEqual(result["diagnostics"], diagnostics)

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "candidate"
            output.mkdir()
            diagnostics = [{"code": "UNKNOWN_STATIC_CREATOR_FAILURE", "sourceId": "sprite-source"}]
            report = {"targetProfile": "cocos-3.8.8", "staticValidation": "pass", "editorValidation": "pass",
                "nativeStaticValidation": "pass", "staticPresentationValidation": {"status": "pass",
                    "expectedSourceVisibleCount": 1}, "diagnostics": diagnostics}
            result = finish(output, report,
                blocking_diagnostics=_creator_blocking_diagnostics(report, {"components": []}, diagnostics, {}))
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["diagnostics"], diagnostics)


if __name__ == "__main__":
    unittest.main()
