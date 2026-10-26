# beaver v0.1.0

唯一产品进度入口。2026-10-26。状态：**本地候选已验证，未公开发布**。

## 授权和边界

已原生核验技术总监聊天 `01a14c8c-6402-7d03-bab8-ec7ea8051abf` 的人类消息：
- `01a1764c-0246-7541-88e4-9a84d3556574`：三产品整改与beaver实施。
- `01a1764d-40ff-7351-8717-feecc92dc1b5`：独立beaver开发者。
- `01a17684-35f6-7ed2-a252-2f7f73d2898a`：同事向僵尸工程的有价值内容整合。

只写beaver；未修改GREA/monkey或正式游戏工程，未启动暂停游戏，未改服务/玩家资产。独立本地Git，无远端、推送、Release或全局安装。设计依据为Manager的三产品PLAN/CONTRACT及同事交接PLAN；普通实现自主完成，无子Agent。

## B0–B6 实际出口

| 阶段 | 状态 | 已完成 |
|---|---|---|
| B0 来源 | complete | 初始56项逐能力盘点；monkey正式冻结包身份；GREA40入口/367模板索引按需接收；同事4脚本完整读及机制独立实现 |
| B1 CLI | complete | 安装/version/capabilities/doctor/project inspect、结构化JSON与非零错误、身份绑定计划/显式执行 |
| B2 采用 | complete | 三方冲突、身份/前置保护；原生移动/新增目录/资产、保存重开、正常回滚、后续改动拒绝、真实导入后失败与受控恢复；大工程只读预览 |
| B3 原生工程 | complete | 窗口/固定列表/按钮/TMP文本、Prefab字段/组件/Sprite绑定、GUID/localID、PPU/pivot及重开；显式原生移动 |
| B4 图片/配置 | complete | 无损PNG、RGBA/alpha；必填scalar JSON与DTO/TextAsset读取器；静态程序集检查明确partial；共用payload清单/别名/独立复制/原子晋升 |
| B5 验证/构建 | complete | 真实3秒PlayMode/0错误，BuildPipeline macOS成功且源树不变，160项制品完整性；Player退出0、JSON拒绝和合成事件计数1；截图已查看 |
| B6 分发/调用 | complete | 源码外清空PYTHONPATH的wheel安装与实际调用；固定GREA dev3锁定最终wheel，实际project.inspect/原生构建/Player及事后身份检查，monkey0.4与beaver0.1均ready |

最终wheel：`.private/dist/final-03/beaver_game_tools-0.1.0-py3-none-any.whl`，59166B，SHA256 `09020d42b75497ec39040f08e48fab24378a0baa5b51cebe92529fe67a7ee2f6`。先前final-01/02为历史候选，保留身份，不混称最终版。

23项针对性Python测试通过，命令 `PYTHONPATH=src:tests python3 -m unittest discover -s tests -q`。实际来源/哈希/层级及34项证据见 `VALIDATION-v0.1.0.json`；CLI以 `CLI-CONTRACT.md` 与实际capabilities为准。

## 重要证据与限制

- 规模预览使用既有monkey隔离样本，约3.27GB/16.46万文件，43.8秒；只读，不启动其Editor，不证明游戏业务。
- 自制PNG从262556压至879B，解码RGBA完全一致；自制几何字体与UI用于样例，私有素材/vendor未进入包。
- 同事交接机制已实质接入payload.py、unity.py和player.py。全部别名按旧/新hash统一重定向；source不变、独立inode、新目录原子不覆盖晋升。模拟中途IO失败与并发空目标均不会晋升半成品。来源见 `COLLEAGUE-INTAKE.json`。
- 最终GREA调用：`.private/grea-intake-verification/`，内含锁、同源构建、Player前后清单、进程身份、截图和事后包身份。早期安装包的原生Prefab读回单独保留于 `.private/grea-verification/`，不冒称最终wheel重复运行了所有旧步骤。
- 原生路径固定Unity6000.6.2f1。Creator仅静态检查/三方预览；native apply/build明确unsupported。Windows/Linux原生晋升/构建/运行未验，不外推。
- 静态asmdef扫描不求值全部平台/define条件，8项可选/平台引用保持partial；真实编译、PlayMode和构建单独通过。
- 工程采用有受保护原生回滚；普通unity修改只留journal/before-image，尚无通用自动回滚。旧monkey计划/采用状态不静默重放；旧事务继续用原版本恢复。
- Player使用合成UI事件，物理输入、原版视觉一致性、复杂资源闭包和完整游戏业务未验。独立证据目录/进程不代表玩家存档隔离；须项目适配另验。
- 同事整包7GB校验由来源项目执行；beaver仅读取采用脚本/相关清单结构并核ZIP成员CRC/SHA，不声称全包已逐文件验收。固定307/34003、WebView/WASM、私有经济规则、原游戏内容均未引入。

## 保留的失败与修复

UI早期失败依次暴露内建字体不适合生成TMP、缺Settings/shader和首次场景设置初始化；已改显式字体/依赖前置检查及计划声明。源审计通过后才标complete。Player首次未产生运行结果，样例显式后台运行后重新构建并通过。真实导入后处理器改写导致采用拒绝，已记录实际after身份并恢复before-image。失败收据保留，未提升为通过。

GREA原入口及monkey旧实现由原所有者保留；本项目接收记录不授权删除/切换消费者。后续新增需求另按实际范围推进。
