# ingest

The ingest module is the step the rest of Eddic is built around: a session
transcript becomes a recap and a set of page updates, and every non-obvious
claim in them can be traced back to the line of transcript that produced it.
Capture and the [transcriber](transcriber.md) deliver the transcript; the
[wiki](wiki.md) holds the result, [lint](lint.md) checks it, and
[publish](publish.md) and the [lore bot](lore-bot.md) carry it to the table.
Between them there used to be nothing but improvisation, which is a strange
gap in a toolkit whose entire premise is that the agent writes the campaign
down.

## What is deterministic and what is not

The prose stays the agent's, permanently. Composing a recap is the one step
here that cannot be computed, and pretending otherwise would produce the
kind of output nobody reads. What the module makes deterministic is
everything wrapped around the prose, because those are the parts that go
wrong silently: seeding the recognizer with the campaign's own invented
names, listing the anchors a claim may cite, scaffolding the page with
honest pen-axis frontmatter, cutting what the table put off the record, and
proving afterwards that every citation resolves.

`eddic ingest --glossary` builds a whisper prompt from the wiki's page
titles and from every correction previously written into a transcript's
"Known mishearings" section. Invented proper nouns are where speech
recognition fails hardest and where the campaign already knows every answer,
so this is the cheapest accuracy in the pipeline — and because corrections
feed forward, the same name stops being mangled after the first time someone
fixes it. `--index` lists the citable anchors. `--scaffold` writes the recap
page. `--redact` cuts off-the-record passages.

## Provenance, and why it makes automation safe

Eddic's doctrine is that the agent ships without waiting for the DM to bless
the result. That is only defensible if a wrong fact can be traced to
whatever produced it. Without citations, a misheard proper noun becomes a
wiki fact, projects to the player tier, enters the bot's corpus, and is
quoted back to players as canon with nobody able to say where it came from —
and the correction path is archaeology.

So a page derived from a session carries `sources:` in frontmatter naming
every transcript and handout behind it, and individual claims carry a marker
naming the moment they were established:

```
The party reached the Sunken City by the low road.
<!-- src: sessions/session-4-transcript.md#t=0:41:07 -->
```

The marker is an HTML comment because it must never reach a player: the
projection strips it, which matters because a comment survives rendering
into view-source. The lint resolves both — `source-missing` when a cited
file is not there, `source-anchor-missing` when a timestamp is not in the
transcript — on the principle that a citation which does not resolve is
worse than none, since it has the appearance of evidence.

## Off the record

A session transcript is read in full by a third-party model when the recap
is written, and a table's four hours contain a great deal that was never
about the game. `[OTR]` and `[/OTR]` markers bracket anything the table
wants excluded, and `--redact` removes those passages before anything else
reads the file. The cut leaves a visible marker rather than a silent gap, so
the table can confirm their request was honoured; an unclosed marker runs to
the end of the file, because if someone said stop and nobody said start
again, that is the safe reading. Marking is currently post-hoc, done by the
DM while the transcript is still theirs alone — a live pause command is a
stated gap in the [recorder](recorder.md) pattern.

## Verification

`modules/ingest/verify/run.py` plants a campaign and proves the
deterministic half: the glossary draws on page titles and recorded
mishearings and skips recap titles, deduplicating so a corrected name is not
repeated from its own page; the anchor index reports exactly the timestamps
the transcript contains and invents none; scaffolding writes machine
authorship with no visibility marker and refuses to overwrite an existing
recap; and redaction cuts marked regions including an unclosed one, leaves
its marker, and is safe to run twice. The provenance checks themselves live
in the [lint](lint.md) module's verify, where the rest of the wiki's
structural rules are proven.
