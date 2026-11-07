"""Bounded report reading and transport summaries, independent of CLI parsing."""


def publish_inspection(arguments, data, inputs, name):
    """Retain the inspection provenance and hash policy shared by project/build."""
    import json
    from .io import new_output, sha, write_json

    stage = new_output(arguments.out, inputs)
    data["provenance"] = (
        "caller-supplied snapshot; native collection origin not independently authenticated"
        if getattr(arguments, "snapshot", None)
        else "filesystem inspection; no native snapshot"
    )
    if "planSha256" in data:
        data["planSha256"] = sha(
            json.dumps(
                {k: v for k, v in data.items() if k != "planSha256"},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
    write_json(stage / name, data)
    return dict(data, report=str(stage / name))


def _p0_report(path):
    """Read our bounded large reports without changing ordinary spec limits."""
    from grea.development.io import read, load
    from grea.development.output_limits import MANIFEST_BYTES, MANIFEST_NODES

    return load(read(path, max_bytes=MANIFEST_BYTES), max_nodes=MANIFEST_NODES)


def _p0_summary(data):
    """Project transport metadata only; the complete report remains hashed on disk."""
    result = {
        k: data[k]
        for k in (
            "status",
            "report",
            "mode",
            "projectRoot",
            "productRoot",
            "profileIdentity",
            "structureDocumentationIdentity",
            "sourceUnchanged",
            "helperCleaned",
            "editorExitCode",
            "projectConformance",
            "batchReadiness",
            "planSha256",
            "counts",
            "transaction",
            "sourceSha256",
            "restoredFiles",
            "objectIdentityCount",
        )
        if k in data
    }
    if isinstance(data.get("nativeReadback"), str):
        result["nativeReadback"] = data["nativeReadback"]
    for field in (
        "inventory",
        "assets",
        "fields",
        "issues",
        "blockers",
        "remainingStructureIssues",
        "deletedPaths",
        "deletedFolders",
        "changes",
        "unresolvedDependencies",
    ):
        if isinstance(data.get(field), list):
            result[field + "Count"] = len(data[field])
    if isinstance(data.get("coverage"), dict):
        coverage = data["coverage"]
        result["coverage"] = {k: coverage[k] for k in ("complete",) if k in coverage}
        if isinstance(coverage.get("blockers"), list):
            result["coverage"]["blockerCount"] = len(coverage["blockers"])
    if isinstance(data.get("execution"), dict):
        e = data["execution"]
        result["execution"] = {k: e[k] for k in ("status", "code", "reason") if k in e}
        if isinstance(e.get("blockers"), list):
            result["execution"]["blockerCount"] = len(e["blockers"])
    result["detailStorage"] = "complete-report-file; summary is not a replacement for inspection"
    return result
