# Cocos 离线结构解析与模块证据

此参考限定 `cocos_assets` 与 `cocos_modules` 的可观察输出。工具只读取明确选择的文件，在完整预检后写入不存在的候选目录；不会运行来源 JavaScript、创建 Unity 资产或证明玩法与渲染一致。原项目脚本和原始证据仍由项目持有。

从已安装 GREA 根目录使用统一执行层。先用 `list-tools` 和 `describe-tool` 确认当前版本、依赖与参数，再通过 `run-tool` 调用工具；安装 Skill 本身不会额外安装 Node：

```sh
grea describe-tool '{"tool_id":"cocos_assets"}'
grea run-tool '{"tool_id":"cocos_assets","arguments":["--input","/absolute/source.json","--output","/absolute/new-candidate","--adapter","cocos-2.4-compiled-v1"],"run_dir":"/absolute/new-run"}'
```

## `cocos_assets`：Creator 2.4 离线子集

版本 0.1.0 使用 GREA 自带 Python，不增加第三方依赖。仅显式支持 `cocos-2.4-compiled-v1`（header=1、11 段）、共享表 pack 和 Texture2D pack，不承诺兼容所有 Creator 2.4 变体。UUID 只接受标准 36 字符或压缩 22 字符形式；其他身份编码拒绝。自定义 payload/内联值保留类型标签，不表示引擎语义已完整恢复。实例和资源引用保持 `__id__`、`__uuid__` 数据形式，不成为生产运行时对象。

bundle 模式使用 `--config /absolute/bundle/config.hash.json --asset-index N`；索引可重复，最多 64 项。配置中的 import version 精确选择文件；无 version 时仅在唯一匹配时继续。pack 的 `pack_section_ordinal` 与 `asset_index` 分开记录。Texture pack 必须显式指定 `--pack-adapter cocos-2.4-texture-pack-v1`，不会按数组长度猜格式。native 二进制资源不在本工具范围。

## `cocos_modules`：JavaScript 静态语法证据

0.1.0 是可选 AST 工具，需本机 Node 与锁定 Acorn 8.15.0。只有维护或明确采用该工具时，才在已安装 GREA 产品根目录执行：

```sh
npm ci --prefix tools/cocos --ignore-scripts --no-audit --no-fund
grea run-tool '{"tool_id":"cocos_modules","arguments":["--input","/absolute/game.js","--output","/absolute/new-index","--adapter","browserify-table-v1"],"run_dir":"/absolute/new-run"}'
```

| adapter | 可提取范围 |
| --- | --- |
| `browserify-table-v1` | 三参数函数调用的字面量模块表；保留工厂原始字节、依赖和字面量 RF 语法 |
| `define-browserify-v1` | 同类模块表，但位于明确的 define 包裹函数内 |
| `define-factory-candidates-v1` | 动态拼表表达式中的赋值函数候选；不猜名称、表归属、动态依赖或 RF，结果始终为 partial |

Creator 3.4.1 的 `system-register-v1` 与 CCON 独立适配子集见 [Creator 序列化与 CCON 证据](Creator序列化与CCON证据.md)。

## 预算、报告与解释

- 单文件默认读取预算 32 MiB，可显式降低，上限 256 MiB；bundle 每个来源最多 32 MiB、合计 64 MiB。候选数据文件总量最多 64 MiB，可用 `--max-output-bytes` 降低。
- AST 子进程限时 30 秒，V8 堆 256 MiB，且有节点数和深度限制。预算用于可靠性约束，不把 Node VM 当作安全隔离机制。
- 报告包含 schema/tool/implementation 版本、source format、来源 SHA/字节数、选择项、输出 SHA、status、errors/unsupported、scope/effects；候选报告还列 unresolved 与 syntax candidates。
- 退出码 0 表示当前声明范围完整，1 表示 unsupported/partial，2 表示输入、依赖、IO 或预算错误。统一执行层还会保留外层回执、stdout、stderr 和报告。0 不等于原生 Unity 转换验收通过。

不执行初始化器或工厂，不做常量折叠、别名求值、反混淆或源码改写。标为 `literal_syntax` 的 RF 只代表字面语法，不证明调用运行或 `cc` 未被遮蔽；缺少字面 RF 不证明没有脚本类。块作用域、提升和赋值中的标识符保留未解析。输出文件名按 SHA-256 身份生成，避免路径字符替换冲突；区间按 UTF-8 字节计。遇到歧义、未知 loader、重复身份或损坏数据时审查报告，不选 glob 第一项，也不执行 JS 隐藏缺口。

公开 fixtures 是自有合成数据；私有资源回放只是有限格式回归，旧导出来自旧 reader，不是独立 oracle。Creator 2.4 结论不覆盖其他版本。Creator 3.x 必须先有包体版本证据；header 1 可跨版本复用，不能单独证明引擎版本。
