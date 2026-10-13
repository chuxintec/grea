# 数据契约与能力目录

本目录全部 JSON 由 `scripts/generate_contracts.py` 从 `src/grea/contracts.py` 和 `src/grea/unity_project_contracts.py` 生成。修改源码定义，再生成；CI 用 `--check` 防止漂移。不要手工改 JSON 来绕过运行时校验。

| 文件 | 类型 | 用途与消费者 |
| --- | --- | --- |
| [operations.json](operations.json) | 操作目录，包含输入 Schema | CLI/MCP 集成方查询操作与参数；不是单一 JSON Schema |
| [result.schema.json](result.schema.json) | JSON Schema | 校验统一响应中的状态、错误、证据与限制 |
| [unity-project.schema.json](unity-project.schema.json) | JSON Schema | 项目配置 profile：路径、工具链、模块、存档与例外 |
| [unity-plan.schema.json](unity-plan.schema.json) | JSON Schema | 只读设计计划；不得作为生成执行许可 |
| [unity-generation-plan.schema.json](unity-generation-plan.schema.json) | JSON Schema | 生成器计划：输入身份、所有权、变更及执行前提 |
| [unity-manifest.schema.json](unity-manifest.schema.json) | JSON Schema | 已生成文件的归属、哈希与恢复身份 |
| [unity-report.schema.json](unity-report.schema.json) | JSON Schema | 静态检查结果；通过不等于已运行 Unity |
| [unity-capabilities.json](unity-capabilities.json) | 能力目录 | 声明支持组合与具名参考工程证据；不是 JSON Schema，也不把参考工程结果套到任意项目 |

运行时导入 Python 定义；这些导出文件用于外部集成和人工查阅。六个 Schema、两个目录都保留稳定文件名。JSON 结构兼容性与文档命名是不同事项，不能因整理研发阶段而合并不同语义的计划。

```sh
python3 scripts/generate_contracts.py
python3 scripts/generate_contracts.py --check
```

实际调用从 [使用指南](../docs/使用指南.md) 开始。项目输入示例见 [静态配置](../tests/fixtures/unity-project-v1.json) 和 [生成配置](../tests/fixtures/unity-generation-v1.json)；先核对各自支持范围。
