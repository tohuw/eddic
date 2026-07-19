# AGENTS.md — agent entry point

You are reading the instruction root for Eddic, a toolkit for
online-hosted D&D campaigns. Two kinds of agent arrive here. Identify
which you are and route accordingly.

## You are setting up or running a campaign for your user

Your user wants Eddic's facilities — a campaign wiki, a lore bot,
published sites, transcription, timeline tooling — not Eddic's source
code. Go to `modules/` and read the module your user needs (the index is
in `wiki/modules/index.md`; if it does not exist yet, the roadmap in
`wiki/roadmap.md` tells you what is real today). Each module's pattern doc is
written for you: preflight checks, a procedure, marked decision points,
and a verify section.

Rules that bind you while applying patterns:

- Every decision point ships a recommended default. If your user has
  told you to just set things up ("do what you think is best"), take
  every default and ask nothing. Otherwise, ask only at marked decision
  points — never re-ask something the pattern has defaulted.
- Run the deterministic scripts the pattern points at; do not improvise
  replacements for them. Your judgment belongs at decision points and in
  adapting to the user's environment, not inside the deterministic core.
- Record what you applied in the campaign's manifest
  (`.eddic/manifest.json`) so future runs are idempotent and upgradable.
- Never let anything DM-only reach a player-facing surface. The
  projection and firewall lint exist for this; trust them, run them.
- Respect authorship: never stylistically rewrite human-authored prose.
  Mechanical, owner-directed transforms only. See `wiki/design/principles.md`.

## You are developing Eddic itself

Read `wiki/design/principles.md` (principles — they are tiebreakers, not decoration) and
`modules/CONTRACT.md` (the module contract, including the deterministic
CI floor and the semantic rubric) before changing anything.

Repo conventions:

- `CLAUDE.md` is a two-line stub importing this file. Author agent
  instructions here, in AGENTS.md files, only. Do not fork content into
  CLAUDE.md; Claude-specific overrides go under its `## Claude Code`
  heading if ever genuinely needed.
- The content bar for everything in this repo: *stuff your agent might
  not guess at but is proven to work, and bears a sane architectural set
  of decisions your agent can manifest into working stuff.* If a
  competent agent would do it unaided, it does not belong here.
- No symlinks, no bash-isms in module machinery. Everything deterministic
  must run on Windows and macOS via the `eddic` CLI (uv-run Python,
  PEP 723). See the installation principle in `wiki/design/principles.md`.
- Write docs in dense prose. No padding.
- Keep module docs campaign-agnostic: no examples from any real
  campaign (including the one Eddic grew out of). Generalize to what
  the reader ought to try; when an example needs a concrete term,
  use the verify fixtures' invented world (the Warden, the Sunken
  City).
