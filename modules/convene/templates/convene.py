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
# PREP is not an auto-reminder — the DM triggers it with /session prep;
# it shares the template/override machinery but evaluate() never fires it.
PREP = "prep"
# REVEAL/REVEAL_ITEM are not per-event reminders either: the reveal digest
# fires on the corpus-refresh beat, batching pages newly reaching the
# projection into one "the veil lifts" post. They share the same
# override/translation machinery.
REVEAL, REVEAL_ITEM = "reveal", "reveal_item"
# EVENT is the one neutral heads-up a NON-session scheduled event gets.
# When SESSION_MATCH carves sessions out by name keyword, everything that
# is not a session announces once on first sight and convene then stays
# out — no quorum, no lifecycle, no DM framing. It is event-tracked and
# fired-once like the lifecycle reminders (recurrence is id-keyed), but
# evaluate() emits it only for non-session events.
EVENT = "event"

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
    # {body} is the DM's verbatim ask — the frame is Snorri's, the words
    # between it are the DM's, never rewritten. Overridable/translatable
    # like the rest.
    PREP:     "{ping}A prep note for the table before next session:\n\n"
              "{body}",
    # The reveal digest: a batched, mechanical relay (like PREP) of pages
    # newly visible in the projection. {entries} is the rendered list of
    # REVEAL_ITEM lines, each carrying a page's own title and link, never
    # rewritten. {ping} is available for overrides but off by default so a
    # routine reveal is quiet. Overridable/translatable like the rest.
    REVEAL:      "{ping}The veil lifts — {count} new page(s) in the "
                 "archive:\n{entries}",
    REVEAL_ITEM: "• **{title}**{link}",
    # EVENT: the single neutral heads-up a non-session event gets. It pings
    # the session role like CREATED ({ping}) but carries no quorum, no DM
    # mention, no session framing — convene's entire involvement with a
    # calendar entry that is not a session.
    EVENT:    "{ping}A new event is on the calendar: **{title}**, {when}.",
}

AT_RISK_WINDOW_H = 36     # flag the DM this many hours out if short
IMMINENT_WINDOW_H = 2     # the go/no-go nudge


def evaluate(session, now, quorum, require_dm=True,
             at_risk_h=AT_RISK_WINDOW_H, imminent_h=IMMINENT_WINDOW_H,
             is_session=True):
    """The reminder keys due now and not yet fired, for one tracked
    event. Pure — no clock, no Discord.

    session: {start: epoch, count: int, dm_in: bool,
              status: scheduled|active|completed|canceled,
              fired: iterable[str]}

    is_session: True (default) runs the full quorum lifecycle — the
    backward-compatible path when no session keyword is configured. False
    means the caller classified this as a NON-session calendar entry: it
    gets exactly one neutral EVENT heads-up on first sight (fired-once by
    id) and no quorum, AT_RISK, IMMINENT, or ENDED ever.
    """
    fired = set(session.get("fired", ()))
    if not is_session:
        return [] if EVENT in fired else [EVENT]
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


def is_session_name(name, session_match):
    """Classify a scheduled event by name keyword. Pure. An empty
    session_match ⇒ every event is a session (the backward-compatible
    default). Otherwise an event is a session iff its name contains the
    keyword, case-insensitively — everything else is a non-session that
    gets one neutral heads-up and no lifecycle."""
    return (not session_match
            or session_match.lower() in (name or "").lower())


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
                  count=0, quorum=3, dm_mention="", recorder_line="",
                  body="x", entries="x", link="", url="")
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


def render(key, *, title="", when="", when_rel="", start=None, now=None,
           count=0, quorum=0, dm_mention="", recorder=True, ping="",
           body="", templates=None):
    hours = int(round((start - now) / 3600.0)) if start and now else 0
    recorder_line = ("Bring the recorder into the voice channel. "
                     if recorder else "")
    return (templates or REMINDERS)[key].format(
        title=title, when=when, when_rel=when_rel, hours=hours,
        count=count, quorum=quorum, dm_mention=dm_mention,
        recorder_line=recorder_line, ping=ping, body=body)


