# Native execution finalization and recovery

`native-import` records the observed child-process result even when independent verification raises an exception. Verification exceptions remain failures. Terminal execution results and journal state are written during finalization; an operator interruption remains an interruption after the receipt is saved. This does not turn a partial import into an accepted candidate.

For an older transaction with a stale running journal, use a fresh independent output:

```sh
monkey recover-native-execution --request request.json --expected-request <request-sha256> --out <fresh-recovery-directory>
monkey verify --candidate <old-transaction>/UnityProject --level editor --out <fresh-verification-directory>
```

The first command only observes the pinned old transaction and process table. It does not run Unity, run verification, send a signal, or rewrite the old journal, logs or candidate. The second command independently verifies the existing native files. Neither command reruns decoding or native import. Successful recovery-command execution means a recovery receipt was created, not that the game or native candidate passed acceptance.

The recovery request uses schema `monkey-native-execution-recovery-request/1`, schemaVersion `1`, and exactly these top-level fields:

- `transactionRoot`: absolute old provider-output directory.
- `producer`: `toolId` (`monkey`), original `toolVersion`, original `launcherSha256`, original absolute `entrypointPath`, and its recorded `entrypointSha256`.
- `pins`: exact file hashes/byte counts and the identities below.

`pins` contains SHA-256 and byte count pairs (`<name>Sha256`, `<name>Bytes`) for `nativePlan`, `planIdentity`, `executionJournal`, `runReceipt`, `projectManifest`, `nativeProgress`, `importLog`, and `consoleLog`. It also contains absolute `runReceiptPath`, `sourceManifestSha256`, and `importPlanSha256`. SHA-256 strings must be lowercase. The request itself is pinned by the CLI argument.

The files are resolved from the transaction as follows:

| Pin | File |
| --- | --- |
| nativePlan | native-plan.json |
| planIdentity | plan-identity.json |
| executionJournal | execution-journal.json |
| projectManifest | UnityProject/manifest.json |
| nativeProgress | UnityProject/Analysis/Readback/native-progress.json |
| importLog | import.log |
| consoleLog | console.log |
| runReceipt | absolute runReceiptPath outside the transaction |

The native plan's `sourceManifestSha256` is the **file hash of the exported candidate manifest**. It is distinct from that manifest's internal original-game `sourceManifestSha256`. The manifest's owning `planSha256` is also distinct from the native import-plan file hash. Recovery checks these hash roles separately, including the exact manifest-owned import-plan artifact.

Recovery requires the original producer identity and command to bind the same plan, source candidate, Editor path, output transaction and execution flag. It refuses changed pins, an existing execution result, a non-running original journal, or any still-present/reused recorded PID or process group. The independent receipt reports the outer producer's recorded exit code separately from the Unity exit code. If the old Unity exit code was never recorded, it remains unknown even when the PID/group are now absent and native-progress reports completion. Promotion remains ineligible; original evidence stays unchanged.

The receipt records the recovery tool version and module hash separately in `recoveryProducer`; its `producer` identity describes the original transaction.
