# Consumer text corpus font completion

`monkey.native_font_completion.complete_native_font_from_corpus` prepares a new, bounded CoreText static fallback atlas from a hash-pinned runtime text corpus. It takes the selected static font's saved binding, base generation receipt, and base SDF plan as read-only pinned inputs. It retains the same static asset ID/path and exact family/style/PostScript name, variation axes, CoreText font file SHA-256, generator SHA-256, target OS build, and all previously generated glyph metrics and pixels.

```python
from monkey.native_font_completion import complete_native_font_from_corpus

result = complete_native_font_from_corpus(
    corpus_path, expected_corpus_sha256,
    base_binding_path, expected_base_binding_sha256,
    base_generation_receipt_path, expected_base_generation_receipt_sha256,
    base_static_plan_path, expected_base_static_plan_sha256,
    coretext_generator_path, new_output_directory,
    static_font_asset_id="coretext-static-sdf-…",
    watch_files={
        "dynamicArial": {"path": selected_arial_asset, "sha256": expected_arial_sha256},
        "legacyFont": {"path": legacy_font_asset, "sha256": expected_legacy_sha256},
    },
)
```

The output directory must be new. The function resolves the corpus through the requested primary family on the current macOS host. Scalars already in the static atlas are retained; scalars resolved through the exact pinned primary face remain primary; any remaining scalar must resolve through the selected exact static fallback face and matching CoreText font-file hash. Any face, variation, file hash, OS build, generator, or coverage mismatch stops preparation.

The function reruns the pinned generator for the full existing-plus-new glyph set, compares all prior glyph metrics and image tiles, then appends only missing tiles into a copy of the old atlas. It updates a copy of the font binding, writes a generation receipt and consumer-resolution receipt, and validates/stages the result through `prefab_system_fonts.prepare_static_inputs`. The source atlas, source binding, source font assets, Editor project, and installed system fonts are not modified. System-font bytes are not copied or exported.

## Evidence boundary

- `status=prepared` means a new SDF and binding candidate was generated and internally checked. `nativeImport`, `saveReopenReadback`, and `playerGlyphCheck` stay pending until Unity performs those separate operations.
- The per-label source bindings and Arial primary assets are preserved. The consumer corpus does not replace the primary face or add labels to the recovered source project.
- Importing a `DynamicOS` font in Unity can mutate the Editor's serialized font asset when `TryAddCharacters` runs. Native import must happen only in a new isolated candidate. Compare the selected DynamicOS asset, legacy font asset, and all candidate inputs before and after Editor import/save/reopen; this module performs no Editor operation.
- Static atlas completion is bounded to the exact input corpus plus its existing base glyphs. Later runtime, translated, or user-entered text requires another explicit corpus and generated candidate.
- The CoreText face file is inspected in place. Its SHA-256 pins source identity, but its bytes are not distributed; target font licensing and Player font availability remain separate considerations.

## Example

Pin the consumer corpus, source text provider, base font binding, prior generation receipt, and static plan by SHA-256. The returned completion record lists the added scalars, the unchanged primary and fallback identities, the new atlas and receipt hashes, and whether each watched source font asset stayed byte-identical. Native Editor import, save/reopen, and Player glyph checks remain separate evidence.
