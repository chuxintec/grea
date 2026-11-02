# Selected Unity-source Prefab recovery

Development profile: source Unity 2021.3.30f1, target Unity 6000.6.2f1 and uGUI 2.6.0. This additive profile reuses pinned inspection and AssetRipper exports. It does not execute source assemblies, WASM or source business code. Existing commands and fixed artifacts remain unchanged.

## Public commands

```
monkey recover-unity-prefabs --request REQUEST.json --expected-request SHA256 --out NEW_DIRECTORY
monkey verify-unity-prefabs --candidate CANDIDATE/UnityProject --expected-manifest SHA256 --unity-editor EXACT_EDITOR --out NEW_DIRECTORY --budget-seconds 600
monkey verify-unity-prefabs --candidate CANDIDATE/UnityProject --expected-manifest SHA256 --unity-editor EXACT_EDITOR --out NEW_DIRECTORY --headless
monkey freeze-unity-prefabs --native-output NATIVE_DIRECTORY --expected-execution SHA256 --out NEW_DIRECTORY
monkey inspect-unity-prefab-schemas --request REQUEST.json --expected-request SHA256 --out NEW_DIRECTORY
```

Generation returns exit 1 with `needs_action`: generated output is not native acceptance. Verification runs only a fresh owned copy, refuses concurrent main Unity/Creator Editors, pins its plan/helper, retains logs and readback, and stops only its own child when its budget expires. `native-verified-subset` requires readback `completed` and child exit 0. `native-partial` retains explicit unsupported presentation with exit 1. Neither status proves Player, business, visual parity or consumer adoption. A timed-out or failed child is not accepted from counts or an old readback.

`--headless` runs with `-batchmode -nographics`, defers rendering/visible edits and preserves partial status. A second independent headless process verifies the saved state without saving again and compares all native identity/reference tables across processes. Freeze requires both exited processes, exact original/source and readback hashes, and unchanged post-exit file bytes. It excludes Library and the Editor verifier and produces the existing target-profile/namespace/file-ownership manifest for adoption preflight. Source namespace is derived from the complete selected root identities; it does not imply compatibility with an existing consumer assembly or Resources key.

## Request contract

`monkey-unity-prefab-recovery-request/1`, schemaVersion 1, requires the exact target version, source roots `{sourceSha256,file,pathId}`, a pinned input index and a pinned provider export inventory/receipt/binding/prepared-job lineage. Optional source selection and metadata pins remain evidence, never implementation selectors. Type evidence pins DummyDLL bytes and prior static decompiler declarations per assembly. Declarations prove schema only; this command does not rerun the decompiler or recover methods. Explicit `allowDisabledUnavailableCarriers` permits only proven field carriers with disclosed source/target base differences and disabled unavailable behavior.

Optional `sdkEvidence` pins official target C# sources, metadata and their assembly definitions. A source assembly/namespace/class maps only to an exact pinned target declaration and script GUID/localID. Native reconstruction must independently verify GetClass and the actual script tuple. Provider stubs remain quarantined outside Assets; a planned SDK rebind remains pending until native verification. Optional per-assembly `ilDeclarations` pins static IL text for exact declared field assembly/type references, including cross-assembly enums; it does not execute or recover source methods.

Optional `builtinSchemaReceipts` supplies fresh, pinned exact-source built-in schemas. The schema command accepts `monkey-unity-prefab-builtin-schema-request/1` with source, providerPython, wantedObjects and budgetSeconds. It reads at most 32 exact objects through the existing pinned UnityPy worker, recording process exit and unchanged source bytes. New schema evidence does not assert equivalence to an earlier reader. The graph retains source identities and references for all indexed files; typed-value/string budgets apply to reachable objects and used schemas, with separate whole-file alias guards. Serialized external GUID hex is explicitly raw bytes; native GUID text conversion does not infer resource names from path IDs.

The input index binds existing source/inspection/typed-object receipts and a combined serialized-file lookup. Selected originals, selected derived provider inputs, receipts, schemas and payloads are hash checked. Prior reader fingerprints are retained as prior evidence; they are not asserted equal to the current reader. Missing or ambiguous external identities remain gaps. Graph object identities include container SHA, serialized-file SHA/name and path ID. Built-in engine references retain original identity and are unverified until native readback.

Provider selection uses exact original AssetBundle container paths and GUID closure, not first basename matches. Original Prefab/resource/meta bytes are copied unchanged; generated script declarations preserve original assembly and type identity. Runtime layout uses the existing GUID-preserving layout planner. Unsupported code is retained outside Assets; original executable assemblies and provider assembly definitions are not admitted. Unknown methods are never replaced with empty implementations.

## Candidate and native evidence

`UnityProject/manifest.json` owns exact generated files. Source graph, prior input receipts, declaration evidence, provider lineage, schema/carrier dispositions and relocation mappings live under Analysis. The generation report separates native, static and business status. Native expectations derive hierarchy/component order/fields/references from source evidence and target resource GUIDs from retained metadata. Native readback records actual class/assembly, GUID/localID/type, field storage types, saved/reopened identity and representative text/image/transform edit renders. Source enabled values are checked before unavailable behaviors are explicitly disabled; persisted disabled state is checked afterward.

The first development profile remains acceptance-pending. Compiled source shaders, unsupported source effects, target-native script mapping and non-UI render scope can require further work. Do not infer a complete module, ten-root exit or all-Unity support from generation, local tests or successful SDK compilation alone. Fixed producer/package identities and actual consumer receipts are separate handoff requirements.

Source RectTransform stored Transform XY may be stale relative to anchoredPosition. Native expectations retain those stored source values as evidence and derive actual XY from the source parent size, anchors and pivots; all authoritative Rect fields remain checked. Source UInt8 fields become bool expectations only with proven declaration/native field profiles, including the bounded UI.FontData bool fields. Integers, enum storage and array lengths remain distinct from bool and float fields in actual readback.
