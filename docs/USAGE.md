# 当前开发分支：monkey-project/2

稳定安装为 `0.4.0`，本地开发为 `0.6.0.dev1`，新操作命令见 [v0.5 说明](V0.5-OPERATIONS.md)。日常使用已安装 Release 的 `monkey`；仓库入口仅转发，源码开发显式使用 `.venv/bin/python -m monkey.cli`。新输出布局以 [PROJECT-SPEC](PROJECT-SPEC.md) 为准，以下历史格式化说明不适用于新输出；`--format none|grea` 都是弃用别名。

```sh
monkey convert --help
monkey layout-preview --conversion /path/to/completed-conversion --layout /path/to/layout.json --out /path/to/new-preview
monkey layout-migration --from /path/to/old/UnityProject --to /path/to/new/UnityProject --out /path/to/new-migration
```

预览读取转换输出中的 Structured 计划；迁移命令读取工程 Assets/assets 的 meta 身份，拒绝重复 GUID/UUID。清单列出移动、未移动、仅旧工程存在及新增资产；它不修改游戏工程，也不证明内容、导入设置或玩法一致。新输出目录必须不存在。


## v0.6 全量 C# 初稿与资源候选

源码开发入口仍须显式调用项目环境。Unity 包级转换默认输出全量可取得的 JS C# 初稿，不需要类型合同：

```sh
PYTHONPATH=src .venv/bin/python -m monkey.cli convert --source /path/to/package --target unity6 --out /path/to/new-candidate --offline
PYTHONPATH=src .venv/bin/python -m monkey.cli code-draft --source /path/to/game.js --out /path/to/new-code-drafts
```

已有资源候选可按精确 owning manifest 哈希在新目录组装，不重新解包/解码或启动 Editor：

```sh
PYTHONPATH=src .venv/bin/python -m monkey.cli convert --reuse-candidate /path/to/frozen/UnityProject --expected-candidate <manifest-sha256> --target unity6 --out /path/to/new-complete-candidate --offline
```

若既有 Editor 保存的 Scene/Prefab 尚未登记在旧清单，先用 `freeze-resource-candidate --candidate <project> --expected-manifest <sha256> --expected-readback <sha256> --out <new-frozen-root>` 封存。它只接受精确版本、已保存重开的 nativeFiles 哈希与明确列出的 Editor 状态，不接受未知资产/代码，不启动 Editor。

再次复用已含完整初稿的候选时，工具按生成器签名、原源码哈希与每个生成文件的 owning hash 校验整源阶段；一致时跳过 AST worker 和转写。生成器变化会要求冷阶段，篡改/人工所有权不被当成可复用内容。`--reuse-source-stages` 也使用相同初稿阶段校验；报告分别记录 source/full-CSharp parser 是否执行。

`Docs/CSHARP-DRAFTS.md` 是接续入口；`Analysis/Code/package-csharp-drafts.json` 汇总各源分母和报告路径。逐源报告将完整字段/方法/诊断分为 Details 分片；每条映射包含源位置/hash和实际目标文件。全部草稿在 `SourceRecovery/CSharp/<source-hash>/`，位于 Unity 编译目录之外。`code-types`、`--module-selectors` 和 `--module-contract` 仅用于可选的强类型增强。未编译/未验证的候选通常退出码为 1，须结合 `completed`、`status` 与具体诊断判断；退出码 1 不自动表示转换中断。

以下保留旧版本用法及历史验收说明。

# v0.2 开发增量（尚未发布）

本地开发版本0.2.0.dev1；v0.1发行包/标签保持0.1.0不变。

```sh
monkey research-matrix --root /path/to/source archive/games --out /path/to/new-matrix
```

只读动态发现所有非点号/下划线游戏目录，缺RESEARCH.json、未知引擎、缺源及符号链接均保留在case分母并列原因。只记录来源元数据/显式清单和已知Analysis目录；不跟随外部来源指针，不执行转换。输出cases.json/discovery.json/coverage.md；metadata_hint_only不等于版本正文已解析或游戏导出成功。

Cocos代码按用户最新要求默认TS优先，JS次选；具体CLI/实现状态见V0.2-PLAN/V0.2-EXAMPLES，尚未宣称代码生成与格式化已完成。

```sh
monkey code-model --source /path/to/source-module.js --module-name NumberLabel --out /path/to/new-code-model
```

静态具名方法和源字节范围/hash；当前只把实例字段读/写标为语义候选，其余方法明确unsupported。该命令不执行源JS、不生成可用业务代码，partial/exit1；实际代码生成仍在后续实现。

Unity来源首个明确本地bundle的单命令候选转换已接入`convert`，严格依赖版本/隔离/限制及实际证据见[Unity来源Provider](providers/UNITY-SOURCE.md)。这还不是全Unity原包转换或原生通过，启动包外置纹理未闭合时会先blocked。

# v0.1 命令说明

当前预发布版本v0.3.0.dev1；`monkey --version`和`monkey capabilities --json`可核对。旧0.3.0.dev1为内部开发候选编号，旧证据不改写；跨toolVersion的resume/reuse按原身份合同拒绝，需明确新输出，不静默改旧候选。

# 一键工程转换

产品目标规则：Cocos全部版本原包可选Unity6/Cocos3.8.8/both；Unity、Laya/LayaAir、Egret、自研与其他引擎全部版本原包仅以Unity6为目标。当前实际解析子集见[支持矩阵](SUPPORT-MATRIX.md)，未接入来源不能据以下命令视为已还原。

在monkey根目录运行，无须逐阶段调用reader或export：

```sh
bin/monkey convert --source /path/to/game.wxapkg --target unity6 --out outputs/game-unity
bin/monkey convert --source /path/to/game.apk --target both --out outputs/game-both
bin/monkey convert --source /path/to/cocos-project --target cocos38 --out outputs/game-creator
```

`UnityProject/`、`CocosProject/`为独立目标工程，`conversion-result.json`说明候选状态和缺口。
结构化支持范围为声明的2.4.15格式；其他格式保留文件证据，不能视为原生还原成功。
输入原件不修改，输出目录必须新建。生成代码合同放在编译排除区，不生成假业务。

