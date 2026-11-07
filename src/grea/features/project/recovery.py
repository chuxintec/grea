"""Project recovery command declarations and orchestration.

Algorithms and transaction guards remain in grea.recovery.
"""

import sys
from grea.recovery import incremental
from pathlib import Path

ROUTES = {
    "adopt": None,
    "adopt-recover": None,
    "layout-migration": "layout-migration",
    "project-model": "project-model",
    "native-finish-plan": "native-finish-plan",
    "native-finish": "native-finish",
    "native-import": "native-import",
    "recover-native-execution": "recover-native-execution",
    "shard-unity-plan": "shard-unity-plan",
    "restore-unity-plan": "restore-unity-plan",
    "freeze-native-selection": "freeze-native-selection",
    "upgrade-native-runtime": "upgrade-native-runtime",
    "register": None,
    "apply": None,
}


def register(sub, *, include_intake_plan=True):
    p = sub.add_parser("adopt", help="Legacy three-way asset adoption; new transactions use grea develop adopt")
    p.add_argument("--candidate", help="Frozen incoming package or Unity-source project")
    p.add_argument("--target", help="Existing owned development project; never the source export")
    p.add_argument("--baseline", help="Explicit frozen common generation for first adoption")
    p.add_argument(
        "--lineage", help="Explicit stable game namespace for Unity-source exports without their own namespace"
    )
    p.add_argument("--plan", help="Previously reviewed adoption-plan.json; required for execution")
    p.add_argument("--expected-plan", help="Exact SHA256 of the reviewed adoption plan")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--editor-path", help="Existing exact target Editor executable")
    p.add_argument("--budget-seconds", type=int, default=1200)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "adopt-recover",
        help="Deprecated compatibility: recover an existing adoption transaction; legacy transaction recovery",
    )
    p.add_argument("--transaction", required=True)
    p.add_argument("--editor-path", required=True)
    p.add_argument("--budget-seconds", type=int, default=1200)
    p = sub.add_parser(
        "layout-migration",
        help="Old candidate path -> new candidate path for every shared GUID/UUID, for AssetDatabase.MoveAsset in adopted projects",
    )
    p.add_argument("--from", dest="old", required=True)
    p.add_argument("--to", dest="new", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "project-model", help="Inspect explicit target asset path slots and identity without moving files"
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "native-finish-plan",
        help="Prepare incremental source Scene export and SHRINK evidence using existing native assets",
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--exclude-scene", action="append", default=[])
    p = sub.add_parser(
        "native-finish", help="Plan or execute one bounded incremental finish in an explicitly owned native project"
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--preparation", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--editor-path", required=True)
    p.add_argument("--expected-manifest", required=True)
    p.add_argument("--budget-seconds", type=int, default=600)
    p.add_argument("--deadline-utc", required=True)
    p.add_argument("--window-end-utc", required=True)
    p.add_argument("--execute", action="store_true")
    p.add_argument("--previous-execution")
    p = sub.add_parser(
        "native-import", help="Plan or explicitly execute a bounded Unity/Creator import in a fresh copy"
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--editor-path", required=True)
    p.add_argument("--expected-manifest", required=True)
    p.add_argument("--budget-seconds", type=int, default=600)
    p.add_argument("--deadline-utc", required=True)
    p.add_argument("--window-end-utc", required=True)
    p.add_argument("--execute", action="store_true")
    p.add_argument(
        "--render-preview", action="store_true", help="Unity: use a real graphics device for diagnostic previews"
    )
    p = sub.add_parser(
        "recover-native-execution",
        help="Write a hash-bound independent receipt for a stopped transaction without changing old evidence or launching an Editor",
    )
    p.add_argument("--request", required=True)
    p.add_argument("--expected-request", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("shard-unity-plan", help="Checkpoint all owned Unity plan inputs in verified chunks")
    p.add_argument("--plan", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--expected-manifest", required=True)
    p.add_argument("--max-new-chunks", type=int)
    p = sub.add_parser("restore-unity-plan", help="Reassemble the exact owned plan stage from its pinned index")
    p.add_argument("--index", required=True)
    p.add_argument("--expected-index", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "freeze-native-selection",
        help="Freeze selected saved Unity Prefabs with native identities and producer-declared compile dependencies",
    )
    p.add_argument("--candidate", required=True)
    p.add_argument(
        "--prefab",
        action="append",
        required=True,
        help="Exact candidate-relative Assets Prefab path; repeat to select more than one",
    )
    p.add_argument("--expected-manifest", required=True)
    p.add_argument("--expected-readback", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "upgrade-native-runtime",
        help="Copy a frozen selection and upgrade only exact known native presentation templates",
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--expected-manifest", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("register")
    p.add_argument("--candidate", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("apply")
    p.add_argument("--target", required=True)
    p.add_argument("--candidate", required=True)
    p.add_argument("--expected-manifest", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--write", action="store_true")
    p.add_argument("--preview")


def dispatch(args, *, usage_parser):
    if args.command == "adopt":
        print("Legacy adoption command. For new development transactions use grea develop adopt.", file=sys.stderr)
        if args.execute:
            if (
                not args.plan
                or not args.expected_plan
                or (not args.editor_path)
                or any((args.candidate, args.target, args.baseline, args.lineage))
            ):
                usage_parser.error(
                    "adopt --execute requires --plan --expected-plan --editor-path and no candidate/target/baseline"
                )
            from grea.recovery.adoption_native import execute

            result = execute(args.plan, args.out, args.editor_path, args.budget_seconds, args.expected_plan)
        else:
            if not args.candidate or not args.target or any((args.plan, args.expected_plan, args.editor_path)):
                usage_parser.error("adopt preview requires --candidate --target and optional --baseline")
            from grea.recovery.adoption import preview

            result = preview(args.candidate, args.target, args.out, args.baseline, args.lineage)
        return (result, 1 if result["status"] == "blocked" else 0)
    if args.command == "adopt-recover":
        print("Legacy adoption recovery. Use the implementation recorded in the original transaction.", file=sys.stderr)
        from grea.recovery.adoption_native import recover

        result = recover(args.transaction, args.editor_path, args.budget_seconds)
        return (result, 0)
    if args.command == "layout-migration":
        from grea.recovery.layout.records import migration

        return (migration(args.old, args.new, args.out), 0)
    if args.command == "project-model":
        from grea.recovery.project_model import inspect as project_model

        return (project_model(args.candidate, args.out), 0)
    if args.command == "native-finish":
        from grea.recovery.cocos_native_finish import execute as native_finish

        result = native_finish(
            args.candidate,
            args.preparation,
            args.out,
            args.editor_path,
            args.expected_manifest,
            args.budget_seconds,
            args.deadline_utc,
            args.window_end_utc,
            args.execute,
            args.previous_execution,
        )
        return (result, 0 if result["status"] in ("planned", "completed") else 1)
    if args.command == "native-finish-plan":
        from grea.recovery.cocos_native_finish import prepare

        return (prepare(args.candidate, args.out, args.exclude_scene), 0)
    if args.command == "apply":
        result = incremental.apply(
            args.target, args.candidate, args.expected_manifest, args.out, Path.cwd(), args.write, args.preview
        )
        return (
            dict(
                status=result["status"],
                assets=result.get("counts", {}).get("assets", len(result.get("assets", []))),
                spriteFrames=result.get("counts", {}).get("spriteFrames", len(result.get("spriteFrames", []))),
                diagnostics=len(result["diagnostics"]),
                report=str(args.out) + "/manifest.json",
            ),
            1 if result["status"] == "partial" else 0,
        )
    if args.command == "register":
        from grea.recovery.io import new_output, write_json, finish

        record = incremental.register(args.candidate, Path.cwd())
        out = new_output(args.out, [Path(args.candidate).resolve()])
        write_json(out / "registration.json", record)
        result = finish(out, dict(schemaVersion=1, diagnostics=[], registration=record))
        return (
            dict(
                status=result["status"],
                assets=result.get("counts", {}).get("assets", len(result.get("assets", []))),
                spriteFrames=result.get("counts", {}).get("spriteFrames", len(result.get("spriteFrames", []))),
                diagnostics=len(result["diagnostics"]),
                report=str(args.out) + "/manifest.json",
            ),
            1 if result["status"] == "partial" else 0,
        )
    if args.command == "shard-unity-plan":
        from grea.recovery.export_plan import shard

        result = shard(args.plan, args.out, args.expected_manifest, args.max_new_chunks)
        return (result, 1 if result["status"] == "paused" else 0)
    if args.command == "restore-unity-plan":
        from grea.recovery.export_plan import restore

        return (restore(args.index, args.expected_index, args.out), 0)
    if args.command == "native-import":
        from grea.recovery.native import native_import

        result = native_import(
            args.candidate,
            args.out,
            args.editor_path,
            args.expected_manifest,
            args.budget_seconds,
            args.deadline_utc,
            args.window_end_utc,
            args.execute,
            render_preview=args.render_preview,
        )
        return (
            {k: result.get(k) for k in ("status", "processStarted", "processExited", "pid", "reason", "report")},
            0 if result["status"] in ("planned", "candidate") else 1,
        )
    if args.command == "recover-native-execution":
        from grea.recovery.native import recover_execution

        result = recover_execution(args.request, args.expected_request, args.out)
        return (result, 0)
    if args.command == "upgrade-native-runtime":
        from grea.recovery.native_runtime_update import upgrade

        updated = upgrade(args.candidate, args.expected_manifest, args.out)
        return (
            dict(
                status="prepared",
                manifest=str(Path(args.out) / "manifest.json"),
                runtimeUpdate=updated["runtimeUpdate"],
            ),
            0,
        )
    if args.command == "freeze-native-selection":
        from grea.recovery.native_selection import freeze

        frozen = freeze(args.candidate, args.prefab, args.out, args.expected_manifest, args.expected_readback)
        return (
            dict(
                status="frozen",
                manifest=str(Path(args.out) / "manifest.json"),
                files=len(frozen["files"]),
                selection=frozen["selection"],
                diagnostics=frozen.get("diagnostics", []),
            ),
            0,
        )
    raise ValueError(f"Unknown recovery command: {args.command}")
