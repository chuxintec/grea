<!-- 生成副本，勿直接编辑。权威来源：docs/providers/server-go.md；由 scripts/skill_closure.py 维护。 -->

# Go六服示例框架（开发候选）

通用Go执行能力归beaver。模板/生成器/依赖/合同/许可与历史验证已定向冻结交接（GREA 安装目录 `proposals/beaver-execution-handoff.md`），0.3候选07已交付通用Go工具与自有六服/Unity联调证据；GREA现按固定07及08/09身份接入部分候选、协议和计划路由，详见[有限适配](beaver.md#固定03候选07和08的有限适配)。数据库/Docker和Go构建执行未在本轮命名适配中接入，不代表上游未实现。原server_go_project合同和消费者仍未替代；下文是旧有限示例的实际合同，不用新工具证据升级它。

`grea legacy server_go_project --output new-server`只生成，不安装、编译、启动容器或部署。模板在tools/server-go/template，独立虚构Signal奖励业务；六服入口cmd/gateway、chat、server、login、world、billing。内部gRPC/Proto；MySQL独立所有者库/账号，Redis只限流，真实支付Unavailable。详细边界以 [Go技能](../../SKILL.md) 为准。

Go 1.26.2及go.mod/go.sum固定依赖。生成的api/game.pb.go/game_grpc.pb.go由本例IDL和具名protoc插件产生；重新生成使用protoc-gen-go 1.36.12、protoc-gen-go-grpc 1.6.2与系统protoc。编译各入口或统一`go build -o bin/role ./cmd/role`；Docker需`CGO_ENABLED=0 GOOS=linux GOARCH=arm64`或按目标架构设置，不能把macOS二进制放入Linux镜像。

显式准备隔离栈：`python3 stack.py prepare --name grea-<unique-run> --port <unused-loopback-port>`；会在新.local生成仅本栈凭据、MySQL初始化SQL、compose.json及身份。随后`python3 stack.py config/up/status/down`。只允许grea-身份，down仅清理该Compose项目自己的卷和容器。镜像digest在stack.py固定；自有Go镜像按运行名隔离。最大资源约1GiB/1.1CPU，唯一对外端口绑定loopback。源码不含可用凭据，.local不可提交/分发。

这是显式development HTTP/内部私网gRPC样例；入口拒绝非development模式，生产TLS/身份、WSS、渠道验签、owner迁移、outbox/inbox和跨玩家分布式业务尚未实现。它们不是当前样例验证通过的暗示，不能直接对公网开放。

HTTP：POST /v1/login传credential返回sessionId；其余/v1/state、command、chat、order从Authorization Bearer取得会话，不接受body伪造身份。命令含operationId/expectedRevision/action/configVersion。64位数字走ProtoJSON十进制字符串。clients目录给Unity/Cocos适配及恢复语义，自有测试可持久化后重开并同号重试；无真实客户端实测时必须明确标记。

浏览器适配：development网关只允许GREA_BROWSER_ORIGIN声明的精确Origin（默认http://127.0.0.1:7456），支持Authorization/Content-Type预检，其他Origin拒绝。按实际Creator预览Origin配置，不能使用通配符绕过。跨配置版本的历史pending迁移、会话撤销和生产身份兼容窗口尚需产品明确实现，不从本固定版本示例推断完成。
