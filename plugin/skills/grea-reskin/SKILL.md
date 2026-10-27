---
name: grea-reskin
description: 已有恢复工程的授权换皮：按当前授权制作或采用设计，复用或制作素材，切图与序列帧接入 Unity，保持指定的玩法和交互不变，并做 alpha、边缘和按钮状态检查。Use when reskinning a recovered Unity game with scoped new art. 不用于原版一致性恢复。
---

# GREA · 授权换皮

先读 [共同约束与执行入口](../grea/references/共同约束与执行入口.md)，再读 [换皮与资源制作](references/游戏换皮与资源制作.md)。

- 比较基线是最新的批准设计，以及指定不变的玩法和交互；换皮美术通过不等于原版美术一致。
- 已批准的素材直接复用；只在本期确实需要设计确认时才进入审批环节，不重复审批已有版本。
- 跨引擎转换的工程换皮后，按 [原生可维护门](../grea/references/测试与结果交付.md#原生可维护性跨引擎转换) 复核：新素材通过原生 Sprite、图集和 Prefab 接入，守卫不新增违规。
- 界面接入与输入检查见 [界面还原与输入交互](../grea-parity/references/Unity界面还原与输入交互.md)；结果按 [分层验收](../grea/references/测试与结果交付.md) 记录。

- 换皮以美术为先：真实界面/角色/怪物选样定风格 → UI/ICON切片及原画/Spine成套生产 → 样板范围100%原功能替换 → 用户确认风格后全量换皮与Bug修复 → 最后才按约定做UI/UE游戏调优。约30%如有约定不是美术覆盖率，S1–S4保持原布局、入口和操作。
- 从选样起持续更新同一份资源台账及界面/角色/怪物/特效/关卡设定；可玩Player、静态PNG和改色不能冒充完整美术或Spine。已授权样板直接做候选，不逐页追加审批。后置调优见 有限二次开发（`grea-evolve` 技能）。
- 资源替换使用 [theme_assets 合同](../grea/references/providers/theme-assets.md)，先预览与校验，再在授权隔离工程通过Editor应用/回退。骨骼、事件及多Sprite不在首版自动替换范围。

## 执行工具与边界

beaver 执行资源处理、接入与检查；素材设计按批准范围，恢复阶段复用已核 monkey 基线。 完整执行链的必选依赖、固定绑定和过渡例外见[monkey与beaver调用](../grea/references/monkey与beaver调用.md)，仅在准备执行或依赖变化时加载。
