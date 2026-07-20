# Pattern: the recorder bot

Gives the campaign its own session recorder: a **separate Discord
bot** (not the lore bot — different lifecycles: the archivist is
always-on and cloud-cheap; the recorder is session-time-only,
voice-heavy, and wants to run beside the disk the transcriber reads).
Consent is structural, not policy: recording starts with a post in
the voice channel's text chat, and **a member's microphone is
captured only after they react to it** — enforced inside the audio
sink, where unconsented packets are dropped before any file exists.

Plain status, for you and the owner: Discord's DAVE E2EE broke voice
receive across the Python ecosystem in March 2026. This module works
anyway — `templates/dave_recv.py` combines the davey DAVE library
with import-time patches to py-cord 2.8.0's receive path (approach
shared with py-cord's in-progress fix PR), and a live capture plus
transcription proved it end to end on 2026-07-18. The patches target
py-cord 2.8.0 exactly; when upstream lands voice receive, they
retire. Pin the versions as written below.

## Preflight

- The capture pattern is applied (this bot is its no-third-party
  route; free Craig remains the default there).
- A second Discord application for the recorder: the lore-bot
  pattern's portal flow applies (create app, Reset Token once into
  the recorder's own variables.txt) — but note the recorder needs
  **no privileged intents at all**: slash commands are interactions,
  consent reacts arrive as raw reaction events, and voice states are
  a default intent. The Message Content toggle is the lore bot's
  need, not this bot's. Invite with scopes
  `bot applications.commands` and permissions View Channels, Send
  Messages, Read Message History, Add Reactions, **Connect**, and
  **Speak** (only for the transparency chime it plays at record
  start), **Set Voice Channel Status**, and **Change Nickname** (so it
  can wear a `(RECORDING)` badge on its own name while capturing) —
  integer `281477194517568`. Build the invite URL yourself with BOTH scopes:
  Discord's default install link omits the `bot` scope, and the
  resulting "Success! authorized and added" dialog is
  indistinguishable from a real invite while adding only slash
  commands — the bot never joins the member list, and it sees zero
  guilds. If the bot is "authorized" but absent, this is why;
  re-invite with `scope=bot%20applications.commands`.
- uv on the DM's machine; the bot runs at session time only.

## Procedure

1. Create `<campaign>/recorder-bot/` and copy in
   `templates/recorder.py`, `templates/dave_recv.py`, and
   `templates/control.py` (the loopback control surface); make a
   gitignored `variables.txt` with `DISCORD_TOKEN` (and optionally
   `RECORD_DIR`, `PRIVACY_URL`, `WIKI_LOG` — defaults suit the
   standard layout; control-surface env is a decision point below).
   Record:
   `eddic.py manifest record --module recorder --version 0.2.0`.

2. Wire a minimal `bot.py` beside them (a py-cord `discord.Bot`
   that imports `recorder` and calls `recorder.setup(bot)` — you
   know the five lines), then register it as a campaign **service**
   so the owner never types a runtime incantation. Add to
   `.eddic/config.json`:

       "services": {
         "recorder": {
           "dir": "recorder-bot", "entry": "bot.py",
           "python": "3.14",
           "with": ["py-cord[voice]==2.8.0", "davey"]
         }
       }

   The owner launches a session with `eddic run recorder` — the
   dispatcher supplies the pinned runtime and runs it in the
   foreground, so **Ctrl-C stops it and exactly one copy runs by
   construction** (the Discord-side ghost that outlives a hard kill
   is why one-process discipline matters; the foreground launcher
   gives it for free).

3. The session: `/record-start` in a voice channel plays an
   audible chime, sets a visible recording status on the channel
   (opt out per-session with the `channel_status` option), and posts
   the consent message as a **public** channel post (announcement,
   privacy-posture link, live roster of who is being recorded) — the
   ephemeral slash reply is only a private ack with a jump link, never
   the consent surface itself, and if the public post cannot be sent
   the bot disconnects instead of recording. Reacts open each member's
   gate; `/record-stop` stages per-speaker WAV into
   `sessions/raw/<date>/` and appends a `witness` log entry.
   Transcription stays a deliberate step (transcriber pattern). The
   same start/stop/status run through a loopback control surface too
   (see the `streamdeck` module) — one shared session core, so button
   and slash never diverge. While at least one consented mic is
   capturing, the bot appends `(RECORDING)` to its own guild nickname
   (dropped when the session stops or the last react is removed;
   truncated to fit Discord's 32-char nick limit, and best-effort — a
   missing Change Nickname permission never breaks recording). If the
   recorded voice channel empties of non-bot members for the
   auto-disconnect timeout, the session auto-stops down the same clean
   path as `/record-stop` and posts a brief note in the channel.

4. First run on a new setup: record a short test with one consenting
   and one non-consenting member and play both outcomes back to the
   owner before a real session trusts it.

## Decision points

- **Who may operate the recorder.** Default: **Manage Server**, per
  command. The recorder ships each verb as its own **top-level** command —
  `/record-start`, `/record-stop`, `/record-consent-role`,
  `/record-empty-timeout`, and `/record-help` — rather than as subcommands
  of one `/record` group. The four control/config commands each carry
  `default_member_permissions` set to Manage Server, so out of the box only
  members who can manage the server (Administrator implies it) see or run
  them; `/record-help` is left open so anyone can read how consent works.
  This split is deliberate: **Discord attaches command permissions only to
  a top-level command, never to a subcommand of a group**, so a grouped
  `/record start` could not be permissioned apart from `/record stop`. With
  each verb top-level, every one appears **individually** in Server
  Settings → Integrations → the recorder → Command Permissions, where an
  admin can allow a specific role or member on a per-command basis (or for
  the whole integration) with no code change and no redeploy — e.g. grant a
  trusted player `/record-start` and `/record-stop` while keeping
  `/record-consent-role` and `/record-empty-timeout` admin-only. The gate
  lives on the command, not inside the handlers, so a role you grant is
  never hidden from the command (which `default_member_permissions` used as
  an in-code check would cause). Doing this from the bot instead (the
  application-command-permissions API) would require a user OAuth token,
  which a bot has no business holding, so the native Integrations UI is the
  supported path. The env fallbacks below (`CONSENT_PING_ROLE`,
  `EMPTY_DISCONNECT_SECONDS`) tune *behaviour*, not *who may operate*; that
  is Discord-native only.
