# 其他引擎的原始图片出口

开发版增加明确的 `--source-family laya|layaair|egret|eraget|custom|other`，目标只允许Unity6；Eraget归为Egret。当前通用出口是 **已提供原始PNG/JPEG的派生gallery**，不解析这些引擎的节点、图集切片或方法。显式family属于用户声明，精确源引擎版本保持unknown；不能把这个通用子域说成Laya/Egret全版本恢复。直接低层Creator plan同样拒绝此IR。

另有基于已审阅callback的[自定义二进制数据/图集profile](CUSTOM-BINARY-RESOURCE.md)，支持来源表、Plist/Skin数据与精确纹理闭包。样例项目当前166修订已据缓存同SHA、直接启动与运行时版本确认Egret5.2.32；不以历史gallery或该样本声称真实Laya已支持。

```sh
bin/monkey convert --source-family egret --source /path/to/decrypted.wxapkg \
  --target unity6 --out outputs/images --format grea
```

多包用schemaVersion=1/sourceProfile=`generic-image-resources-v1`的显式inputs清单；既有ID/路径边界仍适用。原文件逐SHA全记账并完整放在SourceRecovery/Original，源JS/Wasm/DLL/Lua不执行、不放进Assets。每张实际图片产生具备明确派生来源的全图Sprite预览；sourceSpriteFrames=0/sourceGraphsRestored=0/methodsRecovered=0。单图16M像素、合计64M像素/1024张导出预算；超出项明确保留待转。未知二进制清单和无图片的输入blocked，不生成空引擎工程。remote/native/format参数只按已实现合同处理，未知开关不静默忽略；专用远程清单、原图集和源代码绑定待后续adapter。

《样例项目》4原解密wxapkg，40展开输入19112966B；其中16张PNG/JPEG已生成派生gallery，所有输入均留原件。源default.res等实际是zlib后二进制，尚未解析，不能当JSON资源清单。02离线grea成功，早期01后处理API接线错误保留。

公开单命令03 `--format grea --native`：Unity94895于22:24:49.703592Z→22:24:58.927183Z exit0/reaped，strict0/editorpartial；32Sprite变体、16gallery引用强GUID/rect核对，源nodes0、sourceGraphVerification=not_run。manifest `[private fingerprint omitted]`。原视觉/交互/玩法not_run；本机没有额外真实Laya样本，Laya/custom入口只由自造反例验证。
