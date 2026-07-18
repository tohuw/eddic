# Recorder — live-test learnings (2026-07-18)

RESOLVED same day: the DAVE spike (davey + five import-time patches
to py-cord 2.8.0) made receive work, a live capture + transcription
proved it, and the module SHIPPED at 0.1.0 (modules/recorder/).
Residual trigger: when Pycord-Development/pycord#3139 lands upstream,
dave_recv.py retires and the version pin lifts. This file remains
the operational history and the sink-contract notes.

Proven live, owner in the loop:
- One-bot architecture: recording as a capability the deployed lore
  bot loads (`try: import recorder` beside bot.py); one app, one
  token, one process.
- Slash flow: `/record start|stop|help` via a py-cord command group;
  invites need the `applications.commands` scope; `DEBUG_GUILDS` env
  for instant per-guild sync during development.
- Interaction timing: **defer immediately**, then do slow work.
  Voice connect() returns before the handshake completes — poll
  `is_connected()` (10 s budget) before `start_recording`, and fail
  loud with a retry message.
- Consent post in the voice channel's text chat, react-gated:
  roster updates live in the post; removing the react drops capture
  from that moment. **Emoji comparisons must strip U+FE0F** —
  Discord may report reacts without the variation selector.
- Honest language (owner's correction): the gate is *microphones*,
  not people — "only the microphones of people who react are
  recorded", with the open-mic cross-talk caveat stated. The privacy
  page carries the same commitment.
- Message edits must rebuild content from live state — Message
  objects hold stale cached content.
- Ops discipline: restart = stop, **verify dead**, start — and the
  verification must match what actually runs: `uv run bot.py`
  spawns a child whose argv is just `python bot.py`, so full-path
  pgrep patterns match only the wrapper and orphan the bot itself.
  Match on `bot\.py$` (or ps and read with your eyes). Killing the
  wrapper does not reliably kill the child. We accumulated SIX
  zombie gateway sessions this way; N sessions of one bot race
  every slash ack — the loser gets 10062 "Unknown interaction"
  while a winner's defer sticks as a forever-"thinking" ephemeral —
  and race voice connects into unreproducible chaos. If slash
  commands 10062 with fresh interactions and instant handlers,
  count your processes before blaming the library. Run unbuffered.
  Also: a SIGKILLed voice connection leaves the bot's ghost
  standing in the channel until Discord times it out or a human
  disconnects it — Discord-side state is part of process hygiene.

Sink contract for py-cord 2.8's new engine (what the fix will land
on): router calls `sink.write(data, user)` where `data.pcm` is
decoded 48 kHz 16-bit stereo PCM and user may be None; the event
router additionally requires `__sink_listeners__` (list of
(event, method) pairs; empty is fine) and `walk_children()`; the
reader touches `sink.client`. Our ConsentSink already matches.

How Craig survives DAVE (2026-07-18 research): a bot is a legitimate
E2EE *participant* — it joins the call's MLS group and receives keys
like any client. The working implementation is **davey**
(github.com/Snazzah/davey — Rust DAVE via OpenMLS, by Craig's
co-maintainer; the JS ecosystem's de facto core), and davey ships
**Python bindings**. So pycord#3139 is plumbing (wire DAVESession
into the voice packet path), not cryptography; if it stalls, wiring
davey ourselves — into py-cord's 2.8 engine, whose sink contract we
already match — is the credible fallback before any Node-sidecar
contortion.

Known design debt before shipping:
- Silence-gap padding: per-speaker tracks only receive speech
  frames; long sessions drift out of cross-track alignment. Pad
  gaps by packet timestamps (Craig does) or the transcriber's merge
  ordering degrades.
- Prefer Opus/OGG passthrough over PCM-WAV (~10x smaller; audio
  already arrives Opus-encoded) — see notes/cloud-recorder-plan.md,
  which also holds the R2/cloud architecture (streaming multipart,
  two-token credentials, retention lifecycle).
