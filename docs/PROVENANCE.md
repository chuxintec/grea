# 来源、提取和许可

`SOURCE-INVENTORY.json` 对总监指定 56 项逐项记录内容身份、导入依赖、函数、硬编码与敏感标记计数、归属和处置。筛查不包含凭据值或游戏素材。56 项读取后重验一致，与总监种子哈希相同。

`SOURCE-FREEZE.json` 固定 monkey 通用采用实现及其依赖身份；原文快照只在 `.private/sources/monkey`，不作为运行依赖，不进入 wheel。正式提取只包含工程采用、清单消费和受限文件工具。没有提取 Cocos/Unity 源包解析器。

- `adoption.py`、`adoption_native.py`、`candidate_snapshot.py`、`output_limits.py`、`owned_fs.py` 和 `targets/BeaverAdoption.cs` 由冻结 monkey 对应文件派生。
- `io.py` 仅提取文件/JSON函数；`errors.py` 仅提取结构化错误和预算；`transaction_fs.py` 提取锁和原子写入。未复制 incremental 的候选转换、缓存、布局生成逻辑。
- Python import 改为 beaver 内部模块；状态根改 `.beaver`，C# 类型/环境变量改 Beaver/BEAVER；计划合同改 `beaver-adopt/1`，身份绑定增加实际依赖。
- `tests/test_adoption.py` 由 monkey 自有合成测试派生，使用 beaver 自有清单 helper。MIT 归属保留于包内 `licenses/MONKEY-MIT.txt`。
- GREA alpha audit 作为图片检查的算法来源；其 MIT 归属保留于 `licenses/GREA-MIT.txt`。后续提取需登记实际文件身份。
- 肥鹅和向僵尸文件只读盘点；游戏账户、ID/价格/规则、角色、素材、服务地址及原始日志未复制到包内。游戏工具仍留原工程，不移动、不链接。向僵尸保持暂停。

清单不是公开素材授权。私有项目仅作本地参考；公开示例只能使用 beaver 自有合成内容。第三方二进制未打包。


## 同事研发交接增量

`COLLEAGUE-INTAKE.json`固定四份完整已读脚本与相关清单结构的来源身份。整包源SHA来自总监索引，beaver只核选定ZIP成员CRC/SHA；不重复7GB解压，也不冒称整包完整审计。四份私有源仅保留于.private，不进入Git或wheel。

`payload.py`以既有受限I/O独立实现清单/别名/覆盖身份、独立复制及原子晋升，`unity.py`与`player.py`实际共用核验器；启动回执扩充exe/开始/PID/时限等证据。未复制源私有代码、数据、vendor、WebView/WASM或固定游戏常量。Windows脚本仅提供机制参考，未宣称Windows原生通过。macOS原子晋升常量按本机SDK的sys/stdio.h核对并用自有样例验证。

## v0.2 增量

batch、references、loading_keys、debug 及四份 Batch/ListView/SafeArea C# companion 为本项目新增实现，使用 Python 标准库和工程已有 Unity/uGUI/TMP API，没有再提取其他产品执行代码。v0.1 派生文件及原许可继续保留；大制品预算为显式新合同。

真实验证仅使用固定 f3991c6 交付源的 beaver 私有冻结副本与独立工作副本；54280 项冻结输入最终重新核验一致。真实素材、正式 JSON、业务代码、fixture、原始日志、完整原生报告和 App 全留 `.private/v02`，不进入 Git 或 wheel。公开验证索引只记录身份、计数、路径和支持边界，不分发游戏资料。独立 UI fixture 使用不同 bundle/company/product，无 Entry/Mainline/Preview host，无账号/普通存档或业务服务访问；不将此隔离能力宣称为通用工具自动提供。

## v0.3 增量

GREA 通用 Go 六服执行模板按固定交接清单 SHA `283f5fca66e95f1fa65a52fa3c43169f40661ded30a13db375a6e0bb37ab92b3` 接收，45份源文件/104020字节，选定22份模板保留于 `server_templates/grea_seed/`，实际源身份逐项记录 SOURCE-MANIFEST。沿用包内 GREA MIT 归属，未复制 Cocos、旧破坏性脚本、运行凭据或游戏业务数据。protobuf 由已验证 protoc/plugin 生成，不手改生成文件。Unity/C#工具及复杂配置读取器为本轮新增实现；运行需要调用方已有 Unity/.NET/Go/protoc，不打包其二进制。

真实 FoodStreet 的 v0.3 资源、JSON、代码快照、改名候选、原始日志和 App 继续只在 `.private/v03`。自有 Go 示例配置可作为模板内容；Docker secrets、容器卷和测试账户不进入 Git/wheel。工具健康、私有试点和正式主开发采用分别记录。

原生进程UTF8 job的ASCII base64封装及受限子环境为beaver独立实现，仅Python/C#标准库，无新增第三方二进制。正式采用的Mono环境枚举失败保留原始日志，根因以实际重试结果界定；未使用文件名编码猜测或改名。Mono编码语义参考 https://www.mono-project.com/docs/faq/technical/ 与 https://www.mono-project.com/docs/advanced/pinvoke/，文档不替代Unity原生验证。

## v0.4 toolkit 兼容

从本仓固定提交6791ddf98e31e411f7efe17d474f66251a1e9f76定向恢复src/beaver/toolkit与其测试，保留GREA MIT归属及原始工具ID/报告/退出码。该提交的父提交正是本轮基线1f62450；未导入旧版本号或覆盖在途CLI。恢复的58个文件字节身份见私有toolkit-compatibility回执；旧0.4.0轮包/producer不覆盖。新UI检查、接线和诊断由本项目实现，不包含肥鹅业务/素材。
