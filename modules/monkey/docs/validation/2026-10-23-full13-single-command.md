# full13公开单命令端到端核对

当前在途，不是全版本/全游戏转换完成。实现提交4ecbf6f。

- frozen candidate: outputs/full-sample-game-13；获取回执: outputs/full-sample-game-13-acquired/acquisition.json；实际新副本及顺序回执: outputs/full-sample-game-13-native/native-orchestration.json。
- 原input-set SHA [private fingerprint omitted]，每端17201项/884709704B，1776Spine闭包。获取声明16627/799052150B全缓存SHA，无新GET、无重复materialization；之前实际GET探针独立保留，不将0 missing推成未知地址都存在。
- Unity manifest80484c192bee73c172673fc3d0dfa87906d242149d061afaad3ed2dd6a8e02bb；Creator [private fingerprint omitted]，均含acquisition证据。
- name/routing审计零问题，两端身份、保留字节及非名称IR保持；static和原生结果待本页后续实际记录。
- Unity固定段15:40:33.784088Z→16:08:33.784088Z内部/16:10:33.784088Z外部，方法1200秒；新own35982启动，自有副本。启动前两次ps无其他主Editor，禁止延钟/并发下一端/操作其他进程。
- 首新错误保留；nonzero诊断/child未退出停止下端。nativeStages completed也不等于原版画面/输入/业务或Spine播放通过。

full12在acquisition附证读取60MiB generated manifest误用原始输入32MiB预算安全停，原生0；仅修复使用现有生成文件128MiB/8m有界读取，逐文件owned SHA检查保持。33MiB反例及篡改owned文件拒绝均验证，失败目录不改。

全量覆盖口径另核：节点24784/组件28514保持。Unity可转换组件11995→11988，新增7个明确Grid handoff：graphic最小尺寸4、scaled child2、缓存extent1；其余方向对齐/MinSize等仍由原生Grid实现。不能把这7项写成行为已转换。Creator可转换12568。双端1694独立Prefab计划、16原字体保持；静态verify、name与routing均零问题（full13-unity-static/full13-creator-static/full13-name-audit/full13-routing-audit）。Unity已实际进入texture-settings方法，own35982，后续回读待验。

## 实际结果：停止于Unity严格几何门

own35982 exit0/reap，方法441.597秒，1694原生Prefab+Scene与editable保存重开、24784节点、MissingScript0；editor fail40，分为同20源节点的Scene20与独立Prefab20。编排stopped，Creator not_run；全量单命令尚未通过。差异.private/full13-geometry-differences.json，集中多行Grid与上层布局，后续修复另新候选，失败副本不改。

实际UGUI2.6 Flexible Grid的minHeight为单行；preferredHeight依实际宽度得行数。同节点Image与Grid priority0导致preferred混用。修复为6行正常uGUI子类IntrinsicGridLayoutGroup，只override layoutPriority1，配原生Flexible+Preferred fitter，无源图/常量高度/自写Grid算法；恢复4个Graphic metrics原生映射。13图646节点/886组件/88frame/16字体探针08 manifest31b49cb02301eb989ee874f683580e3fb2d2d8af7c38fb4c8b212f1de03557bb，static/preflight及C# compile通过，真实尚未执行。

## 后续成组结果（不覆盖full13）

Unity Probe08：13图646节点/13 Prefab/16字体，4.093秒，own42078 exit0/reap，Scene+独立Prefab完整geometry/scale/quaternion/引用零诊断。Creator sizing03：15图577节点/15 Prefab/16字体/5位图页+alpha帧，3.772秒，own49235 normal TERM/reap，强Scene与Prefab geometry/引用/bitmap页零诊断。01剩1页裁切，02子资源reimport未修且新增页回读揭示3页，03移除该调用、完整图明确trimType none而闭合；均保留失败原件。原字体类型仍BitmapFont→SpriteFrame→Texture，未采用纯Texture替代。

Creator Label CLAMP及缓存Sprite CUSTOM为source-baked静态呈现政策，原自动尺寸行为单列handoff（probe61+3，冻结全量13适用1006+18）。不是字体测量/动态业务修复，不放宽.001几何容差。待full14集中完整输入，不追认full13通过。
