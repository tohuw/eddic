# Privacy posture

Two audiences read this page. **Players** at a table running Eddic —
this is the page an Eddic bot links when it asks for your consent, and
it tells you what happens to your voice and your words. **DMs** running
the tooling — the second half tells you what you are taking on and what
you owe your table before the first recording. It is a statement of how
the tools are built, not legal advice; every DM operates their own
instances, so the settings described here are theirs to set.

## For players

### What gets recorded

Your table's sessions are recorded as audio, one track per speaker.
Two routes exist and your DM picked one. **Craig** is a third-party
recording bot: the audio passes through and rests on a company's
servers until your DM downloads it. **Eddic's own recorder** runs on
your DM's machine, so nobody outside the table holds the audio — but it
is experimental, and your DM should be running Craig alongside it.

With Eddic's recorder, **your microphone is captured only after you
react to the consent post**. No react, no capture — enforced inside the
code that writes the files, not by policy. One honest limit: if your
voice carries through someone else's open microphone, it lands on their
track, as in any recording of a shared room.

### Where the recording goes

The audio is turned into a written transcript on your DM's own machine.
That step is offline and leaks nothing. The transcript is timestamped
and labelled by speaker, using your Discord display name.

**Then an AI reads the whole transcript.** To write the session recap
and the wiki pages that come out of it, an assistant run by a company
outside your table — Anthropic's Claude or OpenAI's ChatGPT, whichever
your DM uses — is handed the transcript in full, start to finish. That
includes everything the recording caught while it was running: talk
between scenes, your day, your job, your health, the joke you would
rather not see in writing. Nothing filters it first, because telling
the story apart from the banter is exactly the job the assistant is
being given.

This is the disclosure that matters most, and it is a separate thing
from being recorded. Reacting to a consent post says yes to a
microphone. On its own it does not say yes to your words being sent to
a company. Both should be said out loud at your table. If only the
first one was, ask about the second.

### Who can see what

- **The audio and the transcript** stay on your DM's machine and are
  never published. If your table uses Craig, its servers hold the audio
  too, under Craig's own terms.
- **The AI provider** sees the full transcript every time a recap is
  written, and — separately — sees the player wiki, your question, and
  the last fifteen messages in the channel every time the lore bot is
  asked something. Those fifteen include messages from people who never
  addressed the bot and may not have noticed it was there. Both
  providers state that their API traffic is not used to train models by
  default.
- **The published player site** is unlisted, which is not the same as
  private. It is not linked from anywhere and carries a tag asking
  search engines to skip it, but there is no login: anyone holding the
  URL can read it. Treat anything on it as being on the open web,
  because it is.
- **The DM's secrets** are not on any surface you can reach. A
  deterministic step builds the player wiki by copying only what is
  marked player-visible, so the site, the lore bot, and your companion
  cannot leak what your DM has not revealed — that is structure, not a
  setting someone might forget.
- **The roster** (which real person plays which character) lives in a
  private file on your DM's side. It never enters the wiki, the repo,
  or anything published; it rides only inside a bot's request so the
  bot knows who it is talking to.

### What you can ask for

- **Not to be recorded at all.** Do not react. Nothing else is
  required, and nothing else is asked of you.
- **To go off the record.** Say so and your DM stops the recording.
  Today that means stopping the session recording and starting a fresh
  one afterwards; a dedicated pause button is a known gap, not a
  shipped feature, and your DM knows it.
- **To have something cut.** Ask for a passage to be deleted from the
  transcript and the audio. Before the recap runs, that is clean — the
  passage never reaches the AI at all, so ask soon rather than late.
  After the recap has run, your DM can still cut it from their copies
  and from the wiki, but they cannot reach into another company's
  systems and unsend it. Providers retain API traffic for a limited
  period for abuse monitoring and, by their stated defaults, do not
  train on it.
- **To have a page fixed or removed.** The campaign wiki is
  fix-forward: your DM edits and republishes, and every surface follows
  within minutes. What someone has already read stays read; that is the
  honest limit of any deletion.
- **Your own writing left alone.** A backstory, a page, a legend in
  your character's voice — anything you wrote is marked as yours from
  the moment it lands, and Eddic's tooling will not restyle or rewrite
  it. It can be moved, linked, and corrected for facts; it is not fed
  to an AI to be improved.
- **A veto on anything being sold.** If your table ever packages its
  campaign for anyone else, that needs your separate, explicit, and
  specific agreement, given at that time, over the exact material in
  question. Consenting to a recording is never consenting to a sale.

## For the DM

Running this makes you the person holding your table's voices, and the
person who decides where their words go. Eddic gives you machinery and
a firewall; it does not give you a compliance department. What the
tooling cannot do for you:

**Say the three things out loud, before the first recording.** That
sessions are recorded; that recordings become written transcripts; that
an AI service outside the table reads each transcript in full to write
the recap. The consent post now says all three, but a post is a notice
and your table deserves the sentence from you. Anyone who wants to
think about it should get the chance before the first session, not
mid-scene.

**Treat consent as per-purpose, not as a blanket.** A react is consent
to a microphone. It is not consent to a model provider, not consent to
publication, and not consent to sale. Ask again each time the purpose
changes, and take a no as final without negotiation.

**Know which account your transcripts ride on.** Both providers' API
terms say they do not train on API traffic by default. A transcript
pasted into a consumer chat window is governed instead by that
account's own training setting, which you should set deliberately. If
you use a chat client to write recaps, that is the setting your table's
privacy actually depends on.

**Set a retention period and honour it.** Local session audio has a
default (see the capture pattern) and it is a default, not an
enforcement — nothing deletes files behind your back, so the sweep is
yours to run. Say what the period is when you say the three things.

**Be able to stop.** A player asking to go off the record gets it, on
the spot, without being asked why. Until a pause command exists, that
means stopping the recorder — do it rather than explaining why it is
awkward.

**Remember that player-visible means public.** The published site has
no login. Marking a page player-visible puts it on the open web at a
URL that will end up in browser histories, chat logs, and phones. That
is fine for a campaign wiki and it is not fine for anything real about
a real person; keep the two apart.

**Get fresh consent before selling anything.** Selling a campaign built
from recorded sessions means every participant agreeing again,
specifically, to that. Your table's table talk is not yours to sell
because it happened on your recording.

**Check what your jurisdiction wants.** Some places require every
party's consent before a conversation is recorded, and some require it
in a particular form. Eddic's structural gate — no react, no capture —
happens to satisfy a strict reading, but the obligation is yours and
this page is not the advice you would need.

## Questions

Ask your DM: they run the instances and hold the configuration. For how
the tools are built, the source is
[public](https://github.com/tohuw/eddic).
