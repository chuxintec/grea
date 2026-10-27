# 数据契约与能力目录

本目录全部 JSON 由 `scripts/generate_contracts.py` 从 `src/grea/contracts.py` 、`src/grea/unity_project_contracts.py` 、`src/grea/cocos_contracts.py` 、`src/grea/native_exit_contracts.py` 、`src/grea/authoring_contracts.py` 、`src/grea/change_contracts.py` 和 `src/grea/evidence_contracts.py` 生成。修改源码定义，再生成；CI 用 `--check` 防止漂移。不要手工改 JSON 来绕过运行时校验。

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

实际调用从 [使用指南](../plugin/skills/grea/references/使用指南.md) 开始。项目输入示例见 [静态配置](../tests/fixtures/unity-project-v1.json) 和 [生成配置](../tests/fixtures/unity-generation-v1.json)；先核对各自支持范围。

## 有限制作输入

`unity-config-authoring.schema.json` 定义闭合标量字段表的制作契约；`unity-native-assets.schema.json` 定义明确 Sprite 与 Transform 动画切片。跨字段范围、主键、目标、坐标和生成所有权由工具完整预检。两者由 `src/grea/authoring_contracts.py` 生成，不改变既有操作 Schema；具体边界见 [制作链](../plugin/skills/grea/references/providers/unity-authoring.md)。

`change-contract.schema.json` 的可选 art_production 约束换皮阶段与后置调优；`art-ledger.schema.json` 描述持续选样/资源/设定与Spine生产状态，供 theme_assets validate-ledger 消费。结构/引用声明通过不等于真实媒体、用户批准或Editor/Player验收；使用说明见 [主题映射](../plugin/skills/grea/references/providers/theme-assets.md)。

## 生命周期与本地运营数据

change-contract.schema.json以oneOf显式分开旧v1 ui_ux与有界变更v2；operations.json中的stage/work_mode/delivery_level只作合同/规划，不授予权限。art-ledger新增可选provenance，旧记录仍兼容。operations-event.schema.json由lifecycle_data_contracts生成，定义本地只读事件v1；IANA时区、重复ID/回执、窗口等语义由工具检查。参见[兼容及预览](../plugin/skills/grea/references/providers/lifecycle-analysis.md)。

## monkey 批量工具链

[monkey-pipeline.schema.json](monkey-pipeline.schema.json)由`src/grea/monkey_contracts.py`从版本化操作表生成，定义plan请求与预算；实际路径、完整输入引用、版本/hash和执行前后身份另由运行时验证。不是转换结果或原生验收证明。

`beaver-operation.schema.json` 由命名转发表生成，限定旧0.1/0.2及固定0.3候选07和08/元数据等价09的49个路由；`x-beaver-versions`标适用版本，`x-beaver-capability`给出精确声明ID或apply的动态能力入口。版本/producer、绝对路径、实现锁、预期hash及预算由运行时校验；debug宽高成对也进入Schema。GREA封装schema_version1不等于provider的production spec3、config3 spec2，不复制其工程执行Schema。

`beaver-result.schema.json` 为两个固定0.3实现接入使用的beaver-result/1结果外壳校验；约束producer、状态、诊断/制品和验证字段，保留provider的data。旧0.1/0.2合同和摘要算法不因此改变；Schema存在不证明原生、游戏采用或0.3整版通过。

其中actualChanges逐项为非空路径string或object摘要，不统一包装；数字/null/数组等不合法。外层校验失败可能发生在原生已写入之后，需结合executed、原stdout/退出码及事务见证判断，不能以Schema拒收推断零写入或回滚成功。
