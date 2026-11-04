# GREA 生命周期与当前执行计划

本文件是 GREA 产品唯一计划。当前开发线为 `v1.1.0.dev2`；正式源码与固定运行时按各自身份保留。分支整理、工具实际运行、项目采用与发布分别验收。

```manager-task-view
{
  "schemaVersion": 1,
  "projectId": "grea",
  "updatedAt": "2026-11-04T12:44:27.632395+00:00",
  "authority": "original-plan-owner; read-only projection, not canonical cutover",
  "currentVersion": "1.1.0.dev2",
  "currentStage": "立即处理GREA旧根120未提交文件：有效代码/契约/测试由当前开发线覆盖；49历史验收记录已脱敏入Git，36一次性清理文件退休；统一根目录到v1.1.0.dev2并收干净。monkey归并唯一v0.8.0线仍执行，四页原生产物保留、二进制暂停。",
  "activeImplementationTask": "grea:T-repository-root-wip",
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
        "../../Games/projects/21-zombie-cannon/Analysis/v010-development-20261104/build-runtime-repair-grea-01/delivery-index.json"
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
        ".private/development/product-driven-20261104/first-batch-index.json"
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
        ".private/development/product-driven-20261104/first-batch-index.json"
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
        ".private/development/product-driven-20261104/first-batch-index.json",
        ".private/development/product-driven-20261104/beaver070dev1-handoff-index.json",
        "../../Tools/beaver/.private/product-driven-v0.7.0-20261104/lead-handoff.json",
        ".private/development/product-driven-20261104/beaver070dev1-consumer-adoption-supplement.json"
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
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/FOUR-ACTIVITY-RECOVERY-CONSUMER-INPUTS.json",
        ".private/development/foodstreet-activity-bulk-20261104/coordination/grea-monkey-bulk-04.json",
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/toolchain-entry-index.json",
        ".private/development/foodstreet-activity-bulk-20261104/critical-path-astc-resume.json"
      ],
      "evidence": [
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-native-03-toggle-index.json"
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
        "../../Tools/monkey/.private/unity-prefab-v080-20261104/dev8-fixed-two-root-handoff-index.json"
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
        "../../Games/projects/21-zombie-cannon/Analysis/v010-development-20261104/first-level-upgrade/source-gap-index.json"
      ]
    },
    {
      "id": "grea:T-repository-version-branches",
      "title": "立即清理三仓库废弃分支并统一版本命名",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "in_progress",
      "description": "GREA已完成本地21→2/远端9→2，默认v1.0.0，53ff3bc已推；标签/5工作树WIP未变。monkey首轮18→3已独立回读，后被本聊天最新人类指令覆盖：必须合并为唯一v0.8.0系列，先归并0.7修复再删除0.7系列heads，owner执行中。beaver仍在执行，不能报三仓库完成。",
      "sourceRefs": [
        "../../Manager/decisions/20261104-grea-repository-cleanup/PLAN.md",
        ".private/development/repository-cleanup-20261104/branch-migration.json"
      ]
    },
    {
      "id": "grea:T-repository-root-wip",
      "title": "收口旧根120未提交文件并统一当前开发工作区",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "in_progress",
      "description": "核对120文件：代码/契约/测试由现行版本覆盖，无需把旧实现覆盖新版；现行计划归入本开发线，49份历史消费者记录脱敏后保存在Git历史，36份过期维护脚本/日志直接退休。最后根目录切换v1.1.0.dev2，核工作区干净；不改固定运行时与已发布标签。",
      "sourceRefs": [
        ".private/development/repository-cleanup-20261104/root-wip-classification.json"
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
    "standard": "../../Manager/standards/VERSIONING.md",
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

## 当前约束与实际结果

- monkey 按用户最新指令归并为唯一 `v0.8.0` 系列；旧 0.7 标签和消费者制品保留，不再迭代 0.7 分支。
- 肥鹅四活动由 monkey 程序成组转换；已实际保存 11 个业务 Prefab、668 节点，无 Missing Script。字体与静态引用仍在工具修复，采用和视觉未验，不以报告或人工改 Prefab 替代。
- 二进制编译/打包仍由用户暂停；本次源码与分支整改不恢复该线，不新增 Release 或安装。
- 旧固定消费者、源码提交、锁、输入和运行时保留；路径型 sourceRefs 以仓库根为基准，私有执行证据不纳入公开源码。

## 历史与本轮整理

旧计划的逐次过程和 49 份继承验收记录已从当前源码树退休，保存在 [继承记录提交](https://github.com/chuxintec/grea/commit/1c7e6778c278812cf7cef2651090c65e122e696a) 中。公开历史副本已去除本机用户目录，各 JSON 记录原件 SHA256 和字节数，不能将脱敏副本的字节身份冒充原件。现行能力、合同、回归与失败边界继续保留；36 份无调用方的一次性维护脚本/日志直接删除，不建立新的 archive 或备份目录。