def load_state(path):
    p = Path(path)
    if not p.is_file():
        return {"events": {}, "announced": []}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            raise ValueError("state file is not a JSON object")
    except (ValueError, OSError):
        # A corrupt state file (e.g. a crash mid-write) must not wedge the
        # bot at import — load_state runs in setup(), before ready()'s
        # try/except. Fall back to empty state, as load_messages does.
        return {"events": {}, "announced": []}
    d.setdefault("events", {})
    d.setdefault("announced", [])
    return d


def save_state(path, state):
    out = {"events": state["events"],
           "announced": sorted(state["announced"])}
    if state.get("settings"):
        out["settings"] = state["settings"]     # slash-set config
    if state.get("prep"):
        out["prep"] = state["prep"]             # last /session prep ask
    # Atomic write: a crash mid-write would otherwise leave a truncated
    # convene_state.json that load_state hits at the next import — enough
    # to stop the whole bot starting. Write to a temp file, then replace.
    p = Path(path)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(out, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def reconcile(state, live_event_ids):
    """Keep bookkeeping only for events Discord still has."""
    return {eid: rec for eid, rec in state["events"].items()
            if eid in live_event_ids}


def new_projected_pages(corpus, announced):
    """Every content page now in the projection corpus but not yet in the
    `announced` set — the full player-visible delta (session recaps and
    every other newly-revealed page), the broad counterpart to botlib's
    session-only new_session_pages. Reads only the projection the bot
    already polls, so a page surfaces here only once it is already
    player-visible: the reveal announce is leak-proof by construction.
    Pure — the caller owns the announced set and its persistence."""
    import botlib
    return [p for p in botlib.page_paths(corpus)
            if p not in announced
            and p.rsplit("/", 1)[-1] not in botlib.NON_CONTENT]


def respond_args(text, responder="", prep=None):
    """The suggest_page arguments for one private prep response — the
    witness-inbox drop /session respond files on a player's behalf.
    The player's words are the content, verbatim — mechanical relay,
    never rewritten. The rationale ties the response back to the prep
    ask it answers (the ask's timestamp is its id, `prep-<at>`) and
    quotes the ask's first line so the DM's review file reads in
    context without opening the state file. Pure."""
    who = (responder or "").strip() or "a player"
    if prep and prep.get("text"):
        first = prep["text"].strip().splitlines()[0]
        snip = first[:120] + ("…" if len(first) > 120 else "")
        rationale = (f"Private /session respond reply from {who} to "
                     f"prep-{int(prep.get('at', 0))}: “{snip}”")
    else:
        rationale = (f"Private /session respond reply from {who} — no "
                     "prep ask is outstanding.")
    return {"title": f"Prep response — {who}",
            "content": text,
            "rationale": rationale}


def witness_request(base_url, token, tool, arguments):
    """The MCP tools/call request that files one suggestion into the
    retrieval worker's witness inbox: returns (url, body_bytes,
    headers). Header auth keeps the token out of the URL (path-borne
    tokens leak through logs and screenshots); the plain client UA
    matters because a Cloudflare-fronted host with bot controls on
    403s Python-urllib's default. Pure — file_suggestion does the
    network."""
    url = base_url.rstrip("/") + "/mcp"
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": arguments}}
                      ).encode("utf-8")
    headers = {"content-type": "application/json",
               "accept": "application/json",
               "user-agent": "eddic-convene",
               "authorization": f"Bearer {token}"}
    return url, body, headers


