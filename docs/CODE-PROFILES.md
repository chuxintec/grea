The Foodstreet contracts and recipe adapter are an optional legacy project extension. They are loaded only through explicit `--module-profile` or `--configuration-table` selection, never by project-name detection or the default Prefab pipeline. The extension manifest declares its scope, provider and packaged generator files; the core keeps the source-bound contract mechanism and compatibility entry points. These profiles are not a general recipe or game-logic recovery claim.

# Built-in typed source profiles

```sh
monkey code-emit --source game.js --module-profile foodstreet-demand-health-v1 --configuration-table ElementMultiOrderPool.json --out new-code-candidate
```

This command emits a fresh owned candidate, including the exact resolved contract under `SourceRecovery`, source method index, normal C# and original runtime JSON. It returns `partial` / exit 1 because compilation, behavior and native validation are separate. `--module-profile`, `--module-contract` and legacy `--code-model` are mutually exclusive. Unknown source revisions require a reviewed new typed contract; the CLI does not silently reuse a similar-looking profile.

`monkey.code_profiles.load_profile(profile_name, source_path) -> bytes` returns canonical UTF-8 JSON bytes for a built-in typed code contract. The allowed names are `foodstreet-demand-health-v1` and `foodstreet-motion-math-v1`. The loader reads the JSON with `importlib.resources`, checks its schema and pinned source identity, then reads the supplied source file and requires an exact byte count and SHA-256 match. Unknown names and source mismatches fail before any code generation. It does not execute source code.

The profile captures source method/class identities, typed records, module fields, method IDs/hashes/signatures/locals, namespace, and the bounded call domain. It contains no original code spans, absolute paths, media, or configuration values. The output is a contract input to Monkey's typed AST emitter; the profile does not contain C# method bodies and does not imply broad support for Cocos or all methods in the source.

The bundled `foodstreet-demand-health-v1` is pinned to source SHA-256 `[private fingerprint omitted]` and 7,147,892 bytes. It selects 12 methods across three classes. The AST-based emitter must still independently verify every class/method identity, source hash, and typed call-domain before producing candidate code.

The resource lives under `monkey/extensions/legacy_foodstreet/code_profiles/foodstreet-demand-health-v1.json`; distribution metadata must include that package data file. The loader resolves it from the installed package, never from the current repository or adjacent `.private` artifacts.

The second profile selects four exact static methods from the same frozen source: angle normalization, angle unwrapping with a same-class dependency, Point2 distance, and clamping. Its Point2 fields and primitive binary64 call domain are explicit. It uses normal `Math.Sqrt` and source arithmetic; it does not generate the original vector factory or a Cocos runtime. Independent tests cover wrap boundaries, negative zero, NaN, distance overflow and reversed clamp bounds. Selection of three roots automatically adds the fourth method. It is separate from the original 12-method configuration/health profile; a reviewed combined contract can select all 16 without duplicating methods.
