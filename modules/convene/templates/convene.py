"""convene — session lifecycle as a capability of the campaign lore
bot. Loaded by bot.py when present (like the recorder capability):
`import convene; capability = convene.setup(client)`.

Convene DRIVES Discord's native Guild Scheduled Events — it never
rebuilds the event card, RSVP, or countdown. On top of the native
event it adds the three things Discord and generic scheduling bots
cannot: quorum (a session happens iff the DM plus N players are in),
lifecycle nudges (bring the recorder; stage and transcribe after),
and recap announcement (a new sessions/ page in the projection the
bot already polls becomes an announcement in the table's channel).

Design: convene owns no gateway event handlers. On each poll tick it
recounts attendees from Discord and evaluates a pure state machine —
so quorum changes are caught within one cycle, restarts lose nothing,
and the bare-Client single-handler limit never bites. Session quorum
does not need sub-minute reaction.

The pure core (evaluate, render, persistence, reconcile) imports
without discord and is what the module verifies.
"""

import json
import os
from pathlib import Path


def envint(key, default=0):
    """Int from an env var, tolerant of a trailing inline comment
    or stray whitespace — config files are edited by humans."""
    raw = os.environ.get(key)
    if raw is None:
        return int(default)
    raw = raw.split("#", 1)[0].strip()
    return int(raw) if raw else int(default)

# reminder keys, each fired at most once per event (persisted)
CREATED, AT_RISK, IMMINENT, ENDED = (
    "created", "at_risk", "imminent", "ended")

REMINDERS = {
    CREATED:  "{ping}A session is on the calendar: **{title}**, {when}. "
              "React *interested* on the event so we can call quorum.",
    AT_RISK:  "Heads up{dm_mention} — **{title}** is {when_rel} and "
              "only {count} of {quorum} are in. Rally the table, or "
              "pick a new night while there's time.",
    IMMINENT: "{ping}**{title}** is on tonight — quorum met ({count}/"
              "{quorum}). {recorder_line}See you at the table.",
    ENDED:    "That's a wrap on **{title}**. When you get a moment: "
              "stage the recording and transcribe it, and the recap "
              "will announce itself once it's published.",
}

AT_RISK_WINDOW_H = 36     # flag the DM this many hours out if short
IMMINENT_WINDOW_H = 2     # the go/no-go nudge


def evaluate(session, now, quorum, require_dm=True,
             at_risk_h=AT_RISK_WINDOW_H, imminent_h=IMMINENT_WINDOW_H):
    """The reminder keys due now and not yet fired, for one tracked
    session. Pure — no clock, no Discord.

    session: {start: epoch, count: int, dm_in: bool,
              status: scheduled|active|completed|canceled,
              fired: iterable[str]}
    """
    fired = set(session.get("fired", ()))
    status = session.get("status", "scheduled")
    hours_out = (session["start"] - now) / 3600.0
    met = session["count"] >= quorum and (
        session.get("dm_in", True) or not require_dm)

    due = []
    if CREATED not in fired:
        due.append(CREATED)
    if status == "completed":
        return due + ([ENDED] if ENDED not in fired else [])
    if status in ("canceled", "active"):
        return due                      # nothing new once it's off the
                                        # scheduling board (but active
                                        # sessions still end later)
    if 0 < hours_out <= at_risk_h and not met and AT_RISK not in fired:
        due.append(AT_RISK)
    if 0 < hours_out <= imminent_h and met and IMMINENT not in fired:
        due.append(IMMINENT)
    return due


def load_messages(path, defaults=None):
    """Reminder templates, with a campaign's JSON override merged over
    the defaults — the seam for re-voicing and translation. A bad
    template (unknown placeholder) is rejected and the default kept,
    so a broken translation can never crash a reminder."""
    msgs = dict(defaults or REMINDERS)
    p = Path(path)
    if not p.is_file():
        return msgs
    sample = dict(ping="", title="x", when="w", when_rel="w", hours=1,
                  count=0, quorum=3, dm_mention="", recorder_line="")
    try:
        override = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return msgs
    for k, v in override.items():
        if k in msgs and isinstance(v, str):
            try:
                v.format(**sample)
                msgs[k] = v
            except (KeyError, IndexError, ValueError):
                pass                        # keep the default
    return msgs


