# Pattern: maintenance routines

Gives the campaign its recurring upkeep without a human remembering
anything. A routine here is a **contract**, not a how-to: it must be
**idempotent** (running twice equals running once), **safe to miss**
(a skipped run degrades freshness, never correctness), and **safe to
double-run** (two overlapping runs cannot corrupt anything). Any
runner that honors the contract is a valid adapter; you (the agent)
map the contract onto whatever scheduler the owner's world offers —
you know your host's native machinery, so the adapters below are
stated as contracts plus one worked template, never as vendor
tutorials.

## Preflight

- The verbs a routine composes are vendored and green by hand first:
  a routine automates what already works, never debugs it.
- A runner exists in the owner's world, chosen by the preference
  chain: **hosted agent routines** (best value when the owner's
  agent subscription includes them) → **GitHub Actions** (free tier,
  fits cloud-mode campaigns whose repo is on GitHub) → **local
  cron-esque** (launchd, Task Scheduler, cron; fits a machine that
  is reliably awake).

## Procedure

1. Pick the routine's contract from `templates/` (or write a new one
   in the same shape: purpose, composed verbs, idempotency argument,
   miss/double-run argument, default cadence, refusal behavior).
   Two standard routines ship. **Freshness**
   (`templates/routine-freshness.md`): wiki changed → strict lint →
   project → stage → deploys — the loop that keeps every player
   surface tracking the wiki, deterministic and zero-token.
   **Semantic review** (`templates/routine-semantic-review.md`): the
   lint module's model pass packaged as a routine — strict lint,
   project, `semantic-review` to build the packet, the agent's checklist
   pass, validate, then file findings as `suggest_edit` suggestions into
   the DM's inbox (or a plain report). It is the token-spending
   exception below, and its output is advisory only: agent proposes,
   human disposes, nothing auto-applied.
2. Map it onto the chosen runner. For GitHub Actions,
   `templates/gh-actions-freshness.yml` is a working start (fill the
   two secrets it names; it triggers on wiki pushes, so cadence is
   event-driven). For hosted agent routines and cron-esque runners,
   implement the contract natively — the contract file is the spec.
3. Refusals must be loud, never silent: a routine that hits a lint
   error or a firewall refusal stops and surfaces the reporter's
   output through the runner's notification surface (failed check,
   failed job, failed unit — whatever the runner shows the owner).
   It never "fixes" anything; judgment stays with the owner and
   their agent.
4. Log a `schema` entry naming the routine, its runner, and its
   cadence. Routines are part of the campaign's shape.

## Decision points

- **Runner.** Default: the preference chain top-down — take the
  first rung the owner's world already has. Do not introduce a new
  paid service to host a routine; the chain exists so the free rung
  is always reachable.
- **Cadence.** Default: event-driven where the runner supports it
  (on wiki push); otherwise the contract file's stated interval.
  When in doubt, slower — a stale surface self-heals on the next
  run; a noisy routine trains the owner to ignore it.
- **Token budget.** Default: deterministic-only routines (the
  freshness loop spends zero model tokens). A routine that reads
  transcripts or lints semantically documents its cost posture and
  pre-compresses inputs (DESIGN: token economics) before any model
  sees them — the shipped **semantic-review** routine is exactly this
  case: its scaffolding is free and deterministic, the one model step
  is bounded by a checklist, and its default cadence is
  between-sessions rather than per-push so the token spend rides the
  rhythm of play.

## Verify

- `uv run modules/routines/verify/run.py` — parses the Actions
  template as YAML, checks it composes only vendored verbs in the
  contract's order with strict lint first, refuses-on-error
  semantics (no continue-on-error), and confirms both shipped contract
  files (freshness and semantic-review) state all five required
  sections, and that the semantic-review contract names its advisory
  posture and its filing path into the retrieval inbox.
- Live: trigger the chosen runner once by hand (push a trivial wiki
  change, or run the unit manually) and watch the whole chain
  succeed; then trigger it twice back-to-back and confirm the
  second run is a clean no-op or a clean repeat — that is the
  double-run clause, observed.
