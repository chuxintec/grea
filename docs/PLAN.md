# beaver v0.4：接收GREA执行工具（2026-10-27）

用户要求GREA以技能为主、执行代码迁入monkey/beaver并统一发布。0.4.0在0.3.0上新增`toolkit`包：23个GREA执行工具原样迁入（ID/报告/退出码不变），`beaver tool <id>`运行，对应测试69项迁入`tests/toolkit`。全量190项中188项通过；2项Go测试依赖主checkout的`.private`私有工具/夹具，在隔离worktree中缺失，主checkout原样通过。v0.3全部事务与制品不变。

# beaver v0.3：Unity＋Golang联合开发与交付

2026-10-26，0.3.0本地交付（未发布），codex/beaver-v0.3；基线fae3845，0.2全部制品与事务保持。完整范围沿Manager/decisions/20261026-grea-monkey-beaver/BEAVER-V03-UNITY-PRODUCTION.md；真实用户三条授权见.private/v03/authorization.json，含最新Golang必选补充。

当前维护定位（2026-10-27）：将既有肥鹅 v1.2 按需支持延续至 v1.3 完整主体，按[总监 v1.3 计划第四节](/Users/wangmeng/Documents/Manager/decisions/20261027-foodstreet-v13/PLAN.md)支持真实任务中的 GREA＋beaver 通用工程执行缺口。已原生核验总监聊天 turn `01a17af6-4be7-7651-a107-2dca3728f7a7` / human `01a17af6-4c06-7682-b8eb-0ef50e01cc28` 的实际用户指令；复用已验证的 beaver 0.3 固定包，带限制本地交付记录及历史失败保持，不因支持范围延续而新建工具版本。

优先接收批量 Prefab、资源引用、代码、JSON 配置及构建的具体通用执行缺口；小范围纯代码修改不强制复杂工具事务，工具失败不阻断可独立推进的游戏业务。最小复现记录固定工具身份、命令/目标、预期与实际、错误定位、影响和可用替代；只有真实任务依赖且有可操作证据时，才针对性修复并验证受影响部分。历史中文 Play／Metal 问题不作为自动清零任务，不重复已验证整套，也不自动开启广泛新版本。

游戏业务及正式工程由肥鹅单写，Skill／方法／薄适配由 GREA 单写，通用执行问题及私有复现由 beaver 负责。项目专用证书和启动修复由肥鹅实施，仅其中有最小复现的通用工具缺口交 beaver。本轮真实缺口可在三位已登记开发者与技术总监间直接低通信协调，严重阻塞、数据/架构风险或权限裁定交总监；不跨写正式游戏、服务或存档，不新增全局安装、推送或 Release。普通 ACK 不作为开发前置。

已完成维护：肥鹅 `storage-feedback-01` 暴露执行后的结果合同差异。固定 beaver 已原生 verified、退出 0，但 GREA 将合法 `actualChanges` 路径字符串限定为对象而拒收。beaver 已明确逐项 string/object 合同，并以固定安装版通过 6 项 CLI 合同检查；保存原始 provider stdout 后，只读验证 GREA 修正后的校验可接受原四路径并拒绝五类非法项；生成 Schema 与代码一致，GREA 的 8 项受影响检查及原结果离线重验通过，原 invocation/外层失败文件哈希未变。原外层 needs_action、原生成功及事务分别保留，不重放、不改旧回执。GREA 主开发已修正消费侧 Schema/生成文件及执行后失败提示，并向肥鹅交接；beaver 仅改文档/回归，版本、wheel 与 producer `e6191235…` 不变，无 Engine/游戏/服务写入。证据在 `.private/v03/result-contract/` 与 `.private/v03/result-contract-tests.log`。v1.3 当前暂无新增具体通用缺陷或执行器实现任务，不派发子 Agent或循环巡检。

