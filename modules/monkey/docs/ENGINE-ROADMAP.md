# Active v0.7 priority: complete core Prefab recovery

The active scope is [PLAN](PLAN.md): at least ten distinct core Prefabs independently accepted in Creator 3.8.8 and Unity 6000.6.2f1. Phase one requires source identity, hierarchy, static components/fields/references, fixed-state render, native persistence and regeneration. Phase two covers dynamic scripts, events, changing layouts and physical input; these no longer block static acceptance. Broader source-profile/CDN expansion below is retained as historical backlog and does not compete with this version.

> 2026-10-26最新用户裁定：默认全量C#初稿导出，允许类型/语法/API缺口；本文的严格typed/profile子集为可选增强，不再作为其他有源方法导出的门槛。现行进度和完整候选链见 [PLAN](PLAN.md)。
## 2026-10-27 当前出口：五层架构、功能类、归入源码与跨层集成

执行重写的[private planning reference]

当前已验全局规划GlobalArchitecture05：47模块、1484种子派生类型、1831来源去向、27链，所有引用的117配置/230Prefab或Scene路径来自冻结清单。来源归属与分析输入分开；实际模块生成NativeProject01已单CLI启动，输出按五层和标准候选manifest组装，48项相关定向检查通过。原生业务实现、Editor绑定、整工程编译、真实JSON/资源/输入跨层回读继续独立验收，设计/模型完成不能代替运行。

## 历史出口：2026-10-26 全量逐文件后处理（已被上方替代）

事件 `monkey-v06-full-project-postprocess-20261026-01`；本聊天已原生回读总监 turn `[private identifier]` / human `[private identifier]`。用户明确要求全量资源/代码项目恢复，Codex也必须实际批量处理全量，可以有错误，不能以少量测试结束。执行权威计划 §5B 最新全文。先前两方法调用只证明封装可用；5A、3a0391a、ca0350a及07证据保留，**全量后处理未完成，v0.6继续开发/实际跑全队列**。

以manifest自动发现07完整5,522 C#、19,571索引方法、47,384函数映射；按源/模块/依赖分批，实际分析/修订每个文件并记录具体保留或修改理由、未决项。项目prepare/run/status/resume、失败隔离/精确session、多批连续串行；旧全任务一次session/resume及一次模块调用上限被覆盖，单批预算/有限重试仍保护空转。继承模型/上下文/登录配置，不降级；额度/认证/权限真实阻塞保留pending并如实报，不换通道。独立完整AI修订工程含资源、Scene/Prefab、JSON和源映射，07/冻结资源/正式游戏/GREA/beaver只读，无发布/推送/全局安装。

主体为真实全量处理；复用61检查/资源证据，不重跑旧原生套件。所有就绪批连续执行，不能以调度器或新小样完成而停工；版本或严重问题反馈，不等逐批ACK。


# 已批准后续来源扩展

本路线沿唯一PLAN执行，不另建任务表。用户原生授权见SUPPORT-MATRIX.md；工作版本U/C不是预先声明发布号或已支持状态。

## 当前路线覆盖：v0.6 C# 合并大版本

以 MONKEY-V06-CSHARP-PLAN (local path omitted) 和唯一 [PLAN](PLAN.md) 的C1–C9为当前范围：原06-A/B/C/D、原建议C# v0.7以及后续原C#脚本恢复/依赖/字段事件/Unity接线/增量/编译交接一次纳入v0.6。先样例项目完整脚本→真实方法模块→跨类依赖与原生绑定，再按不同合同推进Mono与IL2CPP/WASM。至少3个有分支/集合/调用的真实代表模块及1组Unity有限可操作子集；签名/数值getter/草稿不算方法实现。

