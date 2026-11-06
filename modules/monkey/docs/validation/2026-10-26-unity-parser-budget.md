# Unity 解析预算优化与样例项目复测

用户要求按已讨论方案修改并再次测试。开发版本 0.3.0.dev2；日常安装 Release 仍为 0.3.0.dev1，既有 tag/附件/安装未修改。原游戏、GREA 只读；本轮没有新建外部任务或 Agent，没有运行游戏源代码，也没有新增 Editor/Player/玩法验收。

## 修改

1. `inspect-unity` 与 Unity 来源 `convert` 新增 `--unity-object-value-limit` / `--unity-container-value-limit`。默认内联预算分别 250,000 / 8,000,000；硬上限 1,000,000 / 16,000,000。旧单包默认 4,000,000。时间预算是独立参数。
2. Font.m_FontData 与 AssetBundle.m_PreloadTable 仅在实际 TypeTree 证明固定宽度和对齐时，使用对象内有界 reader 分块读原始字节，不先扩成百万项列表。每块最多 8,192 元素；signed int32 fileID、signed int64 pathID、字节序和数组顺序保持。字体 uint8 原字节与引用表分开编码。未知布局仍走严格读取，不推断补零。
3. 每块与整体都有 SHA、长度与计数；主 JSON 保存显式 UnityArrayChunks 描述符与完整字段位置，主 JSON 也流式写出。按 job/对象/容器记录政策及实际消耗。payload 每容器最多 256 MiB，主 JSON/源输入各 128 MiB，深度与对象数保护保留。
4. 复用绑定 worker/分块实现/预算/语义验证器合同及所有输入；参数变更、块丢失/篡改/乱序/附加文件拒绝。复用、准备、工程复制和最终 freeze 均核查块闭包。工程自包含复制到 Analysis/Evidence/typed-data，manifest 逐文件封存；不会把证据块放进 Player。

具体契约与用法见 [UNITY-PARSE-BUDGETS](../providers/UNITY-PARSE-BUDGETS.md)。

## 实际复测

先对全部历史失败所在的 5 个容器定向测试，再通过公开开发 CLI 重新解析全部 601 个原容器（源/依赖 SHA 固定不变），并重新组装全量 Unity6 工程。纹理准备和 AssetRipper 输出复用上轮的完整冻结字节与派生绑定，本轮没有重新运行 AssetRipper，也没有重抓 CDN。

|项目|旧结果|新结果|
|---|---:|---:|
|原始对象|81,580|81,580|
|成功解析|80,605|81,544|
|未解析|975|36|
|预算导致的缺口|939|0|
|Font 预算缺口|4|0|
|AssetBundle 索引预算缺口|2|0|
|MonoBehaviour 累计预算缺口|933|0|

技能表现包实际需要 5,725,048 个内联值，新上限内完整解析；主 JSON 为 122,536,737 字节，仍在 128 MiB 限制内。不是无限放宽预算。全量检查 worker 实测峰值 RSS 为 969932800 字节，是整个 worker 生命周期高水位，不是每个容器独占内存；未将其与未测量的旧峰值作性能比较。

独立逐对象对比：81,580 个原始对象身份/原始字节 hash 保持，原来成功的 80,605 个对象字段值等价，新增 939 个成功，没有旧成功项回退。原已解析对象的 19 个大数组与新块按有符号 ID、顺序、编码和 hash 等价。另从原包用未分块的 UnityPy 严格读取独立重建重点 8 个数组，38,465,356 字节与块内容逐字节一致。全量最终工程包含 25 个大字段的 1116 块 / 49480972 字节，闭包完整。

318 项回归通过；新增反例包含块丢失/篡改/乱序/未知块、参数漂移拒绝、负数和 int64 边界、双字节序及原对象边界错误。75,244 个生产资产/代码/meta 文件与上轮发布候选逐文件 hash 相同，0 文件集合差异、0 字节差异。37,635 个资源文件、37,582 个资源 GUID、重复 GUID 0。887 原件 / 7,595 已取得纹理完整留存。

新恢复的两个 AssetBundle 目录使原目录条目从 63,302 增至 65,479；精确映射目标仍为 29,621。新增索引项不能冒充新增原生文件或已解决引用。

## 输出与限制

最终工程：`outputs/sample-project-parser-optimized/UnityProject`。
冻结 manifest SHA256：`[private fingerprint omitted]`。
文件：164,599；逻辑字节：3,267,184,074（比旧候选 3,307,505,149 字节少 40,321,075 字节）。最终 manifest 全文件重新计算 hash 通过。

剩余 36 个都是 MonoBehaviour 严格结构读取长度不匹配；不是预算问题，未降级 check_read 或执行源程序集。此前 425 个 CDN 键缺件、57 GUID / 17,495 处未闭合引用、原方法/业务恢复以及完整 Editor/Player/视觉仍是独立缺口。资源数量及实际生产文件未发生变化，解析完整性提升不能称为完整游戏恢复。

完整本地证据：`.private/sample-project-parser-20261026/delivery.json`、`inspection-comparison.json`、`streamed-source-audit.json`、`asset-parity.json`、`tests-final.log`；原失败回执和旧 Release 候选保留。
