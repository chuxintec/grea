# monkey 技术上下文与历史

当前开发任务和v1.1验收唯一入口：[GREA lifecycle-roadmap](/Users/wangmeng/MyProjects/Tools/grea/proposals/lifecycle-roadmap.md)，由GREA负责人单写。monkey保留仓库、0.8.0实现版本、会话及代码单写，不再维护独立未完待办或开发release列表。

- 肥鹅四页工具实现、实际原生结果与采用：`grea:T-foodstreet-four-activity-bulk`。
- 肥鹅四页收口后僵尸全量有源Prefab转换与采用：`grea:T-zombie-bulk-static-prefabs`。
- 二进制模块工作：`grea:T-binary-provider-macos`，保留当前用户后置/暂停约束。

2026-11-04实际任务源迁移：已从下方结构化视图删除三个未完task和未完dev8 release；已完成历史仍保留。旧ID→GREA ID、原输入/消费者/阻塞摘要与原文SHA见 `.private/unified-task-source-20261104/handoff-index.json`；这不是将未完产品任务标done/cancelled。

当前技术交付记录：dev11加入固定plan/文件清单/IR/源清单的不可变组件族续接，复用t=0材质、禁用态Animation与非渲染Spine静态载体；100项聚焦检查及108源文件离线C#引用编译通过。Spine 75组件/18数据/18原始ASTC页只读来源核验完成，未解码、未恢复渲染/播放。实际续接、Unity保存重开、冻结及beaver采用由GREA唯一调用；本文不另建验收待办。

## 已完成交付及技术历史

以下为历史来源与已完成技术记录，旧的Current/Next/待验措辞均为当时快照，不再构成独立当前任务或开发发布计划。

Unified0.8.0.dev9 source integration complete (2026-11-04): merge retains all prior Unity-source recovery/profiles/CLI/package resources and includes the fixed Cocos Toggle null-spec bridge, request-pinned CoreText static fallback policy, source-font prepare/generate CLI, and absent retained-asset contract schema guard.179 Unity-focused pytest checks pass;75 Cocos/font/static-field/common-CLI checks pass with1 optional environment probe skip (groups overlap, not a combined unique total). No new Editor/Swift/binary run. Prior real GREA actual03 produced11Prefabs/668nodes/0missingScripts but partial static refs; actual04 exposed unavailable Unity font family. New source lets GREA alone regenerate/import with exact identities; missing Spine/Animation/custom materials remain explicit gaps. The merge histories retain both old branches; single current v0.8.0.dev9 head/default replaces all previous heads after exact remote verification, tags/fixed bytes remain unchanged.

2026-11-04 latest user override human01a1a68e-cacd-79f1-a284-b10ddae38551, natively verified in GREA chat: consolidate monkey into the single v0.8.0 series; no new v0.7 iteration. Preserve prior fixed Cocos/Unity artifacts and tags. Integrate Toggle/font commits through a87dde2 and current strict static-reference null-contract fix into next v0.8.0.dev9, keep Unity-source recovery, run affected checks, then migrate default and retire covered prior heads. Root tracked PLAN/TEAM WIP is checkpointed before isolated detached integration; opaque .codex remains untouched. GREA alone runs actual four-page import/adoption.

2026-11-04 branch cleanup completed under natively verified human01a1a685/67a/67c: local18heads→3 and remote3oldheads retired after new exact heads verified; default v0.7.0, retained v0.7.0@86d47f35744a/v0.7.1.dev3@a87dde2c2725/v0.8.0.dev8@203161f122b4. All old heads ancestors of retained history;5 worktrees HEAD/index/trackedWIP unchanged and alltags unchanged. Paused binary and historicalv0.4.1 worktrees retained detached; no publication/protection relaxation. Source .private/repository-cleanup-20261104/result.json. Current fontdev3 resolves explicit fallback-static policy vs Unity unavailable-family actual04;35checks pass, actual static generation/native rerun is GREA-owned. Static ref module now has native21ArgumentNullException failures matching absent staticRetainedAssets phantom Contract before resource routes; schema guard under module single-writer.

2026-11-04 GREA actual-native03-toggle (fixed0da189a) exited0 and saved11 business Prefabs/668nodes, missingScripts0, sceneReopened/editableRoundtrip true; adoption/visual not_run, acceptance partial with311 STATIC_FIELD_NATIVE_MISMATCH. Fixed0.7.1.dev2 source9ee0f95 exposes prepare/generate-source-system-fonts;32 focused checks pass, package-owned Swift unchanged. Frozen source snapshot and52-label actual02 request delivered in .private/foodstreet-four-activity-20261104/source-system-font-dev2-handoff.json; GREA alone runs actual preparation/generation/plan/export/native-import. Legacy font fixture tests unavailable in isolated worktree (3errors/3failures) are excluded from pass count. Next task fixes generic static carrier/ref assignment/readback; no business script expansion or page edits.

2026-11-04 Foodstreet priority: binary work paused_by_user; fixed v0.8 dev8 two-root public CLI handoff is complete (dev8-fixed-two-root-handoff-index.json), adoption remains GREA-owned. GREA is the sole Foodstreet actual convert/native-import caller. Current actual02 failed at896/903 components with missing_toggle_spec despite zero source Toggles: JSON null Spec was materialized by Unity. Isolated stable-line worktree .private/worktrees/cocos-system-font-v071 commit0da189a (0.7.1.dev1) fixes explicit presence/source-type gating in creation and saved readback, preserving missing-spec strict refusal.16 focused checks pass including1 optional skip; fixed source and runnable argv delivered to GREA. No monkey Editor/duplicate batch. Next module exposes existing pinned system-font resolver/SDF preparation;52 system labels/47 dependent outlines remain separate. No publication/global upgrade/game writes.

# monkey 技术交付历史（非当前任务源）

## Full-parent native continuation — 2026-11-04

Original BattleMain still fails strict native reconstruction (Native11,13,14 retained). CopySerialized source-state preservation passes the two real-source UV-only save/cold fixtures; it does not accept the full root. The complete imported-particle audit covers19 particles/37,730 non-reference fields across BattleMain and an independent progress-effect root: only38 differences, source CollisionModule.m_Bounce scalar/minScalar1 versus native provider0, with CollisionModule disabled. Per-leaf scalar restoration repopulates empty curves. Bulk JSON probes are diagnostic only, not an accepted mapping. Native public-API probe12 completed two-source save/independent cold: Constant=1 uses two native default zero-value keys, raw scalar1/minScalar0, while UV arrays stay empty. The earlier proposed scalar0/key1 signature mixed two experiments and was wrong; no production mapping was adopted. Corrected full signatures passed saved and independent cold in two sources,8Prefab/meta files unchanged. Revised ruling by GREA lead remains pending before any production mapping; no resource window is reserved. Related Python checks73pass. No fixeddev8, consumer switch, source mutation or new publication.

Source inventory join is complete:161 exact roots,10 matched through existing source/native identities and adopted GUIDs;151 source-parsed only. Index `.private/unity-prefab-v080-20261104/source-prefab-inventory-with-adoption-02.json`. Original10roots/59pairs are reused and not revalidated.

## GREA internal-module routing — 2026-11-04

Ordinary assignments, bounded technical rulings and candidate/consumer coordination now go through the GREA lead. monkey remains the single recovery-source writer and continues this v0.8 task in the existing repository/session; no WIP or fixed identity moved. The standalone repository is now private; external distribution is unified under GREA. A later explicit human decision switches new module distribution to binaries; the earlier complete-module-source choice is superseded, and old copies/licences are not revoked. No independent monkey publication is authorized. Historical v0.7 publication receipts remain unchanged.

The wrong earlier Bounce target signature was withdrawn before implementation. Corrected v2 ruling and native-window coordination were handed to GREA with the exact current consumer/fixed-candidate/evidence index `.private/unity-prefab-v080-20261104/grea-lead-handoff-index.json`. The existing Foodstreet resource request stays in flight; no duplicate dispatch or ACK dependency.

## Dev8 source checkpoint — 2026-11-04

Corrected GREA-ratified Bounce v2 profile, unchanged original source/explicit target mapping and exact native signature/public evaluations are integrated. Native SDK-driven RectTransform serialization now clears scene drivers while inactive, restores planned scalar values, saves through Editor APIs and restores root activeSelf on the persistent asset in both reconstruction and verification. Full BattleMain Native19 passes491nodes/1,380components/59,291fields and independent progress-effect Native03 passes4nodes/8components/4,297fields across save/reopen/independent cold, with stable native identities/references. Both remain headless native-partial, with unknown behaviors disabled and visual/business not accepted.

Actual production native verifier/refusal fixture15 passes12 materialized native-target refusals and28 captured-native-signature contract refusals.14 attempted curve edits normalized by Unity and caused no materialized target drift; they are recorded separately and are not claimed refused. Earlier fixture14 stopped on that ineffective mutant and is retained.116 related Python checks pass. The verbose full native report exceeded the unchanged128MiB readback cap in Native18; lossless compact JSON (all fields retained) resolves it in Native19. Fixeddev8 package/actual fixed entry handoff is being established; no consumer lock or original59pairs changed.

## 已完成历史投影

本块仅保留已完成历史；未完成task/development-release及其管理阻塞条目已从本源实际删除并交GREA。

