# beaver

独立游戏开发 CLI，主开发单写。只写本项目；源工具和正式游戏只读。
Python CLI + Unity 原生 Editor companion；不实现源包恢复解析器。
唯一进度入口 docs/PLAN.md；CLI 公开契约 docs/CLI-CONTRACT.md。
配置以运行时 UTF-8 JSON 为唯一数值源。原生资源用引擎 API 编辑。
默认 inspect/plan；apply 必须绑定计划身份、目标及前置哈希。后续人工修改不能被恢复覆盖。
隔离验证只用本项目 .private 内自有合成工程。不得启动暂停游戏。
本轮仅本地开发、提交和隔离安装；无远端、推送、全局安装或服务变更。
来源及许可记录 docs/SOURCE-INVENTORY.json、docs/PROVENANCE.md；私有资料不进入分发包。
不新增子 Agent；按实际影响验证，状态明确区分静态、原生、Player、视觉及业务。
