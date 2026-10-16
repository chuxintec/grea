# Unity 五层模板与通用组件整合执行计划

> For agentic workers: 使用 `superpowers:executing-plans` 逐任务串行执行；本任务不启用子 Agent。以下复选框记录执行结果，候选、已实现与已验证分开报告。

**Goal:** 在现有 grea 基础包上整合五层工程模板、第一批通用交互组件和基础 UI Prefab，并用两个不同结构的隔离示例验证；不改动 IceFire 生产工程。

**Architecture:** 五层是业务工程的职责与依赖约束，不是五个必须发布的通用库。复用现有 foundation、ui.ugui、editor 包；项目的 Domain/Gameplay、数据和美术继续由项目所有。公共实现只负责必要的接口、生命周期和 Unity 能力接入，不引入第二套引擎、调度或资源体系。

**Tech Stack:** 当前可用基线为 Unity 6000.6.2f1、URP 17.6.0、uGUI 2.6.0、三个 `com.grea.*` 包 0.2.1。执行前核对实际 lock 与本次测试环境；这些是当前验证组合，不代表其他 Unity 版本、Windows 或 IL2CPP 自动通过。

## 授权与分支

- 用户于 2026-10-16 要求将此方案整理为具体执行内容，发送“Grea 开发与维护”会话整合，并切换独立新分支。
- 维护仓库：`grea` 独立仓库根目录；执行前用 `git rev-parse --show-toplevel` 确认。
- 本分支：`codex/unity-framework-extraction-20261016`。
- 创建基线：`8521ca5468454da147306a1047ddd5e9d1c0426a`，对应已发布 `v2026.10.16-rc1`。
- 创建前已核验 main、上述 HEAD 与干净工作区。分支已创建，本计划是交接文档，不是运行实现已完成的证明。
- 不 reset/覆盖既有分支，不在 main 上实施，不自动合并 main、推送或发布新版本。
- IceFire 仍由另一个会话执行迁移；本任务仅可读取相关代码与证据，不改动它的 Assets、Packages、ProjectSettings、存档、计划、构建或当前 Editor 状态。
- 隔离 Unity 工程及原始验证材料在 grea `.private/framework-extraction-20261016/<唯一运行身份>/`；不得将原游戏图片、字体、Spine、音频、完整存档、私有路径或来源运行时放进公共包。
- 标准唯一来源仍是 `plugin/`，安装副本由同步脚本生成。未经实证的 IceFire 经验只登记候选，不提前升级为通用强制规则。

## 本轮范围与边界

| 内容 | 本轮处理 | 完成含义 |
| --- | --- | --- |
| 五层工程模板 | 在现有 counter-composition 示例基础上完善职责、程序集边界、所有权和最小闭环 | 新工程可独立创建、修改、测试；公共包不引用 Game |
| 已有基础系统 | 核验并复用作用域、服务生命周期、存档、音频、资源句柄、诊断 | API/契约/示例与实际代码一致，相关正反例通过 |
| 按钮交互 | 审计 CommandButton 与 Unity Button 的覆盖，补确有缺口的按压反馈 | 正常点击、拖出、失焦、禁用、重复绑定与异步晚到行为可验证 |
| 基础 Prefab | 第一批 UIHost、ModalShell、ButtonShell | 无原游戏素材，序列化引用明确，可在 Inspector 直接维护 |
| 列表、Toast、Loading | 本轮记录需求与复用证据；只有两个示例实际共需时才实现最小能力 | 未实现的项保持候选，不生成空类或宣称可用 |
| 数值战斗品类模块 | 记录属性/Buff、奖励事务、背包/装备、战斗会话的候选契约 | 不直接把 IceFire 规则搬入基础包，不宣称通用战斗已实现 |
| 源引擎兼容机制 | 明确排除 | SourceSceneCoordinator、InheritedViewFactory、来源节点图/身份、通用源 Tween/帧循环不进入框架 |
| 配置制作体系 | 保留现有明确契约 | 本轮不附带切换 JSON/Excel/SO 或引入 Luban；单一制作源原则不变 |

## 文件归属

