---
name: grea-recover
description: 游戏恢复阶段：在授权范围内识别和提取原包证据，调用 monkey 将 Unity Mono/IL2CPP 或受支持的 Cocos/Laya/Egret/H5 来源恢复为独立 Unity/Cocos 候选，核对代码、资源身份与原生交接。只读取证不自动转换；已有可维护工程的功能迭代、换皮和去残留转开发阶段。
---

# GREA · 来源恢复与候选交接

先读[恢复阶段执行与交接](references/恢复阶段执行与交接.md)和[共同约束](../grea/references/共同约束与执行入口.md)。选择只读取证或获准完整恢复；输出范围由当前任务决定，缺少源引擎/目标时先辨识，不猜参数或替换目标。

## 按来源和目标加载

| 任务 | 参考 |
| --- | --- |
| 包体、资源与引用提取 | [提取与引用恢复](references/提取与引用恢复.md)；补原版体验时读[原版运行与内容取证](../grea-research/references/原版运行与内容取证.md) |
| Unity 原包 → Unity 候选 | [Unity工程重建与恢复](references/Unity工程重建与恢复.md)；IL2CPP/DummyDLL/真实源码的可信度分别记录 |
| 非 Unity 来源 → 原生 Unity | [Unity原生转换规范](references/Unity原生转换规范.md)、[跨引擎行为一致性](references/Unity跨引擎移植与行为一致性.md)；Cocos来源按[映射](references/Unity源引擎映射-Cocos.md) |
| 明确恢复到 Cocos | [恢复阶段执行与交接的Cocos目标](references/恢复阶段执行与交接.md#cocos目标)；源版本、目标版本和固定provider能力分别核对 |
| Cocos 结构与源码证据 | [Cocos离线解析与模块证据](references/Cocos离线解析与模块证据.md)、[Creator序列化与CCON证据](references/Creator序列化与CCON证据.md) |
| 工具或资源专项缺口 | [IL2CPP辅助解析器](references/IL2CPP辅助解析器.md)、[Shader检查工具](references/Shader检查工具.md)、[Android旧模拟器调用](references/Android旧模拟器调用.md)、[Frida配对与调用](references/Frida配对与调用.md)；只按需使用 |
| 跨引擎候选的原生出口 | [Unity原生退出检查工具](references/Unity原生退出检查工具.md)；静态、Editor、Player证据分别记录 |

完整恢复按[全量初版工程与协作](references/全量初版工程与协作.md)核来源去向和候选；monkey维护转换，不在GREA重写解析器。Unity Prefab/Scene通过原生接口操作，不外部手改YAML。真正原生Unity来源使用原生运行时/资产时，跨引擎原生门可记不适用并说明；WebView/WASM宿主不能据来源名豁免。

本阶段出口是独立候选、源ID到目标资源/代码映射、适用的原生检查和缺口清单。清单、lookup、空壳、IR、exit0或导入成功都不等于完整可玩游戏。缺失业务、界面、服务器或存档接续交[开发阶段](../grea-develop/SKILL.md)；采用与三方合并由开发阶段组织beaver执行，保护既有工作工程。
