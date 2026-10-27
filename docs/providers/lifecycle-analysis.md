# 版本兼容、只读事件分析与配置预览

这些是本地有限工具，不连接游戏服务、不写普通档或生产配置，不提供GM、支付、公告或发行渠道上传。原生/可玩版本与真实运营效果仍须对应项目数据和授权。本轮fixture为自有合成，不能据此宣称真实游戏收益或留存改善。

## 配置与存档兼容

```sh
bin/grea legacy compatibility_plan --before /path/old-contract.json --after /path/new-contract.json --sample /path/isolated-save.json --output /path/new-plan
```

合同v1：schema_version、config（相对合同的path及sha256）、save（version整数及fields对象）、protocol_version、pending_fields。fields按字段名声明type（string/integer/number/boolean/object/array/null）、required布尔及可选default。样例用`_schema_version`，只接受前/后明确版本，未知新版本拒绝；未知字段保留并要求review，不默删。最多100份显式样例/总16MiB，单JSON4MiB，失败不覆写来源。

仅支持顶层字段/类型和已声明默认值：删除/改类型、pending变动、协议变化、未升版本却改结构均needs_action；不猜单位/枚举/ID或嵌套语义。配置内容hash变化与save版本独立；两者不应混为一个拒档开关。兼容时输出candidate副本供审核，不执行任何迁移或SQL。已确认服务器资产不能被旧客户端备份覆盖。

## 事件、漏斗与经济流

```sh
bin/grea legacy operations_preview events --input /path/events.jsonl --start 2026-10-20T00:00:00+08:00 --end 2026-10-22T00:00:00+08:00 --as-of 2026-10-22T00:00:00+08:00 --timezone Asia/Shanghai --steps start,finish,claim --active-event start --window-seconds 3600 --data-kind simulation --output /path/new-analysis
```

事件合同见operations-event.schema.json。必填v1、全局event_id、event_type、带UTC offset的event_time、伪匿名player_id/session_id、game_version/config_version/environment；可有payload和economy。总文件≤16MiB、单行≤64KiB、≤100000条唯一事件；同ID同内容去重、不同内容拒绝。调用者负责授权/匿名性/完整性，报告不列玩家标识。watermark为已取得数据范围声明，不能假定未来数据已齐。

窗口[start,end)，as-of不早于end；按环境/游戏版本/配置版本拆分。漏斗每会话最多一次尝试，事件时间严格递增，同时间无法确定先后不推进，显式计歧义；转化分母为到达第一步的会话数，分母不存在为null。D1以组内首次观测活跃日期为cohort，按IANA时区日界线计算；D1整日未关闭排除，左截断和版本分组使它**不是获客留存**。不对缺失/延迟事件补零或因果归因。

economy字段：kind=grant/spend/snapshot、asset_id、quantity为非负int64十进制字符串、receipt_id。按环境/玩家/回执/资产/类型识别重复经济回执（跨版本/配置分组仍去重，采用输入中最早事件；窗口外首次发生的重放不计新收益），不因换event_id重复计数；冲突内容拒绝。报告仅产出/消耗/净流和快照数，未证明期初库存/守恒。data-kind区分observed_events/ledger/simulation，身份仍是声明，模拟不变成实际流水。

## 配置与发行候选预览

```sh
bin/grea legacy operations_preview config --before /path/old.json --after /path/new.json --schema /path/schema.json --target /path/target.json --output /path/new-preview
```

两份JSON均用显式本地Draft2020-12 Schema校验；拒绝外部$ref/$dynamicRef/$recursiveRef及资源$id，不下载Schema。target v1包含environment/audience/effective_at（带offset）、client_versions、approval_reference、rollback_limits、platform（未选写none）。最多256项JSON Pointer差异，超限要求缩小输入。状态candidate_not_applied；审批引用是声明，不是权限。

Schema通过不证明旧客户端/save/protocol兼容；回退配置也不撤销发奖/扣款/迁移。production_write为Unavailable。platform=none保持未选，其余也仅登记目标并标adapter_not_implemented，不默认Steam、创建账号或宣称渠道预检已支持。

## 本地串联与交接

[完整调用示例](../../tools/lifecycle-feedback/README.md)复用既有合成输入，将事件分析、人工有限配置diff、前向兼容、配置回退且保留新save schema及最终目录盘点串联；入口无需额外服务。缺事件的LC2 Player输入日志不自动变成运营数据，模拟指标不构成调优依据。交接沿用既有来源/内容清单/验收/未发布字段，不新增生产或商业平台能力。
