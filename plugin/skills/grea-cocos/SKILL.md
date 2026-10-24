---
name: grea-cocos
description: 将已授权游戏恢复、移植或构建为Cocos Creator目标工程，提供3.8.8五层模板、基础序列化转换子集、资源身份和浏览器运行流程。尊重显式Cocos目标；不把源引擎包装成Unity，也不声称全版本自动转换。
---

# grea-cocos · Creator目标

读 [工程与迁移](references/05-Cocos-工程与迁移.md)。源版本和目标版本分别记录；当前目标3.8.8，浏览器优先。`cocos_project`创建自有五层示例，`cocos_convert`仅转换明确支持的基础Scene/Prefab；输入原件只读，输出全新，未支持项不静默丢弃。

Unity专属asmdef/uGUI/UPM规则不套给Creator；不改官方引擎，不默认安装Funplay。调研不等于开发授权；需要Go后端时见 [grea-server-go](../grea-server-go/SKILL.md)。


完整初版导出与接续边界遵循[全量初版工程与协作](../../shared/01-流程-全量初版工程与协作.md)。批量转换由固定monkey负责，GREA核交接并编排后续开发；lookup/静态候选不等于原生初版。已有工程的局部修复不无条件重导。
