# CLI contract v1

版本 0.1.0（开发中）。所有业务命令 stdout 为单个 `beaver-result/1` JSON，包含 operationId、producer/version/implementationSha256、status、data、artifacts、actualChanges、diagnostics、limitations、verification。
退出 0=ok；3=计划有冲突 blocked；2=无效输入、前置条件失败或执行失败。帮助为 argparse 文本；没有任意 shell 透传。

| 命令 | 参数 | 效果 |
|---|---|---|
| `version` | 无 | 版本和实现内容身份 |
| `capabilities` | 无 | 实际能力、provider 和验证状态 |
| `doctor` | `--editor-path` 可选 | 仅本地存在检查；不启动引擎、不探测认证 |
| `project inspect` | `--project`、可选 `--assets` | 引擎、编辑器、依赖；可选资产大小及 GUID/UUID 重复检查 |
| `adopt plan` | `--candidate --target --out`，首次 `--baseline`，可选 `--lineage` | 输出独立计划；目标/候选只读 |
| `adopt apply` | `--plan --expected-plan --out --editor-path`，可选 `--timeout` | 原生应用、独立重开、状态记录 |
| `adopt rollback` | `--transaction --editor-path`，可选 `--timeout` | 仅恢复事务仍拥有的改动；后续变更拒绝 |
| `image inspect` | `--input` | PNG/静态图片尺寸、alpha、RGBA 与文件 hash |
| `image compress` | `--input --output`；执行另加 `--apply --expected-source` | 默认预览；PNG 无损重压缩，输出新文件 |
| `config validate` | `--schema --input` | 严格标量 JSON、重复键/ID、范围与字段检查 |
| `config generate` | `--schema --out` | 新独立目录内生成 C# DTO 与运行时 TextAsset JSON 读取器 |
| `code inspect` | `--project` | asmdef 名称/GUID引用及using清单；不代替编译 |
| `unity plan` | `--project --spec --out` | 冻结显式原生操作与整个源文件身份 |
| `unity apply` | `--plan --expected-plan --out --editor-path`；可选 `--timeout` | 执行限定原生操作、保存重开及源审计 |
| `player run` | `--manifest --expected-manifest --out`；可选 `--duration` | 核全部制品身份后启动自有进程，限时退出/停止；不授予业务通过 |
| `payload verify` | `--root --manifest`；可选 `--scope --allow-unlisted` | 流式文件/大小/哈希/独立inode及别名检查；未覆盖项默认拒绝，显式允许仍为partial |
| `payload plan` | `--root --manifest --target --out`；可选成对`--overrides --override-root` | 冻结来源、覆盖前后身份、别名与独立目标；不写最终目标 |
| `payload apply` | `--plan --expected-plan --out` | 验证独立临时树后原子晋升；不覆盖现存目标，不就地改来源 |

计划文件 `adoption-plan.json` 使用 `beaver-adopt/1`，旁侧 `plan-identity.json` 绑定字节 SHA256。绑定实现身份、明确根、生成基线、目标全部资产 hash、项目依赖/版本、candidate manifest、逐项动作/冲突与恢复信息。执行需相同计划身份；任何目标前置漂移拒绝。

输入消费 monkey schemaVersion=1 `manifest.json` 或 Unity `recovery-manifest.json`；候选规范沿用 monkey-project/2.0.0，未新增第二解析器。目标 Unity 6000.6.2f1 和 Creator 3.8.8 可预览；只有 Unity 有原生执行实现（尚待本项目实证）。Creator apply 明确不支持。

首次必须独立共同基线；按 GUID/UUID + namespace + profile 三方比较。保留人工变更和源删除资产；双边变更、身份歧义、未知占位、依赖不匹配均阻止执行。原生移动使用 AssetDatabase，改变 payload 时使用 Unity 导入，检查 GUID/localID 与至多128个未改 prefab/scene直接依赖。字符串加载键和业务/视觉不由此保证。

`project inspect` 默认不扫描/重复 hash 大资产。`--assets` 扫描元信息；严格采用预览和执行逐流 hash 候选及目标，预算8GiB/500000文件/单文件512MiB，清单128MiB。输出不得与输入重叠。不存在隐式全局配置、自动安装或升级。

`--version` 等价于 `version`。统一状态保留 partial/failed/not_run，退出分别1/2/3。失败事务包含journal引用，不能根据actualChanges空数组推断零写入。旧 `monkey-adopt/1` 计划不重放；已有`.monkey/adoption`状态明确拒绝隐式迁移，旧事务继续用原monkey版本恢复。beaver不修改旧状态。

