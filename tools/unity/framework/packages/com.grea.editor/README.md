# Grea Editor 0.3.0

MIT 自有源码。依赖 Foundation 0.2.1 / uGUI 0.3.0，仅 Editor 程序集，没有 Runtime→Editor 引用。BindingValidator 保持只读；M3 新增 ProjectGenerator，只允许 grea 拥有的暂存工程创建资产。

最小用法：`var findings = Grea.Editor.BindingValidator.Inspect(explicitRoot);`。检查指定 GameObject 及其 inactive 子节点；返回对象相对路径、组件完整名、字段名与 `MISSING_SCRIPT` / `MISSING_BINDING`。实现 IBindingCheck 的组件提供必需字段列表。null 根抛 ArgumentNullException；正常空根返回空列表。见 `Tests/Editor/BindingTests.cs`。

不全场搜索、不修改资产、不补默认引用。没有声明校验协议的组件不被判定为“全部绑定正确”；空 findings 也不代表 Prefab/Scene 结构、Canvas 排序、资源加载、UI 显示或玩法通过。ProjectGenerator 经 PrefabUtility/AssetDatabase/EditorSceneManager 创建 Prefab、配置和场景；记录 GUID/fileID 和逐资产哈希日志。已记录资产只校验不重写，pending 或人工修改使恢复停止。Run 入口仅从暂存工程 Tools/Generated/request.json 读取已预检配置；普通项目应通过 grea 的 plan/generate/recover 契约调用，不能直接对已有工程执行。

将包目录保留 meta 复制到新测试工程 Packages；同时安装所需自有包。业务工程正式接入需经过对应项目授权和验收。

生成器额外依赖 uGUI 与 URP 17.6.0 的 Editor 可用 API。生成/恢复测试位于 grea tests/unity/m3，必须带隔离测试工程标记才执行。当前不升级基础 Prefab，也不 Apply Variant overrides。


0.3.0 的 ProjectGenerator 版本为 0.1.2。ButtonShell 使用稳定根 Image/Button/CommandButton 与单独 Visual/Image/Label/Icon 和 ButtonPressFeedback；Icon 默认关闭。ModalShell 使用遮罩、原生 Frame、正文槽、标题与关闭按钮。UIHost 提供 1080×2340 参考分辨率、SafeArea 和三层容器，以及单一 EventSystem。字体引用 Editor 自带 LegacyRuntime.ttf，不复制原游戏字体；具体包体许可仍按 Unity 条款。

生成配方是资源唯一来源；Journal 记录真实 GUID/fileID/文件和 meta 哈希。人工改文字、尺寸、颜色后可以保存重开，但再次生成必须拒绝覆盖。缺少生成资源的 safeAreaRoot/contentSlot/title 会定位 Prefab 路径、组件和字段；BindingValidator 对旧手工资源保持原契约。仅新隔离工程制作，不能用此 API 批量重写用户工程。

ModalShell 仅关闭按钮的默认导航为 None，避免方向键落入背景；项目为实际内容按钮显式连接导航，不能依赖所有活动 Selectable 的自动几何搜索来构成模态边界。两个示例分别连接内容动作与关闭按钮，错误弹窗隐藏内容动作时仍可关闭。它不是任意层数的模态栈或输入框架。
