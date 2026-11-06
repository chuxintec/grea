# Whole-project Codex batch processing

This legacy per-file strategy was superseded for the active v0.6 recovery by the architecture-first human decision on 2026-10-27. Its queue stopped safely after 46 batches / 3,476 reviewed files; remaining records and all source/results are retained. A queue marked `strategySupersededBy` is readable but rejects run/resume/recheck. The current goal is a versioned five-layer architecture, semantic type/member ownership, whole-module implementation and integrated native Unity entry, not completion of the old 6,445-file checklist. See `PLAN.md` and the current internal planning reference C# plan. The CLI contract below remains historical/compatible for other explicitly authorized queues; it does not authorize resuming the replaced queue.

This is the v0.6 delivery workflow after deterministic export. The previous two-method pass is connector evidence only. Original candidates remain immutable; a separate complete project contains copied resources, scenes, prefabs, configuration, source maps and the progressively revised C# files.

```sh
monkey code-project-prepare --candidate /path/to/export --expected-manifest <sha256> \
  --out /path/to/new-project-run --batch-max-files 128 --batch-code-bytes 524288
monkey code-project-run --run /path/to/new-project-run
monkey code-project-status --run /path/to/new-project-run
monkey code-project-resume --run /path/to/new-project-run
monkey code-project-pause --run /path/to/new-project-run
# Wait until status is paused and the recorded child has exited, then:
monkey code-project-configure --run /path/to/new-project-run --batch-seconds 3600 --idle-seconds 900
monkey code-project-resume --run /path/to/new-project-run
```

Preparation discovers every manifest-owned C# file, without SDK/engine filtering. The known full-JS function index remains its own denominator; older named drafts and generated native helpers are additional actual code files. Exact original modules are supplied when their content hash matches the owning inventory. Absent source context is explicit and never fabricated. Source/group ordering and dependency hints organize batches; dependency cycles do not turn into queue deadlocks. Oversized files remain whole and are marked as such.

`run` continuously executes all ready batches through one CLI at a time. Batch limits protect against stalls and do not limit the project to one session or one module. Each attempt can resume its exact saved session within its remaining child-time budget. Failed files get a finite retry window while independent work continues. Authentication, quota and real permission errors stop the queue with unprocessed work visible; they do not trigger alternate providers or model downgrades. `resume --retry-failed` explicitly grants exhausted failed batches another finite retry window without overwriting their old attempts.

The project default is 3,600 seconds per attempt, with a 900-second no-output limit. The first real 104-file / 501,624-byte batch exhausted the earlier 1,200/180 settings before its full structured review was returned. A pause request is asynchronous: its receipt does not claim the child stopped. The worker saves its exact session and workspace before the supervisor exits. Budget changes require the supervisor lock to be free and the child to have exited; they retain cumulative execution time, resume counts, attempt numbers and model configuration. They do not retroactively declare interrupted files reviewed.

Each batch has independent copied code, immutable source context, the prompt/schema, session/events/stderr, per-file review results, usage and actual patch. Every required source-function ID must appear in the per-file review coverage. Known field IDs are also accepted. Additional indexed nested-function IDs are accepted only when they belong to the same pinned source and their full byte spans lie inside source fragments supplied for that file; Missing required IDs still fail. Unrecognized additional IDs are excluded from verified coverage, retained verbatim as metadata issues, and downgrade the file to partial; they never count toward another file. A file is accepted only with a concrete result, preserved declarations/markers and valid output boundaries. Unchanged files need code-specific findings. Partial files can be fully reviewed while retaining unknown semantics. An explicit `originalLogicPreserved=false` with concrete semantic limitations remains false in the report; it does not turn an actually analyzed draft into an unexamined file. This is not a claim of equivalence. Explicit blocked/unexamined results or missing required coverage remain unprocessed. Missing review coverage stays unprocessed; it is never counted by clearing a queue entry.

Accepted edits integrate serially into the complete project through a replayable journal. Existing unrecorded edits are refused. A crashed supervisor can consume a finished batch or resume its precise checkpoint; a still-live or unknown child is not killed or duplicated. Source provenance and original exports are protected; no hard links share writable code with them.

`state.json` and compact `progress.jsonl` carry durable status. Final `Analysis/Code/project-codex-postprocess.json` distinguishes actually processed, unchanged, partial, failed/blocked and pending files. The candidate manifest hashes actual revised bytes. Pending, running or unexamined blocked files prohibit a whole-project completion claim. Even full processing does not prove compilation, gameplay or original-game equivalence. No source JS/WASM/assembly, Editor or Player is executed by this workflow.

`code-project-recheck --run ...` revalidates completed saved reviews after a validator fix without another model call. It requires a stopped supervisor/child, retains attempt counts, checks derived payloads against the hashes recorded at the time of review, and never treats a pending pause or missing review as completed.

The project workflow uses the fixed per-batch JSON review ledger to avoid repeating all long records in the final CLI response. The worker archives and hashes that artifact, validates every selected record, and still requires actual code/source analysis. `code-project-pause --after-current-attempt --run ...` finishes the active attempt before pausing for a supervisor upgrade; it does not interrupt the working model.
