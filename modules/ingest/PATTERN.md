# Pattern: session ingest — transcript into canon

Gives a campaign the step everything else is built around: a session
becomes a recap and a set of page updates, with each claim traceable to
the line that produced it. Capture and the transcriber deliver a
transcript; publish and the lore bot carry the result to the table.
Between them sat improvisation, and this is the pattern for it.

The prose is the agent's — that is deliberate and permanent. What is
deterministic here is everything around the prose: seeding the
transcriber with the campaign's own invented names, listing the anchors
a claim may cite, scaffolding the page with honest frontmatter, cutting
what the table took off the record, and checking afterwards that every
citation resolves.

Provenance is the point. "Automatic is the point" (AGENTS.md) means a
recap ships without the DM reviewing it first, and that is only safe if
a wrong fact can be traced back to what produced it. Without citations
a misheard proper noun becomes a wiki fact, projects to the player
tier, enters the bot's corpus, and is quoted to players as canon with
nobody able to say where it came from.

## Preflight

- cli, wiki, and lint patterns applied (wiki 0.5.0 / lint 0.6.0 or
  later — the lint must know the provenance checks).
- transcriber applied, or transcripts arriving some other way in the
  `[H:MM:SS] speaker: text` shape the anchors depend on.
- The table knows a machine reads every word of the transcript. This is
  the privacy disclosure the capture and recorder patterns carry; do not
  run an ingest for a table that has not been told.

## Procedure

1. Vendor the verb:

       cp scripts/ingest.py <campaign>/.eddic/lib/ingest.py
       uv run <campaign>/.eddic/eddic.py manifest record \
           --module ingest --version 0.1.0 --verbs ingest

2. **Before transcribing**, seed the recognizer with the campaign's own
   names:

       uv run <campaign>/.eddic/eddic.py ingest --glossary

   Pass the result to the transcriber's `--prompt`. Invented proper
   nouns are what speech recognition fails on, the campaign already
   knows every one of them, and this is the cheapest accuracy the
   pipeline will ever buy. It draws on page titles and on every
   correction recorded in a transcript's **Known mishearings** section,
   so the list gets better each session.

3. **Cut what was off the record.** Anything the table wanted excluded
   is marked `[OTR]` / `[/OTR]` in the transcript, then:

       uv run <campaign>/.eddic/eddic.py ingest --redact <transcript> --write

   This runs before anything reads the transcript, because the recap
   step sends it to a model. The cut leaves a visible marker rather than
   a silent gap: a redaction nobody can see is indistinguishable from
   nothing having happened, and the table should be able to confirm
   their ask was honoured. An unclosed `[OTR]` runs to the end of file —
   if someone said stop and nobody said start again, that is the safe
   reading.

4. **Scaffold the recap:**

       uv run <campaign>/.eddic/eddic.py ingest --scaffold <transcript> --session N

   The page arrives with `sources:` naming the transcript,
   `authorship: machine`, `curation: agent`, and no visibility marker.
   It is DM-only until someone marks it otherwise, on purpose.

5. **Write it.** Install `templates/ingest-brief.md` as the standing
   instruction for this work and follow it: read the whole transcript
   first, cite each non-obvious claim with `<!-- src: ... -->` against a
   real anchor from `ingest --index`, leave out what you are not sure
   you heard, and record resolved mishearings so the next transcription
   improves. Update the handful of other pages the session earned;
   route contradictions through the merge-proposal flow rather than
   overwriting.

6. **Check, then ship.** `eddic lint` resolves every `sources:` entry
   and every citation anchor: `source-missing` and
   `source-anchor-missing` mean a citation that looks like evidence and
   is not. Mark the recap `visibility: player` only after reading it
   back for anything the players did not learn. Then project, build,
   publish, and log an `ingest` entry naming the session and its
   sources.

## Decision points

- **Citation density.** Default: every non-obvious factual claim — a
  name, a death, a promise, a debt, a location — and nothing else. Your
  own connective prose does not need a marker, and a claim already
  carried by a page you link to is cited there. Denser than that makes
  recaps unreadable in the master and buys nothing, since the markers
  are stripped from the player copy anyway; sparser, and the first
  disputed fact is untraceable, which is the whole failure this exists
  to prevent.
- **Recap visibility.** Default: player-visible, marked deliberately
  after a read-back. A recap is the most-read page a campaign has and
  the one players actually want, so DM-only recaps are rare — but the
  marking stays a decision rather than a scaffold default, because a
  secret said aloud at the table is a secret the firewall cannot see.
- **Off-the-record marking.** Default: the DM marks `[OTR]` regions
  after the session while the transcript is still theirs alone. A
  live `/record-pause` is the better ergonomic and is a stated gap in
  the recorder pattern; until it exists, post-hoc marking is the whole
  facility, and the table should be told that is how it works.
- **Redaction timing.** Default: before the recap is written, always.
  Redacting afterwards means the model already read it, which is the
  thing the table asked you not to do.
- **Who ingests.** Default: the DM's own agent, on the DM's machine,
  against the DM-tier corpus. A hosted routine can lint and can file
  suggestions, but authoring canon from a verbatim transcript is the
  most sensitive read in the campaign and it belongs where the audio
  already lives.

## Verify

- `uv run modules/ingest/verify/run.py` — deterministic floor: the
  glossary draws page titles and known-mishearing corrections and skips
  recap titles; `--index` lists real anchors and refuses to invent
  them; `--scaffold` writes correct frontmatter and refuses to
  overwrite an existing recap; `--redact` cuts `[OTR]` regions
  including an unclosed one, leaves a visible marker, and is
  idempotent.
- Provenance enforcement lives in the lint module's verify: a `sources:`
  entry naming no file is `source-missing`, and a citation anchor absent
  from the transcript is `source-anchor-missing`.
- In the real campaign: run an ingest end to end, then open the
  projected recap and confirm no `<!-- src:` marker survived into the
  player copy — the projection strips them, and view-source is where a
  surviving one would show up.
