# 组件、Prefab、配置与插件目录

本页定义候选内容及验收契约；除明确列出的现有 grea 能力外，均未实现。配套的 [结构化示例](examples/README.md)不含 Unity 资产，也不是场景生成输入。

## 框架组件：先复用，再补缺口

| 组件/能力 | 当前基础 | 本配方拟补充的职责与验收 |
| --- | --- | --- |
| LifetimeScope / Lease / OperationStamp | grea Foundation 0.2.1 | 组合 Application/Player/Battle/UI 所有权；取消后晚回调、双释放、失败逆序清理 |
| CommandButton / ModalPanel / ScreenHost | grea uGUI 0.2.1 | 页面路由、类型化结果、焦点栈、暂停引用；失败后仍可导航 |
| AssetCatalog / AudioPlayer | grea 有局部实现和范围限制 | 绑定代次、资源缺失诊断、音量分组、循环/一次性句柄；不宣称通用异步加载后端已有 |
| FileSaveStore | grea 最小文件保存/显式 Recover | 新模板的 schema 迁移与奖励事务另实现；不混用样本兼容存档格式 |
| PageRouter / PopupStack | 新设计 | 重入策略、唯一输入所有者、创建失败恢复、返回值与焦点；不等于已有 ScreenHost 的全部能力 |
| RecycledList / ItemBinding | 新设计 | 同数量换数据、快速往返、大滚轮、异步图标取消、空列表；先做有性能依据的列表，不强制所有列表虚拟化 |
| RewardTransaction / RewardReceipt | 新设计 | 奖励/消耗/额度/receipt 一次提交、重放幂等、保存失败、提交未知回读 |
| BattleSession / NumericPipeline | 新配方 seed-once | 明确属性合成顺序、伤害/护盾/死亡/波次/结算；原数值规则由项目提供 |
| Clock / Random / Schedule ports | 新配方及可选来源适配 | 暂停/倍速/墙钟分离；恢复时原共享随机与帧顺序由兼容合同约束 |
| Badge / Guide / Settings | 新配方，可选前两项 | 红点由业务投影计算；引导不伪造领取；设置跨退出重开持久化 |
| Diagnostics | 复用有界诊断并补业务关联字段 | build/session/operation/entity/route、丢弃/轮转计数；不默认写完整存档 |

不先引入第二套 DI、全局事件总线或全游戏单例。重复出现且不携带业务含义的模块，在第二个独立消费者验证后再考虑进入公共包。

## Prefab 目录与契约

拟生成基础只使用自有几何、系统允许的字体或独立授权资源。表中“现有”表示当前生成器确有基础壳，**不表示已满足此表所有扩展要求**。样本的工作 Variant/源模板不能随通用包分发（E05、E13）。

| Prefab | 来源/目标职责 | 必需插槽与绑定 | 首批验收 |
| --- | --- | --- | --- |
| UIHost | 现有基础；拟扩安全区/焦点管理 | Canvas、Scaler、Raycaster、Pages/Modals/Toasts/Loading；唯一 EventSystem 由宿主拥有 | 输入模块与 profile 一致、层序/缩放/窗口变化、无重复 EventSystem |
| ButtonShell | 现有基础；拟统一完整反馈 | Graphic、Button、CommandButton；可选文本/图标 | 绑定一次、忙碌、失败恢复、拖出/取消、静音 |
| ModalShell | 现有基础；拟加入类型化结果 | 内容、遮罩、关闭按钮；焦点/暂停来自宿主 | 关闭两轮、嵌套、创建失败、销毁中回调 |
| PageShell / TabBar | 新设计 | Header/Content/Footer、TabItem slot | 显示/隐藏释放，拒绝切页时状态一致 |
| RewardDialog | 新设计，展示 receipt | ItemList、Confirm、可选详情 | 重开仅展示；不发奖，不扣次数；长奖励滚动 |
| InventoryItem / ItemDetail | 新设计 | 图标、数量、品质、角标、选择/锁定 | 回池不串图/监听；缺图错误可定位，不保留上一条图标 |
| UpgradeDialog / ShopOffer | 新设计 | 成本、效果预览、数量、购买/升级命令 | 不足/满级/配置缺失/重复点击；UI 预览与提交结果一致 |
| BattleHud / PauseDialog | 新设计 | 波次/生命/资源投影，暂停/速度/技能槽 | 暂停与后台独立，返回后无旧 BattleScope |
| SkillOffer / ResultDialog | 新设计 | 候选卡、确认、结果 receipt、继续/返回 | 三选一仅为合成演示；实际候选数配置化；结算最多一次 |
| SettingsDialog | 新设计 | 音量、开关、返回；可选输入字段 | IME、空白、长度、编辑完成/取消、重开保留 |
| LoadingOverlay / Toast | 规范中已有候选，本配方待实现 | 状态文本、取消能力、输入策略 | 加载失败可退出；提示队列有界 |
| ActorView / ProjectileView / FloatingNumber | 新设计 | 渲染挂点、动画端口、回收钩子 | 回池复位、重复播放、排序/混合、命中与数字时序 |

