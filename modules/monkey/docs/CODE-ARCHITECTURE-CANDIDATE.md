# Native architecture candidate assembly

`monkey.code_architecture_candidate.assemble_native_candidate(...)` creates a
fresh, isolated Unity candidate from a frozen Candidate07 resource project, a
validated architecture plan, and an aggregated generated-module directory. It
does not run Codex, Unity, or source code.

The API takes the candidate root and its exact `manifest.json` SHA-256, pinned
architecture plan and validation JSON paths plus hashes, an aggregated module
root and its `manifest.json` hash, then a fresh output path. The validation
document must come from `validate_architecture` and its `classPaths` must match
the deterministic paths implied by the plan. Its five-layer assembly reference
matrix is checked against the architecture contract.

The aggregated module manifest has a `files` array. Each implementation row
contains `path`, `sha256`, `bytes`, `classId`, `sourceUnitIds`,
`sourceMemberIds`, and `status` (`complete` or explicit `partial`). The class
ID and path must match the validated plan. The module manifest pins
`sourceManifestSha256` to the frozen Candidate07 manifest and
`architectureSha256` to the architecture plan bytes; the plan itself must pin
the same Candidate07 manifest. Complete rows must cover all class source units
and source members declared by its planned fields and methods. Partial rows
must list omitted IDs in `unresolvedSourceUnitIds` and
`unresolvedSourceMemberIds`, or provide specific textual `unresolved` reasons.
An optional `modules` array records module `id` and `status`. Empty/comment-only
outputs and immediately empty class/struct shells are rejected; this does not
prove meaningful business behavior. Missing planned class files are rejected
unless the caller explicitly sets `allow_partial=True`; resulting missing or
partial classes remain recorded as partial and never imply successful
compilation.

`implementedClassPaths` records the presence of an owned generated class file.
It does not establish recovered behavior, successful compilation, or runtime
acceptance; consult each file's partial/unresolved metadata and separate evidence.

Assembly keeps all manifest-owned files under `Assets/Game/Content/`,
`ProjectSettings/`, and the two package lock inputs (`Packages/manifest.json`
and `Packages/packages-lock.json`), plus required ancestor metadata when
present. It omits old production scripts and source evidence. The five fixed
assembly definitions are generated deterministically at
`Assets/Game/<Layer>/<Layer>.asmdef`; Domain and Gameplay set
`noEngineReferences=true`. External assembly references are empty by default
and are included only when explicitly supplied by the caller. Package versions
and project settings are copied byte-for-byte from the pinned candidate.

All input files must be represented exactly by their owning manifests; symlinks,
stale hashes, untracked files, output overlap, and an existing output directory
are rejected. Files are copied, not hard-linked. A final source recheck occurs
before the output manifest is written. The output keeps the standard
CandidateSnapshot manifest contract (`schemaVersion: 1`, Unity `targetProfile`,
`namespace`, `scopeMode: "whole-input"`, and file owners limited to `generated`,
`retained`, or `manual`) so Monkey and Beaver can consume it. Architecture
format identity and stage pins live in `architectureSchemaVersion` and
`provenance`. Each file retains its standard owner; `sourceKind` and per-file
`provenance` preserve whether it came from candidate resources, an architecture
module, assembly generation, or an existing helper. Module provenance keeps
the classId and source-to-target member mappings. Compilation and runtime
behavior remain unverified until a later Unity validation stage.

The optional `retained_support_paths` argument preserves explicitly selected
Candidate07 native layout helpers only from
`Assets/Game/Presentation/Common/Layout/`: `IntrinsicGridLayoutGroup`,
`NativeLinearLayoutGroup` (which may also contain `NativeChildLayoutGroup`),
`NativeRectConstraints`, and `NativeTextLineBox`. Each helper must be selected
with its `.cs` and `.cs.meta` pair. The files are hash-checked against the
Candidate07 manifest and recorded with `owner: retained`,
`sourceKind: existing-implementation`, and
`provenance.kind: native-layout-support`; they are not architecture class outputs.
Other legacy scripts and editor conversion tools remain excluded. Duplicate
Unity meta GUIDs across retained assets and support helpers are rejected.

## C# 9 compiler compatibility

The pinned `unity-6000.6.2f1-ugui` compiler profile is recorded from the existing
read-only response file
`.private/v060-architecture-first-20261027/NativeAudioNativeProbe01/Evidence/editor-compile.rsp`
(SHA-256 `[private fingerprint omitted]`).
It uses C# 9 and references both the Unity 6000.6.2f1 managed assemblies and
netstandard2.1 reference assemblies; it has no `/define` switch. An offline
compile with those same references reports CS0518 for a minimal `record` plus
`init` probe when `IsExternalInit` is absent, and compiles successfully with the
shim. This check used the saved response file and local Roslyn compiler without
starting Unity.

Assembly scans planned C# source after removing comments and literals. If no
`record` declaration or `init` accessor is used, it adds no shim. When either is
used, the verified profile causes one manifest-owned public type to be generated
at `Assets/Game/Domain/CompilerSupport/IsExternalInit.cs`, with a deterministic
`.meta` and GUID. Other layers reference `Game.Domain` through the fixed
assembly graph, so the same public type is shared across the candidate. The file
is recorded as `owner: generated`,
`sourceKind: compiler-compatibility-support`, without a `classId`; its path is
kept outside `classPaths` and `implementedClassPaths`. The assembly manifest's
`compilerSupport` entry records the profile evidence, feature trigger, type path,
hash and GUID. Reserved-path or GUID collisions fail assembly. Compilation
remains `not_run` until a later validation stage.

Run the focused tests from the repository root:

```sh
PYTHONPATH=src .venv/bin/python -m unittest tests.test_code_architecture_candidate
```
