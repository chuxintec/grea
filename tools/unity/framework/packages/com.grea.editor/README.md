# Grea Editor 0.2.0

MIT 自有源码。依赖 Foundation/uGUI 0.2.0，仅 Editor 程序集，没有 Runtime→Editor 引用。BindingValidator 保持只读；M3 新增 ProjectGenerator，只允许 grea 拥有的暂存工程创建资产。

最小用法：`var findings = Grea.Editor.BindingValidator.Inspect(explicitRoot);`。检查指定 GameObject 及其 inactive 子节点；返回对象相对路径、组件完整名、字段名与 `MISSING_SCRIPT` / `MISSING_BINDING`。实现 IBindingCheck 的组件提供必需字段列表。null 根抛 ArgumentNullException；正常空根返回空列表。见 `Tests/Editor/BindingTests.cs`。

不全场搜索、不修改资产、不补默认引用。没有声明校验协议的组件不被判定为“全部绑定正确”；空 findings 也不代表 Prefab/Scene 结构、Canvas 排序、资源加载、UI 显示或玩法通过。ProjectGenerator 经 PrefabUtility/AssetDatabase/EditorSceneManager 创建 Prefab、配置和场景；记录 GUID/fileID 和逐资产哈希日志。已记录资产只校验不重写，pending 或人工修改使恢复停止。Run 入口仅从暂存工程 Tools/Generated/request.json 读取已预检配置；普通项目应通过 grea 的 plan/generate/recover 契约调用，不能直接对已有工程执行。

将包目录保留 meta 复制到新测试工程 Packages；同时安装所需自有包。业务工程正式接入需经过对应项目授权和验收。

生成器额外依赖 uGUI 与 URP 17.6.0 的 Editor 可用 API。生成/恢复测试位于 grea tests/unity/m3，必须带隔离测试工程标记才执行。当前不升级基础 Prefab，也不 Apply Variant overrides。
