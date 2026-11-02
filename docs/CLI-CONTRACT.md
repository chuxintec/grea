# CLI contract v1

当前固定候选见 [PLAN.md](PLAN.md)（正式基线 0.5.0），沿用 `beaver-result/1`。除保留原始输出和退出码的 `tool <id>` 子命令外，业务命令 stdout 为单个 JSON，包含 operationId、producer/version/implementationSha256、status、data、artifacts、actualChanges、diagnostics、limitations、verification。
退出 0=ok；1=partial；3=blocked/not_run（包括无效参数与前置条件未满足）；2=failed（执行/读回失败）。帮助为 argparse 文本；没有任意 shell 透传。

`actualChanges` 是数组，每项为**非空路径字符串或对象摘要**，消费者须保留类型、顺序及原值。`batch/production apply` 通常返回已变资源相对路径字符串，`unity apply` 沿用原生变化记录；工程绑定、迁移、采用/恢复和失败检查点可返回操作/数量/身份或待核写入对象。对象内部字段由操作定义，不能将整个数组限定为对象，也不能把字符串强转为对象后丢失原值；数字、布尔、null 和嵌套数组不是合法变更项。对应 JSON Schema 项合同为 `{"oneOf":[{"type":"string","minLength":1},{"type":"object"}]}`。这是既有固定 producer 的合同澄清，不改变其输出或身份。

原生执行与外层消费校验分别记录：provider 已返回 `status=ok`、原生 verified 后，外层 Schema 拒收不等于原生失败或零写入。应保留原始 provider stdout、退出码、计划/事务及外层拒收，修正校验后只读重验原结果；不能重新执行 apply、改写旧回执或根据空数组推断零写入。producer/计划身份、退出码与其他信封字段的检查仍各自生效。

| 命令 | 参数 | 效果 |
|---|---|---|
| `version` | 无 | 版本和实现内容身份 |
| `capabilities` | 无 | 实际能力、provider 和验证状态 |
| `doctor` | `--editor-path` 可选 | 仅本地存在检查；不启动引擎、不探测认证 |
| `project inspect` | `--project`、可选 `--assets` | 引擎、编辑器、依赖；可选资产大小及 GUID/UUID 重复检查 |
| `adopt plan` | `--candidate --target --out`，首次 `--baseline`，可选 `--lineage` | 输出独立计划；目标/候选只读 |
| `adopt apply` | `--plan --expected-plan --out --editor-path`，可选 `--timeout` | 原生应用、独立重开、状态记录 |
| `adopt rollback` | `--transaction --editor-path`，可选 `--timeout` | 仅恢复事务仍拥有的改动；后续变更拒绝 |
| `intake plan` | `--candidate --target --spec --out` | 独立只增合同；核精确当前前态与外部脚本，不伪造旧baseline |
| `intake apply` | `--plan --expected-plan --out --editor-path`；可选`--timeout` | 仅新资产，原生导入及独立无窗口重开，旧代码/meta不变 |
| `intake rollback` | `--transaction --expected-plan --editor-path`；可选`--timeout` | 仅本事务新增且后态未变的资源/空目录；任何后续修改拒绝 |
| `image inspect` | `--input` | PNG/静态图片尺寸、alpha、RGBA 与文件 hash |
| `image compress` | `--input --output`；执行另加 `--apply --expected-source` | 默认预览；PNG 无损重压缩，输出新文件 |
| `config validate` | `--schema --input` | 严格标量 JSON、重复键/ID、范围与字段检查 |
| `config generate` | `--schema --out` | 新独立目录内生成 C# DTO 与运行时 TextAsset JSON 读取器 |
| `code inspect` | `--project` | asmdef 名称/GUID引用及using清单；不代替编译 |
| `unity plan` | `--project --spec --out` | 冻结显式原生操作与整个源文件身份 |
| `unity apply` | `--plan --expected-plan --out --editor-path`；可选 `--timeout` | 执行限定原生操作、保存重开及源审计 |
| `player run` | `--manifest --expected-manifest --out`；可选 `--duration` | 核全部制品身份后启动自有进程，限时退出/停止；不授予业务通过 |
| `payload verify` | `--root --manifest`；可选 `--scope --allow-unlisted` | 流式文件/大小/哈希/独立inode及别名检查；未覆盖项默认拒绝，显式允许仍为partial |
| `payload plan` | `--root --manifest --target --out`；可选成对`--overrides --override-root` | 冻结来源、覆盖前后身份、别名与独立目标；不写最终目标 |
| `payload apply` | `--plan --expected-plan --out` | 验证独立临时树后原子晋升；不覆盖现存目标，不就地改来源 |

