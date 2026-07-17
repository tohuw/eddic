# Data controls — provider privacy profiles

What campaign content touches which vendor, and which switches govern
it. Dated like everything in `docs/compatibility.md`; vendors move
their policies, so re-check dates before repeating a claim. This is
operational guidance, not legal advice. The authorship-and-rights
frame lives in `DESIGN.md`.

## What actually leaves the campaign

- **Answer clients** (Claude, ChatGPT) see whatever tier their token
  unlocks, question by question. The player tier never contains DM
  material by construction — that guarantee is the projection's, not
  any privacy setting's.
- **Resident bots** send the corpus to their model provider's API on
  every uncached question.
- **The roster** (real names) rides only in a resident bot's request,
  behind the cached region, and never enters wikis, repos, or corpora.

## Anthropic (profile dated 2026-07)

- Consumer (claude.ai): training-related settings live in the user's
  account controls; the posture taken in DESIGN.md is to set them
  deliberately and accept the black-box trust, named honestly.
- API: not used for training by default per Anthropic's commercial
  terms. The lore bot's traffic is API traffic.

## OpenAI (profile dated 2026-07)

- Consumer (ChatGPT): "Improve the model for everyone" is the
  training toggle (Settings → Data Controls); Temporary Chats are
  excluded from training and history but still retained up to ~30
  days; Memory and connected-app content follow the account's
  training setting. Feedback (thumbs) submits the conversation for
  review — tell tables that feedback on a lore answer shares the
  exchange.
- API: not used for training by default (help.openai.com 5722486).
  An OpenAI-provider lore bot is API traffic, billed and governed
  separately from anyone's ChatGPT subscription.

## Token handling

- Tokens live in Worker secrets and connector configs — never in
  files, repos, URLs you write down, or chat transcripts when
  avoidable. When a connector UI accepts bearer auth, prefer it (the
  token stays out of the endpoint URL); Claude's connector UI is
  URL-only today, which is why the capability URL exists.
- When you must show a token, show it once, for pasting, and say so.
  When referring to one later, use a fingerprint (first 8 characters)
  — enough to tell tokens apart, useless to an eavesdropper.
- **Exposure means rotation, not deliberation**: a token that landed
  in a transcript, screenshot, shared screen, or log gets rotated
  (`wrangler secret put`, seconds, no republish) before anyone
  wonders whether the exposure mattered. The DM tier's token is the
  campaign's biggest secret in one string; treat a suspected leak as
  a fact.
