# Additive Unity intake specification v1

`beaver.intake_contract.validate_spec(doc)` checks the closed, declarative input
contract for additive asset intake. It returns the original dictionary on
success and raises `BeaverError` with an `INTAKE_SPEC_` code on invalid input.
It performs no filesystem reads, Unity Editor calls, writes, or compiler
discovery. Plan, apply, rollback, native readback, and prefab-context coverage
belong to separate workflow stages; passing this validator alone is not
evidence that any of those stages ran or that a product works.

The [JSON Schema draft 2020-12 document](schemas/additive-intake-1.schema.json)
describes the static closed-object shape, required fields, array limits,
scalar types, hashes, and typed field-value union. It is useful for editors
and early structural checks. `validate_spec` and the plan guards remain the
semantic authority: they additionally enforce Windows-invalid names, NFC and
case-fold path aliases, matching extensions, nonzero/reference relationships,
cross-list uniqueness and disjointness, and prefab/asset/compiler context.
JSON Schema does not claim to enforce those cross-table or filesystem facts.

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
transaction only when its recorded before/after state still matches. The native path is exercised separately on private neutral fixtures; formal product intake remains consumer-owned and requires its own evidence. A successful Python plan does not establish native execution. Each native phase has its own timeout; budget the outer call for three phases plus startup/cleanup (apply) or two phases (rollback). No command uses a foreground Editor or changes TCC.

## Execution and preservation boundary

Planning verifies the fixed candidate, all selected file/meta pairs, complete declaration of candidate compiler inputs, serialized GUID closure, unique destination paths/GUIDs/Resources keys, exact retained script pins, evidence files, protected assets, and the full current Assets/Packages/ProjectSettings file and Assets-directory state. Every selected Prefab requires an exact owner set. Source type/domain and field declarations are caller-reviewed provenance; target GetClass, persistent identity, type/domain/name and declared SerializedObject values are actually checked natively. Source and target domains may explicitly differ; neither source methods nor domain equivalence is claimed. Float comparison uses a fixed absolute tolerance of 0.00001. Integer observations include enum, array-size and layer-mask properties.

Apply creates only selected non-code asset pairs. It uses the established native import/rollback backend, then starts an independent no-graphics Editor for verification. Existing source, metadata, settings, folders and old adoption states must remain unchanged; owned new directories and their native folder metadata are recorded. A basename change can affect Unity asset/root names and therefore requires explicit correct expectations; no inferred rename is silently accepted.

Transactions live outside the product. No singleton adoption state is created or replaced, so separate source namespaces can be appended in independent reviewed transactions. V1 external reuse is limited to same-GUID/type C# scripts; existing non-script dependencies or different-GUID rewrites require a separately supported contract, not omission of closure guards. Rollback requires an exited process, exact recorded post-state and original implementation/plan, then removes only the recorded new assets and owned empty folders through native APIs, independently checks absence and retained types, and requires the complete original file/directory state. Any later source, metadata, new-file or directory edit blocks rollback; it is preserved. Failures retain journals and cannot be treated as zero writes or replayed automatically. A helper-install/cleanup ownership failure stops for inspection.

Neutral validation covers explicit source/default-domain script compatibility, typed fields/references, cold reopen, failed name expectation with guarded rollback, and later-edit refusal. Visual, Player, game behavior, unsupported source shaders and unknown recovered behavior remain separate consumer gates. Existing `adopt` baseline requirements and old fixed transactions are unchanged.

A successful intake preserves source diagnostics and native/presentation/Player/business provenance in `sourceCandidateValidation`. Source native-partial/unknown statuses or diagnostics keep the public result partial (exit1), while `intakeStatus=verified` and a complete transaction mean the declared intake succeeded. This is not a retry instruction: inspect the complete receipt and reuse it. Unsupported source behavior is never certified by object/field counts.
