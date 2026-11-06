# `asset.move` delta checkpoints

The optimization is opt-in through `checkpointPolicy: "move-delta-v1"` in a batch schema 2 spec. It accepts only a nonempty list of `asset.move` steps whose source and target paths are not Unity scenes. Runtime installs, extra read paths, and mixed steps are rejected. Batches without this field keep the existing full-write-set checkpoint behavior.

Planning retains the complete `writeSet` and full content preconditions. It also records the exact initial `Assets` directory set and the target-parent directories the move steps may create. Apply rechecks all content preconditions and the directory set before launching Unity.

The native report describes each checkpoint with `checkpointPolicy`, `checkpointState`, `checkpointCount`, `checkpointPaths`, and `checkpointComplete`:

- `full-initial` hashes the complete write set before executing steps.
- `delta` hashes only the successful move's source and metadata, target and metadata, and metadata for destination parent folders created by that move. The report may serialize the full cached write-set rows for inspection; those cached rows are not a source-state certificate.
- `full-final` hashes every write-set path from disk after all steps succeed or after an exception is caught. Only this state can support success validation or recovery.

The cache stores SHA-256 and byte counts, never modification times. Native `hashReadOperations` exposes the actual number of hashed files. A full report is still serialized after each step, so JSON serialization cost remains proportional to the write-set size. Python also computes a full write-set state after execution and checks the final report against it. It compares source inventory before and after, verifies scene/build-settings and native reopen checks through the existing paths, and rejects unplanned file or directory changes.

Recovery requires a matching `full-final` report, complete write-set coverage, no unplanned paths, and equality between the native report, Python's recorded post-state, and the current source. It then rechecks every before-image and refuses later edits before calling the native restore path. A delta-only report, missing final report, incomplete path list, or mismatched source state is blocked without a guessed restore.

## Native fault fixture for integration

Use a private Unity project with two or more imported non-scene source assets and explicit empty destination parents. An `AssetModificationProcessor` in the fixture should reject the second move after the first has completed. Verify that the caught failure emits a `full-final` report matching the mixed partial state, then call public `recover` and confirm the original source and metadata bytes plus GUID identities are restored.

For the negative case, make native report persistence fail after a delta checkpoint and prevent the catch path from writing a complete `full-final` checkpoint. Confirm public recovery refuses the transaction before any Editor restore. Also make a later manual edit after a valid `full-final` checkpoint and confirm recovery rejects it. These tests distinguish native execution and persistence behavior from the Python unit tests, which only validate the checkpoint contract.

## Local validation scope

An installed candidate completed 128 actual moves with a 514-path write set. Explicit native hash reads decreased from 33,886 (default) to 1,120 (opt-in), with the same Python post-state hashes. Independent bulk collection checked moved GUID/localID/type/name pairs. A native project callback refused the second of three moves; full-final partial recovery restored the before-state. A checkpoint persistence fault prevented full-final evidence and public recovery refused it; a separate reviewed reverse plan plus native empty-folder cleanup restored the private fixture. Later edited text bytes also blocked recovery. These are small synthetic assets; full-report serialization still scales with the write-set size and this is not evidence of arbitrary large-batch throughput.
