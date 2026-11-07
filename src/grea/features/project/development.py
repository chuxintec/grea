"""Project development command declarations and orchestration.

Algorithms and transaction guards remain in grea.development.
"""

from pathlib import Path
from grea.development.reporting import _p0_report, publish_inspection

ROUTES = {
    "project": "",
    "adopt": "adopt",
    "unity": "unity",
    "batch": "batch",
    "workspace": "workspace",
    "production": "production",
    "structure": "structure",
    "native": "native",
}


def register(sub, *, include_intake_plan=True):
    project = sub.add_parser("project").add_subparsers(dest="action", required=True)
    inspect = project.add_parser("inspect")
    inspect.add_argument("--project", required=True)
    inspect.add_argument("--assets", action="store_true")
    adopt = sub.add_parser("adopt").add_subparsers(dest="action", required=True)
    plan = adopt.add_parser("plan")
    plan.add_argument("--candidate", required=True)
    plan.add_argument("--baseline")
    plan.add_argument("--sdk-migration")
    plan.add_argument("--expected-sdk-migration")
    plan.add_argument("--target", required=True)
    plan.add_argument("--lineage")
    plan.add_argument("--out", required=True)
    apply = adopt.add_parser("apply")
    apply.add_argument("--plan", required=True)
    apply.add_argument("--expected-plan", required=True)
    apply.add_argument("--out", required=True)
    apply.add_argument("--editor-path", required=True)
    apply.add_argument("--timeout", type=int, default=600)
    recover = adopt.add_parser("rollback")
    recover.add_argument("--transaction", required=True)
    recover.add_argument("--editor-path", required=True)
    recover.add_argument("--timeout", type=int, default=600)
    finalize = adopt.add_parser("finalize")
    finalize.add_argument("--transaction", required=True)
    finalize.add_argument("--editor-path", required=True)
    finalize.add_argument("--timeout", type=int, default=600)
    finalize.add_argument("--canonicalize-parent-case", action="store_true")
    unity = sub.add_parser("unity").add_subparsers(dest="action", required=True)
    unity_plan = unity.add_parser("plan")
    unity_plan.add_argument("--project", required=True)
    unity_plan.add_argument("--spec", required=True)
    unity_plan.add_argument("--out", required=True)
    unity_apply = unity.add_parser("apply")
    unity_apply.add_argument("--plan", required=True)
    unity_apply.add_argument("--expected-plan", required=True)
    unity_apply.add_argument("--out", required=True)
    unity_apply.add_argument("--editor-path", required=True)
    unity_apply.add_argument("--timeout", type=int, default=600)
    unity_recover = unity.add_parser("recover")
    for flag in ("transaction", "expected-plan", "editor-path"):
        unity_recover.add_argument("--" + flag, required=True)
    unity_recover.add_argument("--timeout", type=int, default=600)
    font_recover = unity.add_parser("recover-font-source")
    for flag in ("transaction", "expected-plan", "review", "out"):
        font_recover.add_argument("--" + flag, required=True)
    for entry in (unity_plan, unity_apply, unity_recover):
        entry.add_argument("--summary", action="store_true")
    batch = sub.add_parser("batch").add_subparsers(dest="action", required=True)
    bp = batch.add_parser("plan")
    bp.add_argument("--project", required=True)
    bp.add_argument("--spec", required=True)
    bp.add_argument("--out", required=True)
    ba = batch.add_parser("apply")
    ba.add_argument("--plan", required=True)
    ba.add_argument("--expected-plan", required=True)
    ba.add_argument("--out", required=True)
    ba.add_argument("--editor-path", required=True)
    ba.add_argument("--timeout", type=int, default=600)
    br = batch.add_parser("recover")
    br.add_argument("--transaction", required=True)
    br.add_argument("--out", required=True)
    br.add_argument("--editor-path", required=True)
    br.add_argument("--timeout", type=int, default=600)
    workspace = sub.add_parser("workspace").add_subparsers(dest="action", required=True)
    wp = workspace.add_parser("plan")
    wp.add_argument("--project", required=True)
    wp.add_argument("--spec", required=True)
    wp.add_argument("--out", required=True)
    wa = workspace.add_parser("apply")
    wa.add_argument("--plan", required=True)
    wa.add_argument("--expected-plan", required=True)
    wa.add_argument("--out", required=True)
    wi = workspace.add_parser("inspect")
    wi.add_argument("--project", required=True)
    wi.add_argument("--profile")
    wr = workspace.add_parser("rebind")
    wr.add_argument("--project", required=True)
    wr.add_argument("--profile", required=True)
    wr.add_argument("--expected-profile", required=True)
    wr.add_argument("--out", required=True)
    wr.add_argument("--accept-authority-change", action="store_true")
    wr.add_argument("--spec")
    production = sub.add_parser("production").add_subparsers(dest="action", required=True)
    pp = production.add_parser("plan")
    pp.add_argument("--project", required=True)
    pp.add_argument("--spec", required=True)
    pp.add_argument("--out", required=True)
    pa = production.add_parser("apply")
    pa.add_argument("--plan", required=True)
    pa.add_argument("--expected-plan", required=True)
    pa.add_argument("--out", required=True)
    pa.add_argument("--editor-path", required=True)
    pa.add_argument("--timeout", type=int, default=600)
    pr = production.add_parser("recover")
    pr.add_argument("--transaction", required=True)
    pr.add_argument("--out", required=True)
    pr.add_argument("--editor-path", required=True)
    pr.add_argument("--timeout", type=int, default=600)
    structure = sub.add_parser("structure").add_subparsers(dest="action", required=True)
    si = structure.add_parser("inspect")
    si.add_argument("--project", required=True)
    si.add_argument("--snapshot")
    si.add_argument("--exceptions")
    si.add_argument("--out", required=True)
    si.add_argument("--product-root")
    si.add_argument("--profile")
    si.add_argument("--summary", action="store_true")
    sp = structure.add_parser("plan")
    for f in ("audit", "mappings", "out"):
        sp.add_argument("--" + f, required=True)
    sp.add_argument("--snapshot")
    sp.add_argument("--consumer-resolutions")
    sp.add_argument("--summary", action="store_true")
    native = sub.add_parser("native").add_subparsers(dest="action", required=True).add_parser("readback")
    for f in ("project", "spec", "out", "editor-path"):
        native.add_argument("--" + f, required=True)
    native.add_argument("--timeout", type=int, default=600)
    native.add_argument("--summary", action="store_true")


