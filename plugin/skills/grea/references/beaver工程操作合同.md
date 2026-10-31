# beaver 工程开发工具接入

GREA 维护 Skill 与方法，monkey 恢复独立候选，beaver 执行开发工程操作。完整执行链两者必选，按阶段使用；已有工程不为形式重导。旧 GREA 工具 ID 保留，未经完整合同和消费者验证不退休。

当前源码模块锁指定正式 beaver **0.5.0**（见 `modules.lock.json`）：保留 0.3/0.4 合同和 23 个 `beaver tool <id>` 工具，新增本页的五个 UI/接线/诊断入口。GREA 的委托工具通过已绑定 provider 或随包 wheel 执行。历史 0.1/0.2/0.3/0.4 精确实现仍可按原 lock 使用，不自动升级绑定或重放旧事务；0.3.x 无 `tool` 子命令，不能用于委托工具。

版本之外还需核producer实现身份。当前支持的精确实现及wheel以已安装的模块锁、GREA适配器和调用生成的lock为准；不在Skill重复维护哈希清单。相同版本号不能替代字节核验，未知实现拒绝。

## 发现与固定绑定

`beaver_pipeline discover` 只读搜索标准用户安装位置、`grea_modules install` 的模块安装、PATH或已有绑定，不启动程序、联网或安装。多个不同安装为 ambiguous；坏绑定不静默换版本。`GREA_PROVIDERS` 显式配置优先：

```json
{"schema_version":1,"providers":{"beaver":{"command":["/absolute/isolated/bin/beaver"],"probe":["/absolute/isolated/bin/beaver","capabilities"],"systems":["Darwin"]}}}
```

beaver `capabilities` 默认JSON，没有 `--json`。GREA读取 `beaver-result/1` 的 producer/version 和 data中的 `beaver-capabilities/1`。包文件、启动程序/解释器及稳定能力字段固定到 lock，忽略每次变化的operationId。

0.2还须声明 `beaver-batch/2`、`beaver-batch-transaction/2`、`beaver-unity/1` 和 `beaver-adopt/1` 及对应能力；缺失、重复声明或未知版本不就绪。不同版本分别使用显式provider配置与lock，不能只编辑lock里的版本号。monkey显式命令覆盖只表示可发现，不等于已绑定。

支持0.3系列/0.4/0.5的固定实现还核 `beaver-project/1`、`beaver-production/3`、`beaver-production-transaction/3` 与明确组合能力ID。包内Python、C#、Go模板/配置/许可均进入producer实现身份，再由GREA核包文件和launcher锁。相同版本号但未知producer也拒绝；旧原生事务不能换实现重放。旧0.1/0.2能力摘要算法保持不变。

- `pin --identity-root PACKAGE --output NEW`：显式核实际导入的包，写NEW/beaver-lock.json；不修改全局安装或客户端配置。
- `check --config LOCK --output NEW`：核包、程序和能力身份。无锁仅探测成功也不是完整执行链就绪。
- `toolchain_check --beaver-config LOCK --output NEW`：同时检查固定monkey/beaver。缺失、不兼容或漂移为needs_action，不回退旧实现。
- 原 `inspect --config LOCK --project PROJECT --output NEW` 保持兼容，只做工程上下文检查。

## 命名操作转发

CLI/MCP共用 `beaver_pipeline invoke --config LOCK --request REQUEST --output NEW`。请求以生成Schema（GREA 安装根目录资源 `schemas/beaver-operation.schema.json`；实际参数先用 `describe-tool`/工具 `--help` 核对）为准，只有命名操作/参数，不接受raw argv、shell或任意输出覆盖：

```json
{
  "schema_version": 1,
  "operation": "payload.verify",
  "options": {
    "root": "/absolute/payload",
    "manifest": "/absolute/artifact-manifest.json"
  },
  "timeout_seconds": 30
}
```

