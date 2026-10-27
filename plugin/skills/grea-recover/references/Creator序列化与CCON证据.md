# Creator 序列化与 CCON 离线证据

本文说明 Creator 3.4.1 的有限离线读取适配器；先从包体或可靠项目记录取得具体 Creator 版本证据。序列化 header/协议结构可能跨引擎版本复用，单凭 header 1 不能确认引擎版本。通过已安装 GREA 根目录的 `list-tools`、`describe-tool` 核实当前能力，并以 `run-tool` 调用 `cocos_assets` 或 `cocos_modules`。

## `cocos_assets`：bundle 索引

```sh
grea run-tool '{"tool_id":"cocos_assets","arguments":["--config","/absolute/config.json","--asset-index","N","--adapter","cocos-3.4.1-index-v1","--output","/absolute/new-candidate"],"run_dir":"/absolute/new-run"}'
```

调用者明确选择 bundle 索引和配置版本。实现范围包括 UUID 与子资源后缀、短 pack ID、数字或规范十进制字符串成员索引、版本索引、共享 header-1 pack 节序号、选定 standalone import 与 CCON sidecar。适配器复用 header-1 序列化协议解码，不把 Creator 2.4 bundle 适配器整体套用到 3.x。

缺少版本、重复身份、越界、多个 pack 归属或节数不一致时失败；不按 glob 首个结果猜选，也不下载 native 数据。

## `cocos_assets`：CCON JSON 与 BIN sidecar

```sh
grea run-tool '{"tool_id":"cocos_assets","arguments":["--input","/absolute/file.json","--adapter","cocos-3.4.1-ccon-json-v1","--output","/absolute/new-candidate"],"run_dir":"/absolute/new-run"}'
```

仅支持观察到的 CCON JSON version 1、单个 `.bin` sidecar 和 `Uint8Array` 字节范围。JSON 的 `document` 是对象表，`__id__` 保留为数据引用；`TypedArrayRef` 指向经 SHA-256 校验的 BIN 子范围。缺少 BIN、未知版本或构造器、多个 chunk 均明确拒绝。曲线编码、骨骼播放、CCONB 二进制容器和游戏运行不在范围内。

## `cocos_modules`：System.register

```sh
grea run-tool '{"tool_id":"cocos_modules","arguments":["--input","/absolute/file.js","--adapter","system-register-v1","--output","/absolute/new-candidate"],"run_dir":"/absolute/new-run"}'
```

使用锁定 Acorn AST 提取 System.register 工厂函数原始字节范围及字面量依赖。动态模块名/依赖和匿名调用保留 unresolved，并将报告标为 partial；重复字面量身份失败。不执行工厂、不求值表达式、不导入游戏模块；语法调用不证明运行时已注册。

## 证据范围

自有有限夹具覆盖离线解析逻辑，不等同于产品输入完整性。当前项目重放只覆盖 Creator 3.4.1 的一个 CCON 动画描述和两个音频 pack 节，不推广成所有 3.x 内容均受支持。离线读取结果只能支持所列结构与字节范围，不证明动画、骨骼或玩法运行。
