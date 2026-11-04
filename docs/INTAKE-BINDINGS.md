# Native script binding preparation

`intake bindings-plan` and `intake prepare-bindings` extend the existing intake
pipeline when an incoming C# MonoScript has the same full type and exact source
bytes as a retained script, but a different GUID. Ordinary intake's same-GUID
external script contract and all versions 1–5 remain unchanged.

```
beaver intake bindings-plan --source SOURCE_PROJECT --target RETAINED_PROJECT \
  --spec BINDINGS_JSON --out FRESH_PLAN_DIRECTORY
beaver intake prepare-bindings --plan FRESH_PLAN_DIRECTORY/binding-plan.json \
  --expected-plan EXACT_PLAN_SHA --out FRESH_PREPARATION_DIRECTORY \
  --editor-path UNITY_6000_6_2F1 --timeout 280
```

The first command is read-only apart from its new plan directory. The second
copies only the source's Assets, Packages and ProjectSettings to an independent
project, without source Library, caches or an inherited owning manifest. Neither
command writes the retained target. Preparation is not adoption or an owning
export and makes no baseline claim.

The closed `beaver-intake-bindings/1` input has `schemaVersion: 1`, operation
`prepare-script-bindings`, `bindings`, `prefabs`, and `bridgeReferences`. Each of
1–16 bindings explicitly pins source/target C# paths, GUIDs, source/meta SHA256,
full type, compilation assembly and MonoScript localID 11500000. Full types and
code bytes must match; GUIDs must differ. Compilation scope is checked against
the nearest asmdef; asmref scopes are rejected. Bridge references are explicit
assembly names (for example `UnityEngine.UI`, `Unity.TextMeshPro`), and cannot
reference predefined Assembly-CSharp. Each mapping must occur in the selected
regular Prefabs; nested Prefab dependencies must also be selected. Variants are
rejected by the native gate. Source snapshots are bounded to 30000 files/2 GiB.

In the copy, exact retained script bytes and metadata are imported in the
non-auto-referenced `Beaver.IntakeBindings` assembly. Original source scripts
remain untouched. The native helper independently checks original and bridge
MonoScript GetClass, assembly, GUID and localID. It uses SerializedObject object
references, including m_Script, to map to the retained GUIDs and saves with
PrefabUtility. It never edits serialized YAML or metadata text.

Changing m_Script may destroy Unity's old managed component wrapper. The helper
captures persistent owner GUID/localID keys and reacquires the exact current
object after applying a binding before dirtying or saving. Lost or duplicate
owner IDs fail the gate; exceptions and field comparisons are never skipped.

The helper records every serialized property, persistent reference GUID/localID,
object identity and property type before the change. ObjectReference values are atomic GUID/localID/type records, with MonoScript class/assembly checked against the explicit bindings. Their internal serialized pointer subtrees (including transient m_FileID storage) are not enumerated; all ordinary numeric fields, array elements and other real serialized properties remain included. Only the declared script
identities and their matching Editor class identifier may differ. Unsupported
property kinds, missing references, missing scripts, field loss, unexpected
files/settings changes and failed/late Editor exit block consumption. A second
cold Editor process must reproduce the normalized snapshot and resolve mapped
components through the preparation assembly. These are execution requirements;
compiling the helper alone does not prove Unity accepts m_Script migration.

A successful preparation removes its owned helper and writes a receipt plus
`intake-binding-inputs.json`. Those exact same-GUID externalScript rows can feed
ordinary intake after GREA freezes the saved native selection with provenance.
The receipt's other compiler omissions are only a partial input: all remaining
compiler inputs, selected asset closure, typed target oracle, package dependencies
and destination mappings must still be declared. Ordinary target native preflight
rechecks the retained target's actual GetClass/assembly/GUID and later edits.

Subtree mapping already exists: each intake `additions` row explicitly maps its
source asset to an absent target path, preserving the incoming GUID and metadata.
The target owner chooses the subtree and fresh-plans before applying; preparation
never overwrites a same-path old root. No new adopter or YAML mapping is required.

Each native preparation phase has a 1–1200 second budget. With `--timeout 280`,
allow at least 650 seconds for the two phases, cleanup and process exit. On
failure, retain that disposable directory and logs; no successful preparation
receipt is emitted and no formal target rollback is needed. Never apply a failed
copy or repeat a successful target intake transaction. Product/visual/business
acceptance and full original behavior recovery are outside this operation.

Failure envelopes distinguish a prelaunch failure (`native: not_run`) from a
started Editor gate (`native: failed`, with owned PID/exit receipts) and an
unreaped Editor (`native: attempted_exit_pending`). Preserve those receipts.
