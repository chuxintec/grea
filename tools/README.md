# 通用工具实现

日常通过仓库根的 `bin/grea` 调用，以 [工具目录](../TOOLS.md) 选择工具、[registry.json](../registry.json) 查询实际入口。这里保存实现，不另设一套工具 ID。

| 目录 | 内容 |
| --- | --- |
| artifacts | 资产台账、依赖审计、文件与图像检查、录像信息、解包和封装；共享文件身份与报告模块 |
| recovery | 数值纹理、严格事件差分和显式项目解析器检查 |
| unity | Editor 资源审计、包备份/恢复、Profiler 安装和 Spine 构建配置 |
| dotnet | 托管程序集清理工具源码 |
| shaders | Shader 分阶段编译与反射探针 |
| wechat | 已授权离线包的解密、解包及 TextAsset 导出 |

自带脚本与外部依赖分别判断。第三方接入说明集中在 [docs/providers](../docs/providers/)，许可与安装边界见 [THIRD_PARTY](../THIRD_PARTY.md)。工具测试统一在 [tests/tools](../tests/tools/)；维护脚本在 [scripts](../scripts/)。