计划文件 `adoption-plan.json` 使用 `beaver-adopt/1`，旁侧 `plan-identity.json` 绑定字节 SHA256。绑定实现身份、明确根、生成基线、目标全部资产 hash、项目依赖/版本、candidate manifest、逐项动作/冲突与恢复信息。执行需相同计划身份；任何目标前置漂移拒绝。

本地 fix10 的采用计划额外记录 `adoptionDependencies` 和 `executionPolicy`。生产者可通过 manifest 的 [版本化依赖声明](ADOPTION-DEPENDENCIES.md) 补充非 GUID C# 依赖；声明节点必须全部在同一冻结清单中，缺省明确为 undeclared，不推断完整性。已有包依赖仍须精确匹配。公开命令参数不变，旧计划/事务继续使用原固定 runner。

变更 `.cs/.asmdef/.asmref/.rsp/.dll` 时，原生 Editor 先记录所有原身份与依赖、暂存编译输入并退出；下一次独立 Editor 启动实际编译后才导入资源，再独立重开严格比较完整 GUID/localID/type 集合。编译输入必须具有冻结的 `.meta` 与真实 GUID；无元数据者在预览阻止，不让 Unity 自动生成未归属身份。两阶段共用同一事务和 before-image，仅最终核验后提交一次状态。`native-code.json` 的 staged 仅表示暂存，不能当编译通过。readback 的 compilerInputs/compilationBoundary 表明是否实际经过该边界。

编译错误使原生 helper 无法运行时，公开 rollback 在确认自有 Editor 已退出、检查全部代码 before/after hash 和备份后，先恢复事务记录的编译输入，再启动 Editor 撤回资源和空的自有目录。该前置恢复仅限明确记账编译输入；后续不同字节、歧义或损坏备份拒绝覆盖。原生恢复继续核对原 GUID/localID 与依赖。Prefab 缺脚本及 Prefab/Scene/SO 零 persistent 对象拒绝；运行时业务、物理输入与视觉仍须消费者分别验收。

输入消费 monkey schemaVersion=1 `manifest.json` 或 Unity `recovery-manifest.json`；候选规范沿用 monkey-project/2.0.0，未新增第二解析器。目标 Unity 6000.6.2f1 和 Creator 3.8.8 可预览；只有 Unity 有原生执行实现（已在自有样例和固定真实工程隔离副本实证）。Creator apply 明确不支持。

首次必须独立共同基线；按 GUID/UUID + namespace + profile 三方比较。保留人工变更和源删除资产；双边变更、身份歧义、未知占位、依赖不匹配均阻止执行。原生移动使用 AssetDatabase，改变 payload 时使用 Unity 导入，检查 GUID/localID 与至多128个未改 prefab/scene直接依赖。字符串加载键和业务/视觉不由此保证。

`project inspect` 默认不扫描/重复 hash 大资产。`--assets` 扫描元信息；严格采用预览和执行逐流 hash 候选及目标，预算8GiB/500000文件/单文件512MiB，清单128MiB。输出不得与输入重叠。不存在隐式全局配置、自动安装或升级。

`--version` 等价于 `version`。统一状态保留 partial/failed/not_run，退出分别1/2/3。失败事务包含journal引用，不能根据actualChanges空数组推断零写入。旧 `monkey-adopt/1` 计划不重放；已有`.monkey/adoption`状态明确拒绝隐式迁移，旧事务继续用原monkey版本恢复。beaver不修改旧状态。

## 原生 spec 子集

所有 spec 都是 schemaVersion=1 的封闭 JSON；未知操作、节点类型、组件/字段和路径拒绝。

