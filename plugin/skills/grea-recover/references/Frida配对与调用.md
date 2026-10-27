# Frida 客户端与服务端配对

Frida 客户端和设备端服务不随公开 GREA 分发。只有当前任务已明确授权目标设备和观察范围时，才安装、推送或连接；GREA 不会自动推送文件、启动服务、附加进程或读取应用存储。项目专用观察脚本留在项目内。客户端存在或版本探测通过，不证明目标设备已连接。

## 安装与发现

从 [Frida 官方安装文档](https://frida.re/docs/installation/) 和 [Frida 官方发布页](https://github.com/frida/frida/releases) 获取匹配版本，核对目标 ABI、发布来源、哈希及许可。客户端可安装到 GREA 私有目录 `.private/providers/frida/.venv`，也可通过 `GREA_PROVIDERS` 指定其他位置。实际可用能力通过已安装 GREA 根目录的 `list-tools`、`describe-tool` 检查。

## 版本配对参考

2026-10-13 的本机调用验收记录：Android ARM64 `frida-server` 17.18.0 与 Python `frida` 客户端 17.18.0 配对。归档 `frida-server-17.18.0-android-arm64.xz` 的 SHA-256 为 `77c2a4aadf6010c69766abea5b6a408c66f5e2da43b3f2c920cf75a5fa1ec7f5`。这是本机归档记录，不是上游签名或当前发行状态的证明；更新时先重新核对官方来源、客户端版本、设备 ABI 和服务端归档。

可运行登记器的只读配对检查：

```sh
grea legacy registry_doctor --verify-frida-pair --json
```

配对记录以随技能分发的 [结构化参考](../assets/frida-pair.reference.json) 为准，诊断不解析用户手册正文。该检查读取记录值，检查客户端版本与 `.private/providers/frida/` 下归档哈希；不执行服务端，也不连接设备。能力、连接状态和对授权数据的实际读取分别记录，不能由配对检查代替。
