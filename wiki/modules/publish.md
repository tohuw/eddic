# publish

The publish module deploys a campaign's player site to Cloudflare Pages as an unlisted static site, behind a safety pipeline that refuses to ship anything that has not passed every check. It contributes a single vendored verb, `publish`, and touches only `.eddic/lib/publish.py`. It depends on the [cli](cli.md), [lint](lint.md), [wiki](wiki.md), and [render](render.md) modules, chaining their verbs into one guarded operation. Only the player site ever deploys from here; the DM-facing surface never leaves the local machine.

## The pipeline

Publishing is one verb precisely so it cannot become four commands in a shell history where a step is skipped. `publish` runs four stages in fixed order and refuses at the first failure, printing the reason on stderr and deploying nothing:

1. Strict lint — the [lint](lint.md) verb under `--strict`, so warnings such as orphans and unreachable pages fail the run, not merely errors. Skippable with `--skip-lint`.
2. Firewall projection — the [wiki](wiki.md) module's `project` verb, which strips DM-only material and produces the player-safe tree. A [firewall](../concepts/the-firewall.md) breach here refuses the deploy, so no DM content can escape into a published page.
3. Render — the [render](render.md) verb (`build`), which turns the projected wiki into the static site. After it runs, the site directory must exist and contain at least one HTML file, or the publish refuses with "site dir is empty after build".
4. Deploy — `wrangler pages deploy <site_dir> --project-name <name>`.

This ordering is the reason publish is a distinct module rather than a documented sequence: the firewall projection and strict lint stand between the wiki and the public internet, and the verb enforces that they always run.

## Invocation and configuration

`publish` runs as a vendored [cli](cli.md) verb and requires the `EDDIC_CONFIG` environment variable the dispatcher sets; run outside that context it exits with a usage error. It reads the campaign's `config.json`: `site_dir` (default `dist/site`) locates the rendered output, and `pages_project` supplies the Cloudflare Pages project name. The name may also be passed explicitly with `--project-name`, which overrides the config value. If neither is set and the run is not a dry run, publish exits with a usage error before doing any work.

`--dry-run` runs the entire pipeline — lint, projection, render, and the emptiness check — then stops short of wrangler and prints the exact deploy command instead of executing it. This is the rehearsal step: it proves the pipeline is clean without touching the deployment. Exit codes are 0 for a published or dry-run-clean run, 1 for a failed stage, and 2 for a usage error. When a live deploy is requested but `wrangler` is not on `PATH`, publish reports how to install it (`npm i -g wrangler`, or `npx wrangler`) and refuses.

## Applying the pattern

Preflight expects the cli, wiki, and render patterns already applied so that `eddic project` and `eddic build` succeed, Node and wrangler available (a global install or `npx`), and wrangler authenticated (`wrangler whoami`). A fresh Cloudflare account additionally needs email verification and a completed `wrangler login`; the first Worker or Pages deploy on an account may require visiting the dashboard's Workers/Compute section once so a `workers.dev` subdomain is auto-created, since wrangler's interactive registration prompt may be unavailable to an agent.

The procedure vendors `publish.py` into `.eddic/lib/` and records the module in the manifest, creates the Pages project once with `wrangler pages project create <name>` and stores that name as `pages_project` in `config.json`, rehearses with `publish --dry-run`, and then publishes. Every subsequent publish is the same verb.

Three decision points each carry a recommended default. The Pages project name defaults to the site name slugified, which becomes the `<name>.pages.dev` subdomain. A custom domain defaults to none, since the pages.dev subdomain suits an unlisted campaign site; attaching one is done in the Cloudflare dashboard and leaves the deploy verb unchanged. Discoverability defaults to unlisted — the `noindex` directive comes from the render template and stays — with search indexing left as an owner decision that has no default path.

## Cost and verification

The Cloudflare Pages free tier covers a campaign site comfortably: static requests are unlimited and the monthly build allowance goes unused because builds happen locally. Wrangler via npm or npx is free. The only optional cost is registering a custom domain; no paid tier is required.

The module's verify harness assembles a complete campaign in a temporary directory — stamping the project, vendoring the lint, project, build, and publish verbs, and seeding a small player wiki with a DM twin page and DM catalog — then runs `publish --dry-run` and asserts the pipeline reaches the printed deploy command while the DM twin never appears in the rendered site. It then plants a firewall breach, a player page linking to a DM-only page, and asserts the publish refuses at the projection stage with a loud refusal. In a live campaign the post-publish check is to fetch the pages.dev URL, click through several pages, and confirm the DM catalog and any DM page return 404.

## Related

See [render](render.md) for how the static site is built, [wiki](wiki.md) and [lint](lint.md) for the projection and checks the pipeline gates on, the [cli](cli.md) for the vendored-verb mechanism, and the [firewall](../concepts/the-firewall.md) concept for what the projection stage protects. Return to the [module index](index.md) or the [Eddic overview](../index.md).
