# Your campaign, with a memory and a voice

Eddic is a free toolkit for online-hosted D&D campaigns. You tell
your AI agent — Claude, Codex, any capable peer — what your table
needs, and it builds the machinery from Eddic's instructions: a
campaign wiki with a spoiler firewall, a published player site, lore
you can ask questions of from your phone, a Discord archivist that
answers your players, and free local session transcription.

## The pitch, brutally true

Your players are not going to read thirty wiki pages. They absolutely
won't. What they *will* do is ask an agent "what the hell is the
Sunken City" and be happy to get a helpful answer — and what they
*might* do, much to your delight, is rabbithole from there into
reading for an hour about the Warden's oath, because you gave them a
facility that made immersion easy. The agent-answer surface is the
product; the wiki is the substrate that makes the answers good.
Your worldbuilding finally has a delivery mechanism.

## What a running campaign looks like

One wiki holds everything — including your secrets. Every page is
DM-only unless you mark it player-visible, and a deterministic
firewall proves no player surface can reach what you didn't reveal.
From that single source: an unlisted website your players can read,
a retrieval endpoint their agents (and yours, in the car, by voice)
can query, and a lore-keeper in your Discord that answers from canon,
cites its pages, and notices wiki changes by itself. Revealing a
secret is one line changed — "lifting the veil" — and every surface
follows.

## What it costs

The **baseline build** runs on a $20/month AI subscription you may
already have, plus free tiers: Cloudflare for the site and retrieval,
GitHub for storage and automation, Discord, and local transcription
instead of paid services. Everything above baseline is an upgrade
with a stated reason.

## How to start

The fastest start is giving your agent the [For agents](for-agents.md)
page — paste its URL into a chat and say what you want: "read
https://eddic-site.pages.dev/for-agents and set up my campaign; do
what you think is best" works. The instructions are written for the
agent; every decision has a sane default; you'll be asked only what
genuinely needs you. See [how it works](how-it-works.md) for the
shape of the thing.

Already a player at a table someone else set up? You need almost
nothing — see [for players](for-players.md).

<div class="copybox">
<input type="text" readonly id="agent-line" value="Read https://eddic-site.pages.dev/for-agents and set up my campaign; do what you think is best." onclick="this.select()">
<button title="Copy" aria-label="Copy the agent instruction" onclick="navigator.clipboard.writeText(document.getElementById('agent-line').value);var b=this;b.dataset.t=b.innerHTML;b.textContent='Copied';setTimeout(function(){b.innerHTML=b.dataset.t},1200)"><svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="5" y="5" width="9" height="9" rx="1.5"/><path d="M11 5V3.5A1.5 1.5 0 0 0 9.5 2h-6A1.5 1.5 0 0 0 2 3.5v6A1.5 1.5 0 0 0 3.5 11H5"/></svg></button>
</div>
