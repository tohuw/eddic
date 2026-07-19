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
4. Hand each player their kit: fill `templates/player-kit.md` with
   `{{SITE_NAME}}` and that player's player-tier capability URL
   (`{{PLAYER_MCP_URL}}` — the token-in-URL form from the retrieval
   pattern's connect flow, which the kit reuses so the player adds the
   connector themselves), and send it, with the `player-companion.md`
   text, one filled kit per player. This is the player-as-audience
   handoff — the only path a player needs, no repo. It is safe to
   distribute by construction: the player token is projection-only
   (the firewall guarantees it), and the companion's conduct is
   verified (see Verify), so nothing DM-only and no unbounded advice
   rides along.
5. Log a `schema` entry naming which companions the table runs.

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
  table wants it there too.
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
  present in the interviewer, and the acceptance rig covering all
  eight behavior classes.
- `verify/conduct-acceptance.md` — the live adversarial suite, run
  once per answer client the table uses. Conduct claims stay
  `unverified` in module.yaml and `docs/compatibility.md` until a
  dated pass is recorded; class 5 matters as much as class 2 — a
  companion that refuses adjudication has failed parity in the other
  direction.
