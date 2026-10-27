# ARM32 Android 模拟器兼容入口

此入口供明确需要 `armeabi-v7a` 环境的取证任务使用。镜像 ABI、启动器和主机架构必须匹配；安装 ARM32 镜像不保证任意新版启动器可以运行它。先确认本次模拟器和目标应用的取证授权，并在项目内保留设备及运行证据。

## 归档来源与核验

兼容归档来源是 AOSP `android-9.0.0_r1` 的 `darwin-x86_64` emulator，官方位置为 [Android emulator prebuilts](https://android.googlesource.com/platform/prebuilts/android-emulator/)。已观察到的归档版本为 `27.3.5`，SHA-256 为 `29003cb3930280ef39444037fe0bd039f2af872d088eb1705c3f610fed6bf379`；哈希覆盖当时下载的归档字节。Gitiles 可能重新生成归档，哈希不匹配时应暂停并人工复核来源，不要静默替换记录。

参考镜像为 `system-images;android-25;google_apis;armeabi-v7a` revision 18。主机记录是 `darwin-x86_64`；Rosetta 或其他翻译环境是否可用须在部署环境单独验证。归档不随公开 GREA 包分发。取得归档后记录实际来源和哈希，保留上游 NOTICE，并将副本放在隔离的本地/项目运行环境；不得覆盖系统 SDK 的其他模拟器。

## 调用

从已安装 GREA 根目录使用 `bin/android-emulator-arm32`，为项目单独创建 AVD 并选择空闲端口。可显式设置 SDK 与 AVD 根路径：

```sh
ANDROID_SDK_ROOT=/path/to/android-sdk \
ANDROID_AVD_HOME=/path/to/project/avd \
  ./bin/android-emulator-arm32 -avd sample-arm32 \
  -port 5554 -no-snapshot -no-boot-anim -gpu swiftshader_indirect -no-audio
```

入口转发原始模拟器参数，不创建镜像、不安装游戏，也不覆盖系统 SDK。`-no-audio` 下的运行不能验收音效。启动后核对 `sys.boot_completed`、package/window 服务和目标应用启动；ADB 可连接不代表 Android 系统已就绪或游戏行为已验证。游戏安装、账号、存档或运行时读取均须有相应授权。

原生运行记录和设备详情保留在执行项目中，不写入 GREA 产品文档。平台帮助、实际安装器能力和本机环境以已安装 GREA 根目录中的实际文件及工具 `describe-tool` 结果为准。
