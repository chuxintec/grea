# monkey 批量恢复与开发交接

当前通用转换计划有限适配 **monkey 0.4.0 / 0.4.1 / 0.6.0**；正式目标 **0.7.0** 的精确模块候选已接入显式静态/既有Editor记录复核及代码依赖审计，实际分发身份见 `modules.lock.json`。不据版本号放开通用转换计划，旧版本继续按原 lock 使用。既有来源工具通过 `monkey tool <id>` 委托：Laya 契约、ELF 常量、XAPK/wxapkg、配置表和 Shader 探针。GREA 不复制转换器、不放开任意 CLI 参数；实际 launcher、包树、完整 capabilities 摘要与所选操作均须匹配。显式 ensure 可安装缺失工具，已有安装不自动升级。候选完整性、原生回读与游戏业务分层验收；新工程布局以实际产物 `projectLayout` 为准。

<!-- grea:tool monkey_pipeline -->
<!-- grea:tool monkey_bridge -->
<!-- grea:path src/grea/integrations/monkey/pipeline.py -->

monkey 与 beaver 是 GREA 完整执行链的必选 provider，按阶段使用；开发侧固定绑定与过渡见[beaver接入](beaver工程操作合同.md)。

## 统一工具链

| 层 | 入口 | 职责 |
| --- | --- | --- |
| 原版取证 | grea-recover（只读取证）、inspect_target | 冻结版本和已取得的完整来源集合；缺包单列 |
| 批量转换 | monkey_pipeline | 固定外部 monkey，生成可审阅计划，执行明确的批量命令 |
| 文件核验 | monkey_pipeline audit | 回读 package manifest 或 Unity recovery-manifest，核目标文件 SHA、字节、入口与工程标记 |
| 原生交接 | monkey_bridge --workflow handoff | 核逻辑源去向与真实原生回执；不能以素材/lookup/文件数量放行 |
| 游戏接续 | beaver 工程工具＋游戏 Agent | beaver 负责工程采用/操作与验证工具，游戏 Agent 成组补业务、视觉、存档与目标平台 |

旧 Cocos 解析、AssetRipper、ILSpy 等 ID 保留，用于取证、针对性诊断或既有固定合同，不在批量恢复主路中重复运行另一套转换器。Unity 来源保留原程序集与类型身份；后续结构迁移须另按影响核验。

## 自动发现、安装、绑定与检查

```sh
bin/grea legacy monkey_pipeline discover
bin/grea legacy monkey_pipeline check --output /path/new-check
bin/grea legacy monkey_pipeline ensure --install-if-missing --output /path/new-readiness
bin/grea legacy monkey_pipeline plan --request /path/request.json --output /path/new-plan
bin/grea legacy monkey_pipeline run --plan /path/new-plan/plan.json --output /path/new-run
bin/grea legacy monkey_pipeline audit --workspace /path/new-run/provider-output --output /path/new-audit
```

同一 ID 由 MCP `run_tool` 调用，arguments 是以上子命令与参数。安装的外层时限建议 900 秒；批量执行时留出来源/产物核验时间。恢复子技能已包含完整调用步骤。

`discover` 只读持久绑定、常规用户安装路径和 PATH，不执行程序或联网；相同实际 launcher 去重，多份不同安装报 ambiguous。显式 `GREA_PROVIDERS` 中的 monkey 配置优先于默认发现。`check` 探测并保存新收据，不安装、不修改绑定；`ensure` 核对实际 Python 导入位置、版本、CLI capabilities 和产品文件后原子写入用户绑定。首次成功绑定后，新任务无需手填安装路径或设置环境变量。

完全缺失时，只有显式 `ensure --install-if-missing` 才获取官方 `chuxintec/monkey` 的 `/releases/latest`；匿名 API 限流时回退官方 Release 页面。拒绝预发行、其他仓库附件、身份不符、重复/缺失校验值和校验失败。只安装下载并核验的 wheel，依赖要求精确版本并使用 PyPI binary wheel；不执行下载的安装脚本、不修改系统 Python/其他工具。自动安装当前支持 POSIX；其他平台保持显式 provider 配置。

默认绑定和 GREA 管理的缺失安装位于 `~/.local/share/grea/providers/monkey/`；测试或受控部署可设置 `GREA_PROVIDER_STATE_DIR`。新安装用独立 venv；从插件自带 Python 安装时另保留独立 Python 副本，不让 provider 依赖会被替换的插件缓存。文件夹已存在但安装不完整、绑定失效、发现歧义均保留并报错，不自动重装。已有外部 monkey 安装只绑定，不移动文件或替换日常入口。