| operation | 必填字段 | 原生行为和范围 |
|---|---|---|
| `ui.create` | prefabPath、scenePath、fontAssetPath、sourceFontPath、width、height、nodes | 新建可编辑uGUI/TMP窗口；节点panel/list/button/text/image，列表为固定VerticalLayoutGroup，不声称ScrollRect；显式工程字体生成TMP资产；需既有TMP Essentials shader/settings |
| `prefab.inspect` | prefabPath | 原生层级、父级、组件、Transform localID、字体、Sprite GUID/localID及几何读回 |
| `prefab.edit` | prefabPath、edits | 现有节点/唯一组件的SerializedProperty字符串/布尔/整数/浮点/对象绑定，保存和重开检查；Variant明确拒绝，结构/脚本身份字段禁止 |
| `assets.move` | moves:[{source,target}] | 原生逐文件移动，GUID/localID及重开一致；禁止目录/环/占位；目录由原生API创建 |
| `project.import` | 无其他字段 | 编译并导入已写入的源文件；计划列明缺失meta路径，既有源改动拒绝；不加包 |
| `sprite.configure` | assetPath、pixelsPerUnit、pivot、maxSize、alphaIsTransparency | PNG→单Sprite，固定无mipmap/Uncompressed，原生Importer参数/身份/像素几何读回；只允许该meta变化 |
| `validate.play` | scenePath、durationSeconds | 显式场景1–30秒PlayMode，记录真实帧数和错误；不判业务或物理输入 |
| `build.macos` | scenes、productName，可选 development、tmpFontPolicy | BuildPipeline StandaloneOSX，整个Assets/Packages/ProjectSettings源身份保持，生成sourceSha256绑定的逐文件制品manifest |

`ui.create`可显式给tmpSettingsPath新建项目TMP设置，但不导入shader、不覆盖既有设置；通常应先由开发者完成官方TMP初始化。首次场景可能生成的SceneTemplateSettings.json会在计划中显式列出。字体只预装既有声明文本和ASCII，缺字拒绝；多语种、复杂动态布局/业务事件由开发Agent处理。按钮不会被注入空业务回调。

`prefab.edit` 的标量value为不变区域字符串；对象绑定用显式assetGuid/localId或targetNode/targetComponent。图片引用匹配具体Sprite localID，不靠图片文件同名猜测。正式JSON仅支持必填scalar int/double/string/bool；生成读取器要求项目已存在官方`com.unity.nuget.newtonsoft-json`，缺包不会自动安装；没有Excel、SO数值副本或任意代码重构。

工程采用具有原生回滚；普通unity操作失败保留journal/before-image并标recovery-required，不提供自动通用回滚。`assets.move`可按新计划反向移动；未知后续改动不能据旧计划覆盖。原生检查和PlayMode/Player不代替完整游戏功能、视觉或发布许可。

## Payload 与同事交接机制

`beaver-payload/1`：`schemaVersion:1`、`files:[{path,bytes,sha256}]`、可选`aliases:[{id,path}]`。别名ID是区分大小写的不透明标识，不访问URL、不解析外部游戏路由协议。多别名可指向同一载荷；重复别名、重复目标、Unicode/大小写目录碰撞、文件/目录前缀冲突、越界、符号链接和hardlink默认拒绝。构建/Player内部仅接受清单明确声明且仍位于制品范围内的链接。

覆盖清单：`schemaVersion:1,entries:[{path,target,source,expectedSha256,sha256,bytes}]`，source相对于明确override-root。旧hash必须匹配基线，所有指向旧path的别名统一转至target；默认保留旧载荷，显式同路径覆盖仅发生在新副本。输入、输出、计划与事务目录不得重叠。采用源协议的转换留给monkey/Agent；私有route-map和原游戏素材不进入beaver。

物化先生成独立inode的临时树并核验完整清单，再使用macOS `RENAME_EXCL` 原子晋升。并发创建的空目录也保留；失败时最终目录不含半成品，临时树和journal留供检查。Linux/Windows晋升代码尚未原生验收，不因macOS通过而外推。固定34003/307、游戏路径、WebView/WASM、vendor二进制均未接入。

构建后与Player启动前/退出后共用此核验器。运行回执增加实际可执行hash、UTC开始、pid、时限、独立证据目录及清除的旧引擎作业变量。独立日志目录与进程不等于隔离玩家存档；存档隔离必须由项目适配并另行证实，本版明确不声称已提供。

## v0.2 成组编辑合同

旧 `beaver-unity/1` 与采用合同保持可调用；v0.1旧事务须固定原0.1 wheel处理，新工具不会重放它们。日常编辑新增以下入口：

