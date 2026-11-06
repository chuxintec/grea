# monkey v0.4.0

本版本将已验的 0.3.0.dev2 解析优化作为正式版本发布。以工具当前声明支持范围交付，不代表所有引擎版本兼容或完整游戏玩法恢复。

## 变更

- Unity Font.m_FontData 与 AssetBundle.m_PreloadTable 按精确类型树流式分块读取，保留原始字节、块哈希和引用身份，减少大数组内联 JSON。
- inspect-unity / Unity convert 支持 --unity-object-value-limit 和 --unity-container-value-limit；默认单对象 250,000、单容器 8,000,000，硬上限分别 1,000,000 / 16,000,000。
- 解析预算、读取器合同及块闭包纳入复用、准备、导出和冻结校验；保持严格字段及长度验证。
- 沿用类型优先目录、拼音命名、JSON 数值配置、源文件台账以及 Unity 纹理无损输出。

## 验证与限制

此前完整复测样例项目 601 容器、81,580 对象：81,544 已解析，未解析 975 → 36；939 个预算失败全部恢复。75,244 个生产资产/代码/meta 文件与前版逐字节相同，887 原件和 7,595 已取得纹理完整留存。完整工程验收见 [解析优化报告](validation/2026-10-26-unity-parser-budget.md)。本次发布另执行工具回归与独立安装烟测，完整回执保留在本机 .private/release-v0.4.0/。

剩余 36 对象均在启动包内：19 Image、10 Text、4 自定义启动/确认组件及 3 TextMeshPro 资源；当前仅头部身份可读，字段布局仍待补齐。另有 425 个精确 CDN 键返回 404、57 个缺失 GUID 等既有缺口，详见 [源资源验收](validation/2026-10-25-release-summary.md)。本版未新增 Editor/Player、视觉或玩法验收；游戏源码恢复及未知类型限制继续明确记录。

## 安装

从本版本 GitHub Release 下载 wheel、SHA256SUMS 和 install_release.py，先核对附件 SHA，再运行：

```sh
python3 install_release.py --wheel monkey_native-0.4.0-py3-none-any.whl --sha256 <wheel SHA256>
monkey --version
monkey capabilities --json
```

唯一日常命令为 ~/.local/bin/monkey；安装器使用独立版本虚拟环境，校验后原子切换 current，保留旧环境回滚。仓库 bin/monkey 转发正式安装；开发验证显式使用 .venv/bin/python -m monkey.cli。引擎、UnityPy、AssetRipper 与游戏素材不包含在发行包中。
