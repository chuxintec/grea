# 静态组件族续接

`continue-static-prefabs` 在冻结的 Cocos 2.4.15 → Unity 6000.6.2f1 uGUI plan 上续接通用组件族。它核对输入 SHA-256 和原阶段文件清单，复制已生成的纹理、字体等自有产物到新目录，不重新 normalize，也不启动 Editor。旧 plan 和源输入保持不变。

请求使用绝对路径和小写 SHA-256：

```json
{
  "schema": "monkey-static-prefab-continuation/1",
  "schemaVersion": 1,
  "plan": {"path": "/frozen/plan/plan.json", "sha256": "<64 hex>"},
  "planManifest": {"path": "/frozen/plan/manifest.json", "sha256": "<64 hex>"},
  "ir": {"path": "/frozen/normalize/ir.json", "sha256": "<64 hex>"},
  "sourceManifest": {"path": "/frozen/inspect/source-manifest.json", "sha256": "<64 hex>"},
  "families": ["materials", "animation"]
}
```

```sh
monkey continue-static-prefabs --request /inputs/continuation.json \
  --expected-request <request-sha256> --out /fresh/continuation
monkey export --plan /fresh/continuation/plan/plan.json --out /fresh/native-candidate
```

默认族为 `materials`、`animation`。材料仅接受已有程序指纹白名单及有证明的源时刻 t=0 投影；不是通用 Shader 翻译。Animation 使用禁用的原生静态载体，保存实际 Clip 或源证据 TextAsset、槽位顺序和组件身份；部分曲线仍是部分曲线，播放与 Animator 均禁用。完整族证据写入新 plan，CLI 仅输出有界计数。

已有静态渲染 plan 可选择 `families: ["mask", "sort", "layout", "text"]`。`mask`、`layout` 和 `text` 要求附加 `sourceEngineEvidence: {"sourceVersion": "2.4.15", "files": [...]}`；每项为唯一 `logicalPath`、原版引擎文件的绝对 `path`、准确 `sha256`、`originUrl`。消费者同时核对版本白名单和实际字节，不能用其他版本的 API 默认值填补未知上下文。原版引擎文件仅作本地证据，不复制进候选或分发包。

`sort` 将实际 SortRoot/SortOrder 身份绑定到原生队列驱动，逐项检查排序字段、持久标记和驱动身份，并检查保存及加载后的完整渲染队列。`layout` 保留同节点多个 Layout 的源组件顺序，通过强类型槽位驱动 RectTransform；显式 Widget 目标必须有可证明的祖先链和 XY 几何。保存初态、原生字段回读、一次性克隆上的尺寸变化与源算法结果分别验证。未知目标或变换上下文保留精确 sourceId 缺口，不使用零值代替。

`text` 只转换源身份及字体绑定完整的同节点 Label/Outline，复用已固定的字体/SDF。系统字体与 bitmap 字体分别使用 2.4.15 的参数约定；TMP 的拟合结果不等于源 Canvas 的整数缩放算法。保存回读另存字体链、行框、实际字号和描边材质，并由主回读绑定完整文件集及哈希。缺少源操作系统、Canvas 测量和栅格化证据时，字体与视觉一致性警告继续保留。

上述续接复用已解码 PNG、字体和 Spine SDK 字节；若主生成器改变，只刷新新 plan 中的生成器 pin，要求新候选重新观测原生单位映射。旧 plan、候选和证据保持不变。诊断报告保留历史记录，另列 `resolved`、`remaining`、`remaining-dynamic` 与精确持久身份依据；对象存在本身不能解除字段、算法或文字度量缺口。

排序中的 Spine 数据交接分别识别 Unity-native binding plan 与 Cocos static rendering config。Cocos 路径核对 import-plan 内嵌配置和独立配置的原始字节，按源组件/实例/数据身份关联真实 SkeletonDataAsset，并核对持久 GUID/localID、骨架、Atlas、页纹理和材质引用。源与派生目录可以不同；骨架副本须字节一致，Atlas 仅允许有证明的页头名称替换，其余字节保持一致。

`complete-static-spine-defaults` 接受 `monkey-static-spine-default-completion/1` 请求，字段为 `schemaVersion:1`、`plan`、`planManifest`、`sourceComponentEngine`；后三者均为 `{path,sha256}`。仅接受确定的 Cocos 2.4.15 `extensions/spine/Skeleton.js` pin，保持原始字段缺省事实，另记有效 `premultipliedAlpha` 默认值及组件/数据 ID 依据。冲突值不合并。它在新目录复用已固定 PNG，逐项核对 source texture ID/SHA、PNG SHA/尺寸；只有新增的源页调用解码器，报告复用和新增计数。旧 plan、字体及已解码页不重制。