```manager-task-view
{
  "schemaVersion": 1,
  "projectId": "monkey",
  "updatedOn": "2026-11-04",
  "ownerSessionId": "01a19b7a-b22a-7ac1-88b0-4c3d3219718b",
  "scope": "仅保留已完成历史。当前开发任务及发布验收唯一来源为GREA proposals/lifecycle-roadmap.md，按负责人分派实施，不维护monkey独立待办。",
  "releases": [
    {
      "id": "monkey:v0.7.0",
      "title": "v0.7.0稳定线正式收口与验后发布",
      "version": "0.7.0",
      "workflowStatus": "done",
      "description": "稳定dev9隔离收口，审核提交86d47f与原制品已发布；远端tag/Release及下载SHA回读一致。v0.8开发独立保留。",
      "acceptanceCriteria": [
        "稳定范围/公开文档/依赖/许可证和制品一致；不含私有载荷或本机路径依赖",
        "制品隔离安装及相关公开入口/代表验证通过，GREA组合验收与总监核查完成",
        "既有GitHub仓库正常发布，远端tag/commit/下载制品SHA回读一致，游戏入口不变"
      ],
      "sourceRefs": [
        "/Users/wangmeng/MyProjects/Manager/decisions/20261104-toolchain-stable-release/PLAN.md"
      ],
      "candidateCommit": "86d47f35744a5af91614c417b00c8eaa2345baad",
      "candidateIndex": ".private/release-v070-20261104/86d47f35744a/candidate-index.json",
      "verification": {
        "result": "pass",
        "scope": "组件包/安装/相关检查、GREA精确组合和总监核查、远端发布与下载身份；不扩大原生/视觉/业务范围"
      },
      "publication": {
        "status": "published-remote-readback-verified",
        "version": "0.7.0",
        "commit": "86d47f35744a5af91614c417b00c8eaa2345baad",
        "tag": "v0.7.0",
        "tagObjectSha": "0bf88e365167103e8d4592a56f088f4551bc7a6a",
        "tagPeeledCommit": "86d47f35744a5af91614c417b00c8eaa2345baad",
        "releaseId": "RE_kwDOVVB5hs4Z2Esp",
        "releaseUrl": "https://github.com/chuxintec/monkey/releases/tag/v0.7.0",
        "publishedAt": "2026-11-04T07:03:25Z",
        "draft": false,
        "prerelease": false,
        "downloadedAssets": [
          {
            "name": "SHA256SUMS",
            "sha256": "d5bed89d7548d7999e476299416038c1e6ad9e7199c3cffba43d8c87781e297b",
            "bytes": 196,
            "url": "https://github.com/chuxintec/monkey/releases/download/v0.7.0/SHA256SUMS",
            "apiDigest": "sha256:d5bed89d7548d7999e476299416038c1e6ad9e7199c3cffba43d8c87781e297b"
          },
          {
            "name": "monkey_native-0.7.0-py3-none-any.whl",
            "sha256": "cb7eed60ff00085260657d2362e5fc60ee46a5d258a748c75770d0e337964dd0",
            "bytes": 1950487,
            "url": "https://github.com/chuxintec/monkey/releases/download/v0.7.0/monkey_native-0.7.0-py3-none-any.whl",
            "apiDigest": "sha256:cb7eed60ff00085260657d2362e5fc60ee46a5d258a748c75770d0e337964dd0"
          },
          {
            "name": "monkey_native-0.7.0.tar.gz",
            "sha256": "b9cef798cc758491bdffa53f46646fdb43cead771bc814d8046c68fec202a866",
            "bytes": 2516298,
            "url": "https://github.com/chuxintec/monkey/releases/download/v0.7.0/monkey_native-0.7.0.tar.gz",
            "apiDigest": "sha256:b9cef798cc758491bdffa53f46646fdb43cead771bc814d8046c68fec202a866"
          }
        ],
        "sourceBranch": "codex/release-v0.7.0",
        "authorizationDecision": "/Users/wangmeng/MyProjects/Manager/decisions/20261104-toolchain-stable-release/component-publication-decision.json",
        "boundary": "Original reviewed artifacts; no rebuild, game/global install/active plugin cache replacement or native revalidation."
      }
    },
    {
      "id": "monkey:v0.8.0-dev7",
      "title": "Unity-source静态Prefab恢复开发候选",
      "version": "0.8.0.dev7",
      "workflowStatus": "done",
      "description": "旧固定dev7与10个已采用静态子集保持，仅此有界候选范围完成；不代表完整BattleMain、整模块或v0.8正式版完成。",
      "candidateCommit": "2e88bc95fbe9cf82d61ad0a192715f334a242695",
      "acceptanceCriteria": [
        "固定版本身份、既有静态保存/独立冷读/消费者采用证据保持",
        "BattleMain仅在源字段严格一致的原生保存及独立冷读通过后接受；未支持能力继续明确拒绝",
        "视觉、Player与业务验收单独记录，不由静态数量推导；正式发布范围尚未授权"
      ],
      "verification": {
        "result": "partial",
        "scope": "固定dev7与已采用静态子集；未签整版/视觉/Player/业务"
      },
      "sourceRefs": [
        "docs/PLAN.md#current-consumer-milestone--2026-11-02",
        "docs/PLAN.md#fixed-dev7-effect-handoff--2026-11-02",
        "/Users/wangmeng/MyProjects/Manager/decisions/20261104-product-driven-tooling/PLAN.md"
      ],
      "consumerProjectId": "zombie",
      "consumerTaskIds": [
        "zombie:T0001",
        "zombie:T0002",
        "zombie:T0003",
        "zombie:T0006"
      ]
    },
    {
      "id": "monkey:history-source-inventory",
      "kind": "phase_milestone",
      "version": null,
      "title": "历史完成：冻结来源Prefab分母与既有消费者映射",
      "workflowStatus": "done",
      "description": "只表示已完成的技术证据核验，不是新的开发release或整版完成声明；源于已完成inventory任务，原dev8开发release已移交GREA。",
      "sourceRefs": [
        ".private/unity-prefab-v080-20261104/source-prefab-inventory-with-adoption-02.json"
      ]
    }
  ],
  "tasks": [
    {
      "id": "monkey:release-v070-publish",
      "primaryReleaseId": "monkey:v0.7.0",
      "title": "核准后发布v0.7.0并回读远端制品",
      "workflowStatus": "done",
      "description": "组件与GREA组合通过，待总监本轮核查结论后创建tag/Release并远端下载回读。",
      "acceptanceCriteria": [
        "稳定范围/公开文档/依赖/许可证和制品一致；不含私有载荷或本机路径依赖",
        "制品隔离安装及相关公开入口/代表验证通过，GREA组合验收与总监核查完成",
        "既有GitHub仓库正常发布，远端tag/commit/下载制品SHA回读一致，游戏入口不变"
      ],
      "blockerIds": [],
      "verification": {
        "result": "pass",
        "scope": "v0.7.0正常分支/tag/Release发布及3附件下载SHA核验"
      }
    },
    {
      "id": "monkey:release-v070-integration",
      "primaryReleaseId": "monkey:v0.7.0",
      "title": "交付GREA固定候选并通过组合验收",
      "workflowStatus": "done",
      "description": "精确候选索引直接给GREA；复用原生证据，受影响组合边界实际验证。",
      "acceptanceCriteria": [
        "稳定范围/公开文档/依赖/许可证和制品一致；不含私有载荷或本机路径依赖",
        "制品隔离安装及相关公开入口/代表验证通过，GREA组合验收与总监核查完成",
        "既有GitHub仓库正常发布，远端tag/commit/下载制品SHA回读一致，游戏入口不变"
      ],
      "blockerIds": [],
      "verification": {
        "result": "pass",
        "scope": "GREA原包隔离组合10项及安装环境test_native_font_stage6项通过；复用owner证据，不重复验收"
      }
    },
    {
      "id": "monkey:release-v070-package",
      "primaryReleaseId": "monkey:v0.7.0",
      "title": "隔离稳定发布线并完成包与相关验证",
      "workflowStatus": "done",
      "description": "保全根WIP，从公开main提取固定dev9稳定源码；生成精确制品/隔离安装/公开入口证据。",
      "acceptanceCriteria": [
        "稳定范围/公开文档/依赖/许可证和制品一致；不含私有载荷或本机路径依赖",
        "制品隔离安装及相关公开入口/代表验证通过，GREA组合验收与总监核查完成",
        "既有GitHub仓库正常发布，远端tag/commit/下载制品SHA回读一致，游戏入口不变"
      ],
      "blockerIds": [],
      "verification": {
        "result": "pass",
        "scope": "436包文件身份、制品隔离安装、44入口烟测、85相关检查和7步中性公开流程；1外部beaver测试未执行"
      }
    },
    {
      "id": "monkey:static-ten-samples",
      "primaryReleaseId": "monkey:v0.8.0-dev7",
      "title": "完成十个不同静态样本的正式接入",
      "workflowStatus": "done",
      "description": "项目owner已完成Widget第十个样本接入；正式59资产对，保留禁用载体和未验视觉等边界。此项完成仅限已声明后台静态目标。",
      "acceptanceCriteria": [
        "十个不同源样本经固定生产者及消费者公开流程接入",
        "受影响源字段及独立冷读通过，既有正式文件保持",
        "未知行为、源语义、视觉/Player/业务缺口明确保留"
      ],
      "blockerIds": [],
      "verification": {
        "result": "pass",
        "scope": "已声明十个后台静态样本正式接入，复用项目owner现有证据"
      },
      "sourceRefs": [
        "docs/PLAN.md#current-consumer-milestone--2026-11-02",
        "/Users/wangmeng/MyProjects/Games/projects/21-zombie-cannon/Analysis/static-prefab-20261102/ten-root-static-milestone-01.json"
      ]
    },
    {
      "id": "monkey:unity-source-prefab-inventory",
      "title": "冻结来源Prefab根与依赖分母及首关消费者映射",
      "workflowStatus": "done",
      "description": "601冻结缓存/132文件名Prefab包/161精确地址根；按源identity和原生GUID关联既有10个正式采用静态子集，151仅来源解析；335粒子/77空TwoConstants/17来源根。未重导或重复验收。 历史实现版本引用monkey:v0.8.0-dev8；其未完开发release条目已移交GREA，本行仅保留已完成的来源分母核验事实。",
      "consumerProjectId": "zombie",
      "consumerTaskIds": [
        "zombie:T0001",
        "zombie:T0002",
        "zombie:T0003",
        "zombie:T0006"
      ],
      "acceptanceCriteria": [
        "源存在/根身份/依赖/未解析与候选/原生/视觉/采用状态分列",
        "复用10根59对原验收，不重导；人工运行时修补独立记录",
        "首关完整模块优先，不以盘点替代修复和固定采用"
      ],
      "sourceRefs": [
        ".private/unity-prefab-v080-20261104/source-prefab-inventory-with-adoption-02.json"
      ],
      "verification": {
        "result": "pass",
        "scope": "冻结来源分母与既有静态子集精确关联；不是整包获取、整模块或新增原生/视觉验收"
      },
      "primaryReleaseId": "monkey:history-source-inventory"
    }
  ],
  "blockers": []
}
```

## Consumer-driven v0.8 continuation — 2026-11-04

