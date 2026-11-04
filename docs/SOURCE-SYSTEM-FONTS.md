# Cocos system-font preparation and generation API

`monkey.source_system_font_preparation` adapts the existing Cocos Label/CoreText resolver and Unity system-font binding planner. It does not execute Creator code, change serialized source font fields, copy installed font files, or create/import Unity assets.

## Prepare request

Call `prepare(request_path, expected_request_sha256, output)`. `request_path` is a UTF-8 JSON file and `expected_request_sha256` is its lowercase SHA-256. Each input is an absolute file path and an explicit lowercase SHA-256:

```json
{
  "schema": "monkey-source-system-font-preparation/1",
  "schemaVersion": 1,
  "ir": {
    "path": "/absolute/path/normalize/ir.json",
    "sha256": "<64 lowercase hex characters>"
  },
  "sourceManifest": {
    "path": "/absolute/path/inspect/source-manifest.json",
    "sha256": "<64 lowercase hex characters>"
  }
}
```

The operation accepts only the `cocos-2.4.15-bundle` profile with source version `2.4.15`. The normalized IR must pin the exact source-manifest bytes. It checks the request, input hashes, safe non-symlink paths, a 1 MiB request limit, a 128 MiB per-input limit, and 256 MiB total input budget. The output directory must be new and must not overlap the pinned inputs.

The existing `resolve_ir_macos_system_font_files` resolves only serialized `cc.Label` components with `systemFont=true` and `font=null`. Its CoreText queries inspect the current macOS host and installed font files read-only. Inputs are re-hashed after the resolver returns. No source script is run.

Outputs:

- `resolution.json`: the resolver's original receipt.
- `unity-system-font-binding.json`: the existing `prefab_system_fonts.prepare` declaration, pinned to the exact IR and receipt.
- `static-sdf-plan.json`: present when a binding contains a `StaticSDFRequired` face; this is a plan only.
- `manifest.json`: top-level request/input/output pins, status, diagnostics, and next action.

Top-level statuses:

- `prepared`: bindings are declared, but native Unity font assets still require Editor import and readback.
- `needs_static_generation`: a bounded static SDF plan exists; no atlas or metrics were made by `prepare`.
- `needs_action`: input identities, resolver evidence, or binding preparation need review.

The manifest always keeps `sourceOSIdentityVerified=false` and `visualEquivalent=false`. The current host's CoreText choice does not identify the source device OS or establish visual equivalence.

## Generate and stage one static SDF face

Call `generate(preparation, expected_preparation_sha256, output, budget_seconds=240)` where `preparation` is the exact `manifest.json` from a `needs_static_generation` result. It rechecks the preparation manifest hash, every declared preparation output pin, and both frozen source inputs. It accepts exactly one `StaticSDFRequired` face whose plan and binding identities match.

The operation invokes only this package's `src/monkey/targets/GenerateCoreTextSdf.swift`, via the installed `swift` executable and a bounded timeout (`budget_seconds` 1–3600). The generator must emit its declared `glyph-atlas.png` and `glyph-metrics.json`; metrics are checked against the static plan, source label IDs, glyph Unicode set, system/font identity, and the package source hash. The API writes `generation-receipt.json` from those verified outputs and passes it to the existing `prefab_system_fonts.prepare_static_inputs` for strict identity validation and portable staging.

Generation outputs include the raw generator files under `generated/`, `generation-receipt.json`, staged portable inputs under `static-inputs-stage/`, and a `manifest.json`. A successful result is `prepared` and still requires a native Unity Editor import/save/readback. Timeouts, nonzero Swift exit, hash drift, malformed metrics, or staging mismatch return `needs_action` with preserved output evidence. The OS font bytes are never copied or included; no native Unity asset or visual-equivalence claim is made.

## Public CLI integration

CLI argument parsing and dispatch are integrated separately by the tool's owner. The intended prepare call is:

```text
monkey prepare-source-system-fonts --request REQUEST.json --expected-request SHA256 --out NEW_OUTPUT
```

The intended generation call is:

```text
monkey generate-source-system-fonts --preparation MANIFEST.json --expected-preparation SHA256 --out NEW_OUTPUT --budget-seconds 240
```

The CLI parser/dispatch is maintained separately from this module. The worktree owner has wired these two commands to the API during this task; this module itself does not change the shared CLI contract.
