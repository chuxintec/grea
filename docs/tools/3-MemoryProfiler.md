# Memory Profiler安装与验证

P1MemoryProfilerInstaller.cs只在显式调用时运行，无启动钩子。安装API固定稳定版 com.unity.memoryprofiler@1.1.12。

- Install：Unity二进制以-batchmode调用-executeMethod P1MemoryProfilerInstaller.Install，不加-quit；异步Package Manager更新完成后脚本退出。
- Verify：可加-quit，同步检查实际包版本和已编译MemoryProfiler程序集。
