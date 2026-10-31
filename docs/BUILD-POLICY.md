# Explicit macOS build mode

`build.macos` accepts optional `development: true` or `false`. Omitting it retains the previous non-development mode. Strings, integers and null are rejected. The choice is part of the immutable plan and its digest.

The native backend selects only `BuildOptions.Development` or `BuildOptions.None`, reads the actual flag from `BuildReport.summary.options`, and rejects a mismatch. Python independently compares `developmentBuild` against the frozen request. The artifact manifest records `development` beside the existing source and plan hashes. Source drift remains a build failure.

Development enables Unity's development behavior, including `Debug.isDebugBuild`. It does not establish account, connection, profile or saved-data isolation. Those are separate explicit player-launch inputs and consumer checks.

`tmpFontPolicy` is optional and closed:

```json
{"schemaVersion":1,"fonts":[{"path":"Assets/Fonts/Example.asset","guid":"11111111111111111111111111111111","sourceSha256":"<64 lowercase hex>","metaSha256":"<64 lowercase hex>","normalizeDynamicAtlas":true}]}
```

Every listed font is protected. Only explicitly normalized dynamic fonts call the public TMP `ClearFontAssetData(true)` API and scoped `SaveAssetIfDirty`. Normalization requires a source font and font-owned atlas subassets; an unnormalized dynamic multi-atlas font is refused. Atlas slots must remain non-null before/after the build. The save guard filters only the listed font paths; there is no global save or arbitrary project hook.

Planning binds exact font/meta bytes and GUIDs. Apply persists verified before-images outside Assets before starting the Editor. `font-checkpoint.json` records write intent, observed postimages and source/build/restored hashes. The artifact manifest carries `fontInputs` and `fontSourcesRestored`; full project source identity must still match after restoration. Source restoration does not establish glyph coverage or player visual correctness.

Normal completion or a build exception restores exact font/meta before-images through the native helper, reimports, and checks bytes. Unexpected postimage changes are refused, preserving later edits. A native interruption keeps the transaction `recovery-required`; it never certifies the artifact. Public `unity recover` can restore the exact font write set only after the owned process has exited, the project is unlocked, all backups match, unrelated source is unchanged, and current bytes equal original or conclusive observed postimages. An in-progress mutation without a conclusive checkpoint is deliberately refused; inspection is required. Recovery does not certify a partially built player.

Runtime profile/connection parameters remain a separate launch contract. There is no arbitrary execute method, numeric build-option mask or game-specific font path.
