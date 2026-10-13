# 第三方依赖与许可边界

grea 自有代码与文档采用 [MIT](LICENSE)。第三方依赖保留各自许可证；MIT 不重新授权 Unity、Spine、游戏包、素材、源码或供应方工具。只处理自己拥有或获准分析的输入。

公开仓库只分发通用源码、流程、测试与接入说明。第三方二进制、安装副本、UPM 快照、插件包、Spine vendor 源码和项目派生解析器不随 Git 分发。已有本机副本可以继续使用，但其存在不等于获得再分发许可。

## Python 依赖

主运行时由 `uv sync --frozen` 按 [uv.lock](uv.lock) 安装；包自带的许可证和 notice 应保留。顶层依赖为 [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)、[jsonschema](https://github.com/python-jsonschema/jsonschema) 和 [Pillow](https://github.com/python-pillow/Pillow)。可选提取环境的版本在 [requirements.txt](python-runtime/requirements.txt)，包含 [UnityPy](https://github.com/K0lb3/UnityPy) 与 [cryptography](https://github.com/pyca/cryptography)。

## 可选提供方

| 能力 | 官方来源 | 接入方式 |
| --- | --- | --- |
| Unity 资产提取 | [AssetRipper](https://github.com/AssetRipper/AssetRipper) | 自行取得匹配平台发行版，配置 `assetripper` |
| IL2CPP 分析 | [Cpp2IL](https://github.com/SamboyCoding/Cpp2IL)、[Il2CppDumper](https://github.com/Perfare/Il2CppDumper)、[Il2CppInspectorRedux](https://github.com/LukeFZ/Il2CppInspectorRedux) | 配置对应提供方；确认所选版本及许可 |
| 托管代码分析 | [ILSpy](https://github.com/icsharpcode/ILSpy) | 安装官方 CLI，配置 `ilspy` |
| .NET | [.NET](https://dotnet.microsoft.com/download) | 安装工具所需版本；本仓库不携带运行时 |
| Android 取证 | [Android SDK](https://developer.android.com/tools)、[scrcpy](https://github.com/Genymobile/scrcpy)、[Frida](https://github.com/frida/frida) | 按设备与系统安装；登记版本，显式授权实际操作 |
| Spine | [官方 runtimes](https://github.com/EsotericSoftware/spine-runtimes)、[许可条款](https://esotericsoftware.com/spine-runtimes-license) | 自行获取匹配源版本；本地构建说明见 `unity-runtimes` |
| Unity 包 | [Unity Package Manager](https://docs.unity3d.com/Manual/Packages.html) | 按目标项目 manifest/lock 解析，私人备份不公开 |
| 系统工具 | [Brewfile](Brewfile)、[工具目录](TOOLS.md) | 使用官方安装渠道；不把某台主机的安装复制成产品默认依赖 |

使用 [providers.example.json](providers.example.json) 配置同一个工具 ID 的本机命令，并通过 `GREA_PROVIDERS` 指定配置文件。该配置受信任且可执行，不从待分析游戏包自动加载。保留版本、来源、哈希和许可证；本仓库不会自动下载或接受供应方条款。

`unity-export-assets`、`webgl-xxtea-decrypt` 仅保留兼容 ID：它们原有的项目派生实现不公开，使用者须显式提供自己的适配器。缺失依赖返回 unavailable，不能仅凭包装脚本存在判断已安装。

## 设计参考

[UPSTREAM.json](UPSTREAM.json) 记录 REA 架构参考与 MCP SDK 来源。REA 用于设计研究，未复制其引擎实现。新增第三方源码前必须独立核对来源、许可和通知保留要求，不能只修改署名后纳入 MIT。
