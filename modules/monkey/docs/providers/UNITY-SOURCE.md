# Unity来源 Provider 合同

当前解析预算与字体/大索引块格式见 [UNITY-PARSE-BUDGETS](UNITY-PARSE-BUDGETS.md)。旧 975 未解析项不能统称“无结构”；其预算问题与类型读取失败分别统计。

目前仅明确本地UnityFS/UnityRaw/UnityWeb及UnityWebData1.0主文件和显式依赖→Unity6候选，不代表wxapkg整包、APK、serializedFile及全部源版本已支持。`inspect-unity`可单独检查UnityPy能读取的显式文件；转换只接受精确bundle或UnityWebData1.0签名。Unity 来源请求 Creator/both 会先拒绝。显式清单 remote/input-set 及受限叶 Prefab 的 native 入口见当前 CLI 帮助与 UNITY-SOURCE-NATIVE.md；不宣称整包原生验收。

```sh
monkey convert --source /path/to/file.ab --target unity6 --out /path/to/new-candidate \
  --provider-python /path/to/existing/python --asset-ripper /path/to/existing/AssetRipper.GUI.Free \
  --dependency-source /path/to/exact-dependency.ab --unity-texture-cache /path/to/cache-pool.json
```

自动按bundle或UnityWebData1.0签名识别Unity，或明确`--source-family unity`。Provider不自动安装：现有Python须UnityPy1.25.3；AssetRipper精确2.0.0+[private fingerprint omitted]，实际首行产品前缀一起核对。Core不import GREA。独立worker只读源bytes，不跟随源目录的DLL/缓存/外部PPtr；TypeTree严格check_read，不使用宽松长度模式。ID为signed64十进制字符串，未解析对象/原始bytes hash保留；嵌入MonoBehaviour schema可恢复具名C#字段，但不包含原方法体。

AssetRipper只复制精确现有可执行文件和固定capstone伴随库到自有目录，版本/二进制SHA留收据；只绑定127.0.0.1随机端口，代理/跨域redirect关闭，不打开浏览器。使用公开Settings/LoadFile/Export/UnityProject接口，先回读TargetVersion6000.6.2f1、Level0、原Shader YAML、TextAsset bytes。设置文件和日志仅自有runtime；命令成功必须302完成redirect，HTTP200错误页不算成功，实际项目/版本/文件hash还需核对。固定总预算和正常TERM/reap，无SIGKILL。

公开接口依据（非代码复制）：AssetRipper2.0.0官方`GUI.Web/Pages/Commands.cs`、`Pages/Settings/SettingsPage.cs`、`WebApplicationLauncher.cs`与`Export/Configuration/SerializedSettings.cs`。运行副本避免默认settings路径写入GREA安装目录。不执行原DLL/JS/Wasm或原游戏方法。

目标工程把原始/Provider空壳源码隔离SourceRecovery；只有已证明字段结构的C#能替换对应Provider空壳，保留脚本meta GUID。未支持类型不生成any/object替身空壳；没有字段/方法的类不另发相同模板。旧VR模块在精确目标内不存在，明确移除并保留原包清单和迁移收据；未知功能不宣称恢复。Provider的deadbeef缺依赖GUID保留诊断，不能当有效引用。恢复manifest与原件hash独立。

## 首批实际证据

- 样例项目启动UnityFS2637008B：1603对象/1497严格parsed/106MB类型缺失；4个Texture2D只有外部资源键令牌，公开convert实际blocked、Provider未启动。原始全资料尚未转换完成。
- 3个带TypeTree远程Bundle严格读到1947对象。独立3122B代表Bundle经公开convert生成Unity6候选，原Prefab1、FrameSpritePool具名16个Sprite数组字段；原空壳隔离，3个外部Sprite引用仍缺。C#只程序集编译通过，方法实现0，不能当业务恢复。
- outputs/unity-source-convert-02/UnityProject/recovery-manifest.json SHA0adf7fe360c1942fc1a92e418125b6b1a6018ca81800be1832a2aa1a6fd680d6。
- 原生只读probe01 own65810 17:59:26Z→17:59:33Z exit1/reaped；Prefab几何/根GUID可读，MissingScript计数0但预期schema组件未识别，严格失败，未保存/集成。编译通过不追认为组件注册通过。

## 显式依赖和缓存（新增实证）

`index-unity --manifest frozen.json --provider-python PY --out fresh`只从schemaVersion=1/files[{path,bytes,sha256}]清单读对象表/外部表，最多2000文件、合计1GiB；不是对象正文解析或全盘发现。PPtr按当前serialized文件的外部表与精确CAB/pathID匹配，重复CAB歧义不猜。

