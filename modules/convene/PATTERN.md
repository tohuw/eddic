# Pattern: convene (session lifecycle)

Extends the always-on lore bot with the campaign's session lifecycle
— a capability, not a second bot, because eventing is text-light and
shares the archivist's always-on lifecycle exactly (one Railway
process, zero new spend). Convene DRIVES Discord's native Guild
Scheduled Events (the event card, the "interested" list, the
countdown are all the platform's; convene never rebuilds them) and
adds the three things the platform and generic scheduling bots
cannot: **quorum** (a session runs iff the DM plus N players are in),
**lifecycle nudges** (bring the recorder; stage and transcribe
after), and **recap announcement** (a new `sessions/` page reaching
the projection the bot already polls becomes an announcement) — which
restores the announce that the source stack's bot once did by cron,
now in its rightful always-on home.

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

2. Configure via the bot's environment (non-secret):
   `SESSION_QUORUM` (default 3), `REQUIRE_DM` (default on),
   `PLAYER_ROLE`, `OWNER_ID`, and a recap target
   (`RECAP_THREAD_ID` or `ANNOUNCE_CHANNEL_ID`). Convene reuses the
   bot's `REFRESH_MINUTES` as its poll cadence and its `SITE_URL` for
   recap links.

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
   construction.

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
