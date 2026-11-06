"""Generic validator for native behavior probe JSON receipts.

Probe runners supply source-derived checkpoint plans and lifecycle assertions;
this module validates the observed values without executing or reimplementing
any engine behavior.
"""
from __future__ import annotations

import math
from typing import Any


SCHEMA = "monkey-prefab-behavior-runtime-probe/1"


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _vector(value: Any) -> tuple[float, float, float] | None:
    if not isinstance(value, list) or len(value) != 3 or not all(_finite_number(v) for v in value):
        return None
    return (float(value[0]), float(value[1]), float(value[2]))


def _is_empty_serialized_array(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 0


def _scale_availability(row: dict[str, Any], label: str, failures: list[str]) -> str | None:
    """Read measured/unavailable scale state without accepting malformed vectors."""
    value = row.get("scale")
    state = row.get("scaleState")
    node_exists = row.get("nodeExists")
    if state == "measured":
        if _vector(value) is None:
            failures.append("measured scale must be a finite three-axis vector: " + label)
            return None
        return "measured"
    if state == "unavailable":
        if node_exists is not False:
            failures.append("unavailable scale requires a destroyed or missing node: " + label)
        if value is not None and not _is_empty_serialized_array(value):
            failures.append("unavailable scale cannot contain a malformed value: " + label)
        return "unavailable"
    if state is not None:
        failures.append("scaleState must be measured or unavailable: " + label)
        return None

    # Legacy Unity JsonUtility receipts serialize a null float[] as [].
    # A missing node makes that empty array an unambiguous unavailable sample.
    if value is None or (_is_empty_serialized_array(value) and node_exists is False):
        if node_exists is False:
            return "unavailable"
        failures.append("unavailable scale requires an explicit unavailable state and missing node: " + label)
        return None
    if _vector(value) is not None:
        return "measured"
    failures.append("scale must be a finite three-axis vector: " + label)
    return None


def _expected_scale(row: dict[str, Any], label: str, failures: list[str]) -> tuple[float, float, float] | None:
    """Resolve typed expected-scale presence, including explicit legacy no-oracle notes."""
    value = row.get("expectedScale")
    state = row.get("expectedScaleState")
    if state == "unspecified":
        if value is not None and not _is_empty_serialized_array(value):
            failures.append("unspecified expected scale cannot contain a value: " + label)
        return None
    if state == "specified":
        vector = _vector(value)
        if vector is None:
            failures.append("specified expected scale must be a finite three-axis vector: " + label)
        return vector
    if state is not None:
        failures.append("expectedScaleState must be specified or unspecified: " + label)
        return None

    # Backward compatibility for old Creator JSON (null) and Unity JsonUtility
    # (empty array). With no state field, an empty expectedScale is the legacy
    # encoding of an absent optional expectation; an explicit "specified" state
    # still rejects it. Actual measured scales are validated independently and
    # never treat an empty array as a vector.
    if value is None:
        return None
    if _is_empty_serialized_array(value):
        return None
    vector = _vector(value)
    if vector is None:
        failures.append("expected scale must be a finite three-axis vector or explicitly unspecified: " + label)
    return vector


def validate_behavior_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Validate actual measurements against the source expectations in a receipt."""
    failures: list[str] = []
    if receipt.get("schema") != SCHEMA:
        failures.append("receipt schema mismatch")
    for field in ("targetEngine", "sourceEngine"):
        if not isinstance(receipt.get(field), str) or not receipt[field].strip():
            failures.append("missing engine identity: " + field)

    observations_raw = receipt.get("observations")
    if not isinstance(observations_raw, list):
        failures.append("observations must be a list")
        observations_raw = []
    observations: dict[str, dict[str, Any]] = {}
    for row in observations_raw:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
            failures.append("each observation needs a nonempty id")
            continue
        if row["id"] in observations:
            failures.append("duplicate observation id: " + row["id"])
            continue
        observations[row["id"]] = row
        if not _finite_number(row.get("elapsedSeconds")) or float(row["elapsedSeconds"]) < 0:
            failures.append("invalid elapsed time: " + row["id"])
        _scale_availability(row, row["id"], failures)

    plan_raw = receipt.get("checkpointPlan")
    if not isinstance(plan_raw, list) or not plan_raw:
        failures.append("checkpointPlan must describe source-derived expected observations")
        plan_raw = []
    plans: dict[str, dict[str, Any]] = {}
    for row in plan_raw:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
            failures.append("each checkpoint needs a nonempty id")
            continue
        key = row["id"]
        if key in plans:
            failures.append("duplicate checkpoint id: " + key)
            continue
        plans[key] = row
        if not isinstance(row.get("relativeTo"), str) or not row["relativeTo"]:
            failures.append("checkpoint needs a relativeTo clock: " + key)
        if not _finite_number(row.get("seconds")) or float(row["seconds"]) < 0:
            failures.append("checkpoint needs a nonnegative scheduled time: " + key)
        if not isinstance(row.get("sourceMeaning"), str) or not row["sourceMeaning"]:
            failures.append("checkpoint needs sourceMeaning: " + key)
        observation = observations.get(key)
        if observation is None:
            failures.append("missing checkpoint observation: " + key)
            continue
        expected_vector = _expected_scale(row, key, failures)
        if expected_vector is not None:
            actual_vector = _vector(observation.get("scale"))
            if actual_vector is None or _scale_availability(observation, key, failures) != "measured":
                failures.append("specified scale checkpoint requires a measured vector: " + key)
            else:
                tolerance = float(row.get("scaleTolerance", 0.04))
                if not _finite_number(tolerance) or tolerance < 0:
                    failures.append("invalid scale tolerance: " + key)
                elif any(abs(a - e) > tolerance for a, e in zip(actual_vector, expected_vector)):
                    failures.append("scale checkpoint mismatch: " + key)
        if _finite_number(row.get("seconds")):
            scheduled = float(row["seconds"])
            observed_at = observation.get("elapsedSeconds")
            time_tolerance = row.get("timeToleranceSeconds", 0.16)
            if _finite_number(observed_at) and _finite_number(time_tolerance) and abs(float(observed_at) - scheduled) > float(time_tolerance):
                failures.append("observation outside checkpoint time window: " + key)

    stability_raw = receipt.get("stabilityChecks", [])
    if not isinstance(stability_raw, list):
        failures.append("stabilityChecks must be a list")
        stability_raw = []
    for check in stability_raw:
        if not isinstance(check, dict):
            failures.append("malformed stability check")
            continue
        before = observations.get(check.get("beforeId"), {})
        after = observations.get(check.get("afterId"), {})
        a = _vector(before.get("scale")) if _scale_availability(before, str(check.get("beforeId")), failures) == "measured" else None
        b = _vector(after.get("scale")) if _scale_availability(after, str(check.get("afterId")), failures) == "measured" else None
        tolerance = check.get("tolerance", 0.015)
        label = str(check.get("name", "stability"))
        if a is None or b is None or not _finite_number(tolerance) or tolerance < 0:
            failures.append("invalid or missing stability samples: " + label)
        elif any(abs(x - y) > float(tolerance) for x, y in zip(a, b)):
            failures.append("scale did not remain stable: " + label)

    destroyed_raw = receipt.get("destructionChecks", [])
    if not isinstance(destroyed_raw, list):
        failures.append("destructionChecks must be a list")
        destroyed_raw = []
    for key in destroyed_raw:
        row = observations.get(key, {})
        if row.get("nodeExists") is not False:
            failures.append("destruction was not observed: " + str(key))

    expected_tasks = receipt.get("taskExpectations", [])
    tasks_raw = receipt.get("taskResults", [])
    if not isinstance(expected_tasks, list) or not isinstance(tasks_raw, list):
        failures.append("taskExpectations and taskResults must be lists")
        expected_tasks, tasks_raw = [], []
    task_results = {
        row.get("name"): row for row in tasks_raw
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    }
    for name in expected_tasks:
        task = task_results.get(name)
        if task is None or task.get("completed") is not True or task.get("faulted") is not False:
            failures.append("task did not complete cleanly: " + str(name))

    unknown = receipt.get("unknownSemantics", [])
    if not isinstance(unknown, list) or any(not isinstance(item, str) for item in unknown):
        failures.append("unknownSemantics must preserve unresolved behavior as strings")
        unknown = []
    time_scale = receipt.get("timeScale")
    if time_scale is not None and not _finite_number(time_scale):
        failures.append("timeScale must be a finite number or null")

    return {
        "schema": "monkey-prefab-behavior-runtime-validation/1",
        "targetEngine": receipt.get("targetEngine"),
        "status": "passed" if not failures else "failed",
        "observations": len(observations),
        "checkpoints": len(plans),
        "failures": failures,
        "unknownSemantics": list(unknown),
    }
