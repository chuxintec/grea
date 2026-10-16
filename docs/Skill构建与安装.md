# Skill 构建与安装（grea 插件）

`plugin/` 维护技能、共享参考、客户端清单、运行时锁和启动薄层；`src/grea/` 是唯一业务实现。构建时组合成可安装插件，不从安装副本反向维护代码。

## 三种交付

| 制品 | 内容 | 使用前提 |
| --- | --- | --- |
| `grea-plugin-macos-arm64.zip` | 8 个技能、MCP、独立 CPython、锁定依赖、公开工具源码和资源 | macOS arm64；兼容的 Codex 或 Claude Code |
| `grea-skill-<tag>.zip` | 仅流程文档、共享参考、版本和插件清单；不注册 MCP | 执行工具时另装兼容 grea |
| `grea-<tag>.zip` | 完整源码、维护脚本和测试 | 从源码使用时需要 Python/uv，见使用指南 |

从 `v2026.10.16-rc1` 开始提供完整平台插件，产品与插件版本均为 `2026.10.16rc1`。开发预览同时标明 `source_kind=worktree-preview`、源码基线提交与实际内容哈希，不能冒充同版本已发布制品。

## 安装完整插件

先核对随包 `SHA256SUMS`，解压完整插件，进入其中的 `grea/` 目录。macOS 可使用 Archive Utility 或 `ditto -x -k`，保留执行权限与中文文件名。包根已生成两种客户端的 marketplace 描述，无需手写 MCP 配置或 Python 路径。

Codex：

```sh
codex plugin marketplace add .
codex plugin add grea@grea-local
codex plugin list --marketplace grea-local --json
```

Claude Code：

```sh
claude plugin marketplace add ./
claude plugin install grea@grea-local
claude plugin list --json
```

Claude 的本地 marketplace 参数使用 `./`；单独的 `.` 在已验客户端会被拒绝。保留解压目录作为本地安装来源，不移动后继续沿用旧 marketplace 记录。安装与更新沿用客户端的信任和启用流程。

新会话中确认 grea 技能与 MCP 工具被发现，再调用 `session`。无需 Git、系统 Python、uv、Homebrew，也不会在首次启动时下载依赖。终端入口仍是包根 `bin/grea`；CLI 和 MCP 使用同一应用层，工具 ID 与参数保持兼容。

如果客户端已有手工配置的 grea MCP 或旧 `.agents/skills/grea*`，先核对来源，按需停用旧入口，避免重复加载。安装器不修改用户已有配置。

Unity Editor、构建模块、AssetRipper、IL2CPP 工具和商业插件不随包安装。核心 MCP 在这些依赖缺失时仍可启动，并按工具报告 unavailable；`session` 成功不等于 Editor 连接或游戏验收完成。

## 制品布局与身份

包根包含 `.codex-plugin/`、`.claude-plugin/`、`.mcp.json`、生成的 marketplace、`plugin/skills/`、`runtime/` 和公开产品资源。客户端通过相对插件根目录的启动器访问固定解释器；安装目录按只读使用，项目输入、输出和日志由工具参数显式指定。

- `plugin-manifest.json`：产品版本、来源类型、提交与内容哈希、逐文件 SHA256/大小/权限。
- `runtime-manifest.json`：固定 CPython 来源、许可归档、Python 依赖实际版本与许可元数据、锁文件与导出依赖的哈希。
- `runtime-requirements.txt`：无构建主机路径的依赖清单，使用锁文件中的包哈希。
- `runtime/licenses/`、`runtime/PYTHON.json`、`runtime/license-manifest.json`：同版本上游完整发行归档的许可材料和提取证据；wheel 许可同时保留在 `dist-info` 内。

来源锁见 [runtime-lock.json](../plugin/runtime-lock.json)。运行时二进制只进入缓存和制品，不进入 Git；许可边界见 [第三方说明](../THIRD_PARTY.md)。

## 构建与验收

在 macOS arm64 源码环境中，构建工具需要 Python 3.11+、uv 0.12.21，以及 PATH 中可调用的 `zstd`（系统 `tar` 用它解包上游完整许可归档；CI 镜像已提供）；使用插件的机器不需要这些构建工具。默认仅从干净提交构建：

```sh
.venv/bin/python scripts/build_plugin.py --out dist/plugin
.venv/bin/python scripts/verify_plugin.py --bundle dist/plugin/grea-plugin-macos-arm64.zip --report dist/plugin/plugin-acceptance.json
.venv/bin/python scripts/verify_plugin_clients.py --bundle dist/plugin/grea-plugin-macos-arm64.zip --report dist/plugin/native-clients.json
```

开发中的未提交改动使用 `--worktree` 构建明确标记的未发布预览。构建先审计公开文件，固定运行时归档哈希；未知许可缺项、资源缺失、版本不符或依赖安装失败均阻止产物完成。输出目录必须不存在，下载只发生在构建时。

`verify_plugin.py` 在含空格和中文的临时目录解包并移动，使用独立 HOME、最小 PATH、macOS 沙箱实际禁止联网、读取源码和写安装目录，验证两种启动配置的 MCP 握手、21 个操作目录、工作流资源、真实核心工具子进程、兼容入口与失败契约。不能在沙箱中再创建沙箱的环境需要允许验收器启动系统沙箱，不能跳过隔离检查后标记通过。

`verify_plugin_clients.py` 另用独立客户端配置与安装缓存，实际验证 Codex、Claude Code 的随包市场安装、技能发现和 MCP 工具发现，全程不发送模型请求。缺少客户端、缺少随包市场或协议不支持时分别记录 blocked/not_run 并失败，不能拿配置模拟代替原生客户端验收。

CI 在 macOS arm64 上构建两次并逐字节比较，再运行隔离验收。实际客户端版本的验收结果单独记录；CI 协议测试不扩大为所有客户端版本或其他操作系统已通过。

## 纯文档 Skill 包与开发同步

独立文档包保持原构建入口：

```sh
python3 scripts/build_skill.py --tag v2026.10.16-rc1 --out dist/skill-check
python3 scripts/build_skill.py --tag v2026.10.16-rc1 --out dist/skill-check --verify
```

示例标签须替换为待验证版本，不覆盖旧 Release。纯文档包移除 MCP 注册、启动器及运行时锁；其可选外部文档链接指向固定提交的 GitHub 源码。它可以作为文档插件安装，也可把技能目录安装到客户端，但不会自动获得运行时。

源码工作区技能同步仍使用 `python3 scripts/sync_skill.py`，之后执行 `--check`。它只管理自己登记的技能副本，不是完整插件安装器，详见 [工作区接入](工作区接入.md)。完整平台插件、文档包及源码包的发布版本必须一致；新版本不复用历史标签。
