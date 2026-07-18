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
4. Log a `schema` entry naming which companions the table runs.

## Decision points

- **Interviewer mode.** Default: `scribe` — the player's own words,
  never rewritten; their story stays their protected expression.
  Offer `drafter` only when the player prefers it, with one sentence
  on the trade (machine prose is nobody's protected expression).
- **Player companion rollout.** Default: offered, not imposed — a
  player who wants no agent at the table simply has none; parity is
  a ceiling on the tool, not a mandate to use it.
- **Engagement framing.** Default: the one line already in the
  template ("the game stays louder than you"). The companion never
  polices attention; that is table culture's job.

## Verify

- `uv run modules/companion/verify/run.py` — deterministic floor:
  templates present, conduct rule verbatim in both companions, the
  puzzle loophole closed, the interviewer's mode dial intact, and
  the acceptance rig covering all seven behavior classes.
- `verify/conduct-acceptance.md` — the live adversarial suite, run
  once per answer client the table uses. Conduct claims stay
  `unverified` in module.yaml and `docs/compatibility.md` until a
  dated pass is recorded; class 5 matters as much as class 2 — a
  companion that refuses adjudication has failed parity in the other
  direction.
