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

## The three templates

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

The deterministic floor is `verify/run.py`: it checks that the three
companion templates and the player kit ship, that both companions
carry the conduct rule
verbatim, that every template is parameterized on the campaign, that
the player template closes the puzzle loophole and keeps the option
landscape open, that the DM template scopes to reference and marks
itself DM-only, that the interviewer carries the scribe/drafter dial
and forbids rewriting the player's words in scribe mode, that the
interviewer carries the collaborator facet's four moves (record first,
the ideas-not-canon register shift, grounding in the session logs, and
projection-only honesty), and that the acceptance rig covers all eight
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
