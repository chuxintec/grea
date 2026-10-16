# 数据契约与能力目录

本目录全部 JSON 由 `scripts/generate_contracts.py` 从 `src/grea/contracts.py` 、`src/grea/unity_project_contracts.py` 、`src/grea/cocos_contracts.py` 、`src/grea/native_exit_contracts.py` 和 `src/grea/authoring_contracts.py` 生成。修改源码定义，再生成；CI 用 `--check` 防止漂移。不要手工改 JSON 来绕过运行时校验。

| 文件 | 类型 | 用途与消费者 |
| --- | --- | --- |
| [operations.json](operations.json) | 操作目录，包含输入 Schema | CLI/MCP 集成方查询操作与参数；不是单一 JSON Schema |
| [result.schema.json](result.schema.json) | JSON Schema | 校验统一响应中的状态、错误、证据与限制 |
| [cocos-evidence.schema.json](cocos-evidence.schema.json) | JSON Schema | 离线结构解析的身份、输出和状态；不证明 Unity 运行验收 |
| [unity-native-exit-policy.schema.json](unity-native-exit-policy.schema.json) | JSON Schema | 已知来源机制的退出清单，不能作为豁免 |
| [unity-player-policy.schema.json](unity-player-policy.schema.json) | JSON Schema | 实际 DLL 的明确类型/引用检查项 |
| [unity-player-manifest.schema.json](unity-player-manifest.schema.json) | JSON Schema | build/source/platform/backend 与完整 DLL 集合摘要 |
| [unity-project.schema.json](unity-project.schema.json) | JSON Schema | 项目配置 profile：路径、工具链、模块、存档与例外 |
| [unity-plan.schema.json](unity-plan.schema.json) | JSON Schema | 只读设计计划；不得作为生成执行许可 |
| [unity-generation-plan.schema.json](unity-generation-plan.schema.json) | JSON Schema | 生成器计划：输入身份、所有权、变更及执行前提 |
| [unity-manifest.schema.json](unity-manifest.schema.json) | JSON Schema | 已生成文件的归属、哈希与恢复身份 |
| [unity-report.schema.json](unity-report.schema.json) | JSON Schema | 静态检查结果；通过不等于已运行 Unity |
| [unity-capabilities.json](unity-capabilities.json) | 能力目录 | 声明支持组合与具名参考工程证据；不是 JSON Schema，也不把参考工程结果套到任意项目 |

运行时导入 Python 定义；这些导出文件用于外部集成和人工查阅。各 Schema 和目录均保留稳定文件名。JSON 结构兼容性与文档命名是不同事项，不能因整理研发阶段而合并不同语义的计划。

```sh
python3 scripts/generate_contracts.py
python3 scripts/generate_contracts.py --check
```

实际调用从 [使用指南](../docs/使用指南.md) 开始。项目输入示例见 [静态配置](../tests/fixtures/unity-project-v1.json) 和 [生成配置](../tests/fixtures/unity-generation-v1.json)；先核对各自支持范围。

## 有限制作输入

`unity-config-authoring.schema.json` 定义闭合标量字段表的制作契约；`unity-native-assets.schema.json` 定义明确 Sprite 与 Transform 动画切片。跨字段范围、主键、目标、坐标和生成所有权由工具完整预检。两者由 `src/grea/authoring_contracts.py` 生成，不改变既有操作 Schema；具体边界见 [制作链](../docs/providers/unity-authoring.md)。
