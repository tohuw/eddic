# For players

You're a player at an Eddic table. Your DM built the campaign's
machinery — a wiki, a spoiler firewall, a retrieval endpoint. You
don't need any of that. You need one thing: an AI companion that knows
the campaign, so you can ask "wait, who is that again?" without paging
a wiki or stalling the game. Here's how to get it. No repo, no setup.

## Your DM hands you a kit

Ask your DM for your player kit. It's a short page they fill in for
you — the campaign's name and your own read-only connector link — sent
alongside a block of instructions called the companion. Both are safe
for you to hold: the link only ever reaches the *player-visible*
version of the world, so it structurally can't leak the DM's secrets,
and the companion's conduct has been adversarially tested. Everything
below is in that kit; this page is just the shape of it.

## The easy way: let your assistant do it

You don't have to know what any of this is. Open your AI assistant
(claude.ai, ChatGPT, or whatever you use), paste in the whole kit plus
the companion text your DM sent, and say **"set me up as this
companion."** It does what it can on its own, and for the rest it hands
you exact clicks — one at a time. When it says "click this," click it
and say "done." That's the entire job; the kit carries instructions
that tell your assistant to walk you through it without jargon.

## Or do it yourself

If you'd rather click through it, it's two things:

- **Give it its personality.** Paste the companion text your DM sent
  into your assistant's standing-instructions box — a claude.ai
  Project's instructions, or a Custom GPT's. That's its rules of
  conduct; it lives there for good.
- **Connect it to the campaign.** On claude.ai: Settings → Connectors →
  Add custom connector, then paste the URL from your kit into the box
  labelled *Remote MCP server URL*; set its tools to "Always allow"
  (they only read). Add it once on the web and it follows you to your
  phone.

Then just ask: "What do we know about the Warden?" · "Remind me what
happened last session." · "Does moving here provoke, or do I disengage
first?" Talk to it like a knowledgeable tablemate.

## What it does, and what it won't

It answers from the campaign lore your table can see, and cites where
it can — recall, rules, an honest map of your options. It will help
you decide by laying the choices out. It tells you when the wiki
doesn't know a thing, because finding out is the fun.

It will never decide or roll for you — the pick and the dice stay
yours. It can't spoil the DM: it only sees the player-visible world,
so a mystery reads as a mystery, not as "I'm not allowed to say." And
it will never write your character for you. The companion stays quiet
enough that the game stays louder than it. That's the whole point.
