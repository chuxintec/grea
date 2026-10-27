# 可选 Il2CppInspectorRedux 辅助解析器

`il2cpp-inspector` 是可选的辅助解析器，不是 Unity 包恢复的唯一工具。通过 [官方仓库](https://github.com/LukeFZ/Il2CppInspectorRedux) 获取适配主机的 CLI 与许可证说明，并按所选发行版准备 .NET。发行包和 .NET 安装副本不随 GREA 公开源码分发。

## GREA 适配器调用

建议用 `GREA_PROVIDERS` 指向已核验的本地安装。既有 macOS ARM64 适配器 `bin/il2cpp-inspector` 预期在 GREA 私有根下存在以下布局：

```text
.private/providers/il2cpp/Il2CppInspectorRedux/2026.2/cli/Il2CppInspectorRedux.CLI-osx-arm64/
.private/runtimes/dotnet/10
```

目录缺失时适配器返回 `unavailable`。从已安装 GREA 根目录通过 `list-tools`、`describe-tool` 核实当前工具定义、路径与参数，再调用已登记的 `il2cpp-inspector` 工具；不要因历史路径推断安装成功。

适配器在本机回环地址使用随机端口，默认看门狗为 180 秒。超时后输出可能不完整，应作为部分结果处理并检查诊断。

## 结果边界

针对当前输入核对 Unity 与 metadata 版本、警告及输出完整性。stub 不能当作原方法实现；帮助调用通过不代表业务解析成功。不要自动执行导出的注入工程。将 CLI 输出、stub、反编译伪代码和可恢复方法体按证据等级分别记录。
