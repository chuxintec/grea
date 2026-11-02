# Unity virtual-pointer QA client

`beaver.qa_virtual_pointer` is the Python client for the separate
`unity-inputsystem-virtual-pointer/1` backend. It talks only to a loopback TCP
companion authenticated by a private channel token. It does not import or call
the legacy native QA helper, Accessibility APIs, OS cursor APIs, or global
input. A missing or unsupported companion is an error; there is no fallback.

The module exports `prepare(spec, expected_spec, out)`,
`bind(project, build, profile, expected_owner, run, channel,
expected_channel, out)`, `input_event(session, expected_session, spec,
expected_spec, out)`, `status(session, expected_session, out)`, and
`stop(session, expected_session, out)`. Input, channel and session paths are
explicit and content-hash bound. Output directories must be new and must not
overlap inputs or the owned app/run directories.

## Prepare and configure an owned run

The prepare spec is a closed `beaver-virtual-pointer-prepare/1` JSON object:

```json
{
  "schemaVersion": 1,
  "contract": "beaver-virtual-pointer-prepare/1",
  "projectId": "demo",
  "buildId": "build-a",
  "profileId": "qa-a",
  "unityVersion": "6000.6.2f1",
  "inputSystemVersion": "1.20.1",
  "leaseSeconds": 300,
  "idleReleaseSeconds": 10,
  "commandMaxSeconds": 5,
  "stopOnTakeover": true
}
```

`prepare` creates a random channel ID and token below
`~/Library/Application Support/beaver/virtual-pointer/channels/CHANNEL/`.
The channel directory is mode `0700`; its private `config.json` is `0600`.
The returned public `virtual-channel.json` omits the token and gives the private
config path and SHA. Declare that config file as a normal Beaver QA `configInput`
and bind it to `BEAVER_VIRTUAL_POINTER_CONFIG` in the existing QA prepare spec.
QA prepare copies the file into its controlled Application Support config
directory. `bind` verifies that copy has the exact private config SHA and that
the owned live process environment uses the declared copy. It refuses runs
without this typed binding. The private channel endpoint and receipt paths stay
under the channel directory; the runtime writes its discovery JSON at the
configured `endpointPath`.

The runtime companion starts only when its environment config exists, the
Player is a Development Build, and `BEAVER_VIRTUAL_POINTER` is compiled in.
Channel configuration never goes in a report or log. Do not include private
config bytes or tokens in bug reports.

## Binding and input

`bind` reuses `qa_binding._resolve` with the explicit project/build/profile/
owner/run tuple and full bundle check. It then checks the live typed config
binding, discovery PID and Unity/Input System versions, and an authenticated
`hello` before writing an immutable session. The discovery record binds the
channel, random instance ID, Input System device ID, nonce, build GUID and coordinate
space/dimensions. This session is not a claim that input was delivered.

Input specs use `beaver-virtual-pointer-input/1` and must repeat the exact
session `instanceId`, `deviceId`, `coordinateSpace`, `screenWidth`, and
`screenHeight`. A spec contains 1–64 commands. Coordinates must be finite and
inside the advertised screen bounds. Scroll deltas are bounded to ±10,000;
drag has 1–128 points and 1–10 frames per step. Only `move`, `down`, `up`,
`click`, `drag`, `scroll`, `release`, and `capture` are accepted. The companion
does not provide arbitrary keyboard, text, script or callback input.

Each command reserves and persists its next sequence under a private lock before
opening a socket. The client never retries a command. A timeout, malformed or
missing receipt, partial response, or identity mismatch leaves the channel
blocked for new gestures. `status` sends only a read-only `inspect` request and
may clear that block only when the nested last-command receipt is terminal
(`verified`, `consumed`, `blocked`, or `not_supported`). A `pending` receipt
keeps gestures blocked while still allowing an explicit stop. Status never
replays an event. Every response is checked against the
bound channel, process, build, device and coordinate identity. Redacted receipts
are persisted below a separate private `client-receipts/` directory with mode
`0600`; the companion retains ownership of its configured `receiptRoot`.

