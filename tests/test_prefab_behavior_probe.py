import unittest

from monkey.prefab_behavior_probe import SCHEMA, validate_behavior_receipt


def receipt():
    return {
        "schema": SCHEMA,
        "targetEngine": "Example native target",
        "sourceEngine": "Example source engine",
        "timeScale": None,
        "checkpointPlan": [
            {"id": "start", "relativeTo": "probeStart", "seconds": 0,
             "expectedScale": [2, 3, 4], "expectedScaleState": "specified",
             "sourceMeaning": "serialized initial scale"},
            {"id": "mid", "relativeTo": "probeStart", "seconds": 0.5,
             "expectedScale": [1, 1, 1], "expectedScaleState": "specified",
             "sourceMeaning": "source midpoint"},
        ],
        "observations": [
            {"id": "start", "elapsedSeconds": 0, "scale": [2, 3, 4], "scaleState": "measured", "nodeExists": True},
            {"id": "mid", "elapsedSeconds": 0.5, "scale": [1, 1, 1], "scaleState": "measured", "nodeExists": True},
            {"id": "heldBefore", "elapsedSeconds": 1, "scale": [1, 1, 1], "scaleState": "measured", "nodeExists": True},
            {"id": "heldAfter", "elapsedSeconds": 1.1, "scale": [1, 1, 1], "scaleState": "measured", "nodeExists": True},
            {"id": "destroyed", "elapsedSeconds": 1.2, "scale": None, "scaleState": "unavailable", "nodeExists": False},
        ],
        "stabilityChecks": [
            {"name": "disabled_holds", "beforeId": "heldBefore", "afterId": "heldAfter", "tolerance": 0.01}
        ],
        "destructionChecks": ["destroyed"],
        "taskExpectations": ["complete"],
        "taskResults": [{"name": "complete", "completed": True, "faulted": False}],
        "unknownSemantics": ["an unspecified lifecycle detail"],
    }


class PrefabBehaviorProbeTests(unittest.TestCase):
    def test_generic_receipt_validator_checks_plan_observations_and_lifecycle(self):
        result = validate_behavior_receipt(receipt())
        self.assertEqual(result["status"], "passed", result["failures"])
        self.assertEqual(result["observations"], 5)
        self.assertEqual(result["checkpoints"], 2)

    def test_source_checkpoint_mismatch_fails(self):
        sample = receipt()
        next(row for row in sample["observations"] if row["id"] == "mid")["scale"] = [1, 2, 1]
        result = validate_behavior_receipt(sample)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("checkpoint mismatch" in issue for issue in result["failures"]))

    def test_stability_destroy_and_task_failures_are_reported(self):
        sample = receipt()
        next(row for row in sample["observations"] if row["id"] == "heldAfter")["scale"] = [1, 1.5, 1]
        next(row for row in sample["observations"] if row["id"] == "destroyed")["nodeExists"] = True
        sample["taskResults"] = [{"name": "complete", "completed": False, "faulted": True}]
        result = validate_behavior_receipt(sample)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("stable" in issue for issue in result["failures"]))
        self.assertTrue(any("destruction" in issue for issue in result["failures"]))
        self.assertTrue(any("task" in issue for issue in result["failures"]))

    def test_explicit_unspecified_scale_is_distinct_from_invalid_empty_measurement(self):
        sample = receipt()
        sample["checkpointPlan"].append({
            "id": "overlap", "relativeTo": "overlapStart", "seconds": 0,
            "expectedScale": [], "expectedScaleState": "unspecified",
            "sourceMeaning": "overlapping actions have no deterministic midpoint oracle",
        })
        sample["observations"].append({
            "id": "overlap", "elapsedSeconds": 0, "scale": [2, 2, 2],
            "scaleState": "measured", "nodeExists": True,
        })
        self.assertEqual(validate_behavior_receipt(sample)["status"], "passed")

        sample["observations"][-1]["scale"] = []
        result = validate_behavior_receipt(sample)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("measured scale" in issue for issue in result["failures"]))

    def test_specified_expectation_rejects_empty_vector(self):
        sample = receipt()
        sample["checkpointPlan"][1]["expectedScale"] = []
        result = validate_behavior_receipt(sample)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("specified expected scale" in issue for issue in result["failures"]))

    def test_legacy_unity_jsonutility_nulls_are_inferred_only_from_explicit_context(self):
        sample = receipt()
        sample["checkpointPlan"][1].update({
            "expectedScale": [],
            "sourceMeaning": "overlapping sample; no deterministic midpoint oracle",
        })
        sample["checkpointPlan"][1].pop("expectedScaleState")
        sample["observations"][-1].update({"scale": [], "nodeExists": False})
        sample["observations"][-1].pop("scaleState")
        result = validate_behavior_receipt(sample)
        self.assertEqual(result["status"], "passed", result["failures"])

        sample["observations"][-1]["scale"] = [1, 2]
        result = validate_behavior_receipt(sample)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("malformed" in issue or "finite three-axis" in issue for issue in result["failures"]))


if __name__ == "__main__":
    unittest.main()
