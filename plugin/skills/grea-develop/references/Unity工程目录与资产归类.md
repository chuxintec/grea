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

单模块 Counter 示例省略层内 `<模块>` 子目录；多模块按上述层内目录划分。其生成专属 Prefab、URP 和 BootstrapConfig 位于 `Assets/GreaGenerated/`，项目业务 seed-once 代码位于 `Assets/Game/<Layer>/`。这是本标准认可的最小配方布局，不要求添加 Runtime 包裹层；既有工程先审计再按获批范围受控迁移；不为符合树形图直接搬迁，也不以历史工程为由整体豁免。

**STR-01 所有权**：Game 只保存该项目的运行与编辑必需内容。第三方代码、通用框架和项目业务分别维护；不能把原导出树换一个 Recovered/Original 名称后直接当成标准化结果。原始导出完整保留在 Analysis，只读证据不进入生成覆盖范围。

**STR-02 职责唯一**：新内容统一用 Game/Editor，不另建第二个日常 Editor 入口。UI 代码归 Presentation 下实际模块；输入设备实现归 Services/Input，输入到业务命令的转换归 Presentation。配置数据归 Content/Config，解析/校验代码归消费它的模块；不再并列含义重叠的 Runtime/UI、Runtime/Config、Runtime/Levels。已有路径先登记差额并规划迁移；只有具体兼容约束才可逐项登记例外，不能以“历史沿用”免除整改。

**STR-03 身份与纳管**：Assets 中维护的文件及目录保留相应 .meta，Packages 的 manifest/lock 与 ProjectSettings 按项目 Git 规则纳管；Library、Temp、Logs、obj、UserSettings、构建制品、原始证据和运行存档不进入源码提交。具体证据托管按项目约定。代码移动、程序集改名和命名空间修改分别分析 MonoScript、反射与序列化影响，不因路径变化自动同时执行。

**STR-04 自包含**：通用代码以锁定包接入；项目专用工具留项目。禁止通过指向维护者 GREA 检出的符号链接才能编译。首次落地默认提供嵌入包分发，保持项目可独立恢复；未来采用 Git/包注册表时固定不可变版本或提交及内容身份，凭据由环境提供。一个包只能安装一份；升级是显式变更。

### 通用包的维护位置

