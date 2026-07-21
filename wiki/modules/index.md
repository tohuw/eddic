# Modules

Eddic is delivered as modules, each a pattern a maintaining agent applies
to a campaign — contributing deterministic verbs to the `.eddic/` core and
a doc written for the agent that runs it. This is the index of shippable
modules, each conforming to [the module contract](../concepts/the-module-contract.md).
Return to the wiki root at [Eddic](../index.md).

Suggested application order for a new campaign: cli → wiki → lint → render
→ publish → retrieval → lore-bot; transcriber stands alone; contribs and
companion layer on once the campaign is live.

| module | facility | status |
|---|---|---|
| [cli](cli.md) | the vendored `.eddic/` CLI: dispatcher, config, author declaration, manifest, secrets intake, `eddic run` service launcher | 0.4.1 |
| [lint](lint.md) | wiki health check: links, anchors, absolute links, stubs, orphans, log format, spoiler firewall, contrib overlays; plus the agent-run semantic-review seam (review packet + findings schema) | 0.4.1 |
| [atlas](atlas.md) | the wiki's cross-link graph as a self-contained, firewall-safe interactive map (player Atlas from the projection, DM Atlas from master); reuses the linter's resolver, deterministic output | 0.1.1 |
| [wiki](wiki.md) | campaign knowledge architecture: schema, fail-closed visibility, twin pages, contributor attribution, overlays, player projection | 0.3.1 |
| [render](render.md) | purpose-built md→html renderer with a self-contained template, real 404, and served `static/` branding | 0.2.1 |
| [publish](publish.md) | Cloudflare Pages deploy behind the lint→project→build safety pipeline | 0.1.0 |
| [retrieval](retrieval.md) | unified-host Worker: player site at /, the one-URL player companion page at /&lt;token&gt;/companion, MCP + Actions REST facade behind two bearer tokens (DM tier = master, player tier = projection), and the optional witness write path (suggest_edit/suggest_page → DM-reviewed inbox) | 0.6.1 |
| [lore-bot](lore-bot.md) | the Discord lore-keeper: answers the table's questions from the player projection (corpus prompt-cached), self-refreshing by polling per the freshness contract; the convene session-lifecycle capability rides it | 0.3.2 |
| [transcriber](transcriber.md) | local whisper.cpp session transcription, per-speaker merge | 0.1.0 |
| [contribs](contribs.md) | the transaction arc: overlays, hash-pinned consent, derivation-graph rights, the sale-build fence | 0.1.0 |
| [companion](companion.md) | at-the-table companions under the knowledge-parity doctrine; backstory interviewer with collaborator facet; single-source player kit handed off as one companion-page URL | 0.2.0 |
| [orlog](orlog.md) | fork-first timeline reconciliation and the time-question query cookbook | 0.1.0 |
| [routines](routines.md) | the maintenance-routine contract and runner chain; freshness loop and the agentic semantic-review as standard routines, the latter runnable as a hosted cloud routine | 0.3.0 |
| [capture](capture.md) | session audio by the table's route (free Craig default), staged for local transcription, no folder navigation | 0.1.0 |
| [discord-setup](discord-setup.md) | the server's standing spec: REST reconcile, lint-style drift, additive-only apply | 0.1.0 |
| [convene](convene.md) | session lifecycle on native scheduled events: quorum, lifecycle nudges, recap + reveal-digest announce, prep ask; a name keyword (`/session keyword`) splits real sessions from other events, which get a light heads-up only | 0.4.0 |
| [recorder](recorder.md) | the campaign's own recording bot: react-gated per-mic consent (fail-closed public consent post, role ping via `/record-consent-role`), DAVE receive via davey + pinned patches, a localhost control surface, a `(RECORDING)` nickname badge, empty-channel auto-stop (`/record-empty-timeout`), and per-command Manage-Server-gated top-level commands (Discord-native) | 0.5.1 |
| [backup](backup.md) | tier-2 blob backup: session audio in object storage (R2 default) via rclone, gitignored, tracked by a path/size/sha256 inventory; two hooks over one worker, text push never blocks | 0.1.0 |
| [launcher](launcher.md) | native double-clickable launcher for a local service: a hand-built, code-signed macOS `.app` with its own live-log window that supervises the service, or a Windows `.cmd`, wrapping the campaign's run verb | 0.3.1 |
| [streamdeck](streamdeck.md) | Elgato Stream Deck button packs for table-time control: start/stop/status/help against the recorder's localhost control surface | 0.1.2 |

For the design tenets these modules answer to, see [principles](../design/principles.md);
for the concepts they build on, see [concepts](../concepts/index.md); for what
is real today versus planned, see the [roadmap](../roadmap.md).
