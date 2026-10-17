# Windows 与使用文档大版本：审计及开发计划

日期：2026-10-17。审计基线：`3d1a2be71292696ecc910523f33e949c160e3927`，已发布 `v2026.10.16`。

实施分支：`codex/windows-docs-major-20261017`。执行方：Grea 开发与维护会话。本文件与[逐文件文档处置清单](windows-docs-inventory-20261017.json)是本轮唯一开发计划；当前仅完成审计和计划，下面的能力均未因本文件而实现。

## 1. 目标、授权和完成定义

本轮交付两个结果：Windows x64 可独立安装、实际运行的 grea 完整插件；围绕安装、使用、接口、Unity、维护、排错整理的精简使用文档。保留已发布 macOS arm64 能力和旧接口的兼容路径。

- 全部实现、文档、测试和候选制品在上述新分支推进。main 起点保持基线不变；不能在 main 开发、合并、变基或强推 main。
- 可按需推送该功能分支执行原生 Windows CI。最终交付分支提交、候选包和验收记录；本任务不创建正式版本标签、不发布 Release、不升级现有全局插件安装。发布流水线的改造以分支 dry run 验证。
- 不修改 Games 中的游戏工程，不重新执行无关原版游戏验收。旧未完成模板、隐藏服务端恢复、Windows 游戏完整复刻不扩入本轮。
- 继续由维护会话单独执行，不创建子 Agent。按阶段提交并连续推进，不把某个阶段完成当作整个任务结束。
- Windows 主目标为原生 Windows 11 x64 普通用户安装；Windows Server 2022 hosted runner 提供原生自动化证据。两种环境分别记录。Windows ARM64、WSL、Wine、Linux 完整插件和 macOS Intel 不自动列为支持。
- 两份客户端清单都必须提供真实、可运行的 Windows 启动配置；Codex 是本轮必须完成的实际客户端安装/发现目标。Claude 的实际客户端安装单独记录，未执行不得声称已验，也不得改动用户现有 Claude 安装。
- 核心 CLI/MCP、Case/revision、静态工具、Windows 供应方接入、Unity CLI/Editor 与普通第三方库存分层验收。不能用全部 external providers 都 available 才算核心可用，也不能以核心握手替代工具/Unity 业务实测。

本期称为 Windows/docs vNext，不擅自改用 SemVer 2.0。候选版本在实现冻结时按现有 CalVer 规则统一设置；保留正式版及历史报告的原身份。

## 2. 审计结论

这是基于当前源码和发布流水线的兼容性审计，不是 Windows 实机测试。现有 Windows smoke 是有效的最低证据，但覆盖范围仅为安装源码依赖后执行一次 session。

