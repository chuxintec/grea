<!-- 生成副本，勿直接编辑。权威来源：docs/providers/monkey.md；由 scripts/skill_closure.py 维护。 -->

# monkey 批量恢复与开发交接

当前新工作流适配 **monkey 0.4.0 / 0.4.1**。GREA 2026.10.27 随包发布 monkey **0.4.1**（`modules.lock.json`）：转换功能与 0.4.0 相同，另含从 GREA 移入的 7 个来源侧工具（`monkey tool <id>`：laya_contract_audit、read_elf_values、unpack_xapk、shader_probe、decrypt_v1mmwx_wxapkg、unpack_wxapkg、export_config_tables），GREA 的同名 ID 及 `wxapkg-unpack`/`wxapkg-decrypt`/`unity-export-config` 自动委托。monkey 仓库与版本独立开发，GREA 不复制转换器；显式 ensure 可安装缺失工具，已有安装不自动升级。已安装版本、锁定能力、来源库存、导出候选、原生回读、游戏业务分别记录。monkey 的目录规范以实际产物的 `projectLayout` 为准；GREA 不把新工程强行搬回历史路径。

<!-- grea:tool monkey_pipeline -->
<!-- grea:tool monkey_bridge -->
<!-- grea:path src/grea/integrations/monkey/pipeline.py -->

monkey 与 beaver 是 GREA 完整执行链的必选 provider，按阶段使用；开发侧固定绑定与过渡见[beaver接入](beaver.md)。

## 统一工具链

| 层 | 入口 | 职责 |
| --- | --- | --- |
| 原版取证 | grea-evidence、inspect_target | 冻结版本和已取得的完整来源集合；缺包单列 |
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

安装最新版不等于适配器支持所有新版本：目前批量接口固定验证 0.4.0，若 GitHub 最新版超出范围，安装结果保留、ready=false，不降级或冒称可转换。已固定计划继续使用旧身份，执行前后检查变化。

lock v2 固定实际安装包文件集、launcher、解释器文件、command/probe 与 capabilities 摘要；pyc 缓存不纳入产品身份，非全部第三方依赖认证。计划 `--config` 可显式固定旧 lock；省略时读取当前已验证绑定。历史 bridge 保留 v1/v2 显式 lock 接口。自定义 provider 仍可按安装与平台（GREA 安装目录 `docs/安装与平台.md`）配置，再用 `pin --package-root <安装包目录> --output <新目录>` 固定；多参数自定义 launcher 不自动推断包位置。

## 请求合同与批量阶段

请求使用生成的 Schema（GREA 安装目录 `schemas/monkey-pipeline.schema.json`），源定义在 `src/grea/monkey_contracts.py`。JSON 路径显式指向本机输入；`input_roots` 是互不重叠的文件或目录，包含选项及 input-set/Unity pool 引用的所有来源。配置文件也要在冻结范围内。默认静态预算最多 20 万文件、32 GiB，每段执行 1–1800 秒；这是适配器上限，monkey 自身更严格的预算继续有效。

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

本轮实际验证见工具链验收（GREA 安装目录 `validation/development/monkey-toolchain-20261026.json`）：已安装 0.4.0 的自有双端样本和防漂移测试；Unity 全容器阶段参数已接入，但本轮不重新运行真实游戏的 AssetRipper/Editor。monkey 上游 601 容器、剩余 36 个未解析对象是该特定样本的历史结果，不能当所有游戏的成功率。

## 历史入口兼容

以下是旧 package/slice 合同的冻结说明。对新版完整恢复使用上面的 monkey_pipeline；旧版参数、ID、默认行为保留。

`monkey`是外部provider，不随GREA复制解析器或全局安装。当前适配实测monkey `0.3.0.dev1`、commit `1e21f8aef71ca6a940ee35e1b1f07f0ed9dedb42`，capabilities schemaVersion1及包级conversion-result schemaVersion1。切片resume/native导入与包级工作区是不同合同；默认包级接口保持兼容；显式 `--workflow slice` 接受切片候选与实际 `--resume-native` 验证，不自动启动Editor。

先按安装说明（GREA 安装目录 `docs/安装与平台.md`）的GREA_PROVIDERS机制配置规范ID `monkey`，command为显式本地CLI argv，probe为同一CLI加`capabilities --json`。新provider默认缺失；路径由用户配置，不使用维护者源码绝对路径。

独立lock JSON需要schema_version1、version、capabilities_sha256（canonical JSON摘要）和identity_files数组，每项path/sha256绑定实际程序/源码或锁定制品。先实际读取capabilities再固定摘要；CLI入口hash不能替代其加载模块身份。GREA在执行前后核验锁定文件；能力变化拒绝，不猜新参数。配置仅记录程序身份，不含凭据或游戏内容。

```sh
bin/grea legacy monkey_bridge --config /path/monkey-lock.json --source /path/input --target unity6 --output /path/new-run
bin/grea legacy monkey_bridge --config /path/monkey-lock.json --workspace /path/prior-package-output --output /path/new-normalization
```

目标仅unity6/cocos38/both，实际capabilities包含精确目标profile；本轮真实探测为Unity6000.6.2f1 uGUI、Creator3.8.8，不能自动替换用户已有Editor版本。`--source`调用真实`convert --package`，输入总计≤512MiB/10000文件，前后身份一致；`--workspace`只读既有真实包级结果。新输出不覆盖/包含来源。timeout1..600秒，进程日志总计1MiB，失败保留receipt。provider运行不是包内脚本执行授权；不探原厂服务、下载缺包或安装引擎。

