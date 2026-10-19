---
name: grea-parity
description: 对照原版修复已恢复或已转换的 Unity 工程中的差异：玩法规则、数值与随机序列、事务与几何判定、动画特效与事件时序、界面布局、字体、遮罩和输入交互。用于局部一致性修复、差分验证与回归，不重建整个工程。Use when a recovered or ported Unity game behaves or looks different from the original and needs a targeted parity fix.
---

# grea-parity · 原版一致性修复与对照

先读 [共同约束与执行入口](../../shared/01-流程-共同约束与执行入口.md)。按缺口只读相关专题：

| 当前缺口 | 参考 |
| --- | --- |
| 调查与集成节奏、代表流程、固定对照条件 | [开发前检查与迭代](references/01-流程-开发前检查与迭代.md) |
| 规则、数值、随机、事务、几何互锁 | [规则与随机一致性](references/06-玩法-规则与随机一致性.md) |
| 动画、Shader 组合、命中与结算时序 | [动画特效与事件时序](references/05-Unity-动画特效与事件时序.md) |
| 界面布局、字体、输入、画面缺失 | [界面还原与输入交互](references/05-Unity-界面还原与输入交互.md) |
| 源引擎语义对照（跨引擎项目） | [跨引擎行为契约](../grea-native-port/references/05-Unity-跨引擎移植与行为一致性.md) |

跨引擎项目修复时同样遵守 [原生转换规范](../grea-native-port/references/05-Unity-原生转换规范.md)：用 Unity 原生实现得到原版的结果，不靠补一段源引擎语义模拟来修复差异。

结果按 [分层验收](../../shared/08-验收-测试与结果交付.md) 记录：规则、真实输入、视觉/音频分别报告，局部修复只复测受影响的入口。跨引擎项目另记 [原生可维护门](../../shared/08-验收-测试与结果交付.md#原生可维护性跨引擎转换)：修复后守卫不新增违规，修改过的 Prefab 和 SO 仍然在 Inspector 修改后直接 Play 生效。

二次开发明确允许的UI/UE维度改用批准新设计，原基线规则仍保持；不要把有意改动当原版回归缺陷。范围见 [grea-evolve](../grea-evolve/SKILL.md)。
