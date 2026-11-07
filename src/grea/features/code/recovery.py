"""Code recovery command declarations and orchestration.

Algorithms and transaction guards remain in grea.recovery.
"""

import zipfile
from grea.recovery.sources.compiled import fail
from pathlib import Path

ROUTES = {
    "static-code-bindings": None,
    "query-methods": "query-methods",
    "inventory-unity-methods": "inventory-unity-methods",
    "apply-unity-method-overlay": "apply-unity-method-overlay",
    "unity-field-plan": "unity-field-plan",
    "unity-code-model": "unity-code-model",
    "lower-cocos-local-methods": "lower-cocos-local-methods",
    "code-emit": "emit",
    "code-draft": "draft",
    "code-postprocess": "postprocess",
    "code-postprocess-resume": "postprocess-resume",
    "code-project-prepare": "project-prepare",
    "code-project-run": "project-run",
    "code-project-status": "project-status",
    "code-project-resume": "project-resume",
    "code-project-pause": "project-pause",
    "code-project-configure": "project-configure",
    "code-project-recheck": "project-recheck",
    "code-architecture-prepare": "architecture-prepare",
    "code-architecture-run": "architecture-run",
    "code-architecture-status": "architecture-status",
    "code-architecture-recheck": "architecture-recheck",
    "code-architecture-refine": "architecture-refine",
    "code-native-prepare": "native-prepare",
    "code-native-run": "native-run",
    "code-native-status": "native-status",
    "code-native-continue": "native-continue",
    "code-native-reassemble": "native-reassemble",
    "code-native-revise": "native-revise",
    "code-native-add-json": "native-add-json",
    "code-architecture-module-prepare": "architecture-module-prepare",
    "code-architecture-module-run": "architecture-module-run",
    "code-architecture-module-status": "architecture-module-status",
    "code-architecture-module-recheck": "architecture-module-recheck",
    "code-architecture-module-recover": "architecture-module-recover",
    "code-types": "types",
    "code-select": "select",
    "code-handoff": "handoff",
    "code-model": "model",
    "unity-code-source": "unity-code-source",
    "unity-code-candidate": "unity-code-candidate",
    "wasm-code-source": "wasm-code-source",
    "wasm-code-candidate": "wasm-code-candidate",
    "code-native-probe": "native-probe",
    "audit-native-code-dependencies": "audit-native-code-dependencies",
}


