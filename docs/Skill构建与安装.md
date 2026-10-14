# Skill 构建与安装

Skill 的唯一源码是 `skill/`。恢复流程和开发规范在 `SKILL.md` 与 `references/`，不从安装副本反向修改。当前版本为 **2026.10.14rc1**，由 [version.json](../skill/version.json) 声明；首次独立制品沿用当前 grea 版本。发布新版本时同时更新其中的 `version` 与 `greaVersion`，发布构建强制核对它们和产品版本一致。

## 两种交付

- 完整包 `grea-<tag>.zip`：产品源码、工具、规范、维护脚本与测试。
- Skill 包 `grea-skill-<tag>.zip`：解压得到 `grea/SKILL.md`、完整专题参考、版本声明、MIT 许可和逐文件身份清单。

Skill 包不附带 Python 环境或 Unity；阅读流程不需要完整仓库，执行工具仍需安装匹配的 grea。安装后通过 `grea session` 核对版本和 requiredOperations；未安装工具时不能声称可以执行恢复。开发分支可能与同版本旧 Release 内容不同，应同时核对源码提交；现有发布标签不重用、不覆盖。

## 安装

校验 Release 附件的 SHA256SUMS，解压 Skill ZIP，将其中 `grea` 目录放入客户端支持的技能目录；安装目标已有内容时先备份或比较，不直接覆盖手工修改。客户端发现技能后，读取 SKILL.md 并实际调用 grea session 才能确认工具连接；文件复制成功不代表 Editor 已连接。

工作区开发安装仍使用 `python3 scripts/sync_skill.py --destination /absolute/skills/grea`，并运行同命令加 `--check`。它从规范源码生成安装副本，会同步删除副本多余文件，不能指向混有手工作业的目录。Release ZIP 是可迁移制品，不依赖此开发同步目录。

独立包内所有本地链接都落在自身目录。指向工具实现、接口说明和历史证据的可选链接在构建时转为固定提交的 GitHub 地址；这些在线资料不计为离线包内容。尚未推送的本地构建所对应在线链接可能不可访问，不能据此宣称已发布。

## 独立构建

在干净、已提交的 grea 源码中执行，输出目录必须不存在：

```sh
python3 scripts/build_skill.py --tag v2026.10.14-rc1 --out dist/skill-check
python3 scripts/build_skill.py --tag v2026.10.14-rc1 --out dist/skill-check \
  --verify --extract /absolute/new-skill-install
```

命令只在本地构建与核验，不创建标签、不上传。构建读取 Git 提交对象，版本不匹配、缺失引用、包外本地路径或校验失败都会停止。

Release 流程同时构建两个 ZIP，生成同一制品清单和校验文件，并独立解压 Skill 检查内容与可迁移链接。相同提交重复构建应字节一致；未来结构调整仍保留完整包的既有入口与工具 ID。


开发安装保留本地仓库链接，Release 安装使用固定提交 URL；两种形式的使用场景不同，保留各自链接转换和测试。版本相同不表示不同提交字节相同，升级时还须核对 sourceRevision／安装来源。同步前用 `--check` 查看差异；生成副本中不存手工内容。

安装身份可通过 `./bin/grea session '{"skill_dir":"/absolute/skills/grea"}'` 显式检查。默认 session 检查随源码附带的 Skill，不自动推断客户端实际加载了哪个目录。
