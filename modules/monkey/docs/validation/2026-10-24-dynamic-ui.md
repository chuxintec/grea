# 原生动态 UI 与真实源上下文

本组把 Cocos 3.8.7 Widget/Layout 序列化字段接入公共 IR，保留边缘/中心、绝对/比例偏移、更新模式、布局方向、容器模式及缩放语义。Creator 使用3.8.8原生组件；Unity生成常规uGUI矩形约束、线性LayoutGroup、TMP及ContentSizeFitter/ILayoutElement，不在Player读取或解释源图。

Creator不再固定Label为CLAMP、Sprite为CUSTOM。原生Label四种overflow和Sprite自动尺寸模式保留；Unity已实现NONE/CLAMP/SHRINK/RESIZE_HEIGHT，其中本组实际动态验证NONE与RESIZE_HEIGHT，其他模式仍需代表验证。Unity线性布局支持固定/容器尺寸、方向、缩放及保留独立横轴/纵轴坐标；网格/子节点resize/负scale等其他边界明确列限制，不冒充全模式已验。

TTF行框按源行高及额外leading配置为独立原生布局组件，文本和宽度变化后重新计算，不写死preferredHeight。0.26比例核自[官方v3.8.7 text-utils](https://github.com/cocos/cocos-engine/blob/v3.8.7/cocos/2d/utils/text-utils.ts)及本机3.8.8。位图字体继续使用独立既有指标。Prefab独立重开提供同声明设计尺寸的临时原生Canvas，以获得真实换行上下文；不保存该临时Canvas或改共享资产。

## 实际证据

同一冻结原件中的 SysDialogPop 和 StarGroup，16节点/2Prefab、原字体/资源：

- Unity：`outputs/cocos387-dynamic-ui-real-05-unity-native`，own63064，exit0/reaped，严格0诊断，Editor总体partial保留未知源脚本/字形视觉范围。
- Creator：`outputs/cocos387-dynamic-ui-real-05-cocos-native`，own58136，正常TERM/reaped，严格0诊断/editor pass，全部1972帧的矩形/裁剪/边框及原生RECT网格读回通过。
- 每端4个真实代表：NONE改字及隐藏恢复；RESIZE_HEIGHT改字及恢复；Widget父尺寸/隐藏后恢复；线性布局增/隐/显/删子节点。Widget宽720→760→800；布局524→644→524→644→524。两端各阶段尺寸及位置差≤0.05px，最大差0.03549px（TTF字宽）；多行高度113→213两端一致。这是原生Editor状态测试，Player/原版完整游戏运行及视觉对照not_run。
- 保存前实际布局与保存后几何逐字段比对：只有启用且实际发出的组件声明驱动的轴可以改变，其余轴、层级、旋转、缩放、颜色与引用继续严格核验。缺少状态探针、初始几何、TTF行框组件或行高证据均失败，不能用宽泛忽略替代。
- 44项相关检查及已安装Unity SDK编译通过。跨目标状态回执和SDK文件SHA位于私有 `cocos387-dynamic-ui-real-01/`，原件只读。

## 已修复与保留失败

Creator02精确浮点相等导致收敛误判；03进一步给出真实反馈差值，发现手动Widget刷新缺少SDK的isAligning上下文。现按官方刷新协议在同步自有计算内设置并finally恢复，同时保留源target=null，不用显式父节点改变源语义。测试覆盖成功/异常后的上下文恢复。

Creator04动态和Prefab读回已过，但严格资源门拦下2张末尾图片：删除vertices使原生Importer失败并保留旧library。现在提供完整RECT网格元数据；1945份既有SDK网格对照一致，旧27份meta无vertices不当作新网格依据；05实际全部1972份原生网格重新核验。没有把04失败改写成通过。

Unity03因JsonUtility为缺省子对象创建对象，不能用bitmapProbe==null判断字体类型；现按实际字体计划。04新行框已生效，但独立Prefab缺Canvas使两行文本测量成一行；已补自有Canvas上下文，05保存重开严格通过。旧产物均保留。

## 真实层级闭包

119份图的离线差异审计仅改变PveFightUI：以Prefab.data为根排除3个脱离层级、仍残留_parent指针的旧记录，原始对象表与诊断保留。88→85节点、118→115组件，114份可得模板图全部父子闭合，5图仍缺6个精确模板。其他图hash不变。此为静态闭包修复，114图未作全量引擎/玩法验收。

接续：嵌套关系与新动态组件的代表集成，然后样例项目3.4.1专用读取/公开导出。Creator根继承、未知业务、未覆盖布局类型与真实视觉/Player验收仍分开记录，不以本组代替版本完成。


## 总监复核后的有限续修

上述16节点/4组是历史代表，不能证明Grid/child-resize或缩放线性。现已按实际分布补6组/54态，Grid和子尺寸用原生Flow/线性组件，详见[有限续修](2026-10-24-layout-followup.md)。旧候选和结果保持冻结。