def register(sub, *, include_intake_plan=True):
    sub.add_parser(
        "static-code-bindings",
        help="Prepare source-proven inert MonoBehaviours, stage a fresh candidate, or audit static destinations; no gameplay acceptance",
    )
    p = sub.add_parser("query-methods", help="Inspect exact frozen evidence; no source program execution")
    p.add_argument("--source", required=True)
    p.add_argument("--member", help="Exact ZIP member; expected SHA identifies member bytes, not the outer ZIP")
    p.add_argument("--expected-sha", required=True)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--out", required=True)
    p.add_argument("--type", default="")
    p.add_argument("--method", default="")
    p.add_argument("--module")
    p.add_argument("--function", type=int)
    p = sub.add_parser("inventory-unity-methods", help="Classify recoverable WASM methods on selected source types")
    p.add_argument("--manifest", required=True)
    p.add_argument("--out", required=True)
    p.add_argument(
        "--include-body-bytes",
        action="store_true",
        help="Include exact identified WASM body bytes and source offsets for the selected remaining methods",
    )
    p.add_argument(
        "--exclude-overlay",
        action="append",
        default=[],
        help="Exclude exact method identities already listed in a prior overlay (repeatable)",
    )
    p = sub.add_parser(
        "apply-unity-method-overlay", help="Apply reviewed source-bound C# methods to existing Unity scripts"
    )
    p.add_argument("--project", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument(
        "--native-signatures",
        action="store_true",
        help="Emit exact overload expectations for the runtime host Editor checker",
    )
    p = sub.add_parser(
        "unity-field-plan",
        help="Validate frozen field semantics and exact source/target identities; never edits Unity assets",
    )
    for name in (
        "candidate",
        "trusted",
        "trusted-sha256",
        "bindings",
        "inventory",
        "inventory-sha256",
        "source",
        "metadata",
        "target-root",
        "out",
    ):
        p.add_argument("--" + name, required=True)
    p = sub.add_parser("unity-code-model", help="Recover named C# data fields from embedded Unity TypeTree evidence")
    p.add_argument("--inspection", required=True)
    p.add_argument("--out", required=True)
    p.add_argument(
        "--bulk",
        action="store_true",
        help="Alias repeated MonoScript only with exact raw bytes and proven field equality",
    )
    p = sub.add_parser(
        "lower-cocos-local-methods", help="Emit source-pinned C# bodies for reviewed local void member contracts"
    )
    p.add_argument("--source", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "code-emit",
        help="Emit source-bound typed C# modules or legacy numeric field methods; unknown methods stay excluded",
    )
    p.add_argument("--source", required=True)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--code-model")
    group.add_argument("--module-contract", help="Exact source/class/method SHA256 and explicit typed C# call domain")
    group.add_argument(
        "--module-profile",
        help="Explicit optional legacy extension profile; exact source identity required, never selected by default",
    )
    p.add_argument("--reuse-from")
    p.add_argument("--expected-manifest")
    p.add_argument(
        "--configuration-table",
        help="Explicit legacy project-extension configuration table; exact source/table identity required, original JSON remains runtime data",
    )
    p.add_argument("--namespace", default="monkey-project")
    p.add_argument(
        "--numeric-field",
        action="append",
        default=[],
        help="Explicit numeric call-subdomain contract; not a global JS type inference",
    )
    p.add_argument("--cocos-code-language", choices=["ts", "js"], default="ts")
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "code-draft",
        help="Export every available source method/function as best-effort C# drafts; type/syntax/API gaps do not gate export",
    )
    p.add_argument("--source", required=True)
    p.add_argument("--expected-source")
    p.add_argument("--out", required=True)
    p.add_argument("--reuse-from")
    p.add_argument("--expected-manifest")
    p = sub.add_parser(
        "code-postprocess",
        help="Explicit optional bounded Codex CLI pass over independent copies of selected generated C#",
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--expected-manifest", required=True)
    p.add_argument("--selected-path", action="append", required=True)
    p.add_argument("--task-file", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--evidence-root")
    p.add_argument("--evidence-file", action="append", default=[])
    p.add_argument("--codex", default="/opt/homebrew/bin/codex")
    p.add_argument("--budget-seconds", type=int, default=900)
    p.add_argument("--idle-seconds", type=int, default=180)
    p.add_argument("--prepare-only", action="store_true", help="Prepare workspace and probe CLI help; no model session")
    p = sub.add_parser(
        "code-postprocess-resume", help="Resume only the exact recorded Codex checkpoint session; never resume latest"
    )
    p.add_argument("--run", required=True)
    p.add_argument("--session", required=True)
    p = sub.add_parser(
        "code-project-prepare", help="Prepare an exact whole-candidate C# batch queue and independent complete project"
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--expected-manifest", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--batch-max-files", type=int, default=128)
    p.add_argument("--batch-code-bytes", type=int, default=512 * 1024)
    p.add_argument("--batch-seconds", type=int, default=3600)
    p.add_argument("--idle-seconds", type=int, default=900)
    p.add_argument("--attempts", type=int, default=2)
    p.add_argument("--codex", default="/opt/homebrew/bin/codex")
    for command in ("code-project-run", "code-project-status", "code-project-resume"):
        p = sub.add_parser(
            command, help="Run all ready batches, inspect durable progress, or resume exact project checkpoints"
        )
        p.add_argument("--run", required=True)
        if command == "code-project-resume":
            p.add_argument(
                "--retry-failed",
                action="store_true",
                help="Explicitly grant a new finite retry window to exhausted failed batches",
            )
    p = sub.add_parser(
        "code-project-pause", help="Request cooperative pause and preserve the active exact-session checkpoint"
    )
    p.add_argument("--run", required=True)
    p.add_argument(
        "--after-current-attempt",
        action="store_true",
        help="Let the current attempt finish before pausing; do not interrupt the active model",
    )
    p = sub.add_parser(
        "code-project-configure", help="Change finite batch budgets only while the supervisor and child are stopped"
    )
    p.add_argument("--run", required=True)
    p.add_argument("--batch-seconds", type=int, required=True)
    p.add_argument("--idle-seconds", type=int, required=True)
    p = sub.add_parser(
        "code-project-recheck", help="Revalidate completed saved reviews after validator fixes without a new model call"
    )
    p.add_argument("--run", required=True)
    p = sub.add_parser(
        "code-architecture-prepare",
        help="Prepare one whole-source native Unity architecture design with immutable evidence",
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--expected-manifest", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--namespace", default="Game")
    p.add_argument("--codex", default="/opt/homebrew/bin/codex")
    p.add_argument("--budget-seconds", type=int, default=3600)
    p.add_argument("--idle-seconds", type=int, default=900)
    p = sub.add_parser(
        "code-architecture-run",
        help="Run or precisely resume the architecture design task, then validate its executable generation contract",
    )
    p.add_argument("--run", required=True)
    p.add_argument("--session")
    p = sub.add_parser("code-architecture-status", help="Read architecture-stage status without running a model")
    p.add_argument("--run", required=True)
    p = sub.add_parser(
        "code-architecture-recheck",
        help="Revalidate a saved finalized architecture patch without another model invocation",
    )
    p.add_argument("--run", required=True)
    p = sub.add_parser(
        "code-architecture-refine", help="Prepare a bounded ownership repair over a previous architecture output"
    )
    p.add_argument("--run", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--codex", default="/opt/homebrew/bin/codex")
    p.add_argument("--budget-seconds", type=int, default=3600)
    p.add_argument("--idle-seconds", type=int, default=900)
    p = sub.add_parser(
        "code-native-prepare", help="Prepare all designed feature modules and one isolated five-layer candidate"
    )
    p.add_argument("--architecture", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--codex", default="/opt/homebrew/bin/codex")
    p.add_argument("--budget-seconds", type=int, default=3600)
    p.add_argument("--idle-seconds", type=int, default=900)
    p.add_argument(
        "--external-references-file",
        help="Explicit JSON layer-to-assembly reference map from verified installed packages",
    )
    p.add_argument(
        "--retained-support-path",
        action="append",
        default=[],
        help="Explicit existing native layout helper and paired meta path retained from the frozen candidate",
    )
    for command in ("code-native-run", "code-native-status"):
        p = sub.add_parser(
            command, help="Run ready modules serially through candidate assembly, or read durable progress"
        )
        p.add_argument("--run", required=True)
    p = sub.add_parser(
        "code-native-continue",
        help="Version a stopped module schedule, reusing pinned terminal outputs and prioritizing unfinished core modules",
    )
    p.add_argument("--run", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--priority", action="append", required=True)
    p.add_argument(
        "--stop-after", help="Natural module boundary for integration; a later run continues the remaining full scope"
    )
    p = sub.add_parser(
        "code-native-reassemble",
        help="Read-only reclassify terminal module outputs and assemble a fresh unvalidated candidate",
    )
    p.add_argument("--run", required=True)
    p.add_argument("--out", required=True)
    p.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Explicit stopped integration checkpoint; preserve all ungenerated classes as missing, never fabricate shells",
    )
    p = sub.add_parser(
        "code-native-revise", help="Apply a hash-pinned C# ownership revision to a fresh native candidate"
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--expected-manifest", required=True)
    p.add_argument("--revision", required=True)
    p.add_argument("--expected-revision", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "code-native-add-json",
        help="Add explicitly self-authored local-test JSON assets to a fresh owned native candidate",
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--expected-manifest", required=True)
    p.add_argument("--spec", required=True)
    p.add_argument("--expected-spec", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "code-architecture-module-prepare", help="Prepare one complete feature module from a designed architecture"
    )
    p.add_argument("--architecture", required=True)
    p.add_argument("--module", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--dependency", action="append", default=[])
    p.add_argument("--previous")
    p.add_argument("--expected-previous-manifest")
    p.add_argument(
        "--supplemental-csharp-spec",
        help="Explicit JSON list of read-only native integration source {path,sha256} pins; never original-source ownership",
    )
    p.add_argument("--codex", default="/opt/homebrew/bin/codex")
    p.add_argument("--budget-seconds", type=int, default=3600)
    p.add_argument("--idle-seconds", type=int, default=900)
    for command in (
        "code-architecture-module-run",
        "code-architecture-module-status",
        "code-architecture-module-recheck",
        "code-architecture-module-recover",
    ):
        p = sub.add_parser(command, help="Run or inspect one isolated source-bound module task")
        p.add_argument("--run", required=True)
        if command.endswith("-run"):
            p.add_argument("--session")
    p = sub.add_parser(
        "code-types",
        help="Extract only statically proven source types/dependencies and write named fillable evidence gaps",
    )
    p.add_argument("--source", required=True)
    p.add_argument("--selectors", required=True)
    p.add_argument("--type-evidence")
    p.add_argument("--namespace")
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "code-select",
        help="Select reviewed source methods, close typed dependencies and check actual lowering; no source execution",
    )
    p.add_argument("--source", required=True)
    p.add_argument("--selectors", required=True)
    p.add_argument("--out", required=True)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--type-evidence")
    group.add_argument("--module-profile")
    p = sub.add_parser(
        "code-handoff",
        help="Generate source-bound named drafts from a frozen Cocos candidate; optional additive owned-copy handoff",
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--expected-manifest")
    p.add_argument("--apply-owned", action="store_true")
    p.add_argument("--reuse-facts")
    p.add_argument("--expected-facts")
    p = sub.add_parser(
        "code-model", help="Inspect named methods and evidenced semantic candidates without executing JavaScript"
    )
    p.add_argument("--source", required=True)
    p.add_argument("--module-name")
    p.add_argument(
        "--lexical-graph",
        action="store_true",
        help="Complete-source lexical class/call evidence, not executable recovery",
    )
    p.add_argument("--expected-source")
    p.add_argument("--method-id", action="append", default=[])
    p.add_argument("--out", required=True)
    p.add_argument(
        "--bulk", action="store_true", help="Preserve ambiguous whole-file assignments as unsupported evidence"
    )
    p = sub.add_parser(
        "unity-code-source",
        help="Static Mono decompilation or source-bound IL2CPP metadata evidence; never execute original assembly",
    )
    p.add_argument("--source", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--expected-source", required=True)
    p.add_argument("--family", choices=["mono", "il2cpp-wasm"], default="mono")
    p.add_argument("--provider")
    p.add_argument("--metadata")
    p.add_argument("--method-map")
    p.add_argument("--expected-metadata")
    p.add_argument("--expected-method-map")
    p = sub.add_parser(
        "unity-code-candidate",
        help="Prepare exact static Mono C# drafts; closure is not IL-equivalence or Unity verification",
    )
    p.add_argument("--source-report", required=True)
    p.add_argument("--expected-report", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--method-id", action="append")
    p = sub.add_parser(
        "wasm-code-source",
        help="Verify exact decoded WASM code bodies and v29 metadata/map identities; never execute a module",
    )
    p.add_argument("--source", required=True)
    p.add_argument("--expected-source", required=True)
    p.add_argument("--metadata", required=True)
    p.add_argument("--expected-metadata", required=True)
    p.add_argument("--method-map", required=True)
    p.add_argument("--expected-method-map", required=True)
    p.add_argument("--decoded-segments", required=True)
    p.add_argument("--brotli-provider")
    p.add_argument("--method-id", action="append")
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "wasm-code-candidate",
        help="Lift supported exact WASM operators to isolated C# fragments; heap and unknown calls remain evidence",
    )
    p.add_argument("--source-report", action="append", required=True)
    p.add_argument("--expected-report", action="append", required=True)
    p.add_argument("--method", action="append", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser(
        "code-native-probe", help="Prepare the exact supported HealthState Unity6 probe; no Editor launch"
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--expected-manifest", required=True)
    p.add_argument("--out", required=True)
    p.add_argument(
        "--recipe-module",
        action="store_true",
        help="Also bind the exact source recipe JSON and recovered catalog in the independent probe",
    )
    p.add_argument(
        "--interactive",
        action="store_true",
        help="Prepare a fresh Editor pointer flow over the source-bound modules and original recipe JSON",
    )
    p = sub.add_parser(
        "audit-native-code-dependencies",
        help="Supplement a frozen selection with exact producer code proofs without changing its warnings",
    )
    p.add_argument("--candidate", required=True)
    p.add_argument("--expected-manifest", required=True)
    p.add_argument("--producer-candidate", required=True)
    p.add_argument("--expected-producer-manifest", required=True)
    p.add_argument("--out", required=True)


def dispatch(args, *, usage_parser):
    if args.command == "inventory-unity-methods":
        from grea.recovery.unity_method_overlay import inventory

        return (
            inventory(
                args.manifest,
                args.out,
                exclude_overlays=args.exclude_overlay,
                include_body_bytes=args.include_body_bytes,
            ),
            0,
        )
    if args.command == "apply-unity-method-overlay":
        from grea.recovery.unity_method_overlay import apply as apply_methods

        return (apply_methods(args.project, args.manifest, native_signatures=args.native_signatures), 0)
    if args.command == "query-methods":
        from grea.recovery.evidence_queries import query_methods

        try:
            result = query_methods(
                args.source,
                args.expected_sha,
                args.out,
                member=args.member,
                type_name=args.type,
                method=args.method,
                module=args.module,
                function=args.function,
                limit=args.limit,
            )
        except (zipfile.BadZipFile, EOFError) as error:
            fail("EVIDENCE_ARCHIVE", args.source or args.manifest, str(error))
        return (
            dict(status=result["status"], operation=result["operation"], report=str(args.out) + "/inspection.json"),
            0,
        )
    if args.command == "lower-cocos-local-methods":
        from grea.recovery.cocos_local_methods import export

        result = export(args.source, args.manifest, args.out)
        return (result, int(result["lowered"] != result["methods"]))
    if args.command == "code-emit":
        if args.module_contract or args.module_profile:
            if args.numeric_field or args.namespace != "monkey-project" or args.cocos_code_language != "ts":
                usage_parser.error(
                    "Module emission excludes legacy numeric/namespace/language flags; use the typed contract namespace"
                )
            from grea.recovery.code_modules import emit, emit_profile

            result = (emit_profile if args.module_profile else emit)(
                args.source,
                args.module_profile or args.module_contract,
                args.out,
                reuse_from=args.reuse_from,
                expected_manifest_sha256=args.expected_manifest,
                configuration_table=args.configuration_table,
            )
        else:
            if not args.numeric_field or args.reuse_from or args.expected_manifest or args.configuration_table:
                usage_parser.error(
                    "Legacy code emission requires --numeric-field and excludes module/configuration flags"
                )
            from grea.recovery.code_emit import emit

            result = emit(
                args.source, args.code_model, args.out, args.numeric_field, args.cocos_code_language, args.namespace
            )
        return (result, 1)
    if args.command == "code-draft":
        from grea.recovery.code_drafts import emit

        result = emit(
            args.source,
            args.out,
            expected_source_sha256=args.expected_source,
            reuse_from=args.reuse_from,
            expected_manifest_sha256=args.expected_manifest,
        )
        return (result, 1)
    if args.command == "code-native-add-json":
        from grea.recovery.code_architecture_resources import add_json_assets
        from grea.recovery.io import read, safe, sha

        result = add_json_assets(args.candidate, args.expected_manifest, args.spec, args.expected_spec, args.out)
        path = safe(args.out) / "manifest.json"
        return (
            dict(
                status="candidate_json_added_unvalidated",
                manifestPath=str(path),
                manifestSha256=sha(read(path, max_bytes=128 * 1024 * 1024)),
                fileCount=len(result["files"]),
                compileStatus=result["compileStatus"],
                runtimeStatus=result["runtimeStatus"],
            ),
            0,
        )
    if args.command == "code-native-revise":
        from grea.recovery.code_architecture_revision import revise_native_candidate
        from grea.recovery.io import read, safe, sha

        manifest = revise_native_candidate(
            args.candidate, args.expected_manifest, args.revision, args.expected_revision, args.out
        )
        path = safe(args.out) / "manifest.json"
        revision = manifest["architectureRevision"]
        return (
            dict(
                status="candidate_revised_unvalidated",
                implementationStatus=manifest["implementationStatus"],
                manifestPath=str(path),
                manifestSha256=sha(read(path, max_bytes=128 * 1024 * 1024)),
                fileCount=len(manifest["files"]),
                revisionId=revision["revisionId"],
                revisionPlanSha256=revision["revisionPlanSha256"],
                changedFileCount=len(revision["changes"]),
                compileStatus=manifest["compileStatus"],
                runtimeStatus=manifest["runtimeStatus"],
            ),
            0,
        )
    if args.command in (
        "code-native-prepare",
        "code-native-run",
        "code-native-status",
        "code-native-reassemble",
        "code-native-continue",
    ):
        from grea.recovery import code_architecture_pipeline as native

        if args.command == "code-native-prepare":
            from grea.recovery.io import load, read, safe

            references = (
                load(read(safe(args.external_references_file), max_bytes=1024 * 1024))
                if args.external_references_file
                else None
            )
            result = native.prepare(
                args.architecture,
                args.out,
                codex=args.codex,
                timeout_seconds=args.budget_seconds,
                idle_seconds=args.idle_seconds,
                external_references=references,
                retained_support_paths=args.retained_support_path,
            )
        elif args.command == "code-native-run":
            result = native.run(args.run)
        elif args.command == "code-native-continue":
            result = native.continue_run(args.run, args.out, args.priority, stop_after_module=args.stop_after)
        elif args.command == "code-native-reassemble":
            from grea.recovery.code_architecture_reassembly import reassemble

            result = reassemble(args.run, args.out, allow_incomplete=args.allow_incomplete)
        else:
            result = native.status(args.run)
        return (
            result,
            0
            if result["status"] in ("prepared", "candidate_assembled_unvalidated", "integration_checkpoint")
            or args.command == "code-native-status"
            else 1,
        )
    if args.command in (
        "code-architecture-module-prepare",
        "code-architecture-module-run",
        "code-architecture-module-status",
        "code-architecture-module-recheck",
        "code-architecture-module-recover",
    ):
        from grea.recovery import code_architecture_modules as module

        if args.command == "code-architecture-module-prepare":
            if bool(args.previous) != bool(args.expected_previous_manifest):
                raise ValueError("--previous and --expected-previous-manifest must be supplied together")
            previous = (
                dict(root=args.previous, manifestSha256=args.expected_previous_manifest) if args.previous else None
            )
            from grea.recovery.io import load, read, safe

            supplements = (
                load(read(safe(args.supplemental_csharp_spec), max_bytes=1024 * 1024))
                if args.supplemental_csharp_spec
                else []
            )
            result = module.prepare(
                args.architecture,
                args.module,
                args.out,
                dependency_roots=args.dependency,
                previous_module=previous,
                supplemental_sources=supplements,
                codex=args.codex,
                timeout_seconds=args.budget_seconds,
                idle_seconds=args.idle_seconds,
            )
        elif args.command == "code-architecture-module-run":
            result = module.run(args.run, session_id=args.session)
        elif args.command == "code-architecture-module-recheck":
            result = module.recheck(args.run)
        elif args.command == "code-architecture-module-recover":
            result = module.recover(args.run)
        else:
            result = module.status(args.run)
        return (
            result,
            0
            if result["status"] in ("prepared", "generated_unreviewed", "rechecked")
            or args.command == "code-architecture-module-status"
            else 1,
        )
    if args.command in (
        "code-architecture-prepare",
        "code-architecture-run",
        "code-architecture-status",
        "code-architecture-recheck",
        "code-architecture-refine",
    ):
        from grea.recovery import code_architecture as architecture

        if args.command == "code-architecture-prepare":
            result = architecture.prepare(
                args.candidate,
                args.expected_manifest,
                args.out,
                namespace=args.namespace,
                codex=args.codex,
                timeout_seconds=args.budget_seconds,
                idle_seconds=args.idle_seconds,
            )
        elif args.command == "code-architecture-run":
            result = architecture.run(args.run, session_id=args.session)
        elif args.command == "code-architecture-recheck":
            result = architecture.recheck(args.run)
        elif args.command == "code-architecture-refine":
            result = architecture.refine(
                args.run,
                args.out,
                codex=args.codex,
                timeout_seconds=args.budget_seconds,
                idle_seconds=args.idle_seconds,
            )
        else:
            result = architecture.status(args.run)
        return (
            result,
            0
            if result["status"] in ("prepared", "architecture_designed") or args.command == "code-architecture-status"
            else 1,
        )
    if args.command == "code-postprocess":
        from grea.recovery.code_postprocess import prepare, run
        from grea.recovery.io import safe, read

        task = read(safe(args.task_file), max_bytes=16000).decode("utf-8")
        prepared = prepare(
            args.candidate,
            args.selected_path,
            args.expected_manifest,
            args.out,
            task,
            evidence_root=args.evidence_root,
            evidence_files=args.evidence_file,
            codex=args.codex,
            timeout_seconds=args.budget_seconds,
            no_progress_seconds=args.idle_seconds,
        )
        if args.prepare_only:
            return (
                dict(
                    status="prepared",
                    request=str(prepared.manifest_path),
                    workspace=str(prepared.workspace),
                    modelStarted=False,
                ),
                0,
            )
        result = run(prepared)
        return (
            dict(
                status=result["status"],
                report=str(prepared.output / "manifest.json"),
                sessionId=result.get("sessionId"),
                changedFiles=len(result.get("actualChanges", [])),
                unresolved=len(result.get("unresolved", [])),
            ),
            0 if result["status"] == "complete" else 1,
        )
    if args.command == "code-postprocess-resume":
        from grea.recovery.code_postprocess import run

        result = run(args.run, session_id=args.session)
        return (
            dict(
                status=result["status"],
                report=str(Path(args.run) / "manifest.json"),
                sessionId=result.get("sessionId"),
                changedFiles=len(result.get("actualChanges", [])),
                unresolved=len(result.get("unresolved", [])),
            ),
            0 if result["status"] == "complete" else 1,
        )
    if args.command == "code-project-prepare":
        from grea.recovery.code_project_postprocess import prepare

        result = prepare(
            args.candidate,
            args.expected_manifest,
            args.out,
            max_files=args.batch_max_files,
            max_code_bytes=args.batch_code_bytes,
            batch_seconds=args.batch_seconds,
            idle_seconds=args.idle_seconds,
            max_attempts=args.attempts,
            codex=args.codex,
        )
        return (result, 0)
    if args.command in ("code-project-run", "code-project-status", "code-project-resume"):
        from grea.recovery import code_project_postprocess as project

        result = (
            project.status(args.run)
            if args.command == "code-project-status"
            else project.resume(args.run, retry_failed=args.retry_failed)
            if args.command == "code-project-resume"
            else project.run(args.run)
        )
        return (
            result,
            0
            if result["status"] in ("complete", "complete_with_partial") or args.command == "code-project-status"
            else 1,
        )
    if args.command in ("code-project-pause", "code-project-configure"):
        from grea.recovery import code_project_postprocess as project

        result = (
            project.request_pause(args.run, finish_current=args.after_current_attempt)
            if args.command == "code-project-pause"
            else project.configure(args.run, batch_seconds=args.batch_seconds, idle_seconds=args.idle_seconds)
        )
        return (result, 0)
    if args.command == "code-project-recheck":
        from grea.recovery.code_project_postprocess import recheck

        return (recheck(args.run), 0)
    if args.command == "code-types":
        from grea.recovery.code_type_evidence import extract_type_evidence
        from grea.recovery.io import load, read, safe, new_output, write_json

        source = safe(args.source)
        selectors = safe(args.selectors)
        evidence = safe(args.type_evidence) if args.type_evidence else None
        result = extract_type_evidence(
            source,
            load(read(selectors, max_bytes=64 * 1024)),
            load(read(evidence, max_bytes=128 * 1024)) if evidence else None,
            namespace=args.namespace if evidence else args.namespace or "Game.Domain.Recovered",
        )
        out = new_output(args.out, [source, selectors] + ([evidence] if evidence else []))
        write_json(out / "type-evidence.json", result)
        if result["status"] == "ready" and result.get("contract"):
            write_json(out / "module-contract.json", result["contract"])
        if result.get("fillableContract"):
            write_json(out / "missing-types.json", result["fillableContract"])
        return (
            dict(
                status=result["status"],
                report=str(out / "type-evidence.json"),
                contract=str(out / "module-contract.json")
                if result["status"] == "ready" and result.get("contract")
                else None,
                missing=str(out / "missing-types.json") if result.get("fillableContract") else None,
            ),
            0 if result["status"] == "ready" else 1,
        )
    if args.command == "code-select":
        from grea.recovery.code_selection import write_selection

        result = write_selection(
            args.source, args.selectors, args.out, type_evidence=args.type_evidence, module_profile=args.module_profile
        )
        return (result, 0 if result["status"] == "selected_ready" else 1)
    if args.command == "unity-code-source":
        from grea.recovery.unity_code_sources import inspect as inspect_code_source

        result = inspect_code_source(
            args.source,
            args.out,
            expected_sha256=args.expected_source,
            family=args.family,
            provider=args.provider,
            metadata=args.metadata,
            method_map=args.method_map,
            expected_metadata_sha256=args.expected_metadata,
            expected_method_map_sha256=args.expected_method_map,
        )
        return (result, 1)
    if args.command == "unity-code-candidate":
        from grea.recovery.unity_code_candidate import prepare_candidate

        return (
            prepare_candidate(
                args.source_report, args.out, expected_report_sha256=args.expected_report, method_ids=args.method_id
            ),
            1,
        )
    if args.command == "wasm-code-source":
        from grea.recovery.wasm_code_sources import inspect_wasm
        from grea.recovery.io import load, read, safe

        result = inspect_wasm(
            args.source,
            args.out,
            expected_source_sha256=args.expected_source,
            metadata=args.metadata,
            expected_metadata_sha256=args.expected_metadata,
            method_map=args.method_map,
            expected_method_map_sha256=args.expected_method_map,
            decoded_segments=load(read(safe(args.decoded_segments), max_bytes=1024 * 1024)),
            method_ids=args.method_id,
            brotli_provider=args.brotli_provider,
        )
        return (result, 1)
    if args.command == "wasm-code-candidate":
        if len(args.source_report) != len(args.expected_report):
            usage_parser.error("Supply one --expected-report SHA256 per source report, in the same order")
        from grea.recovery.wasm_code_semantics import recover_wasm_subset

        refs = [dict(report=p, expectedSha256=h) for p, h in zip(args.source_report, args.expected_report)]
        return (recover_wasm_subset(refs, args.out, selections=args.method), 1)
    if args.command == "code-native-probe":
        if args.interactive:
            from grea.recovery.code_interactive_probe import prepare

            result = prepare(args.candidate, args.expected_manifest, args.out)
        else:
            from grea.recovery.code_native_probe import prepare

            result = prepare(args.candidate, args.expected_manifest, args.out, recipe_module=args.recipe_module)
        return (result, 0)
    if args.command == "unity-field-plan":
        from grea.recovery.unity_field_plan import plan as unity_field_plan

        result = unity_field_plan(
            args.candidate,
            args.trusted,
            args.trusted_sha256,
            args.bindings,
            args.inventory,
            args.inventory_sha256,
            args.source,
            args.metadata,
            args.target_root,
            args.out,
        )
        return (result, 0 if result["writable"] else 1)
    if args.command == "unity-code-model":
        from grea.recovery.unity_code_model import model as unity_code_model

        return (unity_code_model(args.inspection, args.out, args.bulk), 1)
    if args.command == "code-handoff":
        from grea.recovery.cocos_code_handoff import enrich

        return (
            enrich(
                args.candidate,
                args.out,
                args.expected_manifest,
                args.apply_owned,
                args.reuse_facts,
                args.expected_facts,
            ),
            1,
        )
    if args.command == "code-model":
        if args.lexical_graph:
            if not args.expected_source or args.bulk:
                usage_parser.error("--lexical-graph requires --expected-source and excludes --bulk")
            from grea.recovery.code_graph import inspect as code_model

            result = code_model(args.source, args.out, args.expected_source, args.method_id)
        else:
            if not args.module_name or args.expected_source or args.method_id:
                usage_parser.error("Legacy code-model requires --module-name; graph flags require --lexical-graph")
            from grea.recovery.code_model import inspect as code_model

            result = code_model(args.source, args.out, args.module_name, bulk=args.bulk)
        return (result, 1)
    if args.command == "audit-native-code-dependencies":
        from grea.recovery.native_code_dependencies import audit

        result = audit(
            args.candidate, args.expected_manifest, args.producer_candidate, args.expected_producer_manifest, args.out
        )
        return (
            dict(
                status=result["status"],
                scripts=len(result["scripts"]),
                uncovered=result["uncovered"],
                report=str(Path(args.out) / "code-dependency-supplement.json"),
            ),
            0,
        )
    raise ValueError(f"Unknown recovery command: {args.command}")