def dispatch(a):
    if a.command == "structure":
        from grea.development.io import read, load
        from grea.development.structure_audit import inspect, build_plan

        if a.action == "inspect":
            inputs = [a.project] + [x for x in (a.snapshot, a.exceptions) if x]
            data = inspect(
                a.project,
                _p0_report(a.snapshot) if a.snapshot else None,
                load(read(a.exceptions)) if a.exceptions else None,
                a.product_root,
                a.profile,
            )
            if data.get("productRoot") and data.get("profileIdentity"):
                inputs.append(str(Path(data["productRoot"]) / data["profileIdentity"]["path"]))
        else:
            inputs = (
                [a.audit, a.mappings]
                + ([a.snapshot] if a.snapshot else [])
                + ([a.consumer_resolutions] if a.consumer_resolutions else [])
            )
            data = build_plan(
                _p0_report(a.audit),
                load(read(a.mappings)),
                _p0_report(a.snapshot) if a.snapshot else None,
                load(read(a.consumer_resolutions)) if a.consumer_resolutions else None,
            )
        name = "structure-" + a.action + ".json"
        return publish_inspection(a, data, inputs, name)

    if a.command == "native":
        from grea.development.native_readback import inspect

        return inspect(a.project, a.spec, a.out, a.editor_path, a.timeout)
    if a.command == "project":
        from grea.development.context import inspect

        return inspect(a.project, a.assets)
    if a.command == "adopt":
        if a.action == "plan":
            from grea.development.adoption import preview

            return preview(
                a.candidate, a.target, a.out, a.baseline, a.lineage, a.sdk_migration, a.expected_sdk_migration
            )
        if a.action == "apply":
            from grea.development.adoption_native import execute

            return execute(a.plan, a.out, a.editor_path, a.timeout, a.expected_plan)
        if a.action == "finalize":
            from grea.development.adoption_native import finalize

            return finalize(a.transaction, a.editor_path, a.timeout, a.canonicalize_parent_case)
        from grea.development.adoption_native import recover

        return recover(a.transaction, a.editor_path, a.timeout)
    if a.command == "unity":
        if a.action == "recover-font-source":
            from grea.development.build_font_recovery import recover_reviewed

            return recover_reviewed(a.transaction, a.expected_plan, a.review, a.out)
        from grea.development.unity import plan, apply, recover

        if a.action == "recover":
            return recover(a.transaction, a.editor_path, a.expected_plan, a.timeout)
        return (
            plan(a.project, a.spec, a.out)
            if a.action == "plan"
            else apply(a.plan, a.out, a.editor_path, a.expected_plan, a.timeout)
        )
    if a.command == "batch":
        from grea.development.batch import plan, apply, recover

        if a.action == "plan":
            return plan(a.project, a.spec, a.out)
        if a.action == "apply":
            return apply(a.plan, a.out, a.editor_path, a.expected_plan, a.timeout)
        return recover(a.transaction, a.out, a.editor_path, a.timeout)
    if a.command == "workspace":
        from grea.development.project_profile import setup_plan, setup_apply, rebind_plan, inspect

        if a.action == "plan":
            return setup_plan(a.project, a.spec, a.out)
        if a.action == "apply":
            return setup_apply(a.plan, a.expected_plan, a.out)
        if a.action == "inspect":
            return inspect(a.project, a.profile)
        return rebind_plan(a.project, a.profile, a.expected_profile, a.out, a.accept_authority_change, a.spec)
    if a.command == "production":
        from grea.development.production import plan, apply, recover

        if a.action == "plan":
            return plan(a.project, a.spec, a.out)
        if a.action == "apply":
            return apply(a.plan, a.out, a.editor_path, a.expected_plan, a.timeout)
        return recover(a.transaction, a.out, a.editor_path, a.timeout)
    raise ValueError(f"Unknown development command: {a.command}")
