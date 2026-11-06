# Empty Unity folder retirement

`assets.retire` accepts a folder declaration only when `identityPolicy` is explicitly `empty-folder`. Existing file retirement keeps its `native-object` default and behavior. A transaction may contain files or empty folders, never both.

Each folder declaration uses the existing `path`, `role`, `reason`, and `sourceEvidence` fields, plus a source-bound `callerReview`:

```json
{
  "path": "Assets/Game/LegacyEmpty",
  "role": "obsolete-empty-container",
  "reason": "No authored child assets remain.",
  "sourceEvidence": "Analysis/folder-retirement-review.md",
  "identityPolicy": "empty-folder",
  "callerReview": {
    "reference": "Analysis/folder-retirement-review.md",
    "sourceSha256": "<full current imported-source inventory hash>",
    "directorySetSha256": "<current Assets directory-set hash>",
    "dynamicPathReview": {
      "status": "reviewed-no-use",
      "reason": "Reviewed known runtime path construction and callers.",
      "evidence": "Analysis/folder-retirement-review.md#LegacyEmpty"
    }
  }
}
```

The source inventory includes imported files and their `.meta` files. The separate directory guard includes every directory below `Assets`, including empty and hidden directories. Both are rechecked before native execution; the exact directory set is checked again after the independent Editor reopen. A new untracked empty directory therefore invalidates the plan.

Planning accepts only an existing leaf directory with no child entries of any kind. Files, child directories, hidden entries and symlinks block retirement. Nested selected paths are rejected. The exact folder `.meta` bytes and GUID are recorded and saved as a before-image. Static source occurrences of the folder GUID or exact path block the plan. Unity also checks imported-asset dependencies under Assets and Packages and fails closed when it cannot read them. The caller review records potentially dynamic path use; `reviewed-no-use` is a caller assertion, not proof that dynamic use is impossible.

The native Editor must confirm `AssetDatabase.IsValidFolder`, load the folder's main asset as `DefaultAsset`, and obtain its actual GUID and nonzero local ID. No local ID is assumed. It checkpoints immediately before and after `AssetDatabase.DeleteAsset`, then a separate Editor process verifies the folder and meta are absent and that protected roots retain their identities.

Recovery is allowed only from a conclusive native deletion checkpoint. It creates only a folder recorded as deleted and empty at plan time, restores its exact `.meta` bytes, then checks the same GUID/local ID in separate Editor invocations and compares the full source and directory guards. An uncheckpointed folder that appears during recovery, a conflicting later edit, an incomplete deletion checkpoint, or any other ambiguous state leaves the transaction `recovery-required` without guessing.

See `schemas/unity-retirement-spec-1.schema.json` for the versioned input shape. Static and unit checks do not substitute for a native Unity fixture run.

To obtain review bindings with the fixed candidate's Python, use the shipped API; the output is read-only and is not a replacement for reviewing actual callers:

```python
from pathlib import Path
from beaver.unity import source_files, directory_guard
from beaver.io import sha, encoded
project = Path("/absolute/UnityProject").resolve()
print(sha(encoded(source_files(project))))  # callerReview.sourceSha256
print(directory_guard(project)["sha256"])  # callerReview.directorySetSha256
```

A selected folder under Resources does not itself define a loadable extensionless file key; all actual child files must already be absent. The caller review still covers folder-path construction, editor writers and dynamic folder use. This operation does not prove that a retired Resources asset key is unused.
