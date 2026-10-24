# monkey 转换与原生工程接续

`monkey`是外部provider，不随GREA复制解析器或全局安装。当前适配实测monkey `0.3.0.dev1`、commit `1e21f8aef71ca6a940ee35e1b1f07f0ed9dedb42`，capabilities schemaVersion1及包级conversion-result schemaVersion1。切片resume/native导入与包级工作区是不同合同；默认包级接口保持兼容；显式 `--workflow slice` 接受切片候选与实际 `--resume-native` 验证，不自动启动Editor。

先按[安装说明](../安装与平台.md)的GREA_PROVIDERS机制配置规范ID `monkey`，command为显式本地CLI argv，probe为同一CLI加`capabilities --json`。新provider默认缺失；路径由用户配置，不使用维护者源码绝对路径。

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

自有最小原生示例见[生命周期接续验收样例](../../tools/unity/lifecycle-sample/README.md)。固定provider原始候选遇到无效依赖与Editor导入边界时，保留原件，在新Editor脚手架中显式修复、记录差异后接续。**修复后的Editor通过属于GREA adopted工程验收，不伪造原候选的provider resume pass**。这不是任意Cocos游戏自动恢复能力或真实项目完整度百分比。

## 全量初版协作与当前能力

完整恢复采用[全量初版工程与协作](../../plugin/shared/01-流程-全量初版工程与协作.md)。monkey负责批量解析/原生装配/代码依据和初稿；GREA冻结调用并核交接，游戏Agent在真实初版上开发。现有package/slice是此前固定0.3.0.dev1内部候选的已验合同，不代表最新monkey全版本或all-scope。新版本CLI、Unity来源全Bundle及Cocos全集原生续接正在由上游维护；**GREA自动all-scope导出适配not_available**。不要猜`--all-scope`参数、以lookup代替导出，或新写GREA转换器；上游新合同固定版本后再接入。

新增显式、只读的批量交接审计（保持monkey_bridge工具ID）：

```sh
bin/grea legacy monkey_bridge --config /path/pinned-monkey-lock.json --workflow handoff --workspace /path/independent-export --handoff-contract /path/bulk-handoff.json --output /path/new-review
```

该调用仍核固定provider版本/capabilities；只审计既有产物，不调用批量转换、原生导入或游戏业务。结果handoff_ready只表示**声明的逻辑映射和实际文件／原生收据字节吻合**，authority保留caller-declared，不是GREA重新运行了Editor，更不证明完整玩法。成功的初版候选保持partial，不升为全游戏success。缺原生工程、源图仅留原文/lookup、无匹配导入编译收据等均needs_action。

handoff合同v1为JSON，严格包含以下字段：

| 字段 | 形状与含义 |
|---|---|
| schema_version / provider_version | 1；与lock固定版本一致 |
| target_engine / project_path | unity或cocos；相对workspace的真实工程目录 |
| source_inventory | `{path,sha256}`，相对合同文件的既有inspect-target完整目录结果或envelope；盘点文件必须在输入目录之外，实际输入全量重新核SHA；全集范围仍由调用者声明 |
| assets | 每个逻辑源资产一条，唯一source_id、category、source_files（盘点内相对路径数组）、disposition、outputs（相对工程的path/sha256数组）、reason；多个资产可共享文件，不能按重复映射行计算恢复率 |
| entry | `{path,sha256}`，相对目标工程的AI接续入口，含必要使用命令与业务缺口 |
| native_check | null表示未验；或相对合同的`{path,sha256}`，置于目标工程外的实际引擎验收收据（避免清单自指） |

category为texture/sprite/material/shader/font/audio/animation/spine/config/prefab/scene/code/other；disposition为native/draft/retained/unsupported/missing。非native必须写源位置、TODO或缺口原因；前三类须实际输出。所有输入文件必须归属某个逻辑处置，不能漏掉未转换资料。源有Prefab/Scene时逐项要求真正`.prefab`／`.unity`（Creator为`.scene`）；源无图不凭空加Prefab数量门。未知代码保留原始依据，具名草稿和未恢复方法位置，不生成重复空类冒充业务。

native_check内容严格为schema_version1、target_engine、import_status、compile_status、artifacts；两种status需pass，artifacts为相对工程的path/sha256数组，绑定整个当前交付树。明确排除根级Library/Temp/obj/Logs/UserSettings/Build/Builds/.git/.grea缓存或本地构建目录，不能只绑定一个成功Prefab。实际收据与其含义仍由提交者负责，GREA只验字节。输入/目标各≤100000文件/8GiB、单文件≤512MiB，合同/收据≤32MiB；超限明确失败，不降级为“全量成功”。Unity须有Assets、Packages/manifest.json和ProjectSettings/ProjectVersion.txt，Creator须有assets及project.json；不执行这些文件中的指令。

先批量初版，再Agent开发；不要求未知方法或全玩法先完成才交接，也不能以completed、入账数、媒体数或空代码数量替代上述实际产物。既有游戏接收新候选时按版本与GUID来源合并，不能盲覆盖已有JSON/代码/存档。
