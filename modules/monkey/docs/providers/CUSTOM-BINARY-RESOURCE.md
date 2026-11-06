# 自定义二进制资源格式储备

当前 `egret-custom-resource-plist-v1` 是按既有来源检查形成的格式 profile，覆盖 Egret/EUI 的自定义资源包装。历史来源身份、包标识和私人校验值已从发布文档删除；文档说明的是格式处理边界，不代表对新样本的复测。

## 公共命令

显式input-set的sourceProfile取`egret-custom-resource-plist-v1`，可自动选择此资源格式；只允许Unity6。

```sh
bin/monkey convert --input-set source-tables.json --target unity6 --out fresh --format grea --offline
bin/monkey convert --input-set source-tables.json --target unity6 --out fresh-with-remote \
  --remote-manifest exact-files.json --remote-cache-root verified-cache --format grea
```

第一条读包/目录、核本次脚本中已审阅callback SHA和BinJson变长整数的词法绑定，解析3类数据；第二条复用统一acquisition，显式URL/path/SHA/bytes清单→有界GET或核缓存→独立acquired root→相同解析/像素/原生出口。下载代码从不执行，源资源路径必须精确匹配，不按basename或近似hash替换。不可用远端仍留missing。可加`--native --unity-editor <existing-Unity6>`，只在自有副本导入/保存回读；不隐式连接原服务器。

## 格式与边界

- 资源清单：zlib数据、big-endian u16路径前缀数、原变长整数类型/数量/文件名/前缀索引/后缀/字节数、sheet子键/九宫格字符串、按原资源顺序的group索引。原imageWithGrid/ktx等枚举仍保留，不猜地址或改类型。
- Plist pack：原sheet名、精确body字节长、frame名称/rect、trim flag、带首字节sign-magnitude的offX/offY、sourceW/H。原图像键为sheet名`_png`，source frame身份包含原清单/图集/帧名。
- BinJsonUtil VERSION 2：字符串表、具名对象/数组、整数、布尔/null及有限小数，EUI Skin保留完整原数据/$path。未将此Skin格式推广为未知config.bin的格式；原config payload仍隔离且待适配。正式运行时JSON配置另需确认产品schema。
- 源脚本整体用Acorn tokenizer扫描，候选≤64KiB表达式单独静态parse；BinJson所处小脚本≤2MiB再核helper词法scope。曾对9.9MiB整脚本建AST触及256MiB限制，已改tokenize+候选解析，没有提高预算或执行JS。脚本≤32MiB、总64MiB/128个、单worker30秒/总120秒；AST/Token另有限额。
- zlib单源≤32MiB、展开≤64MiB，整批展开≤128MiB；资源/帧≤200000、Skin≤50000；值深度128/总4M。截断/尾字节、越界字符串/组索引、重复对象键/图集帧、大小不符或路径冲突拒绝。
- 已闭合PNG/JPEG图集复用既有像素归一器。原top-left trim转中心offset后检查像素边界，生成trim/full两种Sprite资源；不补占位像素。负偏移导致无法完整放回原尺寸等情况保留原记录并列明确缺口。切片合计64M像素，单图16M；独立原图预览与真实源切片分别计数。

原件在SourceRecovery/Original；来源callback范围/SHA、词法helper、资源/图集/Skin、逐帧物化映射在Analysis/Egret。JSON与源程序均不进Assets；只有被实际验证的图像切片进入编译/导入根。每工程有聚合AI任务和自包含START-HERE，源Skin还不是原生UI图。

## 实际已验证层级

早期来源检查记录了清单、图集和皮肤数据的部分可用性差异。具体来源名称、数量指纹与候选日志已删除；该记录属于历史证据，不能替代当前素材/源码恢复验证。

基于入口中的**默认**inChina=true/testMode=false分支及生产CDN literal，按清单原哈希文件名取得53页：52 GET+1已核缓存，共7975531B，53/53可用，未尝试其他地区/猜文件名。真实runtime是否覆盖默认参数未观察；本次URL选择和取得文件SHA均单列来源回执。Emoji页1537×509/290374B，SHA61142f5aabd84a130c11505855b6fc0e2efee703a57baa5859d638279fe8d104。

公开09 `convert + explicit remote manifest/cache + grea + native`：41输入19403340B，132源切片+17独立图预览，298Sprite变体。Unity own8815于2026-10-24T01:07:12.912716Z→01:07:24.952861Z exit0/reaped，方法1.18秒；strict0/editorpartial，GUID/rect/尺寸/引用和保存重开通过，源节点0/sourceGraphVerification=not_run。候选manifest229847969e423e63de80ace23bba5121b437cbdeeae0c74ccae3900abaea7607。132 trim/full对原页逐RGBA核验在pixel-audit-08，源代码未执行。

公开全53页offline10：93输入27088497B，53页闭合/1920源切片/69派生整图，资源声明81可得/48171未提供，Skin仍3026。1920切片及3840目标trim/full变体逐像素相等，manifest47277e354e8674ad02570cb152369e8c78adc835386ad1d9d1112a4ba64e1a62。全10的Editor未跑，不能把09代表结果改写为全10已原生通过。证据outputs/egret-linghuashi-atlas-pixel-audit-10/audit.json。

27项资源/缓存/编排定向检查、35项关联格式检查通过。原生UI布局、动画/字体、原方法及业务仍pending；后续主优先转当前缓存身份核验、样例项目/样例项目补源、真实嵌套Prefab/override与动态布局。
