"""System recovery command declarations and orchestration.

Algorithms and transaction guards remain in grea.recovery.
"""

from grea.features.catalog import stage_modules
from grea.recovery import __version__
from grea.recovery.sources.bundle import PROFILE
from grea.recovery.sources.project import PROFILE as PROJECT_PROFILE
from grea.recovery.targets.unity import PROFILE as UNITY_PROFILE
from grea.recovery.byte_budgets import defaults as default_byte_budgets
from grea.recovery.targets import cocos

ROUTES = {
    "capabilities": "recovery-capabilities",
    "diagnose": "diagnose",
    "doctor": "recovery-doctor",
    "space-preview": "space-preview",
}


def register(sub, *, include_intake_plan=True):
    cap = sub.add_parser("capabilities")
    cap.add_argument("--json", action="store_true")
    p = sub.add_parser(
        "diagnose", help="Index existing recovery gaps with source identities, evidence hashes and next actions"
    )
    p.add_argument("--source", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--evidence", action="append", default=[])
    p.add_argument("--max-issues", type=int, default=2000)
    p.add_argument("--max-document-bytes", type=int, default=32 * 1024 * 1024)
    p = sub.add_parser("doctor", help="Read local dependency/editor metadata; no installation or Editor launch")
    p.add_argument("--out", required=True)
    p.add_argument("--unity-editor")
    p.add_argument("--creator-editor")
    p.add_argument("--provider-python")
    p = sub.add_parser("space-preview", help="Estimate retained data and reviewable Editor caches; never deletes files")
    p.add_argument("--root", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--protect", action="append", default=[])
    p.add_argument("--max-files", type=int, default=500000)


def dispatch(args, *, usage_parser):
    if args.command == "diagnose":
        from grea.recovery.diagnostics import diagnose

        result = diagnose(args.source, args.out, args.evidence, args.max_issues, args.max_document_bytes)
        return (result, 0 if result["status"] == "no_reported_gaps" else 1)
    if args.command == "doctor":
        from grea.recovery.operations import doctor

        result = doctor(args.out, args.unity_editor, args.creator_editor, args.provider_python)
        return (result, 0 if result["status"] == "ready_for_checked_scope" else 1)
    if args.command == "space-preview":
        from grea.recovery.operations import space_preview

        result = space_preview(args.root, args.out, args.protect, args.max_files)
        return (result, 0 if result["status"] == "preview" else 1)
    if args.command == "capabilities":
        from grea.recovery.output_limits import policy
        from grea.recovery.code_profiles import profile_capabilities

        legacy_profile_capabilities = profile_capabilities()
        return (
            dict(
                version=__version__,
                byteBudgets=default_byte_budgets(),
                profiles=[
                    PROFILE,
                    PROJECT_PROFILE,
                    "cocos-2.4.11-bundle",
                    "cocos-3.8.7-bundle",
                    "cocos-3.4.1-bundle",
                    "cocos-2.1.2-resource",
                    "generic-image-resources-v1",
                    "egret-custom-resource-plist-v1",
                ],
                targetProfiles=[UNITY_PROFILE, cocos.PROFILE],
                activeTargetProfiles=[UNITY_PROFILE],
                pausedCompatibilityTargetProfiles=[cocos.PROFILE],
                ownership=dict(product="GREA", recoveryCommand="grea recover", developmentCommand="grea develop"),
                unityPrefabRecovery=dict(
                    command="recover-unity-prefabs",
                    requestContract="monkey-unity-prefab-recovery-request/1",
                    scope="selected-source-roots-and-provider-GUID-closure",
                    nativeCommand="verify-unity-prefabs",
                    native="implemented-acceptance-pending",
                    sourceCodeExecuted=False,
                ),
                nativeSdkDeclarations=dict(
                    command="audit-native-code-dependencies",
                    contract="monkey-native-sdk-declaration/1",
                    schemaVersion=1,
                    coverage="manifest-pinned-Spine-stage-and-literal-script-reference-tuples",
                    assemblyInspectionOwner="grea develop",
                    migration="not-performed",
                ),
                codeRecovery=dict(
                    status="partial",
                    sourceExecution=False,
                    lexicalGraph="complete-source-static-binding-and-utf8-spans",
                    typedModules="explicit-source-class-method-hashes-and-call-domain",
                    moduleProfiles=legacy_profile_capabilities["profiles"],
                    moduleProfileExtensions=legacy_profile_capabilities["extensions"],
                    selection="optional-strict-typed-dependency-closure-and-lowering",
                    methods="default-full-source-best-effort-CSharp-bodies;unknown-fragments-retained",
                    fullDrafts=dict(
                        commands=["code-draft", "convert"],
                        typeContractRequired=False,
                        sourceMethods="all-indexed-plus-auxiliary-functions",
                        fields="known-class-or-unresolved-owner-binding",
                        diagnostics="source-linked-bounded-shards",
                        compilation="excluded;syntax-and-API-errors-allowed",
                    ),
                    projectPostprocess=dict(
                        commands=[
                            "code-project-prepare",
                            "code-project-run",
                            "code-project-status",
                            "code-project-resume",
                            "code-project-pause",
                            "code-project-configure",
                            "code-project-recheck",
                        ],
                        scope="all-manifest-owned-CSharp-files",
                        execution="single-CLI-continuous-batches;per-batch-limits;exact-session",
                        status="legacy-file-repair;active-run-superseded",
                    ),
                    nativeArchitecture=dict(
                        commands=[
                            "code-architecture-prepare",
                            "code-architecture-run",
                            "code-architecture-status",
                            "code-architecture-recheck",
                            "code-architecture-refine",
                            "code-native-prepare",
                            "code-native-run",
                            "code-native-status",
                            "code-native-continue",
                            "code-native-reassemble",
                            "code-native-revise",
                            "code-native-add-json",
                            "code-architecture-module-prepare",
                            "code-architecture-module-run",
                            "code-architecture-module-status",
                            "code-architecture-module-recheck",
                            "code-architecture-module-recover",
                        ],
                        scope="complete-frozen-source-modules-members-and-resources",
                        layers=["Bootstrap", "Domain", "Gameplay", "Presentation", "Services"],
                        execution="single-existing-Codex-CLI;versioned-source-and-target-ownership",
                        status="architecture-design-stage-available;native-implementation-in-progress",
                    ),
                    optionalPostprocess=dict(
                        commands=["code-postprocess", "code-postprocess-resume"],
                        defaultEnabled=False,
                        provider="existing-local-Codex-CLI",
                        workspace="independent-selected-code-copy",
                        sourceCandidate="immutable",
                        budgets="total-idle-output",
                        resume="exact-recorded-session-only",
                    ),
                    packageComposition="exact-frozen-resource-reuse;one-manifest-with-Scene-Prefab-JSON-and-CSharp",
                    incremental="owned-candidate-fingerprints-and-hash-verified-reuse",
                    mono="static-decompiler-drafts;legal-fixture-target-compiled",
                    il2cpp="v29-exact-WASM-body-evidence;8-pure-i64-operator-fragments;caller-map-assumption;stateful-bodies-not-lifted",
                    native="separate-probe-required;not-implied-by-emission",
                ),
                recoveryOperations=dict(
                    commands=["acquire-resources", "diagnose", "doctor", "space-preview", "resource-probe"],
                    resume="same-manifest-and-input-set; completed-partial-receipt-to-fresh-layer; rehash-selected-payloads",
                    retries="1..3; transient-network-or-408-429-5xx-only; fixed-byte-time-budgets",
                    diagnostics="selected-existing-evidence; no source parsing or target-byte validation implied",
                    space="metadata-preview-only; no deletion",
                    spine="creator-3.8.8/standard-3.8-native-reference-page-time-and-pose-representatives",
                    shader="exact-cocos-2.4.15-builtin-2d-sprite-macro-profile",
                ),
                evidenceInspection=dict(
                    commands=["query-methods", "query-tables", "inspect-aliases"],
                    inputs=["strict-streamed-json-array", "manifest-hashed-table-zip", "exact-url-content-alias-index"],
                    sourceExecution=False,
                    metadataIsMethodBody=False,
                    hashVerification="complete-selected-source; outer-ZIP-not-implied",
                    maxSourceBytes=536870912,
                    maxRowBytes=8388608,
                    maxResults=1000,
                ),
                projectOperations=dict(
                    status="integrated",
                    owner="GREA",
                    command="grea develop",
                    discovery="grea develop capabilities",
                    legacyCommands=["adopt", "adopt-recover", "register", "apply"],
                    creatorNative="unsupported",
                ),
                outputPolicy=dict(
                    wholeInput=policy({"scopeMode": "whole-input"}),
                    selection=policy({}),
                    hashChunkBytes=1048576,
                    sourceDecoderBudgets="independent",
                ),
                additionalPackageProfiles={
                    "cocos-3.4.1-bundle": dict(
                        scope="version-proven-node-ui-prefab-and-resource-subset",
                        graphs="856-of-857-source-graphs;22503-nodes;52-instances;one-null-quaternion-rejected",
                        native="5-source-frames-plus-6-prefabs-331-nodes-8-instances-7-mounted-nodes-1-mounted-widget-both-targets-verified",
                        operations=["package-convert"],
                    ),
                    "egret-custom-resource-plist-v1": dict(
                        scope="reviewed-custom-resource-manifest-plist-binjson-v2",
                        targets=["unity6"],
                        sourceSkins="typed-data-only-native-layout-pending",
                        remoteAcquisition="explicit-manifest-cache-and-bounded-fetch",
                        native="132-source-frames-verified; expanded-atlas-set-pending",
                        operations=["package-convert"],
                    ),
                    "cocos-2.1.2-resource": dict(
                        scope="version-proven-resource-subset",
                        native="211-source-frames-both-targets-verified",
                        graphs="pending",
                        operations=["package-convert"],
                    ),
                    "generic-image-resources-v1": dict(
                        scope="derived-original-image-gallery-only",
                        families=["laya", "layaair", "egret", "eraget", "custom", "other"],
                        targets=["unity6"],
                        native="Egret-16-derived-images-verified",
                        sourceGraphs="not-restored",
                        operations=["package-convert"],
                    ),
                    "cocos-2.4.11-bundle": dict(
                        scope="version-proven-published-bundle-subset",
                        native="91-source-graphs-both-targets-verified",
                        operations=["package-convert"],
                    ),
                    "cocos-3.8.7-bundle": dict(
                        scope="version-proven-node-ui-template-and-resource-subset",
                        native="83-static-graphs-plus-4-prefab-5-native-relations-and-16-node-dynamic-ui-representatives-both-targets-verified",
                        graphs="114-root-closures-static;5-graphs-missing-6-exact-templates;not-all-native-validated",
                        operations=["package-convert"],
                    ),
                },
                toolkit=dict(
                    contract="grea-toolkit/1",
                    runner="grea recover tool <id>",
                    tools=list(__import__("grea.features", fromlist=["RECOVERY_TOOLS"]).RECOVERY_TOOLS),
                ),
                schemaVersion=1,
                dynamicUi=dict(
                    probeVersion=2,
                    verifiedLayoutGroups=6,
                    verifiedLayoutStates=54,
                    native="historical-v02-grid-scale-constraints-child-resize-and-linear-scale-representatives",
                    timing="Editor-native-forced-update;Player-not_run",
                    unityFlowReplacement=dict(
                        status="verified-subset",
                        sourcePrefabs=48,
                        sourceComponents=63,
                        aggregateAssets=50,
                        representatives=6,
                        scope="horizontal-flexible-unscaled-uniform-grid-or-proven-single-row",
                        otherLayouts="review-required;no-source-flow-runtime-fallback",
                        sourceText="questionnaire-Label-not-recovered;Rect-resize-only",
                    ),
                ),
                formatting=dict(
                    implemented=["unity-creator-unimported-owned-grea-v1", "fresh-package-convert-none-grea"],
                    pending=["unity-general-scene-native-format", "unity-source-positive-native-move-sample"],
                    rejected=["materialized-native-assets-require-a-future-native-move-adapter"],
                ),
                unitySourceProfile=dict(
                    inspectionPolicy=dict(
                        defaultObjectValues=250000,
                        defaultContainerValues=8000000,
                        maxObjectValues=1000000,
                        maxContainerValues=16000000,
                        maxDepth=96,
                        streamedFields=["Font.m_FontData", "AssetBundle.m_PreloadTable"],
                        chunkElements=8192,
                        maxPayloadBytes=268435456,
                    ),
                    name="unityfs-unitypy-1.25.3-assetripper-2.0.0",
                    status="partial",
                    inputs="explicit-unity-bundle-or-webdata-files-and-exact-local-texture-cache",
                    additionalContainers=["UnityWebData1.0"],
                    invalidTexturePolicy="block-default-explicit-quarantine-retains-original",
                    dependencyClosure="explicit-frozen-pool-exact-serialized-file-closure",
                    editor="one-prefab-schema-reference-save-reload-verified",
                    publicNative=True,
                    nativeProfile="unity-leaf-prefab-sprite-array-v1",
                    textureHydration=dict(
                        selectionManifest="unity-texture-selection/1",
                        scopes=["container", "selected-texture-set"],
                        cachePaths="exact-frozen-literal-bucket-and-token-filename",
                        partialDerivative=True,
                        partialExitCode=1,
                        selectedPngExport="unity-selected-texture-export/1",
                    ),
                    shaderHandoff="monkey-shader-handoff/1",
                    nativeFormatting="typed-resource-moves-with-dynamic-path-pins; real sample pinned all 134 assets",
                    methodsRecovered=0,
                ),
                implemented=sorted((name for module in stage_modules("recovery") for name in module.ROUTES)),
                planned=[],
                targetValidation={
                    UNITY_PROFILE: dict(
                        static="implemented", editor="representative-subset-verified", visual="not_run"
                    ),
                    cocos.PROFILE: dict(
                        static="implemented", editor="representative-subset-verified", visual="not_run"
                    ),
                },
                compiledFormats=["compiled-v1", "pack-v1", "texture-pack-v1"],
                containerFormats=["plain-wxapkg", "APK-ZIP", "Cocos-resource-directory"],
                packageWorkflow=dict(
                    fileAccounting="implemented",
                    staticModuleRecovery="partial",
                    codeDrafts="default-full-source-actual-CSharp-drafts-with-source-linked-sharded-diagnostics",
                    nativeObjectRecovery="shared-ir-supported-subset",
                    packageResume="hash-checked",
                    inputSets="explicit-local-roots",
                    editorOrchestration="manifest-bound-native-import-command",
                    remoteAcquisition="explicit-manifest-bounded-fetch",
                    cocosCodeLanguages=["ts", "js"],
                    defaultCocosCodeLanguage="ts",
                    numericCodeContracts=["numeric-call-subdomain-v1", "static-number-methods-v1"],
                    staticNumericScope="reviewed-Creator3-descriptor-helper-and-lexical-dependency; no component binding",
                ),
                imageFormats=["PNG", "JPEG", "ASTC (optional pinned decoder)"],
                animationSchemaVersion=1,
                animationSubset=[
                    "local-position",
                    "local-scale",
                    "opacity",
                    "linear",
                    "constant-step",
                    "Normal",
                    "Loop",
                ],
                animationEvents="manual-contract-only",
                targetEditorValidation="representative-subsets-only",
            ),
            0,
        )
    raise ValueError(f"Unknown recovery command: {args.command}")
