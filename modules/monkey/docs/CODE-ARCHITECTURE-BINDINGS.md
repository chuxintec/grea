# Native View Prefab authoring plans

`monkey.code_architecture_bindings.build_prefab_authoring_plan(...)` creates a
source-pinned plan for attaching a generated Presentation `MonoBehaviour` to a
native Unity Prefab and assigning only explicitly evidenced serialized
references. It is read-only: it does not open Unity, mutate Prefabs, create
`.meta` files, or claim compilation or serialization success.

The function consumes the global architecture plan, owning module receipt,
`monkey-code-architecture-asset-context/1`, the exact View/source bytes, and
candidate Prefab bytes. Shared source-manifest and architecture hashes must
agree. A candidate Script `.meta` is accepted only when the module receipt
owns its exact bytes; otherwise the deterministic Script GUID remains pending.

Source property extraction recognizes explicit Cocos decorator expressions
such as `@property(cc.Node)` from a pinned source-unit span. Aliased types stay
unresolved. C# fields are read from `[SerializeField]` declarations and checked
against the architecture class record. An exact same-name source/C# field can
be paired directly; differing names require a caller-provided, case-sensitive
mapping. No case folding or approximate name search is used.

For a Cocos 2.4.15 packed Prefab, pass the original pack and project config
bytes with their SHA-256 pins and the exact pack ID. The module resolves the
source asset UUID through the config UUID table and pack membership, then
decodes only that section through the existing `cocos-2.4-compiled-v1` reader.
It extracts the root script component's literal serialized values and the
complete source node child-index tree. Pass the saved Editor readback bytes and
SHA-256 pin too; the plan checks its exact Prefab path/GUID, saved/reloaded
status, source node identities, hierarchy names, and native component type
lists. Source and candidate YAML trees must have matching ordered child paths
and names before a node reference is considered resolved.

A proven source reference and candidate node path are retained when the
corresponding native component type is absent, but no assignment operation is
emitted. Exact native field types are required, except for the small declared
`TMPro.TMP_Text` base-type map covering `TMPro.TextMeshProUGUI` and
`TMPro.TextMeshPro`. Other type differences remain unresolved. Asset assignments
require a pinned native target path, GUID, and hash. Preview readback fileIDs
are ignored; they never stand in for a source Prefab localID.

The output distinguishes root component attachment from field bindings. A root
component can be identified from the exact code region, source component ID,
source root ID, owned Prefab GUID, and root readback name. The plan still waits
for the candidate Script GUID and `MonoScript.GetClass()` after whole-project
compilation. Source UUIDs remain authoring metadata only; runtime code must
use typed serialized Unity references.

## CardSeasonMainWindow evidence

The latest static plan and receipt are in
`.private/v060-architecture-first-20261027/NativeBindingPlan04/`; earlier
`NativeBindingPlan01` through `NativeBindingPlan03` receipts remain unchanged. The
plan pins the `CardSeasonMainWindow` module C# SHA-256
`[private fingerprint omitted]`, the
source-unit span SHA-256
`[private fingerprint omitted]`, and
native Prefab path/GUID/SHA-256
`Assets/Game/Content/Prefabs/UI/CardSeason/Window/CardSeasonMainWindow.prefab`,
`d6ef85274b0c4469da5fc5509119877b`,
`[private fingerprint omitted]`.

The original asset UUID maps through the project config to UUID index `3137`
and packed section `2640` in pack `0621940b9`. The section decodes to the
source `cc.Prefab` with 62 serialized objects, including 42 reachable
`cc.Node`s and component
`gameAsset:[private identifier]#1/components/1`. Its 16
decorated properties have actual serialized `__id__` references. The full
42-node source hierarchy matches candidate Prefab YAML child-index paths and
names, and prior saved/reloaded Editor readback confirms the same 42 node
identities. Each planned path step records source `cc.Node` and candidate
`UnityEngine.RectTransform` types for the future Editor resolver.

All 12 explicit source-to-C# field-name mappings have decoded references and
candidate node paths. Ten target types are compatible with the current saved
readback; two require a later C# or candidate-component correction:

- `progressBar` is source `cc.ProgressBar` at
  `CardSeasonMainWindow/Mid/CardSeasonRewardArea/bg_progress/progressBar`.
  The C# field is `UnityEngine.UI.Slider`, while readback reports only
  `UnityEngine.UI.Image` there. Source method `renderProgress` reads and writes
  `.progress` and animates the value with `cc.tween`; no assignment is planned.
- `label_progress` is source `cc.Label` at
  `CardSeasonMainWindow/Mid/CardSeasonRewardArea/bg_progress/label_progress`.
  The C# field is `TMPro.TMP_Text`; readback reports
  `TMPro.TextMeshProUGUI`, a supported derived type. Source method
  `renderProgress` writes `.string`.
- `label_title` is source `cc.Label` at
  `CardSeasonMainWindow/Mid/Title/TGame_title/title`. Its C# field is
  `TMPro.TMP_Text`, but readback reports only `UnityEngine.RectTransform` on
  that node. Source method `onData` writes `.string` and passes the label to
  `ApplyTitleOutlineColor`; no assignment is planned.

The remaining nine mapped fields have compatible saved native component types.
Four decorated source fields lack a matching C# serialized field:
`finalRewards` targets a custom item-list component on `ItemList`, `label_time`
targets a custom clock component on `leftTime`, and `spine_top` and
`spine_effect` target `sp.Skeleton` components. Their source references and
paths remain in the plan as source-only unresolved properties.

The plan currently emits zero Prefab write operations. The candidate View has
no `.cs.meta`/Script GUID or compiled `MonoScript` type, and two mapped target
component types are missing. This is a static authoring plan, not an Editor
binding or serialization claim.

Run the focused tests with:

```sh
PYTHONPATH=src .venv/bin/python -m unittest tests.test_code_architecture_bindings
```
