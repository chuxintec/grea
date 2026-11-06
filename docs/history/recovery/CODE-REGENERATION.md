# C8 code regeneration selection

`monkey.code_regeneration.select_reuse(candidate, expected_manifest_sha256, modules, generator_signature)` is a read-only selector. It does not edit or remove the old candidate. The generator must create a fresh candidate and build its complete `manifest.json` using only selected verified bytes plus newly generated module output.

`monkey.code_regeneration.plan_modules(modules, generator_signature)` uses the same request validation and fingerprint rules for a fresh-first build. It does not read a candidate and returns `status`, `moduleRecords`, `actions`, and graph `diagnostics`; valid modules have action `regenerate` with reason `fresh_candidate_required`. It omits `candidateManifestSha256` and `reusableFiles`.

## Request contract

`modules` is an array of `{id, sourceFingerprint, dependencies, targetPaths}`. `id` and dependency IDs use ASCII letters, digits, underscore, dot, colon, or hyphen, beginning with a letter or underscore. Fingerprints are lowercase SHA-256 hex. `targetPaths` contains canonical, NFC-normalized, project-relative POSIX paths; `..`, absolute paths, backslashes, case-fold collisions, duplicate paths, or two owners of one path are rejected. A module's own recursive calls are internal and must not appear as external dependencies.

Every dependency must also appear in the request. Missing references and cycles produce `blocked` actions with explicit reasons. Valid modules are processed dependency-first. The dependency fingerprint is SHA-256 of canonical UTF-8 JSON:

```json
{"schemaVersion":1,"dependencies":[{"id":"callee","sourceFingerprint":"...","cacheKey":"..."}]}
```

Dependency rows sort by module ID and bind the dependency's own source fingerprint and cache key. A module cache key is SHA-256 of canonical UTF-8 JSON with sorted object keys and compact separators:

```json
{"schemaVersion":1,"id":"caller","sourceFingerprint":"...","dependencyFingerprint":"...","generatorSignature":"...","targetPaths":["Assets/Game/Logic/Caller.cs"]}
```

The source fingerprint is supplied by the source/model owner and must bind all source facts used to produce that module. The generator signature must bind the code-generation implementation and any output-affecting options. A dependency fingerprint incorporates the transitive dependency fingerprints, so changing a callee invalidates callers while leaving unrelated modules reusable.

## Candidate manifest contract

The candidate is a frozen code-only candidate with a `manifest.json` whose exact SHA-256 equals `expected_manifest_sha256`. It contains:

```json
{
  "schemaVersion": 1,
  "scopeMode": "code-modules-only",
  "codeGeneratorSignature": "64 lowercase hex characters",
  "files": [{"path":"Assets/Game/Logic/Caller.cs","sha256":"...","bytes":42,"owner":"caller"}],
  "codeModules": [{
    "id":"caller", "sourceFingerprint":"...", "dependencyFingerprint":"...",
    "cacheKey":"...", "dependencies":["callee"],
    "targetPaths":["Assets/Game/Logic/Caller.cs"],
    "files":["Assets/Game/Logic/Caller.cs"],
    "sourceMethodMappings":[{"sourceMethodId":"...","targetMethodId":"..."}]
  }]
}
```

`files[].owner` is the module ID; `codeModules[].files` must equal its `targetPaths`. Method mapping content remains opaque to this module and is carried through on reuse, preserving source and generated identities for audit. Unknown, manual, missing, changed, unowned, or symlinked files cannot be silently overwritten. The inventory must exactly match the manifest (excluding `manifest.json`).

## Result and caller behavior

The result contains a per-module `actions` map and ordered `moduleRecords`. Each action is `reuse`, `regenerate`, or `blocked`, with a specific `reason`. `reusableFiles` maps verified candidate paths to in-memory `bytes`; it is intentionally omitted from JSON reports. `moduleRecords` carry the new source/dependency/cache fingerprints and requested paths, and preserve `sourceMethodMappings` for reused modules. For regenerated modules, the caller supplies newly emitted file records and new identity mappings. Do not copy stale method mappings to regenerated output.

The module graph is capped at 20,000 module records, 20,000 target paths total, and 200,000 declared dependency edges. Topological ordering and cycle detection are iterative, so deep module chains do not consume Python recursion depth. Missing references and cycle members block those modules and callers that depend on them; independent modules keep their own `reuse` or `regenerate` action. Graph diagnostics name the affected module IDs.

The selector re-hashes all candidate files before returning bytes and re-checks selected bytes when loading them. It caps manifest parsing at 128 MiB, candidate inventory at 20,000 files, declared candidate bytes at 256 MiB, and each file at 512 MiB. It writes no reports. Callers may serialize `actions`, `moduleRecords`, and `diagnostics` while excluding `reusableFiles`.

This module owns reuse decisions only. It does not merge human edits, apply to an adopted game, rollback project changes, emit C#, or update the old candidate manifest.
