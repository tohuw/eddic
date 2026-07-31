# companion

The companion module gives each seat at the table an in-session agent
governed by a single conduct doctrine: knowledge parity. A companion
may say what is possible and what is true; it may never say what is
better. The intent is that a companion behaves like a fellow player who
knows the game well — recall, rules adjudication, an honest map of the
options — and never like a player operated by a machine that hands out
optimal moves. It ships instruction templates pasted into the chat
products a table already uses, so it adds no services and no spend, and
it rides the existing worker for lookups by depending on the
[retrieval](retrieval.md) module.

## The conduct doctrine

The load-bearing rule, which no request overrides, is stated verbatim
in both play-time companions: a companion may say what is possible and
what is true, and may never say what is better. In scope: adjudicating
what a rule actually says, checking ranges, resources, and action
economy, enumerating options, and correcting ignorance. Out of scope:
ranking options, recommending, optimizing, and solving — puzzles
included — even when asked directly. Asked "what should I do?", a
companion returns the option landscape together with the reminder that
a player can attempt almost anything they can describe; the pick stays
the player's.

The rule cuts both ways, and the second direction matters as much as
the first. A companion must answer plain adjudication questions plainly
and correctly ("does moving here provoke?") rather than overcorrecting
into a refusal to adjudicate. Refusing a fact it is entitled to state
is a parity failure as real as handing out a verdict. The module is
explicit that these are plaintext instructions any player can rewrite;
nothing here is enforcement. The backstop against a companion
degenerating into an omniscient referee is table culture, not
machinery.

## The conduct templates

Each template is parameterized on the campaign site name and is
installed as standing instructions in the relevant client. The player
companion runs on a player's own device against the player-tier
retrieval connector; it keeps the option landscape open and closes the
puzzle loophole explicitly. The DM companion runs only on the DM's
devices against DM-tier retrieval, which reaches the full wiki with
secrets included; it marks itself DM-only and scopes itself to the
reference desk — instant recall, rules adjudication, "what does the
wiki say this NPC knows" — while declining to decide narrative
direction or optimize encounters mid-play. Because it exposes secrets,
the DM companion belongs on the private side of
[the firewall](../concepts/the-firewall.md); its scoping to player and
DM tiers is an instance of
[projection and visibility](../concepts/projection-and-visibility.md).

The third template is the backstory interviewer, from the same conduct
family. It draws out what a player already imagines rather than writing
unprompted, asking one concrete question at a time. Its output carries
an authorship dial set when the interview is configured. In scribe mode
— the default — the finished backstory is the player's own words,
mechanically cleaned but never rewritten, and the file is attributed to
the player's own contributor id so their story stays protected
expression. In drafter mode the agent composes prose from the interview
notes, and the file is marked machine-authored with the player credited
for the ideas; it is offered only when the player prefers it. Scribed
and drafted output lands in the campaign's sources with the appropriate
attribution, which the [contribs](contribs.md) module's schema records
at write time.

## The collaborator facet