def effective_status(raw, start, now, end=None, duration_s=4 * 3600):
    """Discord's status, with a time-based 'ended' fallback: an event
    that is past its end (or start + a default duration when it has no
    explicit end) counts as completed even if the DM never marked it —
    external events do not auto-complete, and the stage/transcribe
    nudge must still fire. Pure."""
    if raw in ("completed", "canceled"):
        return raw
    horizon = end if end else start + duration_s
    return "completed" if now > horizon else raw


def render(key, *, title, when="", when_rel="", start=None, now=None,
           count=0, quorum=0, dm_mention="", recorder=True, ping="",
           templates=None):
    hours = int(round((start - now) / 3600.0)) if start and now else 0
    recorder_line = ("Bring the recorder into the voice channel. "
                     if recorder else "")
    return (templates or REMINDERS)[key].format(
        title=title, when=when, when_rel=when_rel, hours=hours,
        count=count, quorum=quorum, dm_mention=dm_mention,
        recorder_line=recorder_line, ping=ping)


def load_state(path):
    p = Path(path)
    if not p.is_file():
        return {"events": {}, "announced": []}
    d = json.loads(p.read_text(encoding="utf-8"))
    d.setdefault("events", {})
    d.setdefault("announced", [])
    return d


def save_state(path, state):
    out = {"events": state["events"],
           "announced": sorted(state["announced"])}
    if state.get("settings"):
        out["settings"] = state["settings"]     # slash-set config
    Path(path).write_text(json.dumps(out, indent=1), encoding="utf-8")


def reconcile(state, live_event_ids):
    """Keep bookkeeping only for events Discord still has."""
    return {eid: rec for eid, rec in state["events"].items()
            if eid in live_event_ids}


