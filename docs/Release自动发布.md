# 标签触发的 Release 发布

[Release workflow](../.github/workflows/release.yml) 在推送 `v*` 标签时运行。仅接受 `vX.Y.Z` 与 `vX.Y.Z-rcN`（N 从 1 开始）；例如 `v2026.10.14-rc1` 是预发行，`v2026.10.13` 是正式版本。非法标签或版本不一致会失败，不创建公开 Release。

## 准备版本并推送标签

1. 更新 `pyproject.toml` 、`src/grea/__init__.py` 以及 `skill/version.json` 中的版本；标签 `v2026.10.14-rc1` 对应 Python 版本 `2026.10.14rc1`，正式标签对应 `2026.10.13`。
2. 运行 `uv lock` 更新根包版本，核对没有意外依赖升级，提交并合入待发布代码。
3. 标签指向包含本工作流的发布提交。核对版本后执行：

```sh
git tag -a v2026.10.14-rc1 -m "grea v2026.10.14-rc1"
git push origin main v2026.10.14-rc1
```

示例版本须替换为实际目标，不重复使用或移动已发布标签。推送代码不触发 Release，推送版本标签才触发。工作流使用 GitHub 自动提供的令牌，不需要个人访问令牌；发布 job 才授予 `contents: write`，构建 job 只读。

## 自动执行内容

1. 从标签提交安装锁定依赖，检查公开内容、生成契约、技能链接，并运行完整测试（包含 CLI/MCP）。
2. 核对标签、Python 元数据、运行时版本与锁文件一致，从提交对象制作 ZIP；不读取私人库存或未跟踪文件。中文文件名与执行权限写入压缩包。
3. 生成完整 `grea-<tag>.zip`、独立 `grea-skill-<tag>.zip`、`release-manifest.json`、`SHA256SUMS`。时间来自源码提交，重跑相同提交可比较相同制品。清单只记录公开身份和验证门槛，不放机器路径、秘密或原始日志。
4. 逐文件比较 ZIP 与提交内容，解压到新的临时目录，重新安装依赖并运行测试和 CLI；Skill 单独解压，检查内容身份与本地链接闭包。成功后把制品交给发布 job。
5. 核对远端标签仍指向本次提交，创建草稿，上传四个附件，再下载逐字节校验；全部通过后公开。rc 使用 prerelease，且不作为最新稳定版；正式版由 GitHub 的版本排序选择 Latest。

构建不等于 Windows、Unity Editor 或游戏实测。现有平台限制仍适用。Release 正文列安装方式、版本和限制；工作流执行记录提供当次测试证据。

## 失败与重跑

同标签运行串行执行，不取消正在发布的作业。测试失败不会进入发布；上传中断保留草稿。重新运行时只补齐缺失附件，已有附件必须与本次制品一致。

已发布版本仅在元数据和附件完全一致时视为成功重跑；内容不同、远端标签移动、附件未知或不完整时停止。不会用 `--clobber` 覆盖，也不会自动删除已发布版本。网络超时后先检查现有草稿/附件，再重跑原工作流。

## 手动验证，不发布

在 Actions → Release → Run workflow 填入与所选分支代码版本匹配的 `tag`，或运行：

```sh
gh workflow run release.yml --ref main -f tag=v2026.10.13-rc1
```

手动入口执行全部构建和解压验证，保留 14 天 CI 制品；发布 job 跳过，不创建标签或 Release。它允许测试当前分支，即使同名旧标签已经指向其他提交，因此不能当作该旧标签的新发布。

本地辅助命令要求 Python 3.11+，仓库已提交且工作树干净：

```sh
python3 scripts/release.py prepare --tag v2026.10.14-rc1 --out dist/release --require-tag
python3 scripts/release.py verify --tag v2026.10.14-rc1 --out dist/release --extract /tmp/grea-release-check --extract-skill /tmp/grea-skill-check
```

输出和解压目录必须尚不存在。`prepare`/`verify` 不替代工作流测试，也不发布；`publish` 是写入 GitHub 的维护入口，日常交给标签工作流执行。

Skill 的独立构建入口、明确版本与安装限制见 [Skill 构建与安装](Skill构建与安装.md)。两个 ZIP 都参与 SHA256SUMS 和上传后回读。
