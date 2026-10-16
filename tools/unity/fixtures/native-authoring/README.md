# 自有制作链验收样本

本目录仅含独立合成输入与断言，不包含游戏代码/素材。`Enemy` 是 int key/有范围数值表，`Hint` 是 string key/bool/可空 string 表；后者专门验证 null 与空串保存后仍能区分。

在明确授权的隔离 Unity 工程中执行。实测 Editor 6000.6.2f1、macOS arm64/Mono；项目需启用内置 `com.unity.modules.animation: 1.0.0`、测试框架，不能用 Editor 能编译推断 Player 运行模块齐全。准备一个自有 2×3 RGBA 色块 atlas.png，颜色从左上按行依次为 red/green、blue/yellow、magenta/cyan；运行两个 config candidate 和 native prepare。

将两张 Table 与 NativeProofReceiver 放同一 `Own.Runtime` asmdef；两张 Import、NativeProofEditor、两个产品 audit/converter 放 Editor 编译域。authoring 候选保留在 Assets 外。`NativeProofEditor.Create` 使用 `-greaFixture` 指向含 Enemy/Hint/native 候选的父目录，同时接受产品转换器的 request/root/receipt 参数；目标为 `Assets/NativeOwned`。`ReadAndEdit` 验证 Sprite 像素/九宫格、类型化表、非单位 scale、曲线/事件/循环后，把 x 曲线终点从 4 人工改为 8 并创建 Scene/Resources Prefab。`Reopen` 在新的 Editor 进程验证保存保持。

Play 测试放 `Own.PlayTests` asmdef，引用 Own.Runtime 与 TestAssemblies。使用 `unity test ... --mode PlayMode --filter NativeProofPlayTests`，验证实际 Play 中编辑后的曲线、SO、原生事件、循环 seam 和中断到第二条 clip。测试不依赖转换器进行运行时解释。

用 NativeExitEditorAudit 导出台账，`MoveGeometryAudit` 仅在这个自有副本移动 Sprite（保持 GUID）并修改 border；用既有 ledger compare-editor 核对实际 path 与 sprite_geometry 差异。比较前应显式纳入 enabled build scene，否则报告保留 unlisted_build_scene，不能静默清除。

最后创建新的分发副本，只带 NativeProofRuntime、NativeOwned、NativeProofData、Resources/NativeProof.prefab、NativeProof.unity 和必要 Packages/ProjectSettings，保留 .meta。移除所有转换器/导表/audit 与测试源码；只放 NativeProofBuild 作为构建入口。Build 回执之外要对源 Assets 做前后指纹；Unity 构建只在这个新工作副本进行。启动 Player 时带 `-grea-native-proof`，运行自有自动回读并退出，日志须包含 CONFIG_OK 和 ANIMATION_OK；这不是鼠标或视觉验收。

不得把本样本固定路径推广为真实游戏规则，也不要把本样本的手工修改写回生成器覆盖策略。人工改后的旧目标仍必须拒绝覆盖，新增转换请求使用新目标。


## 实际可见图形与 Player 帧

数值/Transform 断言不等于画面通过。`NativeProofVisualEditor` 是额外自有验收装配器：相机在 `(0,0,-10)`、正交半高 5；为 Widget 绑定裁切旋转恢复后的 6 色图案，为 Other 绑定可见缩放图案，并放置两个不同尺寸的原生 Sliced SpriteRenderer。透明留白与黑色 pivot 锚点都有独立像素位置断言。

用 `scripts/testing/create-native-visual-inputs.py --output NEWDIR` 生成纯自有 9×9 九宫格图和 recipe，再通过 `unity_native_assets prepare` 输出候选。已有自有数值样例先完成手改曲线；在新的隔离副本中复制 Visual/VisualEditor/RenderTests 源码，启用本机内置 imageconversion 与 screencapture 模块。调用 `NativeProofVisualEditor.Configure`，转换器参数 root 固定为这个 fixture 的 `Assets/VisualNine`；原有 NativeOwned 只在自有样例里显式增加图形。先选择 Built-in 管线再添加 renderer，避免保存了 URP 默认材质后切管线导致透明不可见。

`unity test ... --mode PlayMode --filter NativeProof` 运行已有逻辑测试和两项渲染测试，必须提供真实图形设备（不加 -nographics）。可选 `-greaRenderFrames NEWDIR` 保存五相位相机帧；各相位 25 项像素检查，验证源颜色/反旋转/透明补边/pivot、实际位移与缩放、九宫格边角宽度在两种尺寸不变、人工曲线终点 8 的中间效果、循环 seam 与切换到 Return。

分发副本额外携带 VisualNine 原生资产与 NativeProofVisual（自有 QA 消费者），仍移除全部转换器/导表/审计/测试代码。Player 带 `-grea-visual-proof /absolute/NEW_CAPTURE_DIR`：实际 backbuffer 截图、逐帧断言、记录 build GUID/图形设备并自行退出；它不读取转换 recipe。五张 PNG 与 receipt 必须关联实际 Player/Managed 哈希和冻结源码，人工查看这些实帧，不只检查 Transform。离屏与实际 Player 帧分别登记，不能据此把真实 OS 鼠标、原游戏视觉一致性或其他平台改成通过。

Player 实帧采样须等待 `SplashScreen.isFinished`，最长 15 秒，否则保存失败回执；启动淡出期间的 backbuffer 会被 splash 背景混合，不能与游戏像素直接比较。失败 PNG 始终保留，首帧额外提供标明 offscreen-reference 的相机对照及纹理格式/原始 texel 诊断，避免把压缩、材质、启动合成和采样坐标混为一谈。严格颜色阈值不因 Player 首帧失败而放宽。
