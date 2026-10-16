# 项目工具提炼：实施与准入记录

本批从 `8521ca5468454da147306a1047ddd5e9d1c0426a` 建立独立工作树和 `codex/project-tool-extraction-20261016` 分支。框架分支的已修改/未跟踪文件原样保留，不切换共享 checkout，不把离线转换能力放入游戏 Runtime。私有盘点和原始证据留 `.private/project-tool-extraction-20261016`；公共内容只有独立实现、合成测试和脱敏摘要。

既有盘点覆盖九个项目的 1,687 个脚本/源码文件，含测试和大量候选快照，不能当作 1,687 个可推广工具。本批先完成四项证据工具，再按复核补齐有限制作链和两项核心入口；不宣称其余项目工具已经通用化。

| 能力 | 决策 | 本轮结果 |
| --- | --- | --- |
| Cocos 2.4 编译数据/pack/明确 bundle 选择 | adopt protocol / independently implement | `cocos_assets` 0.1.0；版本、下标、表长、深度/字节预算、版本歧义与只新建输出 |
| 模块工厂、依赖与 RF 语法身份 | replace unsafe execution | `cocos_modules` 0.1.0；锁定 Acorn，原始 UTF-8 区间/哈希，不求值、不改写；动态拼表仅 syntax_candidate / partial |
| 原生退出静态候选 | extend existing GUID audit | `unity_native_exit` 0.1.0；直接复用 `unity_dependency_audit`；未命中/改名保持待 Editor 确认 |
| Editor / 实际 Player 类型证据 | add separate observation layers | Editor companion 与 `unity_player_audit` 0.1.0；CompilationPipeline/资产类型不替代实际 DLL 元数据 |
| GUID/资源台账、轨迹比较、快照与 Editor 连接 | reuse | 保留 `unity_asset_ledger`、`compare_events`、`unity_pilot`、`unity_cli` 等现有入口，不另造迁移台账或控制服务 |
| 配置制作、字段/几何前后比对与回执 | bounded implementation | U3：unity_config_candidate；两类强类型表/原生 SO/Player 回读；复用 ledger compare-editor 与现有事件协议 |
| Sprite/Spine/AnimationClip 的有限 Editor 转换 | bounded implementation with explicit gap | U4：unity_native_assets + Editor API；Sprite/Clip 已通过；Spine 仅自有两页/缺页闭包，runtime/适用授权未验证 |
| 源引擎 Runtime、全节点图播放器、动态 C# 转译、项目 CDN/命名字典 | exclude | 留原项目来源/反例，不进入公共运行时、插件默认能力或通用工具 |

## 进度和门槛

- [x] U0：核对既有工具去重、来源/许可、明确版本和副作用。Cocos 引擎参考及游戏代码不再分发；解析器以协议和自有预期独立实现。Acorn/MIT 和 Cecil/MIT 分别锁定，Node/.NET/Unity 是显式可选 provider。
- [x] U1：实现并测试两类独立对象结构、前向实例/UUID 引用、普通/Texture pack、配置精确版本和 ordinal；未知版本/kind、歧义、越界、坏 JSON、预算、链接、重复输出明确失败。4 份私有资产与既有导出一致，2 类真实 pack 回放通过；旧导出不作独立 oracle。
- [x] U1：两类字面量 loader、Unicode 字节位置、文件名碰撞、重复键、RF/依赖未解析与块作用域/赋值反例；含写文件初始化器/工厂的合成输入不产生副作用。真实混淆包保留 69/106 个函数候选，全部保持 partial，不猜名称/动态依赖或恢复运行时。
- [x] U2：两个不同布局的自有源工程候选测试，Editor-only、合法 DTO、动态加载队列及改名反例；静态永不颁发完整原生化通过。
- [x] U2：两份自编译合成 DLL 验证嵌套类型、引用和有限调用、不执行静态构造器；缺类型、坏哈希、测试/禁止依赖、额外/损坏 DLL 和 IL2CPP 反例。
- [x] U2：隔离 Unity Editor 实测编译集合、GUID/资源闭包和对象类型；实际 arm64/Mono Player 71 DLL 回读。同名类型在 Editor 为 `EditorOnly` 字段、Player 为 `PlayerOnly` 字段，证明两层不可混用。初版非法序列化字段差异被 Unity 构建拒绝的证据保留；有效反例改为非序列化字段。
- [x] U3：两类独立 schema/JSON 制作源 → 强类型 C#/Editor importer → SO → 重开与 Player 回读；预检、nullable string 持久化、候选身份和人工修改冲突有反例。既有 ledger 新增 compare-editor，实际改名保留 GUID/localID，路径/名称/几何差异独立报告。C08 复用 run-tool/Editor 执行与事件协议，保留 run ID/请求与输出哈希，不另建控制服务或通用游戏 oracle。
- [x] U4 有限 Sprite/Clip：自有裁切＋旋转＋透明补边＋pivot/九宫格；显式非单位 scale 目标、两条 Clip、线性曲线/事件/循环边界/切换中断；Editor 原生创建、手改、重开、Play、拒绝覆盖、删除转换器后的 arm64/Mono 构建与自动 Player 回读均通过。
- [ ] U4 Spine 原生导入/渲染：自有两页及缺页闭包已通过，现有本地 runtime 候选与许可证已只读登记；匹配 pristine 身份和适用授权证据未建立，runtime 导入/渲染明确 not_run，不复制项目修改版充数。
- [x] U5：六个新增 helper 与既有 ledger 扩展接入同一 registry/run-tool，新增两份制作 Schema/文档/Skill 入口；CLI/MCP 和隔离插件实测。231 项本地回归（229 通过，2 条既有条件跳过），20 个顶层操作与旧 ID/接口保持。GitHub CI 未运行，原生客户端安装/加载未重测。

