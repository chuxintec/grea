# Maintainer responsibilities

The release maintainer owns shared CLI contracts, transaction boundaries, native integration and release artifacts. Module contributors own explicitly assigned, disjoint implementation paths. Original project data and private validation records are not part of the distribution.

Current approved local P0 modules (shared source baseline e0c7e0c):

| Module | Agent | Requested model | Observed configuration | Owned files | State |
| --- | --- | --- | --- | --- | --- |
| Structure audit and move plan | /root/structure_audit | gpt-6-luna / high | spawn accepted; runtime identity not independently probed | structure_audit.py, test_structure_audit.py, STRUCTURE-AUDIT.md | integrated; 32 targeted checks including consumer regressions |
| Build resource filter | /root/build_filter | gpt-6-luna / high | spawn accepted; runtime identity not independently probed | build_filter.py, BeaverBuildFilter.cs, test_build_filter.py, BUILD-FILTER.md | integrated; 10 targeted checks and actual native collection |
| Guarded folder moves | /root/folder_moves | gpt-6-luna / high | spawn accepted; runtime identity not independently probed | unity.py, BeaverNative.cs, test_folder_moves.py, test_retirement.py, FOLDER-MOVES.md, RETIREMENT.md | integrated; folder forward/reverse and native retirement/recovery/reopen verified |
| Readback/capture and shared integration | /root | existing primary configuration | unchanged | CLI, native runner/companion, shared docs/plan/package | integrated; native readback/capture verified |

The primary is the only Editor/desktop/shared-contract writer. Modules do not recursively delegate. Formal package installation and released artifacts are unchanged. Production-project adoption is separately recorded. Module policy and necessary peer communication follow the workspace's current governing standards.