| ID | 严重性 | 已确认事实及入口 | 影响与修改方向 |
| --- | --- | --- | --- |
| W01 | P0 | [插件启动器](../../plugin/launcher/grea)检查 Darwin/arm64；[runtime lock](../../plugin/runtime-lock.json)仅有 Apple ARM64 Python；[MCP 清单](../../plugin/.mcp.json)启动 Shell 文件 | 完整包不能用于 Windows。平台配置、原生启动入口、运行时路径和客户端清单必须一起实现 |
| W02 | P0 | [common.publish_directory](../../src/grea/common.py)只有 renamex_np/renameat2，且在平台分派前创建 CDLL(None) | Case 初始化和工程新建/恢复也存在阻塞；补 Windows 同卷、不替换目标的发布原语，错误路径保留 staging，不能用先 exists 再 shutil.move 代替并发保证 |
| W03 | P0 | [cases.locked](../../src/grea/cases.py)直接依赖 fcntl；revision/status 复用该锁 | 不只是写入，审阅查询也受影响。引入共享的跨平台锁契约，覆盖旧 v1 与当前 revision，保留只读打开及并发语义 |
| W04 | P0 | [runner](../../src/grea/runner.py)在非 POSIX 上只 terminate/kill 直接子进程；回执为 owned_process_only | 工具超时、取消和输出超限可能遗留后代或持有日志管道。需要完整进程所有权、早期纳管及实际清理验证 |
| W05 | P1 | [build_plugin](../../scripts/build_plugin.py)、[runtime_licenses](../../scripts/runtime_licenses.py)、[plugin_release](../../scripts/plugin_release.py)硬编码 macos-arm64、runtime/bin/python3、Apple triple 和 Mac 许可例外 | 不能只添加 Windows ZIP 文件名。需要目标矩阵、逐平台依赖/许可身份、构建及验收报告绑定 |
| W06 | P1 | [plugin_bundle](../../scripts/plugin_bundle.py)使用 POSIX 执行位、tar.gz 和统一路径库存；部分文本调用依赖默认编码 | Windows ZIP 解压、执行权限含义、中文编码、大小写、保留名、junction/reparse 和路径长度需要实测与明确策略；不能让换行/权限差异破坏身份校验 |
| W07 | P1 | [CI](../../.github/workflows/ci.yml)的 windows-smoke 只有 uv sync 和 bin/grea.cmd session；[隔离验证](../../scripts/verify_plugin.py)使用 sandbox-exec；[客户端验证](../../scripts/verify_plugin_clients.py)使用 POSIX 进程组 | 缺少 Windows 全套运行/插件/客户端证据；Mac 的测试布尔值不能直接移植到 Windows 报告 |
| W08 | P1 | registry 共有 73 项，其中 42 项直接声明 Windows；剩余 31 项含别名、Mac 包装器和生成入口 | 数量不等于实际覆盖。逐个解析 alias 和 provider 条件；保留工具 ID，在平台原生实现经过验证后开放对应能力 |
| D01 | P1 | docs 共 77 文件、51 Markdown、顶层 16 Markdown；design 24 文件、validation 15 文件 | 使用导航、实现过程、提案与证据混排；建立六份核心说明和一个导航入口，按消费关系处理其余内容 |
| D02 | P1 | README 仍突出预览/旧 rc 发布入口；[迁移指南](../安装与平台.md)有“7 个技能”“纯源码分发”等未限定的旧表述，而当前是 8 个技能和完整运行时包 | 历史事实混入当前说明，须逐句核对版本和状态，不能一键替换历史报告中的版本号 |
| D03 | P1 | 安装、平台、兼容、工作区接入与维护分散重复；Unity 五篇入口又与包内 README/技能规范交叉 | 按读者任务合并并删除重复解释，保留实际调用、失败处理和能力边界，不把 16 份拼成一篇超长文档 |
| D04 | P1 | [build_plugin.write_product](../../scripts/build_plugin.py)目前复制完整公开源码闭包；[check_docs](../../scripts/check_docs.py)固定读取接口文档路径 | 文档整理涉及打包投影、链接、工作流、Skill 和测试；搬文件而不修改消费者会导致分发断链或身份校验失效 |

## 3. 方案决策

### 3.1 共享业务实现，隔离操作系统差异

继续使用 `src/grea` 单一 CLI/MCP 执行层。平台差异集中为小型模块：文件锁、目录发布、进程所有权、平台能力/运行时布局。可以采用 `src/grea/host/` 或等价聚合位置；不复制 cases/runner 的完整 Windows 版本，不把整个工具仓库套成游戏五层架构。

必须保留：append-only evidence、v1 可读性、revision 变化失效、候选哈希预算、全新输出、输入不可覆盖、结构化失败和原日志回执。平台实现无法满足这些条件时应失败，不悄悄降为无锁或复制覆盖。

