---
name: grea-evolve
description: 对已恢复且可维护的 Unity 工程做有界二次开发，先固定旧工程行为与批准的新设计，隔离产品、存档和构建身份。支持旧UI/UE合同及显式feature/tuning/prototype合同的规划与证据绑定；真实实现和可玩验收按批准范围另行完成。Use for bounded changes with explicit old invariants and approved objectives, not unrestricted gameplay rewriting.
---

# grea-evolve · 已恢复工程的有限二次开发

先读 [生命周期与变更合同](../../shared/01-流程-生命周期与变更合同.md) 和 [共同约束](../../shared/01-流程-共同约束与执行入口.md)，再读 [有限二次开发](references/01-流程-有限二次开发.md)。

- 原工程冻结的规则与持久化不变量、批准新设计的UI/UE维度分别作比较基线；不把新设计当原版一致性。
- 用户授权制作样板时可提出候选设计，按约定审阅；不虚报已批准，不给每页追加审批。
- 换皮主线先按五阶段完成美术及全量替换和Bug修复，再进入约定的UI/UE调优；约30%不是换皮覆盖率，不提前混入美术阶段。独立UI/UE任务保留本期授权范围，不强加一轮美术制作。
- 换皮实施使用 [grea-reskin](../grea-reskin/SKILL.md)；原版未授权变化的缺陷仍由 [grea-parity](../grea-parity/SKILL.md) 按旧依据修复。
- 新feature/tuning/prototype入口提供合同与规划，不能据此声称已实现新玩法或已完成可玩验收。

涉及新功能、调优或原型时按需读[增量设计与版本兼容](references/01-流程-增量设计与版本兼容.md)；配置/存档分析是候选，不直接迁移普通玩家档。
