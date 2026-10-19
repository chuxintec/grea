# v2026.10.19 成组维护与正式发布

基线：v2026.10.17；本包不改游戏工程，不升级全局插件。目标是修复实际工具容量缺陷，精化已有规范与用户入口，沿现有双平台发布流程发布正式版。

| 工作组 | 本地实施／远端判定入口 | 证据与下一门槛 |
| --- | --- | --- |
| DLL 容量与兼容 | 已实现，定向测试通过 | 256统一上限；完整集合/哈希/字节/依赖/不执行IL保留；原生CI继续验证 |
| 审计与生命周期规范 | 已修订，维护者场景走查通过 | 有限FIFO/源机制/Editor候选/实际Player分层，销毁顺序与普通退出 |
| 制作、性能、交付与批次 | 已补入原主题 | 不新建竞争框架，不新增游戏实机门 |
| README与升级说明 | 已重写，链接/准确命令已核对 | 功能、技能、CLI/MCP、双平台、供应方及限制 |
| 迁移兼容 | 仅通用同步器进入产品 | tools/grea与直接布局回归；本机路径说明及私有材料留本地 |
| 开发分支CI/发布预演 | 由分支远端记录判定 | 通过后合并main |
| main CI/发布预演 | 由main远端记录判定 | 对实际集成提交重跑；通过后才打正式标签 |
| 标签Release/下载回读 | 由正式发布记录判定 | 双平台、non-draft/non-prerelease、精确附件及实际下载身份校验 |

验证记录见 [本地维护检查点](../../validation/releases/2026-10-19-maintenance.json)。远端状态与最终源码身份由 [Source checks](https://github.com/chuxintec/grea/actions/workflows/ci.yml)、[Release流程](https://github.com/chuxintec/grea/actions/workflows/release.yml) 和 [v2026.10.19](https://github.com/chuxintec/grea/releases/tag/v2026.10.19) 的 manifest/验收报告提供；待执行项不预填通过。本表固定执行顺序与本地准备检查点；后续远端各门的状态以这些运行记录和最终附件为唯一回读入口，不为嵌入最终SHA循环制造新发布提交。
