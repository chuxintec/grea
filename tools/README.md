# 非 Python 工具与 Unity 源码

Python 产品能力统一维护在 [src/grea/tools](../src/grea/tools)，通过 `bin/grea` 和 [registry.json](../registry.json) 调度；本目录保存其他技术栈的源码与构建输入，不建立第二套工具 ID。

| 目录 | 内容 |
| --- | --- |
| cocos | 可选 Acorn AST 解析与依赖锁；Python 编排在 src/grea/tools |
| unity/assembly-audit | 可选 .NET/Cecil 元数据读取器源码和锁，不加载被检查 DLL |
| unity/framework | Foundation、uGUI、Editor 包源码、稳定 meta 与包测试 |
| unity/adapters | 可选程序集适配包 |
| unity/templates | 按用途命名的计数装配与最小工程模板 |
| unity/audit、unity/packages | Editor 审计和包安装辅助 C# |
| unity/spine | Spine 运行时构建配置与许可；不附带 vendor |
| dotnet | 托管程序集清理工具源码 |

按任务选工具见 [工具目录](../TOOLS.md)，参数见 [工具说明](../docs/tools/制品与资源检查.md)，第三方接入见 [providers](../docs/providers/README.md)。脚本路径不是工具身份；正式调用使用已登记 ID。
