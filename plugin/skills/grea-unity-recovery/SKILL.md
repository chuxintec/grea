---
name: grea-unity-recovery
description: 源游戏本身是 Unity（Mono 或 IL2CPP 包体）时，从 AssetRipper 导出和反编译结果重建可运行的 Unity 工程：GUID 闭包、脚本 GUID/fileID 重映射、Missing Script 处理、Spine/Shader/TMP 接入回读，以及 Mono/IL2CPP/Ghidra 代码恢复证据链。Use when rebuilding a Unity project from a shipped Unity game. 不用于 Cocos、Laya、H5 等跨引擎转换（那类任务用 grea-native-port）。
---

# grea-unity-recovery · Unity 包体到 Unity 工程

先读 [共同约束与执行入口](../../shared/01-流程-共同约束与执行入口.md)；完整恢复的阶段顺序见 [恢复开发](../../shared/01-流程-游戏恢复开发.md)。

## 读取

- [Unity 工程重建与恢复](references/05-Unity-工程重建与恢复.md)：工程路径与版本、原始导出到可运行工程的六个步骤、代码恢复证据链、运行时与资源兼容、Shader 与 Spine 回读。
- 资源提取与身份台账在 `grea-evidence`；界面、规则与动画的差异修复在 `grea-parity`；目录与程序集标准在 `grea-unity-standard`。

## 要点

- 原始导出只读；工作工程中的导入副本和修复副本分开。
- 通过 AssetDatabase/PrefabUtility 导入和修复，不在外部手改场景或 Prefab 的 YAML。
- 先让一个原 Prefab 在真实 Camera/Canvas 下正确显示，再扩展到整个系统。
- 验收按 [分层验收](../../shared/08-验收-测试与结果交付.md) 记录。源游戏是 Unity 时，[原生可维护门](../../shared/08-验收-测试与结果交付.md#原生可维护性跨引擎转换) 记为不适用并写明依据；工程中混入跨引擎来源的模块时，那些模块按原生门验收。
- 反编译结果、IL2CPP 伪代码和 DummyDLL 空壳的可信度不同，分别标注，不当作已恢复的源代码。
