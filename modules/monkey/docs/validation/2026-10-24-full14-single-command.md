# full14 单命令双端资源原生验证

2026-10-24 本地开发候选，代码90253c8。实际命令及阶段详见本机 outputs/full-sample-game-14/conversion-result.json、outputs/full-sample-game-14-native/native-orchestration.json；原件不写、旧失败不覆盖、未发布。

## 输入与冻结身份

每端17201文件、884709704字节全部入账；16627声明CDN文件799052150字节全SHA缓存匹配，无新增GET。这只覆盖明确清单，不消除先前7个HTTP404或未知URL。双端静态、名称稳定、来源路由核对均零问题。

- Unity manifest: [private fingerprint omitted]
- Creator manifest: [private fingerprint omitted]
- 源输入清单: [private fingerprint omitted]

## 实际原生结果

| 目标 | 子进程 UTC / 退出 | 方法耗时 | 强验证 |
| --- | --- | --- | --- |
| Unity6000.6.2f1 | own53301 16:35:36→16:46:23 / exit0、reaped | 475.455秒 | diagnostics0、editor partial |
| Creator3.8.8 | own55108 16:47:06→16:57:09 /正常TERM exit-15、reaped | 520.029秒 | diagnostics0、editor pass |

固定阶段锚点Unity16:35:20.404958Z、Creator16:46:24.264636Z，各自内部+28/外部+30分钟，方法1200秒，未延钟。整链 completed_native_stages；未遗留自有Editor。Creator仅在实际读回通过后正常结束自有进程，不能把TERM退出单独当失败或完成证据。

两端各1694独立源Prefab和24784 Scene节点保存/重开，完整position/size/pivot/active/scale/quaternion及内部引用严格检查。Unity16934 Sprite、16原字体、1006 Label、10508 View引用、MissingScript0；Creator16939 SpriteFrame、16978资产、12568组件、5位图字体SpriteFrame→Texture身份与矩形检查通过。原始版本/字体/位图页/根名策略均核对，无公差放宽。

## 结果边界

Unity11992/28514、Creator12568/28514源组件进入当前转换子集；1006 Creator Label以CLAMP、18 Sprite以CUSTOM保留烘焙几何，源模式和动态尺寸handoff同时保留，不能宣称auto-size语义恢复。Unity使用uGUI GridLayoutGroup的layoutPriority扩展，原生计算Flexible行列及Preferred尺寸。源数据、像素及AST未为本轮重复解析。

914业务代码初稿、1521缺失引用（1517 redirect+4真实main import）、未接入Spine运行时/播放、原版视觉及真实交互仍是独立未完成项。CLI completed=true仅表示候选生成流程完成，status needs_action/exit1符合合同；未声称整游戏恢复或全版本支持。

## CLI本地制品

monkey_native-0.3.0.dev1-py3-none-any.whl，223337字节，SHA256 [private fingerprint omitted]。包含55条目，导入器、Grid原生组件、Acorn和许可证齐全，无私有样本/转换产物。通过项目私有target安装后，在独立cwd确认实际加载安装模块并完成合成wxapkg五文件→双端候选；没有全局安装或发布。dist/full14-local/BUILD.json及.private/wheel-smoke-14/smoke.stdout为本机回执。


## v0.2 源字段回查补充

2026-10-24后续NumberLabel接线核对发现旧normalizer漏读`_N$overflow`别名。离线精确源ID对账：full14已转换的1006 Label中89个受影响（85个源SHRINK=2、4个源RESIZE_HEIGHT=3）；旧source overflow=0说明不适用于这些对象。旧候选/native几何与引用检查读回通过事实保持，表示当时生成合同的读回，不证明这些原动态overflow语义已恢复。原生视觉/业务本来未验；v0.1/tag/候选/原IR不反写，v0.2读取器修正精确别名及冲突拒绝，后续必须按真实模式另行生成验证。
