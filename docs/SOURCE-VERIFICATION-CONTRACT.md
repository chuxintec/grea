# 源组件与原生验证结果

Unity 与 Creator 的 `componentCoverage` 按完整 `plan.components` 逐项列出 `native`、`retained`、`disabled`、`unsupported`、`missing`；`convertible` 不再缩小分母。原生身份必须来自实际保存回读，静态字段、保留数据及源可见内容另需相应证据。源和原生诊断均保留在结果中。

诊断以源身份、代码、位置和原文去重，重复观察的来源及原始索引仍保留。不同字段、消息、位置或源组件不能合并。创建早期缺少原生组件的观察，可以与最终保存身份关联说明后续已有对应物；这不证明原始业务或未知字段语义已经恢复。

`disabledReason` 区分源本来禁用、静态 Button 关闭业务回调、源 Sprite 无图以及原因未知的禁用。只有来源与目标字段、实际持久身份和明确禁用边界均相符，才验证相应静态表达。Unity 的 local file ID 按非零 signed 64 位值核验；不要求正数，文本形式仅接受规范十进制整数并与组合身份交叉核对，不接受布尔值、浮点或越界数。C# Spine 侧报告的对应字段必须是 JSON 整数。Spine 侧报告直接读取保存的实例对象，并与主回读按源身份、GUID、local ID 对接，不以模板身份代替嵌套实例。

- `staticValidation` 只检查拥有文件、GUID、资源与目录完整性。
- `nativeStaticValidation` 检查全源组件的原生身份及字段；未验证或仅保留的组件不能汇总为完整通过。
- `retentionValidation` 单列身份、字段、原始资源的保留结果。
- `staticPresentationValidation` 单列源可见内容的原生静态呈现证据。非渲染 Spine 或未证明的自定义 UI 静态语义仍是 partial。
- `visualValidation`、业务和 Player 均需要独立执行证据。Editor 导入、保存、回读或截图不产生 Player 执行证明；当前这条验证链的 `runtimeCheck` 与 `playerValidation` 为 `not_run`。

`freeze-native-selection` 接受导入器的干净 `imported` 枚举，同时继续核对固定回读 SHA、原生文件、重开、全源覆盖和静态呈现。它不接收缺失分母、未完成呈现或被过滤后的原生诊断来代替这些门槛。已验证静态部分的明确纯动态边界仍单列。

默认静态 Spine 续接会在模板及每个平铺实例上创建真实类型载体，再由既有 Prefab 替换链复制字段、替换引用；同类型 Spine 组件按精确模板来源身份对应。它保留骨骼、atlas、原始纹理页和材料对象引用，不提供渲染或动画证明。

请求显式设置 `spineRendering: true` 时，还须提供 `spineRuntime` 的固定备份 manifest、资源根以及 `spineSourceEngine` 的实际同版本源文件路径与 SHA。此模式在新目录生成必要的页纹理、真实 SkeletonGraphic 与时间零初态；已有字体和 UI 纹理继续复用。数据载体保留不替代渲染器。完整源分母包括不适用或缺输入的行；可见项必须有独立保存回读的渲染器、数据、初态及非空几何和真实材料证据，不能将空节点、引用成功或载体身份当成图像。最终静态呈现、视觉比较与 Player 结果仍分别核验。

自定义 Unity UI schema carrier 的字段型 C# 声明不是原程序集完整方法清单。缺少独立原始方法来源时，即使目标原生基类能绘制，也不证明源类的渲染或生命周期语义已恢复。

引擎版本常量摘要是声明的参考 pin，不能自证实际引擎文件身份；实际源 pack、shader 阶段、脚本、资源及 SDK 字节仍按各自来源核验。63 位参考摘要已统一到规范 64 位定义，未接线历史 helper 的独立来源问题不被此修改宣称解决。

## 公开入口的保存状态与资源封存

Unity 编辑器验证、选择冻结和资源封存共用保存状态准入：实际 producer 的 imported/pass/partial、精确 Editor版本、整数0 Missing Script、editable保存重读及场景重开、规范且非空的nativeFiles清单。源图计划要求saved-source范围；仅显式gallery计划可以使用resources-and-gallery-only/not_run组合。图库证据不产生源图恢复结论。文件、GUID、组件覆盖和呈现仍由各自生产校验核对。

