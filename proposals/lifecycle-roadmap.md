<!-- Historical inherited plan; local home paths redacted. Original SHA256 268636825960249190985a1bb4a4ecf3dc98596fb568400f0a58f8d7c46120a4; current plan is consolidated in the following cleanup commit. -->
> 发布脱敏摘要：本文含原始回执的公开摘要；脱敏前原件仅保存在私有冻结目录。

# GREA 全生命周期版本路线与开发进度

2026-11-04｜状态：**GREA v1.0.0已正式发布并完成整包回读。** main/tag源码16996f4，精确monkey0.7.0＋beaver0.6.0正式制品锁定；双平台CI/搬迁隔离/临时Codex与CLI/MCP代表组合通过。两平台ZIP字节与审核候选一致，8资产、模块锁和五Skill图标完整核验。原根119项WIP文件逐SHA保持，仅本PLAN由owner更新；不改游戏固定入口、全局或活跃插件缓存。**本文件为唯一产品进度入口。** 下方日期版里程碑与兼容条目为历史/原范围记录。

## Manager只读当前任务投影

以下是本PLAN的唯一机器投影；上方版本来自源码/插件声明，不创建新版本或新台账。任务done仅限所列验收范围；原文历史保留。

```manager-task-view
{
  "schemaVersion": 1,
  "projectId": "grea",
  "updatedAt": "2026-11-04T12:31:13.009013+00:00",
  "authority": "original-plan-owner; read-only projection, not canonical cutover",
  "currentVersion": "1.0.0",
  "currentStage": "立即三仓库分支整改：GREA本地/远端已仅v1.0.0、v1.1.0.dev2；用户最新要求monkey合并为唯一v0.8.0系列，0.7字体/Toggle/引用修复先合入后退休0.7 heads；beaver迁移中。四页固定候选及WIP保留，binary暂停。",
  "activeImplementationTask": "grea:T-repository-version-branches",
  "releases": [
    {
      "id": "grea:R2026.10.27-maintenance",
      "title": "GREA 2026.10.27 同版本地维护",
      "version": "2026.10.27",
      "workflowStatus": "in_progress",
      "description": "源码和插件声明版本保持2026.10.27；fixed provider为独立精确候选，非GREA新发布版本。已完成当前入口维护，外部消费和兼容入口统一退役仍分属项目owner/运维；无新增发布安装授权。",
      "acceptanceCriteria": [
        "既有工具ID及阶段门保持，精确provider绑定与受影响入口检查有证据",
        "迁移保留WIP/Git与历史锁，源CLI/MCP及五技能在新根可用",
        "不以本地绑定、consumer静态采用或迁移通过冒充完整产品/新发布验收"
      ],
      "sourceRefs": [
        "pyproject.toml:project.version",
        "plugin/version.json:version",
        ".private/coordination/myprojects-migration-20261103/migration-verification.json"
      ],
      "versionKind": "historical_compatibility"
    },
    {
      "id": "grea:R1.0.0",
      "title": "GREA v1.0.0 正式收口",
      "version": "1.0.0",
      "workflowStatus": "done",
      "description": "正式v1.0.0于2026-11-04T07:39:13Z发布，main/tag源码16996f4；双平台完整ZIP与审核字节一致，8资产SHA/组件锁/5Skill图标及tag/Release已完整回读。原根WIP保全，未更新游戏/全局/活跃插件。",
      "acceptanceCriteria": [
        "两平台完整插件包/许可证/图标/版本/精确依赖一致",
        "从打包制品隔离安装，公开CLI/MCP代表链和拒绝护栏实际通过",
        "明确平台/静态/动态/视觉/Player支持边界，Windows原生以CI实际结果为准",
        "先发组件、更新最终hash后发GREA，回读tag/Release/下载SHA"
      ],
      "sourceRefs": [
        "Manager/decisions/20261104-toolchain-stable-release/PLAN.md",
        ".private/releases/v1.0.0/published-readback-index.json"
      ]
    },
    {
      "id": "grea:R1.1.0",
      "title": "GREA1.1条件开发：双项目工具调用闭环",
      "version": "1.1.0",
      "workflowStatus": "in_progress",
      "description": "已交观测dev1本地候选；新增已授权二进制分发主线，稳定模块输入先Mac后Windows。当前无新公开版；源码wheel迁移改造已停止/私有保留patch，新公开包不带内部实现源码。",
      "acceptanceCriteria": [
        "消费者固定交付/采用/结束条件与运行时责任一致",
        "仅适配已交且确有缺口的有限公开合同",
        "相关消费者有限验证通过，未验/无适用性明确",
        "先Mac后Windows独立编译身份/搬迁/代表流程验收",
        "新GREA公开源码及完整包只含已审模块二进制和明确helper白名单，旧历史保持"
      ],
      "sourceRefs": [
        "Manager/decisions/20261104-product-driven-tooling/PLAN.md"
      ],
      "candidateVersion": "1.1.0.dev1"
    }
  ],
  "tasks": [
    {
      "id": "grea:T-migration-entry-20261103",
      "title": "迁移GREA源码、技能和当前固定provider入口",
      "primaryReleaseId": "grea:R2026.10.27-maintenance",
      "workflowStatus": "done",
      "description": "新根入口与重启后原会话执行器已验证；版本未升级。整个工作区旧别名退役不在本项完成声明内。",
      "acceptanceCriteria": [
        "116项迁前WIP及HEAD/refs保持；只做定点路径修复",
        "新根CLI/MCP及fixed29 readiness通过，五技能副本一致",
        "fixed31/fixed29/dev7另建同版新锁，旧锁原字节保留",
        "重启后cwd/realpath/Git顶层及唯一临时文件写读删成功"
      ],
      "blockerIds": [],
      "sourceRefs": [
        ".private/coordination/myprojects-migration-20261103/migration-verification.json",
        ".private/coordination/myprojects-migration-20261103/post-restart-executor-check.json"
      ]
    },
    {
      "id": "grea:T-qa8-fixed31-binding",
      "title": "交付屏外纯移动修正的QA八路固定绑定",
      "primaryReleaseId": "grea:R2026.10.27-maintenance",
      "workflowStatus": "done",
      "description": "fixed31仅QA8已直接交肥鹅；intake保持fixed29。GREA绑定验收完成，项目新QA Player的运行结论不由本项推定。",
      "acceptanceCriteria": [
        "精确producer/package入口pin通过，143运行文件与13索引pin一致",
        "20合同检查通过，19定向原生及未变矩阵按范围复用",
        "保留按钮/拖动/键盘/未知状态接管保护，交付消费者准确配对入口"
      ],
      "blockerIds": [],
      "sourceRefs": [
        "validation/development/beaver-fix31-qa8-integration-20261103.json",
        ".private/coordination/myprojects-migration-20261103/migration-verification.json:bindings"
      ]
    },
    {
      "id": "grea:T-compatibility-retirement-handoff",
      "title": "等待统一确认旧路径消费者重绑后退役兼容入口",
      "primaryReleaseId": "grea:R2026.10.27-maintenance",
      "workflowStatus": "blocked",
      "description": "GREA已交迁移配对；旧27/30事务和AppSupport历史身份有旧路径，不能由GREA自行删除运维临时别名。仅等待实际消费者/运维统一收口，不新增巡检或产品复验。",
      "acceptanceCriteria": [
        "运维确认受影响会话、工具和历史事务路径均可脱离旧别名",
        "由运维执行统一退役；GREA仅处理新发现的自身入口问题"
      ],
      "blockerIds": [
        "grea:B-ops-old-alias"
      ],
      "sourceRefs": [
        ".private/coordination/myprojects-migration-20261103/migration-verification.json:remaining_old_consumers"
      ]
    },
    {
      "id": "grea:T-build-provider-readiness-20261103",
      "title": "修复显式固定provider readiness并交付同版构建入口",
      "primaryReleaseId": "grea:R2026.10.27-maintenance",
      "workflowStatus": "done",
      "description": "肥鹅真实unity.plan已通过；显式monkey锁保留全部身份门禁，build使用fixed17、QA保持fixed31。仅计划通过，不签编译或产品验收。",
      "acceptanceCriteria": [
        "16项定向测试、真实固定锁漂移拒绝及QA工程错用拒绝通过",
        "真实产品请求由fixed17执行unity.plan返回executed=true/ok",
        "旧锁/包身份保留，无升级/全局安装/Unity启动"
      ],
      "blockerIds": [],
      "sourceRefs": [
        ".private/build-provider-repair-20261103/delivery-index.json"
      ]
    },
    {
      "id": "grea:T-stable-release-pack",
      "title": "保全WIP并整理正式候选及双平台分发",
      "primaryReleaseId": "grea:R1.0.0",
      "workflowStatus": "done",
      "description": "最终main16996f4：发布分支和main的源码CI/双平台dryrun四轮通过，五Skill图标/包身份闭包通过，完整双平台包已由原生CI安装验收；最终索引已交总监。",
      "acceptanceCriteria": [
        "隔离worktree和WIP快照",
        "公开树审计与版本/文档/许可证一致",
        "完整平台候选包精确索引"
      ],
      "blockerIds": [],
      "sourceRefs": [
        "Manager/decisions/20261104-toolchain-stable-release/PLAN.md"
      ]
    },
    {
      "id": "grea:T-stable-combination-acceptance",
      "title": "隔离安装并验收恢复到采用的CLI/MCP组合",
      "primaryReleaseId": "grea:R1.0.0",
      "workflowStatus": "done",
      "description": "已核最终远端monkey0.7/beaver0.6 wheel同字节。完整候选隔离安装10项CLI/MCP、外部集成6项及最终双平台分发验收通过，静态/native/视觉/业务范围分列。",
      "acceptanceCriteria": [
        "精确组件候选从制品安装",
        "中性代表链实际调度/数据保护/partial拒绝语义",
        "无游戏写入/全局安装"
      ],
      "blockerIds": [],
      "sourceRefs": [
        "Manager/decisions/20261104-toolchain-stable-release/PLAN.md"
      ]
    },
    {
      "id": "grea:T-stable-release-publish",
      "title": "验后发布并回读正式制品",
      "primaryReleaseId": "grea:R1.0.0",
      "workflowStatus": "done",
      "description": "总监grea-publish-approved-08放行后，正常tag触发41793202524成功发布。远端v1.0.0/tag peel16996f4、manifest、两完整ZIP实下载SHA、8资产服务端digest、组件锁及5Skill图标闭包核验通过。",
      "acceptanceCriteria": [
        "总监候选核查",
        "组件先发布且最终hash入锁",
        "正常tag/Release及远端下载回读"
      ],
      "blockerIds": [],
      "sourceRefs": [
        "Manager/decisions/20261104-toolchain-stable-release/PLAN.md",
        ".private/releases/v1.0.0/published-readback-index.json"
      ]
    },
    {
      "id": "grea:T-zombie-build-runtime-20261104",
      "title": "恢复僵尸固定beaver0.5构建运行时及新绑定",
      "primaryReleaseId": "grea:R2026.10.27-maintenance",
      "workflowStatus": "done",
      "description": "复用与旧锁同SHA的保留Python3.12.14，私有新venv实际导入原包，包文件/capabilities完全同旧锁。新消费者锁及原dev4 unity.plan通过；旧锁/包/wrapper/global未改，无Editor/build/Player执行。",
      "acceptanceCriteria": [
        "同版原包与真实导入核验",
        "新入口/配对providers/新锁可用",
        "实际unity.plan成功且原锁和全局未改"
      ],
      "blockerIds": [],
      "sourceRefs": [
        "${USER_HOME}/MyProjects/Games/projects/21-zombie-cannon/Analysis/v010-development-20261104/build-runtime-repair-grea-01/delivery-index.json"
      ]
    },
    {
      "id": "grea:T-product-tooling-methods",
      "title": "消费者驱动的固定交付与结束方法",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "done",
      "description": "独立开发worktree实修4份Skill文档，159文档/五技能闭包与隔离同步通过。",
      "acceptanceCriteria": [
        "绑定真实消费者及固定交付身份",
        "无第二执行器、全局切换或游戏重验",
        "方法通过不等于消费者采用"
      ],
      "blockerIds": [],
      "sourceRefs": [
        "${USER_HOME}/MyProjects/Tools/grea/.private/development/product-driven-20261104/first-batch-index.json"
      ]
    },
    {
      "id": "grea:T-runtime-ownership",
      "title": "登记固定依赖实际运行时归属与退役条件",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "done",
      "description": "旧0.5恢复/成功构建复用；新0.7观测候选已部署至GREA明确保留、独立于开发/插件缓存的前缀并记录解释器/依赖/retention。旧0.5私有兼容仍保留，不假称已迁长期部署。",
      "acceptanceCriteria": [
        "绑定真实消费者及固定交付身份",
        "无第二执行器、全局切换或游戏重验",
        "方法通过不等于消费者采用"
      ],
      "blockerIds": [],
      "sourceRefs": [
        "${USER_HOME}/MyProjects/Tools/grea/.private/development/product-driven-20261104/first-batch-index.json"
      ]
    },
    {
      "id": "grea:T-player-observation-adapter",
      "title": "接收beaver公开观测合同并做最小适配",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "in_progress",
      "description": "GREA1.1dev1/beaver0.7dev1已被僵尸真实单次启动/观测/STOP/回收/168制品后验部分采用；真实normal quit/deadline/completed cold及旧生命周期退役未完。肥鹅相关QA/profile已接受且新模式不适用；不复派工具、不重复实玩。",
      "acceptanceCriteria": [
        "绑定真实消费者及固定交付身份",
        "无第二执行器、全局切换或游戏重验",
        "方法通过不等于消费者采用"
      ],
      "blockerIds": [],
      "sourceRefs": [
        "${USER_HOME}/MyProjects/Tools/grea/.private/development/product-driven-20261104/first-batch-index.json",
        ".private/development/product-driven-20261104/beaver070dev1-handoff-index.json",
        "${USER_HOME}/MyProjects/Tools/beaver/.private/product-driven-v0.7.0-20261104/lead-handoff.json",
        "${USER_HOME}/MyProjects/Tools/grea/.private/development/product-driven-20261104/beaver070dev1-consumer-adoption-supplement.json"
      ]
    },
    {
      "id": "grea:T-monkey-bounce-ruling-v2",
      "title": "按更正完整冷读裁定Bounce静态表示映射",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "done",
      "description": "纠正旧scalar0/keys1错误目标；独立核两来源完整签名冷读及8原件SHA，批准仅版本/字段/数值限定profile实现。monkey完整根与候选采用仍待交，不计恢复完成。",
      "acceptanceCriteria": [
        "旧裁定原件保留并撤回误值",
        "更正签名及原件SHA核验，有界实施/拒绝条件书面交owner"
      ],
      "sourceRefs": [
        ".private/development/product-driven-20261104/particle-constant-ruling-v2.json"
      ]
    },
    {
      "id": "grea:T-binary-provider-macos",
      "title": "GREA二进制模块身份与Mac独立分发验收",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "in_progress",
      "description": "用户最新先四页真实Prefab及采用，binary在安全点暂停新编译/打包/兼容扩展/Windows，保留已有源码/WIP/候选。两ownerMac任务已实际派发；beaver稳定源首probe ARM64已编译/基础隔离CLI通过但不可安装，发现身份空map、worker、runpy、helper及cap envelope operationId波动5项，已由GREA有界裁定；GREA独立binary安装/pin WIP、稳定投影与拒源码fallback护栏，不代表Mac组合完成。 GREA适配源码1.1.0.dev2/ecbdd2a已本地提交，237相关检查通过；新完整包主动拒源码fallback。",
      "acceptanceCriteria": [
        "monkey0.7/beaver0.6稳定源码编译，非源码归档fallback",
        "实际Mach-O及全部资源SHA/capabilities/版本/来源锁定；旧Python模式不放宽",
        "独立搬迁/源码不可访问/代表链与拒绝/生命周期实际通过",
        "helper/模板/嵌套归档白名单边界核验；未验资源仍拒绝发布"
      ],
      "sourceRefs": [
        "Manager/decisions/20261104-grea-binary-distribution/PLAN.md",
        ".private/development/binary-distribution-20261104/binary-provider-contract-v1.json",
        ".private/development/binary-distribution-20261104/first-batch-index.json"
      ],
      "executionStatus": "paused_by_user"
    },
    {
      "id": "grea:T-binary-provider-windows",
      "title": "Mac通过后Windows x64原生编译及调用",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "planned",
      "description": "用户最新先四页真实Prefab及采用，binary在安全点暂停新编译/打包/兼容扩展/Windows，保留已有源码/WIP/候选。待Mac组合通过；仅允许无资源占用设计准备，不先并行构建。",
      "acceptanceCriteria": [
        "原生Windows构建/调用/搬迁身份与受影响代表链实际通过",
        "Unity/桌面未验明确单列"
      ],
      "sourceRefs": [
        "Manager/decisions/20261104-grea-binary-distribution/PLAN.md"
      ],
      "executionStatus": "paused_by_user"
    },
    {
      "id": "grea:T-binary-unified-publication",
      "title": "公开GREA源码与内部模块二进制统一发行",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "planned",
      "description": "用户最新先四页真实Prefab及采用，binary在安全点暂停新编译/打包/兼容扩展/Windows，保留已有源码/WIP/候选。已有用户按序验后发布授权；须先精确双平台候选/CI受控制品与新源码边界通过，不覆盖历史tag或当前固定链。",
      "acceptanceCriteria": [
        "公开树/全部嵌套制品无模块当前实现源码/pyc/生成C源或fallback",
        "私有构建向公开制品传递不泄凭据/源码/日志",
        "版本/完整包/能力锁/许可/下载SHA回读一致"
      ],
      "sourceRefs": [
        "Manager/decisions/20261104-grea-binary-distribution/PLAN.md"
      ],
      "executionStatus": "paused_by_user"
    },
    {
      "id": "grea:T-foodstreet-four-activity-bulk",
      "title": "肥鹅四活动完整Prefab经GREA成组恢复与采用",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "in_progress",
      "description": "经GREA公开run-tool调用固定monkey0.7.1.dev1/0da189a，实际native03产出四根及必要子Prefab共11个、668节点，Unity exit0、missingScripts0、保存重开/可编辑回读true。ASTC依赖与Toggle空可选配置工具修复已实测解除。验收仍partial：311静态字段/引用共因与52字体转换缺口由monkey修复，不能以完整业务脚本/全警告清零为前置；beaver实际采用尚未运行。禁止逐页人工修改纯输出。",
      "acceptanceCriteria": [
        "实际GREA公开入口批次请求/纯输出/完整依赖闭包和固定工具身份",
        "三层比较纯输出共因修工具，采用保既有GUID/WIP/存档",
        "四页完整静态布局/组件/图片及同版本UI对照/适配/正常输入通过",
        "接原有业务并退役覆盖性替代作者，不复跑未变已过业务"
      ],
      "sourceRefs": [
        "Manager/decisions/20261104-foodstreet-activity-bulk-recovery/PLAN.md",
        "${USER_HOME}/MyProjects/Games/projects/20-foodstreet/Analysis/v050-development-20261104/FOUR-ACTIVITY-RECOVERY-CONSUMER-INPUTS.json",
        ".private/development/foodstreet-activity-bulk-20261104/coordination/grea-monkey-bulk-04.json",
        "${USER_HOME}/MyProjects/Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/toolchain-entry-index.json",
        ".private/development/foodstreet-activity-bulk-20261104/critical-path-astc-resume.json"
      ],
      "evidence": [
        "${USER_HOME}/MyProjects/Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-native-03-toggle-index.json"
      ]
    },
    {
      "id": "grea:T-monkey-dev8-consumer-handoff",
      "title": "僵尸dev8两完整根固定候选的增量采用交接",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "planned",
      "executionStatus": "queued_after_foodstreet_safe_point",
      "description": "已收内部Python0.8dev8/203161f双根native-partial固定包，未做GREA新绑定/采用；保护既有59对和业务覆盖，不抢四页关键路径，不当binary包。",
      "sourceRefs": [
        "${USER_HOME}/MyProjects/Tools/monkey/.private/unity-prefab-v080-20261104/dev8-fixed-two-root-handoff-index.json"
      ]
    },
    {
      "id": "grea:T-zombie-first-level-source-gap",
      "title": "首关1001必要升级链有界静态补证",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "planned",
      "executionStatus": "queued_after_foodstreet_safe_point",
      "description": "按僵尸明确请求排在四页自然安全点后；只复用工具补方法体/加载族/Pool2必要配置映射，可证与UNKNOWN分开，不执行原JS/WASM/DLL、不全量重导、不扩大v0.2构筑；尚未派新执行。",
      "sourceRefs": [
        "${USER_HOME}/MyProjects/Games/projects/21-zombie-cannon/Analysis/v010-development-20261104/first-level-upgrade/source-gap-index.json"
      ]
    },
    {
      "id": "grea:T-repository-version-branches",
      "title": "立即清理三仓库废弃分支并统一版本命名",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "in_progress",
      "description": "GREA已完成本地21→2/远端9→2，默认v1.0.0，53ff3bc已推；标签/5工作树WIP未变。monkey首轮18→3已独立回读，后被本聊天最新人类指令覆盖：必须合并为唯一v0.8.0系列，先归并0.7修复再删除0.7系列heads，owner执行中。beaver仍在执行，不能报三仓库完成。",
      "sourceRefs": [
        "${USER_HOME}/MyProjects/Manager/decisions/20261104-grea-repository-cleanup/PLAN.md",
        "${USER_HOME}/MyProjects/Tools/grea/.private/development/repository-cleanup-20261104/branch-migration.json"
      ]
    }
  ],
  "blockers": [
    {
      "id": "grea:B-ops-old-alias",
      "taskIds": [
        "grea:T-compatibility-retirement-handoff"
      ],
      "owner": "运维主管 local/01a19f0a-9171-72a0-b9b5-1f30a9130461，相关项目owner配合",
      "description": "临时旧路径别名仍承载历史固定事务/AppSupport旧身份；本会话重启执行器待验已解除，不再列为阻塞。",
      "releaseCondition": "运维确认全部实际旧消费者完成重绑且可安全退役，通知GREA实际需调整的剩余入口。",
      "sourceRefs": [
        ".private/coordination/myprojects-migration-20261103/migration-verification.json:alias_retirement",
        ".private/coordination/myprojects-migration-20261103/post-restart-executor-check.json"
      ],
      "workflowStatus": "blocked"
    }
  ],
  "currentVersionKind": "published_stable",
  "versionPolicy": {
    "standard": "${USER_HOME}/MyProjects/Manager/standards/VERSIONING.md",
    "nextFormalVersion": "1.0.0",
    "nextFormalDisplayVersion": "v1.0.0",
    "testVersionPattern": "1.0.0.devN",
    "defaultIncrement": "minor; reset patch to zero",
    "majorIncrement": "very large update; reset minor and patch to zero",
    "patchIncrement": "small correction",
    "currentDateVersion": "historical identity retained, not renamed",
    "newReleaseAuthorized": true,
    "authorization": "human01a1a53c-a6c6-7612-945a-72d479ac84c0; 先打包验收后发布"
  },
  "targetVersion": "1.0.0",
  "toolchainLead": {
    "agentId": "grea",
    "scope": [
      "grea",
      "monkey",
      "beaver"
    ],
    "modelTarget": "gpt-6-astra/medium",
    "authority": "Manager/decisions/20261104-grea-toolchain-lead/PLAN.md",
    "distributionAuthority": "Manager/decisions/20261104-grea-binary-distribution/PLAN.md",
    "distribution": "GREA public source + internal compiled modules; supersedes prior source-wheel distribution, historical releases unchanged",
    "singleWriters": "Existing module owner paths retained; games keep business/Editor ownership"
  },
  "binaryPausedByUser": {
    "authority": [
      "human01a1a65c-0301-7f70-80b3-a2172bd80cbf",
      "human01a1a65d-8760-7142-be3e-acae0b4fa141"
    ],
    "status": "paused_by_user",
    "scope": "new binary compilation/packaging/compatibility expansion/Windows; preserve WIP/candidates",
    "resumeCondition": "Four actual restored/adopted pages delivered for director acceptance; unresolved acceptance fixes retain priority, no unrelated automatic restart"
  }
}
```

