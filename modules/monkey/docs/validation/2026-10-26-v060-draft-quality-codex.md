# v0.6.0.dev1 初稿质量整改与可选 Codex 后处理

本地开发验收，2026-10-26。按权威计划 5A/5B 和已核验的人类授权执行；保留 `d3f22ab` / `ed8323d` / FullDraftCandidate03。正式安装仍为 0.4.0，没有推送、Release、全局安装、正式游戏写入或新 Editor/Player 验收。

## 确定性初稿整改

- Array/Map/Set 构造保留参数、顺序与求值；Array 单参数区分长度/值，Map/Set 的 null 来源为空；不支持形态先保留参数求值再明确诊断/抛错。绑定或歧义标识符不冒充全局内建。
- 方法/字段名预规划使用精确源 binding/owner/member 身份，声明和引用共用消歧结果。已知静态成员接收者映射到明确类名；未索引 getter 保留原成员名和诊断。动态 this、别名及未知类型不以全局替换猜测。
- 回调保留在原作用域，函数 ID 指向实际存在的内嵌标记。独立 indexed 方法中的同一回调可出现在多个外层视图，canonical 映射选择最窄源跨度；单次 renderer 内重复 ID 仍拒绝。未内嵌且有捕获的 16 项提取为显式 capture 参数，调用点未接线会诊断。
- 实际复核 Set 初值、配方字段/方法消歧调用、静态 owner 和 function@617539 闭包；11 项源样例对照均通过。没有手改确定性生成物。

| 分母 | 上一基线03 | 当前07 |
|---|---:|---:|
| 源类 | 1,157 | 1,157 |
| 索引方法 / 完整映射 | 19,571 | 19,571 |
| 全部函数记录 / 完整映射 | 47,384 | 47,384 |
| 辅助函数内嵌 / 独立提取 | 基线独立输出为主 | 23,535 / 4,278 |
| 物理方法体 | 47,384 | 23,849 |
| C# 文件 | 24,153 | 5,522 |
| 字段记录 / 独立声明 | 3,706 / 3,528 | 3,706 / 3,528 |
| 初始化记录 / 运行时写入 | 1,440 / 2,266 | 1,440 / 2,266 |

完整候选 `FullDraftCandidate07/UnityProject` 的 owning manifest SHA-256 为 `[private fingerprint omitted]`。94,127 文件 / 3,624,135,738 字节，仍含 2 Scene / 1,696 Prefab。沿用 FrozenResources02 原生资源、JSON及身份，除接续说明外资源 hash 不变。beaver 自有 snapshot/verify 独立只读逐文件通过，未改其代码或执行 adopt。

完整源及每条方法/字段的源范围、SHA、详情位置、目标成员或内嵌标记均验证。0 整函数 AST/renderer 失败回退。885,473 条诊断含新增 523,966 条未知成员映射记录；诊断分类变了，不能与旧总数直接比较质量。773 个物理函数记录包含局部未支持/无可转写等标记，内嵌回调诊断在拥有它的输出体中，不冒充所有函数可运行。动态真假值、集合 API、异步状态与未知 getter 仍需后续修复。

禁止 parser/render 后，3 源实际复用 5,632 文件 / 467,924,157 字节，用时 3.443 秒；源候选未写。没有重新解码或原生重导资源。

## 可选后处理实际调用

新增独立 `code-postprocess` / `code-postprocess-resume`；普通 convert/code-draft 默认从不启动模型。见 [调用与边界](../CODEX-POSTPROCESS.md)。独立分配选中代码副本，保留只读 before、prompt/证据hash、可执行入口身份、每次 invocation、JSONL、真实 patch、源身份复核和精确 session 检查点。总 child 时间跨 resume 累计，最多一次精确 session resume；输出、无事件和退出后工作区字节预算独立记录。

首次普通外层沙箱启动在模型 session 建立前失败（CLI 自身只读会话数据库/app-server），无源码差异。已获准的本机运行权限下启动成功；内层仍为 workspace-write，既有配置与登录不改，没有绕过内层保护。只完成一次真实模型调用，无 resume、子 Agent 或模型对比。

- Codex CLI 0.162.1，session `[private identifier]`，child 61.405 秒，exit 0。
- 配方查询模块仅选中一个类文件，实际修改两个指定方法，其余字节逐字节不变；闭包标记保留。原 owning manifest 与选中源码 hash 不变，工作区无新增/删除、软硬链接、远端或提交。
- 替换这两个方法内的 filter 和缓存 Map 调用，产生独立 patch SHA `[private fingerprint omitted]`；原文件 SHA `[private fingerprint omitted]`，修订文件 SHA `[private fingerprint omitted]`。
- **结果 partial**：allRecipes getter 未声明，动态字段/相等语义、Map 与 Dictionary 的 key/null/缺失键差异、Array.filter 的稀疏/长度快照/迭代修改差异共 4 项保留。退出码不当作等价或编译通过。
- 实际两个修订方法体在独立 .NET 8 夹具中编译，顺序/匹配/懒缓存/重复读取/空结果检查通过。夹具只供应稳定非稀疏 List、整数键和 cookware，无迭代修改；不证明完整类、getter、原游戏或任意 JS 域。
- JSONL usage 为 input 99,394、cached input 64,640、output 928；按最后报告 turn 记录，未推断价格。运行事件未回报 model/effort，诚实记 unknown；只读现有配置观测为 gpt-6.1-sol / medium，明确不是实际模型证明。

## 检查与证据

46 项 draft/renderer/symbol 检查、9 项后处理进程/边界/精确恢复检查、6 项包级集成检查通过；公开 CLI 隔离夹具调用通过。既有严格16方法、8WASM、6CUA与旧引擎/安装整套结果沿用，没有重复运行。新分发仅对新增能力检查，身份另记本组 delivery。

完整私有回执在 `.private/v060-draft-quality-20261026/`：`final-candidate-verification.json`、`sample-quality.json`、`final-stage-reuse.json`、`CodexRevision02/manifest.json`/`changes.patch`、`ai-revision-verification.json`。原始游戏片段、候选、prompt/JSONL 和私有编译产物不纳入 Git/发行包。完整游戏、全项目编译、Player/视觉，以及既有36精确schema阻断均未因本组变为通过。

## 冻结源码与新增分发检查

源码 `[private fingerprint omitted]` / tree `[private fingerprint omitted]`；184 产品文件在冻结 git archive、wheel、sdist 和隔离安装中逐字节相同。实际模型调用时的 wrapper SHA 与该提交字节相同。wheel 738,905 字节，SHA `[private fingerprint omitted]`；sdist 1,090,428 字节，SHA `[private fingerprint omitted]`。

隔离安装仅执行新能力 capabilities、code-postprocess prepare-only（无模型）、拒绝非checkpoint精确session恢复三条CLI检查；没有重跑旧安装/类型/引擎套件，没有额外模型调用。安装产物仅位于本项目私有分发目录，不替换全局0.4。

本轮中间04/05/06输出的清单和日志已留档后清理，移除清单逻辑体积10,423,337,634字节（不推断APFS物理回收量）；最终07、AI修订、旧03及冻结资源基线保留。总回执 `.private/v060-draft-quality-20261026/delivery.json` SHA `[private fingerprint omitted]`。
