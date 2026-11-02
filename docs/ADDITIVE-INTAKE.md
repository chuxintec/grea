# Additive Unity intake specifications v1 and v2

`beaver.intake_contract.validate_spec(doc)` checks the closed, declarative input
contract for additive asset intake. It returns the original dictionary on
success and raises `BeaverError` with an `INTAKE_SPEC_` code on invalid input.
It performs no filesystem reads, Unity Editor calls, writes, or compiler
discovery. Plan, apply, rollback, native readback, and prefab-context coverage
belong to separate workflow stages; passing this validator alone is not
evidence that any of those stages ran or that a product works.

The [v1 JSON Schema](schemas/additive-intake-1.schema.json), [v2 JSON Schema](schemas/additive-intake-2.schema.json), and [v3 JSON Schema](schemas/additive-intake-3.schema.json)
use draft 2020-12 to describe each version's static closed-object shape,
required fields, array limits, scalar types, hashes, and typed field-value
union. They are useful for editors and early structural checks.
`validate_spec` and the plan guards remain the semantic authority: they
additionally enforce Windows-invalid names, NFC and case-fold path aliases,
matching extensions, nonzero/reference relationships, cross-list uniqueness
and disjointness, and prefab/asset/compiler context. JSON Schema does not
claim to enforce those cross-table or filesystem facts.

## Top-level shape

The object has exactly these fields:

```json
{
  "schemaVersion": 1,
  "operation": "additive-intake",
  "candidateManifestSha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "additions": [{"source": "Assets/Candidate/Panel.prefab", "target": "Assets/Game/Panel.prefab"}],
  "externalScripts": [],
  "omittedCompilerInputs": [],
  "verifications": [],
  "protectedAssets": [],
  "evidence": []
}
```

`additions` has 1–256 entries. Each entry has exactly `source` and `target`;
both are canonical `Assets/` paths with the same allowed extension: `.prefab`,
`.asset`, `.mat`, `.png`, `.ttf`, `.otf`, `.shader`, `.txt`, or `.json`.
Scripts, assemblies, DLLs, scenes, metadata files, and other imports are
excluded. Source and destination paths are each unique under NFC plus
case-insensitive comparison.

## Schema version 2: retained assets and package scripts

Version 2 keeps every version 1 field and its validation rules, changes
`schemaVersion` to `2`, and requires two additional closed arrays:
`externalAssets` and `packageScripts`. A version 1 object remains valid as-is;
v1 rejects either v2 field as unknown, and v2 rejects a missing new array.

`externalAssets` has at most 256 entries. Each entry has exactly `source`,
`target`, `guid`, `sha256`, `metaSha256`, `objects`, and `reason`. Source and
target are canonical `Assets/` asset paths with the same non-compiler
allowlisted extension (`.asset`, `.mat`, `.png`, `.ttf`, `.otf`, `.shader`,
`.txt`, or `.json`); `.prefab` and compiler inputs are excluded. Each object
list has 1–4096 entries, with at most 4096 objects total across the array.
Objects and fields use the same exact owner/typed-field structure as prefab
`verifications`. Their fields combined with all v1 `verifications` fields are
limited to 250,000. Local IDs are unique within each external asset. Source
paths, target paths, and GUIDs are each unique; external-asset paths cannot
intersect additions or external-script paths, and GUIDs cannot collide with
external-script GUIDs.

An external asset declares retained identity reuse: its source and target
metadata must resolve to the same declared GUID, and the declared asset and
metadata hashes pin the reviewed bytes. It is not a copy or overwrite request.
Native apply must check exact native object observations for the declared
objects and preserve the existing asset bytes.