## 当前批准任务（2026-11-04 v1.0.0正式收口）

用户原生授权已核：正式目标v1.0.0覆盖先前拟定v0.1.0；测试1.0.0.devN。原WIP120项快照保存在`.private/releases/v1.0.0/`，隔离分支`codex/release-v1.0.0`已建；当前dev1整理五技能/调度和维护源码，私有原始回执不入公开树。组件精确候选直交GREA，隔离组合验后交总监并按既有仓库正常发布，组件先发布再固定最终hash；不覆盖游戏入口/安装/锁、不抢前台。以下2026-11-03及更早条目仅历史，不作为当前暂停或版本编号。

**2026-11-03真实构建链路径修复完成。** 肥鹅unity.plan暴露shell dev7被按Python安装检查及QA31错用工程操作两层问题；新增显式GREA_MONKEY_LOCK路径，仍核原pinned/包/launcher/capability固定身份及锁前后哈希，不自动发现回退/安装。16定向测试通过，实际改锁拒绝，QA31在两provider ready后仍拒绝unity.plan；另建原fixed17同版build锁，对真实产品请求unity.plan执行ok，未启动Unity、不代表编译/构建通过。交付索引`.private/build-provider-repair-20261103/delivery-index.json`。owner wrapper须显式monkey锁并区分build17与QA31，旧包/锁不改。

**后续版本号过渡（2026-11-03）。** 按Manager `standards/VERSIONING.md`，下一个GREA正式版为`v0.1.0`，测试候选`0.1.0.devN`；日常默认递增次版本并将修订归零，小修递增第三位，超大更新递增主版本并清零后两位。当前`2026.10.27`仅历史兼容身份，源码/安装包、旧tag、证据及固定provider不原地改号。稳定任务/release ID保持；过渡说明与兼容清单判断升级，不按数字大小推断降级。此项只登记下次实际候选/版本的编号约定，不新增实现、打包、tag或正式发布授权，不触发全量重验。

**2026-11-03迁移入口收口：当前真实根`${USER_HOME}/MyProjects/Tools/grea`。** 运维整树搬迁后116项release WIP哈希与HEAD逐项匹配；editable环境4文件、Tools大小写workspace探测已定点修复，6相关测试通过。共享五技能在`${USER_HOME}/MyProjects/.agents/skills`同步0变更/check一致。source CLI与stdio MCP21工具启动正常；fixed31 QA8/fixed29 intake3/dev7均在迁移专用配置另建精确同版新锁（143/143/458包文件），新根MCP fixed29 readiness通过，无产品原生重验。迁移索引见`.private/coordination/myprojects-migration-20261103/migration-verification.json`。旧配置/锁/历史报告、冻结shebang和唯一original.git保持；旧27/30事务、AppSupport历史会话及Codex UI cwd尚需兼容别名，统一由运维最终退役。安装插件未升级，Manager仍按实际治理根；不宣称整批迁移或UI设置已完成。

**2026-11-03 fixed31/virtual6 QA8已配对。** 精确143文件/13pin及实际CLI pin通过，20合同检查通过；只补已知屏外无按钮未锁定主屏纯移动豁免，缺位置delta和按钮/拖动/键盘未知仍停。19定向原生证明与未变fixed30矩阵复用，无Unity/正式写入。索引[fixed31交付](../validation/development/beaver-fix31-qa8-integration-20261103.json)直接交肥鹅重建一次QA消费者；intake仍fixed29，旧原因和真人来源不推断。

**2026-11-03 fixed30/virtual5接管诊断QA8已绑定，待肥鹅新构建消费。** 精确source `62c400ed`/producer `cc6a7800…`，143运行文件source/wheel/install一致、15pin核验；仅virtual5+三bootstrap共8路，intake保持fixed29。CLI/独立MCP通道prepare及五SHA拒绝实际通过，2自建未绑定通道已清理；15合同检查及schema/docs/Skill同步通过，64producer检查与中性诊断/UI证据复用，不重跑旧矩阵。见[fixed30 QA8绑定索引](../validation/development/beaver-fix30-qa8-integration-20261103.json)。精确companion需owner重建QA Player；stopOnTakeover保护不变，onEvent刷新OS前台并写有界脱敏诊断，native事件不能推断人为来源，旧三次停止原因仍未知。只直接交实际消费者，不抄总监或因后续成功消息例行复验；未启动Player/Editor/写正式项目。

**通信收敛v2.1已采用（2026-11-02）。** 已读Manager COMMUNICATION第0节及九行模板：仅接收方需要行动/裁定/等待交付时直接协作，200–400字、一个证据索引；工具交实际消费者，不重复抄送总监，产品消费由项目主开发汇总。不因成功消息自动重复验收/另建报告/回ACK；普通进度留本任务源，独立验收仅版本出口、明确任务或新失败/证据冲突。历史逐fix/消费复核记录保留，后续不沿袭其重复通信模式。

**最新人类授权纠偏：正常打开App64 windowed+虚拟光标已取得真实画面。** 原生read_thread核最新human `01a19cc8-57c6…`直接要求打开App；此前将运行时不抢焦扩大成启动也必须零激活是过约束，已修Skill，不再全局阻塞。QA8/fixed27+既有virtual4/App64未新增producer或重建；observer四张510×936目标PNG的文件/源SHA核验并直接查看Mainline/bag/cooking/Street有效，snapshot473/22币71钻109体全同，strict live-stop五旗标+buttonfalse通过。见[授权windowed视觉补充](../validation/development/beaver-fixed27-foodstreet-authorized-windowed-visual-20261102.json)。owner UI506/513/522仅按报告当前scope通过，非真实活动业务/真人并行/启动前不激活保证；virtual capture操作仍不支持，图片来自项目observer。旧neutral黑帧与平台失败保留为有限历史，不能继续阻塞本次已授权路线。

**最新fixed29 DamageTip正式静态消费闭环：9根57pairs。** plan `d39d6865…`/journal `91fe5ee8…` complete/nativeVerified/processExited/exit0；wrapper partial/intakeStatus verified/无transporterror保留。原126540manifest项全同、新增18→126558，本轮有界核当前18新增+5旧Prefab/meta+既有asmdef/meta共30文件SHA；既有GameBase及Shader10753七次身份观察全同，code-check/cold新script实际GameBase归属/base/fields一致，128watchers/5声明解析边及双checkpoint通过，3独立进程exit0。53fields/5Prefab对象cold通过。见[DamageTip正式消费者补充](../validation/development/beaver-fix29-zombie-damagetip-consumer-20261102.json)。只签静态schema与目标原生身份：新carrier禁用、5旧实例运行激活未验、动态网格未实现、sourceShader gap/语义/视觉Player业务仍未验；旧失败保留，无重放/重冻/GREA Unity启动。

**DamageTip Shader目标六元身份已有复用证据。** 既有6000.6.2f1 probe唯一f域10753=UnityEngine.Shader/CoreModule/Sprites/Default/Resources/unity_builtin_extra，GREA核四证据pin及精确唯一行。见[目标Shader身份复用](../validation/development/beaver-fix29-damagetip-shader-identity-reuse-20261102.json)。固定29合同/绑定不变，交owner显式补engineObjects并fresh spec5 plan；正式target preflight/import/cold仍须实核，不重放blocked plan01/不重冻来源。源图gap、Shader语义/视觉仍未验，当前8根52pairs。

**DamageTip fresh spec5当前等Shader内置边身份证据。** fixed29真实plan01已不再报程序集限制，blocked/INTAKE_DEPENDENCY_CLOSURE落在Shader f域localID10753/type0；Prefab cold没有该依赖六元组。见[真实证据缺口](../validation/development/beaver-fix29-damagetip-engine-evidence-boundary-20261102.json)。beaver补目标native身份、monkey追原来源后owner再fresh plan；无新合同缺陷证据，fixed29绑定不变，不重跑矩阵/猜名/改包/删引用/重冻。正式8根52pairs/126540保持无写。

**最新fixed29既有程序集schema合同已精确绑定交owner。** source `722ebf28`/producer `24d91ac0…`，仅intake3、QA8保持27。143运行文件source/wheel/install一致、18pin核验；CLI/独立MCP fresh spec5 plan成功，retained/hash/meta/name/漏omission/重复/旧spec及initializer/method schema、旧28 producer拒绝实测；13差分合同/schema/docs/Skill同步通过。复用117producer检查及native各gate/负例/rollback证据，无Editor/正式写入。见[fixed29绑定报告](../validation/development/beaver-fix29-integration-20261102.json)。精确新锁已交僵尸按原授权fresh plan/apply/cold，目标asmdef不改、候选asmdef显式omitted不写、完整67files不重冻，旧spec4失败保留。正式仍8根52pairs待实际消费，carrier禁用/动态数字网格未实现/partial及视觉Player业务边界不变。

**肥鹅新增真实视觉缺口：QA八路无已验证无激活画面路径。** fixed27虚拟capture明确not_supported/空path-SHA；qa.launch直接Popen只证明owned birth，不提供非batch无激活保证，collect仅收既有产物，batch几何/0PNG不能签UI513/UI522视觉。见[无激活视觉边界](../validation/development/beaver-fixed27-nonactivating-visual-boundary-20261102.json)。已交beaver最小合同需求：优先复用App64、目标实例/帧/文件SHA绑定，无焦点/系统鼠标动作，固定证据后再窄绑定；不绕旧native qa.bind/input，不预登记，不重做B01，UI506/508由owner独立对账。

**DamageTip权威交接改revision2，并有真实消费者拒绝。** v2 index `bdec7e70…`完整固定双方asmdef/meta冲突且overwriteAllowed=false；原saved manifest不变、v1仅历史。fixed28公开fresh plan02实际blocked/INTAKE_SPEC_ASSEMBLY，targetAssembly不支持，无actualChanges，等待beaver通用既有程序集合同，不预登记。见[revision2与真实拒绝补充](../validation/development/monkey-dev7-damagetip-revision2-consumer-boundary-20261102.json)。monkey `.private/source-readers/active.json`已明确现存UnityPy1.25.3 Provider为当前依赖、不可当退休fixture清理。正式8根52pairs及effect成功链保持。

**最新DamageTip边界：固定saved静态53字段已核，正式采用等既有assembly合同。** 同dev7已绑定producer不变，67保存文件/索引pin、53fields/1owner4components、first/cold引用稳定及exit1 partial核验。正式与候选同路径GameBase.asmdef名称相同而字节/meta均不同；候选6pair只是相对52已采用子集，不是正式写集。现行newScripts默认Assembly-CSharp-only不覆盖该GameBase carrier，已交beaver判断严格pin既有assembly、不改asmdef及GetClass/base/字段/constructor守卫的通用支持；未预登记能力/写项目/生成或冻结。见[DamageTip assembly边界](../validation/development/monkey-dev7-damagetip-assembly-boundary-20261102.json)。正式仍8根52pairs，carrier禁用/原方法未恢复/动态数字网格未实现，source decode像素不是GPU视觉验收。

**最新fixed28正式effect消费闭环：累计8根52pairs。** fresh spec4 plan `f12221ce…`/journal `ea1615f3…` complete/nativeVerified/exit0/processExited；公开wrapper partial/intakeStatus verified/无transporterror保留。原126524项manifest一致，新增16项已本轮有界核当前字节；6Prefab对象64fields独立cold、Quad六元组preflight/import前后/cold四观察全同、两独立进程exit0。见[正式effect消费者补充](../validation/development/beaver-fix28-zombie-effect-consumer-20261102.json)。仅声明静态数据/目标native身份通过，源mesh等价、Shader语义、视觉/Player/业务仍未验，原gap/deadbeef/partial及旧事务保留，未重试/重冻/启动Unity。下方7根48pairs及pending为前历史。

**最新：fixed28显式engineObjects仅intake3绑定已交正式owner。** source `347f106b`/producer `ddc3b921…`，142运行文件source/wheel/install一致、18pin核验。CLI/独立MCP实际fresh spec4 plan均通过，8字段/闭包拒绝及旧27 exact plan producer拒绝；12合同差分检查/schema/docs/Skill同步通过，无Editor/项目写入。QA8继续fixed27、fixed28不开放无关lane。见[fixed28绑定报告](../validation/development/beaver-fix28-integration-20261102.json)。新锁、完整spec4 schema/六元Quad示例已交僵尸，按原授权fresh plan/apply/cold，不重试plan02或重冻dev7；正式仍7根48pairs等待owner真实消费。目标native六元身份与源mesh gap/Shader语义/视觉/业务分列，原partial exit1保留。下方阻塞为固定28接入前历史，正式采用仍未冒签。

**最新effect消费者阻塞：固定27 fresh plan拒绝内置Mesh闭包。** 真实intake.plan回执blocked/INTAKE_DEPENDENCY_CLOSURE，engine GUID `0000000000000000e000000000000000`，无actualChanges/产物；消费者报告非null Quad localID10210，需beaver显式engine object契约及preflight/cold身份证明后新固定绑定/fresh plan。不得跳过全部engine GUID、改候选删除引用或宣称源mesh gap消失。见[实际消费者边界](../validation/development/monkey-dev7-effect-consumer-engine-boundary-20261102.json)。正式仍7根48pairs，既有Login/fix27两lane闭环不受影响；dev7固定保存态身份已验不变，未签正式effect采用。

**最新：monkey dev7独立effect固定绑定已交正式owner。** source `2e88bc95`/0.8.0.dev7，458运行文件commit/source/wheel/runtime逐字一致、14pin及76保存文件核验。64字段/2owners/4components、零MissingScript/失败、首读/cold引用稳定及两进程exit1证据保留；4新pair/0当前48pair同GUID复用。GREA实际pin及CLI/独立MCP错execution SHA拒绝，无重生成/重冻/Unity启动，14合同检查/schema/docs/Skill同步通过。source mesh gap/deadbeef诊断/partial exit1 needs_action不转成功，Shader仅native引用闭包，BattleMain UV曲线拒绝独立。见[dev7 effect绑定报告](../validation/development/monkey-dev7-effect-integration-20261102.json)；正式owner fresh beaver plan/apply/cold待实际消费，视觉/Player/业务不签。

**最新：fix27两条消费者lane均有真实闭环，僵尸Login静态采用已核。** fresh plan `ee957a59…`/journal `ecd5cfae…` complete/nativeVerified/exit0；公开partial与intakeStatus=verified同时保留，不重试。126473旧文件manifest项一致、增加51项（本次有界核当前51新增+8watcher原件/meta共67文件SHA）；16个.DS_Store仅为已审阅清单覆盖增量。独立cold核350Prefab owners/4757fields、844reference期望、40disabled及2Character42、2新script类型/基类/默认域；128watchers/9声明解析边、双checkpoint和code-check/apply/cold一致。累计7根仅静态声明数据采用；显示、visible edits、Player、业务、原方法仍待验。见[Login消费者补充](../validation/development/beaver-fix27-zombie-login-consumer-20261102.json)。未启动Editor/Player、未写项目或重放旧事务。肥鹅退出后退休已于下方独立闭环，固定报告pending为历史快照。

