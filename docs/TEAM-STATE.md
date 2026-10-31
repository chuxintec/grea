# Maintainer responsibilities

The release maintainer owns shared CLI contracts, transaction boundaries, native integration and release artifacts. Module contributors own explicitly assigned, disjoint implementation paths. Original project data and private validation records are not part of the distribution.

Current approved local P0 modules (shared source baseline e0c7e0c):

| Module | Agent | Requested model | Observed configuration | Owned files | State |
| --- | --- | --- | --- | --- | --- |
| Structure audit and move plan | /root/structure_audit | gpt-6-luna / high | spawn accepted; runtime identity not independently probed | structure_audit.py, test_structure_audit.py, STRUCTURE-AUDIT.md | integrated; 43 targeted checks including namespace and reviewed-comparison regressions |
| Build resource filter | /root/build_filter | gpt-6-luna / high | spawn accepted; runtime identity not independently probed | build_filter.py, BeaverBuildFilter.cs, test_build_filter.py, BUILD-FILTER.md | integrated; 16 targeted checks and actual partial native collection |
| Guarded folder moves | /root/folder_moves | gpt-6-luna / high | spawn accepted; runtime identity not independently probed | unity.py, BeaverNative.cs, test_folder_moves.py, test_retirement.py, FOLDER-MOVES.md, RETIREMENT.md | integrated; folder forward/reverse and native retirement/recovery/reopen verified |
| Readback/capture and shared integration | /root | existing primary configuration | unchanged | CLI, native runner/companion, shared docs/plan/package | integrated; native readback/capture verified |

The primary is the only Editor/desktop/shared-contract writer. Modules do not recursively delegate. Formal package installation and released artifacts are unchanged. Production-project adoption is separately recorded. Module policy and necessary peer communication follow the workspace's current governing standards.

Fix6 execution modules are integrated: explicit source-evidence-only retirement (folder contributor) and exact scene BuildSettings handling (structure contributor). The parent completed isolated native validation and package sealing: 166 affected/shared checks, exact Scene settings apply/reopen/recovery, ordinary batch compatibility and both native retirement modes. Immutable fix5 excludes these modules.

Fix7 necessary gap: `/root/empty_folders` (requested gpt-6-luna/high; spawn accepted, runtime identity not independently probed) owns unity.py, BeaverNative.cs, retirement schema/docs and empty-folder tests. Parent owns shared CLI/version/docs, private fixtures, Editor and candidate sealing. Baseline c1d80d96; no recursive delegation or game-project writes.

Fix7 integrated and natively verified by parent: two empty-folder roundtrips with real DefaultAsset IDs, binary reference refusal and directory drift guards; ordinary file/source-only native retirement compatibility reverified. Parent added portable destination-name preflight to batch/unity moves. 177 affected/shared checks passed. Final runtime producer `b889a59214782d6bcc442a53156150d9729a24d18a2e9349f468e85dcba5725c`; existing fix6/earlier candidates and game transactions unchanged. Large-batch checkpoint/hash cost remains a separately recorded limitation, not optimized in this candidate.

Fix8: `/root/bulk_identity` (requested gpt-6-luna/high, spawn accepted; runtime identity not independently probed) owns build_filter.py/BeaverBuildFilter.cs/tests/BUILD-FILTER.md/collect schema. Reused `/root/empty_folders` owns batch.py/BeaverBatch.cs/checkpoint tests and MOVE-CHECKPOINTS.md. Parent owns shared version/CLI/PLAN/contracts, private fault and bulk fixtures, sole Editor and sealing. Baseline 5b765ebecaaf1fa8fe794f001483e2a29c55c123; no recursion or game writes.

Fix8 modules integrated and frozen. Parent final installed native verification passed complete bulk identities, actual partial/source-only compatibility, default vs opt-in 128-step comparison, independent bulk reopen and failure/recovery matrix. 188 affected/shared checks passed. Final producer `6e81b67b87a3b5fd4d965dbe952672ca99c9e4149a678863c39f3706165211f3`; no game writes, formal lock/install or remote changes. Prior trial evidence remains separate.

Fix9 duplicate-name owner selector: parent sole writer for native_readback.py, BeaverReadback.cs, request schema, tests, shared docs/version and private Editor fixtures. No subagent needed for this single critical path. Fixed fix8 and in-flight transactions remain immutable.

Fix9 parent implementation and final installed native validation complete: exact duplicate prefab/scene owner selection, large/negative signed64 IDs, no-fallback negatives, three independent request runs plus negative-subasset probe; 193 checks. Producer `554075acb4960db076c49c60e26b39c427c37c0029aac5f2f30dc6f49cbd13eb`. No adoption changes or game writes.
