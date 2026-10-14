# grea · 依据证据恢复 Unity 游戏

grea 把原包分析、资源检查、恢复流程和验收记录组织成一套 **CLI / MCP 工具与 Agent 技能**。它帮助你追踪“原版依据是什么、哪些资源已恢复、哪些行为仍待验证”，并提供可直接运行的通用检查工具。

| 你可以做什么 | 项目提供什么 |
| --- | --- |
| 检查 Unity 资产与构建产物 | 资产台账、GUID 依赖审计、文件哈希与包体差异、数值纹理检查 |
| 对照恢复结果 | 事件轨迹差分、图片透明度检查、录像信息与关键帧整理 |
| 组织恢复工作 | 原版取证、资源与规则恢复、真实输入、视觉音频及目标平台的分层验收规范 |
| 接入 Agent 或外部工具 | CLI 与 MCP 共用执行层；外部工具按明确配置接入 |

当前为维护者预览版：Unity 原生验收范围为 **macOS arm64 / Unity 6000.6.2f1**，生成器仅提供 Counter 示例配方。CLI 的静态能力不等于完整跨平台工具链或任意工程生成支持。

| 已实现 | 规划／不支持 | 历史验收 |
| --- | --- | --- |
| 静态配置检查、只读规划、受控工具运行；单一模板的新工程生成与恢复 | 已有游戏全自动迁移、多模板／多平台生成、Windows 完整原生支持 | 历史 Unity／Player 结果只覆盖各自记录的源码、版本与范围 |
| Foundation、uGUI、Editor 源码包和独立 Skill 分发 | 第三方本机定制二进制的完全可复现安装 | 新分支测试与旧 Release 分开，见 [实施记录](docs/history/Unity标准实施记录.md) |

## 快速开始

准备 Git 和 [uv](https://docs.astral.sh/uv/)，然后：

```sh
git clone https://github.com/chuxintec/grea.git
cd grea
uv sync --frozen
./bin/grea session
./bin/grea list-tools
```

Windows 将 `./bin/grea` 换为 `bin\grea.cmd`。也可以下载 [Release 完整使用包](https://github.com/chuxintec/grea/releases)，解压后从 `uv sync --frozen` 开始。

`session` 检查环境，不启动 Unity；可选工具显示 `unavailable` 时，按需安装并配置该工具。先查看一个仓库自带工具的参数：

```sh
./bin/grea describe-tool '{"tool_id":"unity_dependency_audit"}'
./bin/grea legacy unity_dependency_audit --help
```

完整调用示例、MCP 配置和 Windows 参数写法见 [使用说明](docs/使用指南.md)。macOS 与 Linux 有核心测试记录；Windows 原生验证和部分运行能力仍受限，详见 [平台说明](docs/工具集成与平台支持.md#平台结论)。

## 找到需要的内容

| 入口 | 用途 |
| --- | --- |
| [工具目录](TOOLS.md) | 按任务选工具，区分自带实现与外部依赖 |
| [恢复技能](skill/SKILL.md) | 让 Agent 按当前目标加载流程；[安装技能](docs/工作区接入.md#接入已有工作区) |
| [第三方依赖](THIRD_PARTY.md) | 官方来源、许可与本机接入；专题集中在 [providers](docs/providers) |
| [Unity 工程规范](skill/references/05-Unity-工程结构与开发规范.md) | [配置与检查](docs/Unity项目配置与检查.md)、[框架与组件](docs/Unity框架与通用组件.md)、[生成与恢复](docs/Unity工程生成与恢复.md)、[参考游戏](docs/Unity参考游戏.md)、[隔离迁移](docs/Unity隔离迁移指南.md) |
| [贡献指南](CONTRIBUTING.md) | 开发、测试和提交；[自动发布](docs/Release自动发布.md) |

## 仓库结构

```text
src/grea/   CLI、MCP、契约与产品功能；tools/ 子包为通用 Python 模块
tools/      Unity C# 包、模板及其他非 Python 工具源码
skill/      恢复流程规范与专题参考
docs/       用户教程、工具契约、第三方接入及维护文档
tests/      核心与工具回归、技能场景
scripts/    仓库检查、技能同步和 Release 自动化
bin/        启动器与兼容入口
schemas/    生成的接口/配置契约与能力目录，说明见 schemas/README.md
```

本机第三方依赖与备份集中在被忽略的 `.private/`，见 [本机目录约定](docs/兼容与迁移指南.md#本机依赖目录)。

工具 ID 和别名由 `registry.json` 统一维护；移动实现文件不改变调用 ID。实际运行和验收需结合当前项目证据：工具存在、测试通过或构建成功，都不等于游戏已恢复完成。

## 许可与分发

自有代码与文档采用 [MIT](LICENSE)。不附带游戏包、商业素材、第三方程序、Unity 包快照或 Spine vendor；使用者按授权和 [第三方说明](THIRD_PARTY.md) 准备自己的输入与依赖。项目数据、私人配置和本机缓存不进入公开包。

独立 Skill 制品为 `grea-skill-<tag>.zip`，明确版本与工具依赖，安装见 [Skill 分发](docs/Skill构建与安装.md)。历史阶段记录单独保留在 [history](docs/history/README.md)，日常使用无需理解阶段编号。
