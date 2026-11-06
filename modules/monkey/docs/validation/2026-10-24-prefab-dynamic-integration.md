# 嵌套 Prefab 与动态 UI 集成

同一 Cocos 3.8.7 原始代表 CookSoupTaskItem、battleRewardItem、GoodsItem、StarGroup，104 节点、4 Prefab、5 嵌套关系、32 个动态组件计划。Unity01 已通过严格读回 0 诊断（Editor 总体 partial 保留源业务缺口）；Creator04 严格读回 0 诊断、Editor pass。两端各有 2 组动态状态探针，独立资产保存重开后的模板对应关系、覆盖、布局与未驱动几何均受检查。Player、完整原版游戏流程及视觉保真仍为 not_run。

- Unity：`outputs/cocos387-prefab-dynamic-integration-01-unity-native`，own67371，exit0/reaped。Creator 专属修复没有重跑 Unity。
- Creator：`outputs/cocos387-prefab-dynamic-integration-04-cocos-native`，own75174，2026-10-24 05:10:50–05:11:27 UTC，正常 TERM/reaped。1972 SpriteFrame、1973 资源全部逐项读回，4 Prefab、5 关系及 2 动态探针通过；完整自有日志没有本组发现的 Scheduler 销毁错误。

## 实际发现及修复

Creator01 的关系与动态字段通过，但末尾 SpriteFrame 九宫格仍为旧值；父图片 `.meta` 已更新，实际 `library` 子资源仍未重新导入。Creator02 新增真实导入产物就绪检查，拦下另一个保留自动裁剪的 SpriteFrame，未进入场景装配。Creator03 保存子资源成功，但新增的返回 UUID 相等检查错误地拒绝了 API 返回形式，保留失败副本。

现在通过父图片查询原生 SpriteFrame UUID，使用该子资源 UUID 保存并重导入子资源，随后查询持久化 meta，并在有界期限内检查实际导入的矩形、原尺寸、偏移和九宫格；不改写 library、不绕过不一致。Creator04 全部通过。原生加载同时要求重新读取 SpriteFrame，防止内存旧资产残留。[官方资源工作流](https://docs.cocos.com/creator/3.8/manual/en/asset/asset-workflow.html)说明 meta 与 library 的不同职责；具体消息签名以本机 3.8.8 安装的 AssetDB 声明为准。

SDK `checkAndStripNode` 会清除待序列化树的活对象 ID，临时对象销毁仍需这些 ID 执行 Scheduler 清理。装配器在原生序列化前记录、finally 恢复自有 Node/Component 的活 ID；尚无 ID 的自有 Component 经原生 Scheduler 分配。不把 Prefab fileID 充作活对象 ID。宿主增加对该具体生命周期错误的失败判定，包括字段读回先完成的竞态，语义回归覆盖这两种时序。

01–03 失败证据保持不变。这里的严格 0 指目标原生读回，输入中其他未提供 bundle 和未知源业务的历史诊断不因此消失；没有把整个游戏或全部 114 图标为已验证。