`packageScripts` has at most 64 entries. Each entry has exactly `target`,
`guid`, `type`, `assembly`, `localId`, `name`, `packageName`, `packageVersion`,
`packageSource`, `packageJsonSha256`, `sha256`, `metaSha256`, and `reason`.
Targets must be canonical C# files under
`Packages/com.unity.ugui/Runtime/`; package identity is fixed to
`com.unity.ugui`, assembly to `UnityEngine.UI`, and type names must begin with
`UnityEngine.UI.`. Versions use strict semantic-version syntax and sources are
`registry` or `builtin`. Each package script has a nonzero signed 64-bit native
local ID and pinned package JSON, script, and metadata hashes. Target paths and
GUIDs are unique, and package-script GUIDs cannot collide with external asset
or external-script GUIDs. Native verification must resolve exact objects and
confirm `MonoScript.GetClass()` identity.

The plan/apply implementation owns the complete serialized-reference snapshot
before and after native import and must fail closed if its report exceeds the
native output budget. The JSON Schema and contract validator only establish
the declaration shape; they do not read packages, import assets, or prove
native identity.

## Schema version 3: frozen new scripts and UTF-16 characters

Version 3 keeps all version 2 fields and rules and requires a closed
`newScripts` array with at most 16 records. It also adds the `character` field
kind to prefab and external-asset observations. Versions 1 and 2 remain
unchanged and reject `character`.

Each `newScripts` record has exactly `source`, `target`, `guid`, `sha256`,
`metaSha256`, `sourceType`, `sourceAssembly`, `targetType`, `targetAssembly`,
`baseType`, `baseAssembly`, `localId`, `fields`, and `reason`. Source and target
are canonical `Assets/` C# paths. The target cannot be under an `Editor`
directory, and its filename must equal the final class name in `targetType`.
Source and target types must match; the target assembly is exactly
`Assembly-CSharp`. Source/base assemblies are simple names. The GUID and file
and metadata hashes are pinned; local ID is a nonzero signed 64-bit integer.
Fields have at most 128 exact `{name, type, assembly}` entries, with unique C#
identifier names and nonempty types/simple assembly names. Source, target,
GUID, and target type values are unique across the array. One row may use the
same source and target path; path reuse across rows or with additions,
external scripts, or external assets is rejected. GUIDs cannot collide with
external script, external asset, or package script declarations.

`omittedCompilerInputs.coveredByExternalScript` may name either an
`externalScripts.source` or a `newScripts.source` in v3. A new script source
cannot itself be listed as omitted. The plan stage still discovers all
candidate compiler inputs and rejects unaccounted compiler files.

The native workflow freezes each declared script's source and metadata bytes,
uses the compiler stage, then runs an independent code check for
`MonoScript.GetClass()`, the declared base type, and field identities before
Prefab verification and an independent cold reopen. If the gated method
entered and a later phase fails, recovery uses the existing low-level
`restore_code` path under its recorded before-image guards. A failure before
the native method is entered does not invoke that method or count as a
behavior pass. These gates verify declared source identities and serialized
fields; they do not claim gameplay behavior. Existing transactions keep their
previous runtime contract.

The v3 `character` value is an integer UTF-16 code unit from 0 through 65535,
including surrogate values. It is preserved as the supplied code unit; it is
not converted to or normalized as a Unicode code point.

Paths reject traversal, empty components, backslashes, colons, control
characters, non-NFC spellings, Windows-invalid/reserved names, and trailing
spaces or dots. No Unity `.meta` file may be named as an asset. Evidence paths
are absolute, canonical NFC paths and carry a lowercase SHA-256; this module
validates their shape but deliberately does not read them or verify their
contents.

## Existing script reuse

An `externalScripts` entry has exactly `source`, `sourceGuid`, `sourceType`,
`sourceAssembly`, `target`, `targetGuid`, `targetType`, `targetAssembly`,
`targetLocalId`, `targetSha256`, `targetMetaSha256`, and `reason`. Both paths
must end in `.cs`. GUIDs are 32 lowercase hexadecimal characters and must be
identical because v1 preserves serialized `m_Script` references. Source and
target script types must match. Assembly values are simple names without a
`.dll` suffix or path. The target local ID is a nonzero signed 64-bit integer;
both target hashes are lowercase SHA-256 values; the reason is nonempty.
Entries are unique by source, target, and GUID. Script paths cannot overlap
addition sources or targets.

