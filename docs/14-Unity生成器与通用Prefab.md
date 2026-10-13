# Unity 生成器与通用 Prefab（M3）

M3 提供 `plan_unity_generation`、`generate_unity_project`、`recover_unity_generation`；CLI 使用对应 kebab-case。CLI/MCP 共用实现，Editor 长任务通过已有 `unity_cli` provider 和有界 runner 执行。当前只支持新建工程和自身生成工程的保留校验；已有工程 adopt 只读，refactor 写入与模板升级均不支持。M1 的静态接口保持原语义，不用旧 M1 planId 执行 M3。

## 锁定范围与输入

复制 [M3 配置夹具](../tests/fixtures/unity-generation-v1.json) 到一个独立项目根，命名 `grea-project.json`。根目录需已存在，配置中的 `UnityProject` 目标必须不存在，空目录也不覆盖。Evidence、Build 与 Unity 工程分开，路径都相对该根，不允许 symlink、路径穿越或大小写/Unicode 冲突。

精确组合：Unity 6000.6.2f1、URP 17.6.0、uGUI 2.6.0、legacy input、Catalog、macOS arm64/Mono。模板为 `grea-minimal-2d/0.1.0`，生成器 `0.1.0`，自有 Foundation/uGUI/Editor 包 `0.2.0`。当前仅支持夹具中的 Counter 四层模块选择和六项 features，不静默忽略未知模块；Bootstrap 为固定装配层。项目 ID、namespace、场景名与存档 namespace 可配置。依赖包来自随 grea 分发的源码和锁定的官方包，不接受用户替换 frameworkPackages 或例外。

`dependencyLock` 两项为 null，首次生成使用随模板提供的锁定依赖，最终 manifest/lock 的实际字节写入所有权清单。目标平台选择是生成配置，不是 Player 已验证声明。其他平台上的 plan 可只读运行，写入端当前依赖 macOS 原生 Unity 环境；不自动安装 Editor、激活许可或更换版本。

```sh
./bin/grea plan-unity-generation '{"project_root":"/absolute/new-project"}'
./bin/grea generate-unity-project '{"project_root":"/absolute/new-project","plan_id":"<上一步 planId>","run_dir":"Evidence/generate-001","timeout_seconds":300}'
```

以上 `<上一步 planId>` 必须替换为真实的 64 位哈希。规划输出遵循 [M3 计划 Schema](../schemas/unity-generation-plan.schema.json)，不写目标或证据；planId 绑定根路径、配置、模板/包字节、生成器源码、provider 声明与当前目标盘点。执行会重读这些输入；变化返回 `STALE_PLAN`。run_dir 必须位于 evidenceRoot 下且不存在。日志/源码暂存/恢复状态只放本次 run_dir。

## 生成物与所有权

| 内容 | 位置 | 所有权与扩展方式 |
| --- | --- | --- |
| 框架包及稳定 meta | UnityProject/Packages/com.grea.* | package；按版本升级，不能在副本内改包后要求自动覆盖 |
| 分层 Counter 示例、ProjectBootstrap | Assets/Game 各层 | seed-once；首次创建后归项目维护，重复执行保留人工代码 |
| ButtonShell | Assets/GreaGenerated/ButtonShell.prefab | Image、Button、CommandButton；颜色反馈，业务监听运行时装配 |
| ModalShell | Assets/GreaGenerated/ModalShell.prefab | 内容、遮罩、关闭按钮、ModalPanel；EventSystem 是声明的宿主绑定槽，独立基础壳不私造第二个输入系统 |
| UIHost | Assets/GreaGenerated/UIHost.prefab | Canvas/缩放/射线、Pages/Modals/Toasts 层、一个 EventSystem、嵌套按钮/弹窗；填充并回读全部必需字段 |
| BootstrapConfig、Renderer、Pipeline | Assets/GreaGenerated | generated；启动/存档命名配置、URP Renderer 与 Pipeline 资产 |
| Bootstrap、Entry 场景与构建场景表 | 配置声明的 Assets/Game/Scenes 路径 | generated；唯一启动组件加载 Entry，Entry 使用 UIHost，URP 通过 Editor 设置 |
| 所有权清单 | Tools/Generated/manifests/project.json | [Manifest Schema](../schemas/unity-manifest.schema.json)，含 recipeId、输入身份、每文件哈希/meta/GUID、关键对象 fileID、owner |
| 请求、逐资产日志、项目设置、.gitignore | Tools/Generated、ProjectSettings、工程根 | generated；缓存不作为可维护源码纳管 |

Scene/Prefab/ScriptableObject 都通过 AssetDatabase、PrefabUtility、EditorSceneManager 创建，不拼接 Unity YAML。新建资产的 GUID 由 Unity 分配；不同新工程可以不同，同一工程必须保留。基础 Modal 的 events 槽由 UIHost 嵌套实例覆盖；生成器回读宿主完整绑定、单一 EventSystem、启动组件数量和配置引用。业务名和类型由 namespace 明确指定，找不到或多于一个匹配类型即失败。

URP 还会通过自身 Editor 逻辑创建根级 DefaultVolumeProfile 和 UniversalRenderPipelineGlobalSettings；这两项按实际输出登记为 generated，保留其默认路径，不冒称所有 Engine 默认资产已归入 GreaGenerated。

这是有源码和配置的最小生成工程，按钮只演示弹窗生命周期，Counter 示例尚未装配成完整玩法。没有正式画面、字体主题、Toast 内容、复杂列表或生产存档迁移；M4 才负责完整闭环和 Player。按钮外观只使用 Unity 原生 Image，无外部素材。

