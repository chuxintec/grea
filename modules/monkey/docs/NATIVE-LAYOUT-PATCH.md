# 原生布局增量修复

本地开发分支已完成本次冻结 dev3 的 NativeFlow 子集替换，使用 Unity uGUI 组件。冻结 dev3 源工程、历史验收和分发包不改；新候选实际完成50资产/189组件身份及6组代表原生探针，14资产复用先前精确成功证据，36资产本轮新增保存。问卷文本限制单列，Player/业务/像素保真仍not_run。

已审计的实例为 48 个独立源 Prefab／63 个布局，另维护两个汇总 Prefab，共 50 个资产／189 个组件槽。58 个内容网格使用原生 GridLayoutGroup，4 个固定单元格网格使用原生 GridLayoutGroup，1 个异尺寸、固定宽度单行使用 HorizontalLayoutGroup。ContentSizeFitter 复用原对象，避免重复组件。禁用布局继续禁用并保留原有 RectTransform；两个零尺寸模板使用确切嵌套 Prefab 根尺寸，不猜尺寸或启用时机。

内容网格的固定 cell size 来自本次已核等尺寸项目或确切模板；不宣称支持未见的动态异尺寸换行、缩放参与或固定行列。缺少可证明映射的输入保留原几何并给出 review 诊断。`_N$cellSize` 与 `_cellSize` 均读取，冲突拒绝，不能静默用 40×40 代替源尺寸。

`IntrinsicGridLayoutGroup` 直接继承 Unity GridLayoutGroup，仅将布局优先级提高到背景 Image 之上，并让空内容的垂直尺寸收缩至 padding；不实现子节点排列、换行或源布局递推。既有 Linear 帮助组件和共享变更通知基类保留，不把本次 Flow 修复称为它们已迁移。当前精确原生验证环境为 Unity 6000.6.2f1／UGUI 2.6.0。

```sh
bin/monkey native-layout-audit --candidate "$MONKEY_FROZEN" \
  --expected-manifest "$MONKEY_BASE_SHA" --out "$MONKEY_AUDIT"
bin/monkey native-layout-prepare --audit "$MONKEY_AUDIT" --out "$MONKEY_PREPARED"
bin/monkey native-layout-patch --preparation "$MONKEY_PREPARED" \
  --editor "$MONKEY_EDITOR" --budget-seconds 900 \
  --deadline-utc "$MONKEY_INNER_UTC" --window-end-utc "$MONKEY_OUTER_UTC" \
  --out "$MONKEY_EXECUTION_PLAN"
```

第三步默认仅规划。真实执行需新的独立窗口、明确授权和 `--execute`，使用新的执行输出目录；方法至多 900 秒，外窗至多 30 分钟，保留两分钟外部收尾时间。真实启动参数为 batchmode+nographics。候选以 APFS clone-on-write 建立独立 inode，复用暖 Library，不用硬链接回写冻结源。编译前移除精确已审计的旧 Flow 脚本；Editor 只移除这些槽位，不能批量清除其他 Missing Script。

已有退出的 partial 层可在 prepare 传 `--previous-execution`：仅接受同一审计／冻结源、原执行计划和读回、逐资产当前 SHA 全部匹配的已保存成功项。独立候选承接这些资产和原证据，只处理剩余资产，不重新保存已验项；必要新探针在临时加载内容上运行。公共映射代码变化时拒绝直接复用几何证据。旧失败层始终保留。

在本桌面环境，正常原生执行经 `exec_command(require_escalated)` 审批；普通沙盒可能阻止已有 Unity 许可证服务的数据库／XPC 初始化。启动失败不证明账户许可证无效。不在代码中自提权、修改许可或绕审批；审批拒绝、首个新的原生失败均保存现场并停止。失败层不得同窗冷重试，新的尝试另备候选和窗口。

仅当进程退出、精确绑定的 native readback 完成且冻结源未变时，才可执行：

```sh
bin/monkey native-layout-finish --execution "$MONKEY_SUCCESSFUL_EXECUTION" \
  --out "$MONKEY_DELTA"
```

finish 核对全部其他序列化对象的类型／脚本／所属 GameObject／local ID，输出 48 项处置、50 资产增量和旧布局组件到新组件的实际 GUID／fileID 映射。真实游戏采用前须检查旧哈希、人工修改及全部旧脚本引用；冲突需要合并，引用未闭合不得删脚本。本工具不写入游戏工程。原代码和署名／许可证保留在 SourceRecovery/RetiredLayout 和冻结历史，不作法律结论。

实际强制布局更新是 Editor 层证据；Player、完整业务和像素保真仍分别验收。原始失败日志、来源限制和旧读回保留。

问卷原有 Label 未转换时，探针只改变确切源节点对应的现有子 Rect 高度并检查父布局／恢复，不添加替代 Label；文本动态明确为 not_run，并写入机器读回 limitations。

可用 `native-layout-bundle --delta "$MONKEY_DELTA" --out "$MONKEY_BUNDLE"` 生成本地ZIP和adoption-manifest.json，仅携带必要Prefab、运行时适配、原始署名及身份/范围证据；逐项带旧/新哈希与meta GUID保护，不自动应用到游戏。