**最新消费者闭环：肥鹅fix27原通道退休已实测并只读核验。** `vp64-mainline-01`原session/SHA经一次virtual-stop退出后退休，dispatch/launch均false；prepared0600保留原state SHA及nextSequence11/blockedUnknown=false/stopped=false，仅原config/state消失、endpoint不存在、PID missing；原session/archive/lifecycle/typed/owner/profile当前SHA均与退休前一致，exit0非budget、生命周期startup及五清理旗标全真。见[正式消费者退休补充](../validation/development/beaver-fix27-foodstreet-retirement-20261102.json)。该等待已闭，业务revision457/14币71钻109体不因清理回滚；项目后续B01与续档归owner，GREA不重跑业务。僵尸fresh watcher intake仍独立待实际消费。下方固定交付报告保留当时pending快照。

**最新：fix27双有限lane固定交付。** 精确source `8bb6bf34`/producer `88acc905…`，仅五虚拟+三bootstrap+三intake共11路。141 source/wheel/install一致、17索引pin及6下游证据pin核验；实际CLI/独立MCP新prepare、五SHA拒绝、fresh spec3 plan、旧26 exact plan以INTAKE_IMPLEMENTATION拒绝，目标未改、未启动Editor，2自建未绑定通道清理。17差分合同检查及schema/docs/Skill同步通过；110不变检查与producer138安装checks复用，未重跑原生矩阵。单一[fix27绑定报告](../validation/development/beaver-fix27-integration-20261102.json)已交beaver、肥鹅和僵尸。肥鹅用原App64 session/SHA一次post-exit stop，不重建App；僵尸必须fresh watcher plan，旧事务仍原runtime。只在完整clean-exit身份/生命周期证明下清原channel config/state，保留0600预备证据；清理可能完成click/drop，不等于业务撤销。正式两项目消费待owner实际回执，视觉/windowed/自然真人并行仍未验。下方为此前进展。


**最新：virtual4最终固定八路已交肥鹅App64。** virtual3仅生产者内部试验、未交付/登记。最终source `5f38f071`、producer `795c717f…`，141运行文件source/wheel/install一致、22pin核验；CLI/独立stdio MCP真实prepare、五虚拟SHA拒绝、两自建未绑定通道清理完成，10差分合同检查通过，110不变检查复用，未重跑Neutral。见[virtual4绑定报告](../validation/development/beaver-virtual4-integration-20261102.json)。同八操作config/lock/示例已交owner；正常Entry→Mainline additive、实际UI/业务/保存续玩待App64实测，capture仍不支持、真人自然并行/windowed未验。旧virtual2证据保留，新事务改4。

**App63静态段已实际消费并只读核验。** 八路回执、请求与产物SHA匹配；move/release消费，capture不支持使输入外层blocked，未重发或抹除前两条效果；严格五清理旗标、buttonDown=false、正常exit0/collect，revision/coins/diamonds/energy保持454/14/71/110。未点击UI/跨scene/验证业务，0PNG不签视觉。见[静态消费补充](../validation/development/beaver-virtual2-foodstreet-static-consumer-20261102.json)。示例已纠正session文件名并要求使用bind返回data.session；下方App63未启动/等待virtual3均为此前状态。

以下为本轮此前状态，按上方最新交付为准：

**肥鹅正常消费现明确等待virtual3。** owner已源码核实正常登录Additive加载Mainline后卸载Entry，正常主盘输入恢复亦依赖scene/module替换；不能绕Entry先跑主盘。App63未启动、通道未创建，无新事务需清理。virtual2八路薄绑定/110检查仍是有限真实结果，不记为正常肥鹅流程可消费；T0060等同API的virtual3精确pin与scene reload实测，旧无关路由/Neutral不重做。见[实际scene依赖](../validation/development/beaver-virtual2-foodstreet-scene-dependency-20261102.json)。下方“继续静态段”是收到真实消费者依赖前的有界通知，不是当前肥鹅推进指令。

**virtual2固定薄绑定已通过并交肥鹅T0060；scene replacement仍不支持。** 已核`b8fd14fb`的141运行文件commit/wheel/install逐字匹配，16索引pin及正常stop额外receipt；仅五qa.virtual-*和必要qa.prepare/launch/collect bootstrap共八条路由，旧qa.bind/input、intake/SDK不继承。110相关检查通过；CLI/独立stdio真实prepare、五虚拟SHA拒绝、bootstrap SHA/ownership拒绝均实际贯通，2个自建未绑定私密通道已清理，无token入报告。endpoint=false的真实异常stop保partial/CLEANUP_INCOMPLETE与config/blocked state，正常stop严格5旗标+buttonDown=false仅复用原生回执，不重跑Neutral。见[virtual2绑定索引](../validation/development/beaver-virtual2-integration-20261102.json)。同配对config/lock/八操作示例已交App63/T0060，source CLI/MCP用新锁，未刷新全局插件。GREA未运行正式Player或发指针事件；capture not_supported，自然真人并行/windowed focus/正式业务/续档仍待消费者。

producer随后报告已销毁scene module的恢复/SceneLoaded异常边界，将交virtual3及scene reload差异证明；见[scene边界补充](../validation/development/beaver-virtual2-scene-boundary-20261102.json)。已明确通知肥鹅可继续App63支持的静态场景段，若真实流程跨scene卸载/替换须回具体触发并暂停该段，不把现有normal矩阵签为scene replacement通过，不因此重建无关部分。virtual2没有像virtual1被整体撤回；virtual3尚未预登记。下方等待交付/撤回条目保留本次前历史。

**virtual1已撤回，等待virtual2固定修复。** 收到候选索引`d7ac3f81…`后仅只读能力/合同，尚未登记新producer、绑定或执行任何虚拟五操作。producer随后发现stop先置cleanupDone且吞掉设备/后台/endpoint清理异常，可能误报cleanupPerformed=true；已发hold并承诺virtual2补全旗标与异常清理验证。GREA已通知肥鹅T0060暂缓virtual1消费，保留companion/CellView合同准备，不回退native或绕过固定包。原index/只读结果保留为撤回身份，neutral正常路径不外推异常清理。

用户本轮明确批准beaver通用应用内虚拟光标，经GREA接入肥鹅实际验证，系统鼠标/焦点不受工具控制且用户可正常用电脑；旧native保护不得删除。授权已原生核验，总监方案为Manager `decisions/20261102-virtual-pointer/PLAN.md`；仅自有测试App/肥鹅测试Player，不扩大TCC、全局安装、发布或真实支付范围。

GREA负责公开合同/薄入口、精确producer与分层验收；beaver实现后端/companion及中性验证，肥鹅owner单写实际Player接入与canonical台账。已确认消费者Unity6000.6.2f1、Input System lock1.20.1。已与beaver协调有限入口、显式后端、构建/实例/设备/坐标、序号/ack/过期/清理与结果边界。已收到beaver五操作草案（qa.virtual-prepare/bind/input/status/stop，backend unity-inputsystem-virtual-pointer/1），已补入Skill待固定合同；原生后台startup/viewport/release帧仍由beaver验证，当前为**合同草案就绪，awaiting_fixed_producer**，尚未收到固定虚拟包/可调用后端，registry、旧QA门与已安装插件不预先扩能力。

Skill已准备虚拟输入接入门、开发路由及virtual-input/native-input/visual/business/自然桌面并行分层；不支持显式拒绝，无native回退或自动重发。用户其他App活动不终止虚拟测试，主动接管目标App保留停止/清理；自然并行没有样本则待验，不自动操控无关App伪造。固定交付到达后只补实际差异，CLI/独立stdio贯通，再交同一config/lock/companion给正式消费者；复用生产者中性证据，不重复全套或代写项目。fix26及已核恢复链/旧原生保护保持，不为此重导或重验。

## 本轮加严维护（2026-11-02 强力瘦身完成）

按用户加严清理要求，目录由21.42再降至4.73 GiB，本轮减少16.69 GiB。已退休旧QA App、重复工程/回退栈、旧producer整包/本地可选runtime、解包副本及旧发布包；不因历史报告永久保整树。21份包归档同SHA去重，5份GREA证据镜像逐文件与当前monkey权威原件匹配后删除；6个实际intake plan证明当前消费者直接引用monkey候选，固定dev6/fix25/fix26绑定/runtime及当前事务未动。原12份封存回执不变，旧payload状态明确retired-by-cleanup/不能原地重放，包括上一轮所留的旧dist canonical。唯一大项例外为原始私有Git/LFS历史（11个ref对象当前仓库不存在）；唯一APK、最小版本包备份、每个最终试点源及现用一组发布包/一组明确回退保留。旧可选provider wrappers不代表runtime仍已安装，不自动补装。前10大项/≥1GiB子树、逐路径与磁盘观察见[强力瘦身报告](../validation/maintenance/aggressive-slim-20261102/README.md)。未删分支/对象、未造新备份/归档、未启动引擎或全量重验；上方虚拟输入优先级与未验门不变。

## 本轮本地维护（2026-11-02 清理完成）

按本轮用户各项目直接清理授权，目录同口径占用由83.27降至21.42 GiB，减少61.85 GiB。已删87个确认可重建/未占用的旧Unity Library/Temp与uv/Go缓存、3个同SHA重复分发zip；3个干净且已合并worktree经正常git worktree remove移除，分支/.git/HEAD与WIP保持。初始句柄/旧锁暂缓项在第二次实查无占用/活跃进程后清完，无删除失败，不建新归档/备份，不跟symlink跨根，不停止任何进程或重建。1022个受保护源码/WIP与证据SHA核验、12份旧封存回执不变，固定dev6/fix25/fix26及其他当前工具依赖/事务/原件保留。磁盘可用变化含其他项目并发，不能归为本项目独占回收。详见[清理报告](../validation/maintenance/cleanup-20261102/README.md)。本维护不改变上方虚拟输入优先级及各原验收边界。

## 当前新任务（2026-11-02 Unity来源静态Prefab）

**Login真实fix26消费阻塞，恢复已核；LoadingUI正式采用使累计达到六根。** GREA只读核完整Login新plan `472db6e7ec00930191b2cf1dcda88f8420108a007518efe7c6e4cef418dce959`、失败journal `b258089e…`及原runtime回滚journal `071bec72…`。preflight/code-check/rollback-check三个独立PID均exit0，两新脚本身份/基类/字段通过；资源导入前因`Compiled watcher dependencies changed`失败，仅暂存2脚本对。原fix26 restored2/codeRestored/processExited，126457项原记录保持，历史afterFiles126461是暂存快照而非回滚后inventory；23计划资源对当前均不存在，未全树重哈希，不重试或松保护。见[Login消费者失败与恢复](../validation/development/beaver-fix26-login-recovery-20261102.json)。通用compiler watcher共因由beaver维护，待新固定修复，Login未采用、40源禁用行为保留。

**LoadingUI消费者已独立复核通过。** fix25新plan `7b30da73…`及complete/nativeVerified journal `13e50aaa…`、原producer和manifest匹配；15对象/206字段/35对象引用、1项目脚本与2官方UGUI身份首冷一致，PID12350/12992均exit0。126445既有项before/after记录保持，2新增Prefab/meta当前SHA核验，Tip/fix24旧回执未变；public partial/exit1与intakeStatus verified保留。见[LoadingUI消费者验收](../validation/development/beaver-fix25-loading-consumer-20261102.json)。正式不同根累计六个，不增加原headless源分母；新成功事务rollback、视觉/可见编辑/Player/业务仍未验，无GREA原生、正式工程写入、安装推送发布。下方待验与五根口径属于本回执前历史。

**fix26静态声明/Character已有限公开接入，正式消费者待验。** 固定`8c261685`的137运行文件与commit/wheel/install匹配，5合同及98原生证据叶SHA核验；仅三条intake路由增加精确producer `e62c40cf03d5be2eeba64bb11a8b4badef945df8cbe139aaea13f06323403fb3`，contract/3与specVersions=[1,2,3]。CLI/独立stdio完成spec3单脚本声明计划、缺数组/错源码pin/非默认域/未覆盖compiler/v2混入v3字段拒绝；apply/rollback错SHA在原生前拒绝，短预算与非intake执行前拦截，105相关检查通过。fix26单阶段≤280，apply外层≥5×timeout+310、rollback≥2×timeout+160；旧fix23–25预算不变，Schema按版本声明。见[fix26薄接入](../validation/development/beaver-fix26-integration-20261102.json)。固定原生两脚本/8Prefab对象/19字段及Character42/0/65535、独立code-check/cold类型一致、编译失败导入前保护、后改拒绝及42原文件目录回滚仅复用，不重跑Editor。独立config/lock与请求示例已备，正式owner须按完整scope新spec3计划消费；中性样例不签正式Login或任何游戏闭环，partial/exit1与intakeStatus verified保留，不重放旧事务、不安装推送发布。

**主开发接任已完成。** Manager四开发接任记录已释放GREA单写并归档旧owner；交接48份WIP共581378字节的现场/备份及12份固定回执逐件匹配，接任HEAD为`7c9bd3a89dff64a7fa577dbf895b1d403c284565`，无旧自有进程或活跃子Agent待接管。唯一计划及原事务保持，dev6/fix25既有验收不重跑。LoadingUI正式接收已按上方新消费者证据独立审阅；不以同伴进度代替GREA独立审阅，不启动Editor或写正式工程。

**LoadingUI现有公开冻结已只读核验，无新增工具变更。** 同一dev6/3fb450c的现成GREA freeze回执保留executed=true/needs_action/exit1；固定能力指纹、52文件及manifest `1505d3f3b9410aefaf94baee65b8e20163eedcb695d1d06b3c17dbe07a7d8dda`逐件核。原生4节点/11组件、15身份/206字段/35引用首冷一致，PID2691/3222均退出1，0missing/disabled/fail，唯一limit无图形显示；两历史SDK诊断保留。见[LoadingUI只读审阅](../validation/development/monkey-loading-ui-review-20261102.json)。完整DodImage/依赖闭包不裁剪、无enum；正式接收仍需owner新fix25计划及目标脚本、Button/GraphicRaycaster官方包复用核验。正式仍五根，LoadingUI已在旧headless源分母内，不计第十一根；不重冻/重跑Editor/新绑定/改源码或Skill，不签视觉/可见编辑/Player/业务，未推送安装发布。

**fix25真实字体遍历缺口已闭合，TipUI正式采用，累计五根。** GREA只读核新plan `fe3583cc77fd6bde0ec471368c99842062b0a106dac3f22b5b03295d52173c16`、complete/nativeVerified journal `5f59a257839ebfeb4adc97834248a644a0db92d7a82570ffad24902c0ab45694`及原producer；完整68文件源候选未变，16Prefab对象/195字段通过。两项目脚本、两官方UGUI身份、字体3对象/13持久引用首冷一致；Font实际visited50，m_FontData1642040个char按明确scalar条件处理，其余结构仍遍历。PID97104/97615均exit0/exited。126437项before/after记录保字节且与原fix24恢复态衔接；8新增文件（3资源对+2目录meta）及复用脚本/字体原件与meta当前SHA独立核验，原fix24 rollback journal哈希未变。见[TipUI真实消费者验收](../validation/development/beaver-fix25-tip-consumer-20261102.json)。public partial/exit1/intakeStatus verified及两历史SDK诊断保留，不重放；只关闭本次工具缺口，正式新rollback未执行，视觉/可见编辑/Player/业务未验；五根采用不增加原headless源分母，不签十根完整静态。GREA未运行原生/写产品/占屏，下方待验属于本次回执前历史。

**fix25大标量遍历修复已有限公开接入，真实TipUI重试待owner新plan。** 固定`43adf74`的137运行文件、4合同、27原生证据叶及额外oracle/字体/旧恢复pin核验；独立对照无skip oracle3342428属性所得26引用，与优化preflight/cold/rollback对应引用完全相同，含TextAsset共29引用在三阶段一致。早期oracle的OS退出未知保留，不补exit0；引用数组和名为UInt8的复杂数组仍在250001拒绝，上限250000未提高。仅intake三路由增加该精确producer，CLI/stdio spec2计划与拒绝、apply/rollback错SHA、非intake拒绝及101相关检查通过。见[fix25薄接入](../validation/development/beaver-fix25-integration-20261102.json)。同/2 specVersions=[1,2]和3/2阶段预算，无skip开关；独立config/lock/请求示例待项目消费。原生55文件/目录回滚及font后改拒绝仅复用固定证据，不重跑Editor；TipUI未变源候选不重生成，旧fix24 rolled-back事务不重放/迁移，实际消费者尚未记通过，无屏幕/产品写/安装推送发布。

**TipUI真实fix24消费受阻，原事务零导入恢复已闭合。** GREA只读核plan `c98c8ee552e5d23c426feab85184b0acb631c1ad1dcaaa96163bd0c38ae19518`、rollback后journal `5b2a31d3e5b259d72cef892be088a99b1f2efecfbd5e98cb29d64a4ba51ecf0d`：原生preflight因字体标量数据遍历超过250000属性预算失败，尚无native-apply checkpoint；已观察2项目脚本、2包脚本和3字体对象不等于完整接收。PID67777退出，helper目录不存在；记录中126437文件及目录exact-before，原fix24公开rollback完成rolled-back/restored0且无再次Editor。见[消费者失败与恢复](../validation/development/beaver-fix24-tip-recovery-20261102.json)。最初plan漏包声明是owner输入问题且已纠正，真正缺口为generic reference traversal；等待beaver新固定修复在不削弱完整持久引用/后改保护下优化大标量，届时新plan，不用新runtime重放旧事务。TipUI未采用，正式仍四根，原源闭包无需重生成；此处只关闭恢复事务，不关闭接收或视觉/业务。

**dev6两份保存态已有限公开冻结，实际采用待验。** 固定`3fb450c`的452运行文件与commit/source/archive/wheel/runtime逐件一致，23索引叶及两个候选全清单核验；GREA实际pin/freeze精确复现TipUI68文件manifest `a2a1f213f1f7ae90666c9198bd11446173a6f4bb59f7823f3dea8b299cbad673`和原图集修复登录158文件manifest `39202724fb6af44542a4d56d9b1a80d1b97e176300d6d3645d342bf2ab51c64c`，CLI/stdio错SHA拒绝及48相关测试通过。TipUI原生195字段/16身份/28引用、0missing/0disabled/0失败，唯一限制仍无图形显示；Login4757字段/350身份/844引用稳定，40禁用实例和历史22诊断保留。8张登录Sprite原图集像素、原GUID/localID/meta及几何双进程回执匹配，普通unpacked另有2项回归；仅新候选修复缺图，旧dev5/404不改。见[dev6有限接入](../validation/development/monkey-v08-dev6-integration-20261102.json)。仍只freeze，不公开新assets/recover/verify，不产生intakeStatus verified或自动apply；TipUI完整DodImage/DodText/EGameTextType及enum数值须真实复用证明，不删compiler缩closure。Gun trimmed-atlas和BattleMain byte/bool仍拒绝，视觉/可见编辑/Player/业务未验，无GREA原生/屏幕/正式工程写，无安装推送发布。

