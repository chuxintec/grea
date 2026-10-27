# Unity · 脚本与生成契约

> **何时读**：编写或命名脚本、划分生成代码与人工代码、设计或执行工程生成（plan/generate/recover）、处理重复生成与人工修改冲突时。
> **读完产出**：脚本角色与所有权表、生成计划与生成清单、冲突与恢复回执。

本篇属于 [工程标准 v1](Unity工程结构与开发规范.md)（`grea-unity-project` 1.0.0）。生成后的验收见 [工程标准验收](Unity工程标准验收.md)。

## 通用脚本与生成所有权

**SCR-01 脚本角色**：按职责命名，例如 Session、Controller、Presenter、View、Config、Adapter、Validator；名称只作导航，不能用后缀证明分层完成。MonoBehaviour 类型与脚本文件名匹配；命名空间由项目前缀＋层＋模块组成。接口只在替换实现、隔离边界或测试替身确有价值时建立。

| 种类 | 维护者 | 更新方式 |
| --- | --- | --- |
| 框架包实现 | GREA 框架维护者 | 锁定版本升级；项目不直接改安装副本 |
| 模块初始骨架 | 生成器首次创建，随后项目维护者接管 | 清单标记 seed-once；再次生成只能提出迁移建议，不能覆盖 |
| 可再生代码（明确 .g.cs） | 生成器 | 标明生成器/模板版本及所有权；输入未变时内容与 GUID 不变 |
| 人工实现与项目适配器 | 项目维护者 | 不进入再生成写入范围；通过接口、partial 扩展点或组合接入 |
| Editor 校验/构建脚本 | 包或项目对应所有者 | 与 Runtime 编译隔离；构建不能隐式执行生成 |

partial 只用于明确的生成/人工接缝，同一类放同一职责范围；不能把共享全局状态拆成多个 partial 后宣称模块已解耦。类型/字段/程序集迁移须分析 Unity 序列化与反射，按目标版本采用适当迁移方案并在 Editor 回读，不只靠编译。

**SCR-02 执行规则**：Unity API 调用遵循主线程约束；异步任务可观察、可取消，事件订阅成对清理。避免在普通 Update 中做磁盘读写、全场查找或无界分配；是否缓存/池化依实际生命周期与测量决定。UnityEngine.Object 使用 Unity 对象有效性语义，不把已销毁对象的托管包装当有效资源。

**SCR-03 数据与失败**：配置参数集中定义并校验，禁止散落业务魔法值和硬编码资产绝对路径。必需绑定失败返回结构化错误；不要 catch 后静默继续进入“成功”。诊断携带源模块/对象/字段和上下文，不输出凭据和完整用户数据。反射、字符串类型名、原生插件和 IL2CPP/AOT 裁剪路径需列入构建验收。

## 自动生成契约

本节包含静态规划已实现的只读入口与后续生成设计。**plan_unity_project / validate_unity_project 保持静态规划静态范围；工程生成新增 plan_unity_generation / generate_unity_project / recover_unity_generation，实际限制见 [工程生成](../../grea/references/Unity指南.md)。** 当前 validate 不接收 Editor/PlayMode/Player 层级参数；静态规划 plan 不执行或授权写入，实际范围见 [静态规划使用说明](../../grea/references/Unity指南.md)。后续实现必须按 [统一接口](../../grea/references/接口与证据说明.md) 更新 contracts.py、registry.json、schema 和 CLI/MCP 同源分发。

### 输入与操作边界

| 操作与阶段 | 输入 | 输出和写入范围 |
| --- | --- | --- |
| plan_unity_project（静态规划静态） | 项目根、配置文件、new/adopt/refactor 模式、模块范围、比较基线 | 静态规划返回 stdout 设计计划：new 的 create 意图、adopt 的 preserve、refactor 的 review；实际移动/修改及冲突合并留工程生成 |
| plan_unity_generation | 锁定工程生成配方、new/adopt | 只读文件级 create/preserve 条目、planId 与身份；adopt 不认领资产 |
| generate_unity_project | 工程生成 planId、明确新工程根、Evidence 下的新 run_dir | 隔离 Editor 创建/回读，成功后原子发布新工程；已生成工程只校验保留，不覆盖 |
| recover_unity_generation | 原 run_dir、相同 profile/生成器/包身份 | 只在明确退出且检查点完整时续作；有冲突保留并返回 recovery_required |
| validate_unity_project（静态规划静态；其余待实现） | 静态规划接收项目根、配置、模式和范围；Editor/PlayMode/Player 参数留后续实现 | 分层 findings 与证据；默认报告问题，不自动修复；需运行的层级使用明确目标和前提 |

static 层只读源码；Editor/PlayMode/Player 层会导入、产生缓存/日志或使用隔离 QA 存储，应在执行契约声明这些副作用。使用隔离验证副本或已获准的目标，核对验证前后 Assets/ProjectSettings 指纹；发现隐式修改时单列报告，不称作纯只读检查。

