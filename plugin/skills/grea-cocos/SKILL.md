---
name: grea-cocos
description: 将已授权游戏恢复、移植或构建为Cocos Creator目标工程，提供3.8.8五层模板、基础序列化转换子集、资源身份和浏览器运行流程。尊重显式Cocos目标；不把源引擎包装成Unity，也不声称全版本自动转换。
---

# GREA · Creator目标

读 [工程与迁移](references/Cocos工程与迁移.md)。源版本和目标版本分别记录；当前目标3.8.8，浏览器优先。`cocos_project`创建自有五层示例，`cocos_convert`仅转换明确支持的基础Scene/Prefab；输入原件只读，输出全新，未支持项不静默丢弃。

Unity专属asmdef/uGUI/UPM规则不套给Creator；不改官方引擎，不默认安装Funplay。调研不等于开发授权；需要Go后端时见 `grea-server-go` 技能。


完整初版导出与接续边界遵循[全量初版工程与协作](../grea/references/全量初版工程与协作.md)。批量转换由固定monkey负责，GREA核交接并编排后续开发；lookup/静态候选不等于原生初版。已有工程的局部修复不无条件重导。

## monkey 调用步骤（Cocos 目标恢复）

1. 调用 GREA `session` 核实际 MCP 版本，再 `describe_tool(tool_id="monkey_pipeline")`；技能已刷新不等于 MCP 已刷新。找不到新工具时先完成插件刷新，或显式标记使用已安装新版 CLI，不能报 MCP 已更新。
2. 使用 `run_tool` 调 `monkey_pipeline discover`。`discover` 不执行程序、不联网；`check --output <新目录>` 只探测并保存收据。首次接入执行 `ensure --install-if-missing --output <新目录>`：复用并验证已安装 monkey；完全缺失时从官方 GitHub 最新稳定 Release 下载校验并独立安装，再持久绑定。歧义、坏安装、版本不兼容不自动覆盖/降级。
3. 读取 ensure 的 `ready`、`version`、`command`、`lock`；仅 `ready=true` 才继续。新任务默认使用该绑定，既有计划保持自己的固定 lock。使用 source-family=cocos、完整 input-set、target=cocos38（用户明确双端时 both），保持暂停项目边界；候选导出后再按指定 Creator 版本核原生读回。
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

源恢复调用 monkey；Creator 工程接续与验证调用 beaver 的已声明子集，未支持部分明确 needs_action。 完整执行链的必选依赖、固定绑定和过渡例外见[monkey与beaver调用](../grea/references/monkey与beaver调用.md)，仅在准备执行或依赖变化时加载。
