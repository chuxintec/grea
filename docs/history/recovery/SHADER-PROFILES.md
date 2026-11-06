# Exact native Shader profiles

`monkey.shader_profiles` currently supports one deliberately narrow adapter: the supplied Cocos Creator 2.4.15 `builtin-2d-sprite` EffectDescription, with the pinned `glsl1` vertex and fragment stages and one fixed macro assignment. It emits a standalone Unity ShaderLab shader and a companion material into a caller-assigned project-relative `Assets/` folder; the default is `Assets/Game/Content/Shaders/RecoveredBuiltin2DSprite/`. The namespace binds deterministic asset identities and is recorded in the report. It does not modify or bind any game material automatically.

The input identity is `internal:[private identifier]`. Call `describe(effect, effect_sha256=<raw EffectDescription SHA-256>)`; parsing and re-serializing JSON does not prove source-byte identity. The raw digest must match `[private fingerprint omitted]`, and the embedded `glsl1.vert` and `glsl1.frag` must match their independently pinned program digests. The exporter also requires the exact source ID. A mismatch returns an unsupported report; it never selects a shader by name or approximate hash.

The fixed profile sets `USE_TEXTURE=true`; `CC_USE_MODEL`, `USE_ALPHA_TEST`, `CC_USE_ALPHA_ATLAS_texture`, `INPUT_IS_GAMMA`, and `USE_BGRA` are false. Its observable fragment operation is `texture * vertexColor`. The source EffectDescription stores only `blend: true`, so the profile resolves the missing factors from the supported Cocos 2.4 Sprite default: the pinned engine `BlendFunc` initializes `srcBlendFactor=SRC_ALPHA` and `dstBlendFactor=ONE_MINUS_SRC_ALPHA`; when applying a non-default blend it supplies the same pair to both color and alpha equations. The official 2.4 Sprite manual documents the matching `source.RGB * source.A + dest.RGB * (1 - source.A)` formula. Unity therefore uses `Blend SrcAlpha OneMinusSrcAlpha, SrcAlpha OneMinusSrcAlpha` for color and alpha. This is a source-engine default contract; the local CPU oracle checks that equation, while native Unity readback checks the generated target shader. Alpha discard, atlas alpha, gamma conversion, BGRA swizzle, other macro combinations, other Cocos versions, other effects, and general GLSL translation are unsupported. Preserve the original effect and stages and report an adapter gap for those cases.

Example after a catalog adapter has parsed the source JSON and retained its raw SHA-256:

```python
from pathlib import Path
from monkey.shader_profiles import describe, export_profile, prepare_probe

effect = ...  # Parsed JSON from the catalogued source file
raw_sha256 = "[private fingerprint omitted]"
profile = describe(effect, effect_sha256=raw_sha256)
if profile["supported"]:
    result = export_profile(
        effect, Path("/path/to/isolated/UnityProject"), "sample-game", profile["sourceId"],
        effect_sha256=raw_sha256, folder="Assets/Game/Content/Shaders/RecoveredBuiltin2DSprite",
    )
    plan = prepare_probe(
        Path("/path/to/isolated/UnityProject"),
        Path("/path/to/isolated/UnityProject/Assets/Game/Content/Shaders/RecoveredBuiltin2DSprite/shader-profile.json"),
        profile["sourceId"], Path("/private/tmp/shader-probe-run"),
    )
```

All generated outputs are new files; the exporter refuses an existing path. A caller may pass the unique folder already assigned by the layout planner. It must be a canonical, non-symlink path under `Assets/`. Shader, material, and report assets have deterministic Unity `.meta` GUIDs, and the material refers to the generated shader GUID. The report records source/program/target hashes, fixed defines, limitations, and license provenance. The source engine runtime implementation used for blend defaults has an MIT notice; the extracted EffectDescription itself contains no individual license notice, so the report records that distinction without making a separate rights conclusion for the asset. `nativeShader=true` means a native candidate was generated; `status=candidate-generated-native-validation-pending` keeps Unity import, shader compilation, and pixel validation explicitly pending.

`prepare_probe` verifies and copies both generated assets and their `.meta` files into a minimal Unity 6000.6.2f1 project and writes `probe-plan.json`; it does not launch Unity. The Editor method is `MonkeyShaderProbe.Run`. Run only in the separately granted native window with a graphics device; `-nographics` / a null graphics backend must fail. The probe compiles the candidate through `ShaderUtil`, reads the imported material and deterministic GUIDs, saves and reimports it to check the shader reference, then draws through a temporary instance of that serialized material into a controlled `RenderTexture`. It reads one pixel back and compares the result with the fixed source-subset multiply-and-blend oracle. The oracle is not a substitute for validating source variants or broader Cocos behavior.

## Evidence and limits

- Source EffectDescription SHA-256: `[private fingerprint omitted]`.
- Source `glsl1.vert` SHA-256: `[private fingerprint omitted]`.
- Source `glsl1.frag` SHA-256: `[private fingerprint omitted]`.
- Source version: Cocos Creator 2.4.15 as identified by the provided input contract; this module does not independently establish engine provenance.
- Blend-source evidence: [pinned Cocos Creator 2.4.15 `blend-func.js`](https://raw.githubusercontent.com/cocos-creator/engine/[private fingerprint omitted]/cocos2d/core/utils/blend-func.js) and [official Cocos Creator 2.4 Sprite texture/blend documentation](https://docs.cocos.com/creator/2.4/manual/en/asset-workflow/sprite.html).
- The shader adapter was developed against the input contract. Neither this evidence nor the probe claims that all 38 source Effects were compiled or visually validated.
- A v7 candidate produced from this profile passed in Unity 6000.6.2f1 on Metal: ShaderUtil reported no errors, the serialized `.mat` resolved its deterministic shader GUID and retained that reference after save/reimport, and one controlled GPU pixel was within the CPU oracle tolerance. The result and sanitized Editor log receipt are in `.private/v050-continuation-20261026/shader-module/native-receipt-v7.json`.
- This is a fixed-profile target pixel check, not a direct Cocos Editor/runtime screenshot comparison or full visual parity result. Game material adoption and all other 37 source Effects remain unvalidated.