Authority: Manager decisions/20261104-product-driven-tooling/PLAN.md, human01a1a5d9-e8d2-7ab2-996a-4480d40150bf. Zombie T0001/T0002/T0003/T0006 consumes complete BattleMain, first-level models, projectile/effect/HP/damage carriers, in that order. Existing runtime HUD binding, compatible player/frame pools, overlays and business lifecycle fixes remain project work, not tool recovery. The received consumer-packet is the source of module priority and manual work.

Current action uses existing601 frozen typed snapshots, preserving every original file:161 distinct explicitly addressed Prefab roots/dependencies;335ParticleSystems,77source empty TwoConstants cases in17independent Prefabs;36unparsedMonoBehaviours retained. This is the available cached-source denominator, not proof every original game package was obtained. The132 filename-Prefab bundles are distinct from root count. Source inventory and particle mechanism records: `.private/unity-prefab-v080-20261104/`.

First failure and second independent sample are BattleMainUI and source eff_ui_jijiajunei_jindutiao01. UVSourceImportProbe01 preserves its guard/identity-resolution failure, no accepted readback: it incorrectly expected original source pathId to equal provider-native localID. Probe02 now resolves exact source root address, child indices and component order/type; source/native localIDs remain distinct. The corrected guard and launch share one Python control flow and redact unrelated process arguments. No semantics normalization/field omission or fixed candidate is accepted from these probes. RectTransform float32 repair remains separate existing evidence, not rerun as an entire matrix.

## v0.7.0 published — 2026-11-04

Actual GitHub release https://github.com/chuxintec/monkey/releases/tag/v0.7.0 publishedAt 2026-11-04T07:03:25Z; branch/tag peel to86d47f35744a5af91614c417b00c8eaa2345baad. Original reviewed wheel/source/SHA256SUMS downloaded and all match exact candidate hashes. GREA combination and director gate passed before release. Authority: `.private/release-v070-20261104/86d47f35744a/publication-verification.json`; original candidate index updated with remote identities. Current0.8 development/WIP/UV limitation and both game wrappers/locks remain independent and unchanged. Earlier pending release/gate paragraphs are historical checkpoints.

## v0.7.0 stable release — 2026-11-04

User-authorized package/verification-before-publication scope is Manager decisions/20261104-toolchain-stable-release/PLAN.md. Stable source735a87ebbc19 (0.7.0.dev9), public parent/main ff57c75. Isolated release worktree `.private/worktrees/release-v0.7.0`; preservation/checklist/evidence `.private/release-v070-20261104/`. Originalv0.8 branch/WIP/fixeddev7 and both game wrappers/locks remain unchanged. No global install or foreground/native rerun. Candidate and remote publication remain pending actual evidence; v0.8 UV gap is independent.

GREA exact combination accepted (grea-monkey-combined-04): artifact-installed CLI/MCP combination10 checks and all6 external beaver integration checks pass. Existing candidate bytes remain unchanged. Candidate index now records owner evidence; no monkey repeat verification. Director review and actual tag/Release/download readback remain pending.

Stable component candidate now prepared: commit86d47f35744a, final0.7.0 wheel/sdist and SHA256SUMS under `.private/release-v070-20261104/86d47f35744a/`; exact candidate-index.json is authority.436package bytes equal fixeddev9 exceptversion; isolated installation/44CLI checks/85focused checks(1external skip)/7neutral public pipeline steps pass. GREA combination/director review and actual remote publication pending. Historical private SDK audit is freshly refused for migrated symlink path; no guard/evidence rewrite.

Migration path follow-up — 2026-11-03: Foodstreet actual root now available; mutable foodstreet-input-set resolves all4 original inputs/configs under new project root, and current-consumer-route points to .worktrees/v20-develop-delivery-20261103. The old integration-repo remains separately mapped preservedInputWorkspace; its input meaning is not replaced by the formal worktree. Research5 frozen JSONs remain unchanged;28 inputs have same-filesystem-object checks and separate resolved copies. Index: `.private/myprojects-migration-20261103/foodstreet-research-paths/VALIDATION.json`. Earlier pending-Foodstreet migration statements are historical; Manager/app/compatibility alias retirement remains external.

Migration resumed at canonical new root — 2026-11-03: /Users/wangmeng/MyProjects/Tools/monkey. Pre-repair13 release pins match, HEAD/branch/WIP retained, nestedv0.4.1 Git paths repaired; dev6/dev7/dev9 new wrappers and UnityPy1.25.3 import pass. Dev7 all458 package bytes match fixed identity. Original frozen launchers/receipts unchanged; live wrappers and mutable environment/source-reader paths repaired. Completion/remaining old consumers: `.private/myprojects-migration-20261103/VALIDATION.json`. Foodstreet final root and Codex UI/settings still external pending; old aliases must remain until owners finish.

Migration write release — 2026-11-03: owner has saved WIP and released old-root writing for ops migration to /Users/wangmeng/MyProjects/Tools/monkey. No active producer/native transaction or child process. See `.private/myprojects-migration-20261103/RELEASE.json`. Do not resume old-root writes after this checkpoint; resume only on ops new-path handoff, with targeted entry/path repairs and existing evidence preserved.

## Current consumer milestone — 2026-11-02

The project owner reports actual fixed29 Widget public spec4 plan/apply and independent native cold complete (journal `7590bd737aa20527bff9c34a7b8b56cea1b5b26a7202bf479a4017645836ca25`). The normal battle UI Widget is formally integrated as the tenth distinct static sample:2new resources and2directory metas preserve all126558 prior files, now126564;59pairs index SHA `99eb38eef1d3f5b4afe872e1ec8eb36193fb425ba593c9f5ac0402150999389a`. Font/atlas and existing adapter/official Outline bindings were reused with no new script or asmdef change.186fields/14Prefab objects pass owner independent cold. This closes the declared ten-sample background static integration target; it is not game completion or visible/interactive acceptance. GradientColor remains disabled and source semantics/visual/Player/business remain unverified. Authoritative product milestone: consumer `Analysis/static-prefab-20261102/ten-root-static-milestone-01.json`. This tool records the owner's integration result without receipt-triggered duplicate validation or report broadcasting.

BattleMain strict UV follow-up has a completed neutral target probe: `.private/unity-prefab-v080-20261102/UVRepresentationProbe01/summary.json` SHA `65aedc1ec3076f63437e87a65fe7eddd43b46654da4d7352c2e964dc5fc72199`. On target6000.6.2f1, explicitly serialized empty curves and public empty/null/two-constant writes all expose max2/min0 through a fresh SerializedObject while still inactive. Activation/deactivation does not change it; native saved YAML contains the two keys. A second independent process confirms all four saved cases and all8Prefab/meta bytes remain unchanged. Source UV is enabled with mode3 and both source curves empty. This disproves the activation-only explanation; tested APIs still fail source max0. Same-object cache0 is not persistence evidence. Preserve the strict refusal and all failed source attempts; no source normalization, raw-field guard relaxation, target/game edit or producer change. The probe does not prove every possible native API is incapable. First CLI success/report are present, but its requested ../log path was rejected, so complete first-log provenance is not claimed; the cold absolute-path log is retained. No accepted-root reruns, count-driven matrix or Spine restoration.

## Next root and actual consumer — 2026-11-02

The owner reports fixed29/spec5 DamageTip fresh plan/apply/code-check/independent cold complete: current formal source pointer now pins journal `91fe5ee8fdb289a8e798bd57fdd176d599fe853a05865e09a778c6fafc7fc6f8`, after126558,9roots/57pairs. The current57-pair index SHA is `4642f1785a4095a1fb0bb10b996be049b4cfaef2577fc63516f127d77e916446`. GREA independently reviewed that consumer receipt; no producer rerun or refreeze was required. Existing GameBase asset/meta remain unchanged; DamageTip remains a disabled serialization carrier with no numeric-mesh/visual/Player/business claim. Source Shader dependency10753 is original, not native-added; target Sprites/Default identity is independently proven, source Shader semantics remain unverified.

Next fixeddev7 Widget selection `FixedBattleWidgetSavedSelection01` has71 rehashed files, manifest `9ea3d685477c28ff9132e9783652c524c5cd6125de32487498608b88bda84ade`. Public recover/verify/headless/freeze actually ran:4nodes/10components/186fields before save, after reopen and independent cold; zero MissingScript/failures and stable references. All stages retain partial/exit1. Its single GradientColor carrier is disabled; source BaseMeshEffect methods are unavailable and no ModifyMesh stub is invented.

Authoritative Widget diagnostic revision03 `.private/unity-prefab-v080-20261102/dev7-fixed-widget-handoff-03.json` SHA `d0d2352d5c8af3c1ad17d23995e2c11254237efa931fa8235e6870ce6e4480a8` corrects revisions01/02's incomplete path-based classification. All9 candidate GUIDs were joined to the pinned57-pair currentPath/originalIntakePath index plus separately pinned existing script bindings. The source atlas already exists at a relocated currentPath with identical asset/meta bytes; both current files were rehashed. Actual disposition is2new resources (Widget Prefab/Sprite)+2exact reuse (font/atlas)+3existing externalScripts bindings+2omitted compiler inputs (enum/asmdef). Existing target scripts/meta and three script GUID joins were independently checked; source GameBase versus target Assembly-CSharp remains explicit prior Login adapter evidence. No new producer feature, script movement, code/meta overwrite, assembly edit or refreeze is required. Revisions01/02 remain historical incomplete diagnoses; fixed saved selection/manifest stay unchanged. Owner subsequent spec4/native/cold adoption is complete as recorded in the current milestone above; this revision03 was its preceding diagnostic checkpoint. Gradient/visual/Player/business remain unverified. GUID review coverage is the indexed57pairs plus pinned existing scripts, not an exhaustive scan of every other unindexed formal asset.

Active exact-source reader: `.private/unity-sprite-atlas-flip-20261028/Provider/bin/python`, verifiedUnityPy1.25.3; `.private/source-readers/active.json` pins its use. The retired GREA Python path was not restored. BattleMain empty UV curve remains strict source0/native2 refusal, independent of the Widget handoff.

## Deep cleanup and current size — 2026-11-02

