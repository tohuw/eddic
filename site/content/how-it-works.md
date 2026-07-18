# How it works

Eddic is a **system of patterns**: modular instructions written for
an AI agent to read and act on, wrapped around small deterministic
scripts for everything that must never depend on judgment. Your
agent is the installer, the maintainer, and the interpreter; the
scripts are the parts that behave identically every time.

## Two wikis, one truth

You maintain exactly one wiki — the DM master, secrets included.
Visibility is a per-page marker that **fails closed**: no marker
means DM-only. A build step *projects* the player wiki from the
master, and a firewall check refuses the whole build if any
player-visible page so much as links to something hidden. Topics
that reveal progressively keep **twin pages**: the player's version
under the canonical name, the full truth beside it. Revealing is one
marker changed, at your direction; nothing decides what leaks except
a script you can read.

## Surfaces, all downstream of the projection

- **The published site** — an unlisted, fast, readable rendering of
  the player wiki on Cloudflare Pages.
- **Agentic retrieval** — a tiny Cloudflare Worker with two access
  tokens: yours sees the master, the table's sees the projection.
  Any MCP-capable agent can use it; the DM-in-the-car voice question
  is the design case. A leaked token is dead seconds after you
  notice — rotation is one command.
- **The lore bot** — a Discord archivist whose knowledge *is* the
  player projection, so it structurally cannot leak what you haven't
  revealed. Ask it for a hidden thing and it doesn't refuse — it
  can't see that the thing exists, so it sells the mystery instead.
  It watches the wiki and refreshes itself.
- **Transcription** — session audio becomes speaker-labeled
  transcripts locally, free, feeding the wiki's session records.

## Authorship, attribution, and what's yours

Agents never rewrite human prose — mechanical, owner-directed
transforms only, and every change is logged. Contributions from
players are captured with attribution the moment they land, shadow
rather than overwrite, and the machinery can prove exactly whose
words are whose — which is what makes selling a campaign possible
later, with every contributor's concrete consent. Campaign content
made with Eddic belongs to its authors, full stop.

## Agent-agnostic on purpose

Instructions live in the standard `AGENTS.md` form both major agent
families read; retrieval speaks MCP, which is cross-vendor; every
deterministic step runs through one small CLI that works identically
on Windows and macOS. Where products genuinely differ, Eddic keeps a
dated [compatibility ledger](https://github.com/tohuw/eddic/blob/master/docs/compatibility.md)
instead of vague promises: claims are verified, documented, or
honestly marked unverified.
