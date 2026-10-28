# Build resource filter (plan-only)

`beaver.build_filter.collect(project, spec_path, output, editor, timeout=600)` invokes the shared guarded Unity collector and validates its read-only receipt. `beaver.build_filter.plan(project, target, snapshot, source_manifest, backup_root, quarantine_root)` creates a deterministic static classification and reversible isolation plan. It never writes the project, copies backups, moves assets, deletes assets, builds a player, or claims that a source file compiles.

The Unity companion `BeaverBuildFilter.Collect(target, pipeline, buildScenes, explicitRoots)` reads the active `Assets` catalog and computes dependencies with `AssetDatabase.GetDependencies(root, true)` for every enabled build scene and explicit root. It reads each path through both `AssetDatabase.LoadMainAssetAtPath` and `LoadAllAssetsAtPath`, deduplicating Unity objects with object equality; this preserves `SceneAsset` roots whose main object is not returned by `LoadAllAssetsAtPath`, without using instance IDs as asset identities. It reports persistent asset GUIDs, local file IDs, object types, and the roots that reach each dependency. It verifies `EditorUserBuildSettings.activeBuildTarget` against the requested target, requires the requested enabled-scene list to exactly match `EditorBuildSettings.scenes`, and compares the requested pipeline identity with the current Editor pipeline. It also adds all assets under `Resources/`, `StreamingAssets/`, and `PlayerSettings.GetPreloadedAssets()` as implicit roots. Preloaded assets without an active `Assets/` mapping become explicit coverage blockers. The one temporary owned helper root, `Assets/BeaverReadbackTools/`, is excluded from the catalog while the runner executes; no other path is ignored. The collector has no mutation calls.

## Snapshot schema

The native collector writes a UTF-8 JSON object:

```json
{
  "schemaVersion": 1,
  "target": "StandaloneWindows64",
  "pipeline": "Example.RenderPipeline.Asset|0123456789abcdef0123456789abcdef",
  "buildScenes": ["Assets/Game/Main.unity"],
  "explicitRoots": ["Assets/Game/BuildRoots/AddressablesRoot.asset"],
  "implicitRoots": ["implicit:Resources", "implicit:PreloadedAssets"],
  "coverage": {"complete":true,"blockers":[]},
  "inputState": {
    "Assets/Game/Main.unity":{"sha256":"...","bytes":42},
    "Assets/Game/Main.unity.meta":{"sha256":"...","bytes":123},
    "ProjectSettings/EditorBuildSettings.asset":{"sha256":"...","bytes":321}
  },
  "assets": [
    {"path":"Assets/Game/mesh.bin","guid":"0123456789abcdef0123456789abcdef","localIds":[1001],"types":["UnityEngine.Mesh"]}
  ],
  "dependencies": [
    {"path":"Assets/Game/mesh.bin","guid":"0123456789abcdef0123456789abcdef","localId":1001,"type":"UnityEngine.Mesh","roots":["Assets/Game/Main.unity"]}
  ]
}
```

`assets` is the actual current non-folder `Assets/` catalog from `AssetDatabase`, excluding only the collector's owned helper root; it is not a caller-supplied list. Each asset's source file and adjacent `.meta` must exist as ordinary files. `inputState` contains SHA-256 and byte-count preconditions for every catalog asset and `.meta`, plus all source files under `Packages/` and `ProjectSettings/`; the main developer's runner captures this state. Before planning, Python recomputes every recorded hash and compares the current `Assets/` file set with the native catalog. An unimported filesystem file becomes a coverage blocker, and a changed or removed tracked input rejects the stale snapshot. Missing `EditorBuildSettings.asset`, `GraphicsSettings.asset`, or `QualitySettings.asset` is recorded as a coverage blocker rather than a successful assumption. Every dependency must match the catalog GUID, local ID, and type. Missing, malformed, duplicate, or mismatched identity blocks the plan. Build target, enabled build scenes, and pipeline must exactly match the request and the current Editor. `coverage.complete` and `coverage.blockers` make unmapped preloaded assets explicit. Unity packages, dynamic loading, reflection, addressable catalogs not supplied as explicit roots, custom build callbacks, and other runtime behavior are not inferred as absent; static snapshot completeness does not prove these consumers do not exist.

The collection spec is a UTF-8 JSON object with exact fields `schemaVersion`, `platform`, `renderPipeline`, `assets`, and `roots`. `assets` is the complete enabled build-scene path list. `roots` is a list of additional explicit build roots. Each list is bounded at 256 entries; at least one scene or root is required. `collect()` only accepts a report after the shared runner confirms Editor exit 0, unchanged input assets, no unplanned project changes, and temporary helper cleanup.

## Monkey handoff input

