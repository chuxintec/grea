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

These commands use explicit paths and do not register a new shared CLI command:

```sh
PYTHONPATH=src monkey static-code-bindings prepare \
  --ir INPUT/ir.json --bindings INPUT/component-code-bindings.json \
  --code-index INPUT/code-index.json --source-root INPUT/Source \
  --output NEW_PREPARATION

PYTHONPATH=src monkey static-code-bindings stage \
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
PYTHONPATH=src monkey static-code-bindings destinations \
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

File and instance coverage are joined in both directions against the requested
Prefab scopes. Each requested file needs one apply row, one cold row and matching
current bytes/GUID; each expected instance needs one observation in each phase.
The saved Unity YAML must contain that component/local ID, its owning GameObject,
script GUID, source marker, full type/assembly identifier and disabled state.
Omitting a cold file row cannot remove its instances from validation. Missing,
duplicate, misplaced or nonexistent evidence blocks the affected destinations;
unrelated instances retain their independently verified status. Unexpected rows
remain stage diagnostics. The module command writes the ledger then exits 1 for
these structural evidence gaps. Ordinary retained source-field gaps remain a
separate partial result.

`--compatible-prepared` can explicitly admit an older preparation only when
the source manifest, complete mapping identities/proofs, fields/values and all
generated script records are identical. The only allowed difference is added
unresolved-alias diagnostics in the current preparation; removed gaps or changed
source/field evidence are refused. Each native stage retains its actual report
hash. The consumer independently retains alias gaps from the current report.

For large batches, `monkey static-code-bindings index --ledger
DESTINATIONS.json --output NEW_INDEX` writes a source-ID lookup index and
SHA-256-pinned shards. Each shard and the index stay within 4 MiB; every mapping
and destination is retained. Oversized individual mappings fail explicitly.

The public entry exits 0 for a completed requested operation, 1 when its report retains blocked/partial/not-executed mappings or evidence-contract gaps, and 2 for invalid inputs. A successful static operation does not grant source behavior, visual or adoption acceptance.

## Integration ownership

Public registration, importer main flow, version/package manifests and final
acceptance remain with their single writer. An integration can call
`prepare_from_paths`, `stage_candidate` and `record_destinations`, or register
these independent module commands. No existing export changes behavior unless
this optional stage is explicitly selected.

Native receipt schema `monkey-static-code-native/2` records the Editor PID,
UTC process start ticks and observation ticks. The cold receipt pins the exact
apply receipt bytes. Both receipts must match the requested stage, their own
phase and the project's Unity version. Cold verification requires a different
PID whose process started after the apply observation. Historical v1 receipts
remain readable and yield blocked observations under this check.
