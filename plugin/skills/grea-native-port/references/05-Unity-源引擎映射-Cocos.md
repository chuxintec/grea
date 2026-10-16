# Unity · 源引擎映射：Cocos Creator

用于 Cocos Creator 2.x（主要按 2.4 发布包整理）到 Unity 原生实现的一次性转换。3.x 的差异见文末。

每一行给出三项：Unity 目标、转换方法、需要对照的结果。表中"对照"指截图、录像、关键帧或规则测试，用来确认 Unity 实现得到相同结果，**不是**在 Unity 中复刻该 Cocos 机制的理由；总原则见 [原生转换规范](05-Unity-原生转换规范.md)。

具体常量（尺寸、时长、曲线）都从当前包读取。源格式字段名和默认值以实际包的版本为准；本表未覆盖的组件先列入转换缺口清单。

## 场景、节点与坐标

| Cocos | Unity 目标 | 转换方法 | 对照 |
| --- | --- | --- | --- |
| Scene（.fire）、Canvas、设计分辨率 | Unity Scene；Canvas + CanvasScaler（Scale With Screen Size） | reference resolution 取设计分辨率。fitWidth 对应 match=0，fitHeight 对应 match=1；两者都开（SHOW_ALL）用 Expand，都不开（NO_BORDER）用 Shrink | 多个窗口比例下的整屏截图 |
| cc.Node（UI） | GameObject + RectTransform | anchorMin = anchorMax = 父节点 anchorPoint；pivot = 本节点 anchorPoint；anchoredPosition = (x, y)；sizeDelta = (width, height)。Cocos 的位置相对父节点锚点，这样设置后数值可以直接沿用 | 静态布局截图；父节点尺寸变化后的布局 |
| angle / rotation | localEulerAngles.z | 2.x 的 `angle` 逆时针为正，与 Unity 相同；已废弃的 `rotation` 顺时针为正，取反 | 旋转动画的关键帧 |
| scale（含负值翻转） | localScale | 直接映射 | — |
| opacity | 影响子节点时用 CanvasGroup.alpha；只影响自身时用 Graphic.color.a | 按源版本确认 opacity 是否级联；color 只作用于自身渲染组件 | 半透明父子叠加截图 |
| zIndex、siblingIndex | 同级顺序（sibling order） | 静态顺序在转换时烘焙；运行时调整由 View 调用 SetSiblingIndex | 遮挡顺序截图 |
| skew | 无原生对应 | 列入例外：改用美术资源或小型网格组件 | — |
| group 与碰撞分组、Camera cullingMask | Layer、Camera.cullingMask | 分组表转换为 Layer 表 | — |

## 布局与 UI 组件

