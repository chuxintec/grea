# Unity code-source evidence

`monkey.unity_code_sources.inspect` creates a bounded, read-only report for one fixed Unity code input. Its data envelope records the original `source` path, SHA-256, byte count and family; type/method ranges; exact provider identity; method-body evidence and call edges; outputs and diagnostics. Every report sets `sourceCodeExecuted=false`.

## Unity Mono

For `family="mono"`, the source must be a managed PE with a valid CLR header. The module checks PE/CLI structure before invoking ILSpy. Pass `provider=<absolute executable>` or set `MONKEY_ILSPY_PROVIDER`; the module does not discover a provider by walking to a neighboring checkout, so wheel installs do not silently depend on the source tree layout. The provider receives `--disable-updatecheck --nested-directories -p -o <owned output> <exact private source snapshot>`. This statically decompiles the assembly; the original assembly is never loaded or run.

The decompiled project stays under `SourceRecovery/Decompiled/Mono/`, outside Unity `Assets/`. `methods[]` entries with a body use status `decompiled_body_not_verified`; `bodyEvidence` points to the exact decompiler source file, lines, byte count and SHA-256 and sets `verifiedAgainstOriginalIL=false`. Unique within-assembly method symbols receive `exact-symbol-unique` call edges. Unresolved, ambiguous and external calls stay unresolved. The report always leaves `implementedMethods=0`: extracted decompiler bodies are source evidence for a later restore/compile/behavior stage, not an adopted target implementation.

```python
from monkey.unity_code_sources import inspect

result = inspect(
    "/path/to/Assembly-CSharp.dll",
    "/private/tmp/mono-source-candidate",
    expected_sha256="<exact source SHA-256>",
    family="mono",
    provider="/absolute/path/to/ilspy",
)
```

Passing a metadata or method-map file with a Mono assembly is rejected; those evidence inputs belong to the separate IL2CPP-WASM route. Outputs are create-only. The source, provider and generated-file size budgets are enforced before a report is written.

## Isolated C# candidate

`monkey.unity_code_candidate.prepare_candidate(source_report, output, *, expected_report_sha256, method_ids=None)` creates an isolated `CandidateDraft/CSharp/` tree from decompiled `.cs` files. The report hash, original assembly snapshot, per-file SHA-256, method signatures, and body hashes are rechecked before copying. Selecting one method includes its whole decompiler source file, and the report describes all declarations copied with it. The output is never placed under Unity `Assets/`.

`draft_closed` means the selected parsed methods all have body evidence and their observed calls resolve within the selected files. It is still only draft source: original IL equivalence, unobserved reflection/dynamic calls, external dependency closure, and game behavior remain unproved. `draft_incomplete` preserves source in the isolated draft tree while reporting metadata-only declarations, unresolved calls, or relevant parse diagnostics. Both statuses set `implementedMethods=0` and state that the original assembly was not executed.

The module fixture validates the candidate stage end to end using a self-authored Mono DLL: ILSpy source is copied into the candidate tree, compiled as an independent target DLL with the Unity C# SDK, then invoked by a separate self-authored harness against fixed expected results. Only this generated fixture candidate and its harness run; the input DLL is never loaded or executed. A fixture interface declaration also verifies that metadata-only members stay in `draft_incomplete`.

## IL2CPP-WASM

For `family="il2cpp-wasm"`, the module does not decompress or disassemble a WASM payload. It accepts a raw source binary plus optional metadata and method-map files only when each supplied file has its own expected SHA-256. Metadata or method-map claims that bind another source or metadata hash fail closed. Existing `evidence_queries.query_methods` reports are accepted; their `sources[]` identities are preserved, but those reports do not by themselves prove that a method index belongs to the selected WASM revision.

Rows without exact source and metadata SHA links remain `metadata_only` and do not count as recovered methods. A caller-supplied `bodyEvidence.text` with a matching text hash and exact source/metadata binding is retained as `decompiled_body_not_verified`; it does not become implemented C#. Function indexes are never normalized across modules or revisions. Non-WASM, compressed or otherwise opaque inputs retain their identity and diagnostics without decompression.

The route explicitly rejects a dummy `.dll` without a PE CLI header. No `DummyDLL`, guessed IL2CPP layout, inferred function index, source-game WASM, JS, or managed assembly is executed.

## Evidence and limitations

The legal Mono fixture is self-authored in `.private/v060-csharp-20261026/unity-code-sources/mono-fixture/OrderModule.cs`, compiled with the installed Unity 6000.6.2f1 SDK, then statically inspected with the configured ILSpy provider. It exercises a branch, a loop, an expression-bodied method, a cross-class call and an interface declaration. Fixture source, DLL, source report, candidate report, target build, harness, and hash receipts stay under `.private/`.

This validates the local Mono path, candidate-source identity, target C# compilation, and fixture behavior. No real Unity Mono game assembly was supplied for this module. The IL2CPP-WASM tests use a synthetic WASM header and hash-pinned metadata/method-map evidence; they validate identity and mismatch handling, not recovery of an original IL2CPP method body. No real game source candidate has been built or behavior-tested.
