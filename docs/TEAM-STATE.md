# beaver v0.3 模块协作

基线fae3845，codex/beaver-v0.3，0.3.0.dev1。人类授权三条已原生核验（.private/v03/authorization.json）。执行Manager通用MODULE-DEVELOPERS。主开发单写CLI/公共Schema/proto组合/事务/Editor/桌面与隔离Compose应用，正式项目由其主开发采用。

| 实例 | 独占文件/完整模块 | 目标/观测 | 状态 |
|---|---|---|---|
| /root/native_ui | resources.py、BeaverResourceProduction.cs、test_resources.py、RESOURCE-PRODUCTION.md、.private/v03/resources | 复用GPT-6-Luna High；底层无独立回读 | Sprite/Atlas/主字体/Spine闭包/音频材质/SO引用已原生；直接fallback修正待最后集成；模块idle |
| /root/debug_sessions | configuration_v3.py、BeaverJsonRuntime.cs/.go.template、test_configuration_v3.py、CONFIGURATION-v3.md、.private/v03/config | 复用GPT-6-Luna High；底层无独立回读 | 共享复杂Schema已C#＋Go读取；Go真实App幂等完成；真实UI/Spine私有probe已交，模块idle |
| /root/reference_graph | csharp.py、BeaverSemantic*.cs、test_csharp.py、CSHARP-MAINTENANCE.md、.private/v03/csharp | 复用GPT-6-Luna High；底层无独立回读 | 255唯一顺序候选已实编译；统一Unity标准profile已原生+Play，模块idle |
| /root/go_server | server_go.py、server_templates/**、test_server_go.py、SERVER-GO.md、.private/v03/server-go | 新GPT-6-Luna High；底层无独立回读 | 完整Go工具已交；主开发完成自有六服/5owner迁移/Unity-App业务和重启缓存丢失验证，正常停止保留卷，模块idle |

新增Go实例因三个合适既有实例各承担独立就绪必选模块；当前4子Agent+主开发在真实6槽内，无递归、无常驻空任务。模块仅必要影响检查，不运行共享Editor/GUI，不触碰正式游戏/其他容器，不跨改其他产品。公共文件与集成由主开发负责，具体接口变更短报，不逐功能向总监验收。
