# grea 独立维护仓库

本仓库只维护 grea 工具、配套规范、文档、测试和第三方接入说明。README.md 为导航，docs/使用指南.md 为统一教程，docs/维护指南.md 为维护约定。

- 开始确认 Git 根目录为当前 grea 仓库；安装、测试和文档命令默认从本仓库根执行。
- CLI／MCP 共用 src/grea 应用层；公共契约在 contracts.py，工具与平台要求在 registry.json，schemas 由脚本生成。
- 现有兼容入口共用实现，不建立另一套业务逻辑。第三方源码、许可和历史验证不得为统一格式而批量改写。
- 技能规范在 plugin/（skills/<技能>/SKILL.md 与 references/、共享参考 shared/、两种客户端清单及 launcher/ 启动薄层）；Python 产品实现放 src/grea/（通用工具模块在 src/grea/tools/），其他技术栈源码放 tools/，测试放 tests/，仓库维护脚本放 scripts/；第三方专题说明放 docs/providers/。独立运行时由 plugin/runtime-lock.json 锁定、构建进制品，不提交二进制。平台模拟、原生测试、游戏验收分别报告。
- 游戏项目、工作区 memory、用户 .agents／.codex 配置位于仓库外，不是本仓库维护或发布内容。可选接入见 docs/工作区接入.md。
- 本机依赖、第三方二进制、包备份与凭据不得提交；公开树不使用 Git LFS。提交推送依当前用户授权执行。

- 开发规范以 plugin/shared 与 plugin/skills/*/references 为权威，采用 `<类别编号>-<类别>-<模块>.md` 命名，文件名在插件内唯一；docs 维护产品使用说明，历史阶段记录归 docs/history。插件版本见 plugin/version.json 与两份 plugin.json；完整平台插件由 scripts/build_plugin.py 构建，纯文档包由 scripts/build_skill.py 构建；工作区技能副本由 scripts/sync_skill.py 同步到 .agents/skills。
