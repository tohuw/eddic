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
import json
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
# Optional: ping a role on the PUBLIC consent post so the whole table is
# notified to react — not just the invoker (who also gets the ephemeral
# ack). The role is normally set from Discord with `/record consent-role`,
# which persists a role id to CONSENT_PING_STATE; the CONSENT_PING_ROLE env
# (id or name) is only a bootstrap/fallback used when no state file exists.
# Either empty disables the ping.
CONSENT_PING_ROLE = os.environ.get("CONSENT_PING_ROLE", "").strip()
CONSENT_PING_STATE = HERE / "consent_ping.json"

# While at least one consented mic is capturing, the bot wears this suffix
# on its own guild nickname so anyone glancing at the member list sees the
# session is live. Discord caps a nickname at 32 chars; a long base name is
# truncated to fit rather than rejected.
NICK_SUFFIX = " (RECORDING)"
NICK_MAX = 32

# Auto-stop a session whose voice channel has gone empty (no non-bot
# members) for this long. Guards against a session left running after
# everyone has left; runs the same clean stop path as `/record stop`.
EMPTY_DISCONNECT_SECONDS = int(
    os.environ.get("EMPTY_DISCONNECT_SECONDS", "60"))

sessions = {}  # guild_id -> dict(vc, sink, msg, outdir, names)


def is_consent_emoji(emoji):
    return str(emoji).replace("️", "") == EMOJI.replace("️", "")


def apply_recording_suffix(base, suffix=NICK_SUFFIX, limit=NICK_MAX):
    """Return the recording nickname: `base` with `suffix` appended, never
    exceeding `limit` characters. If base + suffix would overflow, the base
    is truncated (the suffix is preserved whole, since it carries the
    signal). Idempotent: a base that already ends with the suffix is
    returned unchanged. Pure — no Discord, safe to unit-test."""
    base = base or ""
    if base.endswith(suffix):
        return base[:limit]
    room = limit - len(suffix)
    if room <= 0:
        # Suffix alone meets or exceeds the limit; nothing else fits.
        return suffix[:limit]
    return base[:room] + suffix


def strip_recording_suffix(nick, suffix=NICK_SUFFIX):
    """Remove exactly one trailing `suffix` from `nick` if present, else
    return it unchanged. Idempotent. Pure. This is the fallback when the
    stored base nickname is unavailable; the primary restore path replays
    the exact base captured when the suffix was first applied."""
    if nick and nick.endswith(suffix):
        return nick[:-len(suffix)]
    return nick


def channel_is_empty(members):
    """True when a voice channel holds no non-bot members. `members` is an
    iterable of objects with a `.bot` attribute (Discord Members). Pure —
    this is the whole arm/cancel decision for the empty-channel timer:
    empty ⇒ arm the disconnect timer, non-empty ⇒ cancel it."""
    return not any(not getattr(m, "bot", False) for m in members)


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


async def set_recording_nick(guild, s):
    """Append the recording suffix to the bot's own guild nickname, once
    per session. Stores the exact base nick on the session for a faithful
    restore. Best-effort: a nick edit that fails (no Change Nickname
    permission, etc.) is logged and swallowed — it must never break
    recording."""
    if guild is None or s.get("nick_set"):
        return
    me = getattr(guild, "me", None)
    if me is None:
        return
    base_nick = getattr(me, "nick", None)  # None when no guild nick is set
    base_display = base_nick if base_nick else getattr(me, "name", "")
    s["base_nick"] = base_nick
    try:
        await me.edit(nick=apply_recording_suffix(base_display))
        s["nick_set"] = True
    except Exception as e:
        print(f"recorder: could not set recording nickname ({e!r}); "
              f"recording proceeds unaffected")


async def clear_recording_nick(guild, s):
    """Restore the bot's nickname to the base captured when the suffix was
    applied (None resets to the username). Falls back to stripping the exact
    suffix if no base was stored. Best-effort, same as setting it."""
    if guild is None or not s.get("nick_set"):
        return
    me = getattr(guild, "me", None)
    if me is None:
        return
    if "base_nick" in s:
        target = s["base_nick"]
    else:
        target = strip_recording_suffix(getattr(me, "nick", None)) or None
    try:
        await me.edit(nick=target)
        s["nick_set"] = False
    except Exception as e:
        print(f"recorder: could not clear recording nickname ({e!r})")


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


def _stored_ping_role_id():
    """The role id set from Discord via `/record consent-role`, or None.
    This state file wins over the CONSENT_PING_ROLE env when present."""
    try:
        data = json.loads(CONSENT_PING_STATE.read_text(encoding="utf-8"))
        rid = data.get("role_id")
        return int(rid) if rid is not None else None
    except (OSError, ValueError, TypeError):
        return None


def resolve_ping(guild):
    """The consent-ping role's mention, or ''. The slash-set role id (state
    file) wins; the CONSENT_PING_ROLE env (id or name) is the fallback used
    only when no state file is present."""
    if guild is None:
        return ""
    stored = _stored_ping_role_id()
    if stored is not None:
        role = guild.get_role(stored)
        return role.mention if role else ""
    if not CONSENT_PING_ROLE:
        return ""
    role = (guild.get_role(int(CONSENT_PING_ROLE))
            if CONSENT_PING_ROLE.isdigit()
            else discord.utils.get(guild.roles, name=CONSENT_PING_ROLE))
    return role.mention if role else ""


