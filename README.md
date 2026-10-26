# beaver

候选／已有工程 → 可持续开发工程与制品。Python CLI，Unity 使用原生 Editor API。
恢复候选由 monkey 提供；方法、阶段选择和调用规范由 GREA 提供。

本地候选版本：0.1.0。Unity 6000.6.2f1 是首版实证路径；Creator 3.8.8 支持静态工程检查和三方预览，原生执行/构建明确不支持。

```sh
python3 -m venv .private/venv
.private/venv/bin/pip install '.[images]'
.private/venv/bin/beaver version
.private/venv/bin/beaver capabilities
.private/venv/bin/beaver doctor
.private/venv/bin/beaver project inspect --project /absolute/project
```

输出统一 JSON，失败有非零退出码。原生执行需显式现有 Editor 路径，不安装或升级引擎。
首版包含：manifest/GUID三方采用与受保护恢复、显式原生移动、uGUI/TMP窗口与列表、Prefab字段/组件/Sprite绑定、原生导入/PlayMode、严格JSON/DTO、无损PNG压缩、同源macOS构建和制品身份校验。payload工具还提供文件/别名完整性、绑定旧哈希的显式覆盖、独立复制与原子不覆盖晋升。复杂游戏业务由开发Agent实现。

验证使用自有合成工程；大工程预览只读复用既有隔离样本。肥鹅、向僵尸正式工程保持只读。运行和截图中的按钮事件是合成UI事件，未声称物理输入或完整游戏验收。

详见 [唯一计划](docs/PLAN.md)、[CLI 契约](docs/CLI-CONTRACT.md)、[来源](docs/PROVENANCE.md) 和 [验证索引](docs/VALIDATION-v0.1.0.json)。本轮不建立远端、推送、Release或全局安装。
