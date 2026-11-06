# 通用审计整改技术记录（2026-11-05）

本记录映射 GREA 唯一任务 `grea:T-monkey-audit-remediation-dual-review`。原审计对象为 `84d3451` 与 dev11 WIP；当前集成基线为 `2ac8e5e` 与 dev25 通用修复。人类授权已原生核验：`01a1a95b-4d69-73e2-abde-24f8b8cf8b42`。固定候选交付后由总监与 Claude CLI 对同一字节独立复审；本记录不是放行决定或独立产品计划。

| 项 | 当前代码与处置 | 证据边界 |
| --- | --- | --- |
| A1 | `fd78d14` 起传播原生诊断，按完整源组件集合生成覆盖和静态呈现维度；`unity_verification_contract` 与 `unity_diagnostic_resolution` 只按精确当前身份与对应领域证据注释已解决项，保留原始诊断。Player 与 runtime 未执行均为 `not_run`。 | 新组合检查执行真实 normalization→assess→reconcile→statuses，不替换这些函数；完整静态、显式动态边界、缺组件、未知组件、缺可见证明及坏身份/字段均覆盖。协议夹具不是 Unity 运行证据。 |
| A2 | 既有代码接受合法 `imported/pass/partial`；当前进一步共用状态枚举，冻结要求已定义的 source graph scope、真正的整数零 missingScripts、布尔成功的 edit/save/reopen，并继续文件哈希、完整验证、组件分母与静态呈现检查。 | 错状态/版本/源图状态及漂移仍拒绝；现有状态门检查没有替换状态门，下游替代的既有用例仅算该门定向检查。完整真实导入与冻结另按固定候选实际结果记录。 |
| A3 | `fd78d14` 与 `273d127` 已将 Creator 的全部 plan.components 与源诊断贯通，convertible 只限制创建子集。当前再修正最终诊断汇总：未知/静态错误不能只使顶层 partial 而静态分项仍 pass；Editor 失败也阻止静态呈现 pass。 | 生产 verify 分母反例与真实 assess→Creator summary 组合验证覆盖未知、引用、字段、文件失败及三类精确动态正例；42项相关检查通过，Creator Editor 未运行。 |
| A4 | 独立验证禁用非渲染 Spine 数据载体和源字节保留，只有精确 sidecar 绑定的 SkeletonGraphic 可关闭源可见渲染缺口。 | 保留验证可以 pass；缺图时 native/static presentation 保持 partial。组合反例执行现有真实门，未将协议行称作原生可见结果。 |
| A5 | `unity_prefab_source_ui`、recovery manifest 与原生 readback 已分开 targetCanRender/sourceStaticSemanticsVerified。无独立原始方法清单时 staticSemanticsProven=false，限制进入 root partial。 | Image/Text/RawImage 的生产 proposal 正反路径已检验；独立方法清单仍缺，未知源行为仍未恢复。 |
| A6 | `fd78d14` 已消除原63位摘要；当前再让生产 Creator Spine reader 核验拥有阶段所固定的原始 source manifest 文件字节，并严格检查64位小写十六进制材料合同摘要。保留数据、呈现和 Slider 真实字节/字段门按调用链复核。 | 新正反例经过真实 reader；输入 manifest 漂移/坏摘要会拒绝。未接线的 prefab_spine_components helper 仍为 tests-only。Creator reader 接受固定 provider 回执作中间态，但在没有原始 material-contract/engine 字节闭包的独立核验时明确写 receipt-only provenance，并发出 SPINE_MATERIAL_ORIGIN_NOT_VERIFIED；该缺口阻止最终静态分项 pass。不能用重复摘要相等冒充来源核验。 |
| A7 | 历史业务能力限定为显式 opt-in legacy extension；核心保留通用合同与薄装载边界，默认 Prefab 链不选择业务 profile。 | 保留精确 source/class/method/table 身份拒绝，扩展输出保持选定调用域、行为/编译/原生未验边界。具体装载与包资源记录在固定索引。 |
| A8 | InputField 完整 inherited TypeTree 与 Unity core 字段检查已接到 `script_proposals→propose_schema`，缺/多/改类型给 gap；行为仍为 disabled-unavailable。字体合并按每个标签的 Unicode 标量核对计数/缺字/聚合记录，并按字体身份合并重复标量，不能丢掉新字符明细。 | InputField 与 A5 合计41项；证据字体相关73项/6子例。已保存17标签与52标签回执均通过只读检查；52标签为350次必需字符出现、145个标量行，未重新生成或重新验收136-glyph SDF输出。两套旧字体测试因缺失私有 Pure01–03 样本产生4失败/9 setup errors，不计通过。字段完整不证明原行为已恢复；无调用者的旧 helper 不宣称通用能力。 |

