# 批量初版开发与失败层记录

## 当前：批量完整初版工程交接（2026-10-24）

历史实施顺序：monkey 先批量导出已取得全集的原生资源与代码初版，再由开发者继续处理业务与验收。原始内部规划引用已从公开摘要移除。

当前分支`codex/full-project-handoff`，本地开发身份0.2.0.dev3，基于冻结dev2；dev1发布及dev2候选保持不变。重启前WIP全部保留，未reset/新建Agent/发布。重启后实际grea MCP session已回读2026.10.24rc1/status ok/package_root `[local path] matched；已复用新版路由和全量初版协作合同。旧CLI-only刷新回执作为历史保留，不追溯修改此前工具身份。

- 样例项目full02一次原生装配已于15:11:01Z退出回收，固定窗口已释放、不可复用。实际1694源Prefab已保存重开，16934 Sprite读回、24784节点、10508引用、0MissingScript；原结果completed_partial且Editor fail/5诊断、16630来源限制不改写。5诊断均SHRINK标签：字体GUID/文本/字形一致，实际字号缩小；正在补配置证据/修验证共因。3源Scene仅有节点读回，需从既有完整层级另存两主线原生Scene、小游戏保留原件与排除说明；不重冷跑素材。
- 914模块已生成10607具名方法、10391字段声明/TODO，模块原文、RF、owner alias/参数/字节SHA保留（`outputs/bulk-sample-game-named-code-02`），0方法实现、未编译；需添加到自有自包含交接并补importer/实际Sprite fileID/Prefab引用合同。7.1MB主脚本bulk静态模型已输出16384方法，重复赋值显式unsupported，不再因全文件预算而丢失模型。
- 向样例项目601容器typed结果已完成并复用：80605 parsed/975 unparsed，745576030字节分片，600池不重解析；发现8052纹理引用/8007唯一键。104原池覆盖91，另找到94个确切缓存键；原脚本DATA_CDN的v8根已通过已知冻结纹理同SHA证明。同一job续取已结束：8007唯一键中7582已取得、425均为确切HTTP404；池共7595份（含13份原始未引用项），无补取child。成功项与404未重试、不猜URL/Hash。下一步为缺失纹理隔离、可续接批量provider准备与完整初版导出。
- 大型typed文档仅在明确批量入口用16M值/128深度、每片128MiB有界预算；全局默认不放开。当前优先收敛纹理清单与可续接准备/导出阶段，再在新协调窗口内做一次AssetRipper整体导出（每段≤30分钟，旧窗口不可复用）。原始/lookup/图库、typed行数与真实native资源分开报告。

样例项目914具名模块已通过公开code-handoff追加到上述自有完整原生工程；原始模块与源映射同工程可读。实际Sprite合同已输出16934 Sprite/8467源帧/1694 Prefab/7756 Sprite PPtr。增量Scene/SHRINK helper已通过本机Unity6程序集离线编译（11份C#），公开native-finish执行器和SHRINK配置/哈希/窗口保护的19项定向检查通过；原5fail不改写。最新准备目录`outputs/bulk-sample-game-finish-plan-03`；仅申请该准备的单次增量原生窗口，不重装配1694 Prefab或媒体。

2026-10-25单次增量窗口01已释放：own Unity pid76169于16:29:53Z启动、16:30:01Z退出回收，exit1，Scene/字体读回均0。NullReference位于旧SettleNativeLayout对nativeProgress的访问；它依赖完整导入初始化，增量入口未建立该状态。保留`outputs/bulk-sample-game-finish-native-01`及工程内失败读回，不在原窗循环冷启；离线改为独立有界布局收敛，再准备新候选层/窗口。原manifest/Prefab/读回输入哈希均保持绑定。本地WIP检查点`09b026c`已保存27路径、56项定向检查通过，未推送/发布。

增量异常已离线修复：BulkSettleNativeLayout只用自身deadline/clock，不读写完整导入的nativeProgress；11份C#再次离线编译通过。新增前次失败层精确身份/归档续接，未知或手工修改层拒绝覆盖；6项专门反例通过（含首次5项）。新准备为`outputs/bulk-sample-game-finish-plan-04`，新窗执行须显式`--previous-execution outputs/bulk-sample-game-finish-native-01`。

增量原生02于16:35:46Z–16:36:01Z完成并回收own76902（exit1/partial）：5处SHRINK配置均configuration-verified、源Prefab SHA不变；两源Scene未保存，原因是新batch Editor的untitled默认场景不允许Additive NewScene。此失败保留`outputs/bulk-sample-game-finish-native-02`，原窗释放不重启。离线修复只在增量入口先打开既有3539字节ImportBootstrap场景，再做两源Scene；不加载/重建全量CandidateScene。

增量原生03已完成：own77202于16:40:28Z–16:40:43Z退出回收，exit0/completed；两主线源Scene32/268节点已保存重开，逐节点Scene GUID/GameObject/RectTransform实际fileID齐，0MissingScript；5SHRINK同组配置通过且Prefab未改。小游戏Scene4节点按产品排除。01/02失败层保留；正在做独立verify和自包含合同/manifest冻结。向样例项目离线准备01同样已完成：601/601，7626个纹理对象有据水合，426个对象对应425确切404键隔离，所有非纹理保留对象字节一致，原始包不写入；own77137已退出回收。下一段只做已准备全集的单次AssetRipper导出，单段预算≤1500秒。

向样例项目AssetRipper全集导出01已完成：own77765退出0/reaped，53.744秒，601冻结输入/813171927字节未变；导出133003文件/1382299527字节，其中65309资源文件（尚非去重资源数），UnreadableAssets0。回执`outputs/bulk-sample-project-provider-01/export.json`，不再重跑provider；公开convert正在复用该导出与601旧typed，组装自包含Unity6工程及248份代码/原件证据（含53有效图片/音频、8业务程序集具名声明、metadata/Wasm/包体），新增方法实现0。样例项目SHRINK复核已按实际缩放字号及原生固定margin计算glyph几何，保持.03阈值；`outputs/bulk-sample-game-finished-check-02`独立editor verify零诊断，旧fail/中间4条几何诊断均保留。

当前继续实现与隔离输出。唯一输出/检查点归本项目`.private/full-project-handoff-01`和`outputs/bulk-*`；两个游戏工作工程保持只读，无新provider/引擎安装、Agent或远端发布。

