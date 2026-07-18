# Routine contract: freshness

**Purpose.** Every player surface (published site, retrieval worker,
lore bot corpus) tracks the wiki without human hands. The lore bot
already self-refreshes by polling; this routine covers the surfaces
that need a push: the projection, the site, and the worker corpora.

**Composed verbs, in order, stop on first failure:**

1. `eddic lint --strict` — errors *or warnings* block; a routine
   must never publish what a human wouldn't.
2. `eddic project` — refuses all-or-nothing on firewall breaches.
3. `eddic build`
4. `wrangler pages deploy <site_dir> --project-name <pages_project>`
5. `eddic stage`
6. `wrangler deploy` (from the campaign's `worker/`)

**Idempotency.** Every step is a pure function of the wiki tree:
same input, same artifacts, same deploys. Running on an unchanged
wiki republishes identical content.

**Safe to miss.** A missed run leaves surfaces stale, never wrong —
the last published state was itself lint-clean and firewall-checked.

**Safe to double-run.** Steps 1–3 and 5 write derived directories
atomically-enough (full rewrite); steps 4 and 6 are last-write-wins
deploys of identical content when concurrent. Two overlapping runs
of the same commit converge on the same result.

**Refusal behavior.** Any nonzero step stops the chain and surfaces
that step's stderr through the runner's failure channel. No retries
inside the routine; the next trigger retries naturally.

**Default cadence.** Event-driven on wiki change; polling fallback
every 30 minutes.
