# Unity M4：参考游戏、独立分发与 Player 验收

Signal Garden 是 grea 的自有最小参考游戏：收集五个信号，支持暂停/恢复、结算、返回、重开与完成次数存档。它用于验证标准、框架、Prefab 和分发链路，不能替代任何原版游戏的一致性验收。M5 的既有工程试点尚未开始。

## 固定组合与源码边界

| 项目 | 本轮配置 |
| --- | --- |
| 工程标准 / 参考游戏 | 1.0.0 / 1.0.0 |
| M3 模板 / 生成器 | grea-minimal-2d 0.1.0 / 0.1.0 |
| 自有包 | foundation、ui.ugui、editor 均为 0.2.0；源码哈希见参考工程 framework.lock.json |
| Editor / CLI | 6000.6.2f1 / 1.0.0-beta.8 |
| 官方依赖 | URP 17.6.0、uGUI 2.6.0、Test Framework 1.8.0；传递依赖见 packages-lock.json |
| 输入 / Player | Legacy Input、macOS arm64、Mono、Medium 托管裁剪 |
| grea 产品版本 | 2026.10.13rc2 保持不变；本阶段不发布 Release 或移动标签 |

[参考源码](../tests/unity/reference-project/README.md) 按 Domain / Runtime / Editor / Tests 分层。Domain 不引用 UnityEngine，Runtime 装配 UI、会话作用域、音频和存档，Editor 负责资产创建、绑定回读与固定目标构建。Content 与 Scenes 是通过 Unity API 创建并纳管的资产，不手写 Unity YAML。作为仓库内测试夹具，业务根命名为 `Assets/Reference`，采用独立命名空间；这不是对现有游戏目录的自动迁移。

基础工程由 M3 生成；参考场景是单场景入口，在运行时实例化 ReferenceView Prefab。按钮嵌套复用 M3 ButtonShell，UIHost / ModalShell 保留在源码中用于检查，未引用的资产不进入 Player。状态切换不重复订阅按钮，离开/暂停使待处理收集失效，失败存档不计入成功次数。所有画面几何和提示音由自有代码生成；未包含游戏包、私人插件、外部美术或字体文件。文字使用 Unity 内置 LegacyRuntime 字体，第三方许可不受 MIT 覆盖。

## 创建、分发和独立恢复

不要直接用 Unity 打开仓库内的参考目录。先通过统一工具 ID materialize，将当前锁定的自有包源码嵌入一个新目录：

```sh
./bin/grea legacy unity_reference prepare --output /absolute/new-reference
./bin/grea legacy unity_reference archive --output /absolute/distribution/reference-source.zip
./bin/grea legacy unity_reference verify --archive /absolute/distribution/reference-source.zip
./bin/grea legacy unity_reference restore --archive /absolute/distribution/reference-source.zip --output /absolute/restored-reference
```

MCP 可用既有 `run_tool`，选择 `tool_id=unity_reference`，传入相同参数和新的 `run_dir`。该工具只处理参考源码的文件分发，不启动 Editor。原有工具 ID 和操作 Schema 不变。

源 ZIP 包含 Assets、Packages manifest/lock、自有框架源码、ProjectSettings、许可证与逐文件 SHA-256 清单，另附整个 ZIP 的 `.sha256` 文件。可以用系统解压工具独立解包，不需要 grea、原开发目录或任何软链接；Unity 官方依赖仍需通过 UPM 解析。脚本先验证清单再恢复，拒绝覆盖已有输出、路径穿越、软链接、大小超限与大小写/Unicode 冲突。SHA-256 用于完整性检查，不是发布者签名；应从可信来源获取包和校验值。

源码包不携带 Library、Temp、Build、日志、存档、Editor 安装或许可证。无缓存的工程恢复不等于离线或全新机器已验收：本轮使用本机已安装的 Editor、许可证和可用 UPM 缓存。

## 测试、重复生成和构建

在恢复后的工程中执行，证据与输出使用工程之外的新目录：

```sh
unity test . --mode EditMode --output /absolute/evidence/editmode.xml --timeout 300
unity test . --mode PlayMode --output /absolute/evidence/playmode.xml --timeout 300
unity run . --timeout 300 -- -nographics -executeMethod Grea.Reference.Editor.ReferenceBuilder.Author
unity build . --target StandaloneOSX --execute-method Grea.Reference.Editor.ReferenceBuilder.Build --output-path /absolute/build/SignalGarden.app --timeout 600
```

