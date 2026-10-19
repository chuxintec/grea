---
name: grea-unity-standard
description: 恢复或转换工程的 Unity 工程标准与治理：目录与 asmdef 分层、生命周期与数据契约、通用组件与 Prefab、生成所有权、资源命名与迁移、旧框架退役，以及固定基线的性能分析与优化。用于结构重构、资产治理和性能任务。Use when restructuring, cleaning up assets, or profiling a recovered or ported Unity project. 普通修复不顺带迁移结构。
---

# grea-unity-standard · 工程标准、治理与性能

先读 [共同约束与执行入口](../../shared/01-流程-共同约束与执行入口.md)。

| 任务 | 参考 |
| --- | --- |
| 标准总览、版本、例外与分篇索引（先读） | [工程结构与开发规范](references/05-Unity-工程结构与开发规范.md)（标准 v1）；落地记录见 [实施记录](https://github.com/chuxintec/grea/blob/3d1a2be71292696ecc910523f33e949c160e3927/docs/history/Unity标准实施记录.md) |
| 目录树、资产类型归类、动态加载路径 | [工程目录与资产归类](references/05-Unity-工程目录与资产归类.md) |
| asmdef 分层、启动场景、生命周期、存档与事件 | [程序集分层与生命周期](references/05-Unity-程序集分层与生命周期.md) |
| 通用组件、自研框架与主流插件的取舍、基础 Prefab | [通用组件与 Prefab](references/05-Unity-通用组件与Prefab.md) |
| 脚本所有权、工程生成与重复生成 | [脚本与生成契约](references/05-Unity-脚本与生成契约.md) |
| 标准符合性验收（A0–A5） | [工程标准验收](references/05-Unity-工程标准验收.md) |
| 资产治理、命名、移动与旧框架退役 | [重构与资源迁移](references/05-Unity-重构与资源迁移.md) |
| 性能问题与优化验证 | [性能分析与优化验证](references/05-Unity-性能分析与优化验证.md)；普通修复不自动跑多轮基准 |

跨引擎项目的技术选型和禁止项以 [原生转换规范](../grea-native-port/references/05-Unity-原生转换规范.md) 为准；工程标准中的通用组件不与其选型基线并存为第二套同类机制。

验收时，标准符合性按 [工程标准验收](references/05-Unity-工程标准验收.md) 的 A0–A5 记录；跨引擎项目另记 [原生可维护门](../../shared/08-验收-测试与结果交付.md#原生可维护性跨引擎转换)，重构和资源迁移后守卫不新增违规。

规范设计与可调用的实现分开核对。只制定计划时，不创建工程，也不执行迁移。

已恢复工程的有界UI/UE开发见 [grea-evolve](../grea-evolve/SKILL.md)；主题替换持续使用同一资源/设定台账，保护GUID/local fileID与制作所有权；新Spine记录实际版本、骨架/附件/动画事件及atlas/纹理导出和目标引用，骨骼/事件不靠图片清单证明不变。