This is a narrow declaration for reusing an explicitly existing external
script. It does not authorize importing, creating, replacing, or editing C#,
`.asmdef`, `.asmref`, `.rsp`, DLL, or other compiler inputs.

`omittedCompilerInputs` entries have exactly `path`, `reason`, and
`coveredByExternalScript`. Paths end in `.cs`, `.asmdef`, `.asmref`, or `.rsp`;
the reason is nonempty and `coveredByExternalScript` must name a declared
external script source. Omitted paths cannot overlap addition sources or
external script sources. This declaration is not a complete compiler-input
inventory: the calling plan stage must discover the candidate's compiler
inputs and reject undeclared omissions or unsupported inputs.

## Prefab observations

`verifications` can be empty. Each entry has exactly `asset` and `objects`;
`asset` must exactly name an `.prefab` `additions.source`. `objects` contains
1–4096 observations. Each observation has exactly `localId`, `type`,
`assembly`, `name`, and `fields`. Local IDs are unique, nonzero signed 64-bit
integers; type and assembly are nonempty; name may be empty. Each field has
exactly `propertyPath`, `kind`, and `value`, and property paths are unique
within that object. Supported kinds are `integer`, `float`, `boolean`,
`string`, and `object`. Integers are signed 64-bit and exclude booleans; floats
are finite numeric values and exclude booleans; strings are at most 16,384
Unicode characters. Object references use exactly `{guid, localId, type,
assembly}`. A null reference has all four fields empty (`guid`, `type`, and
`assembly` empty strings and `localId` zero); non-null references require a
lowercase GUID, nonzero signed local ID, and nonempty type and simple assembly
name. The aggregate field limit is 250,000. Empty field lists are allowed.

These are typed observations, not raw serialized text or executable overrides.
The parent intake workflow must determine which prefab objects and properties
are required by the actual adoption context; a syntactically valid empty
verification list does not satisfy that contextual requirement.

## Protected assets and errors

`protectedAssets` entries have exactly `path`, `sha256`, and `metaSha256`.
Each path is a unique allowed `Assets/` target asset path and cannot also be an
addition destination. Both hashes are lowercase SHA-256 strings. The validator
checks declarations only; the caller must compare them against observed
project files before applying a plan.

All contract failures use `INTAKE_SPEC_*` error codes. Unknown fields are
rejected at every object level. Empty `externalScripts`,
`omittedCompilerInputs`, `protectedAssets`, and `evidence` lists are valid.
Schema validation is a structural precheck; runtime contract validation and
the plan's observed-file guards must still run before an apply operation.

## Neutral examples

Small accepted example: one prefab is added, no external script is reused,
and no evidence or protected-file declarations are supplied.

```json
{"schemaVersion":1,"operation":"additive-intake","candidateManifestSha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","additions":[{"source":"Assets/Candidate/Panel.prefab","target":"Assets/Game/Panel.prefab"}],"externalScripts":[],"omittedCompilerInputs":[],"verifications":[],"protectedAssets":[],"evidence":[]}
```

Rejected example: a traversal path attempts to escape the candidate Assets
root. The validator rejects it with an `INTAKE_SPEC_PATH` failure.

```json
{"schemaVersion":1,"operation":"additive-intake","candidateManifestSha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","additions":[{"source":"Assets/../Outside/Panel.prefab","target":"Assets/Game/Panel.prefab"}],"externalScripts":[],"omittedCompilerInputs":[],"verifications":[],"protectedAssets":[],"evidence":[]}
```

The contract does not relax existing baseline-adoption protections. Its
allowlist only describes additive asset files and explicit references to
already-existing scripts; it does not create compiler inputs or permit
existing product code, metadata, or business assets to change.

