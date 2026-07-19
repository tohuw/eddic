# Modules

Eddic is delivered as modules: each is a pattern a maintaining agent
applies to a campaign, contributing deterministic verbs to the `.eddic/`
core and a doc written for the agent that runs it. This index catalogs
every module and groups them by the job they do. The [cli](cli.md)
pattern stamps the core and is the prerequisite for all the rest. Return
to the wiki root at [Eddic](../index.md).

## Knowledge core

The substrate: the deterministic core, the knowledge architecture built
on it, and the health check that keeps that knowledge sound.

- [cli](cli.md) — stamps a campaign's `.eddic/` core: the dispatcher, config, applied-patterns manifest, and the `lib/` into which every other module vendors its verbs.
- [wiki](wiki.md) — the knowledge architecture: source layer, DM-master wiki, page visibility, twin pages, the typed operation log, and the deterministic player projection.
- [lint](lint.md) — a deterministic reporter, `eddic_lint.py`, that walks the interlinked markdown tree and names the structural rot it finds without editing anything.

## Publishing

Turning the player projection into a site the table can read.

- [render](render.md) — the purpose-built static site generator: a markdown wiki tree in, a mirrored HTML tree out, with working relative links and `noindex` on every page.
- [publish](publish.md) — deploys the player site to Cloudflare Pages behind a guarded pipeline that lints strictly, projects the firewall, and refuses to ship anything that fails a check.

## Retrieval and bots

Agentic surfaces that answer campaign questions, each bounded by the
firewall so they cannot leak what the projection does not contain.

- [retrieval](retrieval.md) — a Cloudflare Worker exposing the wiki as an MCP server, so any MCP-capable agent — the DM's phone in the car — can query the campaign with no login flow.
- [lore-bot](lore-bot.md) — an always-on Discord lore-keeper that answers from the wiki, only from the wiki, and cites the pages a reader can rabbithole into.
- [companion](companion.md) — an in-session per-seat agent governed by knowledge parity: it may say what is possible and true, never what is better.

## Session lifecycle

Standing up the table's home, capturing each session's audio, turning it
into text, and eventing the session itself.

- [discord-setup](discord-setup.md) — versions the Discord server's shape — roles, channels, topics, privacy — as JSON reconciled by one deterministic verb, so server shape stops being tribal memory.
- [convene](convene.md) — the session-lifecycle capability of the lore bot: scheduling, quorum, reminders, and the DM's between-sessions prep ask, vendored beside the bot through the capability seam.
- [capture](capture.md) — gets each session's audio into the campaign by whichever recording route fits the table, handing it downstream without the owner navigating folders.
- [recorder](recorder.md) — a session-time Discord bot that captures per-speaker audio behind a structural consent gate enforced in the audio sink, staging tracks into the transcriber's layout.
- [transcriber](transcriber.md) — runs whisper.cpp locally to turn recorded audio into a `sources/` transcript the wiki ingest compiles from; no accounts, no uploads, audio never leaves the host.

## Timeline and automation

Keeping chronology consistent between wiki and timeline, and running
recurring upkeep without a human remembering to.

- [orlog](orlog.md) — connects the campaign to its Ørlǫg timeline, adding fork-first reconcile discipline and a query cookbook so time is stated one way in each place.
- [routines](routines.md) — defines a maintenance routine as an idempotent, miss-safe, double-run-safe contract, picks a runner off a fixed preference chain, and ships the freshness loop as the first standard routine.

## Economy

Packaging a campaign that absorbed many hands' work for sale without
shipping anything whose rights are unclear.

- [contribs](contribs.md) — the transaction arc: contributed material as overlays that shadow rather than replace base pages, with computed rights and a packaging discipline that ships only what is clear to ship.
