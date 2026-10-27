# Unity指南

用途：选择 GREA 已有的 Unity 检查、生成、框架与隔离恢复能力。不自动改动已有游戏；目录/生命周期/制作约束以 [Unity标准技能](../SKILL.md)为准。

## 项目检查与只读规划

先读取真实 Editor 版本、局部约定和验收记录。`validate-unity-project` 检查项目配置，`plan-unity-project` 输出只读计划与所有权；配置 Schema（GREA 安装根目录资源 `schemas/unity-project.schema.json`；实际参数先用 `describe-tool`/工具 `--help` 核对）是实际契约，不能把提案 profile 当支持选项。

使用 `describe-tool` 核对正式 ID/旧别名。存在工具、连接到 Editor、导入成功、运行和 Player 实测分别报告；Windows Unity 未经本机原生证据不能借用 Mac 结果。

## 生成、恢复与隔离

使用 `generate-unity-project` 消费已确认计划，输出必须全新；生成器拥有的文件与 seed-once 人工文件分开。修改内容、schema 或实现后 planId/recipeId 可失效，应重新规划。`recover-unity-generation` 从明确锁与输入恢复，不依赖旧 Library 或私有绝对路径。

先对不存在的隔离副本操作，保存源文件指纹；构建也使用新的工作副本，避免 URP/Editor 缓存回写源 Assets。失败保留 staging 与回执，不覆盖既有目录。

## 框架与消费者

三个 UPM 包（GREA 安装根目录资源 `tools/unity/framework/packages`；实际参数先用 `describe-tool`/工具 `--help` 核对）分别承担 Foundation、uGUI 与 Editor。五层 Domain/Gameplay/Presentation/Services/Bootstrap 是业务职责，不是五个通用库；公共包不引用项目业务。

自有可执行示例在 GREA 安装根目录 `tools/unity/templates/framework-samples/`：数值战斗检验待领奖/重复领取，网格益智检验取消/失败保存，两者分别核重开与布局；Counter 装配示例保留在 `tools/unity/templates/counter-composition/`。这些是可选资产样例，实际项目仍按本次批准入口验收，不据历史样例声称复杂背包、Buff或商业广告已实现。

```sh
python scripts/testing/prepare-unity-framework.py --help
python scripts/testing/build-framework-sample.py --help
```

## 有限原生制作与退出检查

显式 Sprite/Clip 配方、配置 schema/codec、Editor 观察与实际 DLL 元数据分别见 [制作契约](Unity配置与资源制作工具.md)、[原生退出检查](../../grea-recover/references/Unity原生退出检查工具.md)。生成 C# 或 Prefab 不等于无源引擎残留；源类型名合法出现与实际运行依赖要区分。

正式数值表遵循[DAT-01](Unity程序集分层与生命周期.md#生命周期与数据契约)；本工具页只说明 GREA 能力。第三方候选工具对 SO-authoring 的支持不构成正式配置规范或已验证的运行时路径；详见[有限制作链](Unity配置与资源制作工具.md#强类型配置)。

## 验收边界

先通过原生导入/编译，保存并关闭重开，再验 Play、目标 Player、输入、存档与分发恢复。旧 Mac/Mono 证据不覆盖 Windows/IL2CPP；原生接口事件、OS 键盘、真实鼠标也不是同一层。报告同时保留 not_run 与失败，不用构建成功替代还原完成。
