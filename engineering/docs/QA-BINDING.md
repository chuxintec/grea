# Bind QA input to an existing macOS instance

The QA binding commands attach to one explicitly owned, already running QA instance and one of its visible windows. They use the existing [QA runtime](QA-RUNTIME.md) owner, project, build, profile and run records. Preparing a build, inspecting an instance and binding a window do not launch an application. Launching remains a separate explicit `qa launch` operation.

Two explicit backends are supported: `macos-native-ax-pid/1` preserves the original event-only path; `macos-native-ax-pid-pointer-sync/1` adds guarded system-cursor positioning for Unity input. There is no automatic fallback between them. It requires macOS, a local clang SDK for compiling the small source-bound controller, and existing Accessibility permission. Input also checks existing event-post permission; window capture requires the relevant existing macOS capture access. Permission failure returns a blocked result. The implementation does not request permission dialogs, modify TCC, sign an app, install globally, or select a replacement application.

## Public commands

```sh
beaver qa inspect-instance \
  --project example --build candidate-01 --profile test-01 \
  --expected-owner <owner-sha256> --run run-01 --out out/instance-01

beaver qa bind \
  --project example --build candidate-01 --profile test-01 \
  --expected-owner <owner-sha256> --run run-01 \
  --backend macos-native-ax-pid/1 --window <owned-window-id> \
  --out out/binding-01

beaver qa input \
  --session out/binding-01/qa-binding.json \
  --expected-session <binding-file-sha256> \
  --spec click.json --expected-spec <click-file-sha256> \
  --out out/click-01
```

Each output directory must be fresh and independent of protected input locations. Hash arguments bind exact file bytes; reformatting a JSON file changes its digest. `inspect-instance` and `bind` require every owner/run argument shown. `bind` defaults to the stated backend and accepts optional `--window`; omission succeeds only when exactly one eligible window exists. Multiple windows require an explicit owned window ID. Unsupported backends are rejected without fallback.

`inspect-instance` writes `qa-instance.json`. Its `process-verified` result proves the bounded process checks, not a GUI session: `attachAllowed` remains false and window ownership is not yet observed. `bind` writes `qa-binding.json` and `qa-bind-result.json`, returning the session path and `sessionSha256`. It compiles a controller into that binding output and records both source and binary hashes. An unavailable or ambiguous window returns a blocked binding result.

## Instance identity and session lifetime

An accepted instance binds all of the following:

- The immutable owner SHA and exact project, build, profile and run IDs.
- An owned `qa launch` record still marked running, its controlled executable, cwd and exact log path.
- Launch-time kernel birth evidence: PID, start seconds/microseconds, unique identity and parent PID. Capture must have observed the owned child or its explicit `sandbox-exec` wrapper with matching arguments and typed environment bindings.
- Current kernel process identity, the same executable file, unchanged executable SHA, exact ordered argv and live typed profile/config environment values.
- The executable's device/inode and its own bundle metadata, including Bundle ID and `Info.plist` SHA. Full bundle identity is checked during inspection and binding.
- One visible layer-zero CG window owned by that PID, uniquely mapped to an AX window using owner, geometry and available title evidence.

Executable spelling is checked by actual same-file identity rather than case-folded names. Native bundle checks read `Contents/Info.plist` beside the kernel-resolved executable; a LaunchServices registration or another app with the same Bundle ID is not an instance identity. Raw kernel argv/environment are checked transiently and are not emitted by these inspection reports.

A binding expires five minutes after creation. Each `qa input` verifies the exact session digest, current tool/backend identity, controller path/source/binary hashes, run-record hash and live instance identity. Expiry, process exit, changed birth, changed executable or bundle metadata, changed profile binding, or changed run record invalidates the session. A fresh binding can attach to the same still-running explicit run; rebinding does not start an app or extend the launch operation's time budget.

