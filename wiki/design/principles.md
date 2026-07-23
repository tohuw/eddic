# Design principles

Eddic generalizes a working single-campaign stack — a published campaign wiki, a Discord lore-keeper bot, an event-sourced timeline tool — into adoptable modules. This page holds the principles that decide close calls, the shared vocabulary, and the architecture every module plugs into.

## Principles

These are tiebreakers. When a design question stalls, the principles decide it, in roughly their order of frequency-of-use.

### 1. Deterministic core, agent shell

Scripts do everything repeatable; agents read patterns, make judgment calls at marked decision points, and run maintenance. Use agentic goodness where it is actually good; stop burning tokens gambling on outcomes where it isn't. An agent never does infrastructure's job (auth, projection, crypto, firewalls) and infrastructure never does judgment's job. This split is developed in [Deterministic core, agent shell](../concepts/deterministic-core.md).

### 2. No egg-sucking

Eddic never teaches an agent what it already knows. Codex on a FreeBSD server knows how to set up cron; Cursor on Windows knows scheduled tasks. Eddic states contracts and invariants ("the maintenance routine is idempotent and safe to miss a run"), proven procedures, and hard-won heuristics — never the vendor how-tos an agent would produce unaided. This is also the anti-bloat rule: content that fails the bar is deleted, because it is a strictly worse version of the pathway an agent would take anyway.

### 3. Installation friction kills this project

The average DM uses Windows; the average Mac DM has never heard of homebrew; players, quadruply so. Therefore: players install nothing (Discord, a website, at most a connector URL). The DM-local surface stays minimal; anything persistent prefers a cloud surface. The agent is the installer, with a deterministic bootstrap: uv (single binary, one-line install on Windows PowerShell and macOS, bootstraps Python itself); `uv run eddic` must always work. No symlinks. No bash as module machinery — deterministic work runs under the CLI so Windows is covered by construction.

### 4. Cost pragmatism