文件锁优先评估 Win32 LockFileEx 的共享/独占锁与释放语义；如选择 msvcrt 或维护良好的依赖，须写清与原共享读/独占写契约的对应关系、等待/取消策略及许可。Windows 字节区间锁的偏移、长度和句柄生命周期必须明确。[LockFileEx 官方说明](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-lockfileex)和[Python msvcrt 说明](https://docs.python.org/3.12/library/msvcrt.html)作为实现依据，不能只用平台 mock 关闭此项。

目录发布默认限本地文件系统且 stage/target 同卷；目标已存在，包括空目录，必须拒绝。Windows 移动目录要求同一驱动器，应据 API 行为和并发反例验证实现；不能把跨卷 copy/delete 当成同等原子操作。[MoveFileExW 官方说明](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw)。不承诺断电耐久性或网络盘一致性超过实际验证范围。

进程管理优先使用 Windows Job Object，关闭时终止所属进程。必须处理“子进程在加入 Job 前逃逸”的竞态，检查嵌套 Job/CI 环境，失败时清理已创建进程；不能按进程名全局 taskkill。Job Object 的后代纳管有例外，不把它声称为所有守护进程的绝对隔离或网络沙箱。[Job Objects 官方说明](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)。

### 3.2 按 target 构建和验证自包含插件

- 目标 ID 至少包含 `macos-arm64`、`windows-x64`；由一个受校验的目标定义选择 Python 归档、下载 SHA/大小、平台 triple、可执行路径、依赖 wheel、许可来源、启动入口和验收实现。Mac 旧锁可保持兼容读取，不能直接移用其 zlib-ng 许可例外。
- Windows 完整包使用原生 Python.exe 和固定依赖。优先让客户端直接启动随包解释器/正式启动器；若使用 cmd 包装，必须测试真实客户端与元字符/引号参数往返，不假设 Shell 解析与 POSIX 等价。使用时不依赖系统 Python、uv、Git Bash、WSL 或首启联网安装。
- 编码统一为明确 UTF-8，MCP stdout 只输出协议。覆盖中文/非 ASCII 路径、空格、`&`、`!`、括号、长路径和 CRLF；CLI 源码入口和随包入口都测试。
- ZIP 清单区分可移植文件身份与平台执行属性。Windows 不能用 chmod/readonly attribute 冒充 ACL 写入禁止。保留路径穿越、大小写冲突、保留设备名、重复条目、超预算、链接逃逸和内容变更反例。
- 将插件内容投影和 `plugin_release.validate` 使用的预期闭包共用。允许从运行插件中排除已退役教程/提案/历史日志，但源包仍保留必要维护/测试内容；产品文件哈希必须精确相等，不以放宽白名单来适应差异。
- 每个目标有独立 archive、runtime identity、acceptance report。未来发布组装按声明 target 集合校验，不能拿 Mac 报告接受 Windows ZIP。本轮只产出分支候选及 dry-run CI 制品。

### 3.3 核心能力与外部供应方

全部 73 个登记项形成一个可生成的平台状态表，列 implemented/unsupported、provider_missing、native_verified/not_run 与实际验证版本。不要把声明 Windows 的 42 项直接标为已验。

核心纯 Python 工具、Case/revision、配置/清单/轨迹/表现/性能检查均须在 Windows 原生执行正反例。对可选能力优先接通 wxapkg/XAPK/Cocos 分析、UnityPy、Node/Acorn、.NET/Cecil、AssetRipper、IL2CPP 工具、ffmpeg/ffprobe 和 Unity CLI 的 Windows 原生路径；逐个校验 argv、probe、缺失反馈与至少两种合成输入。上游没有 Windows 构建或本次无法取得许可/设备的供应方要明确保留边界，禁止为了平台表全绿伪造可用。

Unity Editor/商业插件/外部供应方仍由使用者另行准备。Windows Unity 连接、导入/制作和目标 Player 单独立门，不能用生成器静态输出代替 Editor 成功；普通全新 CLI 工具使用无需先安装所有外部软件。

## 4. docs 目标结构与迁移原则

日常入口收敛为导航页与六份核心文档：

| 目标 | 唯一职责 | 主要来源 |
| --- | --- | --- |
| docs/README.md | 按用户任务导航；链接当前版本与支持矩阵 | README 的长目录、现有分散索引 |
| docs/安装与平台.md | 完整插件/源码/文档包，Windows/Mac，安装、升级、回退、支持边界 | Skill构建与安装、工具集成与平台支持、兼容与迁移的现行部分、验证范围与限制 |
| docs/使用指南.md | 从检查输入到执行工具、看回执、管理证据的完整最小任务流程 | 使用指南；不再重复安装和完整操作目录 |
| docs/接口与证据说明.md | CLI/MCP 参数、错误、Case/revision、身份与预算 | 保留现有唯一生成操作表和协议说明 |
| docs/Unity指南.md | 配置/生成/恢复/框架/参考消费者的选择与串联 | 五篇 Unity 入口；详细制作约束链接技能和对应包 README |
| docs/维护与发布.md | 架构边界、开发、文档/技能生成、依赖、验证、构建/发布 dry run | 维护指南、架构设计、公开分发规则、Release自动发布、工作区接入 |
| docs/故障排查.md | 按实际症状定位：装不上、MCP启动失败、provider缺失、路径、锁、超时、Editor失败 | 从现有文档抽取；错误名链接生成契约，避免另写支持状态 |

六份文档是信息架构目标，不以篇数为由删除必要契约。每篇只保留用途、前提、可复制步骤、结果、失败处理及限制；详细示例按需引用，避免形成一篇数万字综合手册。README 保留产品定位、短安装入口、能力状态和 docs 导航。

逐文件动作以 inventory 中的 77 项为起始，每项都必须从 planned 变为 executed/retained_with_reason，记录新路径、旧/新 hash、调用方更新和验证。新增文件也补入收口清单。

- 16 份顶层文档按清单合并；不重复保留完整旧正文。若需要兼容旧外链，用一次性的路径/锚点迁移表或精简跳转页，不能创建另一套长期教程。
- `docs/providers/`、`docs/tools/`只保留仍被 registry/实现消费的专业接入与格式契约；单一模块细节优先放其已有 README，不移走许可原件。
- 已完成、被当前规范覆盖的过程文档从工作树退出；由基线提交/既有版本标签追溯，不再把全部旧 docs 挪到一个新 archive 树冒充精简。先提炼仍有效的约束并处理所有现行引用。
- 尚有价值但未完成的设计提案集中为 `proposals/`，写明未实现范围；精炼正文并引用冻结历史，不能让提案混入默认使用路径。被工具/测试实际引用的示例要保留为有归属的 fixture，不能按目录批量删除。
- 不可变脱敏验证报告移到 `validation/releases/`，逐字节保留，建立一个当前索引；禁止改写旧版本结论/数字/哈希。当前能力状态从新报告生成，旧报告不能替代 Windows 验收。
- 技能的流程规范继续以 `plugin/` 为唯一来源；docs 不复制一套恢复流程。同步更新 workflows、registry、脚本、CLI help、Skill 相对链接、生成器和分发验证。
- 默认完整插件/纯文档 Skill 不再携带无消费者的历史过程树；保留许可、真实调用必需文档和解释边界。源包、插件包、文档包分别检查闭包。

## 5. 分阶段执行清单

| 阶段 | 依赖 | 修改与输出 | 完成检查 |
| --- | --- | --- | --- |
| P0 基线及反例 | 无 | 核对 main/分支身份；保留现有 Mac 全套回归；生成工具平台矩阵、文档消费/锚点清单、Windows 环境清单 | 能重现锁、目录发布、进程清理和插件启动缺口；Windows原生可执行环境确认，缺环境时继续独立实现 |
| P1 跨平台核心 | P0 | 文件锁、目录发布、进程所有权模块；统一调用方及错误回执；UTF-8/路径处理 | Windows 原生的竞争创建、锁并发、进程树、错误/取消反例通过；Mac/Linux原行为保持 |
| P2 完整插件 | P1 | 目标矩阵、Windows运行时锁/许可、启动配置、归档/清单投影与身份 | 干净Windows无系统Python/uv/Git条件下启动；异目录/普通用户/离线/只读安装验证；Mac包重建回归 |
| P3 供应方和Unity接入 | P1/P2 | 逐项处理registry平台路由；Windows原生命令/依赖检查；Unity生成/恢复路径 | 相应输入/失败反例与真实 provider 样本；Unity门单列，不改判为静态通过 |
| P4 docs 收敛 | P0；最终措辞依P1–P3 | 六份核心文档、专业契约、精炼提案、不可变验证索引；逐文件处置/链接映射 | 当前导航不含过期状态；全部消费路径与锚点有效；三类分发包无断链、无冗余过程正文 |
| P5 原生CI与安装 | P2–P4 | Windows完整测试和打包job；Mac回归；跨平台共享/独立验收实现；实际Codex客户端验证 | 按G0–G6给出证据，不能仅改 job 名或扩大 allowlist；报告绑定同一源码/制品 |
| P6 分支候选交付 | P5 | 干净提交、候选制品/校验和、开发总结、剩余阻塞、回退说明 | 可评审且可复验；main及已发布tag未变化，不自动合并/发布/安装 |

P1 与 P4 的独立工作可交替推进；平台差异和文档引用移动各自提交，避免难以审查的大杂烩。不要重复创建第二套 launcher、registry 或维护记录。每个安全节点记录结果后直接进入下一项。

## 6. 验收门与必需反例

| 门 | 必须通过的范围 |
| --- | --- |
| G0 分支/来源 | main及v2026.10.16仍指向基线；开发仅在指定分支。源码、目标、运行时和实际制品身份绑定，工作树预览不冒充正式发布 |
| G1 文件/证据 | 多进程同Case读写、锁持有者异常退出、无权限、旧v1迁移；候选变化失效；竞争目标（包括空目录）不被覆盖，发布失败保留可恢复stage；跨卷明确失败且无半成品 |
| G2 进程 | 父/子/孙进程、父提前退出但后代持管道、超时、取消、输出超限、启动失败、嵌套Job；只清理归属进程，等待有界，日志与回执正确结束；未清理成功绝不能记capture_complete |
| G3 核心/供应方 | CLI/MCP目录一致和实际业务调用；新旧入口一致；中文/空格/元字符/只读/大小写/保留名/junction/路径长度；两个不同输入及损坏/不支持格式；缺可选工具仅影响其能力 |
| G4 插件/客户端 | Windows-x64与Mac-arm64原生构建各自连续两次可复现；干净用户环境搬移安装；使用独立解释器；禁止源读取/联网/安装写入的实际探针分别报告；Codex真实安装、技能发现、MCP工具发现和session版本；不发模型请求 |
| G5 docs | 77项及新增项都有处置结果；核心信息唯一；无已发布却标旧rc/current状态混用；本地链接/锚点、操作表、能力矩阵、Skill、公开树通过；在源包、文档包、完整插件解压副本分别走查 |
| G6 Unity及交付 | Windows实际Unity连接/所选基础生成配方导入、保存/重开、Play和构建；Editor/Player分别留证。生成工作目录不依赖源仓库或Mac路径；最终分支候选、已验/未验平台、回退方式可定位 |

Windows 隔离策略必须来自实际可执行机制（如隔离账户/ACL、可验证的进程网络限制或合适沙箱）；“换PATH/清空环境/不导入源码”不能冒充禁止网络或文件访问。机制不可用时单列该项 blocked，不能复制 Mac 的 true。不要为了测试通过关闭系统安全功能或修改用户防火墙/全局权限。

Windows Server 的原生 CLI/插件/进程回归可关闭其自动化范围，不等于 Windows 11 桌面输入或 Unity Player 体验。若本机没有 Windows 桌面/Unity许可证，优先用可用的功能分支 CI 完成原生核心，再交付可复现的桌面验收脚本和精确阻塞；不得以模拟 platform.system 或Wine证明原生支持。

合法历史证据不必重复跑；修改过的核心边界、平台行为和分发投影必须复测。测试数量不是门槛，故意跳过Windows关键项后不能宣称全量通过。

## 7. 开发规范和最终回报

- 每次提交写明问题、行为变化、验证范围；文档纯移动和内容改写分开，冻结报告只迁移不重写。
- Windows系统调用要显式定义类型宽度、句柄所有权和错误映射，维护错误分支可读性；不要依赖 Python 私有实现字段或复制未经许可的本机包装器。
- 删除前确认替代正文与消费者，保留可回退Git提交；不删除 `.private` 运行时/证据或用户项目来“清理仓库”。
- 当前项目仍使用8个技能和统一CLI/MCP执行层。Skill变更只改plugin，再同步检查；候选开发不擅自更新全局已安装插件。
- P6报告应列：实现提交、每个W/D问题状态、G0–G6证据、Windows和Mac实际运行范围、支持矩阵、文档前后处置统计、制品哈希及复验入口。不得以“代码已写完，等用户继续”结束。
- 真正缺硬件/许可证/外部授权时先完成所有独立任务，再列具体缺口、已尝试路径和解除条件；不得虚构通过。新正式版本发布与main合并等待用户后续指令。

## 8. 计划阶段检查

本计划只新增文档和文档库存，未实现上述Windows能力，未删除任何原文档、未修改main。维护会话开始前再次回读分支与源码身份，避免把其历史 `7857be1` 状态作为当前基线。以本页及随后的验收证据判断完成，不能沿用旧会话末尾的“main已合并”授权执行本轮合并。

## 9. 执行记录

- P0：已确认计划提交与 main 基线；仅推送功能分支运行原生 CI。
- P1：共享锁、无覆盖发布、Windows Job 所有权和 UTF-8 已实现。首轮 Windows Server 实测四项 OS 反例通过；全套揭示并继续修复 CRT 文件身份、源码换行、测试入口与默认编码。
- P2：已加入 windows-x64 锁、原生解释器清单、逐平台许可和包身份；尚待构建/搬移/MCP/真实 Codex 的 CI 回读。
- P4：77 项逐文件处置已执行；保留忽略的 OS 元数据原地，六份核心说明/导航、单一候选提案与不可变验证报告迁移完成；链接与语义检查通过。
- 本记录为进行中状态，G0–G6 未全部关闭；Windows 11 桌面、实际权限隔离及 Unity 仍需独立证据。