Legacy runs with missing or `unknown` owned birth evidence are refused. Finding a matching executable path, PID, name or window later cannot upgrade that historical record to strong provenance. A new run requires an explicit launch under the existing QA runtime contract. There is no `getApp`, `open`, LaunchServices or same-name fallback.

## Closed input specifications

The input spec contains only its operation and the fields below. It cannot override PID, birth, executable identity, Bundle ID or window ID from the session. Unknown fields and invalid types are rejected.

| Operation | Spec fields | Behavior |
| --- | --- | --- |
| `observe` | `{"operation":"observe"}` | Verify the selected window and read its bounded AX snapshot. |
| `click` | `operation`, finite numeric `x`, `y`; optional `button` (`left` or `right`, default `left`) | A mouse-down/up pair directed to the bound PID and window. |
| `drag` | `operation`, `points` containing 2–64 exact `{x,y}` objects; optional `button` | Down at the first point, dragged events through the remaining points, then up at the final point. |
| `key` | `operation`, `key` | A closed key-down/up pair. Allowed keys: `return`, `escape`, `space`, `tab`, `left`, `right`, `up`, `down`, `backspace`, `command-q`. |
| `text` | `operation`, nonempty `text` of at most 256 UTF-16 code units | Unicode keyboard events directed to the bound PID; no clipboard or pasteboard use. |
| `close` | `{"operation":"close"}` | Press only the selected window's own accessible close button. No process signal or termination fallback. |
| `screenshot` | `{"operation":"screenshot"}` | Capture only the bound window to the output directory, with owner/identity observation before and after. |

Example `click.json`:

```json
{"operation":"click","x":200,"y":184.5,"button":"left"}
```

Coordinates use `selectedWindow.bounds`: origin at the window's top-left, x increasing rightwards and y downwards, including the title bar. They are not client-area coordinates and must not be guessed from screenshot pixel dimensions. Use the returned CG/AX coordinate units and verified window geometry. Points outside `0 <= x < width`, `0 <= y < height` are refused; a changed geometry during event preparation also blocks that event.

The mouse controller constructs an explicitly window-numbered NSEvent, measures its public conversion, and reconstructs it at most twice until the resulting payload matches the requested window-relative point. Failure to converge is blocked. It does not use `CGEventSetLocation`, private routing fields, a fixed screen-height correction or a global posting fallback. Results expose `coordinateEncoding`, `constructionAttempts` and numeric payload evidence. These describe encoding, not application handling.

Before each CG event and after the operation, the controller rechecks process birth, current-user ownership, executable device/inode, executable-owned Bundle ID, selected-window ownership, unambiguous AX/CG mapping and selected-window focus. Input may raise and focus that same bound window. All CG input uses `CGEventPostToPid`. Partial gestures remain partial: if a later check fails after a down event, the controller reports the count already posted and does not send an unguarded cleanup event elsewhere.

`observe` returns `axSnapshot` with at most 128 nodes, depth 8 and a bounded read budget. Nodes include an observation index, role, optional bounded title, relative bounds and static-text value where available. Strings are limited to 256 UTF-16 code units. Editable and secure fields do not expose values; raw AX pointers are never returned. Read failures or truncation produce `partial` snapshot evidence. Node indexes are for observation, not stable selectors or an alternative input contract.

`close` records `axActionsAttempted` and `axActionsPerformed` separately from CG `eventsPosted`. It can report `windowCloseObserved`; closing a window need not terminate the application. `command-q` uses only the fixed Command+Q combination and depends on the application's own event/menu handling. Neither operation establishes that saving completed. If a successful close or posted Command+Q is followed by observed process disappearance, the native result can be `performed_exit_observed`; that old session is no longer usable.

`screenshot` invokes the system capture tool with only the explicitly bound window ID. It returns `window.png` and its hash after successful before/after checks. Capture failure or owner uncertainty is blocked; there is no global-screen fallback. A screenshot represents the capture interval, not an atomic lock on the process or window.

## Results and acceptance boundaries

