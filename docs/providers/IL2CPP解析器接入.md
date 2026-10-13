# 可选 Il2CppInspectorRedux

从 [官方仓库](https://github.com/LukeFZ/Il2CppInspectorRedux) 获取匹配主机的 CLI 与许可说明，按所选版本准备 .NET。发行包和 .NET 安装副本不随公开源码分发。

建议通过 GREA_PROVIDERS 配置 `il2cpp-inspector`。既有本机 `bin/il2cpp-inspector` 适配器预期仓库根下私有安装目录 `.private/providers/il2cpp/Il2CppInspectorRedux/2026.2/cli/Il2CppInspectorRedux.CLI-osx-arm64/` 及 `.private/runtimes/dotnet/10`；目录缺失时返回 unavailable。包装器使用本机回环随机端口与默认 180 秒看门狗，超时输出可能不完整。

以当前输入检查 Unity/metadata 版本、警告和输出，不把 stub 当原方法实现，不因帮助调用通过宣称业务解析成功。不要自动执行导出的注入工程。
