# Unity 字段语义校验与身份保护（本地候选 0.2.0.dev2）

此修复包独立于已发布、不可变的 `v0.2.0.dev1`。两个游戏继续固定旧包；本地候选需明确采用后再切换。本工具只读源文件和 Unity 6 目标工程，输出离线计划，不写 Scene/Prefab，不启动 Editor，不恢复方法体。

## 读取层变化

`inspect-unity` 的 MonoBehaviour 严格读取完成后，再用独立的原生头部读取核对 `m_Script` / `m_GameObject`，按可信 TypeTree 检查字段、数组、PPtr、整数范围和有限浮点数。对齐错误导致的完整读取、`string` 节点带 `Array/data string` 的错误形状都不能成为成功数据；失败对象无 `data` / 引用载荷。嵌入及精确借取 schema 的摘要现在保留布局 flags/version/byteSize，schema ID 会随新增布局元数据变化，旧 ID 不应用作跨版本缓存键。

通过时 `semanticValidation` 明确标记头部与形状已验证、全字段值尚未交叉验证、`writable=false`。有限检查不会证明业务、动画、Player 或视觉一致。未知结构保持未解析，不猜字段，也不默认运行 metadata 生成器。

库调用：`monkey.unity_semantics.validate_component(schema, data, independent_header)`。输入为原生 UnityPy 字典或 monkey 的 typed PPtr 字典。支持明确 primitive、嵌套 struct、vector/具名数组；标量字符串必须是字符数组，不能根据空值猜成字符串数组。该函数不自行建立 schema 来源，调用方须固定准确版本、schema 及原始字节。

## 离线计划命令

```sh
monkey unity-field-plan \
  --candidate candidate.json \
  --trusted trusted.json --trusted-sha256 TRUSTED_SHA256 \
  --bindings bindings.json \
  --inventory target-inventory.json --inventory-sha256 INVENTORY_SHA256 \
  --source data.unity3d --metadata global-metadata.dat \
  --target-root /absolute/path/to/UnityProject \
  --out /absolute/path/to/fresh-plan
```

成功返回0，输出 `validation.json` 和 `field-plan.json`。任一所选对象失败，整组返回1，只留诊断，不生成任何字段计划。身份/输入哈希等前置检查失败时不建立输出目录。路径必须是显式普通文件/目录，不接受符号链接或覆盖既有输出。

四份 JSON 均使用 `schemaVersion: 1`。candidate/trusted/bindings 的 `source` 必须完全相同：

```json
{"sha256":"container SHA256", "metadataSha256":"metadata SHA256", "unityVersion":"2021.3.30f1"}
```

实际 source、metadata 字节均由命令重新核对。可信快照及目标 inventory 另需命令行固定哈希；不能把 candidate 自己复制一份当作独立可信证据。CLI 校验调用方冻结的声明和对照，并不从原容器独立重建全部 TypeTree 或重新反编译 DLL。

candidate/trusted 的 `files` 是精确序列化文件名与外部表，外部表依次对应 fileID 1..N：

```json
[{"name":"level0", "externals":["sharedassets0.assets"]},
 {"name":"sharedassets0.assets", "externals":[]}]
```

`objects` 的所选 MonoBehaviour 包含：

- `file` 为该序列化文件名；`pathId` 为非零、带符号64位十进制字符串；`rawSha256` 固定原始对象字节。
- `typeIdentity`：`assembly`、完整命名空间 `type`、冻结声明文件的 `declarationSha256`、非零32位十六进制 `scriptId` / `typeHash`。它们与可信快照全部一致才通过。
- `schema`：`{name,type,children:[...]}`，保留已取得的 `metaFlag/version/byteSize` 等布局字段。完整 schema 字典与可信对照完全相同；未知布局不可猜补。
- `data`：原生 UnityPy 值或 monkey typed PPtr 值；须逐字段与独立可信值一致，空数组/空字符串也按 schema 区分。
- trusted 还含独立头部 `header`（`m_Script`、`m_GameObject`）及 `evidence: {kind: embedded|exact-frozen-bundle, sha256: 固定来源证据SHA}`。作为引用绑定来源的其他对象至少保留 file/pathId/rawSha256。

可信来源应是独立的原嵌入/精确借取 schema 解析及原生头部，而不是曾撤回的 `check_read` 成功标记。现有游戏报告没有完整这些字段时，由游戏 Tools 的适配步骤补齐有据身份；缺失的部分停在诊断，不让 monkey 推断。

`bindings.objects` 每项为 `{source:{file,pathId,rawSha256}, target:TARGET}`；`target-inventory.objects` 是冻结 Unity 对象身份清单，`unityVersion` 为精确 `6000.*` 版本。TARGET 示例：

```json
{"assetPath":"Assets/Scenes/Main.unity", "assetGuid":"32 lowercase hex",
 "assetSha256":"scene SHA256", "localId":"123456", "type":"Game.Label",
 "hierarchy":[{"name":"Root","ordinal":0},{"name":"SameName","ordinal":1}]}
```

层级是逐段名字和同名兄弟序号，不拼接 `/` 或 `#`；名字本身含这些字符仍不产生歧义。定位以 `assetGuid/localId` 为准，并要求 binding 与 inventory 全字段一致、来源对象及目标对象分别唯一。资产 SHA、`.meta` GUID、ForceText YAML local ID 及 ProjectVersion 会从目标工程只读核对。二进制 Scene/Prefab 暂不支持本入口，不能通过名字降级定位。

业务字段中的非空 PPtr 必须按精确源文件/外部表/pathID 找到对应 binding；未映射引用阻止整组计划。空引用转为 null，已映射引用输出 `UnityObjectReference` 及完整目标身份；大整数使用 `{$type: integer, decimal: "..."}` 保持精度。工具不会把原 PPtr 数字直接写入目标 YAML。

游戏侧执行器采用计划时，须再次检查 targetInventorySha256、源身份、目标 assetSha/GUID/localId、目标组件类型及字段类型，按现有受控流程 apply/save/reload。离线计划成功与 Editor 成功分开报告。两个游戏的现有 writer 接入该 DTO 是后续游戏集成，不因安装候选而自动替换。

## 本轮证据与限制

- 向样例项目 schema05：106严格读取完成，其中70与既有独立字段/引用对照一致；独立36没有同等全字段证据。本工具只将70记为有完整对照，不扩写106业务成功。
- 直接重哈希70份原对象并独立读取其原生头部：round01阻止70/70；round03、04各阻止2/70；round05通过70/70。原错误报告保持原件。
- 使用固定 UnityPy 1.25.3、仅1个已冻结借取 Bundle 的真实读取代表：17个借取对象均通过新增头部/形状检查，写回状态仍false。
- 合成负例覆盖错位头指针、空字符串数组、字段/原对象/metadata/type/layout漂移、PPtr形状/缺映射、重名层级缺精确ID、错误兄弟序号、重复身份及目标资源漂移。没有新 Editor、全量 Bundle 重导、游戏写入或新发布。

私有原字节、具体路径/对象和完整回执只在 `.private/game-adoption-fixes-01/`，不会打入分发包。
