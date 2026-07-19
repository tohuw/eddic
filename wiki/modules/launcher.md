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

On macOS the launcher is a real, code-signed `.app`: an `Info.plist` and a
compiled Swift AppKit supervisor at `MacOS/<Name>`. On Windows it is a `.cmd`
file with CRLF line endings. A real Windows `.exe` would need a packager
(pyinstaller, WinSW) and a build step; the `.cmd` is the dependency-free
equivalent and is what this module ships, leaving a signed binary out of
scope until a table has a hard need for one. A single generator stamps both
forms; `--target auto` picks the launcher for the current OS and `both`
stamps the pair side by side for a mixed table sharing one repo, where each
seat regenerates locally because the campaign path is baked in per machine
(and the macOS half only builds on a Mac, which needs `swiftc` and
`codesign` from the Xcode command-line tools). Re-running the generator with
the same arguments is idempotent — it rebuilds the launcher in place — and an
unknown service name is refused with no artifact written.

## Its own window, and its own identity

The macOS app is a hand-built, self-contained AppKit app rather than an
`osacompile` applet or a Terminal-driver, for two reasons. First, it is its
own window: the Swift executable is a real windowed app with a menu bar (a
Quit item on Cmd-Q, and a standard Edit menu so the log is selectable and
copyable) and its own window holding a read-only, monospaced, auto-scrolling
text view that streams the service's stdout+stderr live off the child's pipe,
run unbuffered so nothing stalls into apparent silence. It drives no Terminal
and no other app, so there is nothing else left running to quit and no shared
Terminal to force-quit out from under someone. Quitting the app (Cmd-Q or the
Quit menu), closing its window, or the bot exiting on its own terminates the
whole child process group — the `uv`/python/recorder tree dies together, no
orphan left recording. The earlier designs detached the bot under Terminal,
so quitting the app did nothing to the bot; this owns the lifecycle. Second,
it owns its identity: the bundle carries a per-app reverse-DNS
`CFBundleIdentifier` (`quest.eddic.launcher.<slug>`), its own name, and an
ad-hoc code signature, so macOS TCC pins the service's permissions — the
recorder's microphone, above all — to this app on a stable designated
requirement, not to the shared "Applet" identity an `osacompile` bundle
reuses. Because the bot is the app's own child (in its own session via
setsid), TCC attributes it to the app.

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

The launcher opens the app's own live-log window by default, because the
recorder bot posts consent and streams logs the owner must see, and that
window is also how the owner quits — close it, Cmd-Q, or the Quit menu, and
exactly one copy runs, by construction of the run verb. A `--headless` mode
redirects output to a logfile with no window (an `LSUIElement` agent), but
only for a background service that needs no live interaction and whose stop
is handled elsewhere; a consent-gated recorder should never be headless. `--name` sets the app's
label and, with it, the reverse-DNS identity TCC pins permissions to, so it
stays stable across restamps; `--icon` brands the app. The launcher lands in
the campaign directory by default so it travels and versions with the
campaign and its baked-in path stays correct; a `--dest` (macOS) or a Desktop
shortcut (Windows) puts a copy in the OS launcher surface while the campaign
copy remains the source of truth to restamp from.

## Verify

The module's verifier golden-tests against a planted service spec. Across
every OS it asserts the pure builders and the Windows path: the Swift
supervisor source delegates to the run verb, launches the service as the
app's own child in a new process group and kills that group on quit, streams
the log into its own monospaced `NSTextView`/`NSScrollView` with a Quit item
on Cmd-Q and no Terminal/osascript/`tail` machinery at all; the `Info.plist`
carries the per-app `quest.eddic.launcher.<slug>` identifier, the app's name
as executable and display name, and a microphone usage string (with
`LSUIElement` under `--headless`); the Windows path emits a CRLF `.cmd`
invoking the same run verb; an unknown service refuses with no artifact. On
macOS with the toolchain it also builds the `.app` and asserts a Mach-O
executable, the per-app identifier in the on-disk plist, and an ad-hoc
signature keyed on it (`codesign --verify` passes) — without launching the
app. The live check is a double-click: the app's own window opens, the
service announces itself, and `codesign -dvvv` confirms the app's own
identity; then Cmd-Q or closing the window stops the service and its whole
process group, leaving no orphan and no Terminal ever spawned — the owner
never typed a command.

See the [module index](index.md), the services and run verb the
[cli](cli.md) module provides, and the [recorder](recorder.md) and
[lore-bot](lore-bot.md) services this most often wraps.
