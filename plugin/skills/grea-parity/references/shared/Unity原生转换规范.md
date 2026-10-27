<!-- 生成副本，勿直接编辑。权威来源：plugin/skills/grea-native-port/references/Unity原生转换规范.md；由 scripts/skill_closure.py 维护。 -->

# Unity · 原生转换规范

工具推荐：Unity 官方插件技能（ui-ugui、manage-sprite-atlas、unity-package-management 等）与 Unity CLI/Pipeline 生成和回读原生资源；`recovery compare_events`、`recovery compare_traces` 做规则对照。入口和限制见 工具清单（`grea-native-port` 技能《工具选择与调用》）。

适用于把 Cocos、Laya/FairyGUI、Egret、H5 等非 Unity 源游戏转换为 Unity 工程，以及审计、清理已有项目中的源引擎残留。源游戏本身是 Unity 时按 Unity 工程重建（`grea-native-port` 技能《Unity工程重建与恢复》） 执行。

## 目标形态

交付的是一个 Unity 开发者打开即可按常规方式维护的工程：

- UI、Scene、动画以原生 Prefab/Scene/AnimationClip 为制作源，正常嵌套 Prefab/Variant 合法；人工编辑直接 Play 生效，不靠来源模板/节点图与工作 View 双真源或 Capture 回写。
- 正式数值配置唯一制作源为UTF-8 JSON；Player实际解析为强类型DTO，记录输入/Schema/hash，坏配置拒绝且不静默回退。SO可维护Unity资源引用或引用JSON TextAsset，不另存重复可编辑数值，不能只在Editor转SO后让Player读取另一份表。资源绑定用稳定ID，不依赖行序。
- 运行时只使用 Unity 生命周期、uGUI/TMP 等原生组件和下文选型基线中的官方或主流插件。
- 类型、资源和节点按游戏语义命名（`ShopView`、`RuneSlot`、`DailySignTable`）。来源映射保留在 Analysis；原有领域名称、存档兼容 ID、Unity GUID 和合法第三方数据不因拼写相同而违规，判断依据是运行机制与实际调用者。
- 源引擎只作为**行为与资源的来源**，不作为运行时模型。

## 规则语义与引擎语义

核心原则：**保留原版的规则语义，不保留原版的引擎语义。**

| 类别 | 内容 | 实现与验证 |
| --- | --- | --- |
| 必须对齐：规则语义 | 数值公式与舍入、RNG 序列与消费顺序、结算/消耗/奖励顺序、任务与解锁条件、影响结果的玩法时序、存档键与兼容 | 在 Domain/Gameplay 用强类型 C# 实现；以原代码或原版轨迹为 oracle 做对照测试，见 规则与随机（`grea-native-port` 技能《规则与随机一致性》） |
| 必须对齐：可观察结果 | 布局结果、文字外观、动画曲线与节奏、按钮反馈、遮罩形状、声音时机 | 用 Unity 原生组件配置得到相同结果；以同状态截图、录像和关键帧对照，不复刻源算法 |
| 不复刻：引擎语义 | 节点树与节点身份、组件生命周期与执行顺序、Widget/Layout/Label 度量算法、Mask 命中算法、director/Scheduler/Promise 微任务、Tween/Action 系统、资源 uuid/bundle 体系、场景切换与常驻节点、事件捕获/冒泡实现、源脚本类名 | 换成对应的 Unity 原生机制，见 [Cocos 映射](Unity源引擎映射-Cocos.md) |

当规则结果确实依赖某个执行顺序（例如同帧内先结算后刷新），在 Gameplay 中把这个顺序写成显式调用，而不是复刻整个源帧循环。

原生组件配置无法得到某个视觉结果时（例如反向圆形遮罩），可以写一个用途明确的小型 Unity 组件（如 `InvertedCircleMask`）。它按 Unity 惯例实现，不模拟源引擎组件；同时在项目 `Docs/PROJECT-STRUCTURE.md` 登记原因、替代方案和验证方法。

## 技术选型基线

一个项目对每项只选一种实现，记录版本、许可证及 IL2CPP/目标平台验证情况。新装包按工作区约定备份。可以使用 Unity 官方插件技能完成对应操作。

