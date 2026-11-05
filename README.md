# monkey

当前开发统一在 **0.8.0.dev39** 单线，包含 Unity 来源恢复、Cocos 来源转 Unity 静态 Prefab、
Toggle 空配置桥接、显式 CoreText 静态回退字体及严格静态引用恢复。
新增导出、开发与验收统一以 Unity 为目标；Creator/Cocos 目标保留既有显式兼容入口及历史证据，暂停专项修复和验收。
monkey 由 GREA 统一调度和分发；旧 0.7.0 发布与固定消费者只作兼容保留，
不再继续 0.7 开发。字体入口见 [系统字体工具](docs/SOURCE-SYSTEM-FONTS.md)，
Unity 来源边界见 [Prefab 恢复](docs/UNITY-PREFAB-RECOVERY.md)。

已有 Cocos→Unity plan 可通过 [静态组件续接](docs/STATIC-PREFAB-CONTINUATION.md) 复用冻结产物，按通用组件族补齐静态身份与引用（含全源 Mask、受控裁剪和未激活文字采样证据）；准备、原生回读和视觉验收分别报告。

[MIT License](LICENSE) · [Source](https://github.com/chuxintec/monkey) · [v0.7.0 Release](https://github.com/chuxintec/monkey/releases/tag/v0.7.0)

monkey 是 Python 驱动的原包恢复命令行工具，将已授权取得的包体、资源和源码证据整理为独立候选工程。正式版本 **0.7.0** 在既有 C# 恢复及七个来源侧工具上加入 Cocos 来源静态 Prefab、保存选取与依赖声明流程；工程规范为 [`monkey-project/2.0.0`](docs/PROJECT-SPEC.md)。

Unity 目标使用 Unity 6，采用 `Assets/Game/Content/<Type>/<Module>/`；Creator 资源目标使用 `assets/resources/<Type>/<Module>/`。图片统一放在 Textures，保留 Sprite 导入设置与引用。中文输出名转拼音，保留源名映射及冲突消歧。原始数值配置以 UTF-8 JSON 为维护源。

## 0.7.0 的主要能力

- Cocos 来源的静态 Prefab 恢复支持有据字段、资源、布局、固定状态和双目标保存重开；未知业务、动画曲线和不可用行为仍保留具体缺口。
- `freeze-native-selection` 按冻结源与原生读回选取依赖；`audit-native-code-dependencies` 补充 C# 证明和 SDK 声明，保留未知 MonoScript 表为 `not_run`。
- 字体补齐、Spine 静态资源和运行时展示均按精确源身份与代表样本验证；引擎、字体、SDK、完整业务和第三方许可不随版本号自动保证。

- 包级 `convert` 可生成全部已取得 JS 方法的 C# 初稿，并保留资源、JSON、Scene/Prefab、源码映射及具体未恢复项。支持核验后复用冻结资源候选，避免重复解码。
- 原生架构流程按 Bootstrap/Domain/Gameplay/Presentation/Services 组织完整模块，支持单进程有界生成、断点接续、只读重分类、哈希固定的候选修订和显式本地测试 JSON。
- 大工程解析预算、阶段复用、资源身份、引用闭包和生成所有权保留明确边界。未知方法、缺失资源与不可编译初稿不会变成假成功。
- `monkey tool <id> [args...]` 接收 GREA 的来源侧工具，保持 ID、参数、报告与退出码。GREA 可通过固定版本 provider 调用；人工工程的采用和建设由 beaver 负责。

支持范围按来源格式逐步实现，参见[支持矩阵](docs/SUPPORT-MATRIX.md)。Cocos、Unity、Egret 等已有不同范围的 reader；原图 gallery 不代表节点或业务已恢复。恢复候选、原生导入、编译、玩法及视觉验收分别记录。

## 安装与使用

需要 Python 3.11+。从正式 Release 下载 wheel 和 `SHA256SUMS`，核对校验值后安装到独立环境：

```sh
python3 -m venv .monkey-env
.monkey-env/bin/python -m pip install monkey_native-0.7.0-py3-none-any.whl
.monkey-env/bin/monkey --version
.monkey-env/bin/monkey capabilities
.monkey-env/bin/monkey convert --help
.monkey-env/bin/monkey tool --help
```

Windows 使用环境目录下的 `Scripts/python.exe` 和 `Scripts/monkey.exe`。安装仅提供工具，不包含游戏原包、引擎或私有素材。现有 GREA 集成应使用对应正式版本、精确下载 SHA 和 producer 合同。

完整调用方式见[用法](docs/USAGE.md)、[C# 初稿](docs/CODE-DRAFTS.md)、[架构恢复](docs/CODE-ARCHITECTURE.md)、[候选修订](docs/CODE-ARCHITECTURE-REVISION.md)及[正式发布说明](docs/RELEASE-v0.7.0.md)。

## 验证与限制

历史 0.7.0 稳定源码来自已固定的 0.7.0.dev9。下述历史证据不等于当前 0.8.0 开发版全部通过；实际使用须固定源码/制品 SHA 并单独检查原生、视觉和 Player 证据，不以工具版本或安装成功推断游戏完成。

一个代表性私有来源的完整候选曾以 1,555 份 C#、五个真实程序集完成编译：0 error、3,249 warning。受影响原生核心验证覆盖 348 格、24 个 Sprite 身份、生产点击、持久化重开及视口外输入拒绝。该历史证据不作为发行包内的公开复现素材，也不等于完整游戏恢复。原始证据保留在本地私有档案，公开摘要见版本说明。

生成代码仍可能存在语法、类型、API 和业务缺口。部分模块仍为 partial/unreviewed，原厂认证、远端服务、完整玩法、物理输入、视觉对照与 Player 构建不能据此宣称通过。原生验证还保留两条 Editor Search 启动异常。不得把未知服务器行为实现为假登录、假奖励或假支付。

## 许可与来源

monkey 自有代码采用 [MIT License](LICENSE)。第三方代码与必要版权声明见 [THIRD-PARTY-NOTICES](THIRD-PARTY-NOTICES.md)。游戏原包、素材、引擎及第三方工具不属于本项目的开源授权范围，不随源码发行或安装包提供。

旧原生事务的独立回执与只读复验入口见 [Native execution recovery](docs/NATIVE-EXECUTION-RECOVERY.md)。恢复回执不改写原日志，也不代表候选验收通过。
