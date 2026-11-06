> 2026-10-26最新用户裁定：默认全量C#初稿导出，允许类型/语法/API缺口；本文的严格typed/profile子集为可选增强，不再作为其他有源方法导出的门槛。现行进度和完整候选链见 [PLAN](PLAN.md)。

# 当前 v0.6：C# 代码恢复与模块构建

执行 [统一C1–C9计划](PLAN.md) 和 完整范围 (local path omitted)。本版新增投入为完整模块符号/类型/方法体/跨模块依赖、Unity生命周期事件与原字段配置/资源绑定、确定性C#候选/增量/编译行为/AI交接，原后续C#内容不再另排v0.7。CLI只有实装后才登记能力。下方历史数值子集仍兼容，不代表本大版验收。

固定样例项目main/game.js为7,147,892字节/SHA `[private fingerprint omitted]`。完整词法图928类/16,384方法，原RF914区域不是完整上下文；旧138数值候选保留历史。当前[模块生成](CODE-MODULES.md)/[入口选择](CODE-SELECTION.md)可按显式类型合同批量闭合并实际lowering。4个真实模块16方法候选已编译，16,368未选择不等于不支持；原12方法与新4方法各有独立行为证据。原生9方法有限流程完成6次系统指针操作，非原UI恢复。Unity WASM精确字节链与8纯运算片段另见[WASM来源](WASM-CODE-SOURCES.md)；13波次/触发方法仍缺精确布局/调用目标，caller-map关联假设保留。未知保留具名源位置/原因/编译排除；不执行原JS/WASM/DLL，36正文仅阻断依赖操作。

# 可接续代码子集（v0.2开发中）

```sh
monkey code-model --source original-module.js --module-name NumberLabel --out fresh-facts
monkey code-emit --source original-module.js --code-model fresh-facts/code-model.json \
  --numeric-field value --namespace my-game --cocos-code-language ts --out fresh-code
```

默认TypeScript；JS为显式次选。`code-emit`生成可证实的普通同步实例字段setter/getter，arrow/async/generator不误判this。包级`convert`另支持下方审阅过的静态数值方法合同。渲染前重新静态解析并核全部事实，篡改模型/源/重复owner与危险目标名拒绝；原JS从不执行。

`--numeric-field`明确限定number调用子域，不是断言所有JS动态值都是数字。C#double?未初始化没有值，对应TS undefined；负零/NaN/Infinity在该子域内保持，JS null/string/object/省略参数仍在合同外。未知方法原文/范围/哈希和具体待补状态留SourceRecovery及code-contract，不能用空成功替代。无源级Label声明的普通类只发状态类，不能凭名字生成引擎组件。

只有RF原名/身份、IIFE cc.Label参数、构造别名和方法作用域吻合时，才生成显式Label/TMP表现适配。原继承/decorator helper并未执行或恢复；有限Label字段projection拒绝丢弃未知序列化业务字段。原`_N$overflow`精确读取，冲突拒绝；数字小样的SHRINK用明确baked静态呈现，动态缩字不算恢复。

`code-emit`可以单独输出代码子集；包级`convert --numeric-code-contract numeric.json`已接入相同发现/生成/组件投射/双目标导出链。它不自动补齐所有方法。Unity脚本GUID和TS/JS脚本UUID由namespace+源身份确定、独立于目标路径；Creator TS meta4.0.24来自实际3.8.8导入回读。固定meta的新输出仍须真实验证；JS importer也已实际回读为javascript4.0.24；包级已接受显式js，生成assets/package.json局部ESM边界。

## 包级单命令

```sh
monkey convert --input-set inputs.json --target both --out fresh \
  --numeric-code-contract numeric.json --cocos-code-language ts --format grea
```

`numeric.json`为明确调用子域声明，字段如下（moduleSha256替换为静态恢复模块原始字节的完整SHA256）：

```json
{
  "schemaVersion": 1,
  "kind": "numeric-call-subdomain-v1",
  "moduleName": "Meter",
  "registrationId": "original-rf-identity",
  "moduleSha256": "exact-module-sha256",
  "numericField": "value"
}
```

