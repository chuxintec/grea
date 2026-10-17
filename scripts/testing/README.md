# 有界测试运行器

Unity 基础框架 的隔离源码准备使用 `prepare-unity-framework.py --output <new-directory>`；该脚本只创建新测试目录，不启动 Unity、不改已有工程。原生测试、依赖与验收边界见 [基础框架 使用说明](../../docs/Unity指南.md)。

```sh
python3 scripts/testing/run-tests-bounded.py --project /path/project --timeout-seconds 20 --rss-mb 384 --heap-mb 192 'test/*.test.mjs'
```

Python 3.9+、POSIX ps/进程组，Node 测试需要支持 --import 和 --test-timeout 的 Node。--python /path/python 可运行 Python 探针。只终止自身启动的进程组；RSS 为采样阈值不是内核硬上限；监控不可用时拒绝启动。报告写项目内 output/test-monitor 或新 --report-dir；已有报告目录拒绝覆盖。首个失败停止，返回非零。第三方工具入口保留在 ../bin。

工程生成 使用 `prepare-unity-generator.py` 创建带保护标记的隔离 Editor 测试工程；`--generated-project` 从生成工程复制源码到新 PlayMode 验收目录，不写输入。具体命令见 [工程生成](../../docs/Unity指南.md)。
