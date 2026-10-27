# Cocos 离线解析工具接入手册

`cocos_assets` 0.1.0 随 GREA Python 核心提供；可选 `cocos_modules` 0.1.0 需本机 Node 与 Acorn 8.15.0，按产品维护说明准备依赖后通过 GREA `run-tool` 调用。先用 `list-tools` / `describe-tool` 核实当前 adapter、依赖和预算，再传明确的输入、全新输出目录与 `run_dir`。不执行来源 JavaScript。

Creator 2.4 的格式范围、UUID、pack 选择、AST adapter、预算、报告和失败语义见 Skill reference [Cocos 离线解析与模块证据](../../plugin/skills/grea-recover/references/Cocos离线解析与模块证据.md)。Creator 3.4.1 的 CCON 与 System.register 子集见 [Creator 序列化与 CCON 证据](../../plugin/skills/grea-recover/references/Creator序列化与CCON证据.md)。
