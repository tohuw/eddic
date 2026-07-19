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
  start) plus **Set Voice Channel Status** — integer
  `281477127408704`. Build the invite URL yourself with BOTH scopes:
  Discord's default install link omits the `bot` scope, and the
  resulting "Success! authorized and added" dialog is
  indistinguishable from a real invite while adding only slash
  commands — the bot never joins the member list, and it sees zero
  guilds. If the bot is "authorized" but absent, this is why;
  re-invite with `scope=bot%20applications.commands`.
- uv on the DM's machine; the bot runs at session time only.

## Procedure

1. Create `<campaign>/recorder-bot/` and copy in
   `templates/recorder.py` and `templates/dave_recv.py`; make a
   gitignored `variables.txt` with `DISCORD_TOKEN` (and optionally
   `RECORD_DIR`, `PRIVACY_URL`, `WIKI_LOG` — defaults suit the
   standard layout). Record:
   `eddic.py manifest record --module recorder --version 0.1.0`.

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

3. The session: `/record start` in a voice channel plays an
   audible chime, sets a visible recording status on the channel
   (opt out per-session with the `channel_status` option), and posts
   the consent message (announcement, privacy-posture link, live
   roster of who is being recorded); reacts open each member's gate;
   `/record stop` stages per-speaker WAV into
   `sessions/raw/<date>/` and appends a `witness` log entry.
   Transcription stays a deliberate step (transcriber pattern).

4. First run on a new setup: record a short test with one consenting
   and one non-consenting member and play both outcomes back to the
   owner before a real session trusts it.

## Decision points

- **Consent memory.** Default: strict per-session reacts — one tap
  during banter, no standing state. Alternative: remember acks
  across sessions with a visible opt-out, for tables that find the
  ritual noisy. Never silent capture.
- **Recording destination.** Default: the campaign's
  `sessions/raw/` on the DM's machine — the transcriber's layout,
  zero hosting. A cloud host with object storage is deliberately
  unbuilt; revisit only if a table's DM machine genuinely cannot be
  present at sessions.
- **When it runs.** Default: launched for the session, stopped
  after. It is not a resident service; nothing needs it between
  sessions.

## Verify

- `uv run modules/recorder/verify/run.py` — compiles both templates,
  then unit-tests the consent core against a stubbed library:
  emoji normalization (reacts arrive with and without the U+FE0F
  variation selector), the sink dropping unattributed and
  unconsented packets while counting them, consented audio landing
  as a well-formed per-speaker WAV, and revocation closing the gate.
- Live, once per setup: the two-member test in step 4 — consented
  audio present and transcribable, non-consenting member absent
  from every track.
