# Unity 工具包备份与后续安装

本目录公开备份/恢复工具，不公开任何实际快照或插件包。快照保留在本机或项目指定的私有位置，由 `.gitignore` 排除。优先通过目标项目的 Package Manager 从官方渠道恢复依赖。

`snapshots/<日期>/catalog.json` 记录实际项目安装的非内置UPM包、解析版本、匿名来源编号、依赖与归档SHA-256；archives中的tgz含完整包源、说明及许可证。相同名称版本但不同内容独立保留，不能静默覆盖。

## 生成新备份

```sh
python3 unity-packages/package_backup.py snapshot --project /path/UnityProject --output /path/grea/unity-packages/snapshots/new-date
```

以项目真实Unity根为输入；检查Packages/lock及Library/PackageCache/embedded packages。逐文件SHA-256验证归档后写目录；catalog已存在拒绝覆盖。snapshot只读取项目，不执行包内代码。

## 后续项目安装

```sh
python3 unity-packages/package_backup.py plan --backup /path/snapshots/2026-09-22 --package com.unity.memoryprofiler@1.1.12 --output /tmp/new-install-plan.json
```

plan校验归档哈希，并按保存的实际解析依赖生成file:包路径；发现版本冲突、缺失或同版本多份内容会拒绝猜测。不要手改manifest安装。将 `InstallBackupPlan.cs` 复制到**目标项目**的 Assets/Editor/Tooling，先备份其Packages清单，再通过Unity二进制批处理调用 `-executeMethod InstallBackupPlan.Install -toolingPlan /tmp/new-install-plan.json`，**不加-quit**。异步UPM完成后脚本退出，日志 `BACKUP_INSTALL_OK`。活编辑器存在时使用其已验证脚本接口，不另外开同一工程。

恢复包不保证与任何未来Editor兼容；先查包package.json的Unity版本要求，执行编译/实际能力检查。file:安装记录指向共享备份路径；复制工作区时同步工具备份，或者通过UPM改回明确的registry版本。跨项目不自动安装全部备份包，只选择当前任务需要的包与依赖。

## 非UPM插件

通用插件保留其来源、许可证与恢复说明。包含本机编译路径的预编译运行时和业务原生桥不随产品分发；Spine 等运行时须自行取得获准使用的对应 vendor 源码，再在目标环境构建，匹配数据版本与许可证。不能盲目覆盖目标工程 GUID。

## 可分发的备份元数据

快照默认用 source-N 标识来源，只保存包在输入工程内的相对位置；归档创建者和文件所有者元数据清空。包内源码、许可证与文件内容不因元数据脱敏而改变。已脱敏归档使用重新计算的 SHA-256，恢复计划必须读取当前清单；不能用旧压缩包哈希验证新归档。项目专用原生桥及原始项目记录不随产品分发。

快照会拒绝包含当前用户主目录或输入工程绝对路径的文件；先清理生成缓存或重新取得干净包源，再创建备份。这是本机路径防回流检查，不是任意敏感内容识别器。
