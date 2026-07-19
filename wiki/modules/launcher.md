# launcher

The launcher module turns a campaign's local service — the
[recorder](recorder.md) bot, or a locally-run [lore bot](lore-bot.md) — into
something the owner double-clicks rather than a terminal they open to type
`uv run` into. It depends on [cli](cli.md), because the launcher is a thin
native shell around the campaign's own run verb: it `cd`s into the campaign
and execs `uv run .eddic/eddic.py run <service>`, nothing more. Since the run
verb already builds the pinned uv invocation from the service's config, the
launcher never duplicates or drifts from the run command — change a service's
dependencies in config and the same double-click picks them up.

## Two native forms, one generator

On macOS the launcher is a `.app` bundle: an `Info.plist`, a `MacOS/<Name>`
executable that opens Terminal, and a `Resources/run.sh` that holds the run
verb. On Windows it is a `.cmd` file with CRLF line endings. A real Windows
`.exe` would need a packager (pyinstaller, WinSW) and a build step; the
`.cmd` is the dependency-free equivalent and is what this module ships,
leaving a signed binary out of scope until a table has a hard need for one.
A single generator stamps both forms; `--target auto` picks the launcher for
the current OS and `both` stamps the pair side by side for a mixed table
sharing one repo, where each seat regenerates locally because the campaign
path is baked in per machine. Re-running the generator with the same
arguments is idempotent — it overwrites the launcher in place with identical
bytes — and an unknown service name is refused with no artifact written.

## Wrapping a working command, never debugging one

The launcher automates a command that already works; it does not fix a
broken one. Its preflight requires that the [cli](cli.md) pattern is applied
and that the target service starts green by hand — if `run` with no argument
does not list the service, the service config is wrong and packaging stops
there. uv must be on `PATH`, since the launcher calls `uv run` and the run
verb refuses without it, and the machine that stamps the launcher is the one
the service runs on: the DM's laptop for the recorder bot, whatever host
runs a local lore bot. Application is recorded in the campaign manifest so
the campaign's shape knows the launcher exists and an upgrade can restamp
it.

## Visible by default

The launcher opens a visible terminal by default, because the recorder bot
posts consent and streams logs the owner must see, and a visible window
makes Ctrl-C the obvious stop — exactly one copy runs, by construction of
the run verb. A `--headless` mode redirects output to a logfile with no
window, but only for a background service that needs no live interaction and
whose stop is handled elsewhere; a consent-gated recorder should never be
headless. The launcher lands in the campaign directory by default so it
travels and versions with the campaign and its baked-in path stays correct;
a `--dest` (macOS) or a Desktop shortcut (Windows) puts a copy in the OS
launcher surface while the campaign copy remains the source of truth to
restamp from.

## Verify

The module's verifier stamps launchers against a planted service spec and
asserts the golden shape: the macOS `.app` has an `Info.plist` that parses
and names its executable, a `MacOS/<Name>` executable marked executable on
POSIX that references the service and delegates to `run.sh`, and a `run.sh`
that execs the run verb from the campaign directory; the Windows path emits a
CRLF `.cmd` invoking the same run verb; an unknown service refuses with no
artifact; and `--headless` flips both to the logfile-and-detached shape. The
live check is a double-click: a terminal opens, the service announces itself
and runs, and Ctrl-C stops it — the owner never typed a command.

See the [module index](index.md), the services and run verb the
[cli](cli.md) module provides, and the [recorder](recorder.md) and
[lore-bot](lore-bot.md) services this most often wraps.
