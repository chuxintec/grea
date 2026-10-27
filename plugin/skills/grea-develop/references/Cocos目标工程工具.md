# Cocos Creator 目标工程工具

当前 GREA 源码已提供 `cocos_project` 与 `cocos_convert` 的有限能力，并有自有合成样例验证；生成/转换结果仍是待验候选，不代表目标工程可运行。实际 Editor 导入、TypeScript 编译、浏览器真实输入和渠道验收分别记录。安装后的当前 session 是否加载该能力，调用前以 `session`、工具清单和描述结果核实。仅在用户明确授权的 Cocos 目标范围内使用。

当前 registry 仍保留 GREA 工具：`cocos_project` 尚无已登记接收能力；`cocos_convert` 的 Monkey 接收方能力等价性和消费者切换尚未核验。不要因接收方名称或工具存在而称已迁移/退休；调用按当次 registry 与固定 provider 描述执行。

调用前从已安装 GREA 根目录使用 `list-tools`、`describe-tool` 核实当前参数；通过 `run-tool` 写入全新输出目录，输入保持只读。不要依赖源码树路径或假定安装了本机 Editor/Node。

## `cocos_project`

生成全新的 Creator 3.8.8 五层 Signal Counter 工程，可用 `--width`、`--height` 指定设计尺寸。模板使用 JSON 运行时读取；纯逻辑层不依赖 `cc`，输入和生命周期由 Presentation/Bootstrap 装配。它不含原游戏资产。已有输出路径会被拒绝；`grea-generated.json` 记录模板版本与文件摘要。

调用前使用 `grea describe-tool '{"tool_id":"cocos_project"}'` 确认当前参数，再用该 ID 通过 `run-tool` 传入设计尺寸和新输出目录。生成记录不证明 Creator Editor、浏览器或渠道已验收。

## `cocos_convert`

仅转换未编译 Creator 2.4.15 到 3.8.8 的基础对象数组，以及同代 3.8.8 有限对象。输入为 `.fire`、`.scene` 或 `.prefab`；来源脚本不执行。可用 `--asset-map` 提供如下 JSON：

```json
{"assets":[{"source_uuid":"...","target_uuid":"...","source":"relative/to/map","target":"assets/path","sha256":"..."}]}
```

`source` 相对映射文件解析，`target` 必须位于 `assets/` 下。当前仅接受 JSON、文本和音频外部资源。Sprite/SpriteFrame/纹理、外部字体、图集、Mask、动画、自定义脚本等明确返回 unsupported，不静默丢弃。

退出码 0 表示有限序列化候选，1 表示存在明确未支持项或引用闭包问题，2 表示坏输入或 IO 错误；任何结果都不能代替 Creator 导入和运行验证。

## `cocos_project --audit-project`

保守检查五层的字面量 import/export/dynamic-import 引用、反向依赖和循环依赖。计算式加载或外部依赖会标记需审阅；该扫描不是完整 TypeScript 解析器。实际类型检查和浏览器运行另行记录。

## 完整恢复与有限子集的边界

完整初版导出由固定 monkey 流程负责，GREA 核查交接并编排接续；可支持集合之外的来源或 profile 保持 `not_available`。上述有限 `cocos_convert` 保留旧 ID 兼容，不作为批量完整恢复入口，也不据此另建完整转换器。`cocos_project` 是可选工程规范模板，不代替真实资源和代码导出。Creator 目标保持明确选择，不能把源引擎包装成 Unity；引擎修改、插件和实际浏览器操作按用户授权边界执行。
