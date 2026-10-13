# 通用脚本沉淀与调用

`grea/game-building/scripts/` 是通用恢复工具的维护入口。工作区 `grea/` 存放第三方工具和运行时，项目目录保留业务适配与证据。脚本输出指向任务目录或临时目录，不写回技能包。

## 抽取与验证流程

技能本身的链接、路由可达性、显式 CLI ID 检查与任务场景走查见 [技能维护验证](skill-checks/README.md)。入口为 `recovery check_game_build_skill`；只读检查，不执行 Unity 或被检查工具。参数、退出码、候选目录用法和能力边界统一在该说明维护。

1. 工作中形成可复用能力后，先查询本目录；决定调用、扩展已有工具或提炼新工具。读取候选脚本及调用方，确认参数/输出契约与副作用。
2. 移除硬编码路径、包名、设备号、对象ID、坐标及玩法常量，通过 CLI/配置传入；提供 `--help`，外部程序路径可配置，不依赖原项目模块或隐含 cwd，不自动安装缺失依赖。
3. 新输出默认拒绝覆盖输入或既有证据，归档和映射路径不能逃逸输出目录；失败非零退出。失败可能留下部分输出，检查后改用新目录，不自动清除用户文件。
4. 从tools和项目目录以外的 cwd，至少运行两组不同输入；按风险检查输入缺失、输出冲突和越界等情况。语法检查或 `--help` 不能代替运行验证。
5. 在本文件登记来源、依赖、用法、输出与验证边界。保留既有调用兼容；迁移调用单独验证，不把项目内部工具树搬空。

Prefab 导出器只有在跨文件对象引用、Camera、分支和命名规则均已配置化后才可归为通用工具。关卡求解、存档结构和定向设备操作通常仍留在项目适配层。不为凑 Python / mjs 两类而搬迁业务脚本。

脚本若涉及安装、联网、设备输入、存档修改或清理，须明确副作用；收入工具目录不代表获得执行授权。虚拟环境、node_modules、逆向工具二进制、包体和产物不随技能复制。

## 当前工具

`GREA_ROOT` 为工作区 tools 目录绝对路径，`PYTHON` 为含所需依赖的解释器；脚本自身不依赖工作区名称。

| 脚本 | 来源 / 依赖 | 输入与输出 | 边界 |
| --- | --- | --- | --- |
| `game-building/scripts/unpack_xapk.py` | 原 grea/game-building 同名工具；Python 3.9+ 标准库 | XAPK → Reference、APK清单、各包独立 assets/libil2cpp、源SHA-256 | 不安装、合并分包或执行Android代码；只展开顶层APK的所选内容，不是反编译器 |
| `game-building/scripts/video_sheet.py` | 原 grea/game-building 同名工具；Python 3.9+、Pillow、ffmpeg | 本地录像 → 标注近似采样时间的联系表 | 裁剪/范围/采样率可配置；不控制设备，时间不是原帧PTS或事件时间 |

```sh
"$PYTHON" "$GREA_ROOT/game-building/scripts/unpack_xapk.py" /path/game.xapk --output /tmp/game-extract
"$PYTHON" "$GREA_ROOT/game-building/scripts/video_sheet.py" /path/native.mp4 --output /tmp/native-sheet.jpg --start 0.4 --duration 2 --fps 8 --ffmpeg /path/to/ffmpeg
node "$GREA_ROOT/game-building/scripts/static_build.mjs" --source /path/webgame --output /tmp/webgame-dist --map index.html=index.html --map src=src --map public/assets=assets
```

选择新的输出路径。视频 `--crop LEFT TOP RIGHT BOTTOM` 使用原视频像素，`--columns`、`--width` 只控制联系表排版；完整参数见各工具 `--help`。

## 既有工作区兼容

此前 grea/game-building 工具及项目调用保持原状，迁移前未改主项目入口。它们是迁移前兼容版本；新任务调用grea/game-building/scripts版本，不在两处并行新增同一能力。当前解包器改为分块计算哈希，并支持没有顶层APK的归档输出来源记录。

后续迁移旧入口前，确认它是否依赖历史合并解包目录、固定裁剪或输出命名；保留适配或显式迁移，不用新输出直接覆盖旧资产目录。工作区运行时按实际环境定位。

## 验证边界

