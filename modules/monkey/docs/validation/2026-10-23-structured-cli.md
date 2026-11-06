# 整包CLI与同IR双目标验证

本组入口为 `bin/monkey convert --input-set INPUTS.json --target both --out FRESH`；单目录/明文wxapkg/APK仍通过`--source`进入同一CLI。工具没有全局安装、启动Editor、调用模型或联网获取素材。

## 真实输入与结果

`outputs/structured-sample-game-03`使用`.private/sample-game-input-set.json`明确列出的四个冻结根：main、internal、gameAsset、remoteAsset。声明SHA为`[private fingerprint omitted]`；冻结来源回执关系已核验，appId/游戏版本仍未知。输入5097文件、243799340字节，两个目标accounted文件与字节数均完全相等。它与此前73文件主分包属于不同输入集，不比较百分比。

共享reader识别13994对象；验证IR为20605节点、23373组件、5179 SpriteFrame、6字体、8 JsonAsset。源里一个父子图不一致的资产被整体隔离，未猜测修复。原生计划中Unity10426、Creator9562个组件标记可转换，其余保留缺口。

每端文件去向：4673 structured_candidate、198 copied、135 deduplicated、90 unconverted、1 source_recovered。structured_candidate是具有规范化证据或纹理依赖的输入文件，并不等于已经保存成原生资产。资源键台账1487 missingReferences与reader的717 input_not_provided、4 provided_file_resolver_unmatched、3 unsupported_format为不同口径，不能相加或相互替代。

源1632 Prefab图已规范化，但当前原生适配器生成共享候选森林，不是1632个已保存的原生Prefab。914 RF代码区域保持源码证据与编译排除区合同初稿，不能视为完整业务转译。5399处精确脚本身份绑定；任务按707页面批、6资源批和1不派工的未分类池聚合为714项，336代码区域仍未分类，没有启动Agent。

工程manifest：Unity `[private fingerprint omitted]`；Creator `[private fingerprint omitted]`。标准目录game-standard-v1，原始JSON payload保持值与路径文本；目标工程不依赖原件或另一目标。

## 续跑和失败证据

真实运行先暴露大PSD留存、生成文档读取预算、inline节点、事件引用、坏图、导出清单预算等问题；失败候选保留。普通原始JSON和图像预算没有因此取消，受控生成阶段按所有权/字节数/SHA核验后读取。修复后通过公开`convert --resume ... --input-set ...`复用inspect/normalize/两个plan，归档旧候选并重新输出两目标；最终completed=true、workflowStatus=needs_action。

续跑会拒绝生成文件被改、未知/缺失文件、输入或清单身份变化；完成候选和具有可信journal/备份的中断候选均可恢复。此前完成候选及中断副本保留在Previous，不覆盖人工文件。工具版本仍0.3.0.dev1；尚未引入每个算法阶段独立代码签名，跨算法升级复用仍需谨慎。

## 验证与界限

定向测试：structured3项、package6项、cache2项、source-shapes2项通过，包含跨bundle依赖/JSON值不被目录翻译改动、身份冲突先拒绝、修改阻止续跑、中断恢复、容器路径攻击、缓存映射冲突/穿越与坏图隔离。Unity薄适配器使用本机6000.6.2f1程序集离线C#编译通过，证据`.private/structured-unity-compile-04`；此编译没有启动Unity。

采纳已实测GREA样板暴露的四类适配器问题：移除无效input包、同步刷新TextureImporter、先保存独立新建的bootstrap场景、创建原生输出目录。GREA通过不等于monkey原生通过。

整包Editor导入、保存重开、场景/Prefab回读、画面、业务与Player均not_run；Spine闭包、更多组件/业务语义、独立源Prefab生成和编辑器预检/编排仍待实现。CLI产物是独立可交接候选，不能报告完整游戏已转换可玩。

两目标整包`verify --level static`已通过，诊断均0：`outputs/structured-sample-game-unity-check-01`及`outputs/structured-sample-game-cocos-check-01`。它们核验生成文件哈希/资源引用/GUID与目录边界，不构成Editor导入通过。
