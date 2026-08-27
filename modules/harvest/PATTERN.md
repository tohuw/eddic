# Pattern: harvest the table's chatter

Turns what the table already says in Discord into wiki work: rulings the
DM dropped between sessions, questions nobody could answer, and names
the table spells correctly that the transcripts mangle. It runs nightly,
spends no tokens until a model reads a pre-compressed packet, and files
everything it finds as suggestions the owner triages.

The premise is that **Discord is already the log**. A bot that writes
its own copy of every message owns durability, retention, and the
awkward fact that it has kept things people deleted. This module keeps
one message id per channel instead — a watermark — and asks Discord for
what came after. The state file holds ids and timestamps and never a
word of what anyone said; the script enforces that rather than promising
it, because it is the claim the table is owed.

## Preflight

- The [lore-bot](../lore-bot/PATTERN.md) pattern is applied, or the
  campaign otherwise has a Discord bot application whose token it can
  reach. Harvest reuses that identity; it does not want one of its own.
- The bot is in the guild and can **read** the channels the owner intends
  to harvest. A channel it cannot read fails loudly and holds its
  watermark; it never silently produces nothing.
- **The application has the Message Content privileged intent enabled**
  (Developer Portal → Bot → Privileged Gateway Intents). Without it
  Discord still returns every message over REST, complete and wordless —
  the content field is simply empty. That is indistinguishable from a
  quiet channel by eye, so the pull detects it, refuses the channel, and
  holds the watermark rather than sailing past a window nobody read. If
  a campaign runs several bots, the harvest wants the lore bot's token:
  it already needs that intent to answer questions, while a recorder or
  dice bot generally does not have it.
- The campaign has a built projection (`dist/player` or equivalent). The
  naming pass compares chat against it, and without it every proper noun
  looks novel.
- Decide the allow-list before running anything. Harvest reads **only**
  the channels named in config: an allow-list, never a deny-list, so a
  channel created later is private by default.

## Procedure

1. **Tell the table.** Before the first run, say in the server what is
   being collected, from which channels, and what is kept. The recorder
   module sets the standard for audio and text deserves the same
   treatment; this is a decision point below, not a formality. Name the
   opt-out and honor it: `optout_ids` drops a person's messages before
   they reach the packet.

2. **Configure.** Under `harvest` in the campaign config:

       "harvest": {
         "channels": {"<channel id>": "<label>", ...},
         "dm_ids": ["<the DM's user id>"],
         "bot_ids": ["<the lore bot's user id>"],
         "optout_ids": [],
         "corpus_dir": "dist/player",
         "question_log": "bot/questions.jsonl",
         "state_file": ".eddic/harvest-state.json"
       }

   `dm_ids` is the load-bearing field. Only messages from those ids can
   become canon candidates; everything else is a player talking, however
   confident they sound.

3. **Pull** (deterministic, zero tokens):

       uv run modules/harvest/scripts/harvest.py --pull \
           --config <campaign>/.eddic/config.json \
           --out <campaign>/.eddic/harvest-packet.json

   Watermarks advance only for channels that returned messages, so a
   failed or empty channel loses nothing. The packet carries the DM's
   substantive statements, the table's questions, whatever the lore bot
   could not answer from its own log, and proper nouns the projection
   does not contain — pre-compressed, with any dropping stated in
   `compression_notes`.

4. **Read the packet** against its own `checklist` and `not_in_scope`,
   and emit findings in the packet's `findings_schema`. This is the only
   step that spends tokens and the only place judgment enters. Report a
   contradiction; do not adjudicate it.

5. **Validate**, so a malformed finding never reaches the owner:

       uv run modules/harvest/scripts/harvest.py --validate findings.json

6. **File** each finding through the [retrieval](../retrieval/PATTERN.md)
   witness inbox as a `suggest_edit`, exactly as the semantic-review
   routine does — or, where that path is off, write them under
   `suggestions/` and open a PR. Nothing here writes canon. If a finding
   needs the DM to rule rather than the wiki to change, it belongs in
   `dm-questions.dm.md`, which is a suggestion like any other.

7. **Feed the transcriber.** `naming` findings are worth more than wiki
   edits: chat spelling is right and transcript spelling is wrong, so
   they belong in the transcript's mishearings table and in
   `ingest --glossary`, where they stop the same mistake recurring.

## Decision points

- **Which channels.** Default: **the channels where the table talks
  about the game and nothing else** — a rules channel, a general channel,
  the lore bot's auto-answer channel. Never a DM-only channel, never
  direct messages (harvest cannot read them and should not be given the
  chance), never an off-topic or social channel. When the owner says
  "just pick," take the lore bot's `AUTO_CHANNEL_IDS` plus the rules
  channel: those are where questions already land.
- **Telling the table.** Default: **a plain message in the server before
  the first run**, naming the channels and the opt-out. The
  when-it's-worth-more heuristic: a table that already accepted
  react-gated session recording will accept this in one line; a table
  that has never been recorded deserves the longer version and a chance
  to object before anything runs.
- **Cadence.** Default: **nightly**, off-session, so a night's play is
  harvested with the following day's chatter and the routine never
  competes with a live session. A quiet table can run weekly; the pull
  is idempotent and a missed run just widens the window.
- **Page cap.** Default: **20 pages (2,000 messages) per channel per
  run**, which no table exceeds in a day. A first run against a busy
  server with old channels will hit it, say so, and pick up the rest on
  the next run — that is a truncation notice, not a failure.
- **What the first run harvests.** Default: **only what arrives after the
  first run**, since a fresh watermark starts at the present. Backfilling
  history is possible by seeding a watermark by hand and is usually a bad
  trade: the table consented to what happens next, not to a retroactive
  read of everything it ever said.

## Verify

    uv run modules/harvest/verify/run.py

Runs offline against a fake Discord and proves the properties this
pattern claims: watermarks advance for channels that answered and are
withheld for channels that failed; a second run against the same fixture
returns nothing; an opted-out author is absent from the packet; only the
DM's words appear as canon candidates and short chatter is not promoted;
a proper noun the projection already knows is not reported as novel; the
state file contains no message text; a malformed finding is rejected;
and an oversized packet is compressed and says so.

With a real server: run the pull twice. The first writes a packet and a
state file; the second returns zero messages. Read the state file and
confirm it contains ids and timestamps and nothing anyone said.
