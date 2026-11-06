# 2026-10-22 奖励窗口字体与原生 UI 续包验收

状态：离线候选已更新；Editor、同状态画面对照、真实输入与业务仍为 **not_run**，v0.1 出口未通过。本文补充首批记录，不覆盖其历史结果。

| 验证层 | 本次证据与结果 |
|---|---|
| 冻结输入 | 36 项来源资产，48 节点、82 组件；20 份来源加 1 份脚本证据的 SHA-256 回算不变 |
| 原字体 | BitmapFont 90 字形、44 组字距及 RGBA 图集；原 zh-bold TTF 3493 字形，cmap 覆盖所需中文 |
| 字体绑定 | 3 个中文 Label 按冻结脚本 zh 字体策略人工绑定；绑定受来源清单及脚本 hash、字节范围约束；2 个数量 Label 保留原位图字体。未执行或自动翻译脚本 |
| 原生结构候选 | 48 个组件，包括 13 个源空 Sprite 的禁用 Image；5 处文字及必要布局、遮罩、静止滚动区、按钮缩放候选。不是 Editor 导入结果 |
| 旧资源稳定性 | 与 04 号候选共同的 44 份 art/meta 内容 hash 与 GUID 不变 |
| 定向检查 | 新增 Bitmap/UI 4 例、TTF cmap 2 例与受影响目标输出 4 例通过；合成字体仅检验格式与绑定合同，不冒充字体渲染 |
| C# API 检查 | 实际导入适配器及 View 对现有 Unity 6000.6.2f1、uGUI/TMP 程序集离线编译通过，源 hash 匹配；未启动 Editor |
| 分发检查 | 本地 wheel 47807 字节、21 个成员；移出源码路径后导入成功，包含资产模块、C# 模板与许可，不含私有样本 |
| 静态校验 | 最新候选 61 个文件，清单与引用闭包通过；stage 清单、IR 和资产篡改保护已验证 |
| AI 交接 | 160 条原始诊断聚合为 8 组模块/根因任务；未知脚本、排序、点击业务保持待接入 |
| Unity 实际验证 | not_run；等待总监明确释放独立窗口，未产生实际 Prefab/Scene 或原生 PNG |

## 证据路径与身份

以下文件在本项目内隔离并被 Git 忽略，不纳入发行包：

- `.private/reward-inspect-06/source-manifest.json`：冻结来源与脚本证据。
- `.private/reward-font-bindings.json`：人工核对的字体绑定依据。
- `.private/reward-ir-11/ir.json`、`.private/reward-plan-09/plan.json`：原生映射前的语义与转换计划。
- `outputs/unity-reward-10`：本次候选；对应 `-static`、`-editor`、`-handoff` 为检查与交接回执。
- `.runtime/adapter-compile-15/report.json`：C# 窄编译回执。
- `.private/font-probe-01`：标注为 OFFLINE 的字形度量探针，不能当作 Unity 页面截图。
- `.runtime/wheels-continue01-final`、`.runtime/wheel-continue01-extracted`：本地 wheel 和移位导入检查。
- `.private/continue01-receipt-10.json`：成组机器回执。

候选 manifest SHA-256：`[private fingerprint omitted]`。

wheel SHA-256：`[private fingerprint omitted]`。

## 剩余门槛

得到明确的最多 12 分钟独立窗口后，导入候选并保存/重开，回读字体 GUID、字形四角、Image 边距、节点矩形及 View 数组 fileID，检查可编辑克隆并捕获真实 Unity PNG。相关检查代码已备，尚未执行。BitmapFont 当前仅支持单行；缩放后非零字距、非均匀 Grid、动态滚动及其他未支持条件显式留缺口。真实 TTF 描边尺寸和源页面画面对照仍待核验。

用户已直接授权本聊天向总监发送进展与窗口申请；已送达且总监核对候选 hash。该授权不等于 Editor 窗口授权，也不代替向样例项目协调的授权。
