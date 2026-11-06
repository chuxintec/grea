# Recovering a completed post-process event stream

`monkey.code_postprocess.recover_completed(prepared_root)` is an offline recovery entry point for a narrow crash window: the child emitted a complete terminal `turn.completed` event and its final `agent_message`, but the supervisor disappeared before writing `final-response.json` and the normal manifest. It does not call Codex or infer an operating-system exit status.

The function takes the existing `GLOBAL_LOCK`, then checks the original `process.json` record. The record must still say `running`, its PID must be absent, and the global active-process marker must identify that same PID. A live or reused PID is rejected; the function never signals or kills it. The request must be in `prepared` or `checkpoint`, with a stable `runId`, and no final receipt may exist.

Before finalizing, recovery verifies the pinned Codex executable hash, candidate manifest and selected source bytes, request identity, immutable context bytes and permissions, writable workspace scope and limits, and isolated Git state. The event file must be bounded, newline-terminated valid JSONL, contain no `turn.failed` or `error`, end with exactly one `turn.completed`, and have that event immediately follow an `item.completed` `agent_message` whose text is a JSON object. If a saved `final-response.json` exists, it must equal that terminal message.

Normal runs and recovery share `_finalize_saved`. It applies the ordinary actual-diff accounting, selected-path comparison, response schema, workspace/context/source integrity, Git boundary, diff and output budgets, and receipt construction. Recovery writes an immutable copy of the original request and process records plus hashes of those records and the event stream. It records `exitCode: null`, `returnCode: null`, `completed-event-recovered/exit-not-recorded`, and an observed timestamp. The finalized model output remains `partial` for review even when its declared response says `complete`; this is not evidence that the Codex CLI exited successfully.

A fixed replay returns the saved receipt only after rechecking the recovery copies, event/response identity, candidate sources, context and Git pins. Any pin drift rejects replay. The request becomes `finalized`, so normal `run()` cannot invoke or resume that task.

## Architecture module bridge

`monkey.code_architecture_modules.recover(output)` is the public module-level continuation. It verifies the module/source/context pins and exact selected class paths before calling the worker recovery API, then sends the result through the same `_materialize_result` path used by `run()`. It adds the worker recovery record to the module manifest and keeps compilation/runtime at `not_run`.

The bridge also requires the global active-process marker to match the recorded PID and attempt (and `runId` when that field is present). It preserves a read-only snapshot and hash of that marker. The session ID must be present and unique in the complete event stream; it must match the worker receipt and finalized request, even when the original process record had no session ID.

`recheck()` remains read-only. It permits the exact `completed-event-recovered/exit-not-recorded` case only after checking the worker recovery receipt, original request/process copies, current process bytes, event and response hashes, session identity, active-process snapshot, actual workspace changes, declaration paths, and source/context/Git boundaries. Ordinary nonzero exits and other stop reasons remain rejected. A replay does not rewrite the worker receipt or module manifest.