**fix24精确复用合同已有限接入，登录真实消费仍待验。** 固定`3565efc`的137运行文件、4合同和26原生证据叶SHA核验；只在既有三条intake操作增加精确fix24，cap须为`beaver-additive-intake/2`及specVersions=[1,2]。CLI/stdio已实调spec2规划（1精确existing资源+1合成UGUI包声明，非原生PackageInfo证明），缺v2数组/错误资源meta pin/未声明依赖/v1混入v2字段、apply/rollback错SHA均拒绝；非intake不执行，98相关检查通过。见[fix24薄接入](../validation/development/beaver-fix24-integration-20261102.json)。独立config/lock/请求示例供owner生成新完整计划，旧fix23及旧事务保持原运行时；3/2阶段预算不变。固定上游1新增Prefab、2existing资源/2脚本/1官方UGUI、4对象/19字段/9引用冷开与42原文件回滚证据仅按SHA复用，不冒称登录通过。当前新能力不豁免8张原图缺失/deadbeef、普通缺脚本或完整closure，禁止缩模块/删依赖绕过。GREA无Editor/正式工程写/屏幕占用，不安装推送发布。

**dev5登录保存态已有限公开冻结，完整静态/消费者仍待验。** 固定`a55d88a`的450运行文件与wheel/runtime/source/archive、143候选文件及17索引叶核验通过；实际公开pin/freeze复现manifest `dcef5fe5ca2af00bf05e0cd13b82958d549874ac63ccab62067e7bf350755cf2`，CLI/stdio错误SHA拒绝及47相关测试通过，仍只开放同一freeze。只读复核登录4757字段、350对象身份、844引用冷重开稳定；嵌入Sprite/Texture的13文件及两个原生进程sourceTuple/像素/几何回执匹配，格式/可读性归一化保留。见[dev5有限接入](../validation/development/monkey-v08-dev5-integration-20261102.json)。旧九根只按冻结进度记录及源tuple去重复用，不重新运行或签为dev5全包原生证明；加登录得到10个headless源根，但8张登录Sprite原图集404、效果材质缺图、6类禁用自定义行为及22历史生成诊断均保留，不是十根完整静态闭环。来源/公共仍partial；当前正式已采用四根不变，登录共享代码/字体/资产须用受支持精确复用映射及owner计划，不直接apply或删依赖。GREA无Editor/屏幕/产品写，不扩assets/recover/verify，不推送安装发布。

**三根已完成真实fixed23接收，正式累计采用四根。** GREA只读核消费者plan `15f141ca12fc4d5b1f2f697fa8bcbf67e38cf5d513b29db8ad79b0311efbf4f5`及complete/nativeVerified journal `278d41b42adf31645813d00cbf170182c6e4b418d33d3d23f5fd9eafd1a43c18`，原producer与公共partial/exit1/intakeStatus verified匹配。126407项before与血条after记录完全衔接且本次after未改，30新增文件（9资源对+12目录meta）当前SHA及精确闭包独立核验；18声明对象和287字段、PID7933/8702独立exit0/cold reopen通过。见[三根真实消费者验收](../validation/development/monkey-v08-dev4-consumer-20261102.json)。不重新扫描全源、不重复freeze/原生/apply、不执行正式rollback；原血条及所有固定报告保持。累计四根是实际采用数，本三根属于既有恢复样本，不能增加源根分母或签≥10门；源compiled Shader兼容、画面/可见编辑/Player/业务仍未验，缺图效果组仍独立pending。下方“采用待审”是本次回执之前状态。

**新三根保存态已接固定dev4，采用待项目审阅。** monkey `0.8.0.dev4/2ddb7a9`的446个运行文件与wheel/source/archive及77候选文件核验通过；源身份逐根对照既有原生/冷重开报告，三根共287字段、18对象身份及42引用稳定，两个PID均退出但native-partial/exit1保留。GREA沿原冻结入口实际pin/freeze，独立生成与producer完全相同manifest `7cac2e792c6f6cef64e4b3511fc7a5ae7157f0ac597760d50c6c6913fda324e8`；CLI/stdio错误SHA拒绝及46项相关测试通过。仅新增该精确包/能力指纹，不开放recover/verify/dev3或其他0.8入口；fixed23与已闭环血条不重验。见[三根有限接入](../validation/development/monkey-v08-dev4-integration-20261102.json)。三根属于已有源样本，不新增分母；共享Shader去重不代表渲染/兼容已验，缺原图的其他效果候选独立保留。已准备独立config/lock及同SHA保存态，供owner审阅路径/键和spec后经fixed23接收，GREA不apply、不占屏幕。

**首模块接收工具缺口已完成真实消费者闭环（来源仍partial）。** 项目owner通过固定GREA配置/锁实际plan/apply；GREA只读独立核plan `2a8972fb6548bde136c1af1dd54b667be52a8d3b233300ae3d2e6b960aa44da7`、complete/nativeVerified journal `24fe5b7fd1a00337f91ef97c04c602c27c923d0fdb947f2a97c16bdcc5386217`及原producer。126374项before/after记录精确一致，未重扫全部源文件；33新增文件（12资源对+9目录meta）、3脚本/meta及保护旧Prefab的当前SHA独立复核。原生42声明对象类型/程序集/名称及531字段、两个不同PID正常exit0/cold reopen通过。见[真实消费者验收](../validation/development/beaver-fix23-consumer-20261102.json)。intakeStatus=verified、公共partial/exit1及源native-partial/诊断均保留；不重放apply、不执行正式rollback。仅首个源根模块，不把≥10根生成、画面/可见编辑/Player/业务或源shader/2engine/Outline行为记通过。GREA自身无Editor/产品写/前台占用，原接入及失败报告不改。下方待验口径为本次回执之前历史。

**首次接收合同已补齐固定工具，真实项目消费待验。** beaver fix23/eccea05已交`beaver-additive-intake/1`；GREA核136运行文件与source/wheel/install一致、3合同及19原生证据叶SHA。仅`intake.plan/apply/rollback`进入新scoped版本门，既有adopt/SDK20/QA21/fix22不扩权。公开pin、中性只读plan、apply/rollback错误SHA原生前拒绝及旧inspect拒绝通过；stdio MCP plan与apply拒绝保留底层状态，94项beaver相关检查通过。内层timeout≤500，apply外层≥3×timeout+130、rollback≥2×timeout+130，Schema由同表生成。见[fix23薄接入](../validation/development/beaver-fix23-integration-20261102.json)。独立providers/lock及占位请求示例已备供owner固定项目输入、审阅新plan后自行消费；GREA未运行原生或改正式工程。上游中性2新增/1脚本/5对象/14字段及精确回滚原生结果仅按SHA复用，不外推真实血条模块；来源partial/exit1即使intakeStatus=verified也不能重放。下方“能力缺口尚未实现”属于固定fix23交付前历史。

**最新：固定v0.8.0.dev2/c4b984f保存态冻结已有限公开接入。** wheel-runtime441文件与wheel/source/archive逐件匹配，97候选文件核验；CLI实际pin及`freeze-unity-prefabs`成功生成与producer相同manifest，错误execution SHA执行前拒绝。stdio MCP实际冻结保留partial/exit1；首测客户端返回属性解码失败有记录，修正客户端后拒绝路径通过，未重复原生或正向冻结。45项相关检查、文档/Skill同步闭包/生成契约通过。只开放这一个不启动Editor的保存态冻结操作，恢复生成仅内部请求校验、verify及其他0.8旧命令未开放；不重写provider。见[固定接入验收](../validation/development/monkey-v08-integration-20261102.json)。下列dev1缺口是原交付历史，不覆盖已修的实际wheel绑定/能力/namespace/禁用落实。

**首模块采用的最新缺口：** owner已明确三个非Resources目的路径、保旧key和三脚本字节/GUID；beaver固定20真实只读plan仍在目标全量inventory前以ADOPT_BASELINE_REQUIRED拒绝。GREA已核正式缺口报告SHA `e9772ce492b20d531988c9a11bf0efc8027e4428867040a62e007868c7609a58`。相关startup/源bundle/旧Prefab匹配不证明旧export就是正式工程的共同已采用基线；当前target、incoming或空baseline不能替代。现成SDK/production/batch/payload不提供完整保GUID首次接收及外部.cs映射，不能拼旁路。现行Skill已区分真实prior-export三方采用与待实现的additive intake：审阅target-before/保护集合、全新资产与外部脚本原生兼容、独立重开和仅撤销自己新增内容的guarded rollback。此为已实测的能力缺口，尚未实现/封包，不冒称新fix或生成apply；≥10源根后台恢复继续。

GREA只读复核原生报告：first/cold不同PID均已退出（exit1/native-partial），42对象身份、81引用相同，保存前/保存后/冷重开各531字段通过，2处描边源true→保存与冷重开false。仅同一源根12节点/30组件，不把97证据闭包文件计入样本数，不宣称完整静态显示/可见编辑/Player/业务通过。项目三脚本程序集/GUID保留映射、同Resources键选择/实际消费者与精确独立baseline仍未齐，不能apply。屏幕继续归肥鹅；未启动Editor/Player、不改游戏、不push/安装/发布。

用户已批准以新的Unity原生来源试点推动三工具完善；source历史证据Unity2021.3.30f1 IL2CPP/WASM，目标工程已核Unity6000.6.2f1，实际源包/metadata/bundle版本与hash由当前项目owner重新固定。项目owner已冻结12个不同真实根，覆盖当前UI/战斗/字体图集材质/嵌套/自定义字段；GREA复核清单SHA及12个样本身份，首个采用目标为完整敌人血条模块。按源→静态独立候选→beaver增量采用推进，静态、Editor、Player、业务分项；DummyDLL字段不算方法实现，不做完整WASM恢复前置。

monkey v0.8.0.dev1/501c276首模块生成态已交付；GREA只读核验索引各制品SHA、42候选文件及441个wheel文件与archive/source对应字节。实际launcher源码包443文件，比wheel多2个探针.meta；专属能力声明恢复命令但implemented未列出，已交provider明确固定运行时/能力门，不静默豁免或放开其他0.8操作。已有工程3个同名脚本及源程序集差异交beaver做采用冲突预检；描边、引擎引用和原生/显示/重开仍未验。见[首模块只读预检](../validation/development/monkey-v08-preflight-20261102.json)。至少一个实际模块采用、编辑保存重开和显示后才关闭消费者；不重apply既有6717迁移，不重开肥鹅P0。当前屏幕归肥鹅，僵尸前台Editor/Player及视觉验证暂缓，后台准备继续；GREA不占桌面，其原生AX/PID技术授权不转用于新项目。

beaver随后交付首模块后台只读预检：当前生成manifest缺namespace，既有固定采用快照拒绝UNSUPPORTED_CANDIDATE；两描边组件在生成态仍enabled，禁用仅是nativePlan期望；目标已有三同GUID脚本不可覆盖或重复复制。已把具体差异交monkey在后续新候选/selection补稳定来源身份、实际禁用及显式保留/映射，03和原预检记录保持不变。旧catalog未命中12资源GUID不等于新全库无冲突，不以候选生成通过代替采用或原生验收。

beaver正式三方预检补充SHA `00482d81e76e205c85714443522e4dbaf9b613ddb8efe7eea41cc8b5b388425a` 已由GREA核原字节：候选与旧Prefab还存在相同Resources加载键、不同GUID的冲突，需项目owner选择非Resources显式接线或新唯一key及真实消费者，不能按不同路径直接并存或覆盖。9项源→候选→目标映射的localID均not_observed；5个PNG/TTF仅可准备pins，不代表完整模块已有可apply子集。0个DLL不豁免程序集冲突。已交monkey及项目owner，不新增beaver fix、不生成不完整采用请求，冻结报告保持不变。

已按真实`recover-unity-prefabs --request --expected-request --out`合同准备内部只读请求校验器，核请求SHA、精确字段/目标、源根身份（含64位pathId）、依赖pin形状和禁执行声明；只构造命名参数，不读大依赖、不调用provider、不声称依赖已验。5项定向测试及固定实际请求校验通过。该准备代码尚未接CLI/MCP公开路由，不新增版本白名单；适用新固定包/能力与候选身份补齐后再做实际调度验收。

已接真实工具缺口fix22：132 runtime匹配提交/wheel/install，固定包装进程/合同SHA核，90项受影响检查通过。GREA仅collect+summary、元数据与所有公开入口同一窄门；public pin、错误spec原生前拒绝、非collect与旧inspect拒绝已实调。实际项目collect已复验：Editor exit0/sourceUnchanged/helperCleaned，6717对象名/身份/state与原ledger匹配、issues0；全库111零对象资产仍生成222 blocker并保持partial。GREA只读核回执和报告SHA，未运行Editor或写产品。旧fix8误配providers造成launcher drift已由调用者核配置后ready，不当工具故障；零字节marker导致的argv误识别才是fix22修正。见[fix22接入](../validation/development/beaver-fix22-integration-20261102.json)。本轮仅本地、不push/Release/全局安装。

## 当前有效状态（2026-11-01 P0接续）

本节覆盖下方历史“等待交付/旧未知项”的当前解释；旧原始回执与失败不改写。

2026-11-01用户直接授权提交并推送当前GREA源码快照。本次范围为下列已验薄适配、Skill流程及脱敏记录；不发布版本、不更新正式provider锁或本机插件。SDK fix20与输入fix21的限定项目消费者验收均已通过，v2.0整体另验；提交后的dev9/fix18–21增量为本地未推送状态。

| 事项 | 当前状态与下一步 |
| --- | --- |
| monkey公开有限调度 | dev1保存态audit；dev2/dev3/dev4精确freeze与dev3/dev4有限native-step，dev4增加依赖补证，dev9仅精确SDK声明审计。dev5/dev7仅固定制品/阶段证明审阅，尚非GREA白名单调度，不把“记录交付”写成“接口可调用” |
| 依赖状态 | 最新选择包11原诊断保留，dev4对247库存22脚本/0uncovered的精确producer证明补齐；旧12未知属于历史，非当前未处理总量。不是任意C#分析/原生证明 |
| 已通过段 | dev3独立Player显示/点击、dev7 A10采用按消费者原证据复用；fix12真实保源构建、fix15/16受控文稿拒绝下的正常路径/续档闭合。不因P0重跑全体 |
| beaver公开固定入口 | 最新本地SDK入口fix20，QA新fix21匹配InputSystem/uGUI，旧fix19链保留；正向规划、默认冲突和无归属拒绝已实调。旧fix12、15/16和历史事务保持原producer。正式模块/用户插件不因源码接入自动升级 |
| P0-A SDK迁移 | fix20实际隔离消费者通过：4054真实引用、32 canonical脚本/2 inactive DLL、apply/独立冷重开/rollback及源文件检查已核；正式工程未改，不代表Player/输入或v2.0整体完成 |
| P0-B App实例绑定 | fix21实际原App40默认输入、真实登录、权威棋盘换位、2次正常退出和15字段同profile续玩已核；qa pump=false，无重建/重新播种。旧18/19失败、过期quit blocked和Command-Q partial保留，不外推全产品 |

新用户P0授权已原生核验；唯一出口仍为通用实现→固定交付→GREA公开接入→肥鹅真实验证。当前SDK与实例输入限定消费闭合，项目继续自身业务；不新增版本号占位/空实现，不停止无依赖业务。下文历史状态按各自日期保留，不覆盖本节。

## 2026-10-31 真实项目驱动的工具链接续（本地进行中，未闭环）

本轮工具链完善与可重复的公开流程优先于单独完成功能。以消费者P04为真实样本，GREA维护阶段、固定版本/producer/能力绑定和薄调用合同；monkey维护来源恢复/输出依赖与显示代理，beaver维护采用闭包/导入时序/事务，项目负责业务与消费者复验。各自单写，不复制解析器/采用器，不强制每次全量重跑。已推送main `240eead`保留，本轮没有新增推送、发布或全局安装。

已只读核现有消费者请求及实际调用回执：公开`beaver_pipeline invoke`转`adopt apply`，使用正式beaver0.5.0 producer `bee1d06780155a50735d9e836041cd967a3da0bc2dbe368d1d55cb2cd8700e90`，16脚本/72资源分别保存重开与引用核验通过。此前资源GUID闭包遗漏两份普通C#编译依赖，同批新脚本加载又使首次读取与重开引用不同；临时分阶段已保全成果，未记为通用采用器已修。静态代理实时文字/图片/进度/显隐、字体覆盖和点击表面仍由工具owner修复并回项目复验；项目适配成功不能替工具签全链通过。

GREA在原参考中统一生成态→原生保存态→项目适配态身份，保留原manifest/失败和实际变化，不按.meta或固定数量豁免差异；分清资源依赖与编译依赖、静态与动态结果、直接provider CLI与GREA typed路由。脚本退役须有固定工具公开调用及消费者问题解除证据，业务继续自包含。已与当前monkey、beaver及消费者交接精确合同需求，尚无本轮新增采用修复候选可验。

固定beaver `0.5.1.dev20261031+fix9`的有限接入已验：17份交接文件、122个运行文件与提交/wheel/安装字节一致；公开GREA源码CLI完成pin/正向batch规划/错误owner拒绝，源码stdio MCP保留同一blocked诊断；大正/负64位ID校验及7类非法selector拒绝通过。复用并核hash的上游原生回执为7 observed＋7预期unknown、独立重开及负Material ID；GREA本轮未启动Editor或应用事务。fix9只增强`native.readback`精确owner，不修复脚本adopt、代理动态或输入。见[fix9有限验收](../validation/development/beaver-p0-fix9-integration-20261031.json)及[真实链路审阅](../validation/development/toolchain-consumer-handoff-20261031.json)。旧候选/事务/正式模块锁/用户插件保持；消费者现有0.5.0回执不归功于fix9。

## monkey v0.7 Prefab阶段口径（静态优先，动态另验）

现行门槛覆盖此前静态/脚本/动态合并签收口径：第一阶段至少10个不同核心Prefab完成Creator3.8.8与Unity6000.6.2f1双目标静态验收；来源身份、层级、组件字段、资源引用、实际静态渲染、保存独立重开、再生七项可独立签`staticAcceptance=pass`。业务脚本允许disabled/not_run/partial，第二阶段另核动态/生命周期/事件/输入，不以其未运行抹去静态pass，也不据静态pass称完整恢复或游戏完成。样本/版本范围由monkey批准计划维护，不成为每个游戏固定10项门槛；闭包节点/重复状态不凑核心样本数。

现已有上游dev1 `a458790a68d57108b4cfe038d8aa565d5cc1599b`及消费者P04证据；GREA本轮只读核当前采用链，未重新验全部样本或Creator。保存态可以合法不同于生成态，但需固定合同、前后身份和当前字节回执，不改原清单。已核dev1真实capabilities/CLI及保存态合同；capabilities没有producer字段，实际通过423文件包摘要＋capabilities摘要、launcher/包树v2锁绑定。不把版本白名单当完整适配。

规范已按阶段修订；[旧版本口径回执](../validation/development/monkey-prefab-version-contract-20261029.json)保留历史，不回写旧验收。当前[交接审阅记录](../validation/development/toolchain-consumer-handoff-20261031.json)明确方法/薄适配与消费者未闭环的边界。批准双目标仅为隔离工具验证，不恢复暂停的Cocos产品，不改游戏工程。

## 2026-10-28 UI生产与验收方法（方法已落实，项目实证待补）

已核原生用户批准的项目/工具分工。本轮仅维护GREA：在原有生成契约、界面还原、组件/Prefab、画面对照和测试参考中补齐唯一生成源与旧入口退役、单属性/分阶段布局写者、项目样式组件、同页同状态同视口、功能/视觉/Player分层及重复生成不回退。工具只引用固定beaver已证实入口，未知专项检查不标实现，不复制游戏风格或另建规范。

验证：157份文档705条引用、隔离5技能70篇参考355条内部链接及4项路由检查通过，生成契约无漂移；记录见[UI方法验收](../validation/development/ui-quality-method-20261028.json)。