本次已从临时 cwd 实际验证：双APK同名资源分别保留及源哈希、仅含元数据的归档；横屏/竖屏两种录像的联系表尺寸；两组静态文件映射的字节一致性。拒绝条件覆盖已有输出、归档越界、非法裁剪、缺失静态源、映射越界/重叠、源内输出及符号链接路径。Python工具的 `--help` 与 Node入口已执行，未启动或替换任何项目服务。

运行检查使用合成归档、合成录像和独立静态目录；验证成功不代表真实游戏的全部包格式、资源或原版体验通过。抽帧联系表用于寻找阶段，完整流程时序仍须核对原录像。

## 新增只读分析工具

| 脚本 | 来源与依赖 | 用法与输出 | 边界 |
| --- | --- | --- | --- |
| `game-building/scripts/compare_traces.py` | 从本项目逐步棋盘/RNG差分需求提炼；Python 3.9+ 标准库 | 两份有序 JSONL，重复 `--field /board`、`--field /rng/calls` 选择 JSON Pointer；stdout 给首个差异的零基记录索引或长度差 | 不自动对齐不同事件序列、不猜字段、不容差比较；缺失字段为输入错误；不证明采样方法正确 |
| `game-building/scripts/read_elf_values.py` | 从金币动画常量地址读取提炼；Python 3.9+ 标准库 | ELF 加重复 `--address 0x...`、`--type f32`、`--count 2`；stdout 给文件偏移与值 | 支持ELF32/64、两种字节序的PT_LOAD文件映射；不反编译，不读取进程，不支持扩展程序头计数；无唯一映射、越界或非有限浮点拒绝 |

```sh
python3 "$GREA_ROOT/game-building/scripts/compare_traces.py" /tmp/native.jsonl /tmp/web.jsonl --field /board --field /rng/calls
python3 "$GREA_ROOT/game-building/scripts/read_elf_values.py" /path/libil2cpp.so --address 0x1234 --type f32 --count 2
```

轨迹比较退出码：0一致、1有差异、2输入错误。两工具不写文件；需要落盘时由调用方选择新的输出路径。地址必须是ELF链接期虚拟地址，分析器重定位基址或运行时加载偏移需明确扣除，不能无条件把RVA、运行地址和文件偏移混用。

新增工具验证使用合成ELF32/64与两类轨迹，覆盖相同、首差异、字段缺失、长度差、映射越界和错误文件；另用原版已分析二进制核对常量。合成输入通过不代表所有ELF变体或所有游戏事件模式都受支持。

## Unity 导出依赖审计

```sh
python3 "$GREA_ROOT/game-building/scripts/unity_dependency_audit.py" --assets /path/export/Assets \
  --root GameObject/Example.prefab --root Scenes/Example.unity --output /tmp/new-closure-report.json
```

输出父目录须存在，拒绝覆盖文件、写入源目录、根路径越界或符号链接。默认单个文本扫描上限 32MiB，可用 `--max-text-mib` 调整；超大或二进制文件列为未扫描，不静默算完整。退出码 0=静态扫描完成，1=清单已生成但有缺口，2=输入/执行失败。0 不保证动态加载、内建 GUID、脚本身份或运行可见性正确。

检查器将 `.cs/.dll` 全部列入待审排除项，并不认定它们全是空壳；实际导入前分类原实现/类型空壳/运行时依赖。文本 GUID 闭包不能替代 AssetDatabase 二次核验、二进制 PPtr 解析和 Resources/Addressables 动态加载调查。

## 保留项目专用的工具

| 专用适配器类型 | 作用 | 为什么不直接作为通用工具 |
| --- | --- | --- |
| 资源导入准备 | 选择原资源与依赖闭包 | 根资源、图集和场景规则由当前输入决定；未知引用必须报告 |
| 脚本与字体重映射 | 绑定程序集、类型和资源身份 | GUID／fileID 映射依赖目标工程，不能跨工程照搬 |
| 动画运行时安装 | 导入匹配的数据解析器与 Shader | 数据格式、API 与许可必须逐项匹配 |
| 编辑器接口适配 | 握手、发现与指定操作 | 协议版本与输出约定必须确认，优先已验证官方接口 |
| 场景生成与构建 | 创建工程和 QA 制品 | 宏、场景入口与存档隔离依赖业务目标 |
| 业务规则与体验测试 | 验证关卡、输入和持久化 | 替身与预置状态不能替代真实运行和关闭重开 |


