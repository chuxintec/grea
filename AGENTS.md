<!-- workspace-relocation-20261018 -->
> 当前工作目录为工作区内的 `tools/grea`。旧外层入口 `grea`（工作区根）仅为历史路径兼容链接；新命令使用当前目录，产品内部名称/任务编号/证据保持原值。

# GREA 独立维护仓库

本仓库只维护 GREA 工具、配套规范、文档、测试和第三方接入说明。README.md 为导航，docs/使用指南.md 为统一教程，docs/维护与发布.md 为维护约定。

- 开始确认 Git 根目录为当前 GREA 仓库；安装、测试和文档命令默认从本仓库根执行。
- CLI／MCP 共用 src/grea 应用层；公共契约在 contracts.py，工具与平台要求在 registry.json，schemas 由脚本生成。
- 现有兼容入口共用实现，不建立另一套业务逻辑。第三方源码、许可和历史验证不得为统一格式而批量改写。
- 技能规范在 plugin/（skills/<技能>/SKILL.md 与 references/、共用参考位于 skills/grea/references/、两种客户端清单及 launcher/ 启动薄层）；Python 产品实现放 src/grea/（通用功能在 src/grea/features/，命令目录在 src/grea/commands/），其他技术栈源码放 tools/，测试放 tests/，仓库维护脚本放 scripts/；第三方专题说明放 docs/providers/。独立运行时分别由 plugin/runtime-lock.json 与 plugin/runtime-windows-x64.lock.json 锁定、构建进制品，不提交二进制。平台模拟、原生测试、游戏验收分别报告。
- 游戏项目、工作区 memory、用户 .agents／.codex 配置位于仓库外，不是本仓库维护或发布内容。可选接入见 docs/安装与平台.md。
- 本机依赖、第三方二进制、包备份与凭据不得提交；公开树不使用 Git LFS。提交推送依当前用户授权执行。

- 开发规范以 plugin/skills/*/SKILL.md 与 references 为权威，文件名直接突出内容，无数字/类别拼接前缀，按需加载，文件名在插件内唯一；docs 仅维护项目介绍、安装、使用和维护手册；执行必需的调用合同、边界与最小示例只维护在 Skill references/assets，禁止技能依赖仓库 docs 的链接或文字路径；同步与隔离闭包检查须通过。已完成过程由冻结 Git 历史追溯，未实现项归 proposals，不可变报告归 validation/releases。插件版本见 plugin/version.json 与两份 plugin.json；完整平台插件由 scripts/build_plugin.py 构建；发布仅提供双平台完整插件；工作区技能副本由 scripts/sync_skill.py 同步到 .agents/skills。

## 当前维护边界

GREA 为唯一维护仓库。恢复实现位于 `src/grea/recovery/`，工程事务位于 `src/grea/development/`，跨阶段工具归入 `src/grea/features/<模块>/`。公共 CLI 与 MCP 由 `src/grea/commands/` 从真实解析器生成。修改操作时同步验证参数文档、技能闭包、实际执行与旧调用。
本地完整 Git 历史含非公开源代码，不向公开远端推送。公开插件排除内部实现，编译分发继续后置。正式游戏与原始资源留在项目内。B02 的既有计划、消费者身份及先肥鹅后僵尸的正式采用顺序按原记录执行。

## 五技能阶段架构

安装仅包含 grea、grea-research、grea-recover、grea-develop、grea-release。换皮、Go服务端、Unity/Cocos开发与原版差异修复是开发阶段专题；技术取证归恢复，原版体验归调研，普通Editor操作归开发。保留旧工具ID、工作流mode与CLI/MCP输入；旧技能名称只维护迁移表，不生成重复技能目录。同步升级需移除安装记录中的旧托管技能、保留无关用户技能；构建和隔离验证核对五入口及参考闭包。

## 上下文压缩后接续

本仓库默认由 GREA 主开发单独实现、核验并交付。仅在用户对当前任务明确要求时启用子 Agent。模块交接使用现任主开发和固定制品；退役会话的记录只作历史证据。

恢复执行时先读唯一任务源 `proposals/lifecycle-roadmap.md` 的当前任务，核对最新事件、授权、运行目录、在途进程和退出回执。依据任务锚点接续下一步，复用已经完成的产物。旧消息只能提供背景，单凭旧消息不得删除分支、改写文件、派工或重复启动作业。锚点与当前指令冲突时，先核对最新人类指令或同事件裁定。
