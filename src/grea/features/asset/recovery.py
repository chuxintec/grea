"""Asset recovery command declarations and orchestration.

Algorithms and transaction guards remain in grea.recovery.
"""

import zipfile
from grea.recovery.sources.compiled import fail
from pathlib import Path
from grea.recovery.unity_visual_repair import add_arguments as visual_arguments
from grea.recovery import __file__ as recovery_package_file

ROUTES = {
    "resource-probe": "resource-probe",
    "acquire-resources": "acquire-resources",
    "inspect-aliases": "inspect-aliases",
    "acquire-unity-textures": "acquire-unity-textures",
    "repair-unity-visuals": "repair-unity-visuals",
    "export-unity-textures": "export-unity-textures",
    "classify-unity-shaders": "classify-unity-shaders",
    "freeze-resource-candidate": "freeze-resource-candidate",
    "refresh-static-spine-helpers": "refresh-static-spine-helpers",
    "complete-static-spine-defaults": "complete-static-spine-defaults",
    "prepare-button-material-retry": "prepare-button-material-retry",
    "prepare-source-system-fonts": "prepare-source-system-fonts",
    "generate-source-system-fonts": "generate-source-system-fonts",
    "complete-native-font": "complete-native-font",
    "stage-native-font": "stage-native-font",
    "finish-native-font": "finish-native-font",
}


