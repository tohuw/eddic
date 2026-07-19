# Pattern: native launcher

Turns a campaign's local service — the recorder bot, or a locally-run
lore bot — into something the owner double-clicks, not something they
open a terminal to type `uv run` into. The launcher is a thin native
shell around the campaign's own run verb: it `cd`s into the campaign
and execs `uv run .eddic/eddic.py run <service>`, nothing more. Because
the run verb already builds the pinned uv invocation from the service's
config, the launcher never duplicates or drifts from the run command —
change a service's deps in config and the same double-click picks them
up.

Two native forms, one generator. On macOS the launcher is a `.app`
bundle (an `Info.plist`, a `MacOS/<Name>` executable that opens
Terminal, and a `Resources/run.sh` that holds the run verb). On Windows
it is a `.cmd` file. A real Windows `.exe` would need a packager
(pyinstaller, WinSW) and a build step; the `.cmd` is the dependency-free
equivalent and is what this pattern ships — treat the `.exe` as
out-of-scope until a table has a hard need for a signed binary.

## Preflight

- The cli pattern is applied: `.eddic/eddic.py`, `.eddic/config.json`,
  and the manifest exist. The launcher wraps the run verb, so the run
  verb must exist first.
- The target service is configured and green by hand: `uv run
  .eddic/eddic.py run <service>` starts it from a terminal. The
  launcher automates a working command; it never debugs one. If `run`
  with no argument does not list the service, stop and fix the service
  config before packaging.
- uv is on PATH (the launcher calls `uv run`; the run verb refuses
  without it). The owner's machine is the one the service runs on — the
  DM's laptop for the recorder bot, whatever host runs a local lore
  bot.

## Procedure

1. Stamp the launcher for the service and the current OS:

       uv run modules/launcher/templates/package.py --service <service> \
           --campaign <campaign> --target auto

   `--target auto` picks the launcher for the OS you are on; `both`
   stamps the `.app` and the `.cmd` side by side (for a mixed table
   sharing one repo, where each seat regenerates locally — the campaign
   path is baked in per machine). The generator reads the service from
   `.eddic/config.json`, refuses an unknown service by name, and writes
   the launcher into the campaign directory by default.

2. Hand the launcher to the owner where their OS expects it. On macOS
   the `.app` is Spotlight- and Dock-droppable as-is; move or
   `--dest ~/Applications` it if the owner wants it in Launchpad. On
   Windows the `.cmd` can be right-click → *Send to → Desktop* for a
   shortcut. The owner double-clicks; a terminal opens running the
   service with its console visible, and Ctrl-C (or closing the window)
   stops it — exactly one copy runs, by construction of the run verb.

3. Record the application in the manifest so the campaign's shape knows
   it exists and an upgrade can restamp it:

       uv run <campaign>/.eddic/eddic.py manifest record \
           --module launcher --version 0.1.0 \
           --params '{"service":"<service>","target":"<target>"}'

   Re-running the generator with the same arguments is idempotent: it
   overwrites the launcher in place with identical bytes.

## Decision points

- **Which service(s) to package.** Default: the one local service the
  campaign runs — for most tables the recorder bot, since that is the
  process the DM starts at session time. Package a second launcher (a
  separate `--service`, its own `--name`) only when the campaign truly
  runs a second local service, such as a self-hosted lore bot on the
  Warden's own machine; a hosted service has no local process to launch
  and needs none.
- **Terminal-visible vs headless.** Default: **visible** — the recorder
  bot posts consent and streams logs the owner must see, and a visible
  window makes Ctrl-C the obvious stop. Choose `--headless` (output to
  `.eddic/<service>.log`, no window) only for a background service that
  needs no live interaction and whose stop is handled elsewhere; a
  consent-gated recorder should never be headless.
- **Where the launcher lands.** Default: the **campaign directory**,
  beside `.eddic/` — it travels with the campaign, versions with it,
  and its baked-in path stays correct. Pass `--dest ~/Applications`
  (macOS) or drop a shortcut on the Desktop (Windows) when the owner
  wants it in their OS launcher surface; the campaign copy remains the
  source of truth to restamp from.

## Verify

- `uv run modules/launcher/verify/run.py` — stamps launchers against a
  planted service spec and asserts the golden shape: the macOS `.app`
  has an `Info.plist` that parses and names its executable, a
  `MacOS/<Name>` executable (marked executable on POSIX) that
  references the service and delegates to `run.sh`, and a `run.sh` that
  execs `uv run .eddic/eddic.py run <service>` from the campaign
  directory; the Windows path emits a CRLF `.cmd` invoking the same run
  verb; an unknown service refuses with no artifact; and `--headless`
  flips both to the logfile/detached shape.
- Live: double-click the stamped launcher. A terminal opens, the
  service announces itself and runs (for the recorder bot in the Sunken
  City campaign, its consent post appears), and Ctrl-C stops it. The
  owner never typed a command.