使用这些脚本前检查副作用、参数、目标和本轮生成文件；尤其导入/构建的外层超时不授权重复执行。工具选择见 [技能工具清单](../skill/references/9-工具目录与准入.md)，Unity 连接、schema 和长任务生命周期见 [执行契约](../skill/references/11-Unity工具执行路线.md)；脚本命令和参数在本目录维护。

### 新增审计器验证记录

运行 `python3 "$GREA_ROOT/game-building/scripts/test_unity_dependency_audit.py"` 可重现合成夹具检查：两个不同根输入、传递依赖、代码排除、未知与重复 GUID、拒绝输出覆盖/源内输出/路径越界/根符号链接。测试仅写临时目录，不需要 Unity 或原包。

这些工具使用Python 3.9+；共同的只读哈希/目录保护逻辑在内部模块 `_artifact_common.py`，不依赖原项目。

| 脚本 | 输入/依赖与用途 | 输出及边界 |
| --- | --- | --- |
| `game-building/scripts/video_manifest.py` | 一个或多个本地录像；ffprobe，`--decode`时另需ffmpeg | 新JSON：SHA-256、字节数、时长、尺寸、帧率元数据、音轨及按需解码。0检查通过，1媒体问题已记入报告，2输入/工具错误。不是录屏器，不证明画面/声音内容或事件时序 |
| `game-building/scripts/verify_payload_tree.py` | 期望目录与已释放目录；Python标准库 | 相对文件名、尺寸、SHA-256的缺失/多余/变更报告。0一致，1差异，2输入错误。默认精确比较，显式exclude同时应用两侧并写入报告；不解包、不执行文件 |
| `game-building/scripts/package_windows_portable.py` | 已构建Windows目录、相对入口、标题、架构；makensis、7zz | 新EXE和同名`.manifest.json`。私有暂存快照→NSIS编译→7-Zip测试/释放→逐文件校验→独占发布。0仅表示包体通过，2失败；不运行游戏、不安装工具、不验证Windows兼容性 |

```sh
python3 "$GREA_ROOT/game-building/scripts/video_manifest.py" /path/recording.mp4 \
  --output /tmp/new-video-report.json --require-audio --decode
python3 "$GREA_ROOT/game-building/scripts/verify_payload_tree.py" /path/build /path/extracted/Game \
  --output /tmp/new-payload-report.json
python3 "$GREA_ROOT/game-building/scripts/package_windows_portable.py" --payload /path/windows-build \
  --entry Game.exe --machine x64 --title "Game Preview" --output /tmp/new-game.exe
```

输出父目录需存在，默认拒绝覆盖旧产物；目录工具拒绝根/后代符号链接和输入内输出。打包器另检查入口PE架构、Windows非法/保留名称和大小写冲突；通过参数指定外部程序，不自动安装。文件清单列出显式排除项，不默默漏掉运行依赖。

目录校验只比较普通文件，不比较ACL/时间戳或空目录。打包器当前不转发命令行参数；已实测x64，x86路径未做运行验收。

打包器只处理自己生成的NSIS包，不是任意不可信EXE解包器。私有临时目录只在子游戏退出后由NSIS正常清理；调用方确认存档在外部用户目录。启动器需要实际目标系统验证，签名与平台发布要求另行处理。输入或编译失败不会替换旧包；极晚的磁盘写入失败可能留下本次新文件，核对后换新输出，不自动清除用户目录。

### 可重现验证

```sh
python3 "$GREA_ROOT/game-building/scripts/test_artifact_tools.py"
python3 "$GREA_ROOT/game-building/scripts/test_artifact_tools.py" --integration --fixture-exe /path/existing-x64.exe
```

默认运行标准库检查并明确跳过外部集成；`--integration`需要已安装ffmpeg/ffprobe/makensis/7zz及一个本地x64 PE，只复制和封装它，绝不运行。测试创建独立临时cwd，涵盖两组不同目录、缺失/多余/字节变化、显式排除、拒绝覆盖/输入内输出/符号链接/非法入口；横竖两个视频、有无音轨与坏文件；两个真正编译并释放校验的NSIS包，第二组含嵌套中文路径、空格、单引号和美元符号。测试包没有完整游戏依赖，不是可玩版本。

## Unity 资产迁移台账与预检

