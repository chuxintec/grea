# Architecture module asset context

`monkey.code_architecture_asset_context.build_asset_context(stage, module_classes, *, cache_root=None)` builds a compact, read-only evidence bridge for one architecture module. `stage` is the validated result of the module workflow's `_pin_stage`; `module_classes` are the exact class records selected from its accepted architecture plan. The helper returns `{context, cache}`. `write_module_context(...)` keeps the legacy `Evidence/module-asset-bindings.json` document unchanged when it is at most 8 MiB. For larger contexts, that same path contains a `monkey-code-architecture-asset-context-index/1` index and its complete collection rows are stored in listed `module-asset-bindings.shards/*.json` files. Every shard is at most 8 MiB; no row is truncated or split. The complete indexed payload and all module worker context files together remain within the worker's 64 MiB context budget.

The index records the original full-context SHA-256 and byte count, source/architecture identities, collection row counts, and each shard's relative path, SHA-256, byte count, kind, ordinal, and row count. `load_module_context(index_path)` verifies the index and all listed shard bytes, rejects missing, reordered, altered, oversized, or incomplete shards, rebuilds the original object, and checks that its canonical encoded bytes exactly match the full-context hash and size. It also reads legacy single-file reports. Consumers must load the index and every listed shard before treating the context as complete.

The helper follows exact ownership in this order: class `sourceUnitIds` → catalog units' exact `sourceIds` → frozen `Analysis/Code/component-code-bindings.json` `codeRegion` → candidate-owned `Analysis/Mappings/source-map.json`, `cocos-assets.json`, `resource-paths.json`, and `Analysis/Readback/editor-readback.json`. Each mapping's bytes and SHA-256 are checked against Candidate07's `manifest.json`; the global component-binding bytes are checked against the global worker context pin and, when present, the candidate inventory. The large editor readback is parsed only to a compact index of source prefab identities/nodes and `viewReferences`, never forwarded wholesale. A reusable compact mapping index may be stored outside the candidate under `cache_root`; its filename includes the source manifest hash and it is discarded/rebuilt when its sidecar, schema, manifest pin, or mapping pins differ.

An exact `resource-paths` row plus an owned `.prefab`/`.unity` file, owned `.meta` GUID, and matching editor-readback `sourcePrefabs` path/GUID establishes the source prefab/scene identity. Readback nodes supply exact source-node hierarchy and component-type evidence. A matching `viewReferences` row can additionally provide a local `prefabFileId`, but it targets the editable preview prefab named by `source-map`, not the original source prefab; the helper verifies its GUID and YAML object declaration and labels it `verified-preview-object-reference-only`. That ID is never reused as the source prefab's localID, and `serializedReference` remains `null` until a typed native reference is actually serialized for the intended asset. Missing, ambiguous, or drifted evidence is reported or rejected; target paths are never derived from names.

The module task includes this bounded report with the source/config evidence. It is authoring and serialization context only. Source UUIDs must not be looked up at runtime; implementation should use typed serialized native references. Shared source units can be referenced by multiple planned classes, so `classesWithThisSourceUnit` records that catalog relation but does not assert direct class-to-node ownership. An `assetBindingContext` manifest entry does not mean this module wrote or verified a new Editor reference. No Editor, game runtime, or original JavaScript is run by this module.

## API example

```python
from monkey.code_architecture_modules import _pin_stage
from monkey.code_architecture_asset_context import write_module_context

stage = _pin_stage(global_architecture_directory)
classes = [row for row in stage['plan']['classes'] if row['module'] == module_id]
summary = write_module_context(stage, classes, evidence_directory, context_file_pins,
                               cache_root=private_asset_index_directory)
```

The module workflow calls this helper during `prepare`, stores the context-file pins in `request.json`, and records `assetBindingContext` in its module manifest. For a sharded report, the root path's `sha256`/`bytes` identify the index file; `contextSha256`/`contextBytes` identify the fully reconstructed report. Each shard is separately included in the worker context pin list. Context evidence stays source-pinned; missing localIDs remain explicit follow-up work for typed serialization and later Editor verification.
