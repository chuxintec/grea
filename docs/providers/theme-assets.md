# 主题资源映射与有限UI/UE开发（开发候选）

本地开发分支能力，基于已发布v2026.10.19继续开发；未进入该冻结标签、不代表已发布或已全局安装。`theme_assets` 首版只处理既有单Sprite PNG，保持画布与meta。Python仅校验、预览、生成全新增量包，绝不改Unity工程；Editor伴随脚本显式应用/回退。骨骼附件/图集/事件、多Sprite、新尺寸和Prefab布局不自动修改。

## 输入与步骤

传 `--project`（现有工程只读）、`--replacements`（素材输入根）、`--manifest`（新清单）、`--output`（全新输出，须与输入分离）。先通过 `describe-tool` 确认此开发源码中的工具，不使用旧安装缓存。

```sh
./bin/grea legacy theme_assets validate --project /work/Derived --replacements /work/art --manifest /work/map.json --output /work/validation.json
./bin/grea legacy theme_assets preview --project /work/Derived --replacements /work/art --manifest /work/map.json --output /work/new-preview
./bin/grea legacy theme_assets prepare --project /work/Derived --replacements /work/art --manifest /work/map.json --output /work/new-bundle
```

也可通过run-tool传相同argv并指定新run_dir。0表示有限任务完成，2为输入/依赖/IO失败；生成失败保留部分输出，新输出不覆盖。

映射JSON为 `{schema_version:1,change_contract:{...},assets:[...]}`。严格JSON；设计reference及SHA绑定实际设计文件；candidate不冒称批准。合同见 [Schema](../../schemas/change-contract.schema.json)；[完整清单示例](../examples/theme-map.example.json)中的路径/摘要/Importer字段均为占位，必须换成实际输入和Editor观察，不能直接当已验清单。测试 `tests/test_theme_assets.py` 在临时目录生成自有素材。每行字段：

- `alpha_required` 为切出按钮/图标声明透明像素要求；背景可false，完全透明仍拒绝。
- `usage` 固定为 `ui_sprite`，其他用途包括骨骼图集明确不支持；类型仍需Editor实际确认，声明不能隐藏真实依赖。
- `asset`：项目内 `Assets/...png`，`replacement`：替换根内相对PNG；拒绝越界、链接、大小写/Unicode别名、重复目标与不安全文件名。
- `source_sha256`、`replacement_sha256`、`meta_sha256`：本次真实文件摘要；`guid`为既有32位GUID。
- `sprite`：`mode:"single"`、源PNG `width/height`、归一化 `pivot:[x,y]`、实际 `border:[left,bottom,right,top]`、`pixels_per_unit`、`file_id`。这些由工程现有Editor观察取得，不猜造；Python只能验证声明和图片，不能证明Unity引用。

最多256映射、128MiB显式文件总量、64M累计像素、单图20M像素、JSON1MiB。复用 image_alpha_audit 的实际图像检查；全透明、尺寸变化、陈旧摘要拒绝，边缘统计不认证裁切/视觉。预览只是前后联系表，不生成美术或批准设计。

prepare 只收录摘要不同的行，按索引存 before/after PNG，生成 `theme-plan.json` 与 plan_id。既有meta不写入、不改名；相同图像为未变，不能把它计为完成新主题制作。

## Editor应用与回退

仅向已授权、已隔离身份的工程Editor目录加入 `tools/unity/audit/ThemeAssetApply.cs`；它依赖Unity自带Editor API，无需装主题框架。调用既有Editor入口 `Grea.Tools.ThemeAssetApply.Run`，参数：

```text
-greaThemeBundle /work/new-bundle -greaThemeAction apply -greaThemeReport /work/new-apply.json
```

`rollback`使用同一不可变包、新回执。操作者必须已有对应工程写授权；该工具不调度Editor、不授予许可或窗口、不安装插件。

应用要求 `PlayerSettings.productName` 匹配合同新product_id；合同源/新产品与存档namespace必须不同，实际存档隔离仍需产品验证。完整预检所有目标GUID/local fileID、canvas/pivot/九宫格/PPU、meta和before/after摘要后再写。PNG同卷替换后用AssetDatabase同步导入并重新核对。只替换图像字节，不外部修改YAML或meta；保护条件不符即失败，不自动扩范围。