方法定义与试点代表页实际通过分开；等待项目在真实宿主/候选完成代表页证据后补经验，不据多入口风险推断每次返工根因，也不称UI整改或retirement工具执行完成。僵尸P0各固定合同、在途成果及本地未发布状态保持。此轮不改游戏、不推送/发布/全局安装。

## 2026-10-28 严格目录与阶段交接（本地规范与薄适配完成）

- 已核对用户批准的结构审计、构建资源筛选、原生回读与捕帧范围；只维护 GREA，游戏与 provider 各自单写。
- 规范已统一 Images 为纹理文件目录、Sprites 为独立 Sprite 主资产；明确 Scenes、Config/Levels 与复合资源组判定。恢复程序集/类型身份保留与新业务五层分开；旧业务根不得整体豁免。
- 已明确现行项目配置与 beaver 结构例外独立输入的字段差异；不破坏配置 Schema，不声称自动适配已实现。
- 已收固定 beaver `0.5.1.dev20261028`（提交914adff、producer f9bc89c），完成五项有限路由与同源 Schema；39项定向测试通过。安装包/10份合同hash已核对，六次真实CLI调用覆盖五路由及一次保留的错误target参数回执，合成分类与blocked未升级。未运行Editor/Player，正式项目消费者采用仍待项目验收。记录见[本地适配验收](../validation/development/beaver-p0-integration-20261028.json)。monkey来源分类已按下项接入；已发布 modules.lock 不变。游戏的结构迁移、750×1334候选首关仍由项目验收，不由本页宣布通过。
- beaver修订候选 `0.5.1.dev20261028+fix1` 固定producer d683fbc已纳入，初版门保留；增量10项检查、安装包121文件/10合同及6个原生组件hash通过，合成旧场景→Game/Scenes正向声明及制品SHA核验通过，未执行迁移或重跑原生。见[fix1验收](../validation/development/beaver-p0-fix1-integration-20261028.json)。
- monkey提交57613e7固定wheel（5ea38374）已接入`monkey_pipeline classify-shaders`有界入口，不走全工程snapshot；230运行文件逐字节核验，原始/规范编码能力指纹分别验证，3项新增门禁＋既有恢复相关共17项测试通过。实际CLI合成四类分类、未改文件、not_run语义通过；未经修改handoff实际交给固定beaver fix1，binary/source-evidence-only匹配且隔离blocked。无原生重跑、全量重导或全池审计。见[monkey接入验收](../validation/development/monkey-shader-integration-20261028.json)。游戏结构/Player闭环及真正隔离执行不在GREA此次通过范围。
- beaver最终本地fix2（34ce66e，producer8fa8f67）已加入精确门，旧固定链保留；121运行文件/10合同/6原生组件核验通过。5项增量测试及四次实际CLI验证新inspect→正向声明、旧audit缺闭包blocked、审计后新增文件blocked；报告制品SHA通过，未执行迁移或重跑Editor。见[fix2验收](../validation/development/beaver-p0-fix2-integration-20261028.json)。
- beaver核心fix3（c62245e，producer978da3）已接固定门及成对product-root/profile路径；GREA调用前完整Schema校验、调用后profile哈希核对。121运行文件/10合同、7项针对检查通过，真实CLI合成显式/自动绑定ok、非法完整profile未启动主操作。上游ArraySize=1原生回执只读Schema/哈希通过；63.7MB/65661项原报告经固定installed专用reader只读通过，普通read仍拒绝。GREA外层4MiB预算不变，大响应CLI/MCP端到端未验，较大报告显式使用固定provider CLI；紧凑传输与retirement执行均不声称完成。见[fix3验收](../validation/development/beaver-p0-fix3-integration-20261028.json)。
- 2026-10-29接入最终fix6（c1d80d9，producer8e5d595）：核wheel/121运行文件/15合同；新增summary、consumer-resolutions、unity.recover与退役能力门，完整profile校验沿用。16项定向检查、实际合成CLI审计/来源比较声明/退役规划及源码stdio MCP摘要通过，5.25MB完整报告不内联且SHA独立核验；partial/exit1通过有界转发测试保真。原生退役final producer回执只读核对，Scene preseal证据按两个相同组件SHA复用；未运行Editor、apply/recover或游戏。本地支持与项目采用分开；旧全局绑定/正式锁保持。见[fix6验收](../validation/development/beaver-p0-fix6-integration-20261029.json)。
- 2026-10-29增补fix7（5b765eb，producerb889a59）精确门，fix6链保留；122运行文件/16合同核验通过。18项受影响检查及实际CLI空叶目录folder-only规划、非空拒绝、unity/batch非法目标路径预检通过；调用固定API生成审阅绑定，摘要目录计数/恢复文件数原值保留。原生空目录与普通/source-only兼容回执只读核到final producer，GREA未启动Editor/删除/恢复，不称Scene重跑或大批次优化。见[fix7验收](../validation/development/beaver-p0-fix7-integration-20261029.json)。
- 2026-10-29增补fix8（1b44c0b，producer6e81b67）精确门；122文件逐字匹配提交/wheel/安装副本、17合同核验通过。20项受影响检查及实际CLI默认/增量相同writeSet规划、Scene/额外readPaths拒绝通过；两个新开关仅转发spec，不扩CLI。上游final原生258资产/603配对、合法空name、默认旧字段及partial/exit1只读核验，采集摘要objectIdentityCount保留；GREA未跑Editor或move/recover，不外推大工程耗时。旧链/全局绑定/正式锁保留。见[fix8验收](../validation/development/beaver-p0-fix8-integration-20261029.json)。
- 本节之后的新标准改动尚未推送或发布；此前路径性能修复与协作规范已由用户直接批准提交 main `fb4db3e`，与本轮 P0 接入分开。

## 当前主线：三产品职责整改（2026-10-26）

本节覆盖下方历史 LC 规划中“GREA 自行维护通用执行实现”的归属；历史已验/未验不重写。品牌 GREA，兼容 GREA ID。monkey 负责恢复候选，beaver 负责开发工程操作，GREA 以 Skill/方法与薄调用为主。详细架构见[三产品架构](monkey-grea-lifecycle-architecture.md)，交接见[执行工具交接](beaver-execution-handoff.md)。

当前源码 2026.10.26.dev4 为本地候选，已装 dev2 保持；未提交/推送/发布/全局升级。原游戏工程不改。

### 五技能流程整合（2026-10-27）

后续全量文档审计已完成：逐篇审阅76篇，整合为70篇；候选能力/产物/验收分开，修复JSON/SO、工具归属、Creator运行时与Go权威状态等冲突。52项定向测试及新版macOS arm64隔离插件验证通过，未改游戏、未替换用户安装、未提交推送或发布。处理清单、逐篇去向和限制见[全量文档审计](../validation/development/skill-document-audit-20261027.md)。下方五技能首次整合的包SHA保留原历史身份，不指向本次审计包。

本轮用户已批准按“调研→恢复→开发→发布”整合，正式入口为grea、grea-research、grea-recover、grea-develop、grea-release。换皮和Go服务端归开发；原版观察归调研、技术提取归恢复、工程接收与普通Editor工作归开发。旧入口职责通过技能迁移表和文档路径表解释，安装只保留五入口。既有reference与输入资产保留唯一维护来源，共用monkey恢复步骤归恢复阶段参考，未重写游戏或provider实现。

旧工具ID、模式参数、输入Schema与既有结果字段保留；plan-workflow增加primary_skill/stage/entrypoint，并明确恢复候选之后的开发交接。交付模式在Cocos/Go目标下仍进入发布，取证模式不会因目标引擎/后端选择进入实现。同步与构建核对声明的五技能集；旧托管安装升级清理过时入口并保留无关技能。隔离安装、CLI/MCP和构建产物验收见[五技能整合验收](../validation/development/five-skills-20261027.json)。此轮只做本地未发布候选，不更新用户插件、不推送或发布。

本轮整合已完成：52项针对性测试通过，88个工具条目的执行/输入/输出/别名等兼容字段保持；五技能文档集合可独立安装，162份仓库文档的703条本地链接通过检查。macOS arm64完整候选在搬移后的中文空格路径、独立HOME和最小PATH下，按Codex/Claude清单启动的stdio客户端均通过；源码读取、联网和安装写入被测试沙箱实际拒绝。最终包SHA为`5ccc34697d227fb41b17403de7f8e4a7333ba2b50c88ba76174677f4455c9a48`。这不是原生客户端插件热加载、Windows或游戏运行验收；本机已装插件未更换。

### Skill 文档自包含整理（2026-10-27）

按本轮用户直接要求，将23份被技能引用的provider/工具/接口说明归入对应Skill references，文档入口保留项目介绍、安装、使用与维护职责。执行流程、调用合同、限制及示例不再依赖仓库docs；换皮两份JSON示例归入Skill assets，四份输入Schema由既有契约同源生成，不维护第二套定义。共享与阶段专属参考按需加载，工具ID和运行接口不变；可执行CLI/MCP、provider、引擎依旧是运行依赖，不将文档独立性说成工具零依赖。

增加源码/隔离集合引用闭包检查并接入文档CI；同步拒绝指向技能集合外的本地链接，覆盖图片与引用式链接。隔离导出、删除模拟源码后的可读性、输入示例与Schema、现有插件资源投影以及独立场景走查按受影响范围验证；结果见[本轮验收](../validation/development/skill-self-contained-20261027.json)。未安装用户副本、未改游戏或provider实现，未提交、推送或发布。

### 当前维护范围：[项目 A]v1.3实际采用支持（2026-10-27）

**最新进度：固定beaver0.5.0有限薄适配已完成，正式[项目 A]采用仍待自然任务。** 接收main `9d15c50deeaf07817944ad7032598bf70b6a2b99` 的固定wheel（SHA `595a4c992d42b664f0e30b74aa7563dc3ffc34de1927f9ae5c6653e3f12ac438`），独立安装后producer与交接一致，116运行文件与固定提交逐字节匹配。增加ui.inspect/analyze/repair-plan、wiring.plan、diagnostics.summarize五项命名转发及有界多路径参数，不复制执行器；旧ID/委托/默认模块锁不变。12项定向检查、五次真实CLI调用、两次stdio MCP调用和一个旧toolkit复制入口通过；ui.inspect只核真实parser参数，不运行Editor。接线/修正采用自有静态夹具，只证明规划；未重跑引擎/旧全套、未全局安装或推送发布。见[限定验收记录](../validation/development/beaver05-integration-20261027.json)。下列awaiting_fixed_contract及版本裁定保留为接入前的历史过程，不再代表当前接入状态。

**当前接入目标为beaver 0.5.0，覆盖下文此前0.4.1编号裁定。** 已原生核验最新用户turn `[私有会话标识已脱敏]` 内的版本整合指令 `[私有会话标识已脱敏]` 及本地main合并指令 `[私有会话标识已脱敏]`；方案为 Manager `decisions/20261027-beaver-v05/PLAN.md`。beaver主开发负责把既有toolkit及当前UI/接线/诊断成果合入其本地main并形成固定0.5.0包，GREA不代写或操作其Git。此前已交付的toolkit固定来源及消费合同继续有效，无需重复交接或验收。GREA仅在新实际producer/schema/能力与包就绪后做有限薄适配；较大版本号不代表全部旧/新路由可用。旧0.4.0模块、旧producer和事务保持；接入前状态为awaiting_fixed_contract，当时未预注册；本次接入仍不全局更新、不新增推送或发布。

本轮新增支持：beaver UI批量检查、自动接线与统一诊断的有限接入。已原生读取技术总监聊天中的实际用户指令（turn `[私有会话标识已脱敏]` / human `[私有会话标识已脱敏]`）；权威方案位于 Manager 的 `decisions/20261027-beaver-v04/PLAN.md`。截至此次核对，上游仅启动研发，尚未交付本轮可调用固定合同/候选，GREA状态为 **awaiting_fixed_contract**，不提前登记新操作或编写空实现。

接入只在收到明确版本、producer/包身份、公开能力/请求结果合同及最小原始回执后开始，复用原消费者检查并补实际差异；保留0.3及旧事务、`actualChanges`原值和执行后外层失败语义，不重放事务、不重跑引擎/全旧路由。Go和增量仅按真实任务需要处理。正式游戏由当前“[项目 A]｜开发者 (2)”单写，旧主聊天不唤醒；缺新工具不阻塞独立游戏工作。本轮无新增推送、发布或用户插件替换授权。

已发现并交接版本身份冲突：当前GREA模块锁已经固定一份 `beaver 0.4.0`（旧0.3合同＋toolkit，producer `06a710a70b8e9257e68e6e3b83a34db41e7e1f4e32b2810fe80367db518717f7`，wheel SHA `9d509f509c574a91e18e17053f11f4ce3fa37a27a857600c2791287876eb4ed8`）。它不包含本轮新UI能力，不能仅凭同版本号接收或覆盖。已向beaver主开发提示保护旧制品并在交接时区分身份；新正式命名由其与版本负责人核定。当前registry、模块锁、运行时与Skill能力声明均未改变。不循环等待或制造无依赖实现任务。

后续身份裁定已接收并核对权威方案第8节：能力计划仍为v0.4，新候选使用0.4.1.devN、本地正式包0.4.1，旧0.4.0保持。已向beaver交付最小来源与消费合同：固定提交 `6791ddf98e31e411f7efe17d474f66251a1e9f76`（父提交 `1f624503f7728b8670d63e09c12ac12acab0807d`）、wheel位置/哈希、23个委托ID、四个typed API映射和八个已有隔离实调工具。特别标明 `beaver tool` 保留原JSON/退出码，不包进beaver-result/1；源码差异只涉及toolkit及必要入口/依赖。私有回执 `[私有本地路径已脱敏]`；本轮只回验固定字节与消费路径，未新增测试/引擎/安装。拟议ui/wiring/diagnostics命令仍未注册，接入继续等待真实固定合同。

按2026-10-27已原生核验的用户授权及[项目 A]v1.3主体收口计划，沿v1.2支持契约继续由真实开发驱动维护。复用已验证的本地GREA dev4入口、beaver0.3有限路由、私有绑定、旧固定链及下述结果Schema修复；未更新的全局插件不视为具有本地源码能力。本次支持范围更新未收到具体新工具缺陷，不新增实现或重跑旧验收。无实际缺口时仅保持既有范围；真实反馈按下文同版修正，不另起版本、任务或广泛拆解，不循环巡检/等候，不重复基线49路由、45检查、消费者回读或引擎验证。

[项目 A]主开发单写游戏业务；GREA单写实际采用暴露的Skill、方法、调用合同和薄适配缺口；通用工程执行实现仍由beaver单写，不复制执行器。小范围纯代码修复不强制完整workspace/production/Editor流程；复用有效绑定和证据，工具问题不阻断无依赖业务，也不为展示工具制造采用任务或增加前置验收。

v1.3的一次有界盘点、主体开发、界面完善、本机证书轮换和启动/连接修复由[项目 A]主开发负责，GREA不接管正式工程、服务配置或存档。专用仓自然正向实玩按用户决定保留待验，不冒称通过，也不设为其余主体工作的等待门槛；monkey恢复另行推进，不要求既有工程重导。产品唯一计划和版本交付仍由[项目 A]维护，本节仅记录工具支持边界，不另建产品差额表或拆小版本。

已处理的真实反馈：storage-feedback的production.apply原生complete/verified、写集外0，但GREA错误地只接受actualChanges对象列表，在四条已变路径字符串返回后拒收。现修为非空string/object联合合同并生成Schema，执行后拒收明确标unverified/可能已写入、查事务且不自动重放。8项受影响定向检查与原stdout/exit0/journal离线重验通过；原失败记录保留，不改游戏、不重放、不重跑基线49路由/45检查或引擎，已向[项目 A]/beaver交接。[修复回执](../validation/development/beaver-result-schema-fix-20261026.json)记录当前源码身份；既有45检查和原生采用记录仍按其原检查点保存，不把只读/规划覆盖当作全部effectful返回已验。

出现真实缺口后成组处理：必要最小复现包含固定身份、命令/目标、预期与实际、输入/错误定位、影响及可用替代，不发全量日志或原件。本轮允许与[项目 A]主开发、beaver及技术总监做必要接口交接；普通ACK不是继续开发的前提，不逐小包例行汇报。严重阻塞、数据/架构风险或范围权限裁定交技术总监，独立工作继续。成熟修正再沉淀原Skill条目，不建立竞争流程。

原有未替代Go工具和消费者继续保留；本授权不新增全局安装、推送/Release、服务升级/迁移或真实资产改动。游戏版本和自然实玩前置条件由[项目 A]及总监处理，GREA不注入资格/资产、不缩减产品出口，也不把工具验收当完整游戏验收。

| 工作 | 当前状态 | 剩余与验收 |
| --- | --- | --- |
| G1 Skill 与 reference 重组 | 已实现并验证 | 42 份参考去数字/类别前缀，共用参考移入路由 references；原G1检查点12 Skill基础校验/139文档通过；当前文档指标见收口回执。后续仅仓库私有生成预览，不升级工作区或全局安装 |
| 来源冻结与 beaver 交接 | 已冻结 | 903 个整改前 WIP 文件；40 个 Python 工具入口及367个模板/companion 文件索引；beaver已返回参考/子集接手意见，完整接口替代与消费方切换未验，旧实现保留 |
| 恢复侧7项评审 | 结论已核入矩阵 | monkey核心/子集可复用不等于legacy合同等价；XAPK/ELF/Laya/Shader缺口保留；7项均禁止退休，不交beaver，不新增profile或parser执行 |
| G2 双 provider 与薄绑定 | 已实现并验证 | required monkey/beaver、显式双检查、包身份锁；dev4增加15个命名操作及生成Schema，能力/状态/预算约束与实现仍由两工具执行；9项新增边界＋2项路由检查通过 |
| 同事研发交接方法 | 已纳入本地Skill并验证 | 读取6份Docs、README、关键Evidence与四类Manifest；来源/适配/源码/Player、签名/方法体、表变体与协议分层；monkey0.5专用查询已交付但仅显式开发入口；beaver0.1物化/校验已有命名转发，不冒充稳定monkey0.4能力；140文档/697链接及57份技能Markdown/356链接通过，仅仓库私有生成预览，未安装。见[方法接收回执](../validation/development/colleague-handoff-methodology-20261026.json) |
| G3 真实新链 | 本地集成收口（分层证据） | monkey0.4候选→beaver采用预览已验；最终beaver wheel的GREA dev3项目检查、匹配源码构建/Player前后核验直接复用；dev4薄转发真实CLI及独立stdio MCP通过。早期Prefab读回属于另一wheel，不混称同版全链；[项目 A]正式采用/物理输入未验 |
| beaver0.2消费者兼容 | 已实现并验证 | 固定fae3845最终wheel；显式batch/transaction合同与25命名路由/生成Schema，旧0.1绑定保持。32项适配检查、全部25操作与wheel实际parser一致、真实CLI及独立stdio保留partial/blocked；49份证据身份已核，复用上游50检查与原生/Player，无引擎重测。见[0.2回执](../validation/development/beaver02-integration-20261026.json) |
| beaver0.3 Unity＋Go固定候选接续 | 有限适配及正式08原生采用回执已核，整版由beaver汇总 | 精确wheel/producer、49路由及45适配检查通过；07、08、09的原生/静态/等价包证据分别保留。现已核正式08 rebind→新计划→native complete/verified、写集外0：对既有两份C#相同after-image编译/保存/同Editor重载，非新代码变化或独立重开；原4项项目Play通过，未重跑。68运行文件匹配本地ad876da。App默认Metal问题与direct-render正常进出、购买L3 not_run分别保留；旧Go链不退休。见[0.3回执](../validation/development/beaver03-integration-20261026.json) |
| Go执行资产移交与旧链过渡 | 固定交接已被上游提取，旧消费者未退休 | 通用Go来源45文件104020字节保持冻结；beaver07已交出工具/自有服务证据，本轮GREA仅实际消费Go模块候选和协议比较。旧server_go_project、模板和消费者不删、不假转发，完整合同替代和正式项目接入仍待各自证明。见[Go交接回执](../validation/development/go-beaver-handoff-20261026.json) |
| 兼容切换与旧实现退休 | 未执行 | beaver接收/隔离验证＋消费者切换后才薄转发；[项目 A]在途旧固定链保持 |

