# 资产总览、来源与规格

[工具为独立实现，方法来源和许可见第三方说明](../../THIRD_PARTY.md)。继续使用art-ledger，不另建来源台账。每条记录新增可选provenance：source_url、creator、license、license_reference、restrictions、generation_tool/tool_version/model、prompt_reference、source_references；未知保留缺省/明确unknown，不要求老项目伪造许可。版本、来源及许可是声明，工具不自动确权；不在公开仓库存完整私有提示词。

设计brief记录功能用途、引擎/相机/显示尺寸、画布/透明、原生尺度读图、视觉锁（轮廓/色板角色/视角/光照/边缘/运动）、状态/变体、资源预算及验收。先沿已有设计挑代表样板，授权后按资源族制作；生成结果不等于可交付。原图、切片、Spine及目标引用沿现有台账维护。

```sh
bin/grea legacy image_contact_sheet --manifest /path/images.json --output /path/new-sheet --font /path/font.ttc --columns 4
bin/grea legacy image_alpha_audit --images /path/a.png --output /path/new-audit.json --expect-size 64 64 --max-colors 48 --require-transparency
```

联系表输入：`{"schema_version":1,"images":[{"id":"图标一","path":"icon.png"}]}`，路径相对manifest，标签唯一（大小写/Unicode归一）且≤64字符，数量1..128。不扫描整盘；拒绝链接、越界、多帧。非ASCII标签需显式提供支持该字形的字体（≤128MiB）；仍须实际打开图核字形。预览统一格默认192×192，仅缩小、等比、nearest；`--native-size`保留原像素，各自位置/尺寸及比例写入sheet.json。输出为新目录sheet.png/sheet.json；总输入≤4000万像素，单图≤2000万，表≤2000万且边≤16384。原图不变，输出不能覆盖/混入原始证据。

alpha工具旧参数保留。expect-size为显式宽高；max-colors仅像素/调色板任务启用，按精确RGBA（含alpha差异）计数，超过上限一个颜色同样失败，超出可计范围只报告溢出。HD渐变图默认不限制颜色。透明通道存在不等于有效透明；原有全透明/透明像素/边缘/hash检查保留。规格和静态联系表不能替代游戏内尺寸、pivot、动画、交互与画面对照。
