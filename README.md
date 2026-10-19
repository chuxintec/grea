# grea · 游戏取证、恢复与原生 Unity 转换

> 当前分支包含未发布的 reskin/evolve M1 开发候选：新增主题映射与第9个技能。已发布 v2026.10.19 保持冻结，只有8技能；本分支未推送、发布或更新用户安装。

grea（Game Reverse Engineering and Assembly）为已发布游戏的分析、恢复、复刻与原生 Unity 转换提供 **统一 CLI、stdio MCP、9 个 Agent 技能及可复查的执行回执**。从原包与原版证据出发，把资源、规则、制作资产、源码、构建和验收身份连接起来，让开发者能继续在正常 Unity 工作流中维护工程。

它提供工具和有边界的工作流，不是一键万能转换器。提取成功、编译成功、工具检查通过、真实输入和原版一致性是不同结果；未执行的层保持未验。

[下载正式版](https://github.com/chuxintec/grea/releases/latest) · [开始使用](docs/使用指南.md) · [工具目录](TOOLS.md) · [验证记录](validation/README.md)

## 能解决什么问题

| 任务 | 当前能力 | 边界与入口 |
| --- | --- | --- |
| 原包盘点与取证 | 文件/目录摘要、包体清单、证据清单；wxapkg、XAPK 及资源解包工具；可选反编译和资源提取供应方 | 不执行待分析源代码，不推断隐藏服务器规则；[取证技能](plugin/skills/grea-evidence/SKILL.md) |
| 资源与代码分析 | Unity GUID/依赖闭包与资产台账；Cocos 资源/模块有限静态解析、配置预检、Shader/数值纹理与透明边检查 | 版本/格式按 adapter 声明；缺失、动态拼装及未支持输入保持 partial/unsupported；[专项契约](docs/providers/README.md) |
| 跨引擎原生转换 | 从 Cocos/Laya/H5 等来源的证据建立原生 Unity 制作、规则与可观察结果契约；有限 Sprite/Clip 配方、强类型配置候选与 Editor 伴随工具 | 不在 Player 重建源节点图或源生命周期；完整游戏仍需工程实现与验证；[原生转换](plugin/skills/grea-native-port/SKILL.md) |
| Unity 包体恢复 | 结合 AssetRipper、UnityPy、ILSpy、Cpp2IL 等可选供应方，恢复资源引用与 Mono/IL2CPP 代码证据 | 工具检测不等于恢复完成；受版本、裁剪、符号和供应方格式限制；[Unity恢复](plugin/skills/grea-unity-recovery/SKILL.md) |
| 工程标准与生成 | 项目配置/Schema、静态校验、只读规划、受控生成与中断恢复；明确文件所有权；Foundation/uGUI/Editor 三个 UPM 源码包及最小消费者 | 现有工程不自动迁移；生成不覆盖人工修改；[Unity指南](docs/Unity指南.md) |
| 一致性与回归 | 规则/事件轨迹首差异、表现与性能合同检查、资源/载荷回读；源代码、Editor、实际 Player 元数据分层 | 合同检查不证明输入采集正确、可玩或完整视觉/性能通过；[一致性技能](plugin/skills/grea-parity/SKILL.md) |
| 证据、候选与交付 | Case/revision、证据哈希、追加式审阅声明；执行预算/日志/退出与清理回执；包体身份、封装及交付规则 | 审阅声明不执行游戏；安装/发布沿用户授权，未测平台单列；[接口说明](docs/接口与证据说明.md) |

## 安装与第一次调用

### 完整插件：macOS ARM64 / Windows x64

从 [Release](https://github.com/chuxintec/grea/releases/latest) 下载对应平台完整包：

- `grea-plugin-macos-arm64.zip`
- `grea-plugin-windows-x64.zip`

每包包含锁定的 Python 运行时与核心依赖、CLI、MCP、全部技能、参考和许可证。安装使用时无需另配系统 Python、uv 或源码路径；第三方程序按任务单独准备。Release 另有 manifest、SHA256SUMS 和分平台隔离/客户端验收报告，不再独立分发 Skill 安装 ZIP。

核对校验文件后解压，在解压后的 `grea` 目录中，用已有 Codex 执行：

```text
codex plugin marketplace add .
codex plugin add grea@grea-local
codex plugin list --marketplace grea-local --json
```

重启客户端并开新会话，调用 MCP `session`，确认版本与包路径来自安装副本，再执行一次实际工具调用。installed/enabled、技能可见、MCP 工具发现与工具业务成功分别检查。

Claude Code 的安装入口和 stdio 清单也随包提供，按 [安装与平台](docs/安装与平台.md) 操作。两份 stdio 配置可验证，不等于两个原生客户端都已验收。完整插件支持原生 macOS Apple Silicon、Windows x64；Intel Mac、Windows ARM64、WSL/Wine 不自动支持。升级采用新目录并保留旧版本回退，不覆盖游戏或 Case。

### 源码使用与开发

```sh
uv sync --frozen
./bin/grea session
./bin/grea list-tools
./bin/grea describe-tool '{"tool_id":"unity_player_audit"}'
./bin/grea plan-workflow '{"mode":"assess","source_engine":"cocos"}'
```

上述规划只输出评估流程，不启动转换或游戏。Windows PowerShell 的源码入口为 `bin\grea.cmd session`；复杂 JSON 用 UTF-8 请求文件配合 `--input`，避免 shell 引号差异。命令行帮助为 `./bin/grea --help`；源码的 Python 最低版本与依赖以 [pyproject.toml](pyproject.toml) 和 [uv.lock](uv.lock) 为准，维护构建工具可能要求更高版本。

### 执行一次受控工具任务

先查工具契约、可用供应方和副作用；准备独立输入与全新输出路径。例如保存以下内容为 `request.json`，将示例路径改为本机绝对路径：

```json
{
  "tool_id": "static_asset_copy",
  "arguments": ["--source", "/absolute/input", "--output", "/absolute/new-copy", "--map", "a.txt=b.txt"],
  "run_dir": "/absolute/new-attempt",
  "timeout_seconds": 120
}
```

```sh
./bin/grea run-tool --input request.json
```

Windows 可使用 `C:/work/...`。回读结构化结果及 run_dir 中的回执、stdout/stderr、退出码和产物哈希；不能复用旧运行目录掩盖失败。CLI 与 MCP 共用 [契约](schemas/operations.json) 及执行层；MCP 使用本地 **stdio**，无需另开 HTTP 服务。CLI 操作用短横线，MCP 用下划线，例如 `run-tool` / `run_tool`。既有工具 ID 和兼容入口保留。

## 9 个技能如何分工

| 技能 | 职责 |
| --- | --- |
| [grea](plugin/skills/grea/SKILL.md) | 总入口：辨识来源、任务模式与验收范围，路由到子技能 |
| [grea-evidence](plugin/skills/grea-evidence/SKILL.md) | 原版运行、包体与资源/代码提取、覆盖表和来源台账 |
| [grea-native-port](plugin/skills/grea-native-port/SKILL.md) | 非 Unity 来源转原生 Unity；清理源引擎运行机制与双真源 |
| [grea-unity-recovery](plugin/skills/grea-unity-recovery/SKILL.md) | 原本就是 Unity 的包体恢复、GUID/脚本引用与依赖重建 |
| [grea-parity](plugin/skills/grea-parity/SKILL.md) | 规则、随机、视觉、动画、布局和输入的局部差异修复 |
| [grea-unity-standard](plugin/skills/grea-unity-standard/SKILL.md) | 工程/程序集结构、生命周期、配置、资产治理与性能 |
| [grea-delivery](plugin/skills/grea-delivery/SKILL.md) | Editor任务、构建、制品身份、封装、预览与发布 |
| [grea-reskin](plugin/skills/grea-reskin/SKILL.md) | 有明确设计与授权的换皮，保持指定玩法和交互 |
| [grea-evolve](plugin/skills/grea-evolve/SKILL.md) | 已恢复工程的有限UI/UE二次开发，旧玩法基线与新设计维度分离（开发候选） |

这些技能面向有原版依据的恢复与维护。原创 Unity 开发不自动套用恢复门槛。权威流程维护在 `plugin/shared/` 与各技能 references；docs 解释产品使用，避免两套竞争规范。

## 工具、原生制作与框架

[TOOLS.md](TOOLS.md) 提供按任务选择的目录，[registry.json](registry.json) 记录工具 ID、别名、依赖、效果和格式。目录包含内置工具与可选外部供应方，条目数量不代表本机已装或业务已验证。典型工具族包括：

- **来源与资源**：`inspect-target`、`evidence_manifest`、wxapkg/XAPK 工具、`cocos_assets`、`cocos_modules`、Unity 资源/配置导出与 GUID 台账。
- **规则与表现**：`config_preflight`、`compare_events`、`compare_traces`、`presentation_audit`、`performance_compare`、图像透明边和数值纹理检查。
- **Unity 退出检查**：`unity_native_exit` 给出静态候选与待审线索；Editor 伴随工具回读生产编译/资产范围；`unity_player_audit` 核对完整 Mono Managed DLL 集合及摘要，再读取元数据。当前支持最多256个DLL；它不执行被审DLL，不证明完整调用图、源机制语义或 IL2CPP 退出。
- **原生制作**：`unity_config_candidate`、`unity_native_assets` 生成有限、受契约保护的候选；Editor API 导入后由原生资产制作。不解释完整源引擎，每张表保持一个制作源，人工冲突拒绝覆盖。
- **交付辅助**：`verify_payload_tree`、`package_windows_portable`、`video_manifest`、`video_sheet` 与包备份/恢复工具；是否支持当前目标先查工具说明。

Cocos 2.4 与 Creator 3.4.1 的有限格式解析有各自适配边界，不能互相猜解；Laya/H5/Egret 工作流不意味着任意版本解析器已实现。Spine 数据闭包检查也不等于渲染、运行时兼容或许可已满足。详见 [供应方与格式契约](docs/providers/README.md)。

Unity 侧已有 [Foundation/uGUI/Editor 三个 UPM 包](tools/unity/framework/packages)、受控工程生成与恢复入口，以及 [数值战斗/网格益智自有最小消费者](tools/unity/templates/framework-samples/README.md)。它们验证薄胶水与有限闭环，不是完整 IAA 模板；复杂背包、Buff、商业奖励和列表框架仍是 [候选范围](proposals/numeric-template.md)，不声明已批量适配所有品类。项目可沿用自己的框架和主流插件。

开发候选的 [主题映射](docs/providers/theme-assets.md) 提供校验、前后预览及可回退增量包；独立Editor伴随工具保护单Sprite PNG身份与几何。骨骼、多Sprite、尺寸迁移和游戏玩法不自动处理。

## Case 与典型工作流

Case 是显式创建的项目内追加记录：来源基线→候选 revision→带哈希的证据→分维度审阅→状态回读。候选、来源或证据变化会使旧结论失效，保留历史，不覆盖旧记录。`record-verification` 记录审阅声明，不会自动运行测试或查看图片。

1. **评估/取证**：`session` → `inspect-target` → `plan-workflow` → 选工具提取/分析，记录格式、来源与未知项。只读评估不自动写入目标工程。
2. **恢复/转换**：确认原版与可达范围，选择代表切片；规则用原依据对照，UI/配置/动画转为原生制作源，分模块接入；按规则、制作、真实运行和原版对照分别验收。
3. **维护/修复**：冻结本次候选，按差异选择受影响检查。仅审计器变化可重审未变载荷；运行时或资源变化须验证相关实际消费者。普通包的销毁/退出不能只借开发包结果。
4. **交付**：固定输入与目标，新 buildId 输出，检查完整载荷与封装，按授权发布；同源不等于跨平台已运行，元数据或解包校验不等于安装/实机通过。

Case 操作、严格 JSON Schema、退出码、预算、清理和审阅边界见 [接口与证据说明](docs/接口与证据说明.md)。原始游戏包、玩家档、许可证材料、GUI/性能证据留项目，不进入公共工具仓库。

## 依赖、验收与许可

完整插件的核心运行时自包含；Unity Editor/许可证、Node/Acorn、.NET/Cecil、AssetRipper、ffmpeg、Android 工具等仍是按需准备的外部能力。`describe-tool` / `doctor` 检查 presence 或显式帮助，不自动安装全部软件，也不替第三方授予许可。供应方缺失只阻止相关工具，不阻断独立任务。

发布采用原生 CI、双平台完整插件隔离验收、临时 Codex 安装发现、重复构建、源码身份绑定与附件下载校验。Windows Server CLI 验证不等于 Windows 11 桌面、Unity Editor/Player、GPU 或人工输入已验；未执行部分在 [验证索引](validation/README.md) 和 Release 报告中明确保留。普通发行包不携带玩家/QA档；第三方工具可用不等于隐藏服务端结算、广告、支付等已恢复。

自有代码采用 [MIT](LICENSE)。原游戏素材、商业插件与第三方运行时保留各自许可，不因 grea 开源而获得再分发权；来源与要求见 [THIRD_PARTY.md](THIRD_PARTY.md)。

## 文档与贡献

| 文档 | 内容 |
| --- | --- |
| [安装与平台](docs/安装与平台.md) | 插件/源码安装、供应方、升级与回退 |
| [使用指南](docs/使用指南.md) | 首次调用、输入、回执与任务选择 |
| [接口与证据说明](docs/接口与证据说明.md) | CLI/MCP 操作、Schema、Case、错误与执行预算 |
| [Unity指南](docs/Unity指南.md) | 规划、生成、制作、框架及验收边界 |
| [故障排查](docs/故障排查.md) | 依赖、进程、路径与失败回执 |
| [维护与发布](docs/维护与发布.md) | 源码职责、检查、构建与发布流程 |
| [全部文档导航](docs/README.md) / [贡献指南](CONTRIBUTING.md) | 专项格式、测试和贡献入口 |

通用实现放 `src/grea/`，其他技术栈及 Unity 源码放 `tools/`，维护脚本放 `scripts/`，技能维护源只在 `plugin/`。保留工具 ID、调用契约和旧证据；改动按实际风险运行相关测试，发布前完成既有 CI 和制品门禁。
