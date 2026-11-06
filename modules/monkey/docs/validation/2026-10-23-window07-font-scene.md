# 窗口07与字体/场景修复

实际窗口为2026-10-23 14:23:03–14:26:42北京时间。独立PID36070自行exit1并已回收，提前释放；未发信号、未重启、未改样例项目。证据在outputs/acceptance/v07-window.json和v07-structured-01/，冻结07清单SHA保持bc3305c8a624fa03319c6280508c71738dee9a42a9f0604c06cb8474f55c77e3。

异步TMP Essential导入首次观察到package-completed-event，实际2.6.0包及原名三个shader/TMP Settings均加载、GUID回执ready。此为有限依赖gate通过，不代表字体、Prefab或工程通过。

方法45.90秒失败：bitmap TMP字体SerializedObject.Apply触发OnValidate时material尚未赋值，Unity记录UnassignedReferenceException；随后批处理干净无名初始Scene禁止Additive创建。进度hierarchy0/20605，sourcePrefab0，Scene保存/重开/readback未运行。

离线将原Bitmap Custom Atlas材质先绑定字体，再触发序列化校验；保留原shader、atlas与字形。独立batch仅替换自身干净初始无名场景，菜单模式拒绝用户无名/脏场景；已有已保存场景仍用Additive。自身唯一场景以OpenScene Single正常重开。新增捕获Unity Error/Exception/Assert并于安全点停止，脱敏回执只存hash/phase/planSHA，防止已记录错误后仍推进。

.private/font-scene-compile-01/report.json为当前SDK C#编译pass，无Editor执行。真实修复效果、字体/native Prefab/Scene保存重开仍待下一实际资源grant；不复用窗口07。

08已通过真实CLI新生成Unity单目标：outputs/structured-sample-game-08/UnityProject，emitter e1eeb74，manifest SHA [private fingerprint omitted]。5097/5097文件与243799340字节全部入账；状态needs_action/candidate，convert按合同exit1。Unity静态verify exit0/零诊断，11项受影响检查通过；SDK编译source SHA与当前C#一致，07冻结SHA不变。没有新Editor执行。准备按monkey-font-scene-fix-20261023-01报告成果并申请新独立窗口，原生修复效果/Prefab保存/Scene重开仍待验。
