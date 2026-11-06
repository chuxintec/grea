# Native static-font completion stage

`monkey.native_font_stage.stage` combines a hash-frozen Unity selection with a prepared static-font completion into a separate Unity project. It preserves source asset bytes and `.meta` GUIDs, adds the pinned SDF inputs under `Analysis/NativeFontCompletion/Inputs/<fontkey>/`, and writes an out-of-project request for a later native run. The source manifest contract (selection scope, source readback pin, runtime update, dependencies, namespace, and other fields) is retained without its original file array. It does not launch Unity or write into the selected project.

```python
from monkey.native_font_stage import stage

prepared = stage(
    candidate=selected_candidate,
    expected_manifest=selected_manifest_sha256,
    completion_dir=font_completion_directory,
    expected_completion=font_completion_receipt_sha256,
    out=new_stage_directory,
)
```

The new project is in `prepared["projectRoot"]`; the request is at `prepared["requestPath"]`. `launchArguments` includes both the request path and its SHA-256. The native Editor method is `Monkey.NativeEditor.UnityStaticFontCompletion.Run`. The request pins the stage manifest, selected static font path/GUID/hash, primary DynamicOS assets, binding, staged portable receipt, CoreText corpus-resolution receipt, and consumer text strings.

The stage emits a font-only `UnitySystemFonts.cs` helper with `MONKEY_STATIC_FONT_COMPLETION_ONLY` defined. Its manifest records the unchanged template hash, emitted hash, and profile. This compile profile excludes unrelated source-outline conversion code whose dependencies are outside the selected prefab closure; the ordinary conversion source remains unchanged and keeps its default full behavior. The stage adds built-in `com.unity.modules.jsonserialize` and `com.unity.modules.imageconversion` version `1.0.0` only when they are absent, for the temporary Editor helper. It preserves the existing uGUI version and records those Editor-only package changes; finalization restores the source package manifest and lock from pinned evidence. It does not copy the legacy GameFont asset.

After the Editor writes `Analysis/NativeFontCompletion/native-readback.json`, use:

```python
from monkey.native_font_stage import finish_stage

frozen = finish_stage(
    project=prepared["projectRoot"],
    expected_stage_manifest_sha256=prepared["stageManifestSha256"],
    native_readback_path=readback_path,
    expected_native_readback_sha256=readback_sha256,
    out=new_frozen_candidate_directory,
)
```

Finalization requires a real passing native readback; a prepared or `not_run` readback cannot produce a frozen candidate. It checks font, atlas, and material GUID/local-ID preservation, primary DynamicOS immutability, and the selected static-font hash. The final candidate retains every source-selection file (updating only the selected static font asset), font evidence, and the native readback. Temporary Editor helper scripts and only their newly generated directory metadata are excluded; pre-existing source metadata is retained. The source adoption contract and dependency edges are carried forward and each edge endpoint is checked against the final file inventory. `finalization-report.json` records each retained or excluded staged path with its hash, classification, and `stageRole`. Player rendering remains unverified.
