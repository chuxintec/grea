# Python 工具模块

GREA 2026.10.27 起，执行工具归 monkey 与 beaver 模块：来源侧工具在 `monkey tool <id>`，工程/媒体/证据工具在 `beaver tool <id>`。registry 中这些 ID 带 `delegate`，`run-tool`、MCP 与类型化操作原 ID 不变地委托到已绑定模块；新执行能力也应提交给模块，而不是加回这里。

这里只保留：路由与检查（`monkey_pipeline`、`monkey_bridge`、`beaver_pipeline`、`toolchain_check`、`grea_modules`、`check_skill`、`registry_doctor`、`research_report`），以及依赖 GREA 自带非 Python 资产的工具（`unity_player_audit` 的 .NET 读取器、`unity_reference`/`unity_framework_audit` 的自有 UPM 框架、`project_templates`/`server_go_project`/`cocos_project` 的模板、暂停中的 Cocos `cocos_assets`/`cocos_modules`/`cocos3_evidence`/`cocos_convert`、换皮 `theme_assets`）。`_artifact_common.py` 与 `_image_alpha.py` 是它们的私有辅助。

CLI/MCP → application → registry/runner → launch_tool.py → grea.tools 模块；委托 ID 则 → 模块 CLI。launch_tool.py 只做包定位和模块启动。子进程边界保留超时、取消和日志预算。legacy 保留原始 argv、输出和退出码。

模块导入不得解析命令行或写文件。可复用逻辑用函数提供；main 仅负责参数与调用。修改路径不修改工具 ID。文件路径迁移见 [映射](../../../schemas/document-path-map.json)，运行方法见 [使用指南](../../../plugin/skills/grea/references/使用指南.md)。