| 子命令 | 输入与输出 | 退出码含义 |
| --- | --- | --- |
| snapshot | Assets目录 → 文件/目录GUID、内容/meta哈希、缺失/重复/orphan meta、跨平台路径冲突、空目录和命名候选 | 0无身份问题，1有问题待审，2输入/I/O错误；空目录和疑似哈希名只是候选 |
| compare | 两份该工具快照 → 按GUID关联的移动、增删、内容/meta变化及同路径GUID替换 | 0未变，1有变化或待审问题，2无法可信比较；正常迁移也会返回1，不代表迁移失败 |
| check-plan | 快照与文件级迁移清单 → 源GUID、目标碰撞/父路径、Windows名称和退出理由预检 | 0静态预检通过，1待审，2输入错误；通过不代表可删除或已获授权 |

```sh
python3 "$GREA_ROOT/game-building/scripts/unity_asset_ledger.py" snapshot --assets /path/project/Assets --output /tmp/assets-before.json
python3 "$GREA_ROOT/game-building/scripts/unity_asset_ledger.py" snapshot --assets /path/project/Assets --output /tmp/assets-after.json
python3 "$GREA_ROOT/game-building/scripts/unity_asset_ledger.py" compare --before /tmp/assets-before.json --after /tmp/assets-after.json --output /tmp/assets-delta.json
python3 "$GREA_ROOT/game-building/scripts/unity_asset_ledger.py" check-plan --snapshot /tmp/assets-before.json --plan /tmp/file-moves.json --output /tmp/plan-review.json
```

清单路径相对Assets，不带Assets前缀；GUID应来自快照。例如：

```json
{
  "schema": "unity-file-move-plan-v1",
  "moves": [
    {"from": "UI/old-icon.png", "to": "UI/Sprites/PauseButton.png", "guid": "11111111111111111111111111111111"}
  ],
  "retire": [
    {"path": "Legacy/OldPanel.asset", "guid": "22222222222222222222222222222222", "reason": "Reviewed callers migrated; backup and Editor dependency checks required"}
  ]
}
```

示例GUID不是执行值。目录整体移动须另外通过Editor规划；此预检仅接受文件项。大小写改名、交换路径和已占用目标不自动推断安全执行顺序，应先明确临时路径/阶段。输出必须是已存在父目录中的新文件，不能覆盖输入或写入快照指向的活动Assets。

工具拒绝资产根/后代符号链接，记录排除的常见OS缓存；合法中文不会被标为乱码。不能从哈希名自动生成业务名，也不能凭扩展名判断加密。快照不记录Unity对象name、子资源fileID、GUID动态加载或完整依赖，必须另做Editor回读。目录空不意味着没有图集/生成规则引用。

测试：`python3 "$GREA_ROOT/game-building/scripts/test_unity_asset_ledger.py"`。合成场景覆盖不同目录布局、中文命名、GUID移动/替换、内容与导入器变化、缺失/重复元数据、大小写/Unicode冲突、占位与父路径冲突、符号链接、越界及输出覆盖。实际项目只做只读快照/清单预检，不执行生成、移动、归档或删除。适用流程见[工程重构与资产治理](../skill/references/17-Unity工程重构与资产治理.md)。

### 按迁移清单验收

```sh
python3 "$GREA_ROOT/game-building/scripts/unity_asset_ledger.py" verify-moves --before /tmp/assets-before.json --after /tmp/assets-after.json --plan /tmp/file-moves.json --output /tmp/moves-result.json
```

仅接受非空文件 moves、空 retire；核对每项 GUID、内容和 meta 哈希、旧路径退出、Resources 相对键不变。0 为 planned_files_match，1 为 needs_review，2 为输入/I/O 错误。只核对提供的快照与清单，不读取当前工程；目录退休和清单外改动另用 compare，不验证 Unity 对象名/fileID、类型或运行时加载。

## 图片透明边缘检查

`image_alpha_audit.py` 是 ComfyUI 切图后的只读检查，不负责生成、抠图或修图。Python 3.9+，依赖 Pillow（本次使用 12.2.0）。

```sh
python3 "$GREA_ROOT/game-building/scripts/image_alpha_audit.py" --images /path/button.png /path/icon.png --require-transparency --output /tmp/alpha-result.json
```

输出 JSON 包含尺寸、源格式/模式、SHA256、alpha 包围盒和极值、透明/半透明像素数及不透明边缘统计。完全透明图片始终报问题；整张不透明仅在 require-transparency 下报问题。边缘统计只是诊断，不能判断主体锚点、灰边或按压态视觉是否正确。依赖不足或坏输入返回2；发现问题1；检查通过0。默认最多 20000000 像素，可显式调整 max-pixels；拒绝符号链接与覆盖输出。
