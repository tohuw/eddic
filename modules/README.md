# Modules

The index of shippable modules, each conforming to `CONTRACT.md`.
Suggested application order for a new campaign: cli → wiki → lint →
render → publish → retrieval → lore-bot; transcriber stands alone.

| module | facility | status |
|---|---|---|
| [cli](cli/) | the vendored `.eddic/` CLI: dispatcher, config, applied-patterns manifest | 0.1.0 |
| [lint](lint/) | wiki health check: links, anchors, absolute links, stubs, orphans, log format, spoiler firewall | 0.2.0 |
| [wiki](wiki/) | campaign knowledge architecture: schema, fail-closed visibility, twin pages, player projection | 0.1.0 |
| [render](render/) | purpose-built md→html renderer with a self-contained template | 0.1.0 |
| [publish](publish/) | Cloudflare Pages deploy behind the lint→project→build safety pipeline | 0.1.0 |
| [retrieval](retrieval/) | Worker MCP, two bearer tokens: DM tier = master, player tier = projection | 0.1.0 |
| [lore-bot](lore-bot/) | Discord lore-keeper over the projection, self-refreshing corpus | 0.1.0 |
| [transcriber](transcriber/) | local whisper.cpp session transcription, per-speaker merge | 0.1.0 |
