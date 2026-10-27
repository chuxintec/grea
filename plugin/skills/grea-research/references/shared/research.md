<!-- 生成副本，勿直接编辑。权威来源：docs/providers/research.md；由 scripts/skill_closure.py 维护。 -->

# 调研归一与报告工具

开发候选；不替换已安装插件。`grea legacy research_report --input evidence.json --output new-report`，或用既有run-tool调用同ID。输出目录必须全新，输入只读。输入Schema为 research-input.schema.json（GREA 安装目录 `schemas/research-input.schema.json`）。显式来源文件累计最多64MiB、输入JSON最多8MiB；路径相对输入且不可越界/链接，SHA陈旧拒绝。

sources声明证据文件，items列稳定ID/kind/stage/source_id；protocols按name/direction/kind区分rpc、message、field。输出按真实提供的分类去重；source文件校验不证明分类正确。没有材料的指标为null，嵌套字段不计RPC，配置行不计玩法数。complete_kinds仅调用者覆盖声明。

judgments显式提供事实/推断/假设/经验/未知、来源；estimates提供工种、人工主动小时区间、协作工作日区间、后端是否已包含、前提和置信度。不自动估价、不内置AI倍率，后台和共享配置不能在双客户端重复计成本。方法见 [调研技能](../../SKILL.md)。

实玩覆盖由可选play_coverage输入记录，旧输入兼容但标not_provided；四类缺口独立于资源数量。played仅是分析者申报，工具校验来源SHA、关联、媒体类型和视频时间码，不解码媒体或认证机制理解。详见[强制体验规范](实际体验与画面对照.md)。