| 操作 | beaver原CLI | 关键约束 |
| --- | --- | --- |
| project.inspect、code.inspect | project inspect、code inspect | 显式project；静态上下文/代码检查不是原生通过 |
| adoption.plan/apply/rollback | adopt plan/apply/rollback | 冻结候选/基线；apply需plan和expected-plan；恢复仍受beaver后续修改保护 |
| unity.plan/apply | unity plan/apply | plan输入spec；apply的真实能力取自plan.spec.operation，不能用泛化apply声明绕过能力检查 |
| payload.verify/plan/apply | payload verify/plan/apply | 精确manifest/目标；apply需expected-plan，不复制一套物化算法 |
| config.validate/generate | config validate/generate | 显式schema/input；生成器和运行时校验归beaver |
| image.inspect/compress | image inspect/compress | apply需expected-source；实际图像处理依赖由beaver判定 |
| player.run | player run | manifest和expected-manifest、显式duration；仅限本次授权的自有进程 |
| batch.plan/apply/recover（0.2/固定0.3） | batch plan/apply/recover | spec交provider验证；apply需beaver-batch/2计划和expected-plan；恢复需原事务与匹配执行器，不复放其他版本事务 |
| references（0.2/固定0.3） | references | 显式project，可选外部cache文件；未知动态加载键保留partial，不把缓存当执行前置身份 |
| debug.start（0.2/固定0.3） | debug start | manifest/expected及duration；自有后台worker预算1–3600秒；width/height须成对且64–8192 |
| debug.inspect/stop/tail（0.2/固定0.3） | debug inspect/stop/tail | 只消费明确session.json；stop仅请求自有worker停止；tail的lines为1–500 |
| debug.screenshot/target（0.2/固定0.3） | debug screenshot/target | screenshot登记调用者已有图片及expected哈希，不负责截图或认证来源；target读取事务证据，不连接外部Editor |

路径必须为绝对路径。provider新输出由GREA固定在本次回执内 `provider-output`（图片为provider-output.png）；目标工程/资源目录由请求显式声明，并仍由beaver检查计划/写区/恢复约束。原生apply需editor-path及timeout，Player需duration；外层timeout_seconds至少多留10秒，MCP run_tool预算也应覆盖整个请求和就绪检查。

`debug.start`是异步会话：duration为worker生存预算，与本次启动调用的timeout_seconds分别约束，不要求RPC等待完整会话。它仍是实际进程操作，须有本次任务授权。`payload.verify`的 `unity-artifact:true` 只在0.2或固定0.3可用，显式启用 `beaver-unity-build/2` 的4GiB单文件/8GiB总预算；普通payload预算不因此变大，实际大制品核验复用对应上游证据。

GREA请求/lock JSON上限8MiB；apply计划读取上限128MiB，与provider计划预算对齐，不扩大请求或响应内联预算。

调用前核两项依赖及选定能力，调用后复核包/程序身份，保留provider原始状态、诊断与验证层。partial/blocked/failed/not_run不升级成功；退出码和声明状态不符、截断或身份漂移均不放行。请求JSON不授予额外写入或运行权限。

MCP `run_tool`外层的finding/partial只表示适配进程的诊断出口，必须读取 `parsed_stdout.status` 或本次 `result.json`，其中保留真实blocked/partial及provider诊断。0.1异常分支的blocked＋exit2仍按不一致返回needs_action；0.2实际blocked＋exit3已验证，不为兼容而放松状态检查。

## 固定0.3系列与0.4的有限适配

GREA请求仍是schema_version1的命名参数封装。工程spec与执行数据由beaver维护，不复制其解析/改名/资源或Go执行实现：

