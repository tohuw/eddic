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
