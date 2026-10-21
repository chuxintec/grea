# Cocos目标工具（开发候选）

`cocos_project` 创建全新3.8.8五层Signal Counter工程，`--width/--height`配置设计尺寸。JSON运行时读取，纯层无cc依赖，输入与生命周期在Presentation/Bootstrap装配；不含原游戏资产。存在输出拒绝，grea-generated.json记录模板版本与文件摘要，不表示已Editor/浏览器验收。

`cocos_convert`支持未编译2.4.15→3.8.8基本对象数组及同代3.8.8有限对象。输入.fire/.scene/.prefab；--asset-map可提供 `{assets:[{source_uuid,target_uuid,source,target,sha256}]}`，source相对map路径、target以assets/开头。当前外部资源仅JSON/文本/音频；Sprite/SpriteFrame/纹理/外部字体/图集/Mask/动画/自定义脚本等返回unsupported。0为有限序列化候选，1为有明确未支持/闭包问题，2为坏输入/IO；不执行来源脚本。

入口、支持边界和实际导入流程以 [Cocos技能](../../plugin/skills/grea-cocos/SKILL.md) 为准。生成与转换不能替代Creator导入、TS编译、浏览器真实输入和目标渠道验收。

`cocos_project --audit-project PROJECT --output new-layer-report.json` 保守筛查五层的字面量import/export/dynamic-import引用、反向依赖与环；计算式加载/外部依赖精确报需审阅，不冒充完整TS解析器。生成器不依赖本机Editor/Node；实际类型检查与浏览器运行另记。
