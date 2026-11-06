"""Conservative, evidence-gated static Prefab acceptance accounting.

Evidence input is intentionally declarative. This module does not infer a pass
from artifact existence, node/component counts, or dynamic-phase status.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


TARGETS = ("creator", "unity")
STATIC_CRITERIA = (
    "source_identity",
    "hierarchy",
    "components_fields",
    "asset_references",
    "static_render",
    "save_reopen",
    "regenerate",
)
DYNAMIC_CRITERIA = ("dynamic_behavior", "physical_input")
ALLOWED_STATES = {"pass", "fail", "partial", "not_run"}


def evaluate_static_acceptance(
    samples: Sequence[str | Mapping[str, Any]],
    target_evidence: Mapping[str, Mapping[str, Mapping[str, Any]]],
    *,
    required_samples: int | None = None,
    minimum_dual_target_passes: int = 10,
) -> dict[str, Any]:
    """Evaluate static evidence for the provided fixed sample denominator.

    ``samples`` is an ordered sequence of sample IDs or mappings containing an
    ``id``. ``target_evidence`` is keyed by sample ID, then ``creator``/``unity``
    and criterion. A criterion value is a mapping with explicit ``status`` and
    non-empty ``evidenceId``. For static_render, cross-version comparisons also
    require non-empty ``comparisonScope`` and an explicitly present
    ``versionDifferences`` value (an empty list means reviewed with none found).

    Missing, unknown, malformed, or subset evidence is reported as
    ``not_run``; only a literal ``pass`` with evidenceId can pass a criterion.
    Dynamic criteria are reported independently and do not affect static status.
    """
    sample_ids = [_sample_id(sample) for sample in samples]
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError("sample IDs must be unique; the supplied denominator is fixed")
    if required_samples is not None:
        if isinstance(required_samples, bool) or not isinstance(required_samples, int) or required_samples < 0:
            raise ValueError("required_samples must be a non-negative integer or None")
        if len(sample_ids) != required_samples:
            raise ValueError(
                f"sample denominator mismatch: expected {required_samples}, received {len(sample_ids)}"
            )
    if (
        isinstance(minimum_dual_target_passes, bool)
        or not isinstance(minimum_dual_target_passes, int)
        or minimum_dual_target_passes < 0
    ):
        raise ValueError("minimum_dual_target_passes must be a non-negative integer")
    expected_samples = len(sample_ids) if required_samples is None else required_samples

    matrix: list[dict[str, Any]] = []
    dual_target_passes = 0
    for sample_id in sample_ids:
        targets: dict[str, Any] = {}
        sample_evidence = _mapping(target_evidence.get(sample_id, {}))
        for target in TARGETS:
            raw = _mapping(sample_evidence.get(target, {}))
            criteria: dict[str, Any] = {}
            for criterion in STATIC_CRITERIA:
                criteria[criterion] = _criterion_result(
                    criterion, raw.get(criterion), raw.get("sourceVersion"),
                    raw.get("referenceVersion"),
                )
            static_pass = all(item["status"] == "pass" for item in criteria.values())
            dynamic = {
                name: _criterion_result(name, raw.get(name), None, None)
                for name in DYNAMIC_CRITERIA
            }
            targets[target] = {
                "criteria": criteria,
                "staticAcceptance": "pass" if static_pass else "partial",
                "dynamic": dynamic,
            }
        if all(targets[target]["staticAcceptance"] == "pass" for target in TARGETS):
            dual_target_passes += 1
        matrix.append({"id": sample_id, "targets": targets})

    return {
        "schemaVersion": 1,
        "denominator": len(sample_ids),
        "sampleIds": sample_ids,
        "staticCriteria": list(STATIC_CRITERIA),
        "dynamicCriteria": list(DYNAMIC_CRITERIA),
        "matrix": matrix,
        "dualTargetStaticPassCount": dual_target_passes,
        "firstPhaseThreshold": minimum_dual_target_passes,
        "requiredSamples": required_samples,
        "firstPhaseComplete": len(sample_ids) == expected_samples and dual_target_passes >= minimum_dual_target_passes,
    }


def _sample_id(sample: str | Mapping[str, Any]) -> str:
    value = sample if isinstance(sample, str) else _mapping(sample).get("id")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("each sample must be a non-empty ID or mapping with non-empty id")
    return value.strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _criterion_result(
    criterion: str,
    evidence: Any,
    source_version: Any,
    reference_version: Any,
) -> dict[str, Any]:
    record = _mapping(evidence)
    status = record.get("status")
    evidence_id = record.get("evidenceId")
    valid_id = isinstance(evidence_id, str) and bool(evidence_id.strip())
    result_status = status if isinstance(status, str) and status in ALLOWED_STATES else "not_run"
    if result_status == "pass" and not valid_id:
        result_status = "not_run"
    if criterion == "static_render" and result_status == "pass":
        source_ok = isinstance(source_version, str) and bool(source_version.strip())
        reference_ok = isinstance(reference_version, str) and bool(reference_version.strip())
        if not (source_ok and reference_ok):
            result_status = "not_run"
        cross_version = (
            source_ok
            and reference_ok
            and source_version.strip() != reference_version.strip()
        )
        if cross_version:
            scope = record.get("comparisonScope")
            differences = record.get("versionDifferences")
            # Presence is meaningful: [] records an explicit review finding no
            # differences; omission is not an implicit assertion of parity.
            if not (
                isinstance(scope, str)
                and scope.strip()
                and isinstance(differences, list)
                and all(isinstance(item, str) for item in differences)
            ):
                result_status = "not_run"
    result = {"status": result_status}
    if valid_id:
        result["evidenceId"] = evidence_id.strip()
    if criterion == "static_render":
        for key in ("comparisonScope", "versionDifferences"):
            if key in record:
                result[key] = record[key]
        if source_version is not None:
            result["sourceVersion"] = source_version
        if reference_version is not None:
            result["referenceVersion"] = reference_version
    return result
