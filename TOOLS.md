# grea 工具目录

本页用于**按任务选工具**。安装和调用方法统一见 [使用说明](docs/使用指南.md)；完整登记、别名、依赖路径及平台限制以 [registry.json](registry.json) 为准，使用 list-tools／describe-tool 查询当前有效配置。本页不维护另一份“当前已安装版本”表。

## 选择入口

有具名操作时优先使用它；其他工具通过 run-tool 受控调用。下表中带短横线的操作名是 grea CLI，反引号中的工具 ID 用于 tool_id，不要混用。

| 任务 | 推荐操作或工具 ID | 详细说明／限制 |
| --- | --- | --- |
| 检查包体身份与库存 | inspect-target；解包用 `unpack_xapk` | [通用脚本参数](docs/tools/制品与资源检查.md)；库存不等于已提取全部资源 |
| 原生运行与画面证据 | `adb`、`scrcpy`、`video_manifest`、`video_sheet` | [取证流程](skill/references/恢复-原版运行与内容取证.md)；版本探测不连接或操作游戏 |
| Unity 资源与字段恢复 | `assetripper`、`unitypy` | 原 Prefab／引用关系优先；UnityPy 是独立运行时中的库，不是通用执行命令 |
| IL2CPP／托管代码分析 | `cpp2il`、`ilspy`；按缺口使用 `il2cppdumper`、`ghidra`、`il2cpp-inspector` | [代码恢复流程](skill/references/Unity-工程重建与恢复.md)、[Redux 边界](docs/providers/IL2CPP解析器接入.md) |
| Assets 身份台账 | snapshot-unity-assets；高级用法 `unity_asset_ledger` | [脚本契约](docs/tools/制品与资源检查.md#unity-资产迁移台账与预检) |
| 文本 GUID 依赖闭包 | audit-unity-dependencies | [脚本契约](docs/tools/制品与资源检查.md#unity-导出依赖审计)；动态依赖另验 |
| 玩法轨迹差分 | compare-gameplay-traces；严格事件 schema 用 `compare_events` | [事件契约](docs/tools/规则与格式检查.md#事件schema)；不重排事件 |
| 原始浮点纹理／VAT | inspect-numeric-texture | [数值纹理要求](docs/tools/规则与格式检查.md#数值纹理)；普通 PNG 不等同原始数值 |
| 图片透明度、媒体与压缩 | `image_alpha_audit`、`video_manifest`、`ffmpeg`、`ffprobe`、`pngquant` | [脚本契约](docs/tools/制品与资源检查.md)；部分登记仅提供探测，调用能力以 describe-tool 为准 |
| Shader 分析 | `glslangValidator`、`spirv-cross`、`spirv-val`、`spirv-dis` | [Shader 专项说明](docs/tools/Shader工具.md) |
| Unity Editor 操作与回读 | `unity_cli`、`unity_pipeline`；Editor 资源审计 | [连接流程](skill/references/Unity-编辑器连接与任务执行.md)、[实际资源回读](tools/unity/audit/README.md)；Pipeline 使用官方专用接口 |
| Unity 包与 Spine 运行时恢复 | 包备份、`spine38`、`spine41` | [包备份](tools/unity/packages/README.md)、[Spine 3.8](tools/unity/spine/Spine38/README.md)、[Spine 4.1](tools/unity/spine/Spine41/README.md)；版本不可随意互换 |
| 构建产物核对与 Windows 封装 | `verify_payload_tree`、`package_windows_portable`、`nsis` | [脚本契约](docs/tools/制品与资源检查.md)；封装成功不等于 Windows 运行通过 |
| 诊断、技能检查与有界测试 | doctor、`check_grea_skill` | [维护说明](docs/维护指南.md)、[测试内存工具](scripts/testing/README.md) |
| 特定来源格式和历史工具 | `laya_contract_audit`、wxapkg 系列、旧 ARM32 模拟器 | [条件性恢复工具](docs/tools/规则与格式检查.md)、[旧模拟器](docs/providers/Android旧模拟器接入.md)；不作为默认路线 |

## Unity 工程静态规划

`validate_unity_project` / `plan_unity_project` 已提供 项目配置、依赖和显式程序集检查与只读设计计划。用法见 [配置与检查](docs/Unity项目配置与检查.md)；不启动 Editor，不写目标，不提供工程生成或运行验收。

[框架与通用组件](docs/Unity框架与通用组件.md) 提供 Foundation/uGUI/Editor C# 源码与包测试；使用独立隔离测试入口，不新增 registry 工具 ID，不改变上述静态操作的运行证据。

## 工具存在于哪里

- 公开 grea 子目录：通用源码、脚本、适配入口及说明。第三方程序、运行时和包备份可在本机保留，但不随 Git 分发，见 [依赖说明](THIRD_PARTY.md)。
- 系统安装：部分 Homebrew 工具、Unity Editor、Android SDK、Blender 等；克隆仓库不会自动安装。
- 项目内部：项目专用适配器、真实证据、分析输出和游戏制品，不搬到通用工具目录。
- Python 实现集中在 `src/grea/tools/`，其他技术栈见 [tools](tools/README.md)，第三方专题见 [接入说明](docs/providers/README.md)。

## 版本、库存与能力状态

依赖来源清单、Unity 包 catalog 和匿名验证摘要只描述各自记录范围。需要当前状态时，仅对本次依赖执行 doctor。detected、probe_passed、Editor 连接、真实样本成功分开报告。

Unity 包库存及恢复方法统一见 [备份说明](tools/unity/packages/README.md)。新项目以自己的 manifest／lock 和 Editor 版本为准，不把备份日期的版本当作推荐最新版本。

## 兼容与平台

`check_game_build_skill`、`decode-doctor`、`android_emulator_arm32_legacy` 是兼容别名；新调用使用正式入口。registry_doctor 是旧参数诊断入口，默认只查存在。更多映射见 [迁移说明](docs/兼容与迁移指南.md)。

host_support 表示登记的平台条件，不表示已原生实测；Windows 不能执行本机另行安装的 Mac 二进制。配置方法统一在 [使用说明](docs/使用指南.md#8-windows-原生工具配置)，限制见 [平台结论](docs/工具集成与平台支持.md#平台结论)。

## Unity 工程生成与恢复

`plan_unity_generation` 只读规划/盘点；`generate_unity_project` 仅生成新工程或校验自己的生成清单；`recover_unity_generation` 核验并续作明确的中断记录。写入操作运行 Unity 并生成缓存，不能当成 静态规划 的只读工具。参见 [生成与恢复](docs/Unity工程生成与恢复.md)。

## Unity 参考项目分发

`unity_reference` 提供固定参考源码的 prepare/archive/verify/restore，内嵌自有包、校验锁和 SHA-256；不启动 Unity。独立恢复、测试与 Player 实玩证据见 [参考游戏说明](docs/Unity参考游戏.md)。参考游戏通过不改变任意项目的 静态规划 静态报告。

## Unity 隔离迁移

`unity_pilot` 提供 snapshot/clone/verify，冻结明确输入、独立复制并验证原工程未变化；不启动 Unity，不迁移源工程。默认程序集可选桥接包、两类模块迁移的验收与回退边界见 [迁移说明](docs/Unity隔离迁移指南.md)。私有游戏的快照、补丁、截图和 Player 不进入公共分发。

`shader_probe` 与 `unity_package_backup` 将已有 Shader 探针和包备份实现接入统一调度；先通过 `describe-tool` 查看边界，再使用 `run-tool` 执行。
