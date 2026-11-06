# GREA 项目文档

GREA 在同一产品中实现来源恢复、工程采用、开发和验证。五个技能指导阶段选择，十四个功能模块提供 CLI 与 MCP 入口。

本目录只维护项目介绍、安装、使用、维护与故障手册；provider/tools 页面是用户入口，不重复技能中的规范和完整调用合同：做什么、按什么顺序、怎样验收，以 [grea 技能](../plugin/skills/grea/SKILL.md) 为准。

## 使用

| 文档 | 内容 |
| --- | --- |
| [安装与平台](安装与平台.md) | 选包、macOS/Windows 安装、升级回退与能力边界 |
| [使用指南](使用指南.md) | 检查输入、选择工具、执行并读回结果 |
| [接口与证据说明](接口与证据说明.md) | CLI/MCP 契约、Case/revision 与错误 |
| [Unity指南](Unity指南.md) | 工程检查、生成、恢复、框架与参考示例 |
| [故障排查](故障排查.md) | 按症状定位失败 |
| [维护与发布](维护与发布.md) | 开发、验证、构建和发布门槛 |

## 工具与模块

- [全部命令和参数](../plugin/skills/grea/references/功能模块和命令参数.md)，用 `grea commands` 查询当前版本实际实现。
- [provider 总览](providers/README.md)：供应方安装与使用入口；专项调用合同归各 Skill references；工具说明见[规则与格式检查](tools/规则与格式检查.md)、[制品与资源检查](tools/制品与资源检查.md)、[Shader 工具](tools/Shader工具.md)、[Memory Profiler 安装](tools/MemoryProfiler安装.md)。
- 工具目录与 ID 见 [TOOLS](../TOOLS.md)；换皮示例数据随 `grea-develop/assets/` 分发；开发候选 [主题映射](providers/theme-assets.md)。

验证与发布记录见 [validation](../validation/README.md)；未实现候选在 `proposals/`，不属于可用能力。

技能主路为调研 → 恢复 → 开发 → 发布，共五个入口（含总路由）；工程采用、换皮和Go服务统一属于开发，旧名称见[迁移表](../plugin/skills/grea/assets/skill-layout.json)。
