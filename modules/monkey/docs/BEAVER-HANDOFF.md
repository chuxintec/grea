# beaver 工程采用实现交接

状态：**本地冻结交接已接收；beaver 0.1.0 本地验收已复核，旧消费者切换仍待核验**。来源是 monkey `0.5.0.dev1`；稳定安装仍为 `0.4.0`。用户批准来源与职责见 PLAN、PROJECT-SPEC 和 internal planning reference 三产品合同。本材料不授权启动暂停游戏或修改正式开发工程。

## 不可变来源

本批代码、测试和文档提交于 monkey 本地仓库；准确 commit、tree、逐文件 SHA256、源码归档 SHA256 记录在 `.private/v050-adoption-20261026/beaver-handoff/freeze.json`，归档为同目录 `monkey-0.5.0.dev1-source.tar.gz`。接手方先验证归档及逐文件清单，再从固定快照提取。不能从当前可变 checkout import，不能让两方同时修改同一模块。快照包含产品代码/合成测试，排除 `.private`、`outputs`、原包/玩家档/真实游戏资源。

自有代码为 MIT，保留根 LICENSE 及 THIRD-PARTY-NOTICES。公开产品快照与私有样本/日志分开；真实游戏载荷不进入 beaver 发行。`freeze.json` 还列本地证据文件身份，失败记录与 before-image 原地保留，不作为可分发 fixture。

## 提取范围与所有者

| 来源 | 提取/保留方式 |
|---|---|
| `src/monkey/adoption.py` | beaver 参数化接手三方判断、目标工程状态、冲突、前置校验、载荷准备与提交；保留旧 `monkey-adopt/1` 计划与 `.monkey/adoption/state.json` 兼容读取的明确策略 |
| `src/monkey/adoption_native.py`、`targets/MonkeyAdoption.cs` | beaver 接手自有 Editor child、原生移动/导入/保存重开、日志/恢复与辅助文件清理；不要逐字改名后宣称新合同已验 |
| `src/monkey/incremental.py` | `register/workspace`、开发工程 `_preview/apply`、锁/备份/回滚归 beaver；候选 `snapshot/check_content/identities/diff_data/diff` 为恢复侧读取/差异职责，不整体搬走 |
| `src/monkey/cli.py` | adopt/adopt-recover/register/apply 现为明确过渡兼容；CLI 参数/结果和退出码是调用合同，接手后再按实际能力迁路由 |
| `tests/test_adoption.py`、`tests/test_incremental.py` | 三方冲突、人工改动、身份歧义、依赖/设置漂移、计划陈旧和恢复反例供 beaver 继承；归属与适配后复验 |
| `candidate_snapshot.py`、`output_limits.py`、`owned_fs.py` | monkey 候选读取/预算/路径保护实现保留。beaver 消费版本化候选并实现必要合同校验；不得顺势复制源包解析器。快照中保留这些传递依赖供理解/移植，不依赖活动源码目录 |
| `stage_contracts.py`、`signatures.py`、`structured.py`、`replan.py`、`io.finish` | 继续 monkey 单写：源阶段签名、缓存闭包、预算/流式输出、候选身份；不移交工程操作工具 |
| 其他 native-import/native-layout/field recovery | 在独立候选内恢复与原生生成仍属 monkey；人工开发工程的修改归 beaver，不能仅按文件名含 native 一概搬走 |

## 运行依赖与调用方

- Python >=3.11；事务核心用标准库，当前从 `io`、`sources.compiled.fail/ParseError` 借用通用 I/O/错误合同。beaver 应抽取通用错误适配，不能为 `fail` 复制 compiled 源解析器。完整 monkey 环境固定 Pillow 12.2.0、pypinyin 0.55.0，ASTC 可选 texture2ddecoder 1.0.6；这些不是采用事务本身新增的依赖。
- Unity 执行仅固定现存 **6000.6.2f1**，UnityEditor/UnityEngine API，自有 Editor 辅助代码，不安装包、不改引擎/许可、不用 Pipeline。Creator 3.8.8 只有预览，执行明确 `ADOPT_NATIVE_UNSUPPORTED`。
- 当前直接调用方：monkey CLI 的 adopt/adopt-recover、内部 Python 测试与 monkey 自有私有验证启动脚本。CLI 旧 register/apply 调用 incremental。未将新 adopt 部署到游戏；样例项目已有项目专用采用脚本不是新 adopt 消费者，不能擅自替换。
- GREA 的 monkey 路由/旧工具 ID 和两个游戏专用脚本仅是 internal planning reference SOURCE-INVENTORY 的后续调查种子，尚未证明消费本版本 adopt；原所有者核实、接手验证后才薄兼容/退休。不在本批修改 GREA 或游戏文件。

## 实际验证层

- 全量候选清单/字节核验：样例项目 Unity 75,710 文件/2,834,639,181 字节，Creator 74,694/2,789,086,480；样例项目 164,599/3,267,184,074。详情与清单 SHA 在 validation 摘要及私有 JSON。
- 三方全量预览：最新样例项目 `PreviewNextFinal` 2 个操作/0 冲突/17,642 保留；样例项目 `PreviewFinal` 1/0/37,648，显式 lineage `sample-project-v050-validation`。这些是自有副本中的受控改名/新增反例，不是重新全量导出业务代码。
- 样例项目 `Transaction03`：前一 WIP 算法 `[private fingerprint omitted]`，1 个 BGM 路径移动实际 adopted，GUID/localID 与最多128份未改 Prefab/Scene 直接依赖读回、独立重开与原有 Assets 保护通过。
- 保留失败：最早辅助脚本未处于真实 Editor 目录导致编译失败，确认0资产写入后恢复；随后原生移动成功但 manual 文件 meta 被 Editor 规范化，提交保护准确拒绝，实际原生回滚1资产成功。修复和失败回执均保留。
- 最终冻结算法 `[private fingerprint omitted]`：三方/预算/路径测试通过，C# SDK离线编译通过；**新增目录/资产与目录回滚修改尚未原生实跑**。不能把 Transaction03 前版结果标成最终代码全通过。
- 最新样例项目预览 SHA `[private fingerprint omitted]`；样例项目 `[private fingerprint omitted]`。代码或目标/依赖/状态变化后须重新预览，旧计划不能直接重放。
- 向样例项目本轮没有启动 Editor。Creator 执行、Player/业务/视觉、动态字符串加载键适配均未验证。

## beaver 接收结果（2026-10-26）

beaver 已接收冻结快照并完成其本地 0.1.0 验证；本轮只读复核固定回执/wheel 身份并复用，不重跑原生采用。回执与限制见 [资源引用验收](validation/2026-10-26-resource-reference-correctness.md)。下文保留当时交接要求与 monkey 冻结快照的原验证层，不能倒填为 monkey 代码最终原生全通过。旧兼容消费者切换仍待核验。

## 历史交接时的必要闭合

先验证固定快照与被提取 API/许可；在 **beaver 自有合成工程或允许的样例项目副本** 复验新增目录/新增资产、修改/移动、保存重开、失败中断、回滚、后续人工改动保护。记录新合同/producer身份/验证层，不扩称全部 Unity 版本或 Creator 执行支持。不得因有样例项目预览就启动其暂停工程。

旧入口仍运行真实实现并显式弃用，没有虚构 beaver 转发。beaver 能力/固定版本/消费者核验前不删除旧实现；之后由 monkey 原所有者做兼容迁路由。人工资产、依赖版本/项目设置不自动覆盖/安装；unknown/manual/retained 不抢归属；源删除保留建议；数据/存档/服务不属于文件回滚。
