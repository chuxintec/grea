# 工具源码与自有验证样例

过渡期旧 Python 执行能力保留在 [src/grea/tools](../src/grea/tools)，通过 `bin/grea` 和 [registry.json](../registry.json) 调度；本目录保存其他技术栈的源码、构建输入和跨工具自有验证样例，不建立第二套工具 ID。

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
| unity/lifecycle-sample | 自有原生接续／可玩增量验证输入与Editor API示例 |
| lifecycle-feedback | 合成事件→配置／兼容／回退预览→本地交接调用示例；复用已有工具 |

按任务选工具见 [工具目录](../TOOLS.md)，参数见 [工具说明](../docs/tools/制品与资源检查.md)，第三方接入见 [providers](../docs/providers/README.md)。脚本路径不是工具身份；正式调用使用已登记 ID。

外部转换编排集中在 `src/grea/integrations/monkey/`：identity 固定工具，pipeline 处理计划与执行，audit 核新版产物，package/slice/handoff 保留版本化旧合同。`src/grea/tools/monkey_pipeline.py`、`monkey_bridge.py` 只作为登记入口；解析器由独立 monkey 产品维护。

工程操作实现按[beaver交接](../proposals/beaver-execution-handoff.md)转移，接收验证前保留原实现；新执行能力归 beaver，恢复解析归 monkey，GREA 以 Skill 和薄调用为主。