本地0.6.0.dev1已完成合并候选4模块16方法、原JSON及入口选择/类型依赖/真实lowering链；原12方法证据沿用，新4数学方法和裁剪3方法链已编译并独立验证，合并16方法再次编译。2模块9方法的Unity有限流程已完成6次系统指针操作、事件解绑/保存重开；测试adapter与原生命周期恢复分开。样例项目已补精确segment/map/body链、8纯运算C#片段，13波次/触发方法按字段布局/调用目标缺口保留。分支codex/v0.6-csharp-recovery，详见[续推验收](validation/2026-10-26-v060-continuation.md)。v0.5受限基线不改，广泛新引擎/CDN仍为后续来源路线。人工工程编辑/三方采用/新业务/发布构建归beaver；下方历史版本表不覆盖当前合并决定。

## 历史版本规划：v0.5 – v0.7（2026-10-26，职责整改后）

本节仍是 PLAN 的范围与验收定义，不另设任务源。用户已批准开始 v0.5；在途 0.5.0.dev1 与已发布/安装的 MIT v0.4.0 分开。随后批准三产品职责：**monkey 恢复候选，beaver 操作开发工程，GREA 管流程和路由**。依据 三产品计划 (local path omitted)；下面覆盖此前“monkey adopt/构建/更新”的版本草案，不抹掉实际 WIP 与验证。

### 基线与约束

- `monkey-project/2.0.0` 目录保持：Unity `Assets/Game/Content/<Type>/<Module>/`，Creator `assets/resources/<Type>/<Module>/`；PascalCase 目录、拼音文件、唯一 Textures、JSON 数值真源。
- 样例项目 601 容器/81,580 对象：81,544 成功、36 未完整解析；939 个预算失败已在 v0.4 解决。其 164,599 文件/3,267,184,074 字节候选已通过本轮新预算与全量哈希，不等于 36 对象恢复或运行通过。
- 样例项目原生结构代表证据与视觉/业务分开。Tiled Sprite、派生动画超长名、紧密图集、Spine/Shader 可用子集继续由 monkey 修正候选；不能转交 beaver 后就省略恢复缺口。
- “87 缺脚本”需复现并绑定样本，不与 57 缺失 GUID/17,495 引用互换。528 JSON 需按角色分类；914 模块/10,607 方法/0 实现是既有样例项目批量初版口径，工具已有有限数值子集，不外推任意方法可恢复。
- 正式游戏/GREA 只读；样例项目为架构整改的开发试点但本工具不接管它；样例项目继续暂停。仅用 monkey 自有来源/输出核验，不新启样例项目原生工程。本轮不推送/发布/全局安装。

### v0.5.0：大工程恢复候选与资源收口

顺序：先 05-A；05-B 在途采用代码冻结移交 beaver；monkey 接着处理 05-C，05-D 随组更新。主开发负责共享接口和窗口，独立完整模块按现行通用模块规范登记，不改变产品范围。

