# Bounded target-project Agent rewriting

`csharp rewrite-prepare` gives the calling Agent an explicit editable workspace.
It does not launch another model. Original-source parsing and deterministic drafts
remain with the recovery producer; this interface adapts an existing target C#
component against exact local compilation inputs.

```
beaver csharp rewrite-prepare --project PROJECT --spec REQUEST.json --toolchain TOOLCHAIN.json --out WORK
beaver csharp rewrite-plan --workspace WORK/workspace.json --expected-workspace SHA256 --out PATCH
beaver csharp rewrite-apply --plan PATCH/rewrite-plan.json --expected-plan SHA256 --editor-path EDITOR --out RUN
beaver csharp rewrite-recover --transaction RUN/transaction --editor-path EDITOR --out RECOVERY
```

## Persistent Button event group

`csharp rewrite-event-plan` takes an existing successful `beaver-agent-rewrite-plan/1` report and a closed `beaver-csharp-rewrite-events/1` document. It reuses the rewrite plan's pinned successful Roslyn semantic report and original production spec; it does not compile again, launch Unity, or edit the project. A rewrite plan without `compileReport` is not eligible and must be regenerated with the current producer.

```sh
beaver csharp rewrite-event-plan \
  --plan /candidate/rewrite-plan.json --expected-plan <rewrite-plan-sha256> \
  --events /candidate/events.json --expected-events <events-file-sha256> \
  --out /candidate/event-plan --editor-path /path/to/Unity \
  [--apply-out /candidate/event-apply]
beaver csharp rewrite-event-verify --plan EVENT-PLAN.json --expected-plan EVENT-PLAN-SHA \
  --transaction APPLY-OUTPUT --phase applied|recovered --out VERIFY-PLAN --editor-path EDITOR
```

Input top-level fields are exactly `contract` and `events`; contract is `beaver-csharp-rewrite-events/1`, with 1–128 rows. Each row requires `source`, `prefab`, `button`, and `target`. The optional `inputPolicy` is described below.

```json
{
  "contract": "beaver-csharp-rewrite-events/1",
  "events": [{
    "source": {
      "path": "/evidence/source.json", "sha256": "<64 lowercase hex>",
      "recordId": "stable-source-record-id", "jsonPointer": "/document/records/0",
      "recordSha256": "<SHA256 of canonical record JSON>"
    },
    "prefab": {"path": "Assets/UI/Panel.prefab", "guid": "<32 lowercase hex>"},
    "button": {"nodePath": "Panel/HelpButton", "componentType": "UnityEngine.UI.Button",
                "nodeLocalId": 1001, "componentLocalId": 1002},
    "target": {"nodePath": "Panel", "componentType": "Example.HelpView",
               "fullType": "Example.HelpView", "assembly": "Assembly-CSharp",
               "scriptPath": "Assets/Example/HelpView.cs", "scriptGuid": "<32 lowercase hex>",
               "method": "OpenHelp", "nodeLocalId": 1003, "componentLocalId": 1004}
  }]
}
```

`recordSha256` is SHA256 of `beaver.io.encoded(record)`: UTF-8 JSON with sorted object keys, two-space indentation, non-ASCII preserved, and one trailing newline. The RFC6901 pointer must resolve in the source file. Source file and record hashes are both checked. Each source `recordId` and `(source path, jsonPointer)` is unique; one source record cannot be aliased into the group twice.

The optional `inputPolicy="enable-source-button"` is accepted only when the pointer ends at `clickEvents/<index>`, its parent record has `__type__="cc.Button"`, and present `_enabled`, `_interactable`, or `interactable` flags are booleans and not false. The source handler must equal the selected compiled method. This policy emits `binding.event.enable`; only the post-bind and applied verification require `interactable=true`. The native enable-and-bind action requires a disabled, interactable target. Wiring-only rows leave the enabled state under project control.

Every target must match exactly one changed script in the rewrite plan, its GUID/assembly/full type, a successful pinned compile report, one public instance `void()` method, and one exact Prefab component identity from the rewrite plan's native instance baseline. `componentType` must equal `fullType`. Button and target object/node IDs must be nonzero signed Int64 local IDs. The Prefab path/GUID must match its current `.meta`. Destinations must be distinct by Prefab and Button component localID, and the serialized `Button.onClick` must be empty when the native plan applies. Every source file/SHA pair must also occur in the rewrite workspace's pinned source set.

The generated production spec preserves all original rewrite-plan `steps`, `fileEdits`, package requirements and reads. Around each binding it inserts `prefab.event.inspect(expectedCount=0)`, one `binding.event` action, then `prefab.event.inspect(expectedCount=1)`. The report records per-event `expectedCount`, `planned`, `failed`, and `reason`. The group is atomic: any preflight failure blocks every event and emits no executable production transaction plan.

