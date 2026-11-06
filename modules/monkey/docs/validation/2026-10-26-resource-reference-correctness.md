# v0.5 / 05-C 资源与引用：第一组修复

2026-10-26，本地 0.5.0.dev1。依据总监已核验的人类续推指令：turn `[private identifier]` / human `[private identifier]`，事件 `monkey-resource-reference-continuation-20261026-01`。仅修改 monkey，原来源/正式游戏/GREA/beaver 只读。下列代表集验证不等于完整游戏、Player、视觉或业务验收。

| 项目 | 实际变化 | 证据与限制 |
|---|---|---|
| 未解析 MonoBehaviour 的已知引用 | 独立读取原生基础头，保留 `m_GameObject` / `m_Script` PPtr；正文仍是 unparsed，引用覆盖明确为 native-prefix-only | 36 对象补回 72 处 PPtr 字段（69 个非空、3 个空引用），与原始字节按偏移独立读取一致；1567 个原成功对象字段及全部原对象 hash 不变。不生成正文或字段写回载荷 |
| Unity 派生动画文件名 | `_normal.anim` / `_pressed.anim` 进入统一分配器，对完整文件名计 64 字节；分配记录支持命名预览重放 | 冻结样例项目 776 个控制器 / 1552 个派生片段，仅 2 个超长路径改变；控制器路径和其余 1550 片段路径不变。实际受影响路径在 Unity 6000.6.2f1 创建、保存、独立进程重开，GUID、5 个状态/参数、3 轴缩放曲线与动作引用通过 |
| Creator Tiled | 根据原尺寸、原边框和原生 SizeMode 计算几何；生成候选局部 `BATCHER2D_MEM_INCREMENT` 设置。越过安全上限的几何明确拒绝 | 冻结样例项目 1053 个 Tiled 状态，21 个超过默认 4096 顶点；最大 59892，预算 2106 KiB / 59904 顶点容量。21 个受影响 Sprite、13 个原 SpriteFrame 在 Creator 3.8.8 保存重开，实际顶点/三角形数量、UUID、缓冲分配均通过，最终静态/Editor 验证零诊断。叶节点隔离探针不覆盖整游戏层级/动态业务 |
| Unity 紧密图集 | 原叶 Prefab 验证器增加精确 `settingsRaw=65` 子集；沿已冻结源路径→目标 GUID 映射找到拼音/规范改名后的资产 | 只支持 Unity 2021.3.30f1 / platform 20、无旋转/独立 Alpha/降采样、平面 float32 位置、空存储 UV 流、单 uint16 三角形子网格及有据 atlas UV 变换。3 个真实 Sprite 的 271 顶点 / 336 三角形与所有 UV 经 Unity 6 API 读回；1 Prefab / 16 字段 / 3 Sprite 引用保存重载通过。不改矩形外框代替网格，不重编码纹理 |

## 调用与兼容性

修复接入既有 `convert` / `plan` / `export` / `verify`，Unity 来源紧密图集沿 `convert --native` 的原生叶 Prefab 路径使用，不增加另一套工程采用器。Unity 的按钮资产工厂是同一份生产 Editor helper；导出与历史布局补丁准备均携带它，重放检查也核对 helper。旧不可变候选和 beaver 交接归档没有改写。

Creator 候选同时携带 `rendererBudget`、局部 `settings/v2/packages/engine.json` 及 `Docs/RENDERER-REQUIREMENTS.md`。**只采用 assets 不会迁入该宏**；消费者须明确审阅并合并项目设置，保留其他配置，不能整体覆盖工程设置。原生 Editor 回执不代表 preview/build/Player 已验证。预算提高不会改纹理、UV、边框或使用替代渲染器。

旧源读取缓存仍按精确 reader/schema/I/O 合同处理。本轮读取器变化不能静默把旧缓存标成新版；本次只重读一个 2,637,008 字节启动输入并复用 7 个确定的 schema bundle，未重跑 601 容器。源启动文件 SHA256：`[private fingerprint omitted]`。

