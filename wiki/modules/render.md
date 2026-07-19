# render

The render module is Eddic's purpose-built static site generator: a
markdown wiki tree goes in, a mirrored HTML tree comes out. It exists to
turn the player [projection](../concepts/projection-and-visibility.md)
into a publishable static site — a directory of HTML pages with working
relative links, readable defaults, and a `noindex` directive on every
page — which the [publish](publish.md) module then deploys. Its scope is
fixed by design: it is exactly a wiki renderer and nothing more. A need
that seems to demand an index generator, a taxonomy engine, or a plugin
system belongs in a different module, not here. This deliberate narrowness
is the module's expression of [patterns, not code](../concepts/patterns-not-code.md).
The current version is 0.2.1 and it exposes a single verb, `build`.

## Inputs and dependencies

render depends on the [cli](cli.md) and [wiki](wiki.md) modules. Its
default input is the player projection, not the DM master, so a
player-facing site cannot accidentally render privileged content: the
preflight requires that `eddic project` succeeds first, producing the
projection that render consumes. Its one runtime dependency,
markdown-it-py, is declared inline via PEP 723 and resolved by uv on the
first run, so the module is entirely local and free with no paid posture.
The verb touches three paths in a campaign: the output tree under
`dist/site`, the vendored renderer at `.eddic/lib/build.py`, and the
template at `.eddic/page.html`.

## What the renderer does

Every `page.md` becomes `page.html` at the mirrored position in the output
tree. Relative links whose targets end in `.md` are rewritten to `.html`
with any fragment preserved, so `[text](../index.md#section)` lands
correctly on the built site; links carrying an explicit URL scheme (such
as `https:` or `mailto:`) are left untouched. Each heading receives a
slugified `id` so that fragment links resolve to the right anchor. The
first H1 in the source becomes the page title, falling back to a
title-cased form of the filename when a page has no H1; on the
root/eponymous page, whose title equals the site name, the title tag is
deduped from `Name — Name` to just `Name`. Frontmatter is
stripped before rendering. Non-markdown files — images and other assets —
are copied through unchanged, while `CLAUDE.md`, `AGENTS.md`, `README.md`,
and the campaign operation log are never rendered into the site. Markdown
is processed as CommonMark with the typographer, tables, and smartquotes
enabled. The output directory is removed and rebuilt on each run, so the
site always reflects the current source exactly.

Alongside the rendered pages the build emits a real `404.html`. Without
one, static hosts with an SPA fallback answer every absent path with a
200 and the homepage; an absent page must stay indistinguishable from a
deliberately withheld one, so the renderer forces a genuine 404 on the
live site.

Site branding lives in an optional `static/` directory at the campaign
root. When present, the build copies its files verbatim — excluding
`.DS_Store` — to `static/` in the output, served at `/static/`, so a
campaign can add a banner, favicon, or avatars and reference them by
absolute path from the template or pages. It is a copy-through only:
no processing, no manifest, and nothing is added when the directory is
absent.

## Template

The look is a single self-contained HTML file with `{{TITLE}}`,
`{{SITE_NAME}}`, and `{{BODY}}` tokens. The stock template is a serif,
parchment-and-dark theme that switches on `prefers-color-scheme`, carries
its CSS inlined, makes no external requests, and includes the
`noindex, nofollow` robots meta. Restyling is done by editing the
campaign's own copy of the template at `.eddic/page.html`, which becomes
the campaign's file on vendoring — the module's template is not touched.
The `noindex` meta should be kept unless the owner explicitly wants the
site indexed.

## Configuration and invocation

As a vendored eddic verb the renderer reads `EDDIC_CONFIG`: the
`projection_dir` (default `dist/player`) is rendered to the `site_dir`
(default `dist/site`), with `site_name` and the log name taken from the
same config, and `.eddic/page.html` used as the template when present.
Run directly, it accepts `--src`, `--out`, `--template`, and `--site-name`
flags. Rendering the DM master to HTML is possible by pointing `--src` at
it, but that output must never reach a public deploy target; a browsable
DM site belongs behind the retrieval module's token, not on a Pages
deploy.

## Verify

The module ships a verify harness that renders a planted tree and asserts
the HTML mirror paths, `.md`-to-`.html` link rewriting with fragments
preserved, external links left alone, heading ids for fragment landing,
the title drawn from the H1 and deduped on the eponymous page,
frontmatter stripping, the `noindex` meta, asset copying, the emitted
`404.html`, a campaign `static/` directory copied to the output (minus
`.DS_Store`), and that non-content files are skipped. In a real campaign the check is to open the built
`index.html` locally, click through several links, and confirm the pages
resolve and read well in both light and dark.

See the [module index](index.md), the [concepts index](../concepts/index.md),
and [Eddic](../index.md) for the wider toolkit.
