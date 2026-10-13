# 第三方工具接入

这些文档说明如何取得和配置可选提供方；目录中不分发工具二进制。官方来源与许可边界统一见 [第三方依赖](../../THIRD_PARTY.md)，实际命令通过仓库根的 providers.example.json 和 GREA_PROVIDERS 配置。

- [Frida](Frida接入.md)：本机客户端与设备端版本配对，以及操作授权边界。
- [IL2CPP 辅助解析器](IL2CPP解析器接入.md)：Il2CppInspectorRedux 的安装与调用限制。
- [Android 旧模拟器](Android旧模拟器接入.md)：ARM32 输入的可选兼容环境；[历史来源](android-emulator-provenance.json)。

Spine 的构建配置位于 [tools/unity/spine](../../tools/unity/spine)，包备份/恢复工具位于 [tools/unity/packages](../../tools/unity/packages)。第三方原件和本机安装不需要在公开根目录创建占位说明文件。