## CLI workflow

The implemented command shape is:

```text
beaver intake plan --candidate <candidate> --target <owned-project> --spec <spec.json> --out <new-output>
beaver intake apply --plan <intake-plan.json> --expected-plan <sha256> --editor-path <Unity> --out <new-transaction> --timeout <seconds>
beaver intake rollback --transaction <transaction> --expected-plan <sha256> --editor-path <Unity> --timeout <seconds>
```

`plan` produces a pinned declarative plan and does not import or reopen assets.
`apply` performs the guarded native operation; `rollback` recovers that
transaction only when its recorded before/after state still matches. The native path is exercised separately on private neutral fixtures; formal product intake remains consumer-owned and requires its own evidence. A successful Python plan does not establish native execution. Each native phase has its own timeout; budget the outer call for three phases plus startup/cleanup (apply without newScripts) or two phases (rollback). Spec3 with newScripts requires the five-phase budget documented below. No command uses a foreground Editor or changes TCC.

## Execution and preservation boundary

Planning verifies the fixed candidate, all selected file/meta pairs, complete declaration of candidate compiler inputs, serialized GUID closure, unique destination paths/GUIDs/Resources keys, exact retained script pins, evidence files, protected assets, and the full current Assets/Packages/ProjectSettings file and Assets-directory state. Every selected Prefab requires an exact owner set. Source type/domain and field declarations are caller-reviewed provenance; target GetClass, persistent identity, type/domain/name and declared SerializedObject values are actually checked natively. Source and target domains may explicitly differ; neither source methods nor domain equivalence is claimed. Float comparison uses a fixed absolute tolerance of 0.00001. Integer observations include enum, array-size and layer-mask properties.

Apply creates only selected non-code asset pairs. It uses the established native import/rollback backend, then starts an independent no-graphics Editor for verification. Existing source, metadata, settings, folders and old adoption states must remain unchanged; owned new directories and their native folder metadata are recorded. A basename change can affect Unity asset/root names and therefore requires explicit correct expectations; no inferred rename is silently accepted.

Transactions live outside the product. No singleton adoption state is created or replaced, so separate source namespaces can be appended in independent reviewed transactions. V1 external reuse is limited to same-GUID/type C# scripts; existing non-script dependencies or different-GUID rewrites require a separately supported contract, not omission of closure guards. Rollback requires an exited process, exact recorded post-state and original implementation/plan, then removes only the recorded new assets and owned empty folders through native APIs, independently checks absence and retained types, and requires the complete original file/directory state. Any later source, metadata, new-file or directory edit blocks rollback; it is preserved. Failures retain journals and cannot be treated as zero writes or replayed automatically. A helper-install/cleanup ownership failure stops for inspection.

Neutral validation covers explicit source/default-domain script compatibility, typed fields/references, cold reopen, failed name expectation with guarded rollback, and later-edit refusal. Visual, Player, game behavior, unsupported source shaders and unknown recovered behavior remain separate consumer gates. Existing `adopt` baseline requirements and old fixed transactions are unchanged.

A successful intake preserves source diagnostics and native/presentation/Player/business provenance in `sourceCandidateValidation`. Source native-partial/unknown statuses or diagnostics keep the public result partial (exit1), while `intakeStatus=verified` and a complete transaction mean the declared intake succeeded. This is not a retry instruction: inspect the complete receipt and reuse it. Unsupported source behavior is never certified by object/field counts.

Fixed24 package declarations require an already-resolved, direct, exact version in both Packages/manifest.json and packages-lock.json. Registry source must be https://packages.unity.com; builtin is also supported. Exactly one matching non-symlink Library/PackageCache root is required. The full cached package file tree is pinned and rechecked before mutation/rollback and after native work; package source/meta/package.json hashes and native PackageInfo resolved root/source/version/GetClass are independently checked. Nothing installs or copies package scripts. Candidate compiler stubs with a declared official package GUID are omitted, never imported. Other missing scripts and unselected/deadbeef references remain blocked. External non-code objects require exact object sets, declared typed fields and automatic full persistent-reference snapshots compared across preflight, cold verification and rollback.

