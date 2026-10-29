# Controlled Unity asset retirement

`assets.retire` uses the existing immutable `unity plan` / `unity apply`
transaction. The default and source-only policies accept imported files only. Directory requests
require the separate explicit `empty-folder` policy in [EMPTY-FOLDERS.md](EMPTY-FOLDERS.md);
nonempty directory trees are never retired recursively. The full Assets,
Packages and ProjectSettings source inventory is hashed at plan time and must
still match before execution.

Example spec:

```json
{
  "schemaVersion": 1,
  "operation": "assets.retire",
  "retire": [
    {
      "path": "Assets/Game/Resources/Legacy.json",
      "role": "obsolete-runtime-config",
      "reason": "Replaced by the approved configuration.",
      "sourceEvidence": "Reviewed consumer map dated 2026-10-28."
    }
  ],
  "protectedRoots": [
    "Assets/Game/Scenes/Main.unity",
    "Assets/Game/Editor/ConfigWriter.cs"
  ],
  "resources": [
    {
      "key": "Legacy",
      "path": "Assets/Game/Resources/Legacy.json",
      "guid": "33333333333333333333333333333333",
      "reason": "Retire this implicit Resources key.",
      "sourceEvidence": "Reviewed key inventory dated 2026-10-28."
    }
  ]
}
```

Each selected file needs a source role, reason, and evidence. Each protected
root is an explicit imported file (for example, a scene, configuration asset,
or script) with its own `.meta`. Protected roots cannot also be selected for
retirement. Planning binds the selected file and metadata hashes, metadata
GUIDs, the full source guard, and protected-root hashes/GUIDs. The bounded
transaction permits at most 10,000 file/meta entries and 256 MiB of selected
bytes; larger retirements need reviewed groups.

Every selected asset under a `Resources` folder requires a matching declaration
with its exact extensionless key, path, and GUID. The Editor checks the static
dependency closure returned by `AssetDatabase.GetDependencies` for every
protected root and refuses a deletion still in that closure. Reflection,
string-built keys, and `Resources.Load` uses cannot be proven absent; the
explicit key declaration records the reviewed retirement decision and native
reports mark dynamic use as unprovable. A key collision with any remaining
resource asset blocks the plan. The report does not claim that the key is
unused.

Before launching Unity, apply verifies and copies every selected file and
`.meta` into the transaction's `before/` directory and writes a hash-verified
checkpoint. The native Editor then verifies the source hashes, static metadata
GUIDs, Unity asset GUIDs, and complete before-images. It records every selected
GUID/localID identity before deletion, writes a durable in-progress marker for
each `AssetDatabase.DeleteAsset`, and records the completed path immediately
after the asset and its metadata are absent. Native GUID absence uses
`AssetPathToGUIDOptions.OnlyExistingAssets` because the default API can return
a recently deleted asset's cached GUID. It also records the protected
static dependency paths and checks protected-root bytes and identities before
and after. A separate Editor invocation verifies selected paths remain absent
and protected identities still match. Python's source audit accepts only the
planned selected files and metadata being deleted.

Recovery is available through the same immutable plan identity:

```text
beaver unity plan --project <Unity-project> --spec <retirement.json> --out <fresh-plan-directory>
beaver unity apply --plan <unity-plan.json> --expected-plan <sha256> --out <fresh-transaction-directory> --editor-path <Unity-executable>
beaver unity recover --transaction <transaction-directory> --expected-plan <sha256> --editor-path <Unity-executable>
```

The Python API is
`recover(transaction, editor, expected, timeout=600)`. The caller passes the
transaction directory and the original plan SHA-256. Recovery accepts a
completed retirement or one marked `recovery-required`, and refuses a second
recovery after success. It requires a native per-file deletion checkpoint,
complete GUID/localID records, no unresolved in-progress deletion, and intact
before-images. Under the project lock it checks the entire current source tree
against the exact expected after-state before restoring anything. Existing
identical bytes are kept only when a previous recovery copy checkpoint owns them;
manually recreated files or metadata block recovery. Missing files and metadata are restored with
create-only verified copies. Different bytes, added manual metadata, unplanned
changes, or incomplete deletion evidence block restoration.

After restoring, the implementation temporarily installs the same native
Editor companion used by apply, keeps it present across the refresh and
independent reopen checks, and removes it only if its bytes still match the
owned copy and its reserved directory contains no foreign files. Recovery
reports success only after native GUID/localID readback and a full source-tree
comparison with the original plan. If the Editor cannot compile or run the
companion, verified file restoration may already have occurred, but the
transaction remains `recovery-required`; native restoration is not reported as
verified. An in-progress deletion without a conclusive after-checkpoint is
blocked rather than guessed. This is a selected-file recovery path, not an
automatic whole-project rollback.

Use `--summary` on plan/apply/recover for bounded transport; the full SHA-bound plan or transaction journal retains all selected changes and native object identities.

## Explicit source-evidence-only archive

The default `identityPolicy` is `native-object` and continues to require actual persistent localIDs. An optional `source-evidence-only` policy is restricted to a previously observed asset with **zero Unity objects**, not an asset whose objects exist but whose IDs failed inspection. Each such retirement row must include `sourceIdentityEvidence` with exactly `snapshotPath`, `snapshotSha256` and `assetPath`, referencing a hash-bound guarded build-filter snapshot. The selected row must be `unknown` / `no-persistent-object`, with objectCount 0 and empty localIds/types; its source/meta hashes, byte counts and real GUID must match the retirement plan.

Planning freezes the snapshot digest and selected evidence record. Native apply independently checks current file/meta bytes and the existing GUID, synchronously imports, and confirms there are still exactly zero objects. Inspection errors or any imported object block this mode. Reports keep the real native GUID, empty localIDs and explicit source-only state; no runtime identity is fabricated. Protected-root static dependencies and exact Resources retirement declarations remain mandatory.

Recovery restores create-only verified before-images and independently reopens Unity. Source-only recovery verifies the same bytes/meta/native GUID and the same zero-object observation. If objects appear or inspection is uncertain, restored bytes may remain while the transaction stays recovery-required. The report never claims that such source evidence is usable runtime content. Keep the immutable transaction and its before-images for as long as the archived source evidence is needed; do not treat a disposable temporary output directory as permanent storage.

`snapshotSha256` is the SHA-256 of the snapshot file's exact raw bytes, matching the CLI artifact hash. The target-row digest inside the immutable plan is canonical JSON. Within one plan, shared snapshot artifacts are parsed and runner-validated once while every target is checked separately; caches do not cross plans. Resources key collision guards are case-insensitive.

The derived manifest/runtime job explicitly carries `hasSourceIdentityEvidence` for both policies. Callers do not set this flag in the spec. This prevents JsonUtility's default empty nested objects from being mistaken for supplied evidence, while source-only jobs still require the complete bound record.
