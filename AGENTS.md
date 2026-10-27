<!-- workspace-relocation-20261018 -->
> 当前工作目录为工作区内的 `tools/grea`。旧外层入口 `grea`（工作区根）仅为历史路径兼容链接；新命令使用当前目录，产品内部名称/任务编号/证据保持原值。

# GREA 独立维护仓库

本仓库只维护 GREA 工具、配套规范、文档、测试和第三方接入说明。README.md 为导航，docs/使用指南.md 为统一教程，docs/维护与发布.md 为维护约定。

- 开始确认 Git 根目录为当前 GREA 仓库；安装、测试和文档命令默认从本仓库根执行。
- CLI／MCP 共用 src/grea 应用层；公共契约在 contracts.py，工具与平台要求在 registry.json，schemas 由脚本生成。
- 现有兼容入口共用实现，不建立另一套业务逻辑。第三方源码、许可和历史验证不得为统一格式而批量改写。
- 技能规范在 plugin/（skills/<技能>/SKILL.md 与 references/、共用参考位于 skills/grea/references/、两种客户端清单及 launcher/ 启动薄层）；Python 产品实现放 src/grea/（通用工具模块在 src/grea/tools/），其他技术栈源码放 tools/，测试放 tests/，仓库维护脚本放 scripts/；第三方专题说明放 docs/providers/。独立运行时分别由 plugin/runtime-lock.json 与 plugin/runtime-windows-x64.lock.json 锁定、构建进制品，不提交二进制。平台模拟、原生测试、游戏验收分别报告。
- 游戏项目、工作区 memory、用户 .agents／.codex 配置位于仓库外，不是本仓库维护或发布内容。可选接入见 docs/安装与平台.md。
- 本机依赖、第三方二进制、包备份与凭据不得提交；公开树不使用 Git LFS。提交推送依当前用户授权执行。

- 开发规范以 plugin/skills/*/SKILL.md 与 references 为权威，文件名直接突出内容，无数字/类别拼接前缀，按需加载，文件名在插件内唯一；docs 维护产品使用说明，已完成过程由冻结 Git 历史追溯，未实现项归 proposals，不可变报告归 validation/releases。插件版本见 plugin/version.json 与两份 plugin.json；完整平台插件由 scripts/build_plugin.py 构建；发布仅提供双平台完整插件；工作区技能副本由 scripts/sync_skill.py 同步到 .agents/skills。

## 2026-10-26 三产品职责覆盖

GREA 为品牌（文字一律大写），`grea` 命令、Skill ID、包名与磁盘路径保持小写。GREA 主责 Skill、方法与薄调用；monkey 主责来源恢复候选；beaver 主责开发工程操作、框架/Prefab生成、图片/JSON工具、验证与构建。旧全部通用实现归 GREA 的约定由本条覆盖。旧实现先冻结，beaver接收及消费者验收后才转薄入口/退休，不破坏在途项目。当前本地dev候选不自动安装、推送或发布。
