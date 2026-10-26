# beaver

独立游戏开发 CLI，主开发单写。只写本项目；源工具和正式游戏只读。
Python CLI + Unity 原生 Editor companion；不实现源包恢复解析器。
唯一进度入口 docs/PLAN.md；CLI 公开契约 docs/CLI-CONTRACT.md。
配置以运行时 UTF-8 JSON 为唯一数值源。原生资源用引擎 API 编辑。
默认 inspect/plan；apply 必须绑定计划身份、目标及前置哈希。后续人工修改不能被恢复覆盖。
v0.2隔离验证允许本项目.private内自有合成工程及肥鹅固定已交付版本的冻结副本；本轮人类授权human01a1770a-55b2-7a10-9be1-2cf9642dda4b已原生核验。正式肥鹅、v1.2在途修改、Go、普通存档及其他工具源码只读。副本禁止真实账号/后端；Player须证明独立身份/离线存档边界，不能安全隔离则仅做Editor/自有样例验证并报告缺口。不得启动暂停游戏。
本轮仅本地开发、提交和隔离安装；无远端、推送、全局安装或服务变更。
v0.1基线b67a164及候选保持。v0.2在codex/beaver-v0.2分支开发，整版收口；普通进度只写docs/PLAN.md，不逐功能向总监求确认。
来源及许可记录 docs/SOURCE-INVENTORY.json、docs/PROVENANCE.md；私有资料不进入分发包。
执行[通用模块开发者规范](/Users/wangmeng/Documents/Manager/standards/MODULE-DEVELOPERS.md)；已原生核验human01a1770e-af1d-7510-b494-867958dddf0e允许模块子Agent。主开发单写公共CLI/事务/Schema/Editor，模块限登记文件；动态0～3为常用，实际平台容量优先，无递归派生。按实际影响验证，状态明确区分静态、原生、Player、视觉及业务。
