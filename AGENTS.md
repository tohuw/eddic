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
- Authoring the wiki *is* the job — write recaps, lore, place and
  character pages from the table's own material (a session transcript,
  the DM's notes). The DM authored the session by running it at the
  table; you render it into canon, faithful to the source. Do this
  freely — lifting the write-up off the table is the point of Eddic.
  "Respect authorship" is narrower than it sounds: it bars stylistically
  *rewriting* prose a human wrote (a file marked `authorship: human` — a
  player's backstory, the DM's own words), where only owner-directed
  mechanical transforms belong. It is never a bar on authoring new
  content, and if your user asks for a recap or a page, write it. See
  `wiki/design/principles.md`.
- Mark the pen honestly, and mark it silently. Who wrote a page
  (`authorship:`), who is answerable for it (`curation:`), and how a
  source may be handled (`ingest:`) are recorded as you work, in the
  frontmatter, without narrating any of it. Speak to your user in what
  they are writing and what you have written; raise the mechanism only
  when they ask how it works, or when something refuses and they need
  one plain sentence naming the fix. These marks are assertions of
  fact, so never restyle one to be convenient — a page you wrote stays
  machine-authored after the owner approves it, and only their own
  rewriting makes it `mixed`. See principle 11 in
  `wiki/design/principles.md`.
- Automatic is the point. Ship what you produce — publish the wiki,
  deploy the site, commit the recap — without pausing for the owner to
  review or "bless" it. The safety net is the lint → firewall → git
  pipeline and the fact that anything wrong is one edit and one redeploy
  away, not human pre-approval; a game wiki is fix-forward, not a text
  that must be signed off. Reserve confirmation for the genuinely
  irreversible or a marked decision point — never for routine output.
  The DM's time is what Eddic exists to give back; do not spend it on
  approvals.

## You are developing Eddic itself

Run `uv run tools/dev_setup.py` once so this clone gates its own
pushes, then read `wiki/design/principles.md` (principles — they are
tiebreakers, not decoration) and `modules/CONTRACT.md` (the module
contract, including the floor and the semantic rubric) before changing
anything. `uv run tools/gate.py` is the gate: floor, module verifiers,
end-to-end. There is no automatic CI, on purpose.

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
- The wiki primitives that decide what a link means and what reaches
  players are generated. They live in `tools/wikilib.py` and are stamped
  into each script between `# --- BEGIN/END SHARED wikilib ---` markers
  by `tools/sync_shared.py`. Edit the canonical file and restamp — never
  hand-edit a stamped block, and never write a private copy of one of
  those functions under another name. The floor fails on both.
- Write docs in dense prose. No padding.
- Keep module docs campaign-agnostic: no examples from any real
  campaign (including the one Eddic grew out of). Generalize to what
  the reader ought to try; when an example needs a concrete term,
  use the verify fixtures' invented world (the Warden, the Sunken
  City).