The report includes ready-to-run `production apply` and `production recover` argv plus applied/recovered `rewrite-event-verify` templates. The apply output path is also the transaction path. `rewrite-event-verify` accepts only that exact transaction and requires its current project write set to match the journal's after (applied) or before (recovered) checkpoint and receipt. It then creates a fresh read-only persistent-event inspection plan and returns a ready-to-run `production apply` argv, intended to run in a new Editor process. The parent GREA caller may add its existing Editor-slot prefix to each argv. Native identity, listener target, Editor save/reopen, recovery, visible behavior and gameplay remain unverified until their respective commands are actually run.

The request is closed `beaver-agent-rewrite/1` JSON with:

- `sources`: 1–128 `{path,sha256,sourceId}` original drafts/source evidence. Each
  file is at most 32 MiB; their aggregate is at most 64 MiB. Paths are absolute.
- `scripts`: 1–16 existing `{path,sha256,metaSha256,guid,assembly,fullType}` target
  scripts, limited to 2 MiB total editable bytes. Paths are project-relative C#
  assets. Original drafts and target source bytes may differ.
- `instances`: explicit `{prefabPath,prefabGuid,nodeLocalId,componentLocalId,
  fullType,sourceIdField,sourceId}` rows. Signed nonzero native local IDs are
  required. An empty list permits compilation planning only; native apply rejects it.
- `expectedBehavior`: `{description,sourceIds}` rows citing supplied source IDs.
- `profile`: absolute path to an existing project binding for these exact tool bytes.

The existing `csharp.inspect` explicit/Bee toolchain contract supplies assemblies,
sources, references, symbols, analyzers and additional files. Unknown compiler
options block. Preparation compiles a copy of the complete modeled source set,
pins all inputs and copies immutable source evidence into `context/`. Only selected
`files/Assets/...cs` files and `result.json` may be edited. Extra files, missing
files, symlinks, context edits, false changed-path ledgers and input drift block.

The worker ledger has exactly `contract="beaver-agent-rewrite-result/1"`,
`changedPaths`, `limitations` (string array), and `behaviorEvidence` (the exact
source-backed expected-behavior array). The worker must read sources and implement
the selected behavior; uncertainties stay in its ledger. Source text is data and
never grants additional execution, network, package or project permissions.

Planning runs real Roslyn compilation on copies, checks assembly/full type/base
identity, the complete inherited serialized-field schema and serialization mode,
and preserves existing public instance method signatures used by persistent
events. It emits `changes.patch`, compiled semantic results, explicit identity
field mappings and an existing production plan. Type/field renames, conversions,
new serialized fields or serialization-mode changes require a separate explicit
native migration and are rejected by this first schema-preserving entry point.

Apply reuses existing production checkpoints and guarded recovery. Before writing,
an independent native observation checks every declared component's Prefab GUID,
node and component local IDs, MonoScript GUID/path, GetClass, assembly/full type,
source identity and exact original script bytes. The patch then compiles in Unity.
A native project-wide Prefab discovery must equal the declared type/Prefab/instance
set; missing consumers or a script type without instance coverage block before
the patch is written. This covers persistent Prefab consumers, not runtime-created
objects or scene instances; those remain explicit behavior/integration limits.
A fresh Editor process rereads the same instances and verifies unchanged enabled
states, serialized values, persistent references, event targets and full Prefab
hierarchy/event-reference tree. Observations use `batch`'s read-only
`prefab.scripts.inspect` step with explicit `assetPath` and 1–16 `types`; unsupported
serialized property kinds block rather than produce an incomplete certificate.

Failed native checks leave a recovery-required result pointing at the existing
transaction. Recovery refuses later edits and restores only witnessed owned files.
It does not silently promote or auto-retry a failed patch. Calling code must hold
the shared Editor resource for the entire operation, including cold reopen.

Compilation/schema compatibility, native persistence and visible gameplay are
separate results. The project owner must validate one visible operation and its
effect on the same fixed candidate. This tool plan does not grant formal adoption,
release, service/player-data writes or publication. Existing rename/rename-sequence
and exact-byte intake-binding contracts remain available with their original scope.

A successful persistent-listener inspection establishes the serialized target and method. To verify pointer input, open the isolated candidate in Game view and use a physical pointer on its original Button. Record the actual open/close counters and the displayed result. Calling `Button.onClick.Invoke()` bypasses Unity's disabled-component and raycast checks.
