# Design principles

Eddic's design principles are tiebreakers, not decoration. When a design question stalls, the principles decide it. They are ordered roughly by frequency of use, so an earlier principle generally outranks a later one when two pull in opposite directions. Eddic exists to generalize a working single-campaign stack — a published campaign wiki, a Discord lore-keeper bot, an event-sourced timeline tool — into adoptable modules, and these eleven statements are the invariants that govern how any module is allowed to plug into that whole.

## Deterministic core, agent shell

Scripts do everything repeatable; agents read patterns, make judgment calls at marked decision points, and run maintenance. Agentic behavior is spent where it is actually good and withheld where outcomes should not be gambled on. An agent never does infrastructure's job — authentication, projection, cryptography, firewalls — and infrastructure never does judgment's job. This split, made concrete in [Deterministic core, agent shell](../concepts/deterministic-core.md), is why patterns point at deterministic scripts rather than improvising replacements for them.

## No egg-sucking

Eddic never teaches an agent what it already knows. A coding agent on any platform already knows how to schedule a task or install a runtime; Eddic instead states contracts and invariants, proven procedures, and hard-won heuristics that an agent would not produce unaided. This doubles as the anti-bloat rule: content that fails the bar is deleted, because it is a strictly worse version of what the agent would do anyway.

## Installation friction kills this project

Players install nothing — a campaign reaches them through Discord, a website, or at most a connector URL. The DM-local surface stays minimal, and anything persistent prefers a cloud surface. The one deterministic bootstrap is uv, a single binary installable in one line on Windows and macOS that bootstraps Python itself, so `uv run eddic` always resolves to the [cli](../modules/cli.md).

## Cost pragmatism

Cloud has advantages and a price, and not every table can spend freely on a hobby. The reference architecture is the **baseline build**: a complete Eddic campaign standing on nothing but a single low-cost subscription plus free tiers — free-tier static hosting, free-tier or in-subscription scheduled maintenance, local transcription in place of paid services, and free chat surfaces. Anything above baseline is an upgrade with a stated reason. Modules document a cost posture — a free or local path, a paid or cloud path, and a when-it-is-worth-it heuristic — but never dollar amounts, and every paid recommendation names its free fallback.

## Defaults everywhere

Every decision point in every pattern ships a recommended default. This is what makes "I don't want to make a hundred decisions, just do what you think is best" work mechanically: the agent takes the defaults everywhere and asks nothing. A decision point without a default is a contract violation. The rule is opinionated defaults with escape hatches, and it is enforced by [The module contract](../concepts/the-module-contract.md).

## Authorship preservation

The real invariant is that no agent strips the human art out of human prose. Human-authored files carry authorship frontmatter (`authorship: human`). Agents may perform owner-directed mechanical transforms on them — renames, spelling propagation — but never stylistic rewrites, and every diff to a human-authored file traces to an owner directive through a log entry and the git audit trail.

## The agent-answer surface is the product

Players ask; agents answer; the wiki is the substrate that makes those answers good. Pages are optimized as a retrieval substrate first and a reading destination second: self-contained facts, dense relative links for graph traversal, encyclopedia neutrality. The surfaces that consume this substrate are described under [render](../modules/render.md) and [publish](../modules/publish.md).

## Two wikis, one truth

The DM wiki is the single maintained master. Its visibility frontmatter fails closed: pages are DM-only unless marked `visibility: player`. The player wiki is a deterministic build-time projection, so revealing a page is one frontmatter change rather than a re-authoring. No agent ever decides a leak; a build script decides and the [lint](../modules/lint.md) audits, proving no player-visible page links a DM-only page. The mechanics live in [The firewall](../concepts/the-firewall.md) and [Projection and visibility](../concepts/projection-and-visibility.md).

## Agent-agnostic

Instructions must serve any capable coding agent equally. Agent instructions are authored in AGENTS.md, with a two-line CLAUDE.md stub for runtimes that read only that file. CLIs are preferred over any vendor's proprietary machinery, because every runtime can shell out. Where runtimes genuinely differ, a stated contract plus a preference chain lets the local agent map the work onto whatever facility it has. See [The capability seam](../concepts/the-capability-seam.md).

## Provenance discipline

Each campaign keeps a typed, append-only operation log with absolute dates. Writes from the field land in an append-only witness inbox and are reconciled on the next maintenance run under full discipline — lint, firewall, log — never hot-edited into canon. Chronology is owned externally and consumed through a headless interface; the wiki states time in plain prose, and every reconciliation is owner-directed and logged.

## Personality lives at owned surfaces, never in the data layer

A shared surface a DM owns, such as a table's lore bot, may have a character, because persona there is a feature of that owned surface. The data layer stays voice-neutral so that each user can tune how their own agent responds — including for accessibility and neurodivergence needs. Personality baked into the data would override that tuning and serve no one.

## Related reading

These principles are the tiebreakers behind every module and concept. The [Concepts](../concepts/index.md) index gathers the mechanisms they govern — [Patterns, not code](../concepts/patterns-not-code.md) chief among them — and the [Modules](../modules/index.md) index lists the shippable units that apply them. The whole toolkit begins at the [Eddic](../index.md) root.
