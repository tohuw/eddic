# harvest

The harvest module mines what the table already says in Discord for wiki
work. It runs nightly, pulls the channels the owner allow-lists, and
assembles a packet the maintaining agent reads for three things: rulings
the DM dropped between sessions, questions nobody could answer, and
names the table spells correctly that the transcripts mangle. Everything
it finds becomes a suggestion the owner triages. It depends on
[cli](cli.md), [wiki](wiki.md), [lore-bot](lore-bot.md), and
[routines](routines.md), and touches only `.eddic/`.

## Discord is already the log

The obvious build is a bot that appends every message it sees to a file.
The module deliberately does not do that. A write-ahead log owns
durability (an ephemeral host loses it), owns retention, and quietly
keeps things people deleted. Harvest keeps one message id per channel
instead — a watermark — and asks Discord for what came after. The state
file therefore holds ids, counts and a timestamp, and never a word of
what anyone said; the script asserts that on every save rather than
promising it in prose, because it is the claim the table is owed. A
missed night widens the next window and loses nothing, since Discord
kept the messages and this module did not.

The one thing watermarks cannot recover is what the lore bot was asked
and whether it could answer. That already lives in the bot's own
question log, and harvest reads it rather than collecting it twice.

## The three products

**The gap index** is the cheapest and the best. Every question the lore
bot answered with "the archive doesn't say" is a page the wiki is
missing, phrased in a player's own words and weighted by how often it is
asked. **Canon capture** is the DM's between-session rulings, and its
load-bearing field is the author id: only a configured `dm_id` can
produce a canon candidate, because a player asserting lore confidently
is still a player. **Naming drift** compares proper nouns typed in chat
against the built projection — chat spelling is right and transcript
spelling is wrong, so these findings feed the transcriber's mishearings
table as much as the wiki.

## What it refuses

A channel it cannot read fails loudly and keeps its watermark. A channel
that hits the page cap says so. And a bot application without the
Message Content privileged intent is caught explicitly: Discord returns
every message complete and wordless in that case, which looks exactly
like a quiet channel, so the pull detects the empty window, names the
intent, and holds its place rather than advancing past text nobody read.
That failure was found by running the pattern against a live guild with
the wrong bot's token, which is the only way it would ever have been
found.

## Privacy posture

The channel list is an allow-list, never a deny-list, so a channel
created later is private by default. Direct messages are unreachable and
stay that way. An `optout_ids` entry drops a person's messages before
they reach the packet. The pattern's first procedure step is telling the
table what is collected and from where — the [recorder](recorder.md)
module set that standard for audio, and text is not owed less.

## Where it runs

The recommended shape is in the [lore bot](lore-bot.md)'s own process, as
a capability on the same seam [convene](convene.md) uses: vendor
`harvest.py` and `harvest_capability.py` beside `bot.py`, name
`harvest_capability` in `CAPABILITIES`, and it wakes once a night. The
reason is that everything the harvest needs is already in that process —
the token with the Message Content intent, the corpus in memory, the
question log on the same disk, and a model provider with the corpus
prompt-cached. A standalone service would duplicate all four and, on a
host with per-service disks, could not read the question log at all.

That makes it a fourth rung on the [routines](routines.md) runner chain:
inside a process the campaign already runs. Campaigns without a deployed
lore bot use the scheduled contract instead, which is what
`routine-harvest.md` specifies.

On an ephemeral host the question log, the harvest state, the salt and
the opt-out list all belong on a mounted volume. A lost salt rotates
every asker tag; a lost opt-out list un-opts-out everyone who asked not
to be recorded. Neither failure announces itself.

## Verify

`uv run modules/harvest/verify/run.py` runs offline against a fake
Discord and proves the properties the pattern claims: watermarks advance
for channels that answered and are held for channels that failed; a
second run returns nothing; an opted-out author is absent; only the DM's
words become canon candidates and short chatter is not promoted; a
proper noun the projection knows is not reported as novel; the state
file contains no message text; a wordless channel is named as a missing
intent and holds its place; malformed findings are rejected; and an
oversized packet is compressed and says so.
