# beaver v0.2：本地交付完成

2026-10-26；版本0.2.0，分支`codex/beaver-v0.2`，基线`b67a164e7618179c1665028a516ea6f2bd6dea00`。唯一进度入口。人类授权已原生核验：总监turn01a1770a-5590-7bf1-9433-176841a89ca1/message01a1770a-55b2-7a10-9be1-2cf9642dda4b；完整范围沿Manager/decisions/20261026-grea-monkey-beaver/BEAVER-V02-PLAN.md。human01a1770e-af1d-7510-b494-867958dddf0e允许有界模块Agent，登记见TEAM-STATE.md。

| 工作组 | 交付状态 | 实证出口 |
|---|---|---|
| A 合同/成组操作/恢复 | 本地通过 | blocked退出3/failed退出2；固定计划与实现、写集、逐步原生hash checkpoint；受控失败后4路径恢复、真实组10路径恢复、人工后改拒绝 |
| B Prefab/Variant | 本地通过 | 节点增删/移动/顺序、组件增删、标量/对象/颜色；常规+Variant保存重载；最终安装包创建Variant child/component覆盖并恢复；继承结构限制有明确替代，不改base/Unpack |
| C 完整UI与接线 | 本地通过 | ScrollRect/Mask/Grid/内容适配/动态列表/长文本/安全区；已有真实方法持久事件；15项自有列表与17项真实图鉴的隔离Player、滚动/关闭及截图复核 |
| D 引用图与迁移 | 支持子集通过 | GUID正反依赖、明确消费者替换/原生移动、JSON pointer/C#加载字面量；移动保持GUID/localID，迁移后Player加载成功；未知动态键保留partial |
| E 增量 | 本地通过 | 相关依赖/编译输入按内容核验，缓存只作加速；真实5-step组一次Editor12.52秒；最终版本冻结图首轮34926hash/parse，次轮34926hit、0hash/parse |
| F 调试/整版安装 | 本地通过 | 固定App清单、worker拥有PID/启动参数/预算/日志，无自动重启；Editor/PlayMode独立证据；干净wheel离开源码目录执行、最终原生重开及调试关联通过 |

交付wheel：`.private/dist/v0.2-final-03/beaver_game_tools-0.2.0-py3-none-any.whl`，96635B，SHA256 `a3889c42c7bba72a182712ac8c551904c891b394359e33ea03e74f4ed7a02f2b`；实现身份`688a57a36ae0bb0a11d34d2914644861079837014306148f0b94f1bcb8ec191a`。35个包条目逐一核对源码，含6份C#，无私有资料/真实游戏代码素材。隔离安装`.private/v02/install-final-03`，在`/private/tmp`调用；50项Python检查通过。安装后真实副本只读重开一次Editor10.53秒，源变化0，原生节点874个localID均有效，`debug target`返回ok/recorded_exit（不是活连接）。

## 真实工程闭环

固定交付源`f3991c6bf8f43b3914472e5b31f94ba9742ba19d`，冻结manifest SHA550f9550f3d51d435acc465dc8c4002cb116bd5376759cb47a49ea6e2829a55f；54280项全部匹配，最终重新流式核验1730434339B、缺失/漂移0。`.private/v02/foodstreet-freeze`只读取证、不启动Editor/Player，独立`foodstreet-work`承接编辑；正式肥鹅/v1.2在途修改保持只读；Go、账号、普通存档和暂停项目未操作。

真实5-step组覆盖详情/图鉴/Closet Variant、Sprite引用替换及移动：计划54288路径元信息盘点，只hash1781输入/13806377B；一次Editor12.52秒，Python1789/native1841次哈希读取，声明10写路径、实际7路径变化、写集外0。另开Editor重读3个Prefab，与编辑后文件hash/序列化树/GUID一致，MissingScript0；Variant保持其base。运行后按原固定执行器恢复10写路径原始字节，保留隔离场景及无关字体准备；冻结副本再核0漂移。

专用`BeaverFoodStreetUI`场景、独立company/product/bundle，无Entry/Mainline/Preview业务host。运行断言AccountSession.Client/ProfileDirectory为空；只用正式JSON/已有Sprite呈现，鹅owned状态及已知元素集合为内存UI样本，不绑定领奖。详情内容723>viewport590，滚动位移24；17项图鉴内容1660>viewport800，滚动位移24；现有Close/CloseDetail持久绑定和窗口关闭断言通过，exit0，900×1400实际截图已查看。缺数据Spine占位1项在fixture禁用，未声称Spine验收；未抓取系统/Unity网络流量。静态模板/动态布局风险513条保留，不将静态inactive/零尺寸一概当运行缺陷。

自有App验证15项动态行、inactive模板保留、实际字体、按钮counter1与标签更新、滚动位移、安全区组件；C#字面量+JSON加载键与资源移动后实际Player日志`BEAVER_LOADING_KEY=verified`。截图曾被旧面板遮挡，已通过CLI布局组修正；过早截图又受Unity splash遮暗，fixture等待splash结束后960×640截图清晰。只对已查看的最终截图报告可见布局通过。

## 失败、边界与交接

保留早期TMP旧API编译失败、错误样例路径、instanceID不稳定快照、真实源TMP字体首次构建规范化5项、旧512MiB制品预算失败、后台停帧预算退出和splash早拍。新快照使用持久节点/组件与GUID-localID，不降低哈希门槛；无可信checkpoint或写集外变更仍拒绝猜测恢复。最终补充引用诊断时遇Unity 6.6移除的instanceID API，原生编译发现后修为EntityId；初版退出回执丢启动时间导致partial，修复及新增回归后最终安装包重新原生通过。早期final-01/final-02不是交付包，不重指其事务。

真实UI构建最终源码审计0变化，171文件/1261904766B完整制品哈希通过，App启动前/退出后再核；其中974468464B资源触发显式`beaver-unity-build/2`，单4GiB/总8GiB，普通采用/物化仍单512MiB。未知动态加载2项、61286个JSON字符串只观察不猜语义，图保持partial。最终冻结图13.41秒/173271918实际文本读字节，次轮5.42秒/文本读0；首次跨projectRoot复用缓存被正确失效，不外推速度倍数。自然使用对比见USAGE-v0.2.md。

GREA通用薄调用已实测保留0.2 capabilities、partial/exit1与blocked/exit3；冻结dev3正常版本检查仍拒绝0.2（只允许0.1）。其负责人须明确升级版本白名单/绑定；本项目未改GREA、monkey、全局provider或旧固定0.1链。保留v0.1提交、wheel与34项验证。

物理鼠标/触摸输入、完整游戏业务/存档续玩、视觉还原一致性、Spine行为、Creator原生与其他平台未验收；复杂配置/语义重构属于后续版本。当前仅本地开发、源码提交和隔离安装，无远端/推送/Release/全局安装/服务变更。证据身份详见VALIDATION-v0.2.0.json，用法见USAGE-v0.2.md。
