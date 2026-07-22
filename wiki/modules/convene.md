# convene

Convene is the session-lifecycle module for an online-hosted campaign. It
is not a bot of its own but a capability of the always-on lore bot: a
single vendored file dropped beside that bot's `bot.py`, loaded through the
same [capability seam](../concepts/the-capability-seam.md) the bot already
uses for its optional parts. Because session eventing is text-light and
shares the archivist's always-on lifecycle exactly, convene rides the one
existing hosting process and adds zero new spend and no second host. It
depends on the [lore-bot](lore-bot.md) module being applied and deployed
first, and targets that bot's Discord library. Its current release is
0.5.0.

Convene drives Discord's own Guild Scheduled Events rather than rebuilding
them. The event card, the "interested" list, and the live countdown remain
the platform's; convene reads them and never reconstructs them. On top of
the native event it supplies the things the platform and generic
scheduling bots cannot: quorum, lifecycle nudges, recap announcement, the
reveal digest for pages newly opened to players, and the between-sessions
prep ask with its private return path.

## Sessions and other events

By default convene treats every scheduled event as a session, so a calendar
used only for play needs no configuration. When the same guild schedules
movie nights, one-shots, or planning calls alongside sessions, a keyword —
set from Discord with `/session keyword <word>`, with the env `SESSION_MATCH`
as a first-boot bootstrap — tells convene which entries are sessions: an event
is a session iff its name contains that keyword, case-insensitively, and
everything else is a non-session. The slash setting persists in the state
file and wins over the env; `/session keyword` with no word clears it, so
every event is a session again. A non-session gets a single light
heads-up — one neutral "a new event is on the calendar" notice, pinging the
session role, posted to the auto-events channel on first sight and tracked by
event id so it never repeats — and receives nothing further: no quorum, no
at-risk flag, no go-ahead, and no stage-and-transcribe nudge. That one
announce is convene's entire involvement with a non-session. Leaving
`SESSION_MATCH` unset preserves the original behaviour exactly, so existing
deployments are unaffected.

## Quorum

A quorum decides whether a session actually happens: it runs only if the
game master (DM) plus a configured number of players have marked the event
"interested." The player count is scoped by a role, so on a shared server
each campaign's role gates its own quorum and a stray click from a
non-player is ignored. Whether the DM is required is a separate switch. The
default shape is the DM plus three players, DM required. The DM who counts
toward quorum is always set explicitly and is never inferred from whoever
created the event.

## The lifecycle and its nudges

Convene owns no gateway event handlers. On each poll tick it recounts the
attendees Discord reports and evaluates a pure state machine, so a change
in interest is caught within one cycle and a restart loses nothing. It
reuses the lore bot's refresh cadence for the tick interval. Four reminders
exist, each fired at most once per event and persisted so it never repeats:
a created notice when an event first appears; an at-risk flag to the DM
when the session is short of quorum inside a roughly thirty-six-hour window —
a rally-or-reschedule prompt while there is still time; an imminent go-ahead
once quorum is met near the start, carrying by default a line to bring the
recorder into the voice channel; and an ended nudge to stage the recording
and transcribe it. Because external scheduled events do not auto-complete,
a time-based fallback treats an event past its explicit end — or past its
start plus a default four-hour duration — as ended, so the
stage-and-transcribe nudge still fires when the DM never marks the event
done.

## Recap announcement

When a new `sessions/` page reaches the [projection](../concepts/projection-and-visibility.md)
the bot already polls, convene announces it once in the auto-events
channel — the same channel it posts reminders and go-aheads to, since
0.2.1 folded the separate recap channel away — linking the
[published](publish.md) page. Because recaps are read from the projection,
DM-only pages never announce, by construction. The set of
already-announced recaps lives in the state file, which belongs on durable
storage wherever the host offers it. On a host that wipes local state on
redeploy, convene instead snapshots the recaps already present as
already-announced on connect, so a restart never re-announces the back
catalogue — a fallback that trades away a recap first published during
downtime, which is marked announced without ever posting. Setting
`CONVENE_REANNOUNCE=1` for a single boot deliberately re-posts every recap
once, for when the site URLs change. This restores the recap announcement
that generic cron once did, now in its always-on home.

## The reveal digest

The reveal digest generalizes the recap announcement to every kind of page.
When any page newly enters the projection — a twin flipped to
`visibility: player`, a fresh player page published, not only a `sessions/`
recap — convene batches the delta into a single "the veil lifts" post on the
same lifecycle beat, listing each newly-revealed page's own title and
published link. It is a mechanical relay like the prep ask: the frame is the
bot's voice, the titles and links are the pages' own, and no authored prose
is rewritten. Three defaults shape it: scope is every newly-revealed page,
with session recaps keeping their dedicated line and never repeated in the
digest; cadence is one batched post per beat rather than one message per page,
so an edit-changelog can never become spam; and it announces newly-revealed
pages only, reusing the same persisted `announced` set and startup snapshot
that suppress the recap back catalogue, so an ephemeral host never re-announces
history. Because it reads only the projection, a page can surface in the digest
only once it is already player-visible — the announce is leak-proof by
construction, on the same basis as the recap announcement. The batch frame and
the per-page line are overridable and translatable through
`convene_messages.json` like every other template.

## The prep ask

Between sessions the DM runs `/session prep` and types a "decide this
before we play" ask into a pop-up. Convene broadcasts it to the player role
in the DM's own words, wrapped in a short frame that is the bot's voice —
the words between the frame are the DM's and are never rewritten, a
mechanical relay rather than authorship. The last ask is remembered so
`/session status` can show what remains outstanding. A channel reference
typed as `<#id>` renders as a link when posted.

## The private response path