## Fixed25 reference traversal

The 250000-visited-property guard stays in place per retained object, and the persistent-reference guard remains 250000. Traversal skips a nonempty homogeneous array subtree only when Unity reports a recognized primitive element type and its first element is a matching childless, non-array scalar SerializedProperty. Character bytes, integers, booleans, floats and strings qualify only with this double check. Empty or unknown arrays, object/PPtr arrays, structs, managed references and arrays whose element shape contradicts a primitive name are traversed normally. Nested complex arrays remain traversed; a proven primitive array inside a nested struct can be skipped without hiding its sibling references. Declared typed-field checks still run independently before traversal. Native reports add referenceTraversals with visited counts and each skipped array's path/type/length/scalar property type. Exact object and persistent-reference snapshots continue to be compared across preflight, cold reopen and rollback. No larger budget, reference suppression, resource rewrite or new CLI/spec field is introduced.

The source compiler stage reuses BeaverAdoption code staging and its closed-Editor restore_code recovery; intake does not synthesize an adoption baseline or change old adoption state. A declaration cannot add asmdefs/asmrefs/DLLs. Existing ancestor asmdef/asmref paths are refused for new scripts, and native loaded-type absence is required before staging. GetClass must match the only loaded type of the reviewed full name, its default Assembly-CSharp domain, direct base and every declared field type/assembly before any new Prefab import. Partial failed compilation is recoverable only after the owned Editor exits and current files/directories exactly match the recorded transaction; offline restore_code removes only checkpointed unchanged new source/meta, then a separate native rollback verifies source restoration, type absence and exact original files/directories. Later edits refuse before this removal. Apply may need five native phases; recommended outer budget5*inner+310, rollback2*inner+160, e.g inner<=280 under an1800-second cap. Unknown methods are neither invoked nor declared restored.


### Fixed27 compiled watcher boundary

A spec3 newScripts transaction may make a missing script reference in an unchanged retained Prefab/Scene resolve after compilation. The new-script-only native path records the original direct dependency GUID set and exact watcher source/meta hashes before staging. An independent code-check may add only a declared new .cs GUID whose exact nonzero localID/GUID/type3 m_Script PPtr already appears in that watcher's canonical native YAML. This conservative text reader never rewrites assets: binary, noncanonical, oversized or unrecognized serialization receives no allowance. Every original dependency must remain; unrelated additions, arbitrary MonoScript fields and invented per-watcher allowances are refused.

Original and compiled snapshots are separate, bound to the plan and native compiler checkpoint, with SHA pins persisted in the transaction journal. The compiled checkpoint records every watcher's before/after/added sets. Later consumption verifies those same pins and delta invariants; it never learns a replacement baseline. Resource import start/end and independent cold verify must match the compiled snapshot exactly and retain source/meta hashes. Offline compiler restoration plus native rollback compares the original dependency snapshot, not the compiled one. Native reports expose watcherCheck and the successful CLI subset result adds watcherPolicy, watchersChecked and watcherResolutions. The existing up-to128 unchanged watcher selection is retained; this is not a claim of exhaustive project-wide native watcher coverage. Full original source preservation remains independently guarded.

Ordinary adoption and spec1/2 have no intakeNewScripts opt-in and keep their existing strict watcher behavior. Spec3 with no newScripts also retains the old path. Contract3, request argv, newScripts/Character rules, five apply/two rollback phases and outer budget formulas are unchanged. Old fixed26 transactions require their original runtime; a new fixed producer requires a fresh reviewed plan. Unknown behaviors, gameplay and visuals remain unavailable.
