"""Code development command declarations and orchestration.

Algorithms and transaction guards remain in grea.development.
"""

ROUTES = {"code": "", "csharp": "csharp"}


def register(sub, *, include_intake_plan=True):
    code = sub.add_parser("code").add_subparsers(dest="action", required=True)
    code_inspect = code.add_parser("inspect")
    code_inspect.add_argument("--project", required=True)
    csharp = sub.add_parser("csharp").add_subparsers(dest="action", required=True)
    ci = csharp.add_parser("inspect")
    ci.add_argument("--project", required=True)
    ci.add_argument("--out", required=True)
    ci.add_argument("--toolchain")
    cr = csharp.add_parser("rename")
    cr.add_argument("--project", required=True)
    cr.add_argument("--spec", required=True)
    cr.add_argument("--out", required=True)
    cr.add_argument("--toolchain")
    cs = csharp.add_parser("rename-sequence")
    cs.add_argument("--project", required=True)
    cs.add_argument("--spec", required=True)
    cs.add_argument("--out", required=True)
    cs.add_argument("--toolchain")
    cm = csharp.add_parser("module")
    cm.add_argument("--spec", required=True)
    cm.add_argument("--out", required=True)
    rw = csharp.add_parser("rewrite-prepare")
    for option in ("project", "spec", "out"):
        rw.add_argument("--" + option, required=True)
    rw.add_argument("--toolchain")
    rw = csharp.add_parser("rewrite-plan")
    for option in ("workspace", "expected-workspace", "out"):
        rw.add_argument("--" + option, required=True)
    revent = csharp.add_parser("rewrite-event-plan")
    for option in ("plan", "expected-plan", "events", "expected-events", "out", "editor-path"):
        revent.add_argument("--" + option, required=True)
    revent.add_argument("--apply-out")
    revent_verify = csharp.add_parser("rewrite-event-verify")
    for option in ("plan", "expected-plan", "transaction", "phase", "out", "editor-path"):
        revent_verify.add_argument("--" + option, required=True)
    rw = csharp.add_parser("rewrite-apply")
    for option in ("plan", "expected-plan", "out", "editor-path"):
        rw.add_argument("--" + option, required=True)
    rw.add_argument("--timeout", type=int, default=600)
    rw = csharp.add_parser("rewrite-recover")
    for option in ("transaction", "out", "editor-path"):
        rw.add_argument("--" + option, required=True)
    rw.add_argument("--timeout", type=int, default=600)


def dispatch(a):
    if a.command == "csharp":
        if a.action.startswith("rewrite-"):
            from grea.development import csharp_rewrite as rewrite
            from grea.development.io import load, read

            if a.action == "rewrite-prepare":
                return rewrite.prepare(a.project, a.spec, a.out, load(read(a.toolchain)) if a.toolchain else None)
            if a.action == "rewrite-plan":
                return rewrite.plan(a.workspace, a.expected_workspace, a.out)
            if a.action == "rewrite-event-plan":
                from grea.development import csharp_rewrite_events

                return csharp_rewrite_events.plan(
                    a.plan, a.expected_plan, a.events, a.expected_events, a.out, a.editor_path, a.apply_out
                )
            if a.action == "rewrite-event-verify":
                from grea.development import csharp_rewrite_events

                return csharp_rewrite_events.verify(
                    a.plan, a.expected_plan, a.transaction, a.phase, a.out, a.editor_path
                )
            if a.action == "rewrite-apply":
                return rewrite.apply(a.plan, a.expected_plan, a.out, a.editor_path, a.timeout)
            return rewrite.recover(a.transaction, a.out, a.editor_path, a.timeout)
        from grea.development.csharp import inspect, rename_plan, rename_sequence_plan, module_generate
        from grea.development.io import load, read

        if a.action == "module":
            return module_generate(a.spec, a.out)
        toolchain = load(read(a.toolchain)) if a.toolchain else None
        if a.action == "rename-sequence":
            return rename_sequence_plan(a.project, load(read(a.spec)), a.out, toolchain)
        return (
            inspect(a.project, a.out, toolchain)
            if a.action == "inspect"
            else rename_plan(a.project, a.spec, a.out, toolchain)
        )
    if a.command == "code":
        from grea.development.codecheck import inspect_code

        return inspect_code(a.project)
    raise ValueError(f"Unknown development command: {a.command}")
