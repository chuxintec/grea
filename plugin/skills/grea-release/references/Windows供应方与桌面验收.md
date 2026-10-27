# Windows 原生供应方与桌面复验

用途：配置已有的 Windows x64 工具并区分核心、供应方、客户端和 Unity。不会自动安装全部依赖。先核[统一调用](../../grea/references/接口调用与证据记录.md)与当前安装的目标平台声明。

| 能力 | 原生入口与前提 | 验收边界 |
| --- | --- | --- |
| wxapkg / XAPK | `wxapkg-unpack` / `unpack_xapk` 使用当前 Python | 两种合成输入、损坏与越界反例；不证明全部商业格式 |
| Cocos JS 索引 | Node + `npm ci --prefix tools/cocos --ignore-scripts` 安装锁定 Acorn | AST 静态解析，不执行来源 JS；缺 Node 不阻止 Python 数据解析 |
| Mono DLL 元数据 | dotnet + `tools/unity/assembly-audit` 的锁定 restore/build | DLL 仅读元数据；不加载被查程序集；IL2CPP 不支持 |
| UnityPy / V1MMWX 解密 | 另备 UnityPy / cryptography 的明确环境，通过 canonical provider 配置 | 依赖以目标 runtime-manifest 为准，不保证所有平台均附带；需真实格式样本，不以 help 代替 |
| AssetRipper / Cpp2IL / ilspy / adb / ffmpeg | `GREA_PROVIDERS` 中显式 argv，或 registry 声明的原生 PATH 命令 | 当前主机实际版本、输入和输出另验；不用 Mac 包装器 |
| Unity CLI / Editor | 已安装的原生 unity.exe、所需 Editor/模块与有效许可 | CLI、Editor 连接、导入、保存重开、Play、Player 分开 |

`schemas/tool-platform-matrix.json` 是声明矩阵，不是实测成绩单。自定义供应方只覆盖 canonical ID，保留 argv 数组，避免把带 `&`/空格路径拼接成 cmd 字符串。可执行文件不是原生 exe 时，显式配置对应解释器；不隐式回退到 Git Bash/WSL。

## 目标系统验收

在实际Windows桌面、匹配架构和有效引擎许可下，固定源码/候选ZIP/运行时、构建ID和QA存档，依次记录：核心CLI/MCP、外部provider、Editor导入/编译/保存重开、目标Player输入/显示/存档。所需层未执行就标not_run；是否影响交付由本次范围决定，不能沿用某个历史版本的豁免。

GREA插件维护可使用维护仓库的windows-readiness及verify_plugin_clients脚本，它们不是已安装Skill的运行前置。环境清单不等于运行通过；允许联网的客户端测试不能标成禁网沙箱通过。不要安装任务未要求的客户端。macOS交叉构建和包体核验也不能替代Windows桌面、GPU或输入验收。