多目录使用明确清单，路径相对于该JSON所在目录：

```json
{
  "schemaVersion": 1,
  "sourceProfile": "cocos-2.4.15-bundle",
  "game": {"gameId": "my-game", "engineVersion": "2.4.15"},
  "inputs": [
    {"id": "main", "path": "source/main", "config": "config.json"},
    {"id": "remote", "path": "source/remote", "config": "config.hash.json"}
  ]
}
```

```sh
bin/monkey convert --input-set inputs.json --target both --out outputs/game
bin/monkey convert --resume outputs/game --input-set inputs.json
```

仅扫描列出的本地根。未知appId/version保持未知；已知冲突拒绝。可选`cacheList`与`cacheKind: cache|temp`
读取本地缓存映射，URL仅作身份键，不请求网络。原列表保留，wxfile与物理文件必须在声明根内。
续跑验证清单身份、输入快照和已有工程哈希，拒绝未知/缺失/人工修改文件；原候选归档到`Previous/`。
可校验恢复已有备份的中断运行；没有可信清单的半成品不自动覆盖。结构阶段复用不等于编辑器验收。

静态检查不会启动引擎：

```sh
bin/monkey verify --candidate outputs/game/UnityProject --out outputs/game-unity-check
bin/monkey verify --candidate outputs/game/CocosProject --out outputs/game-creator-check
```

默认`needs_action`与退出码1表示候选生成后仍有待验项；`--offline`显式限定离线候选。
Editor导入、编译、保存重开、画面和业务验收分开记录，目前整包真实Editor验收未完成。

# 当前使用与支持矩阵

结构化对象reader当前声明两种 Cocos **2.4.15 子集**；新增包级全文件盘点与静态代码恢复见下文。不是所有 Cocos 格式的通用原生导入器。

## 发布资源

```sh
.venv/bin/monkey inspect --source /path/to/bundle/config.hash.json \
  --source-profile cocos-2.4.15-bundle --asset-index 123 \
  --dependency-source /path/to/main/config.hash.json --out outputs/inspect-new
.venv/bin/monkey normalize --manifest outputs/inspect-new/source-manifest.json --out outputs/ir-new
.venv/bin/monkey plan --ir outputs/ir-new/ir.json --namespace my-game \
  --target-profile unity-6000.6.2f1-ugui --out outputs/plan-new
.venv/bin/monkey export --plan outputs/plan-new/plan.json --out outputs/unity-new
.venv/bin/monkey verify --candidate outputs/unity-new --level static --out outputs/static-new
.venv/bin/monkey handoff --candidate outputs/unity-new --out outputs/handoff-new
```

`--asset-index` 可重复。索引来自精确版本的 config UUID 表。只读取选择项及引用闭包；共享 pack 只解码选择的 section。依赖 bundle 必须显式提供已有本地 config，不联网找资源。根据版本表读取确切 import/native 文件，不选 glob 第一个。没有版本时只接受确切未版本化文件。

版本依据是用户显式 profile 声明、存在时的 engineVersion 字段、编译 header/shape 校验；发布 config 本身没有完整 Editor 版本证据时不宣称自动识别了版本。未知 header 不猜测升级。

## 可编辑源工程

```sh
.venv/bin/monkey catalog --source /path/to/project \
  --source-profile cocos-2.4.15-project --out outputs/catalog-new
.venv/bin/monkey inspect --source /path/to/project \
  --source-profile cocos-2.4.15-project --asset-index 0 --out outputs/project-inspect-new
```

选择 catalog.json 的 index，后续 normalize/plan/export 相同。要求 project.json/version 严格为 2.4.15，项目有稳定 id 或 name。读取 assets 下 meta 索引、纹理的 sprite-frame subMeta、`.prefab`/`.fire` 对象数组及明确的 native 文件。没有把 compiled reader 套在源工程上。源工程路径仅以合成夹具验证，尚未验真实源工程。

## Unity 导入

用独立、获准资源窗口打开生成候选，执行 `Tools > Monkey > Import Candidate`。独立 batchmode 入口为 `MonkeyImporter.ImportBatch`。工具不会自行启动 Editor；不得拿样例项目正式 Editor 执行。首次导入使用 AssetDatabase/TextureImporter/PrefabUtility 保存原生资产，不调用全局 SaveAssets；已有生成 Prefab/Scene 则拒绝重复导入。

导入指令和源身份只在 `Assets/Monkey/Editor`。原生 Prefab 位于 `Assets/Generated/Views`，Scene 位于 `Assets/Generated/Scenes`，普通 View 组件仅保留 Image/TMP/Button 引用，不带源节点 ID、业务回调或运行时解释器。导入后移除 Assets/Monkey 仍应可编辑/编译；这项真正 Editor 脱离测试尚未执行。

```sh
.venv/bin/monkey verify --candidate outputs/unity-new --level editor --out outputs/editor-check-new
```

该命令读取导入器保存的 `Analysis/editor-readback.json`，不会启动 Editor。没有回读文件则明确 `EDITOR_NOT_RUN`、退出 1；检查 Sprite border/尺寸/GUID/fileID、节点尺寸/锚点/位置、字体GUID/覆盖、Bitmap字形四角、序列化View引用/fileID、原生编辑/保存/重开克隆、缺脚本及保存文件hash。画面对照和业务仍另行验收。Editor 首次保存的 Prefab/Scene GUID 以真实回读为准，**目前仅资源与脚本 GUID 确定性通过静态验证**。

## 支持边界