| 路由（须匹配具体producer及能力声明） | 外部合同与边界 |
| --- | --- |
| workspace.plan/apply/inspect/rebind | spec schemaVersion1；工程profile为beaver-project/1，apply需beaver-project-setup/1计划及expected-plan；rebind需expected-profile，可显式spec及accept-authority-change |
| production.plan/apply/recover | spec与计划schemaVersion3、beaver-production/3；实际写区/独立输入/旧新哈希/包版本/恢复由beaver检查，apply还需expected-plan、editor-path和timeout |
| config3.validate/generate/compare | 外部配置schemaVersion2；validate可带tables/project，compare使用before-schema/after-schema及可选before-input/after-input；C#＋Go生成物仍需项目实际读取验收 |
| csharp.inspect/rename/rename-sequence/module | 显式spec/project及可选toolchain；rename-sequence/1只生成独立语义候选；module默认grea-unity-project/1.0.0的Bootstrap/Domain/Gameplay/Presentation/Services五层，不自动导入工程 |
| resource.image-inspect/image-produce/validate-step | 封闭policy/spec，image-produce必须expected-source；validate-step不执行原生资源操作 |
| server.generate/module-generate/module-plan/protocol-diff/migration-plan/compose-plan/toolchain | 仅候选/计划/有限检查；generate可能调用显式固定protoc，module生成可使用gofmt，Compose计划不启动服务；依赖缺口由provider原样返回 |

组合ID按固定能力声明逐项映射，例如workspace.inspect只能使用 `workspace.plan/apply/inspect/rebind`，不能把任意斜线字符串展开成授权。公开结果Schema（GREA 安装根目录资源 `schemas/beaver-result.schema.json`；实际参数先用 `describe-tool`/工具 `--help` 核对）限定beaver-result/1外壳、producer、状态/诊断/制品和验证字段；对适配器支持的固定实现启用，不改变旧消费者；data仍属provider合同，GREA不重新判定游戏业务。

`actualChanges`逐项可为非空路径字符串（原生batch/production的已变路径）或对象摘要（操作/恢复/失败见证）；GREA原样保留，不强转对象，数字/null/数组和空字符串仍拒绝。执行后才发生的Schema、身份或退出码校验失败会保留 `executed=true`、原provider结果和事务，顶层native记unverified并提示检查回执；不能据外层needs_action/error推断零写入或自动重放apply。离线重验与实际再次执行分开记录，原失败回执不追改。

未接入项：server.inspect虽有CLI但候选未声明其能力；server.protocol-tools/check/build及migration-state/migration-apply/runtime-inspect不在此次有限适配范围，禁止以raw argv兜底。Creator执行/构建仍不支持。完整清单见registry中的unsupported_v03。


## 交付判断

工具安装、能力发现、参数转发、原生事务、独立重开、Player真实输入和业务结果是不同证据层。返回的producer/status/verification仅支持其明确范围；上游样本和项目采用历史不证明本次目标通过。保留旧lock与事务，切换实现后不重放旧事务；业务缺口与工具失败分别定位。

## 固定0.5的UI接线与诊断

GREA源码支持明确固定的beaver 0.5.0（来源main `e0c7e0c`），实际producer须匹配适配器；不接受任意0.5.x。默认随包模块仍由模块锁决定，不因此更新用户安装或旧绑定。新包先按本页发现/固定绑定流程使用独立lock，旧事务仍交原producer处理。

以下五项均通过现有`beaver_pipeline invoke`，请求仍是`schema_version/operation/options/timeout_seconds`。所有路径使用绝对路径；报告输出由适配器固定在新回执的`provider-output`，调用者不能覆盖`out`。具体字段由安装根`schemas/beaver-operation.schema.json`提供。

| operation | options | 执行与结果边界 |
| --- | --- | --- |
| `ui.inspect` | project、spec、editor-path、timeout | 启动指定Editor做原生静态采集，可能导入和使用临时辅助代码；不是普通文件只读。外层预算至少比timeout多10秒。GREA本轮只核参数，未重跑Editor。 |
| `ui.analyze` | snapshot、spec | 分析调用者快照，保留caller-supplied来源标记；不认证真实采集、物理输入或视觉。 |
| `ui.repair-plan` | project、snapshot、spec | 显式布局/字号修正降为既有batch计划，不自动应用、不从告警猜美术预期。 |
| `wiring.plan` | project、snapshot、spec | 按实际类型/精确身份或显式角色选择唯一目标；歧义/漂移/非空绑定保护不满足则blocked，不生成可执行计划。 |
| `diagnostics.summarize` | input（1～256条绝对文件路径数组）、可选limit（1～10000） | 只读显式日志/回执并生成新报告；重复`--input`按原顺序转发，未知原因不编造，写后拒收不当零写入。 |