| 命令 | 参数 | 效果 |
|---|---|---|
| `batch plan` | `--project --spec --out` | spec v2预览，写集/读取依赖内容哈希、实际扫描计数；不启动Editor |
| `batch apply` | `--plan --expected-plan --out --editor-path`，可选`--timeout` | 一次Editor执行整个相关操作组，原生保存/重载和逐步哈希checkpoint |
| `batch recover` | `--transaction --out --editor-path`，可选`--timeout` | 同版本固定执行器恢复完整仍属本次的after状态；人工后改或不确定写入全拒绝 |
| `references` | `--project --out`，可选`--cache` | GUID正反向依赖、已证明C#加载字面量span、未知动态key、JSON未知字符串；元数据缓存与安全边界分离 |
| `debug start` | `--manifest --expected --out`，可选`--duration --width --height`（宽高成对） | 复用固定Mac候选；后台worker拥有实际进程，预算1～3600秒 |
| `debug inspect/stop/tail` | `--session`，tail可选`--lines` | 精确实例观测/向自有worker请求停止/有界脱敏日志；不自动重启 |
| `debug screenshot` | `--session --input --expected` | 登记已有截图的哈希与调用者来源；不生成或认证截图 |
| `debug target` | `--transaction` | 关联Editor/PlayMode计划、PID、日志与原生证据；不附着外部Editor |

批处理JSON为封闭 `schemaVersion:2, operation:batch, steps:[...]`，可给readPaths；需要持久通用列表/安全区组件时显式runtimeRoot（产品Assets内且不在Editor）。临时Editor helper使用保留目录Assets/BeaverBatchTools并按拥有的内容清理。运行时组件不是临时helper，属于计划写集与恢复范围。

支持steps：只读`prefab.inspect {assetPath}`、`prefab.patch {assetPath,actions}`、`asset.move {source,target}`、`reference.replace {assetPath,oldGuid,oldLocalId,newGuid,newLocalId,consumers}`、`text.key {assetPath,format:json-pointer,pointer,before,after}`、`script.key {assetPath,patches:[{start,end,before,after}]}`。引用替换必须显式给完整原生直接消费者，Editor先验证AssetDatabase依赖，不自动扩大写集；Prefab/Scene/ScriptableObject使用SerializedObject改对象引用。移动保留GUID/localID；字符串key仍须明确列消费者更新，不承诺动态字符串全覆盖。脚本仅改被词法扫描证明的资源加载字面量span，Editor启动前安装并实际编译；不做类型/命名空间语义重构。

Prefab actions支持`node.add/remove/reparent/order/active`、`component.add/remove`、`property.set`与[UI actions](NATIVE-UI.md)。node.add使用parent/name/index，默认RectTransform，mode=transform可建普通节点；node.active必须flag。property.set用path/component/property/mode/value，mode为string/bool/int/enum/float/object/null，或以numbers给定的color(RGBA)/vector2；object用assetGuid/localId或targetNode/targetComponent。组件须已存在、唯一具体类型；不生成业务方法。Transform/脚本/Prefab身份字段禁止编辑。

Variant允许可保存的属性、事件、组件与新增child override；继承层级的删除/重排/移动和组件删除拒绝，并给出单独显式base计划或新增child替代，不隐式改base、不Unpack。嵌套实例继承结构同样保护；不支持任意Prefab图自动变换。原生树读回规范化内部节点与外部GUID/localID引用，不把Editor临时instanceID当持久身份。

计划按选中GUID依赖闭包、编译脚本/asmdef及Packages/ProjectSettings实际内容hash；目录元信息只用于变化发现，不作为执行前置身份。无关贴图/音频不全量hash。整个批处理期间发现写集外源变化会报告failed；不猜恢复未备份源。每个原生checkpoint带写集真实after hash，恢复需该checkpoint与当前状态完全一致，并核before备份身份。编译失败/强杀导致无checkpoint时明确blocked手工检查；不会把事后猜测当安全恢复证据。

成功的同会话保存重载与独立Editor重开、PlayMode帧数、App运行、合成事件、真实鼠标/触摸、视觉和游戏业务是独立证据。任何partial/未知动态key/身份探测失败不得由GREA包装为业务通过。

大Unity制品使用显式`artifactPolicy=beaver-unity-build/2`：单文件流式上限4GiB、总8GiB，文件/别名/哈希/独立inode检查保持。构建与Player/debug自动使用此已知合同；独立`payload verify`需显式`--unity-artifact`。普通候选/复制/采用512MiB单文件上限保持，不将大制品预算静默扩展给任意输入。构建后制品校验失败标记artifact-verification-failed，不拿原生Build成功冒充可认证候选。

## v0.3 Unity 与 Go 合同