| 项目 | 当前结果 |
|---|---|
| UUID/压缩 UUID、短十六进制纹理 key | 已实现，畸形身份诊断、不修补猜测 |
| pack ordinal、import/native 版本、redirect | 已实现；未提供依赖 bundle 记 REDIRECT_UNRESOLVED |
| PNG/JPEG、ASTC 2D | 已实现；ASTC 校验 header、block、长度、像素预算，只有固定可选 provider |
| 旋转/trim/offset/originalSize/capInsets | PNG 语义反例及真实切片已验证；亚像素留白不能无损栅格化则记 SUBPIXEL_TRIM |
| TTF/MP3/WAV/OGG | 资源拷贝；16原字体的Unity/Creator原生创建/重载已有实证，不静默替换字体，原版画面对照另验 |
| Node/RectTransform、simple/sliced/tiled Sprite | 已实现typed IR和原生adapter；Unity 13图646节点、Creator 15图577节点强几何实际回读零差异，全量仍未通过 |
| Label/BitmapFont | 原RGBA图集、glyph/offset/advance/kerning生成静态TMP字体；目前单行，缩放时存在非零源未缩放kerning则显式拒绝。TTF先做cmap4/12覆盖检查，再为已知文字生成静态TMP；字体度量/描边仍需实际对照 |
| 有限UI子集 | 父级绝对全拉伸Widget；容器resize H/V及均匀水平Grid；矩形非反转Mask；双轴禁用ScrollView；自目标none/scale Button。使用原生组/Animator，不写源布局运行时。复杂/动态子集仍handoff |
| 原空Sprite/点击回调 | 空frame生成禁用Image并保留待绑定项，防止Unity默认白框；原handler只记录，Button没有假回调或默认成功 |
| Animation/Spine、自定义脚本、事件 | 不生成空回调或假业务；交 AI 包 |
| Cocos 3.8.8 输出 | 1694 Prefab+Scene实际保存重载；full13严格回读失败，后续成组修复在验，原版画面/业务not_run |
| diff/register/apply | 已实现；默认dry-run，expected-manifest与预览收据保护写入 |

Creator新候选保留source overflow/sizeMode，同时显式声明`source-baked-clamp-v1`或`source-baked-custom-v1`：原生Label/Sprite显示与固定源矩形已生成，自动尺寸行为仍为handoff。它不等于动态行为还原。原生SpriteFrame完整图片明确禁用裁切，实际裁片保持来源矩形；字体页另核BitmapFont→SpriteFrame→Texture身份与矩形。新候选Scene和独立Prefab完整geometry/Scale/Quaternion分别核验，旧结果不追认。

`candidate` 表示本命令的离线范围完成，不表示游戏可玩；`partial` 表示已出报告但存在诊断。退出码 0/1/2 分别为声明范围完成、有待处理诊断、参数/IO/协议错误。所有阶段创建新目录，不覆盖输入、旧候选或人工文件。

计划资源、源文件及候选清单均带 hash。静态 verify 会检测包清单等生成文件的修改；Editor verify 允许引擎生成的 meta，只接受与保存回读匹配的 hash。现有受控apply见下文；仍不支持任意目录同步、自动删除或自动合并人工代码。

## 带依据的动态字体绑定

源Prefab中无Font引用的Label可能由原脚本在加载时选择字体。monkey不执行JS、不自动猜字体。可以显式把已人工核对的冻结脚本作为只读证据，inspect增加`--evidence-source /path/to/frozen/game.js`，并选择实际字体asset索引。plan增加`--bindings /path/to/bindings.json`。

绑定JSON包含`sourceManifestSha256`、已登记的`evidenceSha256`、`offset`/`bytes`及`labelFonts`数组；每项为`component`、`font`稳定sourceId和布尔`syntheticBold`。工具核验文件hash、范围、组件和manifest，但原脚本的选择语义由提供绑定的开发者负责核对。禁止覆盖原来已有的明确Font引用。绑定回执写`Analysis/font-bindings.json`；源manifest和IR若被改动会报STAGE_DOCUMENT_CHANGED，不能直接改中间文件绕过来源。

CONTINUE-01只给原奖励页zh场景的3个系统Label绑定了已取得的zh-bold文件，另2个数量文本使用原BitmapFont。没有绑定时仍报缺口，不换系统字体。Bitmap图集包含原彩色描边，采用TMP Bitmap Custom Atlas材质；TTF描边和垂直度量仍等待真正画面对照。

隔离Unity第一次导入需要TMP资源时，adapter只在该候选工程通过已注册包的`resolvedPath`定位UGUI 2.6.0必需资源，导入Essential archive后同步刷新并核验原名shader/settings；不弹交互窗口、不导入Examples、不修改引擎或样例项目。未生成或未就绪会明确失败，不用其他shader替代。新Scene包含固定750×1334设计坐标框、原生Canvas/EventSystem，Editor导入后会尝试离屏捕获`Analysis/native-page.png`；只有文件和真实回读存在才是Unity画面。`scripts/probe_bitmap.py`产物明确标OFFLINE，不是Unity预览。

机器交接包按模块/根因聚合并保留全部明细。真实View数组索引和Prefab component fileID必须读Editor回执；在此之前只提供字段/目标路径，不猜fileID。

## Creator 3.8.8 候选

`plan --target-profile cocos-3.8.8`读取同一schema 1 IR；可用同一`--bindings`证据收据。`export`按plan目标选择emitter。输出`assets/generated/art`的PNG/原TTF/标准BMFont及根meta、`extensions/monkey-import`的Editor-only薄扩展、Analysis映射与AI包；人工业务放`assets/manual`。不随Player解释IR。

资源窗口明确授权后才打开隔离工程，在资产导入就绪后执行`Monkey / Import isolated candidate`一次。扩展检查项目UUID、3.8.8版本和生成内容hash，查询原生SpriteFrame/Texture UUID，保留原生subMeta并设置尺寸/trim/九宫格；创建独立原生节点树并经Creator serializer保存Scene、重新加载回读。已有Scene或回执即拒绝覆盖。未执行时不含实际Scene，不声称真实显示通过。

当前支持Node/UITransform/UIOpacity、simple/sliced/tiled Sprite、原BitmapFont/TTF Label、Label原生描边、必要Widget/Layout/Button/矩形Mask/静止ScrollView子集。未知脚本、动态滚动和事件业务留handoff；字体度量、布局行为与同状态画面仍需真实比较。根UUID按namespace/source ID稳定产生；子资源UUID不在Python拼接猜测。