输出result.json保留needs_action/partial/blocked/failed，候选目录逐文件核SHA/字节（≤20000文件/512MiB），引用资源、代码、目标映射和原始agent-work索引。returncode1是monkey声明的未完成结果，GREA不会升级成完整工程。不同schema、缺索引、版本/字节变化或package模式的native报告拒绝；package模式的native_validation始终not_run。文件记账完整不等于资源/玩法恢复率；单个主分包也不等于全游戏。

ai-modules.json只创建交接数据，不启动Agent。默认把未分组任务留在一个待分析池，不将每条RF区域或诊断发成一轮对话。可通过`--modules JSON`传schema_version1和modules数组，模块包含id/objective/project/task_ids/writable_paths/invariants/verification/evidence；evidence每项显式path/sha256。任务ID须存在且单归属，可写范围不能超过monkey声明，模块不能争写同一文件或重叠目录；共享文件另设唯一写者。该模块合同仍是调用者声明，由真实用户范围约束。

包级自有输入候选保留3条来源明细与needs_action。新增切片接口：

```sh
bin/grea legacy monkey_bridge --config /path/lock.json --workflow slice --source /path/owned/project.json --source-profile cocos-2.4.15-project --all-assets --target unity6 --output /path/fresh-conversion
bin/grea legacy monkey_bridge --config /path/lock.json --workflow slice --workspace /path/fresh-conversion/conversion --resume-native --output /path/fresh-verification
```

切片必须选 `--all-assets` 或重复 `--asset-index N`；目录输入由适配器指向project.json/config.json以避免混入包级自动识别。slice只接受一个目标，当前支持cocos-2.4.15-project/bundle。创建候选不会运行原始脚本或Editor。`--resume-native`仅适用于显式隔离工作区，调用provider的真实resume；只有身份一致的报告声明native/editor pass且Editor版本、Missing Script、编辑保存往返、逐个原生文件和其余候选文件仍匹配，才记录provider_verified_editor_readback。保留partial与业务/视觉待验，不升级为完整游戏。该回读来自本地provider，不能当作独立认证或Player实玩证据。

切片的GREA接续边界`grea-native-continuation`允许`Assets/Game/`，标明它是GREA声明的开发边界，**不是转换器自动翻译出的业务任务**。来源合同、原生引用和新增实现须分别核验。包级仍保留provider的细粒度任务，不改旧ID。

自有最小原生示例见生命周期接续验收样例（GREA 安装目录 `tools/unity/lifecycle-sample/README.md`）。固定provider原始候选遇到无效依赖与Editor导入边界时，保留原件，在新Editor脚手架中显式修复、记录差异后接续。**修复后的Editor通过属于GREA adopted工程验收，不伪造原候选的provider resume pass**。这不是任意Cocos游戏自动恢复能力或真实项目完整度百分比。


## 显式原生交接审计

```sh
bin/grea legacy monkey_bridge --config /path/lock.json --workflow handoff --workspace /path/independent-export --handoff-contract /path/contract.json --output /path/new-review
```

此审计不执行批量导出，`all_scope_export=not_executed_by_handoff_audit`。合同 v1 包含 schema_version、provider_version、target_engine、project_path、source_inventory、assets、entry、native_check；逻辑资产每项声明 source_id/category/source_files/disposition/outputs/reason，outputs 与 entry/native_check 都用相对 path/sha256。source_inventory 为完整 inspect_target 目录结果；native_check 位于工程外，包含 schema_version、target_engine、import_status、compile_status、artifacts，绑定当前全部交付工程文件（排除根级引擎缓存/构建目录）。原生回执仍是提交者声明，GREA 核文件，不冒充重新运行 Editor。

自动发现/绑定/缺失安装与插件随包运行时验证见就绪验收（GREA 安装目录 `validation/development/monkey-readiness-20261026.json`）。

## 开发版来源查询

monkey 0.5.0.dev1已交付query-methods、query-tables、inspect-aliases及验收记录，来源是其docs/EVIDENCE-QUERIES.md和docs/validation/2026-10-26-colleague-evidence-intake.md。使用其明确开发检出/固定wheel入口；日常稳定安装仍0.4.0，不覆盖默认绑定，不将开发能力冒充稳定能力。

在已固定的monkey开发环境中，按其真实capabilities及上述文档选择：

- `query-methods --source FILE --expected-sha SHA --module MODULE --function NUMBER --out NEW`：完整所选来源hash及映射扫描，不产生方法体。
- `query-tables --manifest FILE --expected-manifest-sha SHA --contains NAME --out NEW`：表变体清单查询；实际提取另需源/所选成员hash，清单通过不等于所有载荷已核。
- `inspect-aliases --source FILE --expected-sha SHA --alias EXACT_URL --out NEW`：精确URL身份；不含content-source时不宣称内容已验。

这些是外部monkey开发CLI参数，不是GREA新增命令。当前 `monkey_pipeline` 仍只适配稳定0.4批量合同；本轮未接入三查询的GREA专用薄转发。需要查询时显式使用固定开发入口，或在任务中标此适配待接入；不退回执行交接包脚本。成员SHA只标识成员字节，不冒充多GB外层包已全部核验。此可选增量不阻塞既有三工具集成收口。
