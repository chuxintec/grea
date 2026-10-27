# Creator 3.4.1 与 CCON 的有限离线读取

`cocos_assets --config CONFIG --asset-index N --adapter cocos-3.4.1-index-v1 --output NEW_DIRECTORY` 读取明确选择的 bundle 索引。配置版本是调用者选择；相同序列化结构可能跨引擎版本复用，不能单凭 header 1 证明引擎版本。必须先有包体的 Creator 版本证据。

实现覆盖：UUID 与子资源后缀、短 pack ID、数字/规范十进制字符串的成员索引、版本索引、共享 header-1 pack 的节序号、选定 standalone import 与 CCON sidecar。现有 header-1 结构解码函数复用的是序列化协议，并未把整个 2.4 bundle 适配器当作 3.x。缺版本、重复身份、越界、多个 pack 归属、节数不一致均失败；不猜测 glob 第一项，不下载任何 native 数据。

`cocos_assets --input FILE.json --adapter cocos-3.4.1-ccon-json-v1 --output NEW_DIRECTORY` 支持观察到的 CCON JSON version 1 + 单个 `.bin` sidecar + Uint8Array 字节范围。JSON 里的 `document` 是对象表，`__id__` 保持数据引用；`TypedArrayRef` 指向经过 SHA-256 校验的 BIN 子范围。缺 BIN、未知版本/ctor/多个 chunk 明确拒绝。曲线编码、骨骼播放、CCONB 二进制容器以及游戏运行均不在此适配器范围内。

`cocos_modules --input FILE.js --adapter system-register-v1 --output NEW_DIRECTORY` 用已锁定 Acorn AST 提取 System.register 的工厂函数原始字节范围及字面量依赖。动态模块名/依赖和匿名调用保留 unresolved，报告 partial；重复字面量身份失败。不会执行工厂、求值表达式、导入游戏模块或把语法调用当作运行时注册证明。

自有有限夹具见 `tests/test_cocos3_evidence.py`。当前项目重放覆盖 Creator 3.4.1 的一个 CCON 动画描述及两个音频 pack 节，不泛化为全部 3.x 内容已支持。

<!-- grea:tool cocos_assets -->
<!-- grea:tool cocos_modules -->
<!-- grea:path src/grea/tools/cocos3_evidence.py -->
