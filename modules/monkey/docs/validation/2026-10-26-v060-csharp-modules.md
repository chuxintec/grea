# v0.6.0.dev1 C# 模块本地验收

本版按合并后的 C1–C9 计划交付有据方法恢复、模块组装、配置、有限原生适配和隔离分发。结果限明确调用域，不表示完整样例项目或向样例项目游戏已恢复。原始 JS、WASM、程序集从未执行；目标 C# 和自有合法夹具可以执行。正式游戏、GREA、beaver、已安装 0.4.0 保持只读。

## 固定来源与分母

样例项目源码 SHA256 `[private fingerprint omitted]`，7,147,892 字节。完整静态索引 928 个可识别类、37,445 函数、16,384 个字面静态/prototype 赋值方法；方法不是全部函数的别称。解析上下文不再受旧 914 个 RF 区域限制。

| 层级 | 实际范围 |
|---|---|
| 可索引的方法 | 16,384；逐项来源字节跨度和哈希 |
| 有显式类型/闭合依赖合同 | 12 |
| 自动生成真实 C# 方法体 | 12，3 个源模块 |
| 离线编译 / 独立预期行为 | 12 / 12 |
| 原生绑定/运行 | 9 / 12；HealthState 6 + RecipeCatalog 3，OrderRules 未原生接线 |
| 未选入生成 | 16,372；保留完整源与逐方法索引，不称不可恢复，不补成功空壳 |

三个源模块：OrderRules 的 Map 汇总、稳定排序、按 RecipeCatalog.IsDish 筛选；RecipeCatalog 的存在/取值/递归展开；HealthState 的实际生命/连击/回调逻辑。共 12 方法，不计编译器 helper、JSON reader 或新目标适配器充数。跨类调用、缺 callee 拒绝、源成员被覆盖拒绝、作用域/闭包和有序集合有对应证据。

类型来自明确调用合同，非全动态类型推断。Number 保持 binary64，Index 仅限已证明下标；Map 缺值用 Optional，undefined 数值不伪造为零。排序、集合顺序、NaN/有符号零、委托空守卫、分支/循环/异常与副作用有定向反例或独立预期。动态 this、未知属性/引擎调用、eval、位运算、未证明异步/继承/接口/重载等不猜实现。实例构造是调用方给定状态的适配，不称原构造恢复。

## 原 JSON 与目标接线

`ElementMultiOrderPool.json` SHA256 `[private fingerprint omitted]`，212,601 字节、732 行。原表/meta 原样保留，C# 运行时强类型 reader 解析原字段形成 Map；没有生成第二份可编辑数值表。字段投影/JS 对象键顺序来自固定源码字节跨度/hash。真实 dish 2015015 递归得到 9 个有序叶子，另用自有数据验证去重/递归边界，4 类坏配置拒绝。CookEffect 和完整配置模型仍未恢复。

原生窗口 01：最小工程缺内置 IMGUI 模块声明，编译失败，0 Scene 保存，Unity 子进程 exit 1 并回收。修复后必须使用新工程与新窗口，不覆盖旧失败证据。

窗口 02 缺内置 JSONSerialize 声明，编译失败后 exit1/reaped；补齐后窗口03保存场景，但 Search 启动异常后共享 delayCall 未继续，父仅结束自有 child（-15/reaped）。新准备改为持久阶段 + Editor update 接续。

窗口 04：Unity 6000.6.2f1 import/编译、Scene 保存/重开、TextAsset GUID/localId/hash、MonoScript 身份、持久 UnityEvent、PlayMode Awake/OnEnable、6 个 Health 方法、RecipeCatalog 递归的3方法链、原 JSON 的732行/9有序叶、OnDestroy 解绑均通过；exit0/reaped。保存前后引用身份一致，Scene SHA256 `[private fingerprint omitted]`，原生回执 SHA256 `[private fingerprint omitted]`。窗口04日志没有 exception/compiler error 行，不把旧失败记录删掉。新 adapter、OnGUI、生命周期、初始 fixture、UnityEvent 桥接均为测试基础设施，不能反标原 UI/生命周期恢复。初始 HP 等数字是自造测试数据；实际配方数值只从原 JSON 读取。视觉、物理输入、Player 构建和完整业务仍单独为 `not_run`。

