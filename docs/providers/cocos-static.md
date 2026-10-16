# Cocos 离线结构解析与模块证据

工具只读取明确选择的文件，完整预检后生成不存在的候选目录。它们不运行源 JavaScript，不创建 Unity 资产，不证明玩法或渲染一致。原项目的脚本和原始证据继续归原项目。

`cocos_assets` 0.1.0 使用 grea 自带 Python，无新增第三方依赖。支持显式 `cocos-2.4-compiled-v1`（header=1、11 段）、共享表 pack 和 Texture2D pack；不是对所有 Creator 2.4 变体的兼容承诺。UUID 当前仅接受标准 36 字符或压缩 22 字符形式；其他身份编码明确拒绝。自定义 payload/内联值保留类型标签，不宣称全部引擎语义已恢复。实例和资源引用保留为 `__id__`、`__uuid__`，不会变成生产运行时对象。未知版本/kind 返回 unsupported；损坏下标、表长、JSON、非有限数、预算超限和覆盖冲突返回 error。

```sh
bin/grea run-tool '{"tool_id":"cocos_assets","arguments":["--input","/absolute/source.json","--output","/absolute/new-candidate","--adapter","cocos-2.4-compiled-v1"],"run_dir":"/absolute/new-run"}'
```

bundle 模式改用 `--config /absolute/bundle/config.hash.json --asset-index 7`，索引可重复指定，最多 64 项。配置 import version 精确选取文件；没有 version 时只接受唯一匹配。pack 的 `pack_section_ordinal` 和 `asset_index` 分开记录。Texture pack 需显式 `--pack-adapter cocos-2.4-texture-pack-v1`，不会按数组长度猜格式。native 二进制资源不在本工具范围。

`cocos_modules` 0.1.0 是可选 AST 工具，需要本机 Node 和锁定的 Acorn 8.15.0。它不是插件自带 Python 核心能力；安装插件不会额外安装 Node。维护或明确采用此工具的用户在产品目录执行：

```sh
npm ci --prefix tools/cocos --ignore-scripts --no-audit --no-fund
```

再经同一 `run-tool` 入口传 `--input /absolute/game.js --output /absolute/new-index --adapter <adapter>`：

| adapter | 范围与结果 |
| --- | --- |
| `browserify-table-v1` | 三参数函数调用的字面量模块表；保留工厂原字节、依赖和字面量 RF 语法 |
| `define-browserify-v1` | 同样的表，位于明确的 define 包裹函数内 |
| `define-factory-candidates-v1` | 对动态拼表表达式，仅保留赋值中的函数候选；名称、表归属、动态依赖与 RF 均不猜测，**始终 partial** |

不执行初始化器或工厂，不进行常量折叠、别名求值、反混淆或源码改写。标成 `literal_syntax` 的 RF 也只是语法证据：不证明该调用在运行时发生或 `cc` 未被遮蔽。缺少字面量 RF 不意味着没有脚本类。块作用域/提升/赋值中的标识符保留未解析。文件名用 SHA-256 身份，避免 `/` 改 `_` 造成冲突；区间以 UTF-8 字节计。

报告包含 schema_version、工具/实现版本、source_format、源 SHA/字节数、选择项、输出 SHA、status、errors/unsupported、scope/effects。候选报告还保存 unresolved 及 syntax_candidate。单文件默认读取预算 32 MiB（可显式降低，上限 256 MiB），bundle 每源 32 MiB/合计 64 MiB；候选数据文件合计上限 64 MiB，可用 --max-output-bytes 降低；AST 子进程 30 秒、256 MiB V8 堆、有限节点/深度。预算是可靠性限制，不把 Node VM 当成隔离机制。

退出 0=当前声明范围完整，1=unsupported/partial，2=输入/依赖/IO/预算错误；统一执行层仍保留外层回执、stdout、stderr 和报告，不把 0 等同于原生 Unity 转换通过。遇到歧义、未知 loader、重复身份或损坏数据应审查报告，不改成 glob 第一项或执行 JS 来隐藏缺口。

所有公开 fixtures 为自有合成数据。私有资源回放只是有限格式回归；旧导出来自旧 reader，并非独立 oracle。精确边界见 [工具验收记录](../validation/2026-10-16-project-tools.json)。

Creator 3.4.1 需要显式新适配器，见 [3.4.1/CCON](cocos3-evidence.md)。本文 2.4 结论不覆盖其他版本。
