# Spine 4.1 Runtime Build

Build configuration for pinned official Spine Runtime source from commit `77a5db0ec6d16331f5efbaa7662bba9355bd3424`, with a Unity 6 compatibility adjustment for obsolete `AnimationClip.GetInstanceID` comparisons. Preserve `LICENSE` and upstream notices. Runtime availability does not grant rights to any game's artwork or animation data; use requires an appropriate Spine license.

Build against an existing Unity project's generated assemblies:

```sh
dotnet build timeline/timeline.csproj -c Release \
  -p:UnityEditorPath=/Applications/Unity/Hub/Editor/6000.5.10f1/Unity.app \
  -p:UnityProjectLibrary=/absolute/project/Library
```

Outputs are `spine-csharp.dll`, `spine-unity.dll`, and `spine-timeline.dll`. Copying DLLs, shaders, binding materials, or modifying project assets is intentionally outside this generic component.

公开仓库仅保留构建配置与原许可文本，`vendor/` 源码及编译产物不分发。自行取得上述固定提交，按构建文件所列路径准备 core/unity（适用时 timeline）源码。既有本机兼容调整不随 vendor 分发；更换 Unity 版本后须独立检查 API 兼容性，不保证直接构建通过。

构建配置位于本目录。使用 `-p:SpineVendorRoot=/absolute/spine/vendor` 指定第三方源码目录；未设置时使用仓库根下的本机 `.private/providers/spine/Spine41/vendor`，该目录不随 Git 分发。
