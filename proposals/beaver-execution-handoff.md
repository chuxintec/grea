# GREA 执行工具向 beaver 交接

状态：本地冻结及恢复侧归属评审完成；beaver 已返回逐项接手意见，完整接口替代与消费者切换尚未完成。开发进度统一见[路线与进度](lifecycle-roadmap.md)。

## 可接手材料

[机器清单](../validation/development/grea-beaver-handoff-20261026.json)包含工具入口、内容哈希、静态本地 import 闭包、registry 输入/效果/平台合同、词法调用者候选、模板与 Editor companion 文件。40 个 Python 工具入口中，28 项建议 beaver 接收，7 项恢复侧已由 monkey 评审，均保留兼容存量，5 项保留 GREA 薄接入/方法辅助；这不是接收验收，也不是完整依赖分析。

冻结快照位于仓库本地 `.private/triad-20261026/source-freeze/source/`，903 个文件/7,219,104 字节；`manifest.json` 的 SHA256 为 `327164597eee56a6cef06f09a047270a2c0f5320fd6e779e8e3bb1637c940761`。快照保存整改前 WIP、HEAD、分支和精确文件身份，不依赖变动中的工作树。快照含机器路径 AGENTS，仅作本地交接，不能整份打包公开。`.private/triad-20261026/source-owner-observations.json` 保存总监种子清单的只读复核，未复制游戏源码/资源。

GREA 自有代码 MIT，依赖见快照 LICENSE、THIRD_PARTY.md、pyproject.toml/uv.lock 和各模板实际 notice。367 个工具模板/companion 文件仅作为逐项审查来源，不因此取得第三方再分发权。项目规则、原游戏素材、账号/服务配置不进入 beaver 包。

## Go服务器能力的定向交接

Go为beaver0.3必选，不留待后续版，也不维持GREA新执行主线。此次仅冻结 `.private/go-beaver-handoff-20261026/source/` 的45文件/104020字节：完整tools/server-go/template（含隐藏忽略文件）、server_go_project与publication/path/identity直接辅助、测试、当前IDL生成文件/依赖锁、许可和有限验证说明。机器入口 `.private/go-beaver-handoff-20261026/manifest.json` SHA256为 `283f5fca66e95f1fa65a52fa3c43169f40661ded30a13db375a6e0bb37ab92b3`；`contract.json`给出旧CLI/MCP输入、输出、退出语义与registry副本。[公开交接回执](../validation/development/go-beaver-handoff-20261026.json)记录来源和未验边界。此次不再复制903文件整库，不含游戏、凭据、.local、缓存或二进制。

旧生成器只在新目录发布有限development六服示例：stdout为status/files，完整grea-generated.json为template_version0.1.0与逐文件hash；错误仍是exit2与文本，不冒充统一JSON错误。`server_go_project`、原模板和消费者继续保留，未切换、不允许退休。辅助文件只供机制提取；beaver不得依赖运行中的GREA源码。历史Cocos客户端文件随旧模板冻结作出处，不新增Cocos执行任务。

依赖固定go.mod/go.sum，语言指令1.26.0、历史工具链声明1.26.2，已生成文件标记protoc7.34.1、protoc-gen-go1.36.12与grpc插件1.6.2；本轮未调用这些工具。自有代码MIT；第三方模块许可和镜像digest保留在依赖说明/生成器/stack.py中，不转授其许可。模板含Redis替换位，生成器注入固定digest，不能只复制模板忽略替换行为。

复用历史3项Go单测、11项隔离六服链与CORS仅单测的分层记录，不重跑编译、Docker或服务；原始日志只列身份引用，不转移运行目录。历史live链与当前冻结字节未有精确源码身份绑定，故不声称这份新快照已运行验收。Unity真实联网、生产身份/TLS/WSS、支付、owner迁移和outbox/inbox仍未验/未实现。旧demo的down会清理自有开发卷，不能沿用为0.3数据升级/恢复策略；新实现必须遵守保留数据的版本要求。

GREA持有grea-server-go与六服规范；beaver实现通用Go工程/模块/协议、跨端配置类型、受控数据迁移、构建及Docker工具；游戏项目持有实际业务和唯一正式后端。此处是45文件移交检查点，历史验证不改写。

后续固定0.3已提取其通用机制，包内source-manifest及GREA-MIT通知保留来源；上游补齐自有六服/MySQL重启/Redis丢失及Unity请求证据，GREA实调Go模块候选与协议比较，有限路由见[0.3回执](../validation/development/beaver03-integration-20261026.json)。正式08中文路径的两份既有C# after-image原生收敛已核验；这不构成正式Go采用、完整旧接口替代或生产部署。旧server_go_project与消费者仍未替代或退休，0.3整版由beaver主开发汇总。

## 提取建议

