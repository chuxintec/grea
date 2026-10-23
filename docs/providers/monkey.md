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
