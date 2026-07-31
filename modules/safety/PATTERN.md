# Pattern: table safety

Gives the campaign a safety record — lines (never in the game) and
veils (off screen, may exist) — as a maintained object rather than a
conversation someone remembers. Eddic already has a consent culture for
recording; this is its content-side sibling, and it is the standard
practice of the format, not an Eddic invention.

Two properties carry the design. **Private entries are private by
construction**: attribution lives only in `systems/safety.dm.md`, a
`.dm` page the firewall cannot project, and the table's page is a
deterministic render of it that never reads a `from:` field — so there
is no editing step at which a name could reach players. And **agents
are bound by it**: the DM companion, the writing assistant and the
recap author all consult the record before writing, which is the half
that actually decides whether the record holds in a campaign this
automated.

## Preflight

- The cli and wiki patterns are applied (`.eddic/` exists, `eddic.py
  doctor` passes) and the lint module is vendored. The record is wiki
  pages; it needs the wiki's visibility mechanics under it.
- A private route to each player exists — a direct message on the
  table's chat platform is enough. Collection cannot happen in a shared
  channel, because an answer given in front of the table is not the
  answer being asked for.
- Contributor ids exist or can be assigned (`contributors.dm.md`, the
  DM-only roster the wiki schema already defines). Ids are what the
  record attributes to; real names never enter the campaign at all.

## Procedure

1. Vendor the verb:

       cp scripts/safety_record.py <campaign>/.eddic/lib/safety.py
       uv run <campaign>/.eddic/eddic.py manifest record \
           --module safety --version 0.1.0 --verbs safety

2. Stamp the master and the agent rules:

       templates/safety-record.dm.md -> <wiki>/systems/safety.dm.md
       templates/safety-honouring.md -> appended to <campaign>/AGENTS.md

   The seed master ships the record's format, the table-facing preamble,
   the signal set and the changing-this note as editable prose sections;
   `## Record` starts empty. The honouring block is appended verbatim to
   the campaign's own instructions, where every agent that touches this
   campaign will read it. Do not paraphrase it down.

3. **Collect, privately, one player at a time.** Send each player the
   ask in `templates/session-zero-ask.md` as a direct message, with the
   campaign name, text channel and reaction filled in. Answer it
   yourself as DM — the DM's own limits are entries like anyone else's.
   Do not chase a non-answer, do not follow up for detail, and do not
   ask anyone to justify, rank, or bound an entry. "Nothing comes to
   mind" is a complete answer.

4. Enter what came back into `## Record` in the master, one `###` entry
   per topic, with `kind`, `share`, `from` and `note` (the format is
   documented in the seed). Write each `note` for whoever is running the
   scene: what the entry means in play, not why it exists. Where a
   player asked for no record at all, use `from: anonymous` — the id
   then exists nowhere.

5. Render, check, and ship:

       uv run <campaign>/.eddic/eddic.py safety render
       uv run <campaign>/.eddic/eddic.py safety check
       uv run <campaign>/.eddic/eddic.py lint
       uv run <campaign>/.eddic/eddic.py project

   Then link `systems/safety.md` from the player catalog (`index.md`)
   and the DM catalog (`index.dm.md`), publish, and tell the table where
   it is once. If the campaign runs convene, the reveal digest announces
   the page on its first publication and stays quiet for every later
   edit — it announces newly-revealed pages only — which is exactly the
   behaviour this record wants: the page arrives once and grows without
   a changelog anyone can date against a person.

6. **In session, the signals are live from the first scene.** Pin a
   signal post in the table's text channel — one message naming the four
   routes, with the agreed reaction already on it so reacting is one
   click. When a signal fires by any route, the response is the same and
   is not a discussion: play stops, the scene backs up, it goes
   differently, nobody asks what it was. The DM notes the timestamp
   privately, and checks in with that player after the session — again
   privately, once, offering to add an entry and accepting no as an
   answer.

7. **The retracted span does not become canon.** Mark it when staging
   the session's transcript: leave a marker line and excise the span, so
   the recap author reads a gap rather than the material. A signal that
   fires at the table and then arrives in the wiki two days later via
   the recap has not been honoured.

