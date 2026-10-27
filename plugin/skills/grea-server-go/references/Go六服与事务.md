# 服务端 · Go六服与事务

正式路线为Go：gateway外部HTTPS/JSON或WSS接入，chat聊天，server权威玩法事务，login身份会话，world节点/路由和跨服协调，billing订单与验签后幂等发货。内部统一gRPC/Protobuf；只用MySQL持久化、Redis缓存，Docker部署，不新增MQ/注册中心或其他数据库。每个数据所有者独立库/账号；禁止跨服SQL，协作走RPC。

框架与游戏模块分离。JSON为唯一数值制作源，公开子集派生给Unity/Cocos并带版本/hash，服务端私有字段不下发。ID、revision、金额、时间等64位值在JSON中用十进制字符串，货币用整数/固定单位；未知、null与缺省语义有协议说明，客户端不依赖表行顺序。坏配置拒绝，不静默回退旧表。

所有写命令有权限域、稳定操作号、内容摘要、expected revision和配置版本；相同ID相同内容返回持久回执，不同内容拒绝。事务中锁定/CAS权威状态、业务唯一键与命令回执，commit确认后才能成功。提交超时可能已发生，返回Unavailable/未知并以同号查询或重试，不更换ID或自动改expected revision。Redis不能是唯一资产账或支付回执。跨服任务需要持久outbox/inbox及幂等RPC；未实现不得用内存队列伪装可靠交付。

配置版本由内容哈希派生，不手工维护一个长期不变的版本号；存档记录 schema 版本并提供逐级迁移函数，配置变化既能被检出，也不会让旧档一律失效。大单表按模块拆分，CI/测试校验 schema 与 hash 一致。

客户端不要每次拖动/合成都同步等待服务器并锁输入。高频、无经济后果的操作本地确定性执行并记命令日志；交单、领奖、建造、付费等经济事件或每 N 步批量提交，由服务端用同一规则引擎回放校验，不一致以服务器快照回滚。暂不迁移规则时至少做乐观更新。

六服是逻辑边界：开发期可合并部署或复用同一栈，正式部署再按需拆分；空服（如尚无业务的 chat/billing）保持显式 Unavailable，不为它们每次全量升级八容器。部署使用声明式 compose 与版本化迁移，不依赖一次性脚本序列。

运行底座具备显式secret引用、有限body/队列/并发、deadline/取消、稳定错误、健康状态、退出边界；日志不带token或SQL凭据。鉴权上下文由login校验，路由不授予写权限。生产内部TLS、外部HTTPS/WSS、会话/节点隔离及密钥轮换按实际部署实现，模板未实现项不是自动批准使用不安全降级。

当前 `server_go_project --output new-server` 提供有限development样例：开发allowlist凭据→MySQL会话→gateway→world路由→server一次性starter奖励与事务回执；chat仅已认证主体的有界消息，billing只创建PENDING_PROVIDER订单、支付/发货Unavailable。六角色各自进程，五个所有者MySQL库，Redis网关限流；非产品代码。单节点固定路由不是owner_epoch迁移/HA，不含持久跨服任务、真实渠道和生产运营。普通RPC/HTTP成功仍需检查业务code。

Unity/Cocos Services适配共用HTTP JSON；Gameplay先持久pending后发送，异常保留同号内容，销毁/会话切换拒绝迟到结果。客户端渲染失败不重发业务。接口示例不代替各引擎的真实网络/存档验收。

按 [Go模板说明](shared/server-go.md) 在独立栈验证。容器名/网络/卷/端口与产品分离，只清理本次身份；不能重启现有服务或部署公网。实际MySQL提交/回读、同号重试和未知结果测试与只编译/compose配置分别报告。
