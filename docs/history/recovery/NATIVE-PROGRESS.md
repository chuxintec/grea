# Unity 原生进度条转换

`normalize → plan → export → native-import` 现在处理有明确几何证据的横向正向 Tiled `cc.ProgressBar`。不需要新的命令或运行时源引擎。Unity 输出包含非交互 `UnityEngine.UI.Slider` 和 `NativeHorizontalProgressFill`；后者仅持有序列化 Slider、RectTransform 与完整长度，订阅原生值变更并调整宽度。

保持已有节点、层级、图片、锚点与左边缘，不添加 FillArea、不改成 Filled 图片。完整长度取原始 `_N$totalLength`，不能用父节点宽度替代。原版 380 宽父节点、360 完整长度、60% 对应 216 宽即属此情况。View 可通过注入的 Slider 更新 `normalizedValue`。

规划要求显式原始 bar 引用、有限进度 `[0,1]` 与正完整长度、已导入 Tiled Sprite、直接子节点、左 pivot、单位缩放、无旋转，以及当前宽度与进度乘积一致。方向字段若缺失，仅在中间进度与上述几何一致时记录几何证据；端点不据此推断方向。竖向、反向、Filled、多个进度控制者、Widget/布局/动画竞争或缺资源均保留 `PROGRESS_SUBSET_HANDOFF`，不自动附加组件。该子集不代表所有 Cocos 版本的 ProgressBar 已支持。

源 Prefab 原生保存重开后，Importer 检查 Slider、driver、fill 的实际引用、进度及完整长度。helper 仅在明确选择其 `.cs` 与相邻 `.cs.meta` 时可作为原生 Presentation 辅助保留到架构候选，不自动包含未知脚本。

2026-10-27 本地证据：真实样例项目独立 42 节点子集完成 8 次保存前/重开后几何与回调检查；生产 CLI 另从两节点合成来源完整 inspect/normalize/plan/export/native-import，Unity 6000.6.2f1 编译、保存重开、引用检查及静态核验零诊断。两组输入互相独立，原件哈希未变。记录位于项目私有 `NativeProgressBinding01/` 与 `NativeProgressProduct01/`。这些是原生组件与导出流程验证；物理输入、完整游戏和视觉一致性未验收。
