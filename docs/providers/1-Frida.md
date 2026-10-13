# 可选 Frida 环境

客户端及服务端均不随公开仓库分发。从 [官方文档](https://frida.re/docs/installation/) 与 [发行页](https://github.com/frida/frida/releases) 取得匹配版本，核对目标 ABI、哈希及许可证。客户端可安装到仓库根下被忽略的 `frida/.venv`，也可通过 GREA_PROVIDERS 配置其他路径。

grea 不自动推送文件、启动服务、附加进程或读取应用存储。实际操作须属于当前授权，项目专用观察脚本保留在项目内。客户端存在或版本探测通过不代表目标设备已连接。