| 工作包 | monkey 范围 | 验收与当前状态 |
|---|---|---|
| 05-A 大工程与复用合同 | 完整候选 8 GiB/50 万文件；选择集仍 256 MiB/2 万；单文件 512 MiB。manifest 128 MiB/800 万节点；流式哈希/复制，POSIX 有界 no-follow 读取。inspect/normalize 绑定源、reader/schema、I/O 与库身份；布局/目标发射器独立 | 样例项目双端、样例项目全量清单/字节通过；原包读取/图片解码/worker 被禁止时实际复用通过；布局/版本变化不误失效，reader/I/O 变化拒绝旧缓存，篡改/缺块拒绝。保留现有检查点；未声称任意旧缓存免重读 |
| 05-B 采用实现交接 | monkey 保留候选合同、身份/路径映射与候选差异；开发工程三方冲突、apply/rollback 和原生修改交 beaver | 冻结本地 commit/文件哈希/许可/依赖/调用方/测试及未验清单。旧 CLI 受限 deprecated compatibility 保留；替代经实际消费验证后再退休，不伪造 beaver 成功路由。详见 BEAVER-HANDOFF |
| 05-C 原生资源与引用阻断 | 36 对象的 19 Image+10 Text+3 TMP 按精确布局；4 自定义组件按证据恢复或隔离。借用类型树字段须源/目标身份及独立对照；紧密图集/Tiled/超长动画名；Spine 版本清单与合法 runtime 代表子集、常见 Shader profile | 严格字节/字段/PPtr 核对；真实源资源→候选保存重开/显示。代表 Spine 导入播放、材质编译与固定视图有证据；未知项保留缺口，不以默认字段或放宽读取消除错误。**部分完成**：72 基础引用、2 派生路径、21 Tiled 原生分配/拓扑、3 紧密 Sprite 几何/UV 已验；标准 3.8.99 Spine 两份原生时间/姿态/引用已验；精确单 Shader 的原生材质/编译/Metal 像素已验。36 正文 schema/字段写回仍阻断，未知版本/效果隔离。见 validation/2026-10-26-v050-operations-resources.md |
| 05-D 诊断与使用基础 | acquisition/解析/导出/引用/原生诊断聚合，源 ID→目标位置/影响/动作。显式清单补取、有界重试/缓存验证；环境、文档/CI/空间预估与清理预览 | 404、缺引用、未转写、缺 runtime 分层；逐项处置，清理保护原件/人工/当前候选；声明平台的 CLI/隔离安装实际烟测。本地实现与相关回归已完成；macOS 隔离安装 159 文件/13 CLI 检查通过，Linux/Windows CI 已定义但未远端运行。见 V0.5-OPERATIONS.md |

出口：声明 profile 下的候选及资源缺口可定位、可重复、与 producer/输入/类型身份绑定；05-A/C/D 各自验收。beaver 采用验收单列，不能用它代替候选恢复正确性；不以采用器已交接宣称 v0.5 完成。

### v0.6.0：原方法、字段、事件和配置恢复

| 工作包 | monkey 范围 | 验收要求 |
|---|---|---|
| 06-A 大 JS/有据转写 | 复现固定 SHA 的约 7MB game.js AST 失败，区分语法/包装/预算/模块/provider；保留模块及字节区间，扩展明确纯函数/条件/循环/数据操作子集。C# 与默认 TS，JS 可选 | 不执行原脚本；分开统计总方法/可解析/可转写/实际转写/行为已验；边界反例和独立结果验证，不生成假业务 |
| 06-B 原字段/事件/组件绑定 | 原类/继承/字段/PPtr/事件→目标可证明的脚本/对象；IL2CPP 签名与方法体、TypeTree 与猜测分开；复用 05-C 写回合同 | 明确闭合子集字段/引用保存重开一致；重核缺脚本分母，未知项隔离；不以签名壳或假 Button 回调冒充功能 |
| 06-C 原配置与类型证据 | 分类 528 JSON 的数值/语言/地区/其他角色，解码原格式并保真导出正式 UTF-8 JSON；来源字段/ID/大整数/空值/覆盖规则证据 | 原始值与导出逐字段对照，重复 ID/坏引用可定位；人工产品 schema/DTO 制作和 Player 加载框架归 beaver，不在 monkey 另造运行框架 |
| 06-D 原动态键与效果 | 源键→稳定目标 ID/地址/类型映射，恢复有据加载调用的有限语义；明确 Spine/动画事件/材质子集 | 重命名不丢映射，未知拼接键显式诊断；不把新工程的 Addressables/Bundle 后端算作源恢复 |

出口：固定代表源模块得到可追溯代码/字段/配置候选，目标编译与有据行为子集验证；完整游戏业务与人工工程持续开发由对应主开发者/beaver 承接。

### v0.7.0：来源 profile 与原版远端闭包

