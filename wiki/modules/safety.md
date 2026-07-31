# safety

The safety module gives a campaign a maintained safety record — lines,
which are never in the game in any form, and veils, which may exist in the
world but are never played out — instead of an agreement someone half
remembers from session zero. It is the standard practice of the format
rather than anything Eddic invented, and it is the content-side sibling of
the consent culture the [recorder](recorder.md) and [capture](capture.md)
patterns already carry for recording.

Two properties carry the design.

## Private entries are private by construction

A player must be able to set a line without the table learning it was
theirs, and that cannot rest on anyone remembering to be careful. So
attribution lives only in `systems/safety.dm.md`, a `.dm` page the firewall
cannot project, and the table's copy at `systems/safety.md` is a
deterministic render of that master which never reads a `from:` field at
all. There is no editing step at which a name could reach players, because
the only thing that writes the shared page is a function structurally
incapable of emitting one.

Entries marked `share: dm-only` do not reach the table in any form — not
the topic, not the note — for the case where the entry text would itself
identify who asked. The DM and the agents still honour it.

`eddic safety check` proves the pairing holds: the shared page is exactly
what the master renders (so a hand-edit is caught rather than silently lost
on the next render), it is marked player-visible so the table can actually
read its own record, no `dm-only` entry has leaked into it, and no
attributable contributor id appears on any player-facing surface it is
pointed at. `anonymous` is deliberately not attributable, so a person can
be recorded as having asked for nothing at all.

## Agents are bound by it

This is the half that decides whether the record survives contact with a
toolkit this automated. A safety record the DM honours and the agents do
not is worse than none, because the agents write most of the campaign. The
DM companion, the [writing assistant](companion.md), and the recap author
in the [ingest](ingest.md) loop all consult the record before writing: a
line is never authored into canon and never offered as an idea, and veiled
material is handled as aftermath rather than played out on the page.

## Collection and revision

Session zero collects the record through a private route — a direct
message, never a shared channel, because an answer given in front of the
table is not the answer being asked for. The ask is re-sent periodically,
because these change: a player's line in year two is not the one they had
in month one, and a record nobody revisits quietly becomes wrong.

In-session signals cover stopping or rewinding a scene, including a route
that works for an online table where saying it aloud is the hard part.
Retracted material has a defined path out of the session transcript, which
matters because the transcript is read in full by a model when the recap is
written.

## Verification

`modules/safety/verify/run.py` proves the deterministic floor: the render
drops attribution and every `dm-only` entry, marks the table's copy
player-visible, and is a no-op run twice; `check` catches a hand-edited
shared page, a contributor id reaching a player-facing surface, and a
master that has been marked `visibility: player`; and the schema refuses —
rather than silently dropping — an entry with a bad kind, a bad share, no
note, a duplicate topic, or fields before any entry heading. Silent
dropping is the failure that matters here, because a dropped entry is a
line the table stops seeing.

The half no script can prove is left to the DM: reading a recent recap
against the record and confirming the veils were written as aftermath and
no line appears at all.
