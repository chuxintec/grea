# monkey 与 beaver 调用

## 职责和就绪

GREA 完整执行链必选 `monkey`、`beaver`。恢复导出实际调用 monkey，已有工程接管、生成、编辑、配置、资源处理、测试及构建实际调用 beaver；GREA 提供方法、轻量绑定与证据组织。游戏业务由对应开发者维护。

先 MCP `session` 确认当前加载版本。`required_toolchain.runtime=not_checked` 只表示依赖声明。显式执行：

```json
{"tool_id":"toolchain_check","arguments":["--output","/absolute/new/toolchain-check"],"run_dir":"/absolute/new/toolchain-run"}
```

输出分别保留 monkey/beaver 的真实诊断、版本、能力摘要和锁定状态。任一缺失、歧义、失效、不兼容或实现漂移，完整新执行链为 `needs_action`；文档与只读计划可继续。`run_tool` 外层可能将诊断退出码归为 finding，判断就绪必须读取其 `parsed_stdout.ready/status` 与 `result.json`，不能只看进程正常结束。

外层needs_action/error也可能发生在provider已经写入之后。先核executed、原stdout/退出码、actualChanges及现有journal的after见证，再决定下一步；不能把消费校验失败当零写入、自动重放旧apply或宣称已回滚。actualChanges允许非空路径字符串或对象摘要，须原样保留。修正Schema后的离线重验另存，不追改旧外层/原生回执，也不冒充新执行；已完成动作继续项目原定验证。

首次只读发现使用 `monkey_pipeline discover`、`beaver_pipeline discover`，不联网、安装或运行外部工具。monkey 已有明确授权的缺失自动安装流程见[monkey接入](providers/monkey.md)；beaver 本轮没有自动下载/全局安装。明确 `GREA_PROVIDERS` 配置优先，失效配置不静默换安装。

## 模块统一发布与安装

monkey 与 beaver 是 GREA 的两个模块：各自仓库、版本和 CLI 独立开发，随 GREA 版本统一发布。`modules.lock.json` 固定每个模块的 wheel 文件名、SHA256、字节数、依赖和来源；带 tag 的 GREA 完整插件必须内置这两个 wheel（`modules/wheels/`），预览构建可标 `not_bundled_preview`。模块的共享依赖（Pillow、pypinyin）由 GREA 锁定运行时提供。

```json
{"tool_id":"grea_modules","arguments":["status"],"run_dir":"/absolute/new/modules-status"}
{"tool_id":"grea_modules","arguments":["install","beaver","--output","/absolute/new/beaver-install"],"run_dir":"/absolute/new/beaver-install-run"}
```

`status` 只读；`install` 校验 wheel 与锁一致、逐文件核 RECORD 后装入 provider 状态目录下的独立版本化 venv，不下载、不改已有 binding、不全局安装。安装后的启动器只成为发现候选，仍需按下文 pin（beaver）或 `monkey_pipeline ensure`（monkey），再由 `toolchain_check` 判定就绪；与 `~/.local/bin` 中另一份并存时保持 ambiguous，用显式 `GREA_PROVIDERS` 选择。模块升级先更新锁并重新验证，再随新 GREA 版本发布；在途项目的旧 lock 不自动切换。

## beaver 固定绑定

先按[beaver接入](providers/beaver.md)核对当前实际 CLI。外部 provider 不通过源码 import 集成。开发 CLI 只能由明确配置绑定到隔离上下文，并标明未发布。

```json
{"tool_id":"beaver_pipeline","arguments":["pin","--identity-root","/absolute/installed/package/beaver","--output","/absolute/new/beaver-pin"],"run_dir":"/absolute/new/beaver-pin-run"}
```

保存返回的 `beaver-lock.json`，后续 `beaver_pipeline check --config LOCK --output NEW` 或 `toolchain_check --beaver-config LOCK --output NEW` 重新核程序、包文件和能力摘要。此 pin 只写调用者指定输出，不修改客户端设置或全局安装。没有 lock 仅探测成功也不算可执行链就绪。

通过 readiness 后使用 `beaver_pipeline invoke --config LOCK --request REQUEST --output NEW` 调当前已声明的命名操作。采用、unity.plan/apply、payload、配置/图片、代码检查与Player的参数由beaver请求Schema（GREA 安装目录 `schemas/beaver-operation.schema.json`）固定；引擎操作实现仍在beaver，不在GREA复制。unity.apply还要核plan所选具体能力。完整用法和证据范围见[beaver接入](providers/beaver.md)。

beaver最终0.1.0本地wheel已交付，GREA dev3的匹配源码构建和Player证据可复用；早期Prefab读回属于另一wheel，正式游戏采用、物理输入、全玩法和安装发布分别记录，不能合称同版全链通过。GREA dev4补齐命名转发，仅验证新增边界，不再启动引擎。

GREA源码dev4支持分别固定的0.2、0.3.0.dev1候选07及本地0.3.0候选08/元数据等价09有限路由，旧lock仍绑定原包。新增workspace、production3、config3、C#五层/语义候选、资源和部分Go候选/计划；必须核精确producer与组合能力ID，不把版本号当通用支持，旧原生事务不能换实现重放。更换项目工具身份需旧profile SHA、显式rebind和新计划。先查[版本和参数边界](providers/beaver.md)，不把异步debug预算当RPC等待时间；MCP外层finding需继续读wrapper及provider原始状态。正式08中文路径的有限原生收敛回执现已核验，但不能升级为独立重开、完整游戏或正式Go采用；整体G结论仍由beaver主开发汇总。


## 复用与兼容过渡

已存在开发工程复用冻结来源和已核候选；日常改 UI 不强制重导 monkey，也不为形式双调用重复工作。已有锁定旧 GREA 工具的在途项目可沿其明确批准基线继续，不能把这项例外写成新主线绕过 beaver。

旧工具 ID 与接口保留。执行实现先在来源快照下交 beaver 参数化接收、测试并由消费者验证，之后才将旧 ID 变薄转发；未完成前保持原实现并标明过渡，既不删除，也不返回空成功。源格式解析仍交 monkey，不在 beaver 或 GREA 再建解析器。

## 已有工程的只读检查

需要确认工程上下文时，使用已固定 beaver 的薄适配，不重新导出来源：

```json
{"tool_id":"beaver_pipeline","arguments":["inspect","--config","/absolute/beaver-lock.json","--project","/absolute/project","--output","/absolute/new/project-inspect"],"run_dir":"/absolute/new/project-inspect-run"}
```

此调用检查两项依赖后，真实执行 `beaver project inspect --project PROJECT` 并保留原始状态；只读上下文检查不代表采用、Editor 连接或工程迁移通过。beaver 的能力发现默认 JSON，无 `--json`；不要照搬 monkey 的参数。

## 开发版来源查询

稳定monkey0.4继续负责既有已验批量合同。monkey0.5.0.dev1已实现query-methods、query-tables、inspect-aliases；仅可在明确固定的开发入口使用，不能把它们声明为稳定0.4或当前GREA批量适配已有操作。详见[monkey开发查询](providers/monkey.md#开发版来源查询)，不为接通既有三工具链等待整版0.5。
