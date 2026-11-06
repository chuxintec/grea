# Bounded Unity atlas maintenance

This local maintenance candidate extends the existing `unity-leaf-prefab-sprite-array-v1` profile. It does not replace the published 0.6.0 artifacts. It preserves the existing command, candidate and toolkit identifiers.

## Serialized packing and geometry

The verified tight geometry source is Unity 2021.3.30f1, platform 20. Decode `settingsRaw` as packed bit 0, packing mode bit 1, packing rotation bits 2–5 and mesh type bit 6. The supported combinations remain bounded:

| Raw | Packed | Mode | Rotation | Mesh type |
| --- | --- | --- | --- | --- |
| 65 | yes | Tight | None | Tight |
| 67 | yes | Rectangle | None | Tight |
| 69 | yes | Tight | FlipHorizontal | Tight |
| 73 | yes | Tight | FlipVertical | Tight |
| 77 | yes | Tight | Rotate180 | Tight |

Unknown combinations and reserved bits are rejected. In particular, 73 encodes a vertical reflection, rather than a quarter turn. The tight profile preserves the original float32 planar vertices, vertex order and uint16 triangle indices. It requires the known position/unused-UV stream layout and one triangle submesh; it does not round vertices or regenerate a hull.

For each original position `(vx, vy)`, the atlas affine transform gives `u = (vx * uv.x + uv.y) / width` and `v = (vy * uv.z + uv.w) / height`. A horizontal reflection applies `u = (2 * rect.x + rect.width) / width - u`; a vertical reflection applies `v = (2 * rect.y + rect.height) / height - v`. A half turn applies both reflections. This uses the serialized atlas rectangle without integer rounding. Original Sprite bounds/pivot and the packed atlas rectangle are distinct descriptors.

The reflections, half turn and unchanged topology were compared against bound source SpriteAtlases in Unity 6 Play sessions. Vertex float32 values and triangle indices must match exactly. UVs retain the existing native verifier tolerance of 0.000001 for float32 arithmetic; the two additional source controls observed maximum UV differences below 0.000000106. This does not permit vertex rounding or hull regeneration. Merely loading an unbound Sprite in the Editor can return zero UVs and is not a valid source control. Generated assets were separately imported, saved, reopened and read back in Unity 6000.6.2f1. These checks cover resource identity and geometry, not gameplay or visual acceptance.

## Explicit texture cache families

An explicit frozen cache manifest may identify `Assets/Textures/astc/<literal-bucket>/<exact-token-key>.txt` or `Assets/Textures/dds/<literal-bucket>/<exact-token-key>.txt`. The source bucket is not inferred from image dimensions. Only one supplied cache may match a source key unless an exact object/path binding selects one. See [exact texture selection](UNITY-TEXTURE-SELECTION.md) for the unpublished selected-object contract and partial-derivative boundary. Names and block-size hints do not establish the encoding: DDS magic, complete header, FOURCC and payload length are checked before decoding.

The new DDS subset is one single-level DXT5/BC3 image with matching positive dimensions, no cubemap/volume, no trailing bytes and at most 16,777,216 pixels. Pillow **12.2.0** is required in the selected provider Python. Its canonical normalization is `DDS-DXT5-to-RGBA-no-flip-v1`. ASTC continues to require texture2ddecoder **1.0.6**; DDS bytes are never passed to the ASTC decoder. Missing or mismatched decoder dependencies produce explicit diagnostics and do not trigger installation.

Hydration preserves every non-texture serialized object byte for byte. Native PNG creation preserves the canonical pixel hash and applies the existing vertical orientation conversion for Unity. In the isolated native verification copy, TextureImporter compression is set to Uncompressed and transparent RGB dilation is disabled. Temporary CPU readability is restored to its prior value. `GetPixels32` must match the canonical RGBA SHA-256, dimensions and single mip. Explicit Standalone texture overrides require a separate profile and are rejected. This exact-pixel verification policy is not a final platform compression or memory recommendation.

## Ordered native handoff

Readback includes each field name, element index, original serialized-file/pathID/raw SHA-256, actual imported Sprite GUID/localFileID, texture GUID, vertices, UVs and triangle indices. Empty arrays remain empty and field/element order is preserved. A handoff can contain only native Sprite assets, one proven texture and their metadata; verification schema fixtures do not supply the source game's methods or runtime pool implementation.

Private inputs, source controls, native readback, local wheel and consumer handoff stay in ignored directories. The consuming developer owns runtime references, actor behavior and target project adoption. No global installation, project mutation, remote publication or full-game success is implied.

## Primary format references

- [Unity 2021.3 Sprite packing enum and bindings](https://github.com/Unity-Technologies/UnityCsReference/blob/2021.3/Runtime/2D/Common/ScriptBindings/Sprites.bindings.cs)
- [AssetStudio Sprite serialization bit layout](https://github.com/Perfare/AssetStudio/blob/master/AssetStudio/Classes/Sprite.cs)
- [UnityPy Sprite export implementation](https://github.com/K0lb3/UnityPy/blob/master/UnityPy/export/SpriteHelper.py)

These sources inform format interpretation; support is limited by the independent checks above. Other rotations, variants, split alpha, secondary textures, mip chains, unrelated source versions and complete game behavior remain outside this verified subset.
