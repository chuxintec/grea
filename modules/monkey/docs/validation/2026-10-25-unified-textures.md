# 2026-10-25 统一 Textures 与类型目录

用户确认 Unity Assets/Game/Content/<Type>/<Module>/、Cocos assets/resources/<Type>/<Module>/，并要求 Textures/Sprites 只保留一个。本轮只生成 Textures，保留原 Sprite 导入角色、GUID/UUID、裁切边框信息；不同尺寸/裁切数据保留独立图片，Spine/字体页图仍在闭包旁。

## 最终核验

- 最新 Unity：outputs/sample-game-unified-textures-unity-native/UnityProject。6000.6.2f1，原生验证器 0 诊断；Editor partial 保留源业务/组件缺口。1,694 源 Prefab、24,784 节点、8,952 Sprite、416 源动画、8 组动态探针，保存重开通过。后续只修改 Creator 助手，Unity 当前候选全部文件及 manifest 与已验版本完全一致。
- 最新 Creator：outputs/sample-game-unified-textures-creator-native-05/CocosProject。3.8.8，editor pass、验证器 0 诊断，方法 422.378 秒，PID 64933 已退出。1,694 源 Prefab、24,784 节点、8,472 Sprite/页图、416 动画、356 音频及 8 组动态探针完成回读；音频时长均为正值。
- 两端 528 配置 JSON 均逐表核对源 SHA 和实际导入类型；每端 7,587 纹理映射、214 Shader 来源字节核验无错误。Creator 1,768 原生 SkeletonData 已核 library；Unity 1,776 Spine 闭包以 TextAsset 保留。
- OrderList 的零尺寸 [0,0]、Ingredients 的位置 [-240,0,0] 已保存并读回；Sprite 原生尺寸模式保留。未放宽坐标/尺寸验证规则。
- **显示验收仍未通过**：Creator 日志有 19 次 Tiled Sprite StaticVBAccessor 缓冲区分配错误；这与本轮结构/引用零诊断分开记录。另有 2 个 Unity 派生按钮状态动画名超过 64 字节，仍待修复。Shader 编译、Unity Spine 播放、微信分包、Player/业务/视觉均不由本次导入结果代替。
- 当前源码 308 项测试通过，git diff --check 通过。完整机器证据：.private/unified-textures-20261025/final-native-audit.json、creator-05-asset-readback.json、unity-asset-readback.json、tests-complete.log。旧导出清理完成：删除 12 个过时/失败导出目录及 5 份中间候选备份（17 个受控根），清理前目录占用约 193.34 GiB，文件逻辑字节 203,142,619,438。仅保留本轮离线双目标、Unity 原生、Creator 原生三个阶段；失败回执、manifest、关键助手源码与日志摘要已归档于 .private/unified-textures-20261025/retired-receipts/。

## 离线资产结果