安装最新版不等于适配器支持所有新版本：当前通用转换计划接受 0.4.0 / 0.4.1 / 0.6.0；0.7正式身份及开发候选只接受本文列出的精确操作。若 GitHub 最新版超出范围，安装结果保留、ready=false，不降级或冒称可转换。已固定计划继续使用旧身份，执行前后检查变化。

lock v2 固定实际安装包文件集、launcher、解释器文件、command/probe 与 capabilities 摘要；pyc 缓存不纳入产品身份，非全部第三方依赖认证。计划 `--config` 可显式固定旧 lock；省略时读取当前已验证绑定。历史 bridge 保留 v1/v2 显式 lock 接口。自定义 provider 仍可按[安装与平台](monkey与beaver调用.md)配置，再用 `pin --package-root <安装包目录> --output <新目录>` 固定；多参数自定义 launcher 不自动推断包位置。

## 请求合同与批量阶段

请求使用生成的 Schema（GREA 安装根目录资源 `schemas/monkey-pipeline.schema.json`；实际参数先用 `describe-tool`/工具 `--help` 核对），源定义在 `src/grea/monkey_contracts.py`。JSON 路径显式指向本机输入；`input_roots` 是互不重叠的文件或目录，包含选项及 input-set/Unity pool 引用的所有来源。配置文件也要在冻结范围内。默认静态预算最多 20 万文件、32 GiB，每段执行 1–1800 秒；这是适配器上限，monkey 自身更严格的预算继续有效。

```json
{
  "schema_version": 1,
  "operation": "convert",
  "options": {
    "source-family": "cocos",
    "input-set": "/data/frozen/inputs.json",
    "target": "unity6"
  },
  "input_roots": ["/data/frozen"],
  "timeout_seconds": 1200
}
```

Cocos 全集通过 `convert --input-set`，或显式 `--source` 目录/包，target 可 unity6、cocos38、both。`source-family` 必须明确；generic image gallery 不自动当完整初版。

Unity 全集使用 `convert`，options 必须含 `source-family: unity`、`target: unity6`、`unity-export-scope: all`、`source`、`unity-dependency-manifest`、`provider-python`、`asset-ripper`。可传真实 CLI 的纹理缓存、预处理/导出/inspection 复用、代码/Schema 依据、0.4.0 解析预算；只允许列出的参数，不接受任意 shell 或透传参数。输入池所有容器都要冻结。

较大的 Unity 恢复可依次保存独立计划：`prepare-unity-bulk` → `export-unity-bulk` → `convert`（复用前两段已冻结结果）。export 要求具体 `deadline-utc`、`window-end-utc` 与 `budget-seconds`；工具仍遵守已有资源窗口。新适配器不接受 resume 原地写入，不因某一步失败重跑已核验的全部来源。layout-preview/layout-migration 生成独立布局/身份对照，不应用到游戏工程。

## 结果与限制

`provider-output/` 保留上游原始结果。audit 支持新版分组 `Analysis/`、`Docs/START-HERE.md`、包级 `manifest.json` 和 Unity `recovery-manifest.json`，不再假设旧平铺索引。文件变更、路径穿越、符号链接及未列入清单的工程文件会拒绝；真实 Scene/Prefab 数量仅记录，不据此认定覆盖率。

结果保持 `needs_action`，`native_validation` / `business_validation` 独立为 `not_run`。后续使用真实引擎回执和显式 handoff 合同审计来源去向。Sprite 身份需原生类型、GUID+local fileID、Importer/border/pivot/geometry 和 Prefab PPtr，不以相同字节/GUID直接覆盖人工绑定。

## 历史入口兼容

以下是旧 package/slice 合同的冻结说明。对新版完整恢复使用上面的 monkey_pipeline；旧版参数、ID、默认行为保留。

此兼容合同对应monkey `0.3.0.dev1`、capabilities schemaVersion1及包级conversion-result schemaVersion1；只能在匹配的固定lock使用。切片resume/native导入与包级工作区是不同合同；默认包级接口保持兼容；显式 `--workflow slice` 接受切片候选与实际 `--resume-native` 验证，不自动启动Editor。

先按[安装说明](monkey与beaver调用.md)的GREA_PROVIDERS机制配置规范ID `monkey`，command为显式本地CLI argv，probe为同一CLI加`capabilities --json`。新provider默认缺失；路径由用户配置，不使用维护者源码绝对路径。

独立lock JSON需要schema_version1、version、capabilities_sha256（canonical JSON摘要）和identity_files数组，每项path/sha256绑定实际程序/源码或锁定制品。先实际读取capabilities再固定摘要；CLI入口hash不能替代其加载模块身份。GREA在执行前后核验锁定文件；能力变化拒绝，不猜新参数。配置仅记录程序身份，不含凭据或游戏内容。

