# lint

The lint module gives a campaign a repeatable health check for its wiki: a deterministic reporter, `eddic_lint.py`, that walks a tree of interlinked markdown pages and names the structural rot it finds. It is the reporter half of a reporter/model seam. The script never edits anything — it emits findings; deciding which to fix and which to escalate is the agent's half. That division is deliberate and load-bearing: judgment stays with the agent and the owner, while the machine-checkable floor stays deterministic and stdlib-only, runnable on any Python 3.9+ via `uv run` with nothing to install. This is the [deterministic core](../concepts/deterministic-core.md) applied to wiki maintenance.

## Invocation and exit codes

The reporter takes a wiki directory and optional flags: `uv run scripts/eddic_lint.py <wiki_dir> [--json] [--strict] [--log NAME] [--contribs DIR]`. It exits `0` when clean, `1` when there are errors, and `2` on a usage problem such as a missing directory. Info-level findings never fail a run. Warnings fail only under `--strict`, the mode routines and CI use, where an unread warning is a warning that never gets fixed. `--json` emits the machine-readable report for a consuming agent instead of the human-readable table. When run as a vendored `eddic` verb with `EDDIC_CONFIG` set, it takes the wiki, log name, and contribs directory from the campaign config.

## Severity tiers

Every finding carries a severity that determines whether it fails the run. Errors are broken links and anchors, missing titles, site-rooted links, malformed log entries, firewall breaches, and the contributor-overlay and transaction-arc structural faults. Warnings are stub drift, orphans, and unreachable pages — graph-connectivity problems that are real but not build-breaking outside strict mode. Info covers tiny unstubbed pages and the firewall-skipped notice; these are signals, not failures.

## Structure checks

Each page is parsed with its frontmatter split off and fenced or inline code stripped before analysis. A page with no line beginning `# ` raises `missing-h1` (error) — every page needs a title. Word count is measured on body prose only. A page whose last non-empty line is exactly `STUB` is a stub; if a stub grows past 150 words it raises `stub-overgrown` (warning), a prompt to promote it. A non-stub page under 30 words raises `tiny-unstubbed` (info), flagging an underweight page.

## Link and anchor resolution

Markdown links `[text](target)` are extracted; image links are ignored. A target matching an external scheme (`https:`, `mailto:`, and the like) is skipped. A target beginning `/` is a site-rooted path that resolves on no Eddic surface and raises `absolute-link` (error). Otherwise the target is split on `#` into a path and a fragment. Only paths ending in `.md`/`.MD` are judged as wiki pages; other targets (images, assets) are neither errored nor counted as links. A `.md` path is resolved relative to the directory of the page that contains the link. A path resolving outside the wiki root, or to a page that does not exist, raises `broken-link` (error). When a fragment is present, it is GitHub-slugified — lowercased, stripped of everything but word characters, dashes, and spaces, spaces to dashes — and must equal the slug of some heading in the destination (or, for a same-page `#anchor`, the current page), else `broken-anchor` (error).

## The firewall

The firewall check enforces that a player-visible page never links a hidden one. It fails closed: a page counts as DM-only unless its frontmatter says `visibility: player`. The check activates only when at least one page in the wiki carries `visibility` frontmatter. When it does, every player-visible page is examined, and any link from it to a non-player page raises `firewall-breach` (error). When no page anywhere carries visibility frontmatter, the whole check is skipped and a single `firewall-skipped` (info) finding is recorded — introducing visibility is the [wiki](wiki.md) module's job, not the linter's. See [the firewall](../concepts/the-firewall.md) and [projection and visibility](../concepts/projection-and-visibility.md) for the safety property this defends.

## Reachability and orphans

Both checks run over resolved `.md`-to-`.md` links only. The root catalogs are `index.md` and, where a DM catalog exists, `index.dm.md`; a player catalog can never link DM pages, so DM pages are reachable legitimately only via the DM catalog. A page not reached by following links from the roots raises `unreachable` (warning). A page with zero inbound links from any other page, and which is not itself a root, raises `orphan` (warning). Root catalogs are exempt from the orphan check.

## Operation log

The append-only operation log (default `log.md`, overridable with `--log`) is validated line by line: only lines beginning `## ` are checked. Each must match `## [YYYY-MM-DD] <type> | <summary>` — a two-hash prefix, a bracketed ISO date, a single whitespace-free type token, a space-pipe-space, and free-text summary. The type must be one of `ingest`, `reconcile`, `lint`, `schema`, `witness`, `attribution`, `consent`, or `sever`; any other value, or any malformed `## ` line, raises `log-malformed` (error). The linter never rewrites the log — a malformed entry is reported for the owner to decide on.

## Contributor overlays and transaction arcs

Given a `--contribs` directory, each contributor's files overlay the base wiki at their relative path or a declared `replaces:` target, and the lint sees the same effective view a build would. Structural faults are errors: two overlays claiming one target (`contrib-conflict`), an overlay landing on an existing base page without declaring `replaces:` (`contrib-collision`), a `replaces:` naming no base page (`contrib-replaces-missing`), and a file whose `authorship:` is missing or merely generic (`contrib-unattributed`) — attribution being the point of an overlay. Frontmatter for transaction arcs is validated too: a `transactability:` outside `transactable`, `transactable-with-attribution`, `local-only` raises `invalid-transactability`, and a `derived-from:` naming no page in the effective wiki raises `derived-from-missing`. See [contribs](contribs.md) for how overlays are authored.

## Triage seam

The reporter stops at naming defects. Mechanical, art-free, reversible fixes — repointing a moved link, adding an implied title, weaving in an orphan, appending a `STUB` marker — an agent may make unasked. Anything touching visibility, promoting a stub, rewriting log history, or altering human-authored prose is escalated to the owner. Every lint pass should close with a `lint` entry in the operation log recording what was found, fixed, and escalated. Within a maintenance cadence this runs inside every [routines](routines.md) pass.

See also the [Modules](index.md) index.