本轮验证：全量测试在保持本机 AGENTS 预存迁移头的独立源码快照中运行，369 项/355通过/14按环境跳过；后续 provider 变更以14项针对性测试和真实隔离CLI核验。快照仅去除本机路径迁移头以通过公开树检查，产品源文件保留。详见[本地验证回执](../validation/development/triad-skill-first-20261026.json)。

dev3 完整 macOS arm64 私有候选已构建并校验，Codex/Claude 两种启动清单的随包 MCP 在禁止源码读取、网络、安装目录写入的隔离环境通过；不是客户端安装验收。此为历史dev3完整包的隔离验证。本轮dev4复用其基础与beaver已验构建/Player，新增适配仅做窄验证；未重新构建/验收全部平台插件或更新全局安装。当前源码 HEAD 与暂存区未改变，未推送/发布/全局升级。

当前集成身份和可复用证据见[三工具收口回执](../validation/development/triad-closeout-20261026.json)。monkey0.5开发查询不阻塞稳定0.4＋beaver0.1基线；原生资源/引用缺口仍由monkey维护，不转成GREA新引擎任务。

以上G1–G3与0.2记录为既有检查点，不以后续适配重写其原生层结果。当前候选07接入身份见新回执；全局安装、完整dev3历史插件包与本地dev4源码仍是独立交付层，本轮未构建或安装完整dev4插件。GREA不放行未知0.3 producer，也不等待修复包而重跑已有上游验收。

后续只读收口：已核ad876da的68运行文件与08/09/final一致；final仅METADATA/RECORD修订，身份见接入回执，不重跑45检查或调用。正式08原生采用的边界为同Editor收敛；上游其他Play通过/中文副本SearchDatabase失败和项目App出口分别保留，整版不由GREA代判。

## 历史目标与基线

GREA覆盖游戏调研、取证恢复、美术换皮、功能开发、持续迭代、发行与运营反馈。GREA负责路线/合同/证据/工具编排；monkey负责包与资源/代码初稿到原生工程；引擎、美术、后端和渠道保持独立provider。不是全量安装74个技能，也不建设第二套游戏服务器或项目经理后台。

用户批准来源已通过原会话核验并在私有开发回执保留，原话“按方案推进，落地详细的版本计划和开发文档，推进GREA开发”。总监已原生核验。

源码基线48debf7（codex/research-cocos-go）。已有AGENTS本机修改保留，不清理、不混作本轮新成果；历史v2026.10.19及已安装副本与本轮源码分别记录。既有Creator实际导入/浏览器、真实客户端网络待验不因本路线通过自动关闭。

配套：[系统架构与合同](design/lifecycle-architecture.md)、[开发任务与验证边界](design/lifecycle-implementation.md)。这些文档是批准设计，非已实现接口；代码/工具能力只有实现并验证后才登记可用。

## 三个开发版本

LC1/LC2/LC3是本轮内部版本标识，分别包含实质开发成果。正式插件继续仓库日期版本制，在实际准备发行时确定，不预造上线日期/标签或覆盖旧发布；本轮未获远端发布、推送或全局安装授权。

| 版本 | 用户可用成果 | 主要开发 | 有限出口 |
|---|---|---|---|
| LC1 工程接续版 | 从调研/恢复任务路由到目标工程、资源总览和AI接手包 | 生命周期/模式路由兼容、monkey provider、结果归一/续接、资产来源模板/联系表/规格检查、修JSON规则冲突 | 一条已授权输入走到工程或明确needs_action；来源/产物/缺口可回查，旧Unity调用兼容，至少一个真实可取得输入与必要合成反例 |
| LC2 开发迭代版 | 在恢复工程上按批准设计换皮、加功能、调优并交付成组版本 | feature/tuning/prototype合同、存档/配置兼容分析、类型与UI/音画参考按模式组合、版本影响/交付包 | 一个有界功能或换皮增量从合同到可查看结果，旧不变量/存档边界准确；不以类型must-have强加需求 |
| LC3 运营反馈版 | 用授权数据分析体验/经济问题，生成可审查的配置与发行候选 | 事件/指标合同、只读漏斗/经济分析、配置/活动发布与回滚预览、一个已选平台的发布预检 | 在合成及可得授权数据上指标可复算、候选可审查；无真实运营数据或平台未选明确标缺口，不接生产写入 |

正式生产活动发布、玩家补偿、退款/支付、通知、商业渠道上线、自动实验分流不是本轮默认动作。可设计接口和隔离样例，执行必须有对应真实项目授权；不能将只读分析变成自动运营。

## LC1 详细任务

### L1.1 生命周期/模式合同与旧调用兼容

- 在现有workflows/case/change合同增量加入stage与mode，分别记录source_engine、target_engine/backend、精确版本、平台、批准范围及本次交付层级。
- 支持研究、忠实恢复、换皮、功能扩展、调优/原型、交付、运营模式的明确选择；阶段不是所有任务必跑流水线。未知目标返回需要信息/不支持，不默认Godot。
- 旧省略目标的Unity路径保持兼容；旧ui_ux合同继续有效，不让scope扩展改变已有恢复语义。合同v2与v1解析分开，真实权限仍来自用户，不由JSON里的approved字段授予。
- 清理旧JSON→SO制作真源表述，统一正式数值JSON运行时读取；资源引用SO合法，不能简单禁止全部SO。不要顺带迁移游戏项目。

### L1.2 monkey provider与AI接续

- 先只读检查monkey当前CLI/版本/输出schema，使用显式配置的本地可执行文件/制品版本；不依赖维护者绝对路径，不复制monkey解析器。
- provider负责能力发现、输入/输出边界、命令参数、有限超时/结果解析与产物引用。调用真实convert及其受支持续接；monkey尚不支持的能力明确记录，不由GREA补假输出。
- 输入是来源集合与具体授权范围；输出包括原生工程路径或candidate、资源覆盖、代码初稿/缺口、source→target映射、工具/引擎证据、下一动作。
- 串起研究结论→恢复输入→工程/AI模块包；一个业务包含规则依据/资源引用/可写边界/依赖/受影响验证，不能每条诊断生成一轮Agent对话。
- 不让GREA自动创建新Agent或执行包内脚本。底层needs_action/partial/blocked/failed保持，native完成必须有真实引擎回读；能力存在不等于Editor可用。

### L1.3 资产可视化和规格补齐

- 资源来源/许可/创作者/限制/生成工具等字段并入现有art-ledger，保持现有设计/来源/切片/Spine/目标/证据身份，不另建资源台账。
- 新增受控静态图联系表，或扩展既有同类底层公共代码；支持唯一标签、中文、明确原尺寸/统一比例模式、输出隔离与总像素/文件数量限制。
- 在image_alpha_audit增量加入显式期望尺寸/可选色数约束。修正上游“limit+1仍通过”问题，保留GREA已有hash、透明/空图、边缘、symlink和预算限制。
- 色数仅在像素/调色板任务启用，不能把HD渐变UI默认判不合格。总览不替代游戏内尺寸/pivot/动画状态验证。

## LC2 详细任务

### L2.1 feature/tuning/prototype合同

- 从当前ui_ux扩展为有界功能/规则/调优，逐模式声明旧不变量、新规则/设计、允许变化、源码/配置/存档身份、结果验证范围。
- 忠实恢复对比原版，换皮对比批准设计，feature对比旧不变量＋批准增量，tuning对比明确指标/体验目标。原型限定隔离工程/存档，一个问题与可观察留弃标准；不默认灰盒替代复刻、不强制原型全重写。
- 现有grea-evolve承担扩展，必要细专题放references，避免每个字段/品类再增加顶层Skill。

### L2.2 存档/配置/服务兼容

- 区分配置内容hash、客户端save schema、服务端schema/协议和业务兼容策略；不能用一个hash变化拒绝所有旧档。
- 工具先分析差异与生成迁移计划/候选，显式拒绝未知新版本，保护旧档及pending/幂等信息。只在批准的样例或隔离数据执行验证，不迁移普通游戏档或真实玩家库。
- 本地备份恢复与MySQL权威状态规则分别处理；不能用客户端旧快照覆盖已确认资产事实。

### L2.3 按需参考与版本交付

- 采纳genres、level-design、game-ui-ux、input/game-feel/audio/dialogue中改变执行决策的短参考；must-have变可选设计项，原版有的效果按证据恢复，新增效果需本期批准。
- 只读Unity meta检查规则先与现有依赖/资源审计查重，补真实缺项；DLL fileID、包未安装、二进制资源分别记录，不能用正则通过代替Editor导入。
- 版本输出是源码/配置/制品/兼容与已知缺口一组，不以提交数/测试数当完成；资源、业务、界面按成组成果集成。

## LC3 详细任务

### L3.1 只读数据与经济分析

- 定义有界事件schema与版本、事件ID去重、伪匿名玩家/会话、时间/时区、版本/平台、原始事实与推断分开；本地JSON/JSONL/CSV适配优先，不引入新中间件。
- 漏斗/留存/错误报告须有事件口径、分母/窗口、样本量、缺失/延迟与排除规则；数据不足不出确定收益/归因。
- 经济产出/消耗/库存与JSON配置情景分析，明确实际服务流水、配置理论值、模拟结果三类；不修改余额、不生成假交易。

### L3.2 配置/活动/发布预览

- 产生配置diff、schema/旧客户端兼容报告、生效时间/受众/环境/版本、发布预览和回滚边界；只生成候选，不直接线上生效。
- 数据写入/奖励不可逆副作用与配置回退分开，不承诺回滚配置文件即可撤销发奖。生产操作需独立授权、幂等和实际回读，未实现则Unavailable。
- 发布provider按实际目标选择。首先提供通用候选预检和现有目标信息报告；平台未选不默认Steam或要求开新账号。未来Steam/itch资料使用前核对官方事实；微信/抖音/Android/iOS支持不由文档命名冒充。

## 开发组织与推进

- 沿现有GREA开发者单人维护，不新建子Agent、不改模型/强度/大上下文、不建立项目经理或周期巡检。按完整成组成果本地提交，保护预存修改。
- 先L1.1＋L1.2做一个最小真实工程接续，再L1.3；LC1缺Editor/monkey能力时标具体局部阻塞，继续独立工具，不新增等待回执门槛。底层真实修复由其维护者处理，GREA不跨仓库改代码。
- LC1→LC2→LC3顺序推进，但未执行生产/未选渠道不是已批准本地工具开发的全局阻塞。无新事实不复做调研或重复全量验证。
- 只读引用上游固定commit38a4c25，保留选用文件、LICENSE/NOTICE与修改说明；本地私有游戏材料、账号、完整提示词不进GREA公开树。

## 完工报告与连续推进

本机开发采用工作区总监的《主开发者完工报告与总监续推规范》。成组完成、实际阻塞或准备结束但当前范围未完时，先更新本计划，再向已获用户授权的总监会话原生报告成果、证据、已验/未验、必要剩余及下一包。已批准就绪工作继续，不等待礼节确认；不扩大发布/安装/生产权限。本机来源与路由保留私有协作回执，公开产品不依赖维护者机器路径或会话。

## 当前进度（开发者维护）

| 版本 | 状态 | 下一动作 |
|---|---|---|
| 既有research/Cocos/Go包 | 按原计划保留 | 静态/真实Go已验与Creator待验分开，不被新包覆写 |
| LC1 工程接续 | 工具切片＋自有隔离原生接续／键盘运行通过；鼠标局部未过 | 阶段/模式＋v2合同及旧Unity/ui_ux兼容通过；真实固定monkey调用产出candidate/needs_action；来源/候选/模块池可回查；资产来源字段/中文联系表/尺寸及色数反例通过。后续自有adopted工程的Editor、macOS Player与持久化已验，详见下方新增记录；原始provider候选不冒充原生完成 |
| LC2 开发迭代 | 合同／有限兼容分析＋隔离计数回合增量通过 | feature/tuning/prototype合同及顶层save/config/protocol/pending分析通过；自有样例回合闭环、真实键盘UI、schema1→2、pending与重开已验；不代表任意真实产品或鼠标已验 |
| LC3 运营反馈 | 合成本地反馈链与候选交接入口通过 | 事件v1、会话漏斗/首观测D1、经济流、JSON配置diff通过；自包含入口串联既有工具与清单；真实数据needs_data，平台未选/适配未实现，生产写入Unavailable |

每次更新只记新成果、实际失败/未验和下一步；不追加多套每日台账。正式发布、远端推送、插件全局安装、引擎安装、生产部署与运营写入仍另行授权。

### LC1 本地结果（2026-10-23）

- monkey实测0.3.0.dev1/commit1e21f8a：自有Cocos输入2文件，经真实包级convert产出1个Unity候选、3条明细任务，GREA保持needs_action/candidate；来源前后SHA一致。Editor/编译/业务/画面not_run，不运行原始代码。旧真实产品样本不复制入公开fixtures。
- monkey_bridge支持固定配置/实现身份、能力探测、来源输入或既有包结果归一与有界模块合同；未分组任务留一池，明细不丢弃，不自动派Agent。包级native/resume不支持，明确拒绝；后续新增独立slice/resume合同，不能混用。
- art-ledger新增可选provenance；联系表通过实际中文图回看；alpha可选尺寸/精确RGBA色数，上限+1拒绝。没有上游Python复制/全量安装；保留固定上游来源与Apache通知。
- 定向测试覆盖生命周期2、provider2、资产4、旧evolve2/theme5/workflow3/grea15/case8/skill-sync5；MCP3通过。首次MCP失败定位为本地.venv遗留旧目录editable路径，备份并修复本项目虚拟环境，未修改全局安装或生产launcher。
- 旧JSON→SO制作真源冲突已修，正式JSON由Player强类型解析，SO继续用于资源引用。未改游戏/monkey工程、运行服务或全局插件。

### LC2/LC3 独立工具切片

- compatibility_plan只读显式顶层schema和隔离存档样例，区分config hash/save版本；可生成默认值增量候选，删除/改类型/pending/协议变化要求review，未知未来档拒绝。不执行普通档迁移或连接数据库。
- operations_preview在≤16MiB本地事件上按声明时区/窗口、版本、事件ID/回执去重，给会话漏斗、已关闭首观测cohort D1及经济流；缺分母null、开放日排除、同时间顺序不猜。不是获客留存、库存守恒或收益归因。
- config预览校验两份本地JSON，拒外部Schema引用，输出≤256项差异和受众/环境/生效/回退边界；不上传/发奖/通知/切实验。平台未选保持未选，其他目标也不能冒充已有适配。
- 当前4项分析反例通过（config变化不误拒旧档、pending/未知新档保护、时间/去重/分母/经济回执、Schema外部引用拒绝）。这些工具不关闭可玩工程、真实玩家数据、原生平台或商业渠道验收。

### 成组集成结果与下一出口

66项相称Python检查通过（含旧接口/MCP、13项发布逻辑检查）；独立源码投影加载12技能/21操作，用包内运行时实际调用联系表/色数反例/monkey模块接续/兼容/事件/配置预览。投影core摘要与当前实现一致；不是新原生平台发行构建或已安装插件。另对固定monkey真实既有包级产物只读归一，保持needs_action/candidate、明细索引和一个待分析池，不复制原始素材到公开树、不派Agent。分层记录见validation/development/lifecycle.json。

前述工具切片之后，用户明确授权在隔离工程执行LC1原生接续和LC2可玩增量；本轮仅新建自有样例并启动其独立batch Editor/Player，没有接管既有游戏窗口。新增结果如下；不重复已通过的Go链或无关全矩阵。


### LC1 原生接续与LC2可玩增量（2026-10-23）

- 新增monkey_bridge显式slice入口、来源profile/资产选择和实际provider resume适配；默认package与原ID保持。实际GREA CLI调用固定monkey1e21f8a，处理自有Creator2.4.15两节点/两Sprite/原生Button，静态零诊断、candidate/needs_action不提升。来源前后不变，完整模块绑定源规则/JSON/原生回读哈希；接续边界标明GREA声明，未冒充自动业务翻译。
- 原始候选在Unity6000.6.2f1实际遇到无效com.unity.modules.input依赖；新Unity脚手架经PackageManager解析uGUI builtin2.6.0与2D Sprite1.0.0。隔离NativeAdoption显式设Texture2D、保存bootstrap场景并创建输出目录；外部provider生成的Importer字节未改，原候选仍保留。原候选native resume为not_run，不能把修复后adopted结果回填成原件通过。
- adopted工程原生导入imported、Missing Script0、editableRoundtrip通过、全部原生Sprite/Button引用绑定；逐文件回读哈希仍一致。新Assets/Game接续实现正式JSON强类型读取、原生序列化Button/Text引用、计数与显式隔离存档，Editor规则反例和macOS arm64 Player构建通过。真实键盘UI计数0→2、QUIT、同包重开仍TOTAL2。
- LC1的339个工程/Player文件及存档冻结；在新LC2副本追加菜单→开始→goal3→结算→再玩，以及暂停/继续/取消。真实键盘实玩至TOTAL5/RUNS1，再玩计一次后取消，重开TOTAL6/RUNS1/MENU；所有业务事件与实际Return输入同帧。LC1全部冻结文件与旧档哈希未变。
- LC2 schema1→2追加迁移前原文备份完全一致，累计count及自有测试pending保留；规则检查覆盖菜单/暂停/结算重复提交保护、取消不增完成数、配置版本变化不误拒旧档、未来save版本与坏配置拒绝。未来档负面Player启动未另跑，不将Editor规则检查说成该项Player实测。
- 自动鼠标确实进入Unity，但被读取为窗口外坐标（示例779,-621，窗口480×720），没有有效Button点击；键盘UI通过与鼠标not_passed分别记录，未注入业务回调伪造输入。实机画面已回看，未宣称原版视觉一致性、Windows/Creator运行或商业分发完成。
- 实际v2 feature合同已绑定LC1冻结清单、LC2候选源码与Player Build清单，并登记原始规则、Editor测试和具名Player事件；Case中identity/rules/runtime为范围内reviewer_assertion，visual仍not_run（candidate设计），整体保持incomplete且verified_game_equivalence=false，不把自有玩法冒烟提升为已批准产品的完整验收。
- 自有可复验示例在tools/unity/lifecycle-sample/，分层身份与验收在validation/development/lifecycle-native.json，原日志/工程/包/存档只留[私有本地路径已脱敏]。定向Python 11项、契约、文档、技能同步通过；没有改游戏原工程/monkey源码、推送、合并main、打标签或发布。

当前必要限制是自动鼠标坐标验收和provider无修复原生导入边界；已验自有样例可作为后续接续/有界开发示例，不折算为全游戏恢复率。下一包应优先由底层维护者修复明确导入边界，再在固定版本的新隔离候选复验鼠标路径；原版多根复杂工程与LC3真实授权数据/渠道仍按实际输入推进，不自行扩大生产范围。


