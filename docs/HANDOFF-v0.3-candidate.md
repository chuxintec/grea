# v0.3 固定候选接入

当前 0.3.0 已完成本地交付（含已声明限制）；不构成 Release，不扩大正式游戏或服务操作权限。

- wheel：`/Users/wangmeng/Documents/Games/tools/beaver/.private/dist/v0.3-final/beaver_game_tools-0.3.0-py3-none-any.whl`
- SHA256：`d4dd7229fa9ce56eabb9054d0af2b88591aa0777fe4e3d0fc139b74a105eb598`，239672 bytes。
- implementation：`e6191235381d587870291b8a01ba492b4dac4b2f7faeced50590dbc1342f0882`；干净环境在 `/private/tmp` 执行公开 CLI，68份包文件逐字节一致，含两份隐藏模板，未包含私有资料。
- Unity：6000.6.2f1；旧事务须保留原固定工具，不能换新wheel重放。

正式项目由其主开发单写。本候选优先接入既有任务，不创建新游戏功能：可由肥鹅主开发在“物品详情快捷购买按钮刷新”或同版下一项既有代码/Prefab修正中，先在独立文件准备候选，再用 schema3 production 的 exact old/new SHA fileEdits 安装、原生编译/检查，执行其原本所需测试或 App 复验并交结果。若该修正已完成，不倒退重做，不中断 v1.2；由主开发选择下一个本就需要的任务。

在项目外或项目内私有venv安装该固定wheel；不替换全局beaver。用 workspace plan/apply 创建最小写区绑定；已有绑定先读旧SHA并显式rebind，不覆盖。产品数值JSON继续唯一维护源，production输入源必须独立于实际目标，保留.meta由Editor管理。主开发提供具体目标与批准范围，工具不自行扩写区。

已具备证据：115项标准测试；原生五层模块编译和实际Play（含四类坏JSON拒绝）；实际namespace/type/field三阶段候选255唯一文件；真实切片、Atlas target pack、主字体、直接fallback、Spine闭包、SO字段/原GUID-localID引用、音频与材质首轮原生均通过。资源双Editor独立重开已严格通过，匹配App已实际完成1293物品/3432订单读取及Spine idle渲染（时间增加、28顶点、CanvasRenderer可见）；CUA真实鼠标使详情内容y0→133.01并关闭，App verified/exit0，制品前后核验一致。真实项目采用仍须另行完成，不能据私有副本自测算已采用。

Go自有六服与五owner迁移、同Schema Unity/Go读取、Unity首笔APPLIED、App同intent重试、MySQL单次入账、六服/MySQL重启及Redis丢失后重放均实测，验收栈已普通stop保留卷；不升级现有项目服务。

GREA本地源码薄适配已完成：49个明确路由、45项定向检查及真实私有CLI/独立stdio通过，按有限版本和精确producer绑定，旧0.1/0.2/dev1固定链保持；全局插件未安装或刷新。本聊天未跨改GREA源码。公开结果合同仍beaver-result/1，新production schema3、config3 schema2、rename-sequence/1和Unity标准profile均见CLI-CONTRACT与各模块文档。

接入时回传：固定wheel/implementation身份、项目和具体既有任务、精确修改清单/plan/journal、原生及项目测试/App结果、未验证项与恢复限制。不要只发ACK或工具版本；也不把一次工具试点写成完整游戏验收。

候选06替代05：只增加重复资源绑定在Editor启动前的拒绝；固定wheel身份如上，旧05保留但不派发。完整联合run13通过，全部失败回执与恢复证据保留。

最终本地证据索引：`docs/VALIDATION-v0.3-candidate.json`。首次App因fixture误要求持久监听而失败、首轮鼠标验收因桌面工具延迟超时均保留；仅修正验收脚本，通过后续匹配App与真实输入证据收口。原游戏代码/正式工程未为该断言改动。

最终候选07替代06：仅更新CLI能力中的过期验收说明，并移除C#模板末尾一个空行；逐文件核验差异仅此两项，新增11项相关检查通过。完整原生事务及恢复证据仍绑定06/r18，禁止用07重放这些旧事务；Player由07干净安装从/private/tmp实际调用同一固定App核验。旧候选均保留且未派发；用户已批准派发当前07，三位主开发已收到协调。

候选08修复正式中文路径暴露的Editor启动边界，版本为本地0.3.0（无Release）：UTF8 job文件路径以ASCII base64传递，三套Editor companion严格解码；Editor仅继承必要路径/用户/locale/代理与证书及已有许可路径，不继承PWD/OLDPWD或任意agent变量。父环境不改变，必需变量编码无效则不输出值并提前拒绝。118项标准测试及8份C#真实引用编译通过；正式中文路径原生结果仍待，不预先断言因果已闭合。07的两次失败和旧事务保留；08必须显式重绑定并生成新计划。

最终打包09相对08只改dist-info/METADATA中的README版本/状态及RECORD，68份beaver执行/模板文件逐字相同，版本与producer均不变。08在途计划可保持原包；所有旧包与证据保留。App04特定停止例外已取得本聊天人类直接批准并转交原主开发，原生接入继续。

最终状态：真实肥鹅主开发已在既有购买提示任务实际采用，两份代码安装历史、08独立原生收敛与4项项目测试均核验；App04通过明确-force-gfx-direct正常进出，默认Metal失败仍保留。当前producer自有Play3秒121260帧/0错误及中文apply/recover通过；中文独立副本的Unity Search启动异常严格保留为Play失败。最终包相对09仅README元数据/RECORD，68运行文件不变。旧的“待验”段落为候选演进记录，现行结论以PLAN及51项证据索引为准；不外推完整游戏保真、生产服务、任意Unicode Play或当前全局插件已更新。
