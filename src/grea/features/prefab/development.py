"""Prefab development command declarations and orchestration.

Algorithms and transaction guards remain in grea.development.
"""

from grea.development.errors import fail

ROUTES = {"intake": "intake"}


def register(sub, *, include_intake_plan=True):
    intake = sub.add_parser("intake").add_subparsers(dest="action", required=True)
    requirements = intake.add_parser("package-requirements")
    for option in ("candidate", "target", "source-project", "editor-path", "evidence", "expected-evidence", "out"):
        requirements.add_argument("--" + option, required=True)
    binding_plan = intake.add_parser("bindings-plan")
    for option in ("source", "target", "out"):
        binding_plan.add_argument("--" + option, required=True)
    binding_mode = binding_plan.add_mutually_exclusive_group(required=True)
    binding_mode.add_argument("--spec")
    binding_mode.add_argument("--complete-from")
    binding_plan.add_argument("--expected-candidate")
    binding_plan.add_argument("--dependency-report")
    binding_prepare = intake.add_parser("prepare-bindings")
    for option in ("plan", "expected-plan", "out", "editor-path"):
        binding_prepare.add_argument("--" + option, required=True)
    binding_prepare.add_argument("--timeout", type=int, default=600)
    binding_export = intake.add_parser("export-bindings")
    for option in ("preparation", "expected-plan", "native-runtime", "expected-native-producer", "out"):
        binding_export.add_argument("--" + option, required=True)
    binding_spec = intake.add_parser("spec-bindings")
    for option in ("candidate", "target", "expected-manifest", "mapping", "out"):
        binding_spec.add_argument("--" + option, required=True)
    binding_spec.add_argument("--policy")
    binding_spec.add_argument("--preparation-receipt")
    binding_spec.add_argument("--reuse-exact-assets", action="store_true")
    binding_spec.add_argument("--asset-evidence", action="append", default=[])
    binding_spec.add_argument("--expected-asset-evidence", action="append", default=[])
    binding_spec.add_argument("--binding-source")
    binding_spec.add_argument("--dependency-report")
    binding_spec.add_argument("--classify", action="store_true")
    binding_spec.add_argument("--script-target-root")
    binding_spec.add_argument("--runtime-readback")
    for option in ("source-project", "dotnet", "sdk-root"):
        binding_spec.add_argument("--" + option)
    if include_intake_plan:
        from grea.features.prefab.commands import intake_plan_parameters

        intake_plan_parameters(intake.add_parser("plan"))
    binding_spec.add_argument("--package-evidence")
    binding_spec.add_argument("--expected-package-evidence")
    intake_apply = intake.add_parser("apply")
    for option in ("plan", "expected-plan", "out", "editor-path"):
        intake_apply.add_argument("--" + option, required=True)
    intake_apply.add_argument("--timeout", type=int, default=600)
    intake_rollback = intake.add_parser("rollback")
    for option in ("transaction", "expected-plan", "editor-path"):
        intake_rollback.add_argument("--" + option, required=True)
    intake_rollback.add_argument("--timeout", type=int, default=600)


def dispatch(a):
    if a.command == "intake":
        if a.action == "package-requirements":
            from grea.development.intake_package_requirements import preview

            return preview(
                a.candidate, a.target, a.source_project, a.editor_path, a.evidence, a.expected_evidence, a.out
            )
        if a.action == "spec-bindings":
            from grea.development.intake_binding_spec import generate

            classification = None
            if a.classify:
                if not all((a.source_project, a.dotnet, a.sdk_root)):
                    fail(
                        "INTAKE_DEPENDENCY_CONTEXT",
                        "--classify",
                        "Explicit source project, dotnet and SDK root required",
                    )
                classification = dict(
                    sourceProject=a.source_project,
                    dotnet=a.dotnet,
                    sdkRoot=a.sdk_root,
                    scriptTargetRoot=a.script_target_root,
                    runtimeReadback=a.runtime_readback,
                )
            if len(a.asset_evidence) != len(a.expected_asset_evidence):
                fail(
                    "INTAKE_ASSET_EVIDENCE",
                    "--asset-evidence",
                    "Every explicit asset evidence file requires its exact SHA-256",
                )
            asset_evidence = [dict(path=p, sha256=h) for p, h in zip(a.asset_evidence, a.expected_asset_evidence)]
            return generate(
                a.candidate,
                a.target,
                a.expected_manifest,
                a.mapping,
                a.out,
                a.policy,
                a.preparation_receipt,
                a.package_evidence,
                a.expected_package_evidence,
                classification,
                reuse_exact_assets=a.reuse_exact_assets,
                asset_evidence=asset_evidence,
                binding_source=a.binding_source,
                dependency_report=a.dependency_report,
            )
        if a.action == "export-bindings":
            from grea.development.intake_bindings import export_existing

            return export_existing(a.preparation, a.expected_plan, a.native_runtime, a.expected_native_producer, a.out)
        if a.action == "bindings-plan":
            if a.complete_from:
                from grea.development.candidate_snapshot import snapshot, verify

                incoming, _, files, manifest_sha = snapshot(a.complete_from)
                verify(incoming, files)
                if manifest_sha != a.expected_candidate:
                    fail(
                        "INTAKE_CANDIDATE_DRIFT",
                        a.complete_from,
                        "Exact reviewed candidate manifest required for completion",
                    )
                from grea.development.intake_binding_completion import propose

                return propose(incoming, a.target, a.source, a.out, dependency_report=a.dependency_report)
            from grea.development.intake_bindings import preview

            return preview(a.source, a.target, a.spec, a.out)
        if a.action == "prepare-bindings":
            from grea.development.intake_bindings import execute

            return execute(a.plan, a.expected_plan, a.out, a.editor_path, a.timeout)
        if a.action == "plan":
            from grea.development.intake import plan_from_args

            return plan_from_args(a)
        from grea.development.intake_native import execute, recover

        if a.action == "apply":
            return execute(a.plan, a.out, a.editor_path, a.expected_plan, a.timeout)
        return recover(a.transaction, a.editor_path, a.expected_plan, a.timeout)
    raise ValueError(f"Unknown development command: {a.command}")