## 执行、重复生成与冲突

1. 检查配置/输入/路径/已有目标；以操作系统文件锁串行化同一根的生成和恢复。
2. 将确定的源码与请求写入本次 Evidence 暂存工程；每文件的前像均为不存在，不改正式目标。
3. 运行指定版本 Editor，等待真实编译和 executeMethod 完成。日志由 runner 捕获，有输出/时间预算；不把帮助、进程启动或单纯退出码当绑定通过，要求完整资产日志和回读结果，执行中的 Unity Error 使该步骤失败。
4. 每个资产先记录 pending，再通过 Editor 创建，回读后记录哈希、GUID/fileID。已记录资产只验证，不重建。
5. Editor 完整退出后核对源码、生成物、清单和计划身份；以不可替换目标的原子目录移动发布新工程。目标在此期间出现时保留双方，返回冲突。

再次规划同一生成工程得到 `action=verify`，执行不再开 Editor、不改文件/GUID/监听。generated/package/meta/必需文件变动返回 `OWNERSHIP_CONFLICT`；seed-once 源码变动或新增 human 文件会列出并保留，外层为 partial，且只引用前次生成字节证据，不声称修改后的代码已编译。未知文件永不移动/删除。已有 Variant 不会被 Apply 或重写；修改基础 generated Prefab 会阻止重生成，模板升级必须另行设计迁移。

adopt 示例：

```sh
./bin/grea plan-unity-generation '{"project_root":"/absolute/project","mode":"adopt"}'
```

M3 adopt 仍需 M3 支持的配置配方，只盘点和 preserve，不建立所有权或“认领”已有资产；一般既有项目盘点继续使用 M1。M1 不能把 M3 新模板与包解析误记为已支持。

## 中断恢复

```sh
./bin/grea recover-unity-generation '{"project_root":"/absolute/new-project","run_dir":"Evidence/generate-001","timeout_seconds":300}'
```

恢复必须明确选择原 run，不自动重试。重新验证生成器/配置/包身份和操作系统锁，检查 Editor 的项目锁、上一尝试退出回执和进程组；找不到退出回执或进程仍存活时拒绝再次启动。超时/取消由现有 runner 清理自己拥有的进程组，脱离进程组的外部进程不在其清理保证内。

| 中断点 | 处理 |
| --- | --- |
| 源码暂存部分完成 | 只补齐缺失且计划明确拥有的文件；已出现的字节必须匹配，其他字节保留并停止 |
| prepared、尚未启动 Editor | 复核完整暂存快照后续作 |
| Editor 已明确退出且保存失败快照 | 快照完全相同、锁/进程消失才进入资产日志恢复；手工改动使恢复停止 |
| 已完成某资产的回读检查点 | Editor 校验其原 hash/meta/GUID，跳过该资产，继续后续创建 |
| pending 资产、日志原子写入遗留 tmp/next、无退出/失败快照 | `RECOVERY_REQUIRED`，保留全部资料；不能猜测写入是否完成，也不删除后盲目重放 |
| 已核验、未发布 | 重核快照后原子发布，不再生成 |
| 已发布、最终状态尚未写回 | 核对目标清单与完整字节后完成回执，不重写资产 |

不提供删除/整工程 reset/自动回滚接口。新工程的“原状”是目标不存在，因此失败通常只留下隔离暂存，不需要覆盖前像。磁盘断电、恶意并发替换路径、强制杀掉所有记录写入方、跨文件系统移动未被宣称自动恢复；无法证明安全时保留并报告。人工作业不应写入正在使用的暂存目录。

## 可复现验收

```sh
./.venv/bin/python -m unittest discover -s tests -p test_unity_generation.py -v
python3 scripts/testing/prepare-unity-m3.py --output .private/unity-m3/new-editor-tests
unity test .private/unity-m3/new-editor-tests --mode EditMode --output /absolute/evidence/editmode.xml --timeout 300
python3 scripts/testing/prepare-unity-m3.py --generated-project /absolute/new-project/UnityProject --output .private/unity-m3/new-play-tests
unity test .private/unity-m3/new-play-tests --mode PlayMode --output /absolute/evidence/playmode.xml --timeout 300
```

Python 事务测试模拟 Editor，不算原生证据；另有 Unity 实际生成/绑定、逐检查点恢复、Variant、重复生成和生成物 PlayMode 测试。Editor 破坏性夹具只有检测到隔离标记且测试资产不存在才运行；PlayMode 在生成项目的独立源码副本中添加测试，不污染正式生成清单。输出路径必须为此次新目录。日志、私有包备份保留在 `.private/`；公开结果见 [M3 验证摘要](validation/2026-10-13-unity-m3.json)。

当前验收限定 M3：生成/身份与局部 Editor/组件运行。M4 完整游戏闭环、目标 Player、真实输入/视觉/音频与关闭重开，及 M5 原游戏等价性均未完成。

API 依据：[PrefabUtility.SaveAsPrefabAsset](https://docs.unity3d.com/6000.6/Documentation/ScriptReference/PrefabUtility.SaveAsPrefabAsset.html)、[GUID/local fileID 回读](https://docs.unity3d.com/6000.6/Documentation/ScriptReference/AssetDatabase.TryGetGUIDAndLocalFileIdentifier.html)。Scene 对象使用 GlobalObjectId 回读，不能用普通资产批量加载 API 代替场景加载。
