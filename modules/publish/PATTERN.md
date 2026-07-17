# Pattern: publish the player site

Puts the rendered player site on Cloudflare Pages, unlisted, behind
the full safety pipeline: strict lint → firewall projection → render
→ deploy, refusing at the first failure. The pipeline is why "publish"
is one verb and not four commands in a shell history.

## Preflight

- cli, wiki, and render patterns applied; `eddic project` and
  `eddic build` succeed.
- Node and wrangler available — install them yourself (npx works if
  a global install is unwanted).
- Wrangler authenticated (`wrangler whoami`). Fresh account: see
  below.

### Cloudflare onboarding (fresh account)

The human's complete list — drive everything else yourself:

1. Sign up at dash.cloudflare.com. Free plan; no card, no domain.
2. Click the verification link Cloudflare emails. Deploys fail
   confusingly on unverified accounts (no workers.dev subdomain can
   be created), so don't skip this.
3. Click **Allow** when you run `wrangler login` and their browser
   opens. Run it yourself and wait for it to return; if no browser
   appears, hand them the URL wrangler prints.
4. Only if this is the account's first Worker or Pages deploy and it
   errors that a workers.dev subdomain is needed: have them open the
   Workers/Compute section of the dashboard once — visiting
   auto-creates the subdomain (wrangler's own registration prompt
   needs an interactive terminal, which you may not have). The
   auto-picked name is fine; they can rename it in the dashboard if
   they care.

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
