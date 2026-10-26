# beaver v0.2 模块登记

执行[通用规范](/Users/wangmeng/Documents/Manager/standards/MODULE-DEVELOPERS.md)，human01a1770e-af1d-7510-b494-867958dddf0e已原生核验。共享工作区基线b67a164；无递归派生。主开发负责CLI/批处理事务/公共Schema/BeaverBatch.cs/全部Editor与集成。

| 实例 | 模块与可写区 | 模型目标/观测 | 状态 |
|---|---|---|---|
| /root/reference_graph | references.py、test_references.py、REFERENCE-GRAPH.md；.private/v02冻结副本回执 | gpt-6-luna high / 底层实际配置无独立回读 | 已交付，主开发集成 |
| /root/debug_sessions | debug.py、test_debug.py、DEBUG-SESSIONS.md；loading_keys.py及其测试文档 | gpt-6-luna high / 底层实际配置无独立回读 | 已交付并集成，viewport与有界日志验证通过 |
| /root/native_ui | BeaverBatchUI/ListView/SafeArea.cs、NATIVE-UI.md | gpt-6-luna high / 底层实际配置无独立回读 | 已交付并集成，原生编译及两个隔离Player验证通过 |

各模块均已给版本、准确基线/工具输入、禁止区和必要验证合同；没有合适旧实例，首次按三个独立模块新建。正式游戏、Go、存档和其他工具源码只读。
