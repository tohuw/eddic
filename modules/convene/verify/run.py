# /// script
# requires-python = ">=3.9"
# ///
"""Verify convene's pure core without discord installed: the quorum
state machine fires each reminder once and only when due, the
end-of-session reminder supersedes, persistence round-trips and
reconcile prunes dead events, and recap announce-detection (via the
lore-bot botlib helpers) surfaces each new session page exactly once.
The discord wiring in setup() is exercised live, not here."""

import sys
import tempfile
from pathlib import Path

MOD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MOD / "templates"))
sys.path.insert(0, str(
    MOD.parent / "lore-bot" / "templates"))
import convene          # noqa: E402
import botlib           # noqa: E402

HOUR = 3600


def sess(start_h, count, dm_in=True, status="scheduled", fired=()):
    import time
    return {"start": time.time() + start_h * HOUR, "count": count,
            "dm_in": dm_in, "status": status, "fired": fired}


def main():
    import time
    now = time.time()
    checks = []

    def ev(session, **kw):
        return convene.evaluate(session, now, kw.pop("quorum", 3), **kw)

    # created fires once, on first sight, regardless of timing
    s = sess(72, 0)
    checks.append((ev(s) == ["created"], "created fires on first sight"))
    checks.append((ev(sess(72, 0, fired=["created"])) == [],
                   "created does not fire twice"))

    # at-risk: inside the window, short of quorum, not yet fired
    checks.append((convene.AT_RISK in ev(sess(30, 1, fired=["created"])),
                   "at_risk fires when short inside the 36h window"))
    checks.append((convene.AT_RISK not in ev(sess(30, 3,
                                                   fired=["created"])),
                   "at_risk silent once quorum is met"))
    checks.append((convene.AT_RISK not in ev(sess(72, 1,
                                                   fired=["created"])),
                   "at_risk silent outside the window"))
    checks.append((convene.AT_RISK not in ev(sess(30, 1,
                   fired=["created", "at_risk"])),
                   "at_risk does not fire twice"))

    # imminent: quorum met inside the 2h window
    checks.append((convene.IMMINENT in ev(sess(1, 3,
                                               fired=["created"])),
                   "imminent fires when quorum met near start"))
    checks.append((convene.IMMINENT not in ev(sess(1, 2,
                                                    fired=["created"])),
                   "imminent silent while short of quorum"))

    # require_dm gates quorum
    checks.append((convene.IMMINENT not in ev(
        sess(1, 3, dm_in=False, fired=["created"]), require_dm=True),
        "quorum not met without the DM when required"))
    checks.append((convene.IMMINENT in ev(
        sess(1, 3, dm_in=False, fired=["created"]), require_dm=False),
        "DM not required when the table says so"))

    # completed supersedes; ended fires once
    checks.append((convene.evaluate(
        sess(-2, 3, status="completed", fired=["created"]), now, 3)
        == ["ended"], "completed session fires ended, once"))
    checks.append((convene.evaluate(
        sess(-2, 3, status="completed",
             fired=["created", "ended"]), now, 3) == [],
        "ended does not fire twice"))

    # render fills the templates safely
    txt = convene.render(convene.AT_RISK, title="Session 3",
                         start=now + HOUR, now=now, count=1, quorum=3,
                         dm_mention=" <@1>", when_rel="<t:1:R>")
    checks.append(("Session 3" in txt and "1 of 3" in txt
                   and "<t:1:R>" in txt,
                   "render fills at_risk with the relative timestamp"))

    # persistence round-trip + reconcile
    tmp = Path(tempfile.mkdtemp(prefix="eddic-convene-verify-"))
    sf = tmp / "convene_state.json"
    st = {"events": {"a": {"fired": ["created"]},
                     "b": {"fired": ["created", "at_risk"]}},
          "announced": ["campaigns/x/sessions/session-1.md"]}
    convene.save_state(sf, st)
    back = convene.load_state(sf)
    checks.append((back["events"]["b"]["fired"] == ["created", "at_risk"]
                   and back["announced"] == st["announced"],
                   "state round-trips through disk"))
    pruned = convene.reconcile(back, {"a"})
    checks.append((set(pruned) == {"a"},
                   "reconcile drops events Discord no longer has"))
    checks.append((convene.load_state(tmp / "absent.json")
                   == {"events": {}, "announced": []},
                   "missing state file loads empty"))

    # settings persist through the state file (slash-set config)
    st2 = {"events": {}, "announced": [],
           "settings": {"dm_id": 512, "quorum": 4}}
    convene.save_state(sf, st2)
    checks.append((convene.load_state(sf).get("settings")
                   == {"dm_id": 512, "quorum": 4},
                   "slash-set settings survive the state file"))
    st3 = {"events": {}, "announced": []}
    convene.save_state(sf, st3)
    checks.append(("settings" not in convene.load_state(sf),
                   "no settings key written when there are none"))

    # announce detection over a growing projection corpus
    c1 = ("=== places/sunton.md ===\n# Sunton\n\ntext\n\n"
          "=== campaigns/ls/sessions/session-1.md ===\n# Session 1\n\nr")
    announced = set(botlib.page_paths(c1))  # startup snapshot
    checks.append((botlib.new_session_pages(c1, announced) == [],
                   "startup snapshot means no back-catalogue announce"))
    c2 = c1 + ("\n\n=== campaigns/ls/sessions/session-2.md ==="
               "\n# Session 2 — The Deep\n\nrecap")
    new = botlib.new_session_pages(c2, announced)
    checks.append((new == ["campaigns/ls/sessions/session-2.md"],
                   "a newly-published recap is detected once"))
    announced |= set(new)
    checks.append((botlib.new_session_pages(c2, announced) == [],
                   "an announced recap is never re-announced"))
    checks.append((botlib.page_title(c2,
                   "campaigns/ls/sessions/session-2.md")
                   == "Session 2 — The Deep",
                   "recap title read from the page's H1"))

    # CONVENE_REANNOUNCE gating (the ready() startup catch-up). Off by
    # default: the catch-up marks every existing recap already-announced,
    # so a restart never re-posts the back catalogue. Set to "1" and the
    # catch-up is skipped — nothing is marked, so announce_new_recaps
    # re-posts every recap once (e.g. after the site URLs change).
    import os as _os

    def startup_snapshot(corpus):
        reannounce = _os.environ.get("CONVENE_REANNOUNCE") == "1"
        marked = set()
        for p in botlib.page_paths(corpus):
            if ("sessions/" in p and p not in marked and not reannounce):
                marked.add(p)
        return marked

    all_recaps = ["campaigns/ls/sessions/session-1.md",
                  "campaigns/ls/sessions/session-2.md"]
    _os.environ.pop("CONVENE_REANNOUNCE", None)
    checks.append((botlib.new_session_pages(c2, startup_snapshot(c2)) == [],
                   "default (unset): catch-up marks the back catalogue, "
                   "nothing re-posts"))
    _os.environ["CONVENE_REANNOUNCE"] = "0"
    checks.append((botlib.new_session_pages(c2, startup_snapshot(c2)) == [],
                   "CONVENE_REANNOUNCE=0 stays off — no re-post"))
    _os.environ["CONVENE_REANNOUNCE"] = "1"
    checks.append((sorted(botlib.new_session_pages(c2, startup_snapshot(c2)))
                   == all_recaps,
                   "CONVENE_REANNOUNCE=1 skips the catch-up so every recap "
                   "re-posts"))
    _os.environ.pop("CONVENE_REANNOUNCE", None)

    # recap_channel resolves to the announce channel — one auto-events
    # channel, no separate recap configuration. The resolver lives in the
    # discord wiring (exercised live), so assert at the source level that
    # both resolvers read announce_channel_id and the dropped recap
    # config is gone entirely.
    src = (MOD / "templates" / "convene.py").read_text(encoding="utf-8")
    checks.append((src.count('_channel(cfg["announce_channel_id"])') >= 2,
                   "reminder_channel and recap_channel both resolve the "
                   "announce channel"))
    checks.append(("recap_thread_id" not in src
                   and "RECAP_THREAD_ID" not in src,
                   "the separate recap-channel config is dropped"))
    checks.append(('name="recap-channel"' not in src,
                   "the /session recap-channel command is removed"))

    # message overrides (re-voice / translation seam)
    mf = tmp / "convene_messages.json"
    import json as _json
    mf.write_text(_json.dumps({
        "created": "{ping}¡Sesión! **{title}** — {when}",
        "at_risk": "{title} usa un marcador {desconocido}",  # bad
    }), encoding="utf-8")
    msgs = convene.load_messages(mf)
    checks.append((msgs[convene.CREATED].startswith("{ping}¡Sesión!"),
                   "valid override replaces the default template"))
    checks.append((msgs[convene.AT_RISK] == convene.REMINDERS[convene.AT_RISK],
                   "a template with an unknown placeholder is rejected"))
    checks.append((convene.load_messages(tmp / "absent.json")
                   == convene.REMINDERS, "no override file keeps defaults"))
    out = convene.render(convene.CREATED, title="X", when="W",
                         ping="<@&1> ", templates=msgs)
    checks.append(("¡Sesión! **X**" in out and out.startswith("<@&1> "),
                   "render uses the override with the ping"))

    # prep: the DM's ask goes out verbatim inside a frame, with the ping
    body = ("Send me a couple of NPCs from your backstory. Also: why "
            "was your character headed to <#123>? Roll is 2d6+{mod}.")
    out = convene.render(convene.PREP, ping="<@&9> ", body=body)
    checks.append((body in out and out.startswith("<@&9> "),
                   "prep relays the DM's words verbatim, with the ping"))
    checks.append(("{mod}" in out,
                   "braces in the DM's text survive (not re-interpreted)"))
    # prep frame is overridable/translatable like the other templates
    mf2 = tmp / "convene_messages_prep.json"
    mf2.write_text(_json.dumps({
        "prep": "{ping}Escuchad:\n\n{body}"}), encoding="utf-8")
    pmsgs = convene.load_messages(mf2)
    checks.append((pmsgs[convene.PREP] == "{ping}Escuchad:\n\n{body}",
                   "a valid prep frame override replaces the default"))
    checks.append((convene.load_messages(
        tmp / "absent.json")[convene.PREP] == convene.REMINDERS[convene.PREP],
        "prep falls back to the default frame when not overridden"))
    # prep is DM-triggered, never an auto-reminder
    checks.append((convene.PREP not in convene.evaluate(
        sess(-2, 3, status="completed", fired=["created"]), now, 3),
        "evaluate never emits prep on its own"))
    # prep persists through the state file
    st4 = {"events": {}, "announced": [],
           "prep": {"text": body, "at": 1000, "by": 7}}
    convene.save_state(sf, st4)
    checks.append((convene.load_state(sf).get("prep", {}).get("text") == body,
                   "the last prep ask survives the state file"))
    st5 = {"events": {}, "announced": []}
    convene.save_state(sf, st5)
    checks.append(("prep" not in convene.load_state(sf),
                   "no prep key written when there is none"))

    # effective_status: time-based 'ended' fallback
    checks.append((convene.effective_status("scheduled", now - 5*HOUR,
                   now, duration_s=4*HOUR) == "completed",
                   "an event past start+duration counts as ended"))
    checks.append((convene.effective_status("active", now - 5*HOUR,
                   now, end=now - HOUR) == "completed",
                   "an active event past its explicit end is ended"))
    checks.append((convene.effective_status("scheduled", now + HOUR,
                   now, duration_s=4*HOUR) == "scheduled",
                   "a future event is not force-ended"))
    checks.append((convene.effective_status("canceled", now - 9*HOUR,
                   now) == "canceled",
                   "canceled stays canceled, never force-ended"))

    # envint tolerates inline comments and whitespace (the crash that
    # took convene down on the live bot)
    import os as _os
    _os.environ["_CONV_T"] = "512169632195412010   # Tyson"
    checks.append((convene.envint("_CONV_T") == 512169632195412010,
                   "envint ignores an inline comment"))
    _os.environ["_CONV_T2"] = "  7 "
    checks.append((convene.envint("_CONV_T2") == 7,
                   "envint strips whitespace"))
    checks.append((convene.envint("_CONV_ABSENT", 3) == 3,
                   "envint falls back to default when unset"))
    for k in ("_CONV_T", "_CONV_T2"):
        _os.environ.pop(k, None)

    # ---- Fix 1: a reminder is marked fired only after a successful send.
    # When the announce channel is unset, tick skips (continue) without
    # marking fired, so CREATED/AT_RISK/IMMINENT re-fire once a channel is
    # configured rather than being permanently lost. The tick runs live, so
    # assert the structure at the source level, scoped to the tick body.
    tick_body = src.partition("async def tick():")[2].partition(
        "async def tick_loop(")[0]
    checks.append(("if chan is None:" in tick_body and "continue" in tick_body,
                   "tick skips a reminder when the announce channel is unset"))
    checks.append(('rec["fired"].append(key)' in tick_body
                   and "if chan:" not in tick_body,
                   "tick marks fired only after a send, never under `if chan:`"))

    # ---- Fix 2: a corrupt state file loads as empty rather than raising.
    # load_state runs in setup() before ready()'s try/except, so a truncated
    # convene_state.json (a crash mid-write) would otherwise wedge the bot.
    corrupt = tmp / "corrupt_state.json"
    corrupt.write_text('{"events": {"a": {"fir', encoding="utf-8")  # truncated
    checks.append((convene.load_state(corrupt)
                   == {"events": {}, "announced": []},
                   "a corrupt state file loads as empty, never raising"))
    corrupt.write_text("[1, 2, 3]", encoding="utf-8")       # valid JSON, wrong
    checks.append((convene.load_state(corrupt)
                   == {"events": {}, "announced": []},
                   "a non-object state file loads as empty"))
    # atomic write leaves no temp file behind and still round-trips
    convene.save_state(sf, {"events": {}, "announced": ["p"]})
    checks.append((not sf.with_name(sf.name + ".tmp").exists()
                   and convene.load_state(sf)["announced"] == ["p"],
                   "save_state writes atomically (no .tmp left, round-trips)"))

    # ---- Reveal digest: the full projection delta, batched, newly-revealed
    # only. new_projected_pages is the broad counterpart to new_session_pages
    # (every page type, not just sessions/); the announce filters out session
    # recaps (they keep their own line) and batches the rest into one post.
    def reveals(corpus, announced):
        return [p for p in convene.new_projected_pages(corpus, announced)
                if "sessions/" not in p]

    pc1 = ("=== places/sunton.md ===\n# Sunton\n\nt\n\n"
           "=== README.md ===\n# Readme\n\nx\n\n"
           "=== campaigns/ls/sessions/session-1.md ===\n# Session 1\n\nr")
    snap = set(botlib.page_paths(pc1))          # startup snapshot: all pages
    checks.append((reveals(pc1, snap) == [],
                   "reveal digest: the startup snapshot suppresses the back "
                   "catalogue on a simulated restart"))
    pc2 = pc1 + ("\n\n=== people/the-warden.md ===\n# The Warden\n\nnpc"
                 "\n\n=== places/sunken-city.md ===\n# The Sunken City\n\nloc"
                 "\n\n=== campaigns/ls/sessions/session-2.md ===\n# S2\n\nr")
    new = reveals(pc2, snap)
    checks.append((new == ["people/the-warden.md", "places/sunken-city.md"],
                   "reveal digest: N newly-revealed non-session pages batch "
                   "into one delta (the recap keeps its own line)"))
    checks.append((reveals(pc2, snap | set(new)) == [],
                   "reveal digest: idempotent — an announced reveal never "
                   "re-announces on a re-poll"))
    checks.append(("campaigns/ls/npcs/hidden-villain.md" not in reveals(pc2,
                   snap),
                   "reveal digest: a DM-only page (absent from the "
                   "projection corpus) never announces — leak-proof"))
    # the full-delta contract of the helper itself
    checks.append(("campaigns/ls/sessions/session-2.md"
                   in convene.new_projected_pages(pc2, snap),
                   "new_projected_pages is the full delta (sessions included)"))
    checks.append(("README.md" not in convene.new_projected_pages(pc2, set()),
                   "new_projected_pages excludes non-content files (README)"))
    # the digest fires on the existing lifecycle beat, batched, overridable
    checks.append(("async def announce_reveals(corpus):" in src
                   and src.count("await announce_reveals(corpus)") >= 2,
                   "the reveal digest fires on the corpus-refresh beat and on "
                   "the reannounce catch-up"))
    checks.append(("fetch_member" in src
                   and "get_member" in src.partition(
                       "async def count_interested")[2],
                   "count_interested falls back to fetch_member on a member-"
                   "cache miss (a bare Client would else count a role-scoped "
                   "quorum as 0 despite real interested reacts)"))
    checks.append(('"\\n".join(entries)' in src
                   and "frame.format(" in src,
                   "the reveal digest batches entries into a single post"))
    checks.append((convene.REVEAL in convene.REMINDERS
                   and convene.REVEAL_ITEM in convene.REMINDERS,
                   "the reveal frame and item are overridable templates"))
    # a reveal override with an unknown placeholder is rejected like the rest
    mf3 = tmp / "convene_messages_reveal.json"
    mf3.write_text(_json.dumps({
        "reveal": "Lo, {count} new: {entries}",
        "reveal_item": "- {title} uses {bogus}"}), encoding="utf-8")
    rmsgs = convene.load_messages(mf3)
    checks.append((rmsgs[convene.REVEAL] == "Lo, {count} new: {entries}",
                   "a valid reveal override replaces the default frame"))
    checks.append((rmsgs[convene.REVEAL_ITEM]
                   == convene.REMINDERS[convene.REVEAL_ITEM],
                   "a reveal_item with an unknown placeholder is rejected"))

    # convene.py imports clean without discord (pure core only)
    import py_compile
    try:
        py_compile.compile(str(MOD / "templates" / "convene.py"),
                           doraise=True)
        checks.append((True, "convene.py compiles"))
    except py_compile.PyCompileError as e:
        checks.append((False, f"convene.py compile error: {e}"))

    failed = [m for ok, m in checks if not ok]
    for ok, m in checks:
        print(("ok  " if ok else "FAIL"), m)
    if failed:
        return 1
    print("verify ok: convene module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
