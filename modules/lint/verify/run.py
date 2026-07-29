# /// script
# requires-python = ">=3.9"
# ///
"""Verify the lint module: run the reporter against the fixture wiki
and require exactly the defects the fixture plants, no more, no fewer;
then verify the semantic-review prep/validation script builds a correct
review packet and enforces the findings schema. Exits 0 on match, 1
otherwise."""

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
REPORTER = HERE.parent / "scripts" / "eddic_lint.py"
SEMANTIC = HERE.parent / "scripts" / "semantic_review.py"

EXPECTED = Counter({
    "broken-link": 2,        # sunken-city -> ghost-quarter.md (inline);
                             # sunken-city -> depths/hidden.dm.md (<a href>,
                             # proving HTML links are resolved too)
    "broken-anchor": 1,      # sunken-city -> warden.md#no-such-heading
    "absolute-link": 1,      # sunken-city -> /maps/atlas.html
    "missing-h1": 1,         # lost-shrine
    "firewall-breach": 6,    # index and warden link the DM-only vault
                             # (inline); sunken-city links it via a
                             # reference-style [the vault][v] link; and,
                             # via non-.md forms (issue #22), index links
                             # the DM-only hidden-annex by its .html and
                             # warden links it by its clean/extensionless
                             # URL — each resolved to the .md and judged
                             # alike. The sixth: harbor-watch links an
                             # open merge proposal, which is DM-side
                             # however it marks itself — pinning the
                             # linter to the projection's verdict
    "log-malformed": 2,      # unknown type 'conjure'; freeform ## header
    "orphan": 3,             # lost-shrine; contributed field-notes;
                             # harbor-watch (no quiet marker, so it counts)
    "unreachable": 3,        # lost-shrine; contributed field-notes;
                             # harbor-watch
    "tiny-unstubbed": 1,     # lost-shrine only — kestrel's overlay
                             # replaced the tiny vault page, proving
                             # the effective view took the overlay
    "contrib-conflict": 1,   # vagrant's second claim on the vault
    "contrib-collision": 1,  # kestrel/lost-shrine lands w/o replaces
    "contrib-replaces-missing": 1,  # ghost-annex shadows nothing
    "contrib-unattributed": 1,      # field-notes marked bare 'human'
    "invalid-transactability": 1,   # lost-shrine 'sellable'
    "derived-from-missing": 1,      # warden derived-from ghost-quarter
    "invalid-curation": 1,          # rumor-of-the-warden 'reviewed'
    "invalid-ingest": 1,            # rumor-of-the-warden 'sideways'
    "invalid-lint": 1,              # rumor-of-the-warden 'maybe'
    "merge-proposal-visible": 1,    # rumor-of-the-warden claims player
    "merge-target-missing": 1,      # rumor-of-the-vault -> no-such-page
    "merge-pending": 2,             # both rumor pages await adjudication
})

# The advisory tier, quieted where the pen is held elsewhere. Each of the
# three quieting paths is planted once: curation (field-journal), the
# owner's opt-out (ledger-scrap), and an open proposal (both rumor pages).
EXPECTED_QUIETED = Counter({
    "orphan": 3,          # field-journal, ledger-scrap, the vault rumor
                          # (the warden rumor now has an inbound link)
    "unreachable": 4,     # those three and the warden rumor — the page
                          # linking it is itself outside the catalog
    "tiny-unstubbed": 2,  # field-journal, ledger-scrap
})


def check_reporter():
    proc = subprocess.run(
        [sys.executable, str(REPORTER), str(HERE / "fixture"), "--json",
         "--contribs", str(HERE / "fixture-contribs")],
        capture_output=True, text=True)
    if proc.returncode not in (0, 1):
        print(f"reporter failed (exit {proc.returncode}):\n{proc.stderr}")
        return 1
    report = json.loads(proc.stdout)
    got = Counter(f["code"] for f in report["findings"])

    # The advisory tier: quieted findings must be absent from the default
    # report, counted in the summary, and listed under --show-quieted —
    # quiet, never silent.
    shown = subprocess.run(
        [sys.executable, str(REPORTER), str(HERE / "fixture"), "--json",
         "--contribs", str(HERE / "fixture-contribs"), "--show-quieted"],
        capture_output=True, text=True)
    full = json.loads(shown.stdout)
    quieted = Counter(f["code"] for f in full["findings"] if f.get("quieted"))
    tier_ok = True
    if quieted != EXPECTED_QUIETED:
        tier_ok = False
        for code in sorted(set(EXPECTED_QUIETED) | set(quieted)):
            if EXPECTED_QUIETED[code] != quieted[code]:
                print(f"FAIL: quieted {code}: expected "
                      f"{EXPECTED_QUIETED[code]}, got {quieted[code]}")
    if report["summary"].get("quieted") != sum(EXPECTED_QUIETED.values()):
        tier_ok = False
        print(f"FAIL: summary undercounts quieting: "
              f"{report['summary'].get('quieted')} != "
              f"{sum(EXPECTED_QUIETED.values())}")
    if any(f["code"] in EXPECTED_QUIETED and f["path"] in {
            "field-journal.md", "ledger-scrap.md", "rumor-of-the-warden.md",
            "rumor-of-the-vault.md"} for f in report["findings"]):
        tier_ok = False
        print("FAIL: an advisory finding survived onto a quieted page")
    # Displaying the quieted set must not revive it into enforcement.
    if shown.returncode != proc.returncode:
        tier_ok = False
        print(f"FAIL: --show-quieted changed the exit code "
              f"({proc.returncode} -> {shown.returncode}); it is a display "
              f"flag, not an enforcement one")

    if got == EXPECTED and proc.returncode == 1 and tier_ok:
        print(f"verify ok: {sum(got.values())} findings, all expected; "
              f"{sum(quieted.values())} advisory quieted on three paths "
              "(curation, opt-out, proposal); exit code signals errors "
              "correctly")
        return 0

    if proc.returncode != 1:
        print("FAIL: fixture has errors; reporter should exit 1, "
              f"got {proc.returncode}")
    for code in sorted(set(EXPECTED) | set(got)):
        if EXPECTED[code] != got[code]:
            print(f"FAIL: {code}: expected {EXPECTED[code]}, got {got[code]}")
            for f in report["findings"]:
                if f["code"] == code:
                    print(f"        {f['path']}:{f['line']} — {f['detail']}")
    return 1


