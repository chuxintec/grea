---
name: grea-delivery
description: 恢复或转换工程的构建与交付：macOS/Windows 构建、制品身份与 Build/current 晋升、安装包与单文件交付、试玩视频、桌面窗口与 DPI 验收，以及 Unity Editor 连接、编译重载与长任务执行。Use when building, packaging, previewing or releasing a recovered Unity game, or when driving the Unity Editor for long tasks.
---

# GREA · 构建、交付与 Editor 执行

先读 [共同约束与执行入口](../grea/references/共同约束与执行入口.md)。

| 任务 | 参考 |
| --- | --- |
| 构建、制品身份、输出目录、current 晋升、安装与回滚 | [游戏构建与版本发布](references/游戏构建与版本发布.md) |
| 新项目窗口默认、尺寸口径、DPI 与比例 | [桌面窗口与显示适配](references/Unity桌面窗口与显示适配.md) |
| Editor 发现、只读往返、编辑与长任务 | [编辑器连接与任务执行](references/Unity编辑器连接与任务执行.md) |
| 第三方包许可证、原游戏素材范围、源引擎代码 | [许可证与再分发](references/许可证与再分发.md) |

- 未指定目标平台时默认 macOS。
- 构建、封装和实机运行分别验收。
- 他人交付或历史版本重建，按需读[研发交接资料核验](../grea-evidence/references/研发交接资料核验.md)：源码/已验Player分开，宿主构建与完整资源物化分别绑定同一候选；历史报告不改写成本机实测。
- 跨引擎项目在构建前运行禁止项守卫，交付说明单列 [原生可维护门](../grea/references/测试与结果交付.md#原生可维护性跨引擎转换) 的结果；构建成功不代表该门通过。
- 发布前按 [许可证与再分发](references/许可证与再分发.md) 核对第三方包、原游戏素材和源引擎代码。
- 只进入本次已授权的预览、安装或发布环节。

衍生工程按 `grea-evolve` 技能 分开来源与新产品/存档/构建身份，原验收和新设计验收不互相替代；交付时区分美术/Spine制作、Unity接入和Player实测状态，可玩构建不等于样板风格批准，约定UI/UE调优在全量换皮与Bug修复之后；本模式不新增发布权限。

生命周期增量版本需一起给源码、配置、制品、存档/协议兼容和已知缺口；本地[配置与发行预览](../grea/references/providers/lifecycle-analysis.md)不执行上传或上线，也不证明渠道支持。


完整初版导出与接续边界遵循[全量初版工程与协作](../grea/references/全量初版工程与协作.md)。批量转换由固定monkey负责，GREA核交接并编排后续开发；lookup/静态候选不等于原生初版。已有工程的局部修复不无条件重导。

## 执行工具与边界

beaver 提供工程测试、构建与制品操作，GREA 定义验收与发布方法；渠道发布仍遵本次权限。 完整执行链的必选依赖、固定绑定和过渡例外见[monkey与beaver调用](../grea/references/monkey与beaver调用.md)，仅在准备执行或依赖变化时加载。