| Cocos | Unity 目标 | 转换方法 | 对照 |
| --- | --- | --- | --- |
| cc.Widget | RectTransform 锚点与偏移 | 按 alignFlags 和边距（absolute 或百分比）烘焙 anchorMin/anchorMax/offset。alignMode 无需映射，锚点始终生效。target 不是父节点时调整层级，使目标成为父节点 | 改变窗口比例后的贴边与拉伸 |
| cc.Layout | Horizontal/Vertical/GridLayoutGroup + ContentSizeFitter | 映射 spacing、padding、方向、startAxis；resizeMode CONTAINER 用 ContentSizeFitter，CHILDREN 用 childControlSize | 子项数量变化后的排布 |
| cc.Sprite type | Image.type | SIMPLE→Simple；SLICED→Sliced（border 写入 Sprite）；TILED→Tiled；FILLED→Filled | — |
| Sprite FILLED 参数 | Image.fillMethod / fillOrigin / fillAmount / fillClockwise | HORIZONTAL/VERTICAL/RADIAL 对应 Horizontal/Vertical/Radial360；fillStart 对应 origin；fillRange 的符号对应方向 | 0%、50%、100% 截图 |
| Sprite sizeMode（CUSTOM/TRIMMED/RAW）与 trim | sizeDelta 加 Sprite 导入 rect、pivot | 转换时算出最终显示尺寸和偏移，烘焙到 sizeDelta 和位置。需要 RAW 时用原图尺寸，需要 trim 偏移时设置 Sprite pivot | 用原图、裁切、作者尺寸互不相同的夹具；还要测运行时换图 |
| SpriteFrame、图集（plist） | TextureImporter Multiple 切图或独立图，再打 SpriteAtlas v2 | 转换器还原旋转帧并写入 rect、border、pivot；按界面或模块建图集；资源按用途命名 | 清晰度、九宫格边缘 |
| cc.Label | TextMeshProUGUI | fontSize 直接映射。lineHeight 是绝对行距，按字体度量换算成 TMP lineSpacing。overflow：NONE 用不换行 + ContentSizeFitter；CLAMP 用 Truncate/Masking；SHRINK 用 Auto Size（最大值取原字号）；RESIZE_HEIGHT 用换行 + 垂直 ContentSizeFitter | 多行、长文本、空格、数字跳动截图 |
| LabelOutline、LabelShadow | TMP 材质预设（Outline / Underlay） | 每种样式一份材质预设，不按标签逐个复制 | 描边宽度与颜色 |
| BitmapFont（.fnt） | TMP Font Asset 或 TMP Sprite Asset | 由字形图集生成，保留 advance、基线、行高 | 伤害数字等位图字对照 |
| cc.RichText | TMP 富文本 | 转换器改写标签：color、size、b、i、u 直接对应；`<img>` 用 TMP Sprite Asset 的 `<sprite name=…>`；outline 用材质 | 混排截图 |
| cc.EditBox | TMP_InputField | maxLength→characterLimit；inputMode→contentType；单行/多行→lineType；placeholder 换成 TMP 文本 | IME、长度限制、提交 |
| cc.Mask | RECT 用 RectMask2D；ELLIPSE 用 Mask + 圆形 Image；IMAGE_STENCIL 用 Mask + 带 alpha 的 Image | inverted（反向）没有原生对应，按例外写一个用途明确的小组件或 Shader | 遮罩边缘；点击命中区域 |
| cc.BlockInputEvents | 全屏 Image（raycastTarget 开启、alpha 为 0） | — | 弹窗下层不可点 |
| cc.Button | Button（Selectable） | transition 映射：NONE→None，COLOR→ColorTint，SPRITE→SpriteSwap，SCALE→Animation 过渡（Pressed 缩放 Clip）或小型按压缩放组件。interactable 直接映射；自动置灰用 disabledColor 或灰度材质 | 按下、抬起、拖出、禁用状态 |
| Button clickEvents（EventHandler） | View 中 `button.onClick.AddListener` | 记录原 target、handler 和 customEventData，在 View 代码中写成显式调用和常量参数；不按节点索引或 uuid 动态分派 | 每个按钮的业务结果 |
| cc.Toggle、ToggleContainer | Toggle + ToggleGroup | allowSwitchOff 直接映射；checkMark→graphic | 切换与互斥 |
| cc.Slider、cc.ProgressBar | Slider；或 Filled Image / 不可交互的 Slider | progress、reverse、totalLength 换算为 fill 或 value | 进度条两端与中间截图 |
| cc.ScrollView | ScrollRect + Mask/RectMask2D | elastic→Elastic，inertia→inertia，brake 近似换算为 decelerationRate | 滚动、回弹、惯性录像 |
| cc.PageView | ScrollRect + 分页吸附组件 | 吸附组件是小型 Unity 组件 | 翻页录像 |
| 虚拟列表（项目脚本） | ScrollRect + `ObjectPool<T>` 复用条目 | 条目复位写在 actionOnGet/actionOnRelease 中 | 快速滚动后没有旧数据残留 |

## 动画、补间与特效

| Cocos | Unity 目标 | 转换方法 | 对照 |
| --- | --- | --- | --- |
| cc.Animation、AnimationClip（.anim） | AnimationClip，配 Animator 或 Animation 组件 | 曲线属性对应：position→m_AnchoredPosition；scale→m_LocalScale；angle→localEulerAnglesRaw.z；opacity→CanvasGroup 或 Graphic 的 alpha；width/height→m_SizeDelta；active→m_IsActive；spriteFrame→Image.m_Sprite 的 ObjectReference 曲线。sample→frameRate；关键帧缓动→切线，常量帧→Constant 切线；帧事件→AnimationEvent（调用 View 方法） | 关键帧录像，起止值，完成回调 |
| wrapMode、speed、playOnLoad | Loop Time、Animator 状态速度或 Animation.wrapMode；Play On Awake | PingPong/Reverse 用 Animator 状态或 Animation 组件实现 | 循环边界 |
| `animation.play(name)` | `Animator.Play(stateHash)` 或 `Animation.Play(name)` | 状态名用语义名，映射记录在 Analysis | — |
| cc.tween、cc.Action（moveTo、scaleTo、fadeTo、sequence、spawn、delayTime、callFunc、repeat、repeatForever） | DOTween/PrimeTween 的 Sequence | sequence→Append，spawn→Join，delay→AppendInterval，call→AppendCallback，repeat→SetLoops，stop→Kill；用 SetLink 绑定目标生命周期。缓动名映射到插件内置 Ease（如 quadOut→OutQuad），**不搬运 Cocos easing 源码** | 时长、曲线、中途重启、完成回调 |
| Spine（sp.Skeleton） | spine-unity：UI 用 SkeletonGraphic，场景用 SkeletonAnimation | 运行时版本与数据版本一致；premultipliedAlpha 对应材质 PMA 设置；setAnimation、setMix、timeScale、完成监听使用 spine-unity 的 AnimationState API | 动作、混合、加色叠加、完成时机 |
| DragonBones（dragonBones.ArmatureDisplay） | DragonBones Unity 运行时 | 版本匹配 | 同上 |
| cc.ParticleSystem（plist） | ParticleSystem；UI 中使用时需选定 UI 粒子方案并登记 | 转换器近似映射发射率、寿命、速度、重力、颜色区间和混合模式 | 录像对照，允许的差异要记录 |
| cc.MotionStreak | TrailRenderer | — | 录像 |
| cc.Graphics | Sprite、UI 网格组件或 LineRenderer | 按用途选择，并登记 | 截图 |
| Material、.effect、内置置灰 | URP/UI Shader 或 Shader Graph | 按效果重写，例如置灰用去饱和 UI 材质 | 截图 |

