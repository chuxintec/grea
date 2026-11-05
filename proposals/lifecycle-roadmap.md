# GREA 生命周期与当前执行计划

本文件是 GREA 产品唯一计划。当前开发线为 `v1.1.0.dev2`；正式源码与固定运行时按各自身份保留。分支整理、工具实际运行、项目采用与发布分别验收。

```manager-task-view
{
  "schemaVersion": 1,
  "projectId": "grea",
  "updatedAt": "2026-11-05T15:41:55.078331+08:00",
  "authority": "canonical-plan-owner; module unfinished tasks consolidated into this GREA source",
  "currentVersion": "1.1.0.dev2",
  "currentStage": "Unity目标。A线原40逐图整改；monkey主线并行大计划导出，B线推进原范围有源partial，C线追源持久事件。dev33窄项已签。正式采用、扩样待人审。",
  "activeImplementationTask": "grea:T-foodstreet-monkey-visual",
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
      "title": "GREA v1.1.0：肥鹅四页与僵尸全量静态Prefab工具交付",
      "version": "1.1.0",
      "workflowStatus": "in_progress",
      "description": "本版必交两批实际工具恢复与消费者采用，先肥鹅四活动收口，再僵尸全部有源静态Prefab；全部状态只在GREA维护，总监实际验收。未达到两批出口不得标v1.1完成。既有公共能力及二进制任务保留真实状态；binary仍暂停后置。",
      "acceptanceCriteria": [
        "肥鹅四活动完整页及必要子Prefab由monkey程序成组恢复；字体/布局/组件/图片/引用共因修入工具，beaver实际采用，四页同版本画面对照和相关既有绑定通过。",
        "肥鹅收口后，monkey程序核僵尸完整有源分母/嵌套根/依赖，批量产真实Prefab并全量原生静态检查；代表视觉单列，beaver采用，缺源/纯动态缺口明确。",
        "两批均由总监独立验收；IR/报告/文件数量/源测试/保存单项通过不能替代采用与完整验收。",
        "消费者固定交付/采用/结束条件与运行时责任一致",
        "仅适配已交且确有缺口的有限公开合同",
        "相关消费者有限验证通过，未验/无适用性明确",
        "先Mac后Windows独立编译身份/搬迁/代表流程验收",
        "新GREA公开源码及完整包只含已审模块二进制和明确helper白名单，旧历史保持",
        "审计整改固定候选经总监与Claude CLI同字节独立双审并明确放行，才继续两批产品恢复采用。"
      ],
      "sourceRefs": [
        "Manager/decisions/20261104-product-driven-tooling/PLAN.md",
        "../../Manager/decisions/20261104-grea-unified-v110-tasks/PLAN.md"
      ],
      "candidateVersion": "1.1.0.dev2",
      "requiredTaskIds": [
        "grea:T-foodstreet-four-activity-bulk",
        "grea:T-zombie-bulk-static-prefabs",
        "grea:T-monkey-audit-remediation-dual-review",
        "grea:T-foodstreet-monkey-visual",
        "grea:T-foodstreet-monkey-bindings",
        "grea:T-foodstreet-beaver-target-rewrite"
      ]
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
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf"
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
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf"
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
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf"
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
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf"
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
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf"
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
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf"
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
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf"
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
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf"
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
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf"
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
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf"
    },
    {
      "id": "grea:T-player-observation-adapter",
      "title": "接收beaver公开观测合同并做最小适配",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "verification",
      "description": "固定beaver0.7dev1与GREA保管运行时已交；僵尸实际公开normal/STOP/deadline三类结果、全部自有进程关闭及168文件after-check已回读。肥鹅相关QA合同兼容，新debug模式不适用。尚不扩大整版游戏视觉/性能；旧重复脚本退为薄调用按消费者自然安全点收口。",
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
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "implementationModules": [
        {
          "module": "beaver",
          "legacyTaskId": "beaver:T-0.7.0-player-observation",
          "descriptionAtMigration": "先取僵尸46行封装和肥鹅现成QA约定，映射0.6 player.run/debug/qa.prepare-launch-collect。确有缺口才最小扩既有公开入口，使项目仅保留观测配置与业务断言。",
          "verificationAtMigration": null,
          "fixedDeliveryAtMigration": {
            "index": "../../Tools/beaver/.private/product-driven-v0.7.0-20261104/candidate-delivery.json",
            "version": "0.7.0.dev1",
            "producer": "5a4d5599c7e37f373d31290e150d3ac2048b82a91aa7904a2adfe38a7572bb88",
            "wheelSha256": "706f2a5c35c6fd5d4ac5cee6c750932f49037ff1c1142d662b282c20a51cee30",
            "retainedRuntimeIndex": ".private/development/product-driven-20261104/beaver070dev1-handoff-index.json"
          },
          "sourceRefs": [
            {
              "path": "../beaver/.private/product-driven-v0.7.0-20261104/first-batch-index.json",
              "selector": "$"
            }
          ],
          "independentTaskAuthority": "removed; GREA task only",
          "sourceModuleRoot": "../beaver"
        }
      ],
      "nextAction": "复用已交真实采用证据，由GREA统一收口剩余薄封装退役/总监验收，不再复制一份模块待办。"
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
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "blockerIds": []
    },
    {
      "id": "grea:T-binary-provider-macos",
      "title": "GREA二进制模块身份与Mac独立分发验收",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "todo",
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
      "executionStatus": "paused_by_user",
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "implementationModules": [
        {
          "module": "monkey",
          "legacyTaskId": "monkey:binary-macos-standalone",
          "descriptionAtMigration": "用户已批准二进制分发，覆盖同日完整模块源码包选择；专用稳定工作树86d47f，模块子Agent只写隔离环境。Nuitka standalone实际Mach-O、可搬迁验证与嵌套源码审计；只本地候选交GREA。",
          "verificationAtMigration": null,
          "fixedDeliveryAtMigration": null,
          "sourceRefs": [
            ".private/development/binary-distribution-20261104/binary-provider-contract-v1.json"
          ],
          "independentTaskAuthority": "removed; GREA task only",
          "sourceModuleRoot": "../monkey"
        },
        {
          "module": "beaver",
          "legacyTaskId": "beaver:T-mac-binary-distribution",
          "descriptionAtMigration": "按最新用户优先级在无编译/Editor/Player的安全点暂停。适配源码未提交，未生成新二进制；旧Unity DLL缺UNITY_EDITOR只含BuildFilter，不可分发，全部保留待明确恢复。",
          "verificationAtMigration": null,
          "fixedDeliveryAtMigration": null,
          "sourceRefs": [
            {
              "path": "../../Manager/decisions/20261104-grea-binary-distribution/PLAN.md",
              "selector": "MacARM64首包与源码分发边界"
            }
          ],
          "independentTaskAuthority": "removed; GREA task only",
          "sourceModuleRoot": "../beaver"
        }
      ],
      "nextAction": "按用户先两批Prefab工具交付，binary保WIP暂停；不新增编译或打包。技术probe及helper/身份/worker等原缺口保留待明确恢复。",
      "blockerIds": [
        "grea:B-beaver-B-binary-implementation-identity",
        "grea:B-beaver-B-binary-worker",
        "grea:B-beaver-B-binary-toolkit-runpy",
        "grea:B-beaver-B-binary-helper-boundary",
        "grea:B-beaver-B-binary-capabilities-hash"
      ]
    },
    {
      "id": "grea:T-binary-provider-windows",
      "title": "Mac通过后Windows x64原生编译及调用",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "todo",
      "description": "用户最新先四页真实Prefab及采用，binary在安全点暂停新编译/打包/兼容扩展/Windows，保留已有源码/WIP/候选。待Mac组合通过；仅允许无资源占用设计准备，不先并行构建。",
      "acceptanceCriteria": [
        "原生Windows构建/调用/搬迁身份与受影响代表链实际通过",
        "Unity/桌面未验明确单列"
      ],
      "sourceRefs": [
        "Manager/decisions/20261104-grea-binary-distribution/PLAN.md"
      ],
      "executionStatus": "paused_by_user",
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "blockerIds": []
    },
    {
      "id": "grea:T-binary-unified-publication",
      "title": "公开GREA源码与内部模块二进制统一发行",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "todo",
      "description": "用户最新先四页真实Prefab及采用，binary在安全点暂停新编译/打包/兼容扩展/Windows，保留已有源码/WIP/候选。已有用户按序验后发布授权；须先精确双平台候选/CI受控制品与新源码边界通过，不覆盖历史tag或当前固定链。",
      "acceptanceCriteria": [
        "公开树/全部嵌套制品无模块当前实现源码/pyc/生成C源或fallback",
        "私有构建向公开制品传递不泄凭据/源码/日志",
        "版本/完整包/能力锁/许可/下载SHA回读一致"
      ],
      "sourceRefs": [
        "Manager/decisions/20261104-grea-binary-distribution/PLAN.md"
      ],
      "executionStatus": "paused_by_user",
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "blockerIds": []
    },
    {
      "id": "grea:T-foodstreet-four-activity-bulk",
      "title": "肥鹅四活动完整Prefab经GREA成组恢复与采用",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "blocked",
      "description": "dev24/2ac8e5e refresh/export19后native19越过上轮上下文失败，在353b...#20主位图槽0的fallback注册前置拒绝，PID29919退出。失败快照已保留，需核requiresPersistentFallbackRegistration和角色分流。尚未完整原生/静态验收，正式采用未跑。",
      "acceptanceCriteria": [
        "实际GREA公开入口批次请求/纯输出/完整依赖闭包和固定工具身份",
        "三层比较纯输出共因修工具，采用保既有GUID/WIP/存档",
        "四页完整静态布局/组件/图片及同版本UI对照/适配/正常输入通过",
        "接原有业务并退役覆盖性替代作者，不复跑未变已过业务",
        "按全部源组件与真实原生诊断验收；retained-only非静态可见完成，Player未执行不得报通过；审计A1–A4修复并核受影响候选。"
      ],
      "sourceRefs": [
        "Manager/decisions/20261104-foodstreet-activity-bulk-recovery/PLAN.md",
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/FOUR-ACTIVITY-RECOVERY-CONSUMER-INPUTS.json",
        ".private/development/foodstreet-activity-bulk-20261104/coordination/grea-monkey-bulk-04.json",
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/toolchain-entry-index.json",
        ".private/development/foodstreet-activity-bulk-20261104/critical-path-astc-resume.json"
      ],
      "evidence": [
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-native-03-toggle-index.json",
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-native-08-dev12-index.json",
        "../beaver/.private/intake-bindings-20261104/dev9/candidate-delivery.json",
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-native-09-dev13-index.json",
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-native-10-dev14-index.json",
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-verify-11-dev15-index.json",
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-native-12-dev17-index.json",
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-native-13-dev18-index.json",
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-native-14-dev19-index.json",
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-verify-15-dev20-index.json",
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-native-16-dev21-index.json",
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-native-17-dev22-index.json",
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-native-18-dev23-index.json",
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-native-19-dev24-index.json"
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "implementationModules": [
        {
          "module": "monkey",
          "legacyTaskId": "monkey:foodstreet-four-activity-closure",
          "descriptionAtMigration": "由独立模块核最新固定Cocos链路，四根和已证动态源计算完整闭包，经GREA公开请求生成独立Analysis输出；8项不是分母。仅离线，原生由负责人另交资源，不写产品/WIP。",
          "verificationAtMigration": null,
          "fixedDeliveryAtMigration": null,
          "sourceRefs": [
            "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/FOUR-ACTIVITY-RECOVERY-CONSUMER-INPUTS.json"
          ],
          "independentTaskAuthority": "removed; GREA task only",
          "sourceModuleRoot": "../monkey"
        },
        {
          "module": "beaver",
          "legacyTaskId": "beaver:T-foodstreet-four-root-adoption",
          "descriptionAtMigration": "真实native03的11 Prefab SHA全匹配；固定0.6公开adoption.plan实际阻塞CANDIDATE_UNOWNED（ProjectSettings.asset），未执行native/apply。205资产/53序列化脚本图已核，10同路径碰撞、4同码不同GUID辅助类型需支持绑定；源候选仍partial。修正前份合同：spec3/4可exact generated newScripts，schema-only仅spec5。现已整理一次性GREA→monkey保存态/绑定/闭包输入请求；游戏仅产品root单写，binary继续paused_by_user。",
          "verificationAtMigration": null,
          "fixedDeliveryAtMigration": null,
          "sourceRefs": [
            {
              "path": ".private/development/foodstreet-activity-bulk-20261104/critical-path-astc-resume.json",
              "selector": "actual four-root recovery/adoption latest priority"
            }
          ],
          "independentTaskAuthority": "removed; GREA task only",
          "currentAction": "现有采用工具核4同码不同GUID脚本；能运行即交plan，缺机制则扩既有工具，不只交缺口报告。",
          "sourceModuleRoot": "../beaver"
        }
      ],
      "nextAction": "产品视觉交付及正式采用待原40逐图人审及项目绑定验收。独立工具整改并行。肥鹅四页正式交付后再安排僵尸全量。",
      "blockerIds": [
        "grea:B-beaver-B-native03-owned-export",
        "grea:B-beaver-B-native03-runtime-bindings",
        "grea:B-foodstreet-static-reference-materialization",
        "grea:B-monkey-audit-result-contract",
        "grea:B-monkey-dual-review-release-gate"
      ],
      "priority": 1,
      "bindingToolActual": {
        "version": "beaver 0.7.0.dev6",
        "sourceCommit": "be80a8fc62458ad847c67b230dc9fd4f14fb2c7f",
        "singlePrefab": "actual native apply + independent reopen passed; field/reference/object IDs preserved; source/target unchanged",
        "elevenPrefabBatch": "actual apply+independent reopen+owned export passed; 4 bindings,11 Prefabs,60 references; PID68196/68720 exit0 and reaped; fields/references preserved; original source/target unchanged",
        "formalAdoption": "not_run",
        "sourceInputScope": "native03 partial source used only for binding tool verification; final adoption must use fresh complete source",
        "sourceRefs": [
          "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/beaver-native-bindings-four-02-dev6/provider-output/preparation-receipt.json",
          "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/ugui-resolved-identity-dev7.json"
        ],
        "consumerExport": "939 owned files; sourceNative and typedCoverage remain partial; intake apply not_run",
        "consumerPlan": "dev9/17718a0，13交付文件SHA已由GREA核对全等。109源码按编译/序列化依赖分类；47新增脚本生成16/16/15纯脚本批次，无padding纹理，计划独立重验过（非实际采用）。六绑定11Prefab新计划已生成未原生执行。152资源整扫剩2Shader实际原生对象身份待最终候选/当前目标只读检查。",
        "continuationPlan": "../beaver/.private/intake-bindings-20261104/dev9/installed-complete-01/continuation-plan.json"
      },
      "dependsOnTaskIds": [
        "grea:T-monkey-audit-remediation-dual-review"
      ],
      "executionStatus": "awaiting_audit_dual_review_release"
    },
    {
      "id": "grea:T-zombie-first-level-source-gap",
      "title": "首关1001必要升级链有界静态补证",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "todo",
      "executionStatus": "queued_after_foodstreet_safe_point",
      "description": "按僵尸明确请求排在四页自然安全点后；只复用工具补方法体/加载族/Pool2必要配置映射，可证与UNKNOWN分开，不执行原JS/WASM/DLL、不全量重导、不扩大v0.2构筑；尚未派新执行。",
      "sourceRefs": [
        "../../Games/projects/21-zombie-cannon/Analysis/v010-development-20261104/first-level-upgrade/source-gap-index.json"
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "blockerIds": []
    },
    {
      "id": "grea:T-repository-version-branches",
      "title": "立即清理三仓库废弃分支并统一版本命名",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "done",
      "description": "GREA本地/远端仅v1.0.0、v1.1.0.dev2，默认v1.0.0。monkey归并全部Unity/Cocos及0.7有效修复到v0.8.0.dev9/265a123，本地/远端仅单头且相同，默认已切。beaver仅v0.6.0、v0.7.0.dev1，默认v0.6.0；dev本地保留旧历史合并b848，远端7b8453a，源码tree一致，历史未上传。三仓库旧非版本heads均删除，标签/固定制品保持。",
      "sourceRefs": [
        "../../Manager/decisions/20261104-grea-repository-cleanup/PLAN.md",
        ".private/development/repository-cleanup-20261104/branch-migration.json"
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "blockerIds": []
    },
    {
      "id": "grea:T-repository-root-wip",
      "title": "收口旧根120未提交文件并统一当前开发工作区",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "done",
      "description": "根目录120文件已逐项处理：19已跟踪修改和13旧测试由新版覆盖；49消费者历史记录脱敏入Git 1c7e677后退休当前树；36无调用方维护脚本/日志直接删除；其余已在dev。现行计划由159KB收敛25KB并纳入开发线，根目录切到v1.1.0.dev2，git status无未提交文件。无全局安装或运行时修改。",
      "sourceRefs": [
        ".private/development/repository-cleanup-20261104/root-wip-classification.json"
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "blockerIds": []
    },
    {
      "id": "grea:T-zombie-bulk-static-prefabs",
      "title": "monkey统一0.8线僵尸有源Prefab全量静态批处理与采用",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "blocked",
      "executionStatus": "awaiting_audit_dual_review_release",
      "description": "已原生核验human01a1a696-898d-7d42-8b1c-b50f44dea54e。起始161唯一地址根/601缓存来源，10已采用静态子集、151仅解析；原游戏全部包完整性未知，527目标文件不是源分母。由monkey程序核完整有源/嵌套根和依赖后直接批量生成原生Prefab，复用dev8/已验子集，beaver采用；不逐根人工恢复，不把动态代码当全静态前置。肥鹅四页优先、二进制暂停。",
      "sourceRefs": [
        "../../Manager/decisions/20261104-zombie-bulk-prefab-recovery/PLAN.md",
        "../monkey/.private/unity-prefab-v080-20261104/source-prefab-inventory-with-adoption-02.json"
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "implementationModules": [
        {
          "module": "monkey",
          "legacyTaskId": "monkey:battlemain-uv-empty-curve",
          "descriptionAtMigration": "完整BattleMain491节点1380组件59291字段及独立根4节点8组件4297字段原型save/cold通过；身份引用稳定。负向实际native目标12拒绝、捕获签名28拒绝；14次被引擎归一未形成漂移不计拒绝。固定dev8入口验证/消费未闭环。",
          "verificationAtMigration": {
            "result": "partial",
            "scope": "实际双源复制保存/冷读与完整根失败证据；通用修复未过完整根，不可采用"
          },
          "fixedDeliveryAtMigration": null,
          "sourceRefs": [
            "../monkey/docs/PLAN.md#current-consumer-milestone--2026-11-02",
            "../monkey/.private/unity-prefab-v080-20261102/UVRepresentationProbe01/summary.json"
          ],
          "independentTaskAuthority": "removed; GREA task only",
          "sourceModuleRoot": "../monkey"
        }
      ],
      "dependsOnTaskIds": [
        "grea:T-foodstreet-four-activity-bulk",
        "grea:T-monkey-audit-remediation-dual-review"
      ],
      "nextAction": "双审前不推进产品转换/采用；保留既有成果。总监明确放行同一固定身份后先肥鹅四页交付，再僵尸全量。",
      "supersededTaskIds": [
        "grea:T-monkey-dev8-consumer-handoff"
      ],
      "retainedPendingScope": "dev8完整BattleMain491节点1380组件59291字段及独立根4/8/4297原生保存冷读通过，仍须固定身份/采用；归入本批，不计已经全量恢复。",
      "blockerIds": [
        "grea:B-monkey-audit-result-contract",
        "grea:B-monkey-dual-review-release-gate"
      ],
      "priority": 1,
      "acceptanceCriteria": [
        "monkey程序核清全部已取得且可识别源Prefab根、嵌套根及静态依赖，逐项区分缺源/未解析；161仅起始已知根，不以527目标文件充当源分母。",
        "统一0.8公开批处理生成范围内全部真实Unity Prefab及必要依赖，保来源→目标身份、静态组件字段与序列化引用；复用已验子集，不人工逐根拼装。",
        "全批次实际Unity6000.6.2f1导入、保存/重开和静态层级/字段/引用检查；每根生成/原生/静态状态可回读，失败共因修工具后重跑受影响批次。",
        "按组件族及首关实际消费者做代表视觉对照，未覆盖视觉明确，不从少量样本推全量一致；纯动态缺口与静态完整性分开。",
        "beaver实际采用通过的固定候选，保原业务/GUID/JSON/存档/WIP，明确采用结果；缺源和纯动态未恢复如实保留。",
        "在肥鹅四活动实际收口后推进本批，工具产物与消费者采用由总监验收；两批缺任一项不得将GREA v1.1.0标完成。",
        "按全部源组件与真实原生诊断验收；retained-only非静态可见完成，Player未执行不得报通过；审计A1–A4修复并核受影响候选。"
      ]
    },
    {
      "id": "grea:T-monkey-audit-remediation-dual-review",
      "title": "monkey通用审计整改及总监/Claude独立双审",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "verification",
      "priority": 0,
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "description": "dev27/51a5e90双审退修。单Sprite原生/严格冻结正例已复现。错误归属及矛盾启用状态仍可通过，已解决诊断被拒；入口和Creator/Mask契约需修。",
      "acceptanceCriteria": [
        "固定集成候选源码提交、工具版本/摘要、运行入口、A1–A8矩阵与关键差异一致",
        "未mock关键门正反例：缺组件/可见资源/错状态/哈希/引用/字段拒绝，合法imported与明确纯动态静态正例通过",
        "总监独立审查及Claude CLI独立审查同一固定字节，分歧复核完成；总监记录精确放行身份",
        "不伪造原生/视觉/Player结果；不强杀在途、不丢WIP、不恢复Cocos产品/发布或二进制",
        "双向核对源组件、所属Prefab/节点、角色、持久身份与呈现，显式合法共享通过",
        "公开verify和冻结按当前未解决证据统一判定，覆盖已解决、纯动态、图范围与两种冻结入口",
        "Unity 矩形Mask在导出时具可执行契约，原生保存重开核实。共享源身份与归属按Unity正反例验收。"
      ],
      "sourceRefs": [
        "/Users/wangmeng/MyProjects/Manager/decisions/20261105-monkey-audit-remediation/PLAN.md",
        "/Users/wangmeng/MyProjects/Manager/reviews/20261104-monkey-dual-audit/FINAL-AUDIT.json",
        ".private/development/audit-remediation-20261105/dev25-minimal/audit-result.json",
        ".private/development/audit-remediation-20261105/dev26-minimal/audit-result.json",
        ".private/development/audit-remediation-20261105/dev26-jsonutility-probe/receipt.json",
        ".private/development/audit-remediation-20261105/dev27-minimal/review-handoff.json",
        "/Users/wangmeng/MyProjects/Manager/reviews/20261105-monkey-dev27-dual-review/RESULT.md",
        ".private/development/audit-remediation-20261105/dev28-review/RESULT.json",
        ".private/development/audit-remediation-20261105/dev29-review/RESULT.json",
        ".private/development/audit-remediation-20261105/dev29-review/dual-review-input.json",
        "/Users/wangmeng/MyProjects/Manager/decisions/20261105-grea-unity-target-only/DECISION.md",
        "/Users/wangmeng/MyProjects/Manager/reviews/20261105-monkey-dev29-dual-review/RESULT.md",
        ".private/development/audit-remediation-20261105/dev30-review/RESULT.json",
        "/Users/wangmeng/MyProjects/Manager/reviews/20261105-monkey-dev30-dual-review/RESULT.md",
        ".private/development/audit-remediation-20261105/dev31-review/RESULT.json",
        "/Users/wangmeng/MyProjects/Manager/reviews/20261105-monkey-dev31-dual-review/RESULT.md",
        ".private/development/audit-remediation-20261105/dev32-review/RESULT.json",
        ".private/development/audit-remediation-20261105/dev33-review/RESULT.json",
        "/Users/wangmeng/MyProjects/Manager/reviews/20261105-monkey-dev33-dual-review/RESULT.md"
      ],
      "nextAction": "dev33/7fbf2cb 的所测 Mask 多行和冷读阶段判定已由总监裁定通过。相关生产者、消费代码及证据无变化时复用；其他静态诊断及产品门槛按各自任务处理。",
      "authorizationHumanMessage": "01a1a95b-4d69-73e2-abde-24f8b8cf8b42",
      "blockerIds": [],
      "fixedReviewCandidate": {
        "sourceCommit": "51a5e900b70107fa23de3fe808e3869383a93947",
        "packageSha256": "afc8f03d15a2df49e226da88e29217b203c9cdb24619667b0f499cfd0c46e1a8",
        "handoffSha256": "c3c75bb194a129a54d5d38e14075978b8e38195856a0e3592fc1911dcc3b28f7",
        "approval": "hold_after_independent_dual_review"
      }
    },
    {
      "id": "grea:T-foodstreet-full-conversion-diagnostic",
      "title": "肥鹅1.9.1已取得全包转Unity及独立结果审计",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "done",
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "description": "总监已独立验收肥鹅 1.9.1 隔离转换与问题审计，核对全部 1,701 个源根、1,670 个独立 Prefab、3 个 Scene 及 19 份索引制品。26 个未出件入口和静态、引用、脚本缺口归既有通用整改任务。正式采用继续 HOLD。",
      "acceptanceCriteria": [
        "复核原包和同版资源分母与SHA",
        "GREA公开运行monkey，逐根对照真实生成/原生结果及缺口",
        "制品索引、代表原生审计、共因报告交总监"
      ],
      "sourceRefs": [
        "/Users/wangmeng/MyProjects/Manager/decisions/20261105-foodstreet-full-conversion-audit/PLAN.md",
        ".private/development/foodstreet-full-conversion-audit-20261105",
        ".private/development/foodstreet-full-conversion-audit-20261105/delivery-index.json",
        ".private/development/foodstreet-full-conversion-audit-20261105/REPORT.md",
        "/Users/wangmeng/MyProjects/Manager/decisions/20261105-foodstreet-full-conversion-audit/result.json"
      ]
    },
    {
      "id": "grea:T-foodstreet-monkey-visual",
      "title": "肥鹅驱动 monkey 转换修复和分层实图",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "in_progress",
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "description": "foodstreet-monkey-parallel-20261105，从固定 51a5e900b70107fa23de3fe808e3869383a93947 在专属 detached 工作树实现。原主开发单写 dev28 共享入口、门禁和版本。",
      "acceptanceCriteria": [
        "按全量底册对账，按共因修预算、原生失败和四页文字；其他原因逐根保留",
        "首轮至少40个独立源ID，按4/12/12/8/4去重，固定样本与种子，实图逐张目检；保留前后截图、状态、文件身份、回执和剩余差异",
        "同源40行图册含可直接打开的前后图、预期依据、修复身份和逐图判断。缺图、待证、主体不可辨或明显层级/缺字问题均不计通过。"
      ],
      "sourceRefs": [
        "/Users/wangmeng/MyProjects/Manager/decisions/20261105-foodstreet-monkey-parallel/PLAN.md",
        "/Users/wangmeng/.codex/worktrees/monkey-foodstreet-visual/monkey",
        ".private/development/foodstreet-monkey-parallel-20261105",
        "/Users/wangmeng/.codex/worktrees/monkey-foodstreet-visual/monkey/.private/foodstreet-visual-20261105/handoff-index.json",
        "/Users/wangmeng/.codex/worktrees/monkey-foodstreet-visual/monkey/.private/foodstreet-visual-20261105/image-reviews.json",
        "/Users/wangmeng/MyProjects/Manager/decisions/20261105-foodstreet-monkey-parallel/VISUAL-40-REWORK.md",
        ".private/development/foodstreet-monkey-parallel-20261105/visual40-rework/baseline.json",
        ".private/development/foodstreet-monkey-parallel-20261105/visual40-rework/owner-interim-15-17-27.json"
      ],
      "nextAction": "human-visual40-reject-01：人审退回整批视觉，重新核原40项。按源还原主体、相对坐标、父子/遮挡、文字，修正通用转换或取图后以相同状态重拍。GREA逐图核实后交总监，40项全部通过才扩样。",
      "moduleExecutorSessionId": "01a1aa15-8661-7c92-8458-4779e19afc42"
    },
    {
      "id": "grea:T-foodstreet-monkey-bindings",
      "title": "肥鹅驱动 monkey 静态 MonoBehaviour 批量挂载",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "verification",
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "description": "foodstreet-monkey-parallel-20261105，从固定 51a5e900b70107fa23de3fe808e3869383a93947 在专属 detached 工作树实现。原主开发单写 dev28 共享入口、门禁和版本。",
      "acceptanceCriteria": [
        "先验证 MasterMatchMainWindow 和 ScaleBackEffect 多实例，真实编译、GetClass、保存冷重开、字段/引用/节点与错绑反例",
        "扩至四页并按类型族批量挂载，逐项交代 5,681 个源组件的实际去向和原生证据"
      ],
      "sourceRefs": [
        "/Users/wangmeng/MyProjects/Manager/decisions/20261105-foodstreet-monkey-parallel/PLAN.md",
        "/Users/wangmeng/.codex/worktrees/monkey-foodstreet-bindings/monkey",
        ".private/development/foodstreet-monkey-parallel-20261105",
        "/Users/wangmeng/.codex/worktrees/monkey-foodstreet-bindings/monkey/.private/foodstreet-bindings-20261105/two-types-handoff-index.json",
        "/Users/wangmeng/.codex/worktrees/monkey-foodstreet-bindings/monkey/.private/foodstreet-bindings-20261105/label-fix01/bc-handoff-index.json",
        "/Users/wangmeng/.codex/worktrees/monkey-foodstreet-visual/monkey/.private/foodstreet-visual-20261105/label-dependency-handoff-v2.json",
        "/Users/wangmeng/MyProjects/Manager/reviews/20261105-monkey-dev29-dual-review/RESULT.md",
        "/Users/wangmeng/.codex/worktrees/monkey-foodstreet-bindings/monkey/.private/foodstreet-bindings-20261105/final03/handoff-index.json",
        ".private/development/foodstreet-monkey-parallel-20261105/B-final03-check.json",
        "/Users/wangmeng/.codex/worktrees/monkey-foodstreet-bindings/monkey/.private/foodstreet-bindings-20261105/final05/handoff-index.json",
        ".private/development/foodstreet-monkey-parallel-20261105/B-final05-check.json",
        ".private/development/audit-remediation-20261105/dev30-review/RESULT.json",
        "/Users/wangmeng/MyProjects/Manager/reviews/20261105-monkey-dev30-dual-review/RESULT.md",
        "/Users/wangmeng/.codex/worktrees/monkey-foodstreet-bindings/monkey/.private/dev31-phase/handoff.json",
        ".private/development/foodstreet-monkey-parallel-20261105/B-phase-independent.json",
        ".private/development/audit-remediation-20261105/dev32-review/RESULT.json",
        "/Users/wangmeng/MyProjects/Manager/reviews/20261105-monkey-dev33-dual-review/RESULT.md",
        "/Users/wangmeng/MyProjects/Manager/decisions/20261105-foodstreet-monkey-parallel/DEPENDENCIES-AFTER-DEV33.md",
        "/Users/wangmeng/.codex/worktrees/monkey-foodstreet-bindings/monkey/.private/post33-bindings/handoff.json"
      ],
      "nextAction": "四页93实例：1055110通用i18nLabel访问器规则新增22个完整绑定，原51保真，现73完整/20部分；4个错节点值拒绝。增量已交主线集成。剩余18项依赖可验证的Animation/Spine/Sprite目标，2项List需事件构造或序列化依据。历史全库台账另计。",
      "moduleExecutorSessionId": "01a1aa15-8791-7512-92df-1ab33a28d0de"
    },
    {
      "id": "grea:T-foodstreet-beaver-target-rewrite",
      "title": "肥鹅目标工程受限改写及可回退采用工具",
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "workflowStatus": "blocked",
      "primaryReleaseId": "grea:R1.1.0",
      "description": "事件 foodstreet-monkey-parallel-20261105，start-beaver-target-rewrite-02。C线单写 beaver，隔离肥鹅副本。",
      "acceptanceCriteria": [
        "来源草稿和目标依赖驱动受限改写、可审查补丁、编译、拒绝和独立副本回退",
        "同B线两个试点类型，固定载体后核实例/字段/引用/事件及冷重开，项目主开发真实操作一次及预期效果"
      ],
      "sourceRefs": [
        "/Users/wangmeng/MyProjects/Manager/decisions/20261105-foodstreet-monkey-parallel/PLAN.md",
        "/Users/wangmeng/.codex/worktrees/monkey-foodstreet-bindings/monkey/.private/foodstreet-bindings-20261105/two-types-handoff-index.json",
        "/Users/wangmeng/.codex/worktrees/monkey-foodstreet-bindings/monkey/.private/foodstreet-bindings-20261105/label-fix01/bc-handoff-index.json",
        "/Users/wangmeng/MyProjects/Tools/beaver/.private/target-rewrite-20261105/final2/candidate-delivery.json",
        "/Users/wangmeng/MyProjects/Games/projects/20-foodstreet/Analysis/v050-development-20261104/beaver-dev10-visible-click-20261105/run01/owner-visible-click-result.json",
        "/Users/wangmeng/.codex/worktrees/monkey-foodstreet-visual/monkey/.private/foodstreet-visual-20261105/label-dependency-handoff-v2.json",
        "/Users/wangmeng/MyProjects/Tools/beaver/.private/target-rewrite-20261105/review-closure-20261105.json",
        "/Users/wangmeng/MyProjects/Manager/reviews/20261105-monkey-dev29-dual-review/RESULT.md",
        "/Users/wangmeng/MyProjects/Tools/beaver/.private/target-rewrite-20261105/review-provenance-v2-20261105.json",
        "/Users/wangmeng/MyProjects/Manager/decisions/20261105-foodstreet-monkey-parallel/DEPENDENCIES-AFTER-DEV33.md",
        "/Users/wangmeng/MyProjects/Tools/beaver/.private/target-rewrite-20261105/post33-event/onClickTip-source-trace.json"
      ],
      "nextAction": "已核btn_tip→根组件onClickTip，无自定义参数。等待肥鹅主开发交付MasterMatch帮助打开状态、可空act.aid、TipAnim5Window打开与关闭完成接口及隔离资产依赖。GREA已申请，收到后转beaver实施持久事件、冷重开与回退。",
      "moduleExecutorSessionId": "01a19b7a-b50f-7fb0-9c2b-64e71cc9b342"
    },
    {
      "id": "grea:T-monkey-large-plan-export",
      "title": "大型展开计划的有界导出和续接",
      "primaryReleaseId": "grea:R1.1.0",
      "workflowStatus": "in_progress",
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "moduleExecutorSessionId": "01a19b7a-b22a-7ac1-88b0-4c3d3219718b",
      "description": "现任monkey主开发处理196238948字节计划及CLI探读。",
      "sourceRefs": [
        "/Users/wangmeng/MyProjects/Manager/decisions/20261105-foodstreet-monkey-parallel/DEPENDENCIES-AFTER-DEV33.md"
      ],
      "acceptanceCriteria": [
        "用同一固定输入完成有界导出或验证可恢复分片",
        "截断输入拒绝，重试核身份并防重复，提交工具与真实回执"
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
      "workflowStatus": "blocked",
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf"
    },
    {
      "id": "grea:B-monkey-blocker-uv-empty-native-representation",
      "title": "两真实完整根的Bounce与SDK保存表示技术缺口已过原型门",
      "workflowStatus": "done",
      "taskIds": [
        "grea:T-zombie-bulk-static-prefabs"
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "implementationModule": "monkey",
      "legacyBlockerId": "monkey:blocker-uv-empty-native-representation",
      "description": "Native19及独立Native03全静态字段/引用保存/冷读通过；NativeRefusal15共40拒绝，14未形成漂移的尝试单列。固定dev8/消费仍是后续工作，非整版/视觉/业务验收。",
      "releaseCondition": "完整BattleMain与独立真实根保存/冷读及目标全签名/负向变异拒绝通过，固定候选交GREA，再由消费者采用验收。",
      "sourceRefs": [
        "../monkey/.private/unity-prefab-v080-20261104/BattleRendererNative19/execution-result.json",
        "../monkey/.private/unity-prefab-v080-20261104/IndependentProgressEffectNative03/execution-result.json",
        "../monkey/.private/unity-prefab-v080-20261104/ParticleProfileRefusal15/UnityProject/native-refusal-report.json"
      ],
      "sourceModuleRoot": "../monkey"
    },
    {
      "id": "grea:B-beaver-B-binary-implementation-identity",
      "title": "beaver:B-binary-implementation-identity",
      "workflowStatus": "blocked",
      "taskIds": [
        "grea:T-binary-provider-macos"
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "implementationModule": "beaver",
      "legacyBlockerId": "beaver:B-binary-implementation-identity",
      "description": "Binary producer ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356 equals exact beaver.io.encoded({}) empty-file-map SHA256, unlike stable source producer; compiled __file__ scan does not bind code.",
      "releaseCondition": "原证据中的真实技术缺口修复并经受影响实际调用验证；迁移不视作完成。",
      "sourceRefs": [
        "../beaver/.private/binary-distribution-20261104/first-probe-index.json"
      ],
      "sourceModuleRoot": "../beaver"
    },
    {
      "id": "grea:B-beaver-B-binary-worker",
      "title": "beaver:B-binary-worker",
      "workflowStatus": "blocked",
      "taskIds": [
        "grea:T-binary-provider-macos"
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "implementationModule": "beaver",
      "legacyBlockerId": "beaver:B-binary-worker",
      "description": "debug.start exits2 DEBUG_WORKER_FAILED: tries packageRoot/python (absent); source invokes sys.executable -c. No target process started.",
      "releaseCondition": "原证据中的真实技术缺口修复并经受影响实际调用验证；迁移不视作完成。",
      "sourceRefs": [
        "../beaver/.private/binary-distribution-20261104/first-probe-index.json"
      ],
      "sourceModuleRoot": "../beaver"
    },
    {
      "id": "grea:B-beaver-B-binary-toolkit-runpy",
      "title": "beaver:B-binary-toolkit-runpy",
      "workflowStatus": "blocked",
      "taskIds": [
        "grea:T-binary-provider-macos"
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "implementationModule": "beaver",
      "legacyBlockerId": "beaver:B-binary-toolkit-runpy",
      "description": "tool evidence_manifest --help exits2 AttributeError nuitka_module_loader has no get_code; same source command exits0.",
      "releaseCondition": "原证据中的真实技术缺口修复并经受影响实际调用验证；迁移不视作完成。",
      "sourceRefs": [
        "../beaver/.private/binary-distribution-20261104/first-probe-index.json"
      ],
      "sourceModuleRoot": "../beaver"
    },
    {
      "id": "grea:B-beaver-B-binary-helper-boundary",
      "title": "beaver:B-binary-helper-boundary",
      "workflowStatus": "blocked",
      "taskIds": [
        "grea:T-binary-provider-macos"
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "implementationModule": "beaver",
      "legacyBlockerId": "beaver:B-binary-helper-boundary",
      "description": "48 nonPython resources audited. Internal Editor C# and semantic/ObjC runtime compilers require raw helper source today; omitted in probe. Public SDK/user-template suggestions are not approved wholesale. Native operation/build not_run.",
      "releaseCondition": "原证据中的真实技术缺口修复并经受影响实际调用验证；迁移不视作完成。",
      "sourceRefs": [
        "../beaver/.private/binary-distribution-20261104/first-probe-index.json"
      ],
      "sourceModuleRoot": "../beaver"
    },
    {
      "id": "grea:B-beaver-B-binary-capabilities-hash",
      "title": "beaver:B-binary-capabilities-hash",
      "workflowStatus": "blocked",
      "taskIds": [
        "grea:T-binary-provider-macos"
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "implementationModule": "beaver",
      "legacyBlockerId": "beaver:B-binary-capabilities-hash",
      "description": "Two canonical entire capability envelopes differ only in operationId; data equal. Contract v1 currently says canonical JSON without naming stable projection.",
      "releaseCondition": "原证据中的真实技术缺口修复并经受影响实际调用验证；迁移不视作完成。",
      "sourceRefs": [
        "../beaver/.private/binary-distribution-20261104/first-probe-index.json"
      ],
      "sourceModuleRoot": "../beaver"
    },
    {
      "id": "grea:B-beaver-B-native03-owned-export",
      "title": "beaver:B-native03-owned-export",
      "workflowStatus": "blocked",
      "taskIds": [
        "grea:T-foodstreet-four-activity-bulk"
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "implementationModule": "beaver",
      "legacyBlockerId": "beaver:B-native03-owned-export",
      "description": "monkey纯候选应先用其既有freeze生成拥有选择。beaver重绑后的准备副本当前无manifest及原source editor-readback，不能直接交monkey原freeze；准备工具需受支持消费者拥有导出及原始→保存→重绑谱系/更新oracle，不手工造拥有清单。",
      "releaseCondition": "原证据中的真实技术缺口修复并经受影响实际调用验证；迁移不视作完成。",
      "sourceRefs": [],
      "sourceModuleRoot": "../beaver"
    },
    {
      "id": "grea:B-beaver-B-native03-runtime-bindings",
      "title": "beaver:B-native03-runtime-bindings",
      "workflowStatus": "blocked",
      "taskIds": [
        "grea:T-foodstreet-four-activity-bulk"
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "implementationModule": "beaver",
      "legacyBlockerId": "beaver:B-native03-runtime-bindings",
      "description": "已由beaver dev4实现通用脚本GUID重绑定：单Prefab真实apply/独立重开通过；4脚本/11根apply实际60引用通过，报告36.6MB触发读取预算，cold未跑。工具继续修有界批量报告，正式采用未完。",
      "releaseCondition": "原证据中的真实技术缺口修复并经受影响实际调用验证；迁移不视作完成。",
      "sourceRefs": [],
      "sourceModuleRoot": "../beaver"
    },
    {
      "id": "grea:B-foodstreet-static-font-native",
      "title": "统一0.8静态字体实际原生合同冲突",
      "workflowStatus": "done",
      "taskIds": [
        "grea:T-foodstreet-four-activity-bulk"
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "implementationModule": "monkey",
      "description": "dev10已修静态SDF合同前置，实际native06字体阶段与136字形原生资产通过。整体native静态仍被另165字段/引用差异阻塞，不能扩大为四页完成。",
      "releaseCondition": "统一0.8工具重生成并实际Unity字体/字段/引用检查通过，禁止手改纯输出。",
      "sourceRefs": [
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-native-06-dev10-index.json"
      ]
    },
    {
      "id": "grea:B-foodstreet-static-reference-materialization",
      "title": "四活动源静态组件字段与持久引用尚165项差异",
      "workflowStatus": "blocked",
      "taskIds": [
        "grea:T-foodstreet-four-activity-bulk"
      ],
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
      "implementationModule": "monkey",
      "description": "native06实际311→165：39载体/63对象引用/63持久身份；源Animation/Spine等组件族目标表达/映射需核共因。不静默null/替身，不扩全动态业务。",
      "releaseCondition": "通用静态组件/引用修复经本批真实原生回读及严格静态验证通过，缺输入以具体sourceID说明。",
      "sourceRefs": [
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-native-06-dev10-index.json"
      ]
    },
    {
      "id": "grea:B-monkey-audit-result-contract",
      "taskIds": [
        "grea:T-foodstreet-four-activity-bulk",
        "grea:T-zombie-bulk-static-prefabs"
      ],
      "owner": "monkey implementation; GREA acceptance",
      "description": "dev15只读实际验证已修meta/多角色联结，保903分母，retention pass，Player/runtime not_run；53可见Spine的原生呈现证据已被精确接纳。整体仍因17源组件及度量/诊断合同partial而nativeStatic fail；A2实际最终freeze未跑，A3 Creator仅源检查，完整源/视觉门保持。",
      "releaseCondition": "源组件全分母处置与原生诊断贯通；生成/保留/静态呈现/Player独立，未知非pass；freeze接受合法imported同时保完整门；retained-only不关闭可见源缺图。受影响集成反例与真实候选验证通过，仍需视觉验收。",
      "sourceRefs": [
        "/Users/wangmeng/MyProjects/Manager/reviews/20261104-monkey-dual-audit/FINAL-AUDIT.json",
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-native-08-dev12-index.json",
        "../../Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/actual-verify-11-dev15-index.json"
      ],
      "workflowStatus": "blocked",
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf"
    },
    {
      "id": "grea:B-monkey-dual-review-release-gate",
      "taskIds": [
        "grea:T-foodstreet-four-activity-bulk",
        "grea:T-zombie-bulk-static-prefabs"
      ],
      "owner": "GREA统筹；总监+Claude CLI独立复审",
      "description": "dev33所测Mask多行和冷读身份已签；待原40逐图人审、产品绑定和最终采用身份裁定。",
      "releaseCondition": "原40视觉与产品绑定验收通过，总监按精确身份放行正式采用。",
      "sourceRefs": [
        "/Users/wangmeng/MyProjects/Manager/decisions/20261105-monkey-audit-remediation/PLAN.md"
      ],
      "workflowStatus": "blocked",
      "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf"
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
  },
  "ownerSessionId": "01a19b7a-b985-7142-92f4-3207d1b90bcf",
  "currentReleaseId": "grea:R1.1.0",
  "taskMigration": {
    "authorityHumanMessageId": "01a1a69d-7cb3-7093-8ac0-0a8beb3b7203",
    "sourceSnapshots": "../../Manager/decisions/20261104-grea-unified-v110-tasks/sources-before.json",
    "oldToNew": {
      "monkey:foodstreet-four-activity-closure": "grea:T-foodstreet-four-activity-bulk",
      "beaver:T-foodstreet-four-root-adoption": "grea:T-foodstreet-four-activity-bulk",
      "monkey:battlemain-uv-empty-curve": "grea:T-zombie-bulk-static-prefabs",
      "monkey:binary-macos-standalone": "grea:T-binary-provider-macos",
      "beaver:T-mac-binary-distribution": "grea:T-binary-provider-macos",
      "beaver:T-0.7.0-player-observation": "grea:T-player-observation-adapter",
      "grea:T-monkey-dev8-consumer-handoff": "grea:T-zombie-bulk-static-prefabs"
    },
    "moduleActiveTaskRemoval": "verified_removed_in_both_source_files",
    "finalPluginReadback": "verified: default current projects only foodstreet/zombie/grea, all error=null; monkey/beaver explicit history reads have zero unfinished tasks",
    "sourceFiles": {
      "grea": "proposals/lifecycle-roadmap.md",
      "monkey": "../monkey/docs/PLAN.md",
      "beaver": "../beaver/docs/PLAN.md"
    },
    "moduleRemainingUnfinishedTasks": {
      "monkey": 0,
      "beaver": 0
    }
  }
}
```

