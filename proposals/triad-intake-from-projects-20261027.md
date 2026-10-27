# monkey / beaver 接收交接包（来自肥鹅、向僵尸与 GREA）

日期：2026-10-27。配套 [审计](triad-toolchain-audit-20261027.md)。本包是技术交接数据，不授予跨仓写入或发布权限；各项由对应主开发按真实需求排期，源脚本只读、留在原项目。

格式：来源 → 建议能力 → 最小验收。源路径相对 `Games/`。

## beaver

### B-1 GREA 旧工具等价性（已有能力，17 项）

逐项用同一固定输入比较 GREA 旧工具与 beaver 能力的输出/拒绝行为，差异写进 beaver 合同或明确不覆盖；通过后通知 GREA 改薄转发。清单见 `tools/grea/registry.json` 中 `ownership.receiver.status=receiver_capability_available_equivalence_unverified`。

### B-2 GREA 旧工具缺口（14 项）

| GREA 工具 | 建议 beaver 能力 | 最小验收 |
| --- | --- | --- |
| evidence_manifest | `evidence.manifest`：哈希清单与来源分层 | 与旧工具同输入同字段；目录变化可检出 |
| compare_events / compare_traces | `parity.trace-diff`：首差异定位 | 旧夹具首差异位置一致 |
| presentation_audit / performance_compare | `parity.presentation` / `perf.compare` | 同轨迹、同构建的对照报告 |
| unity_native_exit / unity_player_audit | `player.audit`：Managed DLL 集合与源机制残留 | 旧 256-DLL 上限夹具与拒绝路径 |
| video_manifest / video_sheet / image_contact_sheet | `media.manifest` / `media.sheet` | 解码与联系表字节确定 |
| audit_numeric_texture | `resource.numeric-texture` | 浮点纹理原始字节回读 |
| unity_package_backup | `unity.packages.backup/restore` | 备份哈希先验、恢复回读 |
| package_windows_portable | `build.windows-portable` | 仅在有 Windows 目标需求时做 |
| cocos_project | Creator 能力 | Cocos 暂停，保持 not_supported |

### B-3 项目脚本族

| 来源 | 建议能力 | 说明 |
| --- | --- | --- |
| `projects/20-肥鹅美食街/Tools/launch_native_mainline_52…73.py`、`launch_native_*.py`、`projects/21-向僵尸开炮/Tools/run_editor_window0{2,3,4}.py`、`run_native_actor_motion.py` | `debug.start` 接受“场景＋时长＋截图＋日志过滤”声明式请求 | 编号副本的差异应只剩请求 JSON |
| `20/Tools/build_native_mainline_52…74.py`、`build_native_*.py`、`prepare_native_*.py` | `production.plan/apply` 的 UI/Prefab 步骤模板 | 不生成业务回调；Prefab 以资产为准 |
| `20/Tools/upgrade_foodstreet_stack.py`、`backup_foodstreet_stack.py`、`resume_*_upgrade.py`、`verify_*_upgrade.py` 通用部分、`renew_*`/`local_tls_lifecycle.py` | `server.migration-*`、`server.runtime-inspect`，新增 `server.backup/restore`、`server.tls-renew`（自有栈） | 业务断言留项目；不碰共享 QA 栈 |
| `20/Tools/generate_server_protocol.py` | `server.protocol-tools` | 与项目现有生成结果逐字节一致 |
| `21/Tools/convert_fp_*.py`、`convert_initial_waves.py`、`generate_buff_reader.py`、`generate_local_weapon_reader.py` | `config3.generate` 覆盖复合键与数组嵌套 | 复合键（ID＋序号）读取器回读原行数 |
| `21/Tools/compile_full_sdk.py`、`compile_with_existing_sdk.py` | `unity.project.import` 的编译诊断模式 | errorCS 定位到文件行 |
| `20/Tools/adopt_frozen_monkey_bulk.py`、`build_monkey_merge_map.py`、`21/Tools/adopt_bulk_initial.py`、`adopt_verified_candidate.py` | `adoption.plan/apply`（已有） | 两项目各用一次固定候选做消费者验证 |

### B-4 已知运行缺陷类（写入能力或诊断）

Editor 退出落盘、Licensing 中断恢复、MoveAsset 改主对象名、Player 后台无结果、macOS Metal 呈现卡住：beaver 已在 v0.3 处理前两项，其余建议做成 `debug`/`player.run` 的显式诊断码，不由各项目重复发现。

## monkey

| 来源 | 建议能力 | 最小验收 |
| --- | --- | --- |
| GREA laya_contract_audit、read_elf_values、unpack_xapk、shader_probe | 来源 profile 内的提取/探针子命令 | 与 GREA 旧工具同输入同结果；GREA 再薄转发 |
| `21/Tools/index_wasm.py`、`inspect_wasm_segments.py`、`disassemble_selected_wasm.py`、`decompile_selected_wasm.py`、`map_wasm_methods.py`、`resolve_wasm_literals.py`、`resolve_game_main_calls.py`、`index_metadata.py`、`run_static_dumper.py`、`run_schema_dumper.py` | Unity IL2CPP-WebGL/Wasm 代码证据 profile：索引、选定方法反汇编/反编译、方法→元数据映射、字面量解析 | 不执行原 JS/Wasm；向僵尸既有方法映射可复现 |
| `21/Tools/decode_declared_configs.py`、`decode_textconfig.py`、`restore_startup_schemas.py`、`extract_declared_bundles.py` | 原配置解码进候选 `Analysis/`，保留原二进制证据 | 与项目既有 JSON 逐表一致 |
| `21/Tools/freeze_inputs.py`、`freeze_package_members.py`、`prepare_bulk_handoff.py` | Unity 多根 input-set（600 Bundle＋启动包全部 export root） | 向僵尸 bulk-inputs-01 可直接作为输入 |
| `20/Tools/static-bon-reader.py`、`export_original_mainline.py`、`extract_original_*.py`（通用解码部分） | Cocos BON/配置逐表导出（0.6 已有部分） | 与肥鹅正式 JSON 来源映射一致 |
| `20/Tools/acquire_resources.py`、`acquire_overrides.py` | 远程清单获取（已有 `--remote-manifest`） | 覆盖项目 override 语义或说明不覆盖 |
| monkey `adoption.py`、`adoption_native.py` | 消费者切到 beaver 后退役 | 保留只读兼容或明确弃用，不空成功 |

AssetRipper 启动即超出预算（向僵尸 provider-failure.json）：建议 monkey 在 provider 调用回执中固定记录版本/二进制 SHA/输入 SHA/耗时/预算/退出码，并支持外部已导出结果作为输入，避免重启试错。
