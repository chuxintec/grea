# 合成示例：从配置到奖励与持久化

本目录全部为本次新编的设计样例，不含原游戏源码/数值/资源。版本 `0.1.0-draft.2`，状态 **illustrative / not executed**。它不是可运行 Unity 工程，也不注册任何 GREA 模板、Schema 或接口。

| 文件 | 用途 | 明确限制 |
| --- | --- | --- |
| [template-profile.example.json](template-profile.example.json) | 展示配方、模块、目标环境、默认服务策略和所有权选择 | 不是grea-project.json；现有生成器不会接受 |
| [configuration.example.json](configuration.example.json) | 合成物品、技能、敌人、波次、装备、奖励、服务入口与UI路由 | 数值仅演示关系；资产key是待制作声明，没有资源文件 |
| [prefab-contracts.example.json](prefab-contracts.example.json) | UIHost、基础壳、奖励窗、列表项和HUD的slot/生命周期 | 是结构描述，不是Prefab/YAML；没有伪造GUID/fileID |
| [reward-claim.pseudocode.cs.txt](reward-claim.pseudocode.cs.txt) | 展示请求幂等、资格/版本复核、原子提交与展示分界 | 伪代码，不编译；接口是设计名，不是GREA已发布API |
| [expected-flow.example.jsonl](expected-flow.example.jsonl) | 一条编辑的预期状态序列 | 手写预期，不是测试输出，不可记作PASS |
| [ui-regression-contracts.example.json](ui-regression-contracts.example.json) | Sprite尺寸、动态组合、精确事件例外、射线命中、选择状态与依赖身份反例 | 第二次复评新编；仅合同预期，未执行Unity或输入 |

## 阅读这一条完整链

1. 合成新档：金币100、材料0、装备`starter_wand`为1级；默认广告服务不可用。
2. `inventory.page`使用PageShell；InventoryItem只显示装备快照。升级按钮发送命令，用例核验`upgrade_wand_2`，消费11金币，装备变2级，余额89。
3. `battle.page`启动`training_stage`，使用两段波次、一种敌人和两种技能的合成定义。BattleScope拥有敌人与定时任务；暂停/恢复不改变局外墙钟。
4. 胜利由业务用例提交`reward_victory`的23金币，保存完成标记与receipt，余额112；`result.modal`只展示这一receipt。
5. 若本次明确开启QA模拟广告，`after_result_bonus`模拟完成后领取7金币，余额119，日限额使用1次。实际默认Unavailable时保持112，不能发奖。
6. 重放相同领取请求、关闭再开结果窗，余额仍119；视图的实例ID/代次可以变化，receipt不变。
7. 正常退出应用，重新启动，读回119金币、2级装备、完成关卡和已领取claimKey。该步骤是预期验收，不是本轮实际运行。

`expected-flow.example.jsonl`描述第5步选择QA模拟的分支。所有行都标记`synthetic-example-only`和`not-executed`；它不引用任何真实截图、构建或源文件身份。

## 反向走查

| 变更 | 预期结果 |
| --- | --- |
| 把初始金币改为10 | 升级拒绝，不扣币、不升等级；UI恢复可操作 |
| 删掉被Wave引用的敌人 | 配置关系校验失败，指出wave/field/ref；不生成占位敌人 |
| 把reward指向不存在的Item | 配置拒绝，不能静默跳过该项 |
| 把模拟结果改为Cancelled或Unavailable | 无奖励、无限额消费；展示对应结果 |
| 同operationId更换奖励请求内容 | requestDigest不匹配，拒绝；不把旧回执当新操作成功 |
| 关闭Modal后广告才完成 | UI绑定已失效；业务请求由PlayerScope继续处理/查询，完成后可在新视图回读receipt |
| 明确取消业务请求且尚未提交 | 不写入；普通关窗只取消显示任务，不等同取消已交给PlayerScope的业务请求 |
| 保存抛错/提交结果未知 | 失败或Unknown；不展示成功，不用新ID重试；保留原请求身份等待恢复 |
| 损坏存档后启动 | 显示可诊断恢复状态，保留原字节，不回写新档覆盖 |

## 第二次复评示例的阅读方法

Sprite输入故意设为四组不同尺寸：作者框120×120、原图48×80、trim32×52、Unity导入rect96×96。对本例声明的源模式，CUSTOM保留作者框，TRIMMED用trim，RAW用原图；scale与position不变。远程完整图片使用独立描述，不冒充本地图集帧。多种赋值入口与未知枚举拒绝是后续需要实现的回归合同。

动态组合示例要求root和child都完成业务绑定才Ready。回调存在但射线关闭仍不能通过输入验收；即使两者都有，真实输入仍待执行。源惰性事件的view/node/slot/handler/参数与无目标证据要全匹配，slot改变或目标实际存在都不能忽略。

选择流程中View、Presenter与model始终一致，升级预览使用新选择；依赖反例则说明版本一致不能替代hash一致，传递解析成功不能替代产品直接拥有运行依赖。这些JSON的算术/引用自洽检查不是所描述功能已经运行的证据。

## 内容关系与所有权

configuration中的ID在其类型内唯一。Stage→Wave→Enemy、Equipment→Upgrade→Item、Stage/Placement→Reward→Item、Route→PrefabContract需要能解析；图标/text key也必须在声明库存在。实例数量、权重、范围、资源类型与运行时绑定仍需后续实现校验，JSON可解析不代表游戏可用。

此处资产声明的`not-created`是设计状态，不应进入生产清单假装资产完整。生成器实施时只有真正创建并Editor回读的资产才能获得GUID/fileID/hash。模板业务代码seed-once，框架包按版本维护，人工Variant保留，来源材料只在项目证据中出现。

具体测试应把这里的手写预期转成新代码的断言并实际运行；再经过Editor制作回读、PlayMode和目标Player。文档验证只覆盖文件格式、引用关系与自洽性。