def consent_text(names, ping=""):
    roster = ", ".join(sorted(names)) if names else "nobody yet"
    head = f"{ping}\n" if ping else ""
    return (head + f"{EMOJI} **Recording session open.** This voice channel is "
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
    ping = resolve_ping(channel.guild)
    try:
        msg = await channel.send(
            consent_text(set(), ping=ping),
            allowed_mentions=discord.AllowedMentions(
                everyone=False, users=False, roles=True))
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
                          "status_set": False, "ping": ping,
                          "nick_set": False, "empty_task": None}
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
    # Cancel any armed empty-channel timer so it can't fire after teardown.
    empty_task = s.pop("empty_task", None)
    if empty_task is not None:
        empty_task.cancel()
    s["vc"].stop_recording()
    if s.get("status_set"):
        await set_channel_status(bot, s["vc"].channel.id, "")
    # Drop the recording suffix from the bot's nickname (best-effort).
    await clear_recording_nick(bot.get_guild(guild_id), s)
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
    await s["msg"].edit(content=consent_text(s["names"], ping=s.get("ping", "")) +
                        "\n**Recording ended.**")
    stats = dict(s["sink"].stats)
    print(f"recorder stats: {stats}")
    result = {"ok": True, "outdir": str(s["outdir"]), "tracks": tracks,
              "stats": stats, "consented": sorted(s["names"])}
    if log_error:
        result["log_error"] = log_error
    return result


def _evaluate_empty_channel(bot, guild_id, s, ch):
    """Arm or cancel the empty-channel disconnect timer for a session,
    from the channel's current membership. Idempotent: an already-armed
    timer is left running while the channel stays empty, and a running
    timer is cancelled the moment a non-bot member is present."""
    if channel_is_empty(getattr(ch, "members", [])):
        if s.get("empty_task") is None:
            s["empty_task"] = asyncio.ensure_future(
                _empty_channel_disconnect(bot, guild_id))
    else:
        task = s.pop("empty_task", None)
        if task is not None:
            task.cancel()


async def _empty_channel_disconnect(bot, guild_id):
    """After the channel has been empty for EMPTY_DISCONNECT_SECONDS, run
    the same clean stop path as `/record stop` and post a brief note.
    Races are guarded: a cancel during the wait aborts, and a session that
    closed or re-populated in the meantime is left alone."""
    try:
        await asyncio.sleep(EMPTY_DISCONNECT_SECONDS)
    except asyncio.CancelledError:
        return
    s = sessions.get(guild_id)
    if not s:
        return
    ch = getattr(s["vc"], "channel", None)
    # Re-check: someone may have rejoined in the final instant.
    if ch is not None and not channel_is_empty(getattr(ch, "members", [])):
        s.pop("empty_task", None)
        return
    # Clear our own handle first so close_session's cancel is a no-op on us.
    s.pop("empty_task", None)
    result = await close_session(bot, guild_id)
    if result.get("ok") and ch is not None:
        try:
            mins = EMPTY_DISCONNECT_SECONDS // 60
            span = (f"{mins} minute(s)" if mins
                    else f"{EMPTY_DISCONNECT_SECONDS} second(s)")
            await ch.send(
                f"{EMOJI} Recording auto-ended: the voice channel was "
                f"empty for {span}. Tracks are staged.")
        except Exception as e:
            print(f"recorder: auto-end note not posted ({e!r})")
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

    @record.command(
        name="consent-role",
        description="Set the role @-pinged on the consent post so the "
                    "whole table is notified.")
    @discord.option("role", discord.Role, required=False)
    async def consent_role(ctx: discord.ApplicationContext, role=None):
        if not ctx.author.guild_permissions.manage_guild:
            await ctx.respond("You need Manage Server to set this.",
                              ephemeral=True)
            return
        none = discord.AllowedMentions.none()
        if role is None:
            try:
                CONSENT_PING_STATE.unlink()
            except FileNotFoundError:
                pass
            await ctx.respond(
                "Consent-post ping cleared — the consent post will no "
                "longer @-ping a role.",
                ephemeral=True, allowed_mentions=none)
            return
        CONSENT_PING_STATE.write_text(
            json.dumps({"role_id": role.id}), encoding="utf-8")
        await ctx.respond(
            f"Consent-post ping set to {role.name} — it will be @-pinged "
            f"on the consent post so the whole table is notified to react.",
            ephemeral=True, allowed_mentions=none)

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
        # First consented mic in this session ⇒ wear the recording suffix.
        if s["sink"].consented and not s.get("nick_set"):
            guild = getattr(member, "guild", None) \
                or bot.get_guild(payload.guild_id)
            await set_recording_nick(guild, s)
        await s["msg"].edit(content=consent_text(s["names"], ping=s.get("ping", "")))

    @bot.event
    async def on_raw_reaction_remove(payload):
        s = sessions.get(payload.guild_id)
        if not s or payload.message_id != s["msg"].id:
            return
        if not is_consent_emoji(payload.emoji):
            return
        s["sink"].consented.discard(payload.user_id)
        guild = bot.get_guild(payload.guild_id)
        # Last consented mic gone ⇒ drop the recording suffix.
        if not s["sink"].consented and s.get("nick_set"):
            await clear_recording_nick(guild, s)
        member = guild.get_member(payload.user_id) if guild else None
        if member:
            s["names"].discard(member.display_name)
            await s["msg"].edit(content=consent_text(s["names"], ping=s.get("ping", "")))

    @bot.event
    async def on_voice_state_update(member, before, after):
        # Auto-stop a session whose recorded channel has emptied out. A
        # voice-state change that touches a recorded channel re-evaluates
        # that channel: no non-bot members left ⇒ arm a disconnect timer;
        # anyone (re)joins before it fires ⇒ cancel it.
        if getattr(member, "bot", False):
            return
        for guild_id, s in list(sessions.items()):
            ch = getattr(s["vc"], "channel", None)
            if ch is None:
                continue
            if getattr(before, "channel", None) != ch \
                    and getattr(after, "channel", None) != ch:
                continue
            _evaluate_empty_channel(bot, guild_id, s, ch)

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
