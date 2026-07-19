"""eddic recorder — session recording as a capability of the campaign
bot (py-cord edition: py-cord's voice receive speaks Discord's DAVE
E2EE, which broke every non-DAVE receive path in March 2026).

Consent is structural: a member's audio is captured only after they
react to the session's consent post. No react, no capture — enforced
in the sink, not by policy. Audio is written on the voice thread,
never the event loop.

Config (env / variables.txt): RECORD_DIR (default ../sessions/raw),
PRIVACY_URL (default the Eddic site's posture page), WIKI_LOG
(default ../wiki/log.md).
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
        if ctx.guild_id in sessions:
            await ctx.respond("A recording session is already open "
                              "here.", ephemeral=True)
            return
        # one directory per session, named by its start — never by
        # date alone: a session crosses midnight, two sessions share a
        # date, and a crash-and-restart must never reuse a directory
        # and squash the tracks already in it
        outdir = (RECORD_ROOT
                  / datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
        outdir.mkdir(parents=True, exist_ok=True)
        vc = await voice.channel.connect()
        for _ in range(50):                 # the voice handshake can
            if vc.is_connected():           # lag behind connect()'s
                break                       # return; recording needs
            await asyncio.sleep(0.2)        # the real connection
        else:
            await vc.disconnect(force=True)
            await ctx.respond("Voice connection never came up; "
                              "try again.", ephemeral=True)
            return
        sink = ConsentSink(outdir)

        def finished(exc):
            # py-cord 2.8's AudioReader calls after(error) on its own
            # thread when recording stops
            if exc is not None:
                print(f"recorder: reader stopped with error: {exc!r}")
            sink.close_all()

        msg = await voice.channel.send(consent_text(set()))
        await msg.add_reaction(EMOJI)
        sessions[ctx.guild_id] = {"vc": vc, "sink": sink, "msg": msg,
                                  "outdir": outdir, "names": set(),
                                  "status_set": False}
        vc.start_recording(sink, finished)
        # transparency: an audible chime in-channel, and (unless
        # declined) a visible status on the channel itself
        try:
            vc.play(discord.PCMAudio(io.BytesIO(chime_pcm())))
        except Exception as e:
            print(f"recorder: start chime failed ({e!r})")
        if channel_status:
            await set_channel_status(
                bot, voice.channel.id,
                f"{EMOJI} Recording — react to the consent post")
            sessions[ctx.guild_id]["status_set"] = True
        await ctx.respond(
            f"Recording session open — [the consent post]"
            f"({msg.jump_url}) is up in the channel's text chat. "
            f"Nobody's mic is captured until they react.", ephemeral=True)

    @record.command(name="stop",
                    description="Close the recording session and "
                                "stage the tracks")
    async def stop(ctx: discord.ApplicationContext):
        _age = (discord.utils.utcnow()
                - ctx.interaction.created_at).total_seconds()
        print(f'/stop: interaction age at entry: {_age:.2f}s')
        s = sessions.get(ctx.guild_id)
        if not s:
            await ctx.respond("No open recording session.",
                              ephemeral=True)
            return
        await ctx.defer()
        sessions.pop(ctx.guild_id, None)
        s["vc"].stop_recording()
        if s.get("status_set"):
            await set_channel_status(bot, s["vc"].channel.id, "")
        await s["vc"].disconnect()
        s["sink"].close_all()
        files = sorted(s["outdir"].glob("*.wav"))
        lines = [f"- {f.name} ({f.stat().st_size // 1024} KB)"
                 for f in files]
        try:
            day = datetime.date.today().isoformat()
            with WIKI_LOG.open("a", encoding="utf-8") as lf:
                lf.write(f"\n## [{day}] witness | session audio recorded "
                         f"({len(files)} track(s))\n\nStaged under "
                         f"sessions/raw/{s['outdir'].name}/ by the "
                         f"recorder; transcription is a deliberate "
                         f"maintenance step.\n")
        except OSError as e:
            lines.append(f"(log entry failed: {e})")
        await s["msg"].edit(content=consent_text(s["names"]) +
                            "\n**Recording ended.**")
        stats = s["sink"].stats
        print(f"recorder stats: {stats}")
        report = "\n".join(lines) or (
            f"no consented audio captured (packets — "
            f"written: {stats['written']}, "
            f"unconsented: {stats['unconsented']})")
        await ctx.respond(
            f"Recording closed. Staged in `{s['outdir']}`:\n{report}")

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
            # temporary spike scaffolding: unattended DAVE receive check
            ch = os.environ.get("DAVE_SELFTEST_CHANNEL")
            if ch:
                outdir = RECORD_ROOT / "selftest"
                outdir.mkdir(parents=True, exist_ok=True)
                asyncio.create_task(dave_recv.selftest(
                    bot, int(ch), sink=ConsentSink(outdir)))

    return Capability()