`stop` requests release and device cleanup. A stopped receipt must report buttonDown=false and independently confirm deviceRemoved, actionRoutesRestored, listenerStopped, backgroundRestored and endpointRemoved as true. Missing or failed substeps remain partial, preserve credentials/state and block further gestures; attempted shutdown is not completed cleanup. Local channel config, endpoint and
client state are removed only after a stopped receipt confirms cleanup, the
endpoint still belongs to the bound channel/instance/PID/nonce (or is absent),
and the original owned run is revalidated. A replacement or unreadable endpoint
produces a partial result with `needsAction` and keeps private config/state.
Receipts are value-redacted against the channel token, including nested command
receipts and string values inside lists. A blocked/unknown stop remains visible
as such and keeps local credentials for a deliberate status/stop follow-up.

An in-session `release` or `stop` may finish a pending pointer release through
the normal UI route. It can complete a click/drop/select/produce action; it is
not a business rollback or a guarantee that gameplay state did not change.
Judge business outcomes independently. The archived clean-exit retirement path
is strictly local: it checks the archived QA run and pinned lifecycle receipt,
then writes a mode `0600` prepared retirement receipt pinning the original state
SHA and the validated sequence/unknown flags before deleting only that
channel's private config and client state. Retirement does not resolve a
pending input or business outcome. It makes no socket request and does not
touch Player saves, copied QA configs, the app, owner record, or archived run.

## Evidence boundary

The server receipt distinguishes accepted/consumed events, frames, partial
results and cleanup. It cannot claim game business acceptance. Input routed
through other consumers or direct polling remains unsupported unless it follows
the same normal `InputSystemUIInputModule` route. OS cursor/frontmost-PID
observation is independent and read-only; natural human activity remains a
separate evidence gate. A mock server test verifies client protocol behavior,
not Unity runtime integration or physical/visual input behavior.


## Current support and public commands

The first supported platform is macOS Unity6000.6.2f1 + InputSystem1.20.1/uGUI,
Development Build with the explicit BEAVER_VIRTUAL_POINTER define. Use the five
separate commands `qa virtual-prepare`, `qa virtual-bind`, `qa virtual-input`,
`qa virtual-status`, `qa virtual-stop`; legacy `qa bind/input` retain their old
backend and safeguards. The result has inputMode=virtual-pointer/backend plus
verification.virtualInput; verification.native, visual and business remain
independent. No software command can fall back to native input.

A normal QA prepare may bind only the exact reserved
BEAVER_VIRTUAL_POINTER_CONFIG variable to a declared typed config file. This
also permits the explicit -batchmode argument for a neutral zero-activation test;
other reserved variables and ordinary legacy launch restrictions remain. Unity
batchmode can report Application.isFocused=true without being the OS foreground
app. Receipts therefore separate focused from osForeground/frontmostPid and
applicationBatchMode. Native input means takeover only when the read-only OS PID
actually equals the target and a native control changed. Other-app activity is
neither coordinates nor a termination condition. Viewport changes terminate the
old instance safely; obtain a new prepared instance/session rather than mutating
an immutable coordinate binding.

The source matrix proved real UI clicks, drags and scroll, idle and disconnect
release and cleanup with normal zero exit. It also recorded independent OS
metadata while the target never became foreground. A neutral batchmode result
is not a windowed focus-transition or human-parallel consumer verdict. Natural
human activity requires its own real sample and remains pending until recorded.
The finite capture command currently returns not_supported; it never captures
another app or changes focus. Neutral rendered frames were produced through the
test consumer's own camera, not an OS desktop screenshot. No game-specific page,
coordinate, identity or callback is embedded in the companion.

Scene replacement retires Unity-destroyed modules without treating them as live restoration failures. Any failed restoration of a still-live module is remembered across route clearing and ends the companion safely with partial cleanup; it cannot later become a successful cleanup just because the old route list is empty.
