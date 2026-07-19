# Recorder learnings

Operational history and sink-contract notes from the live-testing of the [recorder](../modules/recorder.md) module, captured 2026-07-18. The learnings here were earned against a real Discord voice channel with the owner in the loop, not derived at a desk; they are recorded so the next person hardening voice receive does not have to rediscover them.

The problem that occasioned this work was resolved the same day. A spike on DAVE — davey plus five import-time patches against py-cord 2.8.0 — made voice receive work, live capture and transcription proved it end to end, and the module shipped at 0.1.0 under `modules/recorder/`. One residual trigger remains: when [Pycord-Development/pycord#3139](https://github.com/Pycord-Development/pycord/pull/3139) lands upstream, `dave_recv.py` retires and the version pin lifts. Until then this page stands as the operational record.

## Proven live, owner in the loop

**One-bot architecture.** The recording capability deploys as part of the lore bot's own load path: `try: import recorder` sits beside `bot.py`, so one application, one token, and one process carry both the always-on archivist and the session-time recorder. There is no second daemon to babysit.

**Slash flow.** Recording is driven by `/record start|stop|help`, a py-cord command group. Invites must request the `applications.commands` scope or the commands never register. During development, the `DEBUG_GUILDS` environment variable forces instant per-guild command sync instead of waiting on Discord's global propagation.

**Interaction timing.** Defer immediately, then do the slow work. Voice `connect()` returns before the handshake actually completes, so the handler must poll `is_connected()` — a ten-second budget — before calling `start_recording`, and must fail loud with a retry message rather than silently proceeding against a half-open connection.

**Consent post, react-gated.** Consent is a reaction on a post in the voice channel's text chat. The roster of who is being recorded updates live inside that post as reactions arrive; removing a reaction drops that member's capture from that moment forward. A hard-won detail: **emoji comparisons must strip U+FE0F**, the Unicode variation selector, because Discord may report the same react with or without it, and a naive equality check silently fails to recognize consent.

**Honest language** (the owner's correction). The gate is over *microphones*, not people. The truthful phrasing is that "only microphones of people who react are recorded" — with the stated caveat that open-mic cross-talk still bleeds another person's voice onto a consenting member's track. The privacy page carries the same commitment; the language must not drift into implying a stronger guarantee than the physics of open microphones allows.

**Message edits rebuild content from live state.** `Message` objects hold stale cached content, so anything that reacts to an edit must rebuild from the current live state rather than trusting the cached body.

## Ops discipline: restart means verify dead, then start

Restarting the bot is stop, **verify dead**, start — and the verification has to match the process that actually runs. `uv run bot.py` spawns a child whose `argv` is just `python bot.py`, so a full-path match misses it; the check needs to anchor on the basename, e.g. `bot\.py$`.

The failure this prevents is duplicate processes racing. In one incident six copies were running. When multiple bots contend for the same slash interaction, the loser gets a `10062` "Unknown interaction" error while the winner's `defer` sticks in a forever-"thinking" ephemeral state, and the voice connections race into unreproducible chaos. The tells: slash commands throw `10062` on fresh interactions that should have instant handlers. **Count the processes before blaming the library.** Run unbuffered so the diagnostic output is actually there when you look.

Also process hygiene, and Discord-side: a `SIGKILL`ed voice connection leaves the bot's ghost standing in the channel until Discord times it out or a human disconnects it. The Discord-side state is part of process hygiene, not separate from it — a hard kill is not clean.

## Sink contract (py-cord 2.8's new engine)

This is the contract the upstream fix will land on. In py-cord 2.8's new voice engine, the router calls `sink.write(data, user)`, where `data.pcm` is decoded 48 kHz 16-bit stereo PCM and `user` may be `None`. The event router additionally requires the sink to expose `__sink_listeners__` — a list of `(event, method)` pairs, empty is fine — and a `walk_children()` method; the reader also touches `sink.client`. Our `ConsentSink` already matches this contract.

## How Craig survives DAVE (2026-07-18 research)

The bot survives DAVE by being a legitimate end-to-end-encrypted *participant*: it joins the call's MLS group and receives keys like any other client, rather than trying to break or bypass the encryption. The working implementation is **davey** ([github.com/Snazzah/davey](https://github.com/Snazzah/davey)) — a Rust DAVE implementation over OpenMLS, written by one of Craig's co-maintainers, and the JS ecosystem's de facto core. Davey ships **Python bindings**. This reframes pycord#3139 as plumbing — wiring a `DAVESession` into the voice packet path — not cryptography. If that PR stalls, wiring davey ourselves into py-cord's 2.8 engine, against the sink contract we already match, is a credible fallback well before any Node-sidecar contortion.

## Known design debt (before shipping)

**Silence-gap padding.** Per-speaker tracks receive only speech frames, so over a long session the tracks drift out of cross-track alignment. The gaps must be padded by packet timestamps — as Craig does — or the transcriber's merge-by-ordering degrades.

**Prefer Opus/OGG over PCM-WAV.** Prefer capturing the Opus-encoded stream into OGG rather than decoding to PCM-WAV. See `notes/cloud-recorder-plan.md` for the R2/cloud, two-token direction this points toward. Both of these are noted against the [transcriber](../modules/transcriber.md)'s downstream needs and remain open on the [roadmap](../roadmap.md).

## Related

- [recorder](../modules/recorder.md) — the shipped module these learnings hardened.
- [capture](../modules/capture.md) — the pattern that chooses a campaign's recording route; the recorder is its self-hosted, consent-gated alternative.
- [transcriber](../modules/transcriber.md) — the on-disk layout the recorder stages into, and the consumer of the alignment and encoding debt above.
- [the deterministic core](../concepts/deterministic-core.md) — why the consent gate is code in the sink's write path rather than agent judgment.
- [the firewall](../concepts/the-firewall.md) — the discipline that keeps the privacy commitment honest across surfaces.
- [roadmap](../roadmap.md) — where the residual pin-lift and cloud-recorder direction live.
