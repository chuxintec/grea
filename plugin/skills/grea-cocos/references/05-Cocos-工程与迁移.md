# Cocos · 工程与迁移

锁Creator3.8.8。Domain为纯数据/规则；Gameplay用例与端口依Domain；Presentation依Gameplay/只读Domain及cc；Services实现端口，处理网络/配置/存储/平台；Bootstrap只装配/启动/释放。纯层不能依赖cc、具体服务或全局定位器，UI不直连网络/发奖。异步结果检查当前会话/生命周期；pending先存再发、同号重试，渲染失败不触发业务重发。

`cocos_project --output new-project --name Example --width 750 --height 1334`生成五层Signal Counter及JSON运行配置。设计尺寸显式可改，750×1334仅竖屏预设，居中等比/安全区与输入坐标一致，不拉伸、不重复乘DPR。正式数值JSON在运行时解析；源配置与派生公共配置有版本/hash，不能再维护SO或另一份手写数值。

`cocos_convert --input file --source-version 2.4.15 --output new-candidate`处理未编译平面对象数组：SceneAsset/Scene/Prefab/Node及列明的基础UI组件。2.4节点尺寸/锚点迁入UITransform，透明度迁入UIOpacity，保留父子关系、局部变换和组件引用。外部资源通过显式UUID映射与SHA验证的JSON/文本/音频闭包；纹理/SpriteFrame/图集trim/旋转/九宫格、Spine、Mask、动画、自定义脚本、skew和编译格式不自动迁移。无法闭合引用或有未知组件时输出blocked_unsupported和对象索引，不发布删掉组件的“成功”图。3.8同代仅基本类型子集，不等于全工程复制。其他2.x、Egret/Laya目标Cocos目前人工原生TS移植，不能宣传自动转换。

保留原资产UUID→目标UUID映射，不删meta重生。不能把2.4类型名原样塞入3.8就称完成；新增通用模板资产可用自己的确定身份，原资产移动沿Editor原生流程。图集/字体/换行、父缩放、空场景/资源导入、二维动画Z尺度、Mask/生命周期分别验证，未覆盖机制明确留待人工制作。工具暂不支持不阻止独立实现。

Creator官方CLI用于实际可用的导入/构建：[官方命令](https://docs.cocos.com/creator/3.8/manual/en/editor/publish/publish-in-command-line.html)。指定实际Editor `--project PROJECT --build "platform=web-desktop;debug=true"`；成功后浏览器开真实构建，核对渲染/输入/资源与设计尺寸。CLI仍需要桌面环境；先协调窗口，不能抢产品Editor。Funplay仅可选探测，缺少时明确未连接，不自动安装。

模板生成、序列化候选、Editor导入、浏览器输入和原版一致性分别记录。详见 [工具说明](../../../../docs/providers/cocos-target.md)。

强制遵守[实际体验与画面对照](../../../shared/03-取证-实际体验与画面对照.md)：核心循环、教学、培养截图和连续录像按当前范围覆盖；静态解析不能代替实玩，修前/修后在真实入口核验。