def register(sub, *, include_intake_plan=True):
    p = sub.add_parser(
        "resource-probe", help="Prepare a minimal native resource probe from exact frozen candidate closures"
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--expected-manifest", required=True)
    resource = p.add_mutually_exclusive_group(required=True)
    resource.add_argument("--spine", action="append")
    resource.add_argument("--shader")
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "acquire-resources",
        help="Fetch only an explicit resource list; verified partial receipts can be resumed into a fresh layer",
    )
    p.add_argument("--manifest", required=True)
    p.add_argument("--input-set", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--cache-root")
    p.add_argument("--resume-from")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--budget-seconds", type=int, default=900)
    p.add_argument("--max-attempts", type=int, default=3)
    p = sub.add_parser("inspect-aliases", help="Inspect exact frozen evidence; no source program execution")
    p.add_argument("--source", required=True)
    p.add_argument("--member", help="Exact ZIP member; expected SHA identifies member bytes, not the outer ZIP")
    p.add_argument("--expected-sha", required=True)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--out", required=True)
    p.add_argument("--alias")
    p.add_argument("--content-source")
    p.add_argument("--content-prefix", default="")
    p = sub.add_parser(
        "acquire-unity-textures", help="Capture exact serialized ASTC keys under a literal original DATA_CDN"
    )
    for name in ("inspection", "cache-manifest", "cdn-source", "cdn-root", "out"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--cache-root")
    p.add_argument("--budget-seconds", type=int, default=1200)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--resume", action="store_true")
    visual_arguments(
        sub.add_parser(
            "repair-unity-visuals", help="Prepare source-identified UI and effect repairs for an exported Unity project"
        )
    )
    p = sub.add_parser(
        "export-unity-textures",
        help="Export exact selected hydrated Texture2D pixels as PNG candidates without whole-container AssetRipper export",
    )
    for name in (
        "source",
        "derivative",
        "hydration-report",
        "expected-hydration-sha256",
        "selection-manifest",
        "provider-python",
        "out",
    ):
        p.add_argument("--" + name, required=True)
    p.add_argument("--budget-seconds", type=int, default=120)
    p = sub.add_parser(
        "classify-unity-shaders",
        help="Classify frozen recovered Shader evidence without compiling, moving or re-exporting assets",
    )
    for name in ("project", "manifest", "expected-manifest", "out"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--source-mapping")
    p.add_argument("--expected-source-mapping")
    p = sub.add_parser(
        "freeze-resource-candidate",
        help="Seal saved resource inventory and retain current verification gaps; does not grant accepted selection; no Editor launch",
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--expected-manifest", required=True)
    p.add_argument("--expected-readback", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "refresh-static-spine-helpers",
        help="Refresh pinned native helpers and Atlas mapping in a fresh stage while reusing decoded texture bytes",
    )
    p.add_argument("--request", required=True)
    p.add_argument("--expected-request", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "complete-static-spine-defaults",
        help="Apply pinned source-version defaults and reuse decoded Spine pages in a fresh stage",
    )
    p.add_argument("--request", required=True)
    p.add_argument("--expected-request", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "prepare-button-material-retry",
        help="Prepare a pinned Unity adapter for source-backed tiled Button target Images",
    )
    for flag in ("candidate", "expected-manifest", "plan", "ir", "out"):
        p.add_argument("--" + flag, required=True)
    p = sub.add_parser(
        "prepare-source-system-fonts",
        help="Resolve pinned source system Labels using existing CoreText and Unity font contracts",
    )
    p.add_argument("--request", required=True)
    p.add_argument("--expected-request", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "generate-source-system-fonts",
        help="Generate and validate static glyph inputs from a pinned source font preparation",
    )
    p.add_argument("--preparation", required=True)
    p.add_argument("--expected-preparation", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--budget-seconds", type=int, default=240)
    p = sub.add_parser(
        "complete-native-font",
        help="Append an explicitly pinned consumer text corpus using the same static font face and preserved glyphs",
    )
    p.add_argument("--request", required=True)
    p.add_argument("--expected-request", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "stage-native-font", help="Prepare a separate native Unity project to apply a pinned static-font completion"
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--expected-manifest", required=True)
    p.add_argument("--completion", required=True)
    p.add_argument("--expected-completion", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "finish-native-font", help="Freeze the actually saved font candidate after native identity and glyph checks"
    )
    p.add_argument("--project", required=True)
    p.add_argument("--expected-stage-manifest", required=True)
    p.add_argument("--readback", required=True)
    p.add_argument("--expected-readback", required=True)
    p.add_argument("--out", required=True)


def dispatch(args, *, usage_parser):
    if args.command == "repair-unity-visuals":
        from grea.recovery.unity_visual_repair import run as repair_visuals

        return (repair_visuals(args), 0)
    if args.command == "resource-probe":
        from grea.recovery.resource_probe import prepare, prepare_shader

        result = (
            prepare_shader(args.candidate, args.expected_manifest, args.shader, args.out)
            if args.shader
            else prepare(args.candidate, args.expected_manifest, args.spine, args.out)
        )
        return (result, 0)
    if args.command == "acquire-resources":
        from grea.recovery.acquisition import prepare, acquire
        from grea.recovery.inputs import input_set

        settings = prepare(
            args.manifest,
            args.out,
            input_set(args.input_set),
            args.cache_root,
            args.budget_seconds,
            resume_from=args.resume_from,
            max_attempts=args.max_attempts,
        )
        result = acquire(settings, args.offline)
        return (
            dict(
                status="complete" if result["summary"]["allDeclaredAvailable"] else "partial",
                report=str(result["receipt"]),
                inputSet=str(result["inputSet"]),
                summary=result["summary"],
            ),
            0 if result["summary"]["allDeclaredAvailable"] else 1,
        )
    if args.command == "inspect-aliases":
        from grea.recovery.evidence_queries import inspect_aliases

        try:
            result = inspect_aliases(
                args.source,
                args.expected_sha,
                args.out,
                member=args.member,
                alias=args.alias,
                limit=args.limit,
                content_source=args.content_source,
                content_prefix=args.content_prefix,
            )
        except (zipfile.BadZipFile, EOFError) as error:
            fail("EVIDENCE_ARCHIVE", args.source or args.manifest, str(error))
        return (
            dict(status=result["status"], operation=result["operation"], report=str(args.out) + "/inspection.json"),
            0,
        )
    if args.command == "freeze-resource-candidate":
        from grea.recovery.package_modules import freeze_native_resources

        result = freeze_native_resources(args.candidate, args.expected_manifest, args.expected_readback, args.out)
        return (result, 1 if result["workflowStatus"] == "partial" else 0)
    if args.command == "acquire-unity-textures":
        from grea.recovery.unity_texture_acquisition import acquire

        result = acquire(
            args.inspection,
            args.cache_manifest,
            args.cdn_source,
            args.cdn_root,
            args.out,
            args.cache_root,
            args.budget_seconds,
            args.workers,
            args.resume,
        )
        return (result, 0 if result["status"] == "captured" else 1)
    if args.command == "export-unity-textures":
        from grea.recovery.unity_texture_export import export as export_textures

        result = export_textures(
            args.source,
            args.derivative,
            args.hydration_report,
            args.expected_hydration_sha256,
            args.selection_manifest,
            args.provider_python,
            args.out,
            args.budget_seconds,
        )
        return (result, 0 if result["status"] == "exported" else 1)
    if args.command == "classify-unity-shaders":
        from grea.recovery.shader_handoff import classify_project

        result = classify_project(
            args.project,
            args.manifest,
            args.expected_manifest,
            args.out,
            args.source_mapping,
            args.expected_source_mapping,
        )
        return (result, 0)
    if args.command == "refresh-static-spine-helpers":
        from grea.recovery.prefab_static_spine_refresh import prepare

        result = prepare(args.request, args.expected_request, args.out)
        return (
            {k: result[k] for k in ("preparationStatus", "planPath", "native", "visual")},
            0 if result["preparationStatus"] == "prepared" else 1,
        )
    if args.command == "complete-static-spine-defaults":
        from grea.recovery.prefab_static_spine_defaults import prepare

        result = prepare(args.request, args.expected_request, args.out)
        return (
            {k: result[k] for k in ("status", "planPath", "rendering", "native", "visual")},
            0 if result["status"] == "prepared" else 1,
        )
    if args.command == "prepare-button-material-retry":
        from grea.recovery.button_material_retry import prepare

        return (prepare(args.candidate, args.expected_manifest, args.plan, args.ir, args.out), 0)
    if args.command in ("stage-native-font", "finish-native-font"):
        from grea.recovery.native_font_stage import stage, finish_stage, NativeFontStageError

        try:
            if args.command == "stage-native-font":
                result = stage(
                    args.candidate, args.expected_manifest, args.completion, args.expected_completion, args.out
                )
            else:
                result = finish_stage(
                    args.project, args.expected_stage_manifest, args.readback, args.expected_readback, args.out
                )
        except NativeFontStageError as exc:
            fail("NATIVE_FONT_STAGE_REJECTED", args.out, str(exc))
        return (result, 0)
    if args.command == "prepare-source-system-fonts":
        from grea.recovery.source_system_font_preparation import prepare

        prepared = prepare(args.request, args.expected_request, args.out)
        return (prepared.record, 0 if prepared.status == "prepared" else 1)
    if args.command == "generate-source-system-fonts":
        from grea.recovery.source_system_font_preparation import generate

        generated = generate(args.preparation, args.expected_preparation, args.out, budget_seconds=args.budget_seconds)
        return (generated.record, 0 if generated.status == "prepared" else 1)
    if args.command == "complete-native-font":
        from grea.recovery.io import read, load, sha
        from grea.recovery.native_font_completion import complete_native_font_from_corpus, NativeFontCompletionError

        raw_request = read(args.request)
        if sha(raw_request) != args.expected_request:
            fail("FONT_REQUEST_SHA_MISMATCH", args.request, "Consumer font request differs from its pin")
        request = load(raw_request)
        allowed = {
            "corpus_path",
            "expected_corpus_sha256",
            "base_binding_path",
            "expected_base_binding_sha256",
            "base_generation_receipt_path",
            "expected_base_generation_receipt_sha256",
            "base_static_plan_path",
            "expected_base_static_plan_sha256",
            "static_font_asset_id",
            "requested_primary_family",
            "expected_primary_style",
            "watch_files",
        }
        required = allowed - {"requested_primary_family", "expected_primary_style", "watch_files"}
        if not isinstance(request, dict) or set(request) - allowed or required - set(request):
            fail("FONT_REQUEST_INVALID", args.request, "Expected the documented pinned consumer font request fields")
        try:
            result = complete_native_font_from_corpus(
                **request,
                generator_path=Path(recovery_package_file).parent / "targets" / "GenerateCoreTextSdf.swift",
                output_dir=args.out,
            )
        except NativeFontCompletionError as exc:
            fail("FONT_COMPLETION_REJECTED", args.request, str(exc))
        return (result, 0)
    raise ValueError(f"Unknown recovery command: {args.command}")
