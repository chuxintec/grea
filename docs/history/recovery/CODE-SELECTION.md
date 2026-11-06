# Source-bound typed module selection

`monkey.code_selection` turns an exact source identity, explicit method selectors, and reviewed type evidence into a bounded candidate module contract. It does not execute source, infer `double`/`object`, emit C#, write a candidate, or claim unselected methods are unrecoverable. The returned contract is passed to the existing `code_modules.emit`/`prepare` path for the actual lowering and candidate generation.

```python
from pathlib import Path
from monkey.code_profiles import load_profile
from monkey.code_selection import select_modules

source = Path(".../game.js")
evidence = load_profile("foodstreet-demand-health-v1", source)  # canonical JSON bytes
result = select_modules(source, [
    {"classId": "class@binding@926434", "methodId": "method@936255"},
], evidence)
if result["status"] == "selected_ready":
    contract = result["contract"]  # pass this schemaVersion-1 contract to code_modules
```

`selectors` is a 1–256 item array of exact `{classId, methodId}` identities. A `null` classId is permitted only to report an indexed method whose source owner could not be resolved; it is `unsupported_semantics`, never evidence of missing source. `type_evidence` accepts a schemaVersion-1 typed contract mapping or canonical JSON bytes (including bytes from `load_profile`). Evidence must bind the complete source SHA-256 and include explicit module class hashes, method hashes, parameter/return/local types, and explicit record/field contracts. An optional `namespace` must equal the reviewed namespace. The returned dictionary includes a subset `contract`, `moduleRecords`, source method byte/hash mappings, requested and auto-added method IDs, per-module `actions`, diagnostics, and `sourceExecuted: false`. The contract prunes records to those referenced by selected types. If a referenced record field is not read in selected methods, `recordShapeEvidence` carries the exact source method ID/hash from reviewed evidence that demonstrates it; a missing witness blocks the relevant action. This permits an emitter to verify field shape from source AST without generating an unrelated witness method. `plan_selection(...)` is an alias for callers that prefer a planning verb.

The selector requests one static graph pass for methods already covered by the supplied bounded evidence. It adds only direct calls that the graph proves target an indexed source class method: `this.member`, or a receiver lexical binding resolved to a source constructor/class binding. It then traverses that closure iteratively. Calls through unrelated local objects, framework methods, collection methods, built-ins, and dynamic receivers do not create guessed module dependencies. If a proven dependency exists in source but has no supplied type contract, the caller is marked `missing_type_or_dependency_contract` with the exact source call span. Missing or mismatched selected source identities are `missing_source`. Async/generator methods, deferred graph facts and computed source-class calls are `unsupported_semantics` with diagnostics. Type grammar errors are reported as missing reviewed type evidence; no substitute type is created.

One narrow reachability rule matches the emitter's explicit call domain: a call in the right side of `x || fallback()` is not treated as a required dependency when `x` is an explicitly typed, non-null `Map`, `Set`, `List`, or declared record/module type. Numeric, optional, function, and unknown values are not pruned. This rule does not remove the source text or the caller's method mapping. Lowering can still return a precise unsupported diagnostic, and a `selected_ready` result is only a selection/preflight result; compile, behavior, Unity binding, and full-game acceptance remain separate.

## Example evidence

Using the packaged sample-game profile and its exact pinned source, selecting `OrderRules.FindDishOrderDemands` (`method@936255`) proves the `RecipeCatalog.IsDish` dependency (`method@616964`), which in turn proves its `RecipeCatalog.GetRecipeOf` dependency (`method@617302`). The closure selects those two typed methods and the requested method. The `Recipe.ingredients` record field has an exact-source shape witness at `method@621011`; that witness method is not emitted or added to the closure. The observed `GetBoardDemandsMap` reference occurs only in `FindDishOrderDemands`' `Map || fallback` branch; the reviewed non-null Map call domain makes that branch unreachable, so it is reported neither as required nor silently regenerated. This result demonstrates selector-driven closure beyond simply returning the full packaged profile.

An indexed method absent from the typed evidence is explicitly reported as a contract gap. Supplying only an ID does not make it eligible for generation. The source remains read-only and candidate creation remains the caller's responsibility.

## CLI and actual emitter preflight

```sh
monkey code-select --source game.js --selectors roots.json --type-evidence reviewed-types.json --out selection
monkey code-select --source game.js --selectors roots.json --module-profile foodstreet-motion-math-v1 --out motion-selection
monkey code-emit --source game.js --module-contract selection/module-contract.json --out code-candidate
```

`roots.json` contains the selector array. Use exactly one `--type-evidence` file or built-in `--module-profile`. The CLI runs both dependency selection and the real emitter's type/AST lowering, reports `lowering: passed` only when both succeed, and only then writes `module-contract.json`. Exit 0 means ready for generation; a diagnosed selection/lowering gap returns 1 and writes `selection.json` without a usable contract. Invalid inputs are errors. The CLI does not compile or validate behavior itself.

The module API `select_modules` is the graph/type planning layer; `write_selection` is the stronger CLI boundary that also calls `code_modules.prepare`. Multiple reviewed modules sharing the same source and namespace can be selected in one bounded contract. There is no fixed 12-method selector restriction. Unselected inventory remains unclassified, rather than being marked unsupported. Each generation accepts at most 256 unique emitted methods plus same-source shape witnesses (at most 64 witnesses); this is a resource guard per selection, not a recovery quota.
