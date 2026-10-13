# Grea Editor 0.1.0

MIT 自有源码。依赖 Foundation/uGUI 0.1.0，仅 Editor 程序集，没有 Runtime→Editor 引用。此包目前只有只读绑定校验，不生成/保存任何资产。

最小用法：`var findings = Grea.Editor.BindingValidator.Inspect(explicitRoot);`。检查指定 GameObject 及其 inactive 子节点；返回对象相对路径、组件完整名、字段名与 `MISSING_SCRIPT` / `MISSING_BINDING`。实现 IBindingCheck 的组件提供必需字段列表。null 根抛 ArgumentNullException；正常空根返回空列表。见 `Tests/Editor/BindingTests.cs`。

不全场搜索、不修改资产、不补默认引用。没有声明校验协议的组件不被判定为“全部绑定正确”；空 findings 也不代表 Prefab/Scene 结构、Canvas 排序、资源加载、UI 显示或玩法通过。生成清单、PrefabUtility 生成、Variant/引用类型与 fileID 回读属于 M3。

将包目录保留 meta 复制到新测试工程 Packages；同时安装所需自有包。业务工程正式接入需经过对应项目授权和验收。
