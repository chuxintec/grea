<!-- 生成副本，勿直接编辑。权威来源：docs/providers/unity-authoring.md；由 scripts/skill_closure.py 维护。 -->

# 有限 Unity 制作链

`unity_config_candidate` 与 `unity_native_assets` 0.1.0 是离线候选制作工具。Editor 伴随脚本通过 Unity API 创建原生资产，仅在授权的隔离工程执行。它们不解析整个源引擎、不提供源节点运行时。

## 强类型配置

```sh
grea run-tool '{"tool_id":"unity_config_candidate","arguments":["--schema","/absolute/Enemy.schema.json","--input","/absolute/Enemy.rows.json","--output","/absolute/new-candidate"],"run_dir":"/absolute/new-run"}'
```

Schema 为 `schemas/unity-config-authoring.schema.json`：显式 namespace、类型名、唯一行 key 和有限字段。首批只支持 int32、bool、string 和可空 string；范围、缺字段、多字段、重复 key、无效 C# 名字全部在写入前拒绝。缺值、null、空串、false、0 不相互代换。Unity 会把序列化 null string 变为空串，因此可空字段生成“值＋是否有值”的私有序列化字段和强类型只读属性；不靠运行时 JSON 补救。

输出包含强类型 `*Table.cs`、Editor-only 导入器、`authoring.json`、原始语义 `source-rows.json` 与 `generation.json` 哈希清单。将 C# 文件复制至自有工程，Editor 文件放 Editor 编译域；authoring 留 Assets 外。导入方法 `Namespace.Editor.NameImport.Import(authoringAbsolutePath, newAssetsPath)` 只接受生成时锁定的 authoring 字节，并拒绝覆盖 SO。候选目录完全相同时重跑返回 unchanged；任何人工改动、额外文件或输入变化都会冲突，选择新目录审查，不自动覆盖。每张表保留一个制作源，示例 JSON 为制作源；SO 是生成的运行资产。

自有两类 schema 和 Editor/Play 验收源码在 `tools/unity/fixtures/native-authoring/`。候选不是已导入的游戏配置；不支持的嵌套字段、Excel、任意源 TextAsset 压缩或游戏分隔方言明确不推断。

## Sprite 与动画

```sh
grea run-tool '{"tool_id":"unity_native_assets","arguments":["prepare","--recipe","/absolute/native.recipe.json","--output","/absolute/new-native-candidate"],"run_dir":"/absolute/new-run"}'
```

输入 Schema 为 `schemas/unity-native-assets.schema.json`。Sprite rect、offset 均为源图左上角像素；rotated_cw 表示源裁片顺时针旋转，制作时逆转并恢复原尺寸透明画布；pivot 为原画布左下归一坐标，border 顺序为左、下、右、上。九宫格不得超过原尺寸。PNG 和 request 都进入生成身份，预检图像、总像素/字节、路径、重复名称和人工冲突。

动画只支持显式 Transform 目标、绝对 local position/scale、线性关键帧、明确循环和 `Pulse()` 事件契约。目标初始 scale 不被假定为 1。每条曲线严格覆盖 `[0,duration]`，未知属性/事件、缺目标、重复路径/绑定、非有限值和乱序关键帧拒绝。源引擎曲线、坐标或时间语义需要项目先明确转换为本契约。`Pulse` 接收器由游戏提供；这里不生成通用生命周期层。

将 `tools/unity/audit/NativeAssetImport.cs` 复制到隔离工程 Editor 目录，通过已有 unity_cli provider / Unity CLI 调用：

```sh
unity run /absolute/own-project --timeout 300 --format json -- -executeMethod Grea.Tools.NativeAssetImport.Run -greaNativeRequest /absolute/candidate/native-request.json -greaNativeRoot Assets/NewNative -greaNativeReceipt /absolute/new-receipt.json
```

目标 Assets 目录必须不存在。生成原生 TextureImporter/Sprite、AnimationClip、AnimatorController、Prefab；Player 不读 recipe。导入失败保留部分输出与失败回执，不宣称事务成功，重新执行需新的目标目录。创建后的人工编辑通过 Inspector/API 保存，可直接 Play；再次转换不会覆盖它。删除 Editor 转换器后仍可使用原生资产。通用工具不自动控制 Editor、安装插件或发起构建。

## Editor 台账与回执

`NativeExitEditorAudit.cs` 的独立观察包含 Resources（Assets 下、排除 Editor 段）、preloaded 与显式根的递归依赖。报告对象 GUID/local fileID、实际 Editor 类型/名称、Sprite rect/pivot/border/PPU 和对象依赖身份。Package Resources 须显式传入。Editor 类型始终为 editor_observed，不是 Player 元数据。

既有 `unity_asset_ledger compare-editor --before ... --after ... --output new.json` 比较这些观察，报告新增/消失身份及路径、类型、几何和依赖变化；所有变化都需审查，不自动批准迁移。原有 snapshot/compare/check-plan/verify-moves 不变，字节和 meta 审查仍用原功能。回执含唯一 run ID、请求/源哈希、输出哈希；外层命令成功与业务断言分别保留。规则轨迹继续使用 compare_events/compare_traces。

## Spine 边界

`unity_native_assets spine-check --skeleton ... --atlas ... --runtime-line 3.8` 仅检查有限 text atlas 页闭包、文件哈希和 skeleton major.minor。自有两页和缺页反例有测试；缺页 exit 1，版本不匹配 exit 2。闭包通过不代表 region/渲染或 runtime 许可。不会安装、复制或修改 Spine Runtime。

本机观察到的项目 runtime 包含项目兼容修改，许可证要求单独满足 Spine 授权条件；尚无确认可用于本批独立分发的 pristine 匹配 runtime 与授权证据。因此 Spine 原生导入/Player 渲染保留 not_run，不能把闭包检查写成完整 Spine 转换通过。

自有可见渲染补验使用显式相机与原生 SpriteRenderer：五个动画相位、每相位 25 项颜色/透明边/pivot/九宫格及可见动画像素断言，并另验移除转换器的实际 Player backbuffer。复现步骤见 样例（GREA 安装目录 `tools/unity/fixtures/native-authoring/README.md`）。这些是自有有限契约验收，不能替代原游戏画面对照或真实鼠标输入。

## 审计后的导出边界

`unity-export-config` 默认只导出实际观察到的 TextAsset 身份、字节和 JSON；显式 `--adapter level-datas-v1` 才检查旧业务表关系。缺少必需表返回 not_applicable。逻辑路径来自 provider container，缺少时为 null；不会拼造 `Assets/Resources` 路径。

UnityPy 用 surrogateescape 表示非 UTF-8 TextAsset 字节时，导出器按相同编码恢复原 bytes。真实 Unity 6000.6.2f1 的自有无 TypeTree Bundle 已验证二进制和两种 JSON 结构；同版本含 TypeTree 的测试 Bundle 在当前锁定 UnityPy 上解析失败，记录 provider_decode_failed，不宣称已支持。此限制须通过 provider 更新或官方 Editor 读取路线另行解决，不能用零张表伪装成功。