`workspace plan/apply/inspect/rebind` 管理工程内 `.beaver/project.json`；`rebind --spec` 显式审阅写区/生成区策略，仍要求旧 profile SHA、固定新计划和 apply。manifest/lock/编辑器版本均为接入身份。

`production plan/apply/recover` 使用 schemaVersion 3，组合精确 `fileEdits` 与原生 batch/resource 步骤；`requiredPackages` 固定已解析版本，缺包在写入前拒绝。资源、JSON 和代码共同受同一写集与恢复见证保护。显式 ProjectSettings 步骤需要两个 Editor 进程：首轮标 pending_editor_reopen，退出后第二进程严格读取磁盘设置、资源断言及全部写集哈希，任一步失败均不能完成事务。若第一进程已输出完整但失败的原生见证，第二进程仅可建立退出后 checkpoint 供受控恢复，状态 checkpoint_verified 永远不能提升为操作成功；编译失败无完整见证仍明确阻断。

`config3 validate/generate/compare` 使用同一 schema 生成并实际解析 C# 与 Go 复杂 JSON，详见 CONFIGURATION-v3.md。

`csharp inspect/rename/rename-sequence/module` 使用实际 Bee 编译上下文；sequence 的 `--spec` 为有序改名请求数组，合同 `beaver-csharp-rename-sequence/1`，在私有源码快照逐阶段编译，生成原工程旧哈希到最终候选的唯一 fileEdits，不直接写工程。模块严格 JSON 读取与序列化兼容边界见 CSHARP-MAINTENANCE.md。

`resource image-inspect/image-produce/validate-step` 为独立图片与封闭资源计划；原生切片/Atlas/TMP/Spine/音频/材质/SO引用按 RESOURCE-PRODUCTION.md。Spine闭包检查与真实播放分开。

`server toolchain/protocol-tools/inspect/generate/module-generate/module-plan/protocol-diff/migration-plan/check/build/compose-plan/migration-state/migration-apply/runtime-inspect` 提供六服 Go 工具，详见 SERVER-GO.md。迁移要求固定候选、计划、Compose归属和当前 schema SHA；实际应用可能产生持久变化，未知/部分状态拒绝盲重放。Compose计划不启动容器，runtime检查不执行游戏业务。

原生Editor进程通过ASCII base64传递UTF8 job路径，由companion严格解码；保留PlaySession中的原路径。子进程继承必要路径/用户/locale、代理证书及已有许可路径，排除PWD/OLDPWD和任意agent环境；不改父进程或全局设置。无效必需环境值在写入前拒绝，诊断仅标变量名。该内部传输变更要求新的固定producer与计划，不用新包恢复旧事务。

## v0.5 UI 工程能力（含原v0.4范围）

新制品0.5.0系列保留旧固定0.4.0 toolkit与0.3事务。公开入口 `ui inspect/analyze/repair-plan`、`wiring plan`、`diagnostics summarize` 见[完整输入和执行边界](DEVELOPMENT-v0.5.md)、[采集合同](UI-INSPECTION.md)、[诊断合同](DIAGNOSTICS.md)。接线和修正仅生成已有batch计划，apply/recover合同不变。`binding.reference`/`binding.event`原生操作在写入时核编译类型/精确身份/当前空值或显式替换；不支持的情况拒绝，不推测fileID或创建空方法。

## Local P0 development commands

Development candidate `0.5.1.dev20261028+fix3` adds `structure inspect/plan`, `build-filter collect/plan`, and `native readback`. This identifies a local candidate; published 0.5.0 artifacts and installations are unchanged. Detailed request and result contracts: [structure audit](STRUCTURE-AUDIT.md), [build filtering](BUILD-FILTER.md), [native readback/capture](NATIVE-READBACK.md). Structure plans use existing batch transactions; native collectors use the existing project/Editor locks and helper ownership cleanup. A blocked plan is not executable, dynamic consumers remain explicit, and preview pixels never imply gameplay or visual parity.

Machine-readable request schemas are in `docs/schemas/`: native-readback-request-1, build-filter-collect-1, structure-mappings-1 and structure-exceptions-1. Cross-field path selection, total pixel/byte budgets, current content hashes and native identities are additionally enforced by the commands. Source provenance uses upstream `monkey-shader-handoff/1`; the independent structure exception file is not an automatic conversion of legacy project configuration exceptions. Folder moves extend the existing `unity plan/apply` route with explicit `directoryMoves`; see [folder transactions](FOLDER-MOVES.md).