Same-root measured usage is now39.828GiB, down from76.463GiB in this deep-cleanup pass. Current authority: `.private/deep-cleanup-20261102/REPORT.md` / summary.json / retention-audit.json. All older90.80GiB/76.323GiB values are historical. Exact deletion plans precede deletion and durable results, with duplicate source SHA pins recorded before removal. Current21/fallback10, source-freeze/font/SDK, fixeddev6/dev7, Gun/Renderer/TextureMaterial and formal consumer inputs retained. Earlier watched UnityProject106 font asset paths belong to retired historical requests; retained self-contained current font/source payloads are not claimed to make those old requests replayable.

BattleMain Native10 still strictly rejects empty UV curve source0/native2; default target keys/tangents/weights/wrap were captured for bounded next-step modeling, with no relaxation. Effect remains fixeddev7/GREA-bound; formal consumer is resolving the builtin Quad intake contract with beaver.

## Fixed dev7 effect handoff — 2026-11-02

Producer `2e88bc95fbe9cf82d61ad0a192715f334a242695` fixes0.8.0.dev7. Its wheel `4def5301d94232937627ce567a711d7adf29628d5f30e54d0146f7c3ef7610dc` has458 package files equal to committed source;131 affected tests pass from that exact runtime. The fixed public CLI actually recover/verify/freeze selects `FixedEffectTextureMaterialSavedSelection01`, manifest `5a23b9dcece825fcb8ecec250663d51dac2237dca9365a5e2c0b34b8b72ce0ad`.64/64 fields,2owners/4components, zero MissingScript/failures, actual save/independent cold and stable references pass; all three CLI stages retain expected partial/exit1/needs_action. Original source mesh gap/provider diagnostics, Shader semantics, visual/Player/business boundaries remain explicit. Existing Login/other adopted roots were not rerun.

Exact producer/source tuple/first+cold/76 saved files/4 new pairs and current48-pair comparison are in `.private/unity-prefab-v080-20261102/dev7-fixed-effect-handoff-01.json` SHA `6e1369a1a5163448b3f634109feff48152f6448d90e037c9fefff7cf87da06eb`. GREA has bound this fixed runtime through `.private/monkey-v08-dev7-integration-20261102/providers.json` (GREA-owned), independently reviewed pins and reused actual native evidence; its development report is `validation/development/monkey-dev7-effect-integration-20261102.json`. The formal consumer owner has received the exact saved selection; adoption remains pending their single-writer receipt. BattleMain UV empty-curve strict refusal remains independent.

## Current continuation — 2026-11-02

The targeted v0.6 retention followthrough retires all unreferenced generated data in the four reviewed scopes, keeping only unique original/source/patch and compact identity/results; see `.private/aggressive-slim-20261102/FOLLOWTHROUGH.md`. Earlier claims that historical final/fallback alone justified those runnable directories are superseded.

Development resumed directly: ParticleSystem UV source-empty curves still fail strict native validation (attempts06–09), with native API curve counts proving the activation/cache issue. Unsuccessful curve rewrites were removed rather than shipped. Actual TextureMaterial07 supplement was accepted into fresh EffectTextureMaterialCandidate01; parent native01 actually saves and independently cold-reopens with64/64 source-field checks, zero MissingScript/failures and stable native references. Overall remains native-partial/headless, exit1; graph engine-reference/provider diagnostics and visual/Shader semantic boundaries are not promoted to full acceptance. Source engine-reference and original provider diagnostics remain explicit. No new version/visual acceptance is claimed.

## Authorized payload retirement — 2026-11-02

User-authorized aggressive cleanup retires historical generated payloads listed in `.private/aggressive-slim-20261102/REPORT.md` and batch manifests. Prior successful native/consumer statements remain historical observations; retired old work directories are no longer locally replayable evidence. Current v0.8 source pins, fixed Delivery, Gun/Renderer/TextureMaterial WIP and v0.7 frozen source pins remain. The earlier90.80GiB observation is historical (current measured root is39.828GiB); this maintenance adds no version acceptance.

## Successor checkpoint — 2026-11-02

Replacement handoff SHA256 `e48a1db5f2730c2903a53e30fa96f0aef1168e63c976bdcfeb503380bba0ba96` was verified; Manager released writing and archived the old owner. All three previous module instances completed and released their files, with no owned process left running. The successor owns the inherited WIP and shared integration. Fixed dev6 and the six formal consumer roots remain the baseline.

The selected Texture/Material façade is now reachable through `rebuild-unity-prefab-texture-material-assets` with exact request hash, Editor path and bounded budget arguments. Dispatch plus inherited texture/material, trim, native, Renderer and Slider checks pass (54 tests). This is command integration evidence only; the façade has not passed native first/cold execution or parent recovery. Shader semantics remain unverified. Gun's exact cache normalization passes fresh native first/cold `TrimmedGunAssets04` (manifest `ec3c3cc4f1a9c00b131c1e51db90f0ea8efd9b51eed9a75e5e2ddd3c8c7daa2f`), preserving failed 01–03. Resource acceptance remains separate from parent/visual acceptance. BattleMain RectTransform remains unresolved.

Texture/Material actual execution continuation: the first request against a historical native work directory correctly failed the complete manifest guard because the native run changed its Prefab. The second request binds the unchanged original `EffectCandidate01` manifest, passes planning and pixel staging, then stops at `UNITY_PREFAB_EDITOR_BUSY` before launch. Preserve both requests and `TextureMaterialNative02`; use a fresh output for the next attempt. Existing resource tests were not rerun. BattleMain's failed RectTransform has source stored local Y=0 and anchored Y=-97.300003; its current failure omitted expected/actual values. The shared native readback now includes those values in mismatch diagnostics, without changing comparison rules. Native validation of that diagnostic is pending the shared Editor becoming available.

Texture/Material attempt07 now passes actual native first/cold execution, manifest `49ae1599736feaaa013604d4f91003eb33bb241e3432af093454622a4941bb5a`. The native helper compilation omissions, missing resource path readbacks and exact `_MainTex` reference subtree snapshot handling are fixed. Attempts03–06 remain failed evidence. Snapshot06 proves only the selected pointer's internal FileID/PathID changed; all other serialized properties remain protected. Eight affected helper/planner checks and diff-check pass. Shader semantic/visual equivalence, supplement consumer integration, parent recovery and fixed package remain pending. BattleRendererNative04 is the fresh current-runtime diagnostic attempt.

BattleRendererNative04 confirms local Y expected585.69999694824219 versus actual585.70001220703125. Layout expectations now round each float32 arithmetic operation, matching Unity's serialized scalar precision without widening tolerances; five affected native-planning tests pass including that regression. Fresh native attempt05 advances beyond the RectTransform mismatch and fails on ParticleSystem `UVModule.frameOverTime.maxCurve.m_Curve.Array.size` (source0/native2). Preserve the failed attempt; curve-mode/source serialization semantics need proof before any normalization. TextureMaterialNative07 supplement loading independently validates both Material and Texture2D mappings. No fixeddev7 or visual completion is claimed.

## Latest local increment — original atlas pixels

Fixed dev5 and its public freeze binding remain immutable. The new dev6 increment adds an explicit selected-pixel atlas repair mode: exact Sprite→SpriteAtlas member/render-key→Texture2D identities, pinned original PNG evidence and an existing candidate relocation record prove each repair. Only full, unrotated rectangle regions with zero trim offsets are covered. Existing Sprite GUID/localID/meta, geometry and source physics outlines are retained; only the native render texture references are rebound to a decoded original-pixel Texture2D. Source float32 arithmetic is preserved without clamping. Original packed flags and observed Unity cache flags are separate evidence.

An eight-Sprite shared-atlas prototype has actual native save/independent read-only reopen evidence. Its repaired login parent also saves and independently reopens with all 4,757 source field checks and stable identities/references. This is headless evidence, not visual acceptance or consumer adoption. A trimmed atlas Sprite remains rejected. A separate two-resource embedded-Sprite closure passes, while its parent native attempt fails on an unproven Renderer byte/bool mapping. Original failed attempts and old bulk-preparation missing-pixel evidence remain unchanged. Package fixation and the next ready UI consumer module are the next bounded work; no foreground or paused engine work is authorized here. Earlier checkpoint wording below is historical where superseded by this section.

## Current scope — 2026-11-02

Latest priority: consumer Prefab recovery continues in the background; the shared screen belongs to the other active product. No foreground Editor/Player or screen-window request. Isolated no-graphics native loading may run only without another main Editor conflict. Visual/static-display and visible editing remain pending, not waived. Fixed dev1 and dev2 outputs remain immutable. The fixed dev2 first native-saved health-bar selection was adopted through GREA and beaver into the actual consumer, with source fields and script mappings independently reopened and old business files preserved. This closes that module-adoption subgoal only. Current dev3 workspace prototypes cover nine distinct actual roots with native save and independent-process identity/reference checks; they are not a fixed dev3 delivery or static-presentation acceptance. The remaining large UI root is blocked by an exact-source atlas texture previously returning HTTP404 and a source Sprite lacking an exact native asset mapping. Preserve these gaps and original failed attempts; do not replace pixels or count the root as complete.

The user has approved a new local Unity-source static Prefab increment driven by an existing consumer project. Source Unity 2021.3.30f1 IL2CPP/WASM and target 6000.6.2f1 are separate pinned identities; source code is not executed and no Cocos recovery gate applies. The current fixed v0.7 dev9 and all earlier native/consumer successes stay immutable. No v0.8 implementation or candidate has yet passed acceptance.

A consumer-owned frozen selection supplies twelve distinct actual source roots with source bundle, serialized-file and strict typed-object hashes. The preferred first adopted module is an enemy-health-bar Prefab. Reuse existing reader/provider, inspection/export and texture/schema caches before adding missing general source/target semantics. Do not hand-code page/character answers, mix colleague source versions, erase Missing Scripts or discard unknown fields. Original script identity, serialized fields/references and disabled unavailable behavior must survive. Native resources, subasset GUID/localID/type, font/material, cross-bundle and actual nested-instance evidence require exact mapping.

The primary owns shared CLI/schema/version, candidate export/native checks and Editor coordination. A bounded source-graph module owns only its new helper/tests. Main consumer development/WIP and migration remain with the current consumer maintainer; beaver owns adoption and SDK/native identity preflight; GREA owns fixed public dispatch. Background work starts without interrupting the other active consumer's Editor/desktop. No source/project writes, remote push/release, global install or new source-service/player-data permission is implied. Consumer-specific native AX/CGEvent authority is not transferred.

