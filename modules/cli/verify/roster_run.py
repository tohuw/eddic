# /// script
# requires-python = ">=3.9"
# ///
"""Verify the roster facility: the identifiers modules actually hold —
Craig track stems, raw user ids, display names with a real first name
glued on — all resolve to one canonical label, and an unknown speaker
stays unknown rather than becoming a wrong one."""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "roster.py"
spec = importlib.util.spec_from_file_location("roster", SCRIPT)
roster = importlib.util.module_from_spec(spec)
spec.loader.exec_module(roster)

DATA = {"players": [
    {"discord_id": "104248823563448320", "discord_username": "tohuw",
     "player": "Ron", "characters": ["Niðrerir"], "label": "Niðrerir",
     "role": "player"},
    {"discord_id": "703756978068914237", "discord_username": "rvhannah",
     "player": "Roger", "characters": ["Thorne Ashenpaw"],
     "label": "Thorne", "role": "player"},
    {"discord_id": "512169632195412010", "discord_username": "theseous",
     "player": "Tyson", "characters": [], "label": "DM", "role": "dm"},
]}


def check(label, ok, detail=""):
    print(f"{'ok  ' if ok else 'FAIL'} {label}"
          + (f" — {detail}" if detail and not ok else ""))
    return 0 if ok else 1


def main():
    fails = 0
    r = lambda s: roster.resolve(s, DATA)

    fails += check("a Craig track stem resolves", r("5-theseous") == "DM")
    fails += check("a full track filename resolves",
                   r("1-Niðrerir_Ron.wav") == "Niðrerir")
    fails += check("a display name with a real first name glued on resolves",
                   r("Thorne_Ashenpaw_Roger") == "Thorne")
    fails += check("a raw user id resolves",
                   r("104248823563448320") == "Niðrerir")
    fails += check("a bare username resolves", r("rvhannah") == "Thorne")
    fails += check("the player's own name resolves", r("Roger") == "Thorne")
    fails += check("an unknown speaker passes through unchanged",
                   r("VisitingGuest") == "VisitingGuest")
    fails += check("empty input does not crash", r("") == "")

    # the longest match wins, so a short alias cannot shadow a real name
    tricky = {"players": [
        {"discord_id": "1", "label": "Ace", "characters": ["Ace"]},
        {"discord_id": "2", "label": "Acer Windbourne",
         "characters": ["Acer Windbourne"]},
    ]}
    fails += check("the most specific match wins",
                   roster.resolve("Acer_Windbourne", tricky)
                   == "Acer Windbourne")

    bad = {"players": [{"discord_id": "not-a-number", "label": ""},
                       {"discord_id": "1", "label": "A", "role": "wizard"}]}
    errs = roster.check(bad)
    fails += check("a non-numeric id, an empty label, and a bad role are "
                   "all caught", len(errs) == 3, str(errs))

    dupes = {"players": [{"discord_id": "7", "label": "A"},
                         {"discord_id": "7", "label": "B"}]}
    fails += check("a duplicate discord_id is caught",
                   any("duplicate" in e for e in roster.check(dupes)))

    seeded = {"players": []}
    added = roster.seed_craig(
        "1) tohuw (104248823563448320)\n"
        "2) rvhannah (703756978068914237)\n"
        "not a track line\n", seeded)
    fails += check("a Craig info.txt seeds the ids and usernames",
                   len(added) == 2
                   and seeded["players"][0]["discord_id"]
                   == "104248823563448320")
    again = roster.seed_craig("1) tohuw (104248823563448320)\n", seeded)
    fails += check("re-seeding adds nobody twice", again == [])

    tmp = Path(tempfile.mkdtemp(prefix="eddic-roster-verify-")) / "roster.json"
    roster.save(tmp, json.loads(json.dumps(DATA)))
    fails += check("the DM sorts first, then labels alphabetically",
                   [p["label"] for p in json.loads(
                       tmp.read_text(encoding="utf-8"))["players"]][0] == "DM")

    print("verify ok: roster facility" if not fails
          else f"verify FAILED: roster facility ({fails})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
