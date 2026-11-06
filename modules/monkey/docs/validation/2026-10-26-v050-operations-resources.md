# v0.5 原生资源代表与操作基础验收

2026-10-26，本地 0.5.0.dev1。延续 05-A/C/D，只改 monkey；采用实现已冻结交 beaver，不重测已接收的采用矩阵，不修改正式游戏或恢复暂停项目。第一组资源证据沿用 [既有验收](2026-10-26-resource-reference-correctness.md)。本组完成不等于 v0.5 全部出口通过。

## 本地交付索引状态（裁定补记）

事件 `monkey-v05-local-restricted-delivery-20261026-01` / MONKEY-V05-LOCAL-EXIT (local path omitted) 接受 `acceptedDelivery=local_declared_subset`。原全范围 `versionComplete=false`、`originalScopeComplete=false` 与以下全部未完成项保持。该补记只整理状态，不新增验证结论。

沿用产品源码 `[private fingerprint omitted]`、原验收收据 `[private fingerprint omitted]` 以及下列同 SHA 的 wheel/sdist；没有重测、重导、重构建、启动引擎或更换日常安装。机器交付索引 `.private/v050-continuation-20261026/delivery.json` 增补裁定字段，原制品身份不变。

继续恢复的输入以逐对象 blocker 为准：匹配 `2021.3.30f1` / platform20 / scriptId / typeHash 的可信 schema/原程序集及匹配依据；字段写回另需独立原字段值与精确目标 GUID/localId/hash。没有这些输入时等待，不循环尝试，不自动启动 v0.6。

| 内容 | 实测结果 | 限制 |
|---|---|---|
| 显式资源补取 | 1～3 次瞬态重试，404/哈希不符不重试；旧完整请求集合/清单/input-set 精确绑定，成功载荷重哈希后进入新层；篡改拒绝 | 只支持已结束的 partial 收据续接，不支持崩溃 journal 或 Range 下载；本轮用自有 HTTP 夹具，未补取原版 CDN |
| 统一诊断 | 源容器 SHA / serialized file / pathId → 已有确切目标记录、影响/动作；36 正文逐项隔离、70 个借用树对象的字段写回门独立；URL 查询信息脱敏 | 不解析原包、不启动 Editor、不重新核验全部目标字节；预算截断/延后可见；历史来源限制和新代表观测不自动相互覆盖 |
| 环境/空间 | 本机 Python/固定依赖/显式 Unity6000.6.2f1/Creator3.8.8/provider 元数据通过；空间预览不删除、保留原件/人工/当前资源，符号链接不跟随 | 元数据就绪不是 Editor 连接或项目成功；逻辑空间不等于可释放物理空间；未装新依赖到全局 |
| Creator Spine | 标准 3.8.99 二进制 Goose16、JSON Catclawaperture 各 1 份：原骨骼/atlas/页图字节与 meta，保存重开 UUID/页名/原生纹理，AnimationState 0→0.125 秒、真实骨骼 world transform 变化，0 诊断 | 分别 55/24 骨骼、60/12 slots；最小资源工程无原游戏层级/业务，未做像素对比，其他 1774 份不外推 |
| Unity Shader | 仅精确 builtin-2d-sprite / 固定 USE_TEXTURE 子集；ShaderUtil 无 error，导出 .mat 的 GUID 引用保存重导保持；Metal RenderTexture 单像素误差 0.0017156899 ≤ 0.018 | CPU oracle 依据精确源 Sprite 默认 blend；不是直接 Cocos 帧比较、全 UI 或其他宏/37 Effect 验证，不自动绑定游戏材质 |
| CLI/分发 | acquire-resources / diagnose / doctor / space-preview / resource-probe 接入；ShaderLab、JS/C# helper 进入 package-data；macOS wheel/sdist 159 产品文件与源码逐字节一致；隔离安装 13 CLI 检查/159 文件哈希通过 | 稳定安装 0.4.0 不动；Linux/Windows、Python 3.11 CI 仅定义，未实际跑远端矩阵 |

