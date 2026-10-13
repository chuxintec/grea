# Shader工具链

依赖 glslang 与 SPIRV-Cross／SPIRV-Tools。通过 doctor 核对当前版本；bin 下的入口动态定位系统安装，不绑定某台机器的安装前缀。

`python3 shader-toolchain/probe.py /path/combined.glsl --output /path/new-directory`

此探针适用当前导出的 `#ifdef VERTEX` / `#ifdef FRAGMENT` 合并GLES文本，不是任意Shader自动恢复器。原文件保持不变；把version提到首行、选择阶段，分别验证ES300与ES310适配副本。ES310适配使用自动location/binding，输出SPIR-V、验证结果、反射、HLSL及MSL。输出目录必须全新；子命令限时60秒。任一阶段失败返回1，原profile失败也不吞掉。

未将生成代码写入Unity资产。ShaderLab、关键字、实例化绑定、纹理采样、灯光和GPU画面仍按项目原证据接入验证。
