# 本地反馈与交接示例

复用既有operations_preview、compatibility_plan和inspect-target，不增加运营服务或另一套调度器。输入来自已验的自有合成fixture；**不是LC2 Player输入日志，也不是真实玩家数据**。LC2原始日志缺运营事件的时间/会话/版本合同，不能补造字段后冒充观测事实。

本例只有一个start、没有finish，合成漏斗为[1,0]；没有session_start活跃事件，因此没有D1结果。数据不足以建议提高奖励。reward1→2只是原有手工配置候选，用于演示有限diff和兼容预览，不是分析器给出的调优建议。新配置没有应用，未选择商业平台。

从GREA仓库根执行以下命令；安装版可替换为对应GREA入口。输出为新临时目录，输入只读，重跑另建目录：

```sh
grea_feedback_run=$(mktemp -d /tmp/grea-feedback.XXXXXX)
grea_feedback_inputs=tools/lifecycle-feedback/inputs
mkdir "$grea_feedback_run/results"

bin/grea legacy operations_preview events --input "$grea_feedback_inputs/events.jsonl" --start 2026-10-20T00:00:00+08:00 --end 2026-10-22T00:00:00+08:00 --as-of 2026-10-22T00:00:00+08:00 --timezone Asia/Shanghai --steps start,finish --active-event session_start --data-kind simulation --output "$grea_feedback_run/results/analysis"

bin/grea legacy operations_preview config --before "$grea_feedback_inputs/old-config.json" --after "$grea_feedback_inputs/new-config.json" --schema "$grea_feedback_inputs/config-schema.json" --target "$grea_feedback_inputs/target.json" --output "$grea_feedback_run/results/config-preview"

bin/grea legacy compatibility_plan --before "$grea_feedback_inputs/before.json" --after "$grea_feedback_inputs/after.json" --sample "$grea_feedback_inputs/sample-save.json" --output "$grea_feedback_run/results/compatibility"
```

读取analysis/analysis.json的data_kind、分母、缺失/开放日期；读取config-preview/preview.json的精确JSON Pointer差异；再核对compatibility/compatibility.json的config_changed、save_versions、issues及candidate。JSON Schema通过不证明存档或业务兼容。候选只保存在报告中，不写回样例。

回退要区分配置和存档：本例回退reward2→1时，保留已升级的save schema2、label和pending，不把schema降回1，也不撤销已发生奖励。先提取刚生成的隔离候选，再分析配置回退：

```sh
python3 - "$grea_feedback_run" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]);report=json.loads((root/'results/compatibility/compatibility.json').read_text())
candidate=report['samples'][0]['candidate']
if candidate is None:raise SystemExit('Compatibility needs review; no candidate')
with (root/'results/save-v2-candidate.json').open('x') as f:json.dump(candidate,f,indent=2)
PY

bin/grea legacy operations_preview config --before "$grea_feedback_inputs/new-config.json" --after "$grea_feedback_inputs/old-config.json" --schema "$grea_feedback_inputs/config-schema.json" --target "$grea_feedback_inputs/target.json" --output "$grea_feedback_run/results/rollback-config-preview"

bin/grea legacy compatibility_plan --before "$grea_feedback_inputs/after.json" --after "$grea_feedback_inputs/rollback.json" --sample "$grea_feedback_run/results/save-v2-candidate.json" --output "$grea_feedback_run/results/rollback-compatibility"

bin/grea inspect-target "{\"path\":\"$grea_feedback_run/results\",\"max_files\":100,\"max_bytes\":1048576}" > "$grea_feedback_run/inventory.json"
```

交接时先检查inventory envelope的status，以及result.coverage=complete；目录摘要是按路径与字节清单计算的身份，**不是压缩包SHA或可玩构建ID**。inventory放在results之外，避免给清单自身做递归指纹。结果目录不再修改；修改后必须重新盘点并保留旧清单。

| 交接项 | 本地入口与预期 |
|---|---|
| 样例输入/口径 | 本目录inputs/；data_kind=simulation、environment=synthetic、明确窗口；新配置为人工候选 |
| 指标 | results/analysis/analysis.json，readonly_analysis；[1,0]，无D1/经济结果，不作真实收益/留存判断 |
| 变更 | results/config-preview/preview.json，仅/reward 1→2，candidate_not_applied |
| 兼容 | results/compatibility/compatibility.json，声明的顶层兼容；schema1→2增默认label，pending保留，不执行迁移 |
| 配置回退 | results/rollback-config-preview/preview.json，仅/reward 2→1；不撤销扣款、发奖或迁移 |
| 回退后的存档 | results/rollback-compatibility/compatibility.json，仍schema2、label及pending不变；不是存档降级 |
| 身份 | inventory.json与本目录输入hash；来源提交、源码是否修改、工具版本另记，不能用目录SHA替代 |
| 交付状态 | 仅本地候选；releaseVersion=null、channel=development；platform=none，production_write=Unavailable；标签/Release/安装/上传均无 |

这些字段对应[现有交付清单](../../plugin/skills/grea-release/references/游戏构建与版本发布.md#5-清单与current晋升)，没有新建current、晋升候选或发版。清单/报告可能含本机绝对路径；外发需另作脱敏，当前不外发。

LC1/LC2真实自有原生与键盘验证见[原生接续样例](../unity/lifecycle-sample/README.md)和[验收报告](../../validation/development/lifecycle-native.json)。它们与本例的模拟运营指标分开；原始provider、鼠标、正式视觉、完整游戏等价、未选平台及真实运营效果的限制继续保留。全生命周期当前状态见[唯一计划](../../proposals/lifecycle-roadmap.md)。
