# Native script binding preparation

`intake bindings-plan` and `intake prepare-bindings` extend the existing intake
pipeline when an incoming C# MonoScript has the same full type and exact source
bytes as a retained script, but a different GUID. Ordinary intake's same-GUID
external script contract and all versions 1–5 remain unchanged.

```
beaver intake bindings-plan --source SOURCE_PROJECT --target RETAINED_PROJECT \
  --spec BINDINGS_JSON --out FRESH_PLAN_DIRECTORY
beaver intake prepare-bindings --plan FRESH_PLAN_DIRECTORY/binding-plan.json \
  --expected-plan EXACT_PLAN_SHA --out FRESH_PREPARATION_DIRECTORY \
  --editor-path UNITY_6000_6_2F1 --timeout 280
```

The first command is read-only apart from its new plan directory. The second
copies only the source's Assets, Packages and ProjectSettings to an independent
project, without source Library, caches or an inherited owning manifest. Neither
command writes the retained target. Preparation makes no adoption or baseline claim. After both native gates it
produces its own bounded, provenance-bearing consumer export.

The closed `beaver-intake-bindings/1` input has `schemaVersion: 1`, operation
`prepare-script-bindings`, `bindings`, `prefabs`, and `bridgeReferences`. Each of
1–16 bindings explicitly pins source/target C# paths, GUIDs, source/meta SHA256,
full type, compilation assembly and MonoScript localID 11500000. Full types and
code bytes must match; GUIDs must differ. Compilation scope is checked against
the nearest asmdef; asmref scopes are rejected. Bridge references are explicit
assembly names (for example `UnityEngine.UI`, `Unity.TextMeshPro`), and cannot
reference predefined Assembly-CSharp. Each mapping must occur in the selected
regular Prefabs; nested Prefab dependencies must also be selected. Variants are
rejected by the native gate. Source snapshots are bounded to 30000 files/2 GiB.

In the copy, exact retained script bytes and metadata are imported in the
non-auto-referenced `Beaver.IntakeBindings` assembly. Original source scripts
remain untouched. The native helper independently checks original and bridge
MonoScript GetClass, assembly, GUID and localID. It uses SerializedObject object
references, including m_Script, to map to the retained GUIDs and saves with
PrefabUtility. It never edits serialized YAML or metadata text.

Changing m_Script may destroy Unity's old managed component wrapper. The helper
captures persistent owner GUID/localID keys and reacquires the exact current
object after applying a binding before dirtying or saving. Lost or duplicate
owner IDs fail the gate; exceptions and field comparisons are never skipped.

The helper records every serialized property, persistent reference GUID/localID,
object identity and property type before the change. ObjectReference values are atomic GUID/localID/type records, with MonoScript class/assembly checked against the explicit bindings. Their internal serialized pointer subtrees (including transient m_FileID storage) are not enumerated; all ordinary numeric fields, array elements and other real serialized properties remain included. Only the declared script
identities and their matching Editor class identifier may differ. Unsupported
property kinds, missing references, missing scripts, field loss, unexpected
files/settings changes and failed/late Editor exit block consumption. A second
cold Editor process must reproduce the normalized snapshot and resolve mapped
components through the preparation assembly. These are execution requirements;
compiling the helper alone does not prove Unity accepts m_Script migration.

A successful preparation removes its owned helper and writes a receipt,
`intake-binding-inputs.json`, and a separately frozen consumer candidate. The
consumer candidate has an owning manifest produced by this preparation operation,
with original-source, saved-source-product and rebound-state lineage and a typed
native oracle. A pure monkey candidate should first use monkey's existing saved-state
freeze. The beaver-derived candidate is not passed off as a monkey export or its
old readback. Same-GUID externalScript rows feed ordinary intake from the frozen
consumer candidate; the temporary bridge compilation scope is explicitly kept out
of the target import set.
The receipt's other compiler omissions are only a partial input: all remaining
compiler inputs, selected asset closure, typed target oracle, package dependencies
and destination mappings must still be declared. Ordinary target native preflight
rechecks the retained target's actual GetClass/assembly/GUID and later edits.

Subtree mapping already exists: each intake `additions` row explicitly maps its
source asset to an absent target path, preserving the incoming GUID and metadata.
The target owner chooses the subtree and fresh-plans before applying; preparation
never overwrites a same-path old root. No new adopter or YAML mapping is required.

