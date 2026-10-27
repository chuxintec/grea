# 第三方工具接入

这些文档说明如何取得和配置提供方：monkey 与 beaver 是完整执行链必选工具，其他供应方按任务准备；目录中不分发工具二进制。官方来源与许可边界统一见 [第三方依赖](../../THIRD_PARTY.md)，实际命令通过仓库根的 providers.example.json 和 GREA_PROVIDERS 配置。

- [Frida](Frida接入.md)：本机客户端与设备端版本配对，以及操作授权边界。
- [IL2CPP 辅助解析器](IL2CPP解析器接入.md)：Il2CppInspectorRedux 的安装与调用限制。
- [Android 旧模拟器](Android旧模拟器接入.md)：ARM32 输入的可选兼容环境；[历史来源](android-emulator-provenance.json)。

Spine 的构建配置位于 [tools/unity/spine](../../tools/unity/spine)，包备份/恢复工具位于 [tools/unity/packages](../../tools/unity/packages)。第三方原件和本机安装不需要在公开根目录创建占位说明文件。

- [Cocos 离线解析与 AST 证据](cocos-static.md)：Python 数据解析及可选 Node provider；不执行源 JavaScript。
- [Unity 原生退出检查](unity-native-exit.md)：静态候选、Editor 观察与实际 Mono DLL 元数据分层；可选 Cecil provider。
- [Unity 有限制作链](unity-authoring.md)：两种配置 schema、Sprite/Clip 原生制作、Editor 身份差分和冲突保护；不推断整个源引擎。

- [Creator 3.4.1、CCON 与 System.register](cocos3-evidence.md)：有限离线证据。
- [配置、表现与性能预检](observation-tools.md)：显式合同与现场采样边界。

- [Windows 原生供应方与桌面复验](windows-native.md)：核心、可选 provider、Codex 与 Unity 各自的原生验收边界。

开发候选：[调研归一](research.md)、[Cocos目标](cocos-target.md)、[Go六服框架](server-go.md)；均保留有限支持与实测边界。

- [monkey转换接续](monkey.md)：显式配置、固定版本、候选与模块包。
- [资产总览与规格](asset-preview.md)：中文标签联系表、来源元数据、尺寸和可选RGBA色数。

- [生命周期兼容与只读分析](lifecycle-analysis.md)：配置/save差异、事件与经济流、配置候选；无生产写入。

- [beaver工程开发](beaver.md)：发现、固定身份、只读工程检查和旧实现交接；没有 provider 时明确 needs_action。
