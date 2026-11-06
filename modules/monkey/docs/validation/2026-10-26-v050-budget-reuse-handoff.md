# v0.5.0.dev1 大工程、阶段复用与采用交接核验

2026-10-26；开发阶段，本轮没有 GitHub 推送/Release/全局安装。日常 CLI 仍为已安装 v0.4.0。原包、正式游戏/GREA 只读；自有输出与副本写入。用户后来批准的三产品职责整改使 05-B 交 beaver，05-A 与恢复阻断仍归 monkey。

## 大工程预算与完整性

全输入候选上限 8 GiB/500,000 文件；选择集仍 256 MiB/20,000；单文件512 MiB，manifest128 MiB/800万节点。源解析预算独立。哈希/复制1MiB块；POSIX目录描述符缓存最多128，拒绝symlink/FIFO/越界/大小写与Unicode碰撞，独立复制不共享可写硬链接。

| 冻结候选 | 文件数 | 总字节 | owning manifest SHA256 |
|---|---:|---:|---|
| 样例项目 Unity | 75,710 | 2,834,639,181 | `[private fingerprint omitted]` |
| 样例项目 Creator | 74,694 | 2,789,086,480 | `[private fingerprint omitted]` |
| 样例项目 Unity | 164,599 | 3,267,184,074 | `[private fingerprint omitted]` |

全部实际文件逐项哈希/大小核验通过，分别约32.4/30.0/62.7秒（本机一次观测，不作性能承诺）。后续RootReader快路径完成全量预览，样例项目21.7秒、样例项目65.4秒。未知文件/越界/漂移拒绝；manifest自填limits不能提升工具上限。

## 源阶段复用

样例项目完整输入集 SHA `[private fingerprint omitted]`；复用旧 inspect/normalize，实际将源解析器与像素解码器 patch 为调用即失败，仍完成复用，IR语义字段一致，约30.7秒。重定位来源路径/新的阶段清单身份单独记录，媒体独立复制。最终代码增加源I/O预算常量身份后，再核旧缓存的inspect/normalize精确合同仍兼容。

样例项目601容器复用既有inspection，`subprocess.Popen`设为调用即失败，未启动源worker/provider，81,544已解析与36未解析原样保留，约13.0秒。没有为复用伪造36对象恢复。

版本/命名/布局变化不触发无关源重读；reader/schema/I/O或归一化库变更使对应缓存失效；原输入与阶段/chunk仍读盘核验。旧v0.4只接受已审精确逐文件/核心I/O及库版本合同，不保证任意历史缓存或任意工具升级都可免解析。原有resume仍有工具/包身份约束，fresh `--reuse-source-stages` 与其分开。

## 采用验证与移交限制

最终三方预览：样例项目2操作/0冲突/17,642保留，样例项目1/0/37,648。采用目标仅自有隔离副本；原始导出不改。人工文件保留，冲突/身份歧义/设置或依赖漂移/陈旧计划拒绝。SourceRecovery/Docs/Analysis未被当作人工工程Assets同步。

样例项目前一WIP真实BGM移动、GUID/localID回读及独立重开通过；经历manual meta规范化保护拒绝并原生回滚的反例。最终目录创建/新增资产修复完成C#离线编译，未做新原生执行；Creator原生执行未实现，向样例项目Editor未启动。详见 [BEAVER-HANDOFF](../BEAVER-HANDOFF.md)，不能将旧算法原生结果冒认为最终WIP已全验。

最终339项测试通过（15.972秒）；源码/证据SHA清单见 `.private/v050-adoption-20261026/beaver-handoff/freeze.json`。未执行Player/微信构建、视觉/业务验收。05-C的36对象/图集/Tiled/动画名/Spine/Shader以及05-D其他项待实施，整版v0.5尚未完成。

私有证据根 `.private/v050-adoption-20261026/`：`large-inventory-audit.json`、`full-source-reuse.json`、`unity-source-reuse.json`、`handoff-source-contracts.json`、`tests-handoff.log`、`compile-handoff.log`、sample-game各Transaction日志/回执与两个最新Preview。失败/恢复证据和before-image原地保留，不公开分发游戏资源。
