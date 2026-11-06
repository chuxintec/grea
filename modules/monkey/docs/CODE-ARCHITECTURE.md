# Native Unity code architecture recovery

The active v0.6 workflow designs the whole source architecture before implementing native feature classes. The old per-file draft queue remains evidence and is not resumed. This workflow is still being implemented; an accepted architecture plan alone is not an implemented or compiled game.

```sh
.venv/bin/python -m monkey.cli code-architecture-prepare \
  --candidate /absolute/frozen/UnityProject --expected-manifest SHA256 \
  --namespace Game --out /absolute/new/ArchitectureStage
.venv/bin/python -m monkey.cli code-architecture-run --run /absolute/new/ArchitectureStage
.venv/bin/python -m monkey.cli code-architecture-status --run /absolute/new/ArchitectureStage
```

Preparation consumes the existing package source index and complete original scripts. Registered regions and every complementary source range receive an explicit source-unit identity. Indexed functions, methods and fields retain exact source spans and hashes; large member catalogs are sharded without discarding records. Actual JSON configurations are included within the bounded input budget, with omissions explicitly identified. Native Prefab/Scene identities and script bindings accompany the catalog. This does not reexport resources or execute original game code.

The global task uses the existing Codex configuration, serial lock and checkpoint runner. It rewrites one planned architecture seed, while all source context stays immutable. The [contract](CODE-ARCHITECTURE-CONTRACT.md) binds semantic classes, responsibilities, typed members, state owners, lifecycle, class and layer dependencies, source dispositions and planned integration chains. Source coverage is a routing statement, not proof of restored behavior. If interrupted, `code-architecture-run --session EXACT_UUID --run ...` can resume only the recorded checkpoint within its cumulative budget.

Next stages generate native assemblies and module tasks, implement the source-backed classes, and integrate the complete candidate. Domain and Gameplay stay independent of Unity; Presentation calls Gameplay, Services implement its ports, and Bootstrap composes all layers. Source fragments are not runtime objects or a JS/Cocos compatibility engine. Existing implementations, native adaptations and unknown source behavior must remain distinguishable. Whole-project compilation and real JSON/resource-to-view-to-rule-to-state feedback are separate pending gates.

After a designed architecture is accepted, `code-native-prepare --architecture STAGE --out NEW_PIPELINE` prepares every module. `code-native-run --run NEW_PIPELINE` executes them serially, resumes precise saved checkpoints, pins their outputs, and assembles an isolated Unity candidate. `code-native-status --run NEW_PIPELINE` reads progress. Existing native layout helpers and package assembly references require explicit retained paths/reference input; old anonymous drafts do not enter the production code directories. Module output remains unreviewed, incomplete classes remain explicit, and the assembled candidate is unvalidated until whole-project compilation and real cross-layer integration run.

The pipeline aggregate records `partial` and an explicit semantic-review limitation even when every planned source ID is mapped. Source coverage alone does not prove implementation. If collection or assembly fails, the supervisor preserves terminal module receipts, records `blocked` with the actual error code, and clears `activeModule`; it does not report a running model. Keep the failed aggregate as evidence and use `code-native-reassemble` with a fresh output to recheck the terminal results without another model call.

Core configuration, transactions, input and Bootstrap should be integrated before peripheral feature generation finishes. If an existing schedule puts these last, let its active worker finish and stop the supervisor at a safe boundary, then prepare a new schedule:

```sh
.venv/bin/python -m monkey.cli code-native-continue --run STOPPED_PIPELINE \
  --out NEW_PIPELINE --priority Content --priority Orders --priority Bootstrap \
  --stop-after Bootstrap
.venv/bin/python -m monkey.cli code-native-run --run NEW_PIPELINE
.venv/bin/python -m monkey.cli code-native-reassemble --run NEW_PIPELINE \
  --out NEW_CHECKPOINT --allow-incomplete
```

Continuation pins the predecessor request/state and reuses terminal module receipts in place, without copying source contexts, changing old requests, or repeating their model calls. Every unfinished module remains scheduled; priorities change execution order, not scope. `--stop-after` returns `integration_checkpoint` only after that module finishes naturally. A later `code-native-run` continues the remaining modules. Explicit incomplete reassembly requires a stopped supervisor, records unfinished classes as missing and creates no placeholder types. It produces an unvalidated integration candidate, not a complete or compiled game. Mutated reused receipts or predecessor state are rejected.

A finalized model plan can be checked again with `code-architecture-recheck --run STAGE` after validator repairs without a model call. Architecture JSON may use the existing 16MiB worker output bound; normal source/context files keep their 8MiB limit. Accepted model payload bytes are preserved exactly. Module contexts shard the complete architecture by module, retaining all class records and global coverage/chain metadata. `code-architecture-refine --run OLD_STAGE --out NEW_STAGE` prepares a bounded consistency repair with the previous exact model payload, immutable original context, recorded diagnostics and lineage; it never overwrites the previous result or marks ownership inconsistencies as recovered behavior.