CONTINUE-02明确允许v0.1待验时推进v0.2/v0.3离线工作，两目标的Editor/视觉状态分别记录。

## v0.3 登记、差异与受控应用

当前CLI JSON合同schemaVersion=1，IR仍为schema 1。`capabilities --json`分别列源profile、两个目标profile及各目标真实验证状态。文件逻辑身份由目标profile/namespace/路径与source-map来源ID表达，内容SHA-256另列；不能把内容变更当成来源身份变更。

输出只在当前工作区的`outputs/<candidate>`登记，状态保存在`.monkey/outputs.json`，绑定绝对根、profile/namespace、来源根与manifest hash。CLI在该目录export后自动登记；其他目录可生成候选，但不能作为apply目标。旧候选或移位后未经登记的候选可用`register --candidate ... --out ...`验证并登记；不通过手改registry更新基线。原Unity10冻结候选保持原位不登记改写。

```sh
monkey diff --before outputs/base --after outputs/next --out outputs/change-report
monkey register --candidate outputs/base --out outputs/registration-report
monkey apply --target outputs/base --candidate outputs/next \
  --expected-manifest <base-manifest-sha256> --out outputs/apply-preview
monkey apply --target outputs/base --candidate outputs/next \
  --expected-manifest <same-base-manifest-sha256> --write \
  --preview outputs/apply-preview/application.json --out outputs/apply-result
```

默认apply只预览；写入必须有先前stage-hash保护的dry-run收据，且预览、当前内容、目标manifest与登记hash一致。路径必须规范化且不能包含符号链接或穿越片段，profile/namespace不能跨线合并。diff分别列added/changed/removed/unchanged/manual及manualConflicts；修改、缺失、目标占位、未知生成区文件、输入候选篡改或保留项被重引入都会拒绝相关写入。

生成区由manifest登记，`Assets/Manual/`和`assets/manual/`属于人工区。工具可初始化README脚手架但登记为manual，后续apply不覆盖、创建或删除人工区文件；人工文件hash仅作初始记录，静态verify与apply不据此覆盖人工内容；人工修改的生成文件作为冲突处理。Editor重写meta及新增原生输出尚不支持自动收编，必须停下处理，不把引擎生成和人工修改混为可覆盖文件。

removed文件保留在原路径，合并后的manifest将其标记retained，记录desired/applied-from manifest及retainedRemovedPaths；不会宣称目标逐字等于新候选。retained文件再次生成且内容变化时拒绝覆盖，目前没有自动所有权释放或垃圾清理命令。

写入前在`.monkey/transactions/<id>/`保存旧文件、manifest、registry和事务journal；同工作区使用更新锁。普通写盘失败会回滚自身已写文件；发现外部并发修改则保留该修改并标记recovery-required，不能承诺任意断电场景自动恢复。遗留update.lock需先检查对应journal，不自动删锁。该能力只处理登记生成文件，不是通用目录同步器，不写源工程。

## 两目标能力矩阵（当前开发候选）

| 能力 | Unity 6000.6.2f1/uGUI | Creator 3.8.8 |
|---|---|---|
| 同一2.4.15 IR、图像/原字体 | 离线支持既有子集 | 离线支持既有子集 |
| 原生节点/UI、必要布局/按钮/遮罩 | Editor-only C#候选 | Editor-only JS薄扩展候选 |
| 静态依赖/hash/AI包 | 通过代表切片 | 通过同源代表切片 |
| 源数值/业务脚本 | 正式JSON/业务待原生实现 | 正式JSON/业务待原生实现 |
| 登记、diff、受控apply | 定向人工区用例通过 | 定向用例及真实候选副本通过 |
| 实际导入/保存/重开、画面对照/输入 | not_run | not_run |
| 动态滚动、未知脚本/事件、Spine | unsupported/handoff | unsupported/handoff |

最低Python3.11与Windows运行环境尚未实测；当前验证环境为macOS arm64/Python3.14.7。开发wheel不是正式发行，不含原素材或测试样本。

## 有限 AnimationClip（CONTINUE-03）

新normalize输出可选的`animationSchemaVersion=1`、`animationClips`及cc.Animation的clip/root绑定。原IR schema仍为1，旧IR缺该字段等价于无动画；未知animation schema明确拒绝。计划可用`--animation <source-clip-id>`选一份来源剪辑，不另建reader；未选择时分析IR内的剪辑。

```sh
monkey plan --ir <normalized>/ir.json --namespace <stable-namespace> \
  --target-profile unity-6000.6.2f1-ugui --animation <source-clip-id> --out <new-plan>
# target-profile cocos-3.8.8 使用同一IR/clip选择；export/verify/handoff沿用现有命令。
```

支持局部x/y/z或position向量、scale向量/scaleX/Y/Z、0..255透明度；严格递增、从0起、在duration内的有限键序列，末键后恒定延至duration。仅linear（含省略/null）和constant阶跃；Normal/Loop、speed=1。其他easing/Bezier/循环、active和组件曲线不默认为线性。路径按源Animation所属节点的子层级唯一解析，缺失/重名、重复通道或Layout/Widget持有位置时明确留缺口。

Python生成六类数据：源位置、目标身份/相对路径、有限键、原生绑定/单位、中点验证探针、事件合同。Unity使用原生AnimationUtility，Creator按同一节点/向量分组为VectorTrack、透明度为RealTrack/UIOpacity；IR和创作脚本仅在Editor，Player不解释源对象图。原生.anim由Editor创建/保存/回读，离线没有实际曲线资产。`Analysis/animation-module.json`和单一AI模块任务聚合部分轨道及事件。

部分映射不会自动播放、附加业务Animator或回调。事件只记录source位置、时间、函数名与JSON参数及manual-only状态，Native事件数组为空；真实采样/播放和可编辑重开未验证。首个真实`CellBoxClicked`为0.5秒/6标量轨道，另两条active未支持，不能标作完整动画还原。详见[动画验收](validation/2026-10-23-animation.md)。
# 一键转换入口（2026-10-23）