Author 在已有清单字节相同时只验证；资产或 meta 有人工改动则拒绝覆盖。它不是升级工具。M3 基础工程自己的 generate 重跑同样返回 unchanged；参考业务源码在基线生成后由项目维护，不能用 M3 清单宣称重生成了业务内容。

Build 显式指定参考场景、架构、后端和裁剪级别；输出已存在时失败。成功产生 app 和 `player-build.json`，并检查 Player 中不含测试/Editor 程序集。Unity CLI 还可用 `--provenance-path` 写构建来源；若隔离工程位于未提交的 grea 工作树下，需要明确 `--allow-dirty-build`，应以分发清单和实际编译源码哈希补充身份，不能把父仓库 HEAD 当成新源码提交。

macOS Player 用 `ditto -c -k --keepParent` 打包以保留可执行位和应用结构，随包附自有 LICENSE、第三方说明/通知、构建回执和校验值。解包到新目录后启动验证。当前是本机构建验证制品，未做 Developer ID 签名、公证或跨机器 Gatekeeper 验收。

## Player 实玩和证据

用 QA 参数启动，不污染普通玩家存档：

```sh
open -n /absolute/build/SignalGarden.app --args --grea-qa-root /absolute/evidence/qa --grea-run-id first -logFile /absolute/evidence/first.log
```

1. START RUN，收集部分信号；PAUSE 或 Escape 后分数保持，RESUME 后继续。
2. 收集满五次，结算只增加一次完成次数；PLAY AGAIN 从零开始。
3. 暂停并 RETURN TO MENU，未完成一局不增加次数；再次进入没有旧监听/迟到回调。
4. 返回菜单并 QUIT；从独立解包的 app 重开，相同 QA root、新 run ID，确认完成次数保留。
5. 检查主菜单、玩法、暂停、结算的显示/输入；失焦暂停；音频输出和听感分别记录。

QA trace 位于 `runs/<run-id>.jsonl`，最多 512 条，包含 buildId、阶段、分数、完成次数、窗口焦点、窗口内输入坐标/射线命中和游戏音频 RMS。普通运行不写该 trace，不收集系统音频或账户数据。相同 run ID 拒绝覆盖。QA 与玩家分别使用 `saves/signal-qa` 和 `saves/signal-player`，存档 DTO 为 `signal:1:<完成次数>`。未知版本/损坏/未完成写入保留原件，显示错误，不静默重置。

本轮自动化鼠标事件到达 Unity 后读到的坐标与目标按钮不一致；人工实玩使用真实指针并保留命中/事件证据。不能把直接调用 onClick、通过测试或只启动进程替代这层证据。音频 RMS 证明游戏混音器有输出，不代表扬声器听感或原版音频一致性。

实际结果、源码/制品/测试哈希和未验项统一见 [M4 验收摘要](validation/2026-10-13-unity-m4.json)。M1 静态 API 的运行状态不会因为这个参考游戏通过而自动变成 pass；能力矩阵仅对命名的参考游戏和精确版本组合登记证据。

## 升级与回退

参考游戏 1.0.0、模板 0.1.0 和包 0.2.0 是独立版本。framework.lock.json 不匹配时停止打包，要求显式评审升级；不能静默用新包覆盖旧包。升级应在新目录保留旧源 ZIP、校验值、制品和存档副本，记录版本/依赖差异，再按上述层级重新验收。回退为恢复旧 ZIP 和已验证 Player；不要删除原存档。未来 DTO 改版必须提供明确迁移策略，当前不承诺跨 DTO 版本自动回退。M5 将验证两类获准业务工程，不能把本次参考成功外推为所有项目可迁移。

Unity API 依据：[BuildPipeline.BuildPlayer](https://docs.unity3d.com/6000.6/Documentation/ScriptReference/BuildPipeline.BuildPlayer.html)、[托管代码裁剪](https://docs.unity3d.com/6000.6/Documentation/Manual/managed-code-stripping-configure.html)、[AudioListener.GetOutputData](https://docs.unity3d.com/6000.6/Documentation/ScriptReference/AudioListener.GetOutputData.html)。