`hydrate-unity --source file.ab --texture-cache pool.json --provider-python PY --out fresh`接受schemaVersion=1/files[{logicalPath,path,bytes,sha256}]。当前仅Unity2021.3、单mip、单2D图的明确外部键；从`Assets/Textures/astc/<max-dimension>/<exact-key>.txt`精确读取ASTC，无网络发现或近似同名替换。验证原始hash、ASTC块/尺寸/长度，固定texture2ddecoder1.0.6一次解码BGRA→RGBA（不翻转），派生bundle写RGBA32。原CAB/pathID和全部非纹理对象raw hash保持；任何缺失阻止派生输出与后续Provider。

convert可重复`--dependency-source`，仅依赖清单及实际消费的缓存计入输入，复制原始证据至SourceRecovery。未知原程序集仍隔离，不因依赖齐全执行原方法。

- 冻结600个Bundle：600/600索引、79977对象表项、0失败；没有宣称79977对象正文已解析。
- 代表Prefab的3个Sprite PPtr从精确CAB找到，同依赖Bundle内3个纹理键在冻结103文件池中精确匹配。输出候选02实际输入5文件/529624B，deadbeef占位0；manifest SHA `[private fingerprint omitted]`。
- 固定RGBA32策略导出3 PNG与规范解码像素hash全部精确一致。早期隐式ASTC解码比较有最大1 LSB差异，失败收据保留；没有放宽容差或追认旧输出。
- probe02普通C#标识符修正后，类实际注册、16 Sprite[]字段/几何/身份读回通过，3个源依赖尚空，saved=false；旧probe01失败保留。
- probe03独立Unity6副本own67435于2026-10-23T18:40:58.386769Z启动、18:41:04.978708Z exit0/reaped；16项严格检查通过，3个真实Sprite引用、MissingScript0、独立editable Prefab保存/重导/重载及引用身份保持，status=resource_subset_verified。公开convert本身仍只生成候选，此原生段为独立受控验证，不能声称公开`--native`已接通Unity来源。

完整启动Bundle缓存仅3/4匹配：`sharedassets1.assets`/pathID `4`需要`Assets/Textures/astc/512/pangzhijiangsi.a976bf1d.txt`，现有另hash同名不能代用。该轮blocked且未写派生bundle/启动Provider或Editor。启动106MB缺TypeTree、CODEPHPY保护方法、完整场景/视觉/业务及全source archive逐项目输出仍未闭合。

### 精确缺件补齐后的新启动候选

总监事件monkey-sample-project-exact-texture-found-20261024-01提供只GET一次的精确原件。核对原包game.js的DATA_CDN明示地址、逻辑键、65552B/SHA `[private fingerprint omitted]`及ASTC8x8/512x512长度；不以文件名hash算法作未证明的身份保证。私有输入池104项，manifest SHA `[private fingerprint omitted]`。新hydrate02四键全部匹配、非纹理对象hash保持，派生SHA `[private fingerprint omitted]`；旧缺件失败不变。

公开convert startup02实际完成候选：5输入/3554576B，Provider2484文件/11019493B、自有child正常退出/原件hash不变；1173份原/Provider代码隔离，schema恢复0，deadbeef占位0。106MB缺schema与方法体未恢复，原生尚未运行，不能用缺占位0冒称无MissingScript或完整项目通过。

### 精确借取类型树（仅正文读取）

```sh
monkey inspect-unity --source /path/to/startup.bundle --provider-python /path/to/python \
  --schema-manifest /path/to/frozen-bundles.json --out /path/to/fresh-inspection
```

池格式与`index-unity`一致：schemaVersion=1，files中明确path/bytes/sha256，最多2000项、合计1GiB。只借用源Unity完整版本、targetPlatform、非零script_id和old_type_hash全部相同的嵌入MonoBehaviour TypeTree；字段名称相同不足以匹配。完整结构含alignment/version等布局标志参与哈希，同身份不同结构拒绝，不静默选择。正文仍check_read=True，不补零、不忽略剩余字节。报告分列borrowedSchemas/schemaProvenance与源embeddedSchemas，记录池/包/布局SHA和原始对象hash；未知方法不执行或生成空类。

样例项目新公开CLI实测`outputs/unity-startup-schema-inspection-01`：600个已冻结Bundle、27种启动脚本类型中18种匹配，70个MonoBehaviour严格完整读出；总计1567/1603对象，仍36未解析。自有worker77699 exit0/reaped，原包SHA不变，typed snapshot SHA `[private fingerprint omitted]`。当时仅inspection，不追认startup02的schema0或原生。13项定向检查包含版本/平台/两种哈希错配、布局冲突、严格尾字节失败与显式清单拒绝。

### 公开转换消费借取结构

