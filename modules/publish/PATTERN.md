# Pattern: publish the player site

Puts the rendered player site on Cloudflare Pages, unlisted, behind
the full safety pipeline: strict lint → firewall projection → render
→ deploy, refusing at the first failure. The pipeline is why "publish"
is one verb and not four commands in a shell history.

## Preflight

- cli, wiki, and render patterns applied; `eddic project` and
  `eddic build` succeed.
- A Cloudflare account exists and wrangler is authenticated
  (`wrangler whoami`). If the user has no account or login, this is
  an interactive step they must do themselves — direct them, don't
  attempt it for them (`wrangler login` opens a browser).
- Node is available for wrangler (npx works if a global install is
  unwanted).

## Procedure

1. Vendor the verb:

       cp scripts/publish.py <campaign>/.eddic/lib/publish.py
       uv run <campaign>/.eddic/eddic.py manifest record \
           --module publish --version 0.1.0 --verbs publish

2. Create the Pages project once (`wrangler pages project create
   <name>`), and record the name in `.eddic/config.json` as
   `pages_project`.

3. Rehearse: `eddic.py publish --dry-run` — the whole pipeline runs,
   nothing deploys, the deploy command prints.

4. Publish: `eddic.py publish`. Every subsequent publish is the same
   verb; lint failures and firewall breaches refuse the deploy with
   the reason on stderr.

## Decision points

- **Pages project name.** Default: the site name, slugified. It
  becomes the `<name>.pages.dev` subdomain.
- **Custom domain.** Default: none — the pages.dev subdomain is
  fine for an unlisted campaign site. If the owner wants one, they
  attach it in the Cloudflare dashboard; the deploy verb is
  unchanged.
- **Discoverability.** Default: unlisted — `noindex` comes from the
  render template and stays. Search indexing is an owner decision
  with no default path here.

## Verify

- `uv run modules/publish/verify/run.py` — assembles a full campaign
  in a temp dir (stamp, vendor lint/project/build/publish, seed a
  wiki), runs `publish --dry-run` and asserts the pipeline runs to
  the deploy command; then plants a firewall breach and asserts the
  publish refuses at the projection stage.
- In the real campaign, after the first live publish: fetch the
  pages.dev URL, click through several pages, and confirm the DM
  catalog and any `.dm` page 404.