| 路径 | 职责 |
| --- | --- |
| `tools/unity/framework/packages/com.grea.foundation/` | 现有基础契约和 Unity 服务接入 |
| `tools/unity/framework/packages/com.grea.ui.ugui/` | 现有 uGUI 生命周期与交互接入 |
| `tools/unity/framework/packages/com.grea.editor/` | 只读绑定校验与受控 Editor 资产生成 |
| `tools/unity/templates/counter-composition/` | 既有五层 seed-once 最小示例，保持旧配方兼容 |
| `tools/unity/templates/framework-samples/numeric-combat/` | 新增自有合成数值战斗验证示例；只使用本轮共享包 |
| `tools/unity/templates/framework-samples/grid-puzzle/` | 新增自有合成网格益智验证示例；领域规则与战斗示例独立 |
| `tests/test_unity_framework.py` | 公共包边界、依赖、meta、准备与隔离的 Python 守卫 |
| `tests/test_unity_generation.py` | 修改生成器时对应的旧配方与生成/恢复回归 |
| 各包 `Tests/`、各示例 `Assets/Tests/` | C# 行为、资源、生命周期与集成验证 |
| `scripts/testing/prepare-unity-framework.py` | 复用既有隔离安装入口；如扩展选项，保留默认行为与 packages-only |
| `docs/design/unity-framework-extraction-inventory.md` | 候选/采纳/排除矩阵及来源依据 |
| `docs/Unity框架与通用组件.md`、各包 README | 实际 API、制作入口、包分发、验证边界 |
| `docs/validation/2026-10-16-unity-framework-extraction.json` | 本轮脱敏验收摘要及对应源码身份；不是原始日志 |
| `plugin/skills/grea-unity-standard/references/05-Unity-通用组件与Prefab.md` | 仅当本轮验证推翻或补齐现有规范时更新原条目 |

新代码按职责放入上述既有包；不得为了对应五层目录创建五个空 UPM 包，也不建立第二个通用 Editor/运行框架目录。

## T0：冻结输入和工作区边界

- [x] 确认接收会话为空闲、读取其最新发布结果。
- [x] 核验 main/HEAD/工作区后创建并切换独立分支。
- [x] 接收会话回读分支与状态，确认此计划是预期的未提交文件；保留其他新出现的修改，不擅自清理。
- [x] 读取仓库 AGENTS、最新 grea 路由与工程标准；通过当前 `bin/grea session` 核对实际工具能力。
- [x] 记录三个 package.json、测试依赖 lock、模板、生成器及本次所读候选文件的哈希。冻结原始候选只在 `.private`；原游戏资产不复制。
- [x] 记录当前模板/组件已有验证，列出本轮变化影响面；无需重跑完全无关的发布流水线。

核对命令：

```sh
git branch --show-current
git rev-parse HEAD
git status --short
bin/grea session
```

预期分支为上文新分支，初始 HEAD 为发布基线；工具 presence 与 Editor 已连接分开记录。

## T1：完成可提炼清单，先消除重复方案

- [x] 读取三个现有包源码、README、测试及 `docs/Unity框架与通用组件.md`，以实际源码和 package.json 为准。当前部分 README 标题仍为 0.2.0，而 manifest 为 0.2.1；同步修正本轮相关版本说明。
- [x] 对每项候选记录：职责、输入/输出、必需依赖、所有者、取消与失败行为、项目常量、序列化字段、现成 Unity/已锁定插件替代、测试及实际使用点。
- [x] 在 inventory 中明确四种结论：复用现有实现、补现有实现缺口、隔离候选、项目专属/排除。
- [x] 首批审查 IceFire 的 `Presentation/UI/Controls/ButtonPressFeedback.cs`、`Services/Persistence/FileSaveStore.cs`、`Presentation/UI/Controls/NativeModalViewport.cs`，只读并记录所读字节身份。
- [x] ButtonPressFeedback 只按其有限按压契约判断可复用性；不得把完整 IceFire 表现层一起复制。
- [x] IceFire 存档的散列文件名、`.tmp/.previous` 顺序与旧档兼容保持项目专属；不可静默替换现有 grea FileSaveStore.Recover 规则，也不可写真实玩家目录。
- [x] NativeModalViewport 当前为旧零尺寸容器接缝服务，不作为通用布局默认组件；正式原生布局确有同类需求时才另行验证。

验收：每项已采纳能力都有明确的现有归属或实际缺口；排除项不能出现在包依赖/生成产物中。

## T2：完善五层模板与明确的维护流程

