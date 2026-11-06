# 2026-10-23 有限 UI 动画模块验收

CONTINUE-03只接续既有v0.3的有限AnimationClip/事件清单。真实Unity/Creator实导主线仍优先，资源未获准；本包未启动任何引擎。既有`unity-reward-v03-02`和`creator-reward-04`保留用于原生页面验证，本次仅创建新输出。没有反复读取21份旧证据或重跑15项基线。

## 实际来源与选择

奖励页已有`Rewards_Show`，但使用sineOut缩放/透明度，本子集不近似改写。只读检查已有冻结bundle后，选`Prefab/Merge/LevelBox/CellBoxReward`（gameAsset索引1504），其原生cc.Animation组件#16明确引用`CellBoxClicked`（索引3225，UUID [private identifier]）；不是凭动画名猜目标。24个依赖资产的输入闭包按现有inspect/normalize执行，原件只读。

该0.5秒剪辑的根x摇动与item节点y/scale(x,y,z)/opacity生成6条标量轨道，源时间与目标节点对应已回查。BubbleIdle.active、lock.active两条轨道明确unsupported，因此是partial clip子集；不自动播放，不冒充完整CellBoxReward表现。真实剪辑没有事件，事件合同用明确标识的合成fixture测试。

## 产物与检查

- `.private/animation-inspect-01`、`.private/animation-ir-01`：复用源reader，新增可选animationSchemaVersion=1与animationClips；旧IR仍可读取。
- `.private/animation-unity-plan-02`、`.private/animation-creator-plan-02`：同一IR和同一显式source Clip选择；时间/值/linear-step、节点/相对路径和目标单位分开记录。
- `outputs/animation-unity-02`、`outputs/animation-creator-02`：双目标候选，静态pass；对应-static/-editor/-handoff回执。每目标单一finite-ui-animation AI模块任务，事件/未知项不逐字段拆派。
- `.runtime/animation-compile-02`：实际C#薄层对现有Unity6000.6.2f1/uGUI/TMP程序集窄编译pass，未启动Editor；三份Creator JS通过node --check，仅语法/API声明核对。
- `.private/continue03-animation-receipt.json`：本包机器回执。

Unity manifest SHA-256：`[private fingerprint omitted]`。

Creator manifest SHA-256：`[private fingerprint omitted]`。

6组动画定向测试pass：线性四分点、constant阶跃边界、透明度0..255→0..1换算、事件仅合同；未知easing/循环/时间/字段拒绝；缺失/重名路径、重叠通道、Layout冲突；伪造native绑定/中点/回调拒绝；IR兼容/未来动画schema拒绝、双目标导出/重复与plan篡改保护。合成轨道只验证子集合同，不是原版实玩证据。

## 原生边界

Unity仅通过Editor AnimationUtility生成原生AnimationClip、broken linear/constant tangent与循环设置；Creator仅通过Editor原生VectorTrack/RealTrack/RealCurve、序列化和asset-db保存，不输出源引擎运行时解释器。位移/缩放通过原生属性，透明度使用CanvasGroup/UIOpacity。离线候选不含已生成的.anim文件；源事件只在Analysis合同保留，原生事件数组为空，不生成业务callback或自动接线。

薄层已备保存后重载、真实绑定/键时刻/值/插值/中点/事件数回读，未执行，editor/曲线采样/播放/同状态画面对照均not_run。原生曲线资产、可编辑重开和页面门槛未通过。Bezier/sineOut等缓动、active、组件曲线、Reverse/PingPong、speed!=1及动态布局冲突仍unsupported；部分剪辑必须先人工补齐未知行为再绑定原生播放。现有开发wheel不包含本Git动画增量，本包未重新打包或发布。
