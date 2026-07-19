# The firewall

The firewall is Eddic's guarantee that no material a game master keeps
secret reaches the people it would spoil. It is not a component but a
property of the campaign architecture, asserted at build time and audited
mechanically, so that revealing something to players is a deliberate act
and never an accident. Its home is the founding principle *two wikis, one
truth*: the master wiki is a single maintained source, and every
player-facing surface consumes a derived copy from which secrets are
absent by construction.

## Fail-closed visibility

Secrecy is the default. A page is DM-only unless its frontmatter carries
`visibility: player`; a page with no frontmatter, or with frontmatter that
omits the marker, is withheld. This is what "fails closed" means in
practice — the failure of an author to think about a page keeps that page
secret rather than exposing it, so forgetting never leaks. Where a topic
has both public and secret aspects, it splits into twin pages: a player
page under the canonical name and a `.dm` twin holding the withheld
material. Any path containing `.dm` is treated as secret regardless of
frontmatter. Visibility is the game master's axis, concerned with spoiler
management, and is distinct from the transactability axis that governs
rights; the firewall answers only the question of what players may see.
See [projection and visibility](projection-and-visibility.md).

## Enforced by projection, not judgment

The firewall is infrastructure's job, never an agent's. The player wiki is
a deterministic build-time projection of the master: the projection step
copies every page marked `visibility: player` into the projection tree,
preserving structure, and copies nothing else. The firewall is checked
before a single byte is written, and a breach refuses the whole projection
all-or-nothing. A breach is a player-visible page that links a non-player
page, or that links a page which does not exist, because in the players'
hands such a link is either a leak or a lie. No agent decides what is safe
to reveal; the build script decides, and it involves no judgment anywhere.
Player-facing surfaces — published sites, lore bots, connectors — ingest
only the projection, never the master, so the firewall stands between the
secret and every place a player could reach. This deterministic core is
carried by the [wiki](../modules/wiki.md) module.

## Audited by lint

Alongside projection, the [lint](../modules/lint.md) tool audits the
firewall as a static property of the master tree. When at least one page
carries visibility frontmatter, lint flags every `firewall-breach` — a
player-visible page linking a page that is not player-visible — as an
error, applying the same fail-closed rule that a missing marker means
DM-only. A wiki that carries no visibility frontmatter at all has nothing
to project and no firewall to enforce; lint records this as a skipped,
informational finding rather than pretending to check something absent.
The two mechanisms agree by design: the linter reports, the projection
refuses, and neither edits anything.

## In the pipeline

The firewall is the load-bearing gate of every derivation. The
[publish](../modules/publish.md) module runs the full safety pipeline —
strict lint, then firewall projection, then render, then deploy — and a
breach refuses the deploy with its reason on stderr, so a leak cannot ship
even by mistake. The [routines](../modules/routines.md) maintenance loop
runs the same projection on every cycle; a firewall refusal stops the loop
and surfaces the reason rather than deploying stale-but-safe or fresh-but-
leaking output. Because the check is deterministic and repeated at every
surface, the firewall holds regardless of who or what edited the wiki
between runs. It is one expression of the broader Eddic principle that
infrastructure, not agents, owns safety properties — see the
[design principles](../design/principles.md) and the wider set of
[concepts](index.md).