### LC3 本地反馈与生命周期候选交接（2026-10-23）

- 续推沿既定LC3范围，不等待monkey、不再循环自动鼠标；底层四项原生导入缺口已归其维护者。只收拢本地反馈与交接，不新选渠道、不取真实玩家数据、不生产写入或新增全量验收。
- 既有合成输入8文件与原验证逐字节一致，operations_preview/compatibility_plan及依赖代码与此前已验独立投影一致；复用已有4项定向检查与66项集成记录，未重写分析器或新建测试框架。LC2 Player日志缺运营时间／会话合同，未补造事实转作运营数据。
- 新增tools/lifecycle-feedback/README.md作为可复用入口，按文档原样执行5次既有工具与1次inspect-target：事件→人工有限JSON配置diff→声明顶层兼容→配置回退→保留save schema2的回退兼容→本地逐文件盘点。新示例/输入沿现有产品投影自动纳入，没有额外服务、MCP操作或调度层。
- 单条合成start的漏斗[1,0]，无活跃session_start事件故无D1、无经济流水；不据此提出奖励上调。reward1→2是原有手工候选；正/反diff仅/reward，均candidate_not_applied。前向schema1→2增默认label；配置回退仍保留schema2、label和pending，只生成候选，不写普通存档、不逆转业务事务。
- 交接沿现有交付清单映射来源提交/dirty、开发通道、数据口径、目录身份、入口、验收与未发布状态。当前本地结果6文件coverage complete，buildId是本地清单身份，不冒称游戏构建或插件发行。分层报告validation/development/lifecycle-feedback.json引用既有LC1/LC2验收摘要，原始本机路径结果和盘点留私有目录；不外发。
- LC1/LC2键盘原生样例、候选正式视觉、原provider、鼠标、完整游戏等价、真实运营数据和未选平台继续分开；LC3链通过不关闭这些限制。可交接当前本地候选源码／示例／证据，整个产品或生产版本未发布、未交付。

下一可执行范围由具名输入／固定provider修复或明确授权数据决定；本轮本地候选交接包已形成，不将未授权渠道、真实数据或生产操作变成继续空转的理由。按完工报告规范回报当前身份、已验与必要剩余，不增加周期巡检或礼节等待。


### 本地main整合与Codex插件升级（2026-10-24）

- 用户明确授权当前分支合本地主分支、GREA＋monkey协作与本机Codex升级；GitHub推送／标签／Release、Claude安装及其他插件／游戏服务不在范围。本机AGENTS预存修改已私有备份且未提交；8个既有提交正常快进合入main，来源分支保留。
- 新权威参考01-流程-全量初版工程与协作，统一路由／恢复／Cocos／交付与provider说明：GREA来源取证冻结→monkey全量资源与可恢复代码／依据导出独立初版→GREA核交接→游戏Agent业务、视觉、服务器和后续迭代。不把未知方法、空类、lookup／媒体／IR或completed标志说成完整初版。GREA不新写转换器；原转换ID保留兼容，非批量恢复主路径。
- 实际plan_workflow完整恢复／port输出批量先行分工和未支持状态；局部fix不强制重导。monkey_bridge保持旧package/slice接口，新增显式handoff合同审计来源完整盘点、逻辑资产处置、实际原生图、代码依据／TODO、AI入口及外置导入编译收据；只核字节和提交者声明，不冒充重跑Editor。新all-scope自动导出适配明确not_available，未等待上游或复制解析器。
- 30项受影响桥接／规划／兼容检查已通过（旧首步骤断言按新流水线修正；输出预算测试在允许本轮子进程信号的环境复验通过），另补lookup伪原生图反例。真实CLI对自有静态样例维持needs_action，未执行引擎；文档、契约及技能验证通过。LC1／2／3既有实跑和限制复用，不开游戏Editor、不做全平台重验。
- 代码／Python包／uv锁及两种客户端源码manifest统一候选版本2026.10.24rc1；不是远端已发布版本。本轮从固定提交构建完整macOS arm64插件，用官方Codex plugin命令更新已有GREA@Konanw；旧包与注册备份，其他插件／凭据不改。
- 完整macOS包已从56e7179干净提交构建，版本2026.10.24rc1、SHA d5770a8fb6539dc812972335b0b6d5ffe96c20aab70a9b758127614db2648e92；隔离验证通过，安装副本3571文件hash匹配、12技能可见。官方Codex plugin add已安装并启用唯一GREA@Konanw，其他配置／marketplace条目不变，Claude未安装更新。
- 安装副本独立stdio的session/describe_tool/plan_workflow通过，package_root与随包Python均在新版缓存；这是独立stdio层。当前会话仍连接2026.10.17，未热加载新版；官方安装器清理旧缓存后已仅恢复原字节保证旧会话正常，不回滚新版注册、不启用第二服务。当前session和只读能力恢复ok。
- 最后待验是正常刷新／新会话后的真实客户端session版本与package_root；必要时由用户在合适时机正常重开Codex，不强重启当前或其他工作。分层回执见validation/development/codex-upgrade-20261024.json。未推送、打标签或发布；LC1／2／3原有未验边界继续保留。

- 收尾向总监发送一次报告被自动审批拒绝（未认可当前会话对具体接收线程的明确授权）；未重试或换渠道。本地代码／安装／回执不受影响，发送阻塞原因已写入本轮分层记录。

## 2026-10-31 固定 monkey dev1 的公开保存态复核（有限接入）

沿用`monkey_pipeline pin/audit`，新增显式`--level static/editor`及预期manifest/readback SHA，转调用固定provider现有只读verify；不启动Editor、不重跑恢复/30×2，不重写原生校验器。423包文件与wheel/归档/固定提交一致；交付源码多出的两份Unity.meta未删除，改用GREA私有wheel副本获得准确身份，无全局安装。pin/probe拒同版不同内容，dev1转换plan/run保持未适配。

公开GREA源码CLI实际完成固定pin与Unity保存态复核：static/nativeStatic/runtimeCheck=pass、editor=partial，原样保留378条Spine动态与56条动画曲线边界，视觉/业务not_run，顶层needs_action。错manifest、错readback（源码stdio MCP）、已锁包漂移、同版异包pin及未适配convert正确定向拒绝。消费者90组原始资源/代码与meta的162保存态＋18未变生成代码/meta当前哈希已只读核对，不为它们重做Editor。

新选择冻结/编译依赖声明和beaver分阶段adopt仍待下一固定交付；已协调唯一adoptionDependencies合同，不预注册命令、不宣布全链完成。新接入证据见[dev1公开入口验证](../validation/development/monkey-dev1-integration-20261031.json)，此前交接审阅保留初次未支持状态，追加当前接入进展，不改历史原始回执。正式锁、全局插件与游戏工程保持，本轮无新增推送/发布。

## 2026-10-31 beaver fix10 evaluation 合同审阅（未晋升）

已核固定源码 `8e25793fe6eaf1c325f701c94256352095a0f3b9`、version `0.5.1.dev20261031+fix10`、producer `3a64f4f5301e1ec1591df6e3ad92a8236e504cb0a9379a21e63c01f81419ed89`；123运行文件与提交/wheel/私有安装逐字节一致，18份合同hash一致。adoptionDependencies v1正式冻结为producer-declared .cs边：缺项/重复/自引用拒绝，异文件环允许；缺省undeclared，不等于完整闭包。adopt plan/apply/rollback参数保持，GREA现有命名转发无需新增参数或C#分析器。

此次仅evaluation接收，不加入GREA可执行版本集合。上游源码试验5资产采用/重开/回滚通过，不替代最终固定安装原生验收；故意编译失败在资源写入前停止并恢复代码before-image，后续原生恢复两次被Unity许可exit198阻断，目录/身份恢复、固定安装原生及消费者复验仍pending。已有fix9与0.5.0记录按原身份保留；不自行修许可证、重放事务或修改游戏。详见[fix10 evaluation审阅](../validation/development/beaver-fix10-evaluation-review-20261031.json)。

### fix10 固定安装原生复验后的接入

随后同一8e25793制品完成固定安装5资产采用/独立重开/公开rollback；故意编译失败事务也完成原生恢复。GREA已核三份原始结果的producer/Schema及最终rollback制品hash；apply journal被后续rollback合法更新，旧apply哈希不当当前文件哈希。历史许可失败和evaluation审阅保留。现增加fix10精确producer版本门，既有adopt参数不变；真实GREA CLI pin ready，26项受影响检查通过。消费者仍pending，GREA未重跑Editor/事务、未改全局安装或发布。见[固定接入回执](../validation/development/beaver-fix10-integration-20261031.json)。

### 消费者公开入口复验进展

已只读核消费者实际grea-dev1-saved-audit-01与fix10-static-preflight-01回执：前者真实调用dev1，static/nativeStatic/runtimeCheck=pass、editor=partial，executed=true/editor_started=false/handoff_ready=false；后者真实fix10 producer完成adoption.plan，native/player/visual/business均not_run。此为消费者已执行保存态审计与采用规划，不是原生apply完成。非GUID支持代码仍由目标基线保全，依赖声明undeclared，等待monkey公开冻结出口；默认monkey0.6发现信息不当实际执行版本。回执hash追加到既有真实链路审阅，未重跑游戏或工具。

### dev2 保存态选择出口已有限接入

固定c279a6a dev2的425文件与wheel/提交逐字节核对，通过GREA公开CLI pin及freeze-native-selection实际生成P04选集219文件、3条producer-declared边；12条未分析脚本诊断保留，字体覆盖仍unknown，动态修复未包含。28项受影响测试通过；源目录额外meta不删除，使用已核wheel私有副本。已开放公开选择出口供fix10消费，原生成态/保存态父hash不变，未启动Editor或推送发布。见[dev2接入](../validation/development/monkey-dev2-integration-20261031.json)。

### 构建链真实消费缺口（待beaver固定合同）

已只读核fix10已安装BeaverNative.Build确为BuildOptions.None；消费者现有构建器实际使用Development，并对TMP动态字体执行有界规范化、逐字体源字节备份、源/构建输入hash区分及finally恢复/reimport。现行通用入口不能冒充项目QA构建。Development策略、profile/Connection明确选择和可审计TMP源保护归beaver设计实现，GREA待固定合同按真实差异适配；不开放任意executeMethod、隐式项目hook或全局SaveAssets。现有在途项目构建链单列未迁移，真实profile/存档隔离和包内字体正确性仍由消费者验收。见[构建合同缺口](../validation/development/consumer-build-contract-gap-20261031.json)；本次仅代码核对，未构建或操作游戏。

消费者随后更正：Profile/Connection环境读取无DEVELOPMENT_BUILD守卫，普通构建也读取；Development用于受限连接错误日志与只读验收探针，不是隔离配置生效条件。不得从BuildOptions.None推断必然使用默认存档。构建模式与运行profile身份分别验收，TMP保护缺口不变。

### fix11构建合同已有限接入

已核固定6b7e74f的124运行文件与提交/wheel/安装相等、19合同及上游固定构建manifest哈希；4字体源/恢复hash相等。固定安装成功构建证据复用；失败/中断证据按上游说明复用仅version字符串不同的源，不冒称另跑固定失败。GREA真实CLI pin及Development正向规划、字符串模式/任意hook拒绝已验，29受影响检查通过，未启动Editor。消费者QA构建与字形/视觉/运行配置仍pending，不退役项目链。见[fix11接入](../validation/development/beaver-fix11-integration-20261031.json)。

### dev2 Shader文本依赖缺口（已实证，待新固定候选）

已只读确认219文件选集漏TMP_SDF-Mobile.shader的literal include TMPro_Properties.cginc及meta；两文件源hash与U106 nativeFiles一致，选集确未登记。dev2公开冻结/字节校验结果保留，但完整Shader依赖门不得记pass；既有fix10加载/回滚只按原限定结果使用。monkey负责通用递归include闭包与独立shaderDependencies合同，新候选未交前不预注册、不手拷修补原选集；原件保留。缺口hash已追加dev2验收记录。

### dev2公开冻结的真实消费者采用（限定通过）

已读取消费者dev2-consumer-native-result-02.json并固定hash：公开freeze的219文件经项目仅路径/namespace适配及3条依赖边映射，fix10在未预置两支持类型的干净目标副本同批采用90资产、18编译输入，独立编译重开身份一致，公开rollback恢复90项，55349基线文件零字节差异；首次导入新增3个Art目录meta明确保留。原私有扫描入口已停用，项目适配仍自包含。

完整依赖门仍false：目标原本存在缺失的TMP include及meta，因此此次成功不能证明219选集完整。12未分析警告、动态/视觉/Player业务未验继续保留；等待新固定修复。消费者fix11 Development＋14字体构建已开始但结果尚未交付，不记构建通过或旧项目builder退役。GREA本次只读消费者摘要，未重跑原生事务。

### fix11真实消费者构建阻塞：进程退出后字体源漂移

已核消费者保全journal状态recovery-required及四份证据hash。原生Build成功、Development及字体恢复标志为true后，退出进程的完整source校验仍发现5份小型动态字体源漂移，公共apply拒绝认证，App15无合格制品清单。不能用原生成功或旧私有fixture替代真实构建通过，现行项目builder不退役。

源恢复/guard生命周期归beaver，要求原fix11事务兼容恢复或明确逐hash before/after合同；GREA只读保留原失败，待固定修复再接入，不写字体/YAML、不自动重放构建。当前消费者恢复结果待交付，尚未签全链通过。

### fix12退出后字体保护接入（消费者待复验）

已核61fc30b固定制品125文件与提交/wheel/安装一致、20合同hash及上游真实安装退出后全source回执hash，5字体源/meta postExit哈希相等。GREA精确绑定fix12，原构建请求不变；独立新增unity.recover-font-source严格review入口，不放宽旧普通recover。真实CLI pin与Development规划/非法模式和hook拒绝通过，33项受影响检查通过，GREA未执行Editor/源恢复。消费者原14字体QA构建待交付；fix11源漂移与旧App不认证的证据保持。见[fix12接入](../validation/development/beaver-fix12-integration-20261031.json)。

### fix12真实消费者构建段通过（App16）

已核consumer-verification-01.json：App16源码bae7b4655a8ddb7770478cb9c6eb1dcc944eccd1通过GREA公开unity.plan/apply使用固定fix12，Development=true，构建0错误，拥有Editor退出0；parent-after-editor-exit认证。消费者逐项复核55608源文件、14字体及meta无差异，275制品文件bytes/SHA一致，legacyBuilderUsed=false。GREA核固定producer、消费者回执hash与provider制品manifest hash，不重复全源/载荷扫描。构建段可记真实消费通过，旧App15失败和人工恢复仍不改记工具恢复成功。Shader闭包、字形、Player登录及业务视觉仍未验，不签全链或v2完成。证据追加fix12接入记录。

### dev3固定选择入口及最终候选接续

434文件与固定4ad7498提交/wheel一致；GREA实际pin/freeze生成221文件并核TMP include+meta存在，28受影响检查通过。运行时/字体最终247文件候选另核manifest bae39e...732373及6依赖边，复用消费者全hash与beaver核验，不重跑全池/Editor。四个新native runtime/font CLI帮助参数已核，尚未注册GREA typed操作；当前已有最终候选可直接采用。221选集与247最终候选分开记，Shader编译、物理输入、Player尚未验。见[dev3接入](../validation/development/monkey-dev3-integration-20261031.json)。

### dev3四项生成操作有限调度已实现

monkey_pipeline native-step新增严格四操作请求；精确dev3锁、有限命名参数、显式输入根及前后完整快照、expected hash、字体request外部路径边界、输出库存/manifest逐文件审计；不自动启动stage指令或Editor。31项受影响检查和四项真实公共CLI非法输入拒绝通过。重型正向生成/字体/Editor本轮未重跑，旧247候选不变。见[四操作适配记录](../validation/development/monkey-dev3-native-steps-20261031.json)；实际新正向产物仍需自然任务复验，不能将调度接通当产品闭环。

### macOS文稿访问整改的通用运行合同（实施等待固定交付）

已原生核验用户要求整改测试App反复文稿提示并继续开发。GREA现有player.run/debug并无本轮prepare/launch/collect合同，不冒充支持；已将有限CLI/MCP、producer/能力、稳定profile/备份、env/cwd/签名及受控denyDocs回执需求交beaver。开发/发布参考补齐运行身份与真实验收门；收到固定实现后有限转发与实调，当前不签整改完成，不在GREA复制启动器。既有dev3和构建结果复用，新增自然运行由消费者执行；无Editor/桌面接管或全局安装。

运行接口设计已收到：拟qa.prepare/launch/collect，仍无固定候选。已向beaver交接实际调度前必须明确的ID/路径与owner摘要、跨构建profile初次seed及不覆盖保护、Bundle内部链接身份、run/PID归属与超时/收集语义、denyDocuments实际生效证据。CLI参数尚在设计中，不预注册；原流程状态继续等待固定合同，独立消费者开发不阻断。

### fix14 QA运行有限接入已交付

已核d4ff4c6固定126运行文件与提交/wheel/安装一致、22合同hash；GREA实际pin ready，公开prepare非法spec与collect未知owner拒绝；36受影响检查通过。新增三项有限命名转发及ID/预算约束，launch无out、不套Editor占用门。真实App21/App22 GUI、同档重开/新构建续档和denyDocs访问来源由消费者自然任务验证，当前不签权限整改完成。见[fix14接入](../validation/development/beaver-fix14-integration-20261031.json)，不重跑Editor或既有构建。

### fix14真实prepare预算阻塞

消费者公开prepare App21-normal在复制resources.assets.resS时触发PAYLOAD_FILE_BUDGET，未launch。已保存消费者CLI回执hash；actualChanges与持久prepare-260c50fccba44f238cbb55ee1d76b74f.json反映阶段写入，blocked不当零写入、不自动重放。原build/spec继续冻结，待beaver固定流复制预算修复及安全partial-stage处理合同，当前权限整改仍未完成。

### fix15大制品prepare修复已接入

已核3096fde固定126运行文件/22合同与提交/wheel/安装一致；GREA公开pin与两项拒绝路径、36检查通过。上游固定公开CLI真实复制App21的277文件/2204390599字节及源副本同CDHash证明已只读核producer与原回执hash，GREA未重复大包复制。旧fixed14失败审核为committed空、无提升，属于当时状态；消费者重试前须再核，无自动清理/重放。三操作/spec不变，仅合格artifact预算贯通。GUI/同档重开/真实新构建/访问来源仍待消费者；见[fix15接入](../validation/development/beaver-fix15-integration-20261031.json)。

### fix15真实launch收口失败

消费者大包prepare成功后，App21真实GUI进入游戏并正常CmdQ退出（消费者记录），但provider CLI收口IO_OR_INPUT失败：data.report为process对象而被当路径处理；kernel路径大小写差异还使PID身份unknown。已固定CLI与持久run回执hash，实际进程副作用保留，不据外层failed自动重放。待beaver固定结果/进程身份合同修复，HTTP瞬时ReceiveFailure由项目修，均未记稳定通过；本轮GREA仅只读核据，无启动/桌面操作。

### fix16运行结果与文件身份修复接入

已核ee13bdd固定126运行文件/22合同与提交/wheel/安装一致，公开pin及拒绝路径、36检查通过；同qa参数兼容旧owner/profile。修复report对象误作路径，samefile处理真实路径别名并保留start/log护栏。已核上游fixed16只读collect原fixed15 normal01的报告hash，不重跑GUI/大包扫描，不改旧失败/unknown。消费者新GUI、同档重开、denyDocs及新构建续档仍待验；HTTP项目问题分列。见[fix16接入](../validation/development/beaver-fix16-integration-20261031.json)。