`structure inspect` optionally accepts both `--product-root <product>` and `--profile <profile-relative-to-product-or-absolute>`. Without them, discovery is bounded to the Unity directory and one parent; a profile is adopted only when paths.unityProject resolves to the selected Unity project. Structure Docs stay in the bound product root. This validates path binding, not the entire upstream profile schema. Dedicated structure audit/native snapshot/build snapshot inputs use the existing 128 MiB manifest and 8,000,000-node limits; ordinary specs retain 32 MiB/3,000,000-node limits. No global read budget is enlarged.

P0 report commands accept optional `--summary`: full inventory, consumers, hashes and native details remain in the complete report file; stdout contains transport metadata/counts and the normal verified artifact SHA. It is suitable for an outer 4 MiB response boundary without claiming the full response crossed that boundary. `unity recover --transaction <retirement-transaction> --expected-plan <SHA> --editor-path <Unity> [--timeout 600]` explicitly restores witnessed assets.retire deletions; it never overwrites later edits or guesses missing deletion checkpoints.

`unity plan/apply/recover` also accept optional `--summary`. For apply/recover the compact envelope retains native status/plan identity and an actual-change count, pointing to the SHA-bound full transaction journal for every change and identity. The default response is unchanged.

`structure plan` accepts optional `--consumer-resolutions <JSON>`, with the strict `structure-consumer-resolutions-1` schema. Exact file SHA/token span/decoded literal and reviewed evidence can resolve only supported source-identity comparisons; native/runtime lookup and unknown dynamic blockers remain separate. See [consumer declarations](STRUCTURE-CONSUMERS.md).

Scene asset moves in `batch` may bind one exact `ProjectSettings/EditorBuildSettings.asset` postimage. The derived file joins the transaction's read/write/restore sets; this is not a general settings-write exemption. See [scene moves](SCENE-MOVES.md). Native retirement also supports the separately reviewed `source-evidence-only` policy described in RETIREMENT.md; the default still requires persistent native object identities.

## Explicit empty-folder retirement

The existing `unity plan/apply/recover` entry accepts an explicit `empty-folder` retirement policy; see [EMPTY-FOLDERS.md](EMPTY-FOLDERS.md) for its closed spec, source/directory guards and recovery limits. This is a distinct native folder identity path, not recursive file retirement. Previously fixed packages remain immutable and cannot replay new plans.

Move destinations in both `batch asset.move` and `unity assets.move` are preflighted component by component against portable file/directory names (forbidden characters, controls, trailing dots/spaces and reserved Windows device names). Invalid targets fail before output or native writes, with the exact path; existing imported source names are not silently rewritten. See [Microsoft file naming rules](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file). A valid explicit rename remains a new caller-reviewed plan and can change native object names; consumer review remains required.

## Bulk identities and pure-move checkpoint policy

Build-filter collection accepts optional `includeObjectIdentities: true`. The guarded disk snapshot then includes paired persistent `objects` (guid/localId/type/name/state); old fields and partial coverage remain. Exact usage is in [BUILD-FILTER.md](BUILD-FILTER.md). `--summary` carries objectIdentityCount without inlining object rows.

Batch schema 2 may explicitly opt into `checkpointPolicy: "move-delta-v1"` for pure non-Scene asset.move steps. Default behavior is retained. Final full write-set hashes and exact Python post-state matching remain mandatory; a cached delta alone cannot certify success or recovery. Read [MOVE-CHECKPOINTS.md](MOVE-CHECKPOINTS.md) for restrictions and fault semantics. JSON report serialization remains proportional to the complete write set at each step.

Native field queries may supply strict `ownerIdentity:{guid,localId}` while retaining the exact asset/nodePath/componentType/propertyPath. This selects one persistent owner in a duplicate name path and never falls back on mismatch. See [NATIVE-READBACK.md](NATIVE-READBACK.md) and its request schema; the runtime presence flag is derived, and JSON writers must preserve signed64 IDs exactly.

Build policy follow-up: [explicit Development and TMP source protection](BUILD-POLICY.md) defines a closed optional font list, exact before-images, distinct source/build/restored hashes and guarded public recovery. Development is independent of player profile/connection configuration. No arbitrary project build hook is accepted.

