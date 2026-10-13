# grea 维护验证

技能维护的检查和场景数据统一在 tools；本页是维护验证入口，不规定游戏开发流程。静态通过与 Agent 行为正确分别记录。

## 静态检查

```sh
python3 /path/Games/grea/bin/recovery check_game_build_skill --workspace-root /path/Games --json
python3 /path/Games/grea/bin/recovery check_game_build_skill --workspace-root /path/Games --skill-dir /tmp/game-build-candidate --json
python3 /path/Games/grea/tests/tools/test_check_game_build_skill.py
```

Python 3.9+，标准库，无安装/网络/Editor/收费调用。可从其他 cwd 执行。检查器只读指定工作区和技能，stdout 输出 JSON；0=静态检查通过，1=有契约问题，2=输入/解析错误。skill-creator 的 quick_validate 仍单独检查技能 frontmatter；本工具不替代它。

检查范围：行内 Markdown 本地链接、Unicode 标题锚点、从入口可达的参考文件、显式 `recovery <ID>` 是否在分发器及对应脚本是否存在、注册表重复 ID。候选技能的外部链接映射到指定工作区；不执行分发器或导入被检查工具。拒绝检查范围之外的链接和技能符号链接；根 Git 不带的 projects 来源缺失仅给历史证据不可用警告。

限制：不是完整 Markdown/HTML 渲染器，不验证外部网站、引用式链接、Unity 运行或工具业务正确性；不推断任意自然语言简称是命令。不能用它自动判定规则冲突、文档语义正确或技能行为验收通过。

## 任务场景走查

[scenarios.json](scenarios.json) 保存稳定的请求、最小前提、预期模式、可观察结果和应阻止的范围扩大。编号用于跟踪，不表示关卡或开发阶段。

1. 维护者从每条请求出发，读候选入口和实际需要的参考，记录其决定、所依据的段落、剩余歧义及是否扩大任务。不能只检查是否出现某个词。
2. 保留各场景的 observed_decision、evidence、result 和 evaluation_method；`maintainer-walkthrough` 表示文档决策走查，不写成已运行独立 Agent 或游戏。
3. 只有已获授权时才做独立 Agent 对照。评估输入只给 request/setup、技能及最小原始材料，不透露预期答案；用实际调用、产物、失败处理和范围检查结果。隔离测试目录，禁止场景自动获得收费、安装、发布权限。
4. 记录候选文件指纹、结构结果、场景结论及未执行项到 `grea/docs/validation/<run-id>/`。发生失败修正权威条目，按影响范围重验；不要给每个反例新增一条全局禁止。

新增场景优先覆盖真实误路由或遗漏行为，不增加重复同义测试。当前场景覆盖完整恢复、局部修复、素材复用/指定工具、目录重构、跨引擎、性能、预览、超时、分维度验收、原创排除和只评估不实施。