| 组 | 状态 | 出口 |
|---|---|---|
| A 工程私有接入 | native_foundation_verified | 版本/根/所有权/精确写区、预检与显式重绑定 |
| B 资源生产 | private_native_and_app_verified | 图片/切片/Atlas、TMP字体与匹配Spine原生闭包、材质/音频接线 |
| C 复杂JSON/C#与Go | private_runtime_verified | 嵌套/数组/字典/枚举/可选/nullable、跨表资源、DTO与运行读取/兼容差异 |
| D 模块/C#维护 | native_verified | 有所有权模板、Roslyn语义类型/namespace/字段改名与Unity序列化保护 |
| E 联合事务 | native_verified | 资源+JSON+C#消费者增量写集、可信checkpoint与受控恢复 |
| F 实用验证/交付 | private_app_and_physical_input_verified | 受影响编译/PlayMode、匹配Mac候选、过程及输入/日志证据 |
| G GREA/真实消费者 | local_adapter_and_real_consumer_verified | 固定包/兼容差异、私有安装与正式项目主开发实际采用 |
| H Go服务器工具 | owned_stack_and_app_verified | BEAVER-V03-GO.md：六服/协议/持久事务/迁移/构建/owned Docker栈、Unity真实联调；共享服务只读 |

主开发单写CLI/公共合同/事务/Editor/集成，优先复用现有模块Agent。开发与原生工具存在、原生执行、真实输入、可见画面、产品业务及真实消费者采用分别记录。正式肥鹅v1.2、Go服务、账号、玩家档、暂停项目和其他工具源码只读。允许beaver.private独立具名Docker项目/网络/数据卷、回环端口和自有测试库；先核占用，不碰QA05/共享容器/卷，不prune。无远端/Release/全局安装/引擎下载/正式服务变更或素材外发。本版整体已按声明限制完成本地交付；真实消费者与上游私有证据分别记录。

v0.2已完成50项Python及固定真实隔离UI/恢复证据，不重复全量基线。当前第一组工作：建立私有工程接入/联合事务合同，同时实现独立资源、复杂配置及C#维护模块。

首轮实现：workspace私有绑定/版本与工具字节锁/写区/显式搬迁与依赖重绑定，3项边界检查通过；production schema3联合fileEdits和原生资源/Prefab步骤接入原批处理checkpoint，3项计划/漂移/写区检查通过，原生执行待成组。Go同一Schema C#＋Go加载及真实隔离MySQL联调是必选，不以health-only模板或空壳UI替代。v0.3仅新增影响验证，正式消费者仍pending。

集成进展：88项当前标准库测试通过（.private/v03/tests-integration-01.log）。固定r01在独立NativeProject完成JSON新文件＋既有Prefab同组原生apply与recover，交易/恢复各自checkpoint、写集及原字节回读通过，未计划变更0；仅证明联合事务基础，不代表B–H完成。真实肥鹅副本已独立复制，首次原生导入进行中；新Bee上下文将用于真实语义重命名。Go候选编译通过后复核发现SQL回执列对齐问题，修正前未启动隔离栈。

真实副本首次原生导入已成功：6000.6.2f1退出0、errorCS=0；与v0.2准备副本逐文件SHA比较54288路径，源文件变更0。证据.private/v03/foodstreet-first-import-audit.json；新Bee生成于v03本副本。

原生资源集成发现并保留失败回执：run01缺Sprite builtin包、run02 API签名错误均发生在native方法前；已通过Unity PackageManager启用本机Builtin com.unity.2d.sprite@1.0.0并核lock。run03已编译/执行setting enum6，但Sprite身份保护把本次新占位误判为旧Sprite；补丁现已实际csc编译。另发现EditorSettings在退出后保存导致原生checkpoint/after唯一该文件不匹配，普通recover正确blocked；显式native修复首次也以磁盘读回不符失败，修复前不报告恢复完成。所有源变化仍为声明写集，原始失败证据不覆盖。

