# Unity TMP source outline conversion — 2026-11-05

The public Cocos-to-Unity conversion now creates a serialized paired-outline
component. The original TMP face retains its original font, material, margins,
style and layout/input identity. An owned native TMP sibling renders the stroke
behind that face and is recreated after reopening. Bitmap outlines retain their
original bitmap behavior. Existing unpaired serialized components keep their
legacy configuration path.

The source-to-native mapping preserves disabled, empty, zero-width and transparent
states. A source-pinned static primary stroke atlas prevents the DynamicOS atlas's
padding from truncating wider outlines. Native TMP SDFAA and CoreText atlases use
their respective distance encodings. Stroke material weight/dilation changes apply
to the separate stroke layer; the original fill material is not adjusted.

Source-node boundary checks, reported source counts and ContentPreviewView label
references exclude only a typed generated stroke with an exact owner relationship.
Unknown source nodes are still refused. Native group opacity and parent masks are
preserved, and derived layers do not receive input or participate in layout.

## Completed checks

- Unity 6000.6.2f1 imported, saved and reopened all sixteen synthetic source Prefabs
  through the public conversion and native-import entries. The reusable fixture
  generator reproduces the inspected source bytes and identities exactly.
- Two separately opened Editor processes produced identical images. Every case
  retains exact white-background RGB equality with its unoutlined counterpart,
  unchanged glyph font/slot/advance/style data, and correct disabled/zero/transparent
  output. Widths 2.5, 3 and 3.6 pass the one-raster-pixel radius tolerance.
- At source radius 3, mixed-text edges measure 3.263/3.000/3.016/3.000 pixels;
  Latin edges 3.153/2.989/3.033/3.031; Chinese fallback edges
  3.000/2.960/2.974/3.000. Half-alpha coverage is 0.5043 of opaque coverage.
- Eleven native behavior checks pass: pair ownership/order, unchanged face,
  node opacity, no raycasts, RectMask2D, stencil Mask, independent cloning,
  disabling, transparent/empty text, and destruction cleanup.
- Thirty-six focused Python checks pass. Five source-set/compile checks pass,
  including ordinary exports without Spine and the pinned Spine source closure.
  The pre-existing combined Unity/paused-Cocos conversion test is outside this
  Unity-only increment; it is not counted as passing.

The actual Foodstreet `Prefab/Effect/wave_desc` source was separately converted
and used to exercise nested source-node accounting and saved resource references.
Its original custom behavior/Animation and original-device visual comparison are
not established by this static check. Native process success is separate from the
CLI's retained source, font-platform and business diagnostics (`partial`).

The reproducible tools and measurement assertions are in
[tests/native_text_outline](../../tests/native_text_outline/README.md). Exact local
commands, hashes, failed attempts and native outputs remain in ignored evidence
under `.private/outline-takeover-20261105`; no private source/font bytes or images
are included in this source change. This is local development, without a release,
global installation or product-project adoption.
