# Pattern: native launcher

Turns a campaign's local service — the recorder bot, or a locally-run
lore bot — into something the owner double-clicks, not something they
open a terminal to type `uv run` into. The launcher is a thin native
shell around the campaign's own run verb: it `cd`s into the campaign and
runs `uv run .eddic/eddic.py run <service>`, nothing more. Because the
run verb already builds the pinned uv invocation from the service's
config, the launcher never duplicates or drifts from the run command —
change a service's deps in config and the same double-click picks them
up.

Two native forms, one generator. On macOS the launcher is a real,
code-signed `.app` — an `Info.plist`, a small compiled Swift supervisor
at `MacOS/<Name>`, and nothing else it does not own. On Windows it is a
`.cmd` file. A real Windows `.exe` would need a packager (pyinstaller,
WinSW) and a build step; the `.cmd` is the dependency-free equivalent
and is what this pattern ships — treat the `.exe` as out-of-scope until
a table has a hard need for a signed binary.

The macOS app is a hand-built, self-contained AppKit app rather than an
`osacompile` applet or a Terminal-driver, and that earns its cost twice
over:

- **It is its own window.** The Swift executable is a real windowed app:
  a menu bar with a Restart item on Cmd-R and a Quit item on Cmd-Q (and a
  standard Edit menu, so the log is selectable and copyable), and its own
  window holding a read-only, monospaced, auto-scrolling text view that
  shows the service's stdout+stderr live (streamed off the child's pipe,
  run unbuffered so nothing stalls into apparent silence). Restart kills
  the running child's process group and relaunches the same service
  command in the same window — a fresh run to pick up a code or config
  change, or to clear a stuck bot — without quitting the app; a genuine
  self-exit of the bot still quits, as before. It drives no
  Terminal and no other app — there is nothing else left running to
  quit, and no shared Terminal to force-quit out from under someone.
  Quitting the app (Cmd-Q or the Quit menu), closing its window, or the
  bot exiting on its own terminates the whole child process group — the
  `uv`/python/recorder tree dies together, no orphan left recording. The
  old designs detached the bot under Terminal, so quitting did nothing;
  this owns the lifecycle.
- **It owns its identity.** The bundle carries a per-app reverse-DNS
  `CFBundleIdentifier` (`quest.eddic.launcher.<slug>`), its own name, and
  an ad-hoc code signature. macOS TCC therefore pins the service's
  permissions — microphone, and the like — to *this app*, keyed on a
  stable designated requirement, not to the shared "Applet" identity an
  `osacompile` bundle reuses. And because the bot is the app's own child
  (in its own session via setsid), TCC attributes it to the app.

## Preflight

- The cli pattern is applied: `.eddic/eddic.py`, `.eddic/config.json`,
  and the manifest exist. The launcher wraps the run verb, so the run
  verb must exist first.
- The target service is configured and green by hand: `uv run
  .eddic/eddic.py run <service>` starts it from a terminal. The launcher
  automates a working command; it never debugs one. If `run` with no
  argument does not list the service, stop and fix the service config
  before packaging.
- uv is on PATH (the launcher calls `uv run`; the run verb refuses
  without it). The owner's machine is the one the service runs on — the
  DM's laptop for the recorder bot, whatever host runs a local lore bot.
- To build the macOS `.app` you are on macOS with `swiftc` and
  `codesign` on PATH (the Xcode command-line tools; `xcode-select
  --install` provides them). The generator refuses the macOS target
  elsewhere rather than stamp a bundle it cannot compile or sign. The
  Windows `.cmd` needs no toolchain.

## Procedure