### 真实HTTP与文稿运行路径影响范围通过

已核App23 d4578aafb16b4a9168ec269ce3450ad9144471b7消费者验收记录/受控拒绝回执hash，并独立匹配两轮运行日志SHA。公开fixed15 prepare复用App21稳定profile且seed未重播；fixed16两轮denyDocuments GUI正常退出0、launch ok、最终collect collected/Bundle匹配，0连接错误与ReceiveFailure，棋盘真实移动退出重开保留，未观察到文稿提示。此影响范围的HTTP和测试运行路径可记消费者通过。

初次live collect在sandbox-exec切换前捕获基线，identity_unknown/recovery_required仍保留，最终退出态collect通过不抹去该限制。受控deny只证明测试所需路径条件，非全文件syscall或clean-TCC；全v2与其他规则/资源/支付缺口仍未完成。旧App21/旧工具失败保持，不新增启动/改数据/发布。

### 25项产品缺口的工具链分流

已原生核本轮用户归属核查指令及批准分类：2项项目算法/集成输入依赖、4项资源/混合恢复、19项规则/服务/版本映射，不是25个工具bug。gap:P04为背包主题，sample:P04为周任务，两ID域分开。GREA在原排障参考加入来源缺失/解析失败/采用失败/项目接线/权威状态/薄适配六路分流，恢复/开发参考按需链接，不复制产品25项台账。

已闭合固定采用/回滚、fix12保源构建及fix15/16运行路径复用，已实调freeze/upgrade/finish不重跑全套。现存12未知依赖、动态Player真实点击及资源限定核查分别由monkey/项目接续；没有新固定合同或实际GREA消费缺陷，不为文档增加实现/版本。分类不关闭产品项，不新增支付/普通档/全局安装/发布权限。

### dev4依赖补证有限接入

已核19d51d4固定435包文件与wheel/提交一致，公开pin和非法审计输入拒绝通过；native-step新增严格audit-native-code-dependencies，冻结两项目manifest与有限命名参数。复用Final247FixedSupplement01报告做只读输出审计：22脚本/逐requires/2包文件及3实现文件hash匹配、0uncovered、11原诊断逐值保留。未重跑producer完整快照/生成、字体、Editor或Player；既有dev3采用/L2继续复用，资源缺口另线不算完成。见[dev4接入](../validation/development/monkey-dev4-integration-20261031.json)。

### dev5 A10原生资源前置门固定交付审核

已核ea172e0固定436包文件与wheel/归档/提交/冻结源码一致。新operation合同未变，不为版本号切换已验dev4链或重跑依赖/字体。Producer报告Creator通用owned树/tombstone/Undo修复后静态S2原生pass，原候选metadata仍dev4，helper等价须单独绑定；GREA已请求准确原生回执与emitted helper根，当前只核固定制品，不冒称独立验过原生证明。Unity renderer/初态及项目入口、动画、赛季映射继续待验，不恢复暂停产品。见[资源前置门审核](../validation/development/monkey-dev5-resource-gate-review-20261031.json)。

已按补齐路径只读核实际NativeRun01/CocosProject：6发射helper与固定dev5源码逐hash相等，候选manifest匹配原生proof/execution父身份，metadata/verification仍dev4不改。静态resource proof为准确S2骨骼13bones/11slots、保存引用及纹理身份通过；editor pass0diag。execution实际exit -15、stopReason=native_completed保留，不当正常用户退出。原生原文及readback hash已封存于原dev5审核记录，GREA未重跑Editor；动态动画、Unity初态/renderer及产品入口仍未验。

### dev7 A10选择闭包阶段记录

已核78f4f8d固定436文件与提交/wheel/归档及冻结源码一致，现有CLI与adoptionDependencies v1未改，不新增typed dispatch或强制迁移旧消费链。producer报告A10源静态/GUI像素证明仍绑定dev6 a18e786 Stage09，dev7补选择包非GUID Spine helper/runtime/DLL/meta/license闭包，独立spineRuntimeClosure不扩csharp边类型。Graphic SDA .01/CanvasPPU100保留源节点.75的单位映射按实际采用核对。

GREA本轮只核固定制品身份与阶段归属，不把源证明改记dev7新运行；S2不等1.9.4赛季/时间，动态playTimes/cache未恢复，目标须采用完整runtime或证明等价GUID/PPU映射。既有dev4/字体/输入及beaver闭环复用，无新Editor/产品Cocos启动。见[dev7阶段审核](../validation/development/monkey-dev7-stage-review-20261031.json)。

## 2026-11-01 SDK采用与构建认证接口预审（固定17待交）

已原生核用户继续推动产品开发指令，沿真实工具链缺陷接续。beaver拟保持adopt plan/apply参数，增加managedAssemblyCompatibility计划数据：Assets内managed PE/CLI实际身份、公有类型、精确importer角色有限覆盖；显式互斥角色policy不授权替换旧SDK/importer或改m_Script，真实native migration仍未实现。GREA现有结果Schema已用合成blocked数据核可原样保留新增对象/诊断，不需新操作或复制DLL分析器。

构建须Succeeded且明确整数errors=0由native和parent独立核；源码/字体保源仍适用失败路径。当前仅接口预审，未注册未知fix17或重放旧计划；收到固定producer、合同及原始正反例后再实调blocked保持阻断。见[SDK接口预审](../validation/development/sdk-adoption-interface-preview-20261101.json)。

### fix17 SDK守卫固定接入

已核9e587a7固定128运行文件与提交/wheel/安装一致、23合同hash，GREA实际pin及39检查通过。公开adoption.plan清洁4 DLL显式pair通过；使用原独立legacy baseline的冲突规划blocked，随后公开apply在ADOPT_CONFLICT处拒绝，无事务/Editor。初次错误baseline参数被原保护拒绝的调试回执保留，不放松保护。

新managedAssemblyCompatibility data/diagnostics原样消费，无额外DLL分析器或新operation。构建Succeeded且显式整数errors0由上游双层核；GREA未重跑Editor/产品构建。App31、fixed12旧事务保持，consumerNativeAcceptance仍pending，历史SDK迁移未实现。见[fix17接入](../validation/development/beaver-fix17-integration-20261101.json)。

P0-B后端协调补充：beaver确认cua-macos bind将以QA_ATTACH_BACKEND_UNSUPPORTED安全拒绝、不调用getApp，SDK迁移独立推进。已向总监给出最小attachExisting接口及native AX替代路径。当前Computer Use只允许cua_repl交互，其他技术须人类明确指定；故可准备本地桥接实现/接口审阅，但实际非CUA输入须明确人类技术授权或可用后端API到达，Agent互相消息不能代签。无新真实输入/TCC/进程控制操作，P0-B保持具体未闭合。

P0-B授权更新（2026-11-01）：已原生核验用户明确允许本轮macOS原生AX／按PID定向CGEvent桥接，仅自有测试App与项目Player、已有权限，不改TCC、不自动启动替代实例。技术授权阻塞解除；beaver固定实现、GREA公开接入和实际消费者验收仍待交，当前不宣称可用。monkey新SDK声明交付已收到，尚未纳入本次已验typed dispatch，不改旧dev7资源/原生证明身份。

### dev9 SDK声明公开消费（本地后续增量，未推送）

固定735a87e的436包文件逐项匹配提交/wheel/交付源码；隔离包避免将源码旁Unity附加meta纳入固定身份。公开pin和native-step依赖补证实调通过，8脚本0uncovered；20,283字节报告与producer固定报告SHA一致，4 DLL的not_run脚本表和literal引用保留。Producer采用显式独立冻结输入副本，不全扫Library、不改原候选；旧ProjectVersion与原生回执差异保留，不据副本宣布重开通过。未运行Editor/Player，SDK迁移与稳定实例输入仍待beaver/项目验收。见[dev9接入](../validation/development/monkey-dev9-integration-20261101.json)。

### SDK迁移／实例绑定接口预审（未封存，不接运行时）

已核beaver SDK-MIGRATION与QA-BINDING现行文档及CLI定义。当前GREA会明确拒绝新sdk-migration参数和qa.inspect-instance/bind/input，不能原样调用；拟在固定交付后补成对路径/hash、新有限operation、QA ID与backend/window约束，并从同源生成契约。现有result envelope可保留blocked时非零posted/AX效果与launchPerformed=false，无需复制SDK或输入实现。未改版本白名单、未绑定活动源码、未跑Editor/桌面；producer独立重开修复及真实消费者仍待交。见[接口预审](../validation/development/sdk-binding-interface-preview-20261101.json)。

### fix18固定公开接入（本地未推送）

已核b5e9b03固定132运行文件匹配提交/wheel/install及7合同。增加adoption.plan SDK成对路径/hash与qa.inspect-instance/bind/input有限门，backend枚举、uint32窗口、完整run身份及同源Schema约束；旧版本不因新CLI参数放开。81项beaver测试通过，包含partial/unknown效果保真及禁止自动重放。

实际公开pin、独立冻结baseline副本上的迁移正向规划（0冲突）及默认旧SDK阻断（4冲突）通过；缺归属inspect/bind与假session分别QA_UNKNOWN_OWNERSHIP／QA_BIND_SESSION_SCHEMA阻断。副本Assets/Packages/ProjectSettings逐项仍等于冻结baseline，未触正在使用的NativeTarget，无Editor/桌面输入。producer报告SDK原生apply/reopen/rollback通过尚待固定回执消费，肥鹅真实迁移与绑定输入仍pending。见[fix18接入](../validation/development/beaver-fix18-integration-20261101.json)。

fix18补充：最终candidate-delivery的14项原始证据已核SHA；固定CLI producer一致，native独立verify状态/SDK程序集与引用标志、GUI绑定launchPerformed=false及中性review passed已只读核。32 canonical脚本、inactive Player真实空表与独立MVID旁证按producer原身份保留，未解释为Player运行通过；不重跑Editor。已准备向项目交付公开invoke＋固定lock路径，产品SDK/输入验收仍未完成。

### App40实际输入差异（fix18保持固定）

beaver反馈消费者App40进程/birth/owner/profile/window绑定和正常退出collect通过，但逻辑窗口内点击及文本未产生登录效果；不把中性fixture或投递状态外推成Unity业务通过。GREA仅记录该实际差异，未独立读取项目原回执，CG屏幕/Cocoa窗口payload差异仍为待证诊断假设。fix18不改、不替换重试、不扩版本门；等待通用工具诊断及必要新固定候选，SDK项目消费独立继续。

### fix19指针同步有限接入（本地未推送）

27d21d2固定132 runtime与提交/wheel/install一致、7合同核验；84项beaver测试通过。新backend仅fix19显式可选，旧event-only/default保持；同源Schema记录值版本门。实际public pin及inspect/default bind/pointer-sync bind均在unknown owner处阻断，无控制器/指针动作。结果保留cursorSync及0事件但已移动的partial效果，不自动重试。固定Unity gui-review只读记录0→click1→drag2/exit0，最终原始输入回执待交，未把此摘要升级为肥鹅产品通过。SDK另一门独立待验，不阻塞就绪输入交付。见[fix19接入](../validation/development/beaver-fix19-integration-20261101.json)。

fix19输入最终交付补充：已核input-delivery的11份证据SHA与9个CLI固定producer，窗口PNG字节SHA匹配且已查看counter2／IntegratedUnity，click/text/drag performed；AX close partial原样保留，normalexit0/collect独立通过。已立即将GREA fix19公开invoke＋pin/backend门交肥鹅主开发，产品输入待实际回执，不等待SDK另一门。SDK fix19新增inactive方案的checkpoint失败单列，producer正在public rollback/修正；完整4055 spec不切行，仅预检、暂不apply。

### fix20 SDK独立固定接入（本地未推送）

已核ec305d7固定132 runtime匹配提交/wheel/install及实际native runtime-map、7合同与10原始证据SHA。固定CLI producer一致，SDK apply/cold verify/rollback原文与inactive/程序集/引用验证标志通过，原Target45文件逐hash回滚一致。GREA新公开pin与独立baseline副本规划0冲突、默认SDK8冲突、stale spec的ADOPT_SDK_SPEC_DRIFT阻断通过，86项beaver测试通过，无Editor重跑。

SDK可独立交项目真实v05 spec/native复验；4055旧完整spec解析记录与当前4054产品spec分别保留，不混身份。输入5实现文件逐项等于fix19、产品InputSystem/uGUI仍未接受；GREA仅开放fix20 SDK门，QA锁继续fix19，避免SDK更新冒称输入修复。见[fix20接入](../validation/development/beaver-fix20-integration-20261101.json)。

### SDK消费者闭合与fix21输入接续

已读取消费者原生会话最终记录，fix20限定SDK通过4054真实引用（2404 script＋1650 object）、32 canonical/2 inactive，4份原native回执SHA/status/error/SDK标志与3份源比较摘要已独立核；复用55767/55763原比较，不全扫正式工程。P0-A scoped native完成，不等于Player/输入或全产品完成。

fix21 b690d00固定132文件/7合同核验，87项beaver检查通过，实际公开pin/unknown-owner拒绝通过；11输入证据和9 CLI producer及实际单窗PNG核验，匹配InputSystem1.20.1/uGUI的counter2/Fixed21UGUI已查看，click3/三点drag5/exit0/collect，AX close partial保留。已给肥鹅新21pin/显式backend做原App40新run真实登录/拖棋/退出/续玩，不重建、不复跑SDK20。见[fix21接入](../validation/development/beaver-fix21-integration-20261101.json)及[SDK消费者核验](../validation/development/beaver-fix20-consumer-20261101.json)。

### P0限定实际消费闭合及回执版本化纠正

只读核实际fix21消费者SHA35612876：9请求SHA、8native报告、2原collect（exit0/非budget/同bundle）及15字段resume均通过；真实默认uGUI输入/登录、31→29权威换位revision340→341、资源不变、两新strongrun/旧profile续玩。无QA pump、重建或重新播种；过期quit blocked和后续Command-Q partial保留，不翻绿。P0-A SDK和P0-B输入在本范围完成，不代表v2.0整体；桌面由项目保留，不新增工具任务或重跑矩阵。

证据纠正：fix20 integration回执曾在上游封SHA后合法增补consumerAcceptance，产生00b232cf漂移。已将新增内容另存独立[SDK消费者补充](../validation/development/beaver-fix20-consumer-20261101.json)，原integration恢复精确20c57295旧字节；fix21 integration保持原48c3eb75字节，实际结果写[输入消费者补充](../validation/development/beaver-fix21-consumer-20261101.json)。[版本化闭环索引v2](../validation/development/sdk-instance-consumer-closure-20261101-v2.json)关联原44a2d879总根和各补充的完整SHA，原beaver总根/旧失败未改。不将消费者完整结果再次原地写入已封存integration报告；本段和v2索引为当前状态出口。

beaver自有追加冻结索引`toolchain-final-closure-20261101-supplement-v2.json`已只读核SHA `4b4ac11640daf488ff4703888fb477fa042178708b756e68242ce26a1fb960bd`；其原44a根/三闭包及GREA正式1fbae与历史快照关系保持。此处仅补定位，未改GREA冻结索引或任何原始回执，无游戏/源树重验。

### fix22实际消费者限定收口

已只读核[fix22消费者补充](../validation/development/beaver-fix22-consumer-20261102.json)：公开GREA/provider partial和exit1保真，实际Editor exit0、源未改/helper清理、marker由Editor正常释放；78,451,604字节快照SHA087135a3已流式核对，61,701资产/79,259对象/0未解析依赖。2MB原比较与来源ledger SHA匹配、6717 pairs/0issues，复用owner逐asset/meta原SHA检查，不重复13k源文件扫描。

beaver独立追加闭包`fix22/consumer-closure-01.json`已核SHA `bfb6b807a25884781b1c685efd20fc42c8adda2b67aa9b549deebec6514fdb27`，其三份SHA命名消费者副本与原snapshot/ledger继续保留。原整串argv识别Editor共因在本消费者层闭合；全库111原零对象资产的两类222 blocker仍partial，不翻绿，不重apply/不运行Player或业务。原integration保持b0f61423固定字节，后续结果在补充单独记录；monkey v0.8新静态Prefab候选/原生显示与项目采用仍另验，旧SDK/QA锁不升级。


### 2026-11-04 工具链负责人接任与二进制分发覆盖

已原生核验 human01a1a615-b947-7962-a02c-a058671ff197、01a1a618补充，以及最新 human01a1a621-7b28-7453-bc28-e86131183912。GREA负责人统一统筹现任monkey/beaver owner，对接项目和总监；保留各源码单写目录/WIP/固定链。当前分发选择为GREA公开薄层和内部模块二进制；覆盖同日完整模块源码选择，旧1.0历史和在途本地观测dev1不重写。

已向僵尸交保留runtime与新debug-only入口；beaver交肥鹅相关合同已接受/新模式不适用。monkey正确Bounce目标签名冷读门通过，已按有界条件裁定，完整根未验。新二进制Mac任务已交两owner，采用稳定monkey0.7/beaver0.6，先做编译、helper边界、真实身份/独立安装与代表链；Windows在Mac实际通过后。私有仓库已回读为PRIVATE、GREA为PUBLIC。先前匿名GREA完整包取源码wheel改造因最新选择停止，未提交/发布；patch仅私有证据保留。


### 2026-11-04 四活动批量恢复立即执行

已原生核验human01a1a639-0d2a-7a41-8d05-38d780e27bd7。按Manager现行批量整改方案，四活动必须实际经GREA公开入口调用monkey，求完整依赖闭包并生成纯输出，先完整布局/组件/图片，再采用和既有业务接线；禁止自由文字行替代和页面特例，不等二进制。项目已交source ID与WIP/桌面窗口，monkey已获成组恢复/机制修复任务；GREA维护通用成组恢复Skill，实际输出与项目验收仍待交。


### 2026-11-04 最新用户优先级：四页真实Prefab/采用先行，binary后置

已原生核验human01a1a65c及human01a1a65d。恢复执行主体必须是monkey程序，Agent只给输入/调用/修通用bug/采用验收，不能逐页推导、作者脚本或报告替代。当前已有public convert partial中间候选，实际Prefab为0；128项DEPENDENCY_MISSING均为ASTC可选依赖未装，GREA已在批次provider私有venv安装并校验1.0.6 ARM wheel，未改monkey源码/核心runtime/全局。下步工具同批重生、阻断静态的共因、公开原生导入，保原失败；不等全脚本/所有警告/二进制。已派monkey/beaver及肥鹅落实新出口；既授僵尸性能窗11:37—11:52尊重并到期释放，随后真实占用可用即原生。二进制WIP/已编译首probe/源码分发方案均保留，在安全点paused_by_user，新增僵尸dev8采用和首关静态补证排四页安全点后。


**2026-11-04 工具实际产物更新。** 固定monkey `0.7.1.dev1`/`0da189a89013`经GREA公开入口重新转换及原生导入，11业务Prefab/668节点已由Unity6000.6.2f1实际生成，进程exit0并退出、无Missing Script、保存重开及可编辑回读通过；不是Agent手工写Prefab。候选自动验收仍partial，311静态字段/引用差异与字体接线交工具共因修复，项目采用和视觉未运行。[实际产物与请求索引](${USER_HOME}/MyProjects/Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-native-03-toggle-index.json)。审核文档提交`56d74d86f99ae1b6c195f20a0e24cacf08c45b61`已在干净开发工作树ff-only整合，未运行打包/发布。仓库整理与版本分支请求排四页关键路径后，不因此清理在途工具源或消费者。