Reports are compact headers capped at 1 MiB. Each complete compact snapshot is
independently pinned by raw UTF-8 SHA256 and byte count, capped at 64 MiB and
8 million JSON nodes. Native capture additionally caps 250000 properties,
50000 owners, 32 MiB of captured text and individual property text at 1 MiB.
Apply/cold-verify snapshot hashes must equal the original before checkpoint.
Large inline pretty-printed reports are not accepted as a fallback.

Each native preparation phase has a 1–1200 second budget. With `--timeout 280`,
allow at least 650 seconds for the two phases, cleanup and process exit. On
failure, retain that disposable directory and logs; no successful preparation
receipt is emitted and no formal target rollback is needed. Never apply a failed
copy or repeat a successful target intake transaction. Product/visual/business
acceptance and full original behavior recovery are outside this operation.

Failure envelopes distinguish a prelaunch failure (`native: not_run`) from a
started Editor gate (`native: failed`, with owned PID/exit receipts) and an
unreaped Editor (`native: attempted_exit_pending`). Preserve those receipts.


A failed Python export can continue with `intake export-bindings --preparation
ORIGINAL_STAGE --expected-plan ORIGINAL_PLAN_SHA --native-runtime
ORIGINAL_BEAVER_PACKAGE_ROOT --expected-native-producer ORIGINAL_PRODUCER_SHA
--out FRESH_EXPORT_DIRECTORY`. The entire original runtime inventory is pinned
(max1024 files/64MiB), its producer must match the old plan, and its native helper
must be byte-identical to the current helper. Both original processes must have
exited successfully and the before/apply/cold snapshots must be identical. Source,
retained script, spec and provenance pins are freshly checked. The original stage
is read-only; this command creates only the new export, never invokes Editor or
replays native gates. A native helper change requires fresh preparation.

Unity persistent localIDs are signed64 values. Export preserves negative material
subasset IDs exactly; zero, booleans and out-of-range IDs remain invalid. Null
references use the complete empty identity tuple. Source provenance is stored
once in an owned8MiB sidecar; the1MiB lineage binds that sidecar rather than
duplicating large original claims.

`intake spec-bindings --candidate EXPORT --expected-manifest SHA256 --target TARGET
--mapping MAPPING --out OUTPUT [--policy POLICY] [--preparation-receipt RECEIPT]`
generates a normal schema 4 intake specification from inventoried native
fragments and an explicit additions mapping, then actually calls the existing
`intake.plan`. A reviewed policy may add existing compiler/asset declarations;
schema 5 additionally permits the existing retained-assembly contract. The tool
never invents compiler omissions, field schemas, or a common baseline.

`consumption-report.json` records exact package requirement conflicts and every
uncovered compiler path, GUID, hash and script type/assembly observed in the
saved native oracle. No type is guessed for unobserved compiler inputs. A
blocked planner remains blocked; this command does not install packages or run
an Editor. An optional receipt must pin this exact exported candidate. The
corrected receipt is a new output with the original receipt path/hash; the
original native evidence and receipt remain unchanged.


### Requested and resolved package identity

`intake package-requirements --candidate EXPORT --target TARGET --source-project
SAVED_PROJECT --editor-path EDITOR --evidence ORIGINAL_PROOF --expected-evidence
SHA256 --out OUTPUT` creates a hash-pinned resolution context and a fresh
requirements report. It checks the candidate, saved project and target input
bytes, Editor version/revision, complete dependency locks, actual package
caches and Editor builtin sources. The supported builtin UGUI override requires
a strictly lower stable requested version and exact resolved/cache/Editor
agreement; missing, stale or inconsistent evidence blocks. Other version
mismatches remain blocked. It never installs packages or edits manifests.

Pass `--package-evidence OUTPUT/package-resolution.json
--expected-package-evidence SHA256` to `intake plan` or `intake spec-bindings`.
The context and all resolved identities are included in the plan and rechecked.
The default requirement policy is unchanged without this explicit context.

### Selected compiler closure and ordered code batches