```sh
bin/grea legacy monkey_bridge --config /path/monkey-lock.json --source /path/input --target unity6 --output /path/new-run
bin/grea legacy monkey_bridge --config /path/monkey-lock.json --workspace /path/prior-package-output --output /path/new-normalization
```

目标仅unity6/cocos38/both，实际capabilities包含精确目标profile；历史适配profile为Unity6000.6.2f1 uGUI、Creator3.8.8，须以固定能力重新核对，不能自动替换用户已有Editor版本。`--source`调用真实`convert --package`，输入总计≤512MiB/10000文件，前后身份一致；`--workspace`只读既有真实包级结果。新输出不覆盖/包含来源。timeout1..600秒，进程日志总计1MiB，失败保留receipt。provider运行不是包内脚本执行授权；不探原厂服务、下载缺包或安装引擎。

输出result.json保留needs_action/partial/blocked/failed，候选目录逐文件核SHA/字节（≤20000文件/512MiB），引用资源、代码、目标映射和原始agent-work索引。returncode1是monkey声明的未完成结果，GREA不会升级成完整工程。不同schema、缺索引、版本/字节变化或package模式的native报告拒绝；package模式的native_validation始终not_run。文件记账完整不等于资源/玩法恢复率；单个主分包也不等于全游戏。

ai-modules.json只创建交接数据，不启动Agent。默认把未分组任务留在一个待分析池，不将每条RF区域或诊断发成一轮对话。可通过`--modules JSON`传schema_version1和modules数组，模块包含id/objective/project/task_ids/writable_paths/invariants/verification/evidence；evidence每项显式path/sha256。任务ID须存在且单归属，可写范围不能超过monkey声明，模块不能争写同一文件或重叠目录；共享文件另设唯一写者。该模块合同仍是调用者声明，由真实用户范围约束。

```sh
bin/grea legacy monkey_bridge --config /path/lock.json --workflow slice --source /path/owned/project.json --source-profile cocos-2.4.15-project --all-assets --target unity6 --output /path/fresh-conversion
bin/grea legacy monkey_bridge --config /path/lock.json --workflow slice --workspace /path/fresh-conversion/conversion --resume-native --output /path/fresh-verification
```

切片必须选 `--all-assets` 或重复 `--asset-index N`；目录输入由适配器指向project.json/config.json以避免混入包级自动识别。slice只接受一个目标，当前支持cocos-2.4.15-project/bundle。创建候选不会运行原始脚本或Editor。`--resume-native`仅适用于显式隔离工作区，调用provider的真实resume；只有身份一致的报告声明native/editor pass且Editor版本、Missing Script、编辑保存往返、逐个原生文件和其余候选文件仍匹配，才记录provider_verified_editor_readback。保留partial与业务/视觉待验，不升级为完整游戏。该回读来自本地provider，不能当作独立认证或Player实玩证据。

切片的GREA接续边界`grea-native-continuation`允许`Assets/Game/`，标明它是GREA声明的开发边界，**不是转换器自动翻译出的业务任务**。来源合同、原生引用和新增实现须分别核验。包级仍保留provider的细粒度任务，不改旧ID。

自有接续示例的可执行资产在 GREA 安装根目录 `tools/unity/lifecycle-sample/`，其方法是：固定provider原始候选遇到无效依赖与Editor导入边界时，保留原件，在新Editor脚手架中显式修复、记录差异后接续。**修复后的Editor通过属于GREA adopted工程验收，不伪造原候选的provider resume pass**。这不是任意Cocos游戏自动恢复能力或真实项目完整度百分比。


## 显式原生交接审计

```sh
bin/grea legacy monkey_bridge --config /path/lock.json --workflow handoff --workspace /path/independent-export --handoff-contract /path/contract.json --output /path/new-review
```

此审计不执行批量导出，`all_scope_export=not_executed_by_handoff_audit`。合同 v1 包含 schema_version、provider_version、target_engine、project_path、source_inventory、assets、entry、native_check；逻辑资产每项声明 source_id/category/source_files/disposition/outputs/reason，outputs 与 entry/native_check 都用相对 path/sha256。source_inventory 为完整 inspect_target 目录结果；native_check 位于工程外，包含 schema_version、target_engine、import_status、compile_status、artifacts，绑定当前全部交付工程文件（排除根级引擎缓存/构建目录）。原生回执仍是提交者声明，GREA 核文件，不冒充重新运行 Editor。

## 开发版来源查询

以下是独立开发CLI的可选查询合同；当前GREA批量适配未转发这些命令。只有明确固定的入口实际声明相应能力时才用，不覆盖日常绑定，也不按此页推断开发版已安装或发布。

