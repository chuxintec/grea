# beaver 工程开发工具接入

GREA 维护 Skill 与方法，monkey 恢复独立候选，beaver 执行开发工程操作。完整执行链两者必选，按阶段使用；已有工程不为形式重导。旧 GREA 工具 ID 保留，未经完整合同和消费者验证不退休。

GREA **2026.10.27** 随包发布 beaver **0.4.0**（`modules.lock.json`）：0.3.0 全部合同不变，另含从 GREA 移入的 23 个执行工具，以 `beaver tool <id>` 运行；GREA 中这些工具 ID 带 `delegate`，`run-tool`/MCP/类型化操作自动转到已绑定的 beaver。仍保留固定 beaver **0.1.0 / 0.1.0.dev1 / 0.2.0** 与下列 0.3 精确实现的有限适配；旧 lock 继续绑定各自原包，不自动切换。0.3.x 绑定没有 `tool` 子命令，委托工具在其上返回 provider 错误。

| 包 | 版本 | 实现SHA256 | wheel SHA256 |
| --- | --- | --- | --- |
| GREA 2026.10.27 模块 | 0.4.0（0.3.0 + toolkit） | 06a710a70b8e9257e68e6e3b83a34db41e7e1f4e32b2810fe80367db518717f7 | 9d509f509c574a91e18e17053f11f4ce3fa37a27a857600c2791287876eb4ed8 |
| 07 | 0.3.0.dev1 | b6400dbd7ca13426ce68a2c4034fb647795e3876d38b26c98d2a98e4ee8bc3c0 | 7f085738b5a10a1da72e76debb4eee5641f066abbc89355dcb3c67a2d0c72f10 |
| 08 | 0.3.0 | e6191235381d587870291b8a01ba492b4dac4b2f7faeced50590dbc1342f0882 | 66fd8d326806cb275fa68fc319d46ca679b5ef3fee1b3f525e1e1a51a62a4321 |
| 09 | 0.3.0，08的元数据等价包 | 与08相同 | b480fb381a85e8c47711d03169a625725b06648393bcf1e9a91fa1272116d2df |
| final（本地最终包） | 0.3.0，运行文件同08/09 | 与08相同 | d4dd7229fa9ce56eabb9054d0af2b88591aa0777fe4e3d0fc139b74a105eb598 |

## 发现与固定绑定

`beaver_pipeline discover` 只读搜索标准用户安装位置、`grea_modules install` 的模块安装、PATH或已有绑定，不启动程序、联网或安装。多个不同安装为 ambiguous；坏绑定不静默换版本。`GREA_PROVIDERS` 显式配置优先：

```json
{"schema_version":1,"providers":{"beaver":{"command":["/absolute/isolated/bin/beaver"],"probe":["/absolute/isolated/bin/beaver","capabilities"],"systems":["Darwin"]}}}
```

beaver `capabilities` 默认JSON，没有 `--json`。GREA读取 `beaver-result/1` 的 producer/version 和 data中的 `beaver-capabilities/1`。包文件、启动程序/解释器及稳定能力字段固定到 lock，忽略每次变化的operationId。

0.2还须声明 `beaver-batch/2`、`beaver-batch-transaction/2`、`beaver-unity/1` 和 `beaver-adopt/1` 及对应能力；缺失、重复声明或未知版本不就绪。不同版本分别使用显式provider配置与lock，不能只编辑lock里的版本号。monkey显式命令覆盖只表示可发现，不等于已绑定；本轮隔离验证复用已核0.4绑定的私有快照。

固定07和08实现还核 `beaver-project/1`、`beaver-production/3`、`beaver-production-transaction/3` 与明确组合能力ID。包内Python、C#、Go模板/配置/许可均进入producer实现身份，再由GREA核包文件和launcher锁。相同版本号但未知producer也拒绝；旧原生事务不能换实现重放。旧0.1/0.2能力摘要算法保持不变。

09与08的68个beaver文件逐成员一致，仅dist-info/METADATA、RECORD变化；独立安装/固定绑定及版本/能力核验通过，复用08的CLI/stdio结果，不重复引擎验收。切换08/09仍须针对实际安装路径新建显式lock，不修改旧lock的路径。

本地final包239672字节，相对09仍只有METADATA/RECORD变化，68个运行文件与08/09完全相同；已核字节等价，复用既有安装、45项适配检查和CLI/stdio，不为文案封装修正重跑或重新安装。final文件名不表示已发布到远端。

