# GREA 七项恢复侧工具归属评审

2026-10-26；事件 `monkey-grea-recovery-handoff-scope-20261026-01`。按已核人类三产品整改授权 `[private conversation reference]`，只评审固定清单中 `proposed_owner=monkey` 的 **7 项**。这七项均留恢复侧，不交 beaver。本轮没有新增 CLI、引擎 profile、依赖安装或源实现搬运；结论是现有实现复用、兼容缺口和有身份的参考保留。

## 固定来源与接手身份

- GREA 来源 HEAD：`[private fingerprint omitted]`。快照可能包含在途源码，以 manifest/逐文件字节身份为准，不能仅用 HEAD 重建。
- GREA 清单 `validation/development/grea-beaver-handoff-20261026.json` SHA256：`[private fingerprint omitted]`。
- GREA 固定源码 `.private/triad-20261026/source-freeze/source/`；外层 `manifest.json` SHA256：`[private fingerprint omitted]`。
- 本地仅冻结七项入口及传递依赖/许可/依赖声明/AST companion，共 **23 文件**，没有整体复制903文件。私有档案 `.private/grea-recovery-handoff-20261026/audit-02/grea-seven-recovery-source.tar.gz`，SHA256 `[private fingerprint omitted]`，128,071字节。只用于来源审查，不进入公开包。
- 对照 monkey 本地代码基线 `[private fingerprint omitted]` / 0.5.0.dev1；日常安装仍为0.4.0。[机器记录](validation/2026-10-26-grea-recovery-handoff.json) 逐项保留入口SHA、闭包、monkey实现路径、兼容缺口与调用者候选。

## 七项实际结论

| 旧工具 | 结论 | 已有能力与不能替代的部分 |
|---|---|---|
| `cocos_assets` | **复用现有核心，条件替代** | monkey已有compiled-v1/pack/texture-pack，以及明确3.4.1 bundle读取。合成正文解码一致、非法版本/索引均拒绝；但旧独立文档/CCON evidence接口、参数及输出schema未做兼容。沿现有reader，不新建第二CompiledV1 |
| `cocos_modules` | **复用现有核心，条件替代** | monkey AST源自同一固定GREA基础，已扩语法/RF证据并内置Acorn8.15.0。三种代表wrapper源范围/哈希一致、partial保留；旧独立`--adapter`/export_index回执与调用者未迁移，不能用code-model输出冒充旧接口 |
| `cocos_convert` | **复用现有候选管线，子集条件替代** | monkey已有2.4.15可编辑工程→共享IR→Creator3.8.8候选。旧独立flat Scene/Prefab+asset-map，以及3.8.8可编辑源输入没有等价接口；真实3.8.8源测试被明确拒绝。目标3.8.8不代表可读任意3.8.8源；不为表格新增profile |
| `unpack_xapk` | **复用APK读取；XAPK只留冻结参考** | monkey直接APK可读，但嵌套XAPK实际返回UNSUPPORTED_CONTAINER。旧工具可解嵌套APK并保留opaque OBB，选择/跳过与Reference报告也不同。后续若提取只补容器组合层，沿现有APK reader；不能把XAPK改后缀当APK处理 |
| `read_elf_values` | **只留参考，当前无等价能力** | Unity字段/元数据恢复不是ELF虚拟地址常量读取。未来有明确来源需求才参数化复用PT_LOAD算法；需绑定链接地址/重定位依据、文件/段边界和有界读取，不能直接搬整文件read_bytes作大包方案 |
| `laya_contract_audit` | **只留参考，当前无等价能力** | 当前通用图片/资源提取不能替代Laya网格/骨骼/粒子合同。旧工具会执行显式指定的可信本地Python provider；不将它接入自动原包读取，更不执行从包里取得的parser。Laya图/网格profile仍未支持 |
| `shader_probe` | **只留参考，待05-C明确子集** | monkey保留源Shader/Effect文本，不等于combined-GLES编译。旧工具依赖glslangValidator/spirv-val/spirv-cross，插宏/升级ES310/自动绑定均是显式适配；编译成功不能证明ShaderLab、材质或渲染等价。本轮未装/运行这些工具 |

这里“条件替代”表示恢复目的/核心实现已有覆盖，**没有一项因此允许直接退休旧入口**。对应legacy CLI输出、退出码、参数/预算、精确输入版本、UUID选择与当前消费方必须先有显式适配和实际核验。GREA单写旧路由/退休，monkey不改其工作树。机器清单的callers只是词法候选，不是已经证明运行调用或切换成功。

## 最小验证与范围

1. 两份固定清单SHA及全部23项选定文件的bytes/SHA核对通过，验证后再核未变。
2. compiled-v1：一份自造Node/Prefab正文，两套固定reader解码一致；非法版本和非法class索引拒绝码一致。`CompiledV1`整体AST已有差异，不能外推所有行为相同；decode_document/budget/uuid_full AST一致。
3. 模块AST：browserify、define-browserify、System.register三种代表，旧/新共4模块的源字节范围和SHA一致；define仍是partial。测试包含写哨兵语句，哨兵未创建。旧CJS的Acorn绑定及版本读取在自有临时桥中定向到monkey既有8.15.0；没有改原快照或解析逻辑，因此这是显式provider适配后的对照，不声称旧安装环境直接可用。第四旧adapter及全部消费方未做全面等价验证。
4. 自造APK/XAPK：monkey直接APK逐条字节保留；XAPK被拒绝。固定旧unpack实际读1个嵌套APK、选1/跳2/失败0，OBB保持opaque。只证明容器合同，不是Android安装或游戏恢复通过。
5. 自造旧2.4.15 flat Prefab产出serialized_candidate_not_imported；monkey现有3.8.8 editable-source被拒绝。另运行6项既有定向反例/流程测试，通过：2.4工程meta/原生资源、3.4.1双端候选/版本拒绝、APK逐项处置/路径拒绝和wxapkg模块草稿。

ELF/Laya/Shader探针未执行，没有新增大矩阵，没有启动Unity/Creator/游戏。339项测试是上一个实现检查点通过的基线，本轮仅文档评审，不重复全套。证据在 `.private/grea-recovery-handoff-20261026/`；早期审查脚本的报告字段/依赖绑定失败日志保留，修正后才形成上述回执。

## 归属、许可和下一步

GREA自有源按MIT，未来提取必须保留原版权；THIRD_PARTY.md和monkey既有GREA/Acorn notices分别保留。第三方parser、编译器、引擎与游戏素材不由GREA自有MIT一并授权。本轮未将任何legacy实现并入monkey公开源码；私人AGENTS、绝对本机资料、原包/资源和完整日志不进发行。

GREA在真实兼容和消费方切换后才退休旧实现；本轮七项 `retireAllowed=false`、`consumerSwitch=not_verified`。现有05-C资源/引用阻断和05-D诊断继续，不依赖此表被全量清零，不复制第二解析器，也不把恢复缺口交beaver。beaver采用事务的独立冻结基线仍是db253cb对应归档，未被本次评审改写。
