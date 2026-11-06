# Terminal architecture pipeline reassembly

`monkey.code_architecture_reassembly.reassemble(pipeline_root, output_root)`
creates a fresh implementation aggregate and Unity candidate from an already
terminal architecture pipeline. It is intended for read-only lexical
reclassification when a prior collector misclassified generated files. It does
not alter the prior pipeline, module states, manifests, source bytes, or Unity
project, and it does not run Codex, Unity, an Editor, or source programs.

```sh
monkey code-architecture-module-recheck --run /path/to/pipeline/Modules/0001
monkey code-native-reassemble --run /path/to/completed-pipeline --out /path/to/new-revision
```

The global architecture stage is re-pinned using its existing validator. The
pipeline request must match its source, architecture, validation, catalog, and
contract hashes. Every pipeline module must be terminal; the pipeline may be in
`candidate_assembled_unvalidated` or another state whose module list is fully
terminal. Pending, prepared, checkpoint, running, or blocked modules are
rejected before the output directory is created.

For every implementation module, the saved manifest SHA must match both the
pipeline state and the existing module status API. The function calls the
read-only `code_architecture_modules.recheck(task)` and verifies its old
manifest hash, complete class coverage, validated class paths, source-unit and
source-member mappings, and per-file hashes against the prior manifest and
bytes. Only rows classified `generated_unreviewed` are copied into the new
`Implementation/` aggregate. Seed residue and incomplete-contract results stay
missing in the new candidate and appear in the reclassification report.

The new aggregate marks copied code `partial` with an explicit semantic-review
limitation, then uses the normal candidate assembler with the pipeline's pinned
external references and retained layout support list. `reclassification.json`
records all old module manifest hashes, every new per-file classification and
hash, omitted classes, global pins, and the assembled manifest hash. Its
pipeline-compatible status is `candidate_assembled_unvalidated`;
`implementationStatus` is always `partial_unreviewed`. Compile, Editor, and
runtime statuses remain `not_run`. Lexical completeness is not semantic review
or proof of behavior. Each file row preserves the prior class status and the
recheck `completenessDiagnostics` so a genuine missing-contract result remains
distinguishable from a prior classifier error. Each implementation module also
retains the exact `Task/manifest.json` hash and its actual worker `status`,
`outcome`, `responseSummary`, and `unresolved` fields in both the new
Implementation manifest and the Unity candidate manifest. The task receipt is
re-hashed before report publication; missing receipt fields or drift rejects
the new output rather than inventing a fallback summary.

Output must be a fresh directory outside the pipeline, source candidate, and
global architecture stage. Hashes are checked immediately before/after copying
and rechecked against the pipeline request/state and old module manifests
before publishing the report. Any failure removes the new output and leaves
all old records untouched.

Run the focused tests from the repository root:

```sh
PYTHONPATH=src .venv/bin/python -m unittest tests.test_code_architecture_reassembly
```
