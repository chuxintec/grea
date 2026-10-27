# Go六服示例框架工具

当前 GREA 保留工具 ID `server_go_project` 与既有生成合同；Beaver 同名接收能力的等价性尚未核验，不能称消费者已切换。调用前按 registry/`describe-tool` 核对实际提供方和参数。该工具只生成源码候选，不安装、编译、启动容器或部署。以下记录的是此 GREA 工具的实际能力。

`grea legacy server_go_project --output new-server` 写入全新目录。模板位于 `tools/server-go/template`，使用虚构 Signal 奖励业务；六个入口为 gateway、chat、server、login、world、billing。它不包含真实支付；完整服务边界以[Go六服与事务](Go六服与事务.md)为准。

Go 1.26.2及go.mod/go.sum固定依赖。生成的api/game.pb.go/game_grpc.pb.go由本例IDL和具名protoc插件产生；重新生成使用protoc-gen-go 1.36.12、protoc-gen-go-grpc 1.6.2与系统protoc。编译各入口或统一`go build -o bin/role ./cmd/role`；Docker需`CGO_ENABLED=0 GOOS=linux GOARCH=arm64`或按目标架构设置，不能把macOS二进制放入Linux镜像。

显式准备隔离栈：`python3 stack.py prepare --name grea-<unique-run> --port <unused-loopback-port>`；会在新.local生成仅本栈凭据、MySQL初始化SQL、compose.json及身份。随后`python3 stack.py config/up/status/down`。只允许grea-身份，down仅清理该Compose项目自己的卷和容器。镜像digest在stack.py固定；自有Go镜像按运行名隔离。最大资源约1GiB/1.1CPU，唯一对外端口绑定loopback。源码不含可用凭据，.local不可提交/分发。

这是显式development HTTP/内部私网gRPC样例；入口拒绝非development模式，生产TLS/身份、WSS、渠道验签、owner迁移、outbox/inbox和跨玩家分布式业务尚未实现。它们不是当前样例验证通过的暗示，不能直接对公网开放。

HTTP：POST /v1/login传credential返回sessionId；其余/v1/state、command、chat、order从Authorization Bearer取得会话，不接受body伪造身份。命令含operationId/expectedRevision/action/configVersion。64位数字走ProtoJSON十进制字符串。clients目录给Unity/Cocos适配及恢复语义，自有测试可持久化后重开并同号重试；无真实客户端实测时必须明确标记。

浏览器适配：development网关只允许GREA_BROWSER_ORIGIN声明的精确Origin（默认http://127.0.0.1:7456），支持Authorization/Content-Type预检，其他Origin拒绝。按实际Creator预览Origin配置，不能使用通配符绕过。跨配置版本的历史pending迁移、会话撤销和生产身份兼容窗口尚需产品明确实现，不从本固定版本示例推断完成。
