# 生命周期原生接续样例

这是GREA自有的最小验收材料，不来自任何游戏工程。它验证外部monkey候选→隔离Unity接续→有界功能增量，不是第二套转换器、通用游戏模板或自动业务翻译。

- `fixture.py`生成一个Creator2.4.15 Prefab（背景、Sprite按钮）、白色纹理、正式JSON和未执行的JavaScript规则证据。新输出必须不存在。
- `Editor/NativeAdoption.cs`仅处理这个样例的隔离导入边界：TextureImporter实际生成Texture2D/Sprite、保存空白bootstrap场景、创建场景输出目录，再调用外部provider自己生成的`MonkeyImporter.ImportBatch`。
- `Editor/LifecycleBuilder.cs`通过Editor API实例化实际转换Prefab，在新`Assets/Game/`中保存、重开原生场景并检查引用，运行规则反例，构建macOS Player。样例实例中的480×720布局、标签和新增控制是明确的接续实现，转换Prefab原件保留。
- `Runtime/CounterState.cs`是自有规则与独立存档服务；Controller持有原生Button/Text序列化引用；PointerEvidence/InputEvidence记录实际输入与焦点，未增加输入模拟或运行时源引擎。业务实现由GREA补齐，不声称从JS自动翻译。
- `config/lc1.json`：每次+1、退出重开计数保留；`lc2.json`：菜单→开始→三次计数→结算→再玩，暂停/继续/返回菜单，累计次数保留。

仅运行于新隔离工程和显式`-grea-data-path`绝对目录，无该参数则Player显示错误，不使用普通游戏存档。数值真源是Player实际解析的Resources/Config/counter.json，配置版本变化不作为拒绝旧档的理由。LC2从schema1追加迁为schema2，原文保存为`.v1.backup`，保留count/pending；未知未来版本、缺版本、坏配置不覆盖旧档。此客户端样例不适用于回滚MySQL权威资产。

## 复验步骤

1. 用GREA包内Python执行`fixture.py --output /path/fresh-owned-source`，锁定外部monkey实现及capabilities，再调用[显式slice入口](../../../plugin/skills/grea/references/providers/monkey.md)。全程不执行Counter.js。
2. 固定Unity6000.6.2f1。先保留候选、manifest及来源SHA。在全新Unity Editor脚手架中，经PackageManager添加`com.unity.ugui`、必要时`com.unity.2d.sprite`；记录**解析后的实际版本**（本机uGUI builtin2.6.0，不能只记录请求的2.0.0）。候选原件不修，显式复制Assets/Analysis到接续工程并记录差异。
3. 在接续工程`Assets/Game/Editor/`放NativeAdoption.cs，通过batch executeMethod调用`NativeAdoption.Import`。检查provider的Analysis/editor-readback.json：正确Unity版本、Missing Script0、editableRoundtrip、实际Sprite/UI引用及逐个原生文件hash。导入是create-only；失败半成品保留并另开干净副本，不无条件删除重跑。
4. 将Runtime/放`Assets/Game/Runtime/`，LifecycleBuilder.cs放`Assets/Game/Editor/`，lc1.json放`Assets/Game/Resources/Config/counter.json`。调用`LifecycleBuilder.Build`，检查Analysis/grea-native-acceptance.json、构建日志、实际.app。只在这个样例执行构建，不对任意用户工程套用。
5. 启动.app并传`-grea-data-path /absolute/isolated-data -logFile /absolute/isolated-player.log`。用真实桌面输入操作ADD +1，检查显示与events.jsonl，再QUIT，重开同一包检查存档。输入注入未进入Unity时记录局部失败，不改写业务事件冒充输入通过。
键盘复验：LC1默认选中ADD，Return计数，Down→Return退出。LC2默认选中START，Return开始；playing默认选中ADD，Down→Return暂停；paused默认选中RESUME，Return继续，Down→Return取消；victory默认选中PLAY AGAIN。每个动作后先核对画面和events。当前自动鼠标在Unity读取为窗口外坐标，保持not_passed，不能将本轮键盘结果写成鼠标通过。

6. 冻结LC1工程/Player/配置/数据hash，另复制工程（排除Library/Temp/Build）和独立存档目录，替换为lc2.json，再构建。验证迁移backup与count/pending、开始/暂停/继续/三次结算/再玩/取消、退出重开。保留LC1包，不以覆盖构建代替版本对比。

`unity run`可执行同步Importer/Builder；异步PackageManager安装要用官方Editor binary batchmode且**不带-quit**，在EditorApplication.update轮询完成后退出。无Pipeline时不安装全局插件。不要手写场景/Prefab YAML。

原始provider候选、GREA显式adopted工程、规则测试、构建、桌面输入、画面、存档、分发恢复是分开的验收项。修复后工程的Editor通过不能伪造原候选的native resume pass。当前执行记录在[生命周期计划](../../../proposals/lifecycle-roadmap.md)及validation/development对应报告；样例通过不代表任意真实游戏完成。
