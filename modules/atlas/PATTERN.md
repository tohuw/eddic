# Pattern: the Atlas

Renders the wiki's cross-link graph as one self-contained interactive
map — pages as nodes, resolved `.md` links as edges — so a reader can
see the shape of the world and jump from any page to its neighbours.
Selecting a node opens a per-page backlinks panel — who *mentions* this
page (inbound) and what it *links to* (outbound), each a click through —
computed by inverting the same resolved edge set, so it needs no new
authoring or parsing and inherits the firewall for free.
The player Atlas is built from the projection, and that closure (a
player page can only link player pages) is the whole firewall story:
no DM page and no DM-only edge can appear, because neither is in the
source tree. The scope is fixed: a graph view of the wiki, nothing
more — if a need seems to demand full-text search, a timeline, or an
editor, it belongs in a different module.

## Preflight

- cli, wiki, and lint patterns applied. The Atlas's edges are the same
  links `eddic lint` validates; its resolver mirrors the linter's, and
  the module's verify pins them equal.
- For a player Atlas: `eddic project` succeeds, so the projection dir
  exists. The renderer's default player input is the projection —
  never the master — so a DM page cannot leak into a player map by
  construction.
- uv available. The verb is stdlib-only (no dependency to resolve) but
  runs through the same `uv run` path as every other verb.

## Procedure

1. Vendor the verb:

       cp scripts/graph.py <campaign>/.eddic/lib/graph.py
       uv run <campaign>/.eddic/eddic.py manifest record \
           --module atlas --version 0.1.0 --verbs graph

2. Build the player Atlas from the projection:

       uv run <campaign>/.eddic/eddic.py project
       uv run <campaign>/.eddic/eddic.py graph --mode player

   `--mode` is explicit and never inferred: it selects the source tree.
   `player` reads the projection (`projection_dir`) and writes
   `<site_dir>/atlas.html`; that file rides the existing site deploy
   and is served at `/atlas.html` by the same ASSETS binding as the
   rest of the site — no worker change, no new serving surface.

3. Rebuild the site and deploy as usual (`eddic build`, then the
   publish/retrieval deploy step). The Atlas is a static sibling of the
   rendered pages; a node's link is a page-relative `.html` path, so it
   resolves both locally and behind the deploy.

4. Optionally link the Atlas from the site (a nav or footer entry
   pointing at `/atlas.html`) so readers can find it. This is a plain
   edit to the campaign's template; keep it minimal.

The map is regenerated from scratch on every run and depends only on
the current tree, so re-running is idempotent and safe to miss: the
Atlas simply reflects whatever the wiki says now.

## Decision points

- **Which Atlas to build.** Default: the player Atlas (`--mode player`,
  from the projection) — the one safe to publish. A DM Atlas
  (`--mode dm`) reads the master and includes DM pages plus the
  stub/orphan/unreachable maintenance overlay; it is DM-local (default
  output `<campaign>/atlas.dm.html`, outside the served `site_dir`) and
  must never reach a player deploy. Worth building when the DM wants a
  maintenance view of the whole world; serving it to the DM tier
  through the retrieval worker is a documented future rung, deliberately
  not built in v1 to keep the Atlas a single self-contained file and off
  `worker.js`.
- **Linking it from the site.** Default: add one unobtrusive footer or
  nav link to `/atlas.html` if the template makes that clean; otherwise
  leave the file reachable by direct URL. The Atlas works standalone
  either way — do not restructure a template to force a link in.
- **Backlinks panel.** Default: on, and there is nothing to configure.
  Clicking a node no longer navigates straight to the page — it selects
  the node and opens a small "mentioned by / links to" panel; the page
  itself opens from the panel's link (or middle-click/open-in-new-tab on
  the node, whose `href` is preserved). The panel is built by inverting
  the resolved edge set at render time, emitted as sorted inline JSON, so
  it stays deterministic and byte-identical and adds no library, asset,
  or request. It is firewall-correct by construction: the player Atlas is
  built from the projection, whose closure guarantees every inbound page
  is itself a player page, so a DM page can never appear as a backlink —
  the same seam that governs the nodes governs the panel. Leave it on;
  the graph is only half-legible without a per-node local view.
- **The Party mark.** Default: on, and there is nothing to configure. If
  the wiki has a `party.md` (the standing roster page whose links to
  `characters/*` are the player-character set), those PC nodes get a warm
  gold ring and a "The Party" legend control that spotlights just the PCs
  — dimming the rest — on hover, and pins on click, in the same spirit as
  the backlinks panel. It is derived entirely from `party.md`'s links via
  the same resolved edge set the graph already computes, so it adds no
  authoring and no new frontmatter, stays deterministic, and is
  firewall-correct by construction: `party.md` is player-visible and its
  PCs are player pages, so a DM-only page can never be a party member (it
  is not in the projection, so it yields no edge and no membership). If
  the wiki has no `party.md`, the Atlas is byte-identical to one built
  without this feature — no party styling, no legend entry. Leave it on;
  "which of these is our crew?" is the first question a reader asks of a
  world map.
- **Palette.** Default: the Atlas matches the stock site shell
  (parchment/dark via `prefers-color-scheme`, category colours from a
  fixed accessible palette) and needs no assets or external requests.
  If the campaign has restyled its site, adjust the inline `:root`
  variables at the top of the generated file's template in `graph.py`'s
  copy — but prefer leaving it, since it degrades gracefully anywhere.

## Verify

- `uv run modules/atlas/verify/run.py` — plants a fixture with a DM-only
  page and a DM->player edge and asserts: (a) node/edge extraction
  matches a golden; (b) the player-mode Atlas, built from the
  projection, contains no DM page and no DM-only edge (the planted
  breach cannot reach the player build); (c) determinism — the same
  input yields a byte-identical `atlas.html` across two runs; (d) the
  resolver matches `eddic_lint.py` (orphan/unreachable sets agree and
  the shared primitives are identical); and (e) the per-node backlinks
  data is the exact inversion of the edge set, is present in the markup,
  and — in player mode — references only player pages (the planted DM
  page cannot appear as anyone's backlink); and (f) the party mark —
  party.md's `characters/*` links define the PC set (a non-character it
  also links is excluded), those nodes are marked and the "The Party"
  focus control ships, and a wiki with no party.md yields byte-identical,
  party-free output. It also confirms `--mode` is required and that a
  DM-mode Atlas over the master, by contrast, does see the page — proving
  the source-tree choice is the firewall.
- In the real campaign: run `eddic graph --mode player`, open
  `dist/site/atlas.html`, drag/scroll to pan and zoom, click a node and
  confirm it opens that page. Grep the file for any known DM-only page
  path and confirm zero hits.
