# DESIGN.md — founding principles and architecture

Eddic generalizes a working single-campaign stack (a published campaign
wiki, a Discord lore-keeper bot, an event-sourced timeline tool) into
adoptable modules. This document holds the principles that decide close
calls, the shared vocabulary, and the architecture every module plugs
into.

## Principles

These are tiebreakers. When a design question stalls, the principles
decide it, in roughly this order of frequency-of-use:

**1. Deterministic core, agent shell.** Scripts do everything
repeatable; agents read patterns, make judgment calls at marked decision
points, and run maintenance. Use agentic goodness where it is actually
good; stop burning tokens and gambling on outcomes where it isn't. An
agent never does infrastructure's job (auth, projection, crypto,
firewalls) and infrastructure never does judgment's job.

**2. No egg-sucking.** Eddic never teaches an agent what it already
knows. Codex on a FreeBSD server knows how to set up cron; Cursor on
Windows knows scheduled tasks. Eddic states contracts and invariants
("the maintenance routine must be idempotent and safe to miss a run"),
proven procedures, and hard-won heuristics — never vendor how-tos an
agent would produce unaided. This is also the anti-bloat rule: content
that fails this bar is deleted, because it is a strictly worse pathway
than what the agent would do anyway.

**3. Installation friction kills this project.** The average DM uses
Windows; the average Mac DM has never heard of homebrew; players,
quadruply so. Therefore: players install nothing (Discord, a website, at
most a connector URL). The DM-local surface stays minimal; anything
persistent prefers a cloud surface. The agent is the installer, with a
deterministic bootstrap: uv (single binary, one-line install on Windows
PowerShell and macOS, bootstraps Python itself); `uv run eddic` must
always work. No symlinks. No bash as module machinery — deterministic
work runs under the CLI so Windows is covered by construction.