已应用/已回退行可幂等略过。未知第三方改动、meta或几何漂移不得强制覆盖。中途失败回执保留 attempted/verified 行；回退仅处理当前字节明确等于本包before/after的目标，回到原PNG后再次导入验证。进程中断或meta已变需先检查实际状态/备份，不能把旧“成功”回执当当前身份。不保证整个多文件操作原子，不能以素材回退代替玩法/存档回滚。

完成状态只表示图像字节及导入字段检查；真正视觉、按钮状态、布局/导航、骨骼附件/事件、命中/取消、存档与Player证据仍分层。当前Editor实际运行按消费者自己的有界窗口验收，本工具不占用或新建游戏窗口。

## 美术优先的阶段与持续台账

换皮主线顺序为 S1真实选样定风格 → S2 UI/ICON切分、原画与所需角色/怪物/特效Spine成套生产 → S3选样范围100%原功能替换 → S4用户确认样板风格后的全量换皮与Bug修复 → S5最后游戏调优。前四阶段保持原布局、入口和操作；约30%如有约定只用于S5整体页面/流程范围，不是美术替换覆盖率。不为每页增加审批，不把可玩/改色/静态PNG冒称完整美术或Spine。具体执行规范以 [换皮制作](../../plugin/skills/grea-reskin/references/游戏换皮与资源制作.md) 为准。

`change_contract.art_production` 可选新增 `stage`、`ledger:{reference,sha256}`；阶段值依次为 `style_sample`、`art_production`、`sample_replace`、`full_reskin`、`game_tuning`。前四阶段允许维度仅 `visual_style`，S4/S5要求design声明approved，S5要求额外 `reskin_complete:{reference,sha256}` 绑定全量换皮与Bug修复完成回执。这是有限声明约束，不是审批服务或自动验收；既有不带该字段的合同/API继续兼容。没有换皮前置的独立UI/UE任务不强套美术阶段。

各阶段更新**同一份**台账文件及其当前SHA，不复制成阶段台账。台账链接持续维护的界面、角色、怪物、特效、关卡设定；以稳定资源/功能ID关联设计来源和版本、源稿、切片、Spine生产/导出、目标引用与状态。纯文档引用不上传任何媒体、原始提示词或私有附件。

```sh
./bin/grea legacy theme_assets validate-ledger --manifest /work/art-ledger.json --output /work/new-ledger-report.json
```

此动作不需要工程、替换图或Editor。读取1MiB以内JSON，按 [art-ledger Schema](../../schemas/art-ledger.schema.json) 校验后输出 `validated_declared_art_ledger`、选样数量和**声明状态**统计；引用的媒体/设置/证据不打开。输出必须全新，旧文件不覆盖。台账示例见 [自有占位示例](../examples/art-ledger.example.json)：10个示例界面、1角色、2个轮廓/动作差异怪物，**不是某真实项目的已完成选样**；概念角色/怪物/特效的Spine明确pending。

台账字段：

- `selection` 列实际界面、角色、怪物的记录ID；数量按本期明确范围，如10/1/N落实，工具不强迫所有项目采用相同数目。
- `settings` 链接interface/character/monster/effect/level五类持续设定文档，无新机制时引用原设定。
- `records[]`：`id/kind/feature_id/original_resource`，`design_source/design_version`，`source_art[]/slices[]/targets[]`，`state` 为 planned/designed/produced/integrated/verified；verified必须另有evidence引用。稳定ID不可重复，选样必须引用正确类别的现有记录。
- character/monster/effect条目明确 `spine.state` 为not_required/pending/authored/exported/integrated/verified。not_required需真实理由，不等于免除用户所需的Spine；exported及以后需editor_version、runtime_version、skeleton、attachments、animations、events（允许明确空列表）、atlas、textures、exports；integrated需目标引用，verified还需自身evidence。
- 概念图/静态切片加pending或authored骨架不能声明为produced完整资源；无证据不声明verified。字段齐备也只表明声明完整，不能证明实际Spine文件兼容、事件时序、导出/导入或运行通过。

PNG清单引用此台账时，`ledger.reference` 是相对映射JSON所在目录的显式安全文件路径，不能越界/链接；会读取该台账、核验SHA及结构并在输出记录摘要。每条PNG行可增加 `ledger_record`：它必须指向interface/icon记录，且targets包含该PNG路径、没有待处理的Spine；不能用骨骼条目伪装为普通UI PNG。bundle保留这一关联，不自动更新生产状态。清单中的骨骼资料仅用于追溯，**不会因此获得骨骼替换能力**；单Sprite/同画布/meta保护保持原边界。