`/session respond` is the ask's return path for a player who runs no
companion. Any member — the command is deliberately ungated, unlike the
DM/config commands — opens a pop-up whose single field goes privately to
the DM: convene files the text verbatim as a `suggest_page` into the
[retrieval](retrieval.md) module's witness inbox on the player's behalf,
tied back to the outstanding ask by its timestamp id, with the responder
named in the drop's rationale so the DM's review file reads in context.
The whole interaction is private by construction: the modal is answered
ephemerally, the response content is never echoed even in the receipt,
and nothing about a response — not even that one was made — ever reaches
a shared channel. The inbox is DM-tier-only to read, so the table cannot
see responses and one player cannot read another's; the DM triages them
with `eddic suggestions` like any other witness drop. The prep record
keeps a count-only tally — never the text — which `/session status`
shows. If the witness write fails or the inbox is unconfigured, convene
refuses or reports the miss in the same ephemeral thread and hands the
player their words back to deliver directly, rather than losing them —
and never falls back to posting in a channel.

## Configuration

Two layers compose. An environment baseline is the durable floor that
survives a host redeploy wiping local state: the maintainer and DM
identities (the DM defaulting to the maintainer when they are the same
person), the quorum count and DM-required switch, the player role, the
ping role, and the one auto-events channel. An optional `SESSION_MATCH`
keyword scopes which calendar entries are sessions (see Sessions and other
events above); left unset, every event is a session. Two optional env-only
settings, `WITNESS_URL` (the retrieval worker's base URL) and
`WITNESS_TOKEN` (a **player-tier** token — any valid tier may suggest, and
the DM token belongs on the DM's own devices, never a bot host), turn on
`/session respond`; they ride env only because a token slash-typed into
Discord would live on in client history. Convene also reuses the
bot's site URL for recap links. On top of that the DM tunes settings live
through slash commands that use Discord's native pickers, so no IDs are
pasted: `/session dm`, `/session quorum`, `/session role`, `/session
channel`, `/session keyword`, plus `/session prep` and `/session status`. The configuring
commands are gated to the maintainer. Slash
settings persist in the state file and win over the environment while that
state lives; once a redeploy wipes it, the environment is the fallback.

Reminder wording is overridable. Dropping a `convene_messages.json` beside
the bot re-voices or translates the templates; every `{placeholder}` must
be preserved, and a template carrying an unknown placeholder is rejected
and the built-in default kept, so a broken translation can never break a
reminder. The prep frame is overridable the same way, its only placeholders
being the ping and the DM's verbatim body; setting it to just those two
drops the frame entirely. The recorder line in the go-ahead is on by
default and can be switched off for a table that captures with an external
service instead.

## Decision points

The scheduling source defaults to convene, but a table wanting only a
calendar and reminders can keep the free Apollo bot untouched; convene
earns its place only for quorum, lifecycle orchestration, and recap
announcement, and a table that wants none of those simply never enables it.
Whether a scheduled event is a session defaults to yes for every event,
backward-compatibly; setting a keyword with `/session keyword <word>` (env
`SESSION_MATCH` is the bootstrap/fallback) carves out non-sessions, which get
a one-time light heads-up and nothing more.
The quorum shape, the RSVP model (the native "interested" button counts as
attending, honest that it is interest and not a commitment), the reminder
wording, the prep voice, and the recorder nudge are each set to a sensible
default with room to tune. The private response path defaults to off and
turns on by setting `WITNESS_URL` and `WITNESS_TOKEN` in the bot's env; it
requires the retrieval pattern's witness write path, and unconfigured,
`/session respond` refuses cleanly before the modal opens. The reveal digest is on by default, batched per
lifecycle beat, and scoped to newly-revealed pages, with each of those three
choices adjustable through wording overrides and the same durability seam as
the recaps. State durability is the last: the announced set
belongs on durable storage wherever the host offers one, with the startup
catch-up as the fallback on an ephemeral host.

## Preflight and verification

The bot's invite must include the Manage Events permission so convene can
read — and, if event creation is later used, create — scheduled events; the
native "interested" button needs no extra permission. Applying convene
requires the lore bot already deployed, the player role name known, and
the auto-events channel chosen. See [discord-setup](discord-setup.md)
for the server side and [capture](capture.md) for how the recording the
lifecycle nudges point at is produced.

The module ships a verifier that golden-tests the pure core with no Discord
present: the quorum state machine fires each reminder once and only when
due, the DM-required switch gates quorum, the ended state supersedes,
persistence round-trips and reconcile prunes dead events, message and prep
overrides fall back safely, and recap announce-detection surfaces each new
session page exactly once and never the back catalogue after a restart. The
reveal digest is covered too — a projection gaining several non-session
player pages yields one batched delta of exactly those pages, a re-poll adds
nothing, DM-only pages never appear, and a simulated restart re-announces
nothing — along with two durability regressions: a reminder due while the
announce channel is unset stays unfired until a channel exists, and a corrupt
state file loads as empty rather than crashing the bot at import.
Session-vs-other-event handling is golden-tested as well: with a keyword set,
a name-matching event runs the full session lifecycle while a non-matching one
yields exactly one heads-up and never quorum, at-risk, imminent, or ended; that
heads-up is idempotent per event id; with no keyword every event is a session,
back-compatibly; and the new heads-up template validates through the same
override machinery. The private response path is golden-tested at its pure
seam: the filed drop carries the player's words verbatim, ties back to the
ask's timestamp id, fits the worker's field caps, and the witness request is
a header-auth `tools/call` that never puts the token in the URL; source-level
checks pin `/session respond` ungated, every reply ephemeral, and no channel
send anywhere in the respond path. The
live driving of real scheduled events is proven separately, once deployed,
and is treated as unproven until that pass is recorded.

Convene is one of Eddic's [modules](index.md).
