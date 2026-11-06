# Creator独立源Prefab适配

代码11ccef4新增共用源图边界校验与原名Creator Prefab路径，薄Editor层通过cc.instantiate、cc.Prefab.data、EditorExtends.serialize构建；asset-db.create-asset原生保存，assetManager.loadAny和cc.instantiate重载。API依据为本机Creator3.8.8 engine/cocos/scene-graph/prefab/prefab.ts公开data/createNode实现，未运行来源脚本。

每份独立Prefab验证源根与子序、局部位置/旋转/缩放/尺寸/锚点/active、组件存在与字体/图片资源、Button/ScrollView/Widget内部引用。根Widget父引用重新绑定到独立根的null父，不携带聚合Scene的DesignRoot。源ID→独立路径保存在source-map/import-plan；保存证据与实际UUID在editor-readback，静态verify不把计划视为原生文件。

公开CLI以05已核源阶段生成outputs/full-sample-game-06-creator，1694计划、17201文件/884709704字节全入账，manifest7c47d0b55c1c2d4acf108281214f76956365d3c216f866977661a4d21e7b238a。static/name/routing审计均零问题，非名称IR同05，16978 UUID不变，源reader/像素/AST未重跑，Spine1776页复用。原生、视觉、业务not_run，需独立Creator窗口，不能把decoded JSON或Prefab计划报为已保存。

Unity full05随后证实10节点20份Layout互相冲突，保护同步适用于Creator；53a7256逐组件列MULTIPLE_LAYOUT_HANDOFF，保留源几何，不选任意方向。06冻结为适配首版，包含冲突保护的新full07正在生成，作为下次必要原生验证候选。15项定向Python检查通过；新增三个Creator JS模块node --check通过。这些仅证明离线合同与语法，未证明Creator运行保存。

## full07修复候选

公开CLI convert --target both --reuse-source-stages outputs/full-sample-game-06-creator --out outputs/full-sample-game-07 --offline，以53a7256生成；20份冲突Layout逐组件handoff，双目标各1694独立Prefab计划，结构和资源身份同05。Unity [private fingerprint omitted]；Creator61e7d81006580f6039572b2d9197d68bb65a91dffcbcbb5949553ec3e2c5aca6。两端1776Spine闭包、零图片解码、全复用，sourceReader/pixelDecoder/AST均未重跑。双端static/name/routing审计零问题；原生仍not_run。
