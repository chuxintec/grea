import unittest

from monkey.prefab_static_acceptance import STATIC_CRITERIA, evaluate_static_acceptance


def accepted_record():
    record = {name: {"status": "pass", "evidenceId": f"receipt:{name}"} for name in STATIC_CRITERIA}
    record["sourceVersion"] = "1.9.1"
    record["referenceVersion"] = "1.9.5"
    record["static_render"].update(
        comparisonScope="shared visible hierarchy and asset identity",
        versionDifferences=["source artwork may differ by release"],
    )
    return record


def two_target_evidence(record):
    return {"P01": {"creator": record, "unity": record}}


class PrefabStaticAcceptanceTests(unittest.TestCase):
    def test_static_pass_does_not_depend_on_dynamic_completion(self):
        record = accepted_record()
        record["dynamic_behavior"] = {"status": "partial", "evidenceId": "probe:dynamic"}
        record["physical_input"] = {"status": "not_run"}
        result = evaluate_static_acceptance(["P01"], two_target_evidence(record))
        self.assertEqual(result["dualTargetStaticPassCount"], 1)
        self.assertEqual(result["matrix"][0]["targets"]["creator"]["staticAcceptance"], "pass")
        self.assertEqual(result["matrix"][0]["targets"]["creator"]["dynamic"]["dynamic_behavior"]["status"], "partial")

    def test_missing_unknown_subset_and_empty_evidence_never_pass(self):
        record = accepted_record()
        record["hierarchy"] = {"status": "pass", "evidenceId": "  "}
        record["components_fields"] = {"status": "subset", "evidenceId": "receipt:subset"}
        del record["asset_references"]
        result = evaluate_static_acceptance(["P01"], two_target_evidence(record))
        criteria = result["matrix"][0]["targets"]["creator"]["criteria"]
        self.assertEqual(criteria["hierarchy"]["status"], "not_run")
        self.assertEqual(criteria["components_fields"]["status"], "not_run")
        self.assertEqual(criteria["asset_references"]["status"], "not_run")
        self.assertEqual(result["dualTargetStaticPassCount"], 0)

    def test_cross_version_render_needs_scope_and_difference_record(self):
        record = accepted_record()
        record["static_render"] = {"status": "pass", "evidenceId": "image:one"}
        result = evaluate_static_acceptance(["P01"], two_target_evidence(record))
        self.assertEqual(
            result["matrix"][0]["targets"]["creator"]["criteria"]["static_render"]["status"],
            "not_run",
        )
        record["static_render"].update(comparisonScope="matching common region", versionDifferences=[])
        result = evaluate_static_acceptance(["P01"], two_target_evidence(record))
        self.assertEqual(
            result["matrix"][0]["targets"]["creator"]["criteria"]["static_render"]["status"],
            "pass",
        )
        for invalid_differences in (None, "none", ["known", None], {}):
            record["static_render"]["versionDifferences"] = invalid_differences
            result = evaluate_static_acceptance(["P01"], two_target_evidence(record))
            self.assertEqual(
                result["matrix"][0]["targets"]["creator"]["criteria"]["static_render"]["status"],
                "not_run",
            )

    def test_render_pass_requires_nonempty_versions_even_when_equal(self):
        record = accepted_record()
        record["sourceVersion"] = ""
        record["referenceVersion"] = "1.9.1"
        result = evaluate_static_acceptance(["P01"], two_target_evidence(record))
        self.assertEqual(
            result["matrix"][0]["targets"]["creator"]["criteria"]["static_render"]["status"],
            "not_run",
        )

    def test_thirteen_sample_denominator_and_ten_dual_target_threshold(self):
        samples = [f"P{i:02}" for i in range(1, 14)]
        evidence = {sample: {"creator": accepted_record(), "unity": accepted_record()} for sample in samples[:10]}
        result = evaluate_static_acceptance(samples, evidence, required_samples=13)
        self.assertEqual(result["denominator"], 13)
        self.assertEqual(result["dualTargetStaticPassCount"], 10)
        self.assertTrue(result["firstPhaseComplete"])
        with self.assertRaises(ValueError):
            evaluate_static_acceptance(samples[:12], evidence, required_samples=13)

    def test_default_denominator_uses_input_and_phase_threshold_is_configurable(self):
        samples = [f"A{i}" for i in range(4)]
        evidence = {sample: {"creator": accepted_record(), "unity": accepted_record()} for sample in samples}
        result = evaluate_static_acceptance(samples, evidence, minimum_dual_target_passes=4)
        self.assertEqual(result["requiredSamples"], None)
        self.assertTrue(result["firstPhaseComplete"])
        result = evaluate_static_acceptance(samples, evidence, minimum_dual_target_passes=5)
        self.assertFalse(result["firstPhaseComplete"])


if __name__ == "__main__":
    unittest.main()