每个契约记录 `prefabId`、`contractVersion`、owner、requiredSlots、requiredComponents、参数类型、事件、绑定阶段、可覆盖项和失效条件。显示名不是稳定 slot，GUID/fileID 不由设计 JSON 编造。

生成器后续通过 Unity Editor 创建并回读对象；设计 JSON 不手写 YAML。基础变更检查所有 Variant 的 slot、组件与覆盖冲突；如果还没有字段级合并能力，就按整个资产冲突处理。更换主题只允许契约声明的颜色/字体/图标/边距，不覆盖业务 key 和监听。

### 动态UI的补充合同

第二次复评将下列字段纳入候选Prefab契约（E25、E26、E30）：

| 合同 | 需要声明 | 验收反例 |
| --- | --- | --- |
| hit-test | 命中Graphic、区域、遮挡/穿透策略、输入owner | onClick可调用但raycastTarget关闭；父遮罩拦截；修复不默认把所有Graphic变为可点 |
| sprite-sizing | 源版本、作者/原图/trim尺寸、赋值入口、scale/pivot保留 | 三组尺寸刻意不同；初始化、地址、ID、动画、远程换图分别检查 |
| deferred-composition | 动态子项生成时机、Ready条件、controller/事件覆盖 | 根面板成功而第二批卡片缺绑定；失败后释放遮罩/暂停且可重新导航 |
| selection-projection | 当前选择ID/版本、View和Presenter同步来源 | 换装后连续升级、预览和重开；显示正确但下一动作仍使用旧选择 |
| source-inert-event | 源对象/节点/slot/handler/参数完整指纹、无目标依据 | 指纹只差一项就不能走例外；真正需要业务handler的事件继续失败 |

源尺寸是恢复合同，通用模板默认保留作者布局。不得用统一缩小节点、SetNativeSize或修改scale掩盖错误枚举映射。静态扫描所有视图后，还需单列有动态换图的入口；生产没有某个模式时，可以用合成夹具检验适配语义，但不能称为该模式的原版实机验证。

### 路径与命名规则细化

新内容采用“业务含义＋职责后缀＋必要稳定ID”，缩写只用于团队能直接理解或必须保留的协议。以下规则应用于后续模板，不要求把当前源工程全部重命名（E28）。

| 内容 | 推荐职责名 | 保留/例外 |
| --- | --- | --- |
| UI工作资产 | InventoryPageView、UpgradeDialogView、ItemCardView | Template表示冻结基线；Variant表示Unity继承关系，不必把两词重复堆进文件名 |
| 数据 | RewardTable（行集合）、ViewCatalog（key到对象）、SavePolicy（策略）、ViewOverrides（编辑差异） | 来源列名/逻辑key可保留历史拼写，显示名和C#属性通过显式映射解释 |
| 代码 | UseCase、Presenter、View、Composition、Codec、Adapter、Importer、Validator | Source只用于源语义/身份；Legacy只用于仍需兼容的旧合同；新公共代码不使用迁移期Typed前缀 |
| 视觉内容 | 按功能/状态/用途命名，再附稳定业务ID | Spine内部页/附件、Shader符号、Resources相对键不机械改名 |
| 来源映射 | 项目内SourceMappings或已有声明位置 | 运行仍消费的对象图不是临时文件，不能仅凭Source名称删除 |

Images与Sprites、基础Prefab与Variant可能有意成对；是否冗余依据消费者和子资源身份判断。Validator能拒绝UUID/重复目录等形式问题，无法证明名称业务含义正确。历史命名空间和空兼容回调在序列化依赖查清前保留。

## 配置库按职责组织

配置库提供**字段契约、关系和合成样例**，不收集原游戏完整数值。Schema 是定义，不靠一份数据的自动类型推断作为长期唯一来源。类型推断可给首次候选，之后变更须显式审核（E07）。

