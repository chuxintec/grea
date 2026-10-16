---
name: grea
description: 游戏逆向恢复与原生 Unity 转换的总入口。当用户要把已发布的游戏（Cocos Creator、Laya/FairyGUI、Egret、H5、微信小游戏 wxapkg、APK/XAPK、Unity Mono/IL2CPP 包）依据原版恢复、复刻或移植为纯原生 Unity 工程，但还没有明确具体环节时使用；本技能判断任务模式，并转到 grea-evidence、grea-native-port、grea-unity-recovery、grea-parity、grea-unity-standard、grea-delivery 或 grea-reskin。Use when recovering, remaking or porting a shipped game into a native Unity project. 不用于原创新游戏，也不用于与原版无关的普通 Unity 开发。
---

# grea · 游戏逆向恢复与原生 Unity 转换

grea 插件把"依据已发布游戏，在 Unity 中恢复或重建"拆成若干技能。本技能只负责判断模式并转交。所有技能共同遵守 [共同约束与执行入口](../../shared/01-流程-共同约束与执行入口.md)，先读它。

## 选择模式

先核对实际项目、局部 AGENTS、编辑器版本、当前计划与验收，以及用户本期目标，再按下表选择。混合请求分别列出各部分的门槛。

| 模式 | 比较基线与必要结果 | 使用的技能 |
| --- | --- | --- |
| 只读取证或成本评估 | 声明输入、已证实能力与未知范围；提取/解析不等于服务端或可玩恢复 | `grea-evidence`；本期不启动游戏实现 |
| 完整恢复或首次重建 | 原版同版本、同状态；完整取证和提取库存、工作工程、差异清单。总体顺序见 [恢复开发](../../shared/01-流程-游戏恢复开发.md) | 先用 `grea-evidence`；源游戏是 Unity 时接 `grea-unity-recovery`，是 Cocos/Laya/H5 等其他引擎时接 `grea-native-port` |
| 跨引擎转原生 Unity，或清理源引擎残留 | 原版的规则语义与可观察结果；原生可维护门 | `grea-native-port` |
| 局部一致性修复 | 相关原版依据和受影响入口；只补缺失的证据和回归 | `grea-parity` |
| 结构重构、资源治理、性能优化 | 当前已核验工程的行为与资源身份；性能任务要有固定设备、场景和负载的前后数据 | `grea-unity-standard`；替换 UI 框架时加 `grea-native-port` |
| 构建、预览、发布 | 明确的源码、平台、制品身份和本次交付层级 | `grea-delivery` |
| 授权换皮 | 最新的批准设计，以及指定不变的玩法和交互 | `grea-reskin` |
| 工具、技能维护与复盘 | 文档、工具和调用方契约；不重跑无关的游戏流程 | [工具清单](../../shared/02-工具-选择与调用.md)、[复盘维护](../../shared/10-维护-开发复盘与规范更新.md) |

`grea plan-workflow` 以 intent、source_engine、engine_version/source_format、target_platform 和 acceptance_profile 给出步骤与必验项；`assess`/`evidence` 只做只读评估/取证，unknown 先辨识来源。拿到计划不表示执行，格式支持须核对工具 adapter。

## 验收维度

各模式的结果按 [分层验收](../../shared/08-验收-测试与结果交付.md) 分别报告。涉及跨引擎实现、原生残留整改或其受影响回归时，另记 [原生可维护门](../../shared/08-验收-测试与结果交付.md#原生可维护性跨引擎转换)；术语含义见 [术语表](../../shared/01-流程-术语表.md)。

## 判断源引擎

- 源包是 Unity（有 `globalgamemanagers`、`*.assets`、`il2cpp_data` 或 Mono 程序集）时，目标是找回或重建 Unity 工程，见 `grea-unity-recovery`。
- 源包是 Cocos（有 `cc.` 类型、`project.json`/`settings.js`、bundle 中的 uuid 资源）、Laya、FairyGUI、Egret 或 H5 时，目标是纯原生 Unity 工程，见 `grea-native-port`。这种情况**不在 Unity 中复刻源引擎运行时**。
- Cocos 先核对实际 2.x/3.x 版本与序列化格式，不能用 2.4 reader 猜解 3.x/CCON；其他原生格式单列支持表，不因 APK 或资源扩展名就判为 Unity。
- 判断不了时，先用 `grea-evidence` 解包和盘点，再回到这里选择。
