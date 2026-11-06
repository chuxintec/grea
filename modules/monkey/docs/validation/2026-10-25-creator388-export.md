# Cocos Creator 3.8.8 离线导出测试

按用户最新指令，本轮仅使用 monkey 导出并静态验证。没有调用其他转换器，没有启动 Creator 或执行原生导入。

实际导出通过 monkey CLI（本地版本 0.2.0.dev3 工作树）：

```sh
bin/monkey convert --input-set [local path] --target cocos38 --namespace sample-game-v11-monkey --out outputs/sample-game-creator388 --offline
bin/monkey verify --candidate outputs/sample-game-creator388/CocosProject --level static --out outputs/sample-game-creator388/StaticVerification
```

- 目标 package.json 声明 Creator 3.8.8；导出 completed=true，整体 partial。
- 静态验证 pass、0 诊断；Editor not_run。
- 全部 17,201 输入、884,709,704 字节进入资源台账。
- 528 份配置 JSON（10 包）、1,776 套 Spine 文件闭包、914 代码草稿；闭包和草稿不代表原生运行完成。
- 候选导入计划：8,511 资产、8,472 SpriteFrame、24,784 节点、1,694 源 Prefab。以上为计划计数，不是 Editor 已生成计数。
- 工程 manifest 63,896 项文件，中文路径 0；正式文件按拼音命名，原配置内容保留。
- 15 项相关离线测试通过；没有本轮功能代码修改、发布或游戏工程修改。

配置入口：outputs/sample-game-creator388/CocosProject/Docs/CONFIGURATION.md。

导出的 4 项源恢复警告仍保留：2 个 UNSUPPORTED_WRAPPER、1 个 MODULE_RECOVERY_PARTIAL、1 个 NATIVE_OBJECT_RECOVERY_PENDING；覆盖范围内仍有 1,521 个缺失引用。不把静态 pass 理解为完整可运行游戏。按最新范围，原生导入、编译、浏览器运行与视觉验收均未执行。

完整回执：.private/creator388-export-20261025/delivery.json，CLI 原始结果位于 outputs/sample-game-creator388/conversion-result.json 与 StaticVerification/verification.json。
