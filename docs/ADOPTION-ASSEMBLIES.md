# Managed SDK adoption preflight

Unity adoption plans include `managedAssemblyCompatibility`. File paths and
asset GUIDs alone do not prevent a newly added SDK from shadowing a retained
MonoScript. The preflight reads PE/CLI assembly and type metadata without loading
or executing DLLs. Renaming a DLL does not change its assembly identity.

The checked scope is managed DLLs inventoried under `Assets/` in the candidate
and target, plus their exact importer metadata. Package-cache assemblies,
assembly references, conditional source compilation and native plugin binaries
are not analyzed. Cross-assembly comparison uses public types; same-named internal/compiler-generated types are legitimate and remain only in hash-bound inventory counts. Internal serialized class hierarchies are not resolved. This is not complete compiler or native binding analysis.
The existing native code import, independent compilation/reopen, GUID/localID
readback and rollback remain separate requirements.

Default behavior is conservative: unknown/missing importers, unsupported binary
formats, same assembly name or overlapping public types with overlapping/unknown roles,
and unreviewed duplicate role pairs block before any native writes. Missing
importer settings are not interpreted as disabled. Only exact supported Any and
Editor settings with unconstrained CPU/OS are recognized; platform-specific or
conditional settings require separate evidence and remain blocked here.

An isolated new SDK may explicitly declare an Editor-only/Player-only pair in
the candidate manifest. Each final DLL must be pinned by path, GUID, file hash,
metadata hash and actual role:

```json
{
  "managedAssemblyPolicy": {
    "schemaVersion": 1,
    "strategy": "explicit-disjoint-role-pairs",
    "assemblies": [
      {
        "path": "Assets/Plugins/Example/Editor/Example.dll",
        "guid": "11111111111111111111111111111111",
        "sha256": "<64 lowercase hex>",
        "metaSha256": "<64 lowercase hex>",
        "role": "editor-only"
      },
      {
        "path": "Assets/Plugins/Example/Player/Example.dll",
        "guid": "22222222222222222222222222222222",
        "sha256": "<64 lowercase hex>",
        "metaSha256": "<64 lowercase hex>",
        "role": "player-only"
      }
    ]
  }
}
```

Pins cannot override a collision or unknown role. They do not authorize adding a
new identity alongside a retained SDK, even when roles are disjoint: compilation
domains do not establish continued resolution of historical serialized script
identities. Replacing an existing DLL or importer is blocked as requiring a
separate native migration. This version does not perform that migration, change
`m_Script`, disable old plugins, choose a canonical SDK or rewrite old assets.
The consumer must retain the failed plan and provide a separately validated
canonical generation/native adaptation with its own rollback before retrying.

Use the existing `beaver adopt plan --candidate ... --target ... --baseline ...
--out ...` and inspect both `conflicts` and `managedAssemblyCompatibility`.
`adopt apply` refuses blocked plans before staging or launching an Editor.
No new CLI arguments or GREA operation are required. Existing fixed plans remain
bound to their original algorithm; a new tool requires a fresh plan.

Build certification additionally requires `BuildResult.Succeeded` and an
explicit integer `buildErrors=0`, both in the native helper and independently
in the waiting parent. Missing, malformed or nonzero counts cannot produce a
certified artifact manifest. Font source protection and post-exit verification
remain in force on failure as well as success.
