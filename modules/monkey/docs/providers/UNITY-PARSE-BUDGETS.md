# Unity 解析预算与大字段分块（0.3.0.dev2）

这些是工具的资源保护阈值，不是 Unity 格式或模型 Token 限制。源对象读取仍严格检查完整字节消费、精确 TypeTree 和原始 hash；未知字段结构不猜测。`--budget-seconds` / `--provider-budget-seconds` 只控制时间。

## 显式参数

`inspect-unity` 和 Unity 来源 `convert` 共用：

|参数|默认|允许范围|
|---|---:|---:|
|`--unity-object-value-limit`|250000|1–1000000|
|`--unity-container-value-limit`|8000000|1–16000000|

计数对象是内联源数据值：字典/列表本身、元素及字段值；字典键不单独计数，PPtr 计一个值。累计范围为单个输入 bundle / data.unity3d 的全部 serialized files，每个容器重置。已分块字段以一个内联描述符计数，实际内容另受每容器 256 MiB payload 上限约束；不会因省略计数而丢弃内容。数据嵌套仍限制 96 层；单输入文件、主 typed JSON 各限制 128 MiB，主 JSON 读取统一有 6400 万节点 / 128 层结构预算。对象总数保护仍为每输入 25 万。输入或输出限制超出时明确失败/部分完成，不冒充全部解析成功。

```sh
# 显式开发入口；正式安装版的功能以其版本为准。
.venv/bin/python -m monkey.cli inspect-unity \
  --source /path/to/data.unity3d --bundle-manifest /path/to/bundles.json \
  --provider-python /path/to/pinned-UnityPy-python --out outputs/new-inspection \
  --unity-object-value-limit 250000 --unity-container-value-limit 8000000 \
  --budget-seconds 1200
```

预算写入 job、typed document、receipt；每对象记录内联/流式数据计数及对象处理前的容器用量，容器汇总内联计数、块数量和字节数。时间/RSS 单独记回执；RSS 是整个 worker 生命周期高水位，不能解释为单个容器的独占内存。

## 字体和索引的读取方式

仅在实际 TypeTree 精确证明布局时，识别 `Font.m_FontData`（单字节 char/UInt8 数组）和 `AssetBundle.m_PreloadTable`（int32 fileID + int64 pathID，12 字节 PPtr）。达到 8192 元素才流式处理，普通小数组保持既有 JSON 表达。未知类型宽度、元素对齐或版本结构使用原严格读取器，不套用固定偏移。

使用对象内有界 reader，逐个根字段读取；大字段不先创建百万项整数/字典列表，每块最多 8192 元素直接读原始字节。验证数组长度、对象边界、数组/根对齐和最终消费字节数。UnityPy 环境本身仍会解压输入容器，本实现不承诺整个 provider 恒定内存。

主 typed JSON 的字段为显式 `UnityArrayChunks` 描述符，包含长度、编码、字节序、总字节与 SHA256、连续块目录；同一对象的 `payloads` 带字段位置。所有块在 `typed-data/<container SHA>/<serialized file ID>-<pathID>-<field>/`，每块有 SHA/字节/起始索引/数量。字体字节按 uint8 保留；PPtr 保留原始有符号 int32/int64 及字节序。块由 Python `iter_payload` 或 `iter_references` 流式读取，不能把描述符当成普通字段数组，更不能只遍历旧 `references` 就声称引用齐全。

普通 `references` 保留内联引用，大索引字段的全部引用在标明编码的 payload 中，没有截断、抽样或虚构空值。主 JSON 使用有界流式编码写入，避免再次构造完整编码字符串。失败对象的未完成块回滚；成功对象保留原始对象 hash。

## 快照与工程闭包

读取器身份覆盖 worker、分块实现、预算策略和语义校验器。`--unity-reuse-inspection` 要求同一读取器合同、输入/类型结构池和预算；预算改变必须重新 inspect，不修改旧回执。每次复用、准备纹理与复制工程时逐块核对 hash/大小、连续索引和完整闭包；缺件、篡改、未知附加块直接拒绝。

生成工程将完整块复制到 `Analysis/Evidence/typed-data/`，与旁边的 typed JSON 保持相同相对寻址。块是开发期证据，不是 Player 运行时资源或解释器。主 manifest 逐项覆盖这些文件；单独复制 typed JSON 而遗漏块不是完整交付。

历史纹理准备及 AssetRipper 输出仅在其原始容器/派生字节、完整内容 manifest 等既有合同仍匹配时复用；新解析快照不冒充重新执行了旧 provider。原始资源、未知方法和原版数据始终独立保留。
