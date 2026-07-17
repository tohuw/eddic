# Eddic

A toolkit for online-hosted D&D campaigns — built to be read by your AI
agent, not just by you.

Eddic is a system of patterns: modular, proven procedures where the agent
is the reader and does as much of the setup, deployment, and upkeep for
the user as possible, using deterministic processes wherever possible.
You tell your agent (Claude, Codex, or any capable peer) what you want;
it reads the relevant Eddic module and manifests working stuff. Codex
users can also install the repo as a plugin (`codex plugin install
tohuw/eddic`) — its bundled skill just routes to the same canonical
instructions.

The name is from the Eddas — the source-books the Norse myths were
compiled from. Eddic is source material for agents.

## The pitch, brutally true

Your players are not going to read thirty wiki pages. They absolutely
won't. What they *will* do is ask an agent "what the hell is the Sunken
City" and be happy to get a helpful answer — and what they *might* do,
much to your delight, is rabbithole from there into reading for an hour
about the Warden's oath, because you gave them a facility that made
immersion easy. The agent-answer surface is the product; the wiki is the substrate
that makes the answers good. Your worldbuilding finally has a delivery
mechanism.

## What Eddic provides

Only stuff your agent might not guess at, but is proven to work and bears
a sane architectural set of decisions your agent can manifest into
working stuff. Nothing here teaches an agent what it already knows.

- A campaign knowledge architecture: one DM-truth wiki, a deterministic
  player-visible projection, hard spoiler firewalls, provenance
  discipline, and agentic retrieval surfaces (including from a phone,
  while driving).
- Modules for the surrounding machinery: publishing, lore bots, session
  transcription, Discord setup, timeline tooling (Ørlǫg), maintenance
  routines, and more — each independently adoptable.
- A contract that lets the community contribute modules (Roll20, Foundry,
  whatever your table runs on) by PR.

## Reading order

- `AGENTS.md` — entry point for agents: routes setup work and
  development work.
- `DESIGN.md` — founding principles, vocabulary, and the campaign
  architecture.
- `modules/CONTRACT.md` — what a module is, its anatomy, and the bar it
  must clear.
- `ROADMAP.md` — the module queue and deferred decisions with their
  triggers.

## Status

Bootstrapping (July 2026). Eddic generalizes a working single-campaign
stack — a published campaign wiki, a Discord lore-keeper bot, and an
event-sourced timeline tool — that ran a real table first. Modules are
being extracted from it in roadmap order.