**4. Cost pragmatism.** Cloud has advantages and cloud has a price, and
not every DM has $33/mo to toss at their playing habit. The **baseline
build** is a named reference architecture: a complete Eddic campaign on
nothing but a $20/mo Claude or ChatGPT subscription (each by the route
its surfaces permit — the dated ledger in `docs/compatibility.md` keeps
this claim honest per vendor) — Cloudflare free
tier for sites and retrieval, GitHub Actions free tier (or
in-subscription routines) for maintenance, local transcription instead
of paid services, Discord free. Everything above baseline is an upgrade
with a stated reason. Modules document *cost posture* (a free/local
path, a paid/cloud path, and a when-it's-worth-it heuristic), never
dollar amounts; every paid recommendation names its free fallback.

**5. Defaults everywhere.** Every decision point in every pattern ships
a recommended default. This is what makes "I don't want to make a
hundred decisions, just do what you think is best" work mechanically:
the agent takes defaults everywhere and asks nothing. A decision point
without a default is a contract violation. Opinionated defaults, escape
hatches.

**6. Authorship preservation.** The old "immutable sources" construct is
retired; the real invariant is that no agent strips the human art out of
human prose. Human-authored files carry authorship frontmatter
(`authorship: human`). Agents may perform owner-directed *mechanical*
transforms on them (renames, spelling propagation — "change the
princess' name to Aria everywhere" loses no art) but never *stylistic*
rewrites. Every diff to a human-authored file traces to an owner
directive via a log entry; git is the audit trail.

**7. The agent-answer surface is the product.** Players ask; agents
answer; the wiki is the substrate that makes answers good. Pages are
optimized as retrieval substrate first and destination second:
self-contained facts, dense relative links (graph traversal for an
agent), encyclopedia granularity. The rabbithole — a player reading for
an hour because an answer linked somewhere — is the delightful side
effect, not the plan of record.

**8. Two wikis, one truth.** The DM wiki is the single maintained
master. Visibility is frontmatter, and it fails closed: pages are
DM-only unless marked `visibility: player`. The player wiki is a
deterministic build-time *projection* — revealing a page to players is
"lifting the veil," one frontmatter change. A firewall lint proves no
player-visible page links to a DM-only page, and player-facing surfaces
(sites, bots, connectors) ingest only the projection, by construction.
No agent ever decides what leaks; a build script decides and a lint
audits.

**9. Agent-agnostic.** Instructions must serve Claude, Codex, and
capable peers equally. Author agent instructions in AGENTS.md; ship a
two-line CLAUDE.md stub (`@AGENTS.md`) since Claude Code reads only
CLAUDE.md (verified July 2026). Prefer CLIs and MCP — every runtime can
shell out, and MCP is cross-vendor — over any vendor's proprietary
machinery. Where runtimes genuinely differ (scheduled maintenance),
state the contract plus a preference chain and let the local agent map
it: hosted agent routines → GitHub Actions → local cron-esque.

**10. Provenance discipline.** Each campaign keeps a typed, append-only
operation log (`ingest`, `reconcile`, `lint`, `schema`, `witness`
entries; absolute dates). Writes from the field (a DM's voice note from
the road) land in an append-only **witness inbox** and are reconciled by
the next maintenance run under full discipline — lint, firewall, log —
never hot-edited into canon. Chronology belongs to Ørlǫg; the wiki
states time in plain prose; reconciliation between them is owner-directed
and logged.

**11. Personality lives at owned surfaces, never in the data layer.**
A shared surface the DM owns — the table's lore bot — is a character;
persona there is a feature, part of the fiction. A data layer that
agents consume (the retrieval worker, corpora, tool results) stays
voice-neutral: plain content, no flavor, no styling, no instructions
to the consuming model. This is not taste. The consuming agent belongs
to the user, and users tune their agents to respond in the specific
ways they need — accessibility and neurodivergence needs included. A
data layer with a personality overrides that tuning and serves no one.
Let the user's agent answer.

## Vocabulary

- **module** — the shippable unit: a directory holding a pattern,
  scripts, templates, and verification. See `modules/CONTRACT.md`.
- **pattern** — a module's instructional layer, written for an agent
  reader: preflight, procedure, decision points, verify.
- **campaign** — one table's instantiation: a repo holding sources, the
  DM wiki, its player projection, config, logs, and the manifest.
- **manifest** — `.eddic/manifest.json` in a campaign: the record of
  which patterns were applied, at what version, with what parameters.
  It is what makes pattern application idempotent, auditable, and
  upgradable — a package manager where the install step is an agent
  following a runbook.
- **projection** — the deterministic build that derives the player wiki
  from the DM wiki's visibility frontmatter.
- **witness inbox** — the append-only queue where field writes wait for
  reconciliation.
- **baseline build** — the named $20/mo-subscription-only reference
  architecture (principle 4).
- **maintaining agent / answer client / model provider** — the three
  roles "agent" hides: the coding agent that applies patterns (Claude
  Code, Codex), the chat product humans ask (Claude, ChatGPT), and
  the API a resident service bills against (Anthropic, OpenAI). Every
  compatibility claim names its role and carries a dated evidence
  state; the ledger is `docs/compatibility.md`.

## Campaign architecture

The provenance pipeline every module plugs into:

    sources (authorship-marked)          witness inbox (field writes)
            \                              /
             v                            v
        DM wiki  — single master, visibility frontmatter, typed log
             |
             |  deterministic projection + firewall lint
             v
        player wiki
             |
             +--> published sites (purpose-built renderer -> Cloudflare Pages)
             +--> lore bot corpus (Discord)
             +--> retrieval connector (Cloudflare Worker MCP, bearer token;
                  DM token sees the master, player token sees the projection)

        Ørlǫg (external) owns chronology; consumed via its headless CLI;
        reconciliation owner-directed and logged.

Maintenance is a scheduled routine (principle 9's preference chain)
whose contract is: ingest new sources and the witness inbox, update the
DM wiki, run lint (links, orphans, catalog, stubs, firewall), rebuild
projections and sites, redeploy, and log — idempotent, safe to miss a
run, safe to run twice.

**Freshness is part of the derivation contract.** Every derived surface
(published site, bot corpus, connector) must state how it tracks the
master; "someone remembers to run the refresh command" is not a
mechanism. The default shape is self-refresh: the surface observes its
substrate (a cheap version check — e.g. the source repo's HEAD — on a
poll) and rebuilds when it moves. This beats publisher-side chaining,
which couples credentials across repos and misses every write path that
bypasses the publisher, and beats webhook listeners, which add serving
surface to things that otherwise need none. Manual refresh commands stay
as escape hatches, never as the mechanism. (Lesson learned in the source
stack: the lore bot loaded its corpus at process start — restart and
reload were equivalent — but its deploys were disconnected from the
wiki's, so every wiki publish left the bot stale until a human noticed.)

## The eddic CLI

`eddic` is the contractual locus for deterministic workflows — the
stable interface patterns are written against, so its implementation
(uv-run Python today, per-OS binaries later) can change without
touching any pattern. Planned verb families: `doctor` (preflight),
`build`, `project` (player projection), `lint`, `ingest`, `witness`
(drain the inbox), `manifest`. Verbs land with the modules that need
them; none exists until its module does.

## Authorship and rights

Every table eventually asks a version of the same worried question:
"what if I want to write a book about this world one day — should an
LLM be seeing my material?" It deserves a straight answer, not
reassurance. Eddic's posture, the rationale behind principles 6 and 10:

- **Feeding your prose to a model neither transfers nor dilutes your
  copyright.** Ownership comes from creation. And copyright protects
  *expression*, not ideas — the book you might write is your
  expression; nothing in this pipeline touches it.
- **Purely machine-generated output cannot be copyrighted under US law
  as it stands** (the human-authorship requirement; probabilistic
  output is a non-starter). This cuts protectively: no entity gains a
  claim over your world through a model's output. It also means the
  derived layer is not where original art should live — which is
  principle 6's job: human art stays in human-authored files, marked
  as such, and agents never rewrite it.
- **Human selection, arrangement, and substantive revision of machine
  output can carry protection; bare prompts generally do not.** The
  authorship frontmatter marks exactly the seam a rights question
  would ask about — who made what, on which side of the line.
- **Training exposure is a settings matter.** Provider APIs do not
  train on inputs by default, and consumer products expose opt-outs;
  Eddic patterns assume accounts configured accordingly. That is trust
  in a black box — say so plainly — but it is a bounded, acceptable
  risk given the points above.
- **Provenance is the working defense, in both directions.** Authorship
  frontmatter, git history, and the typed log form a dated corpus
  proving your material existed before it ever met the pipeline — and,
  inversely, that everything in the derived layer traces to your
  sources via ingest entries, so nothing entered canon unattributed.
- This is recorded consideration, not legal advice, and it is
  US-centric. Tables elsewhere should check their jurisdiction.

## Token economics

Maintenance routines are token-heavy by nature (multi-thousand-line
session transcripts; whole-wiki lint passes), and routines' value
argument depends on staying cheap. Deterministic pre-compression of
transcripts before any agent reads them is a first-class pattern, and
compression layers (headroom, thlibo — both local-first and
agent-agnostic) are recommended *accelerators* in maintainer-side
patterns. Never dependencies: nothing in Eddic may require them, and
heavyweight options (multi-GB local models) are decision points with
heuristics, per principles 3 and 5.
