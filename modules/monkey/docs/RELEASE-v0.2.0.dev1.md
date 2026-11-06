# monkey v0.2.0.dev1（预发布）

这是声明支持范围已通过本地工具验收的开发预发布，Python 包版本为 `0.2.0.dev1`。仓库为私有 `chuxintec/monkey`；需要相应访问权限。v0.1 稳定版本保持不变。

## 工具能力

- `monkey convert` 从明确提供的 wxapkg、APK、资源目录或 input-set 生成独立原生候选工程。Cocos 来源目标为 Unity 6 / Cocos Creator 3.8.8 / both；其他已适配来源目标为 Unity 6。
- 盘点明确输入内全部可枚举文件，按原生转换、复制、去重、原格式待转、缺失引用和过滤逐项记账。支持来源声明中的精确 CDN / 远程包清单、有界下载、版本及哈希核验、缓存复用；不会猜测未取得的远程文件。
- 恢复已支持的图像/帧、字体、资源引用、JSON、节点及 Prefab 子集；输出源码模块索引、有据目标代码、SourceRecovery 和 AI 接续入口。原件只读，新输出隔离，人工修改与身份漂移有冲突保护。
- 可显式编排已安装 Editor 的原生导入、保存重开和分层回读；安装包不包含引擎或本机 provider，也不自动安装这些工具。

## v0.2 新增

- 扩展有版本证据的 Cocos 2.1.2、2.4.11、3.4.1、3.8.7 来源子集，保留 2.4.15；增加 Unity 2021.3 / 2022.3 明确 Bundle / WebData 的受限恢复，以及 Egret 5.2.32 自定义资源/图集读取。具体支持以矩阵为准。
- 原生嵌套 Prefab、模板对应、局部 ID、override，以及实际出现的新增节点/Widget 代表保存重开验证。
- 动态 Label / Widget / Layout，补缩放 Grid、行列约束、child-resize 和缩放线性代表：双端 6 组、54 个 Editor 状态、1242 个几何数值，严格回读零诊断。该结果不等于 Player 或全部布局组合通过。
- 具名有据 C# / TypeScript / JavaScript 数值子集及实际绑定；Cocos **默认 TypeScript，JavaScript 次选**，参数为 `--cocos-code-language ts|js`。未知方法不以空壳或假成功充数。
- 默认 `--format none`，可选 `--format grea` 做独立 typed 后处理，保持资源身份、引用、动态 key 与人工维护边界。

## 安装与运行

Python 3.11+（本地实测 3.14.7）；固定 Pillow 12.2.0。JS 静态解析需要已有 Node.js，Acorn 随包提供；ASTC 可选依赖为 texture2ddecoder 1.0.6。Unity 专用来源需配置既有固定 provider，原生导入需精确 Editor 版本：Unity 6000.6.2f1 / Creator 3.8.8。

```sh
gh release download v0.2.0.dev1 --repo chuxintec/monkey --dir monkey-v0.2.0.dev1
cd monkey-v0.2.0.dev1
shasum -a 256 -c SHA256SUMS
python3 -m venv .venv
.venv/bin/python -m pip install ./monkey_native-0.2.0.dev1-py3-none-any.whl
.venv/bin/monkey --version
.venv/bin/monkey convert --source /path/to/game.wxapkg --target both --out /path/to/new-output --offline
```

`both` 用于 Cocos；其他来源使用 `--target unity6`。输入集合可改用 `--input-set /path/to/inputs.json`；需要按明确清单获取 CDN 时去掉 `--offline`，参数合同见 [USAGE](USAGE.md)。需要格式后处理时追加 `--format grea`。原生导入的 `--native` 和 Editor 参数另见使用说明，不因生成候选就声称已验证。

## 必须保留的限制

这是 **partial / blocked 分层恢复工具，不是所有引擎版本或完整游戏的一键无损还原器**。source archive 11 例均保留，10 例不同范围导出、1 例团结 blocked，完整游戏 0；不能把此数量换算为完整兼容率。Laya/LayaAir、自研及其他格式仍需具体 adapter，图片 gallery 不代表源 UI 已恢复。

47 份其他布局 guard 保留：27 负缩放线性、19 NONE、1 浮点 padding。Spine 运行/播放、Egret 源 UI、缺模板、未知或受保护方法/组件、部分 Unity 类型/实例值、Creator 根继承与未验证的任意 mounted/removed 等按逐 case 限制保留。原生代表是 Editor 强制更新和保存重开；Player 逐帧、原版视觉/输入及完整玩法仍 `not_run`。部分候选返回 exit 1；请读取 `conversion-result.json`，`completed=true` 只表示声明流程完成。

支持详情见 [SUPPORT-MATRIX](SUPPORT-MATRIX.md)、[代码子集](CODE-SUBSET.md)、[布局续修](validation/2026-10-24-layout-followup.md)。232 项工具测试和已验原生代表结果复用，本次发布不复跑引擎。

## 制品与源码身份

本次直接发布已验分发02的三个文件，不重建：

|文件|字节|SHA-256|
|---|---:|---|
|monkey_native-0.2.0.dev1-py3-none-any.whl|398326|[private fingerprint omitted]|
|monkey_native-0.2.0.dev1.tar.gz|609147|[private fingerprint omitted]|
|SHA256SUMS|206|[private fingerprint omitted]|

包源码快照为本地 `[private fingerprint omitted]`；106 个包载荷文件与发布 tag 的产品源码逐字节一致。tag 指向的提交另含最新发布文档和精简验收摘要；没有重造功能或更改包版本。完整开发历史与逐节点证据载荷保留在本地，不推送该含载荷的开发分支；发布提交由既有 main 正常快进产生，不强推，不移动 v0.1。

wheel / sdist 不包含游戏原件、下载资源、私有样本、outputs、引擎/provider 二进制或凭据。GitHub 自动生成的 tag 源码归档对应发布提交文档；附件 sdist 对应上述已验包快照，两者的文档内容可不同。