```sh
bin/monkey convert --source /path/to/creator-2.4.15-project --target unity --out outputs/new-unity
bin/monkey convert --source /path/to/creator-2.4.15-project --target cocos --out outputs/new-creator
bin/monkey convert --recipe /path/to/recipe.json --out outputs/new-candidate
bin/monkey convert --resume outputs/new-candidate
```

`--output` 是 `--out` 的别名；目标也可用完整 profile。源目录须含 project.json 或 config.json，带 hash 的 bundle config 可直接传文件。可编辑工程默认选择全部 metadata 资产并保留未知类型诊断；发布 bundle 需 `--asset-index N`（可重复）或显式 `--all-assets`。无 engineVersion 的 bundle 必须声明 `--source-profile cocos-2.4.15-bundle`，不靠文件名猜源版本。既有 2048 资产闭包、字节预算仍适用。

recipe 为 UTF-8 JSON，可复用范围与依赖，路径相对 recipe 文件解析，不写输出路径：

```json
{
  "source": "source/config.json",
  "target": "cocos",
  "source_profile": "cocos-2.4.15-bundle",
  "namespace": "example-ui",
  "selection": [2],
  "dependencies": [],
  "evidence": []
}
```

也支持 `bindings`、`animations`、`all_assets`；未知字段/错误类型拒绝。recipe 不可混用显式输入选项；输出由 `--out` 指定。

一次调用串联 inspect/normalize/plan/export/verify/handoff，原生候选在 `project/`，各阶段 manifest 独立保留，`conversion.json` 与顶层 `manifest.json` 汇总。失败保留阶段和 `failedStage`，不覆盖原件/旧输出、不删除证据。默认 `status=needs_action`、`resultKind=candidate`，明确原生导入待处理；显式 `--offline` 为 `partial`。当前尚无命令行自动启动编辑器/调用原生导入的实现，不把待处理项当自动化完成；外部编辑器仍需真实可用版本、登录/许可与窗口条件。

`completed=true` 仅表示六个离线阶段执行完毕，不表示原生/视觉/业务完成。退出码沿用：0 无缺口，1 部分/需行动，2 输入/冲突/执行失败；当前 convert 因原生或后续验收未闭合返回 1。未支持的组件和业务在 handoff 内保留。

`--resume` 校验工具版本、原始 conversion 收据、来源/证据 SHA、候选 manifest SHA 后复用工程，仅做原生回读验证；新检查写入独立 `checks/<id>/`。没有回读仍为 needs_action；实际原生引用与文件通过才为 resultKind=native，视觉/业务仍单列待验。引擎生成的 meta 通过原生回读合同校验，人工内容改动仍由 hash 检出。当前仅续验已完成候选；失败的中间生成阶段保留证据但尚不能自动续跑。登记增量仍使用既有 register/apply 合同。

## 包级默认入口与双目标（2026-10-23）

```sh
bin/monkey convert --source GAME.wxapkg --target both --out outputs/new-game
bin/monkey convert --source GAME.apk --target unity6 --out outputs/new-game-unity
bin/monkey convert --source /path/to/obtained-resources --target cocos38 --out outputs/new-game-cocos
```

支持明文wxapkg的BE/ED头、索引和连续不重叠payload，APK ZIP及明确Cocos资源目录。资源目录默认全文件，保留`--package`强制全文件入口；旧asset-index/recipe只用于切片诊断。全量指本次明确输入内的全部可枚举文件；多输入根通过schema 1 input-set校验身份并合并。存在同名不同配置bundle时拒绝混拼。源Cocos版本无法确定时记录unknown，不伪称对象reader支持。非Cocos或未知加密容器明确报错。

边界：最多50,000文件/目录、每文件128MiB、每个容器/目录展开1GiB、容器1GiB、目录深64。整批输入合并默认2048 MiB；显式input-set可用 `"limits":{"maxInputBytes":2147483648}` 声明2GiB的合并预算，严格整数、硬上限8GiB，不改变单文件、单根和数量限制。远端获取每轮仍固定1GiB；派生输入集保留显式合并预算。拒绝穿越、绝对路径、反斜线、symlink/特殊项、大小/哈希变化、同名及Unicode/casefold路径别名、wxapkg重叠或漏计payload。仅一层枚举，不递归解包内部容器；嵌套包原样待转。APK内动态库/dex及平台文件保留证据并排除目标运行时，不执行、不安装。

输出分别为UnityProject/CocosProject；移走其中一个工程不依赖另一个或InputCache。每个工程包含resource-ledger、cocos-assets、code-index、dynamic-keys、agent-work、生成文件hash/所有权，以及AGENTS、START-HERE、PROJECT-STRUCTURE和DEPENDENCIES。已识别PNG/JPEG、TTF/OTF、Ogg/MP3/WAV复制到规范内容目录（仍需引擎导入）；所有未知原件/序列化对象/配置/Spine等留SourceRecovery。数值未判明前不假造正式配置；JSON不是一律当数值表。

AST解析只读源代码，固定Acorn8.15.0；Node堆上限512MiB、单次30秒、AST3百万节点/深512。literal loader/System.register能恢复相应factory；动态/拼表模块仍为候选。RF fallback仅配对同一词法块的静态push/pop，保存精确UTF-8字节范围、hash、类/身份、可读片段；外围import/模块边界未知，未匹配位置另列缺口，不能当完整模块语义证明。每模块生成SourceRecovery内TS/C#初稿、实际依赖/导出/事件/资源键证据；调用抛明确未实现，不接原服、不假奖励。编译/行为均false，未启用业务。

当前返回needs_action/candidate，`completed`只表示留存/工作区生成已执行完毕；nativeObjects=pending_adapter、editor/visual/business=not_run。`--offline`返回partial。包级原生对象恢复、原生导入编排、失败阶段续跑、包级resume/register/apply待接入；目录生成不能代表产品目标已完成。资源覆盖以输入文件/字节为分母，缺失引用另计，去重保留每个来源ID。

