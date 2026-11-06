# 2026-10-25 Cocos / Unity 输出完整性与命名审计

## 结论

**本次已取得的原件全部保留，未发现原件漏存；Cocos 的生产资源导出尚不齐全。** 主要缺口是音频：Unity 生产目录有 356 个 MP3（276 种内容），Cocos 只有 17 个（17 种内容）；259 种音频内容只在 Cocos SourceRecovery 保留，没有进入 assets。静态验证 pass 不能证明两端资源类别覆盖一致。

**共有资源命名总体一致，但未完全满足全部格式限制。** 11,808 个相同身份/类型的资源映射，其文件主名完全一致；914 份代码草稿主名也一致。目录有意采用 Unity PascalCase 与 Creator kebab-case。存在超长文件名及小写开头草稿，详见下文。

本轮只读核查输出和原件，不改资源、不重新导出、不启动任何 Editor，也未修复下列问题。

## 1. 对比范围与文件完整性

当前输入合同：样例项目 1.9.1 / Cocos 2.4.15，`Analysis/v11-monkey-integration-20261024/inputs.json` 指定三个目录。独立遍历物理文件，再逐项核对源 SHA256、两个候选保留文件和 Unity 原生副本保留文件，不只读取旧台账数字。

| 输入根 | 当前物理文件数 |
|---|---:|
| Evidence/source | 17,097 |
| Analysis/package-snapshot | 101 |
| frozen-derived-inputs | 3 |
| 合计 | 17,201 |

总字节 884,709,704。三份工程的源台账均与物理目录完全一致：0 漏项、0 多项、0 源变更、0 保留文件字节错误。去重后各有 16,173 个原件保留路径；去重不是丢文件。

原始两个 wxapkg 的大小和 SHA 与捕获清单一致，也包含在上述保留集合中。其封装不被当前 monkey 明文 wxapkg reader 直接识别，本轮未再次解密/解包；已经取得的解包快照 101 文件进行了独立遍历与输出核对。范围不涵盖未知服务器数据或未取得远端内容，不能据此声明原厂完整内容全部获取。

| 项目阶段 | 文件夹 | 文件（含 meta/证据/工具） | 完整性结果 |
|---|---:|---:|---|
| Unity 离线候选 | 6,002 | 65,560 | 65,559 个清单文件及 manifest 完整，0 哈希错误/未知文件 |
| Cocos 离线候选 | 5,915 | 63,897 | 63,896 个清单文件及 manifest 完整，0 哈希错误/未知文件 |
| Unity 原生导入副本 | 6,522 | 76,391 | 30,599 个原生记录文件哈希一致，原件保留核验通过 |

Unity 原生统计排除 Library、Temp、Logs、UserSettings、obj、.git 缓存/本机设置。Creator 尚未原生导入，不能用它与 Unity 导入后生成的 Prefab、Scene、Controller、Material、folder meta 数量直接比较。

两个离线候选的 Analysis 都有 22,452 文件，SourceRecovery 都有 23,290 文件。生产根分别是 Unity Assets 19,808 文件、Cocos assets 18,133 文件；Unity 原生 Assets 30,612 文件。这些总数包含 meta，不等于逻辑资源数量。

## 2. 内容差异：哪些正常、哪些是缺口

| 类别 | 对比结果 | 判断 |
|---|---|---|
| BON 配置 JSON | 两端各 528；逐身份/顶层键 SHA 完全一致 | 齐全、内容一致 |
| 已物化共同 JSON/字符串 | 548 个 config 映射、3 个 strings 映射 SHA 一致 | 无内容差异 |
| Spine | 两端各 1,776 个闭包，成员文件名和 SHA 一致 | 文件闭包一致；未装运行时不等于可播放 |
| 共同 Sprite | 5,850 个 SHA 相同；2,617 个 SHA 不同 | 后者按 Creator 声明 trimOrigin/size 裁切后，与 Unity 像素全部相同，0 错误 |
| Unity 额外 PNG | 485 个 _untrimmed 派生图 | 正常；Creator 使用原尺寸画布与原生裁切，无需同名副本 |
| 代码初稿 | 两端各 914，源身份集合和文件主名完全一致 | C# / TypeScript 的目标语言差异；不是已恢复业务代码 |
| Animator Controller / TMP / Material | Unity 专用生成类别，Creator 使用对应内建表示；Creator 另有 5 个 FNT | 不能按文件数认定漏导 |
| 源 Prefab/动画 | 两个离线候选只有原生生成计划；Unity 导入后实物化，Creator 未执行 | 未原生生成，不是原件丢失 |
| **音频** | Unity 356 MP3/276 种内容，Creator 17 MP3/17 种内容 | **259 种内容未进入 Creator assets**；对应 338 个 Unity 路径，原件仍在 Creator SourceRecovery |