## 身份和过程

证据根 `.private/v050-continuation-20261026/`，游戏资源和原生日志不入 Git。

- `spine-validation.json`：源候选 manifest `[private fingerprint omitted]`；第二轮探针 manifest `[private fingerprint omitted]`。Creator child 58759 在 native_completed 后受控回收（exit -15，非引擎自然 exit0），CLI 返回 candidate、读回通过。第一轮仅时间推进、姿态 false 的证据保留；修正为原生 state.apply/native model.updateWorldTransform 后新轮通过，不覆盖旧结论。
- `shader-module/native-receipt-v7.json`：Shader SHA `[private fingerprint omitted]`；result SHA `[private fingerprint omitted]`；Unity exit0。首轮 C# enum 编译失败后退出，离线修正/SDK 编译后新窗口执行。日志只保留脱敏身份，不复制启动环境/凭据。
- 透明混合复核后从初版 `One` alpha source factor 修正为精确源 Sprite 默认 `SrcAlpha`；旧 `shader-public-cli` / `catalog-integration` 已标记 superseded。`shader-public-cli-final` 和 `catalog-integration-final` 重新由公开 CLI/catalog 生成，核到与原生 v7 一样的 Shader 字节，6 原生产物、5 原源文件、2 原生路径映射，Unicode namespace 通过；复用原生语义证据，未重复启动 Editor。
- `affected-tests.log`：46 项相关回归通过。`final-guards.log`：最后 12 项（含前组重复 guard 与新增 Shader 拒绝反例）通过，不把重复用例加成独立总数。Shader 模块标准 unittest 4 项和 SDK 编译证据复用其交付。JS 语法检查通过；未重跑 601 容器/全量导出/原生采用矩阵。
- 样例项目诊断显式提高预算后读取两份既有证据 60,479,267 字节、35,965 条 issue，0 omitted；它们包含来源路径映射缺口和汇总，不能称作新增 35,965 个资源损坏。样例项目同样读取 5 文档 116,589,028 字节，40,000 发出/1,490 omitted，明确 complete=false；这是选定历史回执索引，不是新的全游戏核验。

## 版本真实阻断

19 Image、10 Text、3 TMP、4 自定义组件仍缺精确 `2021.3.30f1` / platform20 / scriptId / typeHash 正文 schema。`source-schema-blockers.json` 逐项保存源 SHA、原对象身份、类型与 requiredSchemaIdentity。头部 PPtr 已保留，但正文和字段写回仍拒绝；需要可信精确 schema/对应原程序集以及独立字段对照，不接受 Unity6/同名类/近似树替代。

8 份非标准 Spine 版本原样隔离，Unity Spine runtime 未安装/未验，其他 Shader 继续保存源。完整业务、Player、微信分包/构建、全视觉一致性和消费者切换不属于本组已验证结果。v0.5 仍未完整验收，不发布或替换日常安装。

## 本地分发身份

从不可变产品提交 `[private fingerprint omitted]` 构建，后续验收文档提交不替换该源码身份：

- wheel：575981 字节，SHA256 `[private fingerprint omitted]`。
- sdist：847047 字节，SHA256 `[private fingerprint omitted]`。
- 159 个 product 文件在 Git 源快照 / wheel / sdist / 隔离安装之间相同；MIT 元数据及新增 Shader/JS/C# 模板齐全。macOS arm64 / Python3.14.7 的 13 CLI 检查通过，临时工作目录在 checkout 外。首次构建启动脚本误 resolve venv Python 符号链接，导致找不到 setuptools、0 制品；保留失败日志，改为使用原 venv 入口后成功，未安装全局 backend。
- `delivery.json`、`distribution.json`、`package-audit.json`、`installed-smoke.json` 在上述私有证据根，159 安装文件再核哈希通过。验证结束只读主进程清单为空；日常 `monkey --version` 仍为 0.4.0。没有发布、推送或全局安装。
