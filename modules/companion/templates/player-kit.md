# Your companion for {{SITE_NAME}}

You're a player at the {{SITE_NAME}} table, and this page sets you up
with an AI companion that knows the campaign's lore — so you can ask
"wait, who is that again?" without paging through a wiki or interrupting
the game. Everything you need is on this one page: the companion's
personality, the setup, and your personal connection link. You don't
need to know anything technical.

## The easy way: let your assistant do it

Open your AI assistant (claude.ai, ChatGPT, or whatever you use). Paste
in **this whole page**, then say:

> Set me up as this companion.

It does everything it can on its own. For anything it can't do for you,
it comes back with exactly what to click — one step at a time. When it
says "click this," click it and reply "done." That's the whole job; you
never have to understand the plumbing.

<!-- Assistant reading this page: your task is to get this person set up
as the {{SITE_NAME}} companion. Assume they have never heard the words
"MCP," "connector," "API," or "config" and should not have to — never
ask them to learn a term. Two things must end up true: (1) you adopt the
persona shown under "The companion's personality" on this page as your
standing conduct, and (2) you can read the campaign through the connector
at {{PLAYER_MCP_URL}}. If your client lets you add a remote MCP server /
custom connector yourself, do it and confirm it worked. If it does not
(most chat apps can't self-configure), walk them through the manual steps
below ONE at a time — name the exact button or field label they will see
on screen, wait for "done" after each, and never make them read past the
click in front of them. Finish by having them ask one example question so
they see it work. -->

## The companion's personality

This is the companion's standing instructions. Paste it into your
assistant's instructions box (see step 1 below) and leave it there for
good — it's what makes the companion help you without playing the game
for you.

{{PLAYER_COMPANION}}

## Or set it up yourself

Two things, a couple of clicks each. No rush — the assistant path above
does all of this for you if you'd rather not.

**1. Give the companion its personality.** Copy the personality text
above and paste it into your assistant's standing-instructions box — on
claude.ai that's a Project's instructions, on ChatGPT a Custom GPT's
"Instructions." Leave it there for good.

**2. Connect it to the campaign.** On claude.ai: **Settings →
Connectors → Add ▾ → Add custom connector**. Type any name you like
(e.g. "{{SITE_NAME}}"), and in the box labeled **Remote MCP server URL**
paste this — it's your own personal link, so keep it to yourself:

    {{PLAYER_MCP_URL}}

Leave the other boxes blank, click **Add**, and on the next screen set
its tools to **Always allow** (all it ever does is read). Other apps have
the same "add a custom connector" spot — the URL is all it needs. Do it
once on the web and it follows you to your phone.

## Ask away

However you set it up, that's it — talk to it like a knowledgeable
tablemate:

- "What do we actually know about the Warden?"
- "Remind me what happened last session in the Sunken City."
- "Does moving out of here provoke an attack, or do I need to disengage
  first?"
- "Who did we promise the map to, and what did they offer?"
- "I want to do something clever here — what are my options?"

## What it will and won't do

It **answers from the campaign wiki** your table can see, and cites where
it can — recall, rules, the lay of your options. It will **help you
decide** by laying the choices out honestly. It will tell you when the
wiki simply doesn't know a thing; usually that means the table hasn't
found it yet, and finding out is the fun.

It will **never decide or roll for you** — the pick and the dice stay
yours. It **can't spoil the DM's secrets**: it only ever sees the
player-visible version of the world, so a mystery reads as a mystery, not
as "I'm not allowed to say." And it will **never write your character for
you** — your story is yours. The game stays louder than the companion;
that's the point.
