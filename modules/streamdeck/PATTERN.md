# Pattern: Stream Deck control of the recorder

Lets the owner run Muninn from an Elgato Stream Deck — one tap to start
recording, one to stop, a key that reports status — without touching
Discord. It has two halves that ship together:

- **A control surface inside the recorder.** The recorder module's
  `control.py` runs a tiny HTTP server **bound to `127.0.0.1`** inside
  the already-local recorder process. Its endpoints (`POST
  /record/start`, `POST /record/stop`, `GET /status`, `GET /healthz`)
  call the recorder's *shared session core* — the exact same
  `open_session` / `close_session` / `session_status` the `/record`
  slash commands call, so a button and a slash can never diverge. It is
  loopback-only and never exposed; an optional `X-Muninn-Token` header
  (set `CONTROL_TOKEN`) guards it against other local processes.
- **A button pack the owner binds.** `templates/deckpack.py` stamps a
  folder of scripts that curl those endpoints, each bindable to a Stream
  Deck key via the app's built-in **System ▸ Open** action — no
  plugins. It also emits an experimental `.streamDeckProfile` and a
  README with exact steps.

The control surface belongs to the recorder because it must run in the
recorder's process and event loop; this module owns the owner-facing
pack and the surface's *use*. You cannot bind real Stream Deck hardware
from here, so the profile import is documented as best-effort and the
manual System-Open bind is the guaranteed path; everything else — the
control API (curl it), the pack generation, the router logic — is
deterministically verified.

## Preflight

- The recorder pattern is applied and its bot runs (`eddic run
  recorder`, or the launcher). This module drives the recorder; it does
  not stand alone.
- The recorder's templates include `control.py` (recorder ≥ 0.2.0). If
  an older recorder-bot lacks it, re-apply the recorder pattern to copy
  it in before stamping a pack.
- The control surface is on by default when the recorder runs
  (`CONTROL_ENABLED=0` disables it). Confirm it is up:
  `curl -s http://127.0.0.1:8776/healthz` returns
  `{"ok": true, "service": "muninn-control"}`.
- uv on the owner's machine (the recorder calls `uv run`). `curl` is
  present on macOS and Windows 10+.

## Procedure

1. Decide the control surface's posture in the recorder bot's
   `variables.txt` (env). Defaults need nothing; set any of:
   `CONTROL_ENABLED` (default on), `CONTROL_PORT` (default 8776),
   `CONTROL_TOKEN` (a shared secret; recommended if other local apps are
   untrusted), and a target hint — `CONTROL_CHANNEL_ID` (record this
   voice channel), or `OWNER_USER_ID` (record the channel this member is
   in), or `CONTROL_GUILD_ID`. With no hint the surface records the one
   populated voice channel and refuses if that is ambiguous.

2. Stamp the pack for the owner's OS:

       uv run modules/streamdeck/templates/deckpack.py \
           --campaign <campaign> --token <CONTROL_TOKEN>

   It writes `<campaign>/streamdeck/` with `start-recording`,
   `stop-recording`, `recording-status`, and `muninn-help` scripts
   (`.command` on macOS, `.cmd` on Windows via `--target`), a `README.md`,
   and `Muninn.streamDeckProfile` — those four control-surface keys and
   nothing else. Pass the same `--token` the recorder uses (the scripts are
   local-only; keep the folder out of git) and `--port` if you moved the
   surface.

3. Hand the owner the folder and the README's bind steps: in the Stream
   Deck app, drop **System ▸ Open** on a key and point it at the script;
   set the key title. The `.streamDeckProfile` can be double-clicked to
   import as a starting point, but if a version rejects it, the manual
   bind always works. On macOS the `.command` scripts are already
   `chmod +x`; the first run raises the one-time Terminal-open approval.

4. Record the application in the manifest:

       uv run <campaign>/.eddic/eddic.py manifest record \
           --module streamdeck --version 0.1.1 \
           --params '{"target":"<os>"}'

## Decision points

- **Shared secret.** Default: **set `CONTROL_TOKEN`** to a random string
  and stamp the pack with the same `--token`. The surface is loopback-only,
  so an unauthenticated posture is defensible on a single-user machine;
  set the token when other, less-trusted local processes could reach
  `127.0.0.1` (shared/managed machines, curious roommates). Never expose
  the port off loopback — there is no configuration that does, by design.
- **Which target voice channel.** Default: **auto** — record the single
  populated voice channel, and refuse (clear error) if more than one is
  populated. Set `CONTROL_CHANNEL_ID` for a table that always records the
  same room, or `OWNER_USER_ID` to always follow the DM into whatever
  channel they are in. Prefer a hint over auto for a busy guild with
  several active voice channels.
- **Windows vs macOS scripts.** Default: **this OS** (`--target auto`).
  Use `--target both` for a DM who moves between machines or a mixed
  table sharing one repo; the profile is stamped once and points at the
  first target's scripts.

## Verify

- `uv run modules/streamdeck/verify/run.py` — compiles the generator and
  golden-tests it with no hardware: the core scripts curl the right
  method and endpoint and include the token only when one is given, the
  Windows target emits CRLF `.cmd` files, a full pack materializes with
  the four keys, an executable bit, a README documenting the System-Open
  bind, and a `.streamDeckProfile` that is a valid zip whose manifest
  maps key `0,0` to System-Open on the start script; exactly those four
  control keys are stamped and no extras directory is ever created, and
  `--target both` stamps both OSes.
- `uv run modules/recorder/verify/run.py` — the recorder verifier
  additionally proves the control router: `/healthz` is open, a
  configured token makes a missing/wrong token `401`, `/status` returns
  the snapshot, `start`/`stop` route to their actions with a not-ok
  result mapping to `409`, and an unknown route is `404`.
- Live: with the recorder running, `curl -s
  http://127.0.0.1:8776/healthz` answers; `curl -s -X POST
  http://127.0.0.1:8776/record/start` (add `-H "X-Muninn-Token: …"` if
  set) posts the public consent message in the target channel and begins
  recording exactly as `/record start` would; `curl .../status` reports
  it; `curl -X POST .../record/stop` stages the tracks. Then bind a key
  to `start-recording.command` and confirm the tap does the same.
