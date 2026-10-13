# Unity 项目配置与只读规划（M1）

M1 已提供 `validate-unity-project`、`plan-unity-project`；MCP 名称为 `validate_unity_project`、`plan_unity_project`。两个入口共用实现，只读指定项目，结果输出到 stdout，不创建目录、生成代码/Prefab、安装依赖、打开 Unity 或修改项目。`generate-unity-project` 尚不存在。

工程标准见 [标准 v1](../skill/references/20-标准工程目录与类型归类.md)，后续阶段见 [落地计划](11-Unity工程标准落地计划.md)。

## 1. 配置与 Schema

将 [合成配置示例](../tests/fixtures/unity-project-v1.json) 复制到一个独立测试目录，命名为 `grea-project.json`，再按目标修改。示例不是现有游戏配置；`UnityProject` 为尚不存在的目标子目录。M1 本身不执行复制或写配置。已有工程采用时需明确指定现有路径及匹配的依赖锁指纹，不直接套用示例中的 null 指纹。

| 产物 | 权威定义与用途 |
| --- | --- |
| [项目 Schema](../schemas/unity-project.schema.json) | profile 字段/类型/枚举与未知字段拒绝 |
| [计划 Schema](../schemas/unity-plan.schema.json) | 设计条目、范围、输入/计划指纹、阻塞项与静态报告 |
| [生成清单 Schema](../schemas/unity-manifest.schema.json) | 未来生成物的逻辑 ID、路径、GUID/fileID、内容/meta 哈希、所有权；M1 只冻结文档契约，不生成或应用清单 |
| [报告 Schema](../schemas/unity-report.schema.json) | 静态发现、库存、检查层级与未执行状态 |
| [能力矩阵](../schemas/unity-capabilities.json) | 精确参考组合与验证层级，不代表泛化的 Unity 版本支持 |

Schema 与矩阵的源定义在 `src/grea/unity_project_contracts.py`，经 `contracts.py` 聚合，由 `scripts/generate_contracts.py` 统一生成；API 参数由 `contracts.py` 定义。不要直接修改生成 JSON。JSON Schema 校验结构；路径可移植性、目录关系、依赖指纹与模块唯一性还需运行静态校验器，不能仅用 Schema 通过判断配置可执行。

所有字段显式提供：身份/namespace、paths、toolchain、dependencyLock、template、frameworkPackages、features、modules、scenes、assetBackend、玩家/QA save namespace、exceptions。路径相对项目根；场景和 scope 相对 Unity 工程。M1 的模块名和 namespace 使用 ASCII C# 标识符，目录支持中文和空格，同一模块不能大小写碰撞；QA 与玩家存储标识必须不同。lifecycle 必选，ui 需要 resources。exceptions 只记录，不抑制 M1 的发现。

首个参考组合：Unity `6000.6.2f1`、URP `17.6.0`、uGUI `2.6.0`、legacy input、Catalog、macOS arm64/Mono。编辑器和内置包版本来自 2026-10-13 的本机只读元数据核对；macOS 模块目录存在。**没有打开 Editor、验证许可或运行 Player**。矩阵仅把静态规划标为支持；Editor、PlayMode、Player 为 not_run，generation 为 not_implemented。

`grea-minimal-2d / 0.1.0-design` 是设计配方标识，尚无可执行模板或框架包。未知模板、其它组合、声明尚未实现的框架包会产生发现，不自动换成默认组合。M1 仅核对固定 registry/built-in 风格的包版本与锁；Git/local/file 等依赖来源尚不解析，也不读取它们指向的工程外目录。

## 2. 调用

以下路径是占位值，请先准备自己的隔离目录与配置。请求文件也可通过 `--input /path/request.json` 提供。

```sh
./bin/grea validate-unity-project '{"project_root":"/path/isolated-case","mode":"new"}'
./bin/grea plan-unity-project '{"project_root":"/path/isolated-case","mode":"new"}'
```

省略 profile 时读取项目根的 `grea-project.json`；project_root 必须存在且是非符号链接目录。profile 和 baseline 必须是项目根内的相对路径，不能传绝对路径或历史机器路径。工具只返回 JSON；如需保存，调用方另选新报告文件，不把 shell 重定向指向待检查的输入文件。

| mode | 前置条件 | 计划行为 |
| --- | --- | --- |
| new | Unity 目标不存在或为空，依赖锁指纹为 null | 给出项目版本/包配置、模块源码和场景的设计性 create 条目；不会实际生成 |
| adopt（默认） | 已有 Assets、Packages、ProjectSettings；配置与版本/锁匹配 | 盘点范围内文件，全部 preserve；不搬目录，不改代码 |
| refactor | 已有工程、明确 scope、Evidence 范围内的现存 baseline 文件 | 范围内仅给 review 条目；不作自动移动/删除/改写决策，不证明行为等价 |

