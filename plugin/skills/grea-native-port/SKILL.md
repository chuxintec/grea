---
name: grea-native-port
description: 把 Cocos Creator、Laya/FairyGUI、Egret、H5 等非 Unity 游戏转换为纯原生 Unity 工程：用一次性转换器生成原生 Prefab、Scene、AnimationClip、ScriptableObject，运行时使用 uGUI/TMP、Animator、DOTween/PrimeTween、Addressables 等官方或主流方案；保留原版的规则语义与可观察结果，不在 Unity 中复刻源引擎运行时。也用于审计和清理已有 Unity 项目中的 Cocos/Laya 残留、源节点身份组件和仿源引擎中间件。Use when porting a Cocos, Laya or H5 game to native Unity, or removing source-engine emulation layers from a Unity project.
---

# GREA · 跨引擎转换为原生 Unity

先读 [共同约束与执行入口](../grea/references/共同约束与执行入口.md)。

**目标形态**：Unity 开发者打开工程即可按常规方式维护。Prefab／Scene／SO管理原生对象与资源引用，正式数值以Player实际解析的JSON为唯一制作源；运行时只用 Unity 机制和官方或主流插件；源引擎只是行为和资源的来源。核心原则是**保留规则语义，不保留引擎语义**。


完整初版导出与接续边界遵循[全量初版工程与协作](../grea/references/全量初版工程与协作.md)。批量转换由固定monkey负责，GREA核交接并编排后续开发；lookup/静态候选不等于原生初版。已有工程的局部修复不无条件重导。

## 读取顺序

1. [原生转换规范](references/Unity原生转换规范.md)：目标形态、语义分界、技术选型基线、一次性转换器、禁止项与守卫、平台 SDK、流程、验收三门。**必读。**
2. 按源引擎读映射手册：[Cocos Creator](references/Unity源引擎映射-Cocos.md)。Laya、FairyGUI、Egret 暂无专门手册，按规范与跨引擎契约逐项建立映射，并列入转换缺口清单。
3. [跨引擎行为契约](references/Unity跨引擎移植与行为一致性.md)：来源身份、几何、动画、渲染与时钟的对照清单。
4. 替换或重建 UI 时读 [UI 框架迁移](references/UnityUI框架迁移.md)。

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

## monkey 调用步骤（跨引擎原生移植）

1. 调用 GREA `session` 核实际 MCP 版本，再 `describe_tool(tool_id="monkey_pipeline")`；技能已刷新不等于 MCP 已刷新。找不到新工具时先完成插件刷新，或显式标记使用已安装新版 CLI，不能报 MCP 已更新。
2. 使用 `run_tool` 调 `monkey_pipeline discover`。`discover` 不执行程序、不联网；`check --output <新目录>` 只探测并保存收据。首次接入执行 `ensure --install-if-missing --output <新目录>`：复用并验证已安装 monkey；完全缺失时从官方 GitHub 最新稳定 Release 下载校验并独立安装，再持久绑定。歧义、坏安装、版本不兼容不自动覆盖/降级。
3. 读取 ensure 的 `ready`、`version`、`command`、`lock`；仅 `ready=true` 才继续。新任务默认使用该绑定，既有计划保持自己的固定 lock。Cocos 使用 source-family=cocos 与完整 input-set、target=unity6；源不是已适配的 Cocos/Unity 时先查支持范围，不用图片 gallery 或猜测参数替代原生初版。
4. 编写请求 JSON（operation/options/input_roots/timeout_seconds），使用 `monkey_pipeline plan --request <请求> --output <新计划目录>`。固定工具和完整来源，不遗漏分包；plan 不执行转换。
5. 审阅计划后使用 `monkey_pipeline run --plan <plan.json> --output <新执行目录>`。两个命令省略 `--config` 时使用已绑定 lock，也可显式传已固定 lock。执行由 monkey 外部 CLI 完成，GREA 不复制转换器；每段使用明确预算，新目录不覆盖原工程。
6. `monkey_pipeline audit --workspace <provider-output> --output <新审计目录>` 核交付文件。再以 `monkey_bridge --workflow handoff --config <lock> ...` 核完整来源去向及真实原生回执；字节/数量通过不代表原生、视觉或玩法通过。未完成项留在证据/任务清单，不写假成功回调。
7. 交接通过后按完整模块接续业务、差分与验收；本期局部修复复用既有工程，不无条件重导。

调用示例（MCP；CLI 共用同一执行层）：

```json
{"tool_id":"monkey_pipeline","arguments":["ensure","--install-if-missing","--output","/absolute/new-readiness"],"run_dir":"/absolute/new-invocation","timeout_seconds":900}
```

安装只写独立用户数据目录，联网只用于官方 Release 及固定 Python 依赖；不自动升级已安装工具、引擎或客户端，不执行下载的安装脚本。接口、预算及原生门详见monkey 接入（项目文档 `docs/providers/monkey.md`）。

## 执行工具与边界

monkey 转换来源为原生候选，beaver 接续工程操作；不在 GREA 维护第二解析器。 完整执行链的必选依赖、固定绑定和过渡例外见[monkey与beaver调用](../grea/references/monkey与beaver调用.md)，仅在准备执行或依赖变化时加载。