The current adapter accepts a strict `monkey-shader-handoff/1` envelope with an `items` array. Each item requires `path`, `bytes`, `sha256`, `classification`, `nativeCompilation`, and `runtimeDisposition`; `source`, `target`, `dialect`, `platformEvidence`, and `evidenceId` are optional. `target`, when provided, is exactly `{ "guid": "...", "localFileID": 123 }` and must map to the native catalog identity. An absent or `unmapped` target cannot establish source evidence. `path`, `bytes`, and `sha256` describe the file at that Unity asset path; both byte count and hash are checked against current bytes. The adapter retains these source labels:

| monkey classification | build-filter source class | Meaning |
| --- | --- | --- |
| `source-text` | `source` | Provenance only; source text is not compiler evidence. |
| `platform-compiled`, `recovered-binary` | `binary` | Preserve as binary evidence; do not treat as compilable source. |
| `unknown`, `unsupported` | `unknown` | Preserve without inference. |

For matching, `nativeCompilation` must be `not_run`, `runtimeDisposition` must be one of `source-review`, `evidence-only`, or `blocked`, the `sha256` and byte count must match current target asset bytes, and target GUID/localFileID must match the exact native catalog identity. Extension, name, claimed dialect, `nativeCompilation=not_run`, and an unmapped original `source` path never prove compilation. A modified or incorrectly mapped item becomes `unknown`.

## Classification and plan fields

Assets appearing in the native dependency snapshot are `runtime-referenced`; the plan retains them. A non-referenced asset with matching `source-text`, `platform-compiled`, or `recovered-binary` provenance is `source-evidence-only`, retaining the corresponding `source` or `binary` source classification. The plan still blocks isolation because dynamic/reflection use has not been ruled out. Everything else is `unknown` and retained. In particular, absence from a build dependency list does not prove absence from runtime use.

Each asset row contains its normalized `path`, source and `.meta` hashes, GUID/localIDs/types, source classification, exact dependency roots and objects, and a `reason`. `backup.copySourceTo` / `copyMetaTo` and `isolation.moveSourceTo` / `moveMetaTo` are exact project-relative destinations outside `Assets/`; the backup identity hashes and source GUID/local IDs are included. `rollback` names the exact quarantine source and `.meta` paths to restore and the original destinations. Paths preserve the original relative layout; GUID folders prevent backup collisions across assets.

The output remains `mode: "plan-only"` and `execution.status: "blocked"`. Incomplete coverage uses `BUILD_FILTER_DEPENDENCY_COVERAGE_INCOMPLETE`; otherwise `BUILD_FILTER_RETIREMENT_SCOPE_REQUIRED` requires a separately reviewed `unity plan` with operation `assets.retire`. That existing transaction now supports verified outside-Assets before-images, explicit protected roots and per-key retirement declarations, native dependency refusal, saved/reopened deletion checkpoints and guarded recovery. Classification alone grants no retirement authority; never execute the descriptive isolation paths with filesystem moves. See [retirement](RETIREMENT.md).

## CLI contract

```text
beaver build-filter collect --project <Unity-project> --spec <collect-request.json> \
  --out <fresh-snapshot-directory> --editor-path <Unity-executable> [--timeout 600]
beaver build-filter plan --project <Unity-project> --snapshot <build-snapshot.json> \
  --sources <monkey-shader-handoff.json> --target <target.json> --out <fresh-plan-directory>
```

`--target` is a JSON file path, for example `{"platform":"StandaloneOSX","pipeline":"BuiltIn"}`. Collection uses the explicit request file described above; platform, pipeline, scene and root flags are not separate CLI options. `--out` is always a fresh directory, not an existing JSON filename.

The runner request fields are `schemaVersion`, `platform`, `renderPipeline`, `assets` (enabled build scenes), and `roots` (additional explicit roots). The native job also carries `projectRoot`, `stage`, and `reportName`. The native entry is `BeaverBuildFilter.Run`; it decodes the standard `BEAVER_NATIVE_JOB_BASE64`, writes the report name inside the owned stage, and exits nonzero on collection failure. The command is registered through the shared `run_collector`.

## Fixture coverage

`tests/test_build_filter.py` uses synthetic Unity-style metadata only. It covers a build dependency, hash-matched source evidence, an unknown asset, a false/modified source claim, pipeline and identity mismatch, path traversal, and duplicate native dependencies. It contains no game material or real project identifiers.

`implicit-build-included` distinguishes Unity Resources/StreamingAssets/preloaded inclusion from explicit scene/root references. It does not establish current business dynamic use. Counts expose implicitBuildIncluded separately; implicit assets remain retained until explicit scoped retirement is reviewed and native guards pass.
