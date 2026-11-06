# Native candidate JSON assets

`monkey.code_architecture_resources.add_json_assets(candidate, expected_manifest, spec, expected_spec, out)` adds explicitly self-authored local-test JSON to a fresh copy of a verified native architecture candidate and returns the new candidate manifest. The producer does not change the supplied candidate, source evidence, or spec/artifact inputs. It does not add C# constants, audio, or recovered-original claims.

The input candidate must pass the existing native-candidate verifier, including its complete manifest inventory and file hashes, and must not already contain a `jsonAssetReceipt`. `expected_manifest` pins its manifest bytes. `spec` is a pinned JSON plan and `expected_spec` is its SHA-256. The spec's parent directory is a closed input inventory: it must contain exactly the spec and the JSON artifact files listed by the plan. The candidate and spec directory must be disjoint. `out` must be a nonexistent directory disjoint from both inputs; a failure removes only the output directory created by this call.

The spec schema is `monkey-native-json-assets/1`:

```json
{
  "schemaVersion": "monkey-native-json-assets/1",
  "baseManifestSha256": "<exact candidate manifest SHA-256>",
  "architecturePlanSha256": "<architecture plan SHA-256 from the candidate>",
  "revisionId": "bootstrap-local-test-seed-v1",
  "assets": [
    {
      "path": "Assets/Game/Content/Config/Bootstrap/LocalTestSeed.json",
      "artifactPath": "seed/LocalTestSeed.json",
      "sha256": "[private fingerprint omitted]",
      "bytes": 107,
      "role": "derived-local-test",
      "provenance": {
        "kind": "self-authored-candidate-local-test",
        "sourceId": "candidate-local-test:bootstrap-seed-v1",
        "logicalKey": "Bootstrap/LocalTestSeed",
        "statement": "Self-authored test data; not recovered from the original game."
      }
    }
  ]
}
```

The JSON artifact itself is authored data, for example:

```json
{
  "accountId": "candidate-local-test",
  "inventory": [
    { "itemId": "seed-coin", "count": 25 }
  ]
}
```

Each asset must use the exact `derived-local-test` role and self-authored provenance shown above. Its target must be a canonical `.json` path under `Assets/Game/Content/Config/`. The spec and every asset are strict UTF-8 JSON objects: duplicate keys, `NaN`/infinities, malformed UTF-8, oversized/deep documents, and non-object roots fail closed. Target collisions, orphan `.meta` collisions, duplicate/colliding Unity GUIDs, changed input pins, and unplanned files in the spec directory also fail before the candidate is returned.

The producer copies the full verified candidate inventory, adds each JSON plus a deterministic Unity `.meta`, and writes a complete new manifest. GUIDs derive from the candidate namespace and target path, so repeated output of the same target keeps its identity. New JSON rows use owner `generated` and source kind `candidate-local-test-json`; metadata has its own `candidate-local-test-json-meta` ownership row. `jsonAssetReceipt` pins the base manifest, architecture plan, spec, JSON hashes, generated GUIDs, role, and provenance. The output manifest marks compilation and runtime `not_run`; copying a test seed does not establish game semantics, native binding, or original-game equivalence.
