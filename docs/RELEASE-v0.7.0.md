# monkey v0.7.0

This MIT-licensed release consolidates the stable 0.7.0.dev9 implementation into the `monkey-native` Python package and `monkey` CLI. It carries the existing Cocos-source static Prefab workflow, source/native identity checks, saved-selection dependency closure, font and Spine static-resource handling, runtime presentation helpers and supplemental SDK/code declarations. The separate 0.8 Unity-source development line is preserved and excluded from this release increment.

## Installation

Use Python 3.11+ and verify the exact wheel SHA from SHA256SUMS before installing into an isolated environment. Runtime dependencies are Pillow 12.2.0 and pypinyin 0.55.0; texture2ddecoder 1.0.6 is optional. Node.js is required only for the JavaScript code graph/lowering workflows. Unity 6000.6.2f1, Creator 3.8.8, external parsers/SDKs and original source inputs are explicit operation prerequisites and are not included. The command-line product has no desktop icon installation or engine/plugin auto-activation.

```sh
python3 -m venv .monkey-env
.monkey-env/bin/python -m pip install monkey_native-0.7.0-py3-none-any.whl
.monkey-env/bin/monkey --version
.monkey-env/bin/monkey capabilities --json
.monkey-env/bin/monkey freeze-native-selection --help
.monkey-env/bin/monkey audit-native-code-dependencies --help
```

## Contracts and limits

Existing compatibility toolkit IDs, source pinning, namespace/file ownership, candidate contracts and exit-code behavior remain intact. Source recovery, native import/save/reopen, static rendering, runtime mutation/input, consumer adoption and gameplay remain separate assurance layers. Unknown methods and unavailable source fields are not fabricated. Missing native MonoScript inventories are explicitly not_run, never a proven zero-script DLL. SDK provenance declarations do not authorize or prove consumer SDK replacement, migration or runtime behavior.

The bounded source/target matrix is in SUPPORT-MATRIX.md; selected handoff and code/SDK evidence are documented in providers/NATIVE-SELECTION.md. Representative native evidence is reused without rewriting source payloads or re-exporting game projects. Isolated distribution verification is recorded in validation/2026-11-04-v070-release.md. No universal engine/version compatibility, complete script recovery, original visual parity, physical input, Player build or remote business behavior is claimed.

The wheel and source archive exclude private game originals/candidates/logs, external engine/SDK binaries and credentials. The release neither changes existing game wrappers/provider locks nor upgrades a global installation. Third-party license texts remain included; external runtimes/fonts retain their own licensing conditions.
