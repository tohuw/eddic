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
                         dm_mention=" <@1>")
    checks.append(("Session 3" in txt and "1 of 3" in txt,
                   "render fills the reminder text"))

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
