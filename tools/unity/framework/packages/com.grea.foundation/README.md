# Grea Foundation 0.1.0

MIT 自有源码；M2 候选基础包。最低声明 Unity 6000.6，当前测试组合为 6000.6.2f1/macOS arm64。其他 Editor、Player、IL2CPP 和移动平台未验证。没有 DI 容器、全局单例或隐式服务查找。

`Grea.Foundation.Contracts` 无 Unity 引用；`Grea.Foundation.Runtime` 引用 Contracts 和 Unity Runtime（音频模块 1.0.0）。测试程序集仅在 Editor 且启用测试时编译。安装时将整个目录作为 embedded package 复制到新工程 Packages；保留所有 meta，不复制到 Assets。

## 组件契约与最小用例

| 组件 | 用法、所有权与失败 |
| --- | --- |
| LifetimeScope / OperationStamp | `using (var scope = new LifetimeScope()) { var stamp = scope.Capture("load.1"); }`；每次打开创建新作用域作为代次；关闭先失效/取消，再逆序释放。异步结果在修改状态前调用 `stamp.ThrowIfStale()`。父退出使全部子代次失效。 |
| Lease | `scope.Own(resource, x => x.Dispose())`；一次释放，多次 Dispose 无副作用；释放后 Value 抛异常；不支持多线程并发归还。 |
| ServiceScope | `var app = new ServiceScope(serviceA, serviceB); await app.StartAsync(); ... await app.StopAsync();`；构造顺序启动，逆序清理，含初始化失败项。重复 Start/Stop 复用结果；失败作用域不重启，创建新实例。 |
| AssetCatalog | 显式字典 key→Unity 对象；`catalog.Acquire<GameObject>("screen", scope)`；记录每 key 引用计数；找不到、类型错、对象已销毁均抛具体异常。对象本身是借用，不会 Unload/Destroy；句柄只释放引用声明。 |
| AudioPlayer | `new AudioPlayer(ownerTransform, mixerGroup).Play(clip, scope, loop: true)`；显式宿主，可选 Mixer；句柄退出立即 Stop/清 clip，延迟 Destroy 子对象。无自动池化；非循环播放结束仍需释放句柄；暂停/静音由持有方控制句柄的 AudioSource。 |
| FileSaveStore | `new FileSaveStore(absoluteTrustedRoot, "player", "qa", true)`；不自动选择 persistentDataPath。QA/玩家命名空间必不同；Read 缺档返回 null。Write 最大 1 MiB UTF-8，带 envelope 版本与 SHA256，Flush→同目录 Move/Replace。 |
| DiagnosticBuffer | `new DiagnosticBuffer(128).Record(new DiagnosticEvent("ui", "open.1", "CLOSED"))`；丢弃最旧事件，1–4096 条，每字段最多 80 ASCII 字符；仅记录技术标识，禁止账户/存档/私有路径。Snapshot 返回副本。 |
| UnityPlatformInfo / UnityGameClock | 显式注入 `IPlatformInfo` / `IGameClock`；读取真实平台/焦点或受 timeScale 影响的游戏时间。不把这些接口作为联网、支付或平台权限的成功替身。 |

全部对象在创建它的 Unity 主线程使用，异步续体须回到该线程；没有线程安全承诺。OperationStamp 是协作取消协议，不能阻止忽略它的第三方回调。LifetimeScope.Dispose 取消和释放，但不等待任意外部任务；拥有者仍须观察任务结束。ServiceScope.StopAsync 等待初始化真实结束后才释放；不合作的初始化可能阻塞，调用方需上层超时并保留未完成状态，不能假称资源已清理。

服务在 InitializeAsync 前不得持有需该 scope 释放的资源；Dispose 必须能处理部分初始化。失败与清理异常以 AggregateException 保留；Stop 会再次报告启动失败，确保失败不被吞掉。同步回调内重入 Start/Stop 是明确错误。无可变静态状态，Domain Reload 关闭组合仍需要项目运行验收。

存档根必须是应用独占、无链接的可信目录；单写者，非跨进程锁。SHA256 用于损坏检测，不是认证/加密。原档损坏/未知版本时拒绝覆盖；`ReadBackup()` 只读备份，恢复与业务 DTO 迁移由项目显式决定。遗留 `.pending` 阻止新写入，保留中断证据。此处实测文件替换和中断夹具，不宣称真实断电、跨平台原子性或旧游戏存档兼容。UI 不直接调用此适配器。

`Tests/Editor/FoundationTests.cs` 包含正常与失败用例；Test Framework 1.8.0 为测试工程依赖，不强制业务项目启用测试包。没有内置配置资产、Prefab、玩家数据或第三方二进制。
