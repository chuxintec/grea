import unittest

from monkey.prefab_component_coverage import assess


class ComponentCoverageTests(unittest.TestCase):
    def setUp(self):
        self.plan = {
            "nodes": [{"sourceId": "node-a", "parent": None, "active": True}],
            "components": [{
                "sourceId": "component-a", "node": "node-a", "type": "cc.Sprite",
                "nativeType": "cc.Sprite", "convertible": True, "enabled": True,
            }],
            "diagnostics": [],
        }
        self.native = {"components": [{
            "sourceId": "component-a", "type": "cc.Sprite", "componentUuid": "native-uuid-a",
        }]}

    def test_full_source_denominator_keeps_nonconvertible_unsupported_component(self):
        plan = {
            "nodes": self.plan["nodes"],
            "components": [self.plan["components"][0], {
                "sourceId": "unsupported-a", "node": "node-a", "type": "cc.CustomWidget",
                "nativeType": None, "convertible": False, "enabled": True,
            }],
            "diagnostics": [{"code": "COMPONENT_HANDOFF", "sourceId": "unsupported-a", "message": "not in profile"}],
        }
        result = assess(plan, self.native, "creator")
        self.assertEqual(result["sourceComponentCount"], 2)
        self.assertEqual(len(result["components"]), 2)
        row = next(row for row in result["components"] if row["sourceId"] == "unsupported-a")
        self.assertEqual(row["disposition"], "unsupported")
        self.assertEqual(row["sourceDiagnostics"][0]["code"], "COMPONENT_HANDOFF")
        self.assertEqual(result["nativeStaticValidation"], "fail")
        self.assertEqual(result["playerValidation"], "not_run")

    def test_missing_native_component_cannot_pass_from_convertible_source_plan(self):
        result = assess(self.plan, {"components": []}, "creator")
        self.assertEqual(result["components"][0]["disposition"], "missing")
        self.assertEqual(result["nativeStaticValidation"], "fail")
        self.assertTrue(any(row["code"] == "SOURCE_COMPONENT_WITHOUT_NATIVE_DISPOSITION" for row in result["diagnostics"]))

    def test_explicit_native_identity_failure_is_not_overridden_by_uuid(self):
        readback = {"components": [{
            "sourceId": "component-a", "type": "cc.Sprite", "componentUuid": "uuid-present",
            "sourceIdentityVerified": False, "persistent": True,
        }]}
        result = assess(self.plan, readback, "unity")
        self.assertEqual(result["components"][0]["disposition"], "missing")
        self.assertEqual(result["nativeStaticValidation"], "fail")

    def test_retained_only_does_not_promote_native_or_static_presentation(self):
        readback = {"retainedComponents": [{
            "sourceId": "component-a", "status": "verified", "verified": True,
            "sourceIdentityVerified": True, "representation": "opaque-source-evidence",
        }]}
        result = assess(self.plan, readback, "unity")
        self.assertEqual(result["components"][0]["disposition"], "retained")
        self.assertEqual(result["retentionValidation"], "pass")
        self.assertEqual(result["nativeStaticValidation"], "partial")
        self.assertNotEqual(result["staticPresentationValidation"]["status"], "pass")

    def test_static_fields_need_actual_identity_and_field_readback(self):
        plan = {**self.plan, "components": [{**self.plan["components"][0], "staticFieldBinding": {
            "fields": [{"sourceFieldName": "spriteFrame", "name": "spriteFrame"}],
        }}]}
        result = assess(plan, self.native, "creator")
        self.assertEqual(result["nativeStaticValidation"], "partial")
        readback = {**self.native, "staticFieldBindings": [{
            "sourceId": "component-a", "nativeIdentityVerified": True, "fieldsVerified": True,
            "fields": [{"sourceFieldName": "spriteFrame", "referenceVerified": True}],
        }]}
        result = assess(plan, readback, "creator")
        self.assertEqual(result["components"][0]["staticFieldStatus"], "verified")
        self.assertEqual(result["nativeStaticValidation"], "pass")
        self.assertEqual(result["staticPresentationValidation"]["status"], "partial")

    def test_verified_static_field_carrier_is_disabled_not_native_complete(self):
        plan = {"nodes": self.plan["nodes"], "components": [{
            "sourceId": "script-a", "node": "node-a", "type": "cc.Component",
            "nativeType": None, "convertible": False,
            "staticFieldBinding": {"fields": [{"sourceFieldName": "target", "name": "target"}]},
        }]}
        readback = {"staticFieldBindings": [{
            "sourceId": "script-a", "nativeIdentityVerified": True, "fieldsVerified": True,
            "fields": [{"sourceFieldName": "target", "verified": True}],
        }]}
        result = assess(plan, readback, "creator")
        self.assertEqual(result["components"][0]["disposition"], "disabled")
        self.assertEqual(result["components"][0]["staticFieldStatus"], "verified")
        self.assertEqual(result["nativeStaticValidation"], "partial")
        self.assertEqual(result["retentionValidation"], "not_applicable")

    def test_verified_presentation_requires_native_row_and_rendered_evidence(self):
        readback = {
            **self.native,
            "staticPresentationValidation": {"status": "pass", "components": [{
                "sourceId": "component-a", "sourceVisible": True, "verified": True, "rendered": True,
            }]},
        }
        result = assess(self.plan, readback, "creator")
        self.assertEqual(result["staticPresentationValidation"]["status"], "pass")
        self.assertEqual(result["nativeStaticValidation"], "pass")
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["runtimeCheck"], "not_run")

    def test_source_visible_nonrendering_spine_stays_partial_even_if_retained(self):
        plan = {
            "nodes": self.plan["nodes"],
            "components": [{"sourceId": "spine-a", "node": "node-a", "type": "sp.Skeleton",
                            "convertible": False, "enabled": True}],
            "staticSpineContinuation": {"components": [{"sourceComponentId": "spine-a"}]},
        }
        readback = {
            "staticSpineContinuation": {"status": "verified", "sourceComponentIds": ["spine-a"]},
            "retainedComponents": [{"sourceId": "spine-a", "status": "verified", "verified": True,
                                    "sourceIdentityVerified": True, "representation": "non-rendering-static-spine"}],
        }
        result = assess(plan, readback, "unity")
        row = result["components"][0]
        self.assertEqual(row["disposition"], "retained")
        self.assertEqual(result["retentionValidation"], "pass")
        self.assertEqual(result["nativeStaticValidation"], "partial")
        self.assertEqual(result["staticPresentationValidation"]["status"], "partial")
        self.assertTrue(any(row["code"] == "SOURCE_VISIBLE_SPINE_NOT_RENDERED" for row in result["diagnostics"]))

        incomplete = assess(plan, {}, "unity")
        self.assertEqual(incomplete["retentionValidation"], "not_run")
        self.assertNotEqual(incomplete["nativeStaticValidation"], "pass")

    def test_native_presentation_gap_is_preserved_when_known_visual_rows_pass(self):
        readback = {**self.native, "staticPresentationValidation": {
            "status": "partial", "components": [{
                "sourceId": "component-a", "sourceVisible": True, "verified": True, "rendered": True,
            }, {"sourceId": "unknown-role", "verified": False, "reason": "source-static-role-unproven"}],
        }}
        result = assess(self.plan, readback, "creator")
        self.assertEqual(result["nativeStaticValidation"], "pass")
        self.assertEqual(result["staticPresentationValidation"]["status"], "partial")
        self.assertEqual(result["status"], "partial")
        self.assertIn("STATIC_PRESENTATION_NATIVE_INCOMPLETE", [row["code"] for row in result["diagnostics"]])

    def test_duplicate_or_missing_source_identity_stays_in_denominator(self):
        plan = {"components": [
            {"sourceId": "duplicate", "type": "cc.Sprite", "convertible": True},
            {"sourceId": "duplicate", "type": "cc.Sprite", "convertible": True},
            {"type": "cc.Label", "convertible": False},
        ]}
        result = assess(plan, {"components": []}, "creator")
        self.assertEqual(result["sourceComponentCount"], 3)
        self.assertEqual(len(result["components"]), 3)
        self.assertEqual(sum(result["dispositionCounts"].values()), 3)
        self.assertTrue(any(row["code"] == "SOURCE_COMPONENT_ID_DUPLICATE" for row in result["diagnostics"]))
        self.assertTrue(any(row["code"] == "SOURCE_COMPONENT_ID_MISSING" for row in result["diagnostics"]))

    def test_no_editor_readback_is_not_run_and_never_passes(self):
        result = assess(self.plan, {}, "creator")
        self.assertEqual(result["nativeStaticValidation"], "not_run")
        self.assertEqual(result["staticPresentationValidation"]["status"], "not_run")
        self.assertEqual(result["components"][0]["nativeStatus"], "not_run")
        self.assertEqual(result["playerValidation"], "not_run")

    def test_source_and_raw_native_diagnostics_are_preserved(self):
        plan = {**self.plan, "diagnostics": [{"code": "SOURCE_GAP", "sourceId": "component-a", "message": "original"}]}
        readback = {**self.native, "diagnostics": ["NATIVE_GAP: component-a"]}
        result = assess(plan, readback, "creator")
        self.assertTrue(any(row.get("code") == "SOURCE_GAP" for row in result["sourceDiagnostics"]))
        raw = next(row for row in result["diagnostics"] if row.get("rawDiagnostic"))
        self.assertEqual(raw["rawDiagnostic"], "NATIVE_GAP: component-a")

    def test_creator_full_source_observations_only_accept_actual_uuid_rows(self):
        readback = {"sourceComponentCoverage": [{
            "sourceIndex": 0, "sourceId": "component-a", "sourceType": "cc.Sprite",
            "nativeComponentReadback": [{"sourceId": "component-a", "type": "cc.Sprite",
                                          "nativeType": "cc.Sprite", "componentUuid": "actual-uuid"}],
        }]}
        result = assess(self.plan, readback, "creator")
        self.assertEqual(result["sourceComponentCount"], 1)
        self.assertEqual(result["components"][0]["nativeComponentReadback"]["componentUuid"], "actual-uuid")
        self.assertEqual(result["nativeStaticValidation"], "pass")

        readback["components"] = [{"sourceId": "component-a", "type": "cc.Sprite",
                                   "nativeType": "cc.Sprite", "componentUuid": "actual-uuid"}]
        result = assess(self.plan, readback, "creator")
        self.assertEqual(result["components"][0]["disposition"], "native")

        fabricated = {"sourceComponentCoverage": [{
            "sourceIndex": 0, "sourceId": "component-a", "sourceType": "cc.Sprite",
            "nativeComponentReadback": [{"sourceId": "component-a", "type": "cc.Sprite"}],
        }]}
        result = assess(self.plan, fabricated, "creator")
        self.assertEqual(result["components"][0]["disposition"], "missing")
        self.assertEqual(result["nativeStaticValidation"], "fail")

    def test_creator_prefab_component_rows_fill_full_prefab_coverage(self):
        readback = {"components": [], "sourcePrefabs": [{"components": [{
            "sourceId": "component-a", "type": "cc.Sprite", "nativeType": "cc.Sprite",
            "componentUuid": "prefab-native-uuid",
        }]}]}
        result = assess(self.plan, readback, "creator")
        self.assertEqual(result["components"][0]["disposition"], "native")


if __name__ == "__main__":
    unittest.main()
