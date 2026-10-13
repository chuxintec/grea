# Unity 资源回读审计

`RecoveryRuntimeAudit.cs` 使用 UnityEngine/UnityEditor，无Spine编译依赖，不修改游戏资源、设置或场景。

- `RecoveryRuntimeAudit.Run(string[] args)`：两个参数 `["Assets/指定目录", "/绝对路径/新报告.json"]`，读取该范围Prefab；或 `["@loaded-scenes", "/绝对路径/新报告.json"]` 读取当前已加载场景，不切场景、不进入Play。
- `RecoveryRuntimeAudit.Texture(string[] args)`：三个参数 `["Assets/纹理.asset", "/原始浮点文件.raw", "/新报告.json"]`；GetRawTextureData逐字节比较，报告尺寸、format、filter、wrap、sRGB与mipmap。
- `SelfTest()`：只供含 `P0_ISOLATED_TEST` 哨兵文件的独立临时工程；会创建合成GameObject和测试纹理，禁止在正常业务工程中调用。

Run报告包含observations与findings：Missing Script、Sprite.texture为空、材质为空、错误/占位Shader、实际Shader路径、Sprite排序及相机mask/depth；Spine读取序列化skeletonDataAsset/atlasAssets，核对可解析的传统atlas页名和尺寸。Spine数据版本仅提取头部候选，不把程序集版本当数据版本；新atlas格式或不可解析数据需要专用解析器，不宣称完整通过。

没有finding不等于可见或原版一致。纹理不可读会直接抛错，不擅自开启Read/Write；对压缩纹理的原字节应采用对应格式契约。报告均以CreateNew写入，不覆盖旧证据。Report.observations可能包含未激活对象；验收时结合active、相机与实际画面判断。

先在匹配 Editor 版本的隔离工程中编译并执行 SelfTest。批处理-nographics只能验证编辑器API与字节回读，不能验证Metal渲染效果。