def file_suggestion(base_url, token, tool, arguments, timeout=30):
    """Send one witness write; raise on any refusal (worker error,
    isError tool result) so the caller can tell the player their words
    did not land — and hand them back rather than lose them."""
    import urllib.request
    url, body, headers = witness_request(base_url, token, tool, arguments)
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if "error" in payload:
        raise RuntimeError(f"worker error: {payload['error']}")
    result = payload.get("result", {})
    if result.get("isError"):
        raise RuntimeError((result.get("content") or [{}])[0].get(
            "text", "unknown error"))
    return result


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
    # SESSION_MATCH carves sessions out of a shared calendar by name
    # keyword. Unset/empty ⇒ every scheduled event is a session (the
    # original behaviour, unchanged). Set ⇒ an event is a session iff its
    # name contains the keyword, case-insensitively; anything else is a
    # non-session that gets one neutral heads-up and nothing more.
    SESSION_MATCH = os.environ.get("SESSION_MATCH", "")
    # The witness inbox — where /session respond privately files a
    # player's prep answer. WITNESS_URL is the retrieval worker's base
    # URL; WITNESS_TOKEN a tier token (player tier is the right blast
    # radius — any valid tier may suggest, and the DM token belongs on
    # the DM's own devices, never a bot host). Env-only on purpose: a
    # token slash-typed into Discord would live on in client history.
    WITNESS_URL = os.environ.get("WITNESS_URL", "").rstrip("/")
    WITNESS_TOKEN = os.environ.get("WITNESS_TOKEN", "")
    MESSAGES = load_messages(
        HERE / os.environ.get("CONVENE_MESSAGES", "convene_messages.json"))

    def is_session_event(name):
        # Precedence: the persisted slash-set keyword wins, else the
        # SESSION_MATCH env bootstrap, else empty (every event a session).
        return is_session_name(name, cfg["session_match"])

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
        "session_match": SESSION_MATCH,
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
        return await _channel(cfg["announce_channel_id"])

    # Recaps post to the same channel as reminders and events — one
    # auto-events channel, no separate recap configuration.
    async def recap_channel():
        return await _channel(cfg["announce_channel_id"])

    async def count_interested(event):
        players, dm_in = 0, False
        users = (event.users() if hasattr(event, "users")
                 else event.fetch_users())
        async for u in users:
            if cfg["dm_id"] and u.id == cfg["dm_id"]:
                dm_in = True
                continue                    # the DM is not a player
            member = event.guild.get_member(u.id)
            if member is None:
                # a bare Client keeps no member cache (no privileged
                # members intent), so get_member is None for everyone —
                # fetch over REST, or a role-scoped quorum silently counts
                # 0 despite real interested reacts.
                try:
                    member = await event.guild.fetch_member(u.id)
                except Exception:
                    member = None
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
                    for key in evaluate(
                            session, now, cfg["quorum"],
                            require_dm=require_dm,
                            is_session=is_session_event(event.name)):
                        if chan is None:
                            # No announce channel configured yet: leave the
                            # reminder unfired so it re-fires once one is set
                            # — never mark it fired against a dropped send,
                            # or CREATED/AT_RISK/IMMINENT are lost for good.
                            continue
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
                        rec["fired"].append(key)     # only after a send
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

    @grp.command(name="keyword",
                 description="Word a session's title must contain (omit "
                 "to treat every event as a session)")
    async def keyword_cmd(inter, word: str = ""):
        if not await _gate(inter):
            return
        cfg["session_match"] = word.strip()
        save()
        if cfg["session_match"]:
            msg = (f"Events whose title contains **{cfg['session_match']}** "
                   "are now sessions.")
        else:
            msg = "Cleared — every event is treated as a session again."
        await inter.response.send_message(msg, ephemeral=True)

    @grp.command(name="channel",
                 description="Channel for session reminders")
    async def channel_cmd(inter, channel: discord.TextChannel):
        if not await _gate(inter):
            return
        cfg["announce_channel_id"] = channel.id
        save()
        await inter.response.send_message(
            f"Reminders will post in {channel.mention}.", ephemeral=True)

    class PrepModal(discord.ui.Modal, title="Ask the players to prep"):
        # A paragraph field so a long, multi-paragraph ask fits. The DM's
        # text goes out verbatim inside the frame — never rewritten.
        ask = discord.ui.TextInput(
            label="What should the players decide or prepare?",
            style=discord.TextStyle.paragraph,
            placeholder="Goes out to the players in your own words. "
                        "Paste a channel as <#id> to link it.",
            max_length=3800, required=True)

        async def on_submit(self, inter):
            chan = await reminder_channel()
            if not chan:
                await inter.response.send_message(
                    "No channel to post in yet — set one with "
                    "`/session channel` first.", ephemeral=True)
                return
            body = str(self.ask.value)
            ping = f"<@&{cfg['role_id']}> " if cfg["role_id"] else ""
            await chan.send(
                content=render(PREP, ping=ping, body=body,
                               templates=MESSAGES),
                allowed_mentions=discord.AllowedMentions(
                    roles=True, users=True, everyone=False))
            state["prep"] = {"text": body, "at": time.time(),
                             "by": inter.user.id}
            save_state(STATE_FILE, state)
            await inter.response.send_message(
                f"Sent to {chan.mention}.", ephemeral=True)

    @grp.command(name="prep",
                 description="Ask the players to decide/prepare something "
                             "before next session")
    async def prep_cmd(inter):
        if not await _gate(inter):     # _gate only replies when refused,
            return                     # leaving the response free for the
        await inter.response.send_modal(PrepModal())   # modal on success

    class RespondModal(discord.ui.Modal, title="Respond to the prep ask"):
        # One paragraph field mirroring the prep modal. The player's
        # words go to the DM's witness review inbox VERBATIM and
        # nowhere else — never a channel post, never rewritten. Every
        # reply back to the player is ephemeral, so nothing about the
        # response (not even that one was made) reaches the table.
        answer = discord.ui.TextInput(
            label="Your private response",
            style=discord.TextStyle.paragraph,
            placeholder="Goes only to the DM's review queue — "
                        "the table never sees it.",
            max_length=3800, required=True)

        async def on_submit(self, inter):
            # The witness write is a network call: ack the modal inside
            # its 3 s budget, then file off the event loop (blocking
            # urllib on the loop would stall the gateway heartbeat).
            await inter.response.defer(ephemeral=True, thinking=True)
            text = str(self.answer.value)
            args = respond_args(text, responder=inter.user.display_name,
                                prep=state.get("prep"))
            try:
                await asyncio.to_thread(
                    file_suggestion, WITNESS_URL, WITNESS_TOKEN,
                    "suggest_page", args)
            except Exception as e:
                # Never lose the player's words: the miss and their text
                # come back in the same private thread, chunked under
                # Discord's 2000-char message cap.
                await inter.followup.send(
                    "Couldn't reach the DM's review queue "
                    f"({str(e)[:300]}). Your words, so they aren't "
                    "lost — try again later or hand them to the DM "
                    "directly:", ephemeral=True)
                for i in range(0, len(text), 1900):
                    await inter.followup.send(text[i:i + 1900],
                                              ephemeral=True)
                return
            # count-only receipt on the prep record (never the text, so
            # the state file holds no player secrets): /session status
            # can show the DM how many answers are in.
            if state.get("prep"):
                state["prep"]["responses"] = (
                    state["prep"].get("responses", 0) + 1)
                save_state(STATE_FILE, state)
            await inter.followup.send(
                "Filed to the DM's review queue — only the DM can read "
                "it. Run `/session respond` again to add more.",
                ephemeral=True)

    @grp.command(name="respond",
                 description="Answer the prep ask privately — only the "
                             "DM sees it")
    async def respond_cmd(inter):
        # Open to EVERY member on purpose — the gate is for DM/config
        # commands, and this is the players' door. Config is checked
        # before the modal opens so nobody types an answer that has
        # nowhere to go.
        if not (WITNESS_URL and WITNESS_TOKEN):
            await inter.response.send_message(
                "Private responses aren't switched on for this campaign "
                "yet — for now, just send your answer to your DM as a "
                "direct message. Want it enabled? Ask your DM to turn "
                "it on.", ephemeral=True)
            return
        await inter.response.send_modal(RespondModal())

    @grp.command(name="status", description="Sessions, quorum, and config")
    async def status_cmd(inter, debug: bool = False):
        await inter.response.defer(ephemeral=True)
        dm = f"<@{cfg['dm_id']}>" if cfg["dm_id"] else "unset"
        role = f"<@&{cfg['role_id']}>" if cfg["role_id"] else "none"
        lines = [f"DM: {dm} · quorum: {cfg['quorum']} player(s)"
                 f"{' + DM required' if cfg['require_dm'] else ''}"
                 f" · ping: {role}"]
        prep = state.get("prep")
        if prep:
            first = prep["text"].strip().splitlines()[0] if prep["text"] \
                else ""
            snip = (first[:80] + "…") if len(first) > 80 else first
            n = prep.get("responses", 0)
            lines.append(f"prep out: “{snip}” · set <t:{int(prep['at'])}:R>"
                         + (f" · {n} private response(s) in" if n else ""))
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

    async def announce_reveals(corpus):
        # The reveal digest — "the veil lifts": ONE batched post for pages
        # newly reaching the projection since last seen, EXCEPT session
        # recaps (announce_new_recaps gives those their own line). Reading
        # only the projection means a page appears here only once already
        # player-visible — leak-proof by construction, same basis as the
        # recap announce. Batched (not one message per page) so an
        # edit-changelog can't turn into spam.
        new = [p for p in new_projected_pages(corpus, set(state["announced"]))
               if "sessions/" not in p]
        if not new:
            return
        chan = await recap_channel()
        if chan is None:
            return          # no channel yet: leave unannounced so the
                            # digest re-fires once one is configured
        item_tpl = MESSAGES.get(REVEAL_ITEM, REMINDERS[REVEAL_ITEM])
        entries = []
        for path in new:
            title = botlib.page_title(corpus, path)
            url = (f"{SITE_URL}/{path.removesuffix('.md')}"
                   if SITE_URL else "")
            entries.append(item_tpl.format(
                title=title, url=url, link=(f"\n{url}" if url else "")))
        frame = MESSAGES.get(REVEAL, REMINDERS[REVEAL])
        await chan.send(frame.format(
            ping="", count=len(new), entries="\n".join(entries)))
        state["announced"].extend(new)      # mark only after the post lands
        save_state(STATE_FILE, state)

    class Capability:
        async def ready(self, corpus=""):
            # CONVENE_REANNOUNCE=1: skip the catch-up and re-post every
            # recap once (e.g. after the site URLs change). Unset after.
            reannounce = os.environ.get("CONVENE_REANNOUNCE") == "1"
            # Startup snapshot: mark every page already in the projection —
            # recaps AND every other player-visible page — as already
            # announced, so an ephemeral host that lost the state file never
            # re-announces the back catalogue (recap or reveal) on restart.
            for p in botlib.page_paths(corpus):
                if p not in state["announced"] and not reannounce:
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
                    for key in evaluate(
                            session, now, cfg["quorum"],
                            require_dm=require_dm,
                            is_session=is_session_event(event.name)):
                        if key not in rec["fired"]:
                            rec["fired"].append(key)
            state["events"] = reconcile(state, live_ids)
            save_state(STATE_FILE, state)
            if reannounce:            # post every recap + reveal once now
                await announce_new_recaps(corpus)
                await announce_reveals(corpus)
            client.loop.create_task(tick_loop())
            print(f"convene ready: DM {cfg['dm_id']}, quorum "
                  f"{cfg['quorum']}, {len(state['announced'])} page(s) "
                  f"already announced")

        async def on_corpus_refresh(self, corpus):
            await announce_new_recaps(corpus)     # session recaps get a line
            await announce_reveals(corpus)        # everything else, batched

    return Capability()
