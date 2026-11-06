# monkey 实施、验证与AI接续

## 当前交付目标

默认用户入口为monkey convert，从wxapkg/APK/Cocos资源集合开始，自动盘点全部已取得文件，恢复支持资产和源码模块，输出Unity6/Creator3.8工程与TS/C#初稿，并提供自包含AI接手文档。asset-index保留为调试选项；单奖励页不是最终产品。安全容器适配、全资源处置/字节覆盖、模块映射、规范路径与实际打开分别验收。未知资源和不可编译初稿存SourceRecovery，禁止假成功业务或源运行时解释器。原生自动导入/失败续接的未实现状态继续准确记录。

## Python落地方案

- Python最低3.11，`pyproject.toml`＋src布局，入口`monkey = monkey.cli:main`；标准库argparse/json/dataclasses/pathlib/hashlib/logging优先，避免先引入Web服务或任务队列。
- Pillow用于明确格式的图片读取/重建；仅本项目虚拟环境和锁定依赖。其他图像解码器做可选provider，缺依赖返回dependency_missing，不能静默换算法。
- dataclass/TypedDict或同等显式模型约束数据；IR与报告带schema版本。第一版不引入复杂ORM/数据库；索引和报告为有界JSON，后续有实际规模问题再评估流式存储。
- 自造fixtures先覆盖真实格式形态与关键语义，Python测试优先unittest或现有项目选定pytest；不要重复建立多个运行器。工具运行时不调用AI、不需要网络。

## CLI合同（实际能力以USAGE/PLAN为准）

```text
monkey capabilities --json
monkey inspect --source SOURCE --source-profile cocos-2.4.15-bundle --out NEW_RUN
monkey normalize --manifest SOURCE_MANIFEST --out NEW_IR
monkey plan --ir IR --target-profile PROFILE --out NEW_PLAN
monkey export --plan PLAN --out NEW_CANDIDATE
monkey verify --candidate CANDIDATE --level static|editor --out NEW_REPORT
monkey handoff --candidate CANDIDATE --out NEW_HANDOFF
monkey diff --previous MANIFEST --candidate NEW_MANIFEST --out NEW_DIFF
monkey apply --candidate CANDIDATE --target REGISTERED_OUTPUT --expected-manifest HASH
```

实现可合并内部流水线，但子步骤保持可重复/可定位。一个模块结束无需让Agent手动执行几十条逐文件命令。CLI输出紧凑摘要和报告路径，完整结构写文件；使用机器可读exit/status，不通过长stdout传整个资源树。

默认退出码：0本命令声明范围成功；1产出partial/unsupported/conflict报告且需要处理；2参数/IO/依赖错误。Editor不可用时static可完成、editor标not_run，不冒称已验。dry-run/plan不启动编辑器，不修改目标。

## AI工作包合同

每个包围绕完整可见模块，不按单个字段拆派：

```text
模块：建造详情页
目标：补齐工具未实现的资格展示、提交与结果反馈
输入：源manifest与hash、原脚本位置、页面/状态截图、JSON表ID
已完成：背景、图标、文本组件、九宫格和序列化引用
缺口：业务回调/动态状态/未知组件，逐项标置信度和原依据
可写：目标View/Presenter及明确组件；generated区域需先解除所有权
依赖：现有服务接口或Unavailable状态；不假发奖
验证：受影响页面实际打开与输入、必要失败路径、已有证据复用
输出：变更文件、实际结果、未验项、回查路径
```

机器包`handoff.json`包含taskId、sourceRefs、generatedTargets、gaps、allowedPaths、dependencies、verificationScope；人读Markdown只做视图，不另立任务真源。未知只能生成明确待办，不能用空回调/假返回把缺口抹平。monkey不新建Agent或发送消息，用户当前主Agent选择执行。

## 最小有效验证矩阵

| 层级 | 核对内容 | 不代表 |
|---|---|---|
| reader/资源语义 | UUID/pack越界、缺引用、旋转trim九宫格、Unicode文本、原件不变；每类有有效和相关失败样本 | 编辑器已导入 |
| 输出静态 | GUID/UUID映射稳定、路径闭包、支持矩阵、unknown保留、输出不覆盖、生成冲突 | 画面正确/业务可玩 |
| Editor导入/保存回读 | 引用、类型、尺寸/锚点、缺脚本、可编辑且序列化保存一致 | 真实输入、完整业务或平台交付 |
| 原版代表画面对照 | 同页面状态，关键图/字/层级/遮罩/动画依据；实际截图可查看 | 所有页面保真 |
| AI接续演示 | 一个有真实来源的缺口可按工作包补完；工具重生成不损坏人工修改 | 全游戏/服务端恢复 |

每次只跑修改对应的层；成组阶段验收集中一次，不为一个parser字段启动完整双引擎构建。官方Editor没有可用授权/资源窗口时准确标待验，先交可验证离线增量。不要把not_run删掉换成pass。

## 历史首个切片工作包（保留依据，不限制当前总目标）

1. 核对本目录、原源只读边界、现有工具和私有样本可得性；不全文重复读历史。
2. 列出首批input profile和最低格式证据，挑一个包含图集SpriteFrame＋文本＋九宫格的界面闭包；路径/UUID从现有冻结清单读取，不凭截图猜文件。
3. 先实现inspect/source-manifest、稳定引用索引与两个语义fixtures，再接normalize SpriteFrame；输出一组可检查资源和明确未支持清单。
4. 达到上述可见成果后，连续推进v0.1 Unity输出，不停在计划文档或工具help通过。

## 交付与进度

- 每个大版本是工具的成组能力，不为单个检查点新版本。开发者在PLAN更新结果/阻塞/下一步，提交本项目的明确源码成果，原始私有输入永不进Git。
- 本地包、源码、schema、支持矩阵、样本复算方式、已知缺口和必要引擎版本一并给出。CLI/MCP可连接、脚本测试、引擎导入和真实对照分别说明。
- 真正阻塞反馈总监：缺失条件、受影响范围、已做证据、最小解除方式和独立可继续项。主线程只在成组交付/重大问题时通信，不礼节ACK、不固定巡检。
- 不自动创建远端或推送/发布，不全局安装插件；不把新工具研发变成修改样例项目、恢复其他项目或再次全量验收的理由。

## 参考依据（仅接口与迁移设计参考）

- Cocos官方2.x→3.x迁移说明：https://docs.cocos.com/creator/2.3/manual/en/release-notes/upgrade-guide-v3.0.html
- 官方2.x迁移插件：https://github.com/cocos/cocos-plugin-import-2.x （使用前检查版本、许可及适用输入）
- Unity PrefabUtility：https://docs.unity.com/en-us/engine/6000.5/script-reference/unityeditor/prefabutility （执行时使用实际目标版本文档）
- GREA当前本地解析与有限转换实现；样例项目现有提取器和原版证据仅按需只读参考，路径/私有材料不复制进公开产品。