Exit: at least ten distinct frozen roots and their dependency closure have per-root source/target mappings, actual native import/compile/load/static display/save/independent reopen evidence; representative text/image/transform edits visibly work. At least one useful complete module must be adopted through fixed public tools and verified by the actual consumer. Static, Player, business and visual/source-version limits stay separate. A graph/field count, local unit tests or provider export alone does not close this version. Continue approved ready work without ordinary ACKs; report fixed/public/actual consumer groups or specific severe blockers.

The dev3 four-root native attempt exposed positional pairing between independently ordered source-graph roots and provider paths. It failed before saving any root and remains unaccepted. The next local increment joins paths through exact pinned container/file/path identity, rejects ambiguous or incomplete root sets, and retains the original graph order only for representative selection. The bounded four-root native run is the affected integration check; earlier single-root and consumer receipts are not rerun.

Current next increment is dev5 WIP: the ready three-model dev4 module has actual GREA/beaver consumer intake, independently checked new files and native cold readback. Embedded Sprite reconstruction now validates exact original cache pixels and source geometry through native asset creation, save and a separate read-only process; source positions/indices stay exact, UV cache materialization is explicit, and target-only cache flags are recorded rather than mislabelled source data. InputField/Selectable inheritance retains original fields with unavailable source logic disabled; char values retain their declaration-proven UTF-16 storage. A complete login-root prototype passes 4,757 field checks on 70 nodes, save and independent reopen. This raises the headless save/reopen sample denominator to ten distinct roots, including the separately retained effect root with a missing original material texture. It does not close ten complete dependency/visual cases or v0.8 acceptance. Fix the package/runtime identity and deliver the bounded next candidate; do not replay old roots or request the screen.

## Preserved v0.7 history and accepted consumer scopes

# monkey v0.7.0 — complete core Prefab recovery

Latest fixed development implementation: **0.7.0.dev9**, `735a87ebbc194590c39a6ecd3984b74c4c23c029`. The prior dev7 remains the fixed native-selection producer. Formal **0.6.0** and all earlier frozen consumer candidates retain their original identities. The dated sections below preserve history; this current summary supersedes their pending-state wording.

## Current scope and acceptance — 2026-11-01

The approved continuation is producer SDK identity/dependency declarations for the shared SDK migration workflow. beaver owns PE/CLI inspection, migration planning, execution, rollback and App-instance binding; GREA owns public dispatch; the product owner owns actual incremental adoption and Player/business validation. monkey does not write the consumer project, implement another DLL analyzer or claim migration success from static declarations. The current change extends the existing immutable-selection dependency supplement with `monkey-native-sdk-declaration/1`; original candidates, manifests, warnings and acceptance evidence remain unchanged. The initial fixed supplemental dev8 is retained. The subsequent fixed dev9 adds the consumer-requested explicit per-DLL MonoScript-table `not_run` declaration; an empty table does not claim zero scripts. Twenty-four focused checks and the actual fixed public supplemental audit pass; all eighty-seven old A10 payload files plus the manifest remain byte-identical. The wheel contains all 436 expected package files at exact frozen source bytes. beaver fixed PE/type/importer inspection is reused separately; no second analyzer or Editor run was introduced. GREA independently verifies all 436 package files, pins dev9 through its public entry and reruns the audit on an independent input copy; its report is byte-identical to the producer supplement, including all four `not_run` script tables and three original reference tuples. Thirty-four targeted GREA checks pass. Public status remains `needs_action`, retaining the migration/native boundary. Subsequent beaver fixed20 SDK and fixed21 bound-input actual consumer receipts close their exact local P0 scopes; see the current consumer closure below. The complete fixed-tool/public-entry/real-consumer chain subsequently passed for the exact existing SDK migration and bound default-input App scope described below; broader SDK and product acceptance remain separate.

| Fixed implementation | Proven scope and replacement relationship | Remaining boundary |
| --- | --- | --- |
| dev1 `a458790a68d57108b4cfe038d8aa565d5cc1599b` | Thirty roots / fifty-two closure Prefabs pass bounded native static import/save/reopen in both Editors; ordinary goose save/reopen evidence retained. Supersedes the historical incomplete static checkpoints below. | User-wide visual parity and complete game behavior are not implied. |
| dev3 `4ad7498a35e762f6ef5b6f15a334e973d7794845` | Corrected selected shader closure, editable presentation/input and same-face fallback completion. Neutral native probes and actual consumer Player text/progress/CJK/source-button/disable checks pass. The final 247-file payload and font identities stay frozen. Supersedes dev2's incomplete shader closure. | Natural unlock/claim and business authority were not tested by those probes. |
| dev4 `19d51d4dbe7971bb14c5724963c42dfdbd9ddaca` | Public supplemental audit proves all twenty-two scripts in the actual 247-file payload, zero uncovered. The original eleven diagnostics remain unchanged; the old twelve count was a stage mismatch. Consumer independently reproduced the proof. | Producer compilation evidence is distinct from arbitrary C# analysis or dynamic behavior. |
| dev5 `ea172e0f214dbcd6e179821c05678d86ca0be992` | Independent exact-S2 Creator resource probe passes after owned temporary-scene/Undo teardown repair; original probe metadata and emitted-helper equivalence are retained. | Does not resume the paused Creator product. Controlled post-receipt termination is not an exit-zero claim. |
| dev6 `a18e786d00320aba4c4de373fe1fabe3431b36ba` | Exact-S2 Unity native static import/save/unload/reopen, ordinary GUI save/reopen and native pose images pass with data scale .01 on PPU100 and original node scale .75. This is the native-import implementation; the selected payload is later dev7. | Dynamic Spine behavior remains partial; current season and source-literal timer are not product authority. |
| dev7 `78f4f8d160ab7e09d38e84ba0f374a1b0a98081e` | Clean eighty-seven-file A10 selection carries paired runtime DLL/importer/license/shader/helper closure; eight scripts producer-proven, zero uncovered. Actual selected project compilation/readback passes; clean refreeze is byte-equivalent. beaver read-only acceptance and later App31 incremental product entry, actual click and save-resume evidence pass. | Product SDK compatibility required project-side adaptation; this is not a generic SDK-migration pass. App31 is a bounded historical A10 consumer receipt, not the latest whole-product version. |

| dev9 `735a87ebbc194590c39a6ecd3984b74c4c23c029` | Immutable supplemental SDK declaration records exact DLL/meta/GUID/roles, declared build identities/dependencies, license and three original serialized script-reference tuples. Each DLL explicitly reports its absent native MonoScript-table evidence as `not_run`. Supersedes dev8 at declaration level only. | Public audit consumption is verified; consumer native script tables, compatibility/migration and product proof remain separate. |

The later beaver fixed18 consumer tool (`b5e9b034c3cb850168f3cd1e97d51a6e1063f9fc`) reuses the dev9 declaration and verified SDK source. Its fixed public adoption transaction passes actual apply, independent cold reopen and rollback on an isolated legacy-SDK clone. Thirty-two canonical MonoScript GUID/localID/type identities, actual Editor MVID and old data-asset references are preserved; default legacy SDK conflicts still block. The inactive Player table is actually empty and is accepted only through exact prior canonical DLL SHA/MVID plus complete native-before tuple evidence, not through inferred PE types or a Player-execution claim. Those checks are consumer-owned evidence, not a new monkey native import. GREA fixed18 public integration and real product migration/instance-binding acceptance remain pending; the P0s stay open. No new producer export, font generation or native visual rerun is required by this result.

### Current consumer closure — 2026-11-01

The final hash-verified provider/consumer index supersedes the earlier fixed18 pending-consumer state: beaver fixed20, GREA and the real whole App41 project clone pass SDK adoption, independent cold reopen and rollback. Validation covers 4,054 actual references (2,404 scripts and 1,650 object pointers), 32 canonical native MonoScript GUID/localID/type identities and two fully disabled retained DLLs, including actual canonical compilation/load origin. The formal 55,767 source entries remain unchanged; rollback restores the exact 55,763 scenario inputs. The fixed contract explicitly declares retained inactive assemblies and the larger bounded reference inventory instead of deleting copies or truncating real references.

beaver fixed21 is separately consumed through GREA against App40's actual default InputSystem/uGUI path: login, authoritative ordinary board swap, two normal exits and exact continuation of 15 fields pass, without a QA action pump, global-event fallback or source rebuild. These two exact local P0 scopes are now consumer-closed. This does not certify arbitrary SDK generations, complete game parity or the full product version. monkey dev9 declarations and the original A10 assets are unchanged; their producer-native `not_run`/unknown fields remain historical facts. No new export, font generation or native presentation rerun is required. New SDK bytes require fresh exact fixed evidence.

A later GREA consumer-metadata addition temporarily changed the same-name fixed20 integration receipt after its SHA was externally sealed. The original referenced bytes were restored exactly, and added results are retained in a separate append-only v2 closure supplement. The provider root and failed records were not rewritten. All twelve reviewed provider/native/consumer links and the supplementary public record hashes now match. This correction changes receipt organization only, not the SDK or Player results.

The frozen A10 manifest and handoff are not rewritten by subsequent SDK work. The incomplete first selection and failed scale/import candidates remain historical failures. Resource gaps with no new source are not re-searched. Reuse unchanged Editor/Player/font evidence; validate only the declaration change and actual migration consumers. No new full-pool recovery, remote push/release, global installation, services or player-data write is authorized here.

## Historical scope — 2026-10-30

Latest ordinary-Editor check supersedes the earlier Creator native-field pass as a candidate exit: opening the source detail Prefab exposed a parent background drawn after its child content. The common RenderFlow planner now submits normal parent renderers before descendants, retaining explicit sort values and mask/sort-root boundaries. Regenerate both targets and repeat native plus ordinary-Editor checks. The source queue and its generated readback agreeing with each other did not prove correct source rendering semantics. Current Unity work also preserves exact parent transform bases and source zero-axis scales and rebuilds clipped Images without losing their cull state. The candidate remains unaccepted until these changes pass.

