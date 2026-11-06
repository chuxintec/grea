# 2026-10-25 资源补全与双端分区目录

用户在本聊天明确要求执行 Cocos resources/Bundles 与 Unity Content/<Group> 方案，并修复此前缺失资源。工具源码在 monkey 工作树内修改；原始样例项目/GREA/正式游戏工程只读，未发布。

## 已完成的离线验证

- 冻结输入 17,201 文件、884,709,704 字节；两端逐文件保留核对 0 漏项、0 哈希差异，manifest 外文件 0。
- Unity 候选 86,492 清单文件，Creator 候选 85,561；两端静态 pass、0 诊断。
- 两端各 356 音频文件、276 种独立内容，音频 SHA 集合完全相等。Creator 原先未进入资源目录的 259 种内容已补齐；新增合成真实 WAV 的双端公开 convert 回归测试。
- 两端各 7,587 张完整纹理，与裁切/还原的 SpriteFrame 图片分开；1,776 个 Spine 骨骼/atlas/页图闭包；38 个 Effect 的 214 个说明/GLSL 源文件；528 JSON 配置。
- 12,164 项共有资源映射文件名一致，中文输出路径 0，正式资源文件名超过 64 字节为 0。
- 资源索引 22,434 source_located、1,517 redirect_resolved、4 unresolved_index_entry。最后 4 项缺逻辑键/类型，不称为 4 个已证明丢失文件。
- 首次静态检查把实际 Shader 名 MovieClip 误识别为源目录。规则现只允许 Shader 闭包末级资产名及固定说明/GLSL 文件，其他源类型容器仍拒绝；新增正反例，重新核验两端通过。原始失败回执保留。

## 输出路径

- `outputs/sample-game-resource-layout/UnityProject/Assets/Game/Content/<Group>/<Type>/<Module>/...`
- `outputs/sample-game-resource-layout/CocosProject/assets/resources/<Group>/<Type>/<Module>/...`
- `outputs/sample-game-resource-layout/CocosProject/assets/Bundles/<Group>/<Type>/<Module>/...`

40 个分组；Boot/Common 位于 Creator resources，其他位于 Bundle。所有默认交付方式 local，可用 layout.partitions 显式声明 remote/subpackage 意图。Creator Bundle 根已生成 directory meta；Unity Addressables/AssetBundle 仅输出分组/地址方案，未安装或配置构建后端。

各工程 Docs/CONTENT-INDEX.md、Docs/RESOURCE-LOADING.md、Analysis/Mappings/resource-groups.json 与 resource-catalog.json 提供位置和身份。Spine/Shader 闭包的目录地址是前缀，加载具体文件应使用闭包报告中的 skeletonPath 或文件路径；不能把闭包目录当成单个资源加载。旧逻辑键与新物理路径分别记录，业务动态调用尚需接续。

## 原生验证

Unity 隔离导入进行中；Creator 尚未执行。本节在真实进程结束与回读后更新，不把离线计划计数当作 Scene/Prefab/Animation 已生成。

## 保留边界

- Shader 输出为真实来源代码，不声称已转成 Unity ShaderLab/Creator 3 Effect 或视觉一致。
- Creator 有 1,768 套标准 3.8 数据候选；8 套非标准版本以文本保留，不能强行改版本号。Unity Spine 是导入数据，运行包/播放未完成。
- Scene 为转换核验入口；不把 Preview 作为微信发布启动场景。原业务、动态加载键接线、跨分组依赖、实际微信本地/远程构建和真机加载均未验收。
- 既有未知组件、部分动画语义、业务初稿仍列 handoff；候选 status=partial，不等于完整可玩游戏。

证据：`.private/resource-layout-20261025/`；300 项全套通过后，静态扫描修正与新增音频测试的 18 项布局 + 6 项专项再次通过。旧候选在原生新版通过前保留。