# ---- discord wiring (only touched at runtime) ----------------------
def setup(client):
    import asyncio
    import time
    import discord
    from discord import app_commands
    import botlib

    HERE = Path(__file__).resolve().parent
    STATE_FILE = HERE / os.environ.get("CONVENE_STATE",
                                       "convene_state.json")
    OWNER_ID = envint("OWNER_ID")                     # maintainer
    RECORDER = os.environ.get("RECORDER_NUDGE", "1") != "0"
    SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
    TICK = envint("REFRESH_MINUTES", 5) * 60
    DURATION_S = envint("SESSION_DURATION_HOURS", 4) * 3600
    MESSAGES = load_messages(
        HERE / os.environ.get("CONVENE_MESSAGES", "convene_messages.json"))

    tree = app_commands.CommandTree(client)
    state = load_state(STATE_FILE)

    # Config is an env baseline overlaid with slash-set settings. Env is
    # the durable floor (survives a Railway redeploy that wipes the
    # state file); the slash setters persist to the state file and win
    # while it lives. The DM is ALWAYS explicit config here — never
    # inferred from who created an event.
    defaults = {
        "dm_id": envint("DM_ID", OWNER_ID),
        "quorum": envint("SESSION_QUORUM", 3),
        "require_dm": os.environ.get("REQUIRE_DM", "1") != "0",
        "player_role": os.environ.get("PLAYER_ROLE", ""),
        "role_id": envint("SESSION_ROLE_ID"),
        "announce_channel_id": envint("ANNOUNCE_CHANNEL_ID"),
        "recap_thread_id": envint("RECAP_THREAD_ID"),
    }
    cfg = {**defaults, **state.get("settings", {})}

    def save():
        state["settings"] = cfg
        save_state(STATE_FILE, state)

    def may_configure(user_id):
        allowed = {i for i in (OWNER_ID, cfg["dm_id"]) if i}
        return not allowed or user_id in allowed

    async def _channel(cid):
        if not cid:
            return None
        return client.get_channel(cid) or await client.fetch_channel(cid)

    async def reminder_channel():
        return await _channel(cfg["announce_channel_id"]
                              or cfg["recap_thread_id"])

    async def recap_channel():
        return await _channel(cfg["recap_thread_id"]
                              or cfg["announce_channel_id"])

    async def count_interested(event):
        players, dm_in = 0, False
        users = (event.users() if hasattr(event, "users")
                 else event.fetch_users())
        async for u in users:
            if cfg["dm_id"] and u.id == cfg["dm_id"]:
                dm_in = True
                continue                    # the DM is not a player
            member = event.guild.get_member(u.id)
            # who counts as a player: an explicit PLAYER_ROLE name, else
            # the ping role (the one role you already set doubles as the
            # roster — a stray "interested" click from a non-player is
            # ignored), else anyone. This is also the seam for a shared
            # server: a campaign's role scopes its own quorum.
            if cfg["player_role"]:
                if member and any(r.name == cfg["player_role"]
                                  for r in member.roles):
                    players += 1
            elif cfg["role_id"]:
                if member and any(r.id == cfg["role_id"]
                                  for r in member.roles):
                    players += 1
            else:
                players += 1
        return players, dm_in

    def status_name(event):
        # read the status by name — the enum's attribute differs across
        # libraries (discord.py EventStatus vs py-cord ScheduledEventStatus)
        raw = getattr(event.status, "name", str(event.status))
        return "canceled" if raw == "cancelled" else raw

    async def tick():
        now = time.time()
        try:
            chan = await reminder_channel()
            require_dm = cfg["require_dm"] and cfg["dm_id"] != 0
            live_ids = set()
            for guild in client.guilds:
                for event in await guild.fetch_scheduled_events():
                    eid = str(event.id)
                    live_ids.add(eid)
                    rec = state["events"].setdefault(eid, {"fired": []})
                    count, dm_in = await count_interested(event)
                    start = event.start_time.timestamp()
                    end = (event.end_time.timestamp()
                           if getattr(event, "end_time", None) else None)
                    session = {"start": start,
                               "count": count, "dm_in": dm_in,
                               "status": effective_status(
                                   status_name(event), start, now,
                                   end=end, duration_s=DURATION_S),
                               "fired": rec["fired"]}
                    ping = (f"<@&{cfg['role_id']}> " if cfg["role_id"]
                            else "")
                    for key in evaluate(session, now, cfg["quorum"],
                                        require_dm=require_dm):
                        if chan:
                            await chan.send(
                                allowed_mentions=discord.AllowedMentions(
                                    roles=True, users=True),
                                content=render(
                                    key, title=event.name, ping=ping,
                                    when=discord.utils.format_dt(
                                        event.start_time, "F"),
                                    when_rel=discord.utils.format_dt(
                                        event.start_time, "R"),
                                    start=session["start"], now=now,
                                    count=count, quorum=cfg["quorum"],
                                    dm_mention=(f" <@{cfg['dm_id']}>"
                                                if cfg["dm_id"] else ""),
                                    recorder=RECORDER, templates=MESSAGES))
                        rec["fired"].append(key)
            state["events"] = reconcile(state, live_ids)
            save_state(STATE_FILE, state)
        except Exception as e:                      # a tick must survive
            print(f"convene tick error: {e}")

    async def tick_loop():
        while True:
            await asyncio.sleep(TICK)
            await tick()

    grp = app_commands.Group(name="session",
                             description="Session scheduling (DM)")

    async def _gate(inter):
        if may_configure(inter.user.id):
            return True
        await inter.response.send_message("The DM runs this one.",
                                          ephemeral=True)
        return False

    @grp.command(name="dm", description="Set who counts as the DM for "
                 "quorum (explicit — never guessed)")
    async def dm_cmd(inter, member: discord.Member):
        if not await _gate(inter):
            return
        cfg["dm_id"] = member.id
        save()
        await inter.response.send_message(
            f"DM set to {member.mention}.", ephemeral=True)

    @grp.command(name="quorum",
                 description="Players needed (besides the DM)")
    async def quorum_cmd(inter, players: int):
        if not await _gate(inter):
            return
        cfg["quorum"] = players
        save()
        await inter.response.send_message(
            f"Quorum set to {players} player(s) plus the DM.",
            ephemeral=True)

    @grp.command(name="role", description="Role to ping about sessions")
    async def role_cmd(inter, role: discord.Role):
        if not await _gate(inter):
            return
        cfg["role_id"] = role.id
        save()
        await inter.response.send_message(
            f"Sessions will ping {role.mention}.", ephemeral=True)

    @grp.command(name="channel",
                 description="Channel for session reminders")
    async def channel_cmd(inter, channel: discord.TextChannel):
        if not await _gate(inter):
            return
        cfg["announce_channel_id"] = channel.id
        save()
        await inter.response.send_message(
            f"Reminders will post in {channel.mention}.", ephemeral=True)

    @grp.command(name="recap-channel",
                 description="Channel/thread for recap announcements")
    async def recap_cmd(inter, channel: discord.TextChannel):
        if not await _gate(inter):
            return
        cfg["recap_thread_id"] = channel.id
        save()
        await inter.response.send_message(
            f"Recaps will announce in {channel.mention}.", ephemeral=True)

    @grp.command(name="status", description="Sessions, quorum, and config")
    async def status_cmd(inter, debug: bool = False):
        await inter.response.defer(ephemeral=True)
        dm = f"<@{cfg['dm_id']}>" if cfg["dm_id"] else "unset"
        role = f"<@&{cfg['role_id']}>" if cfg["role_id"] else "none"
        lines = [f"DM: {dm} · quorum: {cfg['quorum']} player(s)"
                 f"{' + DM required' if cfg['require_dm'] else ''}"
                 f" · ping: {role}"]
        for guild in client.guilds:
            for event in await guild.fetch_scheduled_events():
                count, dm_in = await count_interested(event)
                lines.append(
                    f"**{event.name}** — {count}/{cfg['quorum']} in"
                    f"{' (DM in)' if dm_in else ''}")
                if debug:
                    users = (event.users() if hasattr(event, "users")
                             else event.fetch_users())
                    ids = [f"{u.id} ({u.display_name})"
                           async for u in users]
                    lines.append(
                        f"  DM_ID `{cfg['dm_id']}`; interested: "
                        f"{', '.join(ids) or 'none'}; "
                        f"you `{inter.user.id}`")
        await inter.followup.send("\n".join(lines), ephemeral=True)

    tree.add_command(grp)

    async def announce_new_recaps(corpus):
        new = botlib.new_session_pages(corpus, set(state["announced"]))
        if not new:
            return
        chan = await recap_channel()
        for path in new:
            title = botlib.page_title(corpus, path)
            url = (f"{SITE_URL}/{path.removesuffix('.md')}"
                   if SITE_URL else "")
            if chan:
                await chan.send(f"📖 New recap published: **{title}**"
                                + (f"\n{url}" if url else ""))
            state["announced"].append(path)
        save_state(STATE_FILE, state)

    class Capability:
        async def ready(self, corpus=""):
            for p in botlib.page_paths(corpus):
                if "sessions/" in p and p not in state["announced"]:
                    state["announced"].append(p)
            now = time.time()
            require_dm = cfg["require_dm"] and cfg["dm_id"] != 0
            live_ids = set()
            for guild in client.guilds:
                # copy globals into the guild first, or the guild sync
                # registers an empty set and nothing appears
                tree.copy_global_to(guild=guild)
                await tree.sync(guild=guild)
                for event in await guild.fetch_scheduled_events():
                    eid = str(event.id)
                    live_ids.add(eid)
                    rec = state["events"].setdefault(eid, {"fired": []})
                    # startup catch-up: mark everything currently due as
                    # already handled WITHOUT sending, so a restart
                    # (Railway wipes the state file) never re-announces
                    # an event. Only transitions after startup post.
                    count, dm_in = await count_interested(event)
                    start = event.start_time.timestamp()
                    end = (event.end_time.timestamp()
                           if getattr(event, "end_time", None) else None)
                    session = {"start": start,
                               "count": count, "dm_in": dm_in,
                               "status": effective_status(
                                   status_name(event), start, now,
                                   end=end, duration_s=DURATION_S),
                               "fired": rec["fired"]}
                    for key in evaluate(session, now, cfg["quorum"],
                                        require_dm=require_dm):
                        if key not in rec["fired"]:
                            rec["fired"].append(key)
            state["events"] = reconcile(state, live_ids)
            save_state(STATE_FILE, state)
            client.loop.create_task(tick_loop())
            print(f"convene ready: DM {cfg['dm_id']}, quorum "
                  f"{cfg['quorum']}, {len(state['announced'])} recap(s)")

        async def on_corpus_refresh(self, corpus):
            await announce_new_recaps(corpus)

    return Capability()