After regeneration, ordinary Creator Prefab view displays the source title, labels and buttons again. Clicking the Editor's normal Save exposed a separate persistence defect: preview suppression layers were serialized on source Nodes because only the importer invoked the presenter's serialization guard. Preserve the before/after evidence and repair ordinary serialization, then recheck source layers and reopen. Native import/save helpers alone do not satisfy this ordinary-Editor gate.

The current work-in-progress checkpoint preserves the dual-Editor save/reload fixes and their neutral tests before the next repair increment. The next required exit is thirty of thirty selected source Prefabs passing static-field/resource-reference and native execution checks on each target. Preserve the existing successful unchanged evidence; repair common parsing, native carrying, persistence or verification causes. Source-null/dynamic-only exclusions require exact evidence. Do not use page/UUID/game-hash special cases, remove fields or convert nonempty references to null to pass. Creator identity/count/version failure must be decomposed and resolved. Visual review remains pending and dynamic business remains disabled/partial. The checkpoint is not this exit condition.

Checkpoint `696c376b0b9d83dfd6511913a529bf9b1a2fd3b2` was pushed to `origin/codex/v0.7-prefab-recovery`; remote readback matched. A second work-in-progress checkpoint `595973f6399392f0dfe0640c8c4951050ae8f0ea` was pushed and remote SHA read back before continuing the static-field repair. Later work remains local. This is work in progress, not a formal release. Then expand the original thirteen selected Prefabs to thirty distinct representative source Prefabs, with frozen source identities/hashes and component-coverage reasons. Dependency Prefabs and alternate states do not inflate the thirty-item denominator.

Run actual Creator 3.8.8 and Unity 6000.6.2f1 import/compile, load/instantiate, required fixed-state initialization, reference resolution and affected save/reload checks in bounded groups. Keep disabled/partial business behavior and unavailable dependencies explicit. This iteration does not require per-page screenshot comparisons; visual status is `pending_user_review`. Provide one existing-capability viewing entry point and per-target results for user review. No main/tag/Release, global installation or game-project changes are authorized.

The pushed checkpoint adds source-declaration-derived typed fields, nested Prefab synchronization, static state/list projection, font/outline fixes and optional native Spine/material bindings. The thirty-root source selection is frozen: seventeen additional roots are outside the original dependency closure. Normalization retains thirty selected roots and fifty-two closure Prefabs; a source ClickEvent value is preserved separately from node components. Source-defined packed colors and contradictory primitive decorators preserve actual values. The new font probe reports no missing required source glyphs. All fifty-one Spine resource identities have native Creator probe evidence; known dynamic no-bone-motion diagnostics remain separate from static identity.

Current native execution completed Creator import, serialization and save/reload for all fifty-two closure Prefabs (thirty selected roots). Geometry, RichText, static-time materials and native animation assets passed their scoped checks. Overall static verification remains partial because source business fields still include unsupported or dynamic references, and three source Spine components have no statically assigned SkeletonData. These are not complete UI/gameplay acceptance.

Unity has created and verified all fifty-one Spine data assets. Native execution exposed and fixed source alpha import, deterministic material creation, empty initial Spine poses, actual UI submesh material binding, outline Sprite-frame resolution, repeated full-plan parsing and TMP outline material lifecycle. The fixed official Spine source now has a separate hash-verified Editor assembly pair, with the original Player assemblies retained and excluded from Editor; actual Editor assembly loading has passed. UI-color, outline and static-time shaders declare the clip rectangle and explicitly warm the mask variants. The final Unity candidate completed all fifty-two Prefab save/reload checks, with 52/52 supported native reference checks, zero missing scripts, scene reopen and editable roundtrip. Creator completed the same fifty-two closure Prefabs. All thirty selected roots now have per-target native-flow evidence and a private unified review index. Whole static-field verification remains partial: unsupported Animation/ProgressBar/other source references and dynamic Spine behavior remain explicit. No visual, gameplay or full-static-restoration acceptance is claimed. Failed, superseded and deliberately interrupted candidates remain distinct.

The older ten-of-thirteen visual gate and counts below are historical and superseded for this iteration. They remain evidence of earlier limits, not the current exit requirement.

## Historical acceptance and work before scope expansion

Freeze all 13 proposed core Prefabs against original source identities, resources and code. At least 10 distinct core Prefabs must pass both Creator 3.8.8 and Unity 6000.6.2f1: source-to-IR completeness, target native hierarchy/components/fields/references, static images/text/materials/layout in a source-evidenced fixed state, save/reopen and deterministic regeneration. Business scripts may be disabled, not run or partial, with all source fields and references retained. Dynamic behavior and physical input are a separate second phase. Unknown components remain in the source denominator. No acceptance by file counts or zero MissingScript alone.

A is original source/version evidence; B is the frozen pre-v0.7 pure monkey output; C is v0.7 pure output; D is the manually repaired game, used only for locating differences. Game repair scripts must not participate in B/C. Original server gaps remain explicit in the dynamic phase; they do not block independently proven static acceptance. Private source and sample receipts stay outside public artifacts.

Execution order: freeze source identities and baseline; implement independent component/field/reference/event accounting; fix shared source and target semantics; close static component/field/resource bindings; run isolated native/static-render/save-reopen/regeneration checks for each sample. Then extend dynamic scripts/events and input independently. Shared IR and targets have one primary writer. Reuse beaver for applicable native operations; coordinate Editor ownership before execution.

Current: all 13 source anchors are mapped; one instance variant retains an explicit base/override distinction. Original package bytes independently confirm the recovered code bundle and its version literal. Independent node/component/field accounting is integrated into normalization. The initial eleven-core baseline contains 627 nodes, 935 components and 181 custom occurrences (51 classes); these are not the larger dependency-closure totals.

Native subset import/save/reopen has run in both editors. Eleven Creator and four Unity source-bound local behavior components are emitted with unresolved semantics retained. Sixteen selected Spine resources pass Creator resource-reference and observed bone-motion probes; this is not yet Prefab component or visual acceptance. Unity native save/reopen now verifies 928 source nodes across 22 closure Prefabs, separately accounting for 68 TMP-generated nonpersistent submeshes. Source-pinned static fallback and DynamicOS fonts survive Editor exit with zero file-hash diagnostics; this is native subset evidence, not full core acceptance. Exact UI-color material references pass Creator native readback. User-provided visual references cover order states, shop scroll positions, avatar, handbook, goose details and construction; the user explicitly permits cross-version references, with versions recorded separately. Static component/field/resource binding and visual comparison remain incomplete. Static accepted samples: 0/13 on each target; dynamic accepted samples: 0/13; versionComplete=false. Source-family/CDN expansion including 3.8.5 is deferred. Only the explicitly authorized development-branch push is permitted; no formal release, global install or game writes.

## Integration checkpoint and current increment

All existing branch tips are contained in the verified development-branch checkpoint `6109a8b24067a0217ec48c31f4d8700571a6f4ff`; main, tags and formal release were not changed. The branch ledger is in [integration record](BRANCH-INTEGRATION-20261029.md).

The subsequent static-field increment preserves 217 custom components and 694 serialized fields from the existing dependency closure in both target plans. These are conversion-time records, not native field-carrier acceptance. Existing resources are hash-verified and reused. Declaration defaults and native binding remain unverified; all 217 retain their unsupported native disposition. A separate seven-criterion acceptance evaluator and thirteen-core matrix keep dynamic status independent. Static accepted cores remain 0/13 on both targets.

Next: derive typed field carriers and missing defaults from source declarations, bind exact native object references, then close representative fixed-state renders and save/reopen/regeneration using existing evidence. Prefer the source-evidenced shop and handbook states; GuideTalk asynchronous behavior stays outside this static critical path.

## Static-first convergence

First-phase exit: at least ten of the existing thirteen core Prefabs pass on both targets. Record source_identity, hierarchy, components_fields, asset_references, static_render, save_reopen and regenerate independently for every sample and target. All seven must pass; dynamic_behavior and physical_input remain separate. Never replace the core denominator with dependency closure counts.

Preserve all source components through native mappings or generated typed serializable field/reference carriers with business behavior disabled. Empty fieldless shells and zero MissingScript counts do not prove completeness. Carriers must be derived from source declarations, not game-specific templates. Distinguish serialized defaults from source-evidenced display states; missing display evidence remains unverified for the affected sample.

Reuse unchanged source freeze, font/material and 928-node native evidence. GuideTalk asynchronous typing, animation and close lifecycle no longer block the first static result. Select representative cores by available static evidence and close their real graphics render, save/reopen and regeneration gaps in bounded groups.

Visual collection previously used Unity Null graphics, producing invalid gray PNGs. Native import has an explicit `--render-preview` option; capture rejects Null devices. Isolated previews activate only the root on a disposable clone and disclose that scope. Actual rendering is evidence to compare, not automatic visual acceptance. Reference versions remain explicit; cross-version screenshots are not same-version pixel proof.

## Generality requirement

The production recovery path must derive business behavior from source parsing and AST/IR lowering, not select handwritten game-specific templates by source hash, UUID or class name. Source hashes bind evidence and reuse; they are not business implementation selectors. Project-specific WeekTask and Goose WIP has been preserved privately and removed from the production package and public test suite. It is reference analysis only and contributes no complete acceptance.

The same production entry point must be tested with renamed symbols/UUIDs/paths, changed sorting and thresholds, and an independent neutral source example. Generated behavior must follow the changed source. Unsupported semantics remain partial. Existing finite known-behavior adapters require a separate scope audit and must not be reported as general JavaScript conversion. Native font/layout/material/resource fixes continue independently; the ten-core dual-target goal is unchanged.

## Historical pre-v0.7 status

# monkey release and implementation status

Current version: **0.6.0**. This release consolidates the native recovery branch and the source-toolkit branch on `main`; older implementation branches are preserved in history. Retired formatting/engine-emulation code is not revived by consolidation.

## Implemented scope

- Source-format parsing, resource acquisition with exact identities, project manifests and ownership-aware candidate export.
- Large-project parse budgets, stage reuse and explicit missing-source classification.
- Complete-source C# draft emission, source-linked diagnostics, optional bounded postprocessing, and a five-layer native architecture workflow.
- Serial module execution, exact checkpoint recovery, inherited-member evidence, immutable reassembly and pinned candidate revisions.
- Seven received source-side toolkit commands with compatible IDs, arguments, reports and exit codes.

## Evidence boundaries

