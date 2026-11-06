# Exact Texture2D hydration scope

This is a local, unpublished extension of `hydrate-unity`; the formal 0.6.0 wheel and shared installations are unchanged. Consumers must bind the exact local artifact/implementation fingerprint and check capabilities instead of inferring this extension from `--version`.

## Literal frozen cache paths

Cache entries retain their existing `schemaVersion: 1`, `path`, `logicalPath`, `bytes` and `sha256` contract. `logicalPath` is `Assets/Textures/{astc,dds}/<literal-bucket>/<exact-source-token-key>.txt`. The bucket comes from the frozen source manifest; it is not inferred from `max(width,height)`. A 256×512 texture may therefore legitimately use bucket `256`. The decoder still verifies the actual header dimensions and encoding against the selected Texture2D.

Without selection, the whole-container mode matches exact token filenames within the supplied frozen manifest. Exactly one match is required. Multiple supplied buckets or encodings for one token require an explicit binding; no preferred directory, URL decoding, alias or encoding guess is introduced. A filename index keeps matching bounded by the supplied manifest rather than repeatedly scanning it per texture. Missing required textures continue to block whole-container serialization.

## Explicit selected objects

```sh
monkey hydrate-unity --source <frozen.bundle> \
  --texture-cache <frozen-cache.json> --selection-manifest <selection.json> \
  --provider-python <pinned-provider-python> --out <fresh-output>
```

`selection.json` pins the input bytes and selects 1–256 exact Texture2D objects:

```json
{
  "schemaVersion": 1,
  "sourceSha256": "<exact input SHA-256>",
  "objects": [
    {
      "file": "<exact serialized-file name>",
      "pathId": "<canonical signed-int64 decimal string>",
      "rawSha256": "<exact original object-byte SHA-256>",
      "logicalPath": "Assets/Textures/astc/256/<exact-source-token-key>.txt"
    }
  ]
}
```

The explicit path must appear in the frozen cache manifest, and its filename must equal the object's literal token key plus `.txt`. Object type, file/pathID, raw hash, input hash, cache byte count, cache hash, format/header dimensions and decoded pixel length are verified. A missing/mistyped/stale selected identity or missing/ambiguous binding produces diagnostics; it does not fall back to another object or path. Decoder dependency pins are unchanged.

Selection is an explicit texture set, not an automatic Sprite/Prefab reference graph or a full-project export. Callers obtain IDs from source inspection and supply every Texture2D needed for their intended set. Unselected objects are never deleted or parsed for hydration; each unselected Texture2D is marked `not-selected-not-evaluated`, without claiming it has valid pixels or a missing cache. All unselected and non-texture object bytes must survive serialization exactly. Selected pixel format, dimensions and RGBA SHA are read back from the serialized derivative.

The selected set is atomic: if any selected requirement fails, no derivative is committed. `resolved` may describe staged decoding in an unsuccessful report; `serializationCommitted` and `derivedBundleSha256` determine whether a derivative actually exists. Incomplete early inventories have `inventoryComplete: false`.

## Partial is not whole-container success

When the selected set succeeds but other Texture2D objects are deferred, the report has `status: partial`, `selectionComplete: true`, `wholeContainerComplete: false`, `serializationCommitted: true`, explicit `deferred` entries and a verified `derivedBundle`. CLI exit remains **1** for partial; full `hydrated` is the only exit-0 state. The derivative intentionally retains the unprocessed original objects and placeholders. Consumers may explicitly use the proven selected texture subset, but must not reinterpret this receipt as a complete container or feed it to an all-resources-success gate.

Missing selected data returns `needs_action`; missing required data in default whole-container mode remains `blocked`. Ambiguity and identity drift are diagnosed without writing a derivative. Originals are immutable in every mode. No network acquisition, global installation, native Editor import or original game method execution is performed by this operation.

## Validation boundary

Focused tests cover exact non-square bucket matching, unchanged unreadable neighbors, original/pixel identities, full-container blocking, ambiguous cache paths, explicit-path mismatch, stale selectors and serialization drift. A private synthetic two-Texture2D UnityFS fixture additionally exercises the real UnityPy 1.25.3 worker and pinned DDS/ASTC decoders for 256×512 pixels with a literal `256` bucket. This is provider/serialization evidence, not a claim that a consumer's undisclosed real source input, native project or gameplay has been validated.

## Selected PNG delivery without a whole-container exporter

`export-unity` remains a whole-container AssetRipper operation. Passing it a partial hydration derivative can fail on unrelated token-backed textures. Use the separate `unity-selected-texture-export/1` operation for the exact proven texture set:

```sh
monkey export-unity-textures --source <same-original.bundle> \
  --derivative <hydration-output/hydrated.bundle> \
  --hydration-report <hydration-output/hydration.json> \
  --expected-hydration-sha256 <frozen-report-SHA-256> \
  --selection-manifest <same-selection.json> \
  --provider-python <pinned-UnityPy-1.25.3-python> --out <fresh-export>
```

This operation requires a committed selected-hydration receipt and its external SHA pin, the original/derivative byte identities and the original object selector. It independently compares the object inventories and every unselected object byte hash, reads only selected Texture2D TypeTrees, and verifies original object SHA, literal token binding, 2D/single-mip dimensions, derived RGBA format and canonical pixel SHA. It never runs AssetRipper, resolves unrelated textures, deletes objects or writes another bundle. Cache decoding provenance comes from the frozen hydration receipt; the export verifies its resulting derivative pixels rather than reinterpreting or reacquiring the cache.

The clean `Candidate/` directory contains PNGs under `Assets/Game/Content/Textures/Selected/` and `manifest.json`. PNG rows use the same vertical flip for Unity as the existing lossless exporter; PNG decode plus inverse flip must exactly reproduce the hydration RGBA hash. Filenames derive from source identity rather than source names. The manifest locks PNG bytes, source file/pathID/raw SHA, input/derivative/report/selection hashes, cache provenance, pixel dimensions and orientation, and the literal source texture settings. Provider work files and raw RGBA staging stay outside `Candidate/`.

Importer intent is Uncompressed, alphaIsTransparency=false and CPU readability=false. Sampling/color-space source fields are retained as source metadata for controlled adoption, not silently translated. No `.meta`, original GUID/localFileID or completed native import is fabricated. The consumer adopts the PNG while preserving or explicitly binding existing target identities and separately verifies importer/platform/color behavior in the Editor. This operation produces a resource candidate, not a UnityProject or a verified Texture2D import.

When the source receipt is partial, export stays `status: partial`, `exportComplete: true`, `wholeContainerComplete: false`, with the original deferred list and CLI exit **1**. The PNG is available for explicit scoped consumption; whole-container gates remain unchanged. A non-partial selected source may return `exported`/exit 0. Failed or uncommitted proofs cannot create a successful candidate manifest.

Additional checks cover asymmetric PNG orientation, unreadable unselected neighbors, pixel/receipt/selector drift and unselected-byte changes. A private synthetic 225-Texture2D UnityFS case exercises hydration of one object and direct PNG delivery while retaining 224 unrelated external-key textures. This does not establish acceptance of a consumer's real game input or native import.