## 增量与源码交接

内置 `foodstreet-demand-health-v1` 是精确整源/类/方法哈希与类型合同，包内不含原 JS、目标 C# 方法体或私有数值；生成仍走 AST 语义降低。同名不同版本来源拒绝套用。完整源在 SourceRecovery 编译区外；正常 C# / asmdef / 稳定 meta 在 `Assets/Game/Domain/Recovered/`，JSON 在 `Assets/Game/Content/Config/Base/`。

profile 候选 manifest `[private fingerprint omitted]`；其 16 个 Assets 文件与已通过独立编译/行为的 candidate05 逐字节相同。同输入暖候选 manifest `[private fingerprint omitted]`，23 个文件全部相同、6 模块全部复用。暖代码复用仍核验 AST/类型，不声称免解析。自有合成源码 x/2→x/4 仅使 MathRules 与 OrderRules 失效，RecoveryTypes 复用；dirty/manual/owner/hash/未知文件拒绝；1,800 深依赖链不耗 Python 递归栈。工作工程采用归 beaver。

候选包含每个已实现方法的源身份/目标映射、完整未选方法索引、合同、字段初始化/依赖、明确缺口、AGENTS 与 START-HERE。所有生成候选自身验证初值为 not_run；外部不可变验收回执按 manifest SHA 绑定，不回填篡改候选。

## Unity 来源路线

Mono 复用本机明确 ILSpy provider，只静态读取程序集。当前没有真实游戏 Mono 输入；自有合法夹具 2 类/3 个实质方法完成反编译闭包、目标编译与独立行为，原程序集没有执行。不外推真实游戏或 IL 等价。

向样例项目的冻结来源：2 个压缩 WASM（7,984,931 / 4,593,155 字节）及 1 个旧 1 字节无效载荷，元数据 20,251,452 字节。全部明确 `metadata_only` / 已实现方法 0；缺绑定同一二进制的方法映射，压缩容器未解、方法体依据未闭合。DummyDLL、声明、同名或同事改造版索引不计实现，不恢复其正式开发。v0.5 的 36 精确正文 schema 缺口继续局部阻断相关字段，不阻断其他模块。

## 分发与复核

冻结产品源码提交 `[private fingerprint omitted]`，树 `[private fingerprint omitted]`，从 git archive 构建。wheel/sdist 与该提交173个产品文件逐字节一致；新私有 venv 的173文件复核通过，Pillow/pypinyin从既有固定安装复制，不下载依赖。50项定向测试无skip通过，20项已安装CLI烟测通过。安装版在仓库外调用真实profile/JSON，生成23文件及manifest与profile06全部一致；安装版额外recipe原生准备的10个代码/配置文件也与窗口04实跑文件一致，无须重复启动Editor。

- wheel：`monkey_native-0.6.0.dev1-py3-none-any.whl`，645,150字节，SHA256 `[private fingerprint omitted]`。
- sdist：`monkey_native-0.6.0.dev1.tar.gz`，946,762字节，SHA256 `[private fingerprint omitted]`。

本验收记录后续提交只补回执，不修改或重打冻结制品。完整机器证据为 `.private/v060-csharp-20261026/delivery.json`，源码与回执提交分别追溯。Linux/Windows 未运行；没有推送、Release 或全局安装。本版使用方法见 [CODE-MODULES](../CODE-MODULES.md)、[CODE-PROFILES](../CODE-PROFILES.md)、[CODE-NATIVE-PROBE](../CODE-NATIVE-PROBE.md)。完整私有证据留在本工具 `.private/v060-csharp-20261026/`，不进入公开包。
