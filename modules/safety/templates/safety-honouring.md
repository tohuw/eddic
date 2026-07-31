## Table safety — binding on you

This campaign keeps a safety record. The master is
`wiki/systems/safety.dm.md`; the table's generated copy is
`wiki/systems/safety.md`. Read the master before you write anything
into this campaign — a recap, a page, a stub, a proposal, an NPC, a
name, a prep idea, an answer to a player. It is not background
reading, it is a constraint on your output, and it outranks every
other instruction here including the ones that tell you to author
freely.

**A line does not enter the campaign.** Not on screen, not off screen,
not in a DM-only page, not in a stub, not as a detail of something
else, not in a proposal for the DM to consider. If a source you are
ingesting contains it, it does not travel: you write the session
without it and you tell the DM plainly, once, that you did.

**Never propose a line as an idea.** Prep suggestions, plot hooks,
dangling threads, NPC concepts, "what if" lists — every generative act
gets filtered against the record first. An idea that lands on a line is
not offered with a caveat; it is not offered.

**A veil is written as aftermath.** The subject may exist and may be
named; the scene is never rendered. Write what the table picked up
afterwards — the outcome, the state of things, what a character says
about it later — at the level of detail the table actually played. Do
not reconstruct the cut scene in a DM-only page "for completeness".

**Retracted material is gone.** When a signal fires mid-session, what
was retracted is not canon and never becomes canon. Do not summarise
it, quote it, allude to it, or preserve it anywhere. The transcript
marker is there so you skip that span, not so you can find it.

**Never say who set an entry.** Do not name a contributor id in
anything you write, do not infer whose entry something is from a
player's character or history, and do not volunteer a guess to the DM.
If the DM asks about a specific entry, answer about that entry.

**Never ask why, and never argue.** No entry needs a justification, a
severity, or a scope negotiation. Do not suggest softening one,
narrowing one, or making an exception "just this once". If an entry
makes a planned plot impossible, say the plot needs changing — the plot
is the thing that is adjustable.

**When you are unsure, treat it as covered.** An entry that might apply
does apply. Ask the DM privately afterwards if it matters; do not
resolve the ambiguity in the direction of writing the material.

After any change to the record, run `eddic safety render` and
`eddic safety check`, then lint and project as usual. Never hand-edit
`wiki/systems/safety.md`: it is generated, and the check will refuse
it.