在已固定的monkey开发环境中，按其真实capabilities及上述文档选择：

- `query-methods --source FILE --expected-sha SHA --module MODULE --function NUMBER --out NEW`：完整所选来源hash及映射扫描，不产生方法体。
- `query-tables --manifest FILE --expected-manifest-sha SHA --contains NAME --out NEW`：表变体清单查询；实际提取另需源/所选成员hash，清单通过不等于所有载荷已核。
- `inspect-aliases --source FILE --expected-sha SHA --alias EXACT_URL --out NEW`：精确URL身份；不含content-source时不宣称内容已验。

这些是外部monkey开发CLI参数，不是GREA新增命令。当前 `monkey_pipeline` 保留固定0.4/0.6批量合同并按下节增加P0有界分类；尚未接入三查询的GREA专用薄转发。需要查询时显式使用固定开发入口，或在任务中标此适配待接入；不退回执行交接包脚本。成员SHA只标识成员字节，不冒充多GB外层包已全部核验。缺少可选查询不改变既有批量恢复合同。

## 本地 P0 Shader 有界分类

使用条件：已有冻结 Unity 候选，只需分类 Shader 证据；不重导、不使用全量 plan/run 的工程快照扫描。`monkey_pipeline classify-shaders` 是现有工具 ID 下的新增薄入口，CLI/MCP 共用执行层。源码支持本地候选不代表当前已装插件已更新。

固定候选为提交 `57613e78f66a1c4685e748827983827c77922d36` 的 wheel SHA `5ea38374c018ad95bd08bb734b0a471b3f51b7720e3b11934278b19f35e58f7c`；版本仍显示0.6.0，不能只据版本接受。先核安装包及显式命令，复用 `monkey_pipeline pin` 创建独立锁，不覆盖全局绑定。转发同时核锁中完整运行文件、实际命令、固定包树与能力指纹；`unitySourceProfile.shaderHandoff` 必须是 `monkey-shader-handoff/1`。原始 capabilities stdout SHA `8192ca12…` 与 GREA 对解析对象规范编码的 SHA `9a8d4849…` 口径不同，不能直接互比；缺候选时报告缺口，不自动替换正式0.6锁。

```text
monkey_pipeline classify-shaders --config /absolute/p0-lock.json
  --project /absolute/FrozenUnity --manifest /absolute/recovery-manifest.json
  --expected-manifest <SHA256> --output /absolute/new-output
  [--source-mapping /absolute/full-resource-handoff.json
   --expected-source-mapping <SHA256>] [--timeout-seconds 30]
```

这是调用 `run_tool` 时所选 `monkey_pipeline` 的参数，不是独立 shell 命令；CLI 通过既有工具运行入口传入同一参数。source-mapping 与 expected-source-mapping 必须成对；out 由薄入口指定独立 provider-output，不能另传任意 argv。实际外部命令为 `classify-unity-shaders --project --manifest --expected-manifest [--source-mapping --expected-source-mapping] --out`。

结果保留 provider 原回执、report.json 和 handoff.json；handoff 顶层仅 schema/items。逐项 source-text→source-review、platform-compiled/recovered-binary→evidence-only、unknown/unsupported→blocked，全部 nativeCompilation=not_run。target 是序列化声明或 null，source 关联的 unmapped/ambiguous 不猜补。GREA按生产者冻结 Schema 校验、复核 manifest/mapping 和分类文件字节，不重复实现内容分类或把目标声明当 Editor 身份。返回 classified 只代表分类完成，不代表候选恢复完成或运行资产可采用。

