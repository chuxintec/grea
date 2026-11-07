"""System development command declarations and orchestration.

Algorithms and transaction guards remain in grea.development.
"""

import importlib.util
import shutil
import sys
from grea.development import __version__

ROUTES = {
    "version": "version",
    "capabilities": "development-capabilities",
    "doctor": "development-doctor",
    "diagnostics": "diagnostics",
}


def register(sub, *, include_intake_plan=True):
    sub.add_parser("version")
    sub.add_parser("capabilities")
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--editor-path")
    diagnostic = sub.add_parser("diagnostics").add_subparsers(dest="action", required=True).add_parser("summarize")
    diagnostic.add_argument("--input", action="append", required=True)
    diagnostic.add_argument("--out", required=True)
    diagnostic.add_argument("--limit", type=int, default=100)


def capabilities():
    capabilities = [
        dict(
            id="workspace.plan/apply/inspect/rebind",
            state="implemented",
            effects="explicit-project-local-binding",
            verification="content-pinned tool/engine/authority, reviewed writes and relocation",
        ),
        dict(
            id="toolkit.grea",
            state="implemented",
            effects="explicit-output-write",
            tools=list(__import__("grea.features", fromlist=["DEVELOPMENT_TOOLS"]).DEVELOPMENT_TOOLS),
            verification="fixed toolkit from commit 6791ddf; original outputs and exit codes retained",
        ),
        dict(
            id="ui.inspect/analyze/repair-plan",
            state="requires_provider",
            provider="Unity 6000.6.2f1 uGUI/TMP for collection",
            effects="read-temporary-helper-and-report",
            verification="native geometry/compiled fields; static, runtime and caller-supplied provenance separated",
        ),
        dict(
            id="wiring.plan",
            state="implemented",
            effects="plan-output",
            verification="compiled types and exact identities; ambiguous targets blocked; existing batch apply required",
        ),
        dict(
            id="diagnostics.summarize",
            state="implemented",
            effects="read-and-report",
            verification="bounded evidence and explicit execution state; never replays writes",
        ),
        dict(
            id="structure.inspect/plan",
            state="implemented",
            effects="read-and-plan-output",
            verification="static consumers plus exact native identity; migration uses existing batch transactions",
        ),
        dict(
            id="build-filter.collect/plan",
            state="requires_provider",
            provider="matching Unity Editor and active target/pipeline",
            effects="read-temporary-helper-and-report",
            verification="native dependency snapshot and hash-bound provenance; optional persistent GUID/localID/type/name pairs; no automatic deletion or shader replacement",
        ),
        dict(
            id="native.readback",
            state="requires_provider",
            provider="matching Unity Editor; graphics for capture",
            effects="read-temporary-helper-and-report",
            verification="SerializedObject and persistent IDs; owned preview capture; no gameplay or visual acceptance",
        ),
        dict(
            id="production.plan/apply/recover",
            state="requires_provider",
            provider="Unity 6000.6.2f1 + explicit project profile",
            effects="declared-resource-config-code-writes",
            verification="schema3; native apply/reopen/recover verified on private fixtures; formal consumer evidence is project-specific",
        ),
        dict(
            id="config3.validate/generate/compare",
            state="implemented",
            effects="read-and-create-only-generated-code",
            verification="strict shared schema; actual C# and Go JSON readers; caller must run generated consumer",
        ),
        dict(
            id="csharp.inspect/rename/rename-sequence",
            state="requires_provider",
            provider="matching Unity Bee context + .NET Roslyn SDK",
            effects="read-and-create-only-source-candidates",
            verification="ordered semantic rename, analyzers/generators, exact final fileEdits; dynamic unknowns block",
        ),
        dict(
            id="csharp.module",
            state="implemented",
            effects="create-only-module-candidate",
            verification="owned five-layer templates and strict flat JSON reader; no existing assembly mutation",
        ),
        dict(
            id="csharp.rewrite-prepare/rewrite-plan/rewrite-apply/rewrite-recover",
            state="requires_provider",
            provider="exact local Roslyn SDK; Unity 6000.6.2f1 for apply/recover",
            effects="bounded-agent-workspace-reviewed-script-patches-and-native-transaction",
            verification="source/API pins, exact write scope, real compile, unchanged GUID/type/schema/event signatures; behavior requires owner acceptance",
        ),
        dict(
            id="resource.image-inspect/image-produce/validate-step",
            state="implemented",
            effects="read-and-create-only-image-variants",
            verification="closed resource contracts; Pillow required for image operations; native resource execution remains provider-bound",
        ),
        dict(
            id="server.generate/module-generate/module-plan/protocol-diff/migration-plan",
            state="implemented",
            effects="create-only-go-candidate-and-plans",
            verification="six roles, explicit ownership, same JSON schema; no production deploy or payment success",
        ),
        dict(
            id="server.toolchain/protocol-tools/check/build",
            state="requires_provider",
            provider="Go + protoc + pinned Go plugins",
            effects="local-toolchain-build-output",
            verification="actual compiler/protocol generation and atomic candidate binaries; no global install",
        ),
        dict(
            id="server.compose-plan/migration-state/migration-apply/runtime-inspect",
            state="requires_provider",
            provider="explicit owned Docker Compose target + MySQL + Redis",
            effects="plan-or-explicit-owner-schema-mutation",
            verification="candidate/compose/container/network/volume identity and current schema SHA; partial or unknown execution requires inspection",
        ),
        dict(
            id="batch.plan",
            state="implemented",
            effects="plan-output",
            verification="scoped hashes, dependency/compilation inputs; cache is not authority",
        ),
        dict(
            id="batch.apply",
            state="requires_provider",
            provider="Unity 6000.6.2f1 + project uGUI/TMP",
            effects="declared-project-write",
            verification="one Editor process; native checkpoint and serialized save/reload checks",
        ),
        dict(
            id="batch.recover",
            state="requires_provider",
            provider="producer pinned by the transaction + Unity 6000.6.2f1",
            effects="hash-owned-restore",
            verification="exact witnessed after state required; later edits and missing checkpoints block",
        ),
        dict(
            id="references",
            state="implemented",
            effects="read-and-index-output",
            verification="static GUID graph, literal spans, unknown dynamic keys; incremental cache",
        ),
        dict(
            id="debug.start",
            state="implemented",
            effects="owned-budgeted-process",
            verification="fixed candidate manifest; existing asynchronous worker; optional closed observation-root and UTC deadline",
        ),
        dict(
            id="debug.inspect",
            state="implemented",
            effects="read",
            verification="PID/executable/start/marker identity; unknown probes remain partial",
        ),
        dict(
            id="debug.target",
            state="implemented",
            effects="read",
            verification="pinned Editor/PlayMode transaction evidence; no external attachment",
        ),
        dict(
            id="debug.stop",
            state="implemented",
            effects="own-worker-stop-request",
            verification="worker Popen child ownership; no arbitrary PID signals",
        ),
        dict(id="debug.tail", state="implemented", effects="read", verification="bounded redacted own session log"),
        dict(
            id="debug.screenshot",
            state="implemented",
            effects="evidence-registration",
            verification="caller supplied hash only; screenshot origin not authenticated",
        ),
        dict(id="project.inspect", state="implemented", effects="read", verification="python"),
        dict(
            id="adoption.plan",
            state="implemented",
            effects="plan-output",
            engines=["unity-6000.6.2f1", "creator-3.8.8"],
            verification="python; large isolated Unity manifest preview",
        ),
        dict(
            id="adoption.apply",
            state="requires_provider",
            provider="Unity 6000.6.2f1",
            effects="project-write",
            verification="native add/move/save/reopen and interrupted-import fixture",
        ),
        dict(
            id="adoption.finalize",
            state="requires_provider",
            provider="Unity 6000.6.2f1",
            effects="project-write",
            verification="same-helper independent reopen and frozen payload/state checks",
        ),
        dict(
            id="adoption.rollback",
            state="requires_provider",
            provider="Unity 6000.6.2f1",
            effects="project-write",
            verification="native normal/failed transaction restore; later-edit rejection",
        ),
        dict(
            id="intake.plan/apply/rollback",
            state="requires_provider",
            provider="Unity 6000.6.2f1 for native phases",
            effects="create-only-reviewed-assets-and-guarded-owned-removal",
            verification="independent contract; exact before-state, explicit retained scripts, declared native fields; no existing adoption baseline override",
        ),
        dict(
            id="intake.package-requirements/spec-bindings-classify",
            state="requires_provider",
            provider="explicit installed Editor files, local .NET SDK and reused immutable readback only",
            effects="new local specs/owned exact-byte selections; formal target read-only",
            verification="requested/resolved pins, script-only semantic batches, complete native resource evidence and six-binding continuation; native/source/product gates retained",
        ),
        dict(
            id="intake.bindings-plan/prepare-bindings/export-bindings/spec-bindings",
            state="requires_provider",
            provider="Unity 6000.6.2f1 for preparation only; export continuation reuses exact original native gates",
            effects="new-isolated-source-copy-or-export; retained target read-only",
            verification="byte-identical script pins; native full comparison/cold reopen; exact original producer and identical helper required to continue export; no adoption claim",
        ),
        dict(
            id="unity.plan",
            state="implemented",
            effects="plan-output",
            verification="python; exact source and implementation identity",
        ),
        dict(
            id="unity.ui.create",
            state="requires_provider",
            provider="Unity 6000.6.2f1 + uGUI/TMP Essentials + explicit font",
            effects="project-write",
            verification="native save/reopen/source audit",
        ),
        dict(
            id="unity.prefab.inspect",
            state="requires_provider",
            provider="Unity 6000.6.2f1",
            effects="temporary-editor-helper",
            verification="native hierarchy/localID/component/importer readback",
        ),
        dict(
            id="unity.prefab.edit",
            state="requires_provider",
            provider="Unity 6000.6.2f1",
            effects="project-write",
            verification="native text/component/Sprite binding save/reopen",
        ),
        dict(
            id="unity.assets.move",
            state="requires_provider",
            provider="Unity 6000.6.2f1",
            effects="project-write",
            verification="native GUID/localID and save/reopen",
        ),
        dict(
            id="unity.assets.retire/recover",
            state="requires_provider",
            provider="Unity 6000.6.2f1 + explicit protected roots and retirement declarations",
            effects="verified-archive-and-active-asset-retirement-or-guarded-restoration",
            verification="existing Unity transaction; native dependency protection, exact before-images and deletion checkpoint; explicit empty leaf folders require real DefaultAsset identity and guarded directory restoration",
        ),
        dict(
            id="unity.project.import",
            state="requires_provider",
            provider="Unity 6000.6.2f1",
            effects="declared-meta-initialization",
            verification="native generated C# compile and import",
        ),
        dict(
            id="unity.sprite.configure",
            state="requires_provider",
            provider="Unity 6000.6.2f1",
            effects="selected-importer-meta",
            verification="native importer/GUID/localID and save/reopen",
        ),
        dict(
            id="unity.validate.play",
            state="requires_provider",
            provider="Unity 6000.6.2f1",
            effects="bounded-playmode",
            verification="3-second isolated scene; zero runtime errors",
        ),
        dict(
            id="unity.build.macos",
            state="requires_provider",
            provider="Unity 6000.6.2f1 + Mac module",
            effects="create-only-artifact",
            verification="native BuildPipeline; unchanged source; artifact manifest",
        ),
        dict(
            id="player.run",
            state="implemented",
            effects="bounded-owned-process",
            verification="hash-bound macOS artifact launch; application verdict remains separate",
        ),
        dict(
            id="qa.prepare",
            state="implemented",
            effects="verified-bundle-copy-and-owned-test-data",
            verification="explicit artifact and input hashes; stable named test profile; preparation does not launch Player",
        ),
        dict(
            id="qa.launch",
            state="requires_provider",
            provider="macOS GUI session and explicitly prepared runtime",
            effects="owned-player-and-controlled-test-data",
            verification="bounded owned GUI process; optional restrictive Documents denial; actual access and save-resume require consumer evidence",
        ),
        dict(
            id="qa.collect",
            state="implemented",
            effects="owned-run-evidence-report",
            verification="exact project/build/profile/run identities; process and artifact evidence; no inferred gameplay or TCC verdict",
        ),
        dict(
            id="qa.inspect-instance",
            state="implemented",
            effects="read-owned-run; fresh-output-only",
            verification="kernel birth/executable/argv/profile binding; no app launch or GUI input",
        ),
        dict(
            id="qa.virtual-prepare",
            state="implemented",
            effects="private-local-test-channel-config",
            verification="explicit development companion only; credentials excluded from reports; no launch",
        ),
        dict(
            id="qa.virtual-bind",
            state="requires_provider",
            provider="macOS Unity6000.6.2f1/InputSystem1.20.1 explicit development companion",
            effects="owned-application-internal-virtual-device-only",
            verification="neutral real Player click/drag/scroll/idle/disconnect/stop verified; natural human parallel and formal consumer separate; no native fallback",
        ),
        dict(
            id="qa.virtual-input",
            state="requires_provider",
            provider="macOS Unity6000.6.2f1/InputSystem1.20.1 explicit development companion",
            effects="owned-application-internal-virtual-device-only",
            verification="neutral real Player click/drag/scroll/idle/disconnect/stop verified; natural human parallel and formal consumer separate; no native fallback",
        ),
        dict(
            id="qa.virtual-status",
            state="requires_provider",
            provider="macOS Unity6000.6.2f1/InputSystem1.20.1 explicit development companion",
            effects="owned-application-internal-virtual-device-only",
            verification="neutral real Player click/drag/scroll/idle/disconnect/stop verified; natural human parallel and formal consumer separate; no native fallback",
        ),
        dict(
            id="qa.virtual-stop",
            state="requires_provider",
            provider="macOS Unity6000.6.2f1/InputSystem1.20.1 explicit development companion",
            effects="owned-application-internal-virtual-device-only",
            verification="neutral real Player click/drag/scroll/idle/disconnect/stop verified; natural human parallel and formal consumer separate; no native fallback",
        ),
        dict(
            id="qa.bind",
            state="requires_provider",
            provider="macOS native AX with existing permissions and a strongly owned running run",
            effects="attach-only-session-output",
            verification="exact PID/birth/Bundle/run/profile/window-owner; no fallback launch",
        ),
        dict(
            id="qa.input",
            state="requires_provider",
            provider="hash-bound current native AX/PID session and existing permissions",
            effects="explicit guarded PID-directed input; opt-in owned-window system-cursor positioning; window-only observation/capture",
            verification="per-event identity/window guards; event posting is not atomic or business acceptance",
        ),
        dict(
            id="image.inspect",
            state="requires_provider",
            provider="Pillow",
            effects="read",
            verification="exact RGBA/alpha fixture",
        ),
        dict(
            id="image.compress",
            state="requires_provider",
            provider="Pillow",
            effects="create-only",
            verification="lossless PNG stream and exact decoded RGBA",
        ),
        dict(
            id="config.validate",
            state="implemented",
            effects="read",
            verification="strict scalar JSON; native runtime rejects missing/wrong-type fields",
        ),
        dict(
            id="config.generate",
            state="implemented",
            effects="create-only",
            verification="generated C# compiled; runtime TextAsset JSON reader",
        ),
        dict(
            id="code.inspect",
            state="implemented",
            effects="read",
            verification="static asmdef/using inventory; unresolved optional constraints remain partial",
        ),
        dict(
            id="payload.verify",
            state="implemented",
            effects="read",
            verification="shared file/alias/inode/collision checks; also used by build and Player",
        ),
        dict(
            id="payload.plan",
            state="implemented",
            effects="plan-output",
            verification="explicit source/override identities and alias redirection",
        ),
        dict(
            id="payload.apply",
            state="implemented",
            effects="new-independent-payload",
            verification="macOS independent-copy and atomic no-replace fixtures; Linux/Windows promotion not_run",
        ),
        dict(
            id="creator.apply",
            state="not_supported",
            effects="none",
            verification="explicit rejection before provider lookup",
        ),
        dict(id="creator.build", state="not_supported", effects="none", verification="not_run"),
    ]
    return dict(
        contract="grea-development-capabilities/1",
        capabilities=capabilities,
        requiredProviders=[],
        nativeOperationContract="beaver-unity/1",
        batchOperationContract="beaver-batch/2",
        batchTransactionContract="beaver-batch-transaction/2",
        adoptionContract="beaver-adopt/1",
        additiveIntakeContract="beaver-additive-intake/5",
        additiveIntakeSpecVersions=[1, 2, 3, 4, 5],
        intakeBindingPreparationContract="beaver-intake-bindings/1",
        productionOperationContract="beaver-production/3",
        productionTransactionContract="beaver-production-transaction/3",
        projectProfileContract="beaver-project/1",
        limitations=[
            "Provider readiness is not Editor connection or gameplay",
            "Native tests cover Unity 6000.6.2f1 only",
            "Source recovery is available through grea recover",
            "No global install, release, account/service/savegame writes",
            "Native receipts do not prove physical input, visual parity or game business acceptance",
        ],
    )


def dispatch(a):
    if a.command == "diagnostics":
        from grea.development.diagnostics import summarize

        result = summarize(a.input, a.out, a.limit)
        report = result.get("report", result)
        return dict(
            status="partial"
            if report.get("status") in ("unknown", "execution_unknown", "postexecution_outer_schema_rejection")
            else report.get("status"),
            diagnosticReport=report,
            report=result.get("path"),
        )
    if a.command == "version":
        return dict(version=__version__)
    if a.command == "capabilities":
        return capabilities()
    if a.command == "doctor":
        from grea.development.io import safe

        editor = safe(a.editor_path) if a.editor_path else None
        return dict(
            python=sys.version.split()[0],
            unityCLI=shutil.which("unity"),
            pillow="available" if importlib.util.find_spec("PIL") else "not_available",
            editor=dict(path=str(editor) if editor else None, present=editor.is_file() if editor else False),
            nativeConnection="not_probed",
            autoInstall=False,
        )
    raise ValueError(f"Unknown development command: {a.command}")
