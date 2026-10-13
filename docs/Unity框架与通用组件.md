# Unity 框架与通用组件

当前 Foundation、uGUI、Editor 包版本为 `0.2.0`，以自有源码随 grea 分发，尚未发布到 UPM Registry。已有默认程序集可选用桥接包 `0.1.0`。工程规则以 [Unity 开发规范](../skill/references/05-Unity-工程结构与开发规范.md) 为准；本页说明实际 API、安装和测试。

## 包与依赖

| 入口 | 内容 | 编译依赖 |
| --- | --- | --- |
| [Foundation](../tools/unity/framework/packages/com.grea.foundation/README.md) | 纯 Contracts、作用域/代次/句柄、服务启动、诊断、Catalog、音频、最小文件存档及平台端口 | Contracts 无 Unity 引用；Runtime→Contracts、Unity Runtime |
| [uGUI](../tools/unity/framework/packages/com.grea.ui.ugui/README.md) | CommandButton、ModalPanel、ScreenHost | Foundation、uGUI 2.6.0 |
| [Editor](../tools/unity/framework/packages/com.grea.editor/README.md) | 指定对象根的只读 Missing Script/必需字段检查，以及暂存工程内的生成/绑定回读 | Foundation Runtime；包测试使用 uGUI；仅 Editor |
| [装配示例](../tools/unity/templates/counter-composition/README.md) | Game.Domain / Gameplay / Services / Presentation / Bootstrap 与合成计数业务 | 按标准显式向下引用；公共包不引用 Game |

组件的序列化字段、所有权、最小调用与失败契约见各包 README，实际用例在包内 Tests。没有通用战斗、事件总线、DI 容器、虚拟列表、资源异步后端或商业 SDK。资源 Catalog 借用显式对象引用；句柄统计不等于 Unity 内存卸载。关闭作用域使 token/代次失效，但用户回调仍必须协作取消、检查代次和被调用方观察，不能强行终止任意 Task。

所有包带 MIT 许可证和 Unity 生成的稳定 meta。复制包时保留 meta；不要在安装副本改框架源码。程序集有向无环，Contracts/Domain/Gameplay 使用 `noEngineReferences`，测试程序集受 `UNITY_INCLUDE_TESTS` 约束，与运行构建隔离。没有可变全局状态或自动生成单例。

## 隔离安装与原生测试

从仓库根执行，输出目录必须不存在。准备脚本只复制自有源码/示例和依赖声明，不打开 Editor；拒绝既有目标和链接路径。

```sh
python3 scripts/testing/prepare-unity-framework.py --output .private/framework-check/new-project
unity test .private/framework-check/new-project --mode EditMode \
  --output /absolute/new-evidence/editmode.xml --timeout 240 --format json
unity test .private/framework-check/new-project --mode PlayMode \
  --output /absolute/new-evidence/playmode.xml --timeout 240 --format json
```

加 `--packages-only` 可准备完全不含 Game 业务程序集的包独立安装工程。

`/absolute/new-evidence` 应为此次测试单独预建的证据目录，不使用现有文件。Unity 导入会写隔离工程的 Library/ProjectSettings/日志，并恢复 manifest 声明的官方依赖；需要可用 Editor/许可。不要给 `unity test` 加 `--allow-install` 来隐式更换环境。批处理可在命令后添加 `-- -nographics -logFile /absolute/new-evidence/editor.log`。这会降低图形验证能力，不作为画面或音频听感验收。

精确测试组合是 Unity `6000.6.2f1`、URP `17.6.0`、uGUI `2.6.0`、Unity Test Framework `1.8.0`、macOS arm64 Editor。包可在新工程 Packages 中以 embedded 形式安装，包目录间无仓库外软链接/绝对 file 引用。新建独立副本不复用 Library；官方包恢复可使用本机 UPM 下载缓存，不代表离线、全新机器或断网恢复通过。

[测试依赖锁](../tools/unity/framework/test-packages-lock.json) 来自真实 Editor 解析，包含实际传递版本；内置包依赖由该 Editor 提供。不要把包 package.json 中的最低依赖版本与锁定的实际解析版本混为一谈。第三方源码/二进制不随公共包分发；备份恢复工具见 [包备份说明](../tools/unity/packages/README.md)。原始 XML/Editor 日志保留在 `.private/unity-m2/`，公开 [基础框架验证摘要](validation/2026-10-13-unity-m2.json) 仅含脱敏结果、测试名与哈希。

普通 Python 回归不启动 Unity：

```sh
./.venv/bin/python -m unittest discover -s tests -p test_unity_framework.py -v
```

该检查验证程序集边界/无环、meta 唯一性、包依赖/许可及准备脚本的保留与越界行为；它不能替代 C# 编译和运行测试。现有 GitHub Source checks 自动发现这些 Python 测试；本阶段没有创建需要私有许可的 Unity CI 作业。

## 验收解释

基础框架原生测试覆盖服务重复初始化/逆序失败清理、关闭期间取消、父子作用域回收、双归还、诊断预算、资源计数/类型/销毁、存档校验/备份/遗留 pending、分层业务失败提交、按钮重绑/快速点击/失败恢复/晚回调、弹窗反复打开/焦点恢复、页面替换和音频句柄退出。关闭 Domain/Scene Reload 的真实两次 Play 进出另有 Editor 测试；测试恢复原 EditorSettings。

上述包测试记录只证明组件局部行为。完整参考游戏的 A0–A4 见 [参考游戏](Unity参考游戏.md)，两个既有工程所迁模块的 A5 见 [隔离迁移](Unity隔离迁移指南.md)；不能把这些结果自动套用到任意目标工程。真实断电、多写者、IL2CPP、Windows 与完整原版一致性仍未验。

工程生成独立生成接口不改变静态规划的 `validate_unity_project` / `plan_unity_project`，两者继续保持只读静态语义，其 `not_run` 指当前被检查工程未做原生验证。`frameworkPackages` 的解析/安装、embedded 包来源盘点仍未接入静态规划，所以会继续返回 `FRAMEWORK_NOT_IMPLEMENTED`，不能直接用本测试工程充当静态规划已合规工程。包实测不会让静态规划的 `generationReady` 自动变成 true；生成有独立 CLI/MCP 接口。准备脚本是仓库测试工具，不是产品生成器。

包测试与程序集配置依据已核对 [Unity 6000.6 包测试文档](https://docs.unity3d.com/6000.6/Documentation/Manual/cus-tests.html) 和 [asmdef 格式](https://docs.unity3d.com/6000.6/Documentation/Manual/assembly-definition-file-format.html)；本项目包拆分和生命周期 API 是 grea 的设计选择。
