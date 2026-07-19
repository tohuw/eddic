# Modules

The index of shippable modules, each conforming to `CONTRACT.md`.
Suggested application order for a new campaign: cli → wiki → lint →
render → publish → retrieval → lore-bot; transcriber stands alone;
contribs and companion layer on once the campaign is live.

| module | facility | status |
|---|---|---|
| [cli](cli/) | the vendored `.eddic/` CLI: dispatcher, config, author declaration, manifest, secrets intake, `eddic run` service launcher | 0.4.0 |
| [lint](lint/) | wiki health check: links, anchors, absolute links, stubs, orphans, log format, spoiler firewall, contrib overlays | 0.3.0 |
| [wiki](wiki/) | campaign knowledge architecture: schema, fail-closed visibility, twin pages, contributor attribution, overlays, player projection | 0.3.0 |
| [render](render/) | purpose-built md→html renderer with a self-contained template and real 404 | 0.2.0 |
| [publish](publish/) | Cloudflare Pages deploy behind the lint→project→build safety pipeline | 0.1.0 |
| [retrieval](retrieval/) | Worker MCP + Actions REST facade, two bearer tokens: DM tier = master, player tier = projection | 0.4.0 |
| [lore-bot](lore-bot/) | Discord lore-keeper over the projection, self-refreshing corpus, Anthropic/OpenAI providers, capability seam | 0.3.0 |
| [transcriber](transcriber/) | local whisper.cpp session transcription, per-speaker merge | 0.1.0 |
| [contribs](contribs/) | the transaction arc: overlays, hash-pinned consent, derivation-graph rights, the sale-build fence | 0.1.0 |
| [companion](companion/) | at-the-table companions under the knowledge-parity doctrine; backstory interviewer | 0.1.0 |
| [orlog](orlog/) | fork-first timeline reconciliation and the time-question query cookbook | 0.1.0 |
| [routines](routines/) | the maintenance-routine contract and runner chain; freshness loop as the first routine | 0.1.0 |
| [capture](capture/) | session audio by the table's route (free Craig default), staged for local transcription, no folder navigation | 0.1.0 |
| [discord-setup](discord-setup/) | the server's standing spec: REST reconcile, lint-style drift, additive-only apply | 0.1.0 |
| [convene](convene/) | session lifecycle on native scheduled events: quorum, lifecycle nudges, recap announce | 0.1.0 |
| [recorder](recorder/) | the campaign's own recording bot: react-gated per-mic consent, DAVE receive via davey + pinned patches | 0.1.0 |
