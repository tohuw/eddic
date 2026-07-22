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
the players verbatim inside the bot's voice, with its private return
path: **`/session respond`**, an ephemeral modal any player can open
whose answer files straight into the DM's witness review inbox —
never a channel, never the table's eyes.

## Preflight

- The lore-bot pattern is applied and deployed; convene rides its
  process. Convene targets the lore bot's library (discord.py).
- The bot's invite includes **Manage Events** (to read and, if you
  use `/session propose` later, create scheduled events). RSVP is the
  native "interested" button — no extra permission.
- The player role name (for counting players toward quorum) and the
  channel the bot posts to (one auto-events channel — reminders,
  go-aheads, and recap announcements all land there) are known.

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
   `PLAYER_ROLE`, `SESSION_ROLE_ID`, and `ANNOUNCE_CHANNEL_ID` (the
   one auto-events channel — reminders, go-aheads, and recap
   announcements all post there). Then the DM tunes it live with
   **slash commands** using Discord's native pickers — no IDs to
   paste: `/session dm @person`, `/session quorum N`, `/session role
   @Players`, `/session channel #auto-events`, and `/session keyword
   <word>` (the session name keyword; omit the word to clear it). Slash
   settings
   persist and win over env until a redeploy wipes them, then env
   is the fallback. Convene reuses `REFRESH_MINUTES` for its poll
   cadence and `SITE_URL` for recap links. `SESSION_MATCH` (optional)
   scopes which calendar entries are sessions when the guild's schedule
   carries more than sessions — see the decision point below. `/session prep` opens a
   pop-up where the DM types a between-sessions ask; `/session status`
   shows the current config, quorum against live "interested", and the
   outstanding prep ask (with how many private responses have come in).
   `WITNESS_URL` and `WITNESS_TOKEN` (both optional, env-only — a
   token slash-typed into Discord would live on in client history)
   turn on `/session respond`, the players' private answer path — see
   the decision point below.

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
   construction. The same projection-only basis powers the **reveal
   digest**: when any *other* page newly enters the projection — a twin
   flipped to player-visible, a new player page published — convene
   batches the delta into one "the veil lifts" post on that same
   lifecycle beat, so a page announces only once it is already
   player-visible. Between sessions, the DM runs `/session prep` and
   types the ask ("send me two backstory NPCs"; "decide why you were
   headed to the Sunken City") into a pop-up; convene broadcasts it to
   the player role in the DM's own words, wrapped in the bot's voice,
   and remembers it so `/session status` can show what's outstanding.
   Players answer with `/session respond`: a pop-up of their own whose
   text the bot files verbatim into the DM's witness review inbox as a
   pending suggestion, tied back to the ask it answers — the player
   gets an ephemeral receipt, the table sees nothing, and the DM
   triages with `eddic suggestions` exactly like any other witness
   drop.

## Decision points

- **Scheduling source.** Default: **convene** — but free Apollo
  remains perfectly fine for a table that only wants a calendar and
  reminders (mirrors the capture module's Craig default). Convene
  earns its place only for quorum + lifecycle + announce; a table
  that wants none of those simply never enables it, and Apollo is
  untouched.
- **Session vs. other events.** Default: `SESSION_MATCH` **unset** — every
  scheduled event is a session, so a calendar used only for sessions needs
  no configuration and behaves exactly as before. When the guild's schedule
  also carries movie nights, one-shots, or planning calls, set the keyword
  with `/session keyword <word>` (e.g. `/session keyword Session`) — env
  `SESSION_MATCH` is the bootstrap/fallback for the first boot, but the
  slash setting persists and wins thereafter, and `/session keyword` with no
  word clears it back to every-event-a-session. An event is then a session
  iff its name contains the keyword, case-insensitively. Non-session events
  get a single light heads-up — one neutral "a new event is on the calendar"
  @-ping to the auto-events channel on first sight, tracked by event id so it
  never repeats — and nothing else: no quorum, no rally-or-reschedule flag,
  no go-ahead, no stage-and-transcribe nudge. That one announce is convene's
  entire involvement with a non-session. Re-voice or translate it through the
  `event` template in `convene_messages.json` (placeholders `{ping}`,
  `{title}`, `{when}`).
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
- **Private prep responses (the companion-less path).** Default: off —
  set `WITNESS_URL` (the retrieval worker's base URL) and
  `WITNESS_TOKEN` (a tier token) in the bot's env to turn on
  `/session respond`. It is the private return path for a player who
  does not run a companion: an ephemeral modal, open to **every**
  member (deliberately ungated — the gate is for DM/config commands),
  whose text the bot files verbatim as a `suggest_page` into the
  retrieval module's witness inbox on the player's behalf. The
  destination is the point: the inbox is DM-tier-only, so the table
  never sees a response and even the submitting player cannot read
  others' — a no-read-history channel can NOT substitute, because
  Discord's history permission is all-or-nothing (it neither hides
  co-present players' live replies nor preserves a player's own). Use
  the **player-tier** token: any valid tier may suggest, and the DM
  token belongs on the DM's own devices, never a bot host. Collect it
  with the secrets helper at setup; it rides env only, never Discord.
  Each drop's rationale names the responder and quotes the outstanding
  ask (tied by its timestamp id) so review files read in context; the
  prep record keeps a count-only receipt — never the text — for
  `/session status`. If the write fails (inbox full, worker down), the
  bot hands the player their words back in the same ephemeral thread
  rather than losing them. Requires the retrieval pattern's witness
  write path (an `INBOX` KV binding); unconfigured, `/session respond`
  refuses cleanly before the modal opens.
- **Recorder nudge.** Default: on — the go-ahead reminds the DM to
  bring the recorder. Turn it off (`RECORDER_NUDGE=0`) for a table
  that captures with Craig instead.
- **Reveal digest.** Default: **on, batched, newly-revealed only.**
  When any page newly enters the projection — a twin flipped to
  `visibility: player`, a new player page published, not just a
  `sessions/` recap — convene posts one "the veil lifts" digest on its
  existing recap/ended lifecycle beat, listing each newly-revealed
  page's own title and published link (a mechanical relay, like the
  prep ask — no authored prose is rewritten). Three defaults fold in:
  *scope* is every newly-revealed page (session recaps keep their own
  dedicated line and are not repeated in the digest); *cadence* is one
  batched post per lifecycle beat, never one message per page, since an
  edit-changelog would be spam; *new-vs-updated* is newly-revealed only
  — the persisted `announced` set and the startup snapshot suppress the
  back catalogue exactly as they do for recaps, so an ephemeral host
  never re-announces history. It reads only the projection, so a page
  can appear only once already player-visible: leak-proof by
  construction. Re-voice or translate the batch frame and the per-page
  line through `convene_messages.json` (`reveal`, placeholders
  `{count}`/`{entries}` plus an optional `{ping}`; and `reveal_item`,
  placeholders `{title}`/`{link}`).
- **State durability.** Default: put `convene_state.json` on **durable
  storage** (a persistent volume or a KV store) when the host offers
  one; otherwise rely on the startup catch-up. That file holds the
  `announced` set (which recaps have posted) and each event's fired
  reminders. On an ephemeral host — Railway, say, wipes the disk on
  every redeploy — it is lost on redeploy, so on connect convene runs a
  catch-up that marks the recaps already in the projection as
  already-announced. That catch-up is the fallback that stops a
  redeploy re-posting the back catalogue, but it is only a fallback: a
  recap that first appeared while the bot was down gets marked
  announced without ever posting, so it is missed. Point `CONVENE_STATE`
  at a mounted volume (an absolute path wins over the module-local
  default) to carry the set across redeploys and close that gap. To
  deliberately re-post every recap once — after the site URLs change,
  say — set `CONVENE_REANNOUNCE=1` for a single boot, then unset it.

## Verify

- `uv run modules/convene/verify/run.py` — golden-tests the pure
  core with no Discord: the quorum state machine fires each reminder
  once and only when due, `require_dm` gates quorum, end supersedes,
  persistence round-trips and reconcile prunes dead events, and
  recap announce-detection surfaces each new session page exactly
  once (never the back catalogue after a restart), `CONVENE_REANNOUNCE`
  is honored (it skips the catch-up so every recap re-posts), and
  recaps resolve to the one announce channel. The reveal digest is
  golden-tested too: a projection gaining N non-session player pages
  yields one batched delta of exactly those pages, re-polling the same
  projection yields nothing (idempotent), DM-only pages never appear,
  and the startup snapshot suppresses the back catalogue on a simulated
  restart. Two durability regressions are covered as well: a reminder
  due while the announce channel is unset stays unfired (it re-fires
  once a channel exists), and a corrupt state file loads as empty
  rather than crashing the bot at import. The private respond path is
  golden-tested at its pure seam: the filed drop carries the player's
  words verbatim (braces survive), ties back to the ask's timestamp id,
  fits the worker's field caps even at the modal's maximum, and the
  witness request is a header-auth `tools/call` that never puts the
  token in the URL; source-level checks pin `/session respond` ungated,
  every reply ephemeral, and no channel send anywhere in the respond
  path.
- Live, once deployed: create a scheduled event, watch `/session
  status` track "interested" against quorum, let it cross the
  threshold and confirm the go-ahead fires, then publish a session
  recap and confirm the announcement posts once. Until this pass is
  recorded, treat live scheduled-event driving as unproven.
