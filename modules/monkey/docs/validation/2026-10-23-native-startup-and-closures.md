# Unity首轮启动及离线差额

窗口事件`monkey-unity-window-20261023-03`获实际许可后于北京时间2026-10-23 12:23:13开始，截止12:35:13；12:25:12提前释放。固定932220d候选Unity manifest `[private fingerprint omitted]`逐项核验，再复制到`outputs/acceptance/v03-structured-01/UnityProject`。执行已安装unity CLI1.0.0-beta.11、Unity6000.6.2f1的`unity run ... -executeMethod MonkeyImporter.ImportBatch`；Editor仅写副本。

实际PID97901在引擎/资源导入前停滞，日志有readonly database、macOS服务Connection invalid、许可token更新不可用；但entitlement已成功解析。采样主线程为NSApplication事件循环。根因仍未证实，不能把token警告直接等同无许可，也不当作转换器导入失败。已向本次PID发送普通SIGTERM，CLI exit6，随后ps确认PID不存在；无SIGKILL、未操作样例项目进程、未重启。总监已收到实际释放报告。import/save/reopen/readback/visual/business均not_run。

证据在上述acceptance目录的`window.json`、`import.log`、`startup-sample.txt`和`preflight/`；日志仅本地忽略区，不进入发行。只读比对GREA `.private/lifecycle-native/lc1-import.log`也有同类启动警告，而`lc1-import-native.log`进入COMMAND LINE与Initialize engine阶段。正常缓存/IPC执行权限是值得验证的线索，不是已证实根因；下一轮需新资源许可，并走正常执行审批申请本地缓存/IPC访问，不改安全设置、不拷认证。GREA真实成功仍不等于monkey通过。

离线差额：

- Unity独立源Prefab计划按source图边界输出，验证根唯一/节点内部引用，Scene排除；薄层保存后原生加载核对节点/缺脚本、写source→path→GUID回执。对冻结IR的规划复算得到1630份/20305节点，无边界诊断；2个源Scene共300节点继续由Scene路径管理。此前坏图隔离不进入规划。此计数是计划，不是1630份原生已保存Prefab。
- Spine显式31资源依赖闭包复算，30 closure_recovered、1 SPINE_NATIVE_MISSING（`gameAsset:[private identifier]`）。真实可辨二进制头为3.8.99；原bin/atlas保留，ASTC按明确textureNames/UUID解为PNG页面。`.private/spine-closure-check-02/Analysis/spine-closures.json`为证据；第一次验证因Analysis父目录缺失失败，修复后另建02，未删除原01。没有安装/复制runtime，不宣称播放或原生Spine组件可用。
- `preflight`只读核验候选与日志，不启动Editor、不写全局缓存。真实冷启动日志分类为疑似宿主缓存/IPC和token更新warning；宿主实际写权限/IPC不探测，根因置信度inference。
- 新输出保存包级源码恢复、reader、normalize、两目标plan、emit阶段算法签名；续跑拒绝算法未知/变化，且在归档前结束，避免把当前签名补到历史缓存。缓存列表缺失项/原清单hash已汇总到包级report.cacheInputs。

定向验证：新增3项图边界/Spine缺依赖/启动日志误判反例通过；structured3项（含标准目录独立Prefab指令和算法变化拒绝）及package6项通过。新增Unity薄层离线C#编译通过`.private/source-prefab-compile-01`，无引擎启动。新功能没有覆盖写入932220d冻结候选或acceptance副本；完整新整包生成和新原生Prefab/Spine导入仍not_run。

## 新整包和公开续跑回归

随后在`outputs/structured-sample-game-04`全新执行双端CLI，输入仍是同四根5097文件/243799340字节；新算法签名随输出记录。两目标均实际包含30份Spine闭包/1缺失报告，Unity import-plan实际含1630份独立Prefab计划。

复查补充克隆根节点的局部RectTransform保留，避免从预览父级脱离时继承世界变换。第一次局部修正离线编译在`.private/source-prefab-compile-02`因将GameObject直接当RectTransform失败，改为明确GetComponent后03编译通过；未启动引擎。公开`convert --resume ... --input-set ...`完成二次生成，journal=completed，缓存阶段复用、旧项目归档，最新emit算法身份与实际源码一致。

当前Unity manifest `[private fingerprint omitted]`，Creator manifest `[private fingerprint omitted]`。实际生成的根克隆适配器已包含正确RectTransform类型与局部值复制；仍需真实原生回读才能验证几何结果。缓存缺失汇总另补1项包级集成反例通过：本地映射缺文件进入report，未请求URL。冻结03不修改。

最新04两端静态verify均0诊断，证据`outputs/structured-sample-game-04-unity-check`和`outputs/structured-sample-game-04-cocos-check`。再次回读03冻结manifest与原SHA相同。上述静态检查和离线编译不将本轮启动not_run改写为原生pass。