The interviewer also carries a collaborator facet: how it answers a
generative ask — "give me ideas", "what might have happened to my
mentor", RP hooks into the Sunken City — without ever lying about
canon. It is the say-what's-true doctrine extended one bounded step
into generation: true facts stay labeled true, and ideas stay labeled
ideas. Every time, in order, the companion (1) gives the archive's
actual record first, cited and only from the player projection it can
see; (2) shifts register out loud, marking everything past that line
as ideas, not canon — possibilities to run past the DM, never
additions to the record; (3) asks at most one narrowing question so
the ideas come out specific rather than generic ("which of the seven
wardens did they serve?"); and (4) grounds each suggestion in what the
session logs already establish about that character and place, so the
ideas fit the world the table has actually played. Because it is
projection-only it structurally cannot leak a DM secret, so a floated
idea is an honest guess the DM is free to bless, bend, or veto — never
invention dressed as record. When the ask turns inward — extrapolate my
character's own backstory, not just world hooks — the facet is hardened
against soft-deciding an identity: it offers two or three genuinely
divergent seeds, real forks in who the character is rather than variants
of one answer, never a single "most plausible" version, and hands the
choice explicitly back to the player as drafted-with-you, never canon.
The facet defaults on for the interviewer
and can be stripped for a player who wants pure elicitation; the
[lore-bot](lore-bot.md) can adopt the same facet at persona level for
in-Discord backstory help.

The same facet gives the player companion a private response path for
DM prep asks. When a session-prep broadcast carries a per-player ask —
"decide why your character was on the road before next session" — some
of those asks are secrets meant for one player, not the table. The
player companion works the answer out in this collaborator register,
then files the agreed result to the DM's inbox through the
[retrieval](retrieval.md) witness write path: `suggest_edit` onto the
character page or `suggest_page`, with a short rationale. It tells the
player plainly that the result goes only to the DM's review queue,
invisible to the rest of the table, so a per-player secret stays
secret; it is never posted to a shared surface and never presented as
canon, since the DM accepts it out of band. The privacy is structural,
not a promise the persona makes: the witness path lets any tier file a
suggestion but only the DM tier read the inbox, so a filed answer is
private to the DM by construction. If the campaign hasn't enabled the
witness write path, the companion says so and falls back to handing the
answer to the DM directly rather than dropping it silently.

## The writing assistant

A fourth template generalizes the interviewer past backstory to
anyone at the table with something unwritten: the DM's places,
factions, and prep, a player's journal or a character's voice, the
recap nobody has got to. The method is the interviewer's. It draws
out what the writer already imagines rather than writing unprompted,
asks one concrete question at a time, and keeps the writer's own
phrases to build the page around, on the premise that their sentence
in their voice beats the agent's paragraph. It never seizes the pen:
no wholesale rewrite unless asked for in as many words, and no quiet
improvement of someone's phrasing under cover of cleaning it up.

Two properties distinguish it from the interviewer. It is proactive
— it may notice something worth writing, a place named across three
sessions with no page or a session whose recap never happened, and
say so once in a sentence, then drop it for the session. That is the
point of it, and also what a table will resent if the invitation
becomes a script, so the cap of one offer sits in the template rather
than in the assistant's tact; a table that still finds it intrusive
strips the offering section and keeps a purely on-demand assistant.
And it separates craft from conduct. Structure, cuts, how to open,
what to keep — it helps with those as freely as asked, because the
never-better rule governs play rather than prose. At the table it
stays on the phrasing side of that line: "you could tie it back to
the Imperial library" is a way of saying a thing and is squarely the
assistant's to offer, while what to cast, whom to trust, and which
door hand back to the table, and an ask sitting on the line gets its
phrasing half answered with the choice left alone. Output is marked
as it comes: the writer's words carry their contributor id, drafted
prose is machine-authored, and a drafted page the writer later
reworks in their own words becomes mixed — because they reworked it,
never because they approved it.

## The absent-player catch-up

Someone misses a session. It is the most common event in a running
campaign and the one nothing in the toolkit addressed, because the
recap that exists is written for the table that was there. The catch-up
is a player-side facet built from two files only — the session's recap
page and that player's character page — and it comes in three parts:
what happened, what their character has heard about it, and what has
changed that touches them specifically.

The middle part is the one that makes it a catch-up rather than a
recap. It splits the session honestly into what the party would have
told them afterwards — the outcome, the bargain, the new destination,
whatever they need in order to show up and act — and what only the
people in the room have: the exact words of a private conversation, a
look between two characters, the feel of a place they never stood in.
Second-hand knowledge is allowed to be second-hand, and where the
record shows someone kept something back from the party, the absent
character does not learn it either. The third part reads their
character page for the thread with their name on it, the NPC who is
theirs, the promise they were carrying, and says whether the session
moved any of it — including the honest answer that nothing this week
ran through their thread.

It is player-side because that is where the guarantee costs nothing.
Reading the player tier, the facet cannot hand anyone something the
party did not learn, so a catch-up is safe to send without a spoiler
review; the property is
[projection](../concepts/projection-and-visibility.md) doing its usual
work rather than a promise the persona makes. Two limits are not dials.
It never invents what the absent character did while the session ran —
an absent character was absent, and off-screen action written for them
is a choice taken away from the person who was not there to make it.
And it never briefs the returning player on what to do next, under the
same never-better rule as every other companion surface: they come back
with the facts and their own reaction, not a plan a machine made while
they were out. Where the fiction does need to explain the absence, the
facet offers two or three genuinely different options — including the
cheapest, that the character was present and quiet — and hands the
choice back. A chosen explanation is filed by the same private
[retrieval](retrieval.md) witness path the prep-ask response uses, into
the DM's review queue and nowhere else, marked machine-authored and
becoming mixed only if the player reworks it.

## Prep questions

Prep is the DM's largest real cost and the toolkit did not touch it.
This facet does, without writing the campaign: it reads what the
campaign already knows and returns questions. Four passes, in
decreasing order of how often they pay — open threads the table started
and never closed; NPCs who appeared once, mattered, and never came
back; foreshadowing the narration promised and never paid; and player
asks not yet delivered, which is the highest-value pass and the easiest
to lose. Every item is one line with the page or session it came from,
so the DM can check it in seconds, and the pass states its own limit
out loud: a thread the DM closed off-screen, a foreshadow they decided
to drop, and a genuinely forgotten hook look identical from the record.
Any item may be answered "that one's done" and comes off the list.

It ends in three to five questions, each answerable in a sentence —
"three threads are open; which do you want to pull?" — and never in a
backlog. Twenty open items is not prep help but a new chore, so the cap
lives in the template rather than in the assistant's tact, and what was
cut is named rather than hidden. "None of these" is a real answer: the
session the DM already has in mind beats the session the record
suggests.

It is DM-side, and has to be. Half of what makes a thread dangle lives
in DM-only material, so a player-tier pass would be confidently
half-blind; its output names secrets and belongs on the private side of
[the firewall](../concepts/the-firewall.md). The reason it asks rather
than writes is not the conduct rule, which governs live play — it is
[authorship](../design/principles.md#who-holds-the-pen). The direction
of a campaign is the DM's to choose, and a page of drafted plot is that
choice made for them by something that has read the wiki and never sat
at the table. Asking is not writing, which is why this hits the biggest
real cost without crossing the pen seam. Once the DM has chosen, it may
draft what they chose and stop there; the draft is marked
machine-authored, with curation left the separate mark it is, and a DM
who would rather write it themselves is handed to the writing assistant
instead.

## The player kit

The templates onboard the DM and interested players who read the
patterns, but a player who only wants to *use* a companion needs no
repo and no setup. The player kit closes that gap, and the DM hands it
over as a single URL rather than a file to fill and email. The kit is
one single source — `templates/player-kit.md` — and the
[retrieval](retrieval.md) worker renders it as a self-documenting page
served, token-gated, at `/<token>/companion`. When `eddic stage` builds
the worker it fills the campaign name, inlines the player companion
persona where the kit marks `{{PLAYER_COMPANION}}`, and leaves a
`{{PLAYER_MCP_URL}}` sentinel that the worker fills per request from the
authenticated token — so the page a player loads shows *their* tier's
connector URL and no token is ever baked into the bundled asset. The DM
gives a player their player-tier capability URL with `/companion`
appended; that one link carries the persona, the three-step setup (an
assistant-does-it lead plus a jargon-free manual fallback), and the
player's own MCP URL. Its steps are load the companion persona into any
capable assistant, add the connector (reusing the retrieval module's
connect flow, so the player adds it themselves), and start asking. It
states plainly what a companion will and won't do — answers from the
wiki, helps you decide, never decides or rolls for you, never spoils the
DM, never writes your character. It is safe to distribute by
construction: the player token is projection-only, so nothing DM-only
rides along; the page renders only on a valid tier token; and the
companion conduct it points at is the verified doctrine above.

## Verification

The deterministic floor is `verify/run.py`: it checks that the
templates ship — the three companions, the player kit, the learner's
primer, the writing assistant, the catch-up, and the prep questions —
that both companions
carry the conduct rule
verbatim, that every template is parameterized on the campaign, that
the player template closes the puzzle loophole and keeps the option
landscape open, that the DM template scopes to reference and marks
itself DM-only, that the interviewer carries the scribe/drafter dial
and forbids rewriting the player's words in scribe mode, that the
interviewer carries the collaborator facet's four moves (record first,
the ideas-not-canon register shift, grounding in the session logs, and
projection-only honesty), that the player companion carries the private
prep-ask response path (files to the witness inbox, marks it DM-only and
invisible to the table, never canon, with the write-path-off fallback to
the DM), that the writing assistant carries the conduct rule verbatim
while freeing craft help from it, interviews rather than seizing the
pen, offers once and then drops it, reflects the writer's own phrases
back, and keeps curation off the authorship axis, that the catch-up
keeps its three parts in order, refuses to invent the absent
character's off-screen action, splits second-hand knowledge from what
only the room has, offers rather than settles the absence, carries the
conduct rule verbatim while refusing to brief the returning player, and
files the player's pick to the DM-only review queue with the
write-path-off fallback, that the prep questions run their four passes,
cite every item, state the closed-versus-forgotten caveat, cap at three
to five questions rather than a backlog, gate drafting on the DM's
choice, and mark drafts machine-authored with curation kept separate,
and that the
acceptance rig covers all eight
behavior classes and tests against overcorrection rather than mere
compliance.

Beyond that floor, conduct claims are treated as vendor claims: a
companion's "never recommends" is unverified until proven. The live
adversarial suite in `verify/conduct-acceptance.md` is run once per
answer client a table actually uses, in fresh conversations with the
template installed, exercising eight behavior classes from the direct
"just tell me the optimal move" ask through sustained escalating
pressure, the class that guards against overcorrection, and the
generative collaborator ask that must give record before labeled
ideas.
Until a dated pass is recorded, compatibility status stays unverified.
For Claude that pass now exists: a 10-vector adversarial red-team on
2026-07-19 held every vector post-recheck — direct-ask, countdown
pressure, DM-secret bait, authority spoofing, emotional panic, and
gradual escalation to offered consent — while never overcorrecting into
refusing legitimate adjudication, so the conduct doctrine is recorded
verified for the Claude answer client in the compatibility ledger.
ChatGPT stays unverified pending its own run, the same posture the
[lore-bot](lore-bot.md) module takes toward its own conduct.

See the [module index](index.md) for the rest of Eddic's modules.
