# 窗口04与批量导入修复

窗口04获明确grant后，北京时间12:42:12实际接管，截止12:54:12；独立副本`outputs/acceptance/v04-structured-01/UnityProject`固定原04 manifest `[private fingerprint omitted]`。本次`unity run`通过正常exec审批获本地缓存/IPC访问，实际PID8690，Unity6000.6.2f1进入COMMAND LINE、引擎初始化和资产导入；没有重现readonly database警告。这证明本次正常权限路径越过启动阻塞，不把之前推断升级为对所有机器的根因结论。

到期未完成。12:54:08前核对PID完整工程身份后普通SIGTERM；12:54:24 ps确认该PID不存在（确认发生在截止后12秒）。期间仅等待并核对退出，没有继续试验、SIGKILL或操作样例项目进程。CLI exit6因SIGTERM。window.json记录partial、import partial、sourcePrefab0、scene/save/reopen/readback not_run；无致命异常、原04冻结SHA回读不变。原始日志仅本地忽略区且权限600，报告使用脱敏`import.redacted.log`；不把CLI自动注入认证字段复制进产品或报告。

## 实际瓶颈

脱敏日志记录22504次Imported事件、10954个唯一GUID（包含引擎/包/重复导入，不是22504份资产），11552次Asset Pipeline Refresh，报告的Total字段累计673.36秒。该累计可能含嵌套，不是独立CPU计时；但源代码与同一GUID反复导入一致：每纹理先ForceUpdate、SaveAndReimport、再ForceUpdate，造成逐项刷新。3849个GUID已各出现4次Imported，仍未走到原生Prefab保存。

## 离线修复

Unity薄层改为128项一批：先同步确保已存在Importer；批内WriteImportSettingsIfDirty并排队一次ImportAsset，finally保证StopAssetEditing；批次结束同步Refresh并加载每个真实Sprite，null仍报错。未完成的资产不在暂停导入期间加载。源Prefab目录创建/刷新移至循环前，保留每份Prefab原生保存和重开验证。

依据官方API：[StartAssetEditing](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/AssetDatabase.StartAssetEditing.html)、[WriteImportSettingsIfDirty](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/AssetDatabase.WriteImportSettingsIfDirty.html)。本次编译使用已安装6000.6.2f1程序集；官方说明不等于本机批量导入实测。

增加Editor阶段进度`Analysis/native-progress.json`：schema1、planSHA、阶段、processed/total、elapsedSeconds、status及nativeResumeSupported=false。可显式使用MONKEY_NATIVE_BUDGET_SECONDS（1..3600）或MONKEY_NATIVE_DEADLINE_UTC；批次/阶段安全点检查，到限写budget_exhausted，清理本次独立创建的Scene，不全局保存或操作其他场景。同步资产导入/引擎初始化期间不能硬抢占，宿主仍须监控总窗口和真实进程退出；默认未设预算时保持完整导入。进度不是编辑器回读，也不是允许原地重跑的恢复收据，已有Scene/Prefab仍create-only拒绝。

`preflight --progress FILE`核验schema、枚举、计数/有限耗时、精确import-plan SHA；即使completed也只标reported_unverified，不能替代原生回读。日志有导入却无完成标记时明确NATIVE_IMPORT_COMPLETION_NOT_RECORDED。未来原生接续必须核验阶段产物/所有权并处理部分Scene/资产，不凭进度数字跳过；本轮没有冒称已实现原地native续跑。

离线检查：新增进度身份/计数/状态和缺少完成标记反例，4项边界测试通过；Unity新薄层离线C#编译03通过（无Editor启动）。窗口04副本和冻结04不写入修复。批处理耗时改善、正常保存/重开、几何与源Prefab/Spine原生验收仍需新的实际窗口许可，当前未验。

## 修复候选05

全新`outputs/structured-sample-game-05`双端整包生成completed=true/needs_action，5097文件/243799340字节逐项留存相等；含1630独立Prefab计划和双端30 Spine闭包/1缺bin。实际Unity脚本包含128项批处理、finally恢复导入、阶段进度与显式预算检查；当前emit源码身份与报告相同。Unity manifest `[private fingerprint omitted]`，Creator `[private fingerprint omitted]`。原04冻结manifest再次核对不变。

05仍没有启动Editor；修复原生性能/保存/重开均未验，不用04的部分资产导入替代05通过。
05两端静态verify均零诊断，证据`outputs/structured-sample-game-05-unity-check`及`outputs/structured-sample-game-05-cocos-check`。该检查不启动Editor，不构成批处理实际加速或页面通过。
