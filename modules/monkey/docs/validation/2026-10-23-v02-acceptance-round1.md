# 2026-10-23 v0.2 样例项目样本首轮 Creator 验收

状态：**实际资产导入partial；工程控制窗口绑定blocked；v0.2出口未通过。**

| 层 | 实际结果 |
|---|---|
| 输入身份 | 冻结creator-reward-04 manifest b438700518e4ce87b73b227254dd2124bf5e0680449c529691caf2781ee14abf及60生成文件核对后，原样复制独立副本 |
| 验收工程 | `outputs/acceptance/v02-reward-01`，实际Creator3.8.8启动 |
| 初次启动 | 受限进程SIGABRT，崩溃栈在macOS应用注册_RegisterApplication；未据此宣告项目导入失败 |
| 正常桌面启动 | 官方--project参数指定副本，实际Load engine/Creator3.8.8/monkey-import enable/asset-db ready |
| 原生资产导入 | Creator写出的25/25 asset meta imported=true；25根UUID匹配；23个图像各2个Texture/SpriteFrame子资源，共46条 |
| 原生资产配置 | 导入扩展未运行，trim/offset/九宫格尚未按计划设置和回读，不能把默认导入当成完整资产验收 |
| 工程窗口操作 | 按bundle ID及app路径只能绑定无标题推荐Dashboard启动提示，Window菜单无工程窗口；真实主工程窗口尚无法安全定位/操作 |
| 原生Scene/5个Label绑定 | not_run；Candidate.scene及editor-readback.json不存在 |
| 编辑保存重开 | not_run |
| 浏览器真实PNG/UI命中 | not_run，未生成页面截图，不用离线预览代替 |
| 原版同状态视觉对照 | not_run，未为取得画面改动正式游戏或存档 |

北京时间08:16:46接管，08:26:52释放鼠标/键盘/焦点（UTC00:16:46–00:26:52，606秒），早于12分钟截止；总监已收到释放消息。Dashboard使用正常Cmd+Q退出。Creator仍被应用清单报告为running，工程temp/startup.json记录PID41840；因不能安全绑定工程主窗口而未强退，保留并明确无人输入。样例项目Unity/Player保持原状。

工程正常启动与默认资产导入已有真实证据；控制窗口绑定的具体内部原因仍未证实，不能冒称登录、项目API或产品资源失败。Dashboard显示登录UI但未输入凭据。后续先恢复受支持的工程窗口绑定，再申请明确的新资源时段执行一次导入扩展和真实页面验证；不继续同条件重复启动，不安装/修改引擎或安全设置，不扩v0.3动画。

证据：`.private/v02-acceptance-01/input-identity.json`（包含开始/释放和冻结输入身份）、`native-asset-observation.json`（实际Creator写出的asset meta逐项观察）、`round1-result.json`（分层回执）、验收工程`temp/logs/project.log`与本轮工具输出中的asset-db ready/插件enable。初始输入manifest仍作为冻结身份保留；Editor已改写副本内meta，它不是副本当前所有文件均未变的证明。冻结原件未作为Editor工程打开。

本轮没有代码修复、测试重跑、发布或新增功能；仅记录实际验收和环境/控制阻塞。