| 方面 | 默认 | 可选或条件 |
| --- | --- | --- |
| UI | uGUI + TextMeshPro | 用户明确要求时使用 UI Toolkit |
| 布局 | RectTransform 锚点与偏移；Horizontal/Vertical/GridLayoutGroup、ContentSizeFitter | — |
| 图片与图集 | TextureImporter Sprite（Single/Multiple）+ SpriteAtlas v2 | — |
| 动画 | AnimationClip + Animator，或用于简单播放的 Animation 组件 | 序列演出用 Timeline |
| 补间 | DOTween 或 PrimeTween，项目内只选一个 | — |
| 异步与定时 | `Awaitable`、Coroutine，配合 `destroyCancellationToken` 取消 | 项目已用时可选 UniTask |
| 资源加载 | 直接序列化引用 | 动态或大量资源用 Addressables，使用语义地址；不用 `Resources` 存放目录式 Catalog |
| 场景 | Boot 加内容场景，用 SceneManager 切换；常驻对象 `DontDestroyOnLoad` | 需要叠加时用 Additive |
| 配置 | 强类型字段/DTO 与原生序列化资产 | 正式JSON唯一制作源，Player读取强类型DTO；SO只管理资源/JSON引用，消费者不运行源引擎配置解析器 |
| 输入 | Input System + EventSystem（`InputSystemUIInputModule`）；指针用 `IPointer*Handler` | — |
| 对象池 | `UnityEngine.Pool.ObjectPool<T>`，带显式复位 | — |
| 音频 | AudioSource + AudioMixer，由音频服务管理 | — |
| 骨骼动画 | 与数据版本匹配的 spine-unity（UI 用 SkeletonGraphic，场景用 SkeletonAnimation）或 DragonBones Unity 运行时 | — |
| 本地化 | 单语言直接使用资源 | 多语言用 com.unity.localization |
| 依赖装配 | 序列化引用加构造参数 | 组合根膨胀时用 VContainer |
| 存档 | 存档端口 + JSON（com.unity.nuget.newtonsoft-json）文件存储 | 原版键与编码兼容由适配器负责 |

主流插件能满足的需求直接使用主流插件。GREA 自有的通用框架包只作为薄胶水，每项能力在项目中只保留一种实现；各 GREA 组件对应的主流方案与选择规则见 自研框架与主流插件的关系（`grea-native-port` 技能《Unity通用组件与Prefab》）。新装包的许可证登记见 许可证与再分发（`grea-native-port` 技能《许可证与再分发》）。

## 来源迁移器与日常制作流水线

- 源引擎迁移器（源布局烘焙、源动画转换、首次配置切换、源 Sprite 切图）放在项目 `Tools/`，或 `Assets/Game/Editor/Conversion/` 这类一次性目录。转换器输入源数据，输出原生资产，通过 AssetDatabase/PrefabUtility 写入。
- 源引擎迁移完成后，生产程序集、Prefab 和场景不依赖该迁移器；移除它后，已有原生资产仍能编译、运行和构建。日常 Excel/JSON 导表、Unity Importer 等制作工具可以长期维护，采用明确的唯一制作源、生成所有权和回读校验，不解释源引擎节点图。
- 再次运行转换器只输出候选（写到 `Library/` 或独立目录），检测到人工修改就拒绝覆盖。Build 校验和打包已有资源，不重新运行来源迁移器；日常制作工具的生成策略由项目声明，人工编辑冲突必须保留。
- 源 uuid 到 Unity GUID 与路径、源名到语义名的映射表，以及转换器未覆盖的特性清单，都保存在 Analysis。
- 不建立通用万能转换器。只覆盖本项目实际用到的源组件，未支持项报错。

## 禁止项与守卫

以下内容不得出现在交付的生产工程（`Assets/` 中的运行程序集、Prefab、场景和资源）中：

