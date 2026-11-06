# Creator 2.1.2 资源子集

`cocos-2.1.2-resource` 从本次输入的原 JS 静态解析 `cc.ENGINE_VERSION="2.1.2"` 及唯一 `window._CCSettings={...}`。固定 Acorn 仅读 literal object/array/string/number/boolean/null 和数字 !/-/+；函数调用、计算属性、重复属性、spread及多份settings拒绝，不执行原JS或源模块factory。记录整个输入和原赋值字节范围SHA。原始13206项UUID表、packedAssets成员及md5AssetsMap版本用于精确定位，不能用缓存中另一版本代替。

旧缓存是文件名→时间戳的109项声明，`cacheKind=legacy-flat`只读取这些声明的确切文件；时间戳不是内容身份，实际SHA另冻结。导入pack按原顺序/成员数解包；不同pack同身份正文冲突拒绝。SpriteFrame content明确投射rect/offset/originalSize/rotation/insets，未知几何字段拒绝；纹理身份、版本与文件必须匹配。Prefab/Scene、AnimationClip、材质和方法只保留证据，不套2.4节点解释。

实际《样例项目》5个已解密原包+109缓存：129展开输入26806035B；211源Frame/38纹理依赖/81隔离图/1原生音频，956模块草稿、5源码来源待补、9Spine闭包待补。settings完整声明资产身份并集19298，本次未提供18955；这与当前已解析引用缺口0分开统计，不能称为全部资源已取得。

公开单命令02双端原生：Unity93877于22:20:45.832681Z→22:21:03.159315Z exit0/reaped；Creator94149于22:21:04.060650Z→22:21:26.613506Z正常TERM/reaped。两端strict0，Unitypartial/Creatorpass。Unity422Sprite变体、211gallery引用逐GUID/geometry核验，源nodes0/sourceGraphVerification=not_run；未恢复原界面或玩法。02 manifest `[private fingerprint omitted]` / `[private fingerprint omitted]`。

后续03只补充完整声明资产分母及缺源计数，不重复已通过的像素/原生段；211实际Frame及其资源投射范围相同。03 Unity `[private fingerprint omitted]` / Creator `[private fingerprint omitted]`。未知旧格式与其他1.x/2.x仍需独立adapter。

2026-10-24 当前147补源：5个当前原包、109项缓存索引冻结后，从源JS的WECHAT_GAME分支、`wxDownloader.REMOTE_SERVER_ROOT`及原settings的UUID/版本/pack成员取得7676个import、5415个native。JSON pack和原TextureUnpacker的`type=cc.Texture2D,data=...`两种封装分别核；5159纹理按原format索引选PNG/JPG，保留min/mag/wrap/PMA（目标采样/混合行为仍待适配），不按缺省.png猜地址。音频/粒子/字体从原_native字段和MD5Pipe路径规则导出；文件名型font_cn.ttf保留原UUID目录URL，不臆造同名地址。两份metadata和两张图片的瞬态URLError分别有界重试成功，没有目录枚举或猜hash。13091个精确资源全部可得并逐SHA冻结，19298个声明身份当前均提供。

源图、Spine、动画、BitmapFont等尚不被该资源profile消费的正文保留在原packed载荷；索引只记路径/成员身份/原件及解码SHA，避免把未消费正文重复膨胀成约900MB单个JSON。当前紧凑inspect约21MB。源版本不匹配的三个旧缓存项仍留证据，但生成工程排除它们，不与运行资产按内容去重；其中一张旧PNG不会进入Assets/assets。原件与缓存索引不修改。Prefab/Scene等旧格式结构及方法继续是独立缺口，不以资源全得替代原生恢复。

公开07命令（`--input-set ... --target both --offline --reuse-source-stages ...`）实际13220输入/1228708650B，合并预算显式2GiB。source阶段算法/hash与06完全相同才复用，7343源Frame、每端14686变体、249音频/1字体；旧缓存三项过滤、原字节留SourceRecovery。Unity manifest93502f5cfd2e0a1ba9a65608221e77621b8cf69e8b11698e81843388d4c3f0d3，Creator872235edc8036c39f824efbceadd47eeabf926f1993c8f1d1d6d121dd3978304。双端static pass/0诊断；7343全部原几何/纹理身份匹配，48代表Frame覆盖13组合（PNG44/JPG4、旋转/裁切/offset/insets）96像素变体逐RGBA相同；双端29372目标PNG载荷hash均匹配正确语义（Creator trim使用完整页+原生trim元数据，不能拿trim PNG字节假比）。当前全07 Editor未跑，旧211代表Editor证据不追认全量。资源图和Spine等6546项继续隔离，956模块草稿及5wrapper待补。