输入/输出、版本、状态和安装方法见 [Cocos 工具](../providers/cocos-static.md)、[三层原生检查](../providers/unity-native-exit.md)。版本化 Schema 从 Python 定义生成；静态、Editor、Player、原版一致性仍分别验收。完整摘要见 [验收记录](../validation/2026-10-16-project-tools.json)。

本批不提交、推送、合并 main、发布或更新全局安装插件；不修改游戏原工程和普通存档。新项目使用已验有限契约时仍要建立自己的 schema/目标/输入指纹和回归，不能把协议解析或本批自有样本直接当作生产游戏资产验收。

- 收口补测：输出数据总预算、非有限 JavaScript 数值和非法 Unicode 代理字符/文件名冲突均有失败反例及回归；早期 U0–U2 快照的 66 文件 SHA 与当时插件预览逐项一致；U3/U4 后的快照为 89 个登记文件，后续增量以验收记录中的当前文件清单为准。历次预览与当前源码身份分别登记，视觉补验采用新的实现哈希和预览，避免旧快照被写成当前最终状态。源码/网络/安装写入被系统拒绝、主机开发运行时不可用时，两个新增纯 Python 工具仍通过本地 stdio；Node/Cecil 可选能力明确 unavailable。这里不是本机 Codex/Claude 插件加载或安装验收。

## 复核补验

Resources 原实现在未显式传入时漏掉自有 Prefab/SO 及间接依赖；保留失败报告，自动收集 Assets/Resources、排除 Editor、去重后通过实际 Editor 类型断言，导入观察不签发完整原生结论。配置 nullable string 使用显式序列化标记。自有样本首次缺内置 Animation 模块、Play 循环断言漏初始采样均保留失败记录；启用已有模块和修正测试时序后通过。独立 Player 59 DLL 的必需类型/禁止转换器与测试依赖检查通过。鼠标仍未可靠验收，不能由内部 Play 或键盘路线替代。


## 可见渲染收尾

R1 已补实际画面：自有相机明确距离/取景，Widget/Other 绑定可见原生图形，独立九宫格图验证两种尺寸的边角宽度。3 项 Play/渲染测试通过；Editor 五相位各 25 项像素断言。移除转换器的 arm64/Mono Player 在 Metal 上另取得五张实际 backbuffer 帧，同样 125 项严格像素断言通过，已逐张查看；62 个实际 DLL 回读无转换器/测试身份，冻结的 42 文件分发源与 169 文件 Editor 样例源码均未被构建改写。启动采样等待原生 SplashScreen 完成；保留空画面、材质管线不匹配及 splash 合成失败帧，不用放宽颜色阈值掩盖失败。

R2 已修正：Skill 源码确有两份参考文档更新，仅隔离同步/check；工作区和全局安装副本未更新。66 与 89 均明确为旧阶段快照；当前登记实现为 93 文件，以验收摘要逐项哈希为准。新增针对性 Python 11 项通过，沿用之前全量 229 通过/2 跳过记录，不重复全部昂贵验收。最终源码与新插件预览逐项核对，真实已安装客户端、CI、其他平台、Spine 原生导入与 OS 鼠标仍按未验状态保留。两个分支与原有改动继续隔离，不提交/推送/合并/发布。