公开verify保留全部历史诊断，用当前证据重新判断尚未解决项。已解决诊断或已证明纯动态边界不因历史存在而使静态结果/公开退出码失败；未知诊断及静态前提缺口继续阻断。选择冻结要求完整静态分项、组件分母和身份/呈现闭包通过，不能用历史标签自行清除错误。

freeze-resource-candidate 的输出是供模块组合复用的资源库存封存，sourceAcceptance固定为not_granted；它不授予选择/产品采用许可。结构保存状态、图范围、哈希或Missing Script错误拒绝封存，退出2。通过结构准入后，保存完整当前source verification回执与validationGaps：无静态缺口的封存退出0，存在未知/未解决静态缺口时仍保留资源库存但manifest/工作流标partial并退出1。后续组合工程仍须独立编译/导入/验证；已验收选择必须使用freeze-native-selection。原始readback状态和诊断不改写，Player仍为not_run。

保存回读还须与当前拥有的import-plan字节SHA及source manifest SHA一致；这两个pin由真实Importer写出，不能由消费者把旧回读补成新证据。节点physicalInventoryContract v1记录实际GetComponents的类型继承、启用状态、GUID/localID、源角色映射及Prefab对应源链，源数据与所属Prefab明细分开核验。该库存限于源映射节点，未知自定义Graphic也按真实继承链核查；缺旧库存保持未验证。

## Independent saved scene and source Prefab observations (dev29)

The source Prefab and aggregate Candidate asset are independently saved clones. Their physical GUID/localFileID pairs are not equal and are not connected by a Prefab source relationship. `components` remains the derived source-Prefab mirror; `sourcePrefabs[].components` independently owns those details. `sceneComponents`, under `sceneComponentContract=monkey-unity-saved-scene-components/1` and `sceneComponentPhase=saved-scene-reopened`, independently observes source roles on reopened scene nodes. Its physical identity follows the actual scene-to-Candidate prefab correspondence, with an observed identityPath. Each scope proves its own complete source role denominator, owner/node/type/enabled state, static fields and physical inventory. Matching source IDs ties semantic roles across scopes; it never authorizes copying an asset GUID between them. Missing scope evidence stays partial, including historical readbacks. Owner renderer sidecars cannot manufacture scene renderer evidence; the Spine unit positives explicitly author both scopes and are not new native producer receipts.

The static Mask continuation may resolve an omitted/empty source material slot only through verified Cocos 2.4.15 engine bytes and one exact internal builtin material in the original manifest, with its existing shader/profile checks. It records `sourceMaterialResolution=engine-default-builtin` and resolver provenance alongside actual material/effect IDs. An explicit missing UUID, ambiguity or changed engine/material bytes is refused. A default rectangle Mask without the required contract still fails export before Editor.


The Unity Mask export preflight always reopens and hash-binds the original manifest and material proof; deleting optional resolver declarations cannot bypass it. Saved import instructions use a separate typed declaration check, because their native queue shape and file ownership differ from source export plans. That declaration check grants neither original-byte validation nor clipping acceptance. Only absent/null/empty optional explicit-material resolver strings compare equally after Unity serialization; required identities and nonempty default resolver pins remain exact.

A raw `SOURCE_GAPS` aggregate remains recorded. It stops blocking current static selection only when its exact count and every source-origin diagnostic index can be reconstructed and each member independently resolves or remains dynamic. A malformed aggregate, unknown source member or unresolved static member still blocks.


Controlled Unity Mask clipping is separate from source visual parity. The probe places its white Sprite relative to the center anchor so its extent includes the full source rectangle and the outside sample for every source pivot. It captures an unmasked PNG before checking the sampled pixels. The consumer derives the camera projection from source geometry and compares alpha thresholds at Unity float32 precision. The bounded image-alpha profile additionally requires an exact source-to-TextureSpec mapping, generated-owned PNG bytes, native Single/FullRect/uncompressed alpha settings, persistent Sprite/Material/shader identities and sampled RenderTexture results. The independent consumer hashes the source PNG and checks bottom-origin texel coordinates and alpha comparisons itself. Threshold zero retains alpha-zero texels because the pinned source shader discards only alpha below the threshold. Unsupported/inverted profiles, missing ownership or absent contrast samples remain explicit gaps; modeled receipts and offline compilation cannot replace real saved native rendering.
