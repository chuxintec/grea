# beaver

候选／已有工程 → 可持续开发工程与制品。Python CLI，Unity 使用原生 Editor API。
恢复候选由 monkey 提供；阶段选择、方法和调用规范由 GREA 提供。

当前本地版本 **0.5.0**，固定交付基线 **0.3.0**；交付状态、实际消费者证据与限制见 `docs/PLAN.md`，未对外发布。Unity 6000.6.2f1 已在自有样例和肥鹅固定版本的隔离副本实证。Creator 3.8.8 仅支持静态检查与三方预览，原生执行/构建不支持。

```sh
python3 -m venv .private/venv
.private/venv/bin/pip install '.[images]'
.private/venv/bin/beaver version
.private/venv/bin/beaver capabilities
.private/venv/bin/beaver project inspect --project /absolute/project
```

除 `beaver tool <id>` 保持旧 toolkit 原始输出与退出码外，业务命令输出 `beaver-result/1` JSON：0=ok、1=partial、2=failed、3=blocked/not_run。原生执行须显式指定已有 Editor；工具不安装或升级引擎。

v0.2 增加成组计划/执行/受控恢复、限定 Variant、节点与组件操作、滚动/网格/动态列表、安全区和已有方法事件绑定；提供引用图、精确 JSON/C# 加载键迁移、资源替换/移动，以及复用候选的持续调试会话。关键前置条件按内容哈希核验，一次 Editor 执行相关操作组，人工后改禁止覆盖恢复。

v0.1 的 GUID/manifest 三方采用、JSON/DTO、PNG 无损压缩、原生导入/PlayMode、macOS 构建和制品核验仍可调用，固定旧候选与证据保留。运行时 JSON 是唯一数值源；不生成空业务回调或另一套引擎。

验证覆盖实际详情滚动窗口、17 项图鉴、Closet Variant 和资源引用组，正式游戏、Go、账号及普通存档未被操作。截图、合成事件、物理输入与完整游戏业务分别报告；目前物理输入、完整业务、Spine 行为和视觉还原一致性未验收。

见[用法](docs/USAGE-v0.2.md)、[CLI 合同](docs/CLI-CONTRACT.md)、[唯一进度](docs/PLAN.md)、[v0.2 验证索引](docs/VALIDATION-v0.2.0.json)、[来源许可](docs/PROVENANCE.md)。本轮仅本地提交和隔离安装，无远端、推送、Release 或全局安装。


v0.3 将私有工程接入、资源生产、复杂 JSON/C#＋Go 同源读取、Roslyn 语义维护与联合事务接入同一公开 CLI，并提供 Go 六服的协议、迁移、构建及自有 Compose 验证工具。Unity 模块默认使用 `grea-unity-project/1.0.0` 的 Bootstrap/Domain/Gameplay/Presentation/Services；旧五层模板须显式选择兼容 profile。

设置修改使用独立 Editor 重开核验；完整原生 checkpoint 是受控恢复的必要条件。运行能力与实际游戏采用分开记录，v0.3 整版进度以 PLAN 为准。Go 私有 Unity→gateway→MySQL→Unity 链路已实测同请求幂等及重启/缓存丢失，正式服务器与支付不在本轮操作范围。

本版 UI 检查、原生字段/事件接线、明确字段修正与统一诊断见 [v0.5 开发用法](docs/DEVELOPMENT-v0.5.md)；实际验证与正式采用以唯一 PLAN 为准。


## 0.4.0：接收 GREA 执行工具

GREA 2026.10.27 起把 23 个执行工具移交 beaver，工具 ID、参数、报告与退出码不变，用 `beaver tool <id> [args]` 运行（GREA 的 `run-tool` 同 ID 自动委托）。源码在 `src/beaver/toolkit/`，所需 GREA 辅助模块随附于 `toolkit/support/`；运行库见 `toolkit` extra（Pillow、jsonschema）。清单：`beaver tool --help` 或 capabilities 的 `toolkit.grea`。
