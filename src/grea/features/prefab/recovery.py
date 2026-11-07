"""Prefab recovery command declarations and orchestration.

Algorithms and transaction guards remain in grea.recovery.
"""

import json
from grea.recovery.sources.compiled import fail

ROUTES = {
    "select-prefab-presentation": "select-presentation",
    "audit-prefab-presentation": "audit-presentation",
    "prepare-unity-runtime-hosts": "prepare-hosts",
    "continue-static-prefabs": "continue-static-prefabs",
    "prefab-static-fields": "static-fields",
    "prefab-behavior-ir": "behavior-ir",
    "recover-unity-prefabs": "recover",
    "inspect-unity-prefab-schemas": "inspect-schemas",
    "rebuild-unity-prefab-texture-material-assets": "rebuild-texture-materials",
    "rebuild-unity-prefab-assets": "rebuild-assets",
    "verify-unity-prefabs": "verify",
    "freeze-unity-prefabs": "freeze",
}


def register(sub, *, include_intake_plan=True):
    p = sub.add_parser("select-prefab-presentation", help="Freeze a representative Cocos UI Prefab sample")
    p.add_argument("--ir", required=True)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--pool")
    p.add_argument("--exclude")
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "audit-prefab-presentation", help="Verify saved prefab references, sibling order and layout coordinates"
    )
    p.add_argument("--project", action="append", required=True)
    p.add_argument("--selection", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "prepare-unity-runtime-hosts", help="Identify original per-prefab MonoBehaviour hosts for native validation"
    )
    p.add_argument("--manifest", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--project", help="Install the matching Editor save/cold verifier in this candidate")
    p = sub.add_parser(
        "continue-static-prefabs",
        help="Continue pinned component families in a fresh plan without rerunning source normalization",
    )
    p.add_argument("--request", required=True)
    p.add_argument("--expected-request", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "prefab-static-fields", help="Preserve serialized custom fields in a fresh IR stage without rerunning resources"
    )
    p.add_argument("--manifest", required=True)
    p.add_argument("--ir", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "prefab-behavior-ir", help="Generate source-bound native behavior scripts in an independent IR stage"
    )
    p.add_argument("--manifest", required=True)
    p.add_argument("--ir", required=True)
    p.add_argument("--source-bundle", required=True)
    p.add_argument("--expected-source-bundle", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "recover-unity-prefabs",
        help="Recover selected Unity-source Prefabs from exact reader/provider caches and structural type evidence",
    )
    p.add_argument("--request", required=True)
    p.add_argument("--expected-request", required=True)
    p.add_argument("--out", required=True)
    p.add_argument(
        "--input-path-map", help="Explicit input-root relocation descriptor; original input hashes remain mandatory"
    )
    p.add_argument("--expected-input-path-map", help="SHA256 of the explicit relocation descriptor")
    p = sub.add_parser(
        "inspect-unity-prefab-schemas",
        help="Read exact built-in schemas from a pinned source bundle without executing game code",
    )
    p.add_argument("--request", required=True)
    p.add_argument("--expected-request", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "rebuild-unity-prefab-texture-material-assets",
        help="Rebind selected original texture pixels into before-pinned native Materials; Shader semantics remain unverified",
    )
    p.add_argument("--request", required=True)
    p.add_argument("--expected-request", required=True)
    p.add_argument("--unity-editor", required=True)
    p.add_argument("--budget-seconds", type=int, default=600)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "rebuild-unity-prefab-assets",
        help="Create and independently reopen explicitly selected source-derived native Sprite assets",
    )
    p.add_argument("--request", required=True)
    p.add_argument("--expected-request", required=True)
    p.add_argument("--unity-editor", required=True)
    p.add_argument("--budget-seconds", type=int, default=600)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "verify-unity-prefabs", help="Verify a selected Unity-source candidate in a fresh owned native Editor project"
    )
    p.add_argument(
        "--headless", action="store_true", help="Use no graphics or Editor window; visible presentation remains not_run"
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--expected-manifest", required=True)
    p.add_argument("--unity-editor", required=True)
    p.add_argument("--budget-seconds", type=int, default=600)
    p.add_argument("--out", required=True)
    p.add_argument(
        "--input-path-map", help="Explicit input-root relocation descriptor; original input hashes remain mandatory"
    )
    p.add_argument("--expected-input-path-map", help="SHA256 of the explicit relocation descriptor")
    p = sub.add_parser("freeze-unity-prefabs", help="Freeze exact independently reopened Unity-source candidate bytes")
    p.add_argument("--native-output", required=True)
    p.add_argument("--expected-execution", required=True)
    p.add_argument("--out", required=True)
    p.add_argument(
        "--input-path-map", help="Explicit input-root relocation descriptor; original input hashes remain mandatory"
    )
    p.add_argument("--expected-input-path-map", help="SHA256 of the explicit relocation descriptor")


def dispatch(args, *, usage_parser):
    if args.command == "prepare-unity-runtime-hosts":
        from grea.recovery.unity_runtime_hosts import prepare as prepare_hosts

        return (prepare_hosts(args.manifest, args.out, args.project), 0)
    if args.command == "select-prefab-presentation":
        from grea.recovery.prefab_presentation_audit import select

        count = select(args.ir, args.limit, args.out, args.pool, args.exclude)
        return (dict(selected=count), 0)
    if args.command == "audit-prefab-presentation":
        from grea.recovery.prefab_presentation_audit import audit

        report = audit(args.project, args.selection, args.out)
        return ({key: report[key] for key in ("selected", "structuralIssues")}, 1 if report["structuralIssues"] else 0)
    if args.command == "recover-unity-prefabs":
        from grea.recovery.unity_prefab_recovery import recover
        from grea.recovery.input_relocation import command_context

        with command_context(args):
            result = recover(args.request, args.expected_request, args.out)
        return (
            dict(status=result["status"], report=str(args.out) + "/result.json", native=result["native"]),
            1 if result["status"] == "needs_action" else 0,
        )
    if args.command == "inspect-unity-prefab-schemas":
        from grea.recovery.unity_prefab_recovery import pinned
        from grea.recovery.unity_prefab_schemas import extract_builtin_schemas

        _, raw = pinned(dict(path=args.request, sha256=args.expected_request), 8 * 1024 * 1024)
        request = json.loads(raw)
        if (
            request.get("contract") != "monkey-unity-prefab-builtin-schema-request/1"
            or request.get("schemaVersion") != 1
        ):
            fail("UNITY_PREFAB_BUILTIN_SCHEMA_REQUEST", args.request, "Versioned built-in schema request required")
        result = extract_builtin_schemas(
            request["source"]["path"],
            request["source"]["sha256"],
            request["providerPython"],
            request["wantedObjects"],
            args.out,
            budget_seconds=request.get("budgetSeconds", 120),
            prior_reader_evidence=request.get("priorReaderEvidence"),
        )
        return (
            dict(
                status=result["status"], report=str(args.out) + "/receipt.json", processExited=result["processExited"]
            ),
            0 if result["status"] == "schemas_read" else 1,
        )
    if args.command == "rebuild-unity-prefab-texture-material-assets":
        from grea.recovery.unity_prefab_texture_material_rebuild import execute

        result = execute(args.request, args.expected_request, args.out, args.unity_editor, args.budget_seconds)
        return (result, 0)
    if args.command == "rebuild-unity-prefab-assets":
        from grea.recovery.unity_prefab_asset_rebuild import execute

        result = execute(args.request, args.expected_request, args.out, args.unity_editor, args.budget_seconds)
        return (result, 0)
    if args.command == "verify-unity-prefabs":
        from grea.recovery.unity_prefab_native import execute
        from grea.recovery.input_relocation import command_context

        with command_context(args):
            result = execute(
                args.candidate,
                args.expected_manifest,
                args.out,
                args.unity_editor,
                args.budget_seconds,
                headless=args.headless,
            )
        return (
            {k: v for k, v in result.items() if k != "savedFiles"},
            0 if result["status"] == "native-verified-subset" else 1,
        )
    if args.command == "freeze-unity-prefabs":
        from grea.recovery.unity_prefab_native import freeze
        from grea.recovery.input_relocation import command_context

        with command_context(args):
            result = freeze(args.native_output, args.expected_execution, args.out)
        return (result, 1 if result["status"] == "needs_action" else 0)
    if args.command == "continue-static-prefabs":
        from grea.recovery.prefab_static_continuation import prepare

        result = prepare(args.request, args.expected_request, args.out)
        return (
            {k: result[k] for k in ("preparationStatus", "planPath", "familyResults", "native", "visual")},
            0 if result["preparationStatus"] == "prepared" else 1,
        )
    if args.command == "prefab-static-fields":
        from grea.recovery.prefab_static_pipeline import project_ir

        result = project_ir(args.manifest, args.ir, args.out)
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
    if args.command == "prefab-behavior-ir":
        from grea.recovery.prefab_behavior_pipeline import project_ir as prefab_behavior_ir

        result = prefab_behavior_ir(args.manifest, args.ir, args.source_bundle, args.expected_source_bundle, args.out)[
            "manifest"
        ]
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
    raise ValueError(f"Unknown recovery command: {args.command}")
