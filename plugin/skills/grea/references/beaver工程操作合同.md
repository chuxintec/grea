# beaver 工程开发工具接入

GREA 维护 Skill 与方法，monkey 恢复独立候选，beaver 执行开发工程操作。完整执行链两者必选，按阶段使用；已有工程不为形式重导。旧 GREA 工具 ID 保留，未经完整合同和消费者验证不退休。

当前源码模块锁指定 beaver **0.4.0**（见`modules.lock.json`，不表示已发布或本机已安装）：0.3.0 全部合同不变，另含从 GREA 移入的 23 个执行工具，以 `beaver tool <id>` 运行；GREA 中这些工具 ID 带 `delegate`，`run-tool`/MCP/类型化操作自动转到已绑定的 beaver。仍保留固定 beaver **0.1.0 / 0.1.0.dev1 / 0.2.0** 与下列 0.3 精确实现的有限适配；旧 lock 继续绑定各自原包，不自动切换。0.3.x 绑定没有 `tool` 子命令，委托工具在其上返回 provider 错误。

版本之外还需核producer实现身份。当前支持的精确实现及wheel以已安装的模块锁、GREA适配器和调用生成的lock为准；不在Skill重复维护哈希清单。相同版本号不能替代字节核验，未知实现拒绝。

## 发现与固定绑定

`beaver_pipeline discover` 只读搜索标准用户安装位置、`grea_modules install` 的模块安装、PATH或已有绑定，不启动程序、联网或安装。多个不同安装为 ambiguous；坏绑定不静默换版本。`GREA_PROVIDERS` 显式配置优先：

```json
{"schema_version":1,"providers":{"beaver":{"command":["/absolute/isolated/bin/beaver"],"probe":["/absolute/isolated/bin/beaver","capabilities"],"systems":["Darwin"]}}}
```

beaver `capabilities` 默认JSON，没有 `--json`。GREA读取 `beaver-result/1` 的 producer/version 和 data中的 `beaver-capabilities/1`。包文件、启动程序/解释器及稳定能力字段固定到 lock，忽略每次变化的operationId。

0.2还须声明 `beaver-batch/2`、`beaver-batch-transaction/2`、`beaver-unity/1` 和 `beaver-adopt/1` 及对应能力；缺失、重复声明或未知版本不就绪。不同版本分别使用显式provider配置与lock，不能只编辑lock里的版本号。monkey显式命令覆盖只表示可发现，不等于已绑定。

支持0.3系列/0.4的固定实现还核 `beaver-project/1`、`beaver-production/3`、`beaver-production-transaction/3` 与明确组合能力ID。包内Python、C#、Go模板/配置/许可均进入producer实现身份，再由GREA核包文件和launcher锁。相同版本号但未知producer也拒绝；旧原生事务不能换实现重放。旧0.1/0.2能力摘要算法保持不变。

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

GREA源码支持明确固定的beaver 0.5.0（来源main `9d15c50`），实际producer须匹配适配器；不接受任意0.5.x。默认随包模块仍由模块锁决定，不因此更新用户安装或旧绑定。新包先按本页发现/固定绑定流程使用独立lock，旧事务仍交原producer处理。

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