- [x] 保留 counter-composition 旧配方和 seed-once 所有权。补齐文档中的新增规则、界面、服务与测试应改哪些文件，不将示例特定 Counter 命名当作框架类型。
- [x] 五层依赖保持：Domain 无 Unity 依赖；Gameplay 只依赖 Domain 与明确端口；Presentation/Services 依赖业务契约；Bootstrap 负责装配和生命周期，不承接页面业务。
- [x] 公共包不得反向引用 `Game.*`、`IceFire.*`，不得依赖项目绝对路径、固定场景节点名、源 UUID 或源引擎字段表。
- [x] 加入可失败的边界反例：Domain 引入 Unity、包引用 Game、循环 asmdef、测试类型进入 Player、重复 EventSystem 所有权分别应被对应检查拒绝。
- [x] 对于 SceneManager、Input System、Unity Pool、AudioMixer、正式动画能力，模板说明实际接入点；只为真实生命周期/失败契约写少量接入代码，不自建对应引擎。

验收：packages-only 工程不包含 Game 也可编译；五层示例可独立构建；重复生成不覆盖人工修改。

## T3：首批组件整合

- [x] 先以现有 CommandButton/ModalPanel/ScreenHost 与 Unity Button 的行为测试确定缺口，已有能力不另起同类管理器。
- [x] 对确有缺口的按钮按压反馈，在 `com.grea.ui.ugui` 内用明确序列化引用实现有限表现组件；业务回调继续由既有命令接口拥有。参数包括视觉目标、按压比例与时间；不得查来源图或把通用源 Tween 搬进包。
- [x] 对变更行为先建立失败用例，再完成实现：按下/释放恢复；拖出/开始拖动取消；失焦、禁用、销毁取消；其他指针释放不误结束；外部改变基础缩放后正确恢复；与按钮禁用和命令防重入共同工作。
- [x] 回归既有命令：一次输入只派发一次；隐藏/关闭取消旧绑定；晚到异步结果不更新新代次；错误可观察；任务结束与业务成功分开。
- [x] 基础系统只补本轮已证明的契约缺口：服务启动失败逆序清理、作用域重复释放、损坏存档拒绝静默覆盖、音频句柄退出释放、诊断预算、资源未找到/类型错误。保留已有合法行为。
- [x] 每项变更更新所属包测试与 README，不通过泛化命名掩盖单项目常量；不同时安装两套同类框架。

验收：组件在 packages-only 隔离工程通过所影响的 EditMode/PlayMode 正常与失败测试；没有 IceFire 依赖或原版素材。

## T4：三个基础 UI Prefab 的可编辑闭环

- [x] 复用 `com.grea.editor/Editor/ProjectGenerator.cs` 现有 UIHost、ModalShell、ButtonShell 配方；先核对已有结构，只有缺口才扩展。不得给用户既有工程执行全量重生成。
- [x] UIHost 明确 Canvas、页面/弹窗/提示层、缩放与安全区入口、EventSystem 所有者；一个宿主不重复生成输入系统。
- [x] ModalShell 明确遮罩、内容槽、关闭入口、可选标题和初始选择；焦点恢复及多层输入阻断由实际使用策略负责，不假称 ScreenHost 已是完整模态栈。
- [x] ButtonShell 明确 Button、视觉目标、文字/图标槽、可选音效、禁用和按压配置；不持有业务状态或存档。
- [x] 基础资源仅使用自有/可分发中性内容，经当前 Unity Editor API 创建和保存，保留真实 meta。Prefab 文件或生成配方的所有权必须明确，不能形成两份手工同步真源。
- [x] 完成 Inspector 改字段→保存→关闭重开→实例化/Play→构建回读；无需 Capture/源节点图。缺字段反例定位到 Prefab、组件和字段。
- [x] 接口/原生测试覆盖重复开关、父节点禁用、销毁、按压取消与不同安全区矩形；两个最终 Player 在默认窗口通过 OS 键盘导航、模态交互和关闭重开。
- [x] 补验两个最终 Player 的 macOS 窗口放大/还原；发现并修复示例宽窗口控件重叠，新增真实 CanvasScaler 多视口 PlayMode 回归。
- [ ] OS 鼠标点击/按住拖出仍未稳定派发到 Unity，保留 not_run；不以接口或键盘结果替代。

验收：三个基础 Prefab 的实际资源/引用/编辑和生命周期证据齐全；公共包不携带 IceFire 字体、图集、Spine 或美术。

## T5：两个不同结构的隔离示例