上述为 MCP snake_case 名称；CLI 使用对应 kebab-case，未实现入口不注册。name 只有在实现、schema、错误契约与测试齐备后才可注册；不提前暴露不可执行的占位工具。

new 只允许空的新工程目标，不能覆盖已存在 Unity 工程；adopt 只盘点现状、配置和例外，默认不改资产；refactor 必须有获准的模块范围及行为基线，不能把整理文件自动扩大为 UI/存档/框架替换。调用方已有明确授权时直接在该范围执行，不为每个文件增加人工批准步骤。

### 计划和生成清单

**GEN-01 可追溯输入**：计划包含 schemaVersion、planId、mode、项目身份、规范/框架/模板/生成器版本与哈希、工具链身份、配置哈希、纳入范围的文件内容/meta/GUID 指纹、依赖锁、旧/新路径、所需 Editor 操作、所有权及冲突。planId 绑定这些输入；执行前重读输入，变化返回 stale_plan 并重新规划，不能继续使用旧清单。

每个计划项至少包含 action、logicalId、source/target、expectedBeforeHash（新文件为不存在）、owner、preserveGuid、requiredBindings、reason、validationIds。所有输出解析后均在授权根内；拒绝绝对路径注入、.. 越界、符号链接逃逸、大小写/Unicode 冲突和 Windows 保留名。历史证据只引用，不改写。

工程生成清单位于 Unity 工程根 `Tools/Generated/manifests/`，记录相对路径、逻辑资产 ID、实际 GUID/必要 fileID、内容及 meta 哈希、seed-once/generated/human/package 所有权、生成版本和前次清单身份。它是项目恢复所需元数据，可按项目规则纳管；运行日志与含机器路径的过程回执放本次项目 Evidence，不随公共 GREA 分发。时间戳和 runId 属于执行回执，不写入每个再生资产造成无意义差异。

**GEN-02 重复生成**：输入和模板版本相同且生成物未变时，第二次执行不改文件内容、不更换 GUID、不增加对象/监听/配置、不新建另一套目录。新资产仅首次生成身份并写入清单；跨全新工程不要求相同 GUID，但归一化结构和绑定应等价。同工程重复运行必须保留已有身份。

**GEN-03 人工修改保护**：先比较当前文件与上次生成清单。人工文件永不覆盖；seed-once 文件只首次创建；已修改的 generated 文件默认报冲突，给出差异和迁移建议。支持字段级合并前不得把整个 Prefab 序列化重写。未知归属文件只报告，不移动、不删除。清单中消失的模板资产只能提出退休候选，不能借重生成自动删除。

### 执行阶段与失败恢复

1. **预检**：验证 profile、目标版本组合、依赖、路径和写入范围；定位正在使用工程的 Editor，检测并发修改。不能另开一个 Editor 争用同一 Library。
2. **计划**：生成只读差异、风险和验证项；原资源身份、动态键、行为基线缺失时将相应项标为 blocked，其余独立只读工作可继续。
3. **暂存**：将可确定的源码/配置写入项目内非 Assets 的本次暂存目录，核验内容；记录待写文件的前像与回滚映射。已授权目标外不落临时数据。
4. **Editor 应用**：使用当前已验证 Editor 接口，通过 AssetDatabase/PrefabUtility 创建、移动和绑定。分批处理，导入/编辑锁必须在 finally 中释放；等待真实编译与域重载结束。
5. **回读**：核对生成身份、引用、字段、依赖与编译结果；写入实际状态的清单和回执，不先标完成再等待后台任务。
6. **验收**：执行本次要求的静态、Editor、PlayMode、Player 门槛；清单完成不等于行为等价。

**GEN-04 中断处理**：每步有开始/完成和产物身份。超时后先核对 Editor 是否仍在执行，再决定取消或恢复；不盲目重放整个生成。回滚只针对本次已记录改动，在通过当前指纹确认未被用户修改后，经 Editor 恢复资产与 .meta；不能执行整个工程的 git reset、删除 Library 或覆盖后续人工工作。不能安全自动回滚时标 recovery_required，保留日志、前像、受影响清单和下一步。

**GEN-05 执行失败分类**：至少区分 invalid_profile、unsupported_combination、missing_dependency、path_conflict、ownership_conflict、stale_plan、editor_unavailable、compile_failed、binding_failed、verification_failed、recovery_required。外层仍使用 GREA 现有 ok/partial/error 回执，具体错误码在实施时纳入正式契约；已有 API 不因本文自动变更。

生成不内置支付/广告凭据，不读取项目外私人缓存，不自动下载未知来源包，不把本机 .private 库存作为公开模板必需内容。Editor 连接、安装/许可和依赖恢复遵循既有 [执行路线](../../grea-delivery/references/Unity编辑器连接与任务执行.md)。
