"""Ui recovery command declarations and orchestration.

Algorithms and transaction guards remain in grea.recovery.
"""

ROUTES = {
    "layout-preview": "layout-preview",
    "native-layout-audit": "native-layout-audit",
    "native-layout-prepare": "native-layout-prepare",
    "native-layout-patch": "native-layout-patch",
    "native-layout-finish": "native-layout-finish",
    "native-layout-bundle": "native-layout-bundle",
    "prepare-source-text-reference": "prepare-source-text-reference",
    "capture-source-text-reference": "capture-source-text-reference",
    "prepare-context-preview": "prepare-context-preview",
}


def register(sub, *, include_intake_plan=True):
    p = sub.add_parser(
        "layout-preview",
        help="Replay a finished conversion under a layout.json and list current -> previewed paths; writes no project",
    )
    p.add_argument("--conversion", required=True)
    p.add_argument("--layout", help="Game layout.json to preview (docs/history/recovery/PROJECT-SPEC.md section 7)")
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "native-layout-audit", help="Audit a frozen native flow-layout subset for standard Unity replacements"
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--expected-manifest", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "native-layout-prepare", help="Create an independent warm candidate for an audited native layout patch"
    )
    p.add_argument("--audit", required=True)
    p.add_argument("--out", required=True)
    p.add_argument(
        "--previous-execution", help="Resume an exact exited partial layer, reusing its saved native asset evidence"
    )
    p = sub.add_parser("native-layout-patch", help="Plan or execute one bounded prepared native layout replacement")
    p.add_argument("--preparation", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--editor", required=True)
    p.add_argument("--budget-seconds", type=int, default=900)
    p.add_argument("--deadline-utc", required=True)
    p.add_argument("--window-end-utc", required=True)
    p.add_argument("--execute", action="store_true")
    p = sub.add_parser(
        "native-layout-finish", help="Freeze an exited successful native layout subset and consumer-guarded delta"
    )
    p.add_argument("--execution", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "native-layout-bundle", help="Package a frozen verified Prefab/runtime delta with old-hash and identity guards"
    )
    p.add_argument("--delta", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "prepare-source-text-reference",
        help="Prepare an offline source-version Cocos Label reference with pinned runtime and inputs",
    )
    p.add_argument("--request", required=True)
    p.add_argument("--expected-request", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "capture-source-text-reference",
        help="Capture an actual controlled source-version Label reference in an existing headless browser",
    )
    p.add_argument("--preparation", required=True)
    p.add_argument("--expected-preparation", required=True)
    p.add_argument("--browser-executable", required=True)
    p.add_argument("--timeout-seconds", type=int, default=90)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "prepare-context-preview", help="Prepare a source-proven parent capture for an isolated Unity copy"
    )
    for flag in ("project", "source-manifest", "parent-id", "target-id", "out"):
        p.add_argument("--" + flag, required=True)


def dispatch(args, *, usage_parser):
    if args.command == "layout-preview":
        from grea.recovery.layout import load_overrides
        from grea.recovery.layout.records import preview

        return (preview(args.conversion, args.out, load_overrides(args.layout)[0] if args.layout else None), 0)
    if args.command == "native-layout-audit":
        from grea.recovery.native_layout_patch import audit

        return (audit(args.candidate, args.out, args.expected_manifest), 0)
    if args.command == "native-layout-prepare":
        from grea.recovery.native_layout_patch import prepare

        return (prepare(args.audit, args.out, args.previous_execution), 0)
    if args.command == "native-layout-patch":
        from grea.recovery.native_layout_patch import execute

        result = execute(
            args.preparation,
            args.out,
            args.editor,
            args.budget_seconds,
            args.deadline_utc,
            args.window_end_utc,
            args.execute,
        )
        return (result, 0 if result.get("status") in ("planned", "completed") else 2)
    if args.command == "native-layout-finish":
        from grea.recovery.native_layout_patch import finish

        return (finish(args.execution, args.out), 0)
    if args.command == "native-layout-bundle":
        from grea.recovery.native_layout_patch import bundle

        return (bundle(args.delta, args.out), 0)
    if args.command == "prepare-source-text-reference":
        from grea.recovery.prefab_source_text_reference import prepare

        result = prepare(args.request, args.expected_request, args.out)
        return (result, 0 if result["status"] == "prepared" else 1)
    if args.command == "capture-source-text-reference":
        from grea.recovery.prefab_source_text_reference import capture

        result = capture(
            args.preparation,
            args.expected_preparation,
            args.browser_executable,
            args.out,
            timeout_seconds=args.timeout_seconds,
        )
        return (result, 0 if result["status"] == "captured" else 1)
    if args.command == "prepare-context-preview":
        from grea.recovery.prefab_context_preview import prepare_request

        return (prepare_request(args.project, args.source_manifest, args.parent_id, args.target_id, args.out), 0)
    raise ValueError(f"Unknown recovery command: {args.command}")
