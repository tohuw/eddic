# Projection and visibility

Projection and visibility is the mechanism by which one maintained body of
campaign knowledge yields a second, narrower body safe to hand to players.
It rests on a single settled principle: two wikis, one truth. The DM wiki is
the sole maintained master. The player wiki is not authored, edited, or kept
in sync by hand; it is derived from the master at build time by a
deterministic script. Everything a player may see is a strict subset of what
the master holds, computed rather than curated.

## Visibility as fail-closed frontmatter

Visibility is a per-page property expressed in frontmatter. It fails closed:
a page is DM-only unless it explicitly carries `visibility: player`. A page
with no frontmatter, or with frontmatter that omits the marker, is withheld.
Secrecy is therefore the default and disclosure the deliberate act — the
common failure mode where someone forgets to hide a spoiler cannot occur,
because forgetting hides rather than reveals. Revealing a page to players is
a single frontmatter change, described as lifting the veil: one edit moves a
page from withheld to projected on every downstream surface at once.

Visibility is one of Eddic's fail-closed frontmatter axes, governed by the
DM as an act of spoiler management. It is distinct from authorship (who wrote
a page's prose) and from transactability (whether a page may be sold), which
answer to different owners and different questions. Visibility decides only
what the table has seen.

## The projection is a deterministic build

The projection is produced by a build script, not by an agent. It copies
every page marked `visibility: player` from the master into the projection
directory, preserving the tree, and withholds everything else. No judgment is
exercised anywhere in the derivation: a page's fate is fixed entirely by its
marker. This is the projection's whole point and belongs to the
[deterministic core](deterministic-core.md) — no agent ever decides what
leaks; a build script decides and a lint audits. The projection is a pure
function of the master's current state, so it is idempotent and can be rebuilt
from scratch at any time without drift.

Two conventions ride alongside the marker. A topic that reveals progressively
is split into twin pages: a player page under the canonical name holding the
seen material, and a `.dm.md` companion holding the rest — any path containing
`.dm` never projects. Assets under `assets/` project wholesale by convention,
with DM-only assets kept under a path containing `.dm` so they, too, are
withheld. Contributor overlays are resolved before projection and carry their
own visibility frontmatter, fail-closed like any page.

## The firewall guards the seam

The line between projected and withheld is only as trustworthy as the links
that cross it. A player-visible page linking a DM-only page would, in players'
hands, be a leak; a player-visible page linking a page that does not exist
would be a lie. The firewall is the check that forbids both. It proves that no
projected page links to a non-projected or nonexistent page before a single
byte is written, and a breach refuses the whole projection all-or-nothing —
nothing ships until the pages are fixed or the twins split. The firewall is
never weakened by loosening a marker without the owner's say; that decision is
the DM's, because visibility is a safety property. The [firewall](the-firewall.md)
concept covers its rules in full, including the lint that audits the master
in place and escalates breaches rather than silently repairing them. The
firewall activates only once at least one page carries visibility frontmatter;
a wiki with none is projection-inert and the check is skipped.

## Every player surface ingests the projection

Projection is load-bearing because the player-facing surfaces consume it by
construction rather than trusting themselves to filter. The [published
site](../modules/publish.md) is built behind the full pipeline — strict lint,
then firewall projection, then render — and refuses to deploy on any breach.
The [lore bot](../modules/lore-bot.md) takes the player projection as its
corpus, so it cannot cite or leak what the projection does not contain. The
[retrieval connector](../modules/retrieval.md) serves two tiers from two
bearer tokens: the DM token
sees the master, the player token sees the projection, so the same worker
answers both audiences without either seeing the other's material. Because
each surface draws from the projection, one marker change propagates to all of
them, and no surface carries its own idea of what is secret.

---

See also the [campaign wiki module](../modules/wiki.md), which introduces visibility and
vendors the projection build; the [firewall](the-firewall.md), which enforces
the seam; and the [deterministic core](deterministic-core.md), which explains
why the derivation belongs to a script and not an agent. Back to the
[concept index](index.md).
