# Modern UI v1（独立候选配方）

Unity 6000.6.2f1 / uGUI 2.6.0（内含 TMP）/ Input System 1.20.0，macOS arm64 Mono。旧 legacy UI 配方保持独立；不会批量转换现有游戏。

1. `scripts/testing/prepare-modern-ui.py --output NEW_PROJECT --sample numeric-combat|grid-puzzle --font LICENSED_FONT` 创建自包含工程。字体来源、SHA 和许可由使用者明确；仓库不打包游戏字体。
2. 首次导入后，通过 `unity assets import` 导入该工程已解析 UGUI 包中的 `Package Resources/TMP Essential Resources.unitypackage`。不得自行重建 TMP Shader/Settings。
3. `unity run NEW_PROJECT -- -executeMethod ModernSample.Editor.ModernBuilder.Seed` 使用 Editor API 创建 TMP 字体、UI Prefab、配置 SO 和 Scene。输出只能创建一次；后续直接在 Unity 编辑资产，不依赖重复生成覆盖人工修改。
4. 运行配置位于 `Assets/Game/Content/sample_config.asset`；修改生命值或伤害后直接 Play。`ModernUIRoot` 仅管理表现和输入，游戏规则位于样例 Domain/Gameplay，存档位于 Services，Bootstrap 装配依赖。
5. `ModernBuilder.Build` 接受显式 `-buildOutput` 新路径。使用独立 QA 存档必须同时传 `--grea-qa --grea-qa-root ABSOLUTE_PATH`。

两个消费者是小型架构验证切片：数值伤害/原子存档，以及两格交换益智/重开。它们不等于完整战斗框架、通用拼图系统或模拟经营框架。TMP mesh、虚拟设备事件、实际 Mac 输入与截图是不同层证据。

独立包 `packages/com.grea.ui.modern` 只依赖通用包及官方包，不依赖样例。Editor 制作代码仅留在样例的 Editor 程序集中。该配方仍按具体版本列出已运行和未运行门，不能继承旧 legacy 样例的验收。