例：`{"schema_version":1,"operation":"diagnostics.summarize","options":{"input":["/evidence/journal.json","/evidence/editor.log"],"limit":100},"timeout_seconds":30}`。旧操作的options和退出码不变，新增input数组只适用于该诊断操作。

UI spec包含`schemaVersion:1`、mode和显式assets；静态模式为`static-prefab`或`static-scene`。预期值逐项写asset/nodePath/componentType/field/equals及来源。运行状态须由已Play的Editor显式调用公开`BeaverUIInspection.Collect(liveRoot,label)`采集，再交analyze；静态inspect不假装runtime。中心射线采样只说明该状态下的命中，不是物理点击，条件隐藏/禁用也不自动构成缺陷。

接线spec为`schemaVersion:1`与bindings，条目含asset/nodePath/componentType/field/source，目标通过精确target或targetRole/roles给出；没有显式target时只接受类型兼容的唯一候选。Sprite等子资源GUID/localId来自原生回读，不猜fileID。仅支持已声明的Prefab单值引用及Button到真实public instance void()方法；数组、复杂泛型、动态方法和持久化Scene接线未支持。非空引用只有显式replace才可替换；事件不覆盖已有监听，不生成空方法。

修正spec包含`schemaVersion:1`与repairs，每项明确asset/nodePath/componentType/field/mode/value/source。计划保留来源/meta哈希；输出的batch计划及摘要按既有`batch.apply`合同和本次授权执行，使用生成它的固定producer。保存/重载是另一层检查，不把计划通过写成应用成功。

诊断原输入保留，报告带路径/哈希/JSON指针或日志行。跨文件关联需要同一显式操作身份或匹配的stdout路径/哈希；writeSet不等于actualChanges。外层partial/finding继续读内部provider状态，执行后失败只查原事务与实际写集，不自动重放。GREA只验证上述转发、规划/分析和状态保留；原生执行、真实窗口效果与正式游戏采用按项目证据另记。

## 固定本地 P0 候选

源码优先显式绑定 `0.5.1.dev20261029+fix8`，仅接受 producer `6e81b67b87a3b5fd4d965dbe952672ca99c9e4149a678863c39f3706165211f3`（上游提交 `1b44c0b7fc3073f4ae0a8719e9c9fea4956f8b62`，wheel SHA `e9cacdd3ee54c06f960b089c34c8e153c6081438a69d18e0501aa066d0f4599f`）。初版与fix1/fix2/fix3/fix6/fix7继续按原固定锁处理在途链，不自动重放或升级旧事务。这不是默认安装版本；正式 `modules.lock.json` 仍固定发布版。沿用 `beaver_pipeline pin/check/invoke` 与 `schema_version:1` 命名请求，不透传任意参数。旧固定版本不能调用以下新增路由。

| GREA operation | 精确 beaver CLI 与输入 |
| --- | --- |
| structure.inspect | `structure inspect --project`，可选 `--snapshot --exceptions`；fix3/fix6/fix7/fix8另可显式成对给 `--product-root --profile`，自动独立 `--out` |
| structure.plan | `structure plan --audit --mappings`，可选 `--snapshot`，自动独立 `--out` |
| build-filter.collect | `build-filter collect --project --spec --editor-path --timeout`，自动独立 `--out` |
| build-filter.plan | `build-filter plan --project --snapshot --sources --target`，自动独立 `--out`；target 是 `{platform,pipeline}` JSON 文件路径，sources 是来源交接 JSON 路径 |
| native.readback | `native readback --project --spec --editor-path --timeout`，自动独立 `--out` |

