# monkey v0.1

Python包0.1.0。首个正式工具Release；早期0.3.0.dev1仅为内部开发候选编号，旧证据保持原身份。

## 已提供

- 一条`convert`将明确输入的明文wxapkg、APK或Cocos资源/编辑工程集合输出Unity6（6000.6.2f1）、Creator3.8.8或both独立候选。
- 当前结构化来源限定CocosCreator2.4.15支持子集：节点、Prefab、图像/帧、字体、部分布局/动画、资源引用、JSON与原名/身份映射。
- 全文件去向账、缺失引用、静态源码/模块依赖、目标代码占位初稿及AI接续入口；原件只读、输出隔离、人工修改冲突保护。
- 明确远程URL/SHA清单的有界获取与本地缓存复用，404/预算/身份冲突分别报告。尚不自动发现所有引擎的全部CDN地址。
- `--native`按Unity→Creator顺序执行冻结候选的有界原生导入、保存重开及严格回读，首失败停止后续目标。

## 实际验证与边界

full14输入17201文件/884709704字节，16627声明CDN缓存文件全SHA匹配；两端各1694独立Prefab、24784 Scene节点原生保存重开，完整几何/引用验证零诊断。Unity资源层partial，Creator资源层pass；详细证据见`docs/validation/2026-10-24-full14-single-command.md`，不因本次版本号重跑双Editor。

914业务文件仍是占位初稿，尚非可接续的完整业务实现。Creator1006 Label CLAMP及18 Sprite CUSTOM保留烘焙几何，源动态尺寸语义仍handoff；其他未知组件、1521缺失/redirect引用、Spine运行接入/播放、原版视觉、实际交互和整游戏可玩均未完成。`completed=true`只表示声明的候选流程完成，needs_action/exit1不代表游戏交付失败被隐藏。

Unity来源、其他Cocos版本、Laya/LayaAir、Egret和自研/其他引擎是后续目标，v0.1未宣称支持。v0.2方案见`docs/V0.2-PLAN.md`，先审阅再开发。

## 安装和快速运行

Python3.11+（实测3.14.7）；固定Pillow12.2.0；JS静态解析需已有Node.js，Acorn8.15.0随包提供。可选ASTC依赖texture2ddecoder1.0.6。原生导入需已有精确版本Editor；不自动安装或分发编辑器。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install ./monkey_native-0.1.0-py3-none-any.whl
.venv/bin/monkey --version
.venv/bin/monkey convert --source /path/to/game.wxapkg --target both --out /path/to/new-output
```

原生导入可追加`--native --unity-editor /path/to/Unity --creator-editor /path/to/CocosCreator`。明确输入资料集与远程清单参数、身份续验及接续方式见README和docs/USAGE.md。

附件：wheel、源码分发包、SHA256SUMS。源码/包保留GREA和Acorn的MIT许可；没有游戏原件、转换产物、私有样本、编辑器或本机provider。未执行全局安装、游戏服务变更或生产游戏发布。