## 原生启动预检与阶段续跑身份

```sh
bin/monkey preflight --candidate outputs/game/UnityProject \
  --log /path/to/previous-import.log --out outputs/startup-check
```

该命令只检查冻结文件、目标版本、已安装引擎/CLI和已有Editor标记，并对已有日志作分类；不启动Editor、写全局缓存、删除锁、修改安全设置或自动重试。readonly database/系统IPC警告且未初始化引擎时标记`HOST_CACHE_OR_IPC_ACCESS_SUSPECTED`，这是定位推断；许可entitlement已解析时，不仅凭token更新失败就断言许可无效。

新候选记录包级源码恢复、inspect、normalize、目标plan和emit的源码阶段签名。包级续跑在归档/改动候选前拒绝缺失或变化的缓存算法签名。旧开发候选（如932220d）没有这份签名，应保留并用新输出目录重新转换，不能给旧缓存补写当前签名后冒充兼容。

Unity新导入计划另列每个独立源Prefab的根、节点集合和目标路径，跨源节点引用/多根图明确拒绝；Editor薄层保存后加载内容核对，回执缺失时不声称原生Prefab已完成。源Scene不按Prefab冒名输出。Spine闭包输出在`SourceRecovery/Spine/`，保存真实bin、原atlas文本和按显式引用解码的PNG页面；`Analysis/spine-closures.json`区分缺失和未支持。闭包恢复不等于安装兼容且有许可的Spine runtime或动画通过。

原生薄层按128张纹理分批设置与同步加载，避免每张重复刷新。执行层可显式设置`MONKEY_NATIVE_BUDGET_SECONDS=600`或`MONKEY_NATIVE_DEADLINE_UTC`为本次授权窗口的UTC截止；预算在批次/阶段安全点生效，不能硬抢占阻塞的引擎调用，外层仍需核对进程真实退出。停止会写`Analysis/native-progress.json`，已有原生Scene/Prefab保持create-only，暂不支持凭进度原地续跑。

```sh
bin/monkey preflight --candidate outputs/game/UnityProject \
  --progress /path/to/Analysis/native-progress.json --out outputs/progress-check
```

进度必须匹配该候选import-plan SHA；`completed`也不代表编辑器验收通过，仍须`verify --level editor`真实回读。nativeResumeSupported=false不能当作自动重跑授权。

## 受控异步原生导入

`native-import`默认仅生成计划。实际执行必须显式加`--execute`，并由操作者保证本轮独立Editor/资源已获准。不会从历史窗口推导新许可。

```sh
bin/monkey native-import --candidate outputs/game/UnityProject \
  --out outputs/acceptance/my-new-run \
  --editor-path /Applications/Unity/Hub/Editor/6000.6.2f1/Unity.app/Contents/MacOS/Unity \
  --expected-manifest "候选manifest的SHA256" --budget-seconds 600 \
  --deadline-utc "YYYY-MM-DDTHH:MM:SSZ" --window-end-utc "YYYY-MM-DDTHH:MM:SSZ"
```

替换SHA和本轮UTC时间。内部截止至少比外层截止早30秒，当前外层窗口上限1小时；共享验证按实际批准的更短窗口。确认计划后同参数添加`--execute`可执行规划目录；参数/代码或输入变化需新目录，已有部分工程不覆盖。

宿主新建副本后直接启动已指定Editor的batchmode，固定`ImportBatchAsync`且不带`-quit`，等待包完成事件继续。`unity run`固定带`-quit`，不能用于这一异步入口。成功/失败/预算结束由薄层退出，宿主保存真实PID与退出状态，外层必要时仅普通terminate自己的child，无hard kill；未退出明确报attention。`execution-result.json`和`Verification/`分开记录启动、资源、原生回读和来源缺口。

这是生成工程的可选原生验收阶段；没有--execute时不会启动引擎。Unity已实际完成代表样本导入、独立Prefab/Scene保存重开和回读；每个新工程仍须核验自己的结果，不能沿用样本通过状态。

## 原名恢复与受校验重新规划

可恢复的config.paths优先，源_name其次，均无可靠名称才用unknown短ID。目标保留bundle和相对目录；原尺寸/字库atlas等派生资源有语义后缀，真实冲突才消歧。Analysis/name-map.json、package-name-map.json、decoded-name-map.json、module-name-map.json以及spine-closures.json记录映射与原因；中间缓存可以继续哈希命名。

名称规则更新可从明确支持的旧阶段生成新候选，无需重新执行未变化的reader/像素/AST解析：

```sh
bin/monkey convert --input-set inputs.json --target both --namespace SAME_NAMESPACE --reuse-source-stages outputs/FROZEN_OLD --out outputs/FRESH_NEW
```

只接受完全相同的输入路径/字节/SHA及namespace；阶段owner清单和实际文件需全部一致，且算法为当前或明确支持的names-v1元数据迁移（838d05b）。旧候选只读，新的SourceRecovery初稿按RF/模块原名重新组织，不合并旧候选中的人工业务修改。像素缓存只作不可改写的数据复用；引用、meta、manifest和handoff随新路径重新生成。任一身份/算法/文件漂移直接拒绝，不静默跳过。原生回读仍需实际新窗口。

## Creator原生CLI执行

新生成的Creator候选可复用同一`native-import`入口，Editor按显式路径选择；计划默认不启动，实际执行须`--execute`：

```sh
bin/monkey native-import --candidate outputs/game/CocosProject --out outputs/acceptance/game-creator-new \
  --editor-path /Applications/Cocos/Creator/3.8.8/CocosCreator.app/Contents/MacOS/CocosCreator \
  --expected-manifest MANIFEST_SHA256 --budget-seconds 1200 \
  --deadline-utc INTERNAL_UTC --window-end-utc OUTER_UTC --execute
```

