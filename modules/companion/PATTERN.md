# Pattern: table companions

Gives each seat at the table an in-session agent under the
knowledge-parity conduct doctrine (DESIGN: "Companions at the
table"): **it may say what is possible and what is true; it may
never say what is better.** A new player behaves like a player who
knows the game — never like a player being played by a machine. The
same family carries the backstory interviewer.

The abuse backstop is social, and this pattern says so plainly:
these are plaintext instructions any player can rewrite, and the
format's answer to degenerate play is the DM — an adaptive,
omniscient human referee. Nothing here pretends to be enforcement.

## Preflight

- The retrieval pattern is applied and live: player and DM tiers
  reachable from the clients the table actually uses.
- Every intended user has an answer client whose conduct has been
  verified (see Verify) — or knows theirs is running unverified.

## Procedure

1. For each player: install `templates/player-companion.md` (fill
   `{{SITE_NAME}}`) as standing instructions in their client — a
   claude.ai project's instructions, a Custom GPT's instructions, or
   equivalent — alongside their player-tier retrieval connector.
2. For the DM: `templates/dm-companion.md` the same way, on the DM
   tier, on the DM's own devices only.
3. For a backstory session: `templates/backstory-interviewer.md`
   with `{{MODE}}` filled per the decision point below. Scribed
   output lands in `sources/` with the player's contributor id
   (wiki schema: attribution at write time); drafted output is
   marked machine-authored with the player credited for the ideas.
   The template also carries the collaborator facet — how it answers
   generative asks ("give me ideas", "what might") — kept or stripped
   per the decision point below.

   For writing beyond backstory — the DM's places and factions, a
   player's journal, a character's voice, the recap nobody has
   written — install `templates/writing-assistant.md` the same way,
   for the DM and for any player who wants it. It generalizes the
   interviewer: same refusal to write unprompted, same reflection of
   the writer's own phrases, extended to anyone at the table with
   something unwritten. Two things it adds are worth knowing before
   you install it. It is **proactive** — it may notice an unwritten
   place or recap and offer, once per session, then drop it — which
   is the point of it and also the thing a table will resent if the
   invitation ever becomes a script. And it separates craft from
   conduct: it helps with structure, cuts, and phrasing as freely as
   asked, because the never-better rule governs play rather than
   prose, while at the table it stays on the phrasing side of the
   line and hands tactics back to the table.
4. For a player learning the game: `templates/learners-primer.md` is
   the capability the player companion follows on request to build a
   one-page HTML Learner's Primer of that player's own character and
   turn — numbers from the player's sheet, context and links from the
   projection, rules explained in place, under the companion's
   possible-and-true / never-better rule. Reference implementation:
   `templates/learners-primer.skeleton.html`.
5. For a player who missed a session: `templates/catch-up.md` is a
   second player-side capability, followed on request against the
   session's recap page and that player's character page. It is
   player-side because that is where the guarantee is free — reading
   the player tier, it cannot hand anyone something the party did not
   learn, so a catch-up needs no spoiler review before it is sent —
   and because the one thing it must not settle, why the character was
   absent, is the player's to settle. It never invents what the absent
   character did; where the fiction needs an explanation it offers two
   or three and lets the player pick, filing the chosen one to the DM
   by the same private witness path as a prep-ask response.
6. For the DM's prep: `templates/prep-questions.md` is a DM-side
   capability that reads the campaign and returns questions rather than
   prose — open threads, NPCs who never came back, unpaid
   foreshadowing, player asks not yet delivered, each cited to the page
   it came from, ending in three to five questions answerable in a
   sentence. It is DM-side because half of what makes a thread dangle
   is DM-only, so a player-tier pass would be confidently half-blind,
   and its output names secrets and goes nowhere a player can read it.
   It asks rather than writes for authorship reasons rather than
   conduct ones — the never-better rule governs live play, while the
   campaign's direction is the DM's to choose — and it may draft once
   the DM has chosen, marking what it drafts machine-authored like
   anything else it writes.
7. Publish the player kit as a page, then hand each player a URL — no
   files to fill or email. Vendor the two single-source templates into
   the campaign so the retrieval worker can render them:

       mkdir -p <campaign>/.eddic/companion
       cp templates/player-kit.md templates/player-companion.md \
           <campaign>/.eddic/companion/

   Leave `{{SITE_NAME}}` and `{{PLAYER_MCP_URL}}` in place — `eddic
   stage` fills the site name and inlines the persona at
   `{{PLAYER_COMPANION}}` when it builds `worker/companion.mjs`, and the
   worker fills the MCP URL per request from the authenticated token
   (nothing is baked in). Re-stage and deploy the worker (the retrieval
   pattern's flow). The kit page is then served, token-gated, at
   `https://<worker>/<token>/companion`. Hand each player their own
   player-tier capability URL with `/companion` appended — one URL,
   self-documenting: it carries the persona, the setup steps (assistant
   lead plus jargon-free manual fallback), and that player's own MCP URL
   filled in. This is the player-as-audience handoff — the only path a
   player needs, no repo, no attachment. It is safe to distribute by
   construction: the player token is projection-only (the firewall
   guarantees it), the page renders only on a valid tier token, and the
   companion's conduct is verified (see Verify), so nothing DM-only and
   no unbounded advice rides along.
8. Log a `schema` entry naming which companions the table runs.

## Decision points

- **Interviewer mode.** Default: `scribe` — the player's own words,
  never rewritten; their story stays their protected expression.
  Offer `drafter` only when the player prefers it, with one sentence
  on the trade (machine prose is nobody's protected expression).
- **Collaborator facet.** Whether the interviewer may answer a
  generative ask — "give me ideas", "what might have happened",
  RP hooks — or stay purely elicitive, drawing out only what the
  player already imagines. Default: on — the say-what's-true rule
  extended to generation, in the order the template fixes: the
  archive's actual record first and cited, then a marked register
  shift to *ideas, not canon* for the DM to rule on, at most one
  narrowing question so the ideas are specific rather than generic,
  and every suggestion grounded in what the session logs already
  establish about that character and place. It stays projection-only,
  so a floated idea is an honest guess and never a leaked secret, and
  invention is never dressed as record. When the ask is to extrapolate
  the player's own backstory rather than world hooks, it offers two or
  three genuinely divergent seeds — real forks in who the character is,
  not variants of one answer — never a single "most plausible" one, each
  labeled drafted-with-you and the choice left explicitly to the player;
  a suggested identity is never narrowed to one on the machine's
  authority. Strip the block for a player who wants the interviewer to
  offer nothing of its own; the same
  facet can ride the player companion for in-play RP hooks when the
  table wants it there too. **Private responses to DM prep asks.**
  When `/session prep` broadcasts a per-player ask ("decide why your
  character was on the road"), the player companion is the private
  response path: it works the answer out in this collaborator register,
  then — with the write path on — files the agreed result to the DM's
  inbox via the retrieval witness (`suggest_edit` onto the character
  page, or `suggest_page`) with a short rationale, and tells the player
  plainly it goes only to the DM's review queue, invisible to the rest
  of the table, so a per-player secret stays secret. It is never posted
  to a shared surface and never presented as canon (the DM accepts it).
  With the write path off, it says so and falls back to "give this to
  the DM directly" rather than dropping it. The witness path is
  projection-scoped and DM-read-only by construction: any tier may
  file, only the DM tier reads the inbox, so a filed suggestion is
  private to the DM (retrieval decision point "Writeable retrieval").
- **Learner's primer.** Default: offered on request, not pushed — the
  player companion mentions it to a new player or builds one when
  asked, never as an unsolicited artifact. It is a facet of the player
  companion under the same conduct rule; the build teaches the option
  landscape and never optimizes. Every number comes from the player's
  own character sheet (never fabricated); world terms link into the
  projection, rules terms are explained in place, and an unclear value
  is sent to the DM rather than guessed.
- **Absent-player catch-up.** Default: on, sent unprompted after any
  session someone missed — the miss is the trigger, because a player
  who has to ask for a catch-up mostly does not ask. It is built from
  the recap and that player's character page only, in three parts:
  what happened, what their character has heard second-hand versus
  what only the people in the room have, and what moved on the threads
  that are theirs. Two limits are not dials. It never invents what the
  absent character did — an absent character was absent, and off-screen
  action written for them is a choice taken away — and it never
  briefs them on what to do next session; they come back with the
  facts and their own reaction. Where the absence needs explaining in
  fiction it offers two or three genuinely different options,
  including the cheapest one (the character was present and quiet),
  and the pick is the player's; the pick is filed to the DM's review
  queue by the witness path, or handed to the DM directly when that
  path is off. Turn it off for a table that resolves absences at the
  table and wants no artifact.
- **Prep questions.** Default: on and on demand, offered at most once
  per prep conversation. The pass returns four kinds of item — open
  threads, NPCs introduced and never returned, unpaid foreshadowing,
  player asks not yet delivered — each cited to its page or session,
  under a stated caveat that a deliberately closed thread and a
  forgotten one look identical from the record. It ends in three to
  five questions, never a backlog: a list of twenty is not prep help
  but a new chore. Drafting stays gated on the DM's answer, and what
  it drafts is marked machine-authored with curation left as the
  separate mark it is. Worth turning off only for a DM who prefers to
  arrive at prep with nothing in front of them; worth leaving on for
  the common case, which is a campaign carrying more open thread than
  anyone can hold in their head.
- **Tactical help.** Default: the never-better rule stays on for
  shared in-session surfaces, and off for a player asking about their
  own character outside a scene — the learner's primer included. The
  split is deliberate: what the rule protects is *other people's*
  game, so it binds where a ranked answer spends the table's spotlight
  and relaxes where a player is only working out how their own
  character functions. A table that wants full tactical help turns the
  rule off and says so out loud; a table that wants it absolute leaves
  it on everywhere. Say plainly which you have set, because a player
  who does not know the rule is on will read a refusal as the
  assistant being broken and go ask a chatbot with no such rule —
  which is the outcome the setting exists to make a choice rather than
  an accident. Secrets are not on this dial at all: those are held by
  tier isolation, and no setting reaches them.
- **Writing assistant reach.** Default: installed for the DM and
  offered to every player, with the proactive invitation on. The
  offer is capped at one per session by the template itself, which
  is what keeps proactive from becoming pestering; a table that
  still finds it intrusive strips the "Offering, once" section and
  keeps a purely on-demand assistant. Worth turning the invitation
  off for a table whose players have said they do not want to be
  written at, and worth leaving on for the common case: the person
  who would like to write more and never quite starts.
- **Player companion rollout.** Default: offered, not imposed — a
  player who wants no agent at the table simply has none; parity is
  a ceiling on the tool, not a mandate to use it.
- **Engagement framing.** Default: the one line already in the
  template ("the game stays louder than you"). The companion never
  polices attention; that is table culture's job.

## Verify

- `uv run modules/companion/verify/run.py` — deterministic floor:
  templates present, conduct rule verbatim in both companions, the
  puzzle loophole closed, the interviewer's mode dial intact, the
  collaborator facet's load-bearing phrases (record first, the
  *ideas, not canon* register shift, grounding in the session logs)
  present in the interviewer, the player companion's private
  prep-ask response path (files to the witness inbox, marks it
  DM-only and invisible to the table, never canon, with the
  write-path-off fallback to the DM), and the acceptance rig covering
  all eight behavior classes.
- The learner's primer template and its skeleton ship, the primer
  carries its guardrails (never optimizes the build, never fabricates
  a number, projection-scoped, rules explained in place), and the
  player companion advertises the capability — all checked by
  `run.py` above.
- The catch-up template ships and carries its four load-bearing
  moves: the three parts in order, the refusal to invent what the
  absent character did, the second-hand split, the offered-not-settled
  absence with the choice left to the player, plus the conduct rule
  verbatim and the witness filing with its write-path-off fallback.
- The prep-questions template ships and carries its four passes, the
  citation duty, the closed-versus-forgotten caveat, the three-to-five
  question cap with its refusal to become a backlog, and the gate that
  drafting waits on the DM's choice and is marked machine-authored
  with curation kept a separate mark. Both are checked by `run.py`.
- `verify/conduct-acceptance.md` — the live adversarial suite, run
  once per answer client the table uses. Conduct claims stay
  `unverified` in module.yaml and `docs/compatibility.md` until a
  dated pass is recorded; class 5 matters as much as class 2 — a
  companion that refuses adjudication has failed parity in the other
  direction.
