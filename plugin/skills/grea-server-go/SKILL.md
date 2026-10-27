---
name: grea-server-go
description: 为已获准的游戏定义自有后端边界并生成或开发Go六服框架，使用gRPC/Protobuf、MySQL、Redis和Docker，包含持久幂等命令及Unity/Cocos共用协议。不是恢复未知原厂服务，也不自动批准生产部署或支付接入。
---

# GREA · Go游戏服务端

读 [六服与事务](references/Go六服与事务.md)。`server_go_project`创建自有虚构示例；框架/游戏模块分离，正式JSON唯一制作源。内部六服RPC，客户端仅经gateway；MySQL是持久事实，Redis只缓存/限流。

工具生成、编译、真实六服/数据库贯通与生产就绪分别记录。未接支付返回Unavailable；不假成功，不复用产品数据库或服务。模板的development模式不支持生产身份/TLS部署，不把样例当完整商业后端。

## 执行工具与边界

通用Go工程/模块生成、协议/配置类型、构建和Docker执行由 beaver 维护。GREA现对其固定0.3候选07及08/09提供有限的server候选/协议/迁移/Compose计划及toolchain路由，具体范围见[beaver接入](../grea/references/providers/beaver.md#固定03候选07和08的有限适配)；未接入的构建/数据库/Docker操作不自动透传。工具自有六服/Unity联调证据不等于正式项目采用。`server_go_project`旧ID和消费者继续使用原合同，替代验收前不删除模板或假转发。具体六服业务留项目，不调用 monkey 恢复未知服务端。完整执行链的必选依赖、固定绑定和过渡例外见[monkey与beaver调用](../grea/references/monkey与beaver调用.md)，仅在准备执行或依赖变化时加载。

从恢复交接接入后端前，按需读[原协议与本地消息](../grea-evidence/references/研发交接资料核验.md#原协议与本地消息)。本地JSON DTO闭包不等于原服二进制协议；对方离线赠送/掉落政策不自动继承，不因收到宿主代码替换现有共享Go服务。
