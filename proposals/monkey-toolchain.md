# monkey 工具链接入与重构


> 2026-10-26 职责更新：当前架构为 GREA Skill＋monkey 恢复＋beaver 工程执行，替代旧两产品归属。本文保存 monkey 接入成果与限制，不是第二进度表；当前工作状态统一见[生命周期路线](lifecycle-roadmap.md)，工具移交见[beaver交接](beaver-execution-handoff.md)。已装 dev2 不变，当前本地 dev4 未发布；dev3完整包证据作为历史基线复用。
范围：以实际安装的 monkey 0.4.0 为固定接口，完成 GREA 主路编排、旧接口兼容、文档和测试。不改游戏原工程，不复制 monkey 转换器。

- [x] 原生读取开发会话，核最新版本/已安装入口与能力。
- [x] 抽取 identity / package / slice / handoff，保留 monkey_bridge ID 与函数导入。
- [x] monkey_pipeline：pin → plan → run → audit，支持 Cocos 全集、Unity prepare/export/convert 以及布局预览。
- [x] 新旧 manifest 兼容与来源、工具、文件身份验证。
- [x] 工作流、Schema、Skill、工具目录统一。
- [x] 最终测试、隔离制品验证与验收记录。

只读计划不是执行，字节审计不是原生/玩法验收。原生阶段需要真实引擎证据；新流程不触发游戏重导或自动安装/发布。

验收入口：[本轮记录](../validation/development/monkey-toolchain-20261026.json)。

## 本机就绪与技能调用补齐（dev2）

- [x] 四个恢复/取证子技能明确 discover→ensure→plan→run→audit→handoff。
- [x] 本机安装发现、实际导入位置确认、持久 lock 与就绪检查；显式配置优先。
- [x] 缺失时从官方 GitHub 最新稳定 Release 安装；SHA/元数据核验、API 限流回退、独立 Python、版本不兼容阻断。
- [x] 358 项回归（344 pass / 14 skip）与两条真实安装/复用路径。
- [x] 最终插件安装及当前会话实际加载新版（2026.10.26.dev2，真实 MCP check ready=true）。

[就绪验收](../validation/development/monkey-readiness-20261026.json)分别记录安装、独立 MCP 与当前会话状态。

当前本地集成已接收beaver最终0.1.0并复用已有GREA调用/构建/Player证据，进度见生命周期路线；稳定monkey0.4与显式0.5开发查询分开，不因等待整版0.5停住已批准集成。旧恢复侧7项全部继续保留兼容，不作无证据退休。
