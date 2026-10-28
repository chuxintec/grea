# Unity structure audit and move-plan contract

`beaver.structure_audit` provides read-only path inspection and explicit move declarations for the existing native asset-move batch. It does not move, rename, delete, rewrite consumers, or create project files. The registered structure inspect/plan commands bind these functions without a second transaction executor.

## Python interface

```python
from beaver.structure_audit import inspect, build_plan

audit = inspect(project_path, native_snapshot=None, exceptions=None,
                product_root=None, profile_path=None)
plan = build_plan(audit, [{"source": "Assets/Old/Item.png",
                           "target": "Assets/Game/Content/Images/UI/Item.png"}],
                  native_snapshot=native_snapshot)
```

`inspect(project, native_snapshot=None, exceptions=None, product_root=None, profile_path=None)` returns `beaver-structure-audit/1`. It lists canonical roots and case collisions, hashes assets within a fixed budget, and reports nonstandard/retired roots, missing standard config/docs, static path consumers, GUID dependencies, Resources keys, scene inventory/build entries, and unresolved dynamic loads. Existing `references.inspect_graph` supplies supported GUID and exact C# literal-load evidence. Static scans do not prove reflection, generated strings, package source, Addressables catalog state, or runtime behavior.

`product_root` and `profile_path` are optional paired arguments. When supplied, both are required; the profile must be inside the product root, and its relative `paths.unityProject` must resolve exactly to `project`. Profile symlinks, path escape, malformed minimum binding fields, and a mismatch fail closed. The reader checks `schemaVersion: 1` and `paths.unityProject` only; it does not claim to validate the full upstream GREA schema.

When both are omitted, discovery checks only `<Unity root>/grea-project.json` and its immediate parent’s `grea-project.json`. Each candidate is accepted only when its `paths.unityProject` binds back to the selected Unity root. It never searches farther upward. No valid match yields explicit `PRODUCT_ROOT_UNLOCATED`, `PROFILE_MISSING`, and unlocated structure-doc findings; plans without a binding are blocked.

The report includes `productRoot`, `profileIdentity` (`path`, SHA256, `unityProject`, and schema version), and `structureDocumentationIdentity` for the bound product root’s `Docs/PROJECT-STRUCTURE.md`. That document is read in place; it is not copied into the Unity project. `governanceFiles` records presence and SHA256 for the selected profile, structure document, and checked default profile candidates. `build_plan` rechecks these records, so profile/document edits, additions, or deletions make the plan stale. Unity asset `scannedInputPaths` remain relative to the Unity root and do not include product-root governance paths.

## Native readback input

Pass the full report from the existing `beaver.native_readback.inspect` operation. The structure module accepts and preserves additional caller supplied fields and provenance; it does not flatten the real report to a reduced schema. Relevant fields include:

```json
{
  "schemaVersion": 1,
  "contract": "beaver-native-readback/1",
  "assets": [{
    "path": "Assets/Old/Item.png", "importedType": "Texture2D",
    "objects": [{"path":"Assets/Old/Item.png", "guid":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "type":"Sprite", "name":"Item", "state":"persistent", "localId":2800000}]
  }],
  "inputState": {"Assets/Old/Item.png":{"sha256":"..."}, "Assets/Old/Item.png.meta":{"sha256":"..."}},
  "editorExitCode": 0, "sourceUnchanged": true,
  "nativeReadback": "read_only_native_snapshot"
}
```

The full report must show a successful Editor exit, read-only source guard, cleaned helper, and no unplanned changes. Current source and `.meta` SHA256 values must match both the audit inventory and readback `inputState`; stale snapshots block planning. Every imported object's path/GUID/type/name/state/localId is retained. Missing or nonpersistent identities and inconsistent GUIDs block a move. A canonical `nativeSnapshotSha256` records the supplied report identity in the plan; this digest is not a signature or authentication proof. The module reports observations from the caller supplied readback and does not query the Editor independently.

## Exceptions

`exceptions` is a separate explicit object with `schemaVersion: 1` and an `exceptions` list. Each exception has exactly `path`, `ruleId`, `scope` (`path` or `subtree`), `reason`, `alternativeConstraint`, `validation`, `owner`, and `reviewTrigger`. Matching requires all of path, scope, and the finding's rule ID; one rule never exempts other findings at that path. Exceptions suppress no underlying facts; findings stay visible with their exception rule ID. This input is not read from or converted from `grea-project.json` 1.0.0, whose exception fields differ.

Neutral example: `{"schemaVersion":1,"exceptions":[{"path":"Assets/Plugins/NativeBridge","ruleId":"STR-02","scope":"subtree","reason":"Platform plugin import requires this layout","alternativeConstraint":"Only registered supplier plugin files may live here","validation":"Project plugin inventory and native import receipt","owner":"Project maintainer","reviewTrigger":"Supplier version or target platform changes"}]}`.

