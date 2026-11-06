# monkey

当前开发统一在 **0.8.0.dev45** 单线，包含 Unity 来源恢复、Cocos 来源转 Unity 静态 Prefab、
Toggle 空配置桥接、显式 CoreText 静态回退字体及严格静态引用恢复。
新增导出、开发与验收统一以 Unity 为目标；Creator/Cocos 目标保留既有显式兼容入口及历史证据，暂停专项修复和验收。
monkey 由 GREA 统一调度和分发；旧 0.7.0 发布与固定消费者只作兼容保留，
不再继续 0.7 开发。字体入口见 [系统字体工具](docs/SOURCE-SYSTEM-FONTS.md)，
Unity 来源边界见 [Prefab 恢复](docs/UNITY-PREFAB-RECOVERY.md)。

已有 Cocos→Unity plan 可通过 [静态组件续接](docs/STATIC-PREFAB-CONTINUATION.md) 复用冻结产物，按通用组件族补齐静态身份与引用（含全源 Mask、受控裁剪和未激活文字采样证据）；准备、原生回读和视觉验收分别报告。

[MIT License](LICENSE) · [Source](https://github.com/chuxintec/monkey) · [v0.7.0 Release](https://github.com/chuxintec/monkey/releases/tag/v0.7.0)

monkey 是 Python 驱动的原包恢复命令行工具，将已授权取得的包体、资源和源码证据整理为独立候选工程。正式版本 **0.7.0** 在既有 C# 恢复及七个来源侧工具上加入 Cocos 来源静态 Prefab、保存选取与依赖声明流程；工程规范为 [`monkey-project/2.0.0`](docs/PROJECT-SPEC.md)。

Unity 目标使用 Unity 6，采用 `Assets/Game/Content/<Type>/<Module>/`；Creator 资源目标使用 `assets/resources/<Type>/<Module>/`。图片统一放在 Textures，保留 Sprite 导入设置与引用。中文输出名转拼音，保留源名映射及冲突消歧。原始数值配置以 UTF-8 JSON 为维护源。

## 本地开发工程命令

`monkey develop` 接收 beaver 全部工程命令。运行 `monkey develop --help` 查看命令组，运行 `monkey develop capabilities` 查看验证范围及引擎依赖。恢复仍用原有 monkey 命令；新采用事务使用 `monkey develop intake plan/apply/rollback`。工程实现、原生 Editor 伴随代码、测试和模板随仓库维护，固定历史事务继续使用创建它们的版本。参数和事务边界见 [工程命令合同](engineering/docs/CLI-CONTRACT.md)。

## 0.7.0 的主要能力

- Cocos 来源的静态 Prefab 恢复支持有据字段、资源、布局、固定状态和双目标保存重开；未知业务、动画曲线和不可用行为仍保留具体缺口。
- `freeze-native-selection` 按冻结源与原生读回选取依赖；`audit-native-code-dependencies` 补充 C# 证明和 SDK 声明，保留未知 MonoScript 表为 `not_run`。
- 字体补齐、Spine 静态资源和运行时展示均按精确源身份与代表样本验证；引擎、字体、SDK、完整业务和第三方许可不随版本号自动保证。

- 包级 `convert` 可生成全部已取得 JS 方法的 C# 初稿，并保留资源、JSON、Scene/Prefab、源码映射及具体未恢复项。支持核验后复用冻结资源候选，避免重复解码。
- 原生架构流程按 Bootstrap/Domain/Gameplay/Presentation/Services 组织完整模块，支持单进程有界生成、断点接续、只读重分类、哈希固定的候选修订和显式本地测试 JSON。
- 大工程解析预算、阶段复用、资源身份、引用闭包和生成所有权保留明确边界。未知方法、缺失资源与不可编译初稿不会变成假成功。
- `monkey tool <id> [args...]` 接收 GREA 的来源侧工具，保持 ID、参数、报告与退出码。GREA 可通过固定版本 provider 调用；当前开发版通过 `monkey develop` 进行工程采用和建设。

支持范围按来源格式逐步实现，参见[支持矩阵](docs/SUPPORT-MATRIX.md)。Cocos、Unity、Egret 等已有不同范围的 reader；原图 gallery 不代表节点或业务已恢复。恢复候选、原生导入、编译、玩法及视觉验收分别记录。

## 安装与使用

需要 Python 3.11+。从正式 Release 下载 wheel 和 `SHA256SUMS`，核对校验值后安装到独立环境：

```sh
python3 -m venv .monkey-env
.monkey-env/bin/python -m pip install monkey_native-0.7.0-py3-none-any.whl
.monkey-env/bin/monkey --version
.monkey-env/bin/monkey capabilities
.monkey-env/bin/monkey convert --help
.monkey-env/bin/monkey tool --help
```

Windows 使用环境目录下的 `Scripts/python.exe` 和 `Scripts/monkey.exe`。安装仅提供工具，不包含游戏原包、引擎或私有素材。现有 GREA 集成应使用对应正式版本、精确下载 SHA 和 producer 合同。

完整调用方式见[用法](docs/USAGE.md)、[C# 初稿](docs/CODE-DRAFTS.md)、[架构恢复](docs/CODE-ARCHITECTURE.md)、[候选修订](docs/CODE-ARCHITECTURE-REVISION.md)及[正式发布说明](docs/RELEASE-v0.7.0.md)。

## 验证与限制

历史 0.7.0 稳定源码来自已固定的 0.7.0.dev9。下述历史证据不等于当前 0.8.0 开发版全部通过；实际使用须固定源码/制品 SHA 并单独检查原生、视觉和 Player 证据，不以工具版本或安装成功推断游戏完成。

一个代表性私有来源的完整候选曾以 1,555 份 C#、五个真实程序集完成编译：0 error、3,249 warning。受影响原生核心验证覆盖 348 格、24 个 Sprite 身份、生产点击、持久化重开及视口外输入拒绝。该历史证据不作为发行包内的公开复现素材，也不等于完整游戏恢复。原始证据保留在本地私有档案，公开摘要见版本说明。

生成代码仍可能存在语法、类型、API 和业务缺口。部分模块仍为 partial/unreviewed，原厂认证、远端服务、完整玩法、物理输入、视觉对照与 Player 构建不能据此宣称通过。原生验证还保留两条 Editor Search 启动异常。不得把未知服务器行为实现为假登录、假奖励或假支付。

## 许可与来源

monkey 自有代码采用 [MIT License](LICENSE)。第三方代码与必要版权声明见 [THIRD-PARTY-NOTICES](THIRD-PARTY-NOTICES.md)。游戏原包、素材、引擎及第三方工具不属于本项目的开源授权范围，不随源码发行或安装包提供。

旧原生事务的独立回执与只读复验入口见 [Native execution recovery](docs/NATIVE-EXECUTION-RECOVERY.md)。恢复回执不改写原日志，也不代表候选验收通过。

### Restore visual references in a Unity export

Install the source checkout with the `unity-visuals` extra. Run
`monkey repair-unity-visuals --project CANDIDATE --sources manifest.json --pool ASTC_DIR`
against an independent exported project. The manifest supplies local `bundles` paths
and `roots` entries with `asset`, `cab` and `pathId`. The pool holds ASTC payloads
named for their full source texture token with the `.txt` extension. The tool
writes source image identities and SHA-256 hashes to `visual-repair.json`.
Run the Editor methods `UnitySourceVisualRepair.Apply` and
`UnitySourceVisualRepair.Verify` in separate Editor processes to save and verify
the resulting references.

Optional `states` entries select a reviewed static display state using `root`,
indexed child `path` (e.g. `0/1/0`), `node`, `active` and `reason`. Include
`outlineFallback` when the candidate uses the recovered `DodGame.DodTextOutline`
mesh adapter. Supply the project path of a material using the matching
`Monkey/UnitySource/TextOutline` shader. Optional `objects` entries identify
previously exported particle shape meshes by `cab`, `pathId`, `name` and native
mesh `asset` path. Ambiguous material slots are recorded in the plan for review.

To apply one reviewed tab selection to several roots, add an `exclusiveViews`
entry with sibling names `keep` and `hide` and a `reason`. Both must be active,
uniquely named siblings in the same anchored frame whose rectangles substantially
overlap. Explicit per-node states take precedence.

The command works offline by default. Where the source origin is authorized,
`--fetch-base https://HOST/PATH` fetches only the manifest's `textureRequests`
entries (full source `token`, `width`, `height`, optional `sha256`). It checks the
ASTC payload before writing it. `outsideSuppliedPool` lists referenced tokens
outside this repair pool. Spine texture assets retain their original file names
so the runtime atlas loader can resolve its pages. To audit possible residual
label collisions in a preview, call `UnitySourceOverlapReview.Begin()`,
`Observe(instance, prefabPath)` after each canvas layout rebuild, then `Finish()`.
It records sibling glyph overlaps for visual review. Supply its `findings` in
`overlapFindings` and reviewed `overlapRules` with `keep`, `hide`, `reason` and
optional `parent` to select a static label only for measured active siblings.
For repeated material names, `materialObjects` maps an exported material path
to source `[CAB, pathID]` pairs established by corresponding renderer slots.

For a selected-root batch, run `python -m monkey.unity_object_dependencies --sources manifest.json --output objects.json` against the original bundles. The result separates serialized-file/path-ID pairs found in the pool, external files (including Unity builtins), and missing objects. Material texture maps and other key/value arrays participate in traversal. The visual repair command also retains source-proven zero-sized dynamic font atlases when a bitmap exporter skipped them.

For a HLSLcc GLES3 shader with a parsed `form.json` and numbered `<blobIndex>.glsl` source programs, run `python -m monkey.unity_gles_shader SOURCE_DIRECTORY OUTPUT.shader`. This profile reconstructs non-instanced passes. Check the required material keywords and graphics backend in the target Editor.


For reviewed layouts use `layouts` entries with the same `root`, `path`, `node`
and `reason`. `includeInLayout` enables an existing excluded LayoutElement
under its LayoutGroup. `fitPreferredHeight` lets an existing layout group use
the preferred height of its children. Both are checked again after reopening.

### Lower local Cocos methods to C# bodies

Run `monkey lower-cocos-local-methods --source GAME.js --manifest CONTRACT.json --out NEW_DIRECTORY`.
The contract pins `sourceSha256`. Each `methods` row supplies its lexical graph `id`,
exact `sha256`, reviewed `returns`, permitted zero-argument `voidCalls`, and
a `members` map of same-type string, bool or double members. Optional `visualFields`
map side-effect-free source fields to Unity GameObject, CanvasGroup or Image.
The emitter recognizes empty void methods, local calls and assignments, and
guarded literal active/opacity/sprite resets. It checks the **whole** method AST.
For a single-argument return using a source component field, a typed `returns` and
`returnCall: {"field":"list","method":"find"}` authorize only the complete
`return this.list.find(arg)` shape with the same lexical parameter. A reviewed `localPositionAxes` list can lower `this.node.x/y` to local Unity coordinates
for declared double fields. Addition is supported only for two declared double members.
A comma sequence must lower completely. Unmatched methods have status `review` and a null body. Exit 1 indicates a
partial selection. Optional `templates` entries specify a local C# filename in `file`,
its `sha256`, and method `ids`. Each `/*monkey:method@OFFSET*/` marker must occur
exactly once, and each requested body must have been lowered. Compile the emitted bodies in their declared component
context, bind serialized references, and verify behavior separately in Play Mode.

### Apply reviewed IL2CPP methods to Unity components

`monkey apply-unity-method-overlay --project CANDIDATE --manifest REVIEW.json`
updates existing C# scripts in an independent Unity candidate. Each script retains
its original path and MonoScript GUID. Supply SHA-256 pins for the v29 metadata,
Il2CppDumper declarations, decoded WASM segments in table-overlay order, original
script bytes and reviewed C# output. Each method entry identifies the full source
type, metadata method index/token, dump signature, table slot and body hash.
The command preflights the entire batch and accepts an already-applied script
on retry. Review translations and validate the actual components separately in
Unity Play Mode.

For a byte accessor backed by a declared bool field, a reviewed template can use
`/*wasm:METHOD_INDEX*/` and `lift: "bool-accessor"`. The tool recognizes the full
load, store, or conditional store with a dirty flag and verifies the final script
hash. Other method bodies require explicit translations.

Use `lift: "numeric-accessor"` for complete int32 or float32 property loads and
stores. The index-setter pattern also preserves a second, explicitly converted
float field written by the same source body. Other opcode sequences or field
type mismatches stop the batch.

Use `lift: "struct-getter"` for a `Vector2` or `Color` instance getter when the
WASM body copies the entire declared field into its hidden return buffer. The
rule checks each source and destination word, including field type and offsets.

`monkey prepare-unity-runtime-hosts --manifest HOSTS.json --out hosts.json --project CANDIDATE`
locates each selected script on its original GameObject. The manifest maps
lowercase serialized file names under `files` to bundle `path` and `sha256`.
Each `roots` entry names the candidate prefab `asset`, source `cab` and
`rootId`, fully qualified `type`, assembly name without the .dll suffix, and
candidate `scriptGuid`. The UnityPy dependency comes with the `unity-visuals`
extra. In separate Editor processes, run `UnityRuntimeMethodHosts.Save` and
`UnityRuntimeMethodHosts.Cold` to verify script identity, component position
and persistent local file ID for every source host. Play Mode assertions still
need to trigger and observe the behavior being recovered.

`monkey inventory-unity-methods --manifest INPUT.json --out methods.json`
inventories the original methods before preparing any scripts. Supply the same
pinned `metadata`, `dump` and ordered `segments` as the overlay manifest, plus
`types` entries with the qualified `type` and `typeIndex`. Each method is
reported as automatically translatable, requiring review, or missing a local
body. The report includes prototype, token, WASM body identity and the generated
accessor expression when available. Nested compiler-generated types are checked
against their declaring type. A compiler-generated backing field named
`<Name>k__BackingField` uses the C# template identifier `recoveredBacking_Name`.

For offline method review, add `--include-body-bytes` to record the original
segment offset and hex bytes after exclusions. The command verifies each body
hash. Unresolved slots carry no bytes.

To inventory only outstanding methods, pass one or more
`--exclude-overlay PRIOR.json` options. The command compares metadata, dump
and ordered WASM hashes and checks each selected method identity before
subtraction. Multiple overlays listing the same method subtract it once.
This measures overlay coverage. Play Mode behavior is verified separately.

For small static methods returning a float, inventory can also report
`float-expression`. This lift emits a C# return expression from an entire
straight-line WASM body using float arguments, finite f32 literals, negation
and the four basic arithmetic operations. Parameter reads, stack arity and the
function terminator are checked. Calls, branches, memory access and unsupported
instructions remain available for review.

For a void method with no local variables whose entire WASM body contains only
optional NOP instructions and the function end, `void-noop` emits `return;`.
Constructors and methods with output parameters require separate review.

Use `apply-unity-method-overlay --native-signatures` with the runtime host
Editor checker to check compiled overloads when saving and cold reopening the
candidate. It writes an immutable `expected-method-signatures.json` in the
candidate. The checker binds the script by GUID and checks the declaring type,
static flag, return type, parameter order, generic arguments and by-reference
direction. Missing or ambiguous declarations fail the check. Save and cold
receipts are separate from Play Mode behavior observations. For compiler-generated
local functions, an unnamed by-reference Roslyn display-class parameter retains
its generated type and exact declaring method in the signature check.

Applying a subsequent overlay with `--native-signatures` keeps the initial
signature file intact. Additional expectations are stored by script GUID and
metadata method index under `expected-method-signatures.d/`. The Editor checks
the baseline and all additions together. Reapplying an identical signature is
idempotent, and conflicting signatures for the same method are rejected.
