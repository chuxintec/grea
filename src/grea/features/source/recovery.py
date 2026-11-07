"""Source recovery command declarations and orchestration.

Algorithms and transaction guards remain in grea.recovery.
"""

from grea.recovery.sources.bundle import inspect, PROFILE
from grea.recovery.sources.project import inspect as inspect_project, catalog, PROFILE as PROJECT_PROFILE
from grea.recovery.normalize import normalize
from grea.recovery.targets.unity import plan, verify, handoff, PROFILE as UNITY_PROFILE
from grea.recovery.targets import cocos
from grea.recovery import incremental
from pathlib import Path

ROUTES = {
    "convert": "convert",
    "hydrate-unity": "hydrate-unity",
    "index-unity": "index-unity",
    "export-unity": "export-unity",
    "inspect-unity": "inspect-unity",
    "freeze-unity-handoff": "freeze-unity-handoff",
    "freeze-handoff": "freeze-handoff",
    "export-unity-bulk": "export-unity-bulk",
    "prepare-unity-bulk": "prepare-unity-bulk",
    "preflight": "preflight",
    "inspect": "inspect",
    "catalog": "catalog",
    "normalize": "normalize",
    "plan": "plan",
    "export": "export",
    "verify": "verify",
    "handoff": "handoff",
    "diff": "diff",
}


