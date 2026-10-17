# 第三方依赖与许可边界

grea 自有代码与文档采用 [MIT](LICENSE)。第三方依赖保留各自许可证；MIT 不重新授权 Unity、Spine、游戏包、素材、源码或供应方工具。只处理自己拥有或获准分析的输入。

公开仓库只分发通用源码、流程、测试与接入说明。第三方二进制、安装副本、UPM 快照、插件包、Spine vendor 源码和项目派生解析器不随 Git 分发。已有本机副本可以继续使用，但其存在不等于获得再分发许可。

## Python 依赖

主运行时由 `uv sync --frozen` 按 [uv.lock](uv.lock) 安装；包自带的许可证和 notice 应保留。顶层依赖为 [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)、[jsonschema](https://github.com/python-jsonschema/jsonschema) 和 [Pillow](https://github.com/python-pillow/Pillow)。可选提取环境的版本在 [requirements.txt](tools/requirements-extraction.txt)，包含 [UnityPy](https://github.com/K0lb3/UnityPy) 与 [cryptography](https://github.com/pyca/cryptography)。

完整 macOS arm64 插件制品携带 [python-build-standalone](https://github.com/astral-sh/python-build-standalone) 的 CPython 3.12.14（20260929）及锁定的核心 Python 依赖；来源、平台、大小和 SHA256 见 [运行时锁](plugin/runtime-lock.json)。构建从固定归档恢复，不复制开发机 `.venv`。构建工具 uv 为 0.12.21，安装插件后的运行不依赖 uv。

发行包的 `runtime-manifest.json` 记录解释器来源和各 Python 包的实际版本、许可元数据；`runtime/` 内保留 CPython、内置库与 wheel 的许可文本，`runtime-requirements.txt` 记录依赖哈希。第三方许可不被 grea 的 MIT 覆盖。运行时二进制与下载缓存仅进入构建制品，不提交 Git；完整插件的这一分发范围与仅含源码、文档的两类旧制品分开说明。

所锁定 macOS 归档的上游元数据为四个使用系统 libz 的扩展同时列出了 zlib-ng 备选许可路径，该文件不在归档中。构建保留原始元数据和实际的 19 份许可证，并验证这四个扩展均链接系统 `z`、没有打包 zlib-ng；例外记录在 `runtime/license-manifest.json`。未知缺项、目标改变或链接方式改变会阻止构建，不能沿用此例外。

## 可选提供方

| 能力 | 官方来源 | 接入方式 |
| --- | --- | --- |
| Unity 资产提取 | [AssetRipper](https://github.com/AssetRipper/AssetRipper) | 自行取得匹配平台发行版，配置 `assetripper` |
| IL2CPP 分析 | [Cpp2IL](https://github.com/SamboyCoding/Cpp2IL)、[Il2CppDumper](https://github.com/Perfare/Il2CppDumper)、[Il2CppInspectorRedux](https://github.com/LukeFZ/Il2CppInspectorRedux) | 配置对应提供方；确认所选版本及许可 |
| 托管代码分析 | [ILSpy](https://github.com/icsharpcode/ILSpy) | 安装官方 CLI，配置 `ilspy` |
| .NET | [.NET](https://dotnet.microsoft.com/download) | 安装工具所需版本；本仓库不携带运行时 |
| Android 取证 | [Android SDK](https://developer.android.com/tools)、[scrcpy](https://github.com/Genymobile/scrcpy)、[Frida](https://github.com/frida/frida) | 按设备与系统安装；登记版本，显式授权实际操作 |
| Spine | [官方 runtimes](https://github.com/EsotericSoftware/spine-runtimes)、[许可条款](https://esotericsoftware.com/spine-runtimes-license) | 自行获取匹配源版本；本地构建说明见 [Spine 3.8](tools/unity/spine/Spine38/README.md)／[Spine 4.1](tools/unity/spine/Spine41/README.md) |
| Unity 包 | [Unity Package Manager](https://docs.unity3d.com/Manual/Packages.html) | 按目标项目 manifest/lock 解析，私人备份不公开 |
| 系统工具 | [Brewfile](Brewfile)、[工具目录](TOOLS.md) | 使用官方安装渠道；不把某台主机的安装复制成产品默认依赖 |

使用 [providers.example.json](providers.example.json) 配置同一个工具 ID 的本机命令，并通过 `GREA_PROVIDERS` 指定配置文件。该配置受信任且可执行，不从待分析游戏包自动加载。保留版本、来源、哈希和许可证；本仓库不会自动下载或接受供应方条款。

`unity-export-assets`、`webgl-xxtea-decrypt` 仅保留兼容 ID：它们原有的项目派生实现不公开，使用者须显式提供自己的适配器。缺失依赖返回 unavailable，不能仅凭包装脚本存在判断已安装。

## 设计参考

[UPSTREAM.json](UPSTREAM.json) 记录 REA 架构参考与 MCP SDK 来源。REA 用于设计研究，未复制其引擎实现。新增第三方源码前必须独立核对来源、许可和通知保留要求，不能只修改署名后纳入 MIT。

本机可选依赖统一放在 `.private/providers/` 或 `.private/runtimes/`，备份放 `.private/backups/`。目录约定见 [迁移说明](docs/安装与平台.md)；它们均不随公开包分发。

AssemblySanitizer 使用 [Mono.Cecil 0.11.6](https://github.com/jbevain/cecil)（MIT）；通过 NuGet 恢复，保留其许可通知。

## 可选静态解析与元数据依赖

- Acorn 8.15.0，MIT；npm 固定版本及完整性见 tools/cocos/package-lock.json。来源 https://www.npmjs.com/package/acorn/v/8.15.0 。只用于 AST 解析，不执行输入 JS；node_modules 不随 Git 或 Python 核心插件分发。
- Mono.Cecil 0.11.6，MIT；官方 NuGet 包元数据声明该许可，固定内容哈希见 tools/unity/assembly-audit/packages.lock.json。来源 https://www.nuget.org/packages/Mono.Cecil/0.11.6 。只读 DLL 元数据；.NET SDK、Cecil 二进制与本机构建输出不随源码分发，未来分发二进制需一并保留上游许可。
- Cocos 引擎参考文件和原游戏代码/素材仅为私有协议研究输入，不复制进上述实现、公开 fixtures、运行时或插件。解析器为独立实现，不重新授权来源代码。

有限制作链使用已锁定的 Pillow 处理自有/授权图片，Unity Editor API 创建原生资产；没有新增 Spine runtime 分发。Spine 页闭包检查不建立运行时授权，匹配来源与适用许可应另核验，见 [制作边界](docs/providers/unity-authoring.md)。

构建期使用锁定的 [python-zstandard 0.25.0](https://github.com/indygreg/python-zstandard/tree/0.25.0) 单次流式读取 CPython 许可归档，许可为 BSD-3-Clause（上游内含 zstd 许可）；仅在 dev 依赖组，运行插件的依赖仍从 `uv export --no-dev` 生成。原始许可随其构建环境包保留，不重新授权为 grea 代码。
