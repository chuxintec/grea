# Creator 3.8.7 静态源图子集

从已解码原图读取 Node 的 _lpos/_lrot/_lscale，UITransform 的尺寸/锚点，UIOpacity，以及 Sprite/Label 的渲染颜色。省略字段按固定3.8.7官方声明取默认值；不会把3.x对象直接送入2.4节点解析器并悄悄产生identity。原始字段与source object ID保留，UI几何组件吸收进Node时另留sourceGeometryComponents身份映射。

默认事实来自[Cocos官方v3.8.7源码](https://github.com/cocos/cocos-engine/tree/v3.8.7/cocos)，9个只读文件URL/字节数/SHA与默认事实见[固定来源表](../validation/cocos387-engine-baseline.json)。例如UITransform默认100×100、锚点0.5；Label默认文本/居中/字号、Sprite默认TRIMMED与原node/renderer字段各自读取。未执行或嵌入Cocos源引擎，目标Player仅原生对象。

当前仅静态、无嵌套实例/override的图。非空PrefabInfo.instance/targetOverrides/nestedPrefabInstanceRoots、PrefabInstance均整图隔离。多个UITransform/Opacity/renderer、错owner、未知vector tag/不完整named vector、未归一化Quaternion、disabled UITransform均拒绝。未知组件及尚未适配的Widget/Layout/Button/动画/Spine等原名/原数据保留，标supported=false，不能由2.4默认值误生成同名组件。Label/Sprite有限字段做显式投影；outline独立具名，shadow/grayscale/自定义材料或不受支持字体等继续handoff。静态数据保持不等于动态自动布局或玩法恢复。

原生读回在Scene和独立Prefab保存重开后检查几何、原生资源引用；新profile额外核局部opacity与实际已发出的renderer颜色。Creator保留原layer位并在host及Python验证层核对；Unity目标使用uGUI层5，原layer位作为provenance并明确camera/layer handoff。原Scene globals、摄像机/三维显示/输入及视觉未验收。

实际《下方了》496输入38081754B，119原图中83进入此子集，810节点、81 Prefab（另2静态Scene），908组件描述；36嵌套图隔离，35个原图像边缺件仍保留。986原Frame/1972变体不变。当前IR有118非白节点色、2非255局部opacity；只有实际发出的renderer进行原生颜色核验（Unity363 / Creator380个节点）。

07 Unity own1431于2026-10-23T23:50:14.643489Z→23:50:42.606725Z exit0/reaped，strict0/editorpartial；810节点/81Prefab/95Label/1字体。Creator07导出在unsupported组件source-map漏nativeType，未生成CLI入口，**Creator未启动**；该失败候选冻结。修复None状态、补全双目标全部入口预检和真实反例；08仅重建Creator，未重跑已过Unity。

08 Creator own2304于23:53:25.726798Z→23:54:10.873039Z正常TERM/reaped，strict0/editorpass，方法21.22秒；同810节点/81Prefab/95Label和资源保存重开通过。后补Python layer强核的editor级只读复验亦pass/0诊断，无新Editor；静态级验证不接受importer改写过的meta，不可拿static与editor层级混用。最新源策略对冻结08候选810节点/908组件逐项完全一致，证据在 outputs/cocos38-xiafangle-graphs-08-current-policy-audit/audit.json。

Unity07 manifest `[private fingerprint omitted]`；Creator08 manifest `[private fingerprint omitted]`。原资源06与失败07保持只读。34项定向检查通过，固定本项目可选ASTC运行时另核亦通过；未跑无关全库/全平台。
