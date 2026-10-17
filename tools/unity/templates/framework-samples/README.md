# 两种独立的五层消费者

这些是 grea 自有合成示例，不是已恢复游戏或通用玩法框架。公共包为 Foundation 0.2.1、uGUI/Editor 0.3.0；初始焦点和弹窗内导航显式设置，避免命令临时禁用丢失键盘选择或自动导航跳到背景。两个示例没有互相引用，也没有复制公共包代码。Counter 旧配方仍保持默认入口。

| 示例 | Domain / Gameplay | Services | Presentation / Bootstrap |
| --- | --- | --- | --- |
| numeric-combat | 进入、确定性伤害、暂停、取消、升级；完成后持久化待领奖，再领取一次 | Progress 格式和 ISaveStore 适配；先写成功再提交内存 | 显式按钮/状态/弹窗绑定；单场景装配 |
| grid-puzzle | 3×3 滑块相邻判定、选择/取消、移动、重置、完成一次 | Board 格式和 ISaveStore 适配；保存失败不提交棋盘 | 九格按钮与同一套弹窗/命令组件；单场景装配 |

Domain 不依赖 Unity；Gameplay 仅引用自己的 Domain 和端口；Services/Presentation 实现用例接入，Bootstrap 决定提供方。Editor 是项目自有的一次性制作工具，不进入 Player。Tests 受 `UNITY_INCLUDE_TESTS` 约束。

## 新建与运行

从 grea 仓库根执行，目标目录必须不存在，不用真实游戏工程作输出。两个命令的示例选择与命名空间需要对应：

```sh
python3 scripts/testing/prepare-unity-framework.py --sample numeric-combat --output .private/sample-battle-new
unity run .private/sample-battle-new --timeout 240 --format json -- -nographics -executeMethod Numeric.Editor.SampleBuilder.Seed
unity test .private/sample-battle-new --mode EditMode --output /absolute/new-evidence/editmode.xml --timeout 240 --format json
unity test .private/sample-battle-new --mode PlayMode --output /absolute/new-evidence/playmode.xml --timeout 240 --format json
python3 scripts/testing/build-framework-sample.py --source .private/sample-battle-new --work .private/sample-battle-build-new --output /absolute/new-build/MicroBattle.app
```

益智示例使用 `--sample grid-puzzle` 与 `Puzzle.Editor.SampleBuilder.Seed`；构建包装器从 marker 选择对应 Build。需要 Unity 6000.6.2f1、现有许可与官方包恢复能力；不加 `--allow-install`。准备入口只复制源码，不启动 Unity；Seed 通过 Editor API 创建 Prefab、Scene 和真实 meta，Build 使用已制作资源。官方 URP 会回写预过滤/Volume/全局设置缓存，因此包装器复制到全新工作副本再调用 Build，源 Assets 逐文件保持不变，Unity 缓存写入只发生在构建副本。不要直接在维护源目录调用底层 SampleBuilder.Build。测试输出和构建目录应预先选择新的隔离位置。

三个共享 Prefab 的权威是 `Grea.Editor.ProjectGenerator` 配方（0.1.2）。示例 Builder 在新的带标记工程消费这些资源，再通过显式字段建立项目业务绑定；示例采用单场景入口，生成的通用双场景 seed 不纳入示例 Build。`Assets/SampleView.prefab` 是该示例制作的可编辑快照，PlayMode 测试实例化它。示例制作完成后进入项目所有权，不在既有修改上反复 Seed。通用生成器的 journal 拒绝覆盖人工修改。

## 操作与存档

数值战斗：START → ATTACK（三次初始伤害可胜）→ CLAIM REWARD；也可 PAUSE → CLOSE / RESUME，或 RETURN TO MENU 取消未完成战斗。菜单 UPGRADE 花费 5 币；新局重新取当前等级。待领奖状态阻止开始新局，退出重开后仍可领取；重复领取不再写档。此示例没有自动战斗、属性/Buff、背包、广告或商业数值。

益智：点击编号格选择，再 MOVE SELECTED。初态先移动 5，再移动 6 即完成；选择 1 后移动应被拒绝。CANCEL SELECT 只取消选择；RESET 弹窗关闭即取消，CONFIRM RESET 保存重置，保留累计完成数。合法移动成功保存后才替换当前棋盘，非法操作不保存。

正常启动使用每个应用自己的 `Application.persistentDataPath`，分别进入 `numeric-combat-player` 或 `grid-puzzle-player`。QA 必须同时提供 `--grea-qa --grea-qa-root /absolute/new-qa-root`，否则明确失败。QA 只进入对应 `*-qa` 子目录，并显示 FAIL NEXT SAVE，用于下一次**确实需要保存**的操作失败注入。普通启动不显示该按钮。路径不得指向游戏原工程或真实玩家目录。

损坏/未知版本在启动显示 LOAD ERROR，保留原件，不自动清档或调用 Recover。示例只演示单写者、本地小档；崩溃断电、多进程与多端同步不在承诺中。状态日志用于回读，不依赖命令文件、录制、IPC 或其他应用运行。

## 修改与恢复

改规则到各自 Domain/Gameplay；改存档格式到 Services，并显式定义版本兼容；改界面到 Presentation 和 Editor 制作工具；改装配到 Bootstrap。美术可通过原生 Prefab/Inspector 修改文字、字号、颜色、大小、图标、视觉和内容槽，保留组件显式引用。

独立恢复只复制 `Assets/`、`Packages/`、`ProjectSettings/` 与该示例 marker/制作回执；不复制 Library、Temp、Logs、构建目录或用户存档。恢复后按 lock 导入、测试、构建；不依赖 grea 源码目录或外部软链接。制作源码和导入后的资产身份分别记录，构建前后 Assets 必须一致。

当前实际通过范围见 [本轮验收](../../../../validation/releases/2026-10-16-unity-framework-extraction.json)。自动 onClick/接口测试不等于 OS 输入；Editor、Player、实际输入和未验平台分开记录。没有证据的能力保持 `not_run`。

两个示例按纵向参考分辨率编排；CanvasScaler 使用 Expand，在宽/矮窗口中保留最小设计空间，控件不会因纵向压缩而重叠。多视口原生几何测试不等于 OS 鼠标或移动设备验收；实测边界见验收 JSON 的 resizeFollowUp。
