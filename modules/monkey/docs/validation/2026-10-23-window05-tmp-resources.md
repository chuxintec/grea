# 窗口05纹理推进与TMP资源寻址修复

窗口05于北京时间13:14:28接管，内部截止13:24:28、外层13:26:28，方法预算600秒；固定cf9c012及05 manifest `[private fingerprint omitted]`。新独立副本`outputs/acceptance/v05-structured-01/UnityProject`经正常exec审批启动，实际PID17274。

本轮越过全部纹理方法：计划textures为10358项，即5179帧的trimmed与original两种原生Sprite变体，不是10358个源SpriteFrame。方法计时49.078454秒推进至fonts第6/8项，失败为`Native TMP bitmap shader unavailable after resource import`。不能把49秒当完整导入耗时，接管至确认退出为3分11秒（含复制、初始化及检查）。batch方法抛异常后Unity自行exit1，CLI exit6表示包装命令失败，13:17:39 ps确认PID不存在，已提前释放。sourcePrefab0、Scene保存/重开/读回仍not_run，原05SHA不变。window.json、native-progress.json及脱敏日志为本地证据；没有重启/信号/其他项目操作。

## 资源与名称证据

只读本次已安装的`com.unity.ugui@0f30cee369f3`：package.json与packages-lock均为2.6.0 builtin，Editor6000.6.2f1 BuiltInPackages原件也为2.6.0；原manifest种子2.0.0没有阻止Unity解析实际内置版本。这不是新安装或升级全局包。

`TMP Essential Resources.unitypackage`实际存在，SHA `[private fingerprint omitted]`。只读tar成员确认如下资源与shader名称匹配，失败工程四者均未生成：

|资源|原始shader名称|
|---|---|
|Assets/TextMesh Pro/Shaders/TMP_Bitmap-Custom-Atlas.shader|TextMeshPro/Bitmap Custom Atlas|
|Assets/TextMesh Pro/Shaders/TMP_SDF.shader|TextMeshPro/Distance Field|
|Assets/TextMesh Pro/Shaders/TMP_SDF-Mobile.shader|TextMeshPro/Mobile/Distance Field|
|Assets/TextMesh Pro/Resources/TMP Settings.asset|设置资产|

检查结果`.private/tmp-resource-evidence-01/inspection.json`。实际不是必需包在机器上缺失或shader名称拼错。已安装TMP辅助类GetPackageFullPath依赖物理`Packages/com.unity.ugui`，本工程该目录不存在，后备的TextMesh Pro/Editor Resources位置也为0。其路径分支可离线复现；失败当时没有捕获辅助函数实际返回值，不将后续导入时序完全排除。

只读核对GREA现有样例没有取得本项相同TMP字体闭包的原生证明，不能借其整体通过代替本轮。

## 当前修复及未验项

- 显式依赖声明改为本Editor实际uGUI2.6.0，import-plan含必需资源合同；保留旧版本候选不改档。
- Editor通过PackageInfo.FindForAssetPath取得注册包的resolvedPath，严格核对包名/版本、archive存在与SHA；不用物理虚拟目录猜测或扫描其他工程缓存。
- 只导入该包的Essential archive，不导Examples、不修改引擎/认证、不安装其他runtime。使用当前SDK的UnityEditor.AssetPackage.Package.Import并同步Refresh，加载原名三份shader与TMP Settings，保存GUID/来源回执`Analysis/tmp-resources.json`并嵌入native readback；位图材质直接引用验证过的同名shader资产，没有不等价替换。
- 具体区分包未解析/版本不符、archive缺失、导入后文件未生成、文件存在但native asset未就绪、shader名不符。导入时序如果仍未闭合，报TMP_ESSENTIAL_IMPORT_INCOMPLETE或TMP_ESSENTIAL_ASSETS_NOT_READY，不继续猜测。
- 原生verify对有字体的项目要求上述资源回执，不把仅编译或仅发起Import当作通过；preflight也分类相应失败。新增tmp-resources阶段沿用预算/截止检查。

官方参考：[AssetDatabase.ImportPackage](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/AssetDatabase.ImportPackage.html)；当前SDK内TMP_PackageResourceImporter.cs提供新API的实际用法，离线C#编译确认PackageInfo及UnityEditor.AssetPackage.Package在6000.6.2f1可访问。ImportPackage旧API编译01只有obsolete warning，改当前SDK新API后02无警告通过。官方资料和编译都不是本机实际资源导入完成证明。

定向检查：structured3项（依赖版本/资源合同、标准目录和原件保护）、包级6项（裸工作区依赖种子改动）、进度/资源错误边界4项通过；没有重复旧reader/图像/Creator原生矩阵。修复后的资源实际导入/同步、Prefab/Scene保存重开和代表几何/引用均待新明确窗口许可。

## 修复候选06

新生成Unity单目标`outputs/structured-sample-game-06/UnityProject`，manifest `[private fingerprint omitted]`；固定实现`[private fingerprint omitted]`。同四根5097文件/243799340字节留存相等，仍含1630独立Prefab计划、30 Spine闭包/1缺bin。实际import-plan的tmpResources为com.unity.ugui 2.6.0和原Essential archive，emit身份核对当前源码一致。原05冻结manifest再次核对不变。

仅对本次有变化的Unity候选执行静态verify，未重复Creator/旧reader矩阵。06没有启动Editor；资源实际完成导入和所有原生gate仍待新授权窗口。
06 Unity静态verify零诊断，证据`outputs/structured-sample-game-06-unity-check`；没有运行其Editor。
