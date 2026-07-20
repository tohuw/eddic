"""eddic recorder — session recording as a capability of the campaign
bot (py-cord edition: py-cord's voice receive speaks Discord's DAVE
E2EE, which broke every non-DAVE receive path in March 2026).

Consent is structural: a member's audio is captured only after they
react to the session's consent post. No react, no capture — enforced
in the sink, not by policy. Audio is written on the voice thread,
never the event loop.

The consent post is the load-bearing surface: it is always a PUBLIC
message in the voice channel's text chat (`channel.send`), reacted on
that public post, so every member sees it and opts in. It is never the
ephemeral slash-command reply, which only the invoker can see — that
reply is a brief private ack. If the public consent post cannot be
sent, recording does not begin (no public consent surface, no capture).

The same start/stop/status actions are reachable two ways: the
`/record` slash commands, and a loopback-only control surface
(`control.py`, e.g. for a Stream Deck). Both call the shared session
core below, so they can never diverge.

Config (env / variables.txt): RECORD_DIR (default ../sessions/raw),
PRIVACY_URL (default the Eddic site's posture page), WIKI_LOG
(default ../wiki/log.md). Control surface: CONTROL_ENABLED (default on),
CONTROL_PORT (default 8776), CONTROL_TOKEN (optional shared secret),
CONTROL_CHANNEL_ID / CONTROL_GUILD_ID / OWNER_USER_ID (target hints).
"""

import array
import asyncio
import datetime
import io
import math
import os
import re
import threading
import wave
from pathlib import Path

import discord

import os as _os
if not _os.environ.get("DAVE_OFF"):
    import dave_recv  # patches py-cord 2.8 for DAVE receive

HERE = Path(__file__).resolve().parent
RECORD_ROOT = (HERE / os.environ.get("RECORD_DIR",
                                     "../sessions/raw")).resolve()
PRIVACY_URL = os.environ.get(
    "PRIVACY_URL", "https://eddic-site.pages.dev/privacy")
def _default_wiki_log():
    """The campaign's own config knows where the log lives; the
    standard layout is only the fallback."""
    cfg = HERE.parent / ".eddic" / "config.json"
    if cfg.is_file():
        try:
            import json
            c = json.loads(cfg.read_text(encoding="utf-8"))
            return f"../{c.get('wiki_dir', 'wiki')}/{c.get('log', 'log.md')}"
        except Exception:
            pass
    return "../wiki/log.md"


WIKI_LOG = (HERE / os.environ.get("WIKI_LOG",
                                  _default_wiki_log())).resolve()
EMOJI = "🎙️"

sessions = {}  # guild_id -> dict(vc, sink, msg, outdir, names)


def is_consent_emoji(emoji):
    return str(emoji).replace("️", "") == EMOJI.replace("️", "")


def chime_pcm():
    """A two-note rising chime, synthesized: 48 kHz 16-bit stereo,
    the transparency sound played into the channel at record start."""
    rate = 48000
    out = array.array("h")
    for freq, dur in ((660, 0.18), (880, 0.28)):
        n = int(rate * dur)
        for i in range(n):
            env = min(1.0, i / (rate * 0.01), (n - i) / (rate * 0.06))
            v = int(11000 * env * math.sin(2 * math.pi * freq * i / rate))
            out.append(v)
            out.append(v)
    return out.tobytes()


async def set_channel_status(bot, channel_id, status):
    """Voice-channel status via REST (py-cord has no wrapper yet).
    Best-effort: transparency machinery must never break recording."""
    try:
        route = discord.http.Route(
            "PUT", "/channels/{channel_id}/voice-status",
            channel_id=channel_id)
        await bot.http.request(route, json={"status": status})
    except Exception as e:
        print(f"recorder: channel status not set ({e!r}) — recording "
              f"proceeds; consent post remains the source of truth")