当前一次声明一个源级Label类/数值字段与唯一setter/getter。CLI自动在本次原包静态恢复结果中唯一匹配RF身份/原名，重核模块SHA/方法事实，生成C#/默认TS，按全部原组件身份建立绑定；未知序列化业务字段、重复模块/owner、非Label继承或缺失getter/setter会停止声明分支，不退成“声明成功”的基线工程。原始声明/模块/待补方法均保留工程内部。`--format grea`只移动明确脚本路径和报告槽，GUID/UUID保持；已有代码投射包的resume/reuse暂拒绝，保留旧候选。可加`--native`及编辑器参数顺序实导。

公开单命令合成native01完成7输入/1原组件：Unity own78528于2026-10-23T20:57:53.848046Z→20:58:04.054183Z exit0/reaped；Creator own78894于20:58:04.082896Z→20:58:20.932724Z正常TERM exit-15/reaped。两端严格回读0差异、生成类实际注册/原组件绑定、负零/NaN/Infinity/未初始化、文本引用、Scene+独立Prefab保存重开通过；Unity editor partial保留未实现方法，Creator资源editor pass。它验证自动包级链，不能替代下方真实5组件分母，也不代表业务完成。

## 实际NumberLabel证据

源及5原组件映射见V0.2-EXAMPLES.md；6方法中2个实现、4个pending。C#真实编译通过；TS5.8.2+Creator3.8.8公开SDK对target启用strict，错误字符串调用TS2345拒绝。上游SDK本身82项full-strict声明错误单列，skipLibCheck只隔离这些声明，不放宽target。

- Unity probe05：own70833，2026-10-23T19:23:17.534061Z→19:23:27.140130Z exit0/reaped。MainUi129节点/原Prefab GUID不变，MissingScript0；5实际TMP/原字体/字串引用、数字边界/实例隔离、未初始化态、保存重载及全部节点几何保持。原件SHA保持；初始3轮失败因缺TMP投射、TMP Settings隐式资源和无Canvas字形测量分别保留。字形在隔离active Canvas clone验证，不改原树。
- Creator TS native01：candidate03 SHA804703d0010a88fc25608e2fa519b3d94e7785e1a391cef3ba7c2a544685cd7c。own71766，19:28:21Z→19:28:41Z正常TERM exit-15/reaped，editor pass/诊断0。实际注册NumberLabel，Scene和独立Prefab共129源节点/同5原组件，原字串/字体引用/完整geometry与数字边界/状态隔离保持；重载5个getter为undefined，4未知方法未绑定。
- Creator实际初始自动分配脚本UUID86325443-58b5-4b92-b0e4-bc27ec362d46、classId86325RDWLVLkrDkvCfsNi1G，TypeScript meta4.0.24。此自动分配结果不能作为跨新工程/格式恒定身份承诺；后续固定meta用明确新输出验证，不追改该冻结结果。

以上是原生资源接线与数字方法子集，不代表数字动画/SHRINK动态行为/原版视觉/输入/可玩已通过。


## JS次选真实注册与公开编排

