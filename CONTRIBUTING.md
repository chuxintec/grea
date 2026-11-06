# 贡献指南

从 [使用说明](docs/使用指南.md) 配置 Python 环境。维护约定见 [维护说明](docs/维护与发布.md)，游戏流程在 `plugin/`（GREA 插件），执行契约在 `src/grea/contracts.py`，模块路由在 `src/grea/commands/`，外部工具登记在 `registry.json`。

完整维护测试和发布工具使用 Python 3.12；运行时最低版本仍以 pyproject.toml 为准。标签发布及只验证不发布的入口见 [自动发布](docs/维护与发布.md)。

提交聚焦于一个问题，说明实际行为变化、验证和未执行范围。不要提交游戏包、第三方安装程序、商业素材、玩家存档、账号信息、设备标识、本机绝对路径或原始业务日志。测试使用合成夹具；依赖与许可见 [第三方说明](THIRD_PARTY.md)。

提交前运行：

```sh
uv sync --frozen --extra unity-visuals
npm ci --prefix tools/cocos --ignore-scripts --no-audit --no-fund
./.venv/bin/python scripts/generate_contracts.py --check
./.venv/bin/python scripts/generate_command_reference.py --check
./.venv/bin/python scripts/check_docs.py
./.venv/bin/python -m pytest tests
./bin/grea system check-skill --workspace-root . --json
git add <已审阅的文件>
python3 scripts/audit_public_tree.py
git diff --cached --check
```

Go 协议生成集成用例需要 PATH 中的 protoc、protoc-gen-go 和 protoc-gen-go-grpc；私有来源样本、原生 Editor 与特定平台的用例各自声明前置条件。

公开检查读取 Git 暂存区，输出文件名、行号和问题类别，不打印疑似秘密的值；通过只代表已配置的静态规则未命中，仍需审阅差异。不要用 `git add -f` 绕过本机材料排除规则。

修改技能时用 `scripts/sync_skill.py` 同步自己的客户端副本；CI 只检查源码，不写用户目录。第三方工具和 Unity 的实机测试按改动选择，缺少目标平台时明确未运行，不用模拟测试冒充。
