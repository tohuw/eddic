# Pattern: render the site

Turns the player projection into a publishable static site: a
mirrored HTML tree with working relative links, readable defaults,
and `noindex` on every page. The renderer's scope is fixed by design
— if a need seems to demand an index generator, taxonomy engine, or
plugin system here, the need belongs in a different module.

## Preflight

- cli and wiki patterns applied; `eddic project` succeeds (the
  renderer's default input is the projection, so player-facing sites
  cannot accidentally render the DM master).
- uv available: the renderer declares its one dependency
  (markdown-it-py) inline, and uv resolves it on first run.

## Procedure

1. Vendor the verb and the template:

       cp scripts/render.py <campaign>/.eddic/lib/build.py
       cp templates/page.html <campaign>/.eddic/page.html
       uv run <campaign>/.eddic/eddic.py manifest record \
           --module render --version 0.1.0 --verbs build

2. Build: `uv run <campaign>/.eddic/eddic.py project` then
   `uv run <campaign>/.eddic/eddic.py build`. Output lands in the
   configured `site_dir`.

3. If the owner wants a distinct look, edit `.eddic/page.html`
   directly — it is the campaign's file now (one template, inlined
   CSS, `{{TITLE}}`/`{{SITE_NAME}}`/`{{BODY}}` tokens). Keep the
   `noindex` meta unless the owner explicitly wants the site
   indexed.

## Decision points

- **Theme.** Default: the stock template (serif, parchment/dark via
  `prefers-color-scheme`, no external requests — fonts, CSS, and
  everything else inlined or system). Restyle by editing the
  campaign's copy, not the module's.
- **What to render.** Default: the player projection. Rendering the
  DM master to HTML is possible (`--src`) but its output must never
  reach a public deploy target; if the owner wants a browsable DM
  site, that belongs behind the retrieval module's token, not on
  Pages.

## Verify

- `uv run modules/render/verify/run.py` — renders a planted tree and
  asserts: html mirror paths, `.md` → `.html` link rewriting with
  fragments preserved, heading ids for fragment landing, title from
  H1, frontmatter stripped, noindex present, assets copied,
  non-content files skipped.
- In the real campaign: open `dist/site/index.html` locally; click
  several links; confirm they resolve and the pages read well in
  light and dark.
