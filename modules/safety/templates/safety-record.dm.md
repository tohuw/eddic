---
visibility: dm
authorship: human
curation: human
---

# Table safety (DM record)

The master. Every line and every veil the table has set, with who set
it. This page is DM-only and stays that way: the `.dm` in its name is
what keeps it off every player surface, so attribution can live here
safely and nowhere else.

The table's copy is `safety.md`, and it is generated from this file by
`eddic safety render`. Never write to it directly — the render drops
`from:` and drops every `dm-only` entry, and that is what makes "the
table does not learn who asked" a property of the build rather than
something to remember.

## Format

Each entry in `## Record` is a `###` heading naming the topic, followed
by flat fields:

    kind    line or veil. A line is never in the game in any form.
            A veil may exist in the world but is never played out.
    share   table or dm-only. `table` puts the entry (never the name)
            on the players' page, which is the default and the useful
            case: everyone at the table can then keep the rule. Use
            `dm-only` when the entry text would itself identify the
            person who set it; the DM and the agents still honour it,
            the table never sees it.
    from    the contributor id from `contributors.dm.md`, or
            `anonymous` when the person asked for no record at all.
            Kept so the DM can close the loop later — a removal, a
            check-in — and never rendered anywhere.
    note    what the entry means in play, in one or two sentences.
            Written for whoever is running the scene, not for a
            justification. Wrapping lines are fine.

Add, change, and remove entries freely; nothing here needs a reason
recorded against it. Run `eddic safety render` and `eddic safety check`
afterwards, then lint and project as usual.

## Preamble

This page is the table's record of what this campaign does not put on
screen. It was set at session zero and it changes whenever anyone wants
it to. Entries carry no names: who asked for a line is not recorded
here.

## Signals

Anyone can stop or rewind a scene at any time, without giving a reason
and without saying which entry it was.

- Say it out loud: "X-card", or "let's veil that".
- Type X in the table's text channel. Nobody has to speak.
- React with the agreed reaction on the pinned signal post. Nobody has
  to type.
- Send the DM a private message. Nobody else sees that it happened.

All four do the same thing: play stops, the scene backs up to before
the material, and it goes differently. No one asks what it was about,
at the time or afterwards. Leaving the call is also a signal and needs
no explanation.

## Changing this

To add or remove an entry, tell the DM privately. Nothing needs a
reason and nothing is negotiated. Additions appear here without
announcement. The DM re-sends the session-zero questions from time to
time so nobody has to raise it cold.

## Record
