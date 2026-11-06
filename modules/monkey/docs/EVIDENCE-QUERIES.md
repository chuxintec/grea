# 冻结来源的流式查询与内容核验

开发版0.5.0.dev1新增 `query-methods`、`query-tables`、`inspect-aliases`，复用monkey的路径/预算/错误/输出合同。使用显式开发入口 `.venv/bin/python -m monkey.cli`；稳定安装版仍是0.4.0，尚无这三个入口。本能力不执行原脚本、程序集或WASM，不修改人工游戏工程。

## 方法映射

```sh
.venv/bin/python -m monkey.cli query-methods   --source method-map.json --expected-sha <完整SHA256>   --type Unit --method Upgrade --module main --function 123 --limit 20   --out query-methods-result
```

输入是UTF-8/BOM JSON对象数组，每行至少有字符串 `type/name/module` 和非负整数 `function`；额外assembly/token/slot等原字段保留，不猜方法重载或合并不同module。type/method为不区分大小写的包含搜索，module及function为精确选择；省略module会查所有模块。

分64KiB块严格读取，完整扫描到EOF并核SHA，即使显示limit已满也继续校验。回执有totalRows/matches/returned/limited和完整源身份。`methodBodiesRecovered=0`：映射、签名、函数号或反编译文本都不能因此算已恢复C#方法。此入口不生成或编译方法体，原dcmp/模块仍是另行冻结的证据。

## 嵌套表归档

先查清单，不展开表目录：

```sh
.venv/bin/python -m monkey.cli query-tables   --manifest tables-manifest.json --expected-manifest-sha <清单SHA256>   --contains Level --limit 10 --out query-table-list
```

清单格式 `{"files":[{"name":"fp-Example.json","bytes":123,"sha256":"..."}]}`。名称是精确相对路径，变体分别保留；display/fp、地区、语言和分关卡不能按近似名称或相同表后缀擅自互换。listing只证明清单元数据完整，不证明全部表载荷均已读取。

从ZIP（也可为外层ZIP中的一个嵌套ZIP）核验提取一份：

```sh
.venv/bin/python -m monkey.cli query-tables   --manifest tables-manifest.json --expected-manifest-sha <清单SHA256>   --source handoff.zip --member Evidence/Tables.zip --expected-sha <内层ZIP的SHA256>   --extract fp-Example.json --out query-selected-table
```

完整核验所选内层ZIP字节，临时落盘后检查其全部条目名称/大小与表清单一致；仅所选表再核内容SHA/CRC，并以create-only方式写到输出 `payload/<精确名称>`。未知条目、大小写/路径前缀碰撞、重复目标、链接、篡改和已有输出均拒绝。表载荷按原字节保留，不把提取当作schema/数值语义已验证。

## URL别名与内容身份

```sh
.venv/bin/python -m monkey.cli inspect-aliases   --source routes.json --expected-sha <路由清单SHA256> --alias '/assets/a?version=1'   --content-source handoff.zip --content-prefix Runtime   --out query-alias-content
```

输入格式 `{"entries":[{"url":"/assets/a?version=1","path":"payload/a.bin","bytes":123,"sha256":"..."}]}`。URL只作为精确键，不解码、不忽略版本参数、不联网；path是严格受限的相对路径。按完整内容SHA+大小统计别名，共享内容不丢来源键；重复URL、同路径不同内容、同SHA不同大小拒绝。

可只读路由索引；这时contentVerified=false。指定精确alias后可用content-source目录或ZIP核实际载荷，content-prefix只限定ZIP/目录内的相对根，不能越界。只宣称选中内容通过，不推断其他资源、动态加载、来源原版或游戏完整性。

## 身份与预算

三个命令都输出 `inspection.json`，带producer版本、operation、sourceCodeExecuted、源SHA与验证层。直接文件的SHA对应整个所选文件；使用 `--member` 时 **expected-sha只对应这个成员的完整字节**，源回执明确 `selection.kind=zip-member` 与 `containerHashVerified=false`。不会为了单项查询重复哈希整个多GB外层交接包，外层包完整验收应引用其独立回执。

单项来源最多512MiB，单个JSON值8MiB/20万节点，最多200万行；外层ZIP最多8GiB/50万条目/8GiB展开量，路径最多64层；结果limit为1..1000、回执最多32MiB。沿既有strict JSON逻辑拒绝重复键、非有限数值、缺逗号、尾随数据/逗号、截断和非法UTF-8；源字节/大小全部核验后才发布结果。临时表归档和选中表以有界块处理，临时文件离开上下文清理。

## 接入现有Unity代码证据合同

`--unity-code-evidence`既有schema1清单新增role：method-map、decoded-table-manifest、resource-alias-index、adapted-binary。它们归入SourceRecovery，保留与查询时相同的内容SHA；不会变成Player运行配置或业务实现。

adapted-binary必须声明 `derivedFromSha256`，指向同一清单中具有不同SHA的source-binary，原模块/适配模块分角色与哈希目录保存。该关系由清单声明，不能证明二进制等价。名字含original、相同URL、通过wasm-validate、存在DummyDLL，均不能替代来源与方法体证据。

当前实现/样本核验见 [本轮记录](validation/2026-10-26-colleague-evidence-intake.md)。安装/发布与GREA/beaver调用绑定仍按各自授权执行。