Go首轮真栈beaver-go-review03六服+MySQL+Redis曾全部healthy，5owner迁移按真实容器/volume/network标签、单owner账户及旧schema SHA保护逐库applied。首次MySQL host-bind bootstrap noexec失败保留卷，经固定脚本stdin受控修复后成功；模板改image-layer COPY。宿主HTTP未通（internal-only network未实际发布端口），因此尚无业务联通通过结论，准备修复为gateway专属edge+private网络。旧自有栈正常stop保留数据，不触碰QA05。

Go修复后的beaver-go-edge05已真实启动六服+MySQL+Redis，数据库bootstrap来自固定base镜像层、不再host-bind执行；5owner新空库迁移已applied。运行工具核验实际gateway 127.0.0.1:18296→8080，HTTP真实登录和state回读revision0/balance0。拒绝错误凭据/无session、拒绝int64数字wire、billing固定Unavailable均实测；未发送资产命令，保留fresh state供Unity首笔交易。下一步Unity使用与Go相同JSON/schema并生成同snapshot token后实际请求，仍未完成H。

H实测推进：Unity 20秒PlayMode 834599帧、playErrors0、源SHA未变；配置InputSHA dcb45ca1…/SchemaSHA60ce9e30…与Go一致，Unity首笔unity-first-001获APPLIED/rev1/余额10，精确重试响应body SHA一致，ID内容冲突与旧revision均拒绝。MySQL单owner回读确认资产仅revision1/10，一条APPLIED与一条持久化REVISION_CONFLICT回执（不是仅一条总receipt），config digest与Unity请求snapshot一致。已重启六服及MySQL，Redis标记key存在1→FLUSHDB后0，均自有edge05栈。

App build01成功（73,032,618构建字节、源变更0），首次Player没有业务result，因复制基线旧BeaverV02Probe仅允许.private/v02输出并主动Quit(1)；保留该失败，不称App业务已过。正通过原生Prefab remove退役旧测试组件，新增probe安全启动日志与自身PNG，准备重建真实Player恢复验证。

最新集成：111项标准测试通过（tests-integration-03）。C#真实namespace→type→field顺序候选255唯一输入、三阶段重编译零诊断；root新增公开rename-sequence入口及审阅后写区rebind策略。真实资源联合run04包含260输入/9步骤，仍因EditorSettings native值6而即时磁盘0失败；写集外0，原回执保留。explicit native repair04首次也遇退出落盘，04b已精确恢复全before。定向ProjectSettings新API先在小型自有工程验证。

H实际App闭环通过：go-unity-build-run-03固定制品，player-run-05实际读取同JSON/schema并恢复原intent，APPLIED/rev1/余额10、精确重试bodySHA 8a4eea44…与首次Play一致；内容冲突/旧revision拒绝。实际App绘制成功状态并保存自身frame PNG；CUA截图亦可见该状态。此前App后台暂停造成60秒内无结果，验收probe显式runInBackground后完成，旧失败保留。六服/MySQL重启及Redis丢失后App重放，SQL原行逐字一致，仅一APPLIED、共两回执（含持久化REVISION_CONFLICT），无新command_id。证据edge05-after-app-replay-mysql-audit-02。普通UI按钮输入尚未取得计数变化证据，不据此报告真实输入通过。

设置落盘修复已原生验证：settings-probe-run-02（r11）第一Editor pending_editor_reopen，第二Editor strict verify通过，editorStarts2，witness一致；同固定工具普通recover成功恢复精确原始设置字节（不再依赖explicit修复）。旧失败journal原样保留。真实联合run05沿同合同继续。

真实run05已通过设置live验证，在Sprite逐项读回发现差异，事务明确failed；正在修复Sprite持久元数据而非放宽断言。补充通用失败恢复：新双Editor合同如首轮已有完整原生见证但步骤失败，次轮只生成退出后checkpoint用于恢复，永不把checkpoint_verified当业务/操作成功；first-failed/second-checkpoint及second-failed负向测试通过。无编译见证的旧失败仍不能普通恢复。

114项全量标准测试通过（tests-integration-04），native资源修正均有实际Unity引用编译。公开CLI生成的标准profile五层模块已在NativeProject原生安装编译；独立Play实际通过同一JSON reader/Gameplay context/View/Bootstrap与4类坏配置拒绝（module-play-run-01），未产生源码变化。标准profile不影响Go分层，旧模板仅显式legacy。