- [x] 数值战斗示例只使用自有合成数据：进入战斗、按规则产生伤害、暂停/恢复、结算一次、返回、再次进入；增加一个升级操作以验证校验、保存失败与 UI 刷新顺序。无需复刻 IceFire 技能或完整商业养成。
- [x] 网格益智示例采用固定小网格：选择格子、执行合法移动、拒绝非法移动、重置和过关；通过同一批公共按钮/弹窗/存档能力呈现。棋盘状态与判定保留在该示例 Domain/Gameplay。
- [x] 两示例均自行拥有 Domain/Gameplay/Bootstrap；共享包不增加按游戏类型切换行为的分支，不为第二示例改出另一份公共包。
- [x] 两示例都覆盖打开→操作→取消/失败→关闭→重开，并实际进行 Player 关闭重开存档验证；合成 QA 路径与普通玩家路径分离。
- [x] 第一个示例通过但第二个不能直接消费时，该组件仍标候选，收窄或修正契约后复测；禁止把两个换皮计数器当成不同结构验证。
- [x] 不为示例自动安装新的编辑器/第三方包或抢占 IceFire Editor。使用独立工程和已存在许可；不可用的平台保留未验证。

验收：两个不同结构的消费者均能使用同一版本包，工程可独立恢复，不依赖 grea 检出目录外的软链接或私人原包。

## T6：验证、文档与规范整合

- [x] 在变更稳定的检查点运行相关 Python 守卫：

```sh
./.venv/bin/python -m unittest discover -s tests -p test_unity_framework.py -v
./.venv/bin/python -m unittest discover -s tests -p test_unity_generation.py -v
```

- [x] 用既有准备脚本创建不存在的新隔离路径。下面是本轮第一次包检查的具体入口，重复运行改用新的末尾编号，不清空旧证据：

```sh
python3 scripts/testing/prepare-unity-framework.py --packages-only --output .private/framework-extraction-20261016/packages-01
mkdir -p .private/framework-extraction-20261016/evidence-packages-01
grea_framework_root="$(pwd)"
unity test .private/framework-extraction-20261016/packages-01 --mode EditMode --output "$grea_framework_root/.private/framework-extraction-20261016/evidence-packages-01/editmode.xml" --timeout 240 --format json
unity test .private/framework-extraction-20261016/packages-01 --mode PlayMode --output "$grea_framework_root/.private/framework-extraction-20261016/evidence-packages-01/playmode.xml" --timeout 240 --format json
```

- [x] Unity 调用前读当前 unity-cli/grea-delivery 技能并确认运行接口；不加 `--allow-install` 隐式更换环境。两个示例另用独立运行身份，原始报告保存实际命令、源码 SHA、包版本、平台及结果。
- [x] 对最终变更补独立无 Library 恢复、Player 载荷检查和 Mac 实际输入/视觉验证。必要性能测试按本次组件风险确定；不把微基准、平均 FPS 或测试数量当通用性能承诺。
- [x] 发布能力矩阵：已实现、Editor 已测、Player 已测、真实输入已测、平台未验分别列明。IL2CPP/Windows/移动端未经实际执行不得写支持已验证。
- [x] 包 API 或序列化契约改变时更新三个包之间的版本依赖、模板/配方与锁；没有代码变化不为文档调整虚增运行版本。不沿用旧制品/测试报告证明新身份。
- [x] 同步框架说明、包 README、组件最小示例、安装/升级/回退方法；只把经过两个不同结构示例验证的结论纳入现有规范原条目，不另外建立竞争规则。
- [x] 若修改 plugin 规范，执行唯一同步流程：

```sh
python3 scripts/sync_skill.py
python3 scripts/sync_skill.py --check
```

- [x] 提交前按本仓库既有公开树审计检查 staged 实际字节、素材许可证、源码归属和私有信息；脱敏摘要进入 docs/validation，完整日志与游戏素材留 `.private`。最终汇报本分支改动、测试、未验平台和待合并项。

## 交接与完成判据

接收会话先确认分支和此文档，再从 T0 未勾选项开始。用户已经选择由“Grea 开发与维护”会话执行整合，无需再次询问由哪个会话执行。

本轮可声明完成的最小交付包括：候选/采纳矩阵、可独立使用的五层模板、第一批经过必要修正的现有基础包、三个可编辑 UI 基础资源、两个不同结构消费者，以及与同一源码身份绑定的验证摘要。没有实现的列表/复杂导航/品类系统留在明确候选清单中。

不能用新文档写完、包改名、生成器能运行或 IceFire 内部测试通过代替组件准入；不能为了框架完整而复制源引擎兼容层。完成本分支工作后报告待审查结果，合并、推送和发布另按用户指令进行。

## 接收执行记录