1. 用源引擎类型、uuid、脚本名作运行时类型分发、节点身份或资源调度的兼容机制。扫描这些拼写只能生成审查线索；正常领域名、存档 ID、Spine JSON、有限业务 Tick 以及 Unity GUID 不因名称相似而禁止。改名后的源引擎解释器仍属违规。
2. 为保存源节点身份而挂在 Prefab 上的组件（如 SourceIdentity、SourceWidget、SourceBehaviour），以及运行时依据数据描述构建或改写 UI 树的 ViewDefinition 一类结构。
3. 按节点索引、uuid 或字符串路径绑定事件或控件；控件统一用 `[SerializeField]` 引用。
4. 为解释源引擎协议而自研的 director、帧循环参与者注册、调度器、微任务队列、Tween/Action 系统、Widget/Layout 布局算法、Label 度量算法，用来替代 Unity 已有能力。有限业务完成 FIFO 若不解释源节点、生命周期或帧阶段协议，且有明确线程、作用域退出、受限推进及重入边界，可按业务服务审查；不得仅按名称放行或封禁。核对实际结构与投递、推进、销毁消费者，移除线程/清空/退出边界或加入源调度协议的反例仍须拒绝。
5. 将任意 `key + json` 行或完整源对象图塞入 ScriptableObject，并继续在 Player 中动态解释为生产规则。合法强类型 DTO 的 JSON 序列化、文本字段和第三方标准数据不在此列。
6. 交付后仍有 Templates/Views 双层 UI 真源，或需要 Capture、回写流程。
7. 源引擎运行时源码，或带源引擎许可证限制的文件（例如 Cocos Creator 的 easing 实现及其许可证文件头）。替代做法、原游戏素材范围与第三方包登记见 许可证与再分发（`grea-native-port` 技能《许可证与再分发》）。

守卫做成 EditMode 测试或 Validator。构建前检查生产编译集合、实际根资产与引用；Editor 已加载的对照类型只作为待审候选，不能冒充实际 Player 类型阻断或放行。对本次交付支持的后端，构建后必须核对实际 Player 载荷与禁止项；缺少该层证据不能宣称最终退出通过。普通与 Development 构建可能走不同守卫、裁剪和宏分支，结论绑定实际构建配置。已有项目的过渡机制登记负责人、调用链、退出条件与阶段。`migration_no_regression` 检查没有新增或扩大依赖；它只允许继续迁移，不代表 `final_native_exit` 已通过。最终退出要求相关机制从实际 Player 编译集合、资产闭包与载荷中退出，不能靠白名单豁免。守卫扫描范围、白名单和结果记录在项目验收中。

## 平台 SDK

微信 `wx.*`、抖音 `tt.*` 等平台 API 映射为 Gameplay 中声明的平台端口（广告、支付、登录、分享、排行榜、振动、剪贴板等），由 Services 实现。

- 没有真实服务时返回 Unavailable。
- 用户明确授权的离线替代（如广告点击即成功）单独实现并标明，不计为真实服务成功。
- 资格、限额和奖励事务保留在业务层，不写在平台适配里。

## 流程

1. **盘点**：确认源引擎与格式版本、可达功能清单和原版证据（见 取证（`grea-native-port` 技能《原版运行与内容取证》））。已有项目先统计源引擎残留，并加上守卫。
2. **代表切片**：选一个同时包含图片、文字、遮罩、列表、按钮和动画的页面，加一条玩法流程，完整走一遍：转换、原生 Prefab、View 脚本、Presenter、Domain 规则、对照。通过后再批量推进。
3. **按模块转换**：转换器生成原生资产，然后人工补 View 与绑定；规则移入 Domain 并补 oracle 测试；视觉按截图对照。
4. **退役**：删除转换期的过渡组件和双层资产，收紧白名单。
5. **验收**：按下一节的三道门分别报告。

## 验收三门

| 门 | 通过条件 |
| --- | --- |
| 守卫 | 最终 `final_native_exit` 无未退出的源引擎运行机制；过渡期 `migration_no_regression` 单列，不能替代最终门。源码扫描、Editor 回读和实际 Player 载荷分别核验 |
| 原版对照 | 规则 oracle 测试通过；同状态截图、录像和关键帧对照通过；真实输入通过。分层记录方式见 分层验收（`grea-native-port` 技能《测试与结果交付》） |
| 原生可维护 | 人工维护的 UI/Scene/动画及选择 SO 制作的配置可直接编辑/Play；外部配置源走明确单向候选流程，不能重建源对象图；实际界面可编辑可见，移除转换器后仍编译/构建 |

三道门分别报告；任何一道不通过都不能称为原生转换完成。构建成功、测试数量或旧解释器已移除，都不能替代原生可维护门。
