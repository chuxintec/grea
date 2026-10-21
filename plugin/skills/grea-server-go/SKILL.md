---
name: grea-server-go
description: 为已获准的游戏定义自有后端边界并生成或开发Go六服框架，使用gRPC/Protobuf、MySQL、Redis和Docker，包含持久幂等命令及Unity/Cocos共用协议。不是恢复未知原厂服务，也不自动批准生产部署或支付接入。
---

# grea-server-go · Go游戏服务端

读 [六服与事务](references/11-服务端-Go六服与事务.md)。`server_go_project`创建自有虚构示例；框架/游戏模块分离，正式JSON唯一制作源。内部六服RPC，客户端仅经gateway；MySQL是持久事实，Redis只缓存/限流。

工具生成、编译、真实六服/数据库贯通与生产就绪分别记录。未接支付返回Unavailable；不假成功，不复用产品数据库或服务。模板的development模式不支持生产身份/TLS部署，不把样例当完整商业后端。
