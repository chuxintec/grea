# Unity 原生退出检查：三层独立证据

静态源代码、Editor 观察、实际 Player DLL 分别记录。任何一层都不自动替代原版对照、可维护性审查和目标平台实玩。

`unity_native_exit` 0.1.0 读取明确工程、根资产和退出策略；复用 `unity_dependency_audit` 的文本 GUID 闭包。示例策略：

```json
{"schema_version":1,"exits":[{"id":"graph-exit","relative_path":"Assets/Legacy/Graph.cs","symbol":"Graph","mechanism":"full_source_graph","reason":"运行时解释完整来源节点图，需要退役并核验调用者"}]}
```

工具 ID 经统一 `run-tool` 调度；参数为 `--project /absolute/project --root Scenes/Main.unity --policy /absolute/policy.json --output /absolute/new-report.json`。root 相对 Assets，可重复；Resources 文件加入候选根。策略是待退出机制的证据，不是豁免表，禁止 allow/waiver 字段。机制类别包括完整来源图、来源身份绑定、来源生命周期、动态配置、来源动画和来源资源目录。

已知文件/标识仍在 Player 源候选中时报告 fail；移除、改名或未命中时仍为 not_run / requires_editor_confirmation。合法 JSON DTO、存档 ID、GUID、Spine、有限业务 Tick 不因拼写被禁止。开放值映射配合生命周期/派发只列 review hint。C# 词法结果不是语义绑定；条件编译、asmref、UPM、别名、反射和计算型动态加载需后两层核验。报告含源码字节 SHA、程序集候选、待审队列、已复用的 GUID 闭包和覆盖限制。

Editor 层位于 [NativeExitEditorAudit.cs](../../tools/unity/audit/NativeExitEditorAudit.cs)。只复制到明确授权的**隔离工程**的 Editor 目录，通过既有 `unity_cli`/`unity_pipeline` 调用 `Grea.Tools.NativeExitEditorAudit.Run`，显式传 `-greaAuditRequest /absolute/request.json`：

```json
{"schema_version":1,"roots":["Assets/Game/Scenes/Main.unity"],"dynamic_roots":[],"output":"/absolute/outside-project/new-editor-report.json"}
```

它读取 CompilationPipeline 的 Player 编译集合、AssetDatabase 依赖、预加载资源和显式动态根，临时加载 Prefab/预览场景后释放，不保存资产。Editor 导入、预览与项目自身 Editor 生命周期函数仍可能写缓存，不能称为无副作用沙箱。`editor_loaded_type` 和 `editor_declared_fields` 明确属于 Editor；即使类型全名一样，也不能代替条件编译后的 Player 类型。未覆盖的 build scene 单列 issues，动态根完整性仍需审查。

实际 Player 层 `unity_player_audit` 0.1.1 使用锁定的 Mono.Cecil 0.11.6（MIT）读取 DLL 元数据，不用 Assembly.Load，不执行静态构造器，不解析依赖或加载符号。依赖来源为官方 NuGet，完整性在 `tools/unity/assembly-audit/packages.lock.json`。需本机现有 .NET 8 SDK，显式构建可选 provider：

```sh
dotnet restore tools/unity/assembly-audit/Grea.AssemblyAudit.csproj --locked-mode
dotnet build tools/unity/assembly-audit/Grea.AssemblyAudit.csproj --no-restore --configuration Release
```

工具参数 `--manifest /absolute/build.json --managed /absolute/Managed --policy /absolute/player-policy.json --output /absolute/new-player-report.json`，report 父目录须已存在。示例 manifest：

```json
{"schema_version":1,"build_id":"own-build-001","source_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","platform":"macos-arm64","backend":"Mono","assemblies":[{"path":"Own.Game.dll","sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}]}
```

必须穷举 Managed 目录直接包含的每个 DLL，支持 1–256 个完整集合；集合/摘要不符、缺失、损坏、链接或零项目类型都不能通过。策略至少指定一个实际项目类型：

```json
{"schema_version":1,"required_types":["Own.Game"],"forbidden_types":[],"forbidden_assemblies":["nunit.framework","UnityEngine.TestRunner","UnityEditor.TestRunner"],"forbidden_references":["nunit.framework","UnityEditor.TestRunner","UnityEngine.TestRunner"],"call_types":["Own.Game"]}
```

`metadata_checks_passed` 只表示这些明确检查通过；manifest 的 build/source/platform 是调用方声明，工具核验实际 DLL 集合与摘要，不为构建来源作第三方背书。调用位点仅覆盖所选类型的 call/callvirt/newobj，不是完整调用图或实际执行证据。IL2CPP 返回 unsupported，不能因为没有 DLL 就判清洁。Node、.NET/Cecil、Unity Editor 都是可选外部 provider，不自动安装进 Python 核心插件。

容量提升不改变预算：manifest 1 MiB、单 DLL 64 MiB、总 DLL 512 MiB、元数据报告 32 MiB、读取进程60秒，另有类型/方法/字段/调用位点上限。不能截断清单或漏选 DLL 绕过预算；超出时报告限制，不宣称完整检查。有限业务 FIFO 与源调度机制依据结构、所有权与真实消费者人工/专项审查，不按类名自动豁免。Editor-only 候选不代替实际 Player 元数据。

静态报告始终需后续确认：退出 1；元数据检查通过 0、发现违例/不支持 1、输入/身份/依赖/IO 错误 2。原始报告、Unity 日志与真实项目资料留项目内，公共仓库仅保留合成 fixtures 和脱敏验收摘要。

Editor Resources 补测：自动收集 Assets 下 exact Resources 目录中的文件，排除 exact Editor 目录，并与显式/预加载根去重。未引用 Prefab/SO 及间接依赖有实际遗漏失败与修复后回读；Package Resources 仍需显式根。新增对象 GUID/local fileID/类型/名称/Sprite 几何/依赖观察，可由既有 ledger compare-editor 对照；见 [制作链](unity-authoring.md)。状态仍为 editor_observed，不能签发完整原生通过。
