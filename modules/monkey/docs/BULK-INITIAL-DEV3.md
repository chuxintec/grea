# dev3 本地批量初版交付

本轮先把明确取得的全集导出为可接续工程，再由游戏开发 Agent 实现业务。版本为本地 0.2.0.dev3，未推送或发布；源版本仍按已验证 profile 判断，不宣称所有引擎/版本无损自动转换。

## 样例项目初版

工程：`outputs/bulk-sample-game-native-01/UnityProject`。manifest SHA256：`[private fingerprint omitted]`。

92434文件、3486088823字节。1694源Prefab/24480节点、main与room16_test两个源Scene/300节点、16934 Sprite/8467源帧、7756 Sprite PPtr；实际GUID/local fileID、importer、几何、源引用合同均在`Analysis/native-identity-contract.json`。room16_test仍是原测试场景，小游戏Scene明确排除。代码为914具名模块、10607方法及10391字段声明初稿，0方法实现。

冻结后独立`verify --level editor`零诊断，证据`outputs/bulk-sample-game-frozen-check-03`。SHRINK要求同字体GUID/文本/字形、autoSizing/min/max/实际字号，glyph在实际字号下推导并保持固定原生margin，几何阈值仍为0.03。最初5fail、增量01/02失败/partial、中间4几何诊断及16630源限制分别保留；不是追认旧失败为成功。Player/业务/视觉仍not_run。

## Unity来源初版

工程：`outputs/bulk-sample-project-handoff-03/UnityProject`。recovery manifest SHA256：`[private fingerprint omitted]`。

163473文件、3252286957字节。原始887文件逐项保留原字节，7595已取得纹理均保留，含13未引用原件。601容器复用原typed，7626纹理对象有据水合，426对象来自425确切HTTP404键，原始对象/包保留、PPtr不虚构替代。

一次AssetRipper实际导出133003文件、1382299527字节；加入53有文件签名证明的原始媒体后，资源文件65362、唯一GUID65309、唯一内容hash64476、重复GUID0。53新增媒体GUID待Editor；源路径精确映射57346/63302，5956未映射、975未解析、1992 provider占位引用保留待修。

13个有据字段类/57字段，已用本机Unity6官方程序集离线编译通过，证据`.private/bulk-sample-project-field-compile-01`；这不是Editor导入证明。原始包/Wasm/metadata、248份额外原件/代码证据和20129个具名元数据声明初稿均在工程中；20181类型、138243方法签名、124060字段声明不代表方法已实现（实际0）。Editor/Player/业务/视觉not_run。

## 公开命令

所有输出必须使用新目录；再次生成不得覆盖当前初版或游戏工程。固定provider版本/输入SHA，先原始声明和缓存补取，后准备、独立限时导出、组装。中断后准备阶段用相同job的`--resume`，已明确404不重试。

```sh
monkey inspect-unity --source "$MONKEY_SOURCE" --bundle-manifest "$MONKEY_BUNDLES" --provider-python "$MONKEY_PROVIDER_PYTHON" --out "$MONKEY_INSPECTION" --budget-seconds 600
monkey acquire-unity-textures --inspection "$MONKEY_INSPECTION" --cache-manifest "$MONKEY_ORIGINAL_TEXTURES" --cdn-source "$MONKEY_LITERAL_CDN_SOURCE" --cdn-root "$MONKEY_DECLARED_CDN" --out "$MONKEY_CAPTURE" --budget-seconds 1200
monkey prepare-unity-bulk --inspection "$MONKEY_INSPECTION" --texture-cache "$MONKEY_CAPTURE/textures.json" --capture "$MONKEY_CAPTURE/capture.json" --provider-python "$MONKEY_PROVIDER_PYTHON" --out "$MONKEY_PREPARED" --budget-seconds 1200
monkey export-unity-bulk --prepared "$MONKEY_PREPARED" --asset-ripper "$MONKEY_ASSETRIPPER" --out "$MONKEY_PROVIDER_EXPORT" --budget-seconds 1200 --deadline-utc "$MONKEY_INTERNAL_UTC" --window-end-utc "$MONKEY_OUTER_UTC"
monkey convert --source "$MONKEY_SOURCE" --source-family unity --target unity6 --provider-python "$MONKEY_PROVIDER_PYTHON" --asset-ripper "$MONKEY_ASSETRIPPER" --unity-export-scope all --unity-dependency-manifest "$MONKEY_BUNDLES" --unity-reuse-inspection "$MONKEY_INSPECTION" --unity-texture-cache "$MONKEY_CAPTURE/textures.json" --unity-prepared-textures "$MONKEY_PREPARED" --unity-reuse-provider-export "$MONKEY_PROVIDER_EXPORT" --unity-code-evidence "$MONKEY_CODE_EVIDENCE" --out "$MONKEY_INITIAL"
monkey freeze-unity-handoff --candidate "$MONKEY_INITIAL/UnityProject" --texture-cache "$MONKEY_CAPTURE/textures.json" --source-manifest "$MONKEY_ORIGINAL_MANIFEST" --source-root "$MONKEY_ORIGINAL_ROOT" --expected-manifest "$MONKEY_INITIAL_MANIFEST_SHA" --out "$MONKEY_FREEZE_JOURNAL"
```

这里的变量均是调用方明确配置的源路径/清单/UTC窗口，不进行根地址、CRC、版本或脚本身份猜测。AssetRipper阶段至多1500秒，外部窗口至多30分钟；CLI绑定绝对截止并按剩余时间缩短。两个Unity来源组装失败层01/02保留；修复只裁剪代码模型所需字段、按原字节与字段等价合并重复MonoScript，未重解析600池或重跑provider。

样例项目的追加链为`code-handoff --apply-owned`、`native-finish-plan`、`native-finish --execute`、`handoff --native-contract`、`verify --level editor`、`freeze-handoff --apply-owned`。原生方法`MonkeyImporter.FinishBulkBatch`仅另存两个源Scene并读回5标签，使用原有Library与媒体；受控失败层续接必须显式`--previous-execution`，只接受退出回收且hash匹配、没有已保存源Scene的owned层。当前冻结工程不可再次用旧manifest/旧截止执行。

两初版入口为各自`Docs/BULK-INITIAL-HANDOFF.md`。只交付工具源码/包及本地工程身份，不把私有原件、outputs或大缓存写入发行包。完整输入、去重原生资源、原生Editor读回、代码声明、未实现业务和缺口分别报告。

## 本地工具包身份

源码提交`[private fingerprint omitted]`，tree `[private fingerprint omitted]`。

|制品|字节|SHA256|
|---|---:|---|
|monkey_native-0.2.0.dev3-py3-none-any.whl|453353|[private fingerprint omitted]|
|monkey_native-0.2.0.dev3.tar.gz|610970|[private fingerprint omitted]|

位置`.private/full-project-handoff-01/package/dist`。123产品文件在源码/wheel/sdist逐字节一致，隔离安装无需checkout，6条新命令帮助和能力已读回；安装包重新生成13字段类与实际初版相同，且163473份冻结文件完整哈希复核通过。末次53项定向检查通过；安装验收不等于Unity来源Editor/Player验收。