`convert`可加`--unity-schema-manifest frozen-bundles.json`，在同一链中做精确读取、MonoScript外部表解析、字段C#生成和Provider候选导出。脚本引用仅按同容器serialized文件外部表的唯一完整文件名解析，不把相同pathID跨文件合并。现有Unity程序集类型单列nativePackageTypes，不生成同名替代；空GameObject引用或未知非组件基类不伪装成MonoBehaviour。字段实例保留embedded/borrowed来源及池/布局hash。冻结池全部原件在SourceRecovery/SchemaSources中按SHA去重留存；这些是结构查找输入，未当作要求导出的全部资源依赖。

实际`outputs/unity-startup-schema-convert-03`：5个资源/纹理输入3554576B，另600结构池输入53730632B；70新增严格正文进入消费，生成GradientColor的7字段/4实例与UIButtonScale的4字段/8实例，真实替换对应Provider空壳C#并保持meta。现有引擎包36实例不另造同名类；22已读但尚不支持字段/基类的实例与36未解析对象继续明确缺口。2份生成代码以本机Unity6 SDK编译通过。Provider child81142 exit0/reaped、原件不变，2484原始导出文件/11019493B，最终recovery manifest SHA `[private fingerprint omitted]`。

这里的11字段为C#声明恢复；Provider Scene尚未应用借取字段的实例值，显式`UNITY_BORROWED_SCHEMA_FIELD_VALUES_PENDING`，原生未跑、方法0、原自定义继承/效果仍未知。不能把两个字段类称为完整恢复原脚本。旧候选与失败不改。


### Unity 2022 WebData 与坏 ETC1 载荷隔离

`convert`现可直接接受原始 `UnityWebData1.0\0` 文件；不是从后缀或版本猜容器，也不把其中builtin文件的版本强改成主版本。固定UnityPy/AssetRipper直接消费；每个serialized file的精确版本保留。近似/缺终止符签名拒绝。

默认发现声明为ETC1但非streamed的inline数据小于 `ceil(width/4)*ceil(height/4)*8` 时blocked，不能称为原生像素。显式 `--unity-quarantine-invalid-textures` 才允许从自有派生容器移除这些精确坏纹理对象并继续部分导出。每个移除项保留file/pathID/原对象和payload SHA，原容器完整留SourceRecovery，所有其余对象类型/原bytes SHA在保存重读后必须逐项相同；指向坏纹理的引用保留未解决，不补色块或假纹理。未知格式/空字体纹理不纳入该例外。Provider失败也进入公开diagnostics。

- 勇者乱斗主2022.3.16f1，builtin资源自身2022.3.15f1保留；14482777B原SHA `[private fingerprint omitted]`。3799对象3338严格parsed/461未知，45坏ETC1隔离，其余3754对象保存重读原hash一致。Provider92149 exit0/reaped、4303文件9229669B；2029份代码隔离，0字段类、7缺引用。新候选 `outputs/unity2022-yongzhe-package-02` recovery SHA `[private fingerprint omitted]`。旧01 decoder失败冻结。
- 手机反恐特别行动主2022.3.34f1c1，builtin2022.3.26f1保留；14890280B原SHA `[private fingerprint omitted]`。9675对象9598严格parsed/77未知，40坏纹理隔离、其余9635对象hash一致。Provider92301 exit0/reaped、18066文件35824738B；8913份代码隔离、0字段类、4缺引用。`outputs/unity2022-counterterror-package-01` recovery SHA `[private fingerprint omitted]`。

两者原始文件不变，原方法/原生/视觉/玩法not_run；这是实际资源候选，不是完整项目通过。不能把上述版本外推全部2022、中国版或WebData来源。

Typed正文另有每对象250000值/全请求4000000值预算。超大ComputeShader等对象保留类型、pathID、rawSHA与明确unparsed，不让一个巨型字段数组阻止其后小对象解析，不放宽整体读取上限；对象级/聚合反例已验证。


### 其他source archive用例与Provider证据分层

武侠大明星原启动2021.3.18f1/6326649B SHA `[private fingerprint omitted]`，1559对象1468严格parsed/91未知；6纹理令牌仅3个精确缓存命中。启动分支明确blocked：缺 `logo.24de1a47`、`cm_frame_smalltips.041d0ce7`、`EmojiOne.c4a4a55d`。独立4272B原Sprite配置bundle有据导出，不被启动缺件阻止：SpriteSaveInfo一类/一个Sprite[]字段保持脚本meta并通过本机Unity6 SDK编译；131Sprite引用仍缺，原方法0/native not_run。Provider95567 exit0/reaped，9文件16555B；recovery manifest `[private fingerprint omitted]`。