- **Consent memory.** Default: strict per-session reacts — one tap
  during banter, no standing state. Alternative: remember acks
  across sessions with a visible opt-out, for tables that find the
  ritual noisy. Never silent capture.
- **Consent-post ping.** Default: off. The public consent post is the
  surface everyone opts in on, but a member has to notice it. Set the role
  from Discord with `/record-consent-role @Role` (Manage-Server-gated; run
  it with no role to clear it) and the consent post `@`-pings that role so
  the whole table is notified to react — not just the invoker, who gets the
  ephemeral ack. The choice persists to the campaign-local
  `recorder_settings.json` (gitignored runtime state that also holds the
  empty-timeout below; a legacy `consent_ping.json` from an earlier version
  is read once for back-compat if the new file is absent). Run
  `/record-consent-role` with no role to clear it. `CONSENT_PING_ROLE` in
  `variables.txt` (a role id, or a role name like `Players`) is now only a
  bootstrap/fallback, used when no role has been set from Discord.
  `allowed_mentions` is scoped to
  roles only; `@everyone` and user pings are never sent, and the slash
  confirmation itself pings no one. Both unset (default) posts without a
  ping.
- **Recording destination.** Default: the campaign's
  `sessions/raw/` on the DM's machine — the transcriber's layout,
  zero hosting. A cloud host with object storage is deliberately
  unbuilt; revisit only if a table's DM machine genuinely cannot be
  present at sessions.
- **When it runs.** Default: launched for the session, stopped
  after. It is not a resident service; nothing needs it between
  sessions.
- **Empty-channel auto-stop.** Default: **60 seconds**. When the
  recorded voice channel has no non-bot members left, the bot arms a
  timer and, if nobody rejoins before it fires, runs the same clean
  stop path as `/record-stop` (stage tracks, log the witness line,
  drop the nickname badge, tear down) and posts a note that it
  auto-ended on an empty channel. Any rejoin before the timer fires
  cancels it. Tune it live from Discord with `/record-empty-timeout
  <seconds>` (admin-gated like the other control commands; `0` disables
  auto-stop, and omitting the number reports the current value); the choice
  persists to `recorder_settings.json` and is validated (non-negative, at
  most one hour). `EMPTY_DISCONNECT_SECONDS` in `variables.txt` remains a
  bootstrap fallback used when nothing is persisted. It exists so a session
  is never left silently capturing an empty room after the table disperses.
- **Native launcher.** Default: package the bot as a
  double-clickable launcher via the launcher module (a macOS
  `.app`, a Windows `.cmd`) so the DM starts a session without
  opening a terminal. It wraps this service's own run verb, so the
  recorded command never drifts; skip it only for a DM who prefers
  `uv run` by hand.
- **Control surface.** Default: **on**, loopback-bound, no token —
  `control.py` serves start/stop/status on `127.0.0.1:8776` inside the
  recorder process so a Stream Deck (or any local tool) can drive it;
  see the `streamdeck` module for the button pack. Set `CONTROL_TOKEN`
  in `variables.txt` when other local processes are untrusted, and a
  target hint (`CONTROL_CHANNEL_ID`, `OWNER_USER_ID`, or
  `CONTROL_GUILD_ID`) for a guild with several active voice channels.
  Set `CONTROL_ENABLED=0` to turn it off for a DM who only ever uses
  slash commands. The surface is never exposed off loopback by any
  setting.

## Verify

- `uv run modules/recorder/verify/run.py` — compiles all three
  templates, then unit-tests the consent core against a stubbed
  library: emoji normalization (reacts arrive with and without the
  U+FE0F variation selector), the sink dropping unattributed and
  unconsented packets while counting them, consented audio landing
  as a well-formed per-speaker WAV, and revocation closing the gate.
  It also asserts, by source inspection, that the consent post is a
  public `channel.send` and never an ephemeral interaction reply, that
  each control/config command (`record-start`, `record-stop`,
  `record-consent-role`, `record-empty-timeout`) is a top-level
  `@bot.slash_command` gated with `default_member_permissions` on Manage
  Server while `record-help` is left open, that there is no
  `create_group("record")` group anymore, and that no handler does its own
  in-code permission check, and
  unit-tests the control router (loopback auth, method/path dispatch,
  the `409`/`404` codes). It pure-tests the two session-badge features:
  the `(RECORDING)` nickname computation (append, the 32-char cap that
  truncates an over-long base, and add/strip idempotence) and the
  empty-channel decision (no non-bot members ⇒ arm, a present member ⇒
  hold). It pure-tests the settings layer too: the `recorder_settings.json`
  round-trip and the one-time back-compat read of a legacy
  `consent_ping.json`, the empty-timeout parse/validate (0 disables,
  negative and over-cap rejected), and the timeout precedence
  (persisted > env > 60-second default).
- Live, once per setup: the two-member test in step 4 — consented
  audio present and transcribable, non-consenting member absent
  from every track.
