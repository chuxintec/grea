# v0.6.0.dev1 全量 C# 初稿与完整候选主链

本地开发出口，2026-10-26。依据最新全量导出裁定：源码可取得时默认批量生成实际 C#，类型/API/语法错误列为接续修复项，不以逐方法合同或全量编译作为导出门。正式安装仍未调整，本次无发布、推送或全局安装。

## 完整输入与实际输出

公开 `convert --reuse-candidate ... --expected-candidate ... --target unity6 --out ... --offline` 已实际生成同一独立工程。3份样例项目冻结JS共9,358,387字节，源及所有方法/字段字节范围、SHA、目标文件/成员和详情分片位置均核验；源程序没有执行。

| 分母 | 主源 | App | SubContext | 合计 |
|---|---:|---:|---:|---:|
| 源类 | 928 | 215 | 14 | 1,157 |
| 索引方法/已生成 | 16,384/16,384 | 3,171/3,171 | 16/16 | 19,571/19,571 |
| 辅助函数 | 20,131 | 7,322 | 360 | 27,813 |
| 实际函数记录 | 36,515 | 10,493 | 376 | 47,384 |
| C#文件 | 16,441 | 7,462 | 250 | 24,153 |
| 字段记录 | 2,655 | 1,041 | 10 | 3,706 |
| 独立字段声明 | 2,513 | 1,005 | 10 | 3,528 |
| 初始化记录 | 1,031 | 409 | 0 | 1,440 |
| 方法内运行时写入 | 1,624 | 632 | 10 | 2,266 |

C#文件数含辅助函数和未确定所有者的容器，不能当成原业务类数。类工厂和超大模块容器按明确计数展开，辅助函数仍逐项导出。源类/索引方法与分组候选标签有不同分母；SDK/引擎/业务身份没有被弱词面标签证明，也没有据此过滤文件。

所有索引方法有实际目标成员，0未导出索引方法，0整函数AST或renderer异常回退。但1,254个函数存在局部未支持表达式/语句、预算局部省略或无可转写语句的显式标记；未支持位置、原片段/精确跨度均可定位。556,272条诊断以近似语义和后续修复项为主，不能解释为已编译/等价恢复。确实无法转写的局部显式抛错，不返回假成功。

主索引最大32,699,305字节，完整诊断唯一存于101份512记录详情分片，最大4,363,623字节。旧版主源重复报告450,799,004字节不再作为最终出口。修正了多变量声明/for initializer分隔符；方法内字段写入不再误提升为静态初始化；重复初始化只声明一次并按原字节顺序进入构造体，不因按字段名称排序打乱执行顺序；不同原名规范化碰撞有稳定消歧。动态语义、static this、未知API等仍可能产生语法和语义问题，均属于草稿接续范围。

## 同一候选的资源、配置与身份

旧资源候选manifest漏登记Editor新增的Scene/Prefab；`freeze-resource-candidate` 对准确版本已保存重开的nativeFiles哈希封存新完整基线，不启动Editor。88,493个文件中48,027个具有既有原生读回hash，34项Editor状态仅明确保留，不冒充新的原生证明。原manifest/readback未改。

最终统一候选 `.private/v060-package-mainflow-20261026/FullDraftCandidate03/UnityProject`：

- owning manifest SHA-256：`[private fingerprint omitted]`。
- 112,758个文件，3,484,952,335字节；原资源资产hash完全保留，仅原Docs/START-HERE增加接续入口。
- 2个Scene、1,696个Prefab，包含原来源及辅助预览；不据数量声称全部原版场景已恢复。
- 原JSON/资源键/GUID/localID/组件映射与完整初稿同一工程、同一owning inventory。
- beaver当前`candidate_snapshot.snapshot/verify`独立只读解析并逐文件流式hash通过；4个consumer源码文件hash前后相同，未修改beaver或执行adopt/apply。

接续入口为 `Docs/CSHARP-DRAFTS.md`、`Analysis/Code/package-csharp-drafts.json` 和逐源Details。实际C#位于`SourceRecovery/CSharp/`，Unity不编译此目录；原生编译/业务/Player/视觉没有因草稿存在而变为通过。

## 大工程预算与阶段复用

默认全工程共享上限继续为500,000文件、8GiB总量、512MiB单文件、128MiB manifest；严格方法子集仍保持原20,000/256MiB，只有明确的full-source draft kind可使用whole预算。源AST解析预算独立，Node仅作静态解析，不运行原游戏代码。

在最终真实候选上同时禁止`code_drafts.prepare`和`code_graph.draft_records`，完整初稿阶段仍实际复用24,263文件、328,742,065字节，覆盖全部3源/19,571索引方法/47,384函数；耗时6.148秒，原候选manifest不变，没有创建第二份资源工程。检查生成器完整签名、源SHA及全部阶段文件owner/大小/hash。公开包级复用用例验证了同一调用链；篡改/人工所有权不被静默接收。旧v0.5的样例项目/向样例项目资源大工程复用证据保持冻结，未重复重导。

## 验证与范围

本组父级21项定向集成检查通过：writer12、包级公开默认/增强/冻结/暖阶段/篡改拒绝6、字段上下文1、whole预算/dirty守卫2。类型证据模块11项及renderer原8项沿用模块证据，新增机械语法2项由模块开发者验证；其小型Acorn生成C#通过本地Roslyn编译，临时编译制品未保存，不能当成完整草稿编译回执。

向样例项目继续使用已批准冻结来源：既有8个纯i64运算片段和精确WASM字节证据复用，关联仍有caller-map假设；13个状态方法不伪造正文，不再启动其原生工程。36个精确schema缺口继续约束不安全二进制字段写回，不妨碍有源JS初稿导出。真实游戏Mono样本、完整IL2CPP状态方法、全游戏业务/原UI/Player/视觉仍未验证。

私有完整回执位于 `.private/v060-package-mainflow-20261026/`：`final-candidate-verification.json`、`final-large-stage-reuse.json`、`final-integration-tests.log`、`full-convert-03.log`。原样本、候选、诊断载荷和编译私有制品不纳入Git或发行包；分发身份由本目录`delivery.json`固定。稳定0.4不变。

## 固定本地分发03

源码提交 `[private fingerprint omitted]`，tree `[private fingerprint omitted]`。从`git archive`快照构建一次wheel/sdist，182个产品文件与提交及隔离安装副本逐字节一致；无游戏原件、私有样本、outputs或恢复DLL/WASM入包。

| 制品 | 字节 | SHA-256 |
|---|---:|---|
| monkey_native-0.6.0.dev1-py3-none-any.whl | 719,239 | `[private fingerprint omitted]` |
| monkey_native-0.6.0.dev1.tar.gz | 1,054,967 | `[private fingerprint omitted]` |

隔离安装实际执行capabilities、code-draft冷生成、code-draft逐文件hash复用、code-types数字方法自动类型提取4次调用，全部预期状态；小源为自有测试代码且从未执行。只验证新增主链，没有重复旧24CLI、16方法编译、WASM8或Unity/CUA6。路径为`.private/v060-package-mainflow-20261026/distribution-03/`；不作为全局安装或正式Release。