路径参数使用绝对路径。原生调用显式给 timeout（1～1700秒），外层 `timeout_seconds` 至少多10秒；请求不能覆盖 out。示例命名请求：

```json
{
  "schema_version": 1,
  "operation": "structure.inspect",
  "options": {"project": "/absolute/Unity", "exceptions": "/absolute/structure-exceptions.json"},
  "timeout_seconds": 30
}
```

结构例外/类型映射见[工程目录与资产归类](../../grea-develop/references/Unity工程目录与资产归类.md#恢复脚本与严格目录例外)。映射文件为旧新路径的显式列表；原生快照必须匹配当前内容与持久 GUID/localID。结构计划的 `batchReadiness=not_evaluated`，blocked 不给可执行 batchSpec；declaration_only 也须经过既有 batch plan 的前置检查，不能直接视为可执行。

collect 请求为封闭 `schemaVersion/platform/renderPipeline/assets/roots`（assets 是启用场景，roots 是显式额外根）；native readback 请求含 `schemaVersion/assets`，可按候选 Schema 声明 queries/aliases/capture。Schema 与交叉预算由固定 beaver 校验，GREA 不复制解析器。采集返回 data 中的 report 路径及 verification.native；帮助/参数预检不证明 Editor 连接。预览截图不执行 Play，不证明输入或视觉正确。

build-filter 读取 `monkey-shader-handoff/1` 的来源、当前文件 hash/字节和原生 GUID/localFileID 映射。`source-text` 只证明来源文本；平台编译物/恢复二进制保留证据属性，未知不猜。结果逐项 `buildState` 可为 runtime-referenced、source-evidence-only 或 unknown；原样保留 data。当前隔离仅为计划，outer blocked/exit3，`execution.status=blocked`；不能据未被静态依赖引用就搬走或删除，也不自动换 Shader。新增隔离执行不在此次已验能力内。

本地适配已验证固定包身份、五项命令参数及合成分类/阻断结果；未在 GREA 侧新增运行 Editor、Player、真实输入或业务验收。上游原生证据与消费者项目采用分别记录。

fix1 允许对旧场景路径逐项整改，不再以尚存旧场景全局阻断其他可独立迁移；剩余问题保留 `remainingStructureIssues`，`projectConformance=not-established` 不升级为规范通过。合成旧场景正向规划与报告制品 SHA 已核，执行及构建场景更新仍须项目单独验收。

fix2 结构审计以 `scannedInputPaths` 固定完整扫描输入闭包；旧 audit 缺闭包必须重做 inspect，不能手填字段绕过。审计后新增消费者或元数据会阻断旧计划，需重新审计并检查差异。生成器/旧路径消费者阻塞与单纯剩余结构问题分开，不能把 declaration_only 解释为消费者已更新或整个工程合规。

fix3 的 product-root 是产品绑定范围，Unity 工程与结构说明可在其不同子目录；它不代表冻结整个产品树。profile 必须位于该产品内且 paths.unityProject 精确指向所选工程。未显式给参数时只查 Unity 根及其上一层的 grea-project.json；不向更高层猜测。GREA 在调用前按现行完整 PROFILE Schema 检查匹配配置并核调用后哈希；beaver只负责路径绑定与治理文件身份。缺配置由审计报告，配置不满足完整 Schema 则阻断主操作，不把只具备最小绑定字段当标准配置通过。上述绑定参数只对 fix3/fix6/fix7/fix8 开放，旧固定链不新增要求。

Integer/ArraySize 原生回读兼容保留 value 字符串，另有 hasIntegerValue 与整数 integerValue；只有 hasIntegerValue=true 才读取后者，不把默认0解释为实际结果。GREA原样保留 provider data，不把字符串强转为整数。原生采集证据归实际执行者，本轮GREA只读核验上游固定回执及制品哈希，没有重跑 Editor。

上游报告专用读取预算为128MiB/8M节点，普通请求读取限制不因此增加。GREA薄入口请求仍8MiB、外层stdout仍4MiB；超出外层预算按不完整回执处理，不能说大报告已通过MCP。大报告可显式使用已固定beaver CLI并保留报告文件，不能绕过身份/退出状态校验；fix3及更早候选没有已验的紧凑报告传输；fix6新增支持见下文。retirement执行闭环未包含在fix3核心包内，不能将fix6证据回写为旧版已实现。

### fix6摘要与受控退役

`structure.inspect/plan`、`build-filter.collect/plan`、`native.readback` 和 `unity.plan/apply/recover` 可在命名请求 options 中显式给 `summary: true`，对应 `--summary`，仅固定fix6/fix7/fix8可用。它保留完整报告文件及SHA，stdout只含传输元数据/计数/状态；不能把计数当作已查看完整清单。GREA仍以4MiB捕获外层响应，并流式核报告制品（单件128MiB、合计256MiB）；完整证据由 `provider_result.artifacts` 指向，已核字节身份另记 `provider_artifacts_verified`。缺少必需报告、文件漂移或超预算保持需处理，不自动重放。当前源码stdio MCP已通过5.25MB合成报告的摘要转发与文件hash验证，已装插件/当前宿主会话并未因此更新。

原生采集覆盖不完整时，provider可返回partial/exit1。原验证层、coverage/blockers、原生已完成部分与完整报告均保留；partial不是完整目录、可构建或游戏通过，不能丢掉回执只报失败。传输截断、身份变化和状态/退出码不符仍拒绝，不因有摘要而放宽。

`structure.plan` 新增可选 `consumer-resolutions` 文件路径，只转发给固定fix6/fix7/fix8。声明逐项绑定已审计C#文件的原始SHA、精确token span、解码字面量、人工审阅理由和证据；只可解释受支持的来源身份比较，不能豁免Resources查找、未知动态键或缺失原生身份。来源旧路径是证据时保留，不为消警把来源字符串改成当前资源路径。接受的声明仍是调用者断言，后续业务/动态加载须实际验证。

退役使用现有 `unity.plan` 及 `unity.apply`，spec的operation为 `assets.retire`，不另建删除执行器。每个文件给role/reason/sourceEvidence，指定有meta的protectedRoots；Resources下文件另有精确key/path/GUID的退役决定。普通文件与下节明确的empty-folder事务分开；非空目录不退役，静态依赖或动态使用未知不能当作无引用。默认native-object要求真实非空持久localIDs；显式source-evidence-only只适用于guarded快照中确有零对象的证据文件，逐行给sourceIdentityEvidence的snapshotPath、原始文件snapshotSha256和assetPath。应用时重新导入确认仍零对象，保留真实GUID与空localIDs，不能拿取ID失败冒充零对象，不能编造localID。

恢复新增命名路由 `unity.recover`：options必须给transaction、expected-plan、editor-path、timeout，可给summary；不接受out。它仅恢复有原生删除检查点、完整before-images且当前after状态仍匹配的退役事务。恢复可能已写回字节但原生核验未通过时保持recovery-required，不能推断零写入或用新producer盲重放旧事务。实际apply/recover须符合当前用户写入范围；GREA本轮只验规划和转发，原生执行证据归上游。

Scene移动继续用 `batch.plan/apply/recover`；计划派生的sceneSettings只允许精确EditorBuildSettings路径值变化，将前后字节/GUID/开关/顺序纳入写集与恢复。首进程pending不是通过，独立Editor核持久化；这不是通用Settings写权限。上游两Scene实证绑定其preseal producer；最终包仅按完全相同batch.py/BeaverBatch.cs组件SHA复用，不称最终整体producer重跑。原生退役的最终producer实证与Scene组件复用分开，均不证明视觉、物理输入或玩法。

### fix7空叶目录与目标路径

空目录仍有meta/GUID和可能的引用，不按普通文件删除。`assets.retire` 继续使用同一命名入口；仅 `identityPolicy=empty-folder` 的folder-only事务可处理确实没有任何子项的叶目录，不能与文件退役混用。每行保留role/reason/sourceEvidence，加callerReview：reference、sourceSha256、directorySetSha256、dynamicPathReview（status为reviewed-no-use、reason、evidence）；protectedRoots仍必填。隐藏文件、子目录、符号链接均使其不再是可退役空叶，不得先删这些内容来凑条件。

审阅绑定必须使用所固定候选Python读取：`sha(encoded(source_files(project)))` 与 `directory_guard(project)["sha256"]`（source_files/directory_guard来自beaver.unity，sha/encoded来自beaver.io），不能手算另一种目录口径。目录集合包含Assets下空目录和隐藏目录，计划后新增/改变会失效；两个hash只是输入身份，dynamicPathReview仍是调用者审阅声明，不是动态无使用的工具证明。静态文本GUID/路径及Assets/Packages原生依赖会阻断，无法读取依赖也不放行。

执行必须原生回读真实DefaultAsset GUID和非零localID后使用DeleteAsset并独立重开；不能用固定ID填充。恢复只接受有明确删除检查点、原前像与当前after状态匹配的事务，恢复空目录及精确meta，再分别核身份、全源文件和目录集合。新出现的空目录或后改内容不会被覆盖，歧义保持recovery-required。summary中的deletedFoldersCount和restoredFiles原样保留，后者按实际文件/meta恢复数解释，不把目录数量改写成文件数量。

unity/batch move在任何原生写入前检查目标组件的非法字符、末尾点/空格及保留设备名，并返回具体路径；不改既有来源名，不静默重命名。目标不合法时由调用者审阅显式合法目标并生成新计划。fix7不包含大批次优化；旧Scene证据仍是此前版本/组件边界，不能升级成fix7整体原生重跑。GREA本轮仅验合成规划/拒绝和固定包原回执，未执行删除、恢复或游戏操作。

### fix8批量对象配对与移动checkpoint

两个新增开关都写在现有spec中，不是新CLI命令或GREA options参数：

- build-filter collect spec可显式 `includeObjectIdentities: true`，默认不加objects且旧字段保持。完整磁盘快照每个asset.objects记录实际配对的guid/localId/type/name/state=persistent；使用配对行，不把独立localIds与types做笛卡尔组合或按索引猜配。保留合法空name、负非零localID；name为null、身份未知或查询失败保持unknown/partial，不能补猜。零对象记录objects:[]，不把它解释为读取失败或可运行资产。
- batch schema2可显式 `checkpointPolicy: "move-delta-v1"`，仅用于非空、纯非Scene asset.move列表，没有runtimeRoot或额外readPaths。未给字段时旧全写集checkpoint策略不变；Scene/混合步骤继续旧策略，不能为了使用增量而漏掉依赖。

对象配对由真实AssetDatabase/IsPersistent回读；源文件、meta、保护闭包、覆盖缺口和报告128MiB/8M节点预算保持。采集返回摘要给objectIdentityCount，完整objects只在SHA绑定磁盘快照内；该计数不是源组件分母、Prefab完整恢复率或动态闭包证明。GREA只核上游原回执、字段/哈希与转发，不将其算作本轮新原生采集。

增量模式保留初始完整writeSet哈希，每步仅重hash移动源/目标与meta及新父目录meta；缓存delta仅供观察，不是当前源状态证书。成功及可恢复失败必须有完整full-final落盘、全部路径覆盖及Python完整post-state一致，后改或缺full-final拒绝恢复。逐步完整JSON序列化与退役checkpoint成本仍在；上游128小资产的33886→1120原生hash读取计数不能外推大游戏耗时。原生性能/失败恢复证据仍归对应固定producer，本轮GREA只做合成只读规划。
