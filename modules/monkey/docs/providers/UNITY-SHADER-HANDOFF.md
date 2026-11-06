# Shader evidence handoff — local P0 contract

`monkey-shader-handoff/1` classifies existing frozen candidate files. It does not recover new shader code, compile shaders, alter game projects or certify runtime compatibility. The formal 0.6.0 artifacts remain unchanged.

The consumer file `handoff.json` has exactly `schema` and `items`. The JSON Schema is [monkey-shader-handoff-1.schema.json](../schemas/monkey-shader-handoff-1.schema.json); a neutral example is [shader-handoff.json](../examples/shader-handoff.json).

Each item has `path`, `bytes`, `sha256`, `classification`, `source`, `target`, `dialect`, `platformEvidence`, `nativeCompilation`, `runtimeDisposition`, and `evidenceId`. Classification is content-based:

| Classification | Meaning | Default disposition |
| --- | --- | --- |
| source-text | Recognizable source structure; completeness/dependencies/compiler acceptance unproved | source-review |
| platform-compiled | Serialized compiled payload or identifiable platform binary signature; validity/target usability unproved | evidence-only |
| recovered-binary | Recovered program dump or serialized Shader evidence without sufficient payload evidence | evidence-only |
| unknown | Insufficient or damaged evidence | blocked |
| unsupported | Recognized asset kind outside this classifier, including variant collections/graphs | blocked |

`nativeCompilation` is always `not_run`; no item means native compilation success. A valid ShaderGraph or ShaderVariantCollection can be unsupported by this classifier without being an invalid Unity asset. Dispositions are review/hold instructions, never deletion permission or a substitute for build dependencies.

`target` is either `null` or exactly `{ "guid": "<32 lowercase hex>", "localFileID": <signed integer> }`. GUID and localID come only from the pinned metadata and an unambiguous serialized declaration. They are labelled **declaration-only** in `source.targetIdentityEvidence`; they are not an Editor readback. Plain ShaderLab without a declared localID gets `target: null`, even if a metadata GUID exists. The source metadata retains the declared GUID/IDs and metadata hash so a native consumer can resolve and verify actual persistent identity without guessing.

`source` contains classification evidence, metadata identity, immutable owner/source-map pins and source associations. Source AssetBundle container pointers are retained as pointers; external file IDs are not silently resolved. Missing raw object SHA is explicitly null/unavailable. Exact target path, byte hash and GUID must agree with the source mapping before an association is reported as matched. Unmapped/ambiguous/inconsistent associations remain explicit.

Platform evidence records raw serialized IDs or explicit source tags/signatures. It does not infer a Metal-compatible shader from an exported filename or platform list. The consumer independently reads actual build target, pipeline, references and compiler results. Source text may contain unresolved includes or unsupported target syntax.

## Command

```sh
monkey classify-unity-shaders --project <frozen-Unity-candidate> \
  --manifest <recovery-manifest.json> --expected-manifest <SHA-256> \
  --source-mapping <full-resource-handoff.json> --expected-source-mapping <SHA-256> \
  --out <fresh-output>
```

Source mapping is optional, but its expected SHA is mandatory when supplied. The command reads one bounded owner manifest and hashes only discovered shader-related files and their metadata, not the entire recovered pool. Discovery considers declared shader extensions/directories and bounded `.asset` headers for serialized Shader/variant types; it does not claim to identify every unknown untyped binary. Every classified file must match the owner's bytes/hash. Originals, fixed candidate and mapping are checked unchanged; no engine/provider/compiler is launched.

`handoff.json` is the narrow consumer schema. `report.json` adds owner/input pins, scope, counters, diagnostics and explicit `nativeCompilation: not_run`. A classification result is not a complete-project or build-ready verdict. The consumer checks current bytes, metadata, actual native GUID/localID and build/dynamic dependencies before any reversible isolation. Referenced assets must not be removed merely because their classification is evidence-only.

New recovery inventories also attach `shaderEvidence` to Shader-related `nativeFiles` and their mapped targets. `shaderPolicy.defaultRuntimeAdoption` is `hold-all-unverified-shaders`; exported-file counts remain counts of recovered artifacts, not approved runtime assets. Recovery candidates retain reference evidence in place, while formal runtime adoption must use the consumer's build filter and native proof. This does not silently move/delete shaders or repair references with a generic substitute.

P0 evidence includes a bounded frozen-candidate classification and independent neutral source/dump/unknown fixtures. The legacy source map can lack original object associations for implicit Shader dependencies; such items stay `unmapped` even when their exported bytes, metadata and serialized target declarations are fixed. Additional original-object recovery is a separate scope, not filled by matching names. Synthetic beaver planning checks only protocol compatibility and preserves its runtime-use block; no native compiler or isolation execution is implied.
