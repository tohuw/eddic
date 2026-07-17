# The module contract

A module is Eddic's shippable unit: everything an agent needs to give a
user one facility. Modules are independently adoptable, community
contributions arrive as modules by PR, and this contract is what a
module must be. It is deliberately not an API surface with a kajillion
endpoints — submissions are agentic and so is reception, so the contract
is good-faith semantics resting on a small deterministic floor.

## Anatomy

    modules/<name>/
      module.yaml        # manifest: name, version, summary, touches,
                         #   depends, cost_posture
      PATTERN.md         # the instructional layer, written for an agent
      scripts/           # deterministic machinery, run via the eddic CLI
      templates/         # files the pattern stamps into a campaign
      verify/            # observable success checks

Only `module.yaml` and `PATTERN.md` are unconditionally required;
`scripts/`, `templates/`, and `verify/` are required exactly when the
pattern references them — and a pattern with no verify section does not
merge (see floor).

## Pattern anatomy

Every `PATTERN.md` has four parts, in order:

1. **Preflight** — deterministic checks that the environment can accept
   this pattern: dependencies present, config sane, prior manifest state
   compatible. Fail here, fail cheap.
2. **Procedure** — prose for the agent, invoking `scripts/` for
   everything repeatable. The agent's judgment adapts the procedure to
   the environment; it does not replace the scripts.
3. **Decision points** — the only places the agent consults the user.
   Each one is explicitly marked and **ships a recommended default**
   plus, where experience warrants, a when-it's-worth-it heuristic. A
   decision point without a default is a contract violation: defaults
   are what make "just do what's best for me" work mechanically.
4. **Verify** — observable success criteria, not "it should work now."
   The agent runs these and reports outcomes faithfully.

Patterns must be idempotent: applying the same version with the same
parameters twice is a no-op. Application is recorded in the campaign's
`.eddic/manifest.json` (module, version, parameters, date); upgrades
re-run the pattern at the new version against the manifest.

## Cost posture

`module.yaml` declares `cost_posture`: the free/local path, the
paid/cloud path if one exists, and the heuristic for when paid is worth
it. Never dollar amounts — prices rot; postures don't. Every paid
recommendation names its free fallback. Every module must be satisfiable
inside the baseline build unless its manifest says otherwise and its
pattern says why.

## The deterministic floor (CI-enforced)

Small and mechanical, because semantic review is bad at catching
mechanical rot — a broken script reads fine:

- `module.yaml` present and schema-valid.
- `PATTERN.md` has all four parts; every decision point has a default.
- Every script the pattern references exists and executes (smoke run)
  on macOS and Windows runners.
- A verify section exists and its checks execute.
- No secrets or credentials committed.
- No symlinks; no bash-required machinery.
- Vendor claims are metadata-backed: if a PATTERN names a vendor
  (claude, chatgpt, codex, anthropic, openai), `module.yaml` carries a
  `compatibility:` entry for it — `role` (maintaining agent / answer
  client / model provider), `status` (one of the evidence states in
  `docs/compatibility.md`), `date`, and, for `verified`, `evidence`.
  Nothing below `verified` may be a decision point's default path.
  Truth decays: re-date on re-test, demote when a vendor moves.

## The semantic rubric (review-enforced)

Reviewed in good faith by maintainer plus agent, with a critical eye:

- **Deterministic where possible** — anything repeatable is a script,
  not prose asking the agent to improvise.
- **Probabilistic insertions are responsible** — where the pattern does
  rely on agent judgment, the pattern says so, bounds it, and keeps it
  away from safety properties (visibility, authorship, secrets).
- **No egg-sucking** — the pattern contains nothing a competent agent
  does unaided. Contracts, invariants, proven procedure, heuristics;
  no vendor how-tos.
- **In keeping with Eddic's standards throughout** — vocabulary,
  principles, tone; firewall and authorship invariants respected;
  agent-agnostic (no runtime-exclusive machinery without a stated
  fallback chain).

## Versioning

Modules version independently (semver). A campaign's manifest pins the
version applied; pattern upgrades state what changes on re-application.