dev25 字体角色修复按通用错误分类纳入本集成：主字体、跨字体 fallback、同字体多图集、Sprite 和空槽均有严格证据路由。已保存角色样本与生命周期模型分别报告；未观测的30组不标实测。原生19、固定24、原审计快照与各次失败均不改写。两批产品的新转换/采用停止，后续原生调用仅限本次审计必要最小复现，由 GREA 执行。

项目专用原件、候选和审计原始日志不进入源码包。兼容字段 `staticValidation` 表示生成文件完整性，不替代完整源组件覆盖、`nativeStaticValidation`、数据保留或静态呈现结论。

本地完整证据索引在 `.private/audit-remediation-20261105/`；固定源码/包摘要、测试总数和实际原生结果以交付索引为准。

## dev26：最小导出暴露的可选 Spine 依赖回归

GREA 的 dev25 实际最小导入失败：无 Spine 来源的导出仍包含强依赖 Spine SDK/factory 的桥接脚本。dev26 从生产导出选择处修复，普通排序代理保持 SDK 独立；只有合法且完整的 staticSpineRendering 合同才选择真实适配器。声明需要适配器但未注册、合同损坏或对应组件缺失均拒绝。来源 pin 的传递独立于 outline 等其他模块。两份行为探针的 .cs.meta 使用原字节/GUID 纳入包，不作为非产品文件排除。

569 项回归和91子例通过。另三组完整导出源码编译检查通过：两个无 Spine 夹具均由生产 exporter 生成65个 C# 文件，使用实际 Unity6000.6.2f1/TMP/uGUI 引用且无 Spine DLL；既有 actual-export19 的121个文件离线替换五个当前包模板，缺 SDK 时失败，加入其已固定的 Spine3.8.99 DLL 后通过。该重放未执行真实游戏 export 或 Editor，不替代 GREA 新最小导入、完整验证与冻结。dev25 的失败、固定源码和 wheel 保留；两批产品仍停止，双人同字节复审未放行。

## dev27：真实 JsonUtility 可选 Mask 空值语义

GREA68 在独立失败26副本用 Unity6000.6.2f1 执行固定微检查（回执 SHA256 `89d92002afd4b998c7669ef4a7cbd8826a18e34357de8a619a2f8ccc3363222b`）。16例确认 absent/null/{} 均物化非null Mask对象，null/{}还物化空sourceEngine。无Mask原文被错误拒绝；已有6Mask有效合同通过，缺行、坏schema、坏pin仍拒。原工程196文件及输入pin未变。

生产 exporter 按原合同非null写 staticMasksPresent；{}保留显式声明并由校验拒绝，不能伪造空合同。创建、Prefab刷新、保存回读及字段绑定统一使用存在门与完整源cc.Mask分母，有源Mask时不因无队列免除合同。非空现代payload与false marker冲突拒绝；schema1旧合同仍检查源ID集合和manifest pin。纯managed门测试手工构造已观测DTO，仅证明生产门逻辑；真实JsonUtility由GREA回执及下一固定27复验说明。

同类对象已核对：layoutCompletion/bitmapMissingGlyphs依schema短路，previewState依stateSha256，materialBinding依profile，systemFontBinding依prepared状态，staticRetainedAssets依精确schema，tmpResources依实际TMP需求。未发现同样的Mask空行崩溃；这不证明其他模块的source requiredness已完整，不扩大本轮实现。固定27仍须同微检查的26例扩展、最小全链、严格冻结和9拷贝控制，再由总监与Claude同字节独立复审。

## dev28：同字节双审退修的四组出口

原dev27归档、wheel、矩阵与总监/Claude意见保留。四组整改接到实际生产入口：

