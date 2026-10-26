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