| 工作包 | monkey 范围 | 验收要求 |
|---|---|---|
| 07-A 原版远端资源 | 从固定配置/静态加载代码推导精确版本 URL 清单，原版 CDN 补取、缓存身份/错误分类/续取；不执行 JS、不猜目录枚举 | 来源→清单→下载字节→候选可追溯；404/拒绝/过期保留缺件，不承诺找回服务端不存在的键；联网限已批准原始来源 |
| 07-B 明确 source profile 扩展 | 一个有据家族/版本/格式逐个实现，候选优先 Egret EUI；Cocos 全版本、Unity 全版本和其他引擎是范围方向，不是已支持声明 | 来源/reader/schema/provider 固定，真实样本与合成反例一致；不混“通用图片提取”与图/代码恢复 |
| 07-C 恢复覆盖深化 | 补声明 profile 的结构、模板/override、动态布局/资源语义，复用共享 IR 与目标发射器 | 按代表语义核身份/绑定/保存重开/显示；未支持与缺源单列，不把不同引擎用同一猜测解析器硬套 |
| 07-D 候选交接 | producer/能力/实现身份、输入闭包、逐资源映射、归属、草稿/原配置/运行配置、缺口及验证层随版本文件交付 | beaver/GREA 只消费冻结结果；源解析共因仍归 monkey，不在 beaver 复制 reader；候选 pass 不升级为 Player/视觉/业务 pass |

新工程 Addressables/AssetBundle/Creator Bundle、微信打包、Player 构建、UI/运行框架生成、内容更新回退均由 beaver 提供；GREA 负责方法/路由与依赖锁定。没有 beaver 已验能力时明确阻塞相关执行，不让 monkey 继续兼任。

## 顺序与架构

样例项目full14单命令双端资源原生强回读已零诊断完成，业务/视觉/交互与源行为handoff继续明确保留。当前推进U（Unity来源→Unity6），再C（Cocos3和旧格式扩展），同一立项不重复询问。不新增Agent、不改模型/上下文、不改GREA、不全局安装或下载引擎，不发布/推送，不恢复暂停游戏开发。

Python核心保留统一输入/容器安全、来源身份、资源全账、可读命名、阶段签名与可控接续、目标计划、诊断和AI接续。Unity来源采用自己的typed对象/PPtr/GUID/fileID/pathID契约，不强塞成Cocos节点图；Cocos2/3的序列化适配独立，仅共享证明可等价的UI/资源语义。目标只使用原生对象/组件，Unity Player不嵌源引擎解释器。原名映射对两源家族统一适用。

CLI继续convert --source/--input-set --target unity6|cocos38|both。加入真实source-family/version探测及有依据的显式profile；用户2026-10-23补充：Unity来源无论版本，目标一律Unity6，不保留旧目标版本分支；此目标规则不等于各版本解析已支持。Unity来源选择cocos38/both必须拒绝。能力检测、工具可调用、真实解析、Editor导入、业务分别报告。unknown不伪造工程版本或默认最近reader。

## U：指定Unity来源样本

用户指定最新打开《样例项目》。旧source archive身份[private source identity]/本地修订273/Unity2021.3.30f1 IL2CPP-Wasm仅作线索。2026-10-23本轮只读检查已知对应账号的当前可见包目录，仅发现修订273，内有__WITHOUT_MULTI_PLUGINCODE__.wxapkg、_wasmcode_.wxapkg、_wasmcode1_.wxapkg；这还不是当前Unity版本/后端正文核验，不能只凭旧记录或mtime宣称已验证最新运行内容。本轮已通过固定本机grea:wxapkg-decrypt在monkey私有目录重新解密这3个当前包，明文SHA全部与冻结证据一致；分别3/2/48条目，game.js实际出现2021.3.30f1版本字符串，Wasm条目可枚举。初始仅为当前包体静态证据；后续只读调用本机UnityPy1.25.3，已解析source archive同源data.unity3d（2637008字节、SHA [private fingerprint omitted]）1603对象，包括76 GameObject/76 Transform与RectTransform/1173 MonoScript。8个serialized file均关闭源TypeTree，UnityPy按版本内置类型模板对1326个所选对象有严格正文读数，全部106 MonoBehaviour因类型正文不足严格报长度不符，不使用check_read=false掩盖；这是样本探查，不是通用reader或原生工程通过。证据monkey/.private/unity-sample-project-current-01/typed-inspection-01，未执行源代码。原件/玩家档不写。当前721个已枚举缓存路径均存在，data archive SHA与冻结证据一致；patchFuncIndexList.json从94变111字节单独记漂移，不宣称所有当前缓存与旧版相同。12个TextAsset逐项身份已核：DodGameLib.dll实际为CODEPHPY头、不是普通PE，不能按文件名当可反编译业务DLL；其余5个PE仅观察头部，未执行程序集。

