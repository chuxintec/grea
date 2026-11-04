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
