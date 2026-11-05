# Native TMP outline regression

These are synthetic Cocos 2.4.15 source Prefabs, not recorded player states.
The sixteen cases cover primary Latin, Chinese fallback and mixed text; outline
absent/disabled/zero/transparent, widths 2.5/3/3.6, and half alpha.

Generate fresh inputs and use the normal public conversion entry:

```sh
python tests/native_text_outline/make_fixture.py --out /absolute/fresh/fixture
monkey convert --source /absolute/fresh/fixture/source/config.json --all-assets \
  --target unity --unity-system-fonts coretext --offline --out /absolute/fresh/converted
```

Import the resulting `project` with `monkey native-import`, its exact
`manifest.json` SHA-256, an explicitly selected Unity Editor, a bounded native
window, `--render-preview`, and `--execute`. A partial CLI result can retain
unresolved source/business diagnostics; inspect the process result and saved
Prefab readbacks separately.

In a disposable copy of the saved native project, add `OutlinePixelProbe.cs`
under `Assets/Editor`. Set `MONKEY_OUTLINE_CASES` to JSON `{ "rows": [...] }`;
map each fixture case's `sourceId` through the generated import plan's
`sourcePrefabs` to produce rows containing `name`, `text`, and `path`.
Set `MONKEY_OUTLINE_CAPTURE` to a fresh image directory and execute
`OutlinePixelProbe.Render` with the exact Unity executable. Repeat in a fresh
Editor process, using `initial` and `cold` image directories respectively.

```sh
python tests/native_text_outline/measure.py /absolute/capture /absolute/fresh/fixture
```

The measurement exits nonzero on any failure. It requires exact white-background
RGB equality, unchanged glyph fonts/slots/advances/style, exact cold image
identity, no stroke for disabled/zero/transparent cases, source radius within
one raster pixel, and half-alpha coverage within 0.08 of 128/255. The reported
four edges and pixel deltas remain available in `measurements.json`.

`OutlineBehaviorProbe.Run` accepts `MONKEY_OUTLINE_PREFAB` (the converted mixed
3-pixel case's Unity asset path) and `MONKEY_OUTLINE_BEHAVIOR` (fresh output).
It checks the face's unchanged font/material/style/layout, owned sibling ordering,
ignored layout/raycast, node opacity, RectMask2D and stencil Mask clipping,
independent cloned layers, and disabled/transparent/empty/destroyed cleanup.
It writes images and `result.json`, and throws if any assertion fails.