## 原生 spec 子集

所有 spec 都是 schemaVersion=1 的封闭 JSON；未知操作、节点类型、组件/字段和路径拒绝。

| operation | 必填字段 | 原生行为和范围 |
|---|---|---|
| `ui.create` | prefabPath、scenePath、fontAssetPath、sourceFontPath、width、height、nodes | 新建可编辑uGUI/TMP窗口；节点panel/list/button/text/image，列表为固定VerticalLayoutGroup，不声称ScrollRect；显式工程字体生成TMP资产；需既有TMP Essentials shader/settings |
| `prefab.inspect` | prefabPath | 原生层级、父级、组件、Transform localID、字体、Sprite GUID/localID及几何读回 |
| `prefab.edit` | prefabPath、edits | 现有节点/唯一组件的SerializedProperty字符串/布尔/整数/浮点/对象绑定，保存和重开检查；Variant明确拒绝，结构/脚本身份字段禁止 |
| `assets.move` | moves:[{source,target}] | 原生逐文件移动，GUID/localID及重开一致；禁止目录/环/占位；目录由原生API创建 |
| `project.import` | 无其他字段 | 编译并导入已写入的源文件；计划列明缺失meta路径，既有源改动拒绝；不加包 |
| `sprite.configure` | assetPath、pixelsPerUnit、pivot、maxSize、alphaIsTransparency | PNG→单Sprite，固定无mipmap/Uncompressed，原生Importer参数/身份/像素几何读回；只允许该meta变化 |
| `validate.play` | scenePath、durationSeconds | 显式场景1–30秒PlayMode，记录真实帧数和错误；不判业务或物理输入 |
| `build.macos` | scenes、productName | BuildPipeline StandaloneOSX，整个Assets/Packages/ProjectSettings源身份保持，生成sourceSha256绑定的逐文件制品manifest |

`ui.create`可显式给tmpSettingsPath新建项目TMP设置，但不导入shader、不覆盖既有设置；通常应先由开发者完成官方TMP初始化。首次场景可能生成的SceneTemplateSettings.json会在计划中显式列出。字体只预装既有声明文本和ASCII，缺字拒绝；多语种、复杂动态布局/业务事件由开发Agent处理。按钮不会被注入空业务回调。

`prefab.edit` 的标量value为不变区域字符串；对象绑定用显式assetGuid/localId或targetNode/targetComponent。图片引用匹配具体Sprite localID，不靠图片文件同名猜测。正式JSON仅支持必填scalar int/double/string/bool；生成读取器要求项目已存在官方`com.unity.nuget.newtonsoft-json`，缺包不会自动安装；没有Excel、SO数值副本或任意代码重构。

工程采用具有原生回滚；普通unity操作失败保留journal/before-image并标recovery-required，不提供自动通用回滚。`assets.move`可按新计划反向移动；未知后续改动不能据旧计划覆盖。原生检查和PlayMode/Player不代替完整游戏功能、视觉或发布许可。

## Payload 与同事交接机制

`beaver-payload/1`：`schemaVersion:1`、`files:[{path,bytes,sha256}]`、可选`aliases:[{id,path}]`。别名ID是区分大小写的不透明标识，不访问URL、不解析外部游戏路由协议。多别名可指向同一载荷；重复别名、重复目标、Unicode/大小写目录碰撞、文件/目录前缀冲突、越界、符号链接和hardlink默认拒绝。构建/Player内部仅接受清单明确声明且仍位于制品范围内的链接。

覆盖清单：`schemaVersion:1,entries:[{path,target,source,expectedSha256,sha256,bytes}]`，source相对于明确override-root。旧hash必须匹配基线，所有指向旧path的别名统一转至target；默认保留旧载荷，显式同路径覆盖仅发生在新副本。输入、输出、计划与事务目录不得重叠。采用源协议的转换留给monkey/Agent；私有route-map和原游戏素材不进入beaver。

物化先生成独立inode的临时树并核验完整清单，再使用macOS `RENAME_EXCL` 原子晋升。并发创建的空目录也保留；失败时最终目录不含半成品，临时树和journal留供检查。Linux/Windows晋升代码尚未原生验收，不因macOS通过而外推。固定34003/307、游戏路径、WebView/WASM、vendor二进制均未接入。

构建后与Player启动前/退出后共用此核验器。运行回执增加实际可执行hash、UTC开始、pid、时限、独立证据目录及清除的旧引擎作业变量。独立日志目录与进程不等于隔离玩家存档；存档隔离必须由项目适配并另行证实，本版明确不声称已提供。
