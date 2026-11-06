> 2026-10-26最新用户裁定：默认全量C#初稿导出，允许类型/语法/API缺口；本文的严格typed/profile子集为可选增强，不再作为其他有源方法导出的门槛。现行进度和完整候选链见 [PLAN](PLAN.md)。

# v0.6 来源绑定的 C# 模块

从完整 JS 做静态词法索引，再按精确类/方法与显式类型合同恢复真实方法体。原代码不执行；输入合同不能包含任意 C# 或替代方法体。输出是独立代码候选，不能直接覆盖人工工程。

```sh
monkey code-model --source game.js --lexical-graph --expected-source SOURCE_SHA256 --out code-index
monkey code-emit --source game.js --module-contract code-contract.json --out code-candidate
monkey code-emit --source game.js --module-profile foodstreet-demand-health-v1 --configuration-table ElementMultiOrderPool.json --out sample-game-code
monkey code-emit --source game.js --module-contract code-contract.json --configuration-table ElementMultiOrderPool.json --out code-with-config
monkey code-emit --source game.js --module-contract code-contract.json --reuse-from code-candidate --expected-manifest CANDIDATE_MANIFEST_SHA256 --out code-candidate-next
```

返回 `partial` / 退出码 1 表示限定实现候选。索引成功不表示代码已恢复；生成成功不表示已编译、已运行或完整游戏已恢复。`Analysis/Code/code-modules.json` 记录来源分母、选中方法、实现数量、原位置/哈希与独立验证层；原源保留于编译区外 `SourceRecovery`。未选择的方法不补空 C# 桩。

合同 `schemaVersion=1`：`sourceSha256`、C# `namespace`、`records` 和 `modules`。每个 module 有稳定 `id`、`targetClass`、索引返回的 `classId/classSha256`、源字段 `fields`、`methods`；每个 method 有索引返回的 `id/sha256`、目标 `name`、参数 `parameters` 类型数组、`returns`、必要时显式 `locals`。局部类型按 bindingId 指定最精确，也可对同名同类型局部使用源名称。源码类型、显式调用约束与真实运行证据必须区分，合同不是所有动态调用都合法的证明。

支持类型是 `Number`（JS binary64）、`Index`（已证明的 int32 下标）、`Boolean`、`String`、`Void` 返回、来源字段 record、`List<T>`、`Map<K,V>`、`Set<T>`、`Optional<T>`、`Action<T>` 与有限递归局部 `Function<...,Return>`。缺类型/冲突不降级为 object/dynamic。记录字段须在选中 AST 或精确同源 `recordShapeEvidence` 方法见证中有来源；见证须匹配方法 ID/hash，不生成见证方法；构造记录须完整给出字段，不补默认值。来源构造函数、继承及外部服务初始化不因此恢复：状态类通过明确的目标调用合同构造，静态 map 必须由调用方先提供有效数据。

当前语义范围：typed 算术/比较/字符串连接、赋值与顺序、条件和短路语句、明确 counted for/while、无非空隐式 fallthrough 的 primitive switch、字符串异常、集合汇总/遍历、纯 comparator 的稳定排序、闭包与有据递归、闭合的跨类方法调用、精确 transpiler nullish 委托守卫。遗漏参数、动态属性、coercing objects、eval/反射、未知异步/迭代状态、未知引擎调用均拒绝。显式对象非空调用域可证明不可达的 fallback 不会被补成成功服务。

Map 缺值保留为 `Optional<T>`，而不是零；Number 运算中的 undefined 保留 NaN 语义。nullable 委托只有在精确的丢弃值 null/undefined 守卫中合并，不泛化严格 null 判断。Map/Set 顺序使用普通强类型数据集合；排序显式稳定，不依赖平台 Dictionary/HashSet 或 List.Sort 顺序。NaN、正负零、int 下标转 binary64 与副作用求值须按支持范围核验。字段/集合值要求非空，ID/计数为有限 Number；递归数据须有限无环，不承诺任意原始动态对象等价。回调不得修改正在遍历的数据集合。

`Assets/Game/Domain/Recovered/` 中是正常可编辑 C#、asmdef 与稳定脚本 meta。生成所有权/依赖指纹见 manifest：源方法变化使自身和调用者重生，无关模块可继续使用逐字节核验的旧文件。完整源/位置证据单独更新，不因全文件 SHA 改变强迫所有 C# 文件变化。dirty/manual/缺文件/未知文件/错误 owner/陈旧 manifest 先拒绝，始终写全新目录。人工工作工程采用、合并、回滚由 beaver 执行。

当前代码暖复用仍会静态解析、核验类型并计算新指纹，再复用已核验的输出字节；它不承诺免解析或免语义分析。大资源工程的解包/解码阶段复用沿用 v0.5 的独立合同。

Mono 静态来源另见 [UNITY-CODE-SOURCES](UNITY-CODE-SOURCES.md)。它的 `draft_closed` 只是观察到的反编译闭包，不冒充原 IL 等价或实际游戏验收。Unity 有限对象适配必须明确是新目标适配，并另行验证源字段、目标引用、生命周期、保存重开与真实运行；不能将源域类包装成“所有原组件已恢复”。

`--configuration-table` 当前只接精确 sample-game recipe profile，见 [CODE-CONFIGURATION](CODE-CONFIGURATION.md)。它核整源、原表与静态字节跨度哈希，逐字节保留原 JSON 和 meta GUID；强类型 reader 在运行时解析原字段、按原顺序构建 Map。它不生成第二份数值表，不嵌入配方数值，不声称补齐 CookEffect/完整 Kp。非匹配来源、namespace、Recipe 字段形状明确拒绝，不按同名表猜套。

可用 `monkey code-native-probe --candidate code-candidate --expected-manifest SHA256 --out new-unity-probe` 准备独立原生代表工程；命令只准备、不启动 Editor。当前 profile 与额外新适配器的边界、执行方法和各验证层见 [CODE-NATIVE-PROBE](CODE-NATIVE-PROBE.md)。准备成功不能视为原生验证通过。

模块选择与实际 lowering 预检见 [CODE-SELECTION](CODE-SELECTION.md)。可按入口闭合依赖，输出可直接交 `code-emit` 的裁剪合同；内置 profile 不是可生成方法数量的硬限制。Unity WASM 的独立字节证据与纯运算片段路线见 [WASM-CODE-SOURCES](WASM-CODE-SOURCES.md)，不把原始内存偏移猜成 C# 字段。