自有框架源码在 GREA 的 `tools/unity/framework/packages/`，基础框架已交付 foundation、ui.ugui 和 editor 三包（校验与受限生成）；`tools/unity/templates/counter-composition/` 保存有测试的分层装配示例，也是 `grea-minimal-2d/0.1.0` 的 seed-once 源码输入。只按实际内容建目录；工程生成的实际创建/恢复范围见 生成器与 Prefab（[Unity工程工具与生成](Unity工程工具与生成.md)），不先拆大量微包。

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
| Images | 导入主资产为纹理的文件（含 Texture2D、Sprite 模式纹理及其 Sprite 子资源）；统一目录名为 Images，Textures 是需受控迁移的旧路径，不是并列合法别名 |
| Sprites | 独立序列化、主资产为 Sprite 的文件；纹理内的 Sprite 子资源随宿主 Images 文件保留，不能拆成重复图片 |
| Models | Mesh、导入模型及必要模型组；动画子资源随宿主文件保留 |
| Animations | AnimationClip、AnimatorController、Avatar；按类型或使用者分组 |
| Spine | 按动画组聚合骨骼、Atlas、页纹理、材质和 SkeletonData；记录运行时版本 |
| Fonts | 字体源、TMP/位图字体资产及配套材质/图集；不把所有 .asset 当配置 |
| Audio | 音乐和音效；播放键与音频来源单独登记 |
| Config | 正式数值与资源引用分工见[DAT-01](Unity程序集分层与生命周期.md#生命周期与数据契约)；输入动作按其工具契约维护 |
| Levels | 关卡数据及索引；保留文件号、显示关号、循环规则之间的映射 |

**STR-05 唯一类型映射**：上表为类型目录唯一维护入口；正式场景统一 `Game/Scenes`，不使用 `Content/Scenes`。数值关卡初值属于 `Content/Config/<模块>` 的正式 JSON，`Levels` 只保存非重复数值表的关卡布局/索引资产。Spine、Fonts 是表内明确的复合资源组：其配套页纹理/材质随组保留且登记依赖，不能任意按用途发明新的混合类型目录。先判断受维护的复合组，再按主资产实际类型归类；未知类型列为 unknown 并查证，不按扩展名强行判定。

使用 Unity 实际导入类型、主/子资源和依赖判断。无法加载的 .asset 先查源 MonoScript 和序列化字段，记录推断类型与未修复状态；不能统一放入 MonoBehaviour，也不能为了分类删掉缺脚本资产。

活动工程按类型组织。来源身份、旧路径、GUID、原包/版本写在迁移清单；转换期确需区分来源和编辑副本时，可临时使用类型内的 `Source/Working` 或 `Templates/Views`；跨引擎项目交付前合并为单一原生 Prefab（见 [原生转换规范](../../grea-recover/references/Unity原生转换规范.md)）。不恢复 `_Game/Falcon/GameTemplate/...` 的完整来源树。原始导出工程仍可完整保留在 Analysis，作为只读证据。

脚本按已存在的职责归组；同一 partial 类放在同一职责目录。Runtime、Editor、Tests 的目录名不自动建立编译隔离，需核对 asmdef、条件编译、反射与构建入口。生成工具、校验、构建分别命名，旧重生成器在新布局中应明确停用或迁移调用方。

## 恢复脚本与严格目录例外

Unity 来源脚本可保留 `Game/Scripts/<Assembly>/<Namespace>`，同时记录原程序集、完整类型名、MonoScript GUID及引用。新业务代码按 Bootstrap、Domain、Gameplay、Presentation、Services 归属，Diagnostics 只处理诊断；不能复制恢复类到业务层形成第二份类型，也不能为五层外观批量重命名原程序集/命名空间。路径迁移与编译身份变化分开计划、分别验证。

Product、SourceRecovery、_Recovery 和编号修复副本不能作为长期正式业务/运行资产根。源包、恢复二进制、未知/不可编译 Shader 留活动 Assets 外的 Analysis/Evidence；迁移时记录来源映射与构建依赖，不能直接删除被引用资源。第三方和 Unity 固定入口按其实际约定保留。

**STR-06 有界例外**：仅为真实引擎入口、第三方布局或已证明的序列化/反射兼容约束登记。记录具体规则、最小路径范围、原因、替代约束、验证证据、负责人和复审触发；“旧工程”“保留 Product 全树”不能作为理由。例外不等于验证通过，动态加载无法证明时保留 unknown。

项目 `grea-project.json` 继续使用现行 `grea-unity-project/1.0.0` 配置合同：`paths.unityProject/evidenceRoot/buildRoot`、`toolchain`、`dependencyLock`、`scenes.bootstrap/entry` 等字段按现行 Schema 填写；设计尺寸、额外构建场景及结构映射写 `Docs/PROJECT-STRUCTURE.md`，不能向禁止额外属性的配置强塞字段。

现行配置的 `exceptions[]` 字段仍是 `ruleId/scope/reason/alternative/verification/owner/reviewTrigger`，其中 scope 为原合同的范围说明字符串。beaver 新结构审计候选采用独立输入，不改写该接口；以下是双方对接的字段合同，CLI 及实际能力仍待固定候选验收：

```json
{
  "schemaVersion": 1,
  "exceptions": [{
    "path": "Assets/Plugins/NativeBridge",
    "scope": "subtree",
    "ruleId": "STR-02",
    "reason": "平台插件导入要求该目录",
    "alternativeConstraint": "仅允许已登记供应方插件，不容纳业务代码",
    "validation": "项目内插件清单、哈希及原生导入回执路径",
    "owner": "项目维护者",
    "reviewTrigger": "供应方版本或目标平台变化"
  }]
}
```

`path` 是相对 Unity 工程的可移植路径，不含绝对路径或 `..`；`scope` 仅为 `path` 或 `subtree`，路径唯一，其余字段非空。转换旧配置时必须人工核准具体 path 和 scope，`alternative→alternativeConstraint`、`verification→validation`；不能把自由文本 scope 猜成子树授权。尚无已验自动转换器，使用独立显式输入并与项目文档核对。例外匹配按规则和范围共同判断；规则不符不能豁免其他问题。

## 动态加载与路径

- 使用 Resources 时，可按 `Content/<类型>/Resources/<原逻辑键>` 分布资产；保留 Resources 之后的相对路径。引入分散 Resources 前检查键冲突及全部调用方式。
- 既有同名 Shader/Material 可能依赖 `Resources.Load<T>` 区分。按“键＋实际加载类型”检查，并在 Unity 中验证返回对象路径；无类型、基类、LoadAll 和编辑器查找可能有歧义，不能只看类型表就判定安全。新内容优先使用无歧义键。
- 已使用 Catalog、Addressables 或 AssetBundle 的项目保留其寻址机制和地址/标签；目录规范不要求改为 Resources。
- 同步审查 AssetDatabase 路径、拼接路径、Directory.GetFiles、生成输出、构建场景、ProjectSettings 及当前文档。旧提交的 `git show <commit>:<path>` 是历史定位，不能随活动路径全局替换。
- 同名文件先查用途再决定子目录或有意义的新名；检查大小写、Unicode 和 Windows 保留名。没有证据时保留文件名，避免把按名字查找的对象改坏。

## 目录迁移完成条件

本节定义资产归类目标；既有工程不因目标目录树自动搬迁。实际迁移前的行为/身份冻结、逐文件清单、备份、AssetDatabase 操作、失败恢复和Editor回读统一按[重构与资源迁移](Unity重构与资源迁移.md)执行，避免两篇维护不同的搬迁步骤。完成时至少有逐文件旧/新路径、GUID、实际类型、理由与动态键清单，并通过受影响回归、构建及代表入口验收。

若使用 `unity_asset_ledger verify-moves`，它仅核对清单内 GUID/内容/meta/Resources 相对键；全量增删与清单外变化另用 compare。工具不导入 Unity，不证明资产类型或动画正确，也不将实际内容删除计作目录整理。

目录和类型划分应由当前工程的职责、依赖与构建边界决定；迁移数量、资源名称、特殊玩法和历史验收状态不作为通用规则。