## Move plan

`build_plan(audit, mappings, native_snapshot=None)` accepts 1–256 mappings, matching the existing batch move limit. It returns `beaver-structure-move-plan/1`, either `declaration_only` or `blocked`. `batchReadiness` is always `not_evaluated`; the result never claims that a batch is ready. Each explicit old→target row carries source SHA256, `.meta` SHA256/GUID, native imported type, all native object identities, reverse static GUID dependencies, and any changed Resources key. Moves retain the original extension and never target `.meta`. Targets must follow the registered layout: `Game/Content/{Config,Levels,Prefabs,Materials,Shaders,Images,Sprites,Models,Animations,Spine,Fonts,Audio}`, `Game/Scenes`, the declared code/editor/test layers, or explicit `GreaGenerated`, `ThirdParty`, and `Plugins` roots. `Textures` is a legacy path and is never accepted as a standard target. Before planning, every hashed audit source is re-hashed; any changed consumer invalidates the graph. Unhandled dynamic Resource loads, matching old-path consumers, moved literal Resource keys, ambiguous Resource candidates/types, missing metadata, stale snapshots, missing identities, GUID mismatches, and occupied/case-colliding destinations block the declaration.

`proposedSteps` contains the declared `{"kind":"asset.move","source":...,"target":...}` rows. `batchSpec` is null whenever blockers remain; only a `declaration_only` result includes a batch-shaped declaration, and even then readiness is not evaluated. After explicitly resolving consumers, pass the complete operation through `beaver.batch.plan`. That existing native flow independently checks dependencies and content preconditions, creates missing target folders with `AssetDatabase.CreateFolder`, performs `AssetDatabase.MoveAsset`, and reads back GUID/localIDs. The structure module never executes it.

## Scope and interpretation

Paths are project-relative POSIX paths and moves are restricted to `Assets/`. Current standard locations are `Assets/Game/{Bootstrap,Domain,Gameplay,Presentation,Services,Diagnostics}`, typed content under `Assets/Game/Content/<Kind>/<Module>`, scenes under `Assets/Game/Scenes`, project tools under `Assets/Game/Editor/{Generators,Validators,Build}`, and tests under `Assets/Game/Tests/{EditMode,PlayMode}`. Other roots are findings, not automatic migration instructions. Third-party packages and recovered serialized identities need narrow documented exceptions.

Resources findings include the literal key/API, candidate assets under `Resources`, and native imported types. Missing candidates, duplicate keys, and ambiguous native types have explicit issue codes. The generic type at the call site is not treated as evidence of actual imported type. Matching is static and case-sensitive. Inventory rows include native imported type and object identities only when present in the supplied snapshot. Known type checks use that identity: Texture2D main assets map to `Images` (including sprite-mode textures and Sprite subassets); a serialized Sprite main asset maps to `Sprites`. `Textures` is reported as a legacy path. Unknown imported types stay unclassified rather than inferred from extensions. Spine and Fonts groups may retain companion materials/textures only under a path-scoped, rule-matched exception. Formal enabled build scenes outside `Game/Scenes` are explicit issues. Numeric level values belong in JSON under `Config`; `Levels` is reserved for nonduplicated layout/index assets. Matching rules are from GREA STR-05/06. Build settings findings do not substitute for native build-settings readback.

The audit hashes at most 64 MiB per file and 2 GiB total. Traversal and the reused reference scanner share the existing bounded whole-input policy of 500,000 entries/files, allowing large imported projects to be audited without a separate scanner. Over-budget assets receive explicit findings and cannot be moved by a plan without their hash. Symlinks are reported as scan-blocking findings and never followed; static reference scanning is skipped when a symlink makes its scope unsafe. Scratch reference output uses the system temporary directory, not the game project. Public tests use synthetic files and invented GUID/local IDs only.

A legacy build scene outside Game/Scenes remains an explicit audit issue and a remainingStructureIssues entry when not included in the mapping. It does not block an unrelated safe incremental move or its own correctly targeted migration. projectConformance always remains not-established; declaration_only never signs off the full project structure.

The final planner binds `scannedInputPaths` and hashes across Assets (including metadata), Packages and ProjectSettings. Added/deleted inputs invalidate the audit; newly introduced symlinks are rejected before any content read. Governance files are tracked separately under product-root-relative identities. Existing hashes alone cannot establish closure. The reused C# tokenizer finds ordinary/verbatim Assets path literals in any root and excludes comments; matching generator/JSON consumers and unresolved interpolated Assets prefixes block affected mappings. Proposed targets and their parents use NFC/casefold collision checks, including existing directory spelling and file-as-parent conflicts. Old snapshots without the complete input path set require a new inspect.
