# Development branch integration — 2026-10-29

All local branch tips and the fetched remote main are already ancestors of the starting target commit `57613e78f66a1c4685e748827983827c77922d36`. No divergent commits or merge conflicts exist. Existing consolidation commits remain authoritative; retired implementations are not restored. Source branches and the historical worktree are retained.

| Ref | SHA | Disposition |
| --- | --- | --- |
| `refs/heads/codex/full-project-handoff` | `7eab3bae551399cb77b76f05c208dcf06d1aee2c` | Already contained (0 unique commits) |
| `refs/heads/codex/game-adoption-fixes` | `3c69ba588beb189c810417ebc2aa78d13c9b9ad0` | Already contained (0 unique commits) |
| `refs/heads/codex/native-layout-production-fix` | `eb91533ad5a283cc3917fc9191f11013af116797` | Already contained (0 unique commits) |
| `refs/heads/codex/unity-model101-102-20261028` | `363f980107b4e7bda37eab85b6c2aaf2ccdd212d` | Already contained (0 unique commits) |
| `refs/heads/codex/unity-selected-texture-export-20261028` | `a55595c671980d34b01e49f46f6d392d205bd808` | Already contained (0 unique commits) |
| `refs/heads/codex/unity-shader-handoff-p0-20261028` | `57613e78f66a1c4685e748827983827c77922d36` | Already contained (0 unique commits) |
| `refs/heads/codex/unity-sprite-atlas-flip-20261028` | `b229b35b4c3a8f42280074959d141de901e1c1f1` | Already contained (0 unique commits) |
| `refs/heads/codex/unity-texture-selection-20261028` | `ed867bdb00c7256c32a585466ec51a685dd41ff6` | Already contained (0 unique commits) |
| `refs/heads/codex/v0.2` | `c79befafad597e9e3a93cbd9cf3e44c750ff9d99` | Already contained (0 unique commits) |
| `refs/heads/codex/v0.4.1-grea-toolkit` | `8160d9237e51bc343b4e14e72d2ff866886d06eb` | Already contained (0 unique commits) |
| `refs/heads/codex/v0.6-csharp-recovery` | `e222f69d1ba99c8b8cba5ea4f854b93ed497c2ba` | Already contained (0 unique commits) |
| `refs/heads/codex/v0.7-prefab-recovery` | `57613e78f66a1c4685e748827983827c77922d36` | Already contained (0 unique commits) |
| `refs/heads/main` | `ff57c75fdf5c456e279460889fe6e1cdf7cd2aa5` | Already contained (0 unique commits) |
| `refs/heads/monkey` | `36e9d6dcf05f1e291812b438a81ff0dec5bc9773` | Already contained (0 unique commits) |
| `refs/remotes/origin/main` | `ff57c75fdf5c456e279460889fe6e1cdf7cd2aa5` | Already contained (0 unique commits) |

The uncommitted v0.7 work was preserved before integration, then incorporated with static-first acceptance criteria, native helper packaging and an updated native Prefab test fixture. Private sources, native candidates, raw logs and recovery backups remain outside the public tree.

Validation: 106 Prefab, 37 native, 18 package, 14 animation and 22 integration tests passed (197 total); the Creator Spine material bridge synthetic check passed. A local wheel contains all native helper resources, including pure-expression lowering helpers. These checks do not claim complete static or dynamic core Prefab acceptance.

Publication is limited to `codex/v0.7-prefab-recovery`; main, tags, releases and shared installations remain unchanged. The precise push receipt is retained locally.
