# Counter 分层装配示例

这是 `grea-minimal-2d/0.1.0` 生成配方的 seed-once 源码，使用自有合成计数业务。Scene/Prefab 由 Editor 生成器另行创建；本示例不代表完整可玩的参考游戏。不将它复制到既有游戏。

Domain 定义不可变状态；Gameplay 拥有状态与暂停/退出规则及持久化端口；Services 实现有版本的合成 DTO；Presentation 把按钮请求传给 Gameplay；Bootstrap 显式构造这些对象并持有生命周期。Domain/Gameplay/Services 均无 Unity 类型引用；基础包不引用 Game。

最小用法：`using (var app = new CounterComposition(savePort, optionalCommandButton)) { app.Session.Increment(); }`。UI 不直接保存；保存成功后才提交运行状态；缺档从零启动，未知 DTO/IO 失败显式报错且不重写。第二个装配实例读取前次保存值；这只证明同进程装配重入，不等于 Player 关闭重开。

`Assets/Tests/Editor/CompositionTests.cs` 覆盖暂停、恢复、退出后拒绝命令、重入加载、写入失败和未知版本。复制到实际项目后，Game 命名空间和业务源码归该项目维护；后续工具不得覆盖人工扩展。示例与公共包采用仓库 MIT 许可证。

## 在五层中继续开发

| 改动 | 所有者与具体入口 | 依赖与验收 |
| --- | --- | --- |
| 新规则、状态和计算 | `Domain/CounterState.cs`，按业务扩展自己的模块 | 不引用 Unity 或表现；用纯状态输入验证成功和拒绝分支 |
| 新命令与流程 | `Gameplay/CounterSession.cs`，在这里定义服务端口及提交顺序 | 只引用 Domain 和纯 Contracts；保存失败不能提交运行状态；暂停/退出拒绝新命令 |
| 文件、平台与资源接入 | `Services/CounterPersistence.cs` 或明确端口的适配器 | 具体实现注入 Gameplay；游戏数据编码仍由项目拥有，不将示例 DTO 当通用存档格式 |
| 新界面与反馈 | `Presentation/CounterPresenter.cs` 与项目自有 Prefab/Variant | 输入发请求，按结果刷新；CommandButton 只处理监听和防重入；页面退出清理作用域 |
| 增加或更换依赖 | `Bootstrap/CounterComposition.cs` | 显式构造和逆序释放；其他业务层不得反向引用 Bootstrap |
| 回归 | `Assets/Tests/Editor/CompositionTests.cs` 及实际输入/Player 检查 | 纯测试、Editor 生命周期、真实输入、关闭 Player 重开分别记录 |

五层是职责约束，不是五套框架。`Counter` 和 `Game` 是 seed-once 的示例名，采用后替换为项目自己的模块；公共包不增加按计数、战斗或益智类型切换的分支。

SceneManager 用于 Bootstrap 入口加载与场景退出；Input System/EventSystem 由一个场景所有者配置；需要池化时直接用 Unity Pool；混音走 AudioMixer，动画用原生 Animation/Animator/Timeline 或项目已选插件。只有实际生命周期或失败契约存在缺口时才增加接入代码，不为这些入口创建空管理器。

准备脚本在创建目标前执行源码/具名 asmdef 边界守卫，拒绝纯规则层引用 Unity、公共包引用项目、循环依赖、运行代码依赖 Editor 和未隔离测试。它不能解析任意反射、GUID 引用或预编译二进制的真实依赖，仍需 Unity 编译及 Player 载荷检查。原生成配方继续以源码/生成资产所有权检查保护人工修改；不以重新生成作为日常编辑界面的方式。
