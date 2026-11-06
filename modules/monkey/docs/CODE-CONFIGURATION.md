# C6 sample-game recipe configuration mapping

`monkey.code_configuration.map_element_multi_order_pool(table_path, source_path, root_dish_id=2015015)` is a read-only, source-bound validator for the `ElementMultiOrderPool` recipe subset. It accepts only the frozen table SHA-256 `[private fingerprint omitted]` and the frozen main script SHA-256 `[private fingerprint omitted]`. Source contracts are stored as byte offsets, lengths, and SHA-256 values; no original minified source text is embedded in the product. It statically checks the `Kp`, `_dishMap`, `flattenIngredientsOf`, config Map-converter, and `ElementMultiOrderPool.decode` spans. It does not execute the source.

The result preserves each source row ID and returns the proven recipe projection: `id`, `dish`, and ordered ingredient ID/quantity pairs. `dish` uses the last `elementIdWeight` key after the source config converter has built its Map; `ingredients` converts original string IDs with JavaScript `Number` semantics and retains numeric quantities. `cookType` records the known source rule `cookType > 0 ? cookType : 1`; other raw row data stays in the original JSON and is not invented or silently filled. The report lists fields intentionally outside this selected `getRecipeOf`/`isDish`/`flattenIngredientsOf` projection.

The source converter iterates JavaScript object keys with `for...in`: canonical integer-index keys sort numerically, while other keys retain JSON object order. The adapter mirrors that order before creating recipe and ingredient Maps. This matters because `flattenIngredientsOf` traverses ingredients in Map order and returns first-seen leaves via `Set`.

Duplicate source row IDs, duplicate mapped dish IDs, ingredient IDs that collide after numeric conversion, empty/unsupported row shapes, booleans/non-numeric quantities, unsafe integer IDs, and any recipe cycle in the table are rejected. Repeated leaf occurrences are valid input; the report includes both `leafOccurrences` and first-seen `flattenedLeaves` so de-duplication is reviewable. The table remains the sole runtime value source; no second editable table or hardcoded recipe values are generated.

`monkey.code_configuration.prepare_assets(table_path, source_path, output, root_dish_id=2015015)` creates a fresh staging directory. It copies the table JSON and its existing Unity `.meta` byte-for-byte, then adds `RecipeJsonConfiguration.cs`, a deterministic `.meta` for that reader, and a source evidence report. The C# reader returns `OrderedMap<double,Recipe>` from `Load(string)` and, under Unity, `Load(TextAsset)`. It uses a small bounded JSON parser because Unity's JsonUtility does not preserve numeric-key dictionaries. The parser reads IDs, dish keys, and ingredient pairs from the supplied JSON, mirrors JS object key order, skips unrelated valid JSON values, rejects malformed/unsupported required fields, unsafe numbers, duplicate normalized IDs, and cycles, then fills the recovered `RecipeCatalog._dishMap` shape. It is a profile adapter for this finite source contract, not the full original `Kp`/`CookEffect` implementation.

The candidate C# file contains no original configuration numbers. An independent offline .NET SDK harness loads the copied real JSON, assigns `RecipeCatalog._dishMap`, and calls `RecipeCatalog.FlattenIngredientsOf(2015015)`. The harness validates the target parser and behavior; Unity's `TextAsset` overload and Editor import remain separate and are not implied by this check.

The checked local frozen inputs are:

- `outputs/sample-game-unified-textures/UnityProject/Assets/Game/Content/Config/Base/ElementMultiOrderPool.json` — 212,601 bytes, 732 rows, SHA-256 above.
- `outputs/sample-game-unified-textures/UnityProject/SourceRecovery/Code/Source/snapshot/_subpackages_main_/subpackages/main/game.js` — 7,147,892 bytes, SHA-256 above.

For root dish `2015015`, the source maps to row `293`; recursive recipe dishes are `2015015 → 2005016`, then sibling recipes `2015002` and `2015005` as visited. Source row IDs are `293`, `323`, `275`, and `279`. Independent depth-first traversal in source Map order yields leaf occurrences and flattened leaves:

```text
occurrences = [1010204, 1005303, 1007206, 1002401, 1007204, 1010201, 1004302, 1005203, 1010303]
flattened   = [1010204, 1005303, 1007206, 1002401, 1007204, 1010201, 1004302, 1005203, 1010303]
```

Each selected ingredient quantity is preserved as `1`; the flatten function intentionally returns distinct leaf IDs and does not aggregate quantities. This is static and offline C# validation, not Unity Editor/TextAsset import or gameplay evidence.
