# Static type evidence extraction

`monkey.code_type_evidence.extract_type_evidence` converts exact source identities, bounded method selectors, and optional reviewed schema-1 type evidence into a candidate typed module contract. It uses `code_graph.facts` only; original source is never executed. The extractor does not create game-specific profiles or lower C#.

```python
from pathlib import Path
from monkey.code_type_evidence import extract_type_evidence

result = extract_type_evidence(
    Path("game.js"),
    [{"classId": "class@binding@123", "methodId": "method@456"}],
    type_evidence=None,          # or schema-1 mapping, canonical bytes, or a path
    namespace="Game.Domain.Recovered",
)
if result["status"] == "ready":
    contract = result["contract"]  # pass to code-select / code-emit
else:
    fillable = result["fillableContract"]  # schemaVersion-1 contract; review/fill nulls
    # After human review: set types and callDomain, then run extraction again.
    reviewed = extract_type_evidence(Path("game.js"), selectors, fillable)
```

The selector is `extract_type_evidence(source_path, selectors, type_evidence=None, *, namespace=None)`. `selectors` contains 1–16 exact `{classId, methodId}` rows. A schema-1 seed is source-SHA bound; its class/method hashes are checked against the selected source. It may be a mapping, canonical JSON bytes, or file path. Without a seed, the caller supplies a target `namespace`; target class and method names default to exact source names. Static source-class calls through `this.member` or a lexical constructor/class binding are closed iteratively, with a 64-method and 12-pass limit. For seeded methods, the selector honors the reviewed non-null call-domain rule for unreachable `x || fallback()` branches.

The small inferred domain is `Number`, `Boolean`, `String`, and `Void`. Numeric unary/update and `- * / % **` operators constrain operands to the explicit Number call domain. Relational comparisons yield Boolean and can constrain the unknown side when the other side is proven Number or String. `+` is inferred only when a String or Number operand is already evidenced; `a + b` with both sides unknown stays ambiguous because JavaScript addition may concatenate or add. Equality yields Boolean but does not guess operand types. Literal types, same-type conditional branches, explicit seed types, direct source-call parameter/return evidence, and primitive assignments to `this.field` are also supported. A no-return method yields Void only when the method has no return statement. Every inferred value includes the rule and source byte span; class/method IDs and hashes come from the source graph.

The contract contains only methods whose required parameter, return, local, and module-field types are complete; unknown values never enter this candidate contract. `ready` means a schema-1 contract can be offered to the existing selector/emitter for actual semantic lowering; it does not mean compilation or behavior verification. `fillableContract` is itself a schema-1 contract with `sourceSha256`, `namespace`, `records`, `modules`, `callDomain`, and `missingEvidence`. It retains every known type and exact class/method hashes; each unresolved parameter, return, local, or field is `null`. `missingEvidence` locates that hole by module/class/method identity, hash, binding ID where applicable, source byte span, and the kind of reviewed evidence needed. Namespace or human-reviewed `callDomain` gaps are top-level entries. Fill nulls only after review, supply the call-domain statement, then pass the filled document back as `type_evidence`; the source SHA and method/class hashes are checked again.

`missing_type_or_dependency_contract` means more reviewed type/call evidence is needed; `unsupported_semantics` marks async/generator, nested callback inference, dynamic source-class calls or other explicitly unsupported cases; `missing_source` identifies source identity or exact selector failure. A partial `contract` may accompany gaps for review, but callers must only hand it to generation when status is `ready`.

If selected seed method types reference records, unused record schemas are pruned. Any record field not observed in selected method ASTs must have an exact-source seed method witness; the contract's `recordShapeEvidence` contains only those method IDs and hashes, and witness methods are not added to the generation closure. If no witness exists, the result remains incomplete and names the field.

## Limits

This is intentionally not a whole-program JavaScript type inferencer. Untyped `a + b`, unknown external calls, coercing objects, dynamic property access, callbacks/closures without complete reviewed types, arbitrary collection shapes, optional/nullish behavior, inheritance, async execution, and unsupported operators do not become `object` or guessed primitives. Numeric-operator inference narrows the supported call domain to Number; it is not a claim that every original dynamic caller passed a Number. The parent emitter remains responsible for rejecting unsupported method-body semantics and generating an immutable candidate.

The dedicated standard-library unittest fixtures cover primitive inference, dependency closure, exact seed reuse and record witnesses, ambiguous addition, contradictory constraints, no-value returns, unsupported async behavior, source SHA mismatch, and deterministic contracts. Tests do not run the original game or an editor.
