# Architecture module implementation workflow

`monkey.code_architecture_modules` implements one complete module from a finished global architecture stage. It consumes the accepted global stage in `.private/v060-architecture-first-20261027/GlobalArchitectureNN/`; it does not use Candidate07 draft filenames as implementation units and does not resume the earlier ProjectRun queue.

The public interface is:

```python
from monkey.code_architecture_modules import prepare, run, status

prepared = prepare(
    architecture_stage=".private/v060-architecture-first-20261027/GlobalArchitecture03",
    module_id="Recipe",
    output=".private/v060-architecture-first-20261027/RecipeModule01",
    dependency_roots=[".private/v060-architecture-first-20261027/AcceptedDomainModule"],
    previous_module=None,
)
result = run(".private/v060-architecture-first-20261027/RecipeModule01")
current = status(".private/v060-architecture-first-20261027/RecipeModule01")
```

`architecture_stage` must have `state.status == "architecture_designed"`, pinned `Evidence/source-catalog.json`, `architecture.json`, `validation.json`, `Evidence/architecture-contract.json`, and the worker-recorded `Task/workspace/Analysis/Architecture/architecture.json` payload whose SHA matches the Task revision record. The workflow revalidates class ownership and class paths against the source catalog. Optional state-level architecture/validation hashes are checked when available; this also supports the first completed stage created before those fields were added.

`prepare` selects exactly one existing module ID from the global `architecture.json`. It uses validated `validation.json.classPaths`, seeds every class path, and carries all declared source units and method/field source-member identities. To keep a large plan readable without dropping records, the module context `architecture.json` retains every global field except the full `classes` array; it contains `classCount` and a hash/size/count index of all class shards under `ArchitectureModules/`. Each shard contains full class records, with a hard 8 MiB shard limit and 64 MiB aggregate architecture-context limit. A class that cannot fit intact causes a named failure. Replacing the shard set with its indexed records reconstructs the original global class array exactly. Seed files contain comments only and are explicitly marked `NOT IMPLEMENTED`; they have no declarations or behavior and must never be treated as working code. The worker receives all class shards plus the focused module class seeds, the global contract and validation, exact complete source-unit fragments, source member indexes, the deduplicated union of selected classes’ `configPaths` and relevant integration chains’ `configPaths`, and the candidate-owned `Packages/manifest.json` and `ProjectSettings/ProjectVersion.txt`. These project files are checked against the frozen candidate manifest. Use block namespaces and ordinary C# syntax compatible with the pinned Unity version. Do not add dependencies or assume `Newtonsoft.Json` or `System.Text.Json`; avoid `JsonUtility` when it would lose dictionary or numeric-key structure, and report a parser gap if the pinned project has no evidenced compatible reader.

Dependency roots contain `architecture-module-manifest.json` plus its `.sha256` sidecar. A referenced class with `status="generated_unreviewed"` may be supplied only as explicitly unreviewed implementation context so module order and cycles do not deadlock. This module workflow has no review-acceptance API and rejects a hand-edited `accepted` status. Referenced classes without a generated implementation remain in `pendingImplementations`; the workflow passes their global type contract without fabricating a stub. A previous module revision must be pinned as `{"root": path, "manifestSha256": "..."}`. Its class files are rehashed before reuse.

`run` accepts a session ID only through the underlying worker's exact checkpoint rules. It checks global architecture/source pins, context bytes, worker workspace boundaries, exact changed paths, and every output byte before materializing it at its validated target path. A lexical C# pass strips comments and string/character literals before checking the planned block namespace, namespace-level type declaration, methods and fields. For Domain/Gameplay it also rejects UnityEngine/UnityEditor/MonoBehaviour/ScriptableObject references, `dynamic`, and only the untyped `Dictionary<string, object>` core shape; typed collections and tokens that occur only in comments or literals do not trigger these checks. Special seed headers match only the exact placeholder comment forms (or an implementation file with no code); `NotImplementedException` and actual TODO/FIXME markers are checked outside string literals. User-facing text such as “not implemented; unavailable” inside a string is not a seed marker. Any remaining seed marker or missing/forbidden declaration produces a partial classification; otherwise output remains `generated_unreviewed`. These are bounded source checks, not a C# parser or semantic validation. Model completion is not review acceptance, compilation, Unity binding, or runtime success; those stay `not_reviewed`/`not_run` in the versioned module manifest.

