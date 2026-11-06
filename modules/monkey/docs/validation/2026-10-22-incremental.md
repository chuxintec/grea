# 2026-10-22 v0.3 增量与分发验收

状态：受控离线增量能力已实现，开发wheel可移位导入；不是正式发布。v0.1 Unity和v0.2 Creator实际导入/保存/编辑重开/视觉/输入仍not_run。

8个增量定向用例覆盖新增/修改/移除保留、人工区保留、生成区人工冲突、缺失/占位、未登记根、跨profile、陈旧或被改预览、expected-manifest不一致、输入变更、symlink/非规范路径与伪manual所有权。模拟中途写盘失败后原内容、manifest、registry恢复且留备份journal。受影响Creator3例与目标输出4例通过，合计15个独立定向用例；没有重跑无变化的全套基线。

真实代表页仅用隔离副本`outputs/creator-incremental-base`执行两轮：02→03的生成器元数据更新、03→04的Creator薄扩展更新；每轮diff→dry-run→expected-manifest/preview受控apply→静态verify通过。实际目标内容未涉及游戏业务变化。Synthetic用例覆盖新增和移除；不能把该副本测试扩大为引擎运行验证。

最新Creator候选：`outputs/creator-reward-04`，manifest SHA-256 `[private fingerprint omitted]`。其薄扩展新增原生SpriteFrame rect/originalSize/offset/九宫格/Texture UUID回读检查；未实际执行。

Unity兼容新导出：`outputs/unity-reward-v03-02`，manifest SHA-256 `[private fingerprint omitted]`，静态通过；Manual README登记为人工脚手架，后续不覆盖。

`unity-reward-10`及`creator-reward-02`冻结manifest未变，21份原始来源/证据hash未变；不改样例项目或GREA。旧冻结候选不作为apply实写对象。

开发wheel：`.runtime/wheels-continue02-final3/monkey_native-0.3.0.dev1-py3-none-any.whl`，67010字节/26成员，SHA-256 `[private fingerprint omitted]`。从源码路径外导入、capabilities与模板/模块字节核对通过，包含双目标Editor薄层及许可，不含私有样本/outputs/tests。构建器固定setuptools84.2.1，临时隔离安装；无全局安装或远程发布。

状态与合同见USAGE能力矩阵，机器总回执`.private/continue02-final-receipt.json`；登记/事务回执在`.monkey`，两轮业务无关更新的diff/preview/apply/postapply回执均在outputs。`.monkey`只存工具运行登记/备份，不是项目记忆后端。

边界：已运行Editor的meta/native输出不自动收编；removed文件保留且记录retained；没有自动删除、任意目录同步、人工代码合并或断电自动恢复承诺。遗留更新锁/恢复状态需先检查journal。Python3.11和Windows尚未实测。
