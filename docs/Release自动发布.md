# 标签触发的 Release 发布

[Release workflow](../.github/workflows/release.yml) 在推送 `v*` 标签时运行。仅接受 `vX.Y.Z` 与 `vX.Y.Z-rcN`（N 从 1 开始）；例如 `v2026.10.16-rc1` 是预发行，`v2026.10.13` 是正式版本。非法标签或版本不一致会失败，不创建公开 Release。

## 准备版本并推送标签

1. 更新 `pyproject.toml` 、`src/grea/__init__.py` `plugin/version.json`、`plugin/.codex-plugin/plugin.json` 与 `plugin/.claude-plugin/plugin.json` 中的版本；标签 `v2026.10.16-rc1` 对应 Python 版本 `2026.10.16rc1`，正式标签对应 `2026.10.13`。
2. 运行 `uv lock` 更新根包版本，核对没有意外依赖升级，提交并合入待发布代码。
3. 标签指向包含本工作流的发布提交。核对版本后执行：

```sh
git tag -a v2026.10.16-rc1 -m "grea v2026.10.16-rc1"
git push origin main v2026.10.16-rc1
```

示例版本须替换为实际目标，不重复使用或移动已发布标签。推送代码不触发 Release，推送版本标签才触发。工作流使用 GitHub 自动提供的令牌，不需要个人访问令牌；发布 job 才授予 `contents: write`，构建 job 只读。

## 自动执行内容

1. 从标签提交安装锁定依赖，检查公开内容、生成契约、技能链接，并运行完整测试（包含 CLI/MCP）。
2. 核对标签、Python 元数据、运行时版本与锁文件一致，从提交对象制作 ZIP；不读取私人库存或未跟踪文件。中文文件名与执行权限写入压缩包。
3. 生成完整 `grea-<tag>.zip`、独立文档 `grea-skill-<tag>.zip`、`release-manifest.json`、`SHA256SUMS`。另在原生 macOS arm64 job 构建 `grea-plugin-macos-arm64.zip`，包含固定解释器、依赖、技能与 MCP；重复构建并比较全部字节。
4. 源码包解压后重新安装并测试；文档包校验独立链接。完整插件解包、移动到含空格中文的新目录，在禁止联网、源码读取和安装目录写入的环境中执行核心 MCP 与兼容入口验收，产生 `plugin-acceptance.json`。
5. assemble job 下载两个构建 job 的制品，按同一提交、版本、源码逐文件身份及隔离验收哈希合并；拒绝工作树预览和不匹配的报告。生成包含三个 ZIP、`plugin-acceptance-macos-arm64.json`、身份清单与校验文件的完整附件集合。
6. 核对远端标签仍指向本次提交，创建草稿，上传全部六个附件，再下载逐字节校验；全部通过后公开。rc 使用 prerelease，且不作为最新稳定版；正式版由 GitHub 的版本排序选择 Latest。时间来自源码提交，清单不放主机路径、秘密或原始日志。

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
python3 scripts/release.py prepare --tag v2026.10.16-rc1 --out dist/release --require-tag
python3 scripts/release.py verify --tag v2026.10.16-rc1 --out dist/release --extract /tmp/grea-release-check --extract-skill /tmp/grea-skill-check
# 以下三步在 macOS arm64；不创建标签，不发布。
python3 scripts/build_plugin.py --tag v2026.10.16-rc1 --out dist/plugin
python3 scripts/verify_plugin.py --bundle dist/plugin/grea-plugin-macos-arm64.zip --report dist/plugin/plugin-acceptance.json
python3 scripts/release.py attach-plugin --tag v2026.10.16-rc1 --out dist/release --plugin-dir dist/plugin
```

输出和解压目录必须尚不存在。`prepare`/`verify` 不替代工作流测试，也不发布；`publish` 是写入 GitHub 的维护入口，日常交给标签工作流执行。

三个制品的安装与边界见 [Skill 构建与安装](Skill构建与安装.md)。它们均参与 SHA256SUMS 和上传回读。原生 Codex/Claude 客户端安装发现另由 `scripts/verify_plugin_clients.py` 验收；CI 的 stdio 测试不声称运行了这两个原生客户端。`workflow_dispatch` 也构建并合并插件，但跳过发布。
