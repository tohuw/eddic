# Data controls

Provider privacy profiles: what campaign content touches which vendor, and
which switches govern it. Dated like everything in the compatibility
reference; vendors move their policies, so re-check the dates before
repeating a claim. This is operational guidance, not legal advice. The
authorship-and-rights frame lives in the [design principles](../design/principles.md).

## What actually leaves the campaign

- **The full session transcript.** This is the largest content disclosure in
  the system and the one easiest to forget, because the step that makes it is
  the step that feels like authoring. Transcription itself is local and leaks
  nothing; the recap step that follows sends everything. To write a session
  recap and the pages derived from it (the [wiki module](../modules/wiki.md)
  owns that step), an agent reads the session's **entire verbatim
  transcript** — so the whole transcript goes to whichever model provider
  that agent runs on, Claude or ChatGPT. Everything means everything the
  recording caught: table talk between scenes, health and work chat, asides
  that were never about the game, and speaker labels that are Discord display
  names. Nothing filters it beforehand, because separating the story from the
  banter is precisely the task being handed over. Consent to be recorded is
  not consent to this — the [recorder's](../modules/recorder.md) consent post
  now discloses both, and the DM owes the table the sentence in person
  besides.
- **Answer clients** (Claude, ChatGPT) see whatever tier their token
  unlocks, question by question. The player tier never contains DM material
  by construction — that guarantee is the
  [projection's](../concepts/projection-and-visibility.md), not any privacy
  setting's.
- **Resident bots** send the corpus to their model provider's API on every
  uncached question. The always-on [lore bot](../modules/lore-bot.md) is the
  worked instance, and it sends more than the question: `bot.py`'s answer path
  pulls the channel's **last 15 messages** as context on every mention,
  including messages from members who never addressed the bot and may not have
  registered that it was listening. Ambient channel chatter is therefore a
  standing disclosure, not an occasional one.
- **The roster** (real names) rides only in a resident bot's request, behind
  the cached region, and never enters wikis, repos, or corpora.

Retention is the other half of the question and is thinner than the
disclosure list suggests. The cloud recorder plan carries a 60-day lifecycle
rule; the local path has a documented default in the capture pattern and no
mechanism enforcing it, so the sweep is an owner's step rather than a
guarantee. Transcripts, once written, are campaign source and are kept.
Removing a passage after a recap has run removes it from the campaign's copies
only — no request reaches into a provider's systems to unsend what was already
sent, which is the argument for cutting early rather than apologising late.

## Anthropic (profile dated 2026-07)

- Consumer (claude.ai): training-related settings live in the user's account
  controls; the posture taken in the [design principles](../design/principles.md)
  is to set them deliberately and
  accept the black-box trust, named honestly.
- API: not used for training by default per Anthropic's commercial terms. The
  lore bot's traffic is API traffic.

## OpenAI (profile dated 2026-07)

- Consumer (ChatGPT): "Improve the model for everyone" is the training toggle
  (Settings → Data Controls); Temporary Chats are excluded from training and
  history but still retained up to ~30 days; Memory and connected-app content
  follow the account's training setting. Feedback (thumbs) submits the
  conversation for review — tell tables that feedback on a lore answer shares
  the exchange.
- API: not used for training by default (help.openai.com 5722486). An
  OpenAI-provider lore bot is API traffic, billed and governed separately from
  anyone's ChatGPT subscription.

## Token intake — how an owner hands the agent a secret

Never through the conversation. Four routes, in preference order:

1. **OAuth the agent drives, the human approves** (`wrangler login`,
   `gh auth login`): the agent runs it, the browser opens, the human clicks
   Allow. No token is ever visible to anyone.
2. **Tokens the agent mints** ([retrieval](../modules/retrieval.md) tiers):
   generated and bound as secrets in one motion; the owner supplies nothing
   and receives capability URLs once, labeled.
3. **Vendor-portal tokens** (Discord bots, API keys): the agent drives the
   portal with consent and moves the token straight into the gitignored config
   file — clipboard relay, wiped after, fingerprint only in chat — or,
   self-serve, the agent prepares the file with named empty slots and the owner
   runs `eddic secrets` (see the [cli](../modules/cli.md) module) — a local
   no-echo prompt that writes each value into place and reports only
   fingerprints. (Editing the file by hand works too.)
4. **Already-resident secrets**: the owner says where a key already lives (an
   env file, a shell profile); the agent points the process at it and never
   re-echoes it. Environment beats config file by design, so this route copies
   nothing.

A secret that transits the conversation is exposed, and exposure means
rotation — route 3's discipline exists so it never has to.

## Token handling

- Tokens live in Worker secrets and connector configs — never in files, repos,
  URLs you write down, or chat transcripts when avoidable. When a connector UI
  accepts bearer auth, prefer it (the token stays out of the endpoint URL);
  Claude's connector UI is URL-only today, which is why the capability URL
  exists.
- When you must show a token, show it once, for pasting, and say so. When
  referring to one later, use a fingerprint (first 8 characters) — enough to
  tell tokens apart, useless to an eavesdropper.
- **Exposure means rotation, not deliberation**: a token that landed in a
  transcript, screenshot, shared screen, or log gets rotated
  (`wrangler secret put`, seconds, no republish) before anyone wonders whether
  the exposure mattered. The DM tier's token is the campaign's biggest secret
  in one string; treat a suspected leak as a fact.

Related: [the firewall](../concepts/the-firewall.md),
[projection and visibility](../concepts/projection-and-visibility.md),
[retrieval](../modules/retrieval.md), [lore bot](../modules/lore-bot.md),
[cli](../modules/cli.md), and the [design principles](../design/principles.md).
Back to the [reference index](index.md).