先发现本机可用且版本固定的AssetRipper/UnityPy/提取provider和GREA既有合同，只读复用、固定参数/输出schema，不重写Unity二进制生态。缺工具/TypeTree/元数据列条件，不自动安装。未知DLL/JS/Wasm从不执行。枚举Unity数据目录/AssetBundle/serializedFile及显式容器解包关系，保留GUID/fileID/PPtr、原名/路径、Prefab/Scene、Transform/材质/Shader/字体/模型/音频/配置。

Mono托管实现与IL2CPP/Wasm元数据/方法体分别分层；只有签名/空壳时进入SourceRecovery编译排除区，不声称业务恢复或编译通过。跨版本兼容在隔离候选与目标Editor原生API内有据处理，不靠改ProjectVersion或重做UI伪造恢复。保留对象引用SO；正式数值JSON遵既有约定，不破坏性机械转SO。

出口为真实已取得资源得到可追溯Unity6候选，代表原Prefab/Scene实际导入/引用回读/缺脚本报告/保存重开与显示；整个游戏可玩另验。Unity6和其他旧版本各需要有据样本，不能以该例泛化全家族。

## C：Cocos3和旧格式

首样《下方了》：source archive/games/下方了/Analysis/source-work-20261021/__WITHOUT_MULTI_PLUGINCODE__/app-config.json的gamePlugins.cocos.version实际为3.8.7。该字段是插件引擎声明；正文、UUID/pack/CCON/import/native可用性仍需核。旧身份wx8310ec5d413eee82/修订70，不保证最新或完整资源。

reader按3.x真实序列化、UUID子资源、redirect/bundle/pack、System/JS模块和依赖；新增UITransform/UIOpacity/Canvas/层/坐标差异，unsupported明确隔离。输出Creator3.8尽量保留同源结构/身份；输出Unity6复用原生目标薄层，不能用2.4 parser猜3.x。2.1/1.x等按已取得样本逐profile扩展，不把Cocos2d-x与Creator混同。

出口为《下方了》明确输入→两套独立候选、Creator真实导入/保存重开/代表UI引用回读；Unity只对本轮新增语义作必要验证，不做无关全平台/逐场景矩阵。source archive只读选样，不新建游戏开发项目。

## 后续来源家族

用户本聊天补充范围：Cocos所有版本原包输出Unity6/Cocos3.8.8或both；Unity所有版本、Laya/LayaAir、Egret（用户写作Eraget）、自研及其他引擎原包统一输出Unity6。后续扩展不改变当前样例项目、U、C顺序；按取得样本逐来源识别和独立reader适配，未知不套用Cocos图或假称已支持。非Cocos来源请求cocos38/both一律拒绝。

## 原包与远程资源闭包

沿本聊天CDN/远程包补充授权，一键入口需覆盖原包明确声明的远程资源：已有本地缓存先核SHA复用，有据URL有界获取并记实际HTTP/哈希/缺失收据，未知miniGame地址不猜。样例项目19次GET/16627本地文件核对已经完成；通用CLI明确清单有界获取及缓存SHA复用已接入convert --remote-manifest，真实单GET和16627全缓存核验分别有据；未知URL自动发现尚未实现，不以人工收据冒充通用地址发现。
