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

`spine` 族的非渲染静态载体保留原始数据、atlas 和未解码纹理页的真实 TextAsset 引用及哈希；未序列化的字段保留未知。它不依赖渲染 SDK，不代表动态 Spine 行为或视觉还原已完成。可选 `spineRuntime` 的 `manifest` 为同样的 `{path, sha256}`，`assetsRoot` 为 SDK 备份根目录绝对路径，用于显式 SDK 来源核查。

准备完成的 `preparationStatus=prepared` 仅表示新 plan 已生成。已有诊断和部分恢复状态保留；必须继续 export、真实 native-import、保存重开回读与原有 `freeze-native-selection`。不能以续接报告替代原生验收或工程采用。

显式 `spineRendering: true` 还要求已固定的 `spineRuntime` 与 `{path, sha256}` 格式的 `spineSourceEngine`。它保留原始数据载体，并准备独立 SkeletonGraphic 的时间零姿态；PMA 未知等缺口仍保留。原 Atlas 字节留在源数据载体，渲染 Atlas 仅将页名改为解码 PNG 的文件名，适配固定 SDK 按 `Material.mainTexture.name` 查找页纹理的规则。region 名、坐标和其他字节保持一致，计划记录原始及派生 SHA、逐页纹理身份。保存回读分别记录页名、材质 GUID/localID/类型/路径及纹理、Shader、混合参数检查；托管包装对象的 `ReferenceEquals` 仅作诊断。

已有渲染计划需要更新原生 helper 时，使用 `refresh-static-spine-helpers`。请求 schema 为 `monkey-static-spine-helper-refresh/1`、`schemaVersion: 1`，只接收上例格式的 `plan` 和 `planManifest`。它验证完整自有清单、载体及渲染 payload 哈希，在新目录复制已有产物，仅更新包内白名单 helper 和可从原 Atlas 严格重算的原生页名映射。解码 PNG、SDK、骨骼、字体等字节复用，不调用 ASTC 解码或重新 normalize。输入篡改、映射不符及输出重叠均拒绝。

```sh
monkey refresh-static-spine-helpers --request /inputs/refresh.json \
  --expected-request <request-sha256> --out /fresh/refresh
monkey export --plan /fresh/refresh/plan/plan.json --out /fresh/native-candidate
```

刷新报告同样不表示 Editor、视觉或 Player 验收通过。
