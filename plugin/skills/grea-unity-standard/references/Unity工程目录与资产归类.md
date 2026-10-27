# Unity · 工程目录与资产归类

> **何时读**：新建恢复工程、整理 Assets 目录、判断资产应放在哪个类型目录，或处理 Resources/Catalog/Addressables 等动态加载路径时。
> **读完产出**：项目目录结构与所有权说明（写入项目 `Docs/PROJECT-STRUCTURE.md`）、逐文件的旧/新路径与 GUID 迁移清单、动态加载键清单。

本篇属于 [工程标准 v1](Unity工程结构与开发规范.md)（`grea-unity-project` 1.0.0）。程序集与生命周期见 [程序集分层与生命周期](Unity程序集分层与生命周期.md)；执行迁移的步骤见 [重构与资源迁移](Unity重构与资源迁移.md)。

## 工作区与项目边界

### 标准工程目录与真实类型归类

以下为允许的结构，不是必须一次性建立的空目录清单。项目编号由使用者所在工作区分配，不由生成器猜测或覆盖已有工程。

```text
<项目根>/
  grea-project.json                 # 静态规划机器可读配置
  <游戏工程名>/                    # 既有工程名沿用
    Assets/
      Game/
        Bootstrap/               # 应用入口、依赖装配与顶层作用域
        Domain/<模块>/           # 状态、规则与业务不变量
        Gameplay/<模块>/         # 用例、会话流程、业务端口
        Presentation/<模块>/     # UI、场景视图、输入表现和动画桥接
        Services/<能力>/         # 平台、存档、资源等端口实现
        Diagnostics/             # 项目状态快照与诊断适配
        Content/
          Prefabs/<模块>/          # 需要生成时再分 Generated、Variants
          Config/<模块>/           # 配置资产与运行数据分离
          Levels/<模块>/
          Materials/ Shaders/ Images/ Sprites/ Models/
          Animations/ Spine/ Fonts/ Audio/
        Scenes/                    # 最小入口与实际启用的内容场景
        Editor/
          Generators/ Validators/ Build/
        Tests/
          EditMode/ PlayMode/
      GreaGenerated/               # 固定示例配方的生成专属资产；由所有权清单管理
      ThirdParty/                  # 必须留在 Assets 的供应方资源
      Plugins/                     # 存在平台插件时使用 Unity 导入约定
    Packages/                      # manifest、lock；按需嵌入已锁定包
    ProjectSettings/
  Docs/                            # 结构说明、计划、验收及项目例外
  Tools/                           # 项目专用转换与维护工具
  Art/                             # 制作源、批准设计、制作记录
  Analysis/ Evidence/              # 原始提取、分析、行为/视觉证据
  Build/                           # 严格沿用构建规范
```

单模块 Counter 示例省略层内 `<模块>` 子目录；多模块按上述层内目录划分。其生成专属 Prefab、URP 和 BootstrapConfig 位于 `Assets/GreaGenerated/`，项目业务 seed-once 代码位于 `Assets/Game/<Layer>/`。这是本标准认可的最小配方布局，不要求添加 Runtime 包裹层；既有工程不能为符合树形图自动搬迁。

**STR-01 所有权**：Game 只保存该项目的运行与编辑必需内容。第三方代码、通用框架和项目业务分别维护；不能把原导出树换一个 Recovered/Original 名称后直接当成标准化结果。原始导出完整保留在 Analysis，只读证据不进入生成覆盖范围。

**STR-02 职责唯一**：新内容统一用 Game/Editor，不另建第二个日常 Editor 入口。UI 代码归 Presentation 下实际模块；输入设备实现归 Services/Input，输入到业务命令的转换归 Presentation。配置数据归 Content/Config，解析/校验代码归消费它的模块；不再并列含义重叠的 Runtime/UI、Runtime/Config、Runtime/Levels。已有路径可登记例外，不能自动迁移。

**STR-03 身份与纳管**：Assets 中维护的文件及目录保留相应 .meta，Packages 的 manifest/lock 与 ProjectSettings 按项目 Git 规则纳管；Library、Temp、Logs、obj、UserSettings、构建制品、原始证据和运行存档不进入源码提交。具体证据托管按项目约定。代码移动、程序集改名和命名空间修改分别分析 MonoScript、反射与序列化影响，不因路径变化自动同时执行。

**STR-04 自包含**：通用代码以锁定包接入；项目专用工具留项目。禁止通过指向维护者 GREA 检出的符号链接才能编译。首次落地默认提供嵌入包分发，保持项目可独立恢复；未来采用 Git/包注册表时固定不可变版本或提交及内容身份，凭据由环境提供。一个包只能安装一份；升级是显式变更。

### 通用包的维护位置

自有框架源码在 GREA 的 `tools/unity/framework/packages/`，基础框架已交付 foundation、ui.ugui 和 editor 三包（校验与受限生成）；`tools/unity/templates/counter-composition/` 保存有测试的分层装配示例，也是 `grea-minimal-2d/0.1.0` 的 seed-once 源码输入。只按实际内容建目录；工程生成的实际创建/恢复范围见 [生成器与 Prefab](../../grea/references/Unity指南.md)，不先拆大量微包。

