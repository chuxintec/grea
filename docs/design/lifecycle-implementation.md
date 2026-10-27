# GREA 生命周期开发实施说明

> 职责整改：本文保留此前生命周期设计与已实现边界；执行工具归属以[三产品架构](../../proposals/monkey-grea-lifecycle-architecture.md)为准，GREA维护Skill与薄入口，monkey负责恢复，beaver负责开发工程执行。唯一进度仍为生命周期路线。


当前状态与版本出口见proposals/lifecycle-roadmap.md。本文件说明落点和检查范围，不另设进度表。

## 实现位置

| 范围 | 首选现有落点 | 约束 |
|---|---|---|
| 路由/阶段/模式 | src/grea/workflows.py、contracts.py、change_contracts.py | 复用统一CLI/MCP，版本化兼容旧ui_ux与默认Unity行为 |
| monkey provider | 新provider模块＋docs/providers/monkey.md＋registry | 仅编排、能力/结果归一，不复制转换器；实际路径由配置注入 |
| 资产检查与总览 | src/grea/tools/image_alpha_audit.py及新联系表模块 | 保护原图、固定依赖、输出预算，边界反例先行 |
| 参考与技能 | plugin/skills/grea、evolve、reskin、research、delivery及shared | 改权威源，不手改安装副本；skill只流程，代码归工具层 |
| 运营工具 | src/grea/tools/下窄模块＋contracts/registry/schema | 先只读数据、配置候选；不先造Web后台和在线任务调度 |
| 文档/测试/发布 | docs、tests、scripts原目录；schemas按现有生成 | 新能力真实实现后才注册available；未运行平台仍not_run |

所有具体文件名/操作ID以实际仓库契约查重后确定。建议字段与名称不是提前批准的僵硬API；必要兼容调整由开发者自主实现并留清楚说明。

## 上游吸收清单

固定来源awesome-gamedev-agent-skills commit38a4c2500eeb5ff9ac084336b8f66108069d2f8d；本机克隆只读位于Manager/.runtime/vendor-reviews，公开产品只留仓库URL、commit、选用文件与归属，不能嵌入本机路径。

- 采纳并改造create-game-assets的brief、manifest来源/许可字段、联系表思路。
- image规格增量合入现有alpha工具。已实测上游max-colors上限+1误放行，不能原样复制；require-alpha只证明通道存在，不能替代透明度/空图审计。
- save-systems迁移与备份原则按客户端/服务端权威适用改写。
- genres/level-design/prototype/game-ui-ux/game-feel等仅按模式作短参考；SO数值真源、默认Godot、强制手柄、全部灰盒和类型must-have不直接继承。
- Steam/itch仅有目标需求才接provider；上游Steam等待期21天与官方30天不符、butler使用LATEST未校验、示例明文密码等必须纠正，不能直接变成执行脚本。
- Apache LICENSE/NOTICE和修改说明依选用范围保留；不要将原项目素材、样本或外部收费依赖的许可混为同一授权。源库归属声明不等于完整权属审计。

## 第一工作包：直接开工

1. 核对基线/现存AGENTS差异和新计划，不重读所有历史；保留旧research-cocos-go状态，切换本轮唯一进度入口。
2. 实现生命周期/模式合同最小增量及旧ui_ux/Unity兼容；同步修正旧Cocos映射表中JSON→SO冲突。
3. 只读探测monkey当前capabilities/convert/help与输出结果，做一个可配置provider，实际调用到隔离输出或用真实已有产物完成结果归一；执行所需输入/版本声明清楚，不猜monkey尚无能力。
4. 用有界样例串起research/evidence引用→monkey工程/代码初稿及缺口→AI模块包。真实游戏资源仅在GREA .private隔离验证，不能复制进公开fixtures；上游工具或monkey尚不支持的项如实needs_action。
5. 给出一条可实际执行命令、结果位置和未验边界，本地提交成组成果后接续L1.3，不停在“计划已同步”。

若monkey接口正在改变：固定可复用的已提交版本/输出schema，使用兼容适配；没有稳定能力就先做隔离契约样例并保留真实联调待验，同时继续资产工具等独立开发。不要为等另一个聊天响应停止整个GREA。

## 有限验证

- LC1：旧接口兼容、新模式错配/未知目标、provider缺失/版本不符/输入变化/partial/native证据不足、资源输出保护和色数边界；真实样例至少体现实际调用而非只有模拟返回。
- LC2：批准变化与旧不变量分别覆盖，旧档代表样例及未知版本拒绝、JSON/服务端权威边界；只检查改动支持的引擎和模块，不固定全模式×全平台矩阵。
- LC3：重复事件、时间边界、缺字段/小样本、产出消耗归类、配置兼容/回退预览；仅合成或授权匿名数据，无生产写入和真实交易。
- 每包只跑受影响检查，成组集成再跑仓库要求的相关发布/文档/技能检查一次。旧验证不适用于新代码的地方准确补验，不反复重建完整双平台插件。
- 真实Creator/Unity未获窗口或平台不可用时，原生层not_run；不通过安装引擎、额外子Agent或抢桌面解除。

## 本轮交付范围

本地源码、短Skill与references、CLI/MCP合同/schema、必要合成fixtures、使用示例、实际结果和已知限制。本地分组提交允许；原分支成果保留，需要隔离分支可由开发者选择，但不合并主分支、不远端推送、不创建Release、不安装到全局客户端。

用户本次批准路线实施，不包含线上运营动作、改其他游戏工程、写monkey仓库或生产服务。完成可用本地包后，正式发布/安装再按真实用户授权办理；不用未经授权的动作卡住已可交付源码成果。

## 反馈与持续推进

本轮由既有GREA开发者单人执行。不新建Agent或周期巡检；保持当前模型/强度/上下文。成组交付/真正阻塞/需改变范围时直接反馈总监，普通ACK非前置。

如遇跨聊天自动审批拒绝，记录动作和理由，不换通道/代转/重发绕过；本地已有授权工作继续，进度维护在原任务源。总监读取并协调，不建立经理中转。
