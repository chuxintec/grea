# Creator 3.8.7 来源资源子集

开发分支的包级 `convert` 支持 `cocos-3.8.7-bundle`，输出Unity6/Creator3.8.8/both。单目录/明文wxapkg从本次输入的settings.*.json/CocosEngine=3.8.7辨认；多根input-set可明确sourceProfile，但仍需该原始版本证据。不是把2.4配置默认值改成3.8，也不宣称全部3.x版本已支持。

```sh
monkey convert --input-set sources.json --target both --out fresh
```

共用经验证的compiled-v1字段/引用解码，资源投射单独处理3.x具名rect/offset/originalSize与布尔rotation。完整保留UUID或源短hash加@子资源标识；Frame→Texture2D→ImageAsset必须来自明确对象引用，不能用同名图片或剥离后缀猜关联。纹理数组pack只支持单图2D section，未知mip/多图留缺口；sampler原参数保留但行为尚不宣称转换。只接受中心pivot、quad mesh和100 pixelsToUnit的当前几何子集。

配置redirect的依赖索引可为规范十进制字符串。pack版本可按UUID表中的pack索引登记；双重版本不一致仍拒绝。相同资产在多个pack出现时，仅比较实际提供的完整解码文档；不一致报冲突，缺失与未知section不静默填充。

3.x节点局部变换、UITransform及新组件尚未移植，源Scene/Prefab保留正文并报COCOS3_GRAPH_ADAPTER_PENDING，不套2.4默认零位移/尺寸。Spine、复杂源代码与缺失配置包保持待补。所有原件在候选外/SourceRecovery留存，Player不解释Cocos节点图。

实际下方了修订70：3原wxapkg和472可见缓存映射，496个输入/38081754B；4804正文、986源Frame形成1972 trim/full变体。两端独立编辑器资源导入/保存重开/尺寸与引用回读0差异；Unity还有986个预览引用及rect逐项验证，明确sourceGraphVerification=not_run。119源图、35图像边、3124复杂代码草稿、两原始zip配置包和视觉/玩法未闭合。详细窗口和不可变候选SHA见PLAN。

原生05曾因资源gallery误用源节点边界检查失败，进程退出且Creator未启动。修正为独立的gallery引用/几何强检查，非空源图仍走原检查；06在新候选/新窗口通过。旧失败不改，资源预览不当作源UI或玩法恢复。

2026-10-24新增[3.8.7静态源图适配](COCOS-3.8-GRAPHS.md)：119图中83图/810节点/81 Prefab经双端原生保存重开/引用/几何强核；36嵌套实例或override图保持隔离。原资源06 gallery证据未改写，新增07 Unity与08 Creator证据分列，不把gallery当源UI恢复。
