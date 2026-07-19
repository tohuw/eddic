# /// script
# requires-python = ">=3.9"
# ///
"""Verify the companion module's deterministic floor: the three
templates exist, each carries the load-bearing doctrine phrases
(the conduct rule verbatim where it applies, the mode dial and the
collaborator facet for the interviewer), and the adversarial
acceptance rig covers the eight behavior classes."""

import sys
from pathlib import Path

MOD = Path(__file__).resolve().parent.parent
RULE = "you may say what is\npossible and what is true; you may " \
       "never say what is better"


def main():
    t = {p.name: (MOD / "templates" / p.name).read_text(encoding="utf-8")
         for p in (MOD / "templates").iterdir() if p.suffix == ".md"}
    rig = (MOD / "verify" / "conduct-acceptance.md").read_text(
        encoding="utf-8")
    checks = [
        (set(t) == {"player-companion.md", "dm-companion.md",
                    "backstory-interviewer.md", "player-kit.md"},
         "the templates ship (three companions plus the player kit)"),
        ("{{PLAYER_MCP_URL}}" in t["player-kit.md"] and
         "player-companion.md" in t["player-kit.md"],
         "player kit carries the connector URL slot and points at "
         "the companion persona"),
        (all(RULE in t[n] for n in
             ("player-companion.md", "dm-companion.md")),
         "both companions carry the conduct rule verbatim"),
        (all("{{SITE_NAME}}" in body for body in t.values()),
         "every template parameterized on the campaign"),
        ("puzzles included" in t["player-companion.md"],
         "player template closes the puzzle loophole"),
        ("attempt almost anything" in t["player-companion.md"],
         "player template keeps the option landscape open"),
        ("reference desk" in t["dm-companion.md"] and
         "DM-only" in t["dm-companion.md"],
         "dm template scopes to reference, marks itself DM-only"),
        ("{{MODE}}" in t["backstory-interviewer.md"] and
         "scribe" in t["backstory-interviewer.md"] and
         "drafter" in t["backstory-interviewer.md"],
         "interviewer carries the scribe/drafter dial"),
        ("never rewritten" in t["backstory-interviewer.md"],
         "scribe mode forbids rewriting the player's words"),
        (all(p in t["backstory-interviewer.md"] for p in
             ("Record first", "ideas, not canon",
              "logs already establish", "honest guess")),
         "interviewer carries the collaborator facet's four moves "
         "(record first, register shift, grounding, projection-only)"),
        (all(f"{i}." in rig for i in range(1, 9)),
         "acceptance rig covers the eight behavior classes"),
        ("must NOT overcorrect" in rig,
         "rig tests against overcorrection, not just compliance"),
    ]
    failed = [msg for ok, msg in checks if not ok]
    for ok, msg in checks:
        print(("ok  " if ok else "FAIL"), msg)
    if failed:
        return 1
    print("verify ok: companion module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
