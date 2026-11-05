# Inert custom-script binding stage

`monkey.static_code_bindings` is an optional, independently callable recovery
stage. It generates source-bound static MonoBehaviours and installs them through
Unity Editor APIs in a new candidate clone. It does not compile approximate C#
drafts, translate methods, invoke a model, execute original JavaScript or enable
business callbacks. Native persistence and gameplay acceptance remain separate.

## Inputs and identities

The preparation inputs are the normalized IR, `component-code-bindings.json`,
`code-index.json`, and the original source snapshot root. Each mapping must join
exactly one module, its RF literal name/identity, exact source byte range/hash,
source component, owning asset and node. Ambiguous or missing mappings are
retained as blocked rows. Every original binding row remains in the denominator.

The existing pinned Acorn declaration parser supplies inherited decorated
defaults; exact serialized overrides win. The existing static carrier generator
owns primitive, array, record, color and reference encoding. Declaration gaps,
unknown aliases and unsupported data remain explicit. A script with no proven
static fields is blocked; an empty class is not counted as recovery.

Named types live below
`Assets/Game/Scripts/Presentation/Recovered/StaticFields/Code/`. Their namespace
and metadata GUID derive from the exact code region and field schema, excluding
instance values. Same-named source modules remain distinct. Different instance
schemas may require multiple types; source module and target type counts need
not agree. The original field names are retained in each field plan; generated
serialized slots use the existing carrier's safe field names. Components stay
disabled and contain no lifecycle methods.

## Independent commands

The public `monkey static-code-bindings` entry uses explicit paths; the module entry remains compatible. These operations do not launch an Editor:

```sh
monkey static-code-bindings prepare \
  --ir INPUT/ir.json --bindings INPUT/component-code-bindings.json \
  --code-index INPUT/code-index.json --source-root INPUT/Source \
  --output NEW_PREPARATION

monkey static-code-bindings stage \
  --source SAVED_UNITY_CANDIDATE --prepared NEW_PREPARATION \
  --output NEW_UNITY_CANDIDATE --stage-id example-01 --compile-all-types
```

`--code-region` may be repeated to limit an initial trial. The clone excludes
Library/Temp/Logs and preserves source Prefab bytes and GUID pins. The optional
Editor helper is installed beside the existing importer, without modifying the
shared `UnityImporter.cs` or its plan file. Existing generic carriers remain as
explicit source-data evidence; the named component is an additional static
representation, not an assertion of original business behavior.

The orchestrator must acquire its native resource slot around each complete
apply/cold pair. Execute `MonkeyImporter.StaticCodeApply`, close Unity, and run
`MonkeyImporter.StaticCodeCold` in a fresh Editor process on that same clone.
The helper verifies source plan, report, selected mapping, script and Prefab
pins. Before attachment it requires the original source carrier on the exact
mapped node. A template carrier is accepted only with its declared template ID
and actual native corresponding-source object. Missing or duplicate owners fail.

Creation and assignment reuse `UnityStaticFields.Create/Assign/Read` and the
existing static reference resolver. Saved and cold observations record script
GUID, full type, assembly, source component/node, original owner proof, physical
Prefab/GO/component identities, actual fields and persistent reference IDs.
Cold reads do not create or assign components. The producer compares each
identity to its saved observation. Disposable negative controls cover wrong
node/type, another instance of the same type, missing/wrong reference and
duplicate instance. A reference control must introduce its own new field-level
failure; an unrelated preexisting gap cannot satisfy the control.

```sh
monkey static-code-bindings destinations \
  --prepared NEW_PREPARATION --candidate NEW_UNITY_CANDIDATE \
  --output NEW_DESTINATIONS.json
```

Repeat `--candidate` to join independently executed batches. The consumer checks
request/report pins, unchanged mappings, save-to-cold physical identities,
controls and field observations. It emits every source row as `success`,
`partial`, `blocked` or `not_executed`, retaining every observed destination and
its hashed evidence. Partial fields and missing references never become full
static success. `success` is limited to static persistence and carries
`sourceBehaviorExecuted=false`; it grants no visual, gameplay or adoption pass.

The public entry exits 0 for a completed requested operation, 1 when its report retains blocked/partial/not-executed mappings, and 2 for invalid inputs. A successful static operation does not grant source behavior, visual or adoption acceptance.

## Integration ownership

Public registration, importer main flow, version/package manifests and final
acceptance remain with their single writer. An integration can call
`prepare_from_paths`, `stage_candidate` and `record_destinations`, or register
these independent module commands. No existing export changes behavior unless
this optional stage is explicitly selected.
