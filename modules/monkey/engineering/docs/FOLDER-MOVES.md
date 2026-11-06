# Unity folder moves

`assets.move` keeps its existing operation and schema version 1. Existing file
moves remain valid. A request may also include `directoryMoves`, with entries
of the form `{"source":"Assets/Old/Module","target":"Assets/Game/Domain/Module"}`.
The field is optional; a plan may mix file and directory moves when their paths
are independent. Moves are explicit and never infer a destination from folder
names.

Planning records the complete source-to-target map for every directory, file,
file `.meta`, and folder `.meta` in each selected subtree. Every moved folder
and file must already have its Unity metadata. Regular files are bound to their
SHA-256 and byte count. The plan also binds the project's full pre-move asset
inventory, so any edit between planning and execution invalidates it.

The complete transaction is bounded to 10,000 manifest entries and 256 MiB of
selected file and metadata bytes, with at most 100 directory move requests.
The limits include metadata and nested folder entries because the plan carries
all path mappings and the transaction stores verified before-images. Larger
trees must be split into separately reviewed, non-overlapping subtrees.

Before launching Unity, the transaction copies and verifies every moved file
and metadata file under `before/`, then records a `source-bytes-verified`
checkpoint in its journal. The Editor validates all endpoints and source
hashes, creates every target parent through `AssetDatabase`, then moves each
folder with `AssetDatabase.MoveAsset`. It records folder and asset GUIDs plus
all imported asset local IDs before and after the move. The separate reopen
verification returns the same source-to-target identity map and rechecks file
hashes. Python's source audit permits only manifest paths and newly created
target-parent metadata. Failures retain the journal and before-images as
`recovery-required`; this adds no automatic rollback that could overwrite later
manual edits. Recovery must inspect the journal and use a newly reviewed
reverse move plan when safe.

The native job adds `folderMoveManifest` internally; it is derived from and
covered by the immutable Unity plan identity. `directoryMoves` is the public
spec addition. Neither the command route nor existing file-move request shape
changes. A successful native identity readback confirms persistent GUID/localID
preservation; it does not prove dynamic path keys, gameplay behavior, or visual
parity.

Validation includes targeted synthetic planning/guard checks and an actual Unity 6000.6.2f1 isolated-project transaction: a two-directory, six-asset subtree moved, saved and independently reopened with the same eight folder/asset identities, including a Sprite subasset with a negative local ID and a SceneAsset main object. A new reviewed reverse plan independently reopened and restored all recorded source/meta before-image bytes and identity mappings. New-path field readback preserved nested empty strings, null references and the Sprite reference. No game project was modified by this validation; consumer dynamic keys and business correctness remain unverified.