1. Stamp the launcher for the service and the current OS:

       uv run modules/launcher/templates/package.py --service <service> \
           --campaign <campaign> --target auto

   `--target auto` picks the launcher for the OS you are on; `both`
   stamps the `.app` and the `.cmd` side by side (for a mixed table
   sharing one repo, where each seat regenerates locally — the campaign
   path is baked in per machine, and the macOS half only builds on a
   Mac). The generator reads the service from `.eddic/config.json`,
   refuses an unknown service by name, and writes the launcher into the
   campaign directory by default. Pass `--name <Label>` to name the app
   (the app's identity derives from it), and `--icon <file.icns>` to give
   it an icon. On macOS the generator compiles the Swift supervisor and
   ad-hoc-signs the finished bundle last, after every payload byte is
   final — never edit inside a stamped `.app`, restamp it.

2. Hand the launcher to the owner where their OS expects it. On macOS the
   `.app` is Spotlight- and Dock-droppable as-is; move or `--dest
   ~/Applications` it if the owner wants it in Launchpad. On Windows the
   `.cmd` can be right-click → *Send to → Desktop* for a shortcut. The
   owner double-clicks: on macOS the app's own window opens streaming the
   service live, Cmd-R (or the Restart menu item) relaunches the service
   in place to pick up a change or clear a stuck bot, and Cmd-Q (or the
   Quit menu, or closing that window) stops it cleanly; on Windows a
   console opens and Ctrl-C stops it. For
   a recorder, the first launch raises the one-time microphone prompt,
   which grants to this app's identity and persists — no other
   permission prompts, since the app drives nothing but its own window.

3. Record the application in the manifest so the campaign's shape knows
   it exists and an upgrade can restamp it:

       uv run <campaign>/.eddic/eddic.py manifest record \
           --module launcher --version 0.4.0 \
           --params '{"service":"<service>","target":"<target>"}'

   Re-running the generator with the same arguments is idempotent: it
   rebuilds the launcher in place. (The signed Mach-O bytes are not
   reproducible byte-for-byte, but the bundle's shape, identity, and
   behavior are.)

## Decision points

- **Which service(s) to package.** Default: the one local service the
  campaign runs — for most tables the recorder bot, since that is the
  process the DM starts at session time. Package a second launcher (a
  separate `--service`, its own `--name`) only when the campaign truly
  runs a second local service, such as a self-hosted lore bot on the
  Warden's own machine; a hosted service has no local process to launch
  and needs none.
- **Windowed vs headless.** Default: **windowed** — the recorder bot
  posts consent and streams logs the owner must see, and the app's own
  window is also how the owner controls the service: Restart it in place
  (Cmd-R or the Restart menu item) to pick up a change or clear a stuck
  bot, or quit it (close the window, Cmd-Q, or the Quit menu).
  Choose `--headless` (LSUIElement agent, output to `.eddic/<service>.log`
  only, no window) for a background service that needs no live
  interaction and is stopped some other way; a consent-gated recorder
  should never be headless.
- **App name and icon.** Default: the app is named for the service,
  title-cased (`recorder` → `Recorder`), with no custom icon. Pass
  `--name <Label>` when the campaign has a name for its bot (the app's
  reverse-DNS identity and its TCC permission pinning follow the name, so
  keep it stable across restamps) and `--icon <file.icns>` to brand it.
- **Where the launcher lands.** Default: the **campaign directory**,
  beside `.eddic/` — it travels with the campaign, versions with it, and
  its baked-in path stays correct. Pass `--dest ~/Applications` (macOS)
  or drop a shortcut on the Desktop (Windows) when the owner wants it in
  their OS launcher surface; the campaign copy remains the source of
  truth to restamp from.

## Verify

- `uv run modules/launcher/verify/run.py` — golden tests against a
  planted service spec. Cross-platform, it asserts the pure builders and
  the Windows path: the Swift supervisor source delegates to the run verb
  for the service, launches it as the app's own child in a new process
  group and kills that group on quit, shows the stream in its own
  monospaced `NSTextView`/`NSScrollView` with a Quit item on Cmd-Q and a
  Restart item on Cmd-R (child launch factored into one `startService`
  used at both launch and restart, and a `restarting` flag routing a
  restart-triggered exit back to relaunch instead of app-quit), and no
  Terminal/osascript/`tail` machinery at all; the `Info.plist` carries
  the per-app `quest.eddic.launcher.<slug>` identifier, the app's name as
  executable and display name, and a microphone usage string (and
  `LSUIElement` under `--headless`); the Windows target emits a CRLF
  `.cmd` invoking the same run verb; an unknown service refuses with no
  artifact. On macOS with the toolchain it additionally builds the `.app`
  and asserts a Mach-O executable at `MacOS/<Name>`, the per-app
  identifier in the on-disk `Info.plist`, and an ad-hoc signature keyed
  on that identifier (`codesign --verify` passes). The app is never
  launched by the verifier.
- Live: double-click the stamped `.app`. The app's own window opens and
  the service announces itself and streams into it (for the recorder bot
  in the Sunken City campaign, its consent post appears in the log).
  Confirm the ownership with `codesign -dvvv <App>.app` (Identifier is
  `quest.eddic.launcher.<slug>`, Signature is adhoc) and `PlistBuddy -c
  'Print CFBundleIdentifier' <App>.app/Contents/Info.plist`. Cmd-R (or the
  Restart menu item) relaunches the service in the same window — a
  `— restarting —` line then a fresh live log, without the app quitting.
  Then Cmd-Q the app (or the Quit menu, or the window's close button): the
  service and its whole process group exit — `pgrep -f <service>` shows
  nothing, no orphaned python or recorder, and no Terminal was ever
  spawned. The owner never typed a command.
