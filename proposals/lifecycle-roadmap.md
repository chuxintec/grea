> 发布脱敏摘要：本文含原始回执的公开摘要；脱敏前原件仅保存在私有冻结目录。

# GREA 全生命周期版本路线与开发进度

2026-10-26｜状态：固定beaver0.3候选07及0.3.0运行实现（08/09/final等价包）的有限GREA适配通过；已只读核验正式08中文路径原生收敛采用回执，旧0.1/0.2/07链保留。0.3整版G由beaver主开发汇总；项目App默认渲染和正向购买L3仍是独立边界。安装和发布分别保留范围。**本文件为本轮唯一产品进度入口。** 历史研究/Cocos/Go成果见docs/design/research-cocos-go.md，保留原状态，不重做或补造通过。

## 2026-10-29 monkey v0.7 Prefab版本协调（目标已记录，能力待交付）

已核验本轮用户将Prefab完整恢复作为monkey v0.7.0目标：优先于旧source-family扩张，以至少10个不同核心Prefab完成Creator/Unity双端分层验收。当前13项文件仅为定位线索，源UUID/RF/代码/资源闭包仍待monkey冻结；不能把修补版当真值或用重复窗口/多个状态凑数。Creator3.8.8与Unity6000.6.2f1以实际环境核定，仅工具隔离验证，不恢复暂停的Cocos产品，不改变现行游戏版本出口。

GREA已在原恢复参考补源组件分母、源→IR/IR→目标独立检查、原包/旧纯候选/新纯候选/人工修补四组对照及树/资源/脚本/动态/视觉/再生矩阵。关键显示或本地行为受服务缺口影响仍记partial；至少10项双端适用项未通过时versionComplete=false。门槛属于本次monkey版本，不变成所有游戏通用固定数量。

GREA方法验证：157份文档714条引用、隔离5技能70篇361条内部链接及4项阶段路由检查通过；契约生成无漂移，现行monkey版本支持未改。见[Prefab版本口径验证](../validation/development/monkey-prefab-version-contract-20261029.json)。

monkey维护唯一恢复实现与版本进度；GREA等待真实0.7开发包身份、CLI/Schema、分母账本和回执再有限接入，当前SUPPORTED_VERSIONS/正式锁/全局插件未改。beaver已验原生工具按实际能力选用。规范已记录不代表Prefab能力或样本验收完成；游戏工程与当前P0成果保留。

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
