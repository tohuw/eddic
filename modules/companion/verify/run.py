# /// script
# requires-python = ">=3.9"
# ///
"""Verify the companion module's deterministic floor: the three
templates exist, each carries the load-bearing doctrine phrases
(the conduct rule verbatim where it applies, the mode dial and the
collaborator facet for the interviewer, the player companion's
private prep-ask response path filed to the DM-only witness inbox),
and the adversarial acceptance rig covers the eight behavior
classes."""

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
    # whitespace-collapsed player companion, so phrase checks survive
    # line wrapping in the persona prose
    pc = " ".join(t["player-companion.md"].split())
    checks = [
        (set(t) == {"player-companion.md", "dm-companion.md",
                    "backstory-interviewer.md", "player-kit.md",
                    "learners-codex.md"},
         "the templates ship (three companions, the player kit, "
         "the learner's codex)"),
        ("{{PLAYER_MCP_URL}}" in t["player-kit.md"] and
         "{{PLAYER_COMPANION}}" in t["player-kit.md"],
         "player kit carries the per-request connector URL sentinel "
         "and the inlined-persona slot (single-sourced hosted page)"),
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
        ("suggest_edit" in pc and "suggest_page" in pc,
         "player companion routes a DM prep-ask response to the "
         "witness inbox (suggest_edit/suggest_page)"),
        ("review queue" in pc and
         "invisible to the rest of the table" in pc,
         "private prep-ask response is marked DM-only and invisible "
         "to the rest of the table"),
        ("canon" in pc,
         "private prep-ask response is never presented as canon"),
        ("witness write path" in pc and "to the DM directly" in pc,
         "private prep-ask response falls back to the DM when the "
         "write path is off"),
        (t.get("learners-codex.md", "").find("never optimizes the build") >= 0,
         "codex extends never-better to the build (never optimizes)"),
        ("Never fabricate a value" in t.get("learners-codex.md", ""),
         "codex forbids fabricating a number (the sheet is the source)"),
        (all(s in t.get("learners-codex.md", "") for s in
             ("projection", "off-site")),
         "codex is projection-scoped and explains rules in place, "
         "not off-site"),
        ("Learner's Codex" in pc,
         "player companion advertises the learner's codex capability"),
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