首JS native01确实失败（own96108，正常TERM/reaped）：未预分配meta导致identity门失败，且默认`.js`按CommonJS解释，原ESM import不能加载；旧结果保留。使用[官方3.8模块规范](https://docs.cocos.com/creator/3.8/manual/en/scripting/modules/spec.html)所声明的最近package.json/type=module规则，在assets根写明确模块边界，保持ESM JS，不改成TS或plugin；extensions仍在该边界外。实际JS importer=javascript/ver4.0.24来自首轮Editor读回，使用已验证meta结构和namespace/RF固定UUID。

新实际MainUi129节点/5原RF绑定JS native02：own96527于22:41:40.702916Z→22:41:58.153501Z正常TERM/reaped，editorpass/strict0。JS classId `d70c6lDSQpbe7+KyntJCtEm` 对应script UUID `[private identifier]`；Scene与独立Prefab各5绑定、未初始化态、数字边界/隔离/原文字体保持、几何和保存重载通过。candidate manifest `[private fingerprint omitted]`。身份独立只读审计 `outputs/number-label-js-identity-audit-01`六门全true，旧输出未改；4未知方法及SHRINK动态行为继续pending。

公开`convert --cocos-code-language js --format grea --native`合成端到端02（7输入/1组件）：own97084于22:47:18.787472Z→22:47:35.091237Z正常TERM/reaped、editorpass/strict0，manifest `[private fingerprint omitted]`。01只在格式计划哈希变量误用处失败，保留未格式化候选、native未启动。修正不放宽源hash保护。脚本移动而assets/package.json边界保持；installer只把.cs/.ts/.js当脚本，不把模块JSON误作scriptPath。新投射带codeScriptUuid，类型注册和读回均强核实际压缩classId，而非只看类名。C#输出不因Creator语言选择而改变。

## 新来源静态数值方法：Creator 3.8.7

`convert --numeric-code-contract static-number.json`另接受以下合同，`methods`必须是明确选中的原静态方法名；仍默认TS，显式`--cocos-code-language js`为次选。单独的`code-emit`保持字段合同，未增加不带来源证明的任意表达式执行入口。

```json
{
  "schemaVersion": 1,
  "kind": "static-number-methods-v1",
  "moduleName": "chunks:///_virtual/ParabolaUtils.ts",
  "moduleSha256": "[private fingerprint omitted]",
  "helperModuleName": "chunks:///_virtual/rollupPluginModLoBabelHelpers.js",
  "helperModuleSha256": "[private fingerprint omitted]",
  "methods": ["radiansToDegrees", "degreesToRadians", "lerp"]
}
```

来自下方了的951字节原模块，RF `db6de0nQuNC66zGTRfLeH+G`；保留8个原方法，3个纯数值方法生成，distance/vectorToAngle/normalize/rotateVector/lerpVector等5个向量方法待恢复。源callback可能是独立`function(...)`表达式，以Acorn表达式模式读取并保留原字节偏移，无源码执行或包装后猜偏移。

严格识别literal import setter→createClass→原导出/构造别名→静态descriptor表→单return表达式，仅参数、有限数值字面量、Math.PI、正负号和四则运算。模块setup/别名变化、局部Math遮蔽、重复/计算descriptor属性、未知helper和模型篡改拒绝。此profile只接受已核对SHA的createClass实现；该helper的自由变量e继续在原完整脚本中追到`e=require("../../@babel/runtime/helpers/typeof")`、声明的`@babel/runtime/helpers/typeof.js`及精确callback SHA `[private fingerprint omitted]`。静态worker上限32MiB/1M节点/256MiB/30秒；重赋值、require遮蔽、动态词法scope或无法证明时停止，不执行helper/源构造器。

生成Unity `Monkey.Recovered.ParabolaUtils`静态类及Creator纯ES模块；`--format grea`分别归入`Assets/Game/Domain/Math`和`assets/scripts/domain/math`。函数不依赖源引擎、不绑定Scene组件，binding明确为`static-calls-only-no-component-binding`。工程自带`Docs/STATIC-NUMERIC-UTILITY.md`与聚合任务、原文/方法范围/hash/helper词法证据；当前路径从manifest的codeEmission.scriptPath读取，格式化后不会留下旧路径。

调用合同为显式JS Number/C# double参数，包含-0/NaN/Infinity，Math.PI及类方法保持原定义；非number/省略参数、constructor、helper副作用、向量方法均在外。lerp为未clamp的`t+(e-t)*i`。C#用各一次binary64运算且NoInlining的私有函数保持源运算分组，不能替换成engine Lerp或先折叠常量。

真实公开单命令`outputs/cocos38-parabola-package-10`：496输入/38081754B，83源图/810节点/81Prefab资源计划保持，双目标grea成功；原none完整保留。Unity manifest `[private fingerprint omitted]`，Creator manifest `[private fingerprint omitted]`。当前parser重新读取结果相同、helper context完全一致，两工程30974个owned文件全部逐字节核验（各15512/15462）。Unity6 SDK编译与TS5.8.2 strict均通过，C#、TS编译结果、JS次选各13组实际调用通过：包含负零位模式、NaN/Infinity、外插、乘加收缩反例`lerp(-1,1e16,1e-16)`、大数运算顺序溢出。只运行受控生成代码，原代码/helper未执行。

本组无新Editor或Player；原生导入/组件接线不由纯数值编译替代。资源原生结果复用前组07/08独立记录，完整视觉/输入/玩法仍未验。审计`outputs/parabola-math-audit-10`保留来源、代码、编译/运行SHA及边界结果；09 Creator代码内容有效但落在旧domain/state，冻结保留，10修正目录。