- 308 项测试通过，含图片去重后原 Sprite meta 不变、不同像素同名图片不覆盖、多个源身份共享路径不丢映射、Cocos 子资源加载键反例。
- 两端静态 pass/0 诊断。17,201 文件、884,709,704 字节原输入保留核验一致，manifest 无漏项/未认领文件。
- Unity 原 8,952 Sprite 图片身份保持；7,587 源纹理记录中 5,391 复用现有图片，仅新增 2,196。Creator 原 8,472 Sprite/字体页资产身份保持；7,587 源纹理记录中 5,415 复用、仅新增 2,172。
- 每个复用条目记录原 proposedIdentity、实际 targetIdentity、源 SHA、目标 SHA 与路径；原 Sprite 绑定不动，附加完整纹理形成别名。只按字节一致去重，未按视觉近似删除。
- 两端各 356 音频/276 独立内容、1,776 Spine 闭包、38 Effect/214 Shader 来源文件、528 配置 JSON。12,164 共有资源映射文件名一致，中文路径/超长正式资源文件名为 0。
- 离线正式类型均为 Audio、Config、Fonts、Shaders、Spine、Strings、Textures；不生成 Sprites、Bundles、Local/Remote 或来源分组根。
- Cocos loadKey 对 SpriteFrame/Texture2D 明确使用 /spriteFrame、/texture；目录闭包的 loadKey=null。参见 [Creator 3.8 官方加载文档](https://docs.cocos.com/creator/3.8/manual/en/asset/dynamic-load-resources.html)。

## 原生验证过程

Unity 6000.6.2f1 自有副本已完成（PID 42407，exit 0，686.283 秒）：1,694 源 Prefab、24,784 节点、8,952 Sprite、416 源动画读回；Missing Script 0、场景保存重开与编辑往返通过、验证器 0 诊断。实际文件含 1,696 Prefab（含预览/探针）、2 Scene、1,968 Animation（含派生 UI 状态）、356 MP3。7,587 源纹理映射均导入为 TextureImporter，1,776 Spine 数据以 TextAsset 保留，214 Shader 来源文件字节一致。Editor partial 继续保留 16,630 条源转换限制。Boot 父目录修复已由本轮实证覆盖。

Creator 首轮导入已生成 1,694 Prefab、1 Scene、416 Animation、356 MP3；library 核验 7,587 纹理映射及 1,768 原生 SkeletonData 成功，214 Shader 来源字节一致。最终动态 UI 探针仍复制整棵 24,784 节点树，原生回读长期停滞且日志出现 Tiled Sprite StaticVBAccessor 缓冲区分配错误。10:39:55 UTC 通过自有包装器终止本轮，PID 46446 已退出；首轮 NATIVE_IMPORT_FAILED / operator_interrupted 不记为通过。证据 execution-result、console、进程采样及 creator-first-asset-readback.log 保留。

已将动态探针改为复制对应完整源树与同尺寸/变换上下文，保留 Layout 同级节点；跨树 Widget/ScrollView 引用明确拒绝，避免错误引用原场景。各探针之间让出事件循环并检查期限，继续全部原状态变化与回读要求。本次八组源树分别为 24、203、59、46、144、71、46、46 节点，无跨树引用。307 项测试通过，含隔离与引用反例；第二轮已完成原生执行与八组动态探针，但最终验证失败：356 项音频时长字段缺失、两个节点的 Scene/Prefab 几何差异及汇总项，共 363 诊断。旧输出清理前置门明确拒绝执行，未删除。

复验候选 manifest 差异：Unity 75,710 文件及 manifest SHA 与已验原生源完全一致；Creator 74,694 文件中仅 dynamic-ui.js 与 scene.js 改变，静态 pass/0 诊断。复验路径为 outputs/sample-game-unified-textures-creator-native-02。

第二轮失败分析与修复：AudioClip API 应调用 [getDuration()](https://docs.cocos.com/creator/3.8/api/zh/class/AudioClip)，不存在 duration 属性；已改为原生方法并拒绝非有限/负时长。Creator Layout.onEnable 将零尺寸替换为 300×200 默认值，另有禁用 Widget 配置时的编辑器几何副作用。已在自有场景首次激活后恢复源尺寸/位置，再运行启用的原生布局；后续动态探针不会重置修改后的状态。新增两类语义反例，307 测试通过。第三轮因恢复全部尺寸使一个 Sprite 的 RAW/TRIMMED 尺寸模式被 Editor 切换为 CUSTOM 而终止，PID 57513 已退出，保留 NATIVE_IMPORT_FAILED。随后将恢复严格限制在 uiDrivenFields 未声明的坐标/尺寸轴；值相同不触发编辑器 setter，Prefab 独立激活采用自身预激活快照，同样只恢复未驱动轴。307 项全套及随后 7 项初始化/API 定向测试通过；第四轮 356 音频全部有正时长（0.130417–90.462938 秒）、八组探针完成、零尺寸 Layout 与 Sprite 模式通过；仍有一个禁用 Widget 的 Scene/Prefab 横坐标差异，连同汇总为 4 诊断，未通过。已核对本机 Creator 3.8.8 widget-internal planning reference.ts：手动 updateAlignment 递归祖先时未检查 enabled，而正常帧 visitNode 会检查。monkey 在同步对齐期间仅对自有节点临时过滤禁用 Widget 查找，finally 恢复原方法；不改 Node 原型、引擎文件或 Player 组件。包含异常时恢复的语义测试通过，第五轮最终通过，见上方最终核验。不通过扩大容差或放开未驱动坐标轴消除诊断。

## 文件路径补充核查

两端 1,694 个源 Prefab 的相对路径与文件名完全一致。Unity 另有两个 Preview 测试 Prefab、派生 UI 状态动画及 Materials，为目标原生生成差异。离线正式文件中文/超 64 字节为 0；原生追加文件中文为 0，但发现 Unity 两个派生按钮状态动画名称在 controller 名后追加后缀，超过规范 64 字节，已列为未闭合命名问题，不外推全部原生生成文件已符合长度规范。

合并前后实际 PNG 文件数：Unity 16,557 → 11,166，减少 279,239,888 字节；Creator 16,072 → 10,657，减少 283,865,628 字节。此统计仅含 Textures/Sprites 正式图片，不含原始证据与 Spine/字体闭包；不同裁切/导入身份的 Sprite 不按像素相似度合并。

## 边界

Shader 仍是来源代码，Spine 数据不等于播放已接入；8 套非标准 Spine 版本保留文本。部分动画、组件与业务仍为 handoff。远端分包/微信构建、Player 和视觉未验证；本轮候选保持 partial。

输出：outputs/sample-game-unified-textures；证据：.private/unified-textures-20261025/export-verification.json、image-identity.json、tests.log。最终原生副本及清理回执见上方最终核验；历史输出路径已退役。
