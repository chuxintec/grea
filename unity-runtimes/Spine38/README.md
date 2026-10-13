# Spine 3.8 runtime

Official source: https://github.com/EsotericSoftware/spine-runtimes/tree/8b4844bd4b193ba9e54487ed397a777993cbad56

Build configuration for the 3.8 branch for compatible Spine 3.8 data. Verify the exact exported data version before importing. Preserve LICENSE and upstream notices. Runtime use/distribution remains subject to its license.

Build: `dotnet build unity/unity.csproj -c Release -p:UnityProjectLibrary=/absolute/project/Library`. Unity 6.5 managed reference path is parameterized in Directory.Build.props.

Compatibility: core grants InternalsVisibleTo(spine-unity), matching upstream shared-assembly access; AnimationClip comparer uses Unity object equality and GetHashCode instead of removed GetInstanceID.

公开仓库仅保留构建配置与原许可文本，`vendor/` 源码及编译产物不分发。自行取得上述固定提交，按构建文件所列路径准备 core/unity（适用时 timeline）源码。既有本机兼容调整不随 vendor 分发；更换 Unity 版本后须独立检查 API 兼容性，不保证直接构建通过。
