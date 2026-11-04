# v0.7.0 development: public owned Player observation

Candidate0.7.0.dev1 extends existing `debug start`, not `player run` or the QA process model. It adds no input backend, test framework, game callback or arbitrary argv/environment execution. Existing pinned consumers and published0.6.0 artifacts remain unchanged.

The public call is additive:

```sh
beaver debug start --manifest ARTIFACT.json --expected MANIFEST_SHA --out FRESH_RUN_DIR --duration 1200 --observation-spec OBSERVER.json --expected-observation OBSERVER_SHA --deadline-utc 2030-01-01T12:00:00Z
beaver debug inspect --session FRESH_RUN_DIR/session.json
beaver debug stop --session FRESH_RUN_DIR/session.json
```

Use a current authorized UTC deadline; the example is only syntax. The duration and deadline use the earlier bound. The observation spec follows [the closed schema](schemas/debug-observation-1.schema.json). Only its observation-root flag name is caller-defined; its value is always the fresh run directory. Optional bundle identity is a literal precondition. The observer must keep its own file namespace and must not overwrite beaver's session.json, status.json, observation-spec.json, control or log files. An observation session also supports its own root/STOP file; public debug stop is preferred.

The caller selects an authorized fixed artifact and an authorized project-local evidence directory. Project path policy, observer implementation, business assertions and human foreground/input coordination remain project-owned. The tool adds no foreground-activation or input-dispatch API; the project owner schedules any GUI launch safely. A start result identifies the detached worker; obtain the actual app PID from debug inspect/status after launch, and never treat workerPid as the app PID.

Each cold start uses a new output directory and process. The worker checks the manifest before the async handoff and again immediately before app execution, snapshots the SHA-bound observation spec, records actual argv/cwd, separates stdout/stderr from Unity's log, and verifies the artifact after exit. It uses only its own Popen child for termination and wait/reap. A caught worker failure still cleans up that child. Reaped and independently absent PID are distinct facts. Natural exit, requested stop, expired budget and gameplay results remain separate.

The existing qa prepare/launch/collect spec, typed configuration/profile bindings, immutable app clone and owned-instance guards are unchanged. Existing QA-only consumers need not switch to this observation mode. No public release, global installation, automatic pinned-runtime replacement or game/profile migration is part of this candidate. A fixed runtime must be installed independently of source worktrees and temporary host plugin caches; the provider installation owner records interpreter/dependency provenance and retention conditions.
