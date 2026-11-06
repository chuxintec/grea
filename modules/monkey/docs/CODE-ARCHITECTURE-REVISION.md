# Native architecture candidate revision

`monkey.code_architecture_revision.revise_native_candidate(candidate_root,
expected_manifest_sha256, revision_root, expected_revision_plan_sha256,
output_root)` applies a pinned set of C# changes to a new candidate directory.
It accepts only an unadopted candidate whose manifest identifies
`native-architecture-assembly`; an ordinary candidate or adopted project is
rejected. It never edits the base candidate or a formal project.

For revisions containing multiple helpers, the complete pinned base's root
namespace is verified once per invocation and reused for their owner checks.
The cache is local to that invocation; every base file hash is still verified
before any candidate is copied.

The versioned `revision-plan.json` schema is
`monkey-native-architecture-revision/1` with `baseManifestSha256`,
`architecturePlanSha256`, `revisionId`, `files`, and optional
`sourceEvidencePins`. Every file row has exactly `path`, `artifactPath`,
`oldSha256`, `newSha256`, `bytes`, `classId`, `module`, `layer`, `role`, and a
non-empty `provenance` object. `role` is `replace` or `new-helper`; only a new
helper may use `oldSha256: null`. Revision artifacts are bounded and the
revision directory may contain only the plan and its declared artifact files.

All base candidate files must still match the pinned standard manifest before
copying; a manual edit, missing file, symlink, unowned file, stale source
evidence pin, artifact mismatch, or output overlap rejects the revision. Every
replacement must target a generated architecture class and repeat its original
classId owner. A helper requires a new explicit classId and a path whose layer,
module, namespace suffix, and type name agree with its plan row. Helpers receive deterministic
paired Unity `.cs.meta` files; an existing companion meta is preserved byte for
byte. Duplicate GUIDs are rejected.

Namespace ownership is read from verified architecture-owned C# files, not
guessed from the candidate's external namespace label. Replacements must keep
their original exact namespace and declaration kind. New helpers must use the
exact namespace root derived from the candidate's verified architecture-owned
C# files, followed by the declared layer/module. This supports filling an
otherwise empty module while rejecting mixed or guessed roots. If the candidate
manifest already reserves a `classId` in `classPaths`, a new implementation may
only fill that exact path. Present `classPaths`, `implementedClassPaths`, and
`missingClassPaths` are synchronized in the output manifest.
The existing module checker enforces block namespaces, namespace-level type
placement, and its established Domain/Gameplay dependency rules after comments
and C# literals are stripped.

Only C# files under the five architecture layers are accepted. Domain and
Gameplay revisions reject the established Unity engine/editor references,
`dynamic`, and untyped string-to-object dictionaries. Other identifiers such
as a domain property named `Time` or `System.Numerics.Vector3` are not rejected
by a wider keyword list. The check is lexical, not compilation. JSON, resources,
packages, project settings, scenes, prefabs, and all other files are copied
byte-for-byte. Package declarations, Editor tooling, and helper generation
outside the declared C# revision rows are not supported by this API.

The output is a new standard `candidate_snapshot` candidate with revision pins,
before/after file identities, ownership, and provenance in its manifest. Its
implementation status remains `partial_unreviewed`; compile and runtime stay
`not_run`. It performs no AI, Unity, Editor, package installation, or global
apply operation.

Run the focused tests from the repository root:

```sh
PYTHONPATH=src .venv/bin/python -m unittest tests.test_code_architecture_revision
```
