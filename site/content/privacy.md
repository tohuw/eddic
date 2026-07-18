# Privacy posture

This page is written for players whose table runs Eddic tooling —
it's the page an Eddic bot links when it asks for your consent.
Plain answers, no legalese. (It is a statement of how the tools are
built, not legal advice; your table's DM operates their own
instances.)

## The lore bot

- It answers only when addressed (or in channels your table
  designates), and it answers only from the campaign's **player**
  wiki — the version of the world your DM has revealed. It cannot
  see the DM's secrets, so it cannot leak them.
- To answer, it sends the question, a little recent channel context,
  and the player wiki to an AI provider's API (Anthropic or OpenAI,
  your table's choice). Both providers' APIs state they don't train
  on this traffic by default.
- If your table keeps a roster (who plays whom), it lives in a
  private file on the DM's side, never in the wiki, never published.

## The session recorder

- **It records you only after you opt in.** When recording starts,
  the bot posts in the voice channel's text chat; your audio enters
  the recording only after you react to that post. No react, no
  capture — that's enforced by the code, not by policy.
- Recording is per-speaker and lands on the DM's own machine, in the
  campaign's files. It exists to make session transcripts — the
  table's shared memory.
- **Consent to record is not consent to sell.** If your table ever
  packages its campaign for others (an Eddic capability), session
  material needs every participant's separate, explicit sign-off at
  that time. Saying yes to a recording never says yes to anything
  else.

## Your words, your rights

Anything you write for the campaign — a backstory, a page, a legend
in your character's voice — is captured with your authorship attached
from the moment it lands, and Eddic's machinery can always show you
exactly what of yours the campaign holds. It is never rewritten by
any AI, and it is never sold without your concrete consent over the
exact words in question.

## Questions

Ask your DM — they run the instances and hold the configuration.
For how the tools are built, the source is
[public](https://github.com/tohuw/eddic).
