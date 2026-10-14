# Signal Garden — grea reference game 1.0.1

Collect five mint signals, pause/resume, finish a run, return to the menu and play again. Completed runs persist between launches. Original geometric UI and synthesized tone; game and framework sources are MIT licensed. Unity runtime, built-in font and official Unity packages retain their own licenses.

This source directory is maintained inside grea. Materialize it with `./bin/grea legacy unity_reference prepare --output <new-directory>` before opening: the helper embeds the canonical framework packages instead of maintaining duplicate implementations here. A distributed ZIP already contains those packages and needs no grea checkout.

Use **Unity 6000.6.2f1** with macOS support, URP 17.6.0, uGUI 2.6.0 and Test Framework 1.8.0. The Editor restores official dependencies using Packages/manifest.json and packages-lock.json. Library, Temp, local credentials and preinstalled private packages are not distributed. Do not open this unmaterialized repository directory directly in Unity.

From a restored project:

```sh
unity test . --mode EditMode --output /absolute/new-evidence/editmode.xml --timeout 300
unity test . --mode PlayMode --output /absolute/new-evidence/playmode.xml --timeout 300
unity build . --target StandaloneOSX --execute-method Grea.Reference.Editor.ReferenceBuilder.Build --output-path /absolute/new-build/SignalGarden.app --timeout 600
```

Build produces an arm64/Mono macOS Player with Medium managed stripping and a build receipt. Open `Assets/Reference/Scenes/Reference.unity` in Editor. `ReferenceBuilder.Author` creates only missing initial reference outputs; its recorded content must match on repeat. It will not overwrite human-edited assets. Existing checked-in assets do not require regeneration to build.

Controls: click START RUN, then collect the moving mint signals. PAUSE or Escape pauses; RESUME continues; RETURN TO MENU cancels the current run. PLAY AGAIN starts a fresh run. Losing focus pauses gameplay. QUIT closes the application.

Normal saves are under this application's persistent data path in `saves/signal-player`. QA uses a separate namespace. Launch with `--grea-qa-root /absolute/project-evidence/qa --grea-run-id first` to store QA saves in `saves/signal-qa` and a bounded trace in `runs/first.jsonl`; use a new run ID after reopening the same save root. Trace records state transitions, counts, build ID, focus, actual engine pointer coordinates/raycast hits and this game's audio mixer signal; no account data, screen capture or system audio is collected. Do not reuse a trace filename.

Invalid/unknown saves and pending interrupted writes are retained and reported, never silently reset. Five successful collections are required for a win; only the final collection commits the new completed-run count. Disk failure leaves the win unawarded. This is a local reference, not a leaderboard or production save migration system.

The source ZIP and player archive are generated local artifacts, not a GitHub release. Codesigning/notarization, other platforms, IL2CPP, existing-game parity and multi-project adoption are separate validation scopes.

See THIRD_PARTY.md for dependency notices and framework.lock.json for the exact own-package source identities.

本分支框架锁为 0.2.1；2026-10-14 的 1.0.1 独立恢复 Player 已通过 macOS arm64/Mono 实玩、关闭重开和失焦回归。历史 1.0.0 证据保留，实际构建身份与限制见 grea 文档中的本次验收摘要。
