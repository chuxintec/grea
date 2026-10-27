# Unity · 通用组件与 Prefab

> **何时读**：选择或新增通用组件（作用域、页面/弹窗、按钮、列表、音频、资源、存档、诊断），判断该用 GREA 自研框架还是主流插件，或设计基础 Prefab、Variant 与绑定契约时。
> **读完产出**：组件选型记录（每项能力一种实现，含版本与许可证）、组件准入清单、Prefab 绑定契约与 Variant 所有权说明。

本篇属于 [工程标准 v1](Unity工程结构与开发规范.md)（`grea-unity-project` 1.0.0）。脚本与生成所有权见 [脚本与生成契约](Unity脚本与生成契约.md)。

## 通用组件

以下是 v1 候选能力及准入契约；实际已实现类型见 基础框架包说明（项目文档 `docs/Unity指南.md`），例如 LifetimeScope/ServiceScope、CommandButton/ButtonPressFeedback/ModalPanel/ScreenHost、Catalog 句柄、AudioPlayer、FileSaveStore 和 DiagnosticBuffer。候选名不保证有同名类；池化/列表/异步资源后端/复杂导航仍为计划项，不生成空类。

| 能力与候选类型 | 输入/所有权 | 输出、故障与最低验收 |
| --- | --- | --- |
| 作用域与生命周期（AppScope、SessionScope） | 父作用域、显式依赖、初始化顺序 | Ready/失败状态；重复启动不增实例；失败逆序清理；退出无活跃子任务 |
| 页面与弹窗（ScreenHost、ModalHost） | 视图工厂、作用域、导航/遮罩策略 | 打开/关闭结果；重入、排队/替换策略显式；关闭后不接收旧响应；焦点正确恢复 |
| 交互反馈（ButtonFeedback） | 按下/释放/禁用状态与反馈配置 | 只负责表现；重复绑定一次输入只发一次请求；拖出、取消、失焦不伪造点击 |
| 列表与复用（ItemView、PoolLease） | 展示数据、租约、回收回调 | 无旧文本、旧图片或残留订阅；快速滚动/异步图片晚到不污染新数据；重复归还被识别 |
| 音频（AudioHandle、音频端口适配器） | clip/key、分组、作用域、暂停策略 | 可停止句柄；切关、静音、失焦/恢复按配置；无悬挂播放，不直接奖励或改状态 |
| 资源（AssetHandle、ViewFactory） | 稳定 key、类型、加载后端、调用作用域 | 明确未找到/类型错/已取消；共享引用计数与释放责任可追踪；业务不硬编码提供方路径 |
| 存档（SaveStore 端口与适配器） | schema、slot、QA namespace、领域快照 | 保存/加载/迁移结果；损坏和断电分支；业务存档语义保持；不把默认值静默覆盖旧档 |
| 诊断（DiagnosticSink、StateSnapshot） | 模块、操作身份、结构化事件 | 有界日志与可导出快照；关键信息包含 buildId、场景/会话、模块、operationId、资源 key；默认脱敏 |
| 输入/平台适配 | 选定设备、平台能力与授权 | 原生能力与离线替身分开；缺能力给原因，不伪造广告、支付、排行榜成功 |

**CMP-01 组件准入**：每个组件具备职责、前提、依赖、序列化字段、生命周期、错误契约、测试、最小示例和许可证。跨项目复用至少经过两个不同结构的隔离输入/示例验证；只有一处业务实现时保留候选状态。组件名称相同不代表行为契约相同。

**CMP-02 可替换性**：通用契约不携带某游戏关卡/技能/货币常量，也不依赖项目目录、固定场景对象名或 Find 全场搜索。缺少必需依赖在初始化/验证阶段报出具体字段与对象；不创建隐式全局默认实例掩盖装配错误。

**CMP-03 诊断预算**：开发日志记录事件顺序、失败点和状态摘要；生产默认关闭高频明细。每类日志/快照定义条数、字节上限与采样策略；不能无限增长或附带账号、完整存档和资源原文。重复错误聚合保留首次原因和次数。性能预算由项目的设备、场景和基线确定，不给所有项目编造统一帧率或内存承诺。

