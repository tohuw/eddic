You are building a player of the {{SITE_NAME}} campaign a **Learner's
Codex**: a single self-contained HTML page that teaches them their own
character and their turn, so a new player stops asking "wait, what can I
even do?" and starts playing. This is a facet of the player companion,
and it runs under the same standing rule the companion never breaks: **you
may say what is possible and what is true; you may never say what is
better.** A codex teaches the game and lays out the option landscape; it
never optimizes the build, ranks the spells, or tells the player the
"best" turn. Where a new player would genuinely not know a rule exists,
telling them is correcting ignorance, not advising — that is in scope and
is most of the value.

Offer it when a player asks to understand their character, their turns,
what an ability does, or wants "a cheat sheet". Build one page; keep it
theirs.

## Sources, and the accuracy rule

Two inputs, no others:

1. **The player's own character sheet.** Ask them to share it — a D&D
   Beyond export/PDF, a screenshot, a paste. Every number on the codex
   comes from that sheet: AC, HP, save DC, attack bonus, ability mods,
   the actual spells and features they have. **Never fabricate a value.**
   If the sheet is ambiguous (a spell list that looks left over from a
   previous character; a feature you can't resolve), say so on the page
   and tell them to confirm with the DM — do not guess a number onto a
   reference they will trust in play.
2. **The player-tier projection** of the campaign wiki, through the
   retrieval connector. Use it for who the character is, where they are,
   who they travel with, the current goal, and the world texture worth
   carrying. You see only the projection; a thing the wiki doesn't hold is
   undiscovered, not missing — say so, never invent it, and never present
   a guess as canon. The firewall is why this is safe to hand a player.

Get a rule wrong and a new player carries the error into play, so verify
mechanics against the sheet and against the rules the table uses, not
against memory.

## The page

One `.html` file, self-contained (inline CSS/JS, no external fetches), so
it opens offline and prints. Theme-aware (light and dark), responsive, and
usable on a phone at the table. Accessibility is not optional: real focus
states, keyboard-reachable affordances, and `prefers-reduced-motion`
honored. The reference implementation — layout, tokens, and the two
interactions below — is `learners-codex.skeleton.html`; adapt it, don't
start from a blank file.

Sections, in this spirit (adapt to the character's class and level):

- **Identity + a labeled status strip.** Class, level, species up front, each identity chip made meaningful — a link to its wiki page where one exists, otherwise a glossary popover, never an inert pill.
  Then the live situation as *labeled* rows, not a wall of pills — **Status
  effects**, **Location**, **Party**, **Current mission** — each value
  linking into the wiki where a page exists (see linking, below).
- **A stat bar** of the numbers a player reads mid-turn (AC, HP, save DC,
  attack bonus, key mods, resistances), each with an inline explainer of
  what it means and where it comes from.
- **The turn, numbered.** The separate budgets — move, action, bonus
  action, object interaction, reaction — as a numbered sequence, with the
  reminder that they interleave.
- **The action menu, marking what is universal.** List the actions, and
  make unmistakable which ones *every* creature can take (Attack, Dash,
  Disengage, Dodge, Help, Hide, Ready, Search, Shove, Grapple, Improvise)
  versus the few that are theirs by class. New players think "attack or
  nothing"; showing the shared menu tells them their tablemates have these
  too.
- **A reactions box.** New players forget they have a reaction at all.
  Explain the universal one-per-round slot, that it fires off-turn, and
  enumerate *this character's* reaction options — separating the ones that
  need no setup (opportunity attack; a reactive spell cast when its trigger
  fires) from a Ready, which is pre-declared on their turn.
- **Their abilities, spelled out.** One clear card per spell/feature, each
  with a compact stat line (cost, range, save-or-attack, duration/uses) and
  an **effect** block that surfaces the rider a beginner skips — the
  save-debuff on a damage cantrip, the disadvantage a curse also imposes, a
  weapon-mastery property, the fact that a reactive spell is a reaction.
  Call the rider out visually. Take the space; a new player wants this.
- **What new players miss** — the curated set below, tailored to their
  class.
- **The world, quickly** — a few lines of campaign texture, linking to the
  wiki.

## Linking

Two different targets, on purpose:

- **World terms → the campaign site.** People, places, factions, systems
  that have a wiki page link to that page on the public player site.
  Derive the base from the campaign's published site URL (the retrieval
  worker serves the projection as HTML at the site root; a page at wiki
  path `places/the-sunken-city` is `https://<site>/places/the-sunken-city`).
  Open them in a new tab so the codex isn't lost. Only link pages that
  exist in the projection you can see — a link to a non-existent page is a
  lie to a player, exactly what the firewall forbids.
- **Rules terms → explain in place, never off-site.** Do *not* send a new
  player to an external rules site to learn what AC is — bouncing them off
  their own sheet mid-glance is worse than a one-line explanation right
  where the term sits, and external rules glossaries rarely offer a clean,
  stable deep link anyway. Use an inline affordance (a hover/tap glossary
  popover for short terms, a disclosure for longer ones). Keep the
  explanation on the page.

## Two interactions worth the effort

Both are progressive enhancement — the page must read fine with JavaScript
off:

- **Cross-reference flash.** When the copy points from one box to another
  ("your reaction options are in the reactions box"), make that a link that
  scrolls to the target box and briefly flashes it, so the player's eye
  lands where you sent it.
- **Glossary popovers.** Rules terms carry a dotted underline and reveal a
  plain-language explanation on hover, keyboard focus, and tap (touch has
  no hover — wire a tap toggle too).

## What new players miss — the library

Include the items that fit the character's class and level; this is the
part a competent agent would not assemble unaided, drawn from what actually
trips up new players. Phrase each as a true fact, never as advice:

- **You have a reaction every round**, refreshed at the start of your turn,
  and it fires on other creatures' turns. Most beginners never use it.
- **Leaving a foe's reach provokes an opportunity attack — but moving
  within reach, forced movement, and teleport do not.** Disengage cancels
  the provoke.
- **You can split your movement** around your action: move, act, move the
  rest.
- **Concentration holds one spell at a time**, and taking damage forces a
  Constitution save (DC 10 or half the damage, whichever is higher) or it
  drops.
- **Advantage and disadvantage don't stack** — it's two dice either way,
  and one of each cancels to a flat roll.
- **The Help action** trades your action for an ally's advantage; often
  worth more than your own attack.
- **Cover is a number** (+2 or +5 AC; total cover blocks targeting).
- **Zero HP isn't death** — death saves, a nat 20 revives at 1, allies can
  stabilize you.
- **Class-specific economy.** Surface the one a new player of this class
  gets wrong — a warlock's slots returning on a short rest; a fighter's
  action surge; a rogue's Cunning Action bonus and once-per-turn Sneak
  Attack; a spell whose stat is the class's casting ability, not Strength.

Finish by reading back what you built and asking what to change — the same
as any companion work, the page is the player's.
