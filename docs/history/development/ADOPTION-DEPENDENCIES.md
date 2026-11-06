# Adoption compile dependency declarations

`adoptionDependencies` is an optional producer manifest field for declaring
compile-time dependencies used by adoption previews. It is validated from the
already-snapshotted manifest and its `files` inventory; this check does not
inspect source contents or infer dependencies.

```json
{
  "adoptionDependencies": {
    "schemaVersion": 1,
    "coverage": "producer-declared",
    "edges": [
      {
        "path": "Assets/Game/Consumer.cs",
        "requires": ["Assets/Game/Provider.cs"],
        "kind": "csharp-compile"
      }
    ]
  }
}
```

Each declaration and edge has an exact field set. Paths must be canonical,
safe, slash-separated `Assets/` paths to `.cs` files present in the manifest
file inventory. Duplicate consumers, repeated requirements, self-dependencies,
missing files, unsupported kinds, and malformed paths are rejected. Cycles
between distinct source files are allowed because they are producer evidence,
not a dependency-graph scheduling instruction.

The validator returns a sorted normalized declaration with `status: "declared"`
and `coverage: "producer-declared"`. If the field is absent, it returns
`status: "undeclared"`, `coverage: null`, and no edges. That result does not
mean the compile dependency closure is complete. Consumers must preserve this
distinction and must not promote producer declarations to compiler analysis.

Package requirements and editor-version checks remain governed by the existing
adoption `project_requirements` behavior. This field does not introduce a
second package-version contract or a C# dependency analyzer.
