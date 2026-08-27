# Modules

Eddic is delivered as modules, each a pattern a maintaining agent applies
to a campaign — contributing deterministic verbs to the `.eddic/` core and
a doc written for the agent that runs it. This is the index of shippable
modules, each conforming to [the module contract](../concepts/the-module-contract.md).
Return to the wiki root at [Eddic](../index.md).

Suggested application order for a new campaign: cli → wiki → lint → render
→ publish → retrieval → lore-bot; transcriber stands alone; contribs and
companion layer on once the campaign is live.

## Durability

Modules do not all age the same way, and a reader cannot tell which is
which from the facility column. Each module declares a `fragility:` in
its `module.yaml`, from a closed set of three, alongside a `walk_away:`
line saying what a campaign is left with if that module stops working.
**Durable** means plaintext and stdlib: the campaign's own files, code it
carries a pinned copy of, and no third party who can withdraw. It works
unmaintained. **Vendor-bound** means a named outside party — Discord,
Cloudflare, Apple, Craig, a model provider — can end it by changing an
API, a price or a policy; the facility is real today and is not yours to
keep. **Experimental** means expected to break: it rides interfaces its
vendor never promised, and its pattern must name what to do instead.
Today one module is experimental (the recorder, which patches private
py-cord internals against Discord's rolling voice encryption), and the
durable and vendor-bound halves are roughly even.

The mitigation is structural, and it is the reason a vendor-bound module
is worth shipping at all: **a dead module stops the campaign rather than
breaking it.** Modules vendor independently — each contributes its own
verbs to `.eddic/lib/` and records itself in the manifest, and nothing
imports across module lines — so a facility that dies takes its own
capability with it and leaves the rest running. The wiki is markdown in
a git repo either way. Losing publish costs the deployed site, not the
pages; losing retrieval costs phone access, not the projection; losing
the recorder costs a recording route the table has three of. Read each
module's `walk_away:` before adopting it, and prefer a durable module
where the facilities are comparable.

| module | facility | durability | status |
|---|---|---|---|
| [cli](cli.md) | the vendored `.eddic/` CLI: dispatcher, config, author declaration, manifest, secrets intake, `eddic run` service launcher, and `eddic upgrade` diffing the manifest against an Eddic checkout | durable | 0.5.0 |
| [lint](lint.md) | wiki health check: links, anchors, absolute links, stubs, orphans, log format, spoiler firewall, contrib overlays, pen-axis markers and merge proposals; binding checks that never quiet split from an advisory tier that does; plus the agent-run semantic-review seam (review packet + findings schema) | durable | 0.6.0 |
| [constellation](constellation.md) | the wiki's cross-link graph as a self-contained, firewall-safe interactive map (player Constellation from the projection, DM Constellation from master); reuses the linter's resolver, deterministic output, per-node "mentioned by / links to" backlinks panel, a "the party" mark spotlighting the PCs party.md names | durable | 0.3.2 |
| [wiki](wiki.md) | campaign knowledge architecture: schema, fail-closed visibility, twin pages, contributor attribution, overlays, player projection, the pen axis (curation, ingest mode, tri-state authorship) and the propose-adjudicate-merge flow for new lore | durable | 0.5.0 |
| [render](render.md) | purpose-built md→html renderer with a self-contained template, real 404, and served `static/` branding | durable | 0.2.2 |
| [publish](publish.md) | Cloudflare Pages deploy behind the lint→project→build safety pipeline | vendor-bound | 0.1.0 |
| [retrieval](retrieval.md) | unified-host Worker: player site at /, the one-URL player companion page at /&lt;token&gt;/companion, MCP + Actions REST facade behind two bearer tokens (DM tier = master, player tier = projection), and the optional witness write path (suggest_edit/suggest_page → DM-reviewed inbox) | vendor-bound | 0.6.3 |
| [harvest](harvest.md) | nightly mining of the table's own Discord chatter for wiki work: the DM's between-session rulings, questions the wiki could not answer, and names chat spells right that transcripts mangle; keeps watermarks, never a message store | vendor-bound | 0.1.0 |
| [lore-bot](lore-bot.md) | the Discord lore-keeper: answers the table's questions from the player projection (corpus prompt-cached), self-refreshing by polling per the freshness contract; the convene session-lifecycle capability rides it | vendor-bound | 0.3.3 |
| [transcriber](transcriber.md) | local whisper.cpp session transcription, per-speaker merge | durable | 0.2.0 |
| [ingest](ingest.md) | the session-to-canon step: whisper glossary from the campaign's own names, citable anchor index, recap scaffolding, off-the-record redaction, and claim-level provenance (`sources:` plus `<!-- src: -->` markers the lint resolves and the projection strips) | durable | 0.1.0 |
| [contribs](contribs.md) | the transaction arc: overlays, hash-pinned consent, derivation-graph rights, the sale-build fence (machine prose never sells), the packaging walkthrough to clearable, delivery by private repository | durable | 0.3.0 |
| [companion](companion.md) | at-the-table companions under the knowledge-parity doctrine; backstory interviewer with collaborator facet; single-source player kit handed off as one companion-page URL; private responses to DM prep asks filed to the DM-only inbox; a learner's primer building a new player a one-page teaching aid for their own character and turn; a writing assistant that interviews anyone at the table through what they have not written and never takes the pen | vendor-bound | 0.6.0 |
| [safety](safety.md) | table safety tools: lines and veils in a DM-only master, a generated player copy that cannot carry who asked, in-session stop signals, session-zero collection, and the standing rule that every agent honours the record | durable | 0.1.0 |
| [orlog](orlog.md) | fork-first timeline reconciliation and the time-question query cookbook | durable | 0.1.0 |
| [routines](routines.md) | the maintenance-routine contract and runner chain; freshness loop and the agentic semantic-review as standard routines, the latter runnable as a hosted cloud routine | vendor-bound | 0.3.0 |
| [capture](capture.md) | session audio by the table's route (free Craig default), staged for local transcription, no folder navigation | vendor-bound | 0.1.1 |
| [discord-setup](discord-setup.md) | the server's standing spec: REST reconcile, lint-style drift, additive-only apply | vendor-bound | 0.1.0 |
| [convene](convene.md) | session lifecycle on native scheduled events: quorum, lifecycle nudges, recap + reveal-digest announce, prep ask; a name keyword (`/session keyword`) splits real sessions from other events, which get a light heads-up only; `/session respond` files a player's private, ephemeral prep answer to the DM's witness inbox | vendor-bound | 0.5.1 |
| [recorder](recorder.md) | the campaign's own recording bot: react-gated per-mic consent (fail-closed public consent post, role ping via `/record-consent-role`), DAVE receive via davey + pinned patches, a localhost control surface, a `(RECORDING)` nickname badge, empty-channel auto-stop (`/record-empty-timeout`), and per-command Manage-Server-gated top-level commands (Discord-native) | experimental | 0.6.0 |
| [backup](backup.md) | tier-2 blob backup: session audio in object storage (R2 default) via rclone, gitignored, tracked by a path/size/sha256 inventory; two hooks over one worker, text push never blocks | vendor-bound | 0.1.0 |
| [launcher](launcher.md) | **deprecated 2026-07-30** — native double-clickable launcher for a local service: a hand-built, code-signed macOS `.app` with its own live-log window, Quit and Restart menu items, that supervises the service, or a Windows `.cmd`, wrapping the campaign's run verb | vendor-bound | 0.4.1 |
| [streamdeck](streamdeck.md) | Elgato Stream Deck button packs for table-time control: start/stop/status/help against the recorder's localhost control surface | vendor-bound | 0.1.2 |

For the design tenets these modules answer to, see [principles](../design/principles.md);
for the concepts they build on, see [concepts](../concepts/index.md); for what
is real today versus planned, see the [roadmap](../roadmap.md).
