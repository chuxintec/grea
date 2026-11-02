# Selected Unity-source Prefab recovery

Development profile: source Unity 2021.3.30f1, target Unity 6000.6.2f1 and uGUI 2.6.0. This additive profile reuses pinned inspection and AssetRipper exports. It does not execute source assemblies, WASM or source business code. Existing commands and fixed artifacts remain unchanged.

## Public commands

```
monkey recover-unity-prefabs --request REQUEST.json --expected-request SHA256 --out NEW_DIRECTORY
monkey verify-unity-prefabs --candidate CANDIDATE/UnityProject --expected-manifest SHA256 --unity-editor EXACT_EDITOR --out NEW_DIRECTORY --budget-seconds 600
```

Generation returns exit 1 with `needs_action`: generated output is not native acceptance. Verification runs only a fresh owned copy, refuses concurrent main Unity/Creator Editors, pins its plan/helper, retains logs and readback, and stops only its own child when its budget expires. `native-verified-subset` requires readback `completed` and child exit 0. `native-partial` retains explicit unsupported presentation with exit 1. Neither status proves Player, business, visual parity or consumer adoption. A timed-out or failed child is not accepted from counts or an old readback.

## Request contract

`monkey-unity-prefab-recovery-request/1`, schemaVersion 1, requires the exact target version, source roots `{sourceSha256,file,pathId}`, a pinned input index and a pinned provider export inventory/receipt/binding/prepared-job lineage. Optional source selection and metadata pins remain evidence, never implementation selectors. Type evidence pins DummyDLL bytes and prior static decompiler declarations per assembly. Declarations prove schema only; this command does not rerun the decompiler or recover methods. Explicit `allowDisabledUnavailableCarriers` permits only proven field carriers with disclosed source/target base differences and disabled unavailable behavior.

The input index binds existing source/inspection/typed-object receipts and a combined serialized-file lookup. Selected originals, selected derived provider inputs, receipts, schemas and payloads are hash checked. Prior reader fingerprints are retained as prior evidence; they are not asserted equal to the current reader. Missing or ambiguous external identities remain gaps. Graph object identities include container SHA, serialized-file SHA/name and path ID. Built-in engine references retain original identity and are unverified until native readback.

Provider selection uses exact original AssetBundle container paths and GUID closure, not first basename matches. Original Prefab/resource/meta bytes are copied unchanged; generated script declarations preserve original assembly and type identity. Runtime layout uses the existing GUID-preserving layout planner. Unsupported code is retained outside Assets; original executable assemblies and provider assembly definitions are not admitted. Unknown methods are never replaced with empty implementations.

## Candidate and native evidence

`UnityProject/manifest.json` owns exact generated files. Source graph, prior input receipts, declaration evidence, provider lineage, schema/carrier dispositions and relocation mappings live under Analysis. The generation report separates native, static and business status. Native expectations derive hierarchy/component order/fields/references from source evidence and target resource GUIDs from retained metadata. Native readback records actual class/assembly, GUID/localID/type, field storage types, saved/reopened identity and representative text/image/transform edit renders. Source enabled values are checked before unavailable behaviors are explicitly disabled; persisted disabled state is checked afterward.

The first development profile remains acceptance-pending. Compiled source shaders, unsupported source effects, target-native script mapping and non-UI render scope can require further work. Do not infer a complete module, ten-root exit or all-Unity support from generation, local tests or successful SDK compilation alone. Fixed producer/package identities and actual consumer receipts are separate handoff requirements.