`qa input` writes `qa-input-result.json` with the session/spec hashes, PID/unique identity, window ID, `launchPerformed: false`, native result and limitations. Typical native outcomes are `verified` for observation, `performed` for issued input, `performed_exit_observed` for the bounded normal-exit case, and `blocked` with an error code. A blocked result may still contain nonzero `eventsPosted` or AX action counts from a partly completed operation; it is not proof of zero effects. A controller failure or timeout can leave no complete native receipt. Missing counts likewise do not prove zero input; inspect the owned instance before retrying.

`inputDelivery: posted-to-pid-not-business-acceptance` means exactly that the controller issued events. It does not prove a button callback, drag response, entered text, login, server action, save, normal exit or successful resume. Those require the consuming app's own state/log evidence and, where relevant, visual or gameplay validation. This document does not claim uncompleted consumer acceptance.

Process/window checks and OS event posting are separate operations, not an atomic capability. A target can exit, change or replace a window between checks and a post. The controller narrows this interval through per-event and final verification, reports failures and partial effects, and never claims an atomic guarantee. Existing permissions and a valid binding also do not enlarge the authorized application or data scope.


## Explicit system-cursor synchronization

Select `qa bind --backend macos-native-ax-pid-pointer-sync/1` for a Player which reads physical pointer state, such as the verified Unity 6000.6.2f1 input probe. The choice is fixed in the session; ordinary click/drag specs remain unchanged. Only this backend's mouse gestures add the native `cursorMode: sync-owned-window`. Other operations never relocate the pointer. The default backend does not provide this positioning and failed actual Unity input acceptance when the system pointer was elsewhere.

This mode changes the system-wide pointer position. It first verifies the exact foreground process/window, unchanged geometry, the first visible layer-zero window covering the intended point, and the actual AX hit element's same PID and exact selected AX window. Transparent system overlays are recorded; an actual foreign AX hit or an unknown mapping blocks before positioning. It then moves the pointer directly to the selected window's global point without posting a global mouse event. Click/drag events still use only `CGEventPostToPid` and window-relative measured payloads. No global event fallback, app launch, permission change, or pointer restoration to another location occurs. Use exclusive desktop ownership; user or application pointer movement stops the gesture.

Each point records `cursorSync` and the bounded `cursorSyncHistory`, before/after/target positions, attempted/completed state and AX hit evidence. Drift, process/window/focus changes or an unknown outcome remains blocked/partial with all known effects retained. A positioning attempt alone can change global state even when `eventsPosted` is zero; timeout receipts mark the cursor state possibly changed. Kernel checks, AX hit tests, pointer changes and event posting remain non-atomic. Actual callbacks, saves and product behavior require separate observation.

Window screenshots explicitly request PNG without shadows (`screencapture -o -t png -l <bound-window>`). Click coordinates are logical window points including the titlebar; screenshot bitmap pixels may use Retina scale. Compare the captured dimensions with the reported logical bounds before choosing points. Historical fixed18 captures contain shadows and require padding as well as scale correction.


Known consumer boundary: the fixed19 self-owned Unity probe proved IMGUI/legacy callbacks, text and drag. FoodStreet App40 uses Input System1.20.1, activeInputHandler1 and uGUI InputSystemUIInputModule; its fixed19 pointer-positioning guards passed, but login/text still produced no observed action. That input stack remains unaccepted while a matching neutral fixture is investigated. No QA action pump, application patch or global event fallback is part of this backend.


The matching InputSystem1.20.1/uGUI fixture isolated the fixed19 failure: button transitions reached the device, but pointer position remained(0,0). The explicit synchronization gesture now posts one guarded window-relative `mouseMoved` after initial positioning and before the first down event. New Input System position is initialized before hit-testing the click; subsequent drag points keep the existing synchronization and dragged-event route. This adds one posted event only to the opt-in synchronization path (click3; N-point drag N+2); event-only defaults remain unchanged. Neutral uGUI callbacks/text and held-button motion have been observed; fixed-package and product acceptance are separately recorded in PLAN. No application action pump or global event route is used.
