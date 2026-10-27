---
name: grea-unity-recovery
description: 源游戏本身是 Unity（Mono 或 IL2CPP 包体）时，从 AssetRipper 导出和反编译结果重建可运行的 Unity 工程：GUID 闭包、脚本 GUID/fileID 重映射、Missing Script 处理、Spine/Shader/TMP 接入回读，以及 Mono/IL2CPP/Ghidra 代码恢复证据链。Use when rebuilding a Unity project from a shipped Unity game. 不用于 Cocos、Laya、H5 等跨引擎转换（那类任务用 grea-native-port）。
---

# GREA · Unity 包体到 Unity 工程

先读 [共同约束与执行入口](../grea/references/共同约束与执行入口.md)；完整恢复的阶段顺序见 [恢复开发](../grea/references/游戏恢复开发.md)。


完整初版导出与接续边界遵循[全量初版工程与协作](../grea/references/全量初版工程与协作.md)。批量转换由固定monkey负责，GREA核交接并编排后续开发；lookup/静态候选不等于原生初版。已有工程的局部修复不无条件重导。

## 读取

- [Unity 工程重建与恢复](references/Unity工程重建与恢复.md)：工程路径与版本、原始导出到可运行工程的六个步骤、代码恢复证据链、运行时与资源兼容、Shader 与 Spine 回读。
- 资源提取与身份台账在 `grea-evidence`；界面、规则与动画的差异修复在 `grea-parity`；目录与程序集标准在 `grea-unity-standard`。

## 要点

- 原始导出只读；工作工程中的导入副本和修复副本分开。
- 通过 AssetDatabase/PrefabUtility 导入和修复，不在外部手改场景或 Prefab 的 YAML。
- 先核monkey全量初版的实际资源／代码交接；必要时用代表性原Prefab检查引用和显示，不能以逐个小样替代全量初版。
- 验收按 [分层验收](../grea/references/测试与结果交付.md) 记录。源游戏是 Unity 且工作工程实际使用原生Unity运行时/资产时，[原生可维护门](../grea/references/测试与结果交付.md#原生可维护性跨引擎转换) 记为不适用并写明依据；工程中混入跨引擎来源的模块时，那些模块按原生门验收。若目标为原生可维护Unity，而实际入口仍靠WebView/WASM宿主运行，不能因来源是Unity就记为不适用。
- 反编译结果、IL2CPP 伪代码和 DummyDLL 空壳的可信度不同，分别标注，不当作已恢复的源代码。

## monkey 调用步骤（Unity 原包恢复）

1. 调用 GREA `session` 核实际 MCP 版本，再 `describe_tool(tool_id="monkey_pipeline")`；技能已刷新不等于 MCP 已刷新。找不到新工具时先完成插件刷新，或显式标记使用已安装新版 CLI，不能报 MCP 已更新。
2. 使用 `run_tool` 调 `monkey_pipeline discover`。`discover` 不执行程序、不联网；`check --output <新目录>` 只探测并保存收据。首次接入执行 `ensure --install-if-missing --output <新目录>`：复用并验证已安装 monkey；完全缺失时从官方 GitHub 最新稳定 Release 下载校验并独立安装，再持久绑定。歧义、坏安装、版本不兼容不自动覆盖/降级。
3. 读取 ensure 的 `ready`、`version`、`command`、`lock`；仅 `ready=true` 才继续。新任务默认使用该绑定，既有计划保持自己的固定 lock。使用 source-family=unity、target=unity6、unity-export-scope=all 和完整 unity-dependency-manifest；声明 Python/AssetRipper 与纹理/代码依据。大输入按 prepare-unity-bulk → export-unity-bulk → convert 复用固定结果。
4. 编写请求 JSON（operation/options/input_roots/timeout_seconds），使用 `monkey_pipeline plan --request <请求> --output <新计划目录>`。固定工具和完整来源，不遗漏分包；plan 不执行转换。
5. 审阅计划后使用 `monkey_pipeline run --plan <plan.json> --output <新执行目录>`。两个命令省略 `--config` 时使用已绑定 lock，也可显式传已固定 lock。执行由 monkey 外部 CLI 完成，GREA 不复制转换器；每段使用明确预算，新目录不覆盖原工程。
6. `monkey_pipeline audit --workspace <provider-output> --output <新审计目录>` 核交付文件。再以 `monkey_bridge --workflow handoff --config <lock> ...` 核完整来源去向及真实原生回执；字节/数量通过不代表原生、视觉或玩法通过。未完成项留在证据/任务清单，不写假成功回调。
7. 交接通过后按完整模块接续业务、差分与验收；本期局部修复复用既有工程，不无条件重导。

调用示例（MCP；CLI 共用同一执行层）：

```json
{"tool_id":"monkey_pipeline","arguments":["ensure","--install-if-missing","--output","/absolute/new-readiness"],"run_dir":"/absolute/new-invocation","timeout_seconds":900}
```

安装只写独立用户数据目录，联网只用于官方 Release 及固定 Python 依赖；不自动升级已安装工具、引擎或客户端，不执行下载的安装脚本。接口、预算及原生门详见[monkey 接入](../grea/references/providers/monkey.md)。

## 执行工具与边界

monkey 生成独立 Unity 恢复候选；采用进入工作工程和原生验证由 beaver 执行。 完整执行链的必选依赖、固定绑定和过渡例外见[monkey与beaver调用](../grea/references/monkey与beaver调用.md)，仅在准备执行或依赖变化时加载。

接收第三方工程时按需读[研发交接资料核验](../grea-evidence/references/研发交接资料核验.md)：原始模块、适配模块、当前源码与已验Player分开；签名不当方法体，本地协议不当原服协议。