### 音频缺口原因

`src/monkey/handoff_package.py:45` 的 consumed_inputs 将共享 IR 中所有 native 载荷都视作已被输出消费，没有区分目标引擎。`src/monkey/package.py:318` 因而把对应音频改为只保留证据。Unity 有 AudioClip 输出，Creator `src/monkey/targets/cocos.py:59` 仅处理字体/JSON，其余给 ASSET_HANDOFF；Creator 音频不会完整进入 assets。

此外，台账部分仍称 native_plan_pending_import，容易误导。应按目标实际支持/已输出资产决定 consumed 状态，并补齐 Creator 音频导出及逐目标覆盖检查。本轮只记录，未修改工具或输出。

示例缺口：`bgm_merge.mp3`、`sfx_backpack_in.mp3`、`sfx_backpack_off.mp3`。逐文件路径和 SHA 见 [Creator 音频缺口](../../.private/export-parity-audit-20261025/creator-audio-gap.json)。

## 3. 命名是否一致

| 项目 | 结果 |
|---|---|
| 共有资源文件主名 | 11,808 对，0 差异 |
| 代码草稿文件主名 | 914 对，0 差异，仅 cs/ts 后缀不同 |
| 中文路径 | 两候选及 Unity 原生工程均为 0 |
| Unicode NFC/大小写冲突 | 0 |
| 模块目录大小写 | Unity 首字母大写；Creator 小写；0 大小写违例 |
| 长目录映射差异 | 43 对，全部可由 Creator kebab 分隔符增加长度、64 字节截断加 hash 解释 |
| 映射路径超过 180 字节 | 0 |
| **文件名含扩展名超过 64 字节** | Unity 候选实际 22、Creator 候选实际 18；Unity 导入后实际 36。全部计划中 Unity 123、Creator 118，最长计划段 86 字节 |
| 草稿 PascalCase 例外 | 两端均 18 份文件主名以小写字母开头；两端一致，但不满足规范的 PascalCase 目标 |
| 符号保留 | 计划名 Unity 42、Creator 32 保留括号、+、#、×、∞ 等。它们不是中文，也不全是操作系统非法字符；属于源名/非 ASCII 保留规则与严格字母数字风格间的例外，不能简单当作漏导 |

长度问题来自 stem 先按 64 字节裁切后再添加扩展名，以及碰撞时再追加 owner/hash；`layout/allocate.py:136` 没有对最终文件名重新限长。例如 `elements_sparks_069_hit_star_explosion_radial_no_ct_no_rs_0d21fa.png` 实际为 68 字节。需在保留引用和稳定身份的前提下按最终名称预算处理。

## 4. “1,521 缺失引用”重新分类

旧 `cocos-assets.json` 以 sourceFiles 是否为空标记 missing_reference；跨包重定向自身没有直接文件，因此被误计。

- 1,517 项有显式 redirectTarget，并可在另一个 bundle 定位相同 UUID 及原件，**不能称为漏导文件**。
- 仅 4 个 UUID 在全部已提供 bundle 中未定位；均在 main，缺类型和 logicalPath，当前资产 references 表未发现引用。它们是未闭合身份，不足以证明丢了 4 个真实文件。

```
[private identifier]
[private identifier]
[private identifier]
[private identifier]
```

旧 missingReferences=1521 应拆为重定向已解析与身份未定位计数，见 `src/monkey/package.py:233`、`:389`；本报告纠正其解读，不改写冻结输出。

## 5. 后续修复优先级

1. 补齐 Creator 259 种音频内容进入生产 assets；按目标实际输出修正 consumed/覆盖状态。
2. 最终文件名连同扩展名/碰撞后缀一起限长；补草稿类名与文件名一致的 PascalCase 规则。
3. 修正 missingReferences 统计，保留 4 个未知身份的明确状态。

本轮完整机器结果：[summary.json](../../.private/export-parity-audit-20261025/summary.json)。完整文件夹/文件清单、音频缺口、命名例外、逐像素比较、跨包引用证据均在同目录。输出工程保持原样。
