# Windows 原生供应方与桌面复验

用途：配置已有的 Windows x64 工具并区分核心、供应方、客户端和 Unity。不会自动安装全部依赖。日常入口见 [安装与平台](../安装与平台.md)。

| 能力 | 原生入口与前提 | 验收边界 |
| --- | --- | --- |
| wxapkg / XAPK | `wxapkg-unpack` / `unpack_xapk` 使用当前 Python | 两种合成输入、损坏与越界反例；不证明全部商业格式 |
| Cocos JS 索引 | Node + `npm ci --prefix tools/cocos --ignore-scripts` 安装锁定 Acorn | AST 静态解析，不执行来源 JS；缺 Node 不阻止 Python 数据解析 |
| Mono DLL 元数据 | dotnet + `tools/unity/assembly-audit` 的锁定 restore/build | DLL 仅读元数据；不加载被查程序集；IL2CPP 不支持 |
| UnityPy / V1MMWX 解密 | 另备 UnityPy / cryptography 的明确环境，通过 canonical provider 配置 | 依赖以目标 runtime-manifest 为准，不保证所有平台均附带；需真实格式样本，不以 help 代替 |
| AssetRipper / Cpp2IL / ilspy / adb / ffmpeg | `GREA_PROVIDERS` 中显式 argv，或 registry 声明的原生 PATH 命令 | 当前主机实际版本、输入和输出另验；不用 Mac 包装器 |
| Unity CLI / Editor | 已安装的原生 unity.exe、所需 Editor/模块与有效许可 | CLI、Editor 连接、导入、保存重开、Play、Player 分开 |

`schemas/tool-platform-matrix.json` 是声明矩阵，不是实测成绩单。自定义供应方只覆盖 canonical ID，保留 argv 数组，避免把带 `&`/空格路径拼接成 cmd 字符串。可执行文件不是原生 exe 时，显式配置对应解释器；不隐式回退到 Git Bash/WSL。

## Windows 11 复验入口

在具备桌面和 Unity 许可的 Windows 11 x64 普通用户会话中，先运行：

```text
python scripts/testing/windows-readiness.py --out C:/new-evidence/windows-readiness.json
```

其中 python 为候选维护环境或明确解释器。该脚本只做环境清单，不打开游戏或假造通过；报告给出后续精确入口。源码、候选 ZIP、运行时、测试 XML、Player 构建 ID 和 QA 存档需绑定同一次运行。

独立配置的 Codex 复验使用 `scripts/verify_plugin_clients.py --client codex --codex-bin <native-exe> --bundle <windows-zip> --report <new-json> --allow-network`。`--allow-network` 代表此客户端层未禁网，不能复制为插件隔离层的通过；不发送模型请求，不改用户安装。Claude 未经要求不安装。

Windows Server CI 可关闭原生 CLI/Job/锁及插件范围；本轮 Windows 11 桌面输入、Unity/Player、GPU 性能和人工输入由用户明确排除，保持 not_run，不阻塞本轮发布。后续实机验证需独立授权及证据。Mac 上交叉构建 Windows Player 也只能证明编译与包体，不证明其运行体验。