def register(sub, *, include_intake_plan=True):
    p = sub.add_parser(
        "convert",
        description="Expanded input batch defaults to 2048 MiB; each package entry is limited to 128 MiB. An explicit input set can set its combined budget.",
        help="Convert a source project into an isolated native project candidate",
    )
    p.add_argument(
        "--unity-system-fonts",
        choices=["coretext"],
        help="Resolve Cocos 2.4.15 system Labels on this Mac and generate required Unity SDF faces",
    )
    p.add_argument("--source", help="Local wxapkg/APK, resource/project directory, project.json or bundle config.json")
    p.add_argument(
        "--format",
        choices=["none", "grea"],
        default=None,
        help="Deprecated: every output already uses grea-project-layout/2.1.0; grea is accepted as an alias.",
    )
    p.add_argument(
        "--layout",
        help="Game layout.json: module/rename/bundle-role overrides for grea-project-layout/2.1.0 paths (docs/history/recovery/PROJECT-SPEC.md section 7)",
    )
    p.add_argument(
        "--source-family",
        choices=["auto", "cocos", "unity", "laya", "layaair", "egret", "eraget", "custom", "other"],
        default="auto",
    )
    p.add_argument("--provider-python", help="Existing Python with UnityPy 1.25.3 for Unity source conversion")
    p.add_argument("--asset-ripper", help="Existing exact AssetRipper 2.0.0 provider executable")
    p.add_argument("--provider-budget-seconds", type=int, default=600)
    p.add_argument(
        "--unity-object-value-limit",
        type=int,
        help="Unity inline value limit per object; default 250000, maximum 1000000; streamed payloads have separate byte limits",
    )
    p.add_argument(
        "--unity-container-value-limit",
        type=int,
        help="Unity inline value limit per input container; default 8000000, maximum 16000000",
    )
    p.add_argument(
        "--unity-texture-cache",
        help="Explicit local ASTC or single-level DDS/DXT5 cache pool for supported Unity texture-key hydration",
    )
    p.add_argument(
        "--unity-quarantine-invalid-textures",
        action="store_true",
        help="Explicit partial export excluding exact invalid ETC1 objects; originals and unresolved references retained",
    )
    p.add_argument(
        "--unity-dependency-manifest",
        help="Frozen Unity bundle lookup pool; export only exact reachable serialized-file closure",
    )
    p.add_argument(
        "--unity-export-scope",
        choices=["reachable", "all"],
        default="reachable",
        help="all exports every unique container in the explicit Unity bundle manifest",
    )
    p.add_argument("--unity-prepared-textures", help="Frozen prepare-unity-bulk output; reuse exact derived containers")
    p.add_argument(
        "--unity-reuse-provider-export", help="Frozen export-unity-bulk output; assemble without relaunching provider"
    )
    p.add_argument(
        "--unity-reuse-inspection", help="Reuse an exact same-worker complete inspect-unity --bundle-manifest snapshot"
    )
    p.add_argument(
        "--unity-code-evidence",
        help="Frozen metadata/declaration/source-code evidence manifest for a self-contained AI handoff",
    )
    p.add_argument(
        "--unity-schema-manifest", help="Frozen bundle pool for exact missing TypeTree lookup during Unity conversion"
    )
    p.add_argument(
        "--code-source", help="Exact original JS file present by SHA/bytes in this package or frozen resource candidate"
    )
    p.add_argument(
        "--module-contract", help="Reviewed source-bound typed module contract for the complete Unity candidate"
    )
    p.add_argument(
        "--module-selectors",
        help="Exact classId/methodId roots; infer provable types and close dependencies, optionally using --module-contract as evidence",
    )
    p.add_argument(
        "--configuration-table",
        help="Exact source-bound runtime JSON table accepted by the selected module configuration adapter",
    )
    p.add_argument(
        "--reuse-candidate",
        help="Frozen complete resource candidate to compose with recovered modules, without redecoding source resources",
    )
    p.add_argument("--expected-candidate", help="Required exact SHA256 of the frozen candidate owning manifest")
    p.add_argument(
        "--numeric-code-contract",
        help="Explicit source identity and numeric Label-field or reviewed static Number-method contract; fresh package conversion only",
    )
    p.add_argument(
        "--cocos-code-language",
        choices=["ts", "js"],
        default="ts",
        help="Cocos code output; TypeScript first; JS uses an explicit ESM package boundary",
    )
    p.add_argument(
        "--reuse-source-stages",
        help="Fresh package output using verified source stages; supports names-v1 metadata migration",
    )
    p.add_argument("--input-set", help="Explicit local roots and identity/provenance manifest (schema 1)")
    p.add_argument("--target", choices=["unity", "cocos", "unity6", "cocos38", "both", UNITY_PROFILE, cocos.PROFILE])
    p.add_argument(
        "--package",
        action="store_true",
        help="Inventory all input files and generate self-contained recovery workspaces",
    )
    p.add_argument(
        "--out", "--output", help="Fresh output directory; package targets use UnityProject/ and CocosProject/"
    )
    p.add_argument("--resume", help="Resume a conversion with identity/hash checks; packages also require --input-set")
    p.add_argument("--recipe", help="Reusable JSON input/selection options; combine with --out")
    p.add_argument("--offline", action="store_true", help="Explicitly generate and verify an offline candidate only")
    p.add_argument("--namespace")
    p.add_argument(
        "--source-profile",
        choices=[PROFILE, PROJECT_PROFILE, "generic-image-resources-v1", "egret-custom-resource-plist-v1"],
    )
    pick = p.add_mutually_exclusive_group()
    pick.add_argument("--asset-index", type=int, action="append")
    pick.add_argument(
        "--all-assets", action="store_true", help="Explicitly select every bundle entry (project default)"
    )
    p.add_argument("--dependency-source", action="append", default=[])
    p.add_argument("--evidence-source", action="append", default=[])
    p.add_argument("--bindings")
    p.add_argument("--animation", action="append")
    p.add_argument(
        "--native",
        action="store_true",
        help="After fresh package conversion, execute sequential bounded native imports",
    )
    p.add_argument("--native-out", help="Fresh separate native workspace; default OUTPUT-native")
    p.add_argument("--unity-editor", help="Exact installed Unity executable for --native")
    p.add_argument("--creator-editor", help="Exact installed CocosCreator executable for --native")
    p.add_argument(
        "--native-budget-seconds",
        type=int,
        default=1200,
        help="Method budget per Editor, 1..1200; each window is at most 30 minutes",
    )
    p.add_argument(
        "--remote-manifest",
        help="Explicit URL/path/SHA/byte downloads; Cocos requires --input-set, Unity accepts an explicit source container",
    )
    p.add_argument("--remote-cache-root", help="Read-only root for paths in the remote manifest")
    p.add_argument("--acquisition-out", help="Fresh acquired-files workspace; default OUTPUT-acquired")
    p.add_argument("--remote-budget-seconds", type=int, default=900, help="Acquisition budget, 30..3600 seconds")
    p = sub.add_parser(
        "hydrate-unity", help="Resolve explicit WeChat texture keys against a pinned local ASTC or DDS/DXT5 cache pool"
    )
    p.add_argument("--source", required=True)
    p.add_argument("--texture-cache", required=True)
    p.add_argument(
        "--selection-manifest",
        help="Frozen source SHA and exact Texture2D file/pathId/rawSha256/logicalPath selection; unselected objects stay unchanged and pending",
    )
    p.add_argument("--provider-python", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--budget-seconds", type=int, default=120)
    p = sub.add_parser(
        "index-unity", help="Index exact serialized files and PPtr IDs from an explicit frozen bundle list"
    )
    p.add_argument("--manifest", required=True)
    p.add_argument("--provider-python", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--budget-seconds", type=int, default=600)
    p = sub.add_parser(
        "export-unity", help="Export a Unity bundle through an existing fixed AssetRipper in an isolated copy"
    )
    p.add_argument("--source", required=True)
    p.add_argument("--asset-ripper", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--budget-seconds", type=int, default=600)
    p = sub.add_parser(
        "inspect-unity", help="Strict typed inspection of an explicit Unity serialized file or AssetBundle"
    )
    p.add_argument("--source", required=True)
    p.add_argument(
        "--schema-manifest",
        help="Explicit frozen bundle pool; borrow only identical version/platform/script/type hashes",
    )
    p.add_argument(
        "--provider-python", required=True, help="Existing Python with UnityPy 1.25.3; never installed automatically"
    )
    p.add_argument("--out", required=True)
    p.add_argument("--budget-seconds", type=int, default=120)
    p.add_argument(
        "--bundle-manifest", help="Inspect every unique container in the explicit frozen bundle pool in one worker"
    )
    p.add_argument(
        "--unity-object-value-limit",
        type=int,
        help="Unity inline value limit per object; default 250000, maximum 1000000; streamed payloads have separate byte limits",
    )
    p.add_argument(
        "--unity-container-value-limit",
        type=int,
        help="Unity inline value limit per input container; default 8000000, maximum 16000000",
    )
    p = sub.add_parser(
        "freeze-unity-handoff", help="Freeze complete original/acquired input dispositions in a Unity-source initial"
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--texture-cache", required=True)
    p.add_argument("--source-manifest", required=True)
    p.add_argument("--source-root", required=True)
    p.add_argument("--expected-manifest", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "freeze-handoff", help="Freeze an additive source-native identity and named-code initial handoff"
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--native-contract", required=True)
    p.add_argument("--verification", required=True)
    p.add_argument("--expected-manifest", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--apply-owned", action="store_true")
    p = sub.add_parser(
        "export-unity-bulk", help="Export all frozen prepared containers in one separately bounded AssetRipper stage"
    )
    p.add_argument("--prepared", required=True)
    p.add_argument("--asset-ripper", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--budget-seconds", type=int, default=1200)
    p.add_argument("--deadline-utc", required=True)
    p.add_argument("--window-end-utc", required=True)
    p = sub.add_parser(
        "prepare-unity-bulk", help="Resume exact whole-pool texture preparation independently of provider export"
    )
    p.add_argument("--inspection", required=True)
    p.add_argument("--texture-cache", required=True)
    p.add_argument("--capture", required=True)
    p.add_argument("--provider-python", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--budget-seconds", type=int, default=1200)
    p.add_argument("--resume", action="store_true")
    p = sub.add_parser("preflight", help="Check frozen candidate and classify startup logs without launching an Editor")
    p.add_argument("--candidate", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--log")
    p.add_argument("--progress")
    p = sub.add_parser("inspect")
    p.add_argument("--source", required=True)
    p.add_argument("--source-profile", choices=[PROFILE, PROJECT_PROFILE], required=True)
    p.add_argument("--evidence-source", action="append", default=[])
    p.add_argument("--dependency-source", action="append", default=[])
    p.add_argument("--asset-index", type=int, action="append", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("catalog")
    p.add_argument("--source", required=True)
    p.add_argument("--source-profile", choices=[PROJECT_PROFILE], required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("normalize")
    p.add_argument("--manifest", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--ir", required=True)
    p.add_argument("--static-source-bundle", help="Original JS bundle, parsed only for static constructor fields")
    p.add_argument("--expected-static-source-bundle", help="Expected source bundle SHA-256")
    p.add_argument(
        "--system-font-resolution", help="Explicit macOS CoreText resolution receipt for source system-font Labels"
    )
    p.add_argument("--expected-system-font-resolution", help="Expected resolution receipt SHA-256")
    p.add_argument(
        "--static-font-generation", help="Pinned generated CoreText SDF receipt for an explicitly resolved static face"
    )
    p.add_argument("--expected-static-font-generation", help="Expected generated SDF receipt SHA-256")
    p.add_argument("--spine-bindings", help="Pinned source component and resource emission receipt for Creator")
    p.add_argument("--expected-spine-bindings", help="Expected Spine emission receipt SHA-256")
    p.add_argument("--spine-resources", help="Frozen Creator Spine resource candidate")
    p.add_argument("--namespace", required=True)
    p.add_argument("--bindings")
    p.add_argument(
        "--animation", action="append", help="Select a source AnimationClip ID; default all normalized clips"
    )
    p.add_argument("--target-profile", choices=[UNITY_PROFILE, cocos.PROFILE], required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("export")
    p.add_argument("--plan", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "verify",
        description="Unity import instructions are limited to 256 MiB and checked against the candidate manifest.",
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--level", choices=["static", "editor"], default="static")
    p.add_argument("--editor-readback-sha256", help="SHA-256 of the completed Unity editor-readback.json")
    p.add_argument("--source-prefabs-readback-sha256", help="Matching source-prefabs-readback.json SHA-256")
    p.add_argument("--out", required=True)
    p = sub.add_parser("handoff")
    p.add_argument("--candidate", required=True)
    p.add_argument("--out", required=True)
    p.add_argument(
        "--native-contract",
        action="store_true",
        help="Read existing Sprite importer, actual fileID and Prefab reference evidence",
    )
    p = sub.add_parser("diff")
    p.add_argument("--before", required=True)
    p.add_argument("--after", required=True)
    p.add_argument("--out", required=True)


def dispatch(args, *, usage_parser):
    unity_parse_limits = {
        k: v
        for k, v in [
            ("objectValues", getattr(args, "unity_object_value_limit", None)),
            ("containerValues", getattr(args, "unity_container_value_limit", None)),
        ]
        if v is not None
    } or None
    if args.command == "hydrate-unity":
        from grea.recovery.unity_textures import hydrate

        result = hydrate(
            args.source,
            args.texture_cache,
            args.provider_python,
            args.out,
            args.budget_seconds,
            args.selection_manifest,
        )
        return (result, 0 if result["status"] == "hydrated" else 1)
    if args.command == "index-unity":
        from grea.recovery.unity_index import catalog as index_unity

        result = index_unity(args.manifest, args.provider_python, args.out, args.budget_seconds)
        return (result, 0 if result["status"] == "indexed" else 1)
    if args.command == "export-unity":
        from grea.recovery.providers.assetripper import export as export_unity

        result = export_unity(args.source, args.asset_ripper, args.out, args.budget_seconds)
        return (result, 1)
    if args.command == "inspect-unity":
        from grea.recovery.sources.unity_serialized import inspect as inspect_unity

        if args.bundle_manifest:
            from grea.recovery.unity_batch import inspect_set

            result = inspect_set(
                args.source,
                args.bundle_manifest,
                args.provider_python,
                args.out,
                args.budget_seconds,
                args.schema_manifest,
                parse_limits=unity_parse_limits,
            )
        else:
            result = inspect_unity(
                args.source,
                args.provider_python,
                args.out,
                args.budget_seconds,
                schema_manifest=args.schema_manifest,
                parse_limits=unity_parse_limits,
            )
        return (result, 0 if result["status"] == "inspected" else 1)
    if args.command == "freeze-unity-handoff":
        from grea.recovery.unity_bulk_freeze import freeze as freeze_unity

        return (
            freeze_unity(
                args.candidate,
                args.texture_cache,
                args.source_manifest,
                args.source_root,
                args.out,
                args.expected_manifest,
            ),
            0,
        )
    if args.command == "freeze-handoff":
        from grea.recovery.bulk_handoff import freeze

        return (
            freeze(
                args.candidate,
                args.native_contract,
                args.verification,
                args.out,
                args.expected_manifest,
                args.apply_owned,
            ),
            0,
        )
    if args.command == "export-unity-bulk":
        from grea.recovery.unity_bulk_prepare import export_prepared

        result = export_prepared(
            args.prepared, args.asset_ripper, args.out, args.budget_seconds, args.deadline_utc, args.window_end_utc
        )
        return (
            {
                k: result.get(k)
                for k in (
                    "status",
                    "stage",
                    "pid",
                    "processExited",
                    "exitCode",
                    "outputFiles",
                    "outputBytes",
                    "nativeAssetFiles",
                    "sourceUnchanged",
                    "error",
                )
            },
            0 if result["status"] == "exported_partial" else 1,
        )
    if args.command == "prepare-unity-bulk":
        from grea.recovery.unity_bulk_prepare import prepare as prepare_bulk

        result = prepare_bulk(
            args.inspection,
            args.texture_cache,
            args.capture,
            args.provider_python,
            args.out,
            args.budget_seconds,
            args.resume,
        )
        return (result, 0 if result["status"] == "prepared" else 1)
    if args.command == "handoff" and args.native_contract:
        from grea.recovery.cocos_native_contract import export as native_contract

        return (native_contract(args.candidate, args.out), 0)
    if args.command == "convert":
        if args.unity_system_fonts and (
            args.target not in ("unity", "unity6", UNITY_PROFILE)
            or args.source_family not in ("auto", "cocos")
            or args.source_profile not in (None, PROFILE)
            or args.recipe
            or args.resume
            or args.reuse_candidate
        ):
            usage_parser.error("--unity-system-fonts coretext requires a fresh Cocos bundle conversion to Unity")
        typed_requested = any(
            (
                args.code_source,
                args.module_contract,
                args.module_selectors,
                args.configuration_table,
                args.reuse_candidate,
                args.expected_candidate,
            )
        )
        typed_settings = None
        if typed_requested:
            if args.target not in ("unity", "unity6", UNITY_PROFILE) or not args.out:
                usage_parser.error("Typed package modules require --target unity6 and a fresh --out")
            if any(
                (
                    args.numeric_code_contract,
                    args.resume,
                    args.recipe,
                    args.asset_index,
                    args.all_assets,
                    args.bindings,
                    args.animation,
                    args.native,
                    args.remote_manifest,
                )
            ):
                usage_parser.error(
                    "Typed package modules use fresh local package/candidate assembly; numeric/slice/resume/native/remote flags cannot combine"
                )
            from grea.recovery.package_modules import settings as module_settings

            typed_settings = module_settings(
                args.code_source, args.module_contract, args.module_selectors, args.configuration_table
            )
            if args.reuse_candidate:
                if not args.expected_candidate or any(
                    (
                        args.source,
                        args.input_set,
                        args.reuse_source_stages,
                        args.layout,
                        args.namespace,
                        args.provider_python,
                        args.asset_ripper,
                        args.format,
                    )
                ):
                    usage_parser.error(
                        "Frozen candidate composition requires --expected-candidate and excludes fresh source/layout/provider options"
                    )
                from grea.recovery.package_modules import assemble

                result = assemble(args.reuse_candidate, args.expected_candidate, args.out, typed_settings)
                drafts = result.get("codeDrafts") or {}
                draft_summary = {k: v for k, v in drafts.items() if k != "files"}
                draft_summary["generatedFiles"] = len(drafts.get("files", []))
                return (
                    dict(
                        status=result["status"],
                        completed=result["completed"],
                        projects=result["projects"],
                        codeModules=result.get("codeModules"),
                        codeDrafts=draft_summary,
                        report=str(Path(args.out).resolve() / "conversion-result.json"),
                    ),
                    1,
                )
            if args.expected_candidate:
                usage_parser.error("--expected-candidate requires --reuse-candidate")
            if args.source_family not in ("auto", "cocos"):
                usage_parser.error(
                    "Fresh typed JS package conversion currently requires Cocos; use frozen Unity resources for other source routes"
                )
        if args.numeric_code_contract and any(
            (args.resume, args.recipe, args.reuse_source_stages, args.asset_index, args.bindings, args.animation)
        ):
            usage_parser.error("--numeric-code-contract requires fresh package source stages")
        if args.cocos_code_language != "ts" and (not args.numeric_code_contract):
            usage_parser.error("--cocos-code-language requires --numeric-code-contract")
        if args.format is not None and (args.resume or args.recipe):
            usage_parser.error(
                "--format requires a fresh package conversion; resume/recipe retain their declared contract"
            )
        generic_selection = None
        generic_family = (
            args.source_family
            if args.source_family in ("laya", "layaair", "egret", "eraget", "custom", "other")
            else None
        )
        if args.source_family == "auto" and args.source_profile in (
            "generic-image-resources-v1",
            "egret-custom-resource-plist-v1",
        ):
            generic_family = "egret" if args.source_profile == "egret-custom-resource-plist-v1" else "other"
        if args.input_set and args.source_family == "auto":
            from grea.recovery.inputs import input_set

            generic_selection = input_set(args.input_set)
            if generic_selection["sourceProfile"] == "generic-image-resources-v1":
                generic_family = "other"
            elif generic_selection["sourceProfile"] == "egret-custom-resource-plist-v1":
                generic_family = "egret"
        if generic_family:
            if args.unity_system_fonts:
                usage_parser.error("CoreText system fonts require a Cocos bundle")
            if typed_settings:
                usage_parser.error("Typed JS modules require a Cocos package or an explicit frozen resource candidate")
            if args.target not in ("unity", "unity6", UNITY_PROFILE):
                usage_parser.error("Non-Cocos sources target Unity 6 only")
            if not all((args.source or args.input_set, args.target, args.out)) or (args.source and args.input_set):
                usage_parser.error(
                    "Image-resource conversion requires --source or --input-set, --target unity6 and --out"
                )
            if args.source_profile and args.source_profile not in (
                "generic-image-resources-v1",
                "egret-custom-resource-plist-v1",
            ):
                usage_parser.error("Resource sources require a supported explicit resource profile")
            if unity_parse_limits or any(
                (
                    args.resume,
                    args.recipe,
                    args.reuse_source_stages,
                    args.numeric_code_contract,
                    args.provider_python,
                    args.asset_ripper,
                    args.unity_texture_cache,
                    args.unity_schema_manifest,
                    args.unity_dependency_manifest,
                    args.unity_quarantine_invalid_textures,
                    args.asset_index,
                    args.all_assets,
                    args.bindings,
                    args.animation,
                    args.dependency_source,
                    args.evidence_source,
                    args.cocos_code_language != "ts",
                    args.provider_budget_seconds != 600,
                )
            ):
                usage_parser.error(
                    "Initial generic image profile supports explicit local roots; source adapters, remote manifests and source code binding are pending"
                )
            if not args.remote_manifest and any(
                (args.remote_cache_root, args.acquisition_out, args.remote_budget_seconds != 900)
            ):
                usage_parser.error("Remote options require --remote-manifest")
            acquired = None
            remote_settings = None
            conversion_input_set = args.input_set
            if args.remote_manifest:
                if not args.input_set:
                    usage_parser.error("Egret remote acquisition requires an explicit --input-set")
                from grea.recovery.inputs import input_set

                generic_selection = generic_selection or input_set(args.input_set)
                if generic_selection["sourceProfile"] != "egret-custom-resource-plist-v1":
                    usage_parser.error(
                        "Generic family image acquisition is pending; remote resource roots require the reviewed Egret profile"
                    )
                from grea.recovery.acquisition import prepare

                acquisition_out = (
                    Path(args.acquisition_out).resolve()
                    if args.acquisition_out
                    else Path(args.out).resolve().with_name(Path(args.out).resolve().name + "-acquired")
                )
                remote_settings = prepare(
                    args.remote_manifest,
                    acquisition_out,
                    generic_selection,
                    args.remote_cache_root,
                    args.remote_budget_seconds,
                    [Path(args.out).resolve()],
                )
            if args.native and args.offline:
                usage_parser.error("--native cannot combine with --offline")
            if not args.native and any(
                (args.native_out, args.unity_editor, args.creator_editor, args.native_budget_seconds != 1200)
            ):
                usage_parser.error("native options require --native")
            settings = None
            if args.native:
                from grea.recovery.orchestration import options
                from grea.recovery.inputs import input_set

                generic_selection = generic_selection or (input_set(args.input_set) if args.input_set else None)
                roots = [r["path"] for r in generic_selection["inputs"]] if generic_selection else [args.source]
                if remote_settings:
                    roots.append(acquisition_out)
                settings = options(
                    args.out,
                    args.target,
                    args.native_out,
                    args.unity_editor,
                    args.creator_editor,
                    args.native_budget_seconds,
                    roots,
                )
            if remote_settings:
                from grea.recovery.acquisition import acquire

                acquired = acquire(remote_settings, args.offline)
                conversion_input_set = str(acquired["inputSet"])
            from grea.recovery.resource_package import convert as convert_images

            result = convert_images(
                args.source,
                args.target,
                args.out,
                args.namespace or "monkey-project",
                args.offline,
                conversion_input_set,
                args.format or "none",
                generic_family,
                args.source_profile,
            )
            if acquired:
                from grea.recovery.acquisition import attach

                attach(result, args.out, acquired)
            summary = dict(
                status=result["workflowStatus"],
                completed=result["completed"],
                resultKind=result["resultKind"],
                sourceFamily=result["sourceFamily"],
                sourceProfile=result["sourceProfile"],
                completionScope=result["completionScope"],
                sourceSpriteFrames=result["sourceSpriteFrames"],
                derivedFullImageFrames=result.get("derivedFullImageFrames", 0),
                sourceData=result.get("sourceData"),
                projects=result["projects"],
                diagnostics=result["diagnostics"],
                report=str(Path(args.out).resolve() / "conversion-result.json"),
            )
            if settings:
                from grea.recovery.orchestration import run

                summary["nativeExecution"] = run(result, settings)
            return (summary, 1)
        source_file = Path(args.source) if args.source else None
        unity_source = args.source_family == "unity"
        if args.source_family == "auto" and source_file and source_file.is_file():
            from grea.recovery.io import safe as safe_source
            from grea.recovery.sources.unity_serialized import container_kind

            with safe_source(source_file).open("rb") as stream:
                unity_source = container_kind(stream.read(16)) is not None
        if unity_source:
            if args.unity_system_fonts:
                usage_parser.error("CoreText system fonts require a Cocos bundle")
            if typed_settings:
                usage_parser.error("Reuse the frozen Unity resource candidate for source-bound module assembly")
            if args.numeric_code_contract or args.cocos_code_language != "ts":
                usage_parser.error("Numeric JS code contracts/language selection require Cocos package sources")
            if args.native and args.offline:
                usage_parser.error("--native cannot combine with --offline")
            if args.native and (not args.unity_editor or args.creator_editor):
                usage_parser.error("Unity source --native requires only --unity-editor")
            if not args.native and any(
                (args.native_out, args.unity_editor, args.creator_editor, args.native_budget_seconds != 1200)
            ):
                usage_parser.error("native options require --native")
            if args.target not in ("unity", "unity6", UNITY_PROFILE):
                usage_parser.error("Unity sources target Unity 6 only")
            if not all((args.source, args.out, args.provider_python, args.asset_ripper)):
                usage_parser.error("Unity source requires --source --out --provider-python --asset-ripper")
            if any(
                (
                    args.input_set,
                    args.resume,
                    args.recipe,
                    args.reuse_source_stages,
                    args.asset_index,
                    args.all_assets,
                    args.bindings,
                    args.animation,
                    args.evidence_source,
                    args.source_profile,
                    args.namespace,
                )
            ):
                usage_parser.error(
                    "Unity source profile accepts explicit bundle/dependency/texture inputs; input sets/slice options are not implemented"
                )
            if not args.remote_manifest and any(
                (args.remote_cache_root, args.acquisition_out, args.remote_budget_seconds != 900)
            ):
                usage_parser.error("remote options require --remote-manifest")
            if args.unity_dependency_manifest and args.dependency_source:
                usage_parser.error("Choose --unity-dependency-manifest or explicit --dependency-source")
            native_settings = None
            remote_settings = None
            acquired = None
            protected = []
            if args.native or args.remote_manifest:
                from grea.recovery.unity_acquisition import protected_inputs

                protected = protected_inputs(
                    args.source,
                    args.dependency_source,
                    args.unity_texture_cache,
                    args.unity_schema_manifest,
                    args.unity_dependency_manifest,
                    args.provider_python,
                    args.asset_ripper,
                )
            if args.remote_manifest:
                from grea.recovery.unity_acquisition import prepare
                from grea.recovery.io import safe

                if safe(args.out).exists():
                    usage_parser.error("Choose a fresh conversion output before acquisition")
                acquisition_out = safe(args.acquisition_out or str(args.out) + "-acquired")
                remote_settings = prepare(
                    args.source,
                    acquisition_out,
                    args.remote_manifest,
                    args.remote_cache_root,
                    args.remote_budget_seconds,
                    [*protected, safe(args.out)],
                )
                protected.extend([acquisition_out, remote_settings["manifest"]])
                if remote_settings["cache"]:
                    protected.append(remote_settings["cache"])
            if args.native:
                from grea.recovery.orchestration import options

                native_settings = options(
                    args.out,
                    args.target,
                    args.native_out,
                    args.unity_editor,
                    args.creator_editor,
                    args.native_budget_seconds,
                    protected,
                )
            inputs = dict(
                dependencies=args.dependency_source,
                texture_cache=args.unity_texture_cache,
                dependency_manifest=args.unity_dependency_manifest,
            )
            if remote_settings:
                from grea.recovery.acquisition import acquire
                from grea.recovery.unity_acquisition import merge

                acquired = acquire(remote_settings, args.offline)
                inputs = merge(
                    acquired, **{k: inputs[k] for k in ("texture_cache", "dependency_manifest", "dependencies")}
                )
            from grea.recovery.recover_unity import convert as convert_unity

            result = convert_unity(
                args.source,
                args.out,
                args.provider_python,
                args.asset_ripper,
                args.provider_budget_seconds,
                schema_manifest=args.unity_schema_manifest,
                quarantine_invalid_textures=args.unity_quarantine_invalid_textures,
                export_scope=args.unity_export_scope,
                code_evidence=args.unity_code_evidence,
                reuse_inspection=args.unity_reuse_inspection,
                prepared_textures=args.unity_prepared_textures,
                reuse_export=args.unity_reuse_provider_export,
                layout_path=args.layout,
                parse_limits=unity_parse_limits,
                **inputs,
            )
            if acquired:
                from grea.recovery.unity_acquisition import attach

                attach(result, args.out, acquired)
            if native_settings:
                from grea.recovery.unity_native import finish_conversion

                result = finish_conversion(result, native_settings, args.format or "none")
            return (
                dict(
                    status=result["status"],
                    completed=result["completed"],
                    resultKind=result["resultKind"],
                    sourceFamily="unity",
                    projects=result["projects"],
                    diagnostics=[
                        {k: d.get(k) for k in ("code", "references", "message")} for d in result["diagnostics"]
                    ],
                    nativeExecution=result.get("nativeExecution"),
                    remoteAcquisition=result.get("acquisition"),
                    format=result["format"],
                    report=str(Path(args.out).resolve() / "conversion-result.json"),
                ),
                1,
            )
        if (
            args.unity_export_scope != "reachable"
            or args.unity_code_evidence
            or args.unity_reuse_inspection
            or args.unity_prepared_textures
            or args.unity_reuse_provider_export
        ):
            usage_parser.error("Unity bulk export/code evidence require a Unity source")
        if (
            unity_parse_limits
            or args.provider_python
            or args.asset_ripper
            or args.unity_texture_cache
            or args.unity_schema_manifest
            or args.unity_dependency_manifest
            or args.unity_quarantine_invalid_textures
            or (args.provider_budget_seconds != 600)
        ):
            usage_parser.error("Unity provider options require a Unity source")
        from grea.recovery.convert import convert, resume, recipe

        if not args.remote_manifest and any(
            (args.remote_cache_root, args.acquisition_out, args.remote_budget_seconds != 900)
        ):
            usage_parser.error("remote options require --remote-manifest")
        if args.remote_manifest and (not args.input_set or args.resume):
            usage_parser.error("--remote-manifest requires a fresh conversion with explicit --input-set")
        if not args.native and any(
            (args.native_out, args.unity_editor, args.creator_editor, args.native_budget_seconds != 1200)
        ):
            usage_parser.error("native options require --native")
        if args.native and (args.offline or args.resume or args.recipe):
            usage_parser.error(
                "--native requires a fresh package conversion and cannot combine with --offline/--resume/--recipe"
            )
        if args.reuse_source_stages and (not args.input_set):
            usage_parser.error("--reuse-source-stages requires --input-set and fresh --out")
        if args.resume and args.input_set:
            if any(
                (
                    args.source,
                    args.target,
                    args.out,
                    args.recipe,
                    args.asset_index,
                    args.all_assets,
                    args.bindings,
                    args.dependency_source,
                    args.evidence_source,
                    args.animation,
                    args.source_profile,
                    args.namespace,
                    args.package,
                    args.reuse_source_stages,
                )
            ):
                usage_parser.error("package resume accepts --resume, --input-set and optional --offline only")
            from grea.recovery.package import resume_package

            result = resume_package(args.resume, args.input_set, args.offline, layout_path=args.layout)
            return (
                dict(
                    status=result["workflowStatus"],
                    resultKind=result["resultKind"],
                    completed=result["completed"],
                    projects=result["projects"],
                    report=str(Path(args.resume).resolve() / "conversion-result.json"),
                ),
                1,
            )
        source_path = Path(args.source) if args.source else None
        package_mode = (
            args.input_set
            or args.package
            or args.target in ("both", "unity6", "cocos38")
            or (
                source_path is not None
                and (
                    source_path.suffix.lower() in (".apk", ".wxapkg")
                    or (source_path.is_dir() and (not args.asset_index) and (not args.recipe))
                )
            )
        )
        if (args.numeric_code_contract or typed_settings) and (not package_mode):
            usage_parser.error("Source-bound code contracts require package conversion")
        if package_mode:
            if (
                not all((args.source or args.input_set, args.target, args.out))
                or (args.source and args.input_set)
                or any(
                    (
                        args.resume,
                        args.recipe,
                        args.asset_index,
                        args.dependency_source,
                        args.evidence_source,
                        args.bindings,
                        args.animation,
                        args.source_profile,
                    )
                )
            ):
                usage_parser.error("package conversion requires --source/--target/--out; slice options are unsupported")
            from grea.recovery.package import convert_package

            selection = None
            if args.input_set and (args.native or args.remote_manifest):
                from grea.recovery.inputs import input_set

                selection = input_set(args.input_set)
            acquired = None
            remote_settings = None
            acquisition_out = (
                Path(args.acquisition_out).resolve()
                if args.acquisition_out
                else Path(args.out).resolve().with_name(Path(args.out).resolve().name + "-acquired")
            )
            if args.remote_manifest:
                from grea.recovery.acquisition import prepare

                remote_settings = prepare(
                    args.remote_manifest,
                    acquisition_out,
                    selection,
                    args.remote_cache_root,
                    args.remote_budget_seconds,
                    [Path(args.out).resolve()],
                )
            native_settings = None
            if args.native:
                from grea.recovery.orchestration import options

                if args.input_set:
                    source_roots = [r["path"] for r in selection["inputs"]]
                else:
                    source_roots = [args.source]
                if remote_settings:
                    source_roots.append(acquisition_out)
                native_settings = options(
                    args.out,
                    args.target,
                    args.native_out,
                    args.unity_editor,
                    args.creator_editor,
                    args.native_budget_seconds,
                    source_roots,
                )
            conversion_input_set = args.input_set
            if remote_settings:
                from grea.recovery.acquisition import acquire

                acquired = acquire(remote_settings, args.offline)
                conversion_input_set = str(acquired["inputSet"])
                if args.reuse_source_stages and Path(conversion_input_set).resolve() != Path(args.input_set).resolve():
                    raise ValueError("New acquired files require fresh source stages; acquired evidence is preserved")
            result = convert_package(
                args.source,
                args.target,
                args.out,
                args.namespace or "monkey-project",
                args.offline,
                conversion_input_set,
                reuse_source_stages=args.reuse_source_stages,
                format_profile=args.format or "none",
                code_contract=args.numeric_code_contract,
                cocos_code_language=args.cocos_code_language,
                layout_path=args.layout,
                typed_modules=typed_settings,
                system_fonts=bool(args.unity_system_fonts),
            )
            if acquired:
                from grea.recovery.acquisition import attach

                attach(result, args.out, acquired)
            summary = dict(
                status=result["workflowStatus"],
                resultKind=result["resultKind"],
                completed=result["completed"],
                projects=result["projects"],
                format=result.get("format"),
                inputFiles=result["inputFiles"],
                inputBytes=result["inputBytes"],
                diagnostics=len(result["diagnostics"]),
                nextAction=result["nextAction"],
                report=str(Path(args.out).resolve() / "conversion-result.json"),
            )
            if acquired:
                summary["remoteAcquisition"] = dict(acquired["summary"], receipt=str(acquired["receipt"]))
            if native_settings:
                from grea.recovery.orchestration import run

                summary["nativeExecution"] = run(result, native_settings)
                if summary["nativeExecution"]["status"] != "not_run":
                    summary["nextAction"] = dict(
                        code="REVIEW_NATIVE_AND_SOURCE_GAPS",
                        message="Review native receipt; source/visual/business gaps remain separate",
                    )
            return (summary, 1)
        if args.format == "grea":
            usage_parser.error("--format grea requires a fresh package conversion")
        if args.native:
            usage_parser.error("--native requires package conversion (use --target unity6/cocos38/both or --package)")
        if args.resume:
            if any(
                (
                    args.source,
                    args.target,
                    args.out,
                    args.source_profile,
                    args.asset_index,
                    args.all_assets,
                    args.dependency_source,
                    args.evidence_source,
                    args.bindings,
                    args.animation,
                    args.offline,
                    args.recipe,
                    args.namespace,
                )
            ):
                usage_parser.error("--resume cannot be combined with conversion inputs")
            result = resume(args.resume)
        elif args.recipe:
            if not args.out or any(
                (
                    args.source,
                    args.target,
                    args.source_profile,
                    args.asset_index,
                    args.all_assets,
                    args.dependency_source,
                    args.evidence_source,
                    args.bindings,
                    args.animation,
                    args.namespace,
                )
            ):
                usage_parser.error("--recipe requires --out and cannot be combined with explicit input options")
            result = convert(output=args.out, offline=args.offline, **recipe(args.recipe))
        else:
            if not all((args.source, args.target, args.out)):
                usage_parser.error("convert requires --source, --target and --out (or --resume)")
            result = convert(
                args.source,
                args.target,
                args.out,
                args.namespace or "monkey-project",
                args.source_profile,
                args.asset_index,
                args.all_assets,
                args.dependency_source,
                args.evidence_source,
                args.bindings,
                args.animation,
                args.offline,
                system_fonts=bool(args.unity_system_fonts),
            )
        return (
            dict(
                status=result["workflowStatus"],
                resultKind=result["resultKind"],
                completed=result["completed"],
                project=result["project"],
                diagnostics=len(result["diagnostics"]),
                validation=result["validation"],
                nextAction=result["nextAction"],
                report=result.get("report") or str(Path(args.out).resolve() / "manifest.json"),
            ),
            2 if result["workflowStatus"] == "failed" else 1,
        )
    if args.command == "inspect":
        if args.source_profile == PROJECT_PROFILE:
            if args.dependency_source or args.evidence_source:
                usage_parser.error("Editable project does not accept bundle dependencies")
            result = inspect_project(args.source, args.asset_index, args.out)
        else:
            result = inspect(args.source, args.asset_index, args.out, args.dependency_source, args.evidence_source)
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
    if args.command == "catalog":
        result = catalog(args.source, args.out)
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
    if args.command == "normalize":
        result = normalize(args.manifest, args.out)
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
    if args.command == "plan":
        if args.target_profile == cocos.PROFILE:
            if (
                args.system_font_resolution
                or args.expected_system_font_resolution
                or args.static_font_generation
                or args.expected_static_font_generation
            ):
                usage_parser.error("Explicit TMP system-font resolution applies only to Unity")
            result = cocos.plan(
                args.ir,
                args.namespace,
                args.out,
                args.bindings,
                args.animation,
                spine_bindings=args.spine_bindings,
                expected_spine_bindings=args.expected_spine_bindings,
                spine_resources=args.spine_resources,
                static_source_bundle=args.static_source_bundle,
                expected_static_source_bundle=args.expected_static_source_bundle,
            )
        else:
            if args.spine_bindings or args.expected_spine_bindings or args.spine_resources:
                usage_parser.error(
                    "Spine component receipt currently requires Creator; Unity runtime binding is pending"
                )
            result = plan(
                args.ir,
                args.namespace,
                args.out,
                args.bindings,
                args.animation,
                system_font_resolution=args.system_font_resolution,
                expected_system_font_resolution=args.expected_system_font_resolution,
                static_font_generation=args.static_font_generation,
                expected_static_font_generation=args.expected_static_font_generation,
                static_source_bundle=args.static_source_bundle,
                expected_static_source_bundle=args.expected_static_source_bundle,
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
    if args.command == "diff":
        result = incremental.diff(args.before, args.after, args.out)
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
    if args.command == "export":
        from grea.recovery.targets.unity import dispatch_export

        result = dispatch_export(args.plan, args.out)
        output_path = Path(args.out).resolve()
        if output_path.is_relative_to(Path.cwd() / "outputs"):
            incremental.register(output_path, Path.cwd())
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
    if args.command == "preflight":
        from grea.recovery.preflight import preflight

        result = preflight(args.candidate, args.out, args.log, args.progress)
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
    if args.command == "verify":
        from grea.recovery.io import safe
        from grea.recovery.io import stage_manifest

        profile = stage_manifest(safe(args.candidate)).get("targetProfile")
        pins = (args.editor_readback_sha256, args.source_prefabs_readback_sha256)
        if any((p is not None for p in pins)):
            if profile != UNITY_PROFILE or args.level != "editor" or (not all(pins)):
                raise ValueError("Paired native receipt pins require Unity verify --level editor")
            result = verify(args.candidate, args.out, args.level, readback_pins=pins)
        else:
            result = (cocos.verify if profile == cocos.PROFILE else verify)(args.candidate, args.out, args.level)
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
    if args.command == "handoff":
        result = handoff(args.candidate, args.out)
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