Post-exit build font recovery: `unity recover-font-source --transaction <fixed11-transaction> --expected-plan <SHA> --review <review.json> --out <fresh-receipt-directory>` is a separate, closed-Editor, exact-before-image path for explicitly reviewed fixed11 `BUILD_SOURCE_DRIFT` evidence. It does not loosen ordinary implementation-bound recovery or certify the failed App. See [review schema](schemas/build-font-post-exit-recovery-1.schema.json) and [build policy](BUILD-POLICY.md). Native restoration observations are in-process only; final success requires full-source verification by the parent after Editor exit.

Controlled macOS GUI test runtime: `qa prepare --spec <spec> --expected-spec <SHA> [--out <fresh-dir>]`, `qa launch --project <ID> --build <ID> --profile <ID> --expected-owner <SHA> [--duration 60] [--run <ID>]`, and `qa collect` with the same identities plus required `--run` and optional `--out`. See [QA runtime](QA-RUNTIME.md) and [closed spec](schemas/qa-runtime-spec-1.schema.json). Preparation copies verified Bundle bytes/modes/internal links and records actual signatures; it does not launch. Data configs/logs/explicit test profile are under Application Support, profile owner identity persists across builds, and seed applies only on initial creation. GUI/source-file-access/save-resume remain explicit consumer verification; no TCC alteration or source-debug-string access inference.

Managed SDK preflight for Unity adoption is documented in [ADOPTION-ASSEMBLIES.md](ADOPTION-ASSEMBLIES.md). Plans retain the existing CLI but add hash-bound `managedAssemblyCompatibility`; optional exact manifest `managedAssemblyPolicy` permits only new isolated disjoint role pairs, never existing SDK migration. Build certification requires Succeeded and integer buildErrors=0.


## SDK migration and attach-only App binding (development)

Explicit `adopt plan --sdk-migration FILE --expected-sdk-migration SHA256` uses the existing immutable adoption transaction. See [SDK-MIGRATION.md](SDK-MIGRATION.md) for complete byte/MVID/native MonoScript/role/reference requirements, rollback, and unsupported cases. The default collision guard above remains unchanged; only this explicit policy permits the supported canonical migration.

`qa inspect-instance`, `qa bind`, and `qa input` are documented in [QA-BINDING.md](QA-BINDING.md). They require a strongly captured owned launch, explicit run and owner hash, and existing host AX permissions. Binding/input never launches an App or falls back to name/BundleID/global input. Kernel guards plus PID-directed posting are not atomic and do not establish business acceptance. Fixed/runtime and consumer validation status is recorded in PLAN.

Additive intake has separate `beaver-additive-intake/1` (spec1), `beaver-additive-intake/2` (spec2) and `beaver-additive-intake/3` (spec3) contracts and closed [specification](ADDITIVE-INTAKE.md). It does not relax `beaver-adopt/1` or replace the exact prior baseline required by that operation.

Fixed26 newScripts may use five native phases (preflight, code staging, independent code-check, asset import, independent verify). Set the outer apply budget to at least 5*inner+310 seconds and rollback to at least 2*inner+160; if an 1800-second outer cap applies, inner<=280 is conservative. No-script operations retain their smaller actual phase count but cannot relax the caller budget for a declared newScripts plan. Old transactions require the exact original implementation.

Fixed27 keeps contract3/spec1,2,3 and the same phase budgets. Successful newScripts intake also reports watcherPolicy=declared-new-script-resolution/1, watchersChecked and watcherResolutions. These are bounded static compiler-reference observations; source partial/exit1 and old transaction runtime requirements remain unchanged.

Spec4/`beaver-additive-intake/4` adds explicit `engineObjects` identities (GUID/localID/type/assembly/name/native asset path) with native preflight, importer boundary and independent cold/rollback checks. It inherits spec3/newScripts/Character and the existing phase count/budgets; argv is unchanged. Raw serialized built-in references must be exact declared PPtrs with type0; no GUID-domain exemption or importer-meta engine references. Plan/apply add engineObjects count and apply engineObjectPolicy=declared-native-builtins/1. This verifies declared target-engine identities, not original-source mesh/Shader semantic or visual equivalence; source partial remains. Old plans/transactions require their original implementation.


Spec5 additive intake extends spec4 with explicit retained runtime assembly identities (`retainedAssemblies` rows: target/guid/sha256/metaSha256/name), strict schema-only new C# sources and native compilation-scope checks. It never imports or rewrites asmdef/asmref files. See ADDITIVE-INTAKE.md and schemas/additive-intake-5.schema.json. Argv and native phase budgets remain unchanged; specs1–4 keep their prior boundaries.
