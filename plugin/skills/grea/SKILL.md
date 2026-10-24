---
name: grea
description: 游戏调研、恢复与目标工程开发的总入口。当用户分析或恢复已发布的游戏（Cocos Creator、Laya/FairyGUI、Egret、H5、微信小游戏 wxapkg、APK/XAPK、Unity Mono/IL2CPP 包）依据原版分析、恢复、复刻或选择 Unity/Cocos 客户端及Go后端，但还没有明确具体环节时使用；本技能判断任务模式，并转到 grea-evidence、grea-native-port、grea-unity-recovery、grea-parity、grea-unity-standard、grea-delivery 、grea-reskin 、grea-evolve、grea-research、grea-cocos 或 grea-server-go。Use for game research and explicit Unity/Cocos client or Go backend targets. 研究建议不自动批准开发，普通引擎修复不强套恢复流程。
---

# grea · 游戏调研、恢复与目标选择

grea 插件把游戏调研、恢复与显式目标工程开发拆成若干技能。源引擎、目标引擎与后端分别选择；用户指定目标时尊重选择。本技能只负责判断模式并转交；生命周期兼容、事件/经济只读分析及配置候选按文末有限工具入口，不意味着已支持生产运营。所有技能共同遵守 [共同约束与执行入口](../../shared/01-流程-共同约束与执行入口.md)，先读它。

## 选择模式

先核对实际项目、局部 AGENTS、编辑器版本、当前计划与验收，以及用户本期目标，再按下表选择。混合请求分别列出各部分的门槛。

| 模式 | 比较基线与必要结果 | 使用的技能 |
| --- | --- | --- |
| 已恢复工程的feature/tuning/prototype | v2合同＋旧不变量/批准增量＋配置/save/协议影响；可玩结果另验 | `grea-evolve` |
| 本地运营数据/配置候选 | 明确授权输入、口径/窗口及版本；只读分析，不自动生产写入 | 读取[数据与预览](../../../docs/providers/lifecycle-analysis.md) |
| 游戏调研/多游戏比较 | 品类/循环/差异、成本与发行判断，事实/推断/经验/未知分开；推荐不是开发批准 | `grea-research` |
| Cocos目标工程 | 明确Creator目标版本、五层模板、有限转换子集与浏览器运行 | `grea-cocos` |
| 自有Go后端 | 六服、gRPC/MySQL/Redis、持久幂等与双客户端合同 | `grea-server-go` |
| 只读取证或成本评估 | 声明输入、已证实能力与未知范围；提取/解析不等于服务端或可玩恢复 | `grea-evidence`；本期不启动游戏实现 |
| 完整恢复或首次重建 | 原版同版本、同状态；完整取证和提取库存、工作工程、差异清单。总体顺序见 [恢复开发](../../shared/01-流程-游戏恢复开发.md) | 先用 `grea-evidence`；源游戏是 Unity 时接 `grea-unity-recovery`，目标明确为Unity且源为其他引擎时接 `grea-native-port`；目标Cocos转 `grea-cocos` |
| 跨引擎转原生 Unity，或清理源引擎残留 | 原版的规则语义与可观察结果；原生可维护门 | `grea-native-port` |
| 局部一致性修复 | 相关原版依据和受影响入口；只补缺失的证据和回归 | `grea-parity` |
| 结构重构、资源治理、性能优化 | 当前已核验工程的行为与资源身份；性能任务要有固定设备、场景和负载的前后数据 | `grea-unity-standard`；替换 UI 框架时加 `grea-native-port` |
| 构建、预览、发布 | 明确的源码、平台、制品身份和本次交付层级 | `grea-delivery` |
| 授权换皮 | 美术选样/成套生产/样板完整替换，风格获批后全量换皮与修Bug；最后才做另行约定的UI/UE调优；保持原布局、操作和规则 | `grea-reskin` |
| 已恢复工程的有限二次开发 | 冻结旧基线玩法/存档不变量，允许的UI/UE维度按新设计；显式UI/UE或v2 feature/tuning/prototype合同 | `grea-evolve` |
| 工具、技能维护与复盘 | 文档、工具和调用方契约；不重跑无关的游戏流程 | [工具清单](../../shared/02-工具-选择与调用.md)、[复盘维护](../../shared/10-维护-开发复盘与规范更新.md) |

`grea plan-workflow` 新增 target_engine（unity/cocos/none，省略仍unity）与backend（none/go），不把非Unity来源一律送Unity；研究不自动进入实现。其余以 intent、source_engine、engine_version/source_format、target_platform 和 acceptance_profile 给出步骤与必验项；`assess`/`evidence` 只做只读评估/取证，unknown 先辨识来源。拿到计划不表示执行，格式支持须核对工具 adapter。

## 全量初版与开发分工

完整恢复／首次重建先读[全量初版工程与协作](../../shared/01-流程-全量初版工程与协作.md)：GREA冻结来源→monkey批量导出独立初版→GREA核真实交接→游戏Agent接续业务。当前all-scope适配not_available，不能把lookup、素材池或completed当完整工程；不等待全玩法才交初版。

## 验收维度

各模式的结果按 [分层验收](../../shared/08-验收-测试与结果交付.md) 分别报告。涉及跨引擎实现、原生残留整改或其受影响回归时，另记 [原生可维护门](../../shared/08-验收-测试与结果交付.md#原生可维护性跨引擎转换)；术语含义见 [术语表](../../shared/01-流程-术语表.md)。

## 判断源引擎

- 源包是 Unity（有 `globalgamemanagers`、`*.assets`、`il2cpp_data` 或 Mono 程序集）时，目标是找回或重建 Unity 工程，见 `grea-unity-recovery`。
- 源包是 Cocos（有 `cc.` 类型、`project.json`/`settings.js`、bundle 中的 uuid 资源）、Laya、FairyGUI、Egret 或 H5 时，目标是纯原生 Unity 工程，见 `grea-native-port`。目标为Unity时**不在 Unity 中复刻源引擎运行时**；目标Cocos见 `grea-cocos`。
- Cocos 先核对实际 2.x/3.x 版本与序列化格式，不能用 2.4 reader 猜解 3.x/CCON；其他原生格式单列支持表，不因 APK 或资源扩展名就判为 Unity。
- 判断不了源引擎时，先用 `grea-evidence` 解包和盘点，再回到这里选择。

生命周期阶段/模式及有界feature/tuning/prototype合同见[生命周期与变更](../../shared/01-流程-生命周期与变更合同.md)。monkey仅负责声明支持的转换候选，全量初版核验后才接续业务；不自动启动Agent或执行源代码；运营当前只规划，不声称已有生产工具。