严格核验源候选后复制到全新CocosProject，仅本次child收到绑定路径/manifest的执行标志；等资产库和Scene都返回true后调用一次原生导入。普通打开工程不自动执行。进度/首错/执行结果在acceptance目录，保存后核实际文件SHA和原生回读；退出0不等于原生通过。旧候选没有新执行入口时明确拒绝，应重新生成，不能借用其他已打开工程。真实3源图/76节点样本已完成16原字体、3独立Prefab和Scene保存重载，几何/内部引用核对及editor/static验证通过；全量、原版视觉和游戏业务尚未通过。

## 一次调用完成生成和原生阶段

```sh
bin/monkey convert --input-set inputs.json --target both --out outputs/game \
  --native --unity-editor /path/to/Unity --creator-editor /path/to/CocosCreator \
  --native-out outputs/game-native --native-budget-seconds 1200
```

适用于全新包级转换；`--source game.wxapkg`/APK/资源目录也可。单目标只提供对应Editor；指定的文件必须是已安装的相应可执行文件，不安装引擎。输入、候选与原生输出不能重叠，原生目录已存在则在转换前拒绝。

每个Editor在开始自身阶段时固定28分钟内部截止及30分钟外部截止，预留2分钟正常退出，不顺延当前阶段。Unity→Creator串行，前者未退出、方法错误或有回读差异时停止；只有明确的源组件缺口且回读零差异时可继续下一端。两端完整运行的总时间可能超过30分钟。默认不带`--native`只生成候选；`--native`不能与`--offline`、`--resume`或slice recipe组合。

`conversion-result.json`保留生成事实；独立原生根目录的`native-orchestration.json`记录顺序与阶段结果，每个子目录保存实际工程、执行结果及Verification。`completed_native_stages`只表示原生阶段执行完，源组件、原版视觉和业务缺口继续保留，不能据此宣称完整游戏转换。

## 明确CDN清单的获取与转换

```sh
bin/monkey convert --input-set inputs.json --remote-manifest downloads.json \
  --remote-cache-root /path/to/cache --target both --out outputs/game \
  --acquisition-out outputs/game-acquired --remote-budget-seconds 900
```

`downloads.json`可为文件数组，或`{"schemaVersion":1,"files":[...]}`。每项为`{"url":"https://cdn.example/remote/bundle/config.hash.json","path":"remote/bundle/config.hash.json","sha256":"可选64位SHA256","bytes":123}`。需要明确`--input-set`维持来源身份；不扫描CDN目录、猜测地址、携带URL用户名/密码或执行下载内容。签名查询参数仅用于请求，生成回执记录URL哈希及origin，不复制完整查询参数。

最多50000项、32个明确origin、4路下载，单文件128MiB/总量1GiB；获取窗30..3600秒，默认900秒，内部预留20秒收尾。跳转只允许清单已声明origin。缓存只有SHA匹配才复用；已在原输入范围内不重复复制，不改原件。新下载/外部缓存进入独立`files/`根，生成新的输入集；身份不符放Quarantine，404/缺失/失败逐项记录。没有预期SHA时，下载后SHA只是本次观察值，不声称核对过原厂哈希。

`--offline`只核对缓存，不联网。清单存在缺失项时仍可转换已取得文件，状态保持partial并记录missingFiles；每个目标的`Analysis/acquisition.json`及候选manifest包含获取证据。新增文件时不能套用旧`--reuse-source-stages`；获取结果会保留，应使用新源阶段。可与`--native`组合为获取→生成→顺序原生验证；原生输出须与输入、候选及获取目录分开。

## 有界原生布局替换

`native-layout-audit / native-layout-prepare / native-layout-patch / native-layout-finish` 用于已冻结项目的精确布局子集增量，准备、原生执行和可采用增量分别记录。窗口、正常审批、失败保留与当前支持边界见 [原生布局增量修复](NATIVE-LAYOUT-PATCH.md)。

### 中文命名与游戏配置表

新导出的目标工程文件/目录使用无声调拼音，再应用 Unity/Creator 原有大小写规则；同音文件按稳定源身份消歧。`Analysis/Mappings/*name-map.json` 保留原中文名称与目标路径；源游戏只读，JSON 键和值、界面文本、骨骼 region 名称不改。原始输入缓存保持源路径供哈希追溯。

整包 `convert` 自动识别已支持的 BON 配置，不需要另加参数。进入 `Docs/CONFIGURATION.md` 可直接打开逐表 JSON，机器索引为 `Analysis/Mappings/config.json`。样例项目主表位于 Unity `Assets/Game/Content/Config/Base/`；地区配置独立保存，语言表位于 `Content/Strings/<Locale>/`。目前支持有静态 decoder 证据的 BON tagged-le-v1；其他二进制、含 Binary/Date 的表列 needs_adapter，不能仅将 `.bin` 改后缀。JSON 导出不代表游戏运行时已接入这些表。

已有工程应重新生成到新输出，使用 `layout-migration` 核对 GUID 与路径差异后受控迁移；不直接批量重命名旧工程或改原包。Unity 来源的脚本类型名、Resources 动态键和第三方固定路径仍有身份约束，不能脱离消费者直接改名。

### 统一资源目录（monkey-project/2.0.0）

```sh
bin/monkey convert --package --input-set /absolute/path/inputs.json --target both --offline --out /absolute/path/new-output
```

Unity：`UnityProject/Assets/Game/Content/<Type>/<Module>/`。
Creator：`CocosProject/assets/resources/<Type>/<Module>/`。

两端类型、模块使用 PascalCase；中文名字转拼音，源 bundle/采集目录保留于台账，不生成 Group/Local/Remote/Bundles 目录。`--layout` 支持 modules/renames 等规则，partitions 已取消。语言与小游戏位于对应类型下面。

Scene/Prefab/Animation 原生文件由 `native-import` 或 `convert --native` 阶段生成；离线计划不等于原生文件。`Docs/RESOURCE-LOADING.md` 和 `Analysis/Mappings/resource-paths.json` 提供原始键、sourceId、目标路径与加载键；闭包目录不是可加载的单一资源。

`resource-catalog.json` 记录完整纹理与 Shader 源代码，`spine-closures.json` 记录骨骼/atlas/页图。Unity Addressables/AssetBundle 与远端构建未配置，业务运行/播放/渲染仍单独验收。