## 当前约束与实际结果

- monkey 已归并为唯一 `v0.8.0.dev9`，提交 `265a1235dfb8084428810567045307e24bf819bc`；旧 0.7 标签和消费者制品保留，不再迭代 0.7 分支。
- 肥鹅四活动由 monkey 程序成组转换；已实际保存 11 个业务 Prefab、668 节点，无 Missing Script。字体与静态引用仍在工具修复，采用和视觉未验，不以报告或人工改 Prefab 替代。
- 二进制编译/打包仍由用户暂停；本次源码与分支整改不恢复该线，不新增 Release 或安装。
- 旧固定消费者、源码提交、锁、输入和运行时保留；路径型 sourceRefs 以仓库根为基准，私有执行证据不纳入公开源码。

## 历史与本轮整理

旧计划的逐次过程和 49 份继承验收记录已从当前源码树退休，保存在 [继承记录提交](https://github.com/chuxintec/grea/commit/1c7e6778c278812cf7cef2651090c65e122e696a) 中。公开历史副本已去除本机用户目录，各 JSON 记录原件 SHA256 和字节数，不能将脱敏副本的字节身份冒充原件。现行能力、合同、回归与失败边界继续保留；36 份无调用方的一次性维护脚本/日志直接删除，不建立新的 archive 或备份目录。


统一任务管理：monkey、beaver保留内部实现、源码版本和已完成技术历史；六个未完任务归并到上方GREA任务，移除模块活动条目及重复两根采用待办，旧新ID见taskMigration。v1.1.0必须先交肥鹅四页、再交僵尸有源Prefab全量恢复与采用，并经总监验收。