## 自研框架与主流插件的关系

GREA 的 `com.grea.*` 包（foundation、ui.ugui、editor）是**薄胶水**：把 Unity 原生机制或主流插件接到工程标准的端口和生命周期契约上。它不是另一套运行时框架。跨引擎项目的选型以 [原生转换规范的技术选型基线](../../grea-native-port/references/Unity原生转换规范.md#技术选型基线) 为准；本节说明 GREA 组件在其中的位置。

| 能力 | 主流或原生方案 | GREA 组件的定位 | 选择规则 |
| --- | --- | --- | --- |
| 依赖装配与作用域 | 构造参数与序列化引用；VContainer | `LifetimeScope`、`ServiceScope`：代次、逆序释放、启动失败清理 | 组合根较小时用 GREA 作用域；组合根膨胀改用 VContainer，二者不并存 |
| 页面与弹窗 | uGUI Canvas、Prefab、项目已有 UI 框架 | `ScreenHost`、`ModalPanel`：单页面替换、单弹窗生命周期与焦点恢复；未实现排队或模态栈 | 项目已有 UI 框架时沿用它；UI Toolkit 项目不使用 |
| 按钮命令 | uGUI `Button.onClick` | `CommandButton`：异步命令的防重入、隐藏取消与重绑 | 同步点击直接用 `Button`；需要防重入的异步命令再用 |
| 资源寻址 | 直接序列化引用；Addressables | `AssetCatalog`：对显式引用集合的句柄与计数 | 少量静态资源用序列化引用或 Catalog；动态或大量资源用 Addressables，项目内只保留一种寻址机制 |
| 音频 | AudioSource + AudioMixer | `AudioPlayer`：可停止句柄、作用域退出清理 | 混音、分组和参数始终在 AudioMixer |
| 存档 | 存档端口 + JSON（com.unity.nuget.newtonsoft-json） | `FileSaveStore`：临时写入、备份、`Recover()` | 作为存档端口的文件适配器；原版键与编码兼容由项目适配器负责 |
| 诊断 | `Debug.Log`、Unity Logging | `DiagnosticBuffer`：有界结构化事件 | 只做有界缓冲与导出，日志输出仍走 Unity |
| 补间 | DOTween 或 PrimeTween | 不提供 | 直接使用所选插件 |
| 异步与定时 | `Awaitable`、Coroutine；UniTask | 不提供 | 直接使用，配合 `destroyCancellationToken` |
| 对象池 | `UnityEngine.Pool.ObjectPool<T>` | 不提供（列表复用仍是计划项） | 直接使用，复位写在 `actionOnGet`/`actionOnRelease` |
| 输入 | Input System + EventSystem | 不提供 | 直接使用 |

**新增 GREA 组件的判断步骤**：

1. 列出需求和候选的 Unity 官方功能、主流插件。能满足需求时直接使用，记录版本与许可证。
2. 只有缺口是"把现成方案接到工程标准端口或生命周期"时，才写 GREA 组件；组件只包含这层接缝。
3. 新组件通过 CMP-01 准入，并在 基础框架包说明（项目文档 `docs/Unity指南.md`） 登记它对应的主流方案。
4. 同一项目中，每项能力只保留一种实现：采用主流方案后，相应 GREA 组件不再挂载或装配。

已实现组件的行为约定：存档恢复由应用显式调用 `FileSaveStore.Recover()`，校验通过的 pending 优先提交，损坏副本隔离保留，主档损坏时从有效 backup 恢复，没有有效副本时拒绝覆盖；`CommandButton` 隐藏时取消当前绑定与旧操作，重新显示时只为仍存活的 owner 恢复绑定，显式 Unbind 或 owner 退出后保持解绑。

有限按压使用 `ButtonPressFeedback`，明确引用独立视觉子节点，点击区域保持稳定；业务仍由 Unity Button/CommandButton 拥有。退出、拖动、失焦、禁用应取消表现，其他指针不能释放当前按压；不将源引擎 Tween/输入缓存搬成通用框架。命令临时不可交互时保留原导航选择；完成不抢回用户或新弹窗已经取得的焦点。接口事件测试、操作系统键盘和鼠标分别验收，不能互相替代。

基础包与两个自有不同结构消费者的当前实现和版本见 框架说明（项目文档 `docs/Unity指南.md`），实证边界见 提炼验收（GREA 安装目录 `validation/releases/2026-10-16-unity-framework-extraction.json`）。合成战斗/拼图通过不能推出原游戏完整一致性、其他输入后端或其他平台已通过；品类玩法仍归各项目 Domain/Gameplay。

## 通用 Prefab

**PFB-01 归属**：包内基础 Prefab 仅使用自有/可分发内容；项目 Variant 和业务 Prefab 位于 Content/Prefabs/<模块>。源游戏是 Unity 时，原包 Prefab 优先保留并适配；跨引擎时，源对象树是转换输入，重建为原生 Prefab 并按视觉/交互结果对照，不在生产保留源节点身份或源运行时语义。两种情况都不能强制换成通用壳后声称原版一致。组件复用不授权公开原游戏素材。

| 候选基础 Prefab | 节点/组件契约 | 定制入口与必验项 |
| --- | --- | --- |
| UIHost（仅 uGUI 配置） | Canvas、缩放/安全区入口、页面层、弹窗层、提示层；EventSystem 由场景契约统一拥有 | 层级与排序可配置；不重复生成 EventSystem；无效分辨率/安全区提示明确；UI Toolkit 项目不生成它 |
| ModalShell | Root、交互遮罩、内容插槽、可选标题/关闭入口；引用通过序列化绑定 | 内容通过 Variant/组合提供；多弹窗输入阻断、返回键、重复打开与退出取消按契约 |
| ButtonShell | 可交互组件、视觉状态、可选音效/图标/文字槽位 | 反馈与业务回调分离；禁用、按下拖出、键盘/手柄导航按启用平台验证 |
| ListItemShell | 数据绑定组件、内容槽位、租约清理入口 | 刷新前清理前次数据；复用/异步加载/尺寸变化后无旧引用 |
| LoadingOverlay / ToastView | 内容与生命周期适配，不持有业务会话 | 超时/取消/异常后可退出；提示不消费玩法输入，除非显式配置 |

**PFB-02 绑定契约**：记录 prefabId、contractVersion、组件类型、必需字段、稳定节点标识、可选插槽、依赖、层/排序、激活状态、绑定阶段和允许覆盖项。显示名与业务 key 分开；节点重命名不应靠字符串路径悄悄改变绑定。校验器需定位 Prefab、组件、字段与预期类型。

**PFB-03 变体与生成**：基础生成资产和人工修改分离；有需要时用 Generated 与 Variants 子目录。生成器只更新自己拥有的字段/文件；没有字段级所有权实现时，整个被人工改动的资产均视为冲突。根/插槽结构变更必须检查所有受影响 Variant。Unity Variant 继承基础资产并保存覆盖，但不保证任意基础结构变更都安全，见 [官方 Prefab Variants](https://docs.unity3d.com/6000.0/Documentation/Manual/PrefabVariants.html)。

**PFB-04 引用与验收**：通过 Editor 的 AssetDatabase/PrefabUtility 创建、移动与绑定，保留 .meta、GUID 和需要稳定的局部 fileID。不能在活工程外部拼 YAML 或手写随机 GUID 来修复引用。必须验证 Missing Script、空引用、材质/字体/图集、Canvas/Camera/排序，以及实例化→显示→关闭→再次显示→销毁的真实生命周期；静态合法不代表最终画面正确。


**PFB-04 安全区与输入边界**：安全区与窗口矩形必须先统一坐标原点和像素单位；公共布局先求交再归一化，非法/非有限/无交集不得写坏旧布局。平台逻辑像素、物理像素和左上角原点转换放在平台适配器。弹窗遮罩只阻挡射线，不自动构成键盘模态边界；只有关闭按钮的壳不自动导航到背景，项目为实际内容按钮配置显式内部导航，或采用已有 UI 框架的等价策略。长文本、人工改色/尺寸、保存重开和再生成拒绝覆盖均需按实际启用能力验收。