| 组 | 行为与证明范围 | 验证边界 |
| --- | --- | --- |
| 组件身份/呈现 | 源ID、计划Prefab/节点、组件角色、真实GUID/localID双向核对；派生顶层摘要不能代替所属Prefab行。原生启用状态与源状态、呈现行必须一致。真实GetComponents库存记录类型继承、enabled、资产身份及实际Prefab对应源链。 | 库存仅涵盖源映射节点；不宣称覆盖整个生成子树。旧readback缺库存明确partial，保留原件。共享layout槽、Label/Outline及Mask附属Graphic单列来源；Spine renderer须原完整typed sidecar及实际物理库存交接，保留carrier数据不能代替图像。 |
| 判定与退出码 | 共同unresolved_diagnostics复核当前保存身份及命名要求，原始诊断保留。精确解决的创建诊断与语义正确的纯Button业务限制不压静态；Scroll仅在轴/content/viewport与保存RectTransform身份闭包验证后保留动态物理限制。 | 原始resolution布尔不授予通过。Scroll实际字段在重证后漂移继续拒绝。系统字体平台限制只在独立字体/来源OS/Canvas/栅格化证明齐备时按已声明范围解决，没有新增来源时保留缺口。 |
| 三个公开消费者 | verify、选择冻结、资源封存共用实际producer状态、精确版本、0 Missing Script、保存重读、场景重开、图范围、当前import-plan及source manifest pin。选择冻结还要求全源静态与呈现通过。 | 资源封存仅为模块组合保留库存：sourceAcceptance=not_granted。无缺口退出0；保留有验证缺口的库存标partial并退出1；错误保存状态/哈希/范围退出2。完整当前验证报告随封存固定，组合工程仍须重新验收。 |
| Creator/Mask生产 | Creator真实readSaved产生绑定保存场景节点/组件UUID、活动状态、几何与Sprite/Text资源的typed renderer行，消费方不再接受几个布尔字段作正例；不支持的renderer保留gap。矩形Mask缺/错合同在export创建输出前拒绝，合法legacy与现代合同保留完整来源分母和可映射字段校验。 | 真实Creator SDK与必要Unity最小原生由GREA执行。Node对象模型/协议夹具不冒充Editor。源物理、原版视觉、Player及两批产品采用均不由这些静态证据授予。 |

本轮源/协议回归为668项、102子检查；三组SDK引用编译通过（两个65源文件无Spine、既有121源文件Spine集合离线替换当前模板），另66源文件的物理库存微检查脚本编译通过。Creator Node检查6项通过。均不冒充新的Editor或Player结果。精确源码、逐案复现脚本、原始结果、安装wheel与SDK引用编译证据保存于私有dev28交接目录。新固定候选必须再经过GREA必要最小原生检查以及总监/Claude同字节复审。

## dev29：真实正例退修与两线首包集成

GREA73实测固定28：Sprite两正例三入口误拒，7个反例按期拒；Scroll另有非可视组件sourceVisible误标与跨资产身份误等，Creator在owned teardown把ToDestroy误判成Destroyed。原readback与失败结果保留原字节。新生产者分别读取独立源Prefab和保存重开场景；消费者只在各自范围核物理ID，通过冻结源ID/节点/角色关联语义，绝不补造不存在的Prefab链。旧28缺新sceneComponents仍partial，不把改写旧回读当原生正例。Creator只清理精确owned root，不清空用户全局延迟销毁队列。

A线59f7c7d/ad6437a的128MiB既定生成预算、Progress存在谓词与Button源renderer交接已接共享入口。真实100,783,915字节IR可出计划，但新196,238,948字节计划超现行stage/export上限，当前仍须分批，不宣称整包导出完成。两个历史Mask失败根的4个Mask已用真实固定引擎字节、原manifest内置材质/效果，经生产build_contract和export预检重放；这不是公开转换或原生通过。显式坏材质引用不借默认材质通过。

B线15fe2f0的可证明静态脚本模块接入`monkey static-code-bindings`公开入口；prepare/stage/destinations均不自动启动Editor。字段完整、partial/blocked/not_executed及业务未执行分别保留；公开操作保留缺口退出1、坏输入退出2。原B线候选的93实例保存冷重开及61反例是其固定旧基线回执，不冒充集成候选原生验证。A线40图与B线5681全量去向仍由GREA单一计划管理。最终固定源码和wheel须再做受影响原生正例/拒绝例及同字节独立双审，正式采用保持HOLD。

B线后续fb5822d/5cc8d73已补入，公开目的地审计复核冷重开Prefab/脚本字节与GUID、唯一实例、字段分母及未解析声明别名。最新固定label-fix01由B线实证51完整/42部分、Master的两个TMP引用已指向实际源节点；仍不冒充集成候选回执。共享CLI export路由也改为既定128MiB hash-owned stage读取；41,943,739字节自编填充计划通过公开导出，原普通32MiB读取拒绝，输入哈希未变，未启动Editor。

整合源/协议回归726项、132子检查通过；SDK矩阵4项通过：两个65源文件普通出口、66源文件可选静态脚本helper、121源文件既有Spine集合替换12个当前模板（无SDK按期失败，有固定SDK通过）。Creator Node15项通过。均为离线证据，集成候选真实原生仍待GREA执行。
