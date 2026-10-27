# monkey 与 beaver 调用

本页用于首次准备或依赖身份变化；具体请求只读取相应[monkey合同](monkey恢复工具合同.md)或[beaver合同](beaver工程操作合同.md)。GREA编排，monkey生成恢复候选，beaver操作开发工程，游戏开发者负责业务结果。已有工程不为形式重导，已核身份不变时复用就绪证据。

## 发现与就绪

1. MCP/CLI `session` 核实际GREA版本；`required_toolchain.runtime=not_checked`只是声明。
2. `monkey_pipeline discover` / `beaver_pipeline discover`只读发现，不执行外部工具、联网或安装。显式`GREA_PROVIDERS`优先；多份不同安装为ambiguous，坏绑定不静默换版本。
3. 按各自合同固定实际程序、包文件和能力。monkey用`ensure`，beaver用`pin --identity-root PACKAGE --output NEW`。保存lock，不编辑版本或路径伪造迁移。
4. 需要新的就绪回执时调用：

```json
{"tool_id":"toolchain_check","arguments":["--output","/absolute/new/toolchain-check"],"run_dir":"/absolute/new/toolchain-run"}
```

完整新执行链要求两provider就绪；缺失、不兼容、歧义或漂移为`needs_action`，无依赖文档/规划继续。读取`parsed_stdout.ready/status`及`result.json`，不能只看外层退出码。明确锁定旧基线的在途工作按既有合同继续，不自动切换。

## 随包模块

GREA安装根`modules.lock.json`固定两模块wheel及哈希；版本号不等于当前客户端已安装该模块。完整标签插件要求内置wheel，未打包的预览必须如实标记。

```json
{"tool_id":"grea_modules","arguments":["status"],"run_dir":"/absolute/new/modules-status"}
{"tool_id":"grea_modules","arguments":["install","beaver","--output","/absolute/new/beaver-install"],"run_dir":"/absolute/new/beaver-install-run"}
```

`status`只读。`install`校验锁、wheel与RECORD，写provider状态目录下独立版本化venv，不下载、不全局安装、不修改现有binding；依赖由锁定运行时提供。安装结果只是发现候选，仍须固定绑定和就绪检查。存在多份安装时显式选择；已有项目lock不随模块升级自动变化。

monkey支持显式缺失安装，范围见其合同；不能把一次历史授权写成所有安装的默认许可。beaver无自动下载流程。运行时、引擎、客户端安装分别按本次授权处理。

## 执行与失败

- 恢复：固定来源后`monkey_pipeline plan/run/audit`，再按候选交接规则继续。
- 工程：`beaver_pipeline check --config LOCK --output NEW`核身份；`invoke --config LOCK --request REQUEST --output NEW`只转发已声明命名操作。普通代码编辑不要求人为制造无关provider调用。
- 仅查工程上下文可用`beaver_pipeline inspect --config LOCK --project PROJECT --output NEW`；这是只读检查，不是采用、迁移或Editor连接。
- 外层`finding/needs_action/error`可能发生在provider已经写入之后。先核`executed`、原stdout/退出码、`actualChanges`和journal；执行后消费校验失败不证明零写入，不自动重放apply或宣称回滚。修合同后的离线回读单独记录，不改旧原始回执。
- 旧工具ID与接口继续存在；其执行归属看registry的`delegate`。接收方实现、消费者验证和切换未闭合时不退休旧实现，也不返回空成功。新能力先核实际capabilities与GREA适配，不能透传未登记命令。
