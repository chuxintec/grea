# Unity 可编辑视觉资产恢复

适用已获准的 Unity 来源、已固定包体和独立 Unity 6 候选。按源对象 `(serialized file, pathID, raw SHA-256)` 建账；可寻址根、独立视觉对象和目标物理文件分别计数。复用既有目标必须有原生身份、原始引用或像素/几何证据，不按近似名称认领。

## 公开入口

- `grea asset prepare-bundle-models --inspections 检查目录 --occupied 已占路径.txt --output 新目录`：读取 GREA 批量检查的 `BatchInspection/job.json` 和已固定 typed-objects，复核包体及检查文件哈希，生成 `job.json` 与 `BundleModelRecovery.cs`。只接受 Transform、MeshFilter、MeshRenderer 的静态 FBX 根；外部网格、自定义材质依赖、脚本及骨骼模型明确拒绝。路径由公共 LayoutPlanner 分配。
- `grea asset prepare-visual-assets --texture-plan 纹理.json --atlas-plan 图集.json [--font-plan 动态字体.json] [--binding-plan 材质接线.json] [--packable-sprites] --output 新目录`：固定来源派生的计划与原生脚本，不修改工程。输入数值与成员身份必须已经由源对象证明。
- `grea asset reconstruct-gles-shader --source 源程序目录 --output 新目录`：输入原始 Shader 的 `form.json` 和按 blobIndex 命名的 `.glsl`，输出可编辑 ShaderLab、输入哈希与变体数量。支持 HLSLcc GLES2/GLES3 的非实例化组合程序；原平台剥离的整个 SubShader 使用其原有后续可用 SubShader。部分 Pass 缺程序、未知采样方式或损坏程序不可用其他 Shader 代替。
- `grea asset verify-visual-assets --project 工程 --paths 路径.txt --unity-editor Editor可执行文件 --output 新目录`：通过临时原生探针逐资产读取对象、引用身份和指纹，检查缺引用、Shader 错误和未识别动画属性。发现问题返回 partial；不代替源对象对账、截图或 Play Mode 验收。

所有入口的参数由[命令索引](../../grea/references/功能模块和命令参数.md)生成。准备结果中的 `nativeReadback=not_run` 表示尚未执行 Unity。

## 原生计划与执行

只在独立、可写的候选中放入准备输出的 Editor 脚本，由匹配的可信 Unity Editor 调用下列静态方法。执行记录绑定准备目录及脚本哈希；暂存脚本在采用前移除。

| 原生方法 | 环境变量与输入 | 行为 |
|---|---|---|
| `Grea.VisualRecovery.BundleModels.Run` | `GREA_MODEL_JOB`、`GREA_MODEL_SEEDS`（既有 Mesh 路径逐行）、`GREA_MODEL_PHASE=create/read`、`GREA_MODEL_REPORT` | 读取固定原包，保存独立 Prefab、Mesh、Material，或冷读核对；原节点、局部变换和引用逐项验证 |
| `Grea.VisualRecovery.AssetReadback.Prepare` | `GREA_VISUAL_RUN`（准备目录） | 应用源纹理采样参数、创建源成员组成的 SpriteAtlas |
| `Grea.VisualRecovery.SpriteAtlasRecovery.Run(planPath,reportDirectory)` | 显式计划与回执路径；`--packable-sprites` 输出脚本 | 原生可打包制作切片与图集接线；源 Sprite 保持独立 |
| `Grea.VisualRecovery.AssetReadback.Inspect` | `GREA_VISUAL_RUN`、`GREA_VISUAL_PHASE=save/read`、`GREA_VISUAL_REPORT`（文件名），准备目录包含 `new-paths.txt` | 保存或逐资产原生读取；独立退出并重开 Editor 后比较 TSV 指纹 |
| `Grea.VisualRecovery.SourceTextureBindings.Run` | `GREA_BINDING_RUN`、`GREA_BINDING_PHASE=apply/read`、`GREA_BINDING_REPORT` | 按源材质属性名重接拆分纹理；现有引用必须属于已证明像素一致的 GUID 集合 |
| `Grea.VisualRecovery.DynamicFonts.Run` | `GREA_FONT_RUN`、`GREA_FONT_PHASE=create/read`、`GREA_FONT_REPORT` | 仅从存在的原字体创建空动态 TMP 字库、保存源材质参数，并在独立临时字体中测试出字 |

纹理计划为 `{"textures":[...]}`，每项含 `path,w,h,wrapU,wrapV,wrapW,filter,aniso,colorSpace,mips`。`preserveImport=true` 可只修复源采样参数并保留既有导入类型、压缩和尺寸设置。数值取源 Texture2D，尺寸限 1..8192；`colorSpace=1` 对应 sRGB。不可把不同采样参数的纹理仅按像素合并。原图与解码图都保留校验值，颜色通道和上下方向单独核实。

图集计划为 `{"atlases":[...]}`，每项含 `target,tag,members`；每个成员为 `path,guid,local`，必须解析为实际 Sprite。创建后以 Unity 分配的实际 GUID/localID 更新去向账，不能继续用计划中的预设身份。Unity 6 新建 V1 图集还需以实际资产 GUID 设置内部打包身份，并同时显式设置默认和 Standalone 的无损 RGBA32 格式；只设置平台覆盖仍可能以无效 Automatic 格式进入打包。