真实run06切片已通过，修正V2 authoring读取后run07 Atlas pack通过，字体负向发现原8源TTF缺鲯；run08中文主字库生成后发现同名Atlas/Texture对象歧义，已按SerializedProperty声明类型筛选唯一目标，不猜First。06/07/08均通过独立checkpoint普通recover恢复全部before、未计划变更0。positive corpus3008字并用本次生成静态中文字库作为英文标题fallback；鲯失败及全游戏字形未覆盖限制保留。

run10前9项原生通过（设置/切片/Atlas/主字体/Spine闭包/SO字段引用/音频/材质），末项fallback私有TMP查找遇未初始化缓存；改公开HasCharacter(c,false,false)逐个检查主字体与明确直接fallback，不使用TMP私有状态或未声明global/default。随后完整114测试再通过（integration-05）。恢复遇Licensing Client连接中断；只读核验和Hub刷新已有Personal许可后原生恢复完成537路径exact before，无新增license/协议、无全局进程重启。新r16/run11继续。

自有Go栈edge05已正常stop并保留全部卷（edge05-owned-stop）；H首笔与App重放、SQL单次入账、重启及缓存丢失证据完整，既有QA05不受影响。

真实run13完整成功：260独立文件输入＋10原生步骤，两个独立Editor，final checkpoint/after完全一致，unplanned0。设置、两切片（normalized pivot）、目标Atlas重新pack、3008字主字体、英文标题的明确中文静态fallback、匹配Spine闭包、原SO字段areaTextureAtlas引用GUID/localID、音频与材质导入全部strict verified；271实际变化。stage13之后验证完整成功的普通recover，再重建最终App源。Font1/Font2对同一标题的冲突已修正为单一最终绑定，新增PRODUCTION_BINDING_CONFLICT启动前拒绝；115测试通过（integration-06）。

成功事务run13的普通recover已精确恢复before，run14沿同固定计划重新apply且双Editor strict verified。匹配build01成功1,280,445,566字节，源变更0；App实际读取1293物品/3432订单，Spine idle时间递增、28顶点、CanvasRenderer可见。首次App因fixture错误要求persistent监听失败，原视图实际Awake.AddListener且关闭已触发；失败原件保留。通过独立production事务real-probe-fix-run-01安装仅验收脚本修正（旧/新SHA受控），持久监听字段保留诊断，实际关闭仍必须观察；准备build02与真实输入。未改正式游戏。

最终匹配build02及两类Player证据已通过：源SHA8deb67c8…，制品清单46b57b88…，1,280,445,566字节，build/source无变更；real-player-run-02返回verified/exit0，实际JSON1293物品3432订单、目标Atlas/Sprite/生成字体和Spine idle（time增加、28网格顶点、CanvasRenderer可见）。real-player-physical-02由CUA实际滚动/点击关闭，无SyntheticClick/ProbeScroll，内容y0→133.01039，视图inactive，verified/exit0；制品启动前后逐文件一致。首轮physical-01因桌面调用长延迟达60秒预算，仅记超时不算输入通过。原按钮Awake动态监听如实保留persistent=false诊断，不强迫改游戏。

完整本地候选06已核67包文件与当前源码逐字节一致；公开证据索引docs/VALIDATION-v0.3-candidate.json列26份私有证据的SHA/字节及限制。G仍pending：未向其他聊天发送候选，等待本聊天人类对已提出的固定接入单协调授权；GREA当前仅显式0.2适配，正式项目采用须由其主开发在既有任务内完成。本版尚未完整交付；无推送/Release/全局安装/正式服务变更。

最终候选07修正公开CLI过期的pending说明及模板末尾空行，除此两项无执行差异；11项相关检查通过，67包文件逐字节一致。07 SHA7f085738…/implementation b6400dbd…，私有干净安装从/private/tmp调用同一固定App再获verified/exit0。原生事务仍用06/r18恢复，身份不混用。提交前精确清单64路径，无私有内容；G仍等待明确跨聊天协调授权与正式采用证据。