A representative private candidate with 1,555 C# files compiled across all five actual assemblies with no errors and 3,249 warnings. An affected native core integration passed source-coordinate, 24 Sprite identity, 348-cell rendering, production/persistence/reopen and out-of-viewport rejection checks. Private source material and raw identity logs are excluded from public Git and distribution artifacts. These are historical scoped observations, not a publicly reproduced full-game acceptance.

Partial/unreviewed logic, unavailable original-server behavior and source gaps remain explicit. Physical input, original visual comparison, complete gameplay and Player builds are not implied. Two Editor Search startup exceptions remain recorded in the private evidence.

## Formal release

- Package, CLI and public metadata use 0.6.0.
- Preserve MIT and required third-party attribution, stable compatibility/API identifiers and public download URLs.
- Review the exact staged tree and distributions for private material before publishing `v0.6.0`.
- Verify remote main/tag/Release state and downloaded artifact hashes.
- Coordinate global installation through the designated integration owner; repository release work does not concurrently uninstall or replace shared installations.

Detailed public contracts remain in the adjacent documentation. Private coordination, source evidence and pre-redaction originals are retained outside the release tree.

## Bounded local maintenance

The active local branch addresses one received Unity 2021.3 SpriteAtlas resource subset: exact packing-bit interpretation, original float geometry and UVs, explicit DDS/DXT5 cache hydration, and ordered native Sprite identity readback. Original inputs remain immutable; candidate assets and raw evidence stay outside Git. The formal 0.6.0 release and global installation are not modified. Completion requires the affected source-to-native mapping and precise unsupported-case diagnostics, not another full-game export.

The affected resource subset passed Unity 6000.6.2f1 import/save/reopen: 29 ordered Sprite references, original float32 vertices and triangle topology, actual GUID/localFileID readback and exact native texture pixels. A separately bound source SpriteAtlas confirmed the packing/UV interpretation. A minimal native-asset closure and frame mapping are retained privately for consumer adoption. Game runtime wiring, visual parity and gameplay remain unverified by this maintenance. See [bounded atlas contract](providers/UNITY-ATLAS-SUBSET.md) for limits and importer policy.

A follow-up local resource request found two additional frozen leaf-Prefab closures outside the supplied dependency pool. Their bound source atlases contain 35 and 34 frames and require the narrow FlipHorizontal/Rotate180 settings (69/77), now interpreted as reflections about the serialized atlas rectangle. Source-control vertex/topology checks are exact; the existing UV arithmetic tolerance is unchanged. Independent candidate generation reuses the same DDS/profile chain without repeating the full input pool. Both candidates passed native import/save/reopen, all 69 ordered Sprite identities and exact texture pixel readback; the 38 focused tests also passed. The minimal consumer closure has 69 Sprites, two textures and their metadata, with original field order and per-frame mappings. Native consumer handoff remains separate from game runtime integration and publication.

Another local hydration extension accepts frozen literal cache buckets and an optional source-SHA/file/pathID/raw-SHA/logical-path selection manifest. It atomically hydrates a bounded explicit Texture2D set while retaining all unselected bytes and reporting unprocessed textures as deferred. A partial derivative remains nonzero CLI status and cannot imply whole-container success. Private synthetic two-texture UnityFS cases exercise the real pinned UnityPy/ASTC/DDS workers with 256x512 pixels in bucket 256; consumer source/native acceptance is still separate. See [exact texture selection](providers/UNITY-TEXTURE-SELECTION.md). No formal release or shared installation is replaced.

The follow-up selected PNG outlet now bypasses the whole-container exporter entirely: it binds the original, selected derivative, selector and externally pinned hydration receipt, independently checks unselected bytes and selected RGBA pixels, and emits only PNG candidates with provenance/importer-intent metadata. Partial container state is retained, no native GUID/import is claimed, and the consumer owns controlled adoption. A synthetic 225-texture case covers one exported texture with 224 deferred keys without deleting or decoding those unrelated objects.

## Local P0 Shader evidence handoff

The approved P0 adds a content-first Shader classifier and `classify-unity-shaders` for existing frozen candidates. `monkey-shader-handoff/1` separates recognizable source candidates, platform-compiled data, recovered binary evidence, unknown content and unsupported asset kinds. Native compilation remains `not_run`; source-text only requests source review. New recovery inventories carry explicit Shader hold/review dispositions, without removing referenced evidence or changing legacy exported-file counts into runtime approval.

The bounded existing-candidate check classified 126 serialized platform-compiled Shaders and one unsupported variant collection, hashing about 5.5 MB of Shader/meta content rather than rerunning the full pool. All 127 target identities are serialized declarations, not native readback. The old source map lacks original object associations for the 126 Shaders; these remain explicitly unmapped, with no name-based ID or raw hash inference. A neutral consumer-contract check is accepted by beaver's read-only planner and remains blocked for unproven dynamic runtime use; it is not Editor or isolation-execution evidence.

The fixed candidate, game project, shared installation and formal release are unchanged. beaver owns actual build target/pipeline, dependency coverage, native identities/compilation and any reversible filtering; game-directory migration remains with its owner. No P1 parser/recovery expansion is included. Public schema/example/CLI and limitations are in [Shader handoff](providers/UNITY-SHADER-HANDOFF.md).

## 2026-10-29 current static recovery acceptance

The source-generated StaticBatch10 candidate supersedes the earlier P07 checkpoint and eleven-core audit. P07's source-backed locked state now passes actual Unity 6000.6.2f1 and Creator 3.8.8 open/save/unload/reopen with visible screenshots, six complete native static carriers, and verified state operations. The full Unity independent PNG is visually checked; the live reopened layout is stable. Both windows remain on P07.

P04 and P09 also have actual dual-Editor saved/reopened screenshots. P04's missing untrimmed nine-slice border and P09's Creator RichText fontColor persistence are fixed. P04 still has a heavier Unity title and only 1/5 complete native carriers; P09 has 0/2, with explicit unresolved declarations/references. The other eight baseline pages lack fixed-state dual-Editor visual acceptance. Eleven-interface completion remains false; snapshot-json is not counted as native typed completion. Source Prefabs remain separate from derived preview states; only the latter freeze evaluated Unity layout for static display.

Private current evidence: `.private/v070-prefab-20261029/StaticBatch10/acceptance.json` and `验收说明.md`. Same-plan bounded exports reproduce all 914 Unity and 715 Creator generated files byte-for-byte; this is exporter determinism, not a second native import. 58 focused tests passed. No Player/gameplay/full-state acceptance or release is implied. Next work is the remaining actual field/reference/visual gaps, starting with P04 title rendering; do not expand accounting scaffolding or claim all eleven complete.


## Static continuation after the bounded checkpoint

Continue the original thirteen-sample matrix and source-backed component combinations; the eleven-page audit and P07 checkpoint do not complete this work. Current integration adds Creator 2.4 auto-synced nested Prefabs, source-defined list clones, typed record arrays, exact asset redirects, static COLOR Buttons and native material references. P04 font weight correction is compiled but awaits a fresh native candidate. StaticBatch11 preserves pre-Editor integration failures; none is counted as visual acceptance.

Primary owns shared preview integration, final candidate export and both Editors. Isolated modules own clone validation/helpers, P03 source fixtures/font supplementation, Spine static binding, and P05/P02 fixtures. Original source assets and prior native evidence remain immutable. All new fixture states explicitly distinguish test inputs from observed player state.


## Active static presentation closure

The development-branch checkpoint is preserved. Subsequent work remains local. The bounded thirty-root, fifty-two-Prefab closure requires actual static presentation as well as typed fields and asset references. Existing native checks for 1,035 field bindings and 334 animation reference bindings are reused. Missing Image/TMP components, masks, outlines, source sorting scopes and editable layout/constraint semantics remain required work; source-disabled or absent-font cases retain their source evidence and denominator. Particle playback and unlowered timeline/business behavior remain explicitly unexecuted; their serialized fields/resources are retained separately. Creator retained-document verification now preserves serialization-reserved source keys as opaque source text; native texture decode verification remains under repair. Visual comparison is pending user review and full static restoration remains false. Native Editors are closed only after completed/failed execution, never merely because loading is slow.


## 2026-10-30 development checkpoint and adoption

Preserve the current valid static-recovery implementation, tests and required documentation on the existing development branch before continuing repairs. This checkpoint is work in progress, not native acceptance. Complete the current thirty distinct Prefabs across both declared Editors before fixing a `v0.7.0.dev1` candidate identity and providing the native matrix, local tool entry, boundaries and adoption steps. Adopt only needed modules in the existing Unity/Go consumer project without overwriting business logic or forcing a full reimport. Generic conversion defects remain tool work; product behavior remains consumer work. No main merge, release tag, public Release or global install is authorized by this checkpoint. Visual comparison remains pending user review; dynamic business is outside this static pass.


Continuation after checkpoint `9f590c90f73d5787e478a91dff8c9bb0e29c0227`: keep the current static recovery route and team. Resolve the current TMP character/material proof and Creator generated RichText Label field failures, then continue the unchanged native matrix. Handling import prompts or answering side questions does not complete this version. Known verified TMP Essential Resources prompts are handled by the primary operator. Full native acceptance and the dev1 candidate remain pending.

Ordinary Editor follow-up remains part of acceptance. The goose Prefab was saved and reopened through Unity's native menus with unchanged saved bytes. Creator's ordinary Prefab serializer exposed source-layer persistence and nested override defects that its earlier import/readback pipeline did not cover; both are tracked separately from native generation. A warm Creator undo snapshot error disappears after a cold reopen of the same bytes, but restart is diagnostic evidence, not its fix. The full matrix remains incomplete while these issues and later Unity TMP/Spine cases are under verification.


Creator ordinary-save follow-up now passes in the current bounded candidate: the goose and nested-card Prefabs were opened, saved, closed and reopened through the Editor, then all fifty-two saved Prefabs were freshly read again and independently verified. Source fields, layers, nested identities and pre-existing overrides are preserved; screenshots are retained for user review. Exact owned-object undo and retired-scene cleanup fixes pass repeated in-session readback without resetting user undo state. Unity remains under native verification; full dual-Editor acceptance and the fixed dev1 identity are still pending.


## 2026-10-31 bounded dev1 static acceptance

