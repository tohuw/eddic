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

# reminder keys, each fired at most once per event (persisted)
CREATED, AT_RISK, IMMINENT, ENDED = (
    "created", "at_risk", "imminent", "ended")

REMINDERS = {
    CREATED:  "{ping}A session is on the calendar: **{title}**, {when}. "
              "React *interested* on the event so we can call quorum.",
    AT_RISK:  "Heads up{dm_mention} — **{title}** is {hours}h out and "
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
    sample = dict(ping="", title="x", when="w", hours=1, count=0,
                  quorum=3, dm_mention="", recorder_line="")
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


def render(key, *, title, when="", start=None, now=None, count=0,
           quorum=0, dm_mention="", recorder=True, ping="",
           templates=None):
    hours = int(round((start - now) / 3600.0)) if start and now else 0
    recorder_line = ("Bring the recorder into the voice channel. "
                     if recorder else "")
    return (templates or REMINDERS)[key].format(
        title=title, when=when, hours=hours, count=count, quorum=quorum,
        dm_mention=dm_mention, recorder_line=recorder_line, ping=ping)


def load_state(path):
    p = Path(path)
    if not p.is_file():
        return {"events": {}, "announced": []}
    d = json.loads(p.read_text(encoding="utf-8"))
    d.setdefault("events", {})
    d.setdefault("announced", [])
    return d


def save_state(path, state):
    Path(path).write_text(
        json.dumps({"events": state["events"],
                    "announced": sorted(state["announced"])}, indent=1),
        encoding="utf-8")


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
    QUORUM = int(os.environ.get("SESSION_QUORUM", "3"))
    OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
    # require the DM only when we can actually recognize them; without
    # OWNER_ID set, quorum could never be met
    REQUIRE_DM = os.environ.get("REQUIRE_DM", "1") != "0" and OWNER_ID != 0
    RECAP_THREAD = int(os.environ.get("RECAP_THREAD_ID", "0"))
    ANNOUNCE_CHANNEL = int(os.environ.get("ANNOUNCE_CHANNEL_ID", "0"))
    PLAYER_ROLE = os.environ.get("PLAYER_ROLE", "")
    RECORDER = os.environ.get("RECORDER_NUDGE", "1") != "0"
    SESSION_ROLE = os.environ.get("SESSION_ROLE_ID", "")
    MESSAGES = load_messages(
        HERE / os.environ.get("CONVENE_MESSAGES",
                              "convene_messages.json"))
    SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
    TICK = int(os.environ.get("REFRESH_MINUTES", "5")) * 60

    tree = app_commands.CommandTree(client)
    state = load_state(STATE_FILE)

    async def _channel(cid):
        if not cid:
            return None
        return client.get_channel(cid) or await client.fetch_channel(cid)

    async def reminder_channel():
        # momentary nudges (rally, go-ahead, wrap) — the busy channel
        return await _channel(ANNOUNCE_CHANNEL or RECAP_THREAD)

    async def recap_channel():
        # permanent recap announcements — the recap thread/channel
        return await _channel(RECAP_THREAD or ANNOUNCE_CHANNEL)

    async def count_interested(event):
        players, dm_in = 0, False
        users = (event.users() if hasattr(event, "users")
                 else event.fetch_users())
        async for u in users:
            if OWNER_ID and u.id == OWNER_ID:
                dm_in = True
                continue                    # the DM is not a player
            member = event.guild.get_member(u.id)
            if not PLAYER_ROLE:
                players += 1
            elif member and any(r.name == PLAYER_ROLE
                                for r in member.roles):
                players += 1
        return players, dm_in

    def status_name(event):
        # read the status by name — the enum's attribute name differs
        # across libraries (discord.py EventStatus vs py-cord
        # ScheduledEventStatus); its members are the same words
        raw = getattr(event.status, "name", str(event.status))
        return "canceled" if raw == "cancelled" else raw

    async def tick():
        now = time.time()
        try:
            chan = await reminder_channel()
            live_ids = set()
            for guild in client.guilds:
                for event in await guild.fetch_scheduled_events():
                    eid = str(event.id)
                    live_ids.add(eid)
                    rec = state["events"].setdefault(eid, {"fired": []})
                    count, dm_in = await count_interested(event)
                    session = {"start": event.start_time.timestamp(),
                               "count": count, "dm_in": dm_in,
                               "status": status_name(event),
                               "fired": rec["fired"]}
                    ping = (f"<@&{SESSION_ROLE}> " if SESSION_ROLE
                            else "")
                    for key in evaluate(session, now, QUORUM,
                                        require_dm=REQUIRE_DM):
                        if chan:
                            await chan.send(allowed_mentions=discord.
                                AllowedMentions(roles=True, users=True),
                                content=render(
                                key, title=event.name, ping=ping,
                                when=discord.utils.format_dt(
                                    event.start_time, "F"),
                                start=session["start"], now=now,
                                count=count, quorum=QUORUM,
                                dm_mention=(f" <@{OWNER_ID}>"
                                            if OWNER_ID else ""),
                                recorder=RECORDER,
                                templates=MESSAGES))
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

    @grp.command(name="quorum",
                 description="How many are needed for a session to run")
    async def quorum_cmd(inter, players: int):
        nonlocal QUORUM
        if OWNER_ID and inter.user.id != OWNER_ID:
            await inter.response.send_message("DM only.", ephemeral=True)
            return
        QUORUM = players
        await inter.response.send_message(f"Quorum set to {players}.",
                                          ephemeral=True)

    @grp.command(name="status", description="Sessions and who is in")
    async def status_cmd(inter):
        # defer first: fetching events and attendees can exceed the
        # 3-second interaction deadline ("app did not respond")
        await inter.response.defer(ephemeral=True)
        lines = []
        for guild in client.guilds:
            for event in await guild.fetch_scheduled_events():
                count, dm_in = await count_interested(event)
                lines.append(
                    f"**{event.name}** — {count}/{QUORUM} in"
                    f"{' (DM in)' if dm_in else ''}")
        await inter.followup.send(
            "\n".join(lines) or "no sessions on the calendar.",
            ephemeral=True)

    tree.add_command(grp)

    async def announce_new_recaps(corpus):
        """Called by bot.py after a freshness reload."""
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
            # snapshot existing recaps as already-announced, so a
            # restart never re-announces the back catalogue
            for p in botlib.page_paths(corpus):
                if "sessions/" in p and p not in state["announced"]:
                    state["announced"].append(p)
            live_ids = set()
            for guild in client.guilds:
                # copy the (global) commands into the guild first, or
                # the guild sync registers an empty set and nothing
                # appears until global propagation (up to an hour)
                tree.copy_global_to(guild=guild)
                await tree.sync(guild=guild)
                for event in await guild.fetch_scheduled_events():
                    live_ids.add(str(event.id))
            state["events"] = reconcile(state, live_ids)
            save_state(STATE_FILE, state)
            client.loop.create_task(tick_loop())
            print(f"convene ready: quorum {QUORUM}, "
                  f"{len(state['announced'])} recap(s) known")

        async def on_corpus_refresh(self, corpus):
            await announce_new_recaps(corpus)

    return Capability()
