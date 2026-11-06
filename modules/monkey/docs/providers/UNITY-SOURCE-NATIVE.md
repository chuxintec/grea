# Unity 源包的公开原生验证

`convert` 的 Unity 来源可显式追加 `--native --unity-editor <installed-Unity>`。默认输出统一目录的候选；`--format none|grea` 为兼容别名，不再控制目录迁移。当前精确目标 6000.6.2f1，不安装或切换引擎。原生验证目前只接受下述叶 Prefab 子集，整包资源核验不等于此原生入口支持整包导入。

```sh
monkey convert --source <original.bundle> --target unity6 --out <fresh-output> \
  --provider-python <UnityPy-1.25.3-python> --asset-ripper <AssetRipper-2.0.0> \
  --unity-dependency-manifest <frozen-bundles.json> \
  --unity-texture-cache <exact-texture-cache.json> \
  --native --unity-editor <Unity-6000.6.2f1>
```

本期 `unity-leaf-prefab-sprite-array-v1` 只接受一份原生叶 Prefab、一个嵌入结构的组件/字段类、名称保持的 Sprite[] 字段与精确水合的非变体图集。场景、多组件、借取字段尚未落入实例、缺依赖、null 数组元素、未证明的图集状态、同名资源歧义等，在启动 Editor 前阻断原生段，成功的基础导出保留。null 数组与空数组长度独立核对，不补空资源或猜像素。

未发布的本地维护补充了受限 FlipVertical 紧密网格、显式 DDS/DXT5 缓存和逐帧真实身份读回。位域、原生像素验证策略及不支持边界见 [Unity atlas subset](UNITY-ATLAS-SUBSET.md)。正式 0.6.0 制品不因此改变。

原 PPtr 沿 container/serialized-file 的原 external 表精确解析，decimal pathID 与目标 localID 分列。目标通过唯一源资源名和真实类型匹配，再核原生 GUID/localID、逐项引用顺序、图集 rect、纹理 GUID。PNG 像素按固定纵向方向转换，与源水合 RGBA SHA 比较。Root 名称、active 与 Transform 值保存重开后保持；实际 MonoScript 绑定与声明字段类型/长度、缺脚本均核对。方法不恢复，也不调用源游戏代码。

下述 v0.2 历史格式验证只为已证明的 Sprite/Texture 生成资源移动，保留文件名；当前布局以 PROJECT-SPEC.md 为准。全部既有 meta GUID 在 Editor 前后封存。真实《武侠》样本 134 项全部固定，**实际移动 0 项**；当前正向 native 移动仅有实现与定向计划反例，不能称已用真实游戏证明了资源搬移。

原生段检查实际主 Editor 冲突，仅新副本和自有子进程；方法≤1200秒，固定28分钟内部/30分钟外部截止，正常TERM与回收，不强杀。失败保留 none 基线及 native 工作区；通过后显式 grea 晋升清理过缓存/helper/probe 的独立工程，none 基线放 Unformatted/UnityProject。已导入或人工修改的任意工程仍不是通用迁移对象。

2026-10-24公开真实验证：首次 own98320 因探针副本文件名 Roundtrip 导致根名变化，exit1/reaped，旧失败冻结。改为独立目录内沿用原 Prefab 文件名，没有降低名称/几何检查。新 own98633 于2026-10-23T23:27:07.437151Z→23:27:14.025354Z exit0/reaped，20项检查全true，131引用、一个字段、3张精确水合纹理、136个既有meta GUID、保存重开通过。原none manifest `[private fingerprint omitted]`；受限grea工程manifest `[private fingerprint omitted]`。证据 paths 为 outputs/unity2021-wuxia-native-package-02[-native]，不进入发行包。

启动包另补齐精确3张远程纹理，6键全部水合后输出 outputs/unity2021-wuxia-startup-package-03：7实际输入6442729B，Provider own99060 exit0/reaped、2408文件12417811B/44原生资源/0unreadable；1142份源代码隔离、0字段类、91源对象无结构。manifest `[private fingerprint omitted]`。**启动整包native/原方法/玩法未验**，配置Prefab证据不能替代它。旧02普通沙箱Provider在loopback启动超时并正常回收，03使用允许本机loopback的执行环境成功；所有旧失败不覆盖。
