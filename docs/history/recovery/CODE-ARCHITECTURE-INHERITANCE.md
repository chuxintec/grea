# Hash-pinned C# inheritance evidence

`monkey.code_architecture_inheritance.resolve_inherited_members` resolves a narrow class-to-class inheritance chain from supplied records and source mappings. It returns source evidence that a required declaration is inherited. The module workflow uses this evidence during materialization and read-only recheck to distinguish a real inherited member from an incomplete generated class declaration.

The workflow supplies exact same-module class bytes, recomputes source pins, and saves each inheritance chain in class evidence. Only corresponding planned-method/field-missing markers may be removed, and only for a verified ancestor with no resolver blockers or ancestor architecture guards. Child and ancestor layer, engine, placeholder, owner and untyped-dictionary checks remain active. A changed child hash invalidates saved evidence. An unresolved external terminal base remains explicit and is not a compilation or semantic proof. Sources with conditional-compilation directives are blocked rather than choosing a variant without compiler defines.

## Input contract

```python
result = resolve_inherited_members(
    class_records=[
        {
            "classId": "Tutorial.GuideHand",
            "kind": "class",
            "name": "GuideHand",
            "namespace": "sample-game.Presentation.Tutorial",
            "path": "Assets/Game/Presentation/Tutorial/GuideHand.cs",
            "sha256": "<file sha256 from a verified class record>",
            "bytes": 2723,
        },
        # Include candidate base classes as records too.
    ],
    source_mappings={
        "Assets/Game/Presentation/Tutorial/GuideHand.cs": {
            "path": "Assets/Game/Presentation/Tutorial/GuideHand.cs",
            "sha256": "<same sha256>",
            "bytes": 2723,
            "source": b"<exact UTF-8 bytes>",
        },
        # Include exact bytes and matching hashes for every source that may be traversed.
    },
    required_members={"Tutorial.GuideHand": ["Bind", "Render", "Controller"]},
    max_depth=8,
)
```

Class records must have unique IDs and declare `classId` (or `id`), `kind: "class"`, `name`, `namespace`, `path`, and lowercase SHA-256. Source mappings are keyed by the exact relative source path and repeat the path/hash beside the actual UTF-8 `source` bytes or string. The resolver recomputes SHA-256 and any supplied byte count before parsing. A mismatch raises `InheritanceEvidenceError`; missing mapping, missing declaration, unresolved base, or unsupported syntax is returned as an explicit blocker without evidence from that source.

`required_members` maps class IDs to member names or to `{name: expected_kind}` entries. Supported kinds are `method`, `field`, `property`, and `event`. The output contains one result per input class, direct or inherited member evidence, a `baseShaChain` containing each verified class ID/qualified name/path/SHA-256, unresolved base edges, blockers, and a conservative `resolution` of `complete`, `partial`, or `unresolved`.

## Resolution rules

Only an exact, unique class declaration is followed. An unqualified base name is matched in the declaring class's exact namespace. A fully qualified or `global::` base is matched exactly. `using` aliases, imported namespaces, reflection, naming patterns, comments, method calls, and string contents do not resolve a base or a member.

The source scanner ignores comments and C# string/character literals, then examines direct class-body declarations. Only public, protected, or protected-internal members count. Private, private-protected, and internal-only members do not count because the caller has not supplied assembly identity. A private declaration with the requested name blocks lookup through that class rather than allowing a potentially hidden base member to be guessed. Nested types are not members of the enclosing type.

A known class base may still provide positive member evidence when another base-list entry is unresolved, such as an external interface. That unresolved entry stays in `unresolvedBases`; the result cannot be `complete` while the base chain contains unresolved edges. A member is considered supported only when its evidence names a verified declaring class and source SHA.

The parser stops inheritance traversal on ambiguous class identity, duplicate class records, missing source, hash drift, cycles, generic classes or base types, partial classes, malformed source braces, unsupported aliases, or the configured depth bound. It does not resolve interface inheritance, generic substitution, `using` namespace imports, assembly-dependent internal visibility, conditional compilation variants, or C# overload/accessor semantics beyond the named declaration. Unsupported direct declarations add blockers, and any blocker remains in the result even if another required member has positive evidence. It deliberately prefers a missed positive over inferred evidence.

## Verified Tutorial chain

The read-only test pins `NativeCorePriority03/Modules/0036/architecture-module-manifest.json` using its `.sha256` sidecar and independently verifies each Tutorial source against its class record SHA and byte count. The module's `GuideUtil.cs` declares `Controller`, `Snapshot`, `LifetimeCancellation`, `Bind`, `Render`, and lifecycle methods. Fifteen Tutorial classes with manifest completeness diagnostics inherit `GuideUtil` in `sample-game.Presentation.Tutorial`; those records resolve the missing names to the verified GuideUtil bytes. `GuideHand` also overrides `Render`, so its evidence points to its own verified source for that name. `GuideUtil` itself inherits external `UnityEngine.MonoBehaviour`, which remains explicitly unresolved.

This test establishes lexical declaration and source-chain evidence only. It does not establish C# compilation, Unity assembly composition, actual runtime dispatch, UI behavior, or any source-game semantic equivalence. The module is a standalone library; its caller may use the positive evidence for an appropriately bounded structural classification and must retain all blockers and hashes.

## Verified Narrative chain

The read-only test also pins `NativeProject01/Modules/0026/architecture-module-manifest.json` by its `.sha256` sidecar (`[private fingerprint omitted]`) and checks each source's bytes and SHA against its class record. Four `Narrative_*Item` classes inherit the same-namespace `sample-game.Presentation.Narrative.NarrativeItem`; the fifth pinned record is that base class. The base declares `Controller`, `Snapshot`, `LifetimeCancellation`, `Bind`, `Render`, `OnEnable`, and `OnDestroy`. The helper returns five class results, and the four derived classes resolve all seven requested names to either their own override or the pinned base source. `NarrativeItem.cs` is SHA-256 `[private fingerprint omitted]` (3,818 bytes). Its external `UnityEngine.MonoBehaviour` base remains unresolved; native object bindings and execution are outside this evidence.

For the Tutorial module, the manifest sidecar SHA is `[private fingerprint omitted]`; `GuideUtil.cs` is SHA-256 `[private fingerprint omitted]` (6,740 bytes). Fifteen diagnostic-bearing Tutorial class records plus `GuideUtil` produce sixteen results. The `GuideTarget.Index` auto-property initializer (`{ get; private set; } = -1`) is treated as part of the property declaration, so it does not create a false unsupported-declaration blocker.
