# 可选 Frida 环境

客户端及服务端均不随公开仓库分发。从 [官方文档](https://frida.re/docs/installation/) 与 [发行页](https://github.com/frida/frida/releases) 取得匹配版本，核对目标 ABI、哈希及许可证。客户端可安装到仓库根下被忽略的 `.private/providers/frida/.venv`，也可通过 GREA_PROVIDERS 配置其他路径。

GREA 不自动推送文件、启动服务、附加进程或读取应用存储。实际操作须属于当前授权，项目专用观察脚本保留在项目内。客户端存在或版本探测通过不代表目标设备已连接。

## 本机参考配对

2026-10-13 本机调用验收：Android ARM64 server 17.18.0 pairs with `frida` 17.18.0。归档 `frida-server-17.18.0-android-arm64.xz` 的 SHA-256 为 `77c2a4aadf6010c69766abea5b6a408c66f5e2da43b3f2c920cf75a5fa1ec7f5`。

`./bin/grea legacy registry_doctor --verify-frida-pair --json` 读取本页参考值，检查客户端版本与 `.private/providers/frida/` 下归档哈希；该本机记录不是上游签名证明，不执行服务端或连接设备。更新版本时先核对来源、客户端与归档，再更新参考值。
