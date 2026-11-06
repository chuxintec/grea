# NativeFlow 原生生产边界修复

本地分支 `codex/native-layout-production-fix`。冻结 dev3 源和分发包保持原样；本记录是其独立增量候选，不是新发布或完整游戏验收。

原 NativeFlowLayoutGroup 在 Player 中实现了源布局递推。本次按实际48个源Prefab／63个组件及两个汇总Prefab，改为Unity GridLayoutGroup／HorizontalLayoutGroup及ContentSizeFitter。运行时不再编译或引用旧Flow类型；源代码和MIT署名保留在冻结历史、工具licenses参考和候选SourceRecovery/RetiredLayout。

内容网格的极小子类只处理Image布局优先级及空内容垂直尺寸，不包含排列算法。既有Linear组件和共享变更通知基类仍保留，本次没有整体迁移它们。`_N$cellSize`五处读取缺口修正，双别名冲突拒绝。卡季零尺寸模板采用确切嵌套Prefab根尺寸，禁用项保持禁用。

## 实际验证

|项目|结果|
|---|---|
|Unity／UGUI|6000.6.2f1／2.6.0|
|源Prefab／源布局|48／63|
|含汇总的资产／组件映射|50／189|
|本轮新保存／精确复用旧证据|36／14；复用项未重写|
|绑定节点几何／身份|3384；另逐项核对所有其他序列化对象ID、类型、脚本及owner|
|实际目标组件|168 IntrinsicGridLayoutGroup、18标准GridLayoutGroup、3 HorizontalLayoutGroup|
|代表动态探针|6组；强制原生布局更新、增隐显、容器尺寸、空内容及原有子Rect变化|
|旧运行时类型／旧序列化引用|均不存在|
|冻结源复核|92434份索引文件SHA全部一致|
|离线检查|29项定向、CLI拒绝与导出回归；实际C#编译；ZIP111载荷逐项哈希|

问卷原Label未恢复，探针只改变确切源节点的现有子Rect高度并验证父布局／恢复，不添加替代Label。原文本动态、Player、完整业务、输入和像素保真仍not_run。未见的动态异尺寸换行、缩放参与或固定行列不复用旧Flow算法，保留review诊断。

## 运行层与身份

- 01：默认沙盒出现只读数据库／XPC和许可证初始化错误，未进入方法；只结束自有PID86605，保留原失败。不据此判断用户许可证无效。
- 02：正常require_escalated审批及nographics后许可解析、方法进入；14资产／18组件保存回读通过，问卷探针错误假定存在TMP而停止。PID88949 exit1，旧来源限制和工具假设分开记录。
- 03：独立COW承接已验14资产，仅新增36资产；修正真实组件探针并明确文本缺口。PID90784，UTC18:32:29–18:33:37，exit0/reaped。6探针完成、旧类型及引用闭合，提前释放新窗口。

所有真实段均为新独立窗口，首新失败退出后离线处理；未在同窗重启、改许可、全量重导、构建Player或写游戏工程。

冻结源manifest：`[private fingerprint omitted]`。
最终候选manifest：`[private fingerprint omitted]`。
最终helper：`[private fingerprint omitted]`。

候选：`outputs/native-layout-fix-03/UnityProject`；原生记录：`outputs/native-layout-execution-03`；全工程73项差异及身份合同：`outputs/native-layout-delta-01`。原失败层01/02及精确续接历史保留。

## 局部采用包

`outputs/native-layout-adoption-01/monkey-native-layout-delta.zip`，8824625字节，SHA256 `[private fingerprint omitted]`。

`adoption-manifest.json` SHA256 `[private fingerprint omitted]`。

53项操作为50Prefab、1运行时适配更新、2旧脚本／meta删除指令；111载荷包括不变meta、来源署名及身份／限制证据。ZIP不含Library、完整资源池或全量项目。实际游戏须按GUID与旧SHA核对人工变更、全部旧脚本引用和C#类型使用后合并，再由游戏主开发做必要原生读回。monkey没有将包应用到游戏。

公开步骤和失败续接约束见[NATIVE-LAYOUT-PATCH](../NATIVE-LAYOUT-PATCH.md)。本地工具源码／文档可检查点提交，不推送、tag或Release。