文字的源端观察入口见 [同版本源端文字参考](SOURCE-TEXT-REFERENCE.md)。历史设备状态与受控参考的验收条件分开；不能以 Unity 自己的测量证明源端保真。

`spine` 族的非渲染静态载体保留原始数据、atlas 和未解码纹理页的真实 TextAsset 引用及哈希；未序列化的字段保留未知。它不依赖渲染 SDK，不代表动态 Spine 行为或视觉还原已完成。可选 `spineRuntime` 的 `manifest` 为同样的 `{path, sha256}`，`assetsRoot` 为 SDK 备份根目录绝对路径，用于显式 SDK 来源核查。

准备完成的 `preparationStatus=prepared` 仅表示新 plan 已生成。已有诊断和部分恢复状态保留；必须继续 export、真实 native-import、保存重开回读与原有 `freeze-native-selection`。不能以续接报告替代原生验收或工程采用。

显式 `spineRendering: true` 还要求已固定的 `spineRuntime` 与 `{path, sha256}` 格式的 `spineSourceEngine`。它保留原始数据载体，并准备独立 SkeletonGraphic 的时间零姿态；PMA 未知等缺口仍保留。原 Atlas 字节留在源数据载体，渲染 Atlas 仅将页名改为解码 PNG 的文件名，适配固定 SDK 按 `Material.mainTexture.name` 查找页纹理的规则。region 名、坐标和其他字节保持一致，计划记录原始及派生 SHA、逐页纹理身份。保存回读分别记录页名、材质 GUID/localID/类型/路径及纹理、Shader、混合参数检查；托管包装对象的 `ReferenceEquals` 仅作诊断。

已有渲染计划需要更新原生 helper 时，使用 `refresh-static-spine-helpers`。请求 schema 为 `monkey-static-spine-helper-refresh/1`、`schemaVersion: 1`，接收上例格式的 `plan` 和 `planManifest`，以及可选布尔 `refreshExternalDependencies`（默认 false）。它验证完整自有清单、载体及渲染 payload 哈希，在新目录复制已有产物，仅更新包内白名单 factory、rendering、derived helper 和可从原 Atlas 严格重算的原生页名映射。显式 `refreshExternalDependencies: true` 允许刷新已知、已有所有者的依赖哈希；未知依赖、所有权变化和坏哈希仍拒绝。解码 PNG、SDK、骨骼、字体等字节复用，不调用 ASTC 解码或重新 normalize。输入篡改、映射不符及输出重叠均拒绝。

```sh
monkey refresh-static-spine-helpers --request /inputs/refresh.json \
  --expected-request <request-sha256> --out /fresh/refresh
monkey export --plan /fresh/refresh/plan/plan.json --out /fresh/native-candidate
```

刷新报告同样不表示 Editor、视觉或 Player 验收通过。

已有原生结果可使用 `monkey verify --candidate /saved/native-candidate --level editor --out /fresh/verification` 只读重验。保存后 meta 的原始生成 SHA 与 `nativeFiles` 中的保存 SHA 分开记录；仅当原生成器能逐字节重建原始 pin、GUID/importer/有效字段保持、保存字节与回读 pin 相符时，允许 Unity 省略空的 `userData`、`assetBundleName`、`assetBundleVariant`。除此之外的字节变化仍拒绝，不能跳过所有 `.meta` 差异。

同一源组件的非渲染载体与真实渲染器是两个角色，分别核对持久身份和各自证据。载体负责原字段和引用保留，渲染器负责可见初态；两者互不代替，也不改变源组件分母。保存侧证据先通过主回读中的完整文件集与 SHA 绑定，再参与角色归并；绑定失败时保留根因，不把下游未获证明的表达提升为通过。保存验证仍不代表视觉、交互或 Player 通过。


Static Spine sorting uses the same `ResolveStaticCanvasSpec` method as asset creation. Frozen Cocos JSON carries sourceDefaultScale and targetUnitsPerSourcePixel, leaving the resolved scale absent. A verified source Canvas/CanvasScaler context supplies referencePixelsPerUnit; the expected data scale is computed from these independent inputs before the factory reopens the asset. A saved asset's own scale is never used as its expected value. Invalid explicit scales, missing source facts and invalid Canvas contexts are rejected with field-level expected/actual diagnostics.

