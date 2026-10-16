# 实际 Player 程序集元数据读取器

自有 .NET 8 控制台程序，输入由 `unity_player_audit` 编排预检。Mono.Cecil 精确锁定为 0.11.6，MIT，来源 https://www.nuget.org/packages/Mono.Cecil/0.11.6 ，上游 https://github.com/jbevain/cecil 。运行时使用 Deferred 元数据读取、拒绝程序集解析，不加载被检查 DLL。

构建方式、策略、身份边界与 IL2CPP 限制见 docs/providers/unity-native-exit.md。bin/obj 是本机构建结果，均不纳入 Git；不把读取器放进游戏 Runtime 或最终 Player。
