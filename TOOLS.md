# GREA 工具目录

> 三产品过渡：GREA 维护方法与薄入口；恢复用 monkey，工程开发用 beaver。`toolchain_check` 检查两项必选依赖；`beaver_pipeline` 提供发现/身份锁及命名操作转发。下列旧执行 ID 保持兼容，尚未接收的实现不会提前删除。见[beaver接入](docs/providers/beaver.md)。
>
> 模块统一发布：monkey/beaver 的固定 wheel 见 [modules.lock.json](modules.lock.json)，`grea_modules status|install` 只读查看或隔离安装；每个旧执行 ID 的接收能力登记在 registry `ownership.receiver`。见[审计与路线](proposals/triad-toolchain-audit-20261027.md)。

本页用于**按任务选工具**。安装和调用方法统一见 [使用说明](docs/使用指南.md)；完整登记、别名、依赖路径及平台限制以 [registry.json](registry.json) 为准，使用 list-tools／describe-tool 查询当前有效配置。本页不维护另一份“当前已安装版本”表。

## 选择入口

有具名操作时优先使用它；其他工具通过 run-tool 受控调用。下表中带短横线的操作名是 GREA CLI，反引号中的工具 ID 用于 tool_id，不要混用。

| 任务 | 推荐操作或工具 ID | 详细说明／限制 |
| --- | --- | --- |
| 检查包体身份与库存 | inspect-target；解包用 `unpack_xapk` | [通用脚本参数](docs/tools/制品与资源检查.md)；库存不等于已提取全部资源 |
| 原生运行与画面证据 | `adb`、`scrcpy`、`video_manifest`、`video_sheet` | [取证流程](plugin/skills/grea-evidence/references/原版运行与内容取证.md)；版本探测不连接或操作游戏 |
| Unity 资源与字段恢复 | `assetripper`、`unitypy` | 原 Prefab／引用关系优先；UnityPy 是独立运行时中的库，不是通用执行命令 |
| 配置、UI 表现与性能预检 | `config_preflight`、`presentation_audit`、`performance_compare` | [显式契约与范围](docs/providers/observation-tools.md)；未知/无效状态不按零处理 |
| 证据闭包与前后清单变化 | `evidence_manifest` | [输入契约](schemas/evidence-manifest.schema.json)；删除身份仍显示，当前闭包与范围差异分开 |
| Cocos 结构与脚本身份取证 | `cocos_assets`、`cocos_modules` | [2.4 范围与安装](docs/providers/cocos-static.md)、[3.4.1/CCON/System.register](docs/providers/cocos3-evidence.md)；动态拼表候选保持 partial，不执行源代码 |
| 原生退出与 Player 元数据 | `unity_native_exit`、`unity_player_audit`；Editor companion | [三层证据](docs/providers/unity-native-exit.md)；静态无命中不等于原生化通过 |
| 强类型配置和有限原生资源制作 | `unity_config_candidate`、`unity_native_assets`；Editor companion | [制作链](docs/providers/unity-authoring.md)；候选冲突保护，原生资产单独回读；Spine 仅页闭包 |
| IL2CPP／托管代码分析 | `cpp2il`、`ilspy`；按缺口使用 `il2cppdumper`、`ghidra`、`il2cpp-inspector` | [代码恢复流程](plugin/skills/grea-unity-recovery/references/Unity工程重建与恢复.md)、[Redux 边界](docs/providers/IL2CPP解析器接入.md) |
| Assets 身份台账 | snapshot-unity-assets；高级用法 `unity_asset_ledger` | [脚本契约](docs/tools/制品与资源检查.md#unity-资产迁移台账与预检) |
| 文本 GUID 依赖闭包 | audit-unity-dependencies | [脚本契约](docs/tools/制品与资源检查.md#unity-导出依赖审计)；动态依赖另验 |
| 玩法轨迹差分 | compare-gameplay-traces；严格事件 schema 用 `compare_events` | [事件契约](docs/tools/规则与格式检查.md#事件schema)；不重排事件 |
| 原始浮点纹理／VAT | inspect-numeric-texture | [数值纹理要求](docs/tools/规则与格式检查.md#数值纹理)；普通 PNG 不等同原始数值 |
| 图片透明度、媒体与压缩 | `image_alpha_audit`、`video_manifest`、`ffmpeg`、`ffprobe`、`pngquant` | [脚本契约](docs/tools/制品与资源检查.md)；部分登记仅提供探测，调用能力以 describe-tool 为准 |
| Shader 分析 | `glslangValidator`、`spirv-cross`、`spirv-val`、`spirv-dis` | [Shader 专项说明](docs/tools/Shader工具.md) |
| Unity Editor 操作与回读 | `unity_cli`、`unity_pipeline`；Editor 资源审计 | [连接流程](plugin/skills/grea-delivery/references/Unity编辑器连接与任务执行.md)、[实际资源回读](tools/unity/audit/README.md)；Pipeline 使用官方专用接口 |
| Unity 包与 Spine 运行时恢复 | 包备份、`spine38`、`spine41` | [包备份](tools/unity/packages/README.md)、[Spine 3.8](tools/unity/spine/Spine38/README.md)、[Spine 4.1](tools/unity/spine/Spine41/README.md)；版本不可随意互换 |
| 构建产物核对与 Windows 封装 | `verify_payload_tree`、`package_windows_portable`、`nsis` | [脚本契约](docs/tools/制品与资源检查.md)；封装成功不等于 Windows 运行通过 |
| 诊断、技能检查与有界测试 | doctor、`check_grea_skill` | [维护说明](docs/维护与发布.md)、[测试内存工具](scripts/testing/README.md) |
| 特定来源格式和历史工具 | `laya_contract_audit`、wxapkg 系列、旧 ARM32 模拟器 | [条件性恢复工具](docs/tools/规则与格式检查.md)、[旧模拟器](docs/providers/Android旧模拟器接入.md)；不作为默认路线 |

开发候选 `theme_assets`：只读美术/Spine生产声明台账校验，以及单Sprite PNG校验/预览与增量包；Editor显式应用/回退及限制见 [主题映射](docs/providers/theme-assets.md)。不修改游戏规则或自动处理骨骼/多Sprite。

## Unity 工程静态规划

`validate_unity_project` / `plan_unity_project` 已提供 项目配置、依赖和显式程序集检查与只读设计计划。用法见 [配置与检查](docs/Unity指南.md)；这两个静态操作不启动 Editor、不写目标；需要生成时使用下面独立的生成操作，运行验收另做。

[框架与通用组件](docs/Unity指南.md) 提供 Foundation/uGUI/Editor C# 源码与包测试；使用独立隔离测试入口，不新增 registry 工具 ID，不改变上述静态操作的运行证据。

## 工具存在于哪里

- 公开 GREA 子目录：通用源码、脚本、适配入口及说明。第三方程序、运行时和包备份可在本机保留，但不随 Git 分发，见 [依赖说明](THIRD_PARTY.md)。
- 系统安装：部分 Homebrew 工具、Unity Editor、Android SDK、Blender 等；克隆仓库不会自动安装。
- 项目内部：项目专用适配器、真实证据、分析输出和游戏制品，不搬到通用工具目录。
- Python 实现集中在 `src/grea/tools/`，其他技术栈见 [tools](tools/README.md)，第三方专题见 [接入说明](docs/providers/README.md)。

## 版本、库存与能力状态

依赖来源清单、Unity 包 catalog 和匿名验证摘要只描述各自记录范围。需要当前状态时，仅对本次依赖执行 doctor。detected、probe_passed、Editor 连接、真实样本成功分开报告。

Unity 包库存及恢复方法统一见 [备份说明](tools/unity/packages/README.md)。新项目以自己的 manifest／lock 和 Editor 版本为准，不把备份日期的版本当作推荐最新版本。

## 兼容与平台

`check_game_build_skill`、`decode-doctor`、`android_emulator_arm32_legacy` 是兼容别名；新调用使用正式入口。registry_doctor 是旧参数诊断入口，默认只查存在。更多映射见 [迁移说明](docs/安装与平台.md)。

host_support 表示登记的平台条件，不表示已原生实测；Windows 不能执行本机另行安装的 Mac 二进制。配置方法统一在 [使用说明](docs/使用指南.md)，限制见 [平台结论](docs/安装与平台.md)。

## Unity 工程生成与恢复

`plan_unity_generation` 只读规划/盘点；`generate_unity_project` 仅生成新工程或校验自己的生成清单；`recover_unity_generation` 核验并续作明确的中断记录。写入操作运行 Unity 并生成缓存，不能当成 静态规划 的只读工具。参见 [生成与恢复](docs/Unity指南.md)。

## Unity 参考项目分发

`unity_reference` 提供固定参考源码的 prepare/archive/verify/restore，内嵌自有包、校验锁和 SHA-256；不启动 Unity。独立恢复、测试与 Player 实玩证据见 [参考游戏说明](docs/Unity指南.md)。参考游戏通过不改变任意项目的 静态规划 静态报告。

## Unity 隔离迁移

`unity_pilot` 提供 snapshot/clone/verify，冻结明确输入、独立复制并验证原工程未变化；不启动 Unity，不迁移源工程。默认程序集可选桥接包、两类模块迁移的验收与回退边界见 [迁移说明](docs/Unity指南.md)。私有游戏的快照、补丁、截图和 Player 不进入公共分发。

`shader_probe` 与 `unity_package_backup` 将已有 Shader 探针和包备份实现接入统一调度；先通过 `describe-tool` 查看边界，再使用 `run-tool` 执行。

`static_asset_copy` 按显式路径映射复制静态文件，使用 Python 标准库；参数、退出码和复制边界见 [静态文件映射复制](docs/tools/制品与资源检查.md#静态文件映射复制)。

当前整改能力与未验项见 [审计整改执行记录](https://github.com/chuxintec/grea/blob/3d1a2be71292696ecc910523f33e949c160e3927/docs/design/audit-remediation-20261016.md)。新 TMP/Input System 配方见 [Modern UI v1](tools/unity/profiles/modern-ui/README.md)，旧 reference 证据不能沿用到新配方。

开发候选：`research_report`（[调研](docs/providers/research.md)）、`cocos_project` / `cocos_convert`（[Creator](docs/providers/cocos-target.md)）、`server_go_project`（[Go六服](docs/providers/server-go.md)）。模板生成不自动启动Editor、Docker或生产服务。

批量恢复主路：`monkey_pipeline`固定 monkey 0.4.0，执行 pin→plan→run→audit；`monkey`为外部可配置provider，`monkey_bridge`保留历史包级／切片接续与显式原生交接审计，见[monkey](docs/providers/monkey.md)；`image_contact_sheet`及`image_alpha_audit`规格增量见[资产总览](docs/providers/asset-preview.md)。

本地候选工具：`compatibility_plan`（声明的save/config/protocol/pending差异）与`operations_preview`（事件/经济只读分析及配置预览），见[支持范围](docs/providers/lifecycle-analysis.md)，不提供普通档迁移或生产执行。