- T0：已核验指定分支、基线和单一交接文件。已冻结 125 个公开输入及 C01–C03 的源码字节，清单及快照只在本轮私有运行目录。当前 CLI 为 2026.10.16rc1；本机已有 Unity 6000.6.2f1 / arm64。全局 Pipeline 状态查询未发现可连接实例，不能据此声明没有其他 Editor，后续只针对新隔离工程执行批处理。
- 变更前 Python 基线：框架守卫 6 项、生成/恢复 18 项均通过。既有 Foundation/uGUI/Editor 0.2.1 的历史原生记录只作范围参考，本次 packages-only 原生基线已通过 17 项 EditMode、9 项 PlayMode；更新后的生成器/公共包回归见下。候选决策见[提炼清单](unity-framework-extraction-inventory.md)。

- T2/T3：新增只读源码/具名 asmdef 守卫，覆盖纯层 Unity 引用、公共包项目引用、环、测试进入 Player、运行时 Editor 引用；生成与隔离准备共用。ButtonPressFeedback 经 10 项缺失实现失败用例后完成，追加同帧输入与示例命令所有权测试；不改变基础存档/服务规则。
- T4：生成器/包最终 EditMode 39 项通过，包含非零原点/求交/缩放/非法安全区、长文本/字号/颜色/尺寸保存重开、字段定位、恢复和重复生成拒绝覆盖。第一次长文本测试混用 SerializedObject 快照与直接写入，修正为统一序列化编辑后完整回归通过；保留失败证据。
- T5：自有战斗与 3×3 滑块分别使用同版包。战斗拥有待领奖/领取/升级与失败提交；益智拥有相邻/非法移动/重置。首轮及无 Library 恢复测试均已通过；最终导航焦点修正后的身份仍在验证。
- T6：Python 全量 205 项通过、2 项原有集成条件跳过。首次构建指纹发现官方 URP 回写缓存，已新增独立构建工作副本包装器，3 项测试及一次真实构建证明源 Assets 66 文件字节保持；不通过回写原件掩盖引擎变更。最终两示例 Player/输入/关闭重开仍在执行，未提前勾选完成。

- 最终收口：Foundation 0.2.1、uGUI/Editor 0.3.0（未发布），生成器 0.1.2；所有工具 ID 与现有 API 保持。额外具名消费者引用也被边界守卫拒绝，守卫实现字节纳入 recipeId/planId。
- 自行 Player 验收暴露并修复两个真实问题：命令临时禁用清空键盘选择、自动导航跳到模态背景。均有原生失败断言和回归；最终两个不同结构消费者各通过 27 EditMode + 23 PlayMode，源码独立解包且工作副本初始无 Library，源 Assets 各 66 文件构建后保持。
- 两个最终 arm64/Mono Player 的载荷、构建 ID、包哈希、QA 存档、三次启动和 OS 键盘/视觉均已回读。战斗覆盖待领奖恢复/一次领取/取消/升级失败重试；益智覆盖非法移动/部分恢复/一次完成/重置取消确认/保存失败重试/选择取消。普通存档 namespace 未创建。
- 旧 Counter 经产品统一执行层真实生成并绑定通过；再次执行不启动 Editor、返回 unchanged、所有拥有文件字节不变；独立生成物 24 项 PlayMode 通过。最终生成器 39 项 EditMode、Python 全量 209 项（2 项既有外部集成跳过）通过。
- 仅将已实证契约回写既有 Skill 参考，同步/一致性/Skill 校验通过；本轮串行限制下不运行子 Agent 行为压力测试。源码审计与验收摘要见 [验收记录](../validation/2026-10-16-unity-framework-extraction.json)。
- 状态：实现、当前基线测试与验收记录已收口，保留上述鼠标/拖拽的实机缺口，以及其他平台、InputSystem 设备、断电/多写者和性能基准的 not_run。不修改游戏原工程，不提交推送、合并或发布；当前分支和未提交变更保留供审查。

- 窗口补测：3024×1834 实机暴露网格/按钮重叠，原生失败断言定位 Tile 3 与 Tile 0；仅将两个示例的 CanvasScaler 改为 Expand。两示例各 24 项 PlayMode 通过，包含 540×900、3024×1834、900×540 的实际 Canvas 矩形检查。新 Player 均经前台放大/还原显示验收；战斗补验系统键盘战斗/暂停/恢复/待领奖关闭重开/一次领取/拒绝重复/QUIT。原 214 文件快照与这 4 文件的变更前后哈希在验收 JSON 分开保留。鼠标不再反复重试，也不要求用户代玩。
