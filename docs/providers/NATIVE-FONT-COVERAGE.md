# Saved native font coverage boundary

`monkey.native_font_contract.audit_saved_font_coverage` converts a saved Unity `system-fonts.json` readback and the selected native file inventory into a JSON-ready `monkey-native-font-coverage/1` manifest section. It reads only `fonts`, `labelBindings`, and `nativeFiles`; it does not parse arbitrary Unity YAML or modify the candidate.

```python
from monkey.native_font_contract import audit_saved_font_coverage

font_contract = audit_saved_font_coverage(
    system_font_readback,
    selected_native_files,
    expected_target_os="macOS",
    selected_asset_ids=selected_font_asset_ids,
    required_text_by_label_id=consumer_text_by_label_id,
    producer_contract=font_binding_plan,
)
```

`selected_native_files` must contain the actual frozen candidate's `path` and `sha256` entries. The function joins on the exact saved `assetPath`, uses `assetGuid` from Unity's saved font readback and never invents either identity. Hashes absent from the selected file inventory remain null and set `identityComplete=false`. The caller should store the returned object in the selection manifest as `nativeFontCoverageContract`.

## What the result means

- `staticCoverage.bounded` lists only scalars in the saved TMP lookup readback. `characterTableUnicode` alone is not substituted for lookup evidence. Per-label coverage is `covered` or `missing` only when all bound faces have static lookup evidence.
- `DynamicOS` remains `unknown` for dynamic coverage even when its current atlas has characters. Such labels carry `needConsumer: ["explicitdynamictextcheck"]`. Optional `required_text_by_label_id` records the consumer's actual runtime text requirement; it does not establish that the target runtime rendered it.
- A DynamicOS font with `sourceFontFilePresent=false` and `internalDynamicOS=true` is described as using a platform system face. A `sourceFontFile` path such as `systemArial.ttf` is preserved as readback metadata; it is not treated as bundled font bytes or a portable font identity.
- Target OS mismatch is reported as `unsupported`, with a diagnostic and consumer action. Missing fields remain unknown, not passing.
- A missing static scalar requests `fontbinding`. This contract does not choose or replace a project font; project wiring remains explicit.

The Unity producer's saved readback is `Analysis/Readback/system-fonts.json`. `UnitySystemFonts.Readback.fonts[]` provides saved asset ID/path/GUID, population mode, required scalars and `savedNativeGlyphState`; `labelBindings[]` preserves the exact label and primary/fallback binding identities. Its `targetOS` is the saved font resolution environment, and `targetPlatform` reflects the Editor readback environment; neither proves the Player target. The runtime system-face resolution constraint originates in `prefab_system_fonts.prepare`'s `systemFonts.runtimePlatformConstraint`. Pass that producer binding plan through `producer_contract` when the saved readback does not carry the field. If absent, the result reports platform constraint/status as unknown rather than copying an assumption into the receipt.

This boundary is an adoption aid. It is not dynamic-text acceptance, a system-font portability guarantee, or proof that the named family resolves identically on another operating system.