| 候选包 | 内容和依赖边界 |
| --- | --- |
| com.grea.foundation | 纯契约与最小生命周期/诊断实现；不包含项目玩法、UI 技术栈或商业服务 |
| com.grea.ui.ugui | 可选 uGUI 视图组件和无项目素材的基础 Prefab；显式依赖 foundation 与锁定 UI 包 |
| com.grea.editor | Editor 内的生成、绑定与校验；不进入 Player，不携带原包或业务适配器 |

包内按实际内容建立 Runtime、Editor、Tests、Samples~、Documentation~，附 package.json、许可证和依赖范围。包目录规则参考 [Unity Package layout](https://docs.unity3d.com/6000.0/Documentation/Manual/cus-layout.html)。项目修改放自身扩展/Variant；不能直接修改 PackageCache，也不靠复制第二份同 GUID 资产来定制。

## 类型归类表

| 内容目录 | 实际归属 |
| --- | --- |
| Prefabs | GameObject Prefab；可按 UI、角色、方块、特效分子目录 |
| Materials / Shaders | Material；Shader/HLSL/include 等实现，不能因名字含 Spine 就把 Shader 当骨骼数据 |
| Images / Sprites | Texture2D 原图、贴图；独立序列化 Sprite。一个纹理内的 Sprite 子资源不拆成重复图片 |
| Models | Mesh、导入模型及必要模型组；动画子资源随宿主文件保留 |
| Animations | AnimationClip、AnimatorController、Avatar；按类型或使用者分组 |
| Spine | 按动画组聚合骨骼、Atlas、页纹理、材质和 SkeletonData；记录运行时版本 |
| Fonts | 字体源、TMP/位图字体资产及配套材质/图集；不把所有 .asset 当配置 |
| Audio | 音乐和音效；播放键与音频来源单独登记 |
| Config | ScriptableObject、JSON、输入动作等配置 |
| Levels | 关卡数据及索引；保留文件号、显示关号、循环规则之间的映射 |

使用 Unity 实际导入类型、主/子资源和依赖判断。无法加载的 .asset 先查源 MonoScript 和序列化字段，记录推断类型与未修复状态；不能统一放入 MonoBehaviour，也不能为了分类删掉缺脚本资产。

活动工程按类型组织。来源身份、旧路径、GUID、原包/版本写在迁移清单；转换期确需区分来源和编辑副本时，可临时使用类型内的 `Source/Working` 或 `Templates/Views`；跨引擎项目交付前合并为单一原生 Prefab（见 [原生转换规范](../../grea-native-port/references/Unity原生转换规范.md)）。不恢复 `_Game/Falcon/GameTemplate/...` 的完整来源树。原始导出工程仍可完整保留在 Analysis，作为只读证据。

脚本按已存在的职责归组；同一 partial 类放在同一职责目录。Runtime、Editor、Tests 的目录名不自动建立编译隔离，需核对 asmdef、条件编译、反射与构建入口。生成工具、校验、构建分别命名，旧重生成器在新布局中应明确停用或迁移调用方。

## 动态加载与路径

- 使用 Resources 时，可按 `Content/<类型>/Resources/<原逻辑键>` 分布资产；保留 Resources 之后的相对路径。引入分散 Resources 前检查键冲突及全部调用方式。
- 既有同名 Shader/Material 可能依赖 `Resources.Load<T>` 区分。按“键＋实际加载类型”检查，并在 Unity 中验证返回对象路径；无类型、基类、LoadAll 和编辑器查找可能有歧义，不能只看类型表就判定安全。新内容优先使用无歧义键。
- 已使用 Catalog、Addressables 或 AssetBundle 的项目保留其寻址机制和地址/标签；目录规范不要求改为 Resources。
- 同步审查 AssetDatabase 路径、拼接路径、Directory.GetFiles、生成输出、构建场景、ProjectSettings 及当前文档。旧提交的 `git show <commit>:<path>` 是历史定位，不能随活动路径全局替换。
- 同名文件先查用途再决定子目录或有意义的新名；检查大小写、Unicode 和 Windows 保留名。没有证据时保留文件名，避免把按名字查找的对象改坏。

## 目录迁移完成条件

目录迁移完成条件：有逐文件旧/新路径、GUID、实际类型、理由与动态键清单；用 AssetDatabase 执行。原包套壳目录退出或有具体供应方例外，空目录清理前核对目录引用。迁移前后校验内容、meta、对象名/子资源 ID，回读类型归属及动态加载对象，再运行受影响回归、构建和代表 App 冒烟。

`unity_asset_ledger verify-moves` 可核对清单内文件的 GUID/内容/meta/Resources 相对键；全量增删与清单外变化另用 compare。工具不导入 Unity，不证明资产类型或动画正确，也不将实际内容删除计作目录整理。

目录和类型划分应由当前工程的职责、依赖与构建边界决定；迁移数量、资源名称、特殊玩法和历史验收状态不作为通用规则。