独立 `.asset` Sprite 可以显示，却未必能提供图集打包所需的原始图像。`--packable-sprites` 额外输出 `SpriteAtlasRecovery.cs`，要求候选先由 Package Manager 安装编辑器自带 `com.unity.2d.sprite@1.0.0`。调用 `Grea.VisualRecovery.SpriteAtlasRecovery.Run(完整图集计划路径,新回执目录)`，经 Sprite Editor Data Provider 的能力检查创建原像素副本和可编辑切片，再接入图集。先撤销源 Sprite 的水平/垂直翻转或 180° 打包旋转，像素与切片矩形同步变换；逐顶点校验源 UV 与该变换吻合，未知旋转或取样变换拒绝。原 Sprite GUID、精确网格和原 Prefab 引用保持不变；新增制作副本位于 `Assets/Game/Content/Sprites/Sheets/`，按源纹理、PPU、源打包翻转和同名冲突分组，身份取源成员集合摘要。已有副本须证明所有权和像素一致，才能读回或继续处理。若升级既有图集制作副本，第三个可选参数传入独立的上一轮回执目录；图集只允许从原成员、已证明的上一轮成员或本轮成员切换，不覆盖陌生引用。

轮廓取原始三角形的并集，使用 Unity Sprite Editor 同一原生多边形接口，并检查当前接口签名。本能力已实际验证的版本是 6000.6.2f1，不声明其他版本兼容。原生导入会重新三角化；回执记录轮廓偏移和必要时的填充面积差异；像素网格容差为半像素对角线，退化细边以原轮廓周长推导的像素量化面积上限检查，超限停止。原独立 Sprite 保留完整原几何。制作副本的原生像素网格量化不冒充源网格逐顶点一致。

打包验收必须监听 Unity Error/Exception 并读取实际成员、尺寸、Pivot、边框和像素；报错后的缓存 `spriteCount` 不能作为成功证据。

字体计划为 `{"fonts":[...]}`。每项含 `key,target,name,fontPath,shaderPath,point,padding,width,height,mode,multi,clear,queue,keywords,probe`；另含源材质 `floats[{name,value}]`、`colors[{name,value:{r,g,b,a}}]`、`textures[{name,scale:{x,y},offset:{x,y}}]`。该入口只用于源字符/字形表为空的动态字库；`_MainTex` 指向原生动态图页，其他纹理必须在来源检查中确认为空。来源无字体文件的字库保留限制，不用系统字体替换。工具可临时提供 TMP 字体工厂上下文，绝不保存成游戏设置。原字体材质里未被当前 Shader 声明的历史属性仍经 SerializedObject 保存和冷读核对。

材质接线计划为 `{"materials":[...]}`，每项含 `material,property,texture,textureGuid,source,allowed`，其中 allowed 是现有引用允许的 GUID 数组，必须由原像素和尺寸证明。一个目标材质属性不能由不同源对象提出互相矛盾的目标；遇到冲突须先拆分源实例。该方法使用 SerializedObject 保留 Shader 当前未公开的已保存纹理字段。可选 `sprites` 数组包含 `sprite,guid,local,property,texture,textureGuid,source,allowed`，只接收源证据确认的 `m_RD.texture` 槽；不能只修材质而遗漏直接引用同一采样纹理的 Sprite。

## 关键保真规则

原生 Mesh 已解压后必须关闭再次保存压缩。验证全部顶点流、索引、子网格及 Bounds，防止首次内存对象一致但冷读几何变化。静态网格可按名字和完整几何指纹复用，骨骼及 blendshape 不在此静态入口范围。

Shader 从二进制 `.asset` 转为 `.shader`、字体/纹理改为导入文件或资源被纳入子资产后，PPtr 的 GUID、localID **和 storage type** 都要重映射。`unity_asset_references` 依据真实目标类型处理，未知导入类型拒绝；必须在 Unity 中读取实际引用。

动画修复只接受原组件和源层级证明的 CRC 名称、逐槽 MonoScript 身份；`unity_animation_bindings` 不把一份脚本无差别挂到多类型曲线。属性或路径 CRC 无原字符串时保留原值和限制。已恢复键帧不表示每条曲线都已绑定到实际节点。

Shader 验证包括实际源关键词变体，而不仅默认 Pass。源矩阵数组恢复到原生 uniform 名称和布局；深度比较、纹理 bias/LOD、GLES2 扩展与导数运算保持源含义。平台源码恢复及目标 Editor 编译不等于所有目标 GPU、实例化或动态 GPU 蒙皮已验收。

## 采用与验收

原生保存、退出、冷读完成后冻结文件和 `.meta`，依当前采用流程增量接收。正式工程再次运行 `verify-visual-assets`，并核对源对象映射、类型、GUID/localID、字节和命名。保留既有资产身份，不将临时编辑测试副本、脚本、旧资源或整个验证工程复制进正式工程。

至少实际修改并保存代表材质、切片和曲线，冷读检查修改仍在；骨骼姿态、Animator 过渡及粒子时序在 Play Mode 单列记录。主动激活和人工 CrossFade 是验证刺激，不是游戏业务触发证明。源文件本来为空、动态生成、缺原字段或程序不完整时附准确对象与原因，不能用占位图、猜测路径或任意默认 Shader 报通过。

原生指纹版本 2 按持久对象 GUID/localID 绑定字段，排序后计算，ShaderVariantCollection 按 Shader 身份比较其无序键。Sprite 的 `m_AtlasRD` 为图集打包派生的 Editor 缓存，单列 `editor-cache.tsv`，不混入稳定源引用指纹；`m_RD` 原纹理引用仍逐项验证。原始稳定指纹项写入 `object-fingerprints.tsv`。缓存检查不能替代实际图集打包和像素检查。
