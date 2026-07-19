# Eddic

Eddic is a toolkit for running online-hosted Dungeons & Dragons campaigns. It
is delivered not as an application a table installs and runs but as a body of
patterns a coding agent applies on the table's behalf, standing each facility
up inside the user's own environment. A pattern names its preflight checks, a
procedure, the decision points where it must consult the user, and the
observable criteria that verify success; deterministic scripts do everything
repeatable while the agent's judgment is spent only at the marked decisions.
The facilities cover the arc of a hosted campaign: a maintained campaign wiki
that doubles as a retrieval substrate, a static renderer and published site,
a Discord lore-keeper that answers players from that substrate, session audio
capture and local transcription, an event-sourced timeline, scheduling and
maintenance automation, and the transaction machinery for campaigns shared or
sold. Each applied pattern records itself in the campaign manifest at
`.eddic/manifest.json`, which makes application idempotent and upgradable and
serves as the package manager for a model whose install step is an agent
following a runbook.

The project generalizes a working single-campaign stack — a published wiki,
a lore bot, a timeline tool — into adoptable, contributable units, and its
character is fixed by a short list of invariants: a deterministic core under
an agent shell, players who install nothing, a baseline build that stands on
one low-cost subscription plus free tiers, a recommended default at every
decision point, strict authorship preservation, and instructions authored for
any capable agent rather than a single vendor. This particular wiki documents
Eddic itself and carries no DM/player split: every page is public, so it has
no visibility frontmatter and no firewall.

## Branches

[Modules](modules/index.md) is the catalog of shippable units, each a pattern
plus the deterministic machinery it invokes — lint, the CLI, the wiki schema,
the renderer, publishing, retrieval, the lore bot, transcription and audio
capture, the timeline reconciler, scheduling, Discord setup, contributor
overlays, and companions. The module index lists every one and is the
authoritative entry point for applying a facility to a campaign.

[Concepts](concepts/index.md) gathers the vocabulary the modules are built
against: the mechanism of delivering facilities as patterns rather than code,
the deterministic-core-and-agent-shell split, the module contract and its
deterministic floor, the capability seam that keeps instructions
agent-agnostic, the firewall and projection model that govern visibility in
split wikis, and the release-and-versioning discipline.

[Design principles](design/principles.md) states the eleven invariants that
act as tiebreakers when a design question stalls, ordered by frequency of use
so an earlier principle outranks a later one in conflict. Every module and
concept traces back to these.

[Roadmap](roadmap.md) records the order in which the modules were built, the
rationale that sequenced the queue so each step exercised the last, the items
held open behind a live or human gate, and the deferred decisions that each
name the trigger converting them from open to settled.

The operation log (`log.md`) is the campaign's typed, append-only record of witnessed
writes, reconciliations, lint runs, schema changes, and consent and
attribution events, kept with absolute dates under the provenance discipline.
