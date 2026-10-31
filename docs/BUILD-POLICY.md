# Explicit macOS build mode

`build.macos` accepts optional `development: true` or `false`. Omitting it retains the previous non-development mode. Strings, integers and null are rejected. The choice is part of the immutable plan and its digest.

The native backend selects only `BuildOptions.Development` or `BuildOptions.None`, reads the actual flag from `BuildReport.summary.options`, and rejects a mismatch. Python independently compares `developmentBuild` against the frozen request. The artifact manifest records `development` beside the existing source and plan hashes. Source drift remains a build failure.

Development enables Unity's development behavior, including `Debug.isDebugBuild`. It does not establish account, connection, profile or saved-data isolation. Those are separate explicit player-launch inputs and consumer checks.

`tmpFontPolicy` is optional and closed:

```json
{"schemaVersion":1,"fonts":[{"path":"Assets/Fonts/Example.asset","guid":"11111111111111111111111111111111","sourceSha256":"<64 lowercase hex>","metaSha256":"<64 lowercase hex>","normalizeDynamicAtlas":true}]}
```

Every listed font is protected. Only explicitly normalized dynamic fonts call the public TMP `ClearFontAssetData(true)` API and scoped `SaveAssetIfDirty`. Normalization requires a source font and font-owned atlas subassets; an unnormalized dynamic multi-atlas font is refused. Atlas slots must remain non-null before/after the build. The save guard filters only the listed font paths; there is no global save or arbitrary project hook.

Planning binds exact font/meta bytes and GUIDs. Apply persists verified before-images outside Assets before starting the Editor. `font-checkpoint.json` records write intent, observed postimages and source/build/restored hashes. The native report carries only `fontSourcesRestoredInProcess`. After the owned Editor exits, the parent verifies the complete source set and adds `fontSourcesRestored: true`, `sourceRestorationVerifiedBy: "parent-after-editor-exit"` and per-font post-exit source/meta hashes. Only that parent-certified report enters the artifact manifest. Unknown shutdown mutations fail certification; they are not silently claimed as owned writes. Source restoration does not establish glyph coverage or player visual correctness.

Normal completion or a build exception restores exact font/meta before-images through the native helper and checks bytes. The font save guard remains active until process exit. The helper clears loaded font/atlas dirty state and disables automatic refresh before copying original bytes; it does not reimport restored bytes and thereby re-dirty the atlas during shutdown. Unexpected postimage changes are refused, preserving later edits. A native interruption keeps the transaction `recovery-required`; it never certifies the artifact. Public `unity recover` can restore the exact font write set only after the owned process has exited, the project is unlocked, all backups match, unrelated source is unchanged, and current bytes equal original or conclusive observed postimages. An in-progress mutation without a conclusive checkpoint is deliberately refused; inspection is required. Recovery does not certify a partially built player.

Runtime profile/connection parameters remain a separate launch contract. There is no arbitrary execute method, numeric build-option mask or game-specific font path.


## Explicit reviewed recovery of fixed fix11 shutdown drift

`unity recover-font-source --transaction <old-transaction> --expected-plan <sha256> --review <review.json> --out <fresh-independent-receipt>` is separate from ordinary `unity recover`. The review follows [the versioned schema](schemas/build-font-post-exit-recovery-1.schema.json), binds the exact old plan/implementation, original post-exit journal and process files, and lists every approved file's original and observed post-exit hashes. `reviewReference` records the caller's review source; it does not create authorization.

This exception accepts only fixed fix11 implementation `44a1280aa75d7b720fa0bdfada800441e09dc76c95911ed1b00e2993725f766c` and a recorded `BUILD_SOURCE_DRIFT` after a successful owned Editor exit. Only font/meta paths declared by that original plan are eligible. Before any source writes, the project must be closed and locked, all nonselected sources must match the original plan, every before-image must match, and current bytes must equal the explicit approved after-image or an already restored before-image. Different later edits, damaged backups, changed evidence or an arbitrary old implementation are refused.

The operation atomically copies only verified before-images and then checks the complete source inventory. It starts no Editor, leaves the original transaction evidence intact, and writes a separate receipt with `artifactCertified: false`. Restoring source does not validate the previous built App. A fresh build is required for a new certified artifact.
