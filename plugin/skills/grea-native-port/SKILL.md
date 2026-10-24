---
name: grea-native-port
description: 把 Cocos Creator、Laya/FairyGUI、Egret、H5 等非 Unity 游戏转换为纯原生 Unity 工程：用一次性转换器生成原生 Prefab、Scene、AnimationClip、ScriptableObject，运行时使用 uGUI/TMP、Animator、DOTween/PrimeTween、Addressables 等官方或主流方案；保留原版的规则语义与可观察结果，不在 Unity 中复刻源引擎运行时。也用于审计和清理已有 Unity 项目中的 Cocos/Laya 残留、源节点身份组件和仿源引擎中间件。Use when porting a Cocos, Laya or H5 game to native Unity, or removing source-engine emulation layers from a Unity project.
---

# grea-native-port · 跨引擎转换为原生 Unity

先读 [共同约束与执行入口](../../shared/01-流程-共同约束与执行入口.md)。

**目标形态**：Unity 开发者打开工程即可按常规方式维护。Prefab／Scene／SO管理原生对象与资源引用，正式数值以Player实际解析的JSON为唯一制作源；运行时只用 Unity 机制和官方或主流插件；源引擎只是行为和资源的来源。核心原则是**保留规则语义，不保留引擎语义**。


完整初版导出与接续边界遵循[全量初版工程与协作](../../shared/01-流程-全量初版工程与协作.md)。批量转换由固定monkey负责，GREA核交接并编排后续开发；lookup/静态候选不等于原生初版。已有工程的局部修复不无条件重导。

## 读取顺序

1. [原生转换规范](references/05-Unity-原生转换规范.md)：目标形态、语义分界、技术选型基线、一次性转换器、禁止项与守卫、平台 SDK、流程、验收三门。**必读。**
2. 按源引擎读映射手册：[Cocos Creator](references/05-Unity-源引擎映射-Cocos.md)。Laya、FairyGUI、Egret 暂无专门手册，按规范与跨引擎契约逐项建立映射，并列入转换缺口清单。
3. [跨引擎行为契约](references/05-Unity-跨引擎移植与行为一致性.md)：来源身份、几何、动画、渲染与时钟的对照清单。
4. 替换或重建 UI 时读 [UI 框架迁移](references/05-Unity-UI框架迁移.md)。

## 配合其他技能

| 需要 | 技能或参考 |
| --- | --- |
| 解包、提取、录制原版 | `grea-evidence` |
| 规则 oracle、数值与随机对照，动画和界面差异修复 | `grea-parity` |
| 目录、程序集分层、资源命名与迁移 | `grea-unity-standard` |
| 构建与交付 | `grea-delivery` |
| 具体 Unity 操作（uGUI 层级、SpriteAtlas、包管理等） | Unity 官方插件技能，如 ui-ugui、manage-sprite-atlas、unity-package-management |

## 已有项目去残留

1. 统计残留：源类型字符串、uuid、源节点身份组件、仿源引擎的调度、补间、布局、文本度量代码，以及双层 UI 真源。
2. 加禁止项守卫，存量违规列入只减不增的白名单。
3. 先做一个代表切片，再按模块替换为原生实现，每个模块都要过验收三门。

## 完成条件

三道门分别报告：守卫、原版对照、原生可维护。构建成功、测试数量或已去掉 JS 解释器，都不能代替"原生可维护"这一门。
