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
