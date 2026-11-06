# Typed GREA格式化首个子集（v0.2开发中）

```sh
monkey format-project --project unimported-creator-candidate --profile grea --preview --out fresh-preview
monkey format-project --project unimported-creator-candidate --plan fresh-preview/format-plan.json --out fresh-formatted
```

当前支持未导入、归属明确、使用新typed output-path导入器的生成式Unity/Creator候选。公开package convert默认none、显式--format grea执行导出后的独立阶段；两端均准备成功才晋升canonical，原工程保留Unformatted。格式失败保留基线且阻止native。已导入资产首期拒绝，native move不是本版前置。直接Unity来源新增[受限叶Prefab原生后处理](providers/UNITY-SOURCE-NATIVE.md)，其余来源形状仍在Editor启动前拒绝；不能声称整组v0.2已完成。legacy game-standard-v1、Library/已导入、未知文件/人工漂移拒绝；不在原工程就地移动。

按真实类型将资源放assets/content/images/sprites、fonts、config/recovered、animations、prefabs，Scene放assets/scenes，已证明的Label脚本放assets/scripts/presentation/ui、状态类放domain/state。不创造没有职责的空框架。只改ProjectModel资产路径槽、明确代码artifact/meta、source-map/name-map目标字段、handoff生成目标与导入器outputPaths；SourceId/UUID/原名/正文/逻辑key/数值资源原字节保持。BMFont只从明确font→atlas关系重发单page字段，不重写glyph数值。

Preview包含input manifest/各文件hash/owner、typed路径、资源身份、物理移动和编辑字段。Apply重新生成计划并逐项比较，算法/输入/所有权不同即stale；再次核源文件，输出到fresh目录。大小写/Unicode/路径冲突、人工meta/资源改动、脚本meta/ESM模块边界不符等不静默跳过。纯数值JSON测试保留1.2500、-0.0和恰含旧路径的加载字符串原字节，不做任意JSON/代码全局prefix替换。

## 真实MainUi none/grea对照

- none candidate05：SHA71a110e66437afc0c69b844be0b5d11ba70b3a8ae04afb83fee74fcc8cd7f896；grea01：SHAdcfc2a92581c5fa2298a33b98e79ff6e53186e65dce704979c4ec2ffaee300e2。94目标路径变化、184物理文件移动。
- none native02 own72833：2026-10-23T19:42:33.598898Z→19:42:51.032834Z；grea native01 own73175：19:43:25.973864Z→19:43:43.423979Z。两者正常TERM/reaped、Creator3.8.8 editor pass/0诊断。
- 91资源UUID及75 SpriteFrame身份、原字体页、129源节点几何、同5原NumberLabel组件/数值子集/Scene及独立Prefab保存重载全部保持。脚本固定UUIDd70c6943-490a-5b7b-bf8a-ca7b490ad126、实际classId d70c6lDSQpbe7+KyntJCtEm两模式相同。
- 输入没有物化Prefab/节点的native身份，本次仅此前已分配的资源/脚本ID纳入身份保持。fresh导入MainUi Prefab UUID分别09ecace9-6934-4d09-bc3d-956794e27e9d和1f486368-acee-4b13-a702-7a636cbd5310；不能将首次生成ID说成已有ID保持，也不能据其差异认定旧身份被格式破坏。这些首次生成ID按来源映射记录；如未来支持已有native对象迁移，才需asset database move后另验。

原SHRINK动态行为、4个复杂代码方法、原版视觉/输入/玩法均没有因此晋级。实际比较在outputs/number-label-format-comparison-01/comparison.json（私有、不发行）。

## Unity与公开单命令新增证据

Unity MainUi none/grea：113路径变化/183物理文件移动，Scene/Prefab代码不改写，Editor host原字节不变，仅Analysis/output-paths.json给明确类型路径。own74623于2026-10-23T20:17:39Z→20:17:58Z、own75166于20:21:02Z→20:21:19Z，均exit0/reaped、strict0/editor partial（原未知组件保持partial）。91个已有meta GUID、脚本ed4943a3d3615a76b6fe2586a348f144、129节点geometry、5数值组件/原字体/TMP绑定与保存重载保持。20个字体SO/Prefab/Scene首次生成位置及实际source映射单列，不冒称旧ID。

公开convert --target both --format grea --native已在合成样本执行第二轮完整端到端：Unity76820 exit0/reaped、Creator77095正常TERM/reaped，strict均0，orchestration=completed_native_stages。首轮因包内原图meta未收进回执严格失败并保留；新回执覆盖自有assets，并逐项核导出前封存GUID/UUID不变，未放宽元数据/内容检查。合成1节点链路不作为真实游戏恢复通过；真实129节点验证独立保留。

旧整体字符串/JSON/代码替换写入器已退役，targets/layout.py只读旧manifest物理路径兼容；新生成只用typed槽和位置配置。数值JSON字节、脚本/原名/逻辑key不重写。格式化package resume暂拒绝并保留原工程，需fresh输出。

JS次选已纳入fresh Creator格式：script UUID/meta原字节保持，只有typed脚本路径移动；生成的assets/package.json保持在assets根，不影响extensions的CommonJS入口。格式前强核代码合同中该JSON的SHA及精确type=module，漂移即拒绝。真实5绑定JS注册与公开单命令grea/native合成接线均已执行，范围与失败见CODE-SUBSET.md。

Unity来源公开native/grea已在武侠131引用Prefab通过，136既有meta GUID保持。134个Sprite/Texture因Resources或bundle名固定，实际移动0；不借此宣称真实资源搬移已验。基础none与grea工程分别保留，普通未知Scene/借取实例值仍阻断native。