用户在本聊天明确回复“同意”，已按固定候选07向肥鹅主开发、GREA及技术总监发送本地接入协调。G状态consumer_in_progress：GREA负责有限版本/能力/Schema薄兼容及旧链保持；肥鹅只选既有批准任务实际采用，原已完成修正不倒退。各自主开发单写，本聊天回读交付，不用ACK算完成。无新功能/服务/玩家数据/发布授权。

正式采用发现07原生启动失败：中文job路径直接置env时，Burst在Mono枚举环境抛Illegal byte sequence，locale-only未解决；源码安装后工具failed、无native checkpoint，项目4项Play及App分别验证，不能据此算production成功。root修复原生子进程最小环境＋ASCII base64 job传输（三套companion，PlaySession保留解码路径），adoption身份纳入依赖；118项全量检查与8源/342实际Unity引用离线编译通过。固定候选08为本地0.3.0、wheel66fd8d32…、implementation e6191235…、68包文件精确。已给肥鹅/GREA新身份，正式工程由原主开发在旧after-image审阅后显式rebind/新计划受控收敛；G仍in_progress。root准备自有中文路径副本及证据目录，未启动Editor以保持单写。

G实际阻塞：肥鹅07已把两份代码按计划安装，4项项目Play通过，但原生companion前Burst失败，因此adoption仍partial。App04构建成功但PID5496卡Metal，未晋升，主开发遵守本项目AGENTS“不强退”。候选08已私有安装、显式rebind计划已准备但尚未apply；本聊天已请求用户授权该主开发核对身份后仅SIGTERM此App再重试。根不越权停进程、不改服务/玩家档；自有中文路径原生验收同等等待资源释放。GREA08适配独立继续。

用户已对本聊天具体问题选择“允许仅停止该App并重试”，已转交肥鹅原主开发：必须先核PID5496仍为原App04，仅此进程SIGTERM/同候选重试/08接入，无其他进程、服务或存档授权；root继续不碰正式工程或GUI。打包09仅更新wheel README元数据，68执行文件与08完全相同、producer e6191235…不变；最终09 SHA b480fb38…，08在途计划保持。

最终整版收口：固定本地0.3.0包 .private/dist/v0.3-final/beaver_game_tools-0.3.0-py3-none-any.whl，239672字节，SHA d4dd7229fa9ce56eabb9054d0af2b88591aa0777fe4e3d0fc139b74a105eb598，producer e6191235…；68包文件与08/09及当前源码完全一致，仅README元数据收口。118测试、8源/342引用C#编译、当前producer Play3秒121260帧0错误/source无变化，自有中文project/evidence apply与精确3路径recover通过，Engine资源全部释放。中文独立副本Play的Unity Search异常在cleanLibrary仍复现，严格failed不筛除，不能归因旧缓存；正常ASCII基线Play通过，中文apply/recover与正式08原生成功分别保留。

G已完成实际出口：肥鹅既有v1.2购买提示显示层级修正，两份代码原经07精确安装但native失败；08显式rebind、新计划对既有after-image独立原生收敛确认（不虚构新代码delta），compile/save/reload verified、未计划0，4项目Play通过。App04默认Metal失败保留，已用-force-gfx-direct两次正常进出/浏览/正常退出；不是默认渲染已修或完整游戏验收。GREA本地源码49明确路由/45定向检查、真实私有CLI和独立stdio的ok/blocked/failed、旧链/精确版本/producer/rebind均通过；全局插件未更新，未接入Go live路由与旧Go退休不外推。51份证据哈希及两份消费者不可变观察回执见docs/VALIDATION-v0.3-candidate.json。

A–H按本版授权边界完成；0.3.0为本地交付，无推送/Release/全局安装。后续版本与Cocos不自动启动，正式游戏/服务继续各主开发单写。已知限制为本版明确边界，不以失败冒充通过。
