---
name: grea-evolve
description: 对已恢复且可维护的 Unity 工程做有界二次开发，先固定旧工程行为与批准的新设计，隔离产品、存档和构建身份。当前仅支持 UI/UE 范围：布局、导航、反馈、可读性及换皮，玩法、随机、结算和持久化语义保持不变。Use for bounded UI/UX evolution of a recovered Unity project, not a new game framework or an unrestricted gameplay rewrite.
---

# grea-evolve · 已恢复工程的有限二次开发

先读 [共同约束](../../shared/01-流程-共同约束与执行入口.md)，再读 [有限二次开发](references/01-流程-有限二次开发.md)。

- 原工程冻结的规则与持久化不变量、批准新设计的UI/UE维度分别作比较基线；不把新设计当原版一致性。
- 用户授权制作样板时可提出候选设计，按约定审阅；不虚报已批准，不给每页追加审批。
- 换皮实施使用 [grea-reskin](../grea-reskin/SKILL.md)；原版未授权变化的缺陷仍由 [grea-parity](../grea-parity/SKILL.md) 按旧依据修复。
- 当前只证明 UI/UE 工具与流程，不自动支持新战斗规则、经济系统、完整商业化或无限制原创工程。
