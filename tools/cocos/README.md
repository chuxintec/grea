# Cocos AST 解析 provider

Python 编排：`src/grea/tools/cocos_modules.py`；静态语法解析：`index-modules.cjs`。

依赖固定为 Acorn 8.15.0（MIT），来源 https://www.npmjs.com/package/acorn/v/8.15.0 ，完整许可在安装后的 node_modules/acorn/LICENSE。package-lock.json 固定完整性；安装不执行 lifecycle scripts。node_modules 不纳入 Git 或 Python 插件核心。

本目录不包含 Cocos 引擎源码、原游戏脚本或 VM 执行器。接口、安装与限制见 docs/providers/cocos-static.md。