class ConsentSink(discord.sinks.Sink):
    """Per-user WAV writers behind the consent gate. py-cord 2.8's new
    voice engine calls write(data, user) on its recv thread, where data
    is a VoiceData (data.pcm = decoded 48kHz/16-bit/stereo PCM) and
    user is a User/Member or None (SSRC not yet attributed)."""

    # new-engine sink contract: the event router iterates these
    __sink_listeners__ = []

    def __init__(self, outdir):
        super().__init__()
        self.outdir = outdir
        self.consented = set()
        self.writers = {}
        self.namehints = {}
        self.lock = threading.Lock()
        self.stats = {"written": 0, "unconsented": 0, "unattributed": 0}

    def walk_children(self):
        return []  # no child sinks

    def is_opus(self):
        return False  # we want decoded PCM, not raw opus

    def write(self, data, user):
        if user is None:
            self.stats["unattributed"] += 1
            return
        uid = int(getattr(user, "id", user))
        if uid not in self.consented:
            self.stats["unconsented"] += 1
            return
        pcm = data.pcm if hasattr(data, "pcm") else data
        if not pcm:
            return
        self.stats["written"] += 1
        with self.lock:
            w = self.writers.get(uid)
            if w is None:
                hint = self.namehints.get(uid, str(uid))
                safe = re.sub(r"[^\w-]+", "_", hint).strip("_") or str(uid)
                path = self.outdir / f"{len(self.writers) + 1}-{safe}.wav"
                w = wave.open(str(path), "wb")
                w.setnchannels(2)
                w.setsampwidth(2)
                w.setframerate(48000)
                self.writers[uid] = w
            w.writeframes(pcm)

    def close_all(self):
        with self.lock:
            for w in self.writers.values():
                w.close()
            self.writers.clear()

    def cleanup(self):
        self.close_all()


def consent_text(names):
    roster = ", ".join(sorted(names)) if names else "nobody yet"
    return (f"{EMOJI} **Recording session open.** This voice channel is "
            f"being recorded for the campaign archive.\n"
            f"**Only the microphones of people who react with {EMOJI} "
            f"are recorded** — an unreacted mic is never captured, and "
            f"removing your react stops your capture from that moment. "
            f"(Voices audible through someone else's open mic can still "
            f"be heard on their track, as in any recording.)\n"
            f"Privacy posture: {PRIVACY_URL}\n"
            f"Recording: **{roster}**")


# --- shared session core -------------------------------------------------
# The single source of truth for start/stop/status. Both the /record
# slash commands and the localhost control surface call these, so a
# button and a slash can never do different things. Each returns a plain
# result dict (never raises for expected conditions) so a non-Discord
# caller (the control server) can serialize it straight to JSON.