Add `--classify --source-project SAVED_PROJECT --dotnet DOTNET --sdk-root SDK
--runtime-readback PREVIOUS_COLD_REOPEN_LOG` to `intake spec-bindings`.
The tool checks actual Bee source scopes and source/meta bytes, then runs the
existing offline Roslyn inspector. It follows native script roots and actual
symbol dependencies, records field carriers, runtime components, Editor-only
scope, retained types, compiler support and unknowns. Empty native references
do not prove a file is unnecessary. Namespace symbols create no dependency
edges; late-bound lookups remain explicit blockers.

The reused cold-reopen log and the supplied Editor's actual Mono core library
pin runtime field identities rather than copying reference-facade assembly
names into native expectations. Arrays use their element type's assembly;
unresolved facade and generic forwarding identities are blocked.

`dependency-evidence.json` owns the complete classification, source/target pins
and boundaries. `batch-recipes.json` points to new exact-byte owned selections,
normal spec4 documents and actual existing `intake.plan` results. Each batch
contains at most16 new scripts in explicit script-only mode, preserves
strongly connected dependencies, and records deferred inputs as selection
boundaries. No four-helper omission is invented for unrelated compiler inputs.
Oversized cycles and unresolved dependencies block their dependants.

Script destinations follow the exact uniform prefix of the explicit mapping;
nonuniform mappings require `--script-target-root Assets/...`. Existing matching
script identities can be reused after earlier code adoption. Images stay in
the later serialized asset closure. Re-run the command and
replan against the real target after each predecessor succeeds; later recipes
do not fabricate a future target snapshot. Native preflight, source staging,
independent compile/GetClass, import/cold reopen, source audit and product gates
remain required. Code plans do not authorize formal project writes.

### Exact retained resources and complete binding plans

`spec-bindings --reuse-exact-assets` scans the complete mapped group. An
occupied GUID or destination is a real conflict. A different target GUID at
the original source path is only a reuse comparison when the mapped destination
is free. Source/target bytes, complete metadata, importer identity and complete
native object sets must agree before a generated `externalAssets` declaration
replaces an addition. Neither file extensions nor a shader's conventional
localID prove native identity. Prefab PPtrs are observed references, and do not
prove that all subassets were enumerated.

`--asset-evidence BUNDLE --expected-asset-evidence SHA256` accepts a bundle with
contract `beaver-native-asset-reuse-evidence/1` and actual `sourceStage` and
`targetStage` paths. The adapter validates the immutable batch plan, completed
journal, native result, exact before pins, importer and full object sets. Missing
or inconsistent evidence stays blocked; the complete scan records every issue.

The existing `batch` operation now supports the read-only `asset.inspect` step.
It captures GUID, complete native objects (signed localID/type/assembly/name),
importer type/assembly and file/meta hashes. Its product write set is empty.
Generated inspection requests are plans only: this work does not run an Editor
or replay a partial source. Regenerate them on the approved final source and
current owned target before execution.

`bindings-plan --source UNPREPARED_SOURCE --target TARGET --complete-from
OWNED_CANDIDATE --expected-candidate MANIFEST_SHA --dependency-report REPORT
--out OUTPUT` combines the existing bindings with proven retained component
reuse. It uses the existing planner and native preparation transaction; source
and target identities, fields and dependency evidence stay pinned. The known
four-page case produces six entries. Future consumer declarations are marked
planned, not exported or executed.

Add `--binding-source UNPREPARED_SOURCE` to `spec-bindings --classify` to produce
that complete plan in the same output. `continuation-plan.json` links the real
binding plan, future owning export, script batches, complete resource scan and
final Prefab consumer. It requires an approved final source and actual native
results; it never invents a future target before-image or baseline.

### Script-only batches

Spec4/5 explicitly support `operation: "script-only-intake"`. This operation
requires `additions: []` and 1..16 `newScripts`; additive mode retains its
nonempty asset requirement. Compiler coverage, referenced dependencies,
protected inputs, native preflight, staging, independent code-check, import,
cold reopen and guarded rollback use the existing implementation.

Generated code batches no longer include unrelated images. Their exact-byte
owned selections contain only the selected compiler source/meta pairs,
necessary directory metadata and pinned project/package inputs. Texture
placement stays in the later serialized Prefab/resource closure. The previous
dev8 image padding was not dependency evidence and is retired for new plans;
its frozen outputs remain unchanged.