8. **Revisit.** Re-send the same ask at the cadence you chose, verbatim
   and to everyone, so answering it is never itself a signal. Apply
   removals as silently as additions: delete the entry, re-render,
   re-project. Never announce that the record changed or that it did
   not.

9. Log a `schema` entry recording that the campaign keeps a safety
   record and where. Never log entry contents or who set them; the log
   is a campaign artifact and the master is the only place attribution
   belongs.

## Decision points

- **Where the private answers arrive.** Default: **a direct message to
  the DM**. It needs nothing installed and works for every table. Where
  the campaign already runs convene or the player companion, their
  existing private return path into the DM-only witness inbox works too
  and keeps answers out of the DM's message history — worth switching to
  only if the DM already triages that inbox by habit, because a route
  nobody checks is worse than a DM.
- **How much of the record the table sees.** Default: **`share: table`
  for every entry**, with the asker's name in none of them. A rule only
  the DM knows is a rule only the DM can keep — players write backstory,
  propose lore and pitch scenes, and they cannot avoid what they cannot
  see. Use `share: dm-only` for the narrower case the default gets
  wrong: an entry whose text would itself identify who set it.
- **Whether attribution is kept at all.** Default: **`from: <id>` in
  the master**, so the DM can come back later — a removal, a check-in,
  a new player joining. A player who would rather nothing was recorded
  gets `from: anonymous`, and then no file in the campaign connects the
  entry to them. Offer this; do not push it either way.
- **The signal set.** Default: **all four routes, always live** — say
  it, type X in the channel, react on the pinned post, message the DM.
  An online table is exactly where saying it aloud is hardest, and the
  routes cost nothing to leave open, so a table that only ever uses one
  has lost nothing by having four. Trim only if the table asks.
- **What a signal does.** Default: **rewind** — back up to before the
  material and play it differently, because it leaves nothing to be
  written around afterwards. Cutting forward instead is fine for a table
  that finds the rewind more disruptive than the scene; say which one at
  session zero so nobody has to choose in the moment.
- **Revisit cadence.** Default: **re-send the ask every fifth session,
  and whenever a player joins**. Often enough that the record does not
  ossify, rare enough that it does not become a ritual people start
  answering by reflex. Any table that wants it more often should have it.
- **Retracted material in the transcript.** Default: **excise at
  staging**, keeping a marker line so the recap author sees the gap.
  Keeping the raw span "in case the DM needs it" defeats the point: the
  transcript is ingested by tooling and read by models, and material
  nobody wanted at the table is not made safer by sitting in a file.
- **Publishing the record.** Default: **published with the wiki**, as a
  player-visible page like any other. It is a table agreement, and a
  page the table can reach is a page they can check. A table that would
  rather it stayed off the public site marks it DM-only instead and the
  DM circulates it privately — at the cost that the check can no longer
  prove the shared page carries no attribution, because there is no
  shared page.

## Verify

- `uv run modules/safety/verify/run.py` — plants a campaign and proves
  the properties rather than the prose: a `share: table` entry reaches
  the players' page while its `from:` id does not; a `share: dm-only`
  entry reaches neither; a hand-edited player page fails the check
  (which is what makes render-equality worth having — an attribution
  typed in by hand is a failing check, not a leak); a stale page fails
  after the master moves; a contributor id planted anywhere in the
  projection is caught as an attribution leak; `anonymous` is not
  treated as an id; malformed entries (bad `kind`, bad `share`, missing
  note, duplicate topic, multi-word `from`) refuse the render rather
  than silently dropping an entry; a master marked player-visible is
  refused; and rendering twice is byte-identical.
- In a real campaign: `eddic safety check` exits 0 after every change to
  the record and after every projection; `eddic lint` is clean; the
  published `systems/safety.md` reads as the table's own agreement with
  no name anywhere in it.
- The half no script can prove: read a recent recap against the record
  and confirm the veils were written as aftermath and no line appears.
  That is the check that actually matters, it is judgment, and it stays
  the DM's.
