# Reviewed source-identity comparisons

A source provenance field can legitimately retain an original bundle/container path after the active Unity asset moves. Do not rewrite that provenance string to a new project path merely to remove a structure warning. A caller may instead submit an explicit, narrowly bound comparison resolution to the structure move planner:

```text
beaver structure plan --audit <fresh-audit.json> --mappings <mappings.json> \
  --consumer-resolutions <reviewed-comparisons.json> --out <fresh-plan-directory> --summary
```

The schema is [structure-consumer-resolutions-1](schemas/structure-consumer-resolutions-1.schema.json). Each row binds the exact audited C# file, SHA-256 of its raw bytes, token span, decoded literal, reviewed reason and evidence:

```json
{
  "schemaVersion": 1,
  "resolutions": [{
    "file": "Assets/Game/Services/SourceIdentity.cs",
    "fileSha256": "1111111111111111111111111111111111111111111111111111111111111111",
    "span": [120, 159],
    "literal": "assets/legacy/world/original.prefab",
    "kind": "source-identity-comparison",
    "reason": "Compare the original source container identity, not an active Unity lookup.",
    "evidence": "Reviewed source-provenance contract and exact comparison."
  }]
}
```

The example SHA and span are placeholders. Use the exact `pathConsumers` token span from a fresh audit, including the string token's quotes. Spans are zero-based character offsets, end-exclusive, in the decoded UTF-8 C# source with an initial BOM removed; SHA-256 covers the original file bytes. A changed file, span or decoded literal invalidates the declaration. Duplicate, unused and unsupported declarations are rejected.

The planner only accepts supported direct comparison syntax. A declaration does not resolve a resource lookup, dynamic path, JSON reference or missing native identity. The accepted rows remain explicit caller-reviewed assertions in the plan, not native proof of business behavior. Existing source closure, metadata, profile and native-identity guards still apply.

For unresolved Resources calls, only a directly provable literal leading prefix may narrow which changed logical keys are blocked. All dynamic observations remain in the report. Unknown expressions remain conservative; matching namespace keys, changed/removed keys and ambiguous candidates are still checked. Moving an asset without changing its logical key is separately guarded as before. A lexical namespace observation is not proof that dynamic gameplay works or that a resource is unused.

Resources key/prefix comparisons are case-insensitive, following the [Unity Resources.Load API](https://docs.unity3d.com/cn/2020.3/ScriptReference/Resources.Load.html). Prefix proof accepts only normalized forward-slash segments; unsupported expressions retain conservative blocking.