- `pin --identity-root PACKAGE --output NEW`：显式核实际导入的包，写NEW/beaver-lock.json；不修改全局安装或客户端配置。
- `check --config LOCK --output NEW`：核包、程序和能力身份。无锁仅探测成功也不是完整执行链就绪。
- `toolchain_check --beaver-config LOCK --output NEW`：同时检查固定monkey/beaver。缺失、不兼容或漂移为needs_action，不回退旧实现。
- 原 `inspect --config LOCK --project PROJECT --output NEW` 保持兼容，只做工程上下文检查。

## 命名操作转发

CLI/MCP共用 `beaver_pipeline invoke --config LOCK --request REQUEST --output [NEW`。请求以生成Schema](../../schemas/beaver-operation.schema.json)为准，只有命名操作/参数，不接受raw argv、shell或任意输出覆盖：

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

## 0.2消费者增量与复用证据

固定上游提交 `fae3845bdddc21e311f87540ff718782fb1f7ea7`：49份验收证据的字节与哈希已核，复用其50项Python检查、原生/独立重开、合成UI与Player结果。0.2增量当时运行32项GREA适配检查，以实际wheel解析器核对25个命名参数；真实batch.plan、references partial、debug.inspect [blocked、显式Unity制品选项和旧0.1固定调用通过，独立源码stdio保留partial/blocked。见0.2接入回执](../../validation/development/beaver02-integration-20261026.json)。

[这是0.2历史验收范围，不覆盖后续0.3证据；Go的旧资产交接](../../proposals/beaver-execution-handoff.md)和原消费者继续保留。

## 固定0.3候选07和08的有限适配

GREA请求仍是schema_version1的命名参数封装。工程spec与执行数据由beaver维护，不复制其解析/改名/资源或Go执行实现：

| 路由（只允许固定07、08及元数据等价09） | 外部合同与边界 |
| --- | --- |
| workspace.plan/apply/inspect/rebind | spec schemaVersion1；工程profile为beaver-project/1，apply需beaver-project-setup/1计划及expected-plan；rebind需expected-profile，可显式spec及accept-authority-change |
| production.plan/apply/recover | spec与计划schemaVersion3、beaver-production/3；实际写区/独立输入/旧新哈希/包版本/恢复由beaver检查，apply还需expected-plan、editor-path和timeout |
| config3.validate/generate/compare | 外部配置schemaVersion2；validate可带tables/project，compare使用before-schema/after-schema及可选before-input/after-input；C#＋Go生成物仍需项目实际读取验收 |
| csharp.inspect/rename/rename-sequence/module | 显式spec/project及可选toolchain；rename-sequence/1只生成独立语义候选；module默认grea-unity-project/1.0.0的Bootstrap/Domain/Gameplay/Presentation/Services五层，不自动导入工程 |
| resource.image-inspect/image-produce/validate-step | 封闭policy/spec，image-produce必须expected-source；validate-step不执行原生资源操作 |
| server.generate/module-generate/module-plan/protocol-diff/migration-plan/compose-plan/toolchain | 仅候选/计划/有限检查；generate可能调用显式固定protoc，module生成可使用gofmt，Compose计划不启动服务；依赖缺口由provider原样返回 |

组合ID按固定能力声明逐项映射，例如workspace.inspect只能使用 [workspace.plan/apply/inspect/rebind`，不能把任意斜线字符串展开成授权。公开结果Schema](../../schemas/beaver-result.schema.json)限定beaver-result/1外壳、producer、状态/诊断/制品和验证字段；对两个固定0.3实现启用，不改变旧消费者；data仍属provider合同，GREA不重新判定游戏业务。

`actualChanges`逐项可为非空路径字符串（原生batch/production的已变路径）或对象摘要（操作/恢复/失败见证）；GREA原样保留，不强转对象，数字/null/数组和空字符串仍拒绝。执行后才发生的Schema、身份或退出码校验失败会保留 [executed=true`、原provider结果和事务，顶层native记unverified并提示检查回执；不能据外层needs_action/error推断零写入或自动重放apply。真实采用暴露的此项消费缺陷及原stdout离线重验见修复回执](../../validation/development/beaver-result-schema-fix-20261026.json)，原外层失败与原生成功记录均未追改。

未接入项：server.inspect虽有CLI但候选未声明其能力；server.protocol-tools/check/build及migration-state/migration-apply/runtime-inspect不在此次有限适配范围，禁止以raw argv兜底。Creator执行/构建仍不支持。完整清单见registry中的unsupported_v03。