`recheck(output)` is a read-only classification refresh for a completed module task. It requires `Task/request.json` finalized, `Task/process.json` exited with code 0, and a valid complete/partial worker revision. It revalidates global pins, module context copies, the selected original source files, relevant JSON/mapping input bytes, worker actualChanges, workspace output bytes, and the existing module manifest. It returns `oldManifestSha256`, `taskManifestSha256`, per-file output SHA/bytes, prior/new classification and completeness diagnostics, plus source/context hashes. It does not write to the task, source, module manifest, state, or output files. Returned classifications are lexical metadata only; `semanticValidation` remains `not_performed`, and compilation/Editor/runtime acceptance are not implied.

The module prompt pins the existing resource-loading boundary: frozen assets live under `Assets/Game/Content/<Type>/<Module>/`, not `Resources`. Runtime code cannot use full project paths with `Resources.Load` or `AssetDatabase`; this workflow does not add Addressables or AB. Use typed serialized `Sprite`, `Prefab`, and `TextAsset` references injected through the planned catalog/Bootstrap/Services. JSON values remain in TextAssets and are parsed by the Player; do not duplicate editable numeric tables into ScriptableObjects. `ContentService.RootPath` is only a design hint, not evidence of a runtime loader. The asset context documents source prefab identities and any preview-only localIDs; unresolved source references remain partial until a typed native reference is actually connected and checked.

The manifest is named `architecture-module-manifest.json` to avoid colliding with a candidate assembler's root `manifest.json`. Each class row pins its class ID, target path, source-unit IDs, source-member IDs, type dependencies, and status. Each file row carries `path` (artifact-relative), `targetPath` (candidate-relative), `artifactPath`, SHA-256, byte count, class ID, source-unit IDs, source-member IDs, and status. The parent assembler can aggregate these rows into the owning candidate manifest after review.

Context, input, and output files are never silently truncated. A module with more than `worker.MAX_FILES` classes or an individual evidence file above worker limits fails with a named budget diagnostic and retains the complete global source evidence. This first implementation requires an explicit module split in the architecture plan rather than silently dropping classes.

Class-owned configuration context was corrected after an actual Audio module
reported missing payloads that existed in the frozen candidate. New `prepare`
calls include these payloads even when no representative integration chain
mentions them; catalog identity, full bytes, SHA and context budgets still
apply. Previously prepared/running modules keep their pinned input context and
are not rewritten by this change. A later explicit revision must consume the
omitted evidence before its implementations can be treated as connected.

If a fresh `prepare` fails after creating its output, the new directory is
moved intact to a sibling `<name>.prepare-failed-<id>/` with a
`prepare-failure.json` receipt. No model is invoked during preparation. This
retains failed input evidence while leaving the intended pipeline slot absent
for a later corrected prepare. The archive is not an executable/resumable task.
Directories that already existed before the call are rejected and never moved.

Integration tasks may receive `--supplemental-csharp-spec /absolute/native-inputs.json`: an explicit JSON array of `{ "path": "/absolute/NativeCoordinator.cs", "sha256": "..." }` entries. Preparation copies bounded UTF-8 C# inputs into immutable `SupplementalNative` context and records each hash/path and its native-design role. These implementations supply actual candidate APIs for Bootstrap and module integration; they never establish original-source ownership or trusted backend behavior. Context drift is rejected before the model runs, and original files are read-only. This avoids asking a later composition task to invent APIs for already completed native revisions.
