# 窗口06与异步资源导入执行层

窗口06于北京时间13:40:34接管，内部截止13:50:34、外层13:52:34；新副本`outputs/acceptance/v06-structured-01/UnityProject`固定4deb5ea及06 SHA。正常exec审批启动PID25790。方法44.5275847秒完成纹理后进入tmp-resources，取得com.unity.ugui 2.6.0 BuiltIn与Essential archive SHA `[private fingerprint omitted]`，但Import与同步Refresh返回后所需文件未生成，抛TMP_ESSENTIAL_IMPORT_INCOMPLETE。

Unity自行exit1、CLI exit6；13:43:56按实际工具时钟确认ps无PID，提前释放。先前报告误填13:43:44，已向总监更正，window.json亦更正。没有信号/重启/其他工程操作，原06SHA不变。sourcePrefab0、Scene保存/重开/回读not_run。证据含window.json、native-progress、tmp-resources及脱敏日志；包路径/身份修复有效，时序尚未闭合。

## 必要执行方式变化

旧unity run固定注入-quit；SDK导入资源后须等待importPackageCompleted，而不能在同一同步方法中发起Import后立即判断Ready并抛异常退出。新方案由已安装Editor支持的batchmode执行且不带-quit，完成/失败/取消事件回到Editor事件循环后再继续。它不改变安全/认证、引擎版本或包许可；正式调用仍需当前明确资源许可及正常exec审批。

C# ImportBatchAsync：先核对Editor/新候选状态、计划SHA和注册包身份；缺必需资源时订阅完成/失败/取消，发起Essential-only Import后返回事件循环。只匹配本次包名，完成通知后delayCall核对计划未变，再同步加载原名shader/settings并继续原生构建。回执记录package-completed-event或preexisting-files，资源存在不等于已加载。退出/异常/预算分支注销全部回调；batch只退出自己所在Editor进程，菜单模式不退出用户Editor。无主线程sleep/忙等，不凭旧阶段跳过。传统ImportBatch遇未准备依赖会明确要求异步入口，-quit变体会被异步入口拒绝。

每秒预算检查覆盖等待阶段，原有同步批次/阶段仍检查内部截止。同步引擎调用仍不可硬抢占，外层宿主独立监控总截止。候选Scene保存后新增正常CloseScene/OpenScene，再收集几何和原生引用；native verify要求sceneReopened回执，尚未实跑。

## CLI native-import

默认只写native-plan/identity，不启动Editor或创建工程副本。显式--execute后：校验冻结manifest及每个文件、拒绝未知/缺失/改动文件、校验异步入口；复制新独立工程。计划绑定源SHA、import-plan SHA、launcher源码SHA、Editor路径及预算/UTC截止，计划/参数变化拒绝复用。已有运行/人工目录不原地重跑。

宿主直接Popen已明确指定的Editor（batchmode、固定ImportBatchAsync、无-quit），不是unity CLI外包进程；因此持有真实Editor PID。只注入MONKEY预算/截止，不输出环境或认证参数，日志权限600并生成脱敏副本。外层到期前30秒或收到操作中断时只terminate自己创建的子进程，不发SIGKILL或进程组信号；等最多30秒，仍存活则NATIVE_EXIT_PENDING/requiresAttention并保留PID，不声称释放。进度无效、子进程成功退出但无完成/回读也不会成功；完成后运行既有editor verify，来源缺口仍partial。

本次仅macOS现有工具链离线检查；没有用新方式启动Editor。直接Editor模式的许可/回调/保存实际结果仍待新许可。原地native resume仍不支持。

## 定向验证

新增3项launcher边界测试：真实CLI默认不调用Popen/不创建Project；冻结文件变化拒绝执行；模拟外层到期仅terminate自己持有的child且无kill、保留副本且拒绝复跑；非法时间合同在输出前拒绝。模拟进程不是引擎成功。structured3与边界4通过，SDK C#离线编译05通过；不重复旧reader/Creator矩阵。

## 新候选07与启动计划

固定emitter实现08d5e98，新Unity单目标`outputs/structured-sample-game-07/UnityProject`，manifest `[private fingerprint omitted]`。同5097文件/243799340字节留存相等；仍1630独立Prefab计划、30 Spine闭包/1缺bin。emit身份与当前代码一致，Unity本次有变化的静态verify零诊断，证据`outputs/structured-sample-game-07-unity-check`，原06SHA再次核对不变。

实际执行native-import默认规划，`outputs/structured-sample-game-07-launch-plan-01/native-plan.json`返回planned/processStarted=false，未创建UnityProject。其中未来时间仅作离线规划检查，不是资源窗口或启动许可；新grant后使用新的实际截止与新目录。

宿主IO错误也会普通终止自己已创建的child，避免日志写入失败遗留引擎；另补模拟journal写失败的反例。当前launcher4项通过，模拟不是实际Unity。此后controller小修与计划源码SHA一起记录，不改变07 emitter制品。没有用新的无-quit执行方式启动Editor，实际许可/完成通知/场景与引用回读仍not_run。