永远的蔚蓝星球实际团结2022.3.61t9启动1761819B SHA `[private fingerprint omitted]`。新inspection逐对象预算后3042对象2888parsed/154未知或预算缺口；全部完整版本保留，没有就近套普通Unity版本。固定AssetRipper虽返回ProjectSettings，但3042个对象全为UnreadableAssets，Assets原生资源0。因此新增强门：Provider receipt分列nativeAssetFiles与unreadableObjectFiles；没有实际原生资源时`exported_evidence_only`，公开convert必须blocked且不晋升Unity候选。旧01误分类partial原件/输出冻结，不追认成功；新02已正确blocked，Provider93252 exit0/reaped。团结原生资源/未知类/Lua方法/玩法仍未支持，不能凭UnityPy能读多数对象说已转换。


### 自动精确依赖闭包

```sh
monkey convert --source /path/to/config.bundle --target unity6 --out /path/to/fresh \
  --provider-python /path/to/python --asset-ripper /path/to/AssetRipper.GUI.Free \
  --unity-dependency-manifest /path/to/frozen-bundles.json --unity-texture-cache /path/to/textures.json
```

依赖池与index-unity相同：显式schemaVersion1/files[path,bytes,sha256]，最多2000包/1GiB。必须完整通过固定Provider元数据索引。只按serialized-file完整身份与原external表收敛可达闭包，不按相近文件名、basename资源名或最近版本猜测；同serialized-file身份对应不同容器字节则拒绝，仅全容器字节相同的别名可等价。环、返回主包、自包含多serialized文件处理明确；缺件单列并保留未解决引用，不从池外读取。该参数与手工--dependency-source互斥。

池是查找分母，只有精确可达部分进入资源导出；完整冻结池按SHA留SourceRecovery/DependencyLookup并有用途说明，不能把所有查找文件说成已导出资源。导出资源/实际消耗纹理输入计数、查找池计数/字节分列。每项索引源SHA、selected源SHA和最终原件副本再次核对；闭包与索引保留供接续核验。

武侠新`outputs/unity2021-wuxia-closure-package-01`：冻结212包33404614B、49314元数据对象，全部索引成功。自动选中1依赖（主包合计2资源容器），并消费3精确ASTC缓存；实际资源/纹理5输入2271482B，未包含启动缺3纹理的独立分支。Provider97219 exit0/reaped、277文件12586350B、135原生资源、0Unreadable；原先131个缺引用占位降为0。SpriteSaveInfo一类/一个字段的C#与此前SDK编译代码逐字节相同，fresh Provider meta身份不同且分别保持，不冒称跨fresh继承旧GUID。recovery manifest `[private fingerprint omitted]`；原方法0、原生读回仍待公开native分支验证。3个source atlas PNG逐RGBA/hash与规范化源缓存按明确上下翻转对齐相同，原版视觉/玩法未验。

## 显式 CDN 清单接入统一 Unity 命令

Unity分支现可复用既有 `--remote-manifest` / `--remote-cache-root` / `--acquisition-out` / `--offline`，不再只接受手动合并后的缓存表。清单仍是原来源声明的精确URL/path，可附SHA/bytes；不猜版本、hash或路径，不执行下载内容。

```sh
monkey convert --source <original-data.unity3d> --target unity6 --out <fresh-output> \
  --provider-python <pinned-python> --asset-ripper <pinned-AssetRipper> \
  --unity-texture-cache <existing-cache.json> \
  --remote-manifest <declared-downloads.json> --remote-cache-root <verified-cache>
```

统一acquisition负责显式下载/哈希缓存复用/HTTP缺件回执；Unity适配只做类型输入闭包：`Assets/Textures/astc/...`须真实ASTC头/块长有效，再由源Texture2D精确键/尺寸/mip核验并水合；真实Unity容器加入显式依赖，提供冻结池时加入精确可达查找池。其他文件只作为SourceRecovery/Acquired证据，明确diagnostic，不导入Assets或执行。原缓存同逻辑键不同字节拒绝覆盖。全部可用原件和脱敏acquisition.json在候选冻结前归档；失败或未知项保留，不伪装全游戏资源闭合。Cocos仍使用其input-set，未改变既有接入。

2026-10-24公开真实链 outputs/unity2021-wuxia-acquisition-package-04：初始114项纹理表+3项原URL/精确SHA清单，`--offline`复用本地3文件110848B、0GET/0缺件，6源纹理键全部水合，Provider99626 exit0/reaped、0.655秒，44原生资源/2408文件。候选包含3份原字节和脱敏回执，owned内容逐项核验通过，manifest `[private fingerprint omitted]`；acquisition回执SHA `[private fingerprint omitted]`。没有再次启动Editor；启动整包方法/原生仍未验。混合依赖/证据、同键异字节、坏ASTC、offline不联网、候选在源变化后保持原owned等34定向检查通过。