| 配置组 | 推荐表/资产 | 关键关系与检查 | 首版范围 |
| --- | --- | --- | --- |
| 内容索引 | AssetCatalog、ViewCatalog、AudioCatalog、Localization | key 唯一、实际资源存在、预期类型、来源身份独立 | 必需 |
| 基础物品 | Currency、Item、Rarity | 数量边界、稳定 ID、图标/文本 key | 必需 |
| 战斗 | Actor、Skill、Effect、Stage、Wave | 关卡→波次→敌人；技能→效果；时间单位、命中/目标语义 | 最小单关闭环 |
| 经济与奖励 | Cost、Reward、RewardPool、Offer | 成本/奖励引用 Item；权重合法；资格与次数由用例维护 | 固定奖励与一次购买；随机池后续 |
| 成长 | Equipment、Upgrade、Unlock | 装备→升级路线；每级前后关系；等级上限、循环依赖 | 一件装备的升级示例 |
| 活动 | Task、DailyClaim、OfflineReward | 周期、时区/时间源、领取标记、上限、回拨策略 | 后续可选 |
| 平台策略 | RewardedPlacement、PlatformCapabilities | placement→已定义奖励；生产/QA模式分开、超时和取消 | 默认 Unavailable；QA 模拟可选 |
| UI/主题 | Route、PrefabContract、Theme、TextStyle、NumberStyle | route→view，slot类型、格式、语言缺省；不装入任意执行表达式 | 必需 |
| 构建与保存 | BuildProfile、SavePolicy、DiagnosticsPolicy | 平台/后端、namespace、schema版本、日志预算 | 必需；敏感凭据不放这里 |

拟定制作链为：编辑表/资产 → 结构及关系校验 → 候选 DTO/Codec → 显式审查 → 导入 → 生产 Catalog 回读 → 构建输入冻结。配置字段重命名要区分源列名、C# 属性名和存档字段，不能一次替换三者。

错误至少定位 table、row、field、实际值类型、预期关系和配置内容 hash。校验覆盖：重复 ID/JSON 重复键、未知列、缺列、缺失与 null 区别、有限数/溢出、外键、枚举、权重、循环、非法时间单位与资源类型。部分输入表合法不能掩盖缺失的必需表。

配置升级和存档迁移独立版本化；配置更新导致装备/技能 ID 失效时必须有明确兼容策略。失败保持旧可用配置和原存档，不能静默赋 0 或回写默认进度。首版先用本地不可变 Catalog，不宣称支持热更或远端内容发布。

## 插件与依赖选择

下列版本来自本次读取的工程锁与 grea 源码，是**已观察环境**，不是对上游最新版本的推荐。首版仅建立一套需要实际验收的组合（E16）。

| 依赖 | 样本/现有版本 | 新模板处理 |
| --- | --- | --- |
| Unity / URP / uGUI | 6000.6.2f1 / 17.6.0 / 2.6.0 | 基线候选；记录精确 Editor revision 与 lock，不自动升级 |
| TMP | 样本使用 Unity.TextMeshPro 程序集 | 从实际 uGUI/包解析确认归属，不杜撰独立包版本；字体源/atlas/材质归 Fonts |
| Input System | 1.20.0 | 拟新增 profile 支持；现有 grea 生成器不支持，先验证事件模块与真实输入 |
| Test Framework | 1.8.0 | Editor/Tests 依赖；核验实际执行数，Player 排除测试内容 |
| grea Foundation / uGUI / Editor | 0.2.1 | 复用；不把样本自有框架重命名后作为第二套 foundation |
| Newtonsoft Json | 锁中实际为 3.2.2；本轮确认仅由Pipeline带入，但生产codec直接使用 | 已确认为依赖治理缺口；采用该codec的模板应显式声明，独立副本验证移除可选工具后仍可编译/解析 |
| Spine | 样本目录为 3.8 适配，带独立运行时许可 | 可选，按源导出版本核验；不将 vendor、骨骼或素材重新授权/随模板复制 |
| Pipeline | 0.8.0-exp.1 | 可选 Editor 连接；不成为普通 Player 启动必需项；不复制认证设置 |
| IDE、2D 制作、Timeline 等 | 样本 manifest 中存在 | 按实际资产/制作需要选择，不照搬整份 manifest |
| 广告、分析、远程配置、支付 SDK | 本次没有真实服务验收 | 不预装、不设默认供应商；保留能力端口，后续单独选择与验收 |

第三方引入需有来源、实际版本/内容 hash、许可文件、安装/恢复办法和平台验证。Unity PackageCache、依赖备份、商业插件、字体原件和项目素材不直接成为公开制品。模板分发可包含自有代码与许可允许的合成资产；需要使用者自行获取的依赖写清楚。依赖存在不等于可再分发，完整锁文件也不证明所有平台已通过。
