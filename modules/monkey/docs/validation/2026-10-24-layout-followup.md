# Grid / child-resize 有限验收续修

依据总监事件 `monkey-v02-local-exit-review-20261024-01`，复用原IR、原图和失败记录补既定动态布局范围；原件、已验候选、v0.1及远端均未改。本记录覆盖本次有限缺口，整体v0.2出口仍待总监复核。

## 实际分布与归类

只读核对当前已规范化的样例项目2.4.15、冲关2.4.11、样例项目3.4.1，以及下方了3.8.7经当前resolver可读原图：共2500 Layout。19个affectedByScale Grid、13个child-resize、16个缓存多行Grid；另387个缩放线性布局。缓存多行只是源数据分布，不是运行通过。来源/分布/逐项guard见[源审计](layout-dynamic-source-audit.json)，私有完整审计SHA也在其中。

- 原有缩放线性算法已实现，但旧16节点代表的affectedByScale均为false，故本次补真实缩放代表。
- Grid缩放/固定行列/两轴起排以及resize=2原被Unity guard拒绝，是实际遗漏；现接原生uGUI Flow与线性子尺寸适配。上述32份必修配置不再被guard拒绝，不能推为32份都已原生实跑。
- 保留47份其他guard：27个负缩放线性、19个NONE模式、1个浮点padding；没有借本轮实现所有组合。5份缺精确模板图仍不进入可解析分母。
- 不新增任意mounted/removed、Creator根继承、原方法或游戏业务恢复。

## 实现与版本依据

NativeFlowLayoutGroup使用普通RectTransform/LayoutGroup/ContentSizeFitter，处理行列约束、缩放边界、子尺寸及换行；NativeLinearLayoutGroup补child-resize。轻量输入观察器针对尺寸/缩放/显隐/顺序变化标记uGUI重建；不在Player存源ID、源图或解释器。

行高推进依据[官方3.8.7 Layout](https://github.com/cocos/cocos-engine/blob/v3.8.7/cocos/ui/layout.ts)核对，并与已冻结3.4.1 SDK字段合同对应。2.4.15仅作行为参考，不复制/分发旧引擎代码。新组件保留3.8.7 MIT版权与许可，包中有独立许可证，生成C#也自带完整许可头。

新增probe v2：记录每个子节点的尺寸/位置/scale/active及顺序；验证增、隐、显、删、容器尺寸、子缩放、子尺寸和隐藏恢复共9态。旧候选缺v2字段仍走旧证据合同，不改写历史结果。更新只对实际声明驱动的轴放行；没有把所有布局差异忽略。

## 有界原生代表

|真实来源|规模|最终Unity / Creator|布局组/状态|逐子节点跨目标最大差异|
|---|---|---|---:|---:|
|下方了WorldMainView及精确模板|44节点|grid02 / grid01|1 / 9|0.00007325 px|
|样例项目PlusOneWindow、DigGameWindow|148节点|children04 / children02|3 / 27|0.00004883 px|
|下方了SeasonGiftItemShuraSeal及精确模板|74节点|linear01 / linear01|2 / 18|0.00000187 px|

两端6份最终原生输出均严格0诊断，保存重开及来源Prefab读回通过；Unity仍editor partial保留源业务缺口，Creator三组editor pass。总计54态、1242个几何数值，阈值0.05px。机器回执：[layout-dynamic-native.json](layout-dynamic-native.json)。所有自有child正常回收，不运行原版JS、不改样例项目工程或桌面。

本次检查是原生Editor强制更新后的状态及保存重开；Player逐帧调度、性能、原版视觉/输入和完整玩法not_run。未覆盖组合仍按矩阵，不能声称全部布局/全部版本兼容。

## 失败证据与修复范围

Grid01两端各自严格通过，但跨目标发现缩放后行高差83.8px和隐藏新增子节点位置差172.6px。按版本源码补行高推进，并保持Flow子节点相对父pivot的锚点；Grid02 Unity对未改Creator01通过。后续Creator只改独立Prefab临时上下文，Grid来源两根节点均无Widget/Canvas，动态probe路径不变，因此复用该对照，不重跑Grid。

children01动态数值已一致，但Creator独立DigGameWindow在无UITransform的临时Scene下被根Widget调整到1280×720。现临时加入声明750×1334的原生父上下文，children02严格通过；该上下文不保存至Prefab。Unity02额外许可文件路径被所有权边界拒绝，未启动；Unity03许可头截取错误导致编译失败，已修复并先离线SDK编译，再用children04通过。旧失败保留，不改成pass。

232项完整工具测试通过，另有安装SDK的C#编译和JS语法检查。运行时未新增依赖。旧分发包01仍保留认可证据；新源码影响分发，最后一次更新本地包与隔离安装回执后回报总监，不推送或发布。
