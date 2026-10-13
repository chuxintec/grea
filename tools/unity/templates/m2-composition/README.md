# M2 分层装配示例

这是 seed-once 候选源码示例，使用自有合成计数业务。不是生成模板版本 `grea-minimal-2d/0.1.0-design` 的执行实现，不含 Scene/Prefab，也不代表完整可玩的参考工程（M4）。不将它复制到既有游戏。

Domain 定义不可变状态；Gameplay 拥有状态与暂停/退出规则及持久化端口；Services 实现有版本的合成 DTO；Presentation 把按钮请求传给 Gameplay；Bootstrap 显式构造这些对象并持有生命周期。Domain/Gameplay/Services 均无 Unity 类型引用；基础包不引用 Game。

最小用法：`using (var app = new CounterComposition(savePort, optionalCommandButton)) { app.Session.Increment(); }`。UI 不直接保存；保存成功后才提交运行状态；缺档从零启动，未知 DTO/IO 失败显式报错且不重写。第二个装配实例读取前次保存值；这只证明同进程装配重入，不等于 Player 关闭重开。

`Assets/Tests/Editor/CompositionTests.cs` 覆盖暂停、恢复、退出后拒绝命令、重入加载、写入失败和未知版本。复制到实际项目后，Game 命名空间和业务源码归该项目维护；后续工具不得覆盖人工扩展。示例与公共包采用仓库 MIT 许可证。
