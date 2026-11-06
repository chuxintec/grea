# Native code architecture contract

`monkey.code_architecture_contract.validate_architecture(plan, catalog)` is a
small, read-only structural gate for a source-bound native Unity architecture
plan. It returns deterministic class asset paths, counts, and the fixed
five-layer assembly reference matrix. Invalid input raises the existing
`monkey.sources.compiled.ParseError` with code `CODE_ARCHITECTURE_CONTRACT`, a
field location, and a short reason.

The accepted plan schema is `monkey-native-code-architecture/1`. The plan's
`sourceManifestSha256` must exactly match the lowercase SHA-256 identity on the
catalog. Every catalog source unit must occur exactly once in `sourceCoverage`
with a supported disposition and a nonempty reason. Class and module IDs,
source links, declared module membership, entry point, and integration-chain
references are checked for consistency. Class output paths follow
`Assets/Game/<Layer>/<Module path>/<Name>.cs`; module identifiers use dot
segments, which become directories. `rootNamespace`, module names, class names,
field names, method names, and parameter names are checked as non-keyword C#
identifiers.

Allowed same-layer and cross-layer references are constrained as follows:

| Layer | Allowed source-level dependencies | Assembly references |
| --- | --- | --- |
| Domain | Domain | none |
| Gameplay | Domain, Gameplay | Domain |
| Presentation | Domain, Gameplay, Presentation | Domain, Gameplay |
| Services | Domain, Gameplay, Services | Domain, Gameplay |
| Bootstrap | all five layers | Domain, Gameplay, Presentation, Services |

The plan's `dependsOn` lists name layers and may include the owning layer for
intra-layer relationships. `typeDependencies` lists actual target class IDs; each
reference must exist and respect the declared layer edge. Method `sourceMemberIds`
must belong to the class's declared source units. Large input member catalogs may
be sharded; the stage restores and verifies them before structural validation.
The returned `assemblyReferences` excludes the
owning assembly itself. Core Domain and Gameplay field, parameter, return, and
declared base types (`base` or `baseType`, if supplied) may not use `dynamic`, Unity engine/editor types, or
`Dictionary<string, object>` as a catch-all representation.

Each integration chain must reference Bootstrap, Gameplay, Domain, and
Presentation classes and carry nonempty behavior text. The first core chain
must provide a relative JSON configuration path; optional chains may use
existing Prefab tuning without inventing a configuration file. All configuration and asset paths must
be relative file paths without traversal. This checks path shape and declared
composition only: it does not read files or prove that a path exists, that a
configuration was loaded, or that the described behavior ran.

The validator is bounded to 8,000,000 input values and nesting depth 96, accepts
JSON-like dictionaries/lists, and performs no I/O. It deliberately does not
require every planned class or method to compile, every source unit to map to a
new class, or unknown source behavior to be implemented. It does not generate
Unity code and does not claim source restoration, successful compilation,
runtime integration, or gameplay equivalence.

Run the focused tests from the repository root with:

```sh
PYTHONPATH=src .venv/bin/python -m unittest tests.test_code_architecture_contract
```

Design kinds include class, struct, interface, enum and record; optional null base types denote no declared base. A record plan is not a proof of compiler/serialization compatibility. Implementation ownership (`sourceUnitIds`) must agree reciprocally with source coverage; broad analysis inputs may be stored separately as `sourceInputUnitIds` and confer no implementation claim.
