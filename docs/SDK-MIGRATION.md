# Explicit Unity SDK migration through adoption

SDK migration is an opt-in policy layered on the existing adoption plan and
transaction. Without a migration spec, the existing managed assembly
preflight continues to block ambiguous retained/new SDK identities.

## Public call

The Python preview entry point accepts a separate consumer-authored JSON file
and its required exact SHA256:

```python
preview(candidate, target, output, baseline,
        sdk_migration="sdk-migration.json",
        expected_sdk_migration_sha256="<64 lowercase hex digits>")
```

The spec hash, candidate manifest hash, and complete target `Assets` inventory
hash are copied into the immutable adoption plan. `prepare` rechecks all three
before staging. The ordinary adoption code, apply, independent verify, before
images, and rollback remain the only write and recovery path.

## Spec version 1

The top-level object is closed: unknown fields are rejected.

```json
{
  "schemaVersion": 1,
  "contract": "beaver-sdk-migration/1",
  "unityVersion": "6000.6.2f1",
  "candidateManifestSha256": "<candidate manifest SHA256>",
  "targetAssetsSha256": "<canonical target Assets inventory SHA256>",
  "referenceCoverage": "all-sdk-references-in-adopted-assets",
  "licenses": [
    {
      "id": "spine-runtime",
      "root": "candidate",
      "path": "Assets/Plugins/Spine38/LICENSE",
      "sha256": "<license file SHA256>"
    }
  ],
  "assemblies": [
    {
      "role": "spine-runtime",
      "assemblyName": "Spine.Unity",
      "licenseId": "spine-runtime",
      "monoScriptPolicy": "capture-before-preserve-and-pair-localids",
      "variants": [
        {
          "domain": "editor",
          "action": "replace-preserve-guid",
          "path": "Assets/Plugins/Spine38/spine-unity.dll",
          "after": {
            "guid": "<canonical GUID>",
            "sha256": "<candidate DLL SHA256>",
            "metaSha256": "<candidate importer meta SHA256>",
            "version": [3, 8, 99, 0],
            "metadataTypes": ["Spine.Unity.SkeletonGraphic"]
          },
          "before": {
            "guid": "<same canonical GUID>",
            "sha256": "<current target DLL SHA256>",
            "metaSha256": "<current target importer meta SHA256>",
            "version": [3, 8, 95, 0],
            "roles": ["player"],
            "metadataTypes": ["Spine.Unity.SkeletonGraphic"]
          }
        },
        {
          "domain": "player",
          "action": "add",
          "path": "Assets/Game/Adopted/SDK/Spine38/spine-unity.dll",
          "after": {
            "guid": "<new Player DLL GUID>",
            "sha256": "<candidate DLL SHA256>",
            "metaSha256": "<candidate importer meta SHA256>",
            "version": [3, 8, 99, 0],
            "metadataTypes": ["Spine.Unity.SkeletonGraphic"]
          },
          "before": null
        }
      ]
    }
  ],
  "references": [
    {
      "root": "target",
      "assetPath": "Assets/Game/Content/Prefabs/Legacy.prefab",
      "assetSha256": "<prefab SHA256>",
      "objectLocalId": 11400000,
      "propertyPath": "m_Script",
      "action": "preserve",
      "source": {
        "guid": "<canonical GUID>",
        "localId": 11500000,
        "type": "Spine.Unity.SkeletonGraphic"
      },
      "canonical": {
        "guid": "<same canonical GUID>",
        "localId": 11500000,
        "type": "Spine.Unity.SkeletonGraphic"
      }
    }
  ]
}
```

Each SDK role has exactly one Editor and one Player variant. Candidate paths are
the canonical destination paths; replacement preserves the target GUID, while
the candidate itself supplies the exact already-saved importer after-image.
`metadataTypes` is the complete bounded CLR TypeDef inventory read from the
DLL bytes. It is separate from MonoScript inventory: producer data cannot use
an unrun probe or an empty list as evidence that no MonoScripts exist.

