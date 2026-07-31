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
    wa = " ".join(t["writing-assistant.md"].split())
    cu = " ".join(t.get("catch-up.md", "").split())
    pq = " ".join(t.get("prep-questions.md", "").split())
    checks = [
        (set(t) == {"player-companion.md", "dm-companion.md",
                    "backstory-interviewer.md", "player-kit.md",
                    "learners-primer.md", "writing-assistant.md",
                    "catch-up.md", "prep-questions.md"},
         "the templates ship (three companions, the player kit, "
         "the learner's primer, the writing assistant, the "
         "absent-player catch-up, the prep questions)"),
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
        (RULE in t["writing-assistant.md"],
         "writing assistant carries the conduct rule verbatim "
         "(it sits at the table too)"),
        ("Tactics are not" in wa and "way to say a thing" in wa,
         "writing assistant splits phrasing (offered) from tactics "
         "(never)"),
        ("never writing unprompted" in wa and "take the pen" in wa,
         "writing assistant interviews and never seizes the pen"),
        ("One short invitation" in wa and "does not come up" in wa,
         "writing assistant offers once, then drops it (no script, "
         "no nagging)"),
        ("use it back to them" in wa,
         "writing assistant reflects the writer's own phrases back"),
        ("about play, not prose" in wa,
         "writing assistant frees craft help from the conduct rule "
         "(guardrails are conduct, not craft)"),
        ("never because they approved it" in wa and "mixed" in wa,
         "writing assistant keeps curation off the authorship axis"),
        ("silently" in wa and "not to learn a schema" in wa,
         "writing assistant marks silently (positive duty, no "
         "schema lessons)"),
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
        ("you do not rank or rebuild their character"
         in " ".join(t.get("learners-primer.md", "").split()).lower(),
         "primer still refuses to rank or rebuild the character"),
        ("tends to work" in t.get("learners-primer.md", "")
         or "tend to work" in t.get("learners-primer.md", ""),
         "primer may say which options tend to work (never-better "
         "relaxes for a player's own character, off-scene)"),
        ("Never fabricate a value" in t.get("learners-primer.md", ""),
         "primer forbids fabricating a number (the sheet is the source)"),
        (all(s in t.get("learners-primer.md", "") for s in
             ("projection", "off-site")),
         "primer is projection-scoped and explains rules in place, "
         "not off-site"),
        ("Learner's Primer" in pc,
         "player companion advertises the learner's primer capability"),
        (all(s in cu for s in
             ("1. What happened",
              "2. What your character has heard",
              "3. What has changed that touches you")),
         "catch-up keeps its three parts in order (the session, what "
         "the character heard, what changed for them)"),
        ("the absent character was absent" in cu and
         "You never invent what they did while the session ran" in cu,
         "catch-up never invents the absent character's off-screen "
         "action (an absent character was absent)"),
        ("what the party would have told them afterwards" in cu and
         "only the people in the room have" in cu,
         "catch-up splits second-hand knowledge from what only the "
         "room has"),
        ("cannot hand them something the party did not learn" in cu,
         "catch-up is projection-scoped by construction (never what "
         "the party did not learn)"),
        ("two or three genuinely different options" in cu and
         "hand the choice back explicitly" in cu,
         "catch-up offers the absence explanation and leaves the pick "
         "to the player"),
        (RULE in t.get("catch-up.md", "") and
         "not a briefing on what to do next session" in cu,
         "catch-up carries the conduct rule verbatim and refuses to "
         "brief the returning player"),
        ("suggest_edit" in cu and "review queue" in cu and
         "hand it to the DM directly" in cu,
         "catch-up files the player's pick to the DM-only review "
         "queue, with the write-path-off fallback"),
        ("machine-authored" in cu and
         "never because they approved it" in cu,
         "catch-up marks what it wrote machine-authored and keeps "
         "curation off the authorship axis"),
        ("ask, not to write" in pq,
         "prep questions asks rather than writes"),
        (all(s in pq for s in
             ("Open threads", "NPCs who never came back",
              "Unpaid foreshadowing",
              "Player asks not yet delivered")),
         "prep questions runs its four passes (threads, absent NPCs, "
         "unpaid foreshadowing, undelivered player asks)"),
        ("Never assert an item without saying where you got it" in pq,
         "prep questions cites every item to its page or session"),
        ("look identical from where you sit" in pq,
         "prep questions states the closed-versus-forgotten caveat"),
        ("three to five questions, no more" in pq and
         "Not a backlog" in pq,
         "prep questions caps at three to five and refuses to become "
         "a backlog"),
        ("Once the DM has picked, you may draft" in pq,
         "prep questions gates drafting on the DM's choice"),
        ("marked machine-authored" in pq and
         "curation is a separate mark" in pq,
         "prep questions marks its drafts machine-authored and keeps "
         "curation a separate mark"),
        ("It is authorship" in pq and "DM tier" in pq and
         "nowhere a player can read it" in pq,
         "prep questions is DM-side and asks for authorship reasons, "
         "not conduct ones"),
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
