"""Build development command declarations and orchestration.

Algorithms and transaction guards remain in grea.development.
"""

from grea.development.reporting import _p0_report, publish_inspection

ROUTES = {"payload": "payload", "build-filter": "filter"}


def register(sub, *, include_intake_plan=True):
    payload = sub.add_parser("payload").add_subparsers(dest="action", required=True)
    payload_verify = payload.add_parser("verify")
    payload_verify.add_argument("--root", required=True)
    payload_verify.add_argument("--manifest", required=True)
    payload_verify.add_argument("--scope")
    payload_verify.add_argument("--allow-unlisted", action="store_true")
    payload_verify.add_argument("--unity-artifact", action="store_true")
    payload_plan = payload.add_parser("plan")
    payload_plan.add_argument("--root", required=True)
    payload_plan.add_argument("--manifest", required=True)
    payload_plan.add_argument("--target", required=True)
    payload_plan.add_argument("--out", required=True)
    payload_plan.add_argument("--overrides")
    payload_plan.add_argument("--override-root")
    payload_apply = payload.add_parser("apply")
    payload_apply.add_argument("--plan", required=True)
    payload_apply.add_argument("--expected-plan", required=True)
    payload_apply.add_argument("--out", required=True)
    bf = sub.add_parser("build-filter").add_subparsers(dest="action", required=True)
    bc = bf.add_parser("collect")
    for f in ("project", "spec", "out", "editor-path"):
        bc.add_argument("--" + f, required=True)
    bc.add_argument("--timeout", type=int, default=600)
    bc.add_argument("--summary", action="store_true")
    bp = bf.add_parser("plan")
    for f in ("project", "snapshot", "sources", "target", "out"):
        bp.add_argument("--" + f, required=True)
    bp.add_argument("--summary", action="store_true")


def dispatch(a):
    if a.command == "build-filter":
        from grea.development.io import read, load

        if a.action == "collect":
            from grea.development.build_filter import collect

            return collect(a.project, a.spec, a.out, a.editor_path, a.timeout)
        from grea.development.build_filter import plan

        inputs = [a.project, a.snapshot, a.sources, a.target]
        data = plan(a.project, load(read(a.target)), _p0_report(a.snapshot), load(read(a.sources)))
        name = "build-filter-plan.json"
        return publish_inspection(a, data, inputs, name)

    if a.command == "payload":
        from grea.development.payload import verify_manifest, plan, apply

        if a.action == "verify":
            return verify_manifest(
                a.root, a.manifest, a.scope, allow_unlisted=a.allow_unlisted, artifact=a.unity_artifact
            )
        if a.action == "plan":
            return plan(a.root, a.manifest, a.target, a.out, a.overrides, a.override_root)
        return apply(a.plan, a.out, a.expected_plan)
    raise ValueError(f"Unknown development command: {a.command}")