`ReadCocosStaticSpineSpecForValidation` is the production serialized-input boundary used by sorting. It verifies source/component/data identities, pinned source/derived byte closure, lossless atlas mapping, decoded texture and shader hashes, then calls the shared factory constructor/validator. Offline SDK checks may supply a JSON parser to this boundary; they establish the file/spec contract and cannot establish Unity persistent GUID, Canvas-object context, or save/reload behavior. These remain native Editor evidence.

`refresh-static-spine-helpers` accepts a frozen completed rendering stage and refreshes only the explicit factory and rendering helper allowlist. It copies all decoded PNGs and prepared fonts byte-for-byte, performs no texture decode and preserves effective source defaults. Normal export supplies current sorting helpers. Existing failed/successful candidates stay immutable; subsequent native import requires a fresh candidate directory.

A purely omitted source PMA field legitimately has an empty known-values array. The pinned version-default proof permits that empty array while requiring an unknown-field count and exact source-engine/version/component/data identities; any explicitly false value conflicts with the true default and remains rejected.


`mask` 组件族为全部源 `cc.Mask` 创建 `monkey-static-mask-continuation/1`，包括在 RenderFlow 外的未激活节点及 prefab-sync 实例。组件数与队列事件数分别记录；缺省值只来自固定 Cocos 2.4.15 `CCMask.js` 字节。请求的 `sourceEngineEvidence` 使用与 text/layout 相同的 `{sourceVersion, files}` 结构，文件描述为 `{logicalPath,path,sha256,originUrl}`，不手填 `bytes`。准备操作不启动引擎。

新导入将这些 Mask 保存为带持久身份的 Unity UI Mask。保存重开后，单独的受控预览场景复制精确 RectTransform 和 Mask 设置，以白色子 Image 检验 stencil 内外像素。PNG/JSON 位于 `Analysis/Readback/MaskClipping/`，完整清单及 SHA 固定在主回读；Python 独立检查精确源 ID、保存身份、原节点状态、清理结果、像素投影和 PNG 像素。未运行或不支持的探针保留阻塞缺口。该合成探针证明原生裁剪机制，不是原游戏帧或视觉一致性证明。

刷新还为新导入声明 `monkey-static-spine-source-canvas-context/1`：创建时记录真实 Canvas/Scaler、PPU 和源节点状态，保存及重开阶段只接受明确绑定的受控宿主，验证原始与宿主 PPU。独立 JSON 及 SHA 纳入主回读，但其组件行不重复计入 Spine renderer 分母。期待比例始终由源默认比例、生成单位和创建时 PPU 推导。

已存在的 text 组件族在刷新后声明 `monkey-static-text-isolated-sampling/1`。未激活祖先下的 Label 仅在隔离克隆中采样 TMP 字符 quad 与 Outline 材质；原源节点状态和 Label enabled 单独保存并验证未改。受控采样不激活原始业务脚本，不证明源 Canvas 像素等价。旧未声明这些证据契约的固定候选仍按其原有证据规则校验，不补造新证据。严格源版本/字段证据可以允许 TTF SHRINK 下限 0；显式 TTF 与系统 TTF 均保持字体 GUID、文本、缺字与实际尺寸边界校验。

Inactive Spine owners can use `monkey-static-spine-inactive-source-flow/1` only when the exact full source activity path through the owning Prefab root matches both persistent and loaded hierarchies under an active controlled host. This classification does not turn unreadable SDK renderer lists into empty lists. Owner/data identity and any actual child/material/texture references remain separate mandatory checks; active source owners retain the registered-renderer requirement.

刷新还声明 `monkey-static-spine-owner-context-lifecycle/1`，将 `Analysis/Readback/SpineRendering/owner-context-lifecycle.json` 纳入主回读 SHA 清单。该文件的构造登记、模板替换、排序捕获、保存重开配对与宿主释放记录用于验证对象生命周期，不重复计入 renderer 分母。组件 ID 与节点 ID 分别通过计划表关联，不从组件 ID 的序号推导所属节点。

原生实例替换在完整属性和引用重映射后、旧根销毁前，验证准确的旧/新 renderer、实例根、模板节点、数据资产和实际 Canvas 上下文；全部候选通过后才转移登记并撤销旧对象。保存资产与加载副本继续使用独立配对，释放宿主后撤销该作用域。构造期登记不能充当保存重开证据。失败时保留部分生命周期记录及原异常；完整验收仍要求真实 Editor 的保存、重开与引用结果。