图片统一使用 `Textures/<Module>/`，不再生成 Sprites 目录。保留 Sprite 导入设置与引用；仅合并字节一致且无独立绑定要求的附加完整纹理，尺寸/裁切不同的图片不强行删除。`resource-catalog.json` 记录纹理别名；Spine/字体页图仍留在对应闭包旁。


## 0.5.0.dev1 冻结证据查询

新增流式 `query-methods`、带hash嵌套ZIP的 `query-tables` 和精确URL/内容身份的 `inspect-aliases`。只读来源、隔离输出；签名/映射不计方法体，listing不计全载荷验证。完整参数、预算和代码证据role见 [EVIDENCE-QUERIES](EVIDENCE-QUERIES.md)。这是显式开发入口能力，稳定安装0.4.0不自动升级。


### Checkpoint a large Unity export plan

The public export reads the manifest and plan once each. Each document has a 256 MiB limit, a 16-million-value budget (including keys), and depth limit 96. For resumable transfer, pin the original manifest and run:

```sh
monkey shard-unity-plan --plan STAGE/plan.json --expected-manifest MANIFEST_SHA256 --out SHARDS --max-new-chunks 100
monkey shard-unity-plan --plan STAGE/plan.json --expected-manifest MANIFEST_SHA256 --out SHARDS
monkey restore-unity-plan --index SHARDS/index.json --expected-index INDEX_SHA256 --out NEW_STAGE
monkey export --plan NEW_STAGE/plan.json --out UNITY_PROJECT
```

A bounded run exits 1 when paused. Complete sharding returns the index fingerprint and exits 0. Retries check existing content by SHA-256. The index covers the original manifest and every owned stage file, including source plan, scripts and resource copies. Restoration verifies each file and the original ownership table before publishing a fresh directory. The final export applies Unity's component and source-contract checks. External source evidence referenced by absolute path must still be available for checks that require it.

For a source-linked diagnostic capture, run `monkey prepare-context-preview --project UNITY_COPY --source-manifest SOURCE_MANIFEST --parent-id PARENT --target-id TEMPLATE --out REQUEST_KIT`. The kit pins the actual import instruction, saved parent Prefab and each matching source occurrence. Use the request and included Editor helper in a fresh isolated batch copy and invoke `MonkeyImporter.CaptureContextPreview` in the shared Editor slot. Inspect the resulting frame in its parent context before assigning any visual verdict.


用 `monkey capabilities --json` 查看 `byteBudgets` 三项默认限额。包转换回执记录整批展开字节数和最大条目的实测大小，Unity 验证回执记录导入指令文件大小。超额时 CLI 返回含对象、测量依据、实测字节数、有效上限及单位的 `byteBudget`。1 MiB = 1,048,576 bytes，恰等于上限时通过字节检查。单根展开及原始容器的独立上限为 1024 MiB。

### 在隔离副本重试 Button 目标材质

当颜色过渡 Button 的目标 Sprite 因自定义材质被交接时，可用下列命令准备新的 Unity 候选。输入为完整导出候选、其 manifest.json 的 SHA-256、对应的 plan.json 和原始归一化 IR。

```sh
monkey prepare-button-material-retry --candidate ORIGINAL --expected-manifest SHA256 --plan STAGE/plan.json --ir NORMALIZED/ir.json --out NEW_CANDIDATE
```

工具按来源组件核对 Button 目标、平铺 Sprite、原始 SpriteFrame、材质和 Effect。成功回执列出目标数量、不同来源组件数和新候选指纹。导入指令沿用原始字节。用新指纹在共享 Editor 槽执行 native-import，然后检查保存重读的 Button.targetGraphic、Image、Sprite 和材质。

Unity 保存每个来源 Prefab 后会在 `Analysis/Readback/Prefabs/<GUID>.json` 写入独立回执。dev38 回执含导入指令、来源清单、Prefab 和 .meta 的 SHA-256，以及准备、布局、保存和读回各阶段的毫秒数。保存阶段包含排序准备和初始节点采样，读回阶段包含独立预览。只有写完的回执才以 .json 发布。中断后可据此逐项核验已落盘文件；共享模板和实例的内存替换状态仍需在新的隔离执行中按顺序重建。整包验收继续要求最终场景和 Prefab 的重开证据。

对于保存逐根回执的大型 Unity 导入，先记录 `Analysis/Readback/editor-readback.json` 与 `source-prefabs-readback.json` 的 SHA-256，再对已有执行副本运行：

```sh
monkey verify --level editor --candidate NATIVE/UnityProject --out NEW_REPORT \
  --editor-readback-sha256 EDITOR_SHA256 --source-prefabs-readback-sha256 PREFABS_SHA256
```

两个指纹共同启用 JsonUtility 聚合回执读取，单份最多 1024 MiB、4000 万个结构标点，单行记录最多 32 MiB。工具核对两个阶段共有字段的签名，并按导入指令顺序将每个 Prefab 与独立回执、Prefab 及 .meta 指纹对应。报告的 aggregateReadback 记录两份文件的原始指纹和顺序签名。退出码 1 表示已有完整或部分验证结果，具体差异见报告。

双指纹模式将完整逐项报告存为 verification.json.gz。verification.json 和 manifest.json 提供分类计数、阻塞样例及压缩文件的 SHA-256。

在 macOS 上转换 Cocos Creator 2.4.15 bundle 的系统字体 Label，可在普通 Unity 转换命令加上 `--unity-system-fonts coretext`。该选项解析本机字体，按本次源文字生成所需的静态回退图集，并将指纹传给 Unity 计划。示例使用 bundle 声明的全部资产：

```sh
monkey convert --source /absolute/bundle/config.json --all-assets --target unity --unity-system-fonts coretext --offline --out /absolute/new-output
```

Unity 工程位于 `new-output/project`。包转换 `--target unity6` 也接受同一选项。字体解析与图集生成回执保存在此次转换的 SystemFonts 目录中，记录实际字体、来源文字和生成参数。