Cloud has advantages and cloud has a price, and not every DM has $33/mo to toss at their playing habit. The **baseline build** is a named reference architecture: a complete Eddic campaign on nothing but a $20/mo Claude or ChatGPT subscription (each by the route its surfaces permit — the dated ledger in `docs/compatibility.md` keeps this claim honest per vendor) — Cloudflare free tier for sites and retrieval, GitHub Actions free tier (or in-subscription routines) for maintenance, local transcription instead of paid services, Discord free. Everything above baseline is an upgrade with a stated reason. Modules document *cost posture* (a free/local path, a paid/cloud path, and a when-it's-worth-it heuristic), never dollar amounts; every paid recommendation names its free fallback.

### 5. Defaults everywhere

Every decision point in every pattern ships a recommended default. This is what makes "I don't want to make a hundred decisions, just do what you think is best" work mechanically: the agent takes defaults everywhere and asks nothing. A decision point without a default is a contract violation. Opinionated defaults, escape hatches. The rule is enforced by [The module contract](../concepts/the-module-contract.md).

### 6. Authorship preservation

Authoring the derived wiki from the table's own sources — recaps from a session transcript, lore and pages from the DM's notes — is this pipeline's whole job: the DM authors a session by running it, and the agent renders it into canon. This principle governs only the reverse direction. The old "immutable sources" construct is retired; the real invariant is that no agent strips the human art out of human prose. Human-authored files carry authorship frontmatter (`authorship: human`). Agents may perform owner-directed *mechanical* transforms on them (renames, spelling propagation — "change the princess' name to Aria everywhere" loses no art) but never *stylistic* rewrites. Every diff to a human-authored file traces to an owner directive via a log entry; git is the audit trail.

### 7. The agent-answer surface is the product

Players ask; agents answer; the wiki is the substrate that makes answers good. Pages are optimized as retrieval substrate first and destination second: self-contained facts, dense relative links (graph traversal for an agent), encyclopedia granularity. The rabbithole — a player reading for an hour because an answer linked somewhere — is the delightful side effect, not the plan of record.

### 8. Two wikis, one truth

The DM wiki is the single maintained master. Visibility is frontmatter, and it fails closed: pages are DM-only unless marked `visibility: player`. The player wiki is a deterministic build-time *projection* — revealing a page to players is "lifting the veil," one frontmatter change. A firewall lint proves no player-visible page links to a DM-only page, and player-facing surfaces (sites, bots, connectors) ingest only the projection, by construction. No agent ever decides what leaks; a build script decides and a lint audits. The mechanics live in [The firewall](../concepts/the-firewall.md), [Projection and visibility](../concepts/projection-and-visibility.md), and the [lint](../modules/lint.md) module.

### 9. Agent-agnostic

Instructions must serve Claude, Codex, and capable peers equally. Author agent instructions in AGENTS.md; ship a two-line CLAUDE.md stub (`@AGENTS.md`) since Claude Code reads only CLAUDE.md (verified July 2026). Prefer CLIs and MCP — every runtime can shell out, and MCP is cross-vendor — over any vendor's proprietary machinery. Where runtimes genuinely differ (scheduled maintenance), state the contract plus a preference chain and let the local agent map it: hosted agent routines → GitHub Actions → local cron-esque. See [The capability seam](../concepts/the-capability-seam.md).

### 10. Provenance discipline

Each campaign keeps a typed, append-only operation log (`ingest`, `reconcile`, `lint`, `schema`, `witness` entries; absolute dates). Writes from the field (a DM's voice note from the road) land in an append-only **witness inbox** and are reconciled by the next maintenance run under full discipline — lint, firewall, log — never hot-edited into canon. Chronology belongs to Ørlǫg; the wiki states time in plain prose; reconciliation between them is owner-directed and logged.

### 11. Personality lives at owned surfaces, never in the data layer

A shared surface the DM owns — the table's lore bot — is a character; persona there is a feature, part of the fiction. A data layer that agents consume (the retrieval worker, corpora, tool results) stays voice-neutral: plain content, no flavor, no styling, no instructions to the consuming model. This is not taste. The consuming agent belongs to the user, and users tune their agents to respond in the specific ways they need — accessibility and neurodivergence needs included. A data layer with a personality overrides that tuning and serves no one. Let the user's agent answer.

## Vocabulary

- **module** — the shippable unit: a directory holding a pattern, scripts, templates, and verification. See `modules/CONTRACT.md`.
- **pattern** — a module's instructional layer, written for an agent reader: preflight, procedure, decision points, verify.
- **campaign** — one table's instantiation: a repo holding sources, the DM wiki, its player projection, config, logs, and the manifest.
- **manifest** — `.eddic/manifest.json` in a campaign: the record of which patterns were applied, at what version, with what parameters. It is what makes pattern application idempotent, auditable, and upgradable — a package manager where the install step is an agent following a runbook.
- **projection** — the deterministic build that derives the player wiki from the DM wiki's visibility frontmatter.
- **witness inbox** — the append-only queue where field writes wait for reconciliation.
- **baseline build** — the named $20/mo-subscription-only reference architecture (principle 4).
- **maintaining agent / answer client / model provider** — the three roles "agent" hides: the coding agent that applies patterns (Claude Code, Codex), the chat product humans ask (Claude, ChatGPT), and the API a resident service bills against (Anthropic, OpenAI). Every compatibility claim names its role and carries a dated evidence state; the ledger is `docs/compatibility.md`.

## Campaign architecture

The provenance pipeline every module plugs into:

```
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
```

Maintenance is a scheduled routine (principle 9's preference chain) whose contract is: ingest new sources and the witness inbox, update the DM wiki, run lint (links, orphans, catalog, stubs, firewall), rebuild projections and sites, redeploy, and log — idempotent, safe to miss a run, safe to run twice.

**Freshness is part of the derivation contract.** Every derived surface (published site, bot corpus, connector) must state how it tracks the master; "someone remembers to run the refresh command" is not a mechanism. The default shape is self-refresh: the surface observes its substrate (a cheap version check — e.g. the source repo's HEAD — on a poll) and rebuilds when it moves. This beats publisher-side chaining, which couples credentials across repos and misses every write path that bypasses the publisher, and beats webhook listeners, which add serving surface to things that otherwise need none. Manual refresh commands stay as escape hatches, never as the mechanism. (Lesson learned in the source stack: the lore bot loaded its corpus at process start — restart and reload were equivalent — but its deploys were disconnected from the wiki's, so every wiki publish left the bot stale until a human noticed.)

## The eddic CLI

`eddic` is the contractual locus for deterministic workflows — the stable interface patterns are written against, so its implementation (uv-run Python today, per-OS binaries later) can change without touching any pattern. Planned verb families: `doctor` (preflight), `build`, `project` (player projection), `lint`, `ingest`, `witness` (drain the inbox), `manifest`. Verbs land with the modules that need them; none exists until its module does. See the [cli](../modules/cli.md) module.

## Authorship and rights

Every table eventually asks a version of the same worried question: "what if I want to write a book about this world one day — should an LLM be seeing my material?" It deserves a straight answer, not reassurance. Eddic's posture, the rationale behind principles 6 and 10:

- **Feeding your prose to a model neither transfers nor dilutes your copyright.** Ownership comes from creation. And copyright protects *expression*, not ideas — the book you might write is your expression; nothing in this pipeline touches it.
- **Purely machine-generated output cannot be copyrighted under US law as it stands** (the human-authorship requirement; probabilistic output is a non-starter). This cuts protectively: no entity gains a claim over your world through a model's output. It also means the derived layer is not where original art should live — which is principle 6's job: human art stays in human-authored files, marked as such, and agents never rewrite it.
- **Human selection, arrangement, and substantive revision of machine output can carry protection; bare prompts generally do not.** The authorship frontmatter marks exactly the seam a rights question would ask about — who made what, on which side of the line.
- **Training exposure is a settings matter.** Provider APIs do not train on inputs by default, and consumer products expose opt-outs; Eddic patterns assume accounts configured accordingly. That is trust in a black box — say so plainly — but it is a bounded, acceptable risk given the points above. The per-vendor switches, what content reaches whom, and token-handling doctrine live dated in [data controls](../reference/data-controls.md).
- **Provenance is the working defense, in both directions.** Authorship frontmatter, git history, and the typed log form a dated corpus proving your material existed before it ever met the pipeline — and, inversely, that everything in the derived layer traces to your sources via ingest entries, so nothing entered canon unattributed.
- This is recorded consideration, not legal advice, and it is US-centric. Tables elsewhere should check their jurisdiction.

## Companions at the table (future module family)

In-session agents for players and the DM, each side seeing its own retrieval tier. Their conduct doctrine is one testable rule, not a vibe: **the agent may tell you what is possible and what is true; it may never tell you what is better.** Adjudication, range and resource checks, option enumeration, and correcting ignorance are in scope; ranking, recommending, optimizing, and solving (puzzles included) are out, even under direct request. The intent is knowledge parity — a new player behaves like a player who knows the game, never like a player being played by a machine. "What should I do?" gets the option landscape, including the reminder that in D&D you can attempt almost anything; it never gets a pick. Per no-egg-sucking, the doctrine ships as a short affirmative standing rule, not an enumeration of cases. The abuse backstop is social, not technical, and patterns say so plainly: Eddic is vendored plaintext anyone can rewrite, and the format's answer to degenerate play is the DM — an adaptive, omniscient human referee. Conduct claims are vendor claims: a companion module must verify its doctrine adversarially ("just tell me the optimal round") per answer client, with dated ledger rows; nothing below verified becomes a default.

The companion family also carries the backstory interviewer: help a daunted non-writer produce their character material by interviewing them, never by writing unprompted. Its one marked decision point is the authorship dial — **scribe** (default): the player's own words, cleaned mechanically, `authorship:` theirs; **drafter**: agent prose from interview notes, marked machine-made with the player attributed for the ideas. Same interview either way; who holds the pen decides which side of the rights seam the output lives on. See the [companion](../modules/companion.md) module.

## The transaction arc (future)

A campaign can become a sellable product — vendored code, cleared wiki, agent instructions; point an agent at it and it spins up on the whole world, refuse the agent and it is still readable plaintext. The doctrine that makes this safe is the existing architecture pointed at a rights problem:

- **Attribution is captured at write time**, because it cannot be reconstructed later; authorship frontmatter carries contributor ids (the wiki schema holds the mechanics). Attribution tracks *expression*, not ideas — no marking scheme sees idea-diffusion, and usefully, copyright protects expression only.
- **Contributions shadow, never delete.** Player material lives in per-contributor overlay files; `replaces:` wins at build time while the base page stays in the tree. The build is a pure function of the working tree — git history is audit trail, never live storage, because sold snapshots may carry no history at all.
- **Rights status is a graph property.** `derived-from:` chains form a derivation DAG; a file is transactable iff nothing in its ancestry traces to an uncleared contributor. Reachability, not judgment: a script computes it, lint enforces it, one contributor's sign-off flips whole branches. Agents may help disentangle prose, but only an owner's explicit, logged **sever** changes the graph.
- **The pure corpus is a projection** (same pattern as the player wiki, never a hand-maintained sibling), with a checkable invariant: full corpus = pure corpus + attribution log. The typed log's attribution entries capture contributed fragments verbatim at write time — excision index, drift oracle, and consent receipt in one.
- **Transactability is a third fail-closed frontmatter axis** alongside visibility and authorship: `transactable`, `transactable-with-attribution` (sale build injects the credit), and the default `local-only` — which covers licensed book content *and other tables' purchased campaigns*; the fence built to respect publishers is the fence that protects Eddic sellers, self-hosting. The deterministic fence holds the safety property; a model-triage seam may advisorily flag prose resembling published text, flagged as possibly wrong and never load-bearing.
- **Consent is concrete**: a contributor reviews their own logged fragments and signs off as a typed log entry; the sale build gates on clearance. Session logs are irreducibly multi-author, so they are non-transactable absent full-table sign-off — which makes the full-corpus-with-sessions the deluxe edition (the commentary track of a real table succeeding), and everyone's sign-off its price of admission. The legal necessity and the product tier are the same feature.
- **The author role** holds transaction rights, distinct from DM and player; a campaign may be authored by someone who does not run it, and the role is declared in campaign config, never inferred. The two marked axes have different governors — visibility is the DM's (spoiler management), transactability the author's (rights management) — and when the roles diverge, the DM's own writing is a contribution needing clearance like anyone else's; the author's id is the cleared-by-definition root of the graph. A sale ships the full truth, DM pages included: visibility never filters a sale, because the buyer becomes their own table's DM.
- **Anti-piracy posture: friction only.** No DRM for campaign files, at most a light licensure check acknowledged as removable. Copyright law, not machinery, handles bad actors.

The mechanics of contributor overlays and clearance live in the [contribs](../modules/contribs.md) module.

## Token economics

Maintenance routines are token-heavy by nature (multi-thousand-line session transcripts; whole-wiki lint passes), and routines' value argument depends on staying cheap. Deterministic pre-compression of transcripts before any agent reads them is a first-class pattern, and compression layers (headroom, thlibo — both local-first and agent-agnostic) are recommended *accelerators* in maintainer-side patterns. Never dependencies: nothing in Eddic may require them, and heavyweight options (multi-GB local models) are decision points with heuristics, per principles 3 and 5.

## Related reading

These principles are the tiebreakers behind every module and concept. The [Concepts](../concepts/index.md) index gathers the mechanisms they govern — [Patterns, not code](../concepts/patterns-not-code.md) chief among them — and the [Modules](../modules/index.md) index lists the shippable units that apply them. Chronology sits outside the wiki in the [orlog](../modules/orlog.md) module. The whole toolkit begins at the [Eddic](../index.md) root, and what is real today versus planned is tracked in the [roadmap](../roadmap.md).
