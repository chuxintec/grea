# 2026-10-25 用户确认的类型优先布局

用户明确指定 Unity `Assets/Game/Content/<Type>/<Module>/` 与 Cocos `assets/resources/<Type>/<Module>/`。本轮覆盖此前分组方案；自动 Group、GameRemote、采集容器和自定义 Bundle 根均取消。资源补全保留，原项目只读。

## 代码与离线导出

- 布局规范为 monkey-project/2.0.0，旧 1.0/1.1 固定路径仍可只读定位；输出新目录，不原地改旧工程。
- 所有业务资源按类型→模块组织。小游戏在 Type/MiniGames/Name 下，语言在对应类型下隔离。CupMerge 等同一小游戏名称跨类型统一，源逻辑键和 GUID/UUID 不改。
- Preview Scene、Prefab、Animation 的生成路径同步迁入指定资源根。代码和转换胶水保留原职责目录；Unity 官方 TMP/插件固定路径属于供应方资产例外。
- resource-paths.json 提供身份、原始键、新路径和加载键；闭包目录 loadKey=null，避免误当作单资源。旧 partitions 配置拒绝，无自动分包/远端配置。
- 303 项测试全部通过。最终候选位于 outputs/sample-game-type-layout-02/{UnityProject,CocosProject}；前一个无 02 后缀候选仅用于发现并修正模块大小写，已被替代。
- 17,201 输入、884,709,704 字节逐项核对，两端保留 0 漏项/哈希差异；manifest 外文件 0。静态均 pass，诊断 0。
- 两端各 356 音频文件（276 独立内容）、7,587 完整纹理、1,776 Spine 闭包、38 Effect/214 Shader 来源文件、528 配置 JSON。
- 12,164 共有资源映射文件名一致；中文路径 0，正式资源文件名超 64 字节 0。Cocos 资源区外媒体文件 0；Unity 仅两个 Editor 转换 JSON 位于转换工具目录，业务媒体均进入 Content。
- 两端离线根类型一致：Audio、Config、Fonts、Shaders、Spine、Sprites、Strings、Textures。Scenes/Prefabs/Animations 等在原生阶段生成，不为空目录伪造存在。

## 原生生成

Unity 6 独立副本正在执行；Creator 3.8.8 等待顺序窗口。本节待真实进程结果与保存读回完成后更新。

## 保留边界

Shader 为来源代码，尚未宣称目标 Shader 编译/渲染等价。Creator 1,768 套标准 Spine 3.8 数据可尝试内置导入，8 套非标准版本保留文本；Unity Spine 运行包/播放未完成。未知组件、部分动画与业务草稿仍有 handoff。微信平台构建、远端分包、Player/视觉未验证，候选保持 partial。

证据：.private/type-layout-20261025/；完整性 export-verification.json，测试 tests-final.log，转换 convert-02.log。旧导出清理必须等待新原生阶段通过后执行，并保留回执。
