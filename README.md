# grea · 依据证据恢复 Unity 游戏

grea 为已发布游戏恢复与原生 Unity 转换提供统一 CLI、stdio MCP 和 8 个 Agent 技能。它将来源、资源、规则、候选与验收身份连接起来；取证成功不等于可玩恢复。

- 核心能力：包体/资源清单、Cocos 有限解析、类型化配置预检、轨迹与表现检查、Case/revision、Unity 检查及受控生成。
- Unity 资产：Foundation/uGUI/Editor 包、原生 UI 配方、两个自有战斗/益智消费者。复杂品类系统保持候选。
- 完整插件：macOS arm64 已有正式版；Windows x64 在本分支实现与原生 CI 验收。桌面、Editor/Player、隔离机制分别报告。

从 [安装与平台](docs/安装与平台.md)选择完整插件、源码或纯文档包；按 [使用指南](docs/使用指南.md)执行第一次工具调用。

| 入口 | 用途 |
| --- | --- |
| [文档导航](docs/README.md) | 六份核心说明与必要专项契约 |
| [TOOLS](TOOLS.md) / [registry](registry.json) | 当前 ID、别名、依赖与统一调用 |
| [grea 技能](plugin/skills/grea/SKILL.md) | 恢复模式路由及验收规范 |
| [验证索引](validation/README.md) | 当前与历史报告，各自限定版本和范围 |
| [第三方说明](THIRD_PARTY.md) | 来源、许可及可选供应方 |
| [贡献](CONTRIBUTING.md) | 开发、测试和提交 |

```sh
uv sync --frozen
./bin/grea session
```

Windows 源码入口为 `bin\grea.cmd session`；完整插件自带解释器，不需要先执行 uv。能力存在、原生客户端发现、真实工具运行与游戏验收分别核验。游戏原工程和私人运行证据不进入本仓库。

正式版本通过原生 CI 与双平台插件验收后发布；Windows 实机范围见验证索引。[MIT](LICENSE)。
