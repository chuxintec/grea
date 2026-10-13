# ARM32 Android 模拟器兼容入口

为需要 armeabi-v7a 环境的输入保留独立模拟器。镜像 ABI、启动器和主机架构必须匹配；安装 ARM32 镜像不保证任意新版启动器可运行它。

## 来源与前提

- 归档来自 AOSP android-9.0.0_r1 的 darwin-x86_64 版本，官方来源为 https://android.googlesource.com/platform/prebuilts/android-emulator/；归档不随公开仓库分发，使用者取得后自行记录哈希和来源。
- 在匹配的主机或经独立验证的翻译环境运行，不覆盖系统 SDK 中的其他模拟器。
- 恢复前核对归档哈希，保留上游 NOTICE；创建项目自己的 AVD 并选择空闲端口。

## 调用

从仓库根执行。将示例目录和 AVD 名称替换为已准备的环境；ANDROID_SDK_ROOT 可显式设置，否则使用系统常规用户 SDK 位置。

```sh
ANDROID_SDK_ROOT=/path/to/android-sdk \
ANDROID_AVD_HOME=/path/to/project/avd \
  ./bin/android-emulator-arm32 -avd sample-arm32 \
  -port 5554 -no-snapshot -no-boot-anim -gpu swiftshader_indirect -no-audio
```

该入口转发原始参数，不创建镜像或安装游戏。no-audio 运行不能验收音效。先确认 sys.boot_completed、package/window 服务和目标应用启动，再开展原生实玩；ADB 可连接不等于系统与游戏已经就绪。原生记录与设备详情保留在外部项目，不写入产品文档。
