# 2026-10-25 中文路径拼音化与配置 JSON

用户要求更新 monkey 中文文件命名并找回配置 JSON。本轮实现保留 Claude/接手工作树；未发布、未改源游戏工程。

## 实现

- 共享命名器将汉字转换为无声调拼音，再应用已有 PascalCase/snake_case/kebab-case；pypinyin 固定 0.55.0。同音、大小写冲突保留稳定身份消歧，源中文名称保留在映射。
- 原件副本的路径、解码证据、代码草稿与 Spine 闭包接入命名；Spine atlas 仅更新页文件声明，不改 region/attachment/骨骼内部标识。原始输入缓存保持源布局和字节。
- 缺表原因：样例项目主要配置为 `cc.BufferAsset` 的 BON 二进制，旧版本只留 `.bin`。新增 BON tagged-le-v1 静态适配器，必须同时有明确 Config 资产索引和已识别 decoder 来源证据。严格检查完整消费、字符串引用、重复键、非有限数和资源预算；Binary/Date 等类型明确 needs_adapter，不猜测转换。
- 按每个顶层键生成一份 UTF-8 JSON；索引保存原顶层键、sourceId、源/目标 SHA256 和 JSON Pointer，可重建原对象。基础表、地区覆盖、语言数据不混合，不把来源包装字段塞入正式表。
- 配置入口：目标工程 `Docs/CONFIGURATION.md`；机器索引 `Analysis/Mappings/config.json`；主配置 `Assets/Game/Content/Config/Base/`。

## 离线真实输入验证

- 新候选：`outputs/sample-game-unity6-pinyin/UnityProject`。
- 17,201 个输入、884,709,704 字节：源文件与输出保留原件逐项一致；8,952 图片有效；914 草稿唯一且存在；静态验证 pass、0 诊断。
- 10 个 BON 配置包均完整解码，导出 528 个 JSON；其中基础配置 236，语言 258，地区覆盖 29，地图/鹅与装饰数据 5。韩国覆盖原本为空对象，索引明确记 0 表。
- 用既有只读独立 Reader 解析相同原件，与全部 JSON 按索引重建的对象比较：所有键、值、ID 和结构相等。JSON 内容中的中文原样保留。
- 新目标工程文件及目录中文路径 0；1,776 套 Spine 闭包页图引用有效。
- 与上一离线候选按 GUID 对比：600 路径迁移、8,775 保持、0 旧资产消失、新增 528 配置资产。
- 296 项测试通过，包括同音冲突、Spine 中文页图及复用、JSON 精度、异常数据与预算，以及两种输出格式。`pip check` 与 `git diff --check` 通过。

## Unity 6 原生验证

在自有新副本 `outputs/sample-game-unity6-pinyin-native/UnityProject` 使用 6000.6.2f1；已完成。子进程 exit 0 并回收，静态 pass、Editor partial、验证器 0 诊断；1,694 源 Prefab / 24,784 节点 / 8,952 Sprite / 416 原生动画回读，Missing Script 0，保存重开与可编辑往返通过。528 份配置均有 TextScriptImporter 导入开始/完成证据，导入后字节哈希未变。Editor partial 继续反映既有源限制，非完整玩法验收。

## 边界

本轮证明资源导出、静态数据语义和文件引用。新配置没有自动接入样例项目既有游戏的运行时数据消费者；主配置与地区覆盖如何应用仍由业务层明确选择。源缺失引用 1,521 项、既有源限制与 Player/玩法/视觉未验证状态继续保留。

当前真实样例项目输出中文路径已清零；Unity 来源的 Resources 动态键、程序集/脚本类型身份及部分第三方闭包尚有保名约束，不能脱离消费者强行重命名，也不据此宣称所有引擎/格式均已支持。

完整私有证据：`.private/pinyin-config-20261025/`（资源校验、配置逐值对比、同 GUID 迁移、测试日志、原生窗口与执行回执）。

## 旧输出清理

新版通过后，删除已替代的 outputs/sample-game-unity6、outputs/sample-game-unity6-native-02。删除前核对旧候选生成文件哈希及旧原生目录完成后无新增修改，关键验收与清单移存 .private/pinyin-config-20261025/retired/。共删除 201,809 文件，实际可用空间增加 15.26 GiB；新候选与原生回执哈希复核一致。outputs 仅保留本轮离线/原生两个阶段与 LATEST.md。