07阶段41项适配检查及49操作与wheel真实parser一致性检查通过；私有工程workspace四入口、production只读规划、config3校验/生成及坏配置failed、默认五层模块、Go协议比较/模块候选、旧0.1/0.2与独立stdio均已实调。30份上游证据哈希及67个安装文件字节已核，复用115项测试＋11项收口检查、06原生事务/恢复、07固定App调用及私有Go六服证据。

最终45项适配检查通过（含08增量和大计划边界）；68文件私有安装与49参数parser核验、旧07 profile拒绝→按旧SHA显式rebind→新profile核验、中文路径内production只读计划、config3有效/无效数据及stdio的ok/blocked/failed通过。旧0.1/0.2/07固定lock实调正常且哈希不变。08新增最小Editor继承环境和UTF8 job路径的ASCII base64内部传输，复用其118测试日志与8源/342 [Unity引用离线编译回执；GREA未启动Editor，因此中文路径CLI通过不能证明原生编码修复通过。上游总验证索引的07历史层、08新增静态证据和09等价包分别记录，见0.3接入回执](../../validation/development/beaver03-integration-20261026.json)。

## 正式08采用回执与剩余边界

已只读核验正式项目主开发的08回执：rebind verified，production计划SHA256 `62dc58b4ea95cd046740928043c9b4e27777a423d7a753ea2bc15154786da3fc` 与journal/native-result一致，producer为e619实现；journal complete、native verified/error为空、unplannedPaths为0。08/09的68个运行文件也逐字节匹配新本地提交 `ad876dad06e2097424a7b855f4bc7fb13fff6a13`。

这是既有反馈任务中两份C# after-image的原生收敛：before/after内容哈希相同，1个Editor完成编译/保存/同Editor重载；当前两份代码仍匹配原生after-image。不能写成08首次产生新代码、独立Editor重开或正式资源/Prefab整组验收。项目原4项PlayMode结果已读回passed4/failed0，复用既有结果，本轮未重跑。

项目App04默认渲染的Metal启动问题独立保留；最新项目回执同时记录了 `-force-gfx-direct` [下正常进出/重开，不再笼统写成App始终等待。正向购买反馈L3仍not_run，这些项目出口不归类为工具native失败，也不表示完整游戏已验。原始代码/日志/回执留项目内，GREA仅保存定位、哈希和限定摘要，详见采用记录](../../validation/development/beaver03-integration-20261026.json)。

GREA薄适配及这次有限正式原生采用证据可据此交付；0.3整版G结论由beaver主开发汇总。07旧失败和事务仍保留，不能换08重放；旧Go消费者不自动退休。本轮GREA没有启动引擎、Player或Docker，没有改动游戏工程或部署服务。

上游另报告既有自有工程Play通过，而独立中文副本Play的SearchDatabase异常仍为failed；GREA未重新加载或执行这些附加回执，留给上游分别汇总，不推断任意中文路径或Play场景均通过。

## 0.1历史证据及边界

复用beaver本地提交 `b67a164e7618179c1665028a516ea6f2bd6dea00` 的 `docs/VALIDATION-v0.1.0.json`：34份记录hash及最终wheel内21个包文件与已验lock已核对，本轮未重跑引擎。

| 证据层 | 已验证范围 | 不外推 |
| --- | --- | --- |
| 最终wheel＋GREA dev3 | 固定project.inspect、同源macOS构建、Player前后payload核验及退出0，构建前后source hash一致 | 非肥鹅正式采用、非真实鼠标输入、非存档隔离或完整玩法 |
| 早期wheel `c111b92…` | 原生Prefab读回历史证据，C#来源一致 | 不声称最终wheel重跑了该环节 |
| GREA dev4新增适配 | 命名参数/能力/状态边界、最终wheel真实payload.verify及partial、独立源码stdio MCP调用 | 不宣称新增Unity/Player验收或当前会话全局插件已刷新 |
| 原monkey候选→beaver计划 | 既有冻结自有候选已被真实消费为采用预览 | 0动作不是采用/迁移成功，未把该候选与另一自有工程的Player混成同一全链 |

[Creator执行/构建、其他宿主原生交付、复杂游戏业务/视觉/物理输入仍按真实未验项保留。旧工具接收情况见交接材料](../../proposals/beaver-execution-handoff.md)[，唯一进度见路线](../../proposals/lifecycle-roadmap.md)。
