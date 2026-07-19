# Pattern: convene (session lifecycle)

Extends the always-on lore bot with the campaign's session lifecycle
— a capability, not a second bot, because eventing is text-light and
shares the archivist's always-on lifecycle exactly (one Railway
process, zero new spend). Convene DRIVES Discord's native Guild
Scheduled Events (the event card, the "interested" list, the
countdown are all the platform's; convene never rebuilds them) and
adds the things the platform and generic scheduling bots
cannot: **quorum** (a session runs iff the DM plus N players are in),
**lifecycle nudges** (bring the recorder; stage and transcribe
after), **recap announcement** (a new `sessions/` page reaching
the projection the bot already polls becomes an announcement) — which
restores the announce that the source stack's bot once did by cron,
now in its rightful always-on home — and the **prep ask**, the DM's
between-sessions "decide this before we play" broadcast, relayed to
the players verbatim inside the bot's voice.

## Preflight

- The lore-bot pattern is applied and deployed; convene rides its
  process. Convene targets the lore bot's library (discord.py).
- The bot's invite includes **Manage Events** (to read and, if you
  use `/session propose` later, create scheduled events). RSVP is the
  native "interested" button — no extra permission.
- The player role name (for counting players toward quorum) and,
  optionally, the recap channel/thread are known.

## Procedure

1. Vendor the capability beside the lore bot's `bot.py`:

       cp templates/convene.py <lorebot-dir>/convene.py

   The lore-bot template already carries the seam: it imports
   `convene` if present, calls `capability.ready(corpus)` on connect,
   and calls `capability.on_corpus_refresh(corpus)` after each
   freshness reload. Nothing changes when convene is absent.

2. Configure two ways, and they compose. The **env baseline** is the
   durable floor (survives a host redeploy that wipes local state):
   `OWNER_ID` (the maintainer — gates the commands), `DM_ID` (who
   counts as the DM for quorum — **explicit, never inferred from who
   created an event**; defaults to `OWNER_ID` when the maintainer and
   DM are the same person), `SESSION_QUORUM`, `REQUIRE_DM`,
   `PLAYER_ROLE`, `SESSION_ROLE_ID`, and a target
   (`ANNOUNCE_CHANNEL_ID` for reminders, `RECAP_THREAD_ID` for
   recaps). Then the DM tunes it live with **slash commands** using
   Discord's native pickers — no IDs to paste: `/session dm @person`,
   `/session quorum N`, `/session role @Players`, `/session channel
   #reminders`, `/session recap-channel #recaps`. Slash settings
   persist and win over env until a redeploy wipes them, then env
   is the fallback. Convene reuses `REFRESH_MINUTES` for its poll
   cadence and `SITE_URL` for recap links. `/session prep` opens a
   pop-up where the DM types a between-sessions ask; `/session status`
   shows the current config, quorum against live "interested", and the
   outstanding prep ask.

3. Redeploy the bot. On connect convene syncs its `/session`
   commands per guild, snapshots the recaps already in the projection
   as *already announced* (so a restart never re-announces the back
   catalogue), and starts its poll loop.

4. The lifecycle, hands-off thereafter: the DM (or anyone) creates a
   scheduled event in Discord's own UI; players hit **interested**;
   convene tracks quorum each tick and nudges — a rally-or-reschedule
   flag to the DM if the session is short as it approaches, a
   go-ahead (with a bring-the-recorder line) once quorum is met, a
   stage-and-transcribe nudge when it ends, and the recap
   announcement when the published page appears. Session recaps come
   from the projection, so DM-only pages never announce, by
   construction. Between sessions, the DM runs `/session prep` and
   types the ask ("send me two backstory NPCs"; "decide why you were
   headed to the Sunken City") into a pop-up; convene broadcasts it to
   the player role in the DM's own words, wrapped in the bot's voice,
   and remembers it so `/session status` can show what's outstanding.

## Decision points

- **Scheduling source.** Default: **convene** — but free Apollo
  remains perfectly fine for a table that only wants a calendar and
  reminders (mirrors the capture module's Craig default). Convene
  earns its place only for quorum + lifecycle + announce; a table
  that wants none of those simply never enables it, and Apollo is
  untouched.
- **Quorum.** Default: DM plus 3 players, DM required. Set
  `SESSION_QUORUM` and `REQUIRE_DM` to the table's shape.
- **RSVP model.** Default: the native "interested" button counts as
  attending — honest about its limit (it is interest, not a
  commitment). A finer yes/maybe/no via a reaction post rebuilds what
  Apollo already does and stays off unless a table asks.
- **Reminder wording.** Default: the built-in English templates.
  Drop a `convene_messages.json` beside the bot (start from
  `templates/convene-messages.example.json`) to re-voice the
  reminders or **translate** them — keep every `{placeholder}`; a
  template with an unknown one is rejected and the default kept, so a
  broken translation can never break a reminder. `CONVENE_MESSAGES`
  points elsewhere if you keep per-language files.
- **Prep-ask voice.** Default: the DM's ask goes out verbatim wrapped
  in a short frame (the `prep` template, placeholders `{ping}` and
  `{body}` only). The frame is the bot's; the words between it are the
  DM's and are never rewritten — mechanical relay, not authorship. To
  drop the frame entirely, set `prep` to `"{ping}{body}"`; to re-voice
  or translate it, edit the frame around `{body}`. A channel reference
  in the ask is just `<#id>` in the DM's text — Discord renders it as a
  link when posted.
- **Recorder nudge.** Default: on — the go-ahead reminds the DM to
  bring the recorder. Turn it off (`RECORDER_NUDGE=0`) for a table
  that captures with Craig instead.

## Verify

- `uv run modules/convene/verify/run.py` — golden-tests the pure
  core with no Discord: the quorum state machine fires each reminder
  once and only when due, `require_dm` gates quorum, end supersedes,
  persistence round-trips and reconcile prunes dead events, and
  recap announce-detection surfaces each new session page exactly
  once (never the back catalogue after a restart).
- Live, once deployed: create a scheduled event, watch `/session
  status` track "interested" against quorum, let it cross the
  threshold and confirm the go-ahead fires, then publish a session
  recap and confirm the announcement posts once. Until this pass is
  recorded, treat live scheduled-event driving as unproven.