The current development candidate passes native static verification for all thirty selected distinct Prefabs and the complete fifty-two-Prefab dependency closure in Unity 6000.6.2f1 and Creator 3.8.8. Both Editors actually imported and saved the native assets; the goose Prefab was opened, saved, exited and reopened through native menus with screenshots. The final Unity goose file stayed byte-identical after ordinary saving. Creator also passed ordinary nested-Prefab saving and a fresh saved-asset reread; source layers, identities, fields and existing overrides remain intact. Independent verification uses the frozen native binding-plan bytes and exact source/asset/mesh identities, retaining the original geometry threshold.

This is the bounded v0.7.0.dev1 development candidate, not a formal release or full-game acceptance. Unity overall Editor status remains partial only for explicitly unexecuted dynamic Spine behavior and unlowered animation curves; native static validation passes. Visual review is pending the user, and source-empty/disabled states remain source-empty/disabled. Player interaction, dynamic callbacks, particle playback and business behavior are not accepted by this pass. The input blocker capture override applies only outside Play mode; Player retains its original lifecycle behavior, which has not been physically tested here. Adoption uses the fixed development identity and only required modules in the existing consumer project.

## Active continuation: editable runtime presentation and adoption

Preserve the fixed `a458790a68d57108b4cfe038d8aa565d5cc1599b` static candidate. The current priority is a repeatable recovery-to-adoption-to-consumer-validation chain, driven by the first selected consumer module. Source text, image, progress, visibility and native input must remain usable through ordinary project APIs; a persisted static mesh is not runtime mutation evidence. Repair confirmed recovery-output defects here without product-specific branches or business logic. Keep new runtime meshes separate from saved proof assets and preserve static Editor behavior.

The primary owns presenter integration, output declarations, fixed delivery and native validation. A bounded input module owns the supplemental source-target raycaster; a separate neutral native probe covers changed rendering and EventSystem routing. Neither module owns an Editor or consumer files. Coordinate non-GUID helper dependencies and generated-versus-saved identities with the adoption provider rather than implementing a second adoption engine. Reuse the existing native static receipts; run focused changed-path native checks and then consumer revalidation. The chain remains incomplete until the consumer actually uses a fixed repair and confirms its affected module. No full script recovery, full-pool reimport, formal release or global install is implied.

The saved-selection outlet is ready for a bounded development handoff independently of runtime presentation repair. It produces a clean selected native directory, preserves the original generated and saved identities, adds the known compile-time helper closure and reports unanalysed code/font coverage. A real selected module passed the adoption provider's read-only snapshot verification. The subsequent native mutation/input and consumer font expansion work remains under validation; this selection delivery does not certify it.

The local `0.7.0.dev2` selection-only checkpoint is `c279a6ac9ec3766a4550b5cfdaa5df6cced953c3`. Consumer public adoption, independent reopen and rollback passed for its declared payload, but an existing target shader include masked an omitted non-GUID shader dependency. That candidate is retained and is not complete-dependency acceptance. The continuation adds literal shader include closure and stable diagnostic ordering, native runtime template upgrades, and same-face consumer-corpus font completion with isolated native save/reopen. Basic native mutation, mask pixels, fallback-slot growth and lifecycle probes passed; the no-Graphic/sibling-target input case and final font identity checks remain under validation. Consumer pixel evidence with invalid framing was withdrawn and is not counted as a runtime counterexample.

The neutral native continuation now passes sibling-target input mapping, renderer tint, typed progress, mask pixels, TMP slot growth and lifecycle checks in Unity 6000.6.2f1. Input evidence uses native raycast plus a synthetic callback, not physical input. The separate font run exited with a bridge status-contract mismatch before save/reopen acceptance; the expected pending state is corrected and a fresh stage is prepared. Shared Editor ownership was explicitly returned to the consumer for its authorized HTTP configuration/build. Font native validation and consumer integration remain pending; no complete delivery is claimed.

The subsequent isolated native font run passes: the same static fallback now contains 435 glyphs instead of 425, all 17 consumer text strings resolve through the bound primary/fallback chain, and save/unload/reload preserves font/atlas/material GUIDs and local IDs plus unchanged primary asset hashes. Reload validation unloads the primary and fallback together to prevent stale fallback-character caches. Public finalization produces a clean 247-file candidate accepted by beaver snapshot verification with six declared compile dependency edges; temporary Editor helpers are excluded. The shared Editor window is returned. Player rendering and actual consumer adoption of this fixed runtime/font candidate remain required before the toolchain loop is complete.

## 2026-10-31 selected code proof and bounded resource follow-up

The current public selection has eleven unanalyzed C# diagnostics; the earlier count of twelve was a stage mismatch. Six helpers match exact bundled framework-only sources, and five disabled static-field carriers regenerate exactly from the original hash-owned import plan. The improved freeze records explicit per-script producer proofs instead of suppressing unknown-code warnings. A fresh 221-file selection passes snapshot verification with all eighteen inventoried scripts proven; original asset, metadata and code bytes are unchanged.

`audit-native-code-dependencies` supplements an existing frozen target without rewriting its manifest, diagnostics or font assets. It binds the original producer manifest/plan, regenerates carriers, recognizes the target's actual runtime template revisions, and includes every requires path/hash plus package manifest/lock pins. The existing 247-file font/runtime candidate has twenty-two proven scripts and no uncovered script under this bounded producer contract; its eleven original warnings remain serialized unchanged. Consumer-side independent binding checks pass; fixed implementation identity and actual public invocation are delivered separately from compilation, Player and business acceptance. No beaver adoption-contract change or repeated font generation is needed.

The approved resource follow-up is limited to exact missing badge IDs, four backpack theme IDs and the already obtained home-entry skeleton. Reuse existing indices and the backpack audit. The home-entry source references the S2 skeleton, not a same-named S3 image; selection omission must be distinguished from an unsupported conversion. No new source means no repeated search for the previously missing newer-version shop artwork. Product Player verification stays with the project owner.

The adoption provider independently reran the fixed dev4 public audit and obtained byte-identical evidence; GREA registered the typed operation. The project owner separately verified the adopted component in an actual Player: numeric/text/progress/CJK display and physical source-button click/disable behavior passed, without a weekly unlock/claim authority claim. These results are reused.

The bounded home-entry source and S2 resource closure are now normalized. The existing native Spine planner requires a matching Creator resource readback; no old probe contains this exact source ID. A new independent resource probe exposed two generic temporary-scene lifecycle defects: assembly Canvas recycle tombstones outliving destruction, followed by same-UUID Undo-owned identities outliving the destroyed assembly. Failed native runs and all source packets are preserved. Exact-owned teardown and retirement are under focused repair; source IDs, strict collision guards and external/user undo histories must remain protected. No A10 native component or visual acceptance is claimed until the resource gate and subsequent Unity proof actually pass.

The subsequent independent single-S2 Creator probe now completes native import and saved-scene readback with zero verification diagnostics. The existing static resource verifier confirms the exact skeleton hash/native UUID, thirteen bones, eleven slots and one atlas-page texture binding. The native runner exits its owned Editor only after the completed result; its controlled termination is recorded separately from import acceptance. Forty-four lifecycle/Undo Node checks and nine focused export/resource checks pass. Temporary build-scene retirement is constructor-owned, detached, strict-destroyed and resolver-null only; original saved-scene provenance and baseline/foreign protections remain. This fixes the non-retained assembly path used by the probe; unrelated retained-prefab release behavior is unchanged. Resource identity is accepted, while Unity component/initial-pose verification remains pending.

The exact home-entry selection subsequently passes Unity native import/save/reopen and static validation. Ordinary GUI save/reopen preserves the Prefab bytes, and a regular isolated native scene renders the exact S2 initial pose. Correct framing also exposes a real scale gap: the pinned SkeletonGraphic multiplies mesh vertices by Canvas reference pixels per unit, while the previous unit plan left SkeletonDataAsset scale at one. On an actual PPU-100 Canvas this produces a hundredfold size error. Those receipts remain intact and are not visual-parity acceptance. The bounded continuation adds explicit per-component renderer/PPU unit evidence, rejects incompatible shared data contexts, and requires a fresh native candidate with correct saved scale and measured geometry; source node transforms and global Canvas PPU remain unchanged.

The corrected fresh candidate passes actual Unity import/save/reopen and native-static validation with the saved data scale at .01, an actual PPU-100 QA Canvas and the original .75 node scale unchanged. The full card, red dot and source-literal time bar are visible in the ordinary reopened Prefab GUI and clean native images; forty-four skeleton vertices and a separately rendered skeleton-only image prove the resource is consumed. Ordinary save/reopen preserves the source Prefab bytes, and the owned GUI exits normally after acceptance. The sole dynamic-behavior warning remains; no current-season/time authority or product adoption is claimed. Native checks compare saved scale with the frozen plan rather than a fixed scale of one.

The subsequent selected payload exposes a separate closure gap: it includes only the GUID-referenced Editor Spine assembly, omitting its core and Player pair plus non-GUID helper requirements. That original payload is preserved and rejected. The selection continuation must bind the already verified producer runtime declarations, include its exact paired DLL/importer/license/shader closure, and prove the selected project compiles independently before consumer handoff. No broad assembly parser, duplicate dependency auditor, product modification or repeated full-pool recovery is authorized by this repair.

The fixed selection now carries the manifest-owned Spine runtime pair, importer scope, license and shader records plus the exact missing mask helper. Its public freeze has eighty-seven files, no diagnostics and eight producer-proven scripts; the separate public dependency audit has no uncovered script. An independent Unity Editor opens and compiles that payload, then reloads the exact saved Prefab with zero missing scripts, unchanged GUIDs/bytes, correct scale and the expected skeleton/material references. A fresh clean refreeze has the same manifest and all eighty-seven payload bytes, without the validation Library or helper. The existing adoption provider independently accepts the clean snapshot, C# dependency declarations and evidence hashes without a contract or tool implementation change. Destination incremental adoption, actual product rendering and dynamic/season authority remain with the project owner. Old incomplete payloads and native failures are retained.

## Local maintenance — 2026-11-02

Authorized cleanup removed245 inactive regenerable Unity Library caches only; current three WIP caches, fixed dependencies, candidate resources, source inputs and transaction evidence retained. Exact deletion and disk metrics: `.private/cleanup-20261102/REPORT.md` and `report.json`. No engine run or version acceptance was added.
