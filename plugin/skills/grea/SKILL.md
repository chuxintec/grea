---
name: grea
description: GREA 游戏调研、恢复与工程开发的方法入口：按实际工作流阶段（调研→取证→恢复→工程开发→对照修复→构建交付）选择子技能，编排随 GREA 发布的 monkey 与 beaver 模块。适用于已发布游戏分析恢复、已有可维护工程的迭代和明确的客户端或 Go 目标；调研结论不自动批准开发，普通原创开发不强套恢复门槛。
---

# GREA · 游戏调研、恢复与开发

GREA 维护方法、规范和工具选择。**monkey 恢复原游戏为独立工程候选；beaver 操作开发工程；游戏开发者负责业务与可玩结果。** 底层 `grea` 命令与 Skill ID 保持小写兼容。

开始核对用户目标、实际工程、局部约定、引擎版本和已有验收。执行前读[共同约束与执行入口](references/共同约束与执行入口.md)；工具链准备与缺依赖处理见[monkey与beaver调用](references/monkey与beaver调用.md)。纯方案可继续，不把工具存在当执行通过。

## 按工作流阶段选技能

GREA 技能只承载规范与工作流，按实际工作流划分且独立于仓库：阶段专属规范在各自技能的 `references/`，跨阶段共用规范只有一份，在本技能的 `references/`，其他技能直接链接这里。产品安装、接口和工具使用说明属于项目文档 `docs/`，技能只以路径提及、不依赖它。只加载当前阶段的技能和需要的 reference。

| 阶段 | 用户任务 | 技能 | 执行模块 |
| --- | --- | --- | --- |
| 1 调研立项 | 分析游戏、估算成本、选择目标引擎与平台 | `grea-research`：事实、推断与未知分开；不自动立项 | — |
| 2 取证与交接 | 原版运行录制、识别、解包、资产/代码证据、他人研发交接包 | `grea-evidence`：固定版本和来源 | monkey（解包、来源工具） |
| 3 恢复为候选 | Unity 原包恢复为 Unity 工程 | `grea-unity-recovery`：monkey 候选与引用依据 | monkey |
| 3 恢复为候选 | Cocos/Laya/Egret/H5 转原生 Unity | `grea-native-port`：原规则与可观察结果 | monkey |
| 3 恢复为候选 | 明确选择 Cocos Creator 目标 | `grea-cocos`：声明的版本和有限转换能力 | monkey |
| 4 工程开发 | 候选采用、工程治理、资源迁移、性能 | `grea-unity-standard`：保护当前行为和资源身份 | beaver |
| 4 工程开发 | 已有工程加功能、调优、原型 | `grea-evolve`：旧不变量＋批准增量 | beaver |
| 4 工程开发 | 授权换皮 | `grea-reskin`：批准设计，保护指定布局/规则 | beaver |
| 4 工程开发 | 明确批准的自有 Go 服务 | `grea-server-go`：产品业务留项目；不恢复未知原厂服务 | beaver |
| 5 对照修复 | 原版局部差异修复、真实体验对照 | `grea-parity`：受影响原版证据 | beaver（轨迹/事件/表现对照） |
| 6 构建交付 | 结果分层报告、构建、安装、预览、发布支持 | `grea-delivery`：同源制品及本次权限 | beaver |

同一内容只有一个归属：取证方法在 `grea-evidence`，候选采用与三方合并在 `grea-unity-standard`，生命周期与变更合同在 `grea-evolve`；多数阶段都用的测试与结果交付、真实体验对照属于下文共享参考。混合任务按阶段顺序组合；已有工程正常开发无需重导原包，缺来源基线不假装能够三方合并。新恢复的总体交接见[全量初版工程与协作](references/全量初版工程与协作.md)，整体恢复流程见[游戏恢复开发](references/游戏恢复开发.md)。

## 跨阶段流程

收到他人研发交接包时先转 `grea-evidence` 技能的研发交接资料核验；仅采用获准部分，不由接收资料自动批准游戏开发或政策变化。

- 声明有界功能、存档或协议影响时读[生命周期与变更合同](../grea-evolve/references/生命周期与变更合同.md)。
- 判断本次结果时读[测试与结果交付](references/测试与结果交付.md)，代码、原生、真实输入、视觉及产品业务分别报告。
- 记录开发状态或协作范围时读[开发计划与进度管理](references/开发计划与进度管理.md)和[功能模块并行协作](references/功能模块并行协作.md)。是否并行仍服从用户授权。
- 工具维护读[选择与调用](references/工具选择与调用.md)；项目脚本复制增多或想把能力交给 monkey/beaver 时读[项目脚本沉淀与工具晋升](references/项目脚本沉淀与工具晋升.md)；复盘读[开发复盘与规范更新](references/开发复盘与规范更新.md)。术语含义不清时读[术语表](references/术语表.md)；历史经验及失败处理由共同约束按需导航。
- 本地运营数据分析见数据与预览（项目文档 `docs/providers/lifecycle-analysis.md`）：过渡旧入口，不执行生产运营。

## 共享规范

- 跨阶段结果与对照：[测试与结果交付](references/测试与结果交付.md)、[实际体验与画面对照](references/实际体验与画面对照.md)。
- 工具链：[monkey与beaver调用](references/monkey与beaver调用.md)、[工具选择与调用](references/工具选择与调用.md)。
- 产品使用说明（安装、接口、provider 与工具细节）见项目 `docs/README.md`；它是项目概览，不是技能规范的组成部分。

## 模块与执行

monkey 与 beaver 作为 GREA 模块随版本统一发布，固定版本见 `modules.lock.json`，`grea_modules status/install` 查看或隔离安装。原先在 GREA 内的执行工具已移入模块：工具 ID 不变，`run-tool` 自动委托 `monkey tool <id>` 或 `beaver tool <id>`。`grea plan-workflow`/MCP `plan_workflow` 返回阶段、reference 与必选模块声明，不执行任务。`toolchain_check` 显式核验两模块；恢复使用 `monkey_pipeline`，开发阶段调用已绑定 beaver 的真实能力。未支持的工程操作返回 needs_action，不复制一套执行器补位。
