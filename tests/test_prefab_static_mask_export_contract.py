import copy
import unittest

from test_prefab_static_mask_continuation import StaticMaskContinuationTests
from src.monkey.prefab_static_mask_continuation import (
    StaticMaskContinuationError, build_contract, validate_export_contract,
)


class StaticMaskExportContractTests(unittest.TestCase):
    def fixture(self):
        case = StaticMaskContinuationTests()
        plan, manifest, ids, _temp = case.fixture()
        self.addCleanup(lambda: getattr(case, "doCleanups")())
        plan["staticMasks"] = build_contract(plan, manifest)
        return plan, ids

    def test_no_source_mask_is_an_optional_noop_but_declared_empty_contract_is_rejected(self):
        self.assertEqual({"status": "not-required", "sourceMaskCount": 0, "sourceMaskIds": []},
                         validate_export_contract({"components": [], "staticMasks": None}))
        with self.assertRaisesRegex(StaticMaskContinuationError, "PRESENCE_MARKER_MISMATCH"):
            validate_export_contract({"components": [], "staticMasks": {}})

    def test_source_mask_without_missing_null_empty_or_wrong_contract_fails_before_editor(self):
        base, _ = self.fixture()
        for value in ("absent", None, {}, {"schemaVersion": 1, "contract": "monkey-static-mask-continuation/1",
                                           "sourceManifestSha256": base["sourceManifestSha256"], "masks": []}):
            plan = copy.deepcopy(base)
            if value == "absent":
                plan.pop("staticMasks")
            else:
                plan["staticMasks"] = value
            with self.subTest(contract=value):
                with self.assertRaises(StaticMaskContinuationError):
                    validate_export_contract(plan)

    def test_modern_contract_checks_full_component_fields_queue_and_source_default_scopes(self):
        plan, _ = self.fixture()
        result = validate_export_contract(plan)
        self.assertEqual("verified", result["status"])
        self.assertEqual(6, result["sourceMaskCount"])
        for mutation in ("component-node", "queue-disposition", "default-scope", "source-pin", "row-fields"):
            changed = copy.deepcopy(plan)
            contract = changed["staticMasks"]
            row = contract["masks"][0]
            if mutation == "component-node":
                changed["components"][0]["node"] = "other-node"
            elif mutation == "queue-disposition":
                row["sourceQueueDisposition"] = "outside-static-sort-queue-scope"
            elif mutation == "default-scope":
                contract["sourceDefaults"][0]["sourceIds"].pop()
            elif mutation == "source-pin":
                contract["sourceManifestSha256"] = "0" * 64
            else:
                row["sourceFieldsJson"] = "{}"
            with self.subTest(mutation=mutation):
                with self.assertRaises(StaticMaskContinuationError):
                    validate_export_contract(changed)

    def test_full_schema1_legacy_contract_is_accepted_but_incomplete_source_denominator_is_not(self):
        plan, ids = self.fixture()
        rows = copy.deepcopy(plan["staticMasks"]["masks"])
        plan["staticMasks"] = {"schemaVersion": 1, "contract": "",
            "sourceManifestSha256": plan["sourceManifestSha256"],
            "masks": rows}
        self.assertEqual("legacy-complete", validate_export_contract(plan)["status"])
        plan["staticMasks"]["masks"].pop()
        with self.assertRaisesRegex(StaticMaskContinuationError, "IDENTITY_DENOMINATOR_MISMATCH"):
            validate_export_contract(plan)

    def test_legacy_identity_complete_but_unmappable_mask_rows_fail_before_editor(self):
        plan, _ = self.fixture()
        rows = copy.deepcopy(plan["staticMasks"]["masks"])
        rows[0]["node"] = ""
        plan["staticMasks"] = {"schemaVersion": 1, "contract": "",
            "sourceManifestSha256": plan["sourceManifestSha256"], "masks": rows}
        with self.assertRaisesRegex(StaticMaskContinuationError, "STATIC_MASK_LEGACY_FIELDS_MISSING"):
            validate_export_contract(plan)


if __name__ == "__main__":
    unittest.main()