## 验证身份

私有证据根 `.private/v050-resources-20261026/`，原件/游戏资源/完整原生日志不进入 Git。

- `prefix-validation.json`：1567→1567 parsed、36→36 unparsed、72 处独立字节核对 PPtr（含 3 空引用）；`remaining-36.json` 保留精确 scriptId/typeHash/原始对象 SHA。
- `clip-path-validation.json` / `clip-native-validation.json`：两次自有 Unity 进程 PID 65996 / 66202 均退出 0 并回收；生产工厂 SHA256 `[private fingerprint omitted]`。
- `tiled-native-01/execution-result.json` / `tiled-final-verification/verification.json`：Creator 自有 PID 64910 已退出；原生候选 manifest SHA256 `[private fingerprint omitted]`。最终检查增加了按原生读回尺寸复算拓扑的拒绝条件，直接复用已保存回执通过，没有再次启动 Editor。
- `tight-native-02/execution-result.json`：`resource_subset_verified`，全部 20 项合同检查通过，自有 PID 68238 已退出 0；输入候选 manifest SHA256 `[private fingerprint omitted]`，验证器 SHA256 `[private fingerprint omitted]`。
- `targeted-tests-final.log`：72 项定向测试通过；覆盖原生头部引用保护、完整名称预算/命名预览重放、局部设置导出、Tiled 错帧/空网格/错拓扑/未分配拒绝、紧密网格异常通道/越界索引拒绝、字段写回保护、现有布局准备消费者。`CreatorScene.js` 语法检查通过。

## 仍未闭合

36 个正文结构缺口仍为 Image 19、Text 10、TMP 三类各 1、自定义 GameLauncher / XGameStartup / ReleaseConfirmBehaviour / ReleaseConfirmBehaviourIos 各 1。基础引用恢复不算正文解析成功；没有精确可信 schema 时继续拒绝正文写回。借用字段仍沿现有独立对照与精确目标身份合同，不因本组改变阈值。

紧密网格 01 正向回执保留；最终增加非有限 UV 拒绝后仅在相同 3 Sprite 子集复验为 02，没有重跑整包。

本轮核对已有 Spine/Shader 清单并抽查 48 份闭包文件 hash，未新装运行时或重导全包：每端 1776 套 Spine 闭包中 1768 套自报 3.8.99，8 套自报 `3.8-from-4.0-from-4.1-from-4.2.43`，不强改版本。Creator 的 1768 套仍只是内置 3.8 导入候选，尚未做此组播放验收；Unity 候选没有 Spine runtime/原生 SkeletonData 接入，不能称已播放。每端 38 个 Effect 的 214 份文件是原 Shader 源程序/说明，尚需目标 profile 转换及材质编译、固定视图验证。明细 `spine-shader-audit.json`。这两项继续实施，不以文件存在替代可用性。

05-B 直接复用 beaver 已完成的本地 0.1.0 验收，不重新跑采用/回滚矩阵。只读核对其 `docs/VALIDATION-v0.1.0.json` SHA256 `[private fingerprint omitted]`、wheel SHA256 `[private fingerprint omitted]`。旧 monkey 兼容入口保留，消费者切换/旧入口退休由交接合同另行闭合。

v0.5 整版仍开发中；正常安装入口保持 v0.4.0，无推送/Release/全局安装。正式样例项目/样例项目工程未写入，没有恢复暂停游戏开发。

计算依据：[Creator 官方批处理/缓冲说明](https://docs.cocos.com/creator/3.8/manual/en/ui-system/components/engine/ui-batch.html)、已安装 Creator 3.8.8 原生 Tiled assembler；[Unity Sprite.vertices](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/Sprite-vertices.html) 与 [Sprite.uv](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/Sprite-uv.html) 用于原生读回。精确支持范围另以本组实际样本证据为准。