async def open_session(bot, guild_id, channel, channel_status=True):
    """Connect, post the PUBLIC consent message, react on it, and begin
    consent-gated recording. `channel` is the voice channel to record.
    Returns {"ok": True, "jump_url", "outdir", "channel"} or
    {"ok": False, "error"}."""
    if guild_id in sessions:
        return {"ok": False,
                "error": "a recording session is already open here"}
    # one directory per session, named by its start — never by date
    # alone: a session crosses midnight, two sessions share a date, and
    # a crash-and-restart must never reuse a directory and squash the
    # tracks already in it
    outdir = (RECORD_ROOT
              / datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
    outdir.mkdir(parents=True, exist_ok=True)
    vc = await channel.connect()
    for _ in range(50):                 # the voice handshake can lag
        if vc.is_connected():           # behind connect()'s return;
            break                       # recording needs the real
        await asyncio.sleep(0.2)        # connection
    else:
        await vc.disconnect(force=True)
        return {"ok": False, "error": "voice connection never came up"}
    sink = ConsentSink(outdir)

    def finished(exc):
        # py-cord 2.8's AudioReader calls after(error) on its own
        # thread when recording stops
        if exc is not None:
            print(f"recorder: reader stopped with error: {exc!r}")
        sink.close_all()

    # The consent post MUST be public and MUST exist before capture: it
    # is the surface every member sees and opts in on. If it cannot be
    # posted publicly (missing Send Messages / Add Reactions here, no
    # text-in-voice), there is no consent surface, so recording does not
    # begin — we tear the connection back down rather than record with
    # only an invoker-visible ack.
    try:
        msg = await channel.send(consent_text(set()))
        await msg.add_reaction(EMOJI)
    except discord.DiscordException as e:
        await vc.disconnect(force=True)
        print(f"recorder: consent post failed ({e!r}); recording NOT "
              f"started — no public consent surface")
        return {"ok": False,
                "error": ("could not post the public consent message in "
                          "this channel; check I can send messages and "
                          "add reactions here")}
    sessions[guild_id] = {"vc": vc, "sink": sink, "msg": msg,
                          "outdir": outdir, "names": set(),
                          "status_set": False}
    vc.start_recording(sink, finished)
    # transparency: an audible chime in-channel, and (unless declined) a
    # visible status on the channel itself
    try:
        vc.play(discord.PCMAudio(io.BytesIO(chime_pcm())))
    except Exception as e:
        print(f"recorder: start chime failed ({e!r})")
    if channel_status:
        await set_channel_status(
            bot, channel.id,
            f"{EMOJI} Recording — react to the consent post")
        sessions[guild_id]["status_set"] = True
    return {"ok": True, "jump_url": msg.jump_url,
            "outdir": str(outdir), "channel": getattr(channel, "name", "")}


async def close_session(bot, guild_id):
    """Stop recording, stage the tracks, log the witness line, and mark
    the consent post ended. Returns {"ok": True, "outdir", "tracks",
    "stats"} or {"ok": False, "error"}. `tracks` is a list of
    {"name", "kb"}."""
    s = sessions.get(guild_id)
    if not s:
        return {"ok": False, "error": "no open recording session"}
    sessions.pop(guild_id, None)
    s["vc"].stop_recording()
    if s.get("status_set"):
        await set_channel_status(bot, s["vc"].channel.id, "")
    await s["vc"].disconnect()
    s["sink"].close_all()
    files = sorted(s["outdir"].glob("*.wav"))
    tracks = [{"name": f.name, "kb": f.stat().st_size // 1024}
              for f in files]
    log_error = None
    try:
        day = datetime.date.today().isoformat()
        with WIKI_LOG.open("a", encoding="utf-8") as lf:
            lf.write(f"\n## [{day}] witness | session audio recorded "
                     f"({len(files)} track(s))\n\nStaged under "
                     f"sessions/raw/{s['outdir'].name}/ by the "
                     f"recorder; transcription is a deliberate "
                     f"maintenance step.\n")
    except OSError as e:
        log_error = str(e)
    await s["msg"].edit(content=consent_text(s["names"]) +
                        "\n**Recording ended.**")
    stats = dict(s["sink"].stats)
    print(f"recorder stats: {stats}")
    result = {"ok": True, "outdir": str(s["outdir"]), "tracks": tracks,
              "stats": stats, "consented": sorted(s["names"])}
    if log_error:
        result["log_error"] = log_error
    return result


def session_status(guild_id=None):
    """Pure snapshot of recording state (no I/O, safe from any thread).
    With guild_id, scopes to that guild; without, reports every open
    session — the single-owner control-surface case. Always ok."""
    if guild_id is not None:
        active = [guild_id] if guild_id in sessions else []
    else:
        active = list(sessions)
    out = {"ok": True, "recording": bool(active), "sessions": []}
    for gid in active:
        s = sessions[gid]
        out["sessions"].append({
            "guild_id": gid,
            "channel": getattr(getattr(s["vc"], "channel", None),
                               "name", None),
            "outdir": s["outdir"].name,
            "consented": sorted(s["names"]),
            "stats": dict(s["sink"].stats),
        })
    return out


async def resolve_target(bot):
    """Pick the voice channel the control surface should record when no
    slash-command context names one. Precedence: CONTROL_CHANNEL_ID; the
    voice channel the configured OWNER_USER_ID is in; the single
    populated voice channel (optionally within CONTROL_GUILD_ID).
    Returns (guild_id, channel) or an {"ok": False, "error"} dict."""
    channel_id = os.environ.get("CONTROL_CHANNEL_ID")
    guild_id = os.environ.get("CONTROL_GUILD_ID")
    owner_id = os.environ.get("OWNER_USER_ID")
    if channel_id:
        ch = bot.get_channel(int(channel_id))
        if ch is None:
            return {"ok": False,
                    "error": f"CONTROL_CHANNEL_ID {channel_id} not found"}
        return (ch.guild.id, ch)
    if owner_id:
        for g in bot.guilds:
            m = g.get_member(int(owner_id))
            if m and m.voice and m.voice.channel:
                return (g.id, m.voice.channel)
    candidates = []
    for g in bot.guilds:
        if guild_id and g.id != int(guild_id):
            continue
        for ch in getattr(g, "voice_channels", []):
            humans = [x for x in getattr(ch, "members", []) if not x.bot]
            if humans:
                candidates.append((len(humans), g.id, ch))
    if not candidates:
        return {"ok": False,
                "error": ("no populated voice channel found — join a "
                          "voice channel, or set CONTROL_CHANNEL_ID")}
    if len(candidates) > 1:
        return {"ok": False,
                "error": ("multiple candidate voice channels are "
                          "populated; set CONTROL_CHANNEL_ID to choose")}
    _, gid, ch = candidates[0]
    return (gid, ch)


def setup(bot):
    record = bot.create_group("record",
                              "Session recording (consent-gated)")

    @record.command(name="start",
                    description="Open a recording session in your "
                                "current voice channel")
    async def start(ctx: discord.ApplicationContext,
                    channel_status: discord.Option(
                        bool, "Show a recording status on the voice "
                        "channel (default: yes)", default=True)):
        await ctx.defer(ephemeral=True)
        voice = getattr(ctx.author, "voice", None)
        if not voice or not voice.channel:
            await ctx.respond("Join a voice channel first.",
                              ephemeral=True)
            return
        result = await open_session(bot, ctx.guild_id, voice.channel,
                                    channel_status)
        if not result["ok"]:
            await ctx.respond(result["error"][:1].upper()
                              + result["error"][1:] + ".", ephemeral=True)
            return
        # The public consent post carries consent; this ephemeral reply
        # is only a private ack to the invoker with a jump link to it.
        await ctx.respond(
            f"Recording session open — [the consent post]"
            f"({result['jump_url']}) is up in the channel's text chat. "
            f"Nobody's mic is captured until they react.", ephemeral=True)

    @record.command(name="stop",
                    description="Close the recording session and "
                                "stage the tracks")
    async def stop(ctx: discord.ApplicationContext):
        _age = (discord.utils.utcnow()
                - ctx.interaction.created_at).total_seconds()
        print(f'/stop: interaction age at entry: {_age:.2f}s')
        if ctx.guild_id not in sessions:
            await ctx.respond("No open recording session.",
                              ephemeral=True)
            return
        await ctx.defer()
        result = await close_session(bot, ctx.guild_id)
        if not result["ok"]:
            await ctx.respond(result["error"][:1].upper()
                              + result["error"][1:] + ".")
            return
        lines = [f"- {t['name']} ({t['kb']} KB)"
                 for t in result["tracks"]]
        if result.get("log_error"):
            lines.append(f"(log entry failed: {result['log_error']})")
        stats = result["stats"]
        report = "\n".join(lines) or (
            f"no consented audio captured (packets — "
            f"written: {stats['written']}, "
            f"unconsented: {stats['unconsented']})")
        await ctx.respond(
            f"Recording closed. Staged in `{result['outdir']}`:\n{report}")

    @record.command(name="help",
                    description="How recording and consent work")
    async def help_cmd(ctx: discord.ApplicationContext):
        await ctx.respond(
            f"`/record start` opens a session in your voice channel; a "
            f"consent post appears in its text chat. **Only members "
            f"who react with {EMOJI} are captured** — per-speaker "
            f"tracks, stored with the campaign, for the table's own "
            f"transcripts. `/record stop` closes and stages the "
            f"tracks. Consent to record is never consent to anything "
            f"else. Privacy posture: {PRIVACY_URL}", ephemeral=True)

    @bot.event
    async def on_raw_reaction_add(payload):
        s = sessions.get(payload.guild_id)
        if not s or payload.message_id != s["msg"].id:
            return
        if not is_consent_emoji(payload.emoji) \
                or payload.user_id == bot.user.id:
            return
        member = payload.member
        hint = (member.display_name if member else str(payload.user_id))
        s["sink"].namehints[payload.user_id] = hint
        s["sink"].consented.add(payload.user_id)
        s["names"].add(hint)
        await s["msg"].edit(content=consent_text(s["names"]))

    @bot.event
    async def on_raw_reaction_remove(payload):
        s = sessions.get(payload.guild_id)
        if not s or payload.message_id != s["msg"].id:
            return
        if not is_consent_emoji(payload.emoji):
            return
        s["sink"].consented.discard(payload.user_id)
        guild = bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id) if guild else None
        if member:
            s["names"].discard(member.display_name)
            await s["msg"].edit(content=consent_text(s["names"]))

    def _start_control_surface():
        """Bring up the loopback control surface (Stream Deck etc.),
        unless disabled. Loopback-bound; all Discord work is marshalled
        back onto this event loop. Best-effort: a control-surface
        failure never stops the recorder itself."""
        if os.environ.get("CONTROL_ENABLED", "1").lower() in (
                "0", "false", "no", "off"):
            print("recorder: control surface disabled (CONTROL_ENABLED)")
            return
        try:
            import control
        except Exception as e:
            print(f"recorder: control surface unavailable ({e!r})")
            return
        loop = asyncio.get_running_loop()
        port = int(os.environ.get("CONTROL_PORT", "8776"))
        token = os.environ.get("CONTROL_TOKEN") or None

        async def _control_close():
            # single-owner: close the one open session, whichever guild
            open_guilds = list(sessions)
            if not open_guilds:
                return {"ok": False, "error": "no open recording session"}
            return await close_session(bot, open_guilds[0])

        try:
            srv = control.start_control_server(
                loop,
                open_session=lambda gid, ch: open_session(bot, gid, ch),
                close_session=_control_close,
                status=lambda: session_status(),
                resolve_target=lambda: resolve_target(bot),
                port=port, token=token)
            bot._control_server = srv
            print(f"recorder: control surface on "
                  f"http://127.0.0.1:{port} "
                  f"(token {'set' if token else 'off'})")
        except Exception as e:
            print(f"recorder: control surface not started ({e!r})")

    class Capability:
        async def ready(self):
            # per-guild sync: global command propagation can take up
            # to an hour; a session bot needs /record NOW
            try:
                await bot.sync_commands(
                    guild_ids=[g.id for g in bot.guilds])
            except Exception as e:
                print(f"recorder: guild sync failed ({e!r}); "
                      f"global commands will appear eventually")
            print(f"recorder ready: /record in "
                  f"{len(bot.guilds)} guild(s)")
            _start_control_surface()
            # temporary spike scaffolding: unattended DAVE receive check
            ch = os.environ.get("DAVE_SELFTEST_CHANNEL")
            if ch:
                outdir = RECORD_ROOT / "selftest"
                outdir.mkdir(parents=True, exist_ok=True)
                asyncio.create_task(dave_recv.selftest(
                    bot, int(ch), sink=ConsentSink(outdir)))

    return Capability()
