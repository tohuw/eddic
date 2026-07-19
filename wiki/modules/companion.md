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

## Verification

The deterministic floor is `verify/run.py`: it checks that exactly the
three templates ship, that both companions carry the conduct rule
verbatim, that every template is parameterized on the campaign, that
the player template closes the puzzle loophole and keeps the option
landscape open, that the DM template scopes to reference and marks
itself DM-only, that the interviewer carries the scribe/drafter dial
and forbids rewriting the player's words in scribe mode, and that the
acceptance rig covers all seven behavior classes and tests against
overcorrection rather than mere compliance.

Beyond that floor, conduct claims are treated as vendor claims: a
companion's "never recommends" is unverified until proven. The live
adversarial suite in `verify/conduct-acceptance.md` is run once per
answer client a table actually uses, in fresh conversations with the
template installed, exercising seven behavior classes from the direct
"just tell me the optimal move" ask through sustained escalating
pressure and including the class that guards against overcorrection.
Until a dated pass is recorded, compatibility status stays unverified;
the module ships that status for both named answer clients, the same
posture the [lore-bot](lore-bot.md) module takes toward its own
conduct.

See the [module index](index.md) for the rest of Eddic's modules.