```sh
./bin/grea plan-unity-project '{"project_root":"/path/isolated-case","mode":"refactor","scope":["Assets/Game/Presentation"],"baseline":"Evidence/baseline.json"}'
```

baseline 只核对文件存在与哈希，不认证其来源或行为结论。scope 仅允许 Assets、Packages、ProjectSettings 下互不重叠的范围。版本文件、依赖锁、声明场景及必要相邻 meta 仍作为全局控制输入读取并绑定指纹；计划条目严格限制在 scope 内。范围外程序集或包提供的引用会标待解析，不扩展为全工程/Editor 验证。

默认最多 2000 个库存条目、64 MiB 文件内容；JSON 解析另限单文件 1 MiB，发现项上限 10000，单个 asmdef 最多 1000 条显式引用。用 `max_files`、`max_bytes` 在允许上限内显式调整。超预算返回 RESOURCE_LIMIT，不产出一个伪完整计划；工具不启动外部进程。

## 3. 结果与状态

外层沿用 grea 公共回执；result 按上表的报告/计划 Schema 解读。

- CLI 退出 0 / status=ok：本次静态检查或规划处理完成且无发现。**不表示工程符合完整标准或可以生成**。
- CLI 退出 1 / status=partial：返回可审阅的 findings；包括不支持组合、版本/依赖缺失、meta 或程序集问题等。warning 也保留待处理状态。
- CLI 退出 2 / status=error：参数/配置结构、路径、输入变化、预算等使本次请求失败；没有修改目标文件。

报告的 `staticStatus` 只覆盖声明输入、文件系统与显式 asmdef 元数据。`compliance` 始终为 `not_assessed`，A1–A5 均为 not_run；A0 的局部检查不能代替 Editor 导入类型、动态资源寻址或生命周期验证。

所有计划 `generationReady=false`，blockers 至少包含 `GENERATION_NOT_IMPLEMENTED`。create 是设计意图；不会生成 .cs 内容、.meta、GUID 或 Prefab。已有文件默认 human；M1 不读取/合并历史生成所有权清单，不声称能保护字段级人工覆盖——这些由 M3 实施。

planId 绑定 profile 原始字节、范围/模式、相对文件库存、目录成员/缺失状态、meta/GUID、依赖与版本文件、baseline、参考矩阵及规划器/文档契约身份。重复请求在输入不变时结果稳定。将上次 planId 放入 `expected_plan_id` 重检；变化返回 STALE_PLAN。该检查是当前观察，不是对未来写入的授权或文件锁；未来生成仍须重新验证输入。

常见请求错误：INVALID_PROFILE、INVALID_PROJECT_JSON、INVALID_PROJECT_PATH、INVALID_PROJECT_ROOT、BASELINE_REQUIRED、PATH_CONFLICT、UNSAFE_PROJECT_ENTRY、STALE_INPUT、STALE_PLAN、RESOURCE_LIMIT、CANCELLED。项目发现使用 report.findings 的 code/path/ruleId，不与请求失败混淆。

## 4. 静态检查边界

已覆盖：路径越界/保留名称/重叠，符号链接与特殊文件拒绝，读取中变化，大小写/Unicode 碰撞，meta 缺失/无效/孤立与 GUID 重复，版本/依赖锁一致性，显式 asmdef 名称与 GUID 引用、循环、层间方向、Runtime→Editor/Tests 依赖以及纯规则程序集的 noEngineReferences 声明。

不覆盖：C# 类型分析、隐式 Assembly-CSharp 引用、反射/动态加载、包恢复后实际可解析性、序列化 fileID 绑定、Prefab 视觉、Unity 编译、许可证、Editor 连接和 Player。不会执行项目脚本、csproj 或安装钩子。POSIX 使用目录文件描述符和 no-follow 防止读取时祖先目录被替换为软链接；Windows 路径实现是可移植候选，尚未原生验收。

CLI/MCP 同源，两个工具 ID 同时进入 registry。原有工具 ID 保留；高级 run-tool 会按既有契约创建自己的日志目录，**只读保证指两个直接静态入口不会写目标工程**，不能把外层日志写入混为规划器修改项目。已运行的 MCP 长连接需要重新连接才能加载新增契约，测试使用全新 stdio 连接。

## 5. 复验

```sh
./.venv/bin/python scripts/generate_contracts.py --check
./.venv/bin/python -m unittest discover -s tests -p test_unity_projects.py -v
./.venv/bin/python -m unittest discover -s tests -v
```

测试仅创建 TemporaryDirectory 内的合成工程，覆盖两种目录布局、只读前后字节、稳定/过期计划、成功/partial/error 的 CLI/MCP 一致性及失败边界。不测试或修改工作区现有游戏。
