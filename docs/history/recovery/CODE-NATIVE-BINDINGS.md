# Native Prefab binding identity

`monkey.code_architecture_bindings.build_prefab_authoring_plan(...)` builds a source-pinned authoring plan for an architecture View. It does not modify a Prefab, compile a Unity project, or execute source code.

## Source class proof

Before emitting an attach-component operation, the planner verifies a class-specific chain from the accepted architecture and module evidence:

- The target is one `Presentation` C# class with `baseType: UnityEngine.MonoBehaviour`; its path and source bytes match the module receipt.
- The source unit belongs to both the architecture class and module receipt. Its file and span hashes match the pinned source bytes, and its start offset matches the byte offset embedded in the selected `codeRegion`.
- `architecture.classes[].bindingEvidence.sourceIds` names that exact code region once, with `literalBindingCount: 1`. Across the complete architecture, exactly one class may own that source identity.
- The selected source bytes at that offset contain the literal Cocos `cc._RF.push` registration. Its script type identity must match the selected serialized component type, and its literal class name must match the code-region name.
- The C# file contains the planned class deriving from `MonoBehaviour`. The component-code binding must carry `exact_literal_script_identity`, and its asset/component/node IDs must agree with the pinned source map and packed Prefab evidence.

Sharing a source unit is only a candidate ownership relation. `classesWithThisSourceUnit` cannot establish that multiple classes all represent the same original script. An architecture class without class-specific source identity evidence produces an explicit unresolved plan with zero operations for compatibility with older plans. A contradictory code region, byte offset, Cocos registration ID/name, or ambiguous architecture mapping is rejected.

The target class declaration is checked after the repository's C# lexer blanks comments and literal contents, so a lookalike declaration inside comments or normal, verbatim, or raw strings cannot establish identity. Script IDs must parse as a canonical or supported compact UUID before they can match; malformed UUID-like text remains unresolved/rejected.

The returned `sourceClassIdentityProof` records the class, module receipt, source-unit and source-file pins, exact code region, literal Cocos script registration, source component identity, uniqueness result, and a proof SHA-256. When the proof is unresolved, the plan remains `partial-unresolved-evidence`, `component.attachStatus` states the reason, and `operations` is empty. A pinned Script `.meta` GUID remains only authoring input; whole-project compile and Editor serialization are separate validation steps.

## Assembled Script identity

Fresh architecture assembly now writes manifest-owned `.cs.meta` and `.asmdef.meta` files. Script GUIDs derive from the project namespace, architecture root namespace and class ID, and stay stable when output location or method bodies change. Collisions with retained resources abort assembly. The `scriptIdentities` index binds each class path and C# hash to its metadata hash and GUID; revisions preserve existing GUID bytes and refresh the changed C# hashes.

Module model receipts remain immutable and usually contain only C# files. For their unchanged C# implementations, callers may supply `native_candidate_manifest_bytes`, `native_candidate_manifest_sha256`, and `script_meta_bytes` to obtain the Script identity from a later assembly. The planner verifies the full manifest pin, source/architecture relationship, exact class ownership and bytes, metadata ownership, deterministic GUID and identity index. It records `assembledScriptIdentity`; it does not retrofit metadata into the old module receipt. Conflicts or revised C# without a matching new receipt are rejected. This supplies an authoring identity, not evidence that Unity compiled or attached the class.

## Verification evidence

The focused tests are in `tests/test_code_architecture_bindings.py`. They cover a valid exact identity, source-unit sharing without class identity, duplicate target classes, wrong source ID/offset, mismatched literal Cocos script identity, legacy evidence absence, fake class declarations in comments and string forms, and malformed UUID-like script IDs.

An actual source-pinned plan for `CardSeason.CardSeasonMainWindow` was generated under `.private/v060-architecture-first-20261027/NativeBindingPlan02/Revision03/`. Its literal `cc._RF.push` class name and compressed script ID match the exact code region and source component type. The plan remains `partial-unresolved-evidence` with zero operations because the module receipt has no deterministic C# Script `.meta` GUID and the existing binding fields retain unresolved targets. No Editor or Prefab writes were performed.
