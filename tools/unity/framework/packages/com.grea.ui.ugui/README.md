# Grea uGUI 0.3.0

MIT 自有源码。依赖 Foundation 0.2.1 和 uGUI 2.6.0；实测 Editor 6000.6.2f1 的组件 PlayMode，不代表视觉/输入设备/目标 Player 验收。包包含组件源码；M3 通过 Editor API 生成 UIHost、ModalShell 和 ButtonShell，不分发手写 YAML。

| 组件 | 必需字段与契约 | 最小用例及失败 |
| --- | --- | --- |
| CommandButton | `button: Button`；只管理命令监听，不持有存档和玩法状态。Button 自有 Transition 负责反馈。 | Configure(button)→Bind(owner, async stamp => ...)；一次处理中丢弃额外点击，临时禁用交互。关闭/禁用 Unbind，晚完成先检查 stamp。缺 Button 抛错。 |
| ModalPanel | `content`、`blocker`、`closeButton`、`firstSelected`、`events`；宿主必须位于 content 外，blocker 应有 raycast Target，Canvas 排序由项目设置。 | Configure→Open(parent)→Close→Open；重复 Open 不叠监听；关闭使 VisibleScope 失效并恢复原焦点。缺字段在打开前报错。 |
| ScreenHost | 无序列化字段；调用者显式传入 panel/owner。 | Show(panel, owner) 替换当前页面，Close 幂等。不是弹窗堆栈；多个独立 host 的输入优先级由项目管理；null 目标抛错。 |

按钮 Pending 是已观察的处理任务，**任务完成不等于业务成功**，还需检查 Outcome（Idle/Running/Completed/Cancelled/Failed），失败细节为 LastError。业务命令必须在提交状态/更新视图前检查 stamp，并定义提交后取消语义；本包不实现分布式事务。绑定销毁不强制杀死用户 Task；调用方需要观察返回任务和取消。业务错误不打印完整数据。组件仅支持 Unity 主线程。

基础用法：创建 `LifetimeScope`；用 `CommandButton.Configure(button)` 绑定 Button；用 `Bind(scope, stamp => { stamp.ThrowIfStale(); session.Execute(); return Task.CompletedTask; })` 发出请求；页面退出调用 scope.Dispose 和 Unbind，重开使用新 scope。不得通过 onClick 直接修改持久化 DTO。持有 `ModalPanel.VisibleScope` 的异步内容请求在关闭后失效。

最小运行/失败例见 `Tests/Runtime/UiTests.cs`：重复绑定、快速点击、错误、缺引用、弹窗反复打开/焦点恢复、禁用解绑、音频退出清理。程序化事件测试不等于鼠标/触摸/键盘输入或遮罩视觉验证。返回键、手柄导航、动画、叠栈、对象池、列表和自动加载未实现。

M3 增加 UIHost：显式绑定 canvas/pageLayer/modalLayer/toastLayer/events/openButton/modal；Start 或重新启用后绑定开窗按钮，禁用/销毁取消作用域并关闭弹窗。每个宿主只拥有一个 EventSystem；项目不得重复实例化宿主。组件缺字段会明确报错。生成器按这些字段回读校验。


## 0.3.0 显式制作接口

`ButtonPressFeedback.Configure(Button, Transform visual, float scale, float seconds)` 只缩放显式视觉目标的 x/y，保留 z 和稳定点击区域。使用非缩放根 Button，另设视觉子节点；比例为 (0,1]、时间非负且有限。按下后松开恢复，退出/拖动/失焦/禁用/销毁取消；退出后重新进入不重新武装。其他指针不能夺取当前按压；组件不派发点击、不修改业务、不引入 tween 引擎。外部重新制作的基础缩放不会在取消时丢失。键盘提交仍由 Unity Button/CommandButton 处理，不假称产生鼠标缩放。

`UIHost.safeAreaRoot` 是可选的原生布局入口；`ApplySafeArea(Rect safePixels, Rect viewportPixels)` 接受同一原点、同一**物理像素**单位的矩形，先求交再归一到 anchors，支持非零窗口原点。`Vector2` 重载表示原点为零的屏幕尺寸。非法、非有限或不相交输入抛错且不写布局。平台 SDK 的逻辑像素/左上角坐标由平台适配器转换。配置后运行时在 Screen.safeArea/窗口尺寸变化时更新；不是每帧查来源节点图。

`UIHost.bindOpenButton=false` 让项目自行拥有命令绑定，避免默认 demo Start 重绑；旧资源默认 true 保留行为。`ModalPanel.ConfigureContentSlots(RectTransform body, Text heading)` 提供 ContentSlot/Title/CloseButton 显式制作接口；body 必填、标题可选，旧 Configure 的五参数与焦点恢复行为不变。生成配方会要求标题槽，但旧手工面板可不提供。没有模态栈、异步窗口加载或自动音效策略。

键盘命令暂时禁用按钮时，CommandButton 保留原有导航选择，供模态面板捕获并在关闭后恢复；若 Deselect/Select 回调使作用域失效则不再派发旧请求。异步任务期间用户切换到其他控件后，完成不会抢回焦点。该规则由真实键盘首击失焦反例驱动，接口测试与实际 Player 输入仍分别验收。