# The categories the checklist must cover, and the deterministic codes
# the packet must declare out of scope (a sample the floor guarantees).
REQUIRED_CATEGORIES = {"firewall-prose", "tonal-drift", "contradiction",
                       "dangling-reference", "naming-inconsistency",
                       "stub-overgrown-prose"}
SAMPLE_OUT_OF_SCOPE = {"broken-link", "firewall-breach", "missing-h1",
                       "stub-overgrown", "orphan"}


def run_semantic(args, stdin=None):
    return subprocess.run([sys.executable, str(SEMANTIC), *args],
                          capture_output=True, text=True, input=stdin)


def check_semantic():
    failed = []

    def want(ok, msg):
        print(("ok  " if ok else "FAIL"), msg)
        if not ok:
            failed.append(msg)

    # 1. The packet builds from the fixture, with the projection separate.
    proc = run_semantic([str(HERE / "fixture"), "--projection",
                         str(HERE / "fixture-projection")])
    want(proc.returncode == 0, "packet builds, exit 0")
    try:
        packet = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        print("FAIL: packet is not JSON")
        return 1

    want(bool(packet.get("master_pages")), "packet gathers master pages")
    want(packet.get("projection", {}).get("status") == "present"
         and bool(packet["projection"].get("pages")),
         "packet gathers the player projection SEPARATELY from the master")

    cats = {c.get("category") for c in packet.get("checklist", [])}
    want(REQUIRED_CATEGORIES <= cats,
         "checklist covers every required category (incl. firewall-prose)")
    want(all("complements" in c for c in packet.get("checklist", [])),
         "every checklist item names the deterministic check it complements")

    schema = packet.get("output_schema", {}).get("finding", {})
    want(set(schema) == set(FINDING_KEYS),
         "output schema pins exactly the finding keys")

    codes = set(packet.get("not_in_scope", {}).get("codes", []))
    want(SAMPLE_OUT_OF_SCOPE <= codes,
         "not_in_scope declares the deterministic codes (no re-litigation)")
    want(bool(packet.get("safety_rails"))
         and any("dvisory" in r or "propose" in r
                 for r in packet.get("safety_rails", [])),
         "safety rails documented (advisory-only, agent proposes)")

    # 2. Projection absent => firewall-prose check is marked BLOCKED, not run.
    proc = run_semantic([str(HERE / "fixture")])
    absent = json.loads(proc.stdout)["projection"]
    want(absent.get("status") == "absent" and "BLOCKED" in absent.get("note", ""),
         "no projection => firewall-prose blocked, packet still builds")

    # 3. Schema validation accepts a well-formed findings doc.
    good = json.dumps({"findings": [{
        "page": "warden.md", "anchor_or_line": "the-warden",
        "category": "firewall-prose", "severity": "error",
        "finding": "Player prose reveals the Warden's hidden identity.",
        "suggested_fix": "Move the reveal to the .dm twin."}]})
    proc = run_semantic(["--validate"], stdin=good)
    want(proc.returncode == 0, "validate accepts a schema-valid finding")

    # 4. Schema validation rejects bad severity, bad category, missing key.
    bad = json.dumps([
        {"page": "x.md", "anchor_or_line": "a", "category": "firewall-prose",
         "severity": "blocker", "finding": "f", "suggested_fix": "s"},
        {"page": "y.md", "anchor_or_line": "b", "category": "made-up",
         "severity": "error", "finding": "f", "suggested_fix": "s"},
        {"page": "z.md", "category": "contradiction", "severity": "warning",
         "finding": "f", "suggested_fix": "s"}])
    proc = run_semantic(["--validate"], stdin=bad)
    want(proc.returncode == 1
         and "severity" in proc.stderr and "category" in proc.stderr
         and "anchor_or_line" in proc.stderr,
         "validate rejects bad severity, bad category, and a missing key")

    if failed:
        return 1
    print("verify ok: semantic-review prep + schema validation")
    return 0


# The six keys the finding schema pins; asserted against the packet.
FINDING_KEYS = ("page", "anchor_or_line", "category", "severity",
                "finding", "suggested_fix")


def main():
    return check_reporter() or check_semantic()


if __name__ == "__main__":
    sys.exit(main())