The default `monoScriptPolicy` requires both Editor and Player variants to
expose the same native `MonoScript` full-type/localID table. The opt-in value
`capture-before-preserve-and-attest-inactive-player` covers a Unity Player DLL
that is excluded from the Editor and exposes no `MonoScript` objects there.
It is accepted only when the Player after-image DLL SHA and derived MVID exactly
match the canonical Editor slot's pinned before-image, a complete native
before snapshot was captured, and its full type/localID table matches the
active Editor after table. The report keeps the observed Player `scripts: []`
and labels the separate evidence source path, SHA, MVID, and tuple SHA; it never
fills the inactive table from metadata. Different bytes/MVID, incomplete
before capture, or a different tuple remain blocked. This evidence does not
prove a Player compile or runtime load. Unity local IDs are nonzero signed
64-bit integers and remain exact, including negative IDs.

For a replacement, the spec pins the existing target file and `.meta`, its
assembly identity/version, and importer role. The planned destination must be
that exact path. A new role variant must have an empty target path. The after
meta already contains the canonical GUID and exact Editor-only or
Player-only importer settings; the tool never synthesizes or guesses a meta
after-image. If an old target meta contains only the GUID and no serialized
PluginImporter, its `before.roles` must be `["native-required"]`; the native
Editor records the actual before role and verifies that exact role again on
rollback. A malformed or partially specified importer is still rejected.

Unity captures actual `MonoScript` objects with `MonoScript.GetClass()` and
`AssetDatabase.TryGetGUIDAndLocalFileIdentifier` in the closed Editor before
the compiler stage. After the independent Editor restart it verifies that a
canonical replacement retained every captured GUID, localID, and full type.
Under the default policy, both Editor and Player variants must expose the same
localID/type set. The captured before and after tables are stored in the native
transaction report.
The consumer spec does not carry an MVID field: Beaver derives each DLL's
`moduleVersionId` from its hash-bound CLI Module.Mvid metadata row and adds it
to the normalized plan. Native `GetClass()` results must come from the active
canonical Editor variant's MVID; the report records each script's loaded MVID
alongside its GUID/localID/type. The helper also records the same-name
`AppDomain` assembly MVID when loaded. An assembly that is not loaded is marked
`notObserved`, and the aggregate native assembly-binding flag remains false;
this is not treated as proof of binding. Before-to-after replacement may
change MVID, but cannot change a captured script's GUID/localID/full type.
Independent reopen and rollback compare the MVID evidence for their respective
fixed Editor DLL state. A prior Player-only image without a canonical Editor
before-image is rejected because its native binding source cannot be proven.
The caller supplies exact references that must remain or map; native readback
checks their owning object localID, property path, GUID, referenced localID,
and type. The helper also scans adopted Prefab and Asset objects and refuses
any SDK reference that is missing from the spec. Schema v1 never rewrites
`m_Script`. A non-`m_Script` object reference can be mapped with
`SerializedObject` only when both object identities are explicit and the
containing asset is part of this adoption transaction.

## Refusal boundaries

The tool blocks an unknown license, stale source or target snapshot, unsupported
Unity version, noncanonical path, uninspectable assembly, incomplete TypeDef
inventory, stale importer, changed canonical GUID, mismatched Editor/Player
MonoScript set, missing or duplicate native reference, or any attempted
historical `m_Script` change. It does not delete Missing Script components,
rewrite YAML, or infer compatibility from names or versions. Changed Unity
Scene assets are outside schema v1 because native complete serialized-object
enumeration is not implemented for them.

Any DLL, importer-meta, or mapped serialized-reference write is represented by
the same frozen adoption operation and before-image. DLLs use the existing
closed-Editor compiler stage; apply and independent reopen validate SDK roles,
types, GUID/localID bindings, and serialized references. Native failures use
the existing rollback and later-edit guards. No Editor, Player build, or
project is launched by planning or prepare.