分类后将原始 handoff 与当前工程的原生快照交给[beaver 构建筛选](beaver工程操作合同.md#固定本地-p0-候选)，由其核当前 hash、GUID/localID、目标平台/管线和依赖。未引用不能证明无动态使用；blocked 计划不执行隔离，不删被引用资产、不自动替换 Shader。完整来源对象关联恢复属于单独范围，不靠名称填补。

## v0.7目标与接入状态

monkey v0.7按先静态、后动态推进：静态阶段保全层级、组件/字段、图片/文字/材质及引用，核真实渲染、保存独立重开和再生；业务行为允许禁用/未运行/部分执行，并单列动态结果。源组件分母、阶段出口与三态身份见[独立恢复对照](../../grea-recover/references/全量初版工程与协作.md#prefab完整恢复的独立对照)及[候选交接](../../grea-recover/references/全量初版工程与协作.md#生成态保存态与项目采用身份)。样本数与双目标范围由批准计划维护，不变成所有游戏的固定门槛。

### 固定 dev1 的保存态只读复核

已有限接入 `0.7.0.dev1`，固定提交 `a458790a68d57108b4cfe038d8aa565d5cc1599b`、wheel SHA `06bc81ea71c4e6a0e9b6ccc9a16b43b34f1fc0ecdc7c3d772921b535ff6152f8`。该版本capabilities没有producer字段，不伪造它；以423个包文件的相对路径→SHA映射摘要 `c3673a4f7cf1f724ab6c30b2235bba6a9475426e561d42c069d082b4dd750b7d` 和capabilities规范摘要 `487e5d37974bf9e9556591aae7af5081fa8f76f0c7bbb28599ce3a5dc449c57b`精确绑定。`pin`和实际probe均拒同版本不同内容；锁还绑定程序与包树。包多出文件也属于不同身份，不修改上游来迁就锁，可用已核wheel的独立副本。

通过显式`GREA_PROVIDERS`选择固定程序，沿用`monkey_pipeline pin --package-root PACKAGE --output NEW`生成v2锁；不改默认binding或正式模块锁。已有源码/自定义launcher不走自动ensure，不把全局0.6发现信息当成本次dev1生成器。实际调用：

```sh
bin/grea legacy monkey_pipeline audit --config /absolute/dev1-lock/monkey-lock.json \
  --workspace /absolute/SavedUnityCandidate --level editor \
  --expected-manifest <generated-manifest-SHA256> \
  --expected-readback <saved-editor-readback-SHA256> --output /absolute/new-audit
```

MCP使用`run_tool`选择同一`monkey_pipeline`及上列arguments；外层预算至少360秒。适配器调用固定provider已有`verify --candidate --level editor --out`，只读核现有原生回执与当前字节，**不启动Editor**，不另写原生解析/采用器。`--level static`只核生成态，需要expected-manifest且禁止expected-readback；省略level保持旧generated审计语义，dev1必须显式指定static/editor。此增量不允许dev1的plan/run转换，不修改旧版本接口。

editor级读取固定`Analysis/Readback/editor-readback.json`的nativeFiles实际哈希和原生字段/引用；生成manifest的.meta采用保存回执，其他生成文件仍核原hash，ProjectVersion只按固定provider的6000.6.2f1标准化规则处理。GREA执行前后核manifest/readback/锁及程序包身份，原生成清单不写回。provider输出`verification.json`和执行回执保留；`staticValidation/nativeStaticValidation/runtimeCheck`、`editorValidation`、诊断、视觉与业务各自报告，exit1的动态partial不一律等同静态失败。GREA顶层仍needs_action/handoff_ready=false：这是同provider对既有记录的再核，不是新原生运行、独立认证或项目采用通过。

调用失败核`failure.json`及executed，保留已有输出；身份漂移、错预期hash、不兼容候选和未适配操作拒绝，不用raw argv绕过。新`freeze-native-selection`与`adoptionDependencies`目前为monkey/beaver协调中的下一固定合同，dev1未实现，不提前注册或用项目helper冒充公开能力。

### 固定 dev2 的保存态选择冻结

`0.7.0.dev2`固定提交`c279a6ac9ec3766a4550b5cfdaa5df6cced953c3`、wheel SHA `40cd12a06754b99cd8989d6b61b41c91725223a8a9ed5c5bd380f20c6499938e`，425文件包摘要`05f429c84c46bde954f01af90be96fe448789e881de7defbcc51444aa25c6517`、capabilities规范摘要`8660a3d7d1f576392191fb7d94d66a55bb1d531048658f5d8fca12c85c01973b`。无producer字段，不虚构；沿显式pin固定精确内容。

使用`monkey_pipeline freeze-native-selection --config LOCK --candidate SAVED_PROJECT --prefab Assets/Path/Item.prefab --expected-manifest SHA --expected-readback SHA --output NEW`，prefab可重复，最多128条唯一规范路径。GREA转发已验同名provider命令，复核父身份与输出文件hash；输出项目在NEW/provider-output。实际闭包、包GUID、字体依据和依赖声明由monkey实现，不在GREA重复解析。旧dev1只读audit接口保持；dev2只开放本选择冻结，常规plan/run转换仍未适配。

输出adoptionDependencies是producer-declared，并非完整C#分析；未分析脚本、DynamicOS/新增文字覆盖未知和全部诊断保留。将原始manifest与选集交固定beaver fix10，路径适配需保留依赖映射，不手写producer声明。此出口已固定交付，覆盖前文“拟议出口”状态；实时代理与扩字修复仍属于后续版本。复用保存回执不等于新Editor、采用或业务通过。

### 固定dev3选择与运行时/字体交接

`0.7.0.dev3`固定`4ad7498a35e762f6ef5b6f15a334e973d7794845`，wheel SHA `d95cabf4ef9ec4cf610fcacf17b4db1130ae337a8598702eebef32fb2bd9fe34`；434包文件摘要`f77c5bcaca208a8a9e5a6481db384275fd69688e640de1a921863289263fe11c`、规范capabilities摘要`f6e67a8a6f4921a8ef265f2ae3cb250c7c01a5a1f0d3e888bdd1c5b719f6ab13`。同dev2的显式pin/freeze入口已开放此精确身份，普通convert与新增生成操作不因版本白名单自动放开。

选择冻结递归跟随literal Shader include，shaderDependencies与C#边分列；未知/macro/不安全include拒绝，Unity内建include标来源，编译仍须原生验。dev3修复dev2遗漏，保留旧219原件及失败边界。运行时/字体最终候选与原保存态选集分别固定manifest，不能混用221与247文件身份。采用保留Monkey.NativeUiContracts接口，不另造全局marker别名；原Slider.fillRect=null保留，项目typed绑定实际验。

已核固定provider的四个CLI合同：upgrade-native-runtime要求candidate/expected-manifest；complete-native-font要求request/expected-request；stage-native-font要求candidate/expected-manifest及completion/expected-completion；finish-native-font要求project/expected-stage-manifest及readback/expected-readback，均写新out。它们现已由下述native-step有限调度，不提供raw argv；已有固定最终候选可直接进入beaver采用，无需重复运行。中性native raycast/合成callback、435字形/17文本和保存重开各是有限证据，不证明物理输入、产品字体覆盖或Player业务通过。

### dev3四项生成操作的冻结请求

公共入口为`monkey_pipeline native-step --config LOCK --request REQUEST --output NEW`，只接受固定dev3。REQUEST字段严格为schema_version=1、operation、options、input_roots、timeout_seconds；operation仅upgrade-native-runtime、complete-native-font、stage-native-font、finish-native-font，options恰为上列各命令的命名参数（去掉双横线），不得含out/executeMethod或任意argv。timeout为1..1800整数；input_roots为1..64个存在、互不包含的绝对输入文件/目录。MCP使用同tool_id/arguments，外层预算需覆盖内部timeout和审计。

所有路径选项必须在冻结根内，输入前后按有界完整快照比较；manifest、request、completion/font-completion.json、stage manifest和readback的expected SHA均在执行前核对。complete-native-font的request内全部*_path及watch_files路径也须处于冻结范围；相关绑定/回执引用的资料目录应完整声明，缺少或超预算拒绝，不静默跳过Library等子树。平台CoreText字体/OS/生成器身份由固定provider精确核，GREA不声称冻结整个主机。

仅转调用固定provider，输出限定NEW/provider-output，保存原stdout/exit及failure.executed；输入/锁/包变化不签收。输出有界快照及各manifest登记文件逐项核path/SHA/bytes，不能越出输出；没有登记清单的输出仅提供库存字节证据，provider语义和原生结果分别保留。阶段生成的launchArguments不自动执行，stage不等于字体导入，finish须由provider核真实passing readback；顶层仍needs_action/handoff_ready=false，Player与物理输入另验。

本轮验证覆盖31项受影响检查及四个固定CLI非法输入拒绝，未重跑字体生成或Editor。既有247最终候选继续独立采用；新增正向生成在自然需求中按同合同验证，不借本次调度测试宣称生成/产品通过。

### 固定dev4的依赖补证

`0.7.0.dev4`固定提交`19d51d4dbe7971bb14c5724963c42dfdbd9ddaca`、wheel SHA `590241cef89fa460090088318002c355187235eee2cbe21a471d8bbc34ac7a26`，435文件摘要`5689b6dc039c4f9aafbda9dbdeaf634c25f1013c9ef09cc91fa53377a113baf1`、规范capabilities摘要`b8c1e66b8215c3133c8f0ba4e2bf5d1ae9a9d2632979f41c3c80106ee00ae252`。支持同形freeze/native-step有限入口；新operation `audit-native-code-dependencies`只接受dev4，options恰为candidate、expected-manifest、producer-candidate、expected-producer-manifest。按native-step v1提供输入根和预算，两个项目manifest预核SHA，输出独立目录，不改旧候选/诊断。

补证报告schema=monkey-native-code-dependency-supplement/1；GREA核目标与producer父清单身份、originalDiagnostics未变、逐script/requires/package SHA及固定包中的producerImplementation SHA。模板profile/可再生carrier证明由monkey实现，不另建C#分析器。uncovered为0只指这份目标库存中的精确producer证明范围，不代表任意C#分析、原生编译、业务或真实输入完成；旧warning不删除。已有相同目标、provider与报告时复用冻结补证，不强制重跑大producer树或字体/Editor。

### 固定dev9的SDK生产者声明

`0.7.0.dev9`固定`735a87ebbc194590c39a6ecd3984b74c4c23c029`，436包文件规范摘要`d2534c9bd4240b231ba992e066b2980a92b4aa9b590125dd243fc9cc5970e479`、capabilities规范摘要`0dd7f9b9af2462ced9224ee4642e9ac3f23da80f3e8277a45f29b8026744bea0`。仅接受上述native-step的audit-native-code-dependencies，选项与dev4相同；不放开freeze、转换或字体生成。旧链保持。

原始补证报告增加sdkProducerDeclarations，声明DLL/meta/GUID、Editor/Player角色、构建声明身份、许可证和literal m_Script引用。GREA保留完整报告及SHA，原stdout只提供报告路径，不复制DLL分析器。每DLL的nativeMonoScriptTable.status=not_run且scripts=[]表示未测，不能解释成没有脚本、兼容历史localID或迁移通过；实际PE/public types、Player引用与原生GetClass/assembly/localID由beaver及消费者验收。SDK声明不覆盖冲突守卫，迁移完成与实例输入另验。

### Unity来源Prefab的固定保存态冻结

`0.8.0.dev2`固定提交`c4b984f3ce10e492554d318ace8dba9a85f2dc37`，441文件wheel包摘要`b12528b0ec63ecf7a1498ba94ef5530bf1057a7653931ac5938554667c7969ed`、规范能力摘要`64082896453ab0d3a272864b932a57146545f9ec755fb0c751a8a99e23e7b9f4`。只开放`monkey_pipeline freeze-unity-prefabs --config LOCK --native-output NATIVE --expected-execution SHA --output NEW`，MCP通过同一tool_id/arguments调用，外层预算至少覆盖300秒provider预算及字节核验。LOCK须为对应providers配置生成的v2锁；独立wheel运行时与源码额外文件分别记录，不按版本号放行其他入口。

`0.8.0.dev4`固定`2ddb7a912aa0186168c19947fff340988a446d17`，446文件wheel包摘要`25ded3d292e999a55f3766c9d4c995e9889cff16ef8354b6df0b9489e01c22a9`、规范能力摘要`aadfdd818e55d50628b79558fc3e86c0715a018b72db8513a68a6df943ee48c6`，同样只开放上述保存态冻结，不开放dev3或其他命令。多根交接按完整sourceId核对源→目标及冷重开证据，禁止按列表位置配对；共享依赖在同一候选闭包去重，不能因拆根复制而丢引用或重复计根。历史排序错配失败保留；新候选只覆盖其固定源根及依赖，缺图等其他候选不混入，也不由无诊断推断渲染/Shader兼容通过。

`0.8.0.dev5`固定`a55d88a8045fe081fd732e29cdc05fca9988ce2c`，450文件wheel包摘要`81e0f6f7be15f472b4ff5c0306eb3c264615f952f7b9e5cc48ab72542d6cff8b`、规范能力摘要`0eb6a382f9957fe6a183fce4e63fb794d86689447214c47505a8c1f2c2ca2ead`，仍仅同一保存态冻结入口。原生创建的嵌入Sprite/Texture须保sourceTuple、像素与几何、格式/可读性归一化和真实GUID/localID的首读/冷重开证据；新增目标身份不能冒称原版builtin身份。此能力存在于固定provider，不因此公开新assets/recover/verify命令。历史生成阶段pending-rebind诊断与后来实际MonoScript观察分别记录，不能抹掉旧warning，也不能把已验证的绑定仍笼统写未测；缺失原图的像素和禁用自定义行为另列。已有九根加一根的headless记录只在精确源身份去重后计数，不等于十根完整依赖、显示或业务闭环。

`0.8.0.dev6`固定`3fb450c51b8e3a04c1bd8c71aaea0cee71befea1`，452文件wheel包摘要`302f4ada206cb3462a6d95d7a5af37deee2742cc7b99b595d0058a62fc8a3dad`、规范能力摘要`a9ff89dcb4796318cad3dfd44627528355ef3c5410a22fa603a7ad6b3356cc82`，同样仅保存态冻结。原图集恢复采用新不可变候选：逐Sprite保原sourceTuple、GUID/localID/meta、几何/轮廓及原像素证明，声明新Texture引用和归一化；首读/冷重开观察须一致。旧404/缺图失败原样保留，新图集修复不回写旧候选、也不豁免仍不支持的trimmed atlas/字段类型。普通unpacked路径另核回归，不能把一种profile通过推定为全部atlas类型支持。

完整模块的编译依赖含独立enum时，采用方必须证明其真实目标定义、数值及使用字段兼容；同名MonoBehaviour存在不代表enum已经覆盖。保留完整候选，再按受支持合同声明保留/不导入及原生字段验收，不删enum、脚本或其他依赖缩closure、不直接复制compiler。freeze保持source partial/exit1，不产生intakeStatus=verified；实际采用结果由beaver和消费者另验，headless唯一剩余limit也不能改记可见静态pass。

该操作只转发provider的`freeze-unity-prefabs --native-output --expected-execution --out`。预核原生execution-result SHA、完成保存及独立重开、sourceCodeExecuted=false、source manifest及有界savedFiles/readback；按清单核输入，不扫描Library。只写NEW中的冻结副本，不启动Editor、不运行游戏方法。结束复核锁/包/输入未变、输出清单逐件匹配保存字节、execution/source manifest父身份及源根/诊断未改，保留provider exit1/needs_action/native-partial，不提升为静态显示pass。

当前GREA仅准备了`recover-unity-prefabs`真实请求ABI的内部校验，尚未开放恢复生成、verify-unity-prefabs或其他0.8命令。已有保存态不重跑原生；原生身份稳定不证明画面、可见编辑、Player或业务通过。采用仍须由beaver核namespace、精确baseline、程序集/GUID及Resources键冲突，owner明确保留/映射与真实消费者后再执行，冻结副本不是自动采用授权。


### dev7 固定 effect 保存态选择

`0.8.0.dev7`固定source `2e88bc95fbe9cf82d61ad0a192715f334a242695`，458运行文件包摘要`ef4d3ad75d9395788efe0b857782feb33549c4114fb4f7582ca1c3f63e669c2d`、规范能力摘要`85eca6fb100dfd734fc7ca337fe28b0915c187015620109d938b6ae178ef1853`。沿既有recover/verify/freeze保存态合同，不扩大任意旧pipeline操作。消费者使用已给固定saved selection及manifest，不重生成或重冻已验候选；新正式采用仍经beaver精确plan/写集及独立cold核验。

effect实例64字段/2owners/4components和保存/冷重开引用通过，仅证明声明静态数据。原source mesh `engine-reference-unverified`及deadbeef provider诊断保留，recover/verify/freeze的partial/exit1/needs_action不转为完整成功；不得删失败manifest依赖来闭包。Shader仅核既有native引用，不能声称原compiledShader语义或视觉一致；Player、视觉、业务仍待验。BattleMain UV曲线严格拒绝独立保留，不因effect通过推定其支持，也不重跑已验Login/既有根。

### 显式固定launcher的readiness

已固定的自定义launcher（包括shell包装器）不能将其shebang猜作Python安装解释器。调用方可同时设置`GREA_PROVIDERS`及`GREA_MONKEY_LOCK`，后者指向既有launcher-bound v2精确锁；readiness必须执行原有pinned校验（command/probe、全部package_files及identity_files）、支持版本、真实capabilities摘要和固定候选包门，并核锁在探测前后未变，全部通过才ready。缺匹配配置、身份/包/能力漂移均失败，不回自动发现、不换provider、不自动安装或写全局binding。未提供显式锁时保留原installed-console自动探测及ensure规则。

QA-only provider的readiness通过不扩大工程操作面；如unity.plan须使用实际声明该操作的工程provider固定锁，不能经qa-invoke固定QA锁调用。项目wrapper由其owner显式配置build/QA不同入口，旧锁及事务保持原身份。该路径只证明工具依赖可用，不等于Unity编译、Player或产品验收。


### 正式0.7精确模块

`0.7.0`固定源码`86d47f35744a5af91614c417b00c8eaa2345baad`，wheel SHA `cb7eed60ff00085260657d2362e5fc60ee46a5d258a748c75770d0e337964dd0`；436包文件规范摘要`5295b0f24f763cf1e9ffabe7feb3027a29d53eb51c7fccedf533945671448c64`，capabilities规范摘要`602c0006da911014f850657d731c292bd2ce95b8239e6d9518ab228414463267`。来源为固定dev9稳定线，不含Unity来源0.8增量。正式远端发布状态以模块锁及随包发行记录为准。

GREA的`pin`、`audit --level static/editor`、`native-step`的`audit-native-code-dependencies`核对此身份；后者沿上述四个选项及独立输入根合同。省略audit level、通用plan/run、freeze及字体/运行时生成操作不因此开放。原生选择生成仍由monkey的版本化公开CLI负责，GREA不重写恢复器；生成态中性夹具不得伪造原生回执。输出保留`needs_action`与独立的静态/原生/业务状态，既有游戏锁和历史固定候选不升级。
