# 同版本源端文字参考

`prepare-source-text-reference` 和 `capture-source-text-reference` 为一个原版 Label/Outline 建立受控参考。准备阶段核对原 plan、IR、manifest、2.4.15 引擎源码证据和完整 browser runtime 的字节 pin；浏览器只创建该 Label，不加载游戏业务 JavaScript。捕获阶段实际执行 Cocos Label/TTF assembler，保存 Canvas `measureText`、真实 stroke/fill 调用、字号、行布局、纹理 PNG 和浏览器截图。目标 TMP 的度量不能代替这一源端观察。

请求示例（路径均为绝对路径）：

```json
{
  "schemaVersion": 1,
  "contract": "monkey-cocos-source-text-reference/1",
  "sourceVersion": "2.4.15",
  "sourcePlan": {"path": "/inputs/plan.json", "sha256": "<64 hex>"},
  "sourceIr": {"path": "/inputs/ir.json", "sha256": "<64 hex>"},
  "sourceManifest": {"path": "/inputs/source-manifest.json", "sha256": "<64 hex>"},
  "sourceEngineEvidence": {"path": "/inputs/source-engine-evidence.json", "sha256": "<64 hex>"},
  "cocosRuntime": {"path": "/inputs/cocos2d-js-for-preview.js", "sha256": "<64 hex>", "bytes": 4935769, "engineVersion": "2.4.15"},
  "viewport": {"width": 640, "height": 360, "devicePixelRatio": 1},
  "sourceIds": ["<exact source Label ID>"]
}
```

```sh
monkey prepare-source-text-reference --request /inputs/reference.json --expected-request <request-sha> --out /fresh/source-preparation
monkey capture-source-text-reference --preparation /fresh/source-preparation/preparation.json --expected-preparation <preparation-sha> --browser-executable /existing/chromium --out /fresh/source-capture
```

完整 runtime 由调用方提供并固定 SHA；必须在实际运行中报告 `cc.ENGINE_VERSION=2.4.15`。源码文件片段或其他版本的 runtime 不能替代。runtime 保留在本地参考阶段，不加入工具源码或发行包。显式 TTF 另提供 `sourceFontFiles`，每项为 `sourceFontId/path/sha256/bytes/familyName`，必须与原始字体资产的字节身份相符。BitmapFont 捕获目前返回明确缺口；其原 `.fnt`/atlas 中的 glyph rectangle、advance、offset、line height 可直接作为数值证据，不依赖历史设备 OS。

| 证据 | 可确认的范围 |
| --- | --- |
| 原序列化字段、确定版本的引擎默认值 | 文字、字号、行高、样式、overflow/wrap、Outline 参数与缺省语义 |
| 原字体字节、FNT/图集和实际原生持久引用 | 字体/字形资源身份、字形覆盖和已声明的静态绑定 |
| 受控同版本源端捕获 | 指定浏览器、字体配置、viewport/DPR 下的实际 fitting、绘制、Canvas 度量和栅格参考 |
| Unity 保存重开回读 | 指定候选的实际原生配置、字体链、材质与网格度量 |

受控源参考与目标回读必须按 source ID、文字/字段 pin、字号、viewport/DPR 和明确比较范围配对，再记录差值或视觉结果。捕获成功本身不等于目标一致。历史设备的 OS、字体选择和像素输出属于来源说明；无法从包内恢复这些历史状态，不应阻止建立和验收明确声明环境的同版本参考。包内事实、受控比较、原设备一致性分别报告，保留原始警告历史。

目标侧现有 `inkBounds` 字段保存的是 TMP character quad 的局部几何边界，另以 `nativeBoundsKind=tmp-character-quad-local-bounds-not-pixel-ink` 明示语义；它不是着色后像素墨迹，也不能直接与 Canvas `actualBoundingBox` 或包含描边的栅格边界判等。字号/行数、几何与像素比较须分别取证。`SYSTEM_FONT_PLATFORM_UNVERIFIED` 留作历史来源说明，不单独阻塞原生静态验收；实际源端度量、字形或栅格缺口仍保留相应门槛。
