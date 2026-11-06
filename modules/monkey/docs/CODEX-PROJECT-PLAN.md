# Full-source C# draft post-processing plan

`monkey.code_postprocess_plan.prepare_plan(candidate, expected_manifest_sha256, max_files=128, max_code_bytes=512*1024)` builds a deterministic, read-only plan from a full-source C# draft candidate. `candidate` is the directory containing `manifest.json`; the required SHA-256 pins the exact manifest bytes. The planner verifies the candidate inventory, the package report, every per-source compact report, original source identities, and all discovered `SourceRecovery/CSharp/**/*.cs` outputs before returning a plan. It never writes to the candidate.

`max_files` accepts 1–4096 and `max_code_bytes` accepts 1 byte–1 MiB. Current full-source class drafts are partitioned by source and weak generated group. Legacy whole-module drafts share batches by origin kind and directory group while retaining an independent source hash/path on every file row; native helpers share their stable origin directory group. Files are then packed in stable path order. A class file is atomic: one file larger than the byte budget receives a single-file batch with `oversizeSingleFile: true` and its full byte count. No file or mapping is truncated.

The result has `schemaVersion: 1` and `kind: csharp-draft-postprocess-plan`:

- `sources` contains each pinned source's `sha256`, `bytes`, `sourcePath`, `reportPath`, indexed/function/field counts, and compact diagnostic counts by code.
- `files` contains every manifest-owned `.cs` file exactly once. All `owner: generated` files enter a batch, including C# outside `SourceRecovery/CSharp`; non-generated owners remain visible as `blocked_owner` read-only rows and never enter a rewrite batch.
- Files outside the compact C# draft tree are `extraCode`. A prior module draft with a `// Source module SHA256: <hex>` header is linked to a manifest-owned `.js`/`.ts` file only when the exact bytes hash matches; it gets `sourceKind: hash-proven-legacy-module` and `sourceWholeModule: true`. Native generated C# helpers with no JavaScript counterpart use `sourceKind: native-generated-CSharp`. No source identity or body is fabricated for unmatched C#; the plan records the missing hash/reason or points to the exact C# bytes for review.
- Each file row has `path`, `bytes`, `sha256`, `sourceId`/`sourceSha256`, `sourcePath`, `reportPath`, group/class metadata, dependency module IDs, `functions`, `fields`, source span references, and bounded diagnostic references.
- `files[].functions[]` preserves `methodId`, source name, function span hash and half-open UTF-8 byte span in `sourceBytes`, function span, target method/path, embedded marker, status, and the compact-detail `detailsRef`.
- `files[].fields[]` preserves `fieldId`, source name/hash/span, target member/path, initialization context and placement, status, and the compact-detail `detailsRef`.
- `batches` contains stable IDs, exact C# `paths`, byte totals, all distinct source IDs used by its files, nonblocking `dependsOn`, dependency references, mapping references, and diagnostic references. A shared legacy batch can carry many source IDs; each file row remains the authoritative mapping to its own source pin. Dependency edges are hints: the queue must remain runnable through dependency cycles and can use source/group order with available context.
- `coverage` reports source reports/modules, generated and blocked files/bytes, extra C# files, function/indexed/auxiliary/field totals, diagnostic count, batch count, exact-once generated-file count, and class-only/unmapped rows.

The planner reads no detailed diagnostic shard bodies. It uses per-source aggregate counts from the compact report and references each function/field's `detailsPath` and `detailsIndex` for later targeted inspection. Exact original-source evidence is represented by `sourcePath`, source SHA-256, and byte spans; callers can use `contextEvidence` plus those references to build a bounded read-only `__Context/source-fragments.json` with full, untruncated source slices. The plan itself does not duplicate source text or insert thousands of diagnostics into a prompt.

The planner rejects manifest/report identity drift, noncanonical paths, case collisions, missing targets, malformed spans, repeated source function or field IDs, inconsistent coverage, and files not owned by the candidate manifest. Weak group labels are carried as labels only; no C# group is filtered. The compact diagnostic counts are source-wide, while detail references remain per mapping.

## Example

```python
from monkey.code_postprocess_plan import prepare_plan

plan = prepare_plan(
    candidate="/path/to/Candidate/UnityProject",
    expected_manifest_sha256="<64 lowercase hex characters>",
    max_files=128,
    max_code_bytes=512 * 1024,
)
for batch in plan["batches"]:
    print(batch["id"], len(batch["paths"]), batch["bytes"], batch["dependsOn"])
```

This output is a queue plan, not code review, compilation, Unity import, behavior validation, or approval to modify project files.
