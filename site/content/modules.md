# Modules

Each module is a self-contained pattern your agent applies: preflight
checks, a procedure, marked decision points that all ship defaults,
and a verification step. Apply what your table needs; skip the rest.
Everything below is shipped and CI-verified on Windows, macOS, and
Linux; items marked *live-proven* have also been exercised end to end
on a real campaign.

| module | what it gives your table | |
|---|---|---|
| cli | the campaign's vendored command core: config, health checks, an upgrade-safe record of what's applied | live-proven |
| wiki | the knowledge architecture: schema, fail-closed visibility, twin pages, attribution capture, the player projection | live-proven |
| lint | the health check: broken links, orphans, log format, contribution conflicts, and the spoiler firewall | live-proven |
| render | markdown to a clean static site, nothing more | live-proven |
| publish | the safety pipeline ending in a Cloudflare Pages deploy: strict lint → firewall → build → ship | live-proven |
| retrieval | the two-token Worker endpoint: MCP for agents, a REST facade for Custom GPT Actions | live-proven |
| lore-bot | the Discord archivist: corpus-only answers, cited pages, self-refreshing knowledge | live-proven |
| transcriber | local whisper.cpp transcription with per-speaker merge — the free replacement for paid transcript services | verified |
| contribs | player contributions with attribution, consent receipts, and the sale-build fence | verified |
| companion | at-the-table agents under one rule: what's possible and what's true, never what's better | verified |
| orlog | fork-first timeline reconciliation with the Ørlǫg chronology tool | verified |
| routines | maintenance that runs itself: idempotent, safe to miss, safe to double-run | verified |

Coming: the session **recorder** (specced — one bot records
per-speaker audio with react-gated consent), Discord server
scaffolding, and — further out — transactable campaigns: your world,
cleared and packaged, as something another table can buy and hand to
their agent.

Modules are contributable: the
[contract](https://github.com/tohuw/eddic/blob/master/modules/CONTRACT.md)
is public, and a community VTT module lands the same way ours do —
by meeting it.