## 生命周期、调度与事件

| Cocos | Unity 目标 | 转换方法 | 对照 |
| --- | --- | --- | --- |
| onLoad、start、onEnable、onDisable、onDestroy、update、lateUpdate | Awake、Start、OnEnable、OnDisable、OnDestroy、Update、LateUpdate | 迁移方法体，不复刻 Cocos 的执行顺序；有依赖的顺序改为 Bootstrap 或 Presenter 中的显式调用，不使用 Script Execution Order 去模拟 executionOrder | 依赖顺序的业务结果 |
| schedule、scheduleOnce、unschedule | Coroutine 或 Awaitable（配 `destroyCancellationToken`），或补间插件的 DelayedCall | 按源版本确认节点停用和组件禁用对定时器的影响，在 OnDisable 中显式停止或保留 | 停用、暂停、切场景后的回调 |
| Promise、async/await | `async Awaitable` 方法 | 不实现微任务队列；会影响规则结果的先后顺序，在 Gameplay 中显式编排 | 规则轨迹 |
| director.loadScene、preloadScene、addPersistRootNode | SceneManager.LoadSceneAsync（allowSceneActivation）、DontDestroyOnLoad | 场景拆成 Boot 加内容场景；常驻节点放在 Boot | 切场景、返回、重进 |
| director 时间缩放与暂停 | 玩法时钟与表现时钟分开；必要时使用 Time.timeScale | 按 [跨引擎契约](05-Unity-跨引擎移植与行为一致性.md#时钟与状态) 区分时钟 | 倍速与暂停 |
| node.on(TOUCH_START/MOVE/END/CANCEL) | IPointerDown、IDrag、IPointerUp、IPointerClick 等 Handler | 核对两点差别：释放点在节点外时源发 TOUCH_CANCEL，Unity 发 OnPointerUp 但不发 OnPointerClick；冒泡与吞噬由 raycastTarget 和处理者层级决定 | 拖出、取消、连点 |
| node.emit、自定义事件 | C# event、Action，或 Presenter 的直接调用 | 不建立字符串事件总线 | — |
| systemEvent 键盘 | Input System Action | — | 真实按键 |
| cc.game EVENT_HIDE / EVENT_SHOW | OnApplicationPause / OnApplicationFocus | — | 切后台再回来 |

## 资源、存档、音频与平台

| Cocos | Unity 目标 | 转换方法 | 对照 |
| --- | --- | --- | --- |
| uuid、cc.resources.load、assetManager bundle | 直接序列化引用；动态资源用 Addressables（语义 key） | uuid 到 GUID 与路径的映射写入 Analysis；运行时代码不出现 uuid | 动态加载和失败分支 |
| cc.instantiate、node.destroy | Object.Instantiate、Destroy | — | — |
| cc.NodePool（put/get、unuse/reuse） | `ObjectPool<T>` | put 会移出父节点；在 actionOnRelease/actionOnGet 中显式处理 SetActive、父节点、监听和补间的复位 | 回收后再显示 |
| cc.sys.localStorage | 存档端口与文件存储 | 需要兼容原版存档时，由适配器保留原键和编码 | 关闭后重开 |
| cc.audioEngine、cc.AudioSource | AudioSource 池 + AudioMixer 分组 | 音乐和音效分组，音量映射到 Mixer 参数 | 开关、切后台、播放时机 |
| JSON 配置、cc.JsonAsset | 强类型 ScriptableObject | 在 Editor 中导入为 SO 字段，不在 SO 里存 JSON 字符串 | 规则测试 |
| 物理（PhysicsManager、RigidBody、PhysicsCollider） | Rigidbody2D、Collider2D | 按 PTM_RATIO 换算单位；规则依赖的简单几何判定放在 Domain | 规则轨迹 |
| CollisionManager（非物理碰撞） | Collider2D 触发器，或 Domain 中的几何判定 | — | 命中判定 |
| wx.*、tt.* 平台 API | 平台端口 | 见原生转换规范的平台 SDK 一节 | 不可用时的提示与离线授权路径 |
| JS 数值、排序、取整 | C# 明确类型 | 见 [规则与随机](../../grea-parity/references/06-玩法-规则与随机一致性.md) | oracle 测试 |

## Cocos Creator 3.x 差异

- contentSize 与 anchorPoint 在 UITransform 上；opacity 在 UIOpacity 组件上；旋转使用 eulerAngles。
- 可见性由 Node.layer 加 Camera visibility 决定，映射到 Unity Layer 与 cullingMask。
- 触摸事件同样通过 Node.EventType；全局输入使用 `input.on`。
- Tween、director、resources、assetManager 的语义与 2.x 相近，转换方法沿用本表，但字段名要按 3.x 的序列化格式重新确认。
