"""Ui development command declarations and orchestration.

Algorithms and transaction guards remain in grea.development.
"""

ROUTES = {"ui": "", "wiring": "wiring"}


def register(sub, *, include_intake_plan=True):
    ui = sub.add_parser("ui").add_subparsers(dest="action", required=True)
    uinspect = ui.add_parser("inspect")
    for flag in ("project", "spec", "out", "editor-path"):
        uinspect.add_argument("--" + flag, required=True)
    uinspect.add_argument("--timeout", type=int, default=600)
    urepair = ui.add_parser("repair-plan")
    for flag in ("project", "snapshot", "spec", "out"):
        urepair.add_argument("--" + flag, required=True)
    uanalyze = ui.add_parser("analyze")
    for flag in ("snapshot", "spec", "out"):
        uanalyze.add_argument("--" + flag, required=True)
    wiring = sub.add_parser("wiring").add_subparsers(dest="action", required=True).add_parser("plan")
    for flag in ("project", "snapshot", "spec", "out"):
        wiring.add_argument("--" + flag, required=True)


def dispatch(a):
    if a.command == "ui":
        if a.action == "repair-plan":
            from grea.development.ui_repairs import plan

            return plan(a.project, a.snapshot, a.spec, a.out)
        from grea.development.ui_inspection import inspect, analyze

        if a.action == "inspect":
            return inspect(a.project, a.spec, a.out, a.editor_path, a.timeout)
        from grea.development.io import read, load, new_output, write_json

        data = analyze(load(read(a.snapshot)), load(read(a.spec)))
        data["provenance"] = "caller-supplied snapshot; collection origin not authenticated"
        stage = new_output(a.out, [a.snapshot, a.spec])
        write_json(stage / "ui-report.json", data)
        return dict(data, report=str(stage / "ui-report.json"))
    if a.command == "wiring":
        from grea.development.wiring import plan

        return plan(a.project, a.snapshot, a.spec, a.out)
    raise ValueError(f"Unknown development command: {a.command}")
