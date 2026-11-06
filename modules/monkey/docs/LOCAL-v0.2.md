> 发布更新：用户已授权将既有分发02发布为 `v0.2.0.dev1` GitHub prerelease。下文“未发布”等为本地验收时的历史状态；本次制品不重建，最新说明见 [发布说明](RELEASE-v0.2.0.dev1.md)。

# v0.2 本地候选与分发验收

2026-10-24，总监已确认 **v0.2声明支持范围的本地工具交付验收通过**，依据总监本地验收决定 (local path omitted)，事件monkey-v02-director-local-acceptance-20261024-01。总监独立核对分发02两包大小/SHA、4份回执SHA与106包文件等于源码；原生记录和隔离安装证据复用，不重打包或重验。

版本仍为 `0.2.0.dev1`，未正式发布；本轮开发结束，保留成果，后续等待用户反馈或明确发布指令。不推送/tag/Release，正式v0.1保持冻结。47份其他布局guard、Spine/Egret源UI、缺模板及未知方法等限制保持逐case记录，Player逐帧、原版视觉/输入/完整玩法仍not_run；本地验收不表示全部引擎/布局或完整游戏恢复。

第一轮分发01作为历史认可记录保留；最新分发02见[续修分发回执](validation/v02-local-delivery-followup.json)，实际布局证据见[有限续修](validation/2026-10-24-layout-followup.md)。机器回执中的pending-director-review是生成时状态，当前结论以上述总监验收决定为准，不反向改写回执。

## 一条命令

```sh
bin/monkey convert --input-set /path/to/inputs.json --target both --out /path/to/fresh-output --offline
```

Cocos目标可选unity/cocos/both，其他源引擎统一unity6；默认格式none，显式 `--format grea` 在新输出应用typed迁移。使用已登记精确URL/版本/哈希获取远程文件时，按USAGE的acquisition manifest接入并去掉offline；未知CDN地址不猜。原生导入需独立新副本、确切已安装Editor及明确执行授权；静态候选不等于已可玩。一般partial退出1，调用者读取conversion-result.json，不能把exit1一概视为没有输出。

当前可执行范围及必要依赖见[USAGE](USAGE.md)、[支持矩阵](SUPPORT-MATRIX.md)、[逐case机器状态](validation/research-v02-status.json)。ASTC需已声明的可选 `texture2ddecoder==1.0.6`；Unity专用来源需既有固定provider。安装包不包含引擎、第三方provider二进制、原包、CDN资源或验证输出。

## 已闭合的版本要求

- 统一原包/输入集获取、逐文件字节台账和来源隔离，未知格式/方法保留明确限制与接续入口。
- Cocos3.8.7模板DAG、嵌套实例、局部ID和override，以及真实动态Label/Widget/Layout状态变化，两端原生代表闭环；布局集成同时核对资源与生命周期。
- 样例项目3.4.1专用资源/节点/位图字库/实例reader接公开双目标：同11962文件输入，7071帧、15字库、856图、22503节点、52关系。1份null旋转图拒绝猜值。实际新增7节点/1Widget两端原生表、模板对应与保存重开均闭环。
- 有原文证据的NumberLabel C#/TS优先/JS次选代码及实际绑定、新来源Parabola数值方法；unknown/异步/受保护方法不伪造实现。
- 默认none及可选grea保留typed身份/引用/动态key与人工边界；受影响既有证明复用，不重开全部游戏。

## 第一轮分发01与安装结果（历史认可）

源码提交 `6deb03e`，从228个Git登记文件的独立新快照构建。wheel共109条目、源码包226条目；全部104个包载荷文件逐字节匹配源码，源码包解出后重建wheel载荷一致。两包无.private/outputs/游戏文件/引擎或原生DLL。机器回执：[v02-local-delivery.json](validation/v02-local-delivery.json)。

制品在 `.private/v02-delivery-01/dist/`：

|制品|字节|SHA-256|
|---|---:|---|
|monkey_native-0.2.0.dev1-py3-none-any.whl|393326|[private fingerprint omitted]|
|monkey_native-0.2.0.dev1.tar.gz|598875|[private fingerprint omitted]|

在全新私有venv实际安装wheel及原固定Pillow12.2.0；离线缓存未命中后仅从官方PyPI获取该固定版本，没有全局安装。Python3.14.7，仓库src不在sys.path；从独立cwd运行安装后的8条CLI，none/grea各双目标，四份静态verify均通过，输入哈希不变。最低声明Python3.11未另装解释器验证。ASTC extra和Unity provider没有纳入本次最小安装smoke。

完整230项工具检查通过，受影响49项通过，另25项最终接口定向检查通过。已通过的真实Editor helpers与包内代码字节相同；未为打包重复启动引擎。source archive重新发现仍11例、10例不同范围输出、1例团结blocked、完整游戏0。原版视觉/真实交互/存档/业务、未覆盖格式和方法各按机器状态保留，不能用这些测试数替代游戏验收。


## 有限动态续修后的分发02

源码快照 `0a523d5`（实现df68c59），235个登记文件；wheel 398326B，SHA `[private fingerprint omitted]`；sdist 609147B，SHA `[private fingerprint omitted]`。在 `.private/v02-delivery-02/dist/`，旧01不覆盖。106份包载荷逐字节匹配源码，sdist重建wheel载荷相同，无原包/游戏图片/outputs/引擎二进制。

新私有venv从项目缓存离线安装本地wheel与固定Pillow12.2.0，独立cwd8条安装后CLI包含缩放Grid+child-resize合成输入，none/grea各双目标、4份静态验证通过，原输入SHA不变、仓库src不在sys.path；新Flow组件及完整MIT许可已确认随包和生成工程保留。实际原生6组/54态和232工具测试通过。布局helpers与实际最终代表字节相同，Grid02仅后增许可头、源码体一致。声明范围本地交付现已获总监验收；不推送/发布，Player时序/视觉/玩法和其他组合保留限制。