| 能力 | 来源与处理 |
| --- | --- |
| 项目采用/治理、资产引用与命名 | unity_pilot、unity_asset_ledger、unity_dependency_audit、unity_framework_audit 等；去掉仓库固定路径，保留身份/恢复约束 |
| 框架、Prefab/UI 与配置生成 | project_templates、unity_native_assets、unity_config_candidate 及 tools/unity 模板；保留原生 companion，正式数值以运行时 JSON 为准 |
| 图片资源与 JSON 检查 | image_alpha_audit、image_contact_sheet、static_asset_copy、config_preflight 等；保留输入预算和非就地输出 |
| 差分、原生及制品验收 | compare_events、compare_traces、unity_player_audit、unity_native_exit 等；不把静态通过升级业务通过 |
| 构建交付 | package_windows_portable 与相应 Editor 构建 companion；GREA 自身插件打包维护脚本仍归 GREA |
| 来源解析与转换 | monkey_bridge/pipeline 为 GREA 薄接入；源包解析共因交 monkey，不作为 beaver 第二解析器 |

代码中的固定游戏 ID、路径与测试数据先分类：通用机制参数化；游戏业务保留原项目；第三方依赖保持原许可；无法证明通用的内容只作参考。静态 import 闭包不能证明动态加载资源齐全，接收方需实际隔离调用核验。

## 兼容切换条件

每项按“冻结 → 接收与参数化 → 自有隔离验证 → GREA 薄入口适配 → 消费者切换验证 → 退休重复实现”收口。接收记录固定 beaver 版本/实现、具体能力与验证回执；原工具 ID/输入输出/退出语义不变，partial/needs_action 不提升为 pass。替代没有完成前保留原实现，不破坏肥鹅在途固定链。

正式游戏 Tools 保持自包含，不能移走变符号链接。三产品各单写自身代码；本交接不授权改原工程、唤醒暂停项目、全局安装或发布。

GREA 保留项为 monkey_bridge、monkey_pipeline、registry_doctor、check_grea_skill 和 research_report：分别是外部恢复薄接入、依赖/技能维护检查和调研报告辅助。read_elf_values 属恢复侧，verify_payload_tree 属工程制品侧，不能只按 Python 脚本位置判归属。

## 恢复侧七项兼容结论

monkey 本地提交 `dad5dc1cc8552d7adcebec2647eeb22737de9e0a` 的 `docs/GREA-RECOVERY-HANDOFF.md` 与机器记录 `docs/validation/2026-10-26-grea-recovery-handoff.json` 已按字节核对（记录 SHA256 `4f96b7d784f6eaea0f19ad5db5202db0bccdbe28e135b220db20ae25defa512f`）。这是上游评审证据，不是 GREA 已完成等价适配。

| 兼容存量 | 现有 monkey 覆盖与保留原因 |
| --- | --- |
| cocos_assets | reader 核心可复用；旧参数、独立 CCON/evidence schema 未等价 |
| cocos_modules | AST 核心可复用；旧 adapter/export_index 和消费方未等价 |
| cocos_convert | 声明输入的工程候选子集可复用；旧 flat 输入、asset-map、UUID 选择不等价；目标 Creator3.8.8 不代表支持该版本可编辑源 |
| unpack_xapk | 仅直接 APK 重叠；嵌套 XAPK 未支持，不能改后缀冒充 APK |
| read_elf_values | 无等价 ELF 虚拟地址常量读取能力，仅保留冻结参考 |
| laya_contract_audit | 无等价 Laya 网格/骨骼/粒子合同能力；不自动运行第三方 parser |
| shader_probe | 无等价 combined-GLES/SPIR-V/ShaderLab 转换能力，仅保留冻结参考 |

七项均 `retire_allowed=false`、`consumer_switch=not_verified`，不交 beaver，不把“归属 monkey”解释为 legacy 直接全量转发。退出兼容存量须完成精确输入版本/参数/UUID、结果 schema、退出码和预算的真实适配及消费者验证；不为清表新增 profile、安装或运行第三方解析器。

beaver 的当前回执将 28 项工程侧来源列为 26 项参考未替代、2 项参数化机制子集（image_alpha_audit、config_preflight），未声明旧完整合同等价，也未授权消费方切换。主 Skill 继续按 monkey 恢复、beaver 开发选择新能力；原实现和在途锁定链保持。

GREA 已复用既有 monkey0.4 自有候选，通过固定 beaver0.1.0 隔离快照实调 `adopt plan`。结果为0动作、0冲突、11项保留，候选和工作副本前后逐文件哈希不变；仅证明候选/计划合同被实际消费，不是资源迁移、原生采用或消费者替代验收。尚无原实现退休条件达成。

## 本地集成收口

beaver本地提交b67a164及最终wheel（SHA256 `09020d42b75497ec39040f08e48fab24378a0baa5b51cebe92529fe67a7ee2f6`）已接收。其GREA dev3固定调用的project.inspect、匹配源码构建、Player前后文件身份与退出证据按原范围复用，本轮只核34份回执hash及21个wheel包文件身份，不重启引擎。GREA dev4补齐命名操作/Schema/路由；9项新增边界、2项路由检查及真实payload转发/stdio MCP通过。

此前“尚待beaver交付”状态已由此结论替代；本地集成不等于正式游戏采用。早期Prefab原生读回使用另一wheel，完整原接口等价/旧消费者切换仍未验证，旧工具继续保留。详情见[收口回执](../validation/development/triad-closeout-20261026.json)。
